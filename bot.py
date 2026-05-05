import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from datetime import datetime
import pytz

from config import TELEGRAM_BOT_TOKEN, CUBA_TZ
from analyzer import get_daily_picks

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler(timezone=CUBA_TZ)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("🎯 Picks de Hoy", callback_data="picks_hoy")],
        [InlineKeyboardButton("⚽ Solo Fútbol", callback_data="picks_futbol"),
         InlineKeyboardButton("🏀 Solo Baloncesto", callback_data="picks_basket")],
        [InlineKeyboardButton("⚾ Solo Béisbol", callback_data="picks_beisbol")],
        [InlineKeyboardButton("ℹ️ Ayuda", callback_data="ayuda")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    msg = (
        "🇨🇺 *Pick Cuba Bet* 🎯\n\n"
        "Bienvenido al bot de análisis de apuestas deportivas.\n"
        "Obtengo los partidos del día en horario de Cuba, analizo estadísticas "
        "y te doy las mejores picks con tipo de apuesta recomendado.\n\n"
        "Selecciona una opción:"
    )
    await update.message.reply_text(msg, parse_mode="Markdown", reply_markup=reply_markup)

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    data = query.data
    sport_map = {
        "picks_hoy": None,
        "picks_futbol": "soccer",
        "picks_basket": "basketball",
        "picks_beisbol": "baseball",
    }

    if data == "ayuda":
        msg = (
            "ℹ️ *Cómo funciona Pick Cuba Bet*\n\n"
            "1️⃣ Obtengo partidos del día en horario de Cuba (UTC-5)\n"
            "2️⃣ Analizo estadísticas de cada equipo: forma reciente, goles/puntos, head-to-head\n"
            "3️⃣ Evalúo el mejor tipo de apuesta: 1X2, Over/Under, BTTS, Handicap\n"
            "4️⃣ Solo muestro picks con confianza alta (≥65%)\n\n"
            "🟢 Alta confianza: 75%+\n"
            "🟡 Media confianza: 65-74%\n\n"
            "⚠️ Las picks son análisis estadístico, no garantía de resultado."
        )
        await query.edit_message_text(msg, parse_mode="Markdown")
        return

    if data in sport_map:
        sport_filter = sport_map[data]
        sport_label = {
            "picks_hoy": "Todos los Deportes",
            "picks_futbol": "Fútbol ⚽",
            "picks_basket": "Baloncesto 🏀",
            "picks_beisbol": "Béisbol ⚾",
        }[data]

        await query.edit_message_text(
            f"⏳ Analizando partidos de *{sport_label}*...\nEsto puede tardar unos segundos.",
            parse_mode="Markdown"
        )

        picks = await get_daily_picks(sport_filter=sport_filter)

        if not picks:
            await query.edit_message_text(
                f"😔 No encontré picks recomendables de *{sport_label}* para hoy.\n"
                "Intenta más tarde o revisa otro deporte.",
                parse_mode="Markdown"
            )
            return

        messages = format_picks_message(picks, sport_label)
        await query.edit_message_text(messages[0], parse_mode="Markdown")

        for msg in messages[1:]:
            await query.message.reply_text(msg, parse_mode="Markdown")

async def picks_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("⏳ Analizando todos los partidos de hoy...", parse_mode="Markdown")
    picks = await get_daily_picks(sport_filter=None)
    if not picks:
        await update.message.reply_text("😔 No encontré picks recomendables para hoy.")
        return
    messages = format_picks_message(picks, "Todos los Deportes")
    for msg in messages:
        await update.message.reply_text(msg, parse_mode="Markdown")

def format_picks_message(picks: list, sport_label: str) -> list[str]:
    now_cuba = datetime.now(CUBA_TZ)
    header = (
        f"🎯 *PICKS DEL DÍA - {sport_label}*\n"
        f"📅 {now_cuba.strftime('%d/%m/%Y %H:%M')} (Hora Cuba)\n"
        f"{'─' * 32}\n\n"
    )

    messages = []
    current = header
    for i, pick in enumerate(picks, 1):
        conf = pick['confidence']
        emoji_conf = "🟢" if conf >= 75 else "🟡"
        sport_emoji = {"soccer": "⚽", "basketball": "🏀", "baseball": "⚾"}.get(pick['sport'], "🏆")

        inj_line = f"{pick.get('injuries_note', '')}\n" if pick.get('injuries_note') else ""
        block = (
            f"{sport_emoji} *Partido {i}:* {pick['home']} vs {pick['away']}\n"
            f"🏆 Liga: {pick['league']}\n"
            f"🕐 Hora: {pick['time']} (Cuba)\n"
            f"{'─' * 28}\n"
            f"📊 *Análisis:*\n{pick['analysis']}\n\n"
            f"{inj_line}"
            f"✅ *Pick Recomendada:* `{pick['pick']}`\n"
            f"💰 *Tipo de apuesta:* {pick['bet_type']}\n"
            f"📈 *Cuota real mercado:* {pick['odds']}\n"
            f"{emoji_conf} *Confianza:* {conf}%\n\n"
        )

        if len(current) + len(block) > 4000:
            messages.append(current)
            current = block
        else:
            current += block

    if current.strip():
        current += "\n⚠️ _Análisis estadístico. Apuesta con responsabilidad._"
        messages.append(current)

    return messages

async def send_daily_picks(app):
    logger.info("Enviando picks automáticos del día...")
    picks = await get_daily_picks(sport_filter=None)
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if not chat_id or not picks:
        return
    messages = format_picks_message(picks, "Todos los Deportes")
    for msg in messages:
        await app.bot.send_message(chat_id=chat_id, text=msg, parse_mode="Markdown")

def main():
    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("picks", picks_command))
    app.add_handler(CallbackQueryHandler(button_handler))

    scheduler.add_job(
        send_daily_picks,
        "cron",
        hour=8,
        minute=0,
        args=[app],
        timezone=CUBA_TZ
    )
    scheduler.start()

    logger.info("Bot iniciado correctamente.")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
