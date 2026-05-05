from config import MIN_CONFIDENCE


def analyze(match: dict) -> dict | None:
    home = match["home"]
    away = match["away"]
    hs = match.get("home_stats", {})
    as_ = match.get("away_stats", {})
    h_st = match.get("home_standing", {})
    a_st = match.get("away_standing", {})

    hw = hs.get("w", 0); hl = hs.get("l", 0)
    h_wr = hs.get("wr", 0.5)
    h_rpg = hs.get("rpg", 0.0); h_rag = hs.get("rag", 0.0)

    aw = as_.get("w", 0); al = as_.get("l", 0)
    a_wr = as_.get("wr", 0.5)
    a_rpg = as_.get("rpg", 0.0); a_rag = as_.get("rag", 0.0)

    h_sw = h_st.get("won", 0) or 0
    h_sl = h_st.get("lost", 0) or 0
    a_sw = a_st.get("won", 0) or 0
    a_sl = a_st.get("lost", 0) or 0

    h_swr = h_sw / max(h_sw + h_sl, 1)
    a_swr = a_sw / max(a_sw + a_sl, 1)

    factors = []
    if h_rpg or a_rpg:
        factors.append(f"📋 *Forma reciente (10 juegos):* {home} {hw}V/{hl}D | {away} {aw}V/{al}D")
        factors.append(f"🏃 *Carreras prom:* {home} {h_rpg:.1f}F/{h_rag:.1f}C | {away} {a_rpg:.1f}F/{a_rag:.1f}C")
        run_diff_h = round(h_rpg - h_rag, 2)
        run_diff_a = round(a_rpg - a_rag, 2)
        factors.append(f"📊 *Diferencia de carreras:* {home} {'+' if run_diff_h>=0 else ''}{run_diff_h} | {away} {'+' if run_diff_a>=0 else ''}{run_diff_a}")
    if h_sw or a_sw:
        factors.append(f"🏆 *Temporada completa:* {home} {h_sw}V/{h_sl}D ({h_swr:.0%}) | {away} {a_sw}V/{a_sl}D ({a_swr:.0%})")
    factors.append("🏠 *Ventaja local en béisbol:* ~54% históricamente")

    # Scoring
    score = 52 + 4  # base + home advantage
    if h_wr > a_wr + 0.08: score += 9
    elif a_wr > h_wr + 0.08: score -= 8
    if h_rpg > a_rpg + 0.7: score += 5
    elif a_rpg > h_rpg + 0.7: score -= 4
    if h_rpg - h_rag > a_rpg - a_rag + 0.5: score += 4
    if h_swr > a_swr + 0.06: score += 6
    elif a_swr > h_swr + 0.06: score -= 5

    total_runs_exp = h_rpg + a_rpg

    if score >= 57:
        pick = f"Victoria {home} (Local)"
        bet_type = "Moneyline — Local gana"
        odd = round(1 / max(h_wr + 0.04, 0.3), 2)
        conf = min(score, 85)
    elif score <= 47:
        pick = f"Victoria {away} (Visitante)"
        bet_type = "Moneyline — Visitante gana"
        odd = round(1 / max(a_wr, 0.3) * 1.08, 2)
        conf = min(100 - score + 8, 83)
    elif total_runs_exp >= 9.5:
        pick = "Más de 8.5 carreras"
        bet_type = "Over/Under — Over 8.5"
        odd = 1.90
        conf = min(62 + int((total_runs_exp - 9.5) * 5), 82)
    elif total_runs_exp <= 7.5:
        pick = "Menos de 8.5 carreras"
        bet_type = "Over/Under — Under 8.5"
        odd = 1.90
        conf = min(62 + int((8.5 - total_runs_exp) * 5), 80)
    else:
        pick = f"Victoria {home} (Local)"
        bet_type = "Moneyline — Local gana"
        odd = 1.82
        conf = 65

    if conf < MIN_CONFIDENCE:
        return None

    return {
        "sport": "baseball",
        "home": home, "away": away,
        "league": match["league"],
        "time": match["time"],
        "factors": factors,
        "pick": pick,
        "bet_type": bet_type,
        "odds": f"{odd:.2f}",
        "confidence": conf,
        "injuries_note": "",
        "value": "—",
    }
