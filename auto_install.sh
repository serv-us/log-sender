#!/bin/bash
set -e

# Цвета для вывода
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}╔════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║  Log Sender - Автоматическая установка ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════╝${NC}"
echo ""

# Проверка прав root
if [ "$EUID" -ne 0 ]; then 
    echo -e "${RED}❌ Запустите скрипт с правами root: sudo bash auto_install.sh${NC}"
    exit 1
fi

# Обновление системы
echo -e "${YELLOW}📦 Обновление списка пакетов...${NC}"
apt-get update -qq

# Установка необходимых пакетов
echo -e "${YELLOW}📦 Установка необходимых пакетов...${NC}"
# Устанавливаем переменные окружения для неинтерактивной установки
export DEBIAN_FRONTEND=noninteractive
export NEEDRESTART_MODE=a
export NEEDRESTART_SUSPEND=1

# Ждем освобождения apt lock если занят
while fuser /var/lib/dpkg/lock-frontend >/dev/null 2>&1 ; do
    echo -e "${YELLOW}   Ожидание освобождения apt...${NC}"
    sleep 2
done

apt-get install -y -qq -o Dpkg::Options::="--force-confdef" -o Dpkg::Options::="--force-confold" python3 python3-pip python3-venv git > /dev/null 2>&1

# Клонирование репозитория
REPO_URL="https://github.com/serv-us/log-sender.git"
TEMP_DIR="/tmp/log-sender-install-$$"

echo -e "${YELLOW}📥 Клонирование репозитория из GitHub...${NC}"
rm -rf "$TEMP_DIR"
git clone -q "$REPO_URL" "$TEMP_DIR"

# Переход в директорию проекта
cd "$TEMP_DIR"

# Проверка наличия необходимых файлов
echo -e "${YELLOW}🔍 Проверка файлов проекта...${NC}"
REQUIRED_FILES=("log_sender.py" "requirements.txt" "config.yaml.example")
for file in "${REQUIRED_FILES[@]}"; do
    if [ ! -f "$file" ]; then
        echo -e "${RED}❌ Не найден файл: $file${NC}"
        exit 1
    fi
done
echo -e "${GREEN}✓ Все необходимые файлы найдены${NC}"

# Создание директорий
echo -e "${YELLOW}📁 Создание директорий...${NC}"
mkdir -p /var/log/remnanode
mkdir -p /var/log

# Копирование файлов
INSTALL_DIR="/opt/log-sender"
echo -e "${YELLOW}📋 Копирование файлов в $INSTALL_DIR...${NC}"
mkdir -p $INSTALL_DIR
cp log_sender.py $INSTALL_DIR/
cp requirements.txt $INSTALL_DIR/
cp test_config.py $INSTALL_DIR/ 2>/dev/null || true
cp test_yandex_disk.py $INSTALL_DIR/ 2>/dev/null || true
cp uninstall.sh $INSTALL_DIR/ 2>/dev/null || true
chmod +x $INSTALL_DIR/log_sender.py
chmod +x $INSTALL_DIR/uninstall.sh 2>/dev/null || true

# Копирование конфига (если еще не существует)
if [ ! -f "$INSTALL_DIR/config.yaml" ]; then
    echo -e "${YELLOW}📝 Создание config.yaml из примера...${NC}"
    cp config.yaml.example $INSTALL_DIR/config.yaml
else
    echo -e "${YELLOW}⚠️  config.yaml уже существует, пропускаем (сохраняем ваши настройки)${NC}"
    echo -e "   Пример конфига обновлен: $INSTALL_DIR/config.yaml.example"
    cp config.yaml.example $INSTALL_DIR/config.yaml.example
fi

# Создание виртуального окружения
echo -e "${YELLOW}🐍 Создание виртуального окружения...${NC}"
python3 -m venv $INSTALL_DIR/venv

# Установка зависимостей в виртуальное окружение
echo -e "${YELLOW}📦 Установка зависимостей Python...${NC}"
$INSTALL_DIR/venv/bin/pip install -q --upgrade pip
$INSTALL_DIR/venv/bin/pip install -q -r requirements.txt

# Создание systemd service
echo -e "${YELLOW}⚙️  Создание systemd service...${NC}"
tee /etc/systemd/system/log-sender.service > /dev/null <<EOF
[Unit]
Description=Log Sender to Telegram
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=$INSTALL_DIR
ExecStart=$INSTALL_DIR/venv/bin/python $INSTALL_DIR/log_sender.py $INSTALL_DIR/config.yaml
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# Создание logrotate конфига
echo -e "${YELLOW}🔄 Создание logrotate конфига...${NC}"
cat > /etc/logrotate.d/remnanode <<'LOGROTATE_EOF'
/var/log/remnanode/*.log {
    daily
    rotate 5
    compress
    missingok
    notifempty
    copytruncate
    dateext
    dateformat -%Y-%m-%d-%H%M
    extension .log
}
LOGROTATE_EOF

# Очистка временных файлов
echo -e "${YELLOW}🧹 Очистка временных файлов...${NC}"
rm -rf "$TEMP_DIR"

# Перезагрузка systemd
systemctl daemon-reload

echo ""
echo -e "${GREEN}╔════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║  ✅ Установка успешно завершена!      ║${NC}"
echo -e "${GREEN}╚════════════════════════════════════════╝${NC}"
echo ""
echo -e "${BLUE}📝 Следующие шаги:${NC}"
echo ""
echo -e "${YELLOW}1. Отредактируйте конфигурацию:${NC}"
echo -e "   nano $INSTALL_DIR/config.yaml"
echo -e "   ${BLUE}(укажите bot_token и chat_id)${NC}"
echo ""
echo -e "${YELLOW}2. Проверьте настройки Telegram:${NC}"
echo -e "   cd $INSTALL_DIR && ./venv/bin/python test_config.py"
echo ""
echo -e "${YELLOW}3. Запустите сервис:${NC}"
echo -e "   systemctl enable log-sender"
echo -e "   systemctl start log-sender"
echo ""
echo -e "${YELLOW}4. Проверьте статус:${NC}"
echo -e "   systemctl status log-sender"
echo ""
echo -e "${YELLOW}5. Просмотр логов:${NC}"
echo -e "   journalctl -u log-sender -f"
echo -e "   tail -f /var/log/log-sender.log"
echo ""
