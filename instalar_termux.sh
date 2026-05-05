#!/bin/bash
# =============================================
# Pick Cuba Bet - Instalador para Termux
# =============================================

echo "🇨🇺 Instalando Pick Cuba Bot..."

pkg update -y && pkg upgrade -y
pkg install -y python git

pip install --upgrade pip
pip install python-telegram-bot==21.6 aiohttp==3.9.5 APScheduler==3.10.4 pytz==2024.1

echo ""
echo "✅ Instalación completada."
echo ""
echo "Ahora crea un archivo .env con tus tokens:"
echo "  TELEGRAM_BOT_TOKEN=tu_token"
echo "  API_FOOTBALL_KEY=tu_clave"
echo ""
echo "Luego ejecuta: python bot.py"
