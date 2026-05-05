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
    h_ppg = hs.get("ppg", 0.0); h_apg = hs.get("apg", 0.0)

    aw = as_.get("w", 0); al = as_.get("l", 0)
    a_wr = as_.get("wr", 0.5)
    a_ppg = as_.get("ppg", 0.0); a_apg = as_.get("apg", 0.0)

    h_sw = h_st.get("won", 0) or 0
    h_sl = h_st.get("lost", 0) or 0
    a_sw = a_st.get("won", 0) or 0
    a_sl = a_st.get("lost", 0) or 0
    h_swr = h_sw / max(h_sw + h_sl, 1)
    a_swr = a_sw / max(a_sw + a_sl, 1)

    factors = []
    if h_ppg or a_ppg:
        factors.append(f"📋 *Forma reciente (10 partidos):* {home} {hw}V/{hl}D | {away} {aw}V/{al}D")
        factors.append(f"🏀 *Puntos prom:* {home} {h_ppg:.1f}F/{h_apg:.1f}C | {away} {a_ppg:.1f}F/{a_apg:.1f}C")
        pt_diff_h = round(h_ppg - h_apg, 1)
        pt_diff_a = round(a_ppg - a_apg, 1)
        factors.append(f"📊 *Diferencia de puntos:* {home} {'+' if pt_diff_h >= 0 else ''}{pt_diff_h} | {away} {'+' if pt_diff_a >= 0 else ''}{pt_diff_a}")
    if h_sw or a_sw:
        factors.append(f"🏆 *Temporada:* {home} {h_sw}V/{h_sl}D ({h_swr:.0%}) | {away} {a_sw}V/{a_sl}D ({a_swr:.0%})")
    factors.append("🏠 *Ventaja de cancha local:* ~58% en ligas profesionales")

    # Scoring
    score = 55 + 5  # base + home court
    if h_wr > a_wr + 0.10: score += 10
    elif a_wr > h_wr + 0.10: score -= 9
    if h_ppg > a_ppg + 5: score += 6
    elif a_ppg > h_ppg + 5: score -= 5
    if h_ppg - h_apg > a_ppg - a_apg + 3: score += 5
    if h_swr > a_swr + 0.08: score += 7
    elif a_swr > h_swr + 0.08: score -= 6

    total_pts_exp = h_ppg + a_ppg

    if score >= 60:
        pick = f"Victoria {home} (Local)"
        bet_type = "Resultado — Local gana"
        odd = round(1 / max(h_wr + 0.05, 0.3), 2)
        conf = min(score, 88)
    elif score <= 50:
        pick = f"Victoria {away} (Visitante)"
        bet_type = "Resultado — Visitante gana"
        odd = round(1 / max(a_wr, 0.3) * 1.1, 2)
        conf = min(100 - score + 5, 85)
    elif total_pts_exp >= 230 and h_ppg > 0:
        pick = f"Más de {int(total_pts_exp) - 5}.5 puntos totales"
        bet_type = "Over/Under — Over puntos"
        odd = 1.88
        conf = 68
    else:
        pick = f"Victoria {home} (Local)"
        bet_type = "Resultado — Local gana"
        odd = 1.85
        conf = 65

    if conf < MIN_CONFIDENCE:
        return None

    return {
        "sport": "basketball",
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
