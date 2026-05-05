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

MAX_DEEP_FIXTURES = 12  # max fixtures to deep-analyze (protege el límite de 100 llamadas/día)

# Ligas con mayor calidad de datos y relevancia para apuestas
LEAGUE_PRIORITY = {
    # Fútbol - Tier 1 (90-100pts)
    39: 100,   # Premier League
    140: 98,   # La Liga
    135: 96,   # Serie A
    78: 95,    # Bundesliga
    61: 94,    # Ligue 1
    2: 92,     # Champions League
    3: 90,     # Europa League
    # Tier 2 (70-89pts)
    94: 85,    # Primeira Liga
    88: 83,    # Eredivisie
    144: 82,   # Jupiler Pro League
    179: 80,   # Scottish Premiership
    71: 78,    # Serie A Brasil
    253: 75,   # MLS
    848: 72,   # Conference League
    # Tier 3 (50-69pts)
    307: 65,   # Saudi Pro League
    197: 63,   # Super Lig
    106: 60,   # Ekstraklasa
    119: 58,   # Superliga Dinamarca
    # Resto: 30pts por defecto
}


def get_today_cuba() -> str:
    return datetime.now(CUBA_TZ).strftime("%Y-%m-%d")


async def fetch_json(session: aiohttp.ClientSession, url: str, headers: dict, params: dict = None):
    try:
        async with session.get(
            url, headers=headers, params=params,
            timeout=aiohttp.ClientTimeout(total=15)
        ) as resp:
            if resp.status == 200:
                return await resp.json()
            logger.warning(f"HTTP {resp.status} → {url} params={params}")
            return None
    except Exception as e:
        logger.error(f"Error fetch {url}: {e}")
        return None


# ══════════════════════════════════════════════════════════════
#  FASE 1 — Carga masiva (1 llamada por deporte)
# ══════════════════════════════════════════════════════════════

async def bulk_get_football(session: aiohttp.ClientSession, date: str) -> list:
    data = await fetch_json(
        session, f"{API_FOOTBALL_BASE}/fixtures", HEADERS_FOOTBALL,
        {"date": date, "timezone": "America/Havana"}
    )
    if not data or "response" not in data:
        return []

    fixtures = []
    for f in data["response"]:
        status = f["fixture"]["status"]["short"]
        if status not in ("NS", "TBD"):   # solo partidos no iniciados
            continue
        league_id = f["league"]["id"]
        priority = LEAGUE_PRIORITY.get(league_id, 30)
        fixtures.append({
            "sport": "soccer",
            "fixture_id": f["fixture"]["id"],
            "home": f["teams"]["home"]["name"],
            "home_id": f["teams"]["home"]["id"],
            "away": f["teams"]["away"]["name"],
            "away_id": f["teams"]["away"]["id"],
            "league": f["league"]["name"],
            "league_id": league_id,
            "season": f["league"]["season"],
            "time": f["fixture"]["date"][11:16],
            "venue_city": f["fixture"].get("venue", {}).get("city", "") or "",
            "referee": f["fixture"].get("referee") or "",
            "priority": priority,
        })

    fixtures.sort(key=lambda x: x["priority"], reverse=True)
    logger.info(f"Fútbol: {len(fixtures)} partidos encontrados")
    return fixtures


async def bulk_get_basketball(session: aiohttp.ClientSession, date: str) -> list:
    data = await fetch_json(
        session, f"{API_BASKETBALL_BASE}/games", HEADERS_BASKETBALL,
        {"date": date, "timezone": "America/Havana"}
    )
    if not data or "response" not in data:
        return []

    games = []
    for g in data["response"]:
        games.append({
            "sport": "basketball",
            "fixture_id": g["id"],
            "home": g["teams"]["home"]["name"],
            "home_id": g["teams"]["home"]["id"],
            "away": g["teams"]["visitors"]["name"],
            "away_id": g["teams"]["visitors"]["id"],
            "league": g["league"]["name"],
            "league_id": g["league"]["id"],
            "season": str(g["league"].get("season", "")),
            "time": (g["date"].get("start") or "")[11:16],
            "priority": 50,
        })
    logger.info(f"Baloncesto: {len(games)} partidos encontrados")
    return games


