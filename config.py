import os
import pytz

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
API_FOOTBALL_KEY = os.environ.get("API_FOOTBALL_KEY", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")

CUBA_TZ = pytz.timezone("America/Havana")

if not TELEGRAM_BOT_TOKEN:
    raise ValueError("Falta TELEGRAM_BOT_TOKEN en las variables de entorno")

if not API_FOOTBALL_KEY:
    raise ValueError("Falta API_FOOTBALL_KEY en las variables de entorno")

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
