import asyncio
from fetcher import fetch_all_games
from config import MIN_CONFIDENCE
import logging

logger = logging.getLogger(__name__)


# ─── FOOTBALL ANALYZER ───────────────────────────────────────────────────────

def analyze_football(game: dict) -> dict | None:
    home = game["home"]
    away = game["away"]
    sh = game.get("stats_home", {})
    sa = game.get("stats_away", {})
    hfh = game.get("home_form_home", {})   # home team stats at home
    afa = game.get("away_form_away", {})   # away team stats away
    h2h = game.get("h2h", [])
    injuries_h = game.get("injuries_home", [])
    injuries_a = game.get("injuries_away", [])
    odds = game.get("odds", {})
    ref = game.get("referee_data", {})
    xg_h = game.get("xg_home", {})
    xg_a = game.get("xg_away", {})
    fatigue_h = game.get("fatigue_home", {})
    fatigue_a = game.get("fatigue_away", {})
    ou_h = game.get("ou_history_home", {})
    ou_a = game.get("ou_history_away", {})
    weather = game.get("weather", {})

    if not sh or not sa:
        return None

    # ── Base stats ─────────────────────────────────────
    wins_h = sh.get("wins", 0) or 0
    wins_a = sa.get("wins", 0) or 0
    draws_h = sh.get("draws", 0) or 0
    draws_a = sa.get("draws", 0) or 0
    losses_h = sh.get("losses", 0) or 0
    losses_a = sa.get("losses", 0) or 0
    total_h = max(wins_h + draws_h + losses_h, 1)
    total_a = max(wins_a + draws_a + losses_a, 1)
    win_rate_h = wins_h / total_h
    win_rate_a = wins_a / total_a

    avg_gf_h = sh.get("avg_goals_for", 0.0) or 0.0
    avg_ga_h = sh.get("avg_goals_against", 0.0) or 0.0
    avg_gf_a = sa.get("avg_goals_for", 0.0) or 0.0
    avg_ga_a = sa.get("avg_goals_against", 0.0) or 0.0

    form_h = (sh.get("form", "") or "")[-5:]
    form_a = (sa.get("form", "") or "")[-5:]
    form_score_h = form_h.count("W") * 3 + form_h.count("D")
    form_score_a = form_a.count("W") * 3 + form_a.count("D")

    # ── Home/Away specific form ────────────────────────
    hw = hfh.get("wins", 0) or 0
    hd = hfh.get("draws", 0) or 0
    hl = hfh.get("losses", 0) or 0
    htotal = max(hw + hd + hl, 1)
    home_win_rate_venue = hw / htotal

    aw = afa.get("wins", 0) or 0
    ad = afa.get("draws", 0) or 0
    al = afa.get("losses", 0) or 0
    atotal = max(aw + ad + al, 1)
    away_win_rate_venue = aw / atotal

    avg_gf_h_home = hfh.get("avg_gf", avg_gf_h)
    avg_gf_a_away = afa.get("avg_gf", avg_gf_a)

    # ── xG ────────────────────────────────────────────
    xg_avg_h = xg_h.get("avg_xg", 0.0) or 0.0
    xg_avg_a = xg_a.get("avg_xg", 0.0) or 0.0
    has_xg = xg_h.get("samples", 0) > 3 and xg_a.get("samples", 0) > 3

    # ── H2H ───────────────────────────────────────────
    h2h_home_w = sum(1 for g in h2h if g.get("home_winner"))
    h2h_away_w = sum(1 for g in h2h if g.get("away_winner"))
    h2h_draws = len(h2h) - h2h_home_w - h2h_away_w
    h2h_avg_goals = (
        sum(g.get("total_goals", 0) for g in h2h) / max(len(h2h), 1)
    )
    h2h_over25 = sum(1 for g in h2h if g.get("total_goals", 0) > 2)

    # ── Injuries impact ────────────────────────────────
    def injury_impact(injuries: list) -> int:
        score = 0
        for inj in injuries:
            pos = (inj.get("position") or "").lower()
            if "goalkeeper" in pos or "portero" in pos:
                score += 8
            elif "defender" in pos or "defensa" in pos:
                score += 4
            elif "midfielder" in pos or "centrocampista" in pos:
                score += 3
            elif "forward" in pos or "delantero" in pos:
                score += 6
            else:
                score += 2
        return min(score, 25)

    inj_impact_h = injury_impact(injuries_h)
    inj_impact_a = injury_impact(injuries_a)

    # ── Bookmaker odds implied probability ────────────
    odds_home = odds.get("odds_home", 0.0)
    odds_away = odds.get("odds_away", 0.0)
    odds_draw = odds.get("odds_draw", 0.0)
    odds_over25 = odds.get("odds_over25", 0.0)
    odds_btts = odds.get("odds_btts_yes", 0.0)

    def implied_prob(odd: float) -> float:
        if odd and odd > 1:
            return round(1 / odd * 100, 1)
        return 0.0

    ip_home = implied_prob(odds_home)
    ip_away = implied_prob(odds_away)
    ip_draw = implied_prob(odds_draw)
    ip_over25 = implied_prob(odds_over25)
    ip_btts = implied_prob(odds_btts)

    # ── Referee ────────────────────────────────────────
    ref_avg_goals = ref.get("avg_goals", 0.0) or 0.0
    ref_over25_pct = ref.get("over25_pct", 0.0) or 0.0

    # ── Fatigue ────────────────────────────────────────
    days_h = fatigue_h.get("days_since_last", 7) or 7
    days_a = fatigue_a.get("days_since_last", 7) or 7
    matches14_h = fatigue_h.get("matches_last_14d", 0) or 0
    matches14_a = fatigue_a.get("matches_last_14d", 0) or 0

    fatigue_score_h = max(0, (3 - matches14_h) * 3) + min(days_h, 7)
    fatigue_score_a = max(0, (3 - matches14_a) * 3) + min(days_a, 7)

    # ── O/U history ────────────────────────────────────
    ou_pct_h = ou_h.get("over25_pct", 50.0) or 50.0
    ou_pct_a = ou_a.get("over25_pct", 50.0) or 50.0
    avg_ou_pct = (ou_pct_h + ou_pct_a) / 2
    avg_total_goals_ou = (
        (ou_h.get("avg_total_goals", 2.5) or 2.5) +
        (ou_a.get("avg_total_goals", 2.5) or 2.5)
    ) / 2

    # ── Weather impact ─────────────────────────────────
    wind = weather.get("wind_kmph", 0) or 0
    precip = weather.get("precip_mm", 0) or 0
    weather_reduces_goals = wind > 40 or precip > 5

    # ══════════════════════════════════════════════════
    #  SCORING: determine best pick
    # ══════════════════════════════════════════════════

    analysis_lines = []

    # Form line
    analysis_lines.append(
        f"  • Forma: {home} [{form_h or 'N/A'}] vs {away} [{form_a or 'N/A'}]"
    )

    # Home/away venue form
    analysis_lines.append(
        f"  • Local en casa: {hw}V/{hd}E/{hl}D | Visitante fuera: {aw}V/{ad}E/{al}D"
    )

    # Goals
    analysis_lines.append(
        f"  • Goles prom: {home} {avg_gf_h:.1f}F/{avg_ga_h:.1f}C | {away} {avg_gf_a:.1f}F/{avg_ga_a:.1f}C"
    )

    # xG
    if has_xg:
        analysis_lines.append(f"  • xG: {home} {xg_avg_h} | {away} {xg_avg_a}")

    # H2H
    if h2h:
        analysis_lines.append(
            f"  • H2H últimos {len(h2h)}: {home} {h2h_home_w}W / Empate {h2h_draws} / {away} {h2h_away_w}W | Prom goles: {h2h_avg_goals:.1f}"
        )

    # Injuries
    if injuries_h:
        analysis_lines.append(f"  • Bajas {home}: {len(injuries_h)} jugador(es)")
    if injuries_a:
        analysis_lines.append(f"  • Bajas {away}: {len(injuries_a)} jugador(es)")

    # Odds
    if ip_home:
        analysis_lines.append(
            f"  • Cuotas mercado: Local {odds_home} ({ip_home}%) | Empate {odds_draw} ({ip_draw}%) | Visitante {odds_away} ({ip_away}%)"
        )

    # Referee
    if ref.get("matches", 0):
        analysis_lines.append(
            f"  • Árbitro: {ref.get('name','N/A')} | Prom goles: {ref_avg_goals} | Over 2.5: {ref_over25_pct}%"
        )

    # Fatigue
    analysis_lines.append(
        f"  • Días descanso: {home} {days_h}d ({matches14_h} partidos/14d) | {away} {days_a}d ({matches14_a} partidos/14d)"
    )

    # O/U history
    if ou_h.get("samples", 0) > 5:
        analysis_lines.append(
            f"  • Historial Over 2.5: {home} {ou_pct_h}% | {away} {ou_pct_a}% | Prom total: {avg_total_goals_ou:.1f} goles"
        )

    # Weather
    if weather:
        w_desc = weather.get("desc", "")
        analysis_lines.append(
            f"  • Clima ({game.get('venue_city','')}): {w_desc}, {weather.get('temp_c','')}°C, Viento {wind}km/h, Lluvia {precip}mm"
        )

    # ── Score each possible pick ────────────────────────

    def score_home_win():
        s = 50
        s += 5  # home advantage base
        if home_win_rate_venue > 0.55:
            s += 12
        elif home_win_rate_venue > 0.45:
            s += 6
        if win_rate_h > win_rate_a + 0.12:
            s += 8
        if form_score_h > form_score_a + 3:
            s += 6
        if h2h_home_w > h2h_away_w + 1:
            s += 5
        if inj_impact_a > inj_impact_h + 8:
            s += 7
        elif inj_impact_h > inj_impact_a + 8:
            s -= 8
        if ip_home > 50:
            s += min((ip_home - 50) * 0.5, 10)
        if has_xg and xg_avg_h > xg_avg_a + 0.3:
            s += 6
        if fatigue_score_h > fatigue_score_a + 5:
            s += 4
        elif fatigue_score_a > fatigue_score_h + 5:
            s -= 3
        if weather_reduces_goals:
            s -= 2
        return min(s, 93)

    def score_away_win():
        s = 45
        if away_win_rate_venue > 0.40:
            s += 10
        if win_rate_a > win_rate_h + 0.10:
            s += 8
        if form_score_a > form_score_h + 3:
            s += 6
        if h2h_away_w > h2h_home_w + 1:
            s += 5
        if inj_impact_h > inj_impact_a + 8:
            s += 8
        elif inj_impact_a > inj_impact_h + 8:
            s -= 6
        if ip_away > 45:
            s += min((ip_away - 35) * 0.4, 10)
        if has_xg and xg_avg_a > xg_avg_h + 0.3:
            s += 6
        if fatigue_score_a > fatigue_score_h + 5:
            s += 3
        return min(s, 90)

    def score_over25():
        s = 50
        total_exp = avg_gf_h + avg_gf_a
        if total_exp > 3.0:
            s += 12
        elif total_exp > 2.5:
            s += 7
        if avg_ou_pct > 65:
            s += 10
        elif avg_ou_pct > 55:
            s += 5
        if h2h_avg_goals > 2.8:
            s += 8
        elif h2h_avg_goals > 2.3:
            s += 4
        if ref_avg_goals > 3.0:
            s += 6
        elif ref_avg_goals > 2.5:
            s += 3
        if has_xg and (xg_avg_h + xg_avg_a) > 2.5:
            s += 7
        if ip_over25 and ip_over25 > 55:
            s += min((ip_over25 - 50) * 0.4, 8)
        if weather_reduces_goals:
            s -= 10
        if inj_impact_h + inj_impact_a > 20:
            s -= 5
        return min(s, 92)

    def score_btts():
        s = 50
        if avg_gf_h > 1.3 and avg_gf_a > 1.0:
            s += 10
        if avg_ga_h > 1.0 and avg_ga_a > 1.0:
            s += 8
        btts_h2h = sum(1 for g in h2h if g.get("home_goals", 0) > 0 and g.get("away_goals", 0) > 0)
        if h2h and btts_h2h / len(h2h) > 0.6:
            s += 8
        if ip_btts and ip_btts > 55:
            s += min((ip_btts - 50) * 0.3, 8)
        if has_xg and xg_avg_h > 1.0 and xg_avg_a > 0.8:
            s += 6
        if weather_reduces_goals:
            s -= 8
        if sh.get("clean_sheets", 0) > 5:
            s -= 5
        if sa.get("clean_sheets", 0) > 5:
            s -= 5
        return min(s, 90)

    def score_under25():
        s = 50
        total_exp = avg_gf_h + avg_gf_a
        if total_exp < 2.0:
            s += 12
        elif total_exp < 2.5:
            s += 6
        if avg_ou_pct < 40:
            s += 10
        if h2h_avg_goals < 2.0:
            s += 8
        if ref_avg_goals < 2.3:
            s += 6
        if weather_reduces_goals:
            s += 8
        if inj_impact_h + inj_impact_a > 20:
            s += 6
        if sh.get("clean_sheets", 0) > 6 or sa.get("clean_sheets", 0) > 6:
            s += 5
        return min(s, 88)

    # Evaluate all options
    options = [
        {
            "pick": f"Victoria {home}",
            "bet_type": "1X2 - Local gana",
            "odds_val": odds_home or round(1 / max(win_rate_h, 0.25), 2),
            "confidence": score_home_win(),
        },
        {
            "pick": f"Victoria {away}",
            "bet_type": "1X2 - Visitante gana",
            "odds_val": odds_away or round(1 / max(win_rate_a, 0.25) * 1.1, 2),
            "confidence": score_away_win(),
        },
        {
            "pick": "Más de 2.5 goles",
            "bet_type": "Over/Under - Over 2.5",
            "odds_val": odds_over25 or 1.80,
            "confidence": score_over25(),
        },
        {
            "pick": "Ambos equipos anotan (SÍ)",
            "bet_type": "BTTS - Ambos marcan",
            "odds_val": odds_btts or 1.75,
            "confidence": score_btts(),
        },
        {
            "pick": "Menos de 2.5 goles",
            "bet_type": "Over/Under - Under 2.5",
            "odds_val": odds.get("odds_under25") or 2.10,
            "confidence": score_under25(),
        },
    ]

    best = max(options, key=lambda x: x["confidence"])

    if best["confidence"] < MIN_CONFIDENCE:
        return None

    return {
        "sport": "soccer",
        "home": home,
        "away": away,
        "league": game["league"],
        "time": game["time"],
        "analysis": "\n".join(analysis_lines),
        "pick": best["pick"],
        "bet_type": best["bet_type"],
        "odds": f"{best['odds_val']:.2f}",
        "confidence": best["confidence"],
        "injuries_note": (
            f"⚠️ Bajas: {home}({len(injuries_h)}) / {away}({len(injuries_a)})"
            if injuries_h or injuries_a else ""
        ),
    }


