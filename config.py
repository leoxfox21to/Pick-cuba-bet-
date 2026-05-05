import os
import pytz
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
API_FOOTBALL_KEY = os.environ.get("API_FOOTBALL_KEY", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")

CUBA_TZ = pytz.timezone("America/Havana")

if not TELEGRAM_BOT_TOKEN:
    raise ValueError(
        "\n\n❌ Falta TELEGRAM_BOT_TOKEN\n"
        "Crea el archivo .env en la misma carpeta del bot con este contenido:\n\n"
        "  TELEGRAM_BOT_TOKEN=tu_token_aqui\n"
        "  API_FOOTBALL_KEY=tu_clave_aqui\n\n"
        "Ejecuta: nano .env"
    )

if not API_FOOTBALL_KEY:
    raise ValueError(
        "\n\n❌ Falta API_FOOTBALL_KEY\n"
        "Agrega en el archivo .env:\n\n"
        "  API_FOOTBALL_KEY=tu_clave_aqui\n"
    )

API_FOOTBALL_BASE = "https://v3.football.api-sports.io"
API_BASKETBALL_BASE = "https://v1.basketball.api-sports.io"
API_BASEBALL_BASE = "https://v1.baseball.api-sports.io"

HEADERS_FOOTBALL = {
    "x-rapidapi-host": "v3.football.api-sports.io",
    "x-rapidapi-key": API_FOOTBALL_KEY,
}
HEADERS_BASKETBALL = {
    "x-rapidapi-host": "v1.basketball.api-sports.io",
    "x-rapidapi-key": API_FOOTBALL_KEY,
}
HEADERS_BASEBALL = {
    "x-rapidapi-host": "v1.baseball.api-sports.io",
    "x-rapidapi-key": API_FOOTBALL_KEY,
}

MIN_CONFIDENCE = 65
