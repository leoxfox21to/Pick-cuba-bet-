import aiohttp
import asyncio
from datetime import datetime, date
from config import (
    API_FOOTBALL_BASE, API_BASKETBALL_BASE, API_BASEBALL_BASE,
    HEADERS_FOOTBALL, HEADERS_BASKETBALL, HEADERS_BASEBALL,
    CUBA_TZ
)
import logging

logger = logging.getLogger(__name__)


def get_today_cuba():
    return datetime.now(CUBA_TZ).strftime("%Y-%m-%d")


async def fetch_json(session: aiohttp.ClientSession, url: str, headers: dict, params: dict = None):
    try:
        async with session.get(url, headers=headers, params=params, timeout=aiohttp.ClientTimeout(total=15)) as resp:
            if resp.status == 200:
                return await resp.json()
            else:
                logger.warning(f"Error {resp.status} en {url}")
                return None
    except Exception as e:
        logger.error(f"Excepcion al llamar {url}: {e}")
        return None


# ─── WEATHER ────────────────────────────────────────────────────────────────

async def get_weather(session: aiohttp.ClientSession, city: str) -> dict:
    if not city:
        return {}
    try:
        url = f"https://wttr.in/{city.replace(' ', '+')}?format=j1"
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=8)) as resp:
            if resp.status == 200:
                data = await resp.json(content_type=None)
                current = data.get("current_condition", [{}])[0]
                return {
                    "temp_c": int(current.get("temp_C", 20)),
                    "wind_kmph": int(current.get("windspeedKmph", 0)),
                    "precip_mm": float(current.get("precipMM", 0)),
                    "desc": current.get("weatherDesc", [{}])[0].get("value", ""),
                    "humidity": int(current.get("humidity", 50)),
                }
    except Exception as e:
        logger.warning(f"Weather error para {city}: {e}")
    return {}


# ─── FOOTBALL ───────────────────────────────────────────────────────────────

async def get_football_fixtures(session: aiohttp.ClientSession, date: str):
    data = await fetch_json(
        session,
        f"{API_FOOTBALL_BASE}/fixtures",
        HEADERS_FOOTBALL,
        {"date": date, "timezone": "America/Havana"}
    )
    if not data or "response" not in data:
        return []

    fixtures = []
    for f in data["response"]:
        fixture_id = f["fixture"]["id"]
        home_id = f["teams"]["home"]["id"]
        away_id = f["teams"]["away"]["id"]
        league_id = f["league"]["id"]
        season = f["league"]["season"]
        referee = f["fixture"].get("referee") or ""
        venue_city = f["fixture"].get("venue", {}).get("city", "")
        time_str = f["fixture"]["date"][11:16]

        (
            stats_home, stats_away,
            home_away_home, home_away_away,
            h2h,
            injuries_home, injuries_away,
            odds,
            referee_data,
            xg_home, xg_away,
            weather
        ) = await asyncio.gather(
            get_team_stats_football(session, home_id, league_id, season),
            get_team_stats_football(session, away_id, league_id, season),
            get_team_home_away_stats(session, home_id, league_id, season, "home"),
            get_team_home_away_stats(session, away_id, league_id, season, "away"),
            get_h2h_football(session, home_id, away_id),
            get_injuries(session, home_id, season),
            get_injuries(session, away_id, season),
            get_odds(session, fixture_id),
            get_referee_stats(session, referee),
            get_team_xg(session, home_id, league_id, season),
            get_team_xg(session, away_id, league_id, season),
            get_weather(session, venue_city),
        )

        fatigue_home = await get_fatigue(session, home_id, date)
        fatigue_away = await get_fatigue(session, away_id, date)
        ou_history_home = await get_ou_history(session, home_id, league_id, season)
        ou_history_away = await get_ou_history(session, away_id, league_id, season)

        fixtures.append({
            "sport": "soccer",
            "fixture_id": fixture_id,
            "home": f["teams"]["home"]["name"],
            "away": f["teams"]["away"]["name"],
            "league": f["league"]["name"],
            "time": time_str,
            "venue_city": venue_city,
            "referee": referee,
            "stats_home": stats_home,
            "stats_away": stats_away,
            "home_form_home": home_away_home,
            "away_form_away": home_away_away,
            "h2h": h2h,
            "injuries_home": injuries_home,
            "injuries_away": injuries_away,
            "odds": odds,
            "referee_data": referee_data,
            "xg_home": xg_home,
            "xg_away": xg_away,
            "fatigue_home": fatigue_home,
            "fatigue_away": fatigue_away,
            "ou_history_home": ou_history_home,
            "ou_history_away": ou_history_away,
            "weather": weather,
        })

    return fixtures


