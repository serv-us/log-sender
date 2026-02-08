# Log Sender to Telegram

Автоматическая отправка ротированных логов в Telegram и на Яндекс.Диск с поддержкой разбиения больших файлов и повторных попыток.

## Возможности

- 📦 Мониторинг директории логов и автоматическая отправка после ротации
- 📤 Отправка в Telegram (с поддержкой топиков)
- ☁️ Загрузка на Яндекс.Диск через API
- ✂️ Автоматическое разбиение файлов >47 МБ на части
- 🔄 Повторные попытки при ошибках отправки
- 🌐 Определение IP-адреса сервера
- ⏰ Настраиваемая отсрочка перед отправкой
- 📊 Детальное логирование всех операций

## Установка

### Автоматическая установка на VPS Ubuntu

Установка одной командой:

```bash
curl -fsSL https://raw.githubusercontent.com/serv-us/log-sender/main/auto_install.sh | sudo bash
```

Или с wget:

```bash
wget -qO- https://raw.githubusercontent.com/serv-us/log-sender/main/auto_install.sh | sudo bash
```

Скрипт автоматически:
- Установит все зависимости (Python, Git)
- Скачает проект с GitHub
- Настроит виртуальное окружение
- Создаст systemd сервис
- Настроит logrotate

Подробнее: [INSTALL_VPS.md](INSTALL_VPS.md)

## Настройка

### Telegram

Отредактируйте `config.yaml`:

```yaml
telegram:
  enabled: true
  bot_token: "YOUR_BOT_TOKEN"  # Токен бота от @BotFather
  chat_id: "-1001234567890"     # ID чата/группы для отправки файлов
  message_thread_id: null       # ID топика (опционально)
  
  # Настройки уведомлений (можно указать другую группу/топик)
  notifications:
    enabled: true  # включить/выключить уведомления
    chat_id: null  # ID чата для уведомлений (null = использовать основной)
    message_thread_id: null  # ID топика для уведомлений
```

**Примеры конфигурации уведомлений:**

1. **Уведомления в тот же чат:**
```yaml
notifications:
  enabled: true
  chat_id: null  # используется основной chat_id
```

2. **Уведомления в другую группу:**
```yaml
notifications:
  enabled: true
  chat_id: "-1009876543210"  # другая группа
  message_thread_id: null
```

3. **Уведомления в другой топик той же группы:**
```yaml
telegram:
  chat_id: "-1001234567890"
  message_thread_id: 123  # топик для файлов
  
  notifications:
    enabled: true
    chat_id: null  # та же группа
    message_thread_id: 456  # другой топик для уведомлений
```

4. **Отключить уведомления:**
```yaml
notifications:
  enabled: false
```

#### Получение chat_id

1. Добавьте бота в группу
2. Отправьте сообщение в группу
3. Откройте: `https://api.telegram.org/botYOUR_TOKEN/getUpdates`
4. Найдите `chat.id`

#### Получение message_thread_id (для топиков)

1. Отправьте сообщение в топик
2. Откройте: `https://api.telegram.org/botYOUR_TOKEN/getUpdates`
3. Найдите `message_thread_id`

### Яндекс.Диск

```yaml
yandex_disk:
  enabled: true
  oauth_token: "y0_AgAAAAA..."  # OAuth токен
  upload_path: "/logs"
  delete_after_upload: false
  
  # Уведомления о загрузке
  notifications:
    enabled: true  # отправлять ли уведомления в Telegram
    include_link: true  # включать ли публичную ссылку на файл
```

**Уведомления о загрузке на Яндекс.Диск:**
- Отправляются в Telegram (в чат для уведомлений)
- Содержат информацию о файле, размере, пути
- Могут включать публичную ссылку на файл
- Можно отключить независимо от основных уведомлений

**Получение OAuth токена:**

Подробнее: [YANDEX_DISK_SETUP.md](YANDEX_DISK_SETUP.md)

## Использование

### Проверка конфигурации

```bash
# Проверка Telegram
python3 test_config.py

# Проверка Яндекс.Диска
python3 test_yandex_disk.py
```

### Запуск сервиса

```bash
sudo systemctl start log-sender
sudo systemctl enable log-sender  # Автозапуск
```

### Проверка статуса

```bash
sudo systemctl status log-sender
```

### Просмотр логов

```bash
# Системные логи
sudo journalctl -u log-sender -f

# Логи приложения
tail -f /var/log/log-sender.log
```

### Остановка

```bash
sudo systemctl stop log-sender
```

## Logrotate конфигурация

Файл `/etc/logrotate.d/remnanode`:

```
/var/log/remnanode/*.log {
    daily
    rotate 5
    compress
    missingok
    notifempty
    copytruncate
    dateext
    dateformat -%Y-%m-%d-%H%M
}
```

## Обработка ошибок

Скрипт автоматически:
- Делает 3 попытки отправки сразу (с паузой 2 сек)
- При неудаче добавляет файл в очередь повторной отправки
- Повторяет попытку через 5 минут
- Максимум 5 отложенных попыток

Настройки в `config.yaml`:
```yaml
upload:
  retry:
    max_attempts: 3
    delay_between_attempts: 2
    retry_later_delay: 300
    max_retry_later_attempts: 5
```

## Режимы работы

### Только Telegram
```yaml
telegram:
  enabled: true
yandex_disk:
  enabled: false
```

### Только Яндекс.Диск
```yaml
telegram:
  enabled: false
yandex_disk:
  enabled: true
```

### Оба сервиса
```yaml
telegram:
  enabled: true
yandex_disk:
  enabled: true
```

## Структура проекта

```
log-sender/
├── log_sender.py           # Основной скрипт
├── config.yaml.example     # Пример конфигурации
├── requirements.txt        # Зависимости
├── auto_install.sh         # Скрипт автоматической установки
├── uninstall.sh            # Удаление
├── test_config.py          # Проверка Telegram
├── test_yandex_disk.py     # Проверка Яндекс.Диска
├── README.md               # Документация
├── INSTALL_VPS.md          # Инструкция по установке на VPS
├── YANDEX_DISK_SETUP.md    # Настройка Яндекс.Диска
└── .gitignore
```

**Примечание:** При установке `config.yaml.example` копируется в `config.yaml`. Если `config.yaml` уже существует, он не перезаписывается (сохраняются ваши настройки).

## Требования

- Python 3.6+
- requests
- PyYAML
- watchdog
- yadisk

## Безопасность

⚠️ **Важно:**
- Не публикуйте токены в открытых репозиториях
- Используйте права доступа: `chmod 600 config.yaml`
- Храните config.yaml в безопасном месте

## Лицензия

MIT
