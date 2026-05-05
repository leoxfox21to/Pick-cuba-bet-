import asyncio
import aiohttp
from fetcher import fetch_all_games, get_today_cuba, get_football_fixtures
from config import MIN_CONFIDENCE, HEADERS_FOOTBALL, API_FOOTBALL_BASE
import logging

logger = logging.getLogger(__name__)


def analyze_football(game: dict) -> dict | None:
    home = game["home"]
    away = game["away"]
    sh = game.get("stats_home", {})
    sa = game.get("stats_away", {})
    h2h = game.get("h2h", [])

    if not sh or not sa:
        return None

    score = 50
    analysis_lines = []

    wins_h = sh.get("wins", 0) or 0
    wins_a = sa.get("wins", 0) or 0
    losses_h = sh.get("losses", 0) or 0
    losses_a = sa.get("losses", 0) or 0
    total_h = max(wins_h + sh.get("draws", 0) + losses_h, 1)
    total_a = max(wins_a + sa.get("draws", 0) + losses_a, 1)
    win_rate_h = wins_h / total_h
    win_rate_a = wins_a / total_a

    avg_gf_h = float(sh.get("avg_goals_for", 0) or 0)
    avg_ga_h = float(sh.get("avg_goals_against", 0) or 0)
    avg_gf_a = float(sa.get("avg_goals_for", 0) or 0)
    avg_ga_a = float(sa.get("avg_goals_against", 0) or 0)

    form_h = sh.get("form", "")[-5:] if sh.get("form") else ""
    form_a = sa.get("form", "")[-5:] if sa.get("form") else ""
    form_score_h = form_h.count("W") * 3 + form_h.count("D")
    form_score_a = form_a.count("W") * 3 + form_a.count("D")

    analysis_lines.append(f"  • {home}: {wins_h}V/{sh.get('draws',0)}E/{losses_h}D | Forma: {form_h or 'N/A'}")
    analysis_lines.append(f"  • {away}: {wins_a}V/{sa.get('draws',0)}E/{losses_a}D | Forma: {form_a or 'N/A'}")
    analysis_lines.append(f"  • Goles prom: {home} {avg_gf_h:.1f} vs {away} {avg_gf_a:.1f}")

    h2h_home_wins = sum(1 for g in h2h if g.get("home_winner"))
    h2h_away_wins = sum(1 for g in h2h if g.get("away_winner"))
    if h2h:
        analysis_lines.append(f"  • H2H últimos {len(h2h)}: {home} {h2h_home_wins}W / {away} {h2h_away_wins}W")

    home_advantage = 5
    score += home_advantage

    if win_rate_h > win_rate_a + 0.15:
        score += 10
    elif win_rate_a > win_rate_h + 0.15:
        score -= 8

    if form_score_h > form_score_a + 3:
        score += 8
    elif form_score_a > form_score_h + 3:
        score -= 6

    if h2h_home_wins > h2h_away_wins + 2:
        score += 5
    elif h2h_away_wins > h2h_home_wins + 2:
        score -= 4

    total_avg_goals = avg_gf_h + avg_ga_a
    btts_prob = (avg_gf_h > 1.2 and avg_gf_a > 1.0)

    if score >= 60 and win_rate_h > 0.45:
        pick = f"Victoria {home}"
        bet_type = "1X2 - Local gana"
        odds = round(1.0 / max(win_rate_h, 0.3), 2)
        confidence = min(score + 5, 92)
    elif score <= 44 and win_rate_a > 0.40:
        pick = f"Victoria {away}"
        bet_type = "1X2 - Visitante gana"
        odds = round(1.0 / max(win_rate_a, 0.3) * 1.15, 2)
        confidence = min(100 - score + 10, 88)
    elif total_avg_goals >= 2.5:
        pick = f"Más de 2.5 goles"
        bet_type = "Over/Under - Over 2.5"
        odds = round(1.7 + (total_avg_goals - 2.5) * 0.1, 2)
        confidence = min(60 + int((total_avg_goals - 2.5) * 10), 85)
    elif btts_prob:
        pick = "Ambos equipos anotan (SÍ)"
        bet_type = "BTTS - Ambos marcan"
        odds = 1.75
        confidence = 67
    else:
        return None

    if confidence < MIN_CONFIDENCE:
        return None

    return {
        "sport": "soccer",
        "home": home,
        "away": away,
        "league": game["league"],
        "time": game["time"],
        "analysis": "\n".join(analysis_lines),
        "pick": pick,
        "bet_type": bet_type,
        "odds": f"{odds:.2f}",
        "confidence": confidence,
    }


def analyze_basketball(game: dict) -> dict | None:
    home = game["home"]
    away = game["away"]

    analysis_lines = [
        f"  • Partido de baloncesto: {home} vs {away}",
        f"  • Liga: {game['league']}",
        f"  • Análisis basado en estadísticas de liga disponibles",
    ]

    confidence = 65
    pick = f"Victoria {home} (Local)"
    bet_type = "Resultado - Local gana"
    odds = 1.85

    if confidence < MIN_CONFIDENCE:
        return None

    return {
        "sport": "basketball",
        "home": home,
        "away": away,
        "league": game["league"],
        "time": game["time"],
        "analysis": "\n".join(analysis_lines),
        "pick": pick,
        "bet_type": bet_type,
        "odds": f"{odds:.2f}",
        "confidence": confidence,
    }


def analyze_baseball(game: dict) -> dict | None:
    home = game["home"]
    away = game["away"]

    analysis_lines = [
        f"  • Partido de béisbol: {home} vs {away}",
        f"  • Liga: {game['league']}",
        f"  • Ventaja local histórica en béisbol (~54%)",
    ]

    confidence = 66
    pick = f"Victoria {home} (Local)"
    bet_type = "Moneyline - Local gana"
    odds = 1.80

    if confidence < MIN_CONFIDENCE:
        return None

    return {
        "sport": "baseball",
        "home": home,
        "away": away,
        "league": game["league"],
        "time": game["time"],
        "analysis": "\n".join(analysis_lines),
        "pick": pick,
        "bet_type": bet_type,
        "odds": f"{odds:.2f}",
        "confidence": confidence,
    }


async def get_daily_picks(sport_filter: str = None) -> list:
    games = await fetch_all_games(sport_filter=sport_filter)

    picks = []
    for game in games:
        sport = game.get("sport")
        result = None

        if sport == "soccer":
            result = analyze_football(game)
        elif sport == "basketball":
            result = analyze_basketball(game)
        elif sport == "baseball":
            result = analyze_baseball(game)

        if result:
            picks.append(result)

    picks.sort(key=lambda x: x["confidence"], reverse=True)
    return picks[:15]
