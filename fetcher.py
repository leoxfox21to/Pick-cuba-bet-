import aiohttp
import asyncio
from datetime import datetime
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
        logger.error(f"Excepción al llamar {url}: {e}")
        return None


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
        home = f["teams"]["home"]["name"]
        away = f["teams"]["away"]["name"]
        league = f["league"]["name"]
        time_str = f["fixture"]["date"][11:16]

        stats_home, stats_away, h2h = await asyncio.gather(
            get_team_stats_football(session, f["teams"]["home"]["id"], f["league"]["id"], f["league"]["season"]),
            get_team_stats_football(session, f["teams"]["away"]["id"], f["league"]["id"], f["league"]["season"]),
            get_h2h_football(session, f["teams"]["home"]["id"], f["teams"]["away"]["id"])
        )

        fixtures.append({
            "sport": "soccer",
            "fixture_id": fixture_id,
            "home": home,
            "away": away,
            "league": league,
            "time": time_str,
            "stats_home": stats_home,
            "stats_away": stats_away,
            "h2h": h2h,
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
        "wins": r.get("fixtures", {}).get("wins", {}).get("total", 0),
        "draws": r.get("fixtures", {}).get("draws", {}).get("total", 0),
        "losses": r.get("fixtures", {}).get("loses", {}).get("total", 0),
        "goals_for": r.get("goals", {}).get("for", {}).get("total", {}).get("total", 0),
        "goals_against": r.get("goals", {}).get("against", {}).get("total", {}).get("total", 0),
        "avg_goals_for": r.get("goals", {}).get("for", {}).get("average", {}).get("total", 0),
        "avg_goals_against": r.get("goals", {}).get("against", {}).get("average", {}).get("total", 0),
        "clean_sheets": r.get("clean_sheet", {}).get("total", 0),
        "form": r.get("form", ""),
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
        results.append({
            "home_goals": f["goals"]["home"],
            "away_goals": f["goals"]["away"],
            "home_winner": f["teams"]["home"]["winner"],
            "away_winner": f["teams"]["away"]["winner"],
        })
    return results


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
            "status": g.get("status", {}).get("long", ""),
        })

    return games


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
            "status": g.get("status", {}).get("long", ""),
        })

    return games


async def fetch_all_games(sport_filter: str = None):
    date = get_today_cuba()
    games = []

    async with aiohttp.ClientSession() as session:
        tasks = []

        if sport_filter is None or sport_filter == "soccer":
            tasks.append(get_football_fixtures(session, date))
        else:
            tasks.append(asyncio.coroutine(lambda: [])())

        if sport_filter is None or sport_filter == "basketball":
            tasks.append(get_basketball_games(session, date))
        else:
            tasks.append(asyncio.coroutine(lambda: [])())

        if sport_filter is None or sport_filter == "baseball":
            tasks.append(get_baseball_games(session, date))
        else:
            tasks.append(asyncio.coroutine(lambda: [])())

        results = await asyncio.gather(*tasks, return_exceptions=True)

        for r in results:
            if isinstance(r, list):
                games.extend(r)

    return games