# ─── BASKETBALL ANALYZER ─────────────────────────────────────────────────────

def analyze_basketball(game: dict) -> dict | None:
    home = game["home"]
    away = game["away"]
    hs = game.get("home_stats", {})
    as_ = game.get("away_stats", {})
    h_stand = game.get("home_standing", {})
    a_stand = game.get("away_standing", {})

    hw = hs.get("wins", 0) or 0
    hl = hs.get("losses", 0) or 0
    h_wr = hs.get("win_rate", 0.5) or 0.5
    h_ppg = hs.get("avg_pts_for", 0) or 0
    h_apg = hs.get("avg_pts_against", 0) or 0

    aw = as_.get("wins", 0) or 0
    al = as_.get("losses", 0) or 0
    a_wr = as_.get("win_rate", 0.5) or 0.5
    a_ppg = as_.get("avg_pts_for", 0) or 0
    a_apg = as_.get("avg_pts_against", 0) or 0

    h_season_w = h_stand.get("won", 0) or 0
    h_season_l = h_stand.get("lost", 0) or 0
    a_season_w = a_stand.get("won", 0) or 0
    a_season_l = a_stand.get("lost", 0) or 0

    analysis_lines = []
    if h_ppg or a_ppg:
        analysis_lines.append(f"  • Forma reciente (últimos 10): {home} {hw}V/{hl}D | {away} {aw}V/{al}D")
        analysis_lines.append(f"  • Puntos prom: {home} {h_ppg:.1f}F/{h_apg:.1f}C | {away} {a_ppg:.1f}F/{a_apg:.1f}C")
    if h_season_w or a_season_w:
        analysis_lines.append(f"  • Temporada: {home} {h_season_w}V/{h_season_l}D | {away} {a_season_w}V/{a_season_l}D")
    analysis_lines.append(f"  • Ventaja de cancha local (~58% en ligas top)")

    if not analysis_lines:
        analysis_lines.append(f"  • {home} vs {away} — datos limitados")

    score = 55
    score += 5  # home court
    if h_wr > a_wr + 0.10:
        score += 10
    elif a_wr > h_wr + 0.10:
        score -= 8
    if h_ppg > a_ppg + 5:
        score += 5
    elif a_ppg > h_ppg + 5:
        score -= 4
    if h_season_w > 0 and a_season_w > 0:
        h_s_wr = h_season_w / max(h_season_w + h_season_l, 1)
        a_s_wr = a_season_w / max(a_season_w + a_season_l, 1)
        if h_s_wr > a_s_wr + 0.08:
            score += 7
        elif a_s_wr > h_s_wr + 0.08:
            score -= 6

    if score >= 58:
        pick = f"Victoria {home} (Local)"
        bet_type = "Resultado - Local gana"
        odds_val = round(1.0 / max(h_wr + 0.05, 0.3), 2)
    else:
        pick = f"Victoria {away} (Visitante)"
        bet_type = "Resultado - Visitante gana"
        odds_val = round(1.0 / max(a_wr, 0.3) * 1.1, 2)
        score = 100 - score

    confidence = min(max(score, 60), 88)
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
        "odds": f"{odds_val:.2f}",
        "confidence": confidence,
        "injuries_note": "",
    }


