import aiohttp
import asyncio
from datetime import datetime
from config import FOOTBALL_BASE, BASKETBALL_BASE, BASEBALL_BASE, HEADERS, CUBA_TZ
import logging

logger = logging.getLogger(__name__)


def today_cuba() -> str:
    return datetime.now(CUBA_TZ).strftime("%Y-%m-%d")


async def get(session, url, params=None):
    try:
        async with session.get(
            url, headers=HEADERS, params=params,
            timeout=aiohttp.ClientTimeout(total=12)
        ) as r:
            if r.status == 200:
                return await r.json()
            logger.warning(f"HTTP {r.status} {url}")
    except Exception as e:
        logger.error(f"fetch error {url}: {e}")
    return None


# ─────────────────────────────────────────────────────────────
#  FASE 1 — Carga de partidos del día (1 llamada por deporte)
# ─────────────────────────────────────────────────────────────

async def load_today_matches(sport_filter=None) -> list:
    date = today_cuba()
    matches = []

    async with aiohttp.ClientSession() as session:
        tasks = []
        if sport_filter in (None, "soccer"):
            tasks.append(_bulk_soccer(session, date))
        if sport_filter in (None, "basketball"):
            tasks.append(_bulk_basketball(session, date))
        if sport_filter in (None, "baseball"):
            tasks.append(_bulk_baseball(session, date))

        results = await asyncio.gather(*tasks, return_exceptions=True)
        for r in results:
            if isinstance(r, list):
                matches.extend(r)

    matches.sort(key=lambda x: x.get("priority", 0), reverse=True)
    logger.info(f"Partidos cargados hoy: {len(matches)}")
    return matches


LEAGUE_SCORE = {
    39: 100, 140: 98, 135: 96, 78: 95, 61: 94,
    2: 92, 3: 90, 94: 85, 88: 83, 71: 78,
    253: 75, 307: 65, 197: 63,
}


async def _bulk_soccer(session, date):
    data = await get(session, f"{FOOTBALL_BASE}/fixtures",
                     {"date": date, "timezone": "America/Havana"})
    if not data:
        return []
    out = []
    for f in data.get("response", []):
        if f["fixture"]["status"]["short"] not in ("NS", "TBD"):
            continue
        lid = f["league"]["id"]
        out.append({
            "sport": "soccer",
            "id": f["fixture"]["id"],
            "home": f["teams"]["home"]["name"],
            "home_id": f["teams"]["home"]["id"],
            "away": f["teams"]["away"]["name"],
            "away_id": f["teams"]["away"]["id"],
            "league": f["league"]["name"],
            "league_id": lid,
            "season": f["league"]["season"],
            "time": f["fixture"]["date"][11:16],
            "city": (f["fixture"].get("venue") or {}).get("city", ""),
            "referee": f["fixture"].get("referee") or "",
            "priority": LEAGUE_SCORE.get(lid, 30),
        })
    return out


async def _bulk_basketball(session, date):
    data = await get(session, f"{BASKETBALL_BASE}/games",
                     {"date": date, "timezone": "America/Havana"})
    if not data:
        return []
    out = []
    for g in data.get("response", []):
        out.append({
            "sport": "basketball",
            "id": g["id"],
            "home": g["teams"]["home"]["name"],
            "home_id": g["teams"]["home"]["id"],
            "away": g["teams"]["visitors"]["name"],
            "away_id": g["teams"]["visitors"]["id"],
            "league": g["league"]["name"],
            "league_id": g["league"]["id"],
            "season": str(g["league"].get("season", "")),
            "time": (g["date"].get("start") or "")[11:16],
            "city": "",
            "priority": 50,
        })
    return out


async def _bulk_baseball(session, date):
    data = await get(session, f"{BASEBALL_BASE}/games",
                     {"date": date, "timezone": "America/Havana"})
    if not data:
        return []
    out = []
    for g in data.get("response", []):
        out.append({
            "sport": "baseball",
            "id": g["id"],
            "home": g["teams"]["home"]["name"],
            "home_id": g["teams"]["home"]["id"],
            "away": g["teams"]["away"]["name"],
            "away_id": g["teams"]["away"]["id"],
            "league": g["league"]["name"],
            "league_id": g["league"]["id"],
            "season": str(g["league"].get("season", "")),
            "time": (g.get("date") or "")[11:16],
            "city": "",
            "priority": 45,
        })
    return out


