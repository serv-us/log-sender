#!/bin/bash
set -e

echo "🗑️ Удаление Log Sender..."

# Остановка и удаление сервиса
if systemctl is-active --quiet log-sender; then
    echo "⏹️ Остановка сервиса..."
    sudo systemctl stop log-sender
fi

if systemctl is-enabled --quiet log-sender; then
    echo "🔓 Отключение автозапуска..."
    sudo systemctl disable log-sender
fi

echo "🗑️ Удаление systemd service..."
sudo rm -f /etc/systemd/system/log-sender.service
sudo systemctl daemon-reload

echo "🗑️ Удаление файлов..."
sudo rm -rf /opt/log-sender

echo "🗑️ Удаление logrotate конфига..."
sudo rm -f /etc/logrotate.d/remnanode

echo ""
echo "✅ Удаление завершено!"
echo ""
echo "📝 Логи сохранены в:"
echo "   /var/log/log-sender.log"
echo "   /var/log/log-sender-processed.txt"
echo "   /var/log/log-sender-failed.txt"
echo ""
echo "Удалить логи вручную: sudo rm -f /var/log/log-sender*"