async def get_team_stats_football(session, team_id: int, league_id: int, season: int):
    data = await fetch_json(
        session,
        f"{API_FOOTBALL_BASE}/teams/statistics",
        HEADERS_FOOTBALL,
        {"team": team_id, "league": league_id, "season": season}
    )
    if not data or "response" not in data:
        return {}
    r = data["response"]
    return {
        "wins": r.get("fixtures", {}).get("wins", {}).get("total", 0) or 0,
        "draws": r.get("fixtures", {}).get("draws", {}).get("total", 0) or 0,
        "losses": r.get("fixtures", {}).get("loses", {}).get("total", 0) or 0,
        "goals_for": r.get("goals", {}).get("for", {}).get("total", {}).get("total", 0) or 0,
        "goals_against": r.get("goals", {}).get("against", {}).get("total", {}).get("total", 0) or 0,
        "avg_goals_for": float(r.get("goals", {}).get("for", {}).get("average", {}).get("total", 0) or 0),
        "avg_goals_against": float(r.get("goals", {}).get("against", {}).get("average", {}).get("total", 0) or 0),
        "clean_sheets": r.get("clean_sheet", {}).get("total", 0) or 0,
        "form": r.get("form", "") or "",
        "failed_to_score": r.get("failed_to_score", {}).get("total", 0) or 0,
        "penalty_scored": r.get("penalty", {}).get("scored", {}).get("total", 0) or 0,
        "penalty_missed": r.get("penalty", {}).get("missed", {}).get("total", 0) or 0,
    }


async def get_team_home_away_stats(session, team_id: int, league_id: int, season: int, venue: str):
    data = await fetch_json(
        session,
        f"{API_FOOTBALL_BASE}/teams/statistics",
        HEADERS_FOOTBALL,
        {"team": team_id, "league": league_id, "season": season}
    )
    if not data or "response" not in data:
        return {}
    r = data["response"]
    fixtures = r.get("fixtures", {})
    goals = r.get("goals", {})
    return {
        "wins": fixtures.get("wins", {}).get(venue, 0) or 0,
        "draws": fixtures.get("draws", {}).get(venue, 0) or 0,
        "losses": fixtures.get("loses", {}).get(venue, 0) or 0,
        "avg_gf": float(goals.get("for", {}).get("average", {}).get(venue, 0) or 0),
        "avg_ga": float(goals.get("against", {}).get("average", {}).get(venue, 0) or 0),
        "clean_sheets": r.get("clean_sheet", {}).get(venue, 0) or 0,
    }


async def get_h2h_football(session, team1_id: int, team2_id: int):
    data = await fetch_json(
        session,
        f"{API_FOOTBALL_BASE}/fixtures/headtohead",
        HEADERS_FOOTBALL,
        {"h2h": f"{team1_id}-{team2_id}", "last": 10}
    )
    if not data or "response" not in data:
        return []
    results = []
    for f in data["response"]:
        goals_home = f["goals"].get("home") or 0
        goals_away = f["goals"].get("away") or 0
        results.append({
            "home_goals": goals_home,
            "away_goals": goals_away,
            "total_goals": goals_home + goals_away,
            "home_winner": f["teams"]["home"].get("winner"),
            "away_winner": f["teams"]["away"].get("winner"),
        })
    return results