async def bulk_get_baseball(session: aiohttp.ClientSession, date: str) -> list:
    data = await fetch_json(
        session, f"{API_BASEBALL_BASE}/games", HEADERS_BASEBALL,
        {"date": date, "timezone": "America/Havana"}
    )
    if not data or "response" not in data:
        return []

    games = []
    for g in data["response"]:
        games.append({
            "sport": "baseball",
            "fixture_id": g["id"],
            "home": g["teams"]["home"]["name"],
            "home_id": g["teams"]["home"]["id"],
            "away": g["teams"]["away"]["name"],
            "away_id": g["teams"]["away"]["id"],
            "league": g["league"]["name"],
            "league_id": g["league"]["id"],
            "season": str(g["league"].get("season", "")),
            "time": (g.get("date") or "")[11:16],
            "priority": 45,
        })
    logger.info(f"Béisbol: {len(games)} partidos encontrados")
    return games


async def _sport_recent_games(session, team_id: int, season: str, base_url: str, headers: dict) -> list:
    data = await fetch_json(
        session, f"{base_url}/games", headers,
        {"team": team_id, "season": season, "last": 10}
    )
    if not data or not data.get("response"):
        return []
    return data["response"]


async def _sport_standings(session, league_id: int, season: str, base_url: str, headers: dict) -> list:
    data = await fetch_json(
        session, f"{base_url}/standings", headers,
        {"league": league_id, "season": season}
    )
    if not data or not data.get("response"):
        return []
    return data["response"]


async def deep_analyze_baseball(session: aiohttp.ClientSession, game: dict) -> dict:
    home_id = game["home_id"]
    away_id = game["away_id"]
    league_id = game["league_id"]
    season = game["season"]

    home_games, away_games, standings = await asyncio.gather(
        _sport_recent_games(session, home_id, season, API_BASEBALL_BASE, HEADERS_BASEBALL),
        _sport_recent_games(session, away_id, season, API_BASEBALL_BASE, HEADERS_BASEBALL),
        _sport_standings(session, league_id, season, API_BASEBALL_BASE, HEADERS_BASEBALL),
    )

    def parse_baseball_form(games, team_id):
        wins, losses, runs_for, runs_against = 0, 0, 0, 0
        for g in games:
            h_id = g["teams"]["home"]["id"]
            a_id = g["teams"]["away"]["id"]
            h_score = (g.get("scores", {}).get("home", {}).get("total") or 0)
            a_score = (g.get("scores", {}).get("away", {}).get("total") or 0)
            if h_id == team_id:
                runs_for += h_score
                runs_against += a_score
                if h_score > a_score:
                    wins += 1
                else:
                    losses += 1
            elif a_id == team_id:
                runs_for += a_score
                runs_against += h_score
                if a_score > h_score:
                    wins += 1
                else:
                    losses += 1
        total = max(wins + losses, 1)
        return {
            "wins": wins, "losses": losses,
            "win_rate": round(wins / total, 3),
            "avg_runs_for": round(runs_for / total, 2),
            "avg_runs_against": round(runs_against / total, 2),
        }

    def find_standing(standings_data, team_id):
        for group in standings_data:
            for entry in (group if isinstance(group, list) else [group]):
                t = entry.get("team", {})
                if t.get("id") == team_id:
                    return entry
        return {}

    home_stats = parse_baseball_form(home_games, home_id)
    away_stats = parse_baseball_form(away_games, away_id)
    home_standing = find_standing(standings, home_id)
    away_standing = find_standing(standings, away_id)

    return {
        **game,
        "home_stats": home_stats,
        "away_stats": away_stats,
        "home_standing": home_standing,
        "away_standing": away_standing,
    }


