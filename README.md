# Pick Cuba Bet 🎯

Bot de Telegram para análisis y predicciones de apuestas deportivas en horario de Cuba.

## Deportes soportados
- ⚽ Fútbol (partidos del día con estadísticas completas)
- 🏀 Baloncesto (NBA y ligas internacionales)
- ⚾ Béisbol (MLB y ligas internacionales)

## Características
- Obtiene partidos del día en horario de Cuba (UTC-5)
- Analiza forma reciente, head-to-head, promedios de goles
- Recomienda el mejor tipo de apuesta: 1X2, Over/Under, BTTS, Moneyline
- Solo muestra picks con confianza ≥ 65%
- Envío automático de picks a las 8:00 AM hora Cuba

## Variables de entorno requeridas
```
TELEGRAM_BOT_TOKEN=tu_token_del_bot
API_FOOTBALL_KEY=tu_clave_api_football
TELEGRAM_CHAT_ID=tu_chat_id (opcional, para picks automáticos)
```

## Instalación en Termux

```bash
pkg update && pkg upgrade
pkg install python
pip install -r requirements.txt
python bot.py
```

## Comandos del bot
- `/start` — Menú principal con botones
- `/picks` — Ver todas las picks del día

## API utilizada
- [API-Football](https://www.api-football.com/) — Fútbol, Baloncesto y Béisbol
- Plan gratuito: 100 llamadas/día

## Confianza
- 🟢 Alta: 75%+
- 🟡 Media: 65-74%

⚠️ Las picks son análisis estadístico. Apuesta con responsabilidad.