async def get_injuries(session, team_id: int, season: int):
    data = await fetch_json(
        session,
        f"{API_FOOTBALL_BASE}/injuries",
        HEADERS_FOOTBALL,
        {"team": team_id, "season": season}
    )
    if not data or "response" not in data:
        return []
    injuries = []
    for p in data["response"]:
        injuries.append({
            "player": p.get("player", {}).get("name", "Desconocido"),
            "type": p.get("player", {}).get("reason", "Lesión"),
            "position": p.get("player", {}).get("type", ""),
        })
    return injuries


async def get_odds(session, fixture_id: int):
    data = await fetch_json(
        session,
        f"{API_FOOTBALL_BASE}/odds",
        HEADERS_FOOTBALL,
        {"fixture": fixture_id, "bookmaker": 6}
    )
    if not data or not data.get("response"):
        return {}
    try:
        bets = data["response"][0]["bookmakers"][0]["bets"]
        result = {}
        for bet in bets:
            if bet["name"] == "Match Winner":
                for v in bet["values"]:
                    if v["value"] == "Home":
                        result["odds_home"] = float(v["odd"])
                    elif v["value"] == "Away":
                        result["odds_away"] = float(v["odd"])
                    elif v["value"] == "Draw":
                        result["odds_draw"] = float(v["odd"])
            elif bet["name"] == "Goals Over/Under":
                for v in bet["values"]:
                    if v["value"] == "Over 2.5":
                        result["odds_over25"] = float(v["odd"])
                    elif v["value"] == "Under 2.5":
                        result["odds_under25"] = float(v["odd"])
            elif bet["name"] == "Both Teams Score":
                for v in bet["values"]:
                    if v["value"] == "Yes":
                        result["odds_btts_yes"] = float(v["odd"])
                    elif v["value"] == "No":
                        result["odds_btts_no"] = float(v["odd"])
        return result
    except (IndexError, KeyError):
        return {}


async def get_referee_stats(session, referee_name: str):
    if not referee_name:
        return {}
    data = await fetch_json(
        session,
        f"{API_FOOTBALL_BASE}/fixtures",
        HEADERS_FOOTBALL,
        {"referee": referee_name, "last": 20}
    )
    if not data or not data.get("response"):
        return {"name": referee_name}

    total = len(data["response"])
    total_goals = 0
    over25 = 0
    penalties = 0
    red_cards = 0

    for f in data["response"]:
        g_home = f["goals"].get("home") or 0
        g_away = f["goals"].get("away") or 0
        total_goals += g_home + g_away
        if g_home + g_away > 2:
            over25 += 1

    return {
        "name": referee_name,
        "matches": total,
        "avg_goals": round(total_goals / max(total, 1), 2),
        "over25_pct": round(over25 / max(total, 1) * 100, 1),
    }


async def get_team_xg(session, team_id: int, league_id: int, season: int):
    data = await fetch_json(
        session,
        f"{API_FOOTBALL_BASE}/fixtures",
        HEADERS_FOOTBALL,
        {"team": team_id, "league": league_id, "season": season, "last": 10, "status": "FT"}
    )
    if not data or not data.get("response"):
        return {"avg_xg": 0.0, "avg_xga": 0.0}

    xg_list = []
    xga_list = []

    for f in data["response"]:
        stats = await fetch_json(
            session,
            f"{API_FOOTBALL_BASE}/fixtures/statistics",
            HEADERS_FOOTBALL,
            {"fixture": f["fixture"]["id"], "team": team_id}
        )
        if stats and stats.get("response"):
            for s in stats["response"][0].get("statistics", []):
                if s["type"] == "Expected_Goals" and s["value"]:
                    try:
                        xg_list.append(float(s["value"]))
                    except (ValueError, TypeError):
                        pass

    return {
        "avg_xg": round(sum(xg_list) / max(len(xg_list), 1), 2),
        "samples": len(xg_list),
    }