async def deep_analyze_basketball(session: aiohttp.ClientSession, game: dict) -> dict:
    home_id = game["home_id"]
    away_id = game["away_id"]
    league_id = game["league_id"]
    season = game["season"]

    home_games, away_games, standings = await asyncio.gather(
        _sport_recent_games(session, home_id, season, API_BASKETBALL_BASE, HEADERS_BASKETBALL),
        _sport_recent_games(session, away_id, season, API_BASKETBALL_BASE, HEADERS_BASKETBALL),
        _sport_standings(session, league_id, season, API_BASKETBALL_BASE, HEADERS_BASKETBALL),
    )

    def parse_basketball_form(games, team_id):
        wins, losses, pts_for, pts_against = 0, 0, 0, 0
        for g in games:
            h_id = g["teams"]["home"]["id"]
            v_id = g["teams"]["visitors"]["id"]
            h_score = (g.get("scores", {}).get("home", {}).get("total") or 0)
            v_score = (g.get("scores", {}).get("visitors", {}).get("total") or 0)
            if h_id == team_id:
                pts_for += h_score
                pts_against += v_score
                if h_score > v_score:
                    wins += 1
                else:
                    losses += 1
            elif v_id == team_id:
                pts_for += v_score
                pts_against += h_score
                if v_score > h_score:
                    wins += 1
                else:
                    losses += 1
        total = max(wins + losses, 1)
        return {
            "wins": wins, "losses": losses,
            "win_rate": round(wins / total, 3),
            "avg_pts_for": round(pts_for / total, 1),
            "avg_pts_against": round(pts_against / total, 1),
        }

    def find_standing(standings_data, team_id):
        for group in standings_data:
            for entry in (group if isinstance(group, list) else [group]):
                t = entry.get("team", {})
                if t.get("id") == team_id:
                    return entry
        return {}

    home_stats = parse_basketball_form(home_games, home_id)
    away_stats = parse_basketball_form(away_games, away_id)
    home_standing = find_standing(standings, home_id)
    away_standing = find_standing(standings, away_id)

    return {
        **game,
        "home_stats": home_stats,
        "away_stats": away_stats,
        "home_standing": home_standing,
        "away_standing": away_standing,
    }


# ══════════════════════════════════════════════════════════════
#  FASE 2 — Análisis profundo por fixture_id seleccionado
# ══════════════════════════════════════════════════════════════

async def deep_analyze_fixture(session: aiohttp.ClientSession, fixture: dict) -> dict:
    fid = fixture["fixture_id"]
    home_id = fixture["home_id"]
    away_id = fixture["away_id"]
    league_id = fixture["league_id"]
    season = fixture["season"]
    referee = fixture["referee"]
    city = fixture["venue_city"]
    today = get_today_cuba()

    (
        stats_home, stats_away,
        home_venue_stats, away_venue_stats,
        h2h,
        injuries_home, injuries_away,
        odds,
        referee_data,
        xg_home, xg_away,
        ou_home, ou_away,
        weather,
        fatigue_home, fatigue_away,
    ) = await asyncio.gather(
        _team_stats(session, home_id, league_id, season),
        _team_stats(session, away_id, league_id, season),
        _team_venue_stats(session, home_id, league_id, season, "home"),
        _team_venue_stats(session, away_id, league_id, season, "away"),
        _h2h(session, home_id, away_id),
        _injuries(session, home_id, season),
        _injuries(session, away_id, season),
        _odds(session, fid),
        _referee(session, referee),
        _xg(session, home_id, league_id, season),
        _xg(session, away_id, league_id, season),
        _ou_history(session, home_id, league_id, season),
        _ou_history(session, away_id, league_id, season),
        _weather(session, city),
        _fatigue(session, home_id, today),
        _fatigue(session, away_id, today),
    )

    return {
        **fixture,
        "stats_home": stats_home,
        "stats_away": stats_away,
        "home_form_home": home_venue_stats,
        "away_form_away": away_venue_stats,
        "h2h": h2h,
        "injuries_home": injuries_home,
        "injuries_away": injuries_away,
        "odds": odds,
        "referee_data": referee_data,
        "xg_home": xg_home,
        "xg_away": xg_away,
        "ou_history_home": ou_home,
        "ou_history_away": ou_away,
        "weather": weather,
        "fatigue_home": fatigue_home,
        "fatigue_away": fatigue_away,
    }


# ══════════════════════════════════════════════════════════════
#  Helpers de datos individuales
# ══════════════════════════════════════════════════════════════

async def _team_stats(session, team_id: int, league_id: int, season: int) -> dict:
    data = await fetch_json(
        session, f"{API_FOOTBALL_BASE}/teams/statistics", HEADERS_FOOTBALL,
        {"team": team_id, "league": league_id, "season": season}
    )
    if not data or "response" not in data:
        return {}
    r = data["response"]
    return {
        "wins":   r.get("fixtures", {}).get("wins", {}).get("total", 0) or 0,
        "draws":  r.get("fixtures", {}).get("draws", {}).get("total", 0) or 0,
        "losses": r.get("fixtures", {}).get("loses", {}).get("total", 0) or 0,
        "avg_goals_for":     float(r.get("goals", {}).get("for", {}).get("average", {}).get("total", 0) or 0),
        "avg_goals_against": float(r.get("goals", {}).get("against", {}).get("average", {}).get("total", 0) or 0),
        "clean_sheets":  r.get("clean_sheet", {}).get("total", 0) or 0,
        "failed_to_score": r.get("failed_to_score", {}).get("total", 0) or 0,
        "form": r.get("form", "") or "",
    }


