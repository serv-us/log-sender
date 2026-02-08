#!/usr/bin/env python3
"""
Скрипт для проверки конфигурации и подключения к Telegram
"""
import sys
import yaml
import requests

def test_config():
    try:
        with open('config.yaml', 'r') as f:
            config = yaml.safe_load(f)
        
        print("✅ Конфиг загружен успешно")
        
        # Проверка обязательных полей
        bot_token = config.get('telegram', {}).get('bot_token')
        chat_id = config.get('telegram', {}).get('chat_id')
        
        if not bot_token or bot_token == "YOUR_BOT_TOKEN_HERE":
            print("❌ Не указан bot_token в config.yaml")
            return False
        
        if not chat_id:
            print("❌ Не указан chat_id в config.yaml")
            return False
        
        print(f"✅ Bot token: {bot_token[:10]}...")
        print(f"✅ Chat ID: {chat_id}")
        
        # Проверка подключения к Telegram
        print("\n🔍 Проверка подключения к Telegram...")
        url = f"https://api.telegram.org/bot{bot_token}/getMe"
        response = requests.get(url, timeout=10)
        
        if response.status_code == 200 and response.json().get('ok'):
            bot_info = response.json()['result']
            print(f"✅ Бот подключен: @{bot_info['username']}")
        else:
            print(f"❌ Ошибка подключения к боту: {response.text}")
            return False
        
        # Тестовая отправка сообщения
        print("\n📤 Отправка тестового сообщения...")
        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        data = {
            'chat_id': chat_id,
            'text': '🧪 Тестовое сообщение от Log Sender\n\nКонфигурация работает корректно!'
        }
        
        thread_id = config.get('telegram', {}).get('message_thread_id')
        if thread_id:
            data['message_thread_id'] = thread_id
            print(f"📌 Отправка в топик: {thread_id}")
        
        response = requests.post(url, data=data, timeout=10)
        
        if response.status_code == 200 and response.json().get('ok'):
            print("✅ Тестовое сообщение отправлено успешно!")
            print("\n🎉 Все проверки пройдены! Конфигурация корректна.")
            return True
        else:
            print(f"❌ Ошибка отправки сообщения: {response.text}")
            return False
            
    except FileNotFoundError:
        print("❌ Файл config.yaml не найден")
        return False
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        return False

if __name__ == '__main__':
    success = test_config()
    sys.exit(0 if success else 1)
