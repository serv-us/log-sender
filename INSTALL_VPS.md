# Автоматическая установка на VPS Ubuntu

## Установка одной командой

```bash
curl -fsSL https://raw.githubusercontent.com/serv-us/log-sender/main/auto_install.sh | sudo bash
```

Или с wget:

```bash
wget -qO- https://raw.githubusercontent.com/serv-us/log-sender/main/auto_install.sh | sudo bash
```

Это всё! Скрипт автоматически выполнит полную установку.

## Что делает скрипт

1. ✅ Проверяет права root
2. 📦 Обновляет систему и устанавливает зависимости (Python 3, Git)
3. 📥 Клонирует проект с GitHub
4. 🔍 Проверяет наличие всех необходимых файлов
5. 📁 Создает директории `/opt/log-sender` и `/var/log/remnanode`
6. 📋 Копирует файлы проекта
7. 🐍 Создает виртуальное окружение Python
8. 📦 Устанавливает зависимости (requests, PyYAML, watchdog, yadisk)
9. ⚙️ Создает systemd сервис
10. 🔄 Настраивает logrotate
11. 🧹 Очищает временные файлы

Никаких вопросов - всё автоматически!

## После установки

### 1. Настройте конфигурацию
```bash
nano /opt/log-sender/config.yaml
```
Укажите `bot_token` и `chat_id` для Telegram.

### 2. Проверьте настройки
```bash
cd /opt/log-sender && ./venv/bin/python test_config.py
```

### 3. Запустите сервис
```bash
systemctl enable log-sender
systemctl start log-sender
```

### 4. Проверьте статус
```bash
systemctl status log-sender
```

## Требования

- Ubuntu 18.04+ (или другой Debian-based дистрибутив)
- Права root (sudo)
- Интернет-соединение

## Устранение проблем

### Ошибка: "Permission denied"
```bash
chmod +x auto_install.sh
sudo bash auto_install.sh
```

### Ошибка: "git: command not found"
Скрипт автоматически установит git, но если возникла ошибка:
```bash
sudo apt-get update
sudo apt-get install -y git
```

### Проверка логов после установки
```bash
journalctl -u log-sender -f
tail -f /var/log/log-sender.log
```

## Удаление

Для удаления используйте:
```bash
cd /opt/log-sender
sudo bash uninstall.sh
```

Или вручную:
```bash
sudo systemctl stop log-sender
sudo systemctl disable log-sender
sudo rm /etc/systemd/system/log-sender.service
sudo rm -rf /opt/log-sender
sudo systemctl daemon-reload
```