async def _team_venue_stats(session, team_id: int, league_id: int, season: int, venue: str) -> dict:
    data = await fetch_json(
        session, f"{API_FOOTBALL_BASE}/teams/statistics", HEADERS_FOOTBALL,
        {"team": team_id, "league": league_id, "season": season}
    )
    if not data or "response" not in data:
        return {}
    r = data["response"]
    return {
        "wins":   r.get("fixtures", {}).get("wins", {}).get(venue, 0) or 0,
        "draws":  r.get("fixtures", {}).get("draws", {}).get(venue, 0) or 0,
        "losses": r.get("fixtures", {}).get("loses", {}).get(venue, 0) or 0,
        "avg_gf": float(r.get("goals", {}).get("for", {}).get("average", {}).get(venue, 0) or 0),
        "avg_ga": float(r.get("goals", {}).get("against", {}).get("average", {}).get(venue, 0) or 0),
        "clean_sheets": r.get("clean_sheet", {}).get(venue, 0) or 0,
    }


async def _h2h(session, team1: int, team2: int) -> list:
    data = await fetch_json(
        session, f"{API_FOOTBALL_BASE}/fixtures/headtohead", HEADERS_FOOTBALL,
        {"h2h": f"{team1}-{team2}", "last": 10}
    )
    if not data or "response" not in data:
        return []
    results = []
    for f in data["response"]:
        gh = f["goals"].get("home") or 0
        ga = f["goals"].get("away") or 0
        results.append({
            "home_goals": gh,
            "away_goals": ga,
            "total_goals": gh + ga,
            "home_winner": f["teams"]["home"].get("winner"),
            "away_winner": f["teams"]["away"].get("winner"),
        })
    return results


async def _injuries(session, team_id: int, season: int) -> list:
    data = await fetch_json(
        session, f"{API_FOOTBALL_BASE}/injuries", HEADERS_FOOTBALL,
        {"team": team_id, "season": season}
    )
    if not data or "response" not in data:
        return []
    return [
        {
            "player": p.get("player", {}).get("name", "N/A"),
            "type": p.get("player", {}).get("reason", "Lesión"),
            "position": p.get("player", {}).get("type", ""),
        }
        for p in data["response"]
    ]


async def _odds(session, fixture_id: int) -> dict:
    data = await fetch_json(
        session, f"{API_FOOTBALL_BASE}/odds", HEADERS_FOOTBALL,
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


async def _referee(session, referee_name: str) -> dict:
    if not referee_name:
        return {}
    data = await fetch_json(
        session, f"{API_FOOTBALL_BASE}/fixtures", HEADERS_FOOTBALL,
        {"referee": referee_name, "last": 20}
    )
    if not data or not data.get("response"):
        return {"name": referee_name}
    total = len(data["response"])
    total_goals = sum(
        (f["goals"].get("home") or 0) + (f["goals"].get("away") or 0)
        for f in data["response"]
    )
    over25 = sum(
        1 for f in data["response"]
        if (f["goals"].get("home") or 0) + (f["goals"].get("away") or 0) > 2
    )
    return {
        "name": referee_name,
        "matches": total,
        "avg_goals": round(total_goals / max(total, 1), 2),
        "over25_pct": round(over25 / max(total, 1) * 100, 1),
    }


async def _xg(session, team_id: int, league_id: int, season: int) -> dict:
    data = await fetch_json(
        session, f"{API_FOOTBALL_BASE}/fixtures", HEADERS_FOOTBALL,
        {"team": team_id, "league": league_id, "season": season, "last": 8, "status": "FT"}
    )
    if not data or not data.get("response"):
        return {"avg_xg": 0.0, "samples": 0}

    xg_list = []
    for f in data["response"]:
        stats = await fetch_json(
            session, f"{API_FOOTBALL_BASE}/fixtures/statistics", HEADERS_FOOTBALL,
            {"fixture": f["fixture"]["id"], "team": team_id}
        )
        if stats and stats.get("response"):
            for s in (stats["response"][0].get("statistics") or []):
                if s["type"] == "Expected_Goals" and s["value"]:
                    try:
                        xg_list.append(float(s["value"]))
                    except (ValueError, TypeError):
                        pass

    return {
        "avg_xg": round(sum(xg_list) / max(len(xg_list), 1), 2),
        "samples": len(xg_list),
    }


async def _ou_history(session, team_id: int, league_id: int, season: int) -> dict:
    data = await fetch_json(
        session, f"{API_FOOTBALL_BASE}/fixtures", HEADERS_FOOTBALL,
        {"team": team_id, "league": league_id, "season": season, "last": 20, "status": "FT"}
    )
    if not data or not data.get("response"):
        return {"over25_pct": 50.0, "avg_total_goals": 2.5, "samples": 0}

    games = data["response"]
    total = len(games)
    goals_list = [
        (f["goals"].get("home") or 0) + (f["goals"].get("away") or 0)
        for f in games
    ]
    over25 = sum(1 for g in goals_list if g > 2)
    return {
        "over25_pct": round(over25 / max(total, 1) * 100, 1),
        "avg_total_goals": round(sum(goals_list) / max(total, 1), 2),
        "samples": total,
    }


async def _weather(session, city: str) -> dict:
    if not city:
        return {}
    try:
        url = f"https://wttr.in/{city.replace(' ', '+')}?format=j1"
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=8)) as resp:
            if resp.status == 200:
                data = await resp.json(content_type=None)
                cur = data.get("current_condition", [{}])[0]
                return {
                    "temp_c": int(cur.get("temp_C", 20)),
                    "wind_kmph": int(cur.get("windspeedKmph", 0)),
                    "precip_mm": float(cur.get("precipMM", 0)),
                    "desc": (cur.get("weatherDesc") or [{}])[0].get("value", ""),
                }
    except Exception as e:
        logger.warning(f"Weather error {city}: {e}")
    return {}