# ─────────────────────────────────────────────────────────────
#  FASE 2 — Análisis profundo de UN partido seleccionado
# ─────────────────────────────────────────────────────────────

async def deep_analyze(match: dict) -> dict:
    sport = match["sport"]
    async with aiohttp.ClientSession() as session:
        if sport == "soccer":
            return await _deep_soccer(session, match)
        elif sport == "basketball":
            return await _deep_basketball(session, match)
        elif sport == "baseball":
            return await _deep_baseball(session, match)
    return match


# ── SOCCER deep ──────────────────────────────────────────────

async def _deep_soccer(session, m):
    hid, aid = m["home_id"], m["away_id"]
    lid, sea = m["league_id"], m["season"]

    (sh, sa, hh, ha, h2h, inj_h, inj_a, odds, ref, xg_h, xg_a, ou_h, ou_a, fat_h, fat_a, weather) = \
        await asyncio.gather(
            _soccer_team_stats(session, hid, lid, sea),
            _soccer_team_stats(session, aid, lid, sea),
            _soccer_venue_stats(session, hid, lid, sea, "home"),
            _soccer_venue_stats(session, aid, lid, sea, "away"),
            _soccer_h2h(session, hid, aid),
            _injuries(session, hid, sea),
            _injuries(session, aid, sea),
            _odds(session, m["id"]),
            _referee(session, m["referee"]),
            _xg(session, hid, lid, sea),
            _xg(session, aid, lid, sea),
            _ou_history(session, hid, lid, sea),
            _ou_history(session, aid, lid, sea),
            _fatigue(session, hid),
            _fatigue(session, aid),
            _weather(session, m["city"]),
        )

    return {**m,
            "stats_home": sh, "stats_away": sa,
            "venue_home": hh, "venue_away": ha,
            "h2h": h2h,
            "injuries_home": inj_h, "injuries_away": inj_a,
            "odds": odds, "referee": ref,
            "xg_home": xg_h, "xg_away": xg_a,
            "ou_home": ou_h, "ou_away": ou_a,
            "fatigue_home": fat_h, "fatigue_away": fat_a,
            "weather": weather}


async def _soccer_team_stats(session, tid, lid, sea):
    d = await get(session, f"{FOOTBALL_BASE}/teams/statistics",
                  {"team": tid, "league": lid, "season": sea})
    if not d or "response" not in d:
        return {}
    r = d["response"]
    return {
        "wins":   r.get("fixtures", {}).get("wins", {}).get("total", 0) or 0,
        "draws":  r.get("fixtures", {}).get("draws", {}).get("total", 0) or 0,
        "losses": r.get("fixtures", {}).get("loses", {}).get("total", 0) or 0,
        "avg_gf": float(r.get("goals", {}).get("for",     {}).get("average", {}).get("total", 0) or 0),
        "avg_ga": float(r.get("goals", {}).get("against", {}).get("average", {}).get("total", 0) or 0),
        "clean_sheets": r.get("clean_sheet", {}).get("total", 0) or 0,
        "form": (r.get("form") or "")[-5:],
    }


async def _soccer_venue_stats(session, tid, lid, sea, venue):
    d = await get(session, f"{FOOTBALL_BASE}/teams/statistics",
                  {"team": tid, "league": lid, "season": sea})
    if not d or "response" not in d:
        return {}
    r = d["response"]
    return {
        "wins":   r.get("fixtures", {}).get("wins",  {}).get(venue, 0) or 0,
        "draws":  r.get("fixtures", {}).get("draws", {}).get(venue, 0) or 0,
        "losses": r.get("fixtures", {}).get("loses", {}).get(venue, 0) or 0,
        "avg_gf": float(r.get("goals", {}).get("for",     {}).get("average", {}).get(venue, 0) or 0),
        "avg_ga": float(r.get("goals", {}).get("against", {}).get("average", {}).get(venue, 0) or 0),
    }


async def _soccer_h2h(session, t1, t2):
    d = await get(session, f"{FOOTBALL_BASE}/fixtures/headtohead",
                  {"h2h": f"{t1}-{t2}", "last": 10})
    if not d:
        return []
    out = []
    for f in d.get("response", []):
        gh = f["goals"].get("home") or 0
        ga = f["goals"].get("away") or 0
        out.append({
            "home_goals": gh, "away_goals": ga, "total": gh + ga,
            "home_win": f["teams"]["home"].get("winner"),
            "away_win": f["teams"]["away"].get("winner"),
        })
    return out


