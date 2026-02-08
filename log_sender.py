#!/usr/bin/env python3
import os
import sys
import time
import logging
import socket
from pathlib import Path
from datetime import datetime
import requests
import yaml
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import fnmatch
import json
import yadisk

def ensure_directory_exists(client, path, logger=None):
    """Создает директорию рекурсивно на Яндекс.Диске"""
    if client.exists(path):
        return True
    
    parts = [p for p in path.strip('/').split('/') if p]
    for i in range(len(parts)):
        current_path = '/' + '/'.join(parts[:i+1])
        if not client.exists(current_path):
            try:
                client.mkdir(current_path)
                if logger:
                    logger.info(f"📁 Создана директория на Яндекс.Диске: {current_path}")
            except Exception as e:
                if logger:
                    logger.error(f"❌ Ошибка создания {current_path}: {e}")
                return False
    
    return client.exists(path)

class Config:
    def __init__(self, config_path='config.yaml'):
        with open(config_path, 'r') as f:
            self.data = yaml.safe_load(f)
    
    def get(self, *keys, default=None):
        value = self.data
        for key in keys:
            if isinstance(value, dict):
                value = value.get(key, default)
            else:
                return default
        return value

class LogSender:
    def __init__(self, config):
        self.config = config
        
        # Telegram настройки
        self.telegram_enabled = config.get('telegram', 'enabled', default=True)
        self.bot_token = config.get('telegram', 'bot_token')
        self.chat_id = config.get('telegram', 'chat_id')
        self.thread_id = config.get('telegram', 'message_thread_id')
        
        # Настройки уведомлений
        self.notifications_enabled = config.get('telegram', 'notifications', 'enabled', default=True)
        self.notifications_chat_id = config.get('telegram', 'notifications', 'chat_id') or self.chat_id
        self.notifications_thread_id = config.get('telegram', 'notifications', 'message_thread_id')
        if self.notifications_thread_id is None:
            self.notifications_thread_id = self.thread_id
        
        # Яндекс.Диск настройки
        self.ydisk_enabled = config.get('yandex_disk', 'enabled', default=False)
        self.ydisk_token = config.get('yandex_disk', 'oauth_token')
        self.ydisk_path = config.get('yandex_disk', 'upload_path', default='/logs')
        self.ydisk_delete_after = config.get('yandex_disk', 'delete_after_upload', default=False)
        self.ydisk_notify = config.get('yandex_disk', 'notifications', 'enabled', default=True)
        self.ydisk_include_link = config.get('yandex_disk', 'notifications', 'include_link', default=True)
        self.ydisk_client = None
        
        # Инициализация Яндекс.Диск клиента
        if self.ydisk_enabled:
            try:
                self.ydisk_client = yadisk.YaDisk(token=self.ydisk_token)
                if self.ydisk_client.check_token():
                    # Создаем директорию если не существует (рекурсивно)
                    if not self.ydisk_client.exists(self.ydisk_path):
                        logging.info(f"📁 Создание директории на Яндекс.Диске: {self.ydisk_path}")
                        if not ensure_directory_exists(self.ydisk_client, self.ydisk_path):
                            logging.error(f"❌ Не удалось создать директорию: {self.ydisk_path}")
                else:
                    self.ydisk_enabled = False
                    logging.warning("⚠️ Яндекс.Диск: неверный токен, отправка отключена")
            except Exception as e:
                self.ydisk_enabled = False
                logging.error(f"❌ Ошибка инициализации Яндекс.Диск: {e}")
        
        self.server_name = config.get('server', 'name')
        self.server_ip = config.get('server', 'ip') or self._get_server_ip()
        self.watch_dir = Path(config.get('logs', 'watch_dir'))
        self.patterns = config.get('logs', 'patterns', default=[])
        self.max_size_mb = config.get('upload', 'max_size_mb', default=47)
        self.delay = config.get('upload', 'delay_after_detection', default=5)
        self.pause = config.get('upload', 'pause_between_parts', default=0.3)
        self.pause_before_ydisk = config.get('upload', 'pause_before_ydisk', default=3)
        
        # Настройки повторных попыток
        self.max_attempts = config.get('upload', 'retry', 'max_attempts', default=3)
        self.retry_delay = config.get('upload', 'retry', 'delay_between_attempts', default=2)
        self.retry_later_delay = config.get('upload', 'retry', 'retry_later_delay', default=300)
        self.max_retry_later = config.get('upload', 'retry', 'max_retry_later_attempts', default=5)
        
        self.processed_file = Path(config.get('script', 'processed_files'))
        self.failed_file = Path(config.get('script', 'failed_files'))
        
        # Настройка логирования
        log_file = config.get('script', 'log_file')
        os.makedirs(os.path.dirname(log_file), exist_ok=True)
        
        logging.basicConfig(
            level=logging.INFO,
            format='[%(asctime)s] %(message)s',
            handlers=[
                logging.FileHandler(log_file),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)
        
        # Загрузка истории
        self.processed = self._load_processed()
        self.failed_queue = self._load_failed_queue()
    
    def _get_server_ip(self):
        """Определяет внешний IP-адрес сервера"""
        try:
            # Пробуем получить внешний IP
            response = requests.get('https://api.ipify.org?format=json', timeout=5)
            return response.json().get('ip', 'Unknown')
        except:
            try:
                # Запасной вариант - локальный IP
                s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                s.connect(("8.8.8.8", 80))
                ip = s.getsockname()[0]
                s.close()
                return ip
            except:
                return 'Unknown'
    
    def _load_processed(self):
        """Загружает список уже отправленных файлов"""
        if self.processed_file.exists():
            with open(self.processed_file, 'r') as f:
                return set(line.strip() for line in f)
        return set()
    
    def _mark_processed(self, filepath):
        """Отмечает файл как обработанный"""
        self.processed.add(str(filepath))
        os.makedirs(self.processed_file.parent, exist_ok=True)
        with open(self.processed_file, 'a') as f:
            f.write(f"{filepath}\n")
    
    def _load_failed_queue(self):
        """Загружает очередь неудачных отправок"""
        if self.failed_file.exists():
            with open(self.failed_file, 'r') as f:
                try:
                    return json.load(f)
                except:
                    return []
        return []
    
    def _save_failed_queue(self):
        """Сохраняет очередь неудачных отправок"""
        os.makedirs(self.failed_file.parent, exist_ok=True)
        with open(self.failed_file, 'w') as f:
            json.dump(self.failed_queue, f, indent=2)
    
    def _add_to_failed_queue(self, filepath, parts=None):
        """Добавляет файл в очередь неудачных отправок"""
        entry = {
            'filepath': str(filepath),
            'parts': parts or [],
            'attempts': 0,
            'last_attempt': datetime.now().isoformat(),
            'next_retry': (datetime.now().timestamp() + self.retry_later_delay)
        }
        self.failed_queue.append(entry)
        self._save_failed_queue()
        self.logger.warning(f"⏰ Файл добавлен в очередь повторной отправки: {filepath}")
    
    def _remove_from_failed_queue(self, filepath):
        """Удаляет файл из очереди неудачных отправок"""
        self.failed_queue = [e for e in self.failed_queue if e['filepath'] != str(filepath)]
        self._save_failed_queue()
    
    def _matches_pattern(self, filename):
        """Проверяет, соответствует ли файл одному из паттернов"""
        return any(fnmatch.fnmatch(filename, pattern) for pattern in self.patterns)
    
    def _split_file(self, filepath):
        """Разбивает файл на части по max_size_mb"""
        parts = []
        max_bytes = self.max_size_mb * 1024 * 1024
        
        with open(filepath, 'rb') as f:
            part_num = 0
            while True:
                chunk = f.read(max_bytes)
                if not chunk:
                    break
                
                part_path = f"{filepath}.part{part_num:02d}"
                with open(part_path, 'wb') as part_file:
                    part_file.write(chunk)
                parts.append(part_path)
                part_num += 1
        
        return parts
    
    def _send_message(self, text, use_notification_chat=False):
        """Отправляет текстовое сообщение в Telegram с повторными попытками
        
        Args:
            text: Текст сообщения
            use_notification_chat: Использовать ли настройки чата для уведомлений
        """
        if not self.telegram_enabled:
            return True
        
        # Проверка, включены ли уведомления
        if use_notification_chat and not self.notifications_enabled:
            return True
            
        url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
        
        # Выбираем chat_id и thread_id в зависимости от типа сообщения
        if use_notification_chat:
            chat_id = self.notifications_chat_id
            thread_id = self.notifications_thread_id
        else:
            chat_id = self.chat_id
            thread_id = self.thread_id
        
        data = {
            'chat_id': chat_id,
            'text': text,
            'parse_mode': 'HTML'
        }
        if thread_id:
            data['message_thread_id'] = thread_id
        
        for attempt in range(1, self.max_attempts + 1):
            try:
                response = requests.post(url, data=data, timeout=30)
                if response.json().get('ok', False):
                    return True
                self.logger.warning(f"⚠️ Попытка {attempt}/{self.max_attempts} отправки сообщения не удалась")
            except Exception as e:
                self.logger.error(f"❌ Ошибка отправки сообщения (попытка {attempt}/{self.max_attempts}): {e}")
            
            if attempt < self.max_attempts:
                time.sleep(self.retry_delay)
        
        return False
    
    def _send_document(self, filepath):
        """Отправляет файл в Telegram с повторными попытками"""
        if not self.telegram_enabled:
            return True
            
        url = f"https://api.telegram.org/bot{self.bot_token}/sendDocument"
        data = {'chat_id': self.chat_id}
        if self.thread_id:
            data['message_thread_id'] = self.thread_id
        
        for attempt in range(1, self.max_attempts + 1):
            try:
                with open(filepath, 'rb') as f:
                    files = {'document': f}
                    response = requests.post(url, data=data, files=files, timeout=120)
                    if response.json().get('ok', False):
                        return True
                self.logger.warning(f"⚠️ Попытка {attempt}/{self.max_attempts} отправки файла не удалась")
            except Exception as e:
                self.logger.error(f"❌ Ошибка отправки файла (попытка {attempt}/{self.max_attempts}): {e}")
            
            if attempt < self.max_attempts:
                time.sleep(self.retry_delay)
        
        return False
    
    def _upload_to_yandex_disk(self, filepath):
        """Загружает файл на Яндекс.Диск с повторными попытками"""
        if not self.ydisk_enabled or not self.ydisk_client:
            return True
        
        filename = Path(filepath).name
        remote_path = f"{self.ydisk_path}/{filename}"
        
        for attempt in range(1, self.max_attempts + 1):
            try:
                # Проверяем, существует ли файл
                if self.ydisk_client.exists(remote_path):
                    self.logger.info(f"📁 Файл уже существует на Яндекс.Диске, перезаписываем: {filename}")
                    self.ydisk_client.remove(remote_path)
                
                # Загружаем файл
                self.ydisk_client.upload(filepath, remote_path)
                self.logger.info(f"☁️ Загружено на Яндекс.Диск: {filename}")
                
                # Отправляем уведомление о загрузке
                if self.ydisk_notify and self.notifications_enabled:
                    self._send_ydisk_notification(filename, remote_path, Path(filepath).stat().st_size)
                
                return True
                
            except yadisk.exceptions.PathNotFoundError:
                # Создаем директорию если не существует (рекурсивно)
                self.logger.info(f"📁 Директория не найдена, создаем: {self.ydisk_path}")
                if ensure_directory_exists(self.ydisk_client, self.ydisk_path, self.logger):
                    # Повторяем попытку загрузки
                    continue
                else:
                    self.logger.error(f"❌ Не удалось создать директорию: {self.ydisk_path}")
                    
            except Exception as e:
                self.logger.error(f"❌ Ошибка загрузки на Яндекс.Диск (попытка {attempt}/{self.max_attempts}): {e}")
            
            if attempt < self.max_attempts:
                time.sleep(self.retry_delay)
        
        return False
    
    def _send_ydisk_notification(self, filename, remote_path, file_size):
        """Отправляет уведомление о загрузке файла на Яндекс.Диск"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        file_size_mb = file_size / (1024 * 1024)
        
        message = f"☁️ Файл загружен на Яндекс.Диск\n\n"
        message += f"🖥️ Сервер: {self.server_name}\n"
        message += f"🌐 IP: <code>{self.server_ip}</code>\n"
        message += f"🗓️ Дата: {timestamp}\n"
        message += f"📦 Файл: <code>{filename}</code>\n"
        message += f"📊 Размер: {file_size_mb:.2f} МБ\n"
        message += f"📁 Путь: <code>{remote_path}</code>"
        
        # Добавляем ссылку на файл если включено
        if self.ydisk_include_link:
            try:
                # Получаем публичную ссылку (если файл опубликован) или создаем временную
                publish_info = self.ydisk_client.publish(remote_path)
                public_url = publish_info.href if hasattr(publish_info, 'href') else None
                
                if public_url:
                    message += f"\n🔗 <a href='{public_url}'>Открыть файл</a>"
            except:
                # Если не удалось получить ссылку, просто пропускаем
                pass
        
        self._send_message(message, use_notification_chat=True)
    
    def process_file(self, filepath, is_retry=False):
        """Обрабатывает и отправляет файл"""
        filepath = Path(filepath)
        
        # Проверка, не обработан ли уже
        if not is_retry and str(filepath) in self.processed:
            self.logger.info(f"⏭️ Файл уже обработан: {filepath.name}")
            return
        
        # Проверка существования
        if not filepath.exists():
            self.logger.warning(f"⚠️ Файл не найден: {filepath}")
            return
        
        # Проверка паттерна
        if not self._matches_pattern(filepath.name):
            self.logger.info(f"⏭️ Файл не соответствует паттернам: {filepath.name}")
            return
        
        self.logger.info(f"📦 {'Повторная обработка' if is_retry else 'Обнаружен новый архив'}: {filepath.name}")
        
        # Отсрочка перед отправкой
        if self.delay > 0 and not is_retry:
            self.logger.info(f"⏳ Ожидание {self.delay} сек перед отправкой...")
            time.sleep(self.delay)
        
        # Проверка размера и разбиение (только для Telegram)
        file_size_mb = filepath.stat().st_size / (1024 * 1024)
        files_to_send = []
        parts_created = []
        need_split = False
        
        # Разбиваем только если включен Telegram и файл превышает лимит
        if self.telegram_enabled and file_size_mb > self.max_size_mb:
            need_split = True
            self.logger.info(f"⚠️ Файл {file_size_mb:.1f} МБ превышает лимит Telegram, разбиваем...")
            parts = self._split_file(filepath)
            files_to_send = parts
            parts_created = parts
            self.logger.info(f"✂️ Создано частей для Telegram: {len(parts)}")
        else:
            files_to_send = [str(filepath)]
            if file_size_mb > self.max_size_mb:
                self.logger.info(f"ℹ️ Файл {file_size_mb:.1f} МБ больше {self.max_size_mb} МБ, но разбиение не требуется (Telegram отключен)")
        
        # Отправка уведомления
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        destinations = []
        if self.telegram_enabled:
            destinations.append("Telegram")
        if self.ydisk_enabled:
            destinations.append("Яндекс.Диск")
        
        message = f"📤 Логи с сервера: {self.server_name}\n"
        message += f"🌐 IP: <code>{self.server_ip}</code>\n"
        message += f"🗓️ Дата: {timestamp}\n"
        message += f"📦 Файл: <code>{filepath.name}</code>\n"
        message += f"📊 Размер: {file_size_mb:.2f} МБ\n"
        message += f"📁 Частей: {len(files_to_send)}\n"
        message += f"🎯 Отправка: {', '.join(destinations)}"
        
        if not self._send_message(message):
            self.logger.error("❌ Не удалось отправить уведомление")
        
        # Отправка файлов
        all_success = True
        telegram_success = True
        ydisk_success = True
        
        # Отправка в Telegram (с разбиением если нужно)
        if self.telegram_enabled:
            for idx, file_path in enumerate(files_to_send, 1):
                part_info = f"части {idx}/{len(files_to_send)}" if need_split else "файла"
                self.logger.info(f"📤 Отправка {part_info} в Telegram: {Path(file_path).name}")
                
                if self._send_document(file_path):
                    self.logger.info(f"✅ Telegram: {Path(file_path).name}")
                else:
                    self.logger.error(f"❌ Telegram не удалось: {Path(file_path).name}")
                    telegram_success = False
                    all_success = False
                    break  # Прерываем отправку остальных частей
                
                # Удаляем часть после успешной отправки (только если это разбитый файл)
                if need_split and file_path != str(filepath):
                    try:
                        os.remove(file_path)
                        self.logger.info(f"🗑️ Удалена часть: {Path(file_path).name}")
                    except Exception as e:
                        self.logger.error(f"❌ Не удалось удалить часть {file_path}: {e}")
                
                # Пауза между частями
                if idx < len(files_to_send):
                    time.sleep(self.pause)
        
        # Пауза между Telegram и Яндекс.Диском
        if self.telegram_enabled and self.ydisk_enabled and telegram_success:
            self.logger.info(f"⏳ Пауза {self.pause_before_ydisk} сек перед загрузкой на Яндекс.Диск...")
            time.sleep(self.pause_before_ydisk)
        
        # Загрузка на Яндекс.Диск (всегда целый файл, без разбиения)
        if self.ydisk_enabled:
            self.logger.info(f"☁️ Загрузка на Яндекс.Диск: {filepath.name}")
            if self._upload_to_yandex_disk(str(filepath)):
                self.logger.info(f"✅ Яндекс.Диск: {filepath.name}")
            else:
                self.logger.error(f"❌ Яндекс.Диск не удалось: {filepath.name}")
                ydisk_success = False
                all_success = False
        
        if all_success:
            # Отмечаем как обработанный
            self._mark_processed(filepath)
            # Удаляем из очереди неудачных, если был там
            self._remove_from_failed_queue(filepath)
            
            # Удаляем оригинальный файл если настроено
            if self.ydisk_enabled and self.ydisk_delete_after and ydisk_success:
                try:
                    if filepath.exists():
                        os.remove(filepath)
                        self.logger.info(f"🗑️ Файл удален после загрузки: {filepath.name}")
                except Exception as e:
                    self.logger.error(f"❌ Не удалось удалить файл {filepath}: {e}")
            
            self.logger.info(f"✅ Обработка завершена: {filepath.name}")
        else:
            # Добавляем в очередь повторной отправки
            self._add_to_failed_queue(filepath, parts_created)
            self.logger.error(f"❌ Файл не доставлен, будет повторная попытка позже")
    
    def retry_failed_files(self):
        """Повторяет отправку файлов из очереди неудачных"""
        current_time = datetime.now().timestamp()
        
        for entry in self.failed_queue[:]:  # Копия списка для безопасной итерации
            if entry['next_retry'] <= current_time:
                filepath = Path(entry['filepath'])
                entry['attempts'] += 1
                
                if entry['attempts'] > self.max_retry_later:
                    self.logger.error(f"❌ Превышено максимальное количество попыток для {filepath.name}")
                    self._remove_from_failed_queue(filepath)
                    # Удаляем части, если они были созданы
                    for part in entry.get('parts', []):
                        try:
                            if os.path.exists(part):
                                os.remove(part)
                        except:
                            pass
                    continue
                
                self.logger.info(f"🔄 Повторная попытка {entry['attempts']}/{self.max_retry_later} для {filepath.name}")
                self.process_file(filepath, is_retry=True)
                
                # Обновляем время следующей попытки
                entry['last_attempt'] = datetime.now().isoformat()
                entry['next_retry'] = current_time + self.retry_later_delay
                self._save_failed_queue()

class LogRotateHandler(FileSystemEventHandler):
    def __init__(self, sender):
        self.sender = sender
    
    def on_created(self, event):
        if event.is_directory:
            return
        
        filepath = Path(event.src_path)
        if self.sender._matches_pattern(filepath.name):
            self.sender.logger.info(f"🔔 Обнаружен новый файл: {filepath.name}")
            self.sender.process_file(filepath)

def main():
    if len(sys.argv) > 1:
        config_path = sys.argv[1]
    else:
        config_path = 'config.yaml'
    
    try:
        config = Config(config_path)
        sender = LogSender(config)
        
        sender.logger.info("🚀 Запуск мониторинга логов...")
        sender.logger.info(f"📁 Директория: {sender.watch_dir}")
        sender.logger.info(f"🌐 IP сервера: {sender.server_ip}")
        sender.logger.info(f"🔍 Паттерны: {', '.join(sender.patterns)}")
        sender.logger.info(f"📤 Telegram: {'✅ включен' if sender.telegram_enabled else '❌ выключен'}")
        sender.logger.info(f"🔔 Уведомления: {'✅ включены' if sender.notifications_enabled else '❌ выключены'}")
        if sender.notifications_enabled and sender.notifications_chat_id != sender.chat_id:
            sender.logger.info(f"   └─ Отдельный чат для уведомлений: {sender.notifications_chat_id}")
        sender.logger.info(f"☁️ Яндекс.Диск: {'✅ включен' if sender.ydisk_enabled else '❌ выключен'}")
        if sender.ydisk_enabled:
            sender.logger.info(f"   └─ Уведомления о загрузке: {'✅ включены' if sender.ydisk_notify else '❌ выключены'}")
        
        # Проверка существующих файлов при запуске
        for pattern in sender.patterns:
            for filepath in sender.watch_dir.glob(pattern):
                sender.process_file(filepath)
        
        # Запуск мониторинга
        event_handler = LogRotateHandler(sender)
        observer = Observer()
        observer.schedule(event_handler, str(sender.watch_dir), recursive=False)
        observer.start()
        
        sender.logger.info("👀 Мониторинг активен. Нажмите Ctrl+C для остановки.")
        
        try:
            retry_check_interval = 60  # Проверяем очередь каждую минуту
            last_retry_check = time.time()
            
            while True:
                time.sleep(1)
                
                # Периодическая проверка очереди неудачных отправок
                if time.time() - last_retry_check >= retry_check_interval:
                    if sender.failed_queue:
                        sender.logger.info(f"🔍 Проверка очереди неудачных отправок ({len(sender.failed_queue)} файлов)")
                        sender.retry_failed_files()
                    last_retry_check = time.time()
                    
        except KeyboardInterrupt:
            observer.stop()
            sender.logger.info("🛑 Остановка мониторинга...")
        
        observer.join()
        
    except Exception as e:
        logging.error(f"❌ Критическая ошибка: {e}")
        import traceback
        logging.error(traceback.format_exc())
        sys.exit(1)

if __name__ == '__main__':
    main()
