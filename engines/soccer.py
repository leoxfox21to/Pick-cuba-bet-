from config import MIN_CONFIDENCE


def analyze(match: dict) -> dict | None:
    home = match["home"]
    away = match["away"]
    sh   = match.get("stats_home", {})
    sa   = match.get("stats_away", {})
    vh   = match.get("venue_home", {})
    va   = match.get("venue_away", {})
    h2h  = match.get("h2h", [])
    inj_h = match.get("injuries_home", [])
    inj_a = match.get("injuries_away", [])
    odds  = match.get("odds", {})
    ref   = match.get("referee", {})
    xg_h  = match.get("xg_home", {})
    xg_a  = match.get("xg_away", {})
    ou_h  = match.get("ou_home", {})
    ou_a  = match.get("ou_away", {})
    fat_h = match.get("fatigue_home", {})
    fat_a = match.get("fatigue_away", {})
    wea   = match.get("weather", {})

    if not sh or not sa:
        return None

    # ── Estadísticas generales ─────────────────────────────
    def wr(s):
        t = max(s.get("wins", 0) + s.get("draws", 0) + s.get("losses", 0), 1)
        return s.get("wins", 0) / t

    wr_h = wr(sh); wr_a = wr(sa)
    form_h = sh.get("form", ""); form_a = sa.get("form", "")
    fs_h = form_h.count("W") * 3 + form_h.count("D")
    fs_a = form_a.count("W") * 3 + form_a.count("D")

    avg_gf_h = sh.get("avg_gf", 0.0)
    avg_ga_h = sh.get("avg_ga", 0.0)
    avg_gf_a = sa.get("avg_gf", 0.0)
    avg_ga_a = sa.get("avg_ga", 0.0)

    # Home/Away specific
    hw_h = vh.get("wins", 0); hl_h = vh.get("losses", 0)
    vh_total = max(hw_h + vh.get("draws", 0) + hl_h, 1)
    wr_h_home = hw_h / vh_total

    aw_a = va.get("wins", 0); al_a = va.get("losses", 0)
    va_total = max(aw_a + va.get("draws", 0) + al_a, 1)
    wr_a_away = aw_a / va_total

    # H2H
    h2h_hw = sum(1 for g in h2h if g.get("home_win"))
    h2h_aw = sum(1 for g in h2h if g.get("away_win"))
    h2h_avg = sum(g.get("total", 0) for g in h2h) / max(len(h2h), 1)
    h2h_over = sum(1 for g in h2h if g.get("total", 0) > 2)

    # Injuries
    def inj_weight(inj):
        score = 0
        for p in inj:
            pos = p.get("pos", "").lower()
            score += 8 if "goalkeeper" in pos else 6 if "forward" in pos else 4 if "defender" in pos else 3
        return min(score, 25)

    iw_h = inj_weight(inj_h); iw_a = inj_weight(inj_a)

    # Odds implied probability
    def ip(odd): return round(1 / odd * 100, 1) if odd and odd > 1 else 0
    ip_h = ip(odds.get("home", 0))
    ip_a = ip(odds.get("away", 0))
    ip_d = ip(odds.get("draw", 0))
    ip_o25 = ip(odds.get("over25", 0))
    ip_b   = ip(odds.get("btts", 0))

    # xG
    xg_avg_h = xg_h.get("avg", 0.0)
    xg_avg_a = xg_a.get("avg", 0.0)
    has_xg = xg_h.get("n", 0) >= 3 and xg_a.get("n", 0) >= 3

    # O/U history
    ou_pct_h = ou_h.get("over25_pct", 50.0)
    ou_pct_a = ou_a.get("over25_pct", 50.0)
    ou_avg = (ou_pct_h + ou_pct_a) / 2
    ou_goals_avg = ((ou_h.get("avg_goals", 2.5) + ou_a.get("avg_goals", 2.5)) / 2)

    # Fatigue
    days_h = fat_h.get("days", 7); days_a = fat_a.get("days", 7)
    l14_h  = fat_h.get("last14", 0); l14_a  = fat_a.get("last14", 0)
    fat_score_h = min(days_h, 7) + max(0, (3 - l14_h) * 2)
    fat_score_a = min(days_a, 7) + max(0, (3 - l14_a) * 2)

    # Referee
    ref_avg_g   = ref.get("avg_goals", 0.0) if isinstance(ref, dict) else 0.0
    ref_over_pct = ref.get("over25_pct", 0.0) if isinstance(ref, dict) else 0.0

    # Weather
    wind = wea.get("wind", 0); rain = wea.get("rain", 0)
    bad_weather = wind > 40 or rain > 5

    # ── Factores de análisis (texto) ──────────────────────
    factors = []
    factors.append(f"📋 *Forma reciente:* {home} `{form_h or 'N/A'}` | {away} `{form_a or 'N/A'}`")
    factors.append(f"🏠 *Rendimiento local/visitante:* {home} casa {vh.get('wins',0)}V/{vh.get('losses',0)}D | {away} fuera {va.get('wins',0)}V/{va.get('losses',0)}D")
    factors.append(f"⚽ *Goles prom:* {home} {avg_gf_h:.1f}F/{avg_ga_h:.1f}C | {away} {avg_gf_a:.1f}F/{avg_ga_a:.1f}C")

    if has_xg:
        factors.append(f"📊 *xG (goles esperados):* {home} {xg_avg_h} | {away} {xg_avg_a}")

    if h2h:
        factors.append(f"🔄 *Head to Head (últimos {len(h2h)}):* {home} {h2h_hw}W / Empate {len(h2h)-h2h_hw-h2h_aw} / {away} {h2h_aw}W | Prom goles: {h2h_avg:.1f}")

    if inj_h or inj_a:
        inj_txt = ""
        if inj_h: inj_txt += f"{home}: {len(inj_h)} baja(s) "
        if inj_a: inj_txt += f"{away}: {len(inj_a)} baja(s)"
        factors.append(f"🚑 *Lesiones:* {inj_txt.strip()}")

    if ip_h:
        factors.append(f"💹 *Cuotas Bet365:* Local {odds.get('home','?')} ({ip_h}%) | Empate {odds.get('draw','?')} ({ip_d}%) | Visitante {odds.get('away','?')} ({ip_a}%)")

    if isinstance(ref, dict) and ref.get("matches", 0) >= 5:
        factors.append(f"👨‍⚖️ *Árbitro {ref.get('name','?')}:* {ref.get('matches')} partidos | Prom goles: {ref_avg_g} | Over 2.5: {ref_over_pct}%")

    if ou_h.get("n", 0) >= 5:
        factors.append(f"📈 *Hist. Over 2.5:* {home} {ou_pct_h}% | {away} {ou_pct_a}% | Prom total: {ou_goals_avg:.1f} goles")

    factors.append(f"😴 *Descanso:* {home} {days_h} días ({l14_h} partidos/14d) | {away} {days_a} días ({l14_a} partidos/14d)")

    if wea:
        factors.append(f"🌤 *Clima {match.get('city','')}:* {wea.get('desc','')} {wea.get('temp','')}°C | Viento {wind}km/h | Lluvia {rain}mm")

    # ── Motor de scoring ──────────────────────────────────
    def score_home():
        s = 52
        s += 5  # home advantage
        if wr_h_home > 0.55: s += 12
        elif wr_h_home > 0.45: s += 6
        if wr_h > wr_a + 0.12: s += 8
        if fs_h > fs_a + 3: s += 6
        if h2h_hw > h2h_aw + 1: s += 5
        if iw_a > iw_h + 8: s += 7
        elif iw_h > iw_a + 8: s -= 8
        if ip_h > 50: s += min((ip_h - 50) * 0.4, 10)
        if has_xg and xg_avg_h > xg_avg_a + 0.3: s += 6
        if fat_score_h > fat_score_a + 4: s += 4
        elif fat_score_a > fat_score_h + 4: s -= 3
        return min(s, 93)

    def score_away():
        s = 46
        if wr_a_away > 0.42: s += 10
        if wr_a > wr_h + 0.10: s += 8
        if fs_a > fs_h + 3: s += 6
        if h2h_aw > h2h_hw + 1: s += 5
        if iw_h > iw_a + 8: s += 8
        elif iw_a > iw_h + 8: s -= 6
        if ip_a > 40: s += min((ip_a - 30) * 0.35, 10)
        if has_xg and xg_avg_a > xg_avg_h + 0.3: s += 6
        return min(s, 90)

    def score_over25():
        s = 50
        exp = avg_gf_h + avg_gf_a
        if exp > 3.0: s += 12
        elif exp > 2.5: s += 7
        if ou_avg > 65: s += 10
        elif ou_avg > 55: s += 5
        if h2h_avg > 2.8: s += 8
        elif h2h_avg > 2.3: s += 4
        if ref_avg_g > 3.0: s += 6
        elif ref_avg_g > 2.5: s += 3
        if has_xg and (xg_avg_h + xg_avg_a) > 2.5: s += 7
        if ip_o25 > 55: s += min((ip_o25 - 50) * 0.3, 8)
        if bad_weather: s -= 10
        if iw_h + iw_a > 20: s -= 4
        return min(s, 92)

    def score_btts():
        s = 50
        if avg_gf_h > 1.3 and avg_gf_a > 1.0: s += 10
        if avg_ga_h > 1.0 and avg_ga_a > 1.0: s += 8
        btts_h2h = sum(1 for g in h2h if g.get("home_goals", 0) > 0 and g.get("away_goals", 0) > 0)
        if h2h and btts_h2h / len(h2h) > 0.6: s += 8
        if ip_b > 55: s += min((ip_b - 50) * 0.3, 8)
        if has_xg and xg_avg_h > 1.0 and xg_avg_a > 0.8: s += 6
        if bad_weather: s -= 8
        if sh.get("clean_sheets", 0) > 5: s -= 5
        if sa.get("clean_sheets", 0) > 5: s -= 5
        return min(s, 90)

    def score_under25():
        s = 50
        exp = avg_gf_h + avg_gf_a
        if exp < 2.0: s += 12
        elif exp < 2.5: s += 6
        if ou_avg < 40: s += 10
        if h2h_avg < 2.0: s += 8
        if ref_avg_g < 2.3: s += 6
        if bad_weather: s += 10
        if iw_h + iw_a > 20: s += 6
        if sh.get("clean_sheets", 0) > 6 or sa.get("clean_sheets", 0) > 6: s += 5
        return min(s, 88)

    options = [
        {"pick": f"Victoria {home}",       "type": "1X2 — Local gana",       "odd": odds.get("home") or round(1/max(wr_h,0.25),2), "score": score_home()},
        {"pick": f"Victoria {away}",        "type": "1X2 — Visitante gana",   "odd": odds.get("away") or round(1/max(wr_a,0.25)*1.1,2), "score": score_away()},
        {"pick": "Más de 2.5 goles",        "type": "Over/Under — Over 2.5",  "odd": odds.get("over25") or 1.85, "score": score_over25()},
        {"pick": "Ambos equipos anotan",    "type": "BTTS — Sí",              "odd": odds.get("btts") or 1.75,  "score": score_btts()},
        {"pick": "Menos de 2.5 goles",      "type": "Over/Under — Under 2.5", "odd": odds.get("under25") or 2.10,"score": score_under25()},
    ]

    best = max(options, key=lambda x: x["score"])
    conf = min(best["score"], 95)

    if conf < MIN_CONFIDENCE:
        return None

    inj_note = ""
    if inj_h or inj_a:
        parts = []
        if inj_h: parts.append(f"{home} ({len(inj_h)})")
        if inj_a: parts.append(f"{away} ({len(inj_a)})")
        inj_note = f"⚠️ Bajas: {' / '.join(parts)}"

    return {
        "sport": "soccer",
        "home": home, "away": away,
        "league": match["league"],
        "time": match["time"],
        "factors": factors,
        "pick": best["pick"],
        "bet_type": best["type"],
        "odds": f"{float(best['odd']):.2f}",
        "confidence": conf,
        "injuries_note": inj_note,
        "value": _value_rating(conf, best["odd"]),
    }


def _value_rating(conf: int, odd) -> str:
    try:
        model_prob = conf / 100
        market_prob = 1 / float(odd)
        edge = (model_prob - market_prob) * 100
        if edge >= 8:   return "🔥 Valor ALTO"
        elif edge >= 3: return "✅ Valor MEDIO"
        elif edge >= 0: return "🟡 Sin gran valor"
        else:           return "⛔ Sin valor"
    except (TypeError, ZeroDivisionError):
        return "—"
