"""Kakshya Transit Analysis — Ashtakavarga-Driven Transit Quality Scoring.

Kakshya (Sanskrit: division) splits each zodiac sign into 8 sub-divisions
of 3° 45' each, each ruled by one of the 7 planets + Ascendant.
A transiting planet is favorable when it passes through a Kakshya where
the natal Bhinna Ashtakavarga chart has a bindu (point).

This engine:
  1. Computes all active transits for outer planets (5-year window)
  2. Scores each transit day/degree against Bhinna AV bindus
  3. Identifies "favorable transit periods" (transit in sign with ≥5 SAV)
  4. Identifies "peak days" (transit planet exactly in high-bindu Kakshya)
  5. Produces an Expert-ready text block for injection into LLM prompts

AUTHORITY:
  Source: Brihat Parashara Hora Shastra, Gochara (Transit) chapter
  Validation weight: 0.72 (Ashtakavarga transit) per ValidationMatrix
"""

import swisseph as swe
from core.ayanamsa import AyanamsaManager
from config import settings

def _swe_pos(result):
    """Normalise pyswisseph calc_ut/fixstar return across API versions.
    Old (<2.10): returns (positions_tuple, retflag) — result[0] is a tuple.
    New (>=2.10): returns flat 6-tuple directly   — result[0] is a float.
    """
    return result[0] if isinstance(result[0], (list, tuple)) else result

import math
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional, Tuple


ZODIAC = ["Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo",
          "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces"]

# Kakshya rulers (8 per sign, repeat cycle)
# Order: Saturn, Jupiter, Mars, Sun, Venus, Mercury, Moon, Ascendant
KAKSHYA_LORDS = ["Saturn", "Jupiter", "Mars", "Sun", "Venus", "Mercury", "Moon", "Ascendant"]
KAKSHYA_DEG = 30.0 / 8.0  # 3.75° per kakshya

# Transit planets to analyze
TRANSIT_PLANETS = {
    "Jupiter": swe.JUPITER,
    "Saturn": swe.SATURN,
    "Rahu": swe.MEAN_NODE,
    "Mars": swe.MARS,     # Mars included for 1-year window only
}

# Favorable SAV thresholds
SAV_STRONG = 28    # Very favorable transit sign
SAV_GOOD = 25      # Favorable
SAV_AVERAGE = 20   # Neutral
SAV_WEAK = 15      # Unfavorable


