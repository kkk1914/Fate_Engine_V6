"""
Shadbala — Six-Source Strength System (Parashara).
Calculates proper Shadbala for the 7 classical planets.

The six sources:
  1. Sthana Bala   — positional strength (5 sub-sources)
  2. Dig Bala      — directional strength (house-based)
  3. Kala Bala     — temporal strength (day/night, hora, etc.)
  4. Chesta Bala   — motional strength (retrograde = more chesta)
  5. Naisargika Bala — natural strength (fixed)
  6. Drik Bala     — aspectual strength (benefic/malefic aspects)

Output unit: Rupas (1 Rupa = 60 Shashtiamshas).
Minimum required for full strength per Parashara:
  Sun=6.5, Moon=6.0, Mars=5.0, Mercury=7.0, Jupiter=6.5, Venus=5.5, Saturn=5.0 Rupas.
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
from typing import Dict, Any

PLANETS_SH = {
    "Sun": swe.SUN, "Moon": swe.MOON, "Mars": swe.MARS,
    "Mercury": swe.MERCURY, "Jupiter": swe.JUPITER,
    "Venus": swe.VENUS, "Saturn": swe.SATURN
}

# Minimum Rupas required for full strength
MINIMUM_RUPAS = {
    "Sun": 6.5, "Moon": 6.0, "Mars": 5.0,
    "Mercury": 7.0, "Jupiter": 6.5, "Venus": 5.5, "Saturn": 5.0
}

# Naisargika (natural) Bala — fixed values in Rupas
NAISARGIKA_BALA = {
    "Sun": 1.0, "Moon": 0.857, "Venus": 0.714,
    "Jupiter": 0.571, "Mercury": 0.429, "Mars": 0.286, "Saturn": 0.143
}

# Dig Bala: planet is strong in specific house (full = 60 Shashtiamshas = 1 Rupa)
DIG_BALA_HOUSE = {
    "Sun": 10, "Moon": 4, "Mars": 10, "Mercury": 1,
    "Jupiter": 1, "Venus": 4, "Saturn": 7
}

# Exaltation points (ecliptic degrees)
EXALT_DEG = {
    "Sun": 10.0, "Moon": 33.0, "Mars": 298.0, "Mercury": 165.0,
    "Jupiter": 105.0, "Venus": 357.0, "Saturn": 201.0
}

ZODIAC_V = [
    "Aries","Taurus","Gemini","Cancer","Leo","Virgo",
    "Libra","Scorpio","Sagittarius","Capricorn","Aquarius","Pisces"
]

RULERS = {
    "Aries": "Mars", "Taurus": "Venus", "Gemini": "Mercury",
    "Cancer": "Moon", "Leo": "Sun", "Virgo": "Mercury",
    "Libra": "Venus", "Scorpio": "Mars", "Sagittarius": "Jupiter",
    "Capricorn": "Saturn", "Aquarius": "Saturn", "Pisces": "Jupiter"
}

EXALT_SIGN = {
    "Sun": "Aries", "Moon": "Taurus", "Mars": "Capricorn",
    "Mercury": "Virgo", "Jupiter": "Cancer", "Venus": "Pisces", "Saturn": "Libra"
}

DEBIL_SIGN = {
    "Sun": "Libra", "Moon": "Scorpio", "Mars": "Cancer",
    "Mercury": "Pisces", "Jupiter": "Capricorn", "Venus": "Virgo", "Saturn": "Aries"
}


def calculate_shadbala(jd: float, lat: float, lon: float) -> Dict[str, Any]:
    """
    Calculate full Shadbala for all 7 classical planets.
    Returns rupas per planet plus interpretation tier.
    """
    AyanamsaManager.set_ayanamsa(settings.ayanamsa)

    # Get sidereal positions
    positions = {}
    for name, code in PLANETS_SH.items():
        pos = _swe_pos(swe.calc_ut(jd, code, swe.FLG_SIDEREAL | swe.FLG_SPEED))
        sid_lon = float(pos[0]) % 360
        positions[name] = {
            "sid_lon": sid_lon,
            "sign": ZODIAC_V[int(sid_lon // 30)],
            "deg_in_sign": sid_lon % 30,
            "speed": float(pos[3]),  # daily motion
            "retrograde": float(pos[3]) < 0
        }

    # Houses (sidereal)
    cusps, ascmc = swe.houses_ex(jd, lat, lon, b'P', swe.FLG_SIDEREAL)
    asc_lon = float(ascmc[0]) % 360

    # Determine day/night chart
    sun_lon = positions["Sun"]["sid_lon"]
    is_day = 0 < ((sun_lon - asc_lon) % 360) < 180

    results = {}

    for planet in PLANETS_SH:
        p = positions[planet]
        sign = p["sign"]
        sid_lon = p["sid_lon"]
        deg = p["deg_in_sign"]

        # ── 1. STHANA BALA (positional strength) ──────────────────────────
        sthanabala = 0.0

        # a) Uccha Bala (exaltation strength): 0-60 shashtiamshas
        exalt_lon = EXALT_DEG.get(planet, 0.0)
        debil_lon = (exalt_lon + 180) % 360
        dist_from_exalt = abs(sid_lon - exalt_lon) % 360
        if dist_from_exalt > 180:
            dist_from_exalt = 360 - dist_from_exalt
        uccha = (180 - dist_from_exalt) / 3.0  # max 60
        sthanabala += uccha

        # b) Sapta Varga Bala (dignity across 7 vargas) — simplified
        dignity = "neutral"
        if EXALT_SIGN.get(planet) == sign:
            dignity = "exalted"
            sthanabala += 45
        elif RULERS.get(sign) == planet:
            dignity = "own"
            sthanabala += 30
        elif DEBIL_SIGN.get(planet) == sign:
            dignity = "debilitated"
            sthanabala += 0
        else:
            sthanabala += 15

        # c) Ojayugma (odd/even sign): Sun/Mars strong in odd, Moon/Venus in even
        sign_num = ZODIAC_V.index(sign)
        odd_sign = (sign_num % 2 == 0)  # 0-indexed: Aries=0 (odd), Taurus=1 (even)
        if planet in ["Sun", "Mars", "Jupiter", "Mercury"] and odd_sign:
            sthanabala += 15
        elif planet in ["Moon", "Venus", "Saturn"] and not odd_sign:
            sthanabala += 15

        # ── 2. DIG BALA (directional strength) ────────────────────────────
        # Determine house of planet
        house = _get_house(sid_lon, [float(c) % 360 for c in cusps])
        ideal_house = DIG_BALA_HOUSE.get(planet, 1)
        house_diff = abs(house - ideal_house)
        if house_diff > 6:
            house_diff = 12 - house_diff
        digbala = (1 - house_diff / 6.0) * 60.0
        digbala = max(0.0, digbala)

        # ── 3. KALA BALA (temporal strength) ──────────────────────────────
        kalabala = 0.0

        # a) Natonnata (day/night): Sun, Jupiter, Venus strong in day; Moon, Mars, Saturn at night
        if is_day and planet in ["Sun", "Jupiter", "Venus"]:
            kalabala += 60
        elif not is_day and planet in ["Moon", "Mars", "Saturn"]:
            kalabala += 60
        else:
            kalabala += 30  # Mercury always 30

        # b) Paksha Bala (Moon phase): Moon waxing = benefics strong; waning = malefics
        moon_lon = positions["Moon"]["sid_lon"]
        moon_sun_diff = (moon_lon - sun_lon) % 360
        waxing = moon_sun_diff < 180
        if waxing and planet in ["Moon", "Mercury", "Jupiter", "Venus"]:
            kalabala += 30
        elif not waxing and planet in ["Sun", "Mars", "Saturn"]:
            kalabala += 30

        # ── 4. CHESTA BALA (motional strength) ────────────────────────────
        speed = abs(p["speed"])
        retrograde = p["retrograde"]

        if retrograde:
            chestabala = 60.0  # Retrograde = maximum Chesta Bala
        else:
            # Mean daily motion (approximate)
            mean_speeds = {
                "Sun": 1.0, "Moon": 13.2, "Mars": 0.524,
                "Mercury": 1.383, "Jupiter": 0.083,
                "Venus": 1.2, "Saturn": 0.033
            }
            mean = mean_speeds.get(planet, 1.0)
            # Ratio: faster than mean = stronger (up to max 60)
            ratio = min(speed / mean, 2.0) if mean > 0 else 1.0
            chestabala = min(60.0, ratio * 30.0)

        # ── 5. NAISARGIKA BALA (natural strength) ─────────────────────────
        naisargika = NAISARGIKA_BALA.get(planet, 0.5) * 60.0

        # ── 6. DRIK BALA (aspectual strength) — simplified ────────────────
        # Count benefic vs malefic aspects from other planets
        benefics = {"Jupiter", "Venus", "Moon", "Mercury"}  # Mercury conditional
        malefics = {"Sun", "Mars", "Saturn"}
        drikbala = 0.0

        for other, op in positions.items():
            if other == planet:
                continue
            diff = abs(sid_lon - op["sid_lon"]) % 360
            arc = min(diff, 360 - diff)
            # Check major aspects (conjunction, trine, opposition)
            if abs(arc) <= 10 or abs(arc - 120) <= 10 or abs(arc - 180) <= 10:
                if other in benefics:
                    drikbala += 15
                else:
                    drikbala -= 15

        drikbala = max(-60.0, min(60.0, drikbala))

        # ── Total Shadbala in Shashtiamshas → convert to Rupas ────────────
        total_sha = (sthanabala + digbala + kalabala +
                     chestabala + naisargika + drikbala)
        rupas = total_sha / 60.0

        min_req = MINIMUM_RUPAS.get(planet, 5.0)
        ratio_to_min = rupas / min_req if min_req > 0 else 1.0

        if ratio_to_min >= 1.5:
            tier = "DOMINANT"
        elif ratio_to_min >= 1.0:
            tier = "ADEQUATE"
        elif ratio_to_min >= 0.7:
            tier = "WEAKENED"
        else:
            tier = "SEVERELY WEAKENED"

        results[planet] = {
            "rupas": round(rupas, 3),
            "shashtiamshas": round(total_sha, 2),
            "minimum_required": min_req,
            "ratio_to_minimum": round(ratio_to_min, 3),
            "tier": tier,
            "dignity": dignity,
            "retrograde": retrograde,
            "components": {
                "sthana_bala": round(sthanabala, 2),
                "dig_bala": round(digbala, 2),
                "kala_bala": round(kalabala, 2),
                "chesta_bala": round(chestabala, 2),
                "naisargika_bala": round(naisargika, 2),
                "drik_bala": round(drikbala, 2)
            }
        }

    return {
        "planet_scores": results,
        "method": "Shadbala_Parashara_v1",
        "note": "Sthana Bala uses simplified Sapta Varga. Full Varga Bala requires D1-D9-D12 etc."
    }


def _get_house(lon: float, cusps: list) -> int:
    """Determine house (1-12) from longitude and sidereal cusps."""
    for i in range(12):
        start = cusps[i] % 360
        end = cusps[(i + 1) % 12] % 360
        if start <= end:
            if start <= lon < end:
                return i + 1
        else:
            if lon >= start or lon < end:
                return i + 1
    return 1