async def get_fatigue(session, team_id: int, today: str) -> dict:
    data = await fetch_json(
        session,
        f"{API_FOOTBALL_BASE}/fixtures",
        HEADERS_FOOTBALL,
        {"team": team_id, "last": 3, "status": "FT"}
    )
    if not data or not data.get("response"):
        return {"days_since_last": 7, "matches_last_14d": 0}

    today_date = datetime.strptime(today, "%Y-%m-%d").date()
    days_list = []
    last_14 = 0

    for f in data["response"]:
        d_str = f["fixture"]["date"][:10]
        try:
            d = datetime.strptime(d_str, "%Y-%m-%d").date()
            diff = (today_date - d).days
            if diff >= 0:
                days_list.append(diff)
                if diff <= 14:
                    last_14 += 1
        except ValueError:
            pass

    days_since = min(days_list) if days_list else 7
    return {"days_since_last": days_since, "matches_last_14d": last_14}


async def get_ou_history(session, team_id: int, league_id: int, season: int) -> dict:
    data = await fetch_json(
        session,
        f"{API_FOOTBALL_BASE}/fixtures",
        HEADERS_FOOTBALL,
        {"team": team_id, "league": league_id, "season": season, "last": 20, "status": "FT"}
    )
    if not data or not data.get("response"):
        return {"over25_pct": 50.0, "avg_total_goals": 2.5, "samples": 0}

    total = 0
    over25 = 0
    total_goals = 0

    for f in data["response"]:
        gh = f["goals"].get("home") or 0
        ga = f["goals"].get("away") or 0
        g = gh + ga
        total_goals += g
        if g > 2:
            over25 += 1
        total += 1

    return {
        "over25_pct": round(over25 / max(total, 1) * 100, 1),
        "avg_total_goals": round(total_goals / max(total, 1), 2),
        "samples": total,
    }


# ─── BASKETBALL ─────────────────────────────────────────────────────────────

async def get_basketball_games(session: aiohttp.ClientSession, date: str):
    data = await fetch_json(
        session,
        f"{API_BASKETBALL_BASE}/games",
        HEADERS_BASKETBALL,
        {"date": date, "timezone": "America/Havana"}
    )
    if not data or "response" not in data:
        return []

    games = []
    for g in data["response"]:
        home = g["teams"]["home"]["name"]
        away = g["teams"]["visitors"]["name"]
        league = g["league"]["name"]
        time_str = g["date"]["start"][11:16] if g["date"].get("start") else "N/A"
        games.append({
            "sport": "basketball",
            "fixture_id": g["id"],
            "home": home,
            "away": away,
            "league": league,
            "time": time_str,
            "scores_home": g.get("scores", {}).get("home", {}),
            "scores_away": g.get("scores", {}).get("visitors", {}),
        })
    return games


# ─── BASEBALL ───────────────────────────────────────────────────────────────

async def get_baseball_games(session: aiohttp.ClientSession, date: str):
    data = await fetch_json(
        session,
        f"{API_BASEBALL_BASE}/games",
        HEADERS_BASEBALL,
        {"date": date, "timezone": "America/Havana"}
    )
    if not data or "response" not in data:
        return []

    games = []
    for g in data["response"]:
        home = g["teams"]["home"]["name"]
        away = g["teams"]["away"]["name"]
        league = g["league"]["name"]
        time_str = g["date"][11:16] if g.get("date") else "N/A"
        games.append({
            "sport": "baseball",
            "fixture_id": g["id"],
            "home": home,
            "away": away,
            "league": league,
            "time": time_str,
            "scores": g.get("scores", {}),
        })
    return games


# ─── MAIN FETCH ─────────────────────────────────────────────────────────────

async def _empty() -> list:
    return []


async def fetch_all_games(sport_filter: str = None):
    today = get_today_cuba()
    games = []

    async with aiohttp.ClientSession() as session:
        tasks = []

        tasks.append(get_football_fixtures(session, today) if (sport_filter is None or sport_filter == "soccer") else _empty())
        tasks.append(get_basketball_games(session, today) if (sport_filter is None or sport_filter == "basketball") else _empty())
        tasks.append(get_baseball_games(session, today) if (sport_filter is None or sport_filter == "baseball") else _empty())

        results = await asyncio.gather(*tasks, return_exceptions=True)

        for r in results:
            if isinstance(r, list):
                games.extend(r)

    return games