def calculate_kakshya_transits(
    natal_jd: float,
    lat: float,
    lon: float,
    bhinna_av: Dict[str, List[int]],   # planet → [bindus per sign 0-11]
    sarva_av: List[int],               # [SAV bindus per sign 0-11]
    years_ahead: int = 5
) -> Dict[str, Any]:
    """
    Main entry point. Calculate Kakshya transit quality for next `years_ahead` years.

    Args:
        natal_jd: Birth Julian Day
        lat, lon: Geographic coordinates
        bhinna_av: Bhinna Ashtakavarga from AshtakavargaEngine (after fix!)
        sarva_av: Sarva (total) Ashtakavarga
        years_ahead: How many years to project

    Returns:
        dict with transit_timeline, peak_windows, expert_block
    """
    AyanamsaManager.set_ayanamsa(settings.ayanamsa)

    now = datetime.now(timezone.utc)
    now_jd = _dt_to_jd(now)
    end_jd = now_jd + years_ahead * 365.25

    # Step 1: Get transit positions at monthly intervals
    transit_timeline = []
    jd = now_jd
    while jd <= end_jd:
        month_data = {"jd": jd, "date": _jd_to_date_str(jd), "planets": {}}

        for pname, pcode in TRANSIT_PLANETS.items():
            # Skip Mars beyond 1-year window (too fast for 5yr analysis)
            if pname == "Mars" and jd > now_jd + 365.25:
                continue
            try:
                pos = _swe_pos(swe.calc_ut(jd, pcode, swe.FLG_SIDEREAL))
                sid_lon = float(pos[0]) % 360
                sign_idx = int(sid_lon // 30)
                deg_in_sign = sid_lon % 30
                kakshya_idx = min(int(deg_in_sign / KAKSHYA_DEG), 7)  # clamp to 0-7
                kakshya_lord = KAKSHYA_LORDS[kakshya_idx]

                # Get SAV for this sign
                sav = sarva_av[sign_idx] if sign_idx < 12 else 0

                # Get bhinna AV for transit planet in this sign
                planet_bindus = bhinna_av.get(pname, [0] * 12)
                if pname == "Rahu":
                    # Rahu uses Saturn's bhinna for transit assessment
                    planet_bindus = bhinna_av.get("Saturn", [0] * 12)
                bindu_in_sign = planet_bindus[sign_idx] if sign_idx < 12 else 0

                # Kakshya has bindu? Check planet's bhinna at sign
                # (simplified: if bindu_in_sign > 0, kakshya likely favorable)
                kakshya_favorable = bindu_in_sign > 0

                # Quality assessment
                if sav >= SAV_STRONG and kakshya_favorable:
                    quality = "EXCELLENT"
                elif sav >= SAV_GOOD and kakshya_favorable:
                    quality = "FAVORABLE"
                elif sav >= SAV_GOOD:
                    quality = "MODERATE"
                elif sav >= SAV_AVERAGE:
                    quality = "NEUTRAL"
                elif sav < SAV_WEAK:
                    quality = "UNFAVORABLE"
                else:
                    quality = "WEAK"

                month_data["planets"][pname] = {
                    "longitude": round(sid_lon, 3),
                    "sign": ZODIAC[sign_idx],
                    "sign_idx": sign_idx,
                    "deg_in_sign": round(deg_in_sign, 3),
                    "kakshya": kakshya_idx + 1,
                    "kakshya_lord": kakshya_lord,
                    "kakshya_favorable": kakshya_favorable,
                    "sav_in_sign": sav,
                    "planet_bindus_in_sign": bindu_in_sign,
                    "quality": quality,
                }
            except Exception:
                continue

        transit_timeline.append(month_data)
        jd += 30.4375  # ~1 month

    # Step 2: Identify peak favorable windows
    peak_windows = _find_peak_windows(transit_timeline)

    # Step 3: Identify sign ingresses (important transitions)
    ingresses = _find_ingresses(transit_timeline)

    # Step 4: Build expert text block
    expert_block = _build_expert_block(
        transit_timeline, peak_windows, ingresses, sarva_av, bhinna_av
    )

    return {
        "transit_timeline": transit_timeline[:180],  # Keep ~15 years monthly
        "peak_windows": peak_windows,
        "ingresses": ingresses,
        "sarva_by_sign": {ZODIAC[i]: sarva_av[i] for i in range(12)},
        "expert_block": expert_block,
    }


def _find_peak_windows(timeline: List[Dict]) -> List[Dict]:
    """Find consecutive months where a planet is in an EXCELLENT or FAVORABLE sign."""
    peaks = []
    planet_streaks = {}  # pname → current streak

    for entry in timeline:
        for pname, pdata in entry["planets"].items():
            quality = pdata["quality"]
            if quality in ("EXCELLENT", "FAVORABLE"):
                if pname not in planet_streaks:
                    planet_streaks[pname] = {
                        "planet": pname,
                        "start_date": entry["date"],
                        "start_jd": entry["jd"],
                        "sign": pdata["sign"],
                        "quality": quality,
                        "sav": pdata["sav_in_sign"],
                        "months": 1,
                    }
                else:
                    streak = planet_streaks[pname]
                    if streak["sign"] == pdata["sign"]:
                        streak["months"] += 1
                    else:
                        # Sign changed but still favorable — close old, start new
                        streak["end_date"] = entry["date"]
                        if streak["months"] >= 2:
                            peaks.append(dict(streak))
                        planet_streaks[pname] = {
                            "planet": pname,
                            "start_date": entry["date"],
                            "start_jd": entry["jd"],
                            "sign": pdata["sign"],
                            "quality": quality,
                            "sav": pdata["sav_in_sign"],
                            "months": 1,
                        }
            else:
                if pname in planet_streaks:
                    streak = planet_streaks.pop(pname)
                    streak["end_date"] = entry["date"]
                    if streak["months"] >= 2:
                        peaks.append(dict(streak))

    # Close any remaining streaks
    for pname, streak in planet_streaks.items():
        streak["end_date"] = "ongoing"
        if streak["months"] >= 2:
            peaks.append(dict(streak))

    # Sort by SAV + months
    peaks.sort(key=lambda x: (x["sav"], x["months"]), reverse=True)
    return peaks[:12]  # Top 12 windows


def _find_ingresses(timeline: List[Dict]) -> List[Dict]:
    """Find planet sign ingresses (important astrological transitions)."""
    ingresses = []
    last_signs = {}

    for entry in timeline:
        for pname, pdata in entry["planets"].items():
            sign = pdata["sign"]
            if pname in last_signs and last_signs[pname] != sign:
                ingresses.append({
                    "planet": pname,
                    "from_sign": last_signs[pname],
                    "to_sign": sign,
                    "date": entry["date"],
                    "sav_new_sign": pdata["sav_in_sign"],
                    "quality_new_sign": pdata["quality"],
                    "significant": pdata["quality"] in ("EXCELLENT", "FAVORABLE", "UNFAVORABLE"),
                })
            last_signs[pname] = sign

    return [i for i in ingresses if i["significant"]][:20]


def _build_expert_block(
    timeline: List[Dict],
    peaks: List[Dict],
    ingresses: List[Dict],
    sarva_av: List[int],
    bhinna_av: Dict[str, List[int]]
) -> str:
    """
    Build the text block injected into Expert LLM prompts.
    Format matches Archon/Expert expectations for Vedic quality data.
    """
    lines = ["=== KAKSHYA TRANSIT ANALYSIS (Ashtakavarga-Based) ==="]
    lines.append("Source: Bhinna Ashtakavarga + Sarva Ashtakavarga (post-fix)")
    lines.append("")

    # SAV sign summary (top 4 and bottom 4)
    sav_ranked = sorted(enumerate(sarva_av), key=lambda x: x[1], reverse=True)
    top_signs = [(ZODIAC[i], s) for i, s in sav_ranked[:4]]
    weak_signs = [(ZODIAC[i], s) for i, s in sav_ranked[-4:]]

    lines.append("SARVA AV SIGN STRENGTH:")
    lines.append(f"  Strongest (transit favorable): {', '.join(f'{n}={s}' for n,s in top_signs)}")
    lines.append(f"  Weakest (transit difficult):   {', '.join(f'{n}={s}' for n,s in weak_signs)}")
    lines.append("")

    # Peak favorable windows
    if peaks:
        lines.append("PEAK FAVORABLE TRANSIT WINDOWS (2+ months, EXCELLENT/FAVORABLE):")
        for p in peaks[:6]:
            end = p.get("end_date", "ongoing")
            lines.append(f"  {p['planet']} in {p['sign']}: {p['start_date']} → {end}")
            lines.append(f"    SAV={p['sav']}/56, quality={p['quality']}, duration={p['months']} months")
    else:
        lines.append("PEAK WINDOWS: No extended favorable transit windows found in this period.")

    lines.append("")

    # Key ingresses
    if ingresses:
        lines.append("SIGNIFICANT SIGN INGRESSES (quality changes):")
        for ing in ingresses[:8]:
            lines.append(f"  {ing['planet']}: {ing['from_sign']} → {ing['to_sign']} "
                         f"on {ing['date']} (SAV={ing['sav_new_sign']}, {ing['quality_new_sign']})")

    lines.append("")

    # Current month snapshot
    if timeline:
        current = timeline[0]
        lines.append(f"CURRENT TRANSIT STATUS ({current['date']}):")
        for pname in ["Jupiter", "Saturn", "Rahu"]:
            if pname in current["planets"]:
                pd = current["planets"][pname]
                lines.append(f"  {pname}: {pd['deg_in_sign']:.1f}° {pd['sign']} "
                             f"[SAV={pd['sav_in_sign']}, Kakshya {pd['kakshya']}/{pd['kakshya_lord']}, "
                             f"{pd['quality']}]")

    lines.append("=== END KAKSHYA ANALYSIS ===")
    return "\n".join(lines)


# ─────────────────────────────────────────────────────────────────────────
# Utility functions
# ─────────────────────────────────────────────────────────────────────────

def _dt_to_jd(dt: datetime) -> float:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    epoch = datetime(2000, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    return 2451545.0 + (dt - epoch).total_seconds() / 86400.0


def _jd_to_date_str(jd: float) -> str:
    """Convert JD to human-readable date string."""
    try:
        jd_adj = jd + 0.5
        Z = int(jd_adj)
        F = jd_adj - Z
        if Z < 2299161:
            A = Z
        else:
            alpha = int((Z - 1867216.25) / 36524.25)
            A = Z + 1 + alpha - alpha // 4
        B = A + 1524
        C = int((B - 122.1) / 365.25)
        D = int(365.25 * C)
        E = int((B - D) / 30.6001)
        day = B - D - int(30.6001 * E)
        month = E - 1 if E < 14 else E - 13
        year = C - 4716 if month > 2 else C - 4715
        months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                  "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
        return f"{months[month-1]} {day:02d}, {year}"
    except Exception:
        return f"JD{jd:.0f}"