# ─── BASEBALL ANALYZER ───────────────────────────────────────────────────────

def analyze_baseball(game: dict) -> dict | None:
    home = game["home"]
    away = game["away"]
    hs = game.get("home_stats", {})
    as_ = game.get("away_stats", {})
    h_stand = game.get("home_standing", {})
    a_stand = game.get("away_standing", {})

    hw = hs.get("wins", 0) or 0
    hl = hs.get("losses", 0) or 0
    h_wr = hs.get("win_rate", 0.5) or 0.5
    h_rpg = hs.get("avg_runs_for", 0) or 0
    h_rag = hs.get("avg_runs_against", 0) or 0

    aw = as_.get("wins", 0) or 0
    al = as_.get("losses", 0) or 0
    a_wr = as_.get("win_rate", 0.5) or 0.5
    a_rpg = as_.get("avg_runs_for", 0) or 0
    a_rag = as_.get("avg_runs_against", 0) or 0

    h_season_w = h_stand.get("won", 0) or 0
    h_season_l = h_stand.get("lost", 0) or 0
    a_season_w = a_stand.get("won", 0) or 0
    a_season_l = a_stand.get("lost", 0) or 0

    analysis_lines = []
    if h_rpg or a_rpg:
        analysis_lines.append(f"  • Forma reciente (últimos 10): {home} {hw}V/{hl}D | {away} {aw}V/{al}D")
        analysis_lines.append(f"  • Carreras prom: {home} {h_rpg:.1f}F/{h_rag:.1f}C | {away} {a_rpg:.1f}F/{a_rag:.1f}C")
    if h_season_w or a_season_w:
        analysis_lines.append(f"  • Temporada: {home} {h_season_w}V/{h_season_l}D | {away} {a_season_w}V/{a_season_l}D")
    analysis_lines.append(f"  • Ventaja local histórica en béisbol (~54%)")

    score = 52
    score += 4  # home advantage
    if h_wr > a_wr + 0.08:
        score += 9
    elif a_wr > h_wr + 0.08:
        score -= 7
    if h_rpg > a_rpg + 0.5:
        score += 5
    elif a_rpg > h_rpg + 0.5:
        score -= 4
    if h_season_w > 0 and a_season_w > 0:
        h_s_wr = h_season_w / max(h_season_w + h_season_l, 1)
        a_s_wr = a_season_w / max(a_season_w + a_season_l, 1)
        if h_s_wr > a_s_wr + 0.06:
            score += 6
        elif a_s_wr > h_s_wr + 0.06:
            score -= 5

    total_avg_runs = h_rpg + a_rpg
    if score >= 56:
        pick = f"Victoria {home} (Local)"
        bet_type = "Moneyline - Local gana"
        odds_val = round(1.0 / max(h_wr + 0.04, 0.3), 2)
    elif score <= 46:
        pick = f"Victoria {away} (Visitante)"
        bet_type = "Moneyline - Visitante gana"
        odds_val = round(1.0 / max(a_wr, 0.3) * 1.08, 2)
        score = 100 - score
    elif total_avg_runs >= 9.0:
        pick = "Más de 8.5 carreras"
        bet_type = "Over/Under - Over 8.5"
        odds_val = 1.90
        score = 68
    else:
        pick = f"Victoria {home} (Local)"
        bet_type = "Moneyline - Local gana"
        odds_val = 1.82
        score = 65

    confidence = min(max(score, 60), 86)
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
        "odds": "1.80",
        "confidence": confidence,
        "injuries_note": "",
    }


# ─── MAIN ────────────────────────────────────────────────────────────────────

async def get_daily_picks(sport_filter: str = None) -> list:
    games = await fetch_all_games(sport_filter=sport_filter)

    picks = []
    for game in games:
        sport = game.get("sport")
        result = None
        try:
            if sport == "soccer":
                result = analyze_football(game)
            elif sport == "basketball":
                result = analyze_basketball(game)
            elif sport == "baseball":
                result = analyze_baseball(game)
        except Exception as e:
            logger.error(f"Error analizando {game.get('home')} vs {game.get('away')}: {e}")

        if result:
            picks.append(result)

    picks.sort(key=lambda x: x["confidence"], reverse=True)
    return picks[:15]