async def _injuries(session, tid, sea):
    d = await get(session, f"{FOOTBALL_BASE}/injuries",
                  {"team": tid, "season": sea})
    if not d:
        return []
    return [{"player": p.get("player", {}).get("name", "?"),
             "pos": p.get("player", {}).get("type", "")}
            for p in d.get("response", [])]


async def _odds(session, fid):
    d = await get(session, f"{FOOTBALL_BASE}/odds",
                  {"fixture": fid, "bookmaker": 6})
    if not d or not d.get("response"):
        return {}
    try:
        bets = d["response"][0]["bookmakers"][0]["bets"]
        res = {}
        for bet in bets:
            if bet["name"] == "Match Winner":
                for v in bet["values"]:
                    if v["value"] == "Home":  res["home"]   = float(v["odd"])
                    elif v["value"] == "Away": res["away"]   = float(v["odd"])
                    elif v["value"] == "Draw": res["draw"]   = float(v["odd"])
            elif bet["name"] == "Goals Over/Under":
                for v in bet["values"]:
                    if v["value"] == "Over 2.5":  res["over25"]  = float(v["odd"])
                    elif v["value"] == "Under 2.5": res["under25"] = float(v["odd"])
            elif bet["name"] == "Both Teams Score":
                for v in bet["values"]:
                    if v["value"] == "Yes": res["btts"] = float(v["odd"])
        return res
    except (IndexError, KeyError):
        return {}


async def _referee(session, name):
    if not name:
        return {}
    d = await get(session, f"{FOOTBALL_BASE}/fixtures",
                  {"referee": name, "last": 20})
    if not d or not d.get("response"):
        return {"name": name}
    games = d["response"]
    total = len(games)
    total_goals = sum((f["goals"].get("home") or 0) + (f["goals"].get("away") or 0) for f in games)
    over25 = sum(1 for f in games if (f["goals"].get("home") or 0) + (f["goals"].get("away") or 0) > 2)
    return {
        "name": name,
        "matches": total,
        "avg_goals": round(total_goals / max(total, 1), 2),
        "over25_pct": round(over25 / max(total, 1) * 100, 1),
    }


async def _xg(session, tid, lid, sea):
    d = await get(session, f"{FOOTBALL_BASE}/fixtures",
                  {"team": tid, "league": lid, "season": sea, "last": 8, "status": "FT"})
    if not d or not d.get("response"):
        return {"avg": 0.0, "n": 0}
    vals = []
    for f in d["response"]:
        s = await get(session, f"{FOOTBALL_BASE}/fixtures/statistics",
                      {"fixture": f["fixture"]["id"], "team": tid})
        if s and s.get("response"):
            for stat in (s["response"][0].get("statistics") or []):
                if stat["type"] == "Expected_Goals" and stat["value"]:
                    try:
                        vals.append(float(stat["value"]))
                    except (ValueError, TypeError):
                        pass
    return {"avg": round(sum(vals) / max(len(vals), 1), 2), "n": len(vals)}


async def _ou_history(session, tid, lid, sea):
    d = await get(session, f"{FOOTBALL_BASE}/fixtures",
                  {"team": tid, "league": lid, "season": sea, "last": 20, "status": "FT"})
    if not d or not d.get("response"):
        return {"over25_pct": 50.0, "avg_goals": 2.5, "n": 0}
    games = d["response"]
    totals = [(f["goals"].get("home") or 0) + (f["goals"].get("away") or 0) for f in games]
    n = len(totals)
    return {
        "over25_pct": round(sum(1 for g in totals if g > 2) / max(n, 1) * 100, 1),
        "avg_goals": round(sum(totals) / max(n, 1), 2),
        "n": n,
    }


async def _fatigue(session, tid):
    today = datetime.now(CUBA_TZ).date()
    d = await get(session, f"{FOOTBALL_BASE}/fixtures",
                  {"team": tid, "last": 3, "status": "FT"})
    if not d or not d.get("response"):
        return {"days": 7, "last14": 0}
    diffs, last14 = [], 0
    for f in d["response"]:
        try:
            dt = datetime.strptime(f["fixture"]["date"][:10], "%Y-%m-%d").date()
            diff = (today - dt).days
            if diff >= 0:
                diffs.append(diff)
                if diff <= 14:
                    last14 += 1
        except ValueError:
            pass
    return {"days": min(diffs) if diffs else 7, "last14": last14}