async def _fatigue(session, team_id: int, today: str) -> dict:
    data = await fetch_json(
        session, f"{API_FOOTBALL_BASE}/fixtures", HEADERS_FOOTBALL,
        {"team": team_id, "last": 3, "status": "FT"}
    )
    if not data or not data.get("response"):
        return {"days_since_last": 7, "matches_last_14d": 0}

    today_date = datetime.strptime(today, "%Y-%m-%d").date()
    diffs = []
    last_14 = 0
    for f in data["response"]:
        try:
            d = datetime.strptime(f["fixture"]["date"][:10], "%Y-%m-%d").date()
            diff = (today_date - d).days
            if 0 <= diff:
                diffs.append(diff)
                if diff <= 14:
                    last_14 += 1
        except ValueError:
            pass

    return {
        "days_since_last": min(diffs) if diffs else 7,
        "matches_last_14d": last_14,
    }


# ══════════════════════════════════════════════════════════════
#  PUNTO DE ENTRADA PRINCIPAL
# ══════════════════════════════════════════════════════════════

async def fetch_all_games(sport_filter: str = None) -> list:
    today = get_today_cuba()
    all_fixtures = []

    async with aiohttp.ClientSession() as session:

        # ── FASE 1: carga masiva (1 llamada por deporte) ──────────
        bulk_tasks = []
        if sport_filter in (None, "soccer"):
            bulk_tasks.append(bulk_get_football(session, today))
        if sport_filter in (None, "basketball"):
            bulk_tasks.append(bulk_get_basketball(session, today))
        if sport_filter in (None, "baseball"):
            bulk_tasks.append(bulk_get_baseball(session, today))

        bulk_results = await asyncio.gather(*bulk_tasks, return_exceptions=True)
        for r in bulk_results:
            if isinstance(r, list):
                all_fixtures.extend(r)

        total_found = len(all_fixtures)
        logger.info(f"Total partidos cargados: {total_found}")

        # ── FASE 2: seleccionar top N por deporte ─────────────────
        soccer_top      = [f for f in all_fixtures if f["sport"] == "soccer"][:MAX_DEEP_FIXTURES]
        basketball_top  = [f for f in all_fixtures if f["sport"] == "basketball"][:5]
        baseball_top    = [f for f in all_fixtures if f["sport"] == "baseball"][:5]

        # ── FASE 3: análisis profundo de todos los deportes ───────
        all_deep_tasks = (
            [deep_analyze_fixture(session, f)    for f in soccer_top] +
            [deep_analyze_basketball(session, f) for f in basketball_top] +
            [deep_analyze_baseball(session, f)   for f in baseball_top]
        )
        deep_results = await asyncio.gather(*all_deep_tasks, return_exceptions=True)

        final = [r for r in deep_results if isinstance(r, dict)]

    logger.info(f"Análisis profundo completado: {len(final)} partidos")
    return final
