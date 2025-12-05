#!/bin/bash
echo "╔══════════════════════════════════════════════╗"
echo "║     УСТАНОВКА ТЕЛЕГРАМ БОТА v4.0            ║"
echo "╚══════════════════════════════════════════════╝"

echo "📦 Обновление Termux..."
pkg update -y && pkg upgrade -y

echo "🐍 Установка Python и Git..."
pkg install python python-pip git -y

echo "📦 Установка библиотек..."
pip install telethon colorama

echo "📥 Клонирование репозитория..."
git clone https://github.com/user/tg-mailer-bot.git
cd tg-mailer-bot

echo "🔧 Настройка прав доступа..."
chmod +x install.sh
chmod +x bot.py

echo "✅ Установка завершена!"
echo ""
echo "Для запуска бота:"
echo "1. cd tg-mailer-bot"
echo "2. python bot.py"
echo ""
echo "📱 Получите API ID и Hash на:"
echo "   https://my.telegram.org"
echo ""
echo "⚡ Бот готов к работе!"