async def _weather(session, city):
    if not city:
        return {}
    try:
        url = f"https://wttr.in/{city.replace(' ', '+')}?format=j1"
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=6)) as r:
            if r.status == 200:
                data = await r.json(content_type=None)
                c = data.get("current_condition", [{}])[0]
                return {
                    "temp": int(c.get("temp_C", 20)),
                    "wind": int(c.get("windspeedKmph", 0)),
                    "rain": float(c.get("precipMM", 0)),
                    "desc": (c.get("weatherDesc") or [{}])[0].get("value", ""),
                }
    except Exception:
        pass
    return {}


# ── BASKETBALL deep ──────────────────────────────────────────

async def _deep_basketball(session, m):
    hid, aid = m["home_id"], m["away_id"]
    lid, sea = m["league_id"], m["season"]

    hg, ag, standings = await asyncio.gather(
        _sport_games(session, BASKETBALL_BASE, hid, sea),
        _sport_games(session, BASKETBALL_BASE, aid, sea),
        _sport_standings(session, BASKETBALL_BASE, lid, sea),
    )

    def parse(games, tid):
        w, l, pf, pa = 0, 0, 0, 0
        for g in games:
            hs = g.get("scores", {}).get("home", {}).get("total") or 0
            vs = g.get("scores", {}).get("visitors", {}).get("total") or 0
            is_home = g["teams"]["home"]["id"] == tid
            mf, ma = (hs, vs) if is_home else (vs, hs)
            pf += mf; pa += ma
            if mf > ma: w += 1
            else: l += 1
        n = max(w + l, 1)
        return {"w": w, "l": l, "wr": round(w / n, 3),
                "ppg": round(pf / n, 1), "apg": round(pa / n, 1)}

    def find_standing(data, tid):
        for grp in data:
            for e in (grp if isinstance(grp, list) else [grp]):
                if (e.get("team") or {}).get("id") == tid:
                    return e
        return {}

    return {**m,
            "home_stats": parse(hg, hid),
            "away_stats": parse(ag, aid),
            "home_standing": find_standing(standings, hid),
            "away_standing": find_standing(standings, aid)}


# ── BASEBALL deep ────────────────────────────────────────────

async def _deep_baseball(session, m):
    hid, aid = m["home_id"], m["away_id"]
    lid, sea = m["league_id"], m["season"]

    hg, ag, standings = await asyncio.gather(
        _sport_games(session, BASEBALL_BASE, hid, sea),
        _sport_games(session, BASEBALL_BASE, aid, sea),
        _sport_standings(session, BASEBALL_BASE, lid, sea),
    )

    def parse(games, tid):
        w, l, rf, ra = 0, 0, 0, 0
        for g in games:
            hs = g.get("scores", {}).get("home", {}).get("total") or 0
            vs = g.get("scores", {}).get("away", {}).get("total") or 0
            is_home = g["teams"]["home"]["id"] == tid
            mf, ma = (hs, vs) if is_home else (vs, hs)
            rf += mf; ra += ma
            if mf > ma: w += 1
            else: l += 1
        n = max(w + l, 1)
        return {"w": w, "l": l, "wr": round(w / n, 3),
                "rpg": round(rf / n, 2), "rag": round(ra / n, 2)}

    def find_standing(data, tid):
        for grp in data:
            for e in (grp if isinstance(grp, list) else [grp]):
                if (e.get("team") or {}).get("id") == tid:
                    return e
        return {}

    return {**m,
            "home_stats": parse(hg, hid),
            "away_stats": parse(ag, aid),
            "home_standing": find_standing(standings, hid),
            "away_standing": find_standing(standings, aid)}


async def _sport_games(session, base, tid, sea):
    d = await get(session, f"{base}/games", {"team": tid, "season": sea, "last": 10})
    return (d or {}).get("response", [])


async def _sport_standings(session, base, lid, sea):
    d = await get(session, f"{base}/standings", {"league": lid, "season": sea})
    return (d or {}).get("response", [])
