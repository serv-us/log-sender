#!/usr/bin/env python3
import sys
import yaml
import yadisk
from pathlib import Path

def ensure_directory_exists(client, path):
    """Создает директорию рекурсивно на Яндекс.Диске"""
    if client.exists(path):
        return True
    
    parts = [p for p in path.strip('/').split('/') if p]
    for i in range(len(parts)):
        current_path = '/' + '/'.join(parts[:i+1])
        if not client.exists(current_path):
            try:
                client.mkdir(current_path)
                print(f"   ✅ Создана: {current_path}")
            except Exception as e:
                print(f"   ❌ Ошибка создания {current_path}: {e}")
                return False
    
    return client.exists(path)

def test_yandex_disk():
    try:
        with open('config.yaml', 'r') as f:
            config = yaml.safe_load(f)
        
        print("✅ Конфиг загружен успешно")
        
        # Проверка настроек
        enabled = config.get('yandex_disk', {}).get('enabled', False)
        if not enabled:
            print("⚠️ Яндекс.Диск отключен в конфиге (enabled: false)")
            return False
        
        token = config.get('yandex_disk', {}).get('oauth_token')
        upload_path = config.get('yandex_disk', {}).get('upload_path', '/logs')
        
        if not token or token == "YOUR_YANDEX_OAUTH_TOKEN":
            print("❌ Не указан oauth_token в config.yaml")
            print("\n📖 Инструкция по получению токена с полными правами:")
            print("   1. Откройте: https://oauth.yandex.ru/authorize?response_type=token&client_id=23cabbbdc6cd418abb4b39c32c41195d")
            print("   2. Войдите в аккаунт Яндекс")
            print("   3. Разрешите доступ к Яндекс.Диску")
            print("   4. Скопируйте токен из адресной строки (после access_token= до &token_type)")
            print("   5. Вставьте в config.yaml в поле oauth_token")
            print("\n   Подробнее: см. YANDEX_DISK_SETUP.md")
            return False
        
        print(f"✅ OAuth token: {token[:20]}...")
        print(f"✅ Upload path: {upload_path}")
        
        # Проверка подключения
        print("\n🔍 Проверка подключения к Яндекс.Диску...")
        client = yadisk.YaDisk(token=token)
        
        if not client.check_token():
            print("❌ Неверный токен! Получите новый токен.")
            print("   Используйте: https://oauth.yandex.ru/authorize?response_type=token&client_id=23cabbbdc6cd418abb4b39c32c41195d")
            return False
        
        print("✅ Токен валидный!")
        
        # Получение информации о диске
        try:
            disk_info = client.get_disk_info()
            total_space = disk_info.total_space / (1024**3)  # GB
            used_space = disk_info.used_space / (1024**3)  # GB
            free_space = (disk_info.total_space - disk_info.used_space) / (1024**3)  # GB
            
            print(f"\n💾 Информация о диске:")
            print(f"   Всего: {total_space:.2f} ГБ")
            print(f"   Занято: {used_space:.2f} ГБ")
            print(f"   Свободно: {free_space:.2f} ГБ")
        except yadisk.exceptions.ForbiddenError:
            print("\n⚠️ Недостаточно прав для получения информации о диске")
            print("   Это не критично, продолжаем проверку...")
        
        # Проверка/создание директории
        print(f"\n📁 Проверка директории {upload_path}...")
        try:
            if client.exists(upload_path):
                print(f"✅ Директория существует")
                
                # Список файлов
                try:
                    files = list(client.listdir(upload_path))
                    if files:
                        print(f"   Файлов в директории: {len(files)}")
                        print("   Последние 5 файлов:")
                        for item in files[-5:]:
                            size_mb = item.size / (1024**2) if hasattr(item, 'size') and item.size else 0
                            print(f"   - {item.name} ({size_mb:.2f} МБ)")
                    else:
                        print("   Директория пустая")
                except:
                    print("   Не удалось получить список файлов")
            else:
                print(f"⚠️ Директория не существует, создаем...")
                # Создаем директории рекурсивно
                parts = [p for p in upload_path.strip('/').split('/') if p]
                for i in range(len(parts)):
                    current_path = '/' + '/'.join(parts[:i+1])
                    try:
                        if not client.exists(current_path):
                            client.mkdir(current_path)
                            print(f"   ✅ Создана: {current_path}")
                    except yadisk.exceptions.ParentNotFoundError:
                        print(f"   ⚠️ Ошибка создания {current_path}")
                        continue
                    except Exception as e:
                        print(f"   ⚠️ Ошибка: {e}")
                        continue
                
                # Проверяем что директория создана
                if client.exists(upload_path):
                    print(f"✅ Директория создана: {upload_path}")
                else:
                    print(f"❌ Не удалось создать директорию: {upload_path}")
                    return False
        except yadisk.exceptions.ForbiddenError:
            print(f"❌ Недостаточно прав для работы с директорией {upload_path}")
            print("\n🔧 Решение:")
            print("   1. Получите новый токен с полными правами:")
            print("      https://oauth.yandex.ru/authorize?response_type=token&client_id=23cabbbdc6cd418abb4b39c32c41195d")
            print("   2. При авторизации убедитесь, что разрешены:")
            print("      - Чтение всего Диска")
            print("      - Запись в любом месте")
            print("      - Доступ к информации о Диске")
            return False
        except Exception as e:
            print(f"❌ Ошибка при работе с директорией: {e}")
            return False
        
        # Тестовая загрузка
        print("\n📤 Тестовая загрузка файла...")
        test_file = Path("test_upload.txt")
        test_file.write_text("Тестовый файл от Log Sender\nВремя: " + str(Path(__file__).stat().st_mtime))
        
        remote_path = f"{upload_path}/test_upload.txt"
        try:
            client.upload(str(test_file), remote_path, overwrite=True)
            print(f"✅ Файл загружен: {remote_path}")
            
            # Проверка загруженного файла
            if client.exists(remote_path):
                file_info = client.get_meta(remote_path)
                print(f"✅ Файл подтвержден на диске (размер: {file_info.size} байт)")
                
                # Удаление тестового файла
                client.remove(remote_path)
                print(f"🗑️ Тестовый файл удален с диска")
        except yadisk.exceptions.ForbiddenError:
            print(f"❌ Недостаточно прав для загрузки файлов")
            print("   Получите токен с правами записи (см. выше)")
            test_file.unlink()
            return False
        
        # Удаление локального тестового файла
        test_file.unlink()
        print(f"🗑️ Локальный тестовый файл удален")
        
        print("\n🎉 Все проверки пройдены! Яндекс.Диск настроен корректно.")
        return True
        
    except FileNotFoundError:
        print("❌ Файл config.yaml не найден")
        return False
    except yadisk.exceptions.UnauthorizedError:
        print("❌ Ошибка авторизации! Проверьте токен.")
        print("   Получите новый: https://oauth.yandex.ru/authorize?response_type=token&client_id=23cabbbdc6cd418abb4b39c32c41195d")
        return False
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == '__main__':
    success = test_yandex_disk()
    sys.exit(0 if success else 1)
