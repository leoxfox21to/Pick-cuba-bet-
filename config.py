import os
import pytz
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
API_KEY = os.environ.get("API_FOOTBALL_KEY", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")

CUBA_TZ = pytz.timezone("America/Havana")

if not TELEGRAM_BOT_TOKEN:
    raise ValueError(
        "\n❌ Falta TELEGRAM_BOT_TOKEN en el archivo .env\n"
        "Ejecuta: nano .env  y agrega:\n"
        "  TELEGRAM_BOT_TOKEN=tu_token\n"
        "  API_FOOTBALL_KEY=tu_clave\n"
    )

if not API_KEY:
    raise ValueError(
        "\n❌ Falta API_FOOTBALL_KEY en el archivo .env\n"
        "Regístrate gratis en: dashboard.api-football.com/register\n"
    )

FOOTBALL_BASE   = "https://v3.football.api-sports.io"
BASKETBALL_BASE = "https://v1.basketball.api-sports.io"
BASEBALL_BASE   = "https://v1.baseball.api-sports.io"

HEADERS = {"x-apisports-key": API_KEY}

MIN_CONFIDENCE = 65
MATCHES_PER_PAGE = 5
