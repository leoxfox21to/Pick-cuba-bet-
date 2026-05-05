import os
import logging
import asyncio
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from config import TELEGRAM_BOT_TOKEN, CUBA_TZ, MATCHES_PER_PAGE
from fetcher import load_today_matches, deep_analyze
from engines import soccer, baseball, basketball

logging.basicConfig(
    format="%(asctime)s %(levelname)s %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# Cache de partidos del día (se recarga con /partidos)
_match_cache: list = []
_cache_date: str = ""


async def _get_matches(force=False) -> list:
    global _match_cache, _cache_date
    today = datetime.now(CUBA_TZ).strftime("%Y-%m-%d")
    if force or _cache_date != today or not _match_cache:
        _match_cache = await load_today_matches()
        _cache_date = today
    return _match_cache


# ─── /start ──────────────────────────────────────────────────

async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    kb = [
        [InlineKeyboardButton("📋 Ver partidos de hoy", callback_data="matches:0")],
        [InlineKeyboardButton("⚽ Fútbol", callback_data="filter:soccer"),
         InlineKeyboardButton("🏀 Basket", callback_data="filter:basketball"),
         InlineKeyboardButton("⚾ Béisbol", callback_data="filter:baseball")],
        [InlineKeyboardButton("ℹ️ Cómo funciona", callback_data="help")],
    ]
    await update.message.reply_text(
        "🎯 *Pick Cuba Bet*\n\n"
        "Selecciona un deporte o ve todos los partidos de hoy.\n"
        "Toca cualquier partido para ver el análisis completo y el pick.",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(kb)
    )


# ─── /partidos ───────────────────────────────────────────────

async def cmd_partidos(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("⏳ Cargando partidos de hoy...")
    matches = await _get_matches(force=True)
    if not matches:
        await update.message.reply_text("😔 No encontré partidos para hoy. Intenta más tarde.")
        return
    await _send_match_list(update.message.reply_text, matches, page=0)


# ─── Callbacks ───────────────────────────────────────────────

async def cb_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    data = q.data

    # ── Ayuda
    if data == "help":
        await q.edit_message_text(
            "ℹ️ *Cómo funciona Pick Cuba Bet*\n\n"
            "1️⃣ Cargo todos los partidos del día (1 llamada a la API)\n"
            "2️⃣ Tú eliges el partido que te interesa\n"
            "3️⃣ Analizo ese partido en profundidad:\n"
            "   • Forma reciente de cada equipo\n"
            "   • Rendimiento local/visitante\n"
            "   • Head to Head (H2H)\n"
            "   • xG (goles esperados)\n"
            "   • Cuotas reales del mercado\n"
            "   • Lesiones y bajas\n"
            "   • Árbitro, clima, fatiga\n"
            "   • Historial Over/Under\n"
            "4️⃣ El motor escoge el mejor tipo de apuesta\n"
            "5️⃣ Te doy el pick con nivel de confianza y valor\n\n"
            "🟢 Alta confianza: 75%+\n"
            "🟡 Media: 65–74%\n"
            "🔥 Valor ALTO = cuota está mal puesta por la casa\n\n"
            "⚠️ _Análisis estadístico. Apuesta con responsabilidad._",
            parse_mode="Markdown"
        )
        return

    # ── Filtro por deporte
    if data.startswith("filter:"):
        sport = data.split(":")[1]
        await q.edit_message_text("⏳ Cargando partidos...")
        matches = await load_today_matches(sport_filter=sport)
        if not matches:
            await q.edit_message_text(f"😔 No hay partidos de ese deporte hoy.")
            return
        sport_label = {"soccer": "Fútbol ⚽", "basketball": "Baloncesto 🏀", "baseball": "Béisbol ⚾"}.get(sport, sport)
        await _send_match_list(q.edit_message_text, matches, page=0, label=sport_label)
        return

    # ── Paginación de partidos
    if data.startswith("matches:"):
        page = int(data.split(":")[1])
        matches = await _get_matches()
        await _send_match_list(q.edit_message_text, matches, page=page)
        return

    # ── Analizar partido seleccionado
    if data.startswith("analyze:"):
        idx = int(data.split(":")[1])
        matches = await _get_matches()
        if idx >= len(matches):
            await q.edit_message_text("❌ Partido no encontrado.")
            return

        match = matches[idx]
        sport_emoji = {"soccer": "⚽", "basketball": "🏀", "baseball": "⚾"}.get(match["sport"], "🏆")
        await q.edit_message_text(
            f"⏳ Analizando {sport_emoji} *{match['home']}* vs *{match['away']}*...\n"
            f"Esto toma unos segundos.",
            parse_mode="Markdown"
        )

        try:
            deep = await deep_analyze(match)
            result = _run_engine(deep)
        except Exception as e:
            logger.error(f"Error analizando partido: {e}")
            await q.message.reply_text("❌ Error al analizar el partido. Intenta de nuevo.")
            return

        if result is None:
            await q.message.reply_text(
                f"😔 No encontré un pick confiable para *{match['home']}* vs *{match['away']}*.\n"
                f"Los datos no son suficientemente claros para recomendar una apuesta.",
                parse_mode="Markdown"
            )
            return

        await q.message.reply_text(_format_pick(result), parse_mode="Markdown")

        kb = [[InlineKeyboardButton("📋 Ver más partidos", callback_data="matches:0")]]
        await q.message.reply_text(
            "¿Quieres analizar otro partido?",
            reply_markup=InlineKeyboardMarkup(kb)
        )
        return

    # ── Volver al menú
    if data == "menu":
        kb = [
            [InlineKeyboardButton("📋 Ver partidos de hoy", callback_data="matches:0")],
            [InlineKeyboardButton("⚽ Fútbol", callback_data="filter:soccer"),
             InlineKeyboardButton("🏀 Basket", callback_data="filter:basketball"),
             InlineKeyboardButton("⚾ Béisbol", callback_data="filter:baseball")],
        ]
        await q.edit_message_text(
            "🎯 *Pick Cuba Bet* — Menú principal",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(kb)
        )


# ─── Helpers ─────────────────────────────────────────────────

async def _send_match_list(send_fn, matches: list, page: int, label: str = "Todos los deportes"):
    total = len(matches)
    start = page * MATCHES_PER_PAGE
    end = min(start + MATCHES_PER_PAGE, total)
    page_matches = matches[start:end]

    sport_emoji = {"soccer": "⚽", "basketball": "🏀", "baseball": "⚾"}
    kb = []
    for i, m in enumerate(page_matches):
        idx = start + i
        emoji = sport_emoji.get(m["sport"], "🏆")
        label_btn = f"{emoji} {m['home']} vs {m['away']} ({m['time']})"
        kb.append([InlineKeyboardButton(label_btn, callback_data=f"analyze:{idx}")])

    # Navegación
    nav = []
    if start > 0:
        nav.append(InlineKeyboardButton("⬅️ Anteriores", callback_data=f"matches:{page-1}"))
    if end < total:
        nav.append(InlineKeyboardButton("➡️ Más partidos", callback_data=f"matches:{page+1}"))
    if nav:
        kb.append(nav)

    kb.append([InlineKeyboardButton("🏠 Menú", callback_data="menu")])

    now = datetime.now(CUBA_TZ).strftime("%d/%m/%Y %H:%M")
    text = (
        f"📋 *Partidos de hoy — {label}*\n"
        f"📅 {now} (Hora Cuba)\n"
        f"Mostrando {start+1}–{end} de {total}\n\n"
        f"Toca un partido para ver el análisis completo 👇"
    )
    await send_fn(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(kb))


def _run_engine(match: dict):
    sport = match.get("sport")
    if sport == "soccer":
        return soccer.analyze(match)
    elif sport == "baseball":
        return baseball.analyze(match)
    elif sport == "basketball":
        return basketball.analyze(match)
    return None


def _format_pick(r: dict) -> str:
    conf = r["confidence"]
    emoji_conf = "🟢" if conf >= 75 else "🟡"
    sport_emoji = {"soccer": "⚽", "basketball": "🏀", "baseball": "⚾"}.get(r["sport"], "🏆")
    now = datetime.now(CUBA_TZ).strftime("%d/%m/%Y %H:%M")

    factors_text = "\n".join(r.get("factors", []))
    inj = f"\n{r['injuries_note']}" if r.get("injuries_note") else ""

    return (
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"{sport_emoji} *{r['home']}* vs *{r['away']}*\n"
        f"🏆 {r['league']}  |  🕐 {r['time']} (Cuba)\n"
        f"📅 Análisis: {now}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"📊 *FACTORES ANALIZADOS:*\n"
        f"{factors_text}"
        f"{inj}\n\n"
        f"┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄\n"
        f"✅ *PICK:* `{r['pick']}`\n"
        f"💰 *Tipo:* {r['bet_type']}\n"
        f"📈 *Cuota:* {r['odds']}\n"
        f"{emoji_conf} *Confianza:* {conf}%\n"
        f"💎 *Valor:* {r.get('value', '—')}\n"
        f"┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄\n"
        f"⚠️ _Análisis estadístico. Apuesta con responsabilidad._"
    )


# ─── Picks automáticos (8AM Cuba) ────────────────────────────

async def auto_picks(app):
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if not chat_id:
        return
    matches = await _get_matches(force=True)
    top = matches[:5]
    for m in top:
        try:
            deep = await deep_analyze(m)
            result = _run_engine(deep)
            if result:
                await app.bot.send_message(chat_id=chat_id, text=_format_pick(result), parse_mode="Markdown")
                await asyncio.sleep(1)
        except Exception as e:
            logger.error(f"Auto pick error: {e}")


# ─── Main ────────────────────────────────────────────────────

def main():
    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CommandHandler("start",    cmd_start))
    app.add_handler(CommandHandler("partidos", cmd_partidos))
    app.add_handler(CallbackQueryHandler(cb_handler))

    scheduler = AsyncIOScheduler(timezone=CUBA_TZ)
    scheduler.add_job(auto_picks, "cron", hour=8, minute=0, args=[app])
    scheduler.start()

    logger.info("Bot iniciado.")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
