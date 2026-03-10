"""Vedic_engine Astrology Engine."""
import swisseph as swe
from datetime import datetime, timezone
from typing import Dict, Any, List

# Import shared utilities
from systems.western import clamp360
import math

# Import V2 engines (these must exist in the same directory)
from core.vedic_engines import AshtakavargaEngine
from core.vedic_engines import DivisionalCharts
from core.tajaka import TajakaEngine
from core.shadbala import calculate_shadbala as calculate_shadbala_full

# Vedic_engine-specific constants
ZODIAC_V = ["Mesha", "Vrishabha", "Mithuna", "Karka", "Simha", "Kanya", "Tula", "Vrischika", "Dhanus", "Makara",
            "Kumbha", "Meena"]

NAKSHATRAS = [
    "Ashwini", "Bharani", "Krittika", "Rohini", "Mrigashira", "Ardra", "Punarvasu", "Pushya", "Ashlesha",
    "Magha", "Purva Phalguni", "Uttara Phalguni", "Hasta", "Chitra", "Swati", "Vishakha", "Anuradha",
    "Jyeshtha", "Mula", "Purva Ashadha", "Uttara Ashadha", "Shravana", "Dhanishta", "Shatabhisha",
    "Purva Bhadrapada", "Uttara Bhadrapada", "Revati"
]

VEDIC_GRAHAS = ["Sun", "Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn", "Rahu", "Ketu"]

VEDIC_RULERS = {
    "Mesha": "Mars", "Vrishabha": "Venus", "Mithuna": "Mercury", "Karka": "Moon", "Simha": "Sun", "Kanya": "Mercury",
    "Tula": "Venus", "Vrischika": "Mars", "Dhanus": "Jupiter", "Makara": "Saturn", "Kumbha": "Saturn",
    "Meena": "Jupiter"
}

EXALT = {"Sun": "Mesha", "Moon": "Vrishabha", "Mars": "Makara", "Mercury": "Kanya", "Jupiter": "Karka",
         "Venus": "Meena", "Saturn": "Tula", "Rahu": "Vrishabha", "Ketu": "Vrischika"}
DEBIL = {"Sun": "Tula", "Moon": "Vrischika", "Mars": "Karka", "Mercury": "Meena", "Jupiter": "Makara", "Venus": "Kanya",
         "Saturn": "Mesha", "Rahu": "Vrischika", "Ketu": "Vrishabha"}


def _swe_pos(result):
    """Normalise pyswisseph calc_ut return across API versions.
    Old (<2.10): returns (positions_tuple, retflag) — result[0] is a tuple.
    New (>=2.10): returns flat 6-tuple directly   — result[0] is a float.
    """
    return result[0] if isinstance(result[0], (list, tuple)) else result


def zodiac_sign_v(deg: float) -> str:
    return ZODIAC_V[int(clamp360(deg) // 30)]


def deg_in_sign(deg: float) -> float:
    return clamp360(deg) % 30


def midpoint(d1: float, d2: float) -> float:
    a, b = clamp360(d1), clamp360(d2)
    diff = abs(a - b)
    if diff > 180:
        return clamp360((a + b + 360) / 2)
    return clamp360((a + b) / 2)


def nakshatra_and_pada(sid_lon: float) -> Dict[str, Any]:
    size = 360 / 27.0
    idx = int(clamp360(sid_lon) / size)
    deg_in = clamp360(sid_lon) % size
    pada = int(deg_in / (size / 4.0)) + 1
    return {"nakshatra": NAKSHATRAS[idx], "pada": int(pada)}


def navamsa_sign(sid_lon: float) -> str:
    # Classic D9 mapping by sign modality
    sign_idx = int(clamp360(sid_lon) // 30)
    within = clamp360(sid_lon) % 30.0
    part = int(within // (30.0 / 9.0))
    # Movable: start from same sign; Fixed: 9th; Dual: 5th
    if sign_idx in [0, 3, 6, 9]:
        start = sign_idx
    elif sign_idx in [1, 4, 7, 10]:
        start = (sign_idx + 8) % 12
    else:
        start = (sign_idx + 4) % 12
    return ZODIAC_V[(start + part) % 12]


def dasamsa_sign(sid_lon: float) -> str:
    # Classic D10 mapping
    sign_idx = int(clamp360(sid_lon) // 30)
    within = clamp360(sid_lon) % 30.0
    part = int(within // 3.0)  # 10 parts of 3 degrees
    # Movable: same sign, Fixed: 9th, Dual: 5th
    if sign_idx in [0, 3, 6, 9]:
        start = sign_idx
    elif sign_idx in [1, 4, 7, 10]:
        start = (sign_idx + 8) % 12
    else:
        start = (sign_idx + 4) % 12
    return ZODIAC_V[(start + part) % 12]


def vedic_dignity(planet: str, sign: str) -> str:
    if EXALT.get(planet) == sign:
        return "Exalted"
    if DEBIL.get(planet) == sign:
        return "Debilitated"
    if VEDIC_RULERS.get(sign) == planet:
        return "Own Sign"
    return "Neutral"


def chara_karakas(placements: Dict[str, Any]) -> Dict[str, str]:
    """
    Jaimini Chara Karakas (7). Uses degrees within sign among 7 planets.
    AK=highest, ... DK=lowest.
    """
    candidates = ["Sun", "Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn"]
    vals = []
    for p in candidates:
        if p in placements:
            vals.append((p, float(placements[p]["deg_in_sign"])))
    vals.sort(key=lambda x: x[1], reverse=True)
    labels = ["Atmakaraka", "Amatyakaraka", "Bhratrikaraka", "Matrikaraka", "Putrakaraka", "Gnatikaraka", "Darakaraka"]
    out = {}
    for i, (p, _) in enumerate(vals[:7]):
        out[labels[i]] = p
    return out


def vimshottari_maha_lord(moon_sid_lon: float, age_years: float) -> Dict[str, Any]:
    """
    Returns current Maha Dasha lord + rough remaining years in that MD.
    """
    dasha_lords = ["Ketu", "Venus", "Sun", "Moon", "Mars", "Rahu", "Jupiter", "Saturn", "Mercury"]
    dasha_years = [7, 20, 6, 10, 7, 18, 16, 19, 17]
    nak_size = 360 / 27.0
    nak_idx = int(clamp360(moon_sid_lon) / nak_size)
    lord_idx = nak_idx % 9
    passed = clamp360(moon_sid_lon) % nak_size
    frac_remaining = 1.0 - (passed / nak_size)
    first_left = frac_remaining * dasha_years[lord_idx]

    if age_years < first_left:
        return {"maha_lord": dasha_lords[lord_idx], "approx_remaining_years": round(first_left - age_years, 3)}

    acc = first_left
    idx = (lord_idx + 1) % 9
    while acc + dasha_years[idx] <= age_years:
        acc += dasha_years[idx]
        idx = (idx + 1) % 9

    rem = (acc + dasha_years[idx]) - age_years
    return {"maha_lord": dasha_lords[idx], "approx_remaining_years": round(rem, 3)}


def vimshottari_antardasha(moon_sid_lon: float, age_years: float) -> Dict[str, Any]:
    """
    Returns current Antardasha (sub-period) lord within the active Maha Dasha,
    plus approximate years remaining in that Antardasha.

    Classical Vimshottari rule: within each Maha Dasha the sub-periods cycle
    through all 9 lords in the same sequence, starting from the Maha lord itself.
    Each Antardasha length = (maha_years * antar_years) / 120.
    """
    dasha_lords = ["Ketu", "Venus", "Sun", "Moon", "Mars", "Rahu", "Jupiter", "Saturn", "Mercury"]
    dasha_years = [7, 20, 6, 10, 7, 18, 16, 19, 17]
    TOTAL_CYCLE = 120.0

    nak_size = 360.0 / 27.0
    nak_idx = int(clamp360(moon_sid_lon) / nak_size)
    lord_idx = nak_idx % 9
    passed_in_nak = clamp360(moon_sid_lon) % nak_size
    frac_remaining = 1.0 - (passed_in_nak / nak_size)
    first_left = frac_remaining * dasha_years[lord_idx]

    # ── Identify current Maha Dasha index and age-into-maha ──────────────────
    if age_years <= first_left:
        maha_idx = lord_idx
        maha_start_age = 0.0
        maha_total = dasha_years[lord_idx]
    else:
        acc = first_left
        maha_idx = (lord_idx + 1) % 9
        while acc + dasha_years[maha_idx] <= age_years:
            acc += dasha_years[maha_idx]
            maha_idx = (maha_idx + 1) % 9
        maha_start_age = acc
        maha_total = dasha_years[maha_idx]

    age_into_maha = age_years - maha_start_age

    # ── Walk Antardashas within this Maha ────────────────────────────────────
    # Antardasha sequence starts from the Maha lord itself
    antar_acc = 0.0
    antar_idx = maha_idx

    for _ in range(9):
        antar_years = (maha_total * dasha_years[antar_idx]) / TOTAL_CYCLE
        if antar_acc + antar_years > age_into_maha:
            antar_left = round((antar_acc + antar_years) - age_into_maha, 4)
            maha_left = round(maha_total - age_into_maha, 4)
            return {
                "maha_lord": dasha_lords[maha_idx],
                "antar_lord": dasha_lords[antar_idx],
                "maha_remaining_years": maha_left,
                "antar_remaining_years": antar_left,
                "antar_total_years": round(antar_years, 4),
            }
        antar_acc += antar_years
        antar_idx = (antar_idx + 1) % 9

    # Fallback: end of last Antardasha
    maha_left = round(maha_total - age_into_maha, 4)
    return {
        "maha_lord": dasha_lords[maha_idx],
        "antar_lord": dasha_lords[maha_idx],
        "maha_remaining_years": maha_left,
        "antar_remaining_years": maha_left,
        "antar_total_years": round(dasha_years[maha_idx] / 9.0, 4),
    }


def shadbala_v2(placements: Dict[str, Any], is_day: bool = True) -> Dict[str, Any]:
    """
    Full 6-Strength Shadbala.
    Sub-strengths (all in Shashtiamshas, max indicated):
      1. Sthana Bala  — Positional strength (max ~180)
      2. Dig Bala     — Directional strength (max 60)
      3. Kala Bala    — Temporal strength (max ~80)
      4. Chesta Bala  — Motional/speed strength (max 60)
      5. Naisargika   — Natural/fixed hierarchy (max 60)
      6. Drik Bala    — Aspectual (benefic vs malefic aspect balance)
    Expressed in Rupas (1 Rupa = 60 Shashtiamshas) for final output.

    Classical minimum thresholds (Rupas):
      Sun 6.5 | Moon 6.0 | Mars 5.0 | Mercury 7.0 | Jupiter 6.5 | Venus 5.5 | Saturn 5.0
    """
    # ── Dignity tables ───────────────────────────────────────────────────────
    EXALT_DEG = {
        "Sun": ("Mesha", 10), "Moon": ("Vrishabha", 3),
        "Mars": ("Makara", 28), "Mercury": ("Kanya", 15),
        "Jupiter": ("Karka", 5), "Venus": ("Meena", 27),
        "Saturn": ("Tula", 20),
    }
    DEBIL_SIGN = {
        "Sun": "Tula", "Moon": "Vrischika", "Mars": "Karka",
        "Mercury": "Meena", "Jupiter": "Makara", "Venus": "Kanya",
        "Saturn": "Mesha",
    }
    MOOL = {
        "Sun": "Simha", "Moon": "Vrishabha", "Mars": "Mesha",
        "Mercury": "Kanya", "Jupiter": "Dhanus", "Venus": "Tula",
        "Saturn": "Kumbha",
    }
    OWN_SIGNS = {
        "Sun": ["Simha"], "Moon": ["Karka"],
        "Mars": ["Mesha", "Vrischika"], "Mercury": ["Mithuna", "Kanya"],
        "Jupiter": ["Dhanus", "Meena"], "Venus": ["Vrishabha", "Tula"],
        "Saturn": ["Makara", "Kumbha"],
    }
    # Friendly/neutral/enemy relations (Parashara natural)
    FRIENDS = {
        "Sun":  ["Moon", "Mars", "Jupiter"],
        "Moon": ["Sun", "Mercury"],
        "Mars": ["Sun", "Moon", "Jupiter"],
        "Mercury": ["Sun", "Venus"],
        "Jupiter": ["Sun", "Moon", "Mars"],
        "Venus": ["Mercury", "Saturn"],
        "Saturn": ["Mercury", "Venus"],
    }
    ENEMIES = {
        "Sun":  ["Venus", "Saturn"],
        "Moon": ["None"],
        "Mars": ["Mercury"],
        "Mercury": ["Moon"],
        "Jupiter": ["Mercury", "Venus"],
        "Venus": ["Sun", "Moon"],
        "Saturn": ["Sun", "Moon", "Mars"],
    }

    # ── 5. Naisargika Bala (Natural, fixed) — in Shashtiamshas ───────────────
    NAISARGIKA = {
        "Sun": 60.0, "Moon": 51.43, "Venus": 42.86,
        "Jupiter": 34.29, "Mercury": 25.71, "Mars": 17.14, "Saturn": 8.57,
    }

    # ── Sect / day-night ─────────────────────────────────────────────────────
    DAY_PLANETS   = {"Sun", "Jupiter", "Saturn"}
    NIGHT_PLANETS = {"Moon", "Venus", "Mars"}

    # ── Dig Bala: best-house (in Shashtiamshas) ──────────────────────────────
    # Each planet is strongest at a specific house cusp direction
    DIG_BEST_HOUSE = {
        "Sun": 10, "Mars": 10, "Jupiter": 10,
        "Moon": 4,  "Venus": 4,
        "Mercury": 1, "Saturn": 7,
    }

    CLASSICAL_PLANETS = ["Sun", "Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn"]

    scores = {}
    tier_map = {}

    for p in CLASSICAL_PLANETS:
        d = placements.get(p, {})
        if not d:
            continue
        sign = d.get("sign", "")

        # ── 1. STHANA BALA ───────────────────────────────────────────────────
        # Uccha (exaltation) component: 0-60
        ex_sign, ex_deg = EXALT_DEG.get(p, ("", 0))
        deg_in_s = float(d.get("deg_in_sign", 0))
        if sign == ex_sign:
            # Max 60 at exact exaltation degree, drops linearly to 0 at debil degree
            arc = abs(deg_in_s - ex_deg)
            if arc > 15:
                arc = 30 - arc if arc < 30 else arc  # wrap
            uccha = max(0.0, 60.0 - arc * 2.0)
        elif DEBIL_SIGN.get(p) == sign:
            uccha = 0.0
        elif sign in OWN_SIGNS.get(p, []):
            uccha = 30.0 if MOOL.get(p) == sign else 25.0
        else:
            # Check lord relationship
            lord = VEDIC_RULERS.get(sign, "")
            if lord in FRIENDS.get(p, []):
                uccha = 15.0
            elif lord in ENEMIES.get(p, []):
                uccha = 5.0
            else:
                uccha = 10.0
        uccha = max(0.0, min(60.0, uccha))

        # Kendradi Bala: Angular/Succedent/Cadent (30/20/10 Shashtiamshas)
        bhava = d.get("bhava", 0)  # might not be set yet
        if bhava:
            kendradi = {1: 30, 4: 30, 7: 30, 10: 30,
                        2: 20, 5: 20, 8: 20, 11: 20,
                        3: 10, 6: 10, 9: 10, 12: 10}.get(bhava, 10)
        else:
            kendradi = 15.0  # neutral if unknown

        # Vargottama bonus (same sign D1 and D9)
        varg_bonus = 20.0 if d.get("is_vargottama") else 0.0

        sthan = uccha + kendradi + varg_bonus
        sthan = max(5.0, min(100.0, sthan))

        # ── 2. DIG BALA ──────────────────────────────────────────────────────
        best = DIG_BEST_HOUSE.get(p, 1)
        if bhava:
            # Angular distance (in house units 1-12) from best house
            h_dist = min(abs(bhava - best), 12 - abs(bhava - best))
            dig = max(0.0, 60.0 - (h_dist * 10.0))
        else:
            dig = 30.0  # neutral if house unknown

        # ── 3. KALA BALA ─────────────────────────────────────────────────────
        # Nathonnatha (day/night sect strength): 30 in sect, 15 out of sect
        if p in DAY_PLANETS:
            natho = 30.0 if is_day else 15.0
        elif p in NIGHT_PLANETS:
            natho = 30.0 if not is_day else 15.0
        else:  # Mercury — equal in both
            natho = 22.5

        # Paksha Bala (lunar phase): Moon waxing → Moon benefits, Sun benefits in daytime
        # Simplified: +5 bonus if in-sect, already folded above
        kala = max(10.0, min(60.0, natho))

        # ── 4. CHESTA BALA ───────────────────────────────────────────────────
        CAN_RETRO = {"Mars", "Mercury", "Jupiter", "Venus", "Saturn"}
        if d.get("retrograde", False) and p in CAN_RETRO:
            chesta = 60.0    # retro = max chesta (closest to Earth, most effort)
        elif d.get("combust", False):
            chesta = 5.0     # combust = nearly zero
        else:
            chesta = 30.0    # direct visible = standard

        # ── 5. NAISARGIKA BALA ───────────────────────────────────────────────
        naisargika = NAISARGIKA.get(p, 25.0)

        # ── 6. DRIK BALA ─────────────────────────────────────────────────────
        # Aspectual: benefics aspecting = +15 each, malefics = -10 each
        # We use dignity-based classification
        NATURAL_BENEFICS = {"Moon", "Mercury", "Jupiter", "Venus"}
        NATURAL_MALEFICS = {"Sun", "Mars", "Saturn"}
        drik = 0.0
        p_lon = d.get("lon", 0)
        for other_p, other_d in placements.items():
            if other_p == p or other_p not in CLASSICAL_PLANETS:
                continue
            o_lon = other_d.get("lon", 0)
            # Check full aspects (Parashari: 7th aspect is universal, special aspects too)
            diff = abs(clamp360(float(p_lon)) - clamp360(float(o_lon)))
            diff = min(diff, 360 - diff)
            # 7th aspect (180°): all planets; Mars 4th/8th; Jupiter 5th/9th; Saturn 3rd/10th
            aspects_to_check = [180]
            if other_p == "Mars":    aspects_to_check += [90, 210]  # 4th & 8th (×30°)
            if other_p == "Jupiter": aspects_to_check += [120, 240]
            if other_p == "Saturn":  aspects_to_check += [60, 270]

            for ang in aspects_to_check:
                if abs(diff - ang) <= 5.0 or abs(diff - (360 - ang)) <= 5.0:
                    if other_p in NATURAL_BENEFICS:
                        drik += 15.0
                    elif other_p in NATURAL_MALEFICS:
                        drik -= 10.0
                    break

        drik = max(-30.0, min(30.0, drik))

        # ── Sum and convert to Rupas ─────────────────────────────────────────
        total_sha = sthan + dig + kala + chesta + naisargika + drik
        # Typical max raw ≈ 380 Shashtiamshas; convert to Rupas (÷60)
        total_rupas = total_sha / 60.0
        # Classical minimum thresholds in Rupas
        minimums = {
            "Sun": 6.5, "Moon": 6.0, "Mars": 5.0,
            "Mercury": 7.0, "Jupiter": 6.5, "Venus": 5.5, "Saturn": 5.0,
        }
        minimum = minimums.get(p, 5.0)

        # Tier based on ratio to minimum threshold
        ratio = total_rupas / minimum if minimum > 0 else 1.0
        if ratio >= 1.8:
            tier = "DOMINANT"
        elif ratio >= 1.2:
            tier = "ADEQUATE"
        elif ratio >= 0.8:
            tier = "WEAKENED"
        else:
            tier = "SEVERELY WEAKENED"

        scores[p] = {
            "total_rupas": round(total_rupas, 3),
            "minimum_rupas": minimum,
            "ratio": round(ratio, 3),
            "tier": tier,
            "sub_strengths": {
                "sthana_sha": round(sthan, 2),
                "dig_sha": round(dig, 2),
                "kala_sha": round(kala, 2),
                "chesta_sha": round(chesta, 2),
                "naisargika_sha": round(naisargika, 2),
                "drik_sha": round(drik, 2),
            }
        }
        tier_map[p] = tier

    return {
        "planet_scores": scores,
        "planet_tiers":  tier_map,
        "method": "Shadbala_full_6strength"
    }


# Keep old name as alias so any existing code that calls shadbala_mvp still works
def shadbala_mvp(placements: Dict[str, Any]) -> Dict[str, Any]:
    return shadbala_v2(placements, is_day=True)


def ashtakavarga_mvp(placements: Dict[str, Any]) -> Dict[str, Any]:
    """
    MVP approximation (NOT full traditional Ashtakavarga).
    Gives a 0-100 'sign score' for stability/gains scanning.
    """
    sign_counts = {s: 0 for s in ZODIAC_V}
    for p, d in placements.items():
        s = d.get("sign")
        if s in sign_counts:
            sign_counts[s] += 1
    # baseline + occupancy
    out = {}
    for s, c in sign_counts.items():
        out[s] = max(0.0, min(100.0, round(40 + c * 6.5, 2)))
    return {"sarva_sign_scores": out, "method": "MVP_v1"}


def calc_lon_lat(jd: float, pcode: int, flags: int = 0):
    """Wrapper for swe.calc_ut"""
    pos = _swe_pos(swe.calc_ut(jd, pcode, flags))
    return float(pos[0]), float(pos[1])


def calculate_vedic(jd: float, lat: float, lon: float, time_known: bool, birth_dt_utc: datetime) -> Dict[str, Any]:
    swe.set_sid_mode(swe.SIDM_LAHIRI)
    v_flags = swe.FLG_SWIEPH | swe.FLG_SIDEREAL

    placements = {}
    # 7 classical + outer for placement context
    PLANETS_W = {
        "Sun": swe.SUN, "Moon": swe.MOON, "Mercury": swe.MERCURY, "Venus": swe.VENUS, "Mars": swe.MARS,
        "Jupiter": swe.JUPITER, "Saturn": swe.SATURN, "Uranus": swe.URANUS, "Neptune": swe.NEPTUNE, "Pluto": swe.PLUTO
    }

    for name, pcode in PLANETS_W.items():
        lon_sid, _ = calc_lon_lat(jd, pcode, v_flags)
        sign = zodiac_sign_v(lon_sid)
        n = nakshatra_and_pada(lon_sid)
        d9 = navamsa_sign(lon_sid)
        d10 = dasamsa_sign(lon_sid)
        placements[name] = {
            "lon": lon_sid,
            "sign": sign,
            "deg_in_sign": deg_in_sign(lon_sid),
            "nakshatra": n["nakshatra"],
            "pada": n["pada"],
            "d9": d9,
            "d10": d10,
            "is_vargottama": (sign == d9),
            "dignity": vedic_dignity(name, sign) if name in VEDIC_GRAHAS else "Neutral"
        }

    # Nodes (mean node)
    node = _swe_pos(swe.calc_ut(jd, swe.MEAN_NODE, v_flags))
    rahu = float(node[0])
    ketu = clamp360(rahu + 180)
    placements["Rahu"] = {"lon": rahu, "sign": zodiac_sign_v(rahu), "deg_in_sign": deg_in_sign(rahu),
                          "d9": navamsa_sign(rahu), "d10": dasamsa_sign(rahu),
                          "is_vargottama": (zodiac_sign_v(rahu) == navamsa_sign(rahu)),
                          "dignity": vedic_dignity("Rahu", zodiac_sign_v(rahu))}
    placements["Ketu"] = {"lon": ketu, "sign": zodiac_sign_v(ketu), "deg_in_sign": deg_in_sign(ketu),
                          "d9": navamsa_sign(ketu), "d10": dasamsa_sign(ketu),
                          "is_vargottama": (zodiac_sign_v(ketu) == navamsa_sign(ketu)),
                          "dignity": vedic_dignity("Ketu", zodiac_sign_v(ketu))}

    # Initialize result containers
    houses = {}
    bhava_chalit = {}

    # Ascendant + Houses (sidereal)
    if time_known:
        cv, av = swe.houses_ex(jd, lat, lon, b'P', v_flags)
        asc = float(av[0])
        placements["Ascendant"] = {"lon": asc, "sign": zodiac_sign_v(asc), "deg_in_sign": deg_in_sign(asc)}
        # House signs (sidereal)
        cusp_lons = [float(x) for x in cv[:12]]
        for i in range(12):
            houses[f"Bhava_{i + 1}"] = {"cusp_lon": cusp_lons[i], "sign": zodiac_sign_v(cusp_lons[i]),
                                        "lord": VEDIC_RULERS[zodiac_sign_v(cusp_lons[i])]}
        # Bhava Chalit assignment: boundaries midpoint between cusps
        bounds = []
        for i in range(12):
            a = cusp_lons[i]
            b = cusp_lons[(i + 1) % 12]
            bounds.append(midpoint(a, b))

        # Determine house by "between previous bound and next bound"
        def bhava_index(plon: float) -> int:
            # find nearest cusp interval
            # Use cusp ordering; this is a simplification but works for most charts
            for i in range(12):
                start = bounds[i - 1]
                end = bounds[i]
                x = clamp360(plon)
                if start <= end:
                    if start <= x < end:
                        return i + 1
                else:
                    # wrap
                    if x >= start or x < end:
                        return i + 1
            return 1

        for p, d in placements.items():
            if p in ["Ascendant"]:
                continue
            if "lon" in d:
                bhava_chalit[p] = {"bhava": bhava_index(d["lon"])}

    # Jaimini Chara Karakas
    ck = chara_karakas(placements)

    # Vimshottari Maha Dasha + Antardasha (sub-period)
    now = datetime.now(timezone.utc)
    age_years = (now - birth_dt_utc).days / 365.2425
    moon_lon = placements["Moon"]["lon"]

    dasha = vimshottari_maha_lord(moon_lon, age_years)

    # Merge Antardasha data into the dasha dict
    try:
        antardasha = vimshottari_antardasha(moon_lon, age_years)
        dasha["antar_lord"] = antardasha.get("antar_lord", "Unknown")
        dasha["antar_remaining_years"] = antardasha.get("antar_remaining_years", 0)
        dasha["antar_total_years"] = antardasha.get("antar_total_years", 0)
    except Exception:
        dasha["antar_lord"] = "Unknown"
        dasha["antar_remaining_years"] = 0
        dasha["antar_total_years"] = 0

    # Yogas (basic)
    yogas = []
    if time_known and "Ascendant" in placements:
        # extremely simplified: if kendra lord and trikona lord conjoin in same sign
        # (you can expand to aspects/exchanges later)
        house_signs = [houses[f"Bhava_{i + 1}"]["sign"] for i in range(12)]
        kendra_lords = [VEDIC_RULERS[house_signs[0]], VEDIC_RULERS[house_signs[3]], VEDIC_RULERS[house_signs[6]],
                        VEDIC_RULERS[house_signs[9]]]
        trikona_lords = [VEDIC_RULERS[house_signs[0]], VEDIC_RULERS[house_signs[4]], VEDIC_RULERS[house_signs[8]]]
        wealth_lords = [VEDIC_RULERS[house_signs[1]], VEDIC_RULERS[house_signs[10]]]

        occ = {}
        for p, d in placements.items():
            s = d.get("sign")
            if s:
                occ.setdefault(s, []).append(p)

        for s, ps in occ.items():
            ks = list(set(kendra_lords).intersection(ps))
            ts = list(set(trikona_lords).intersection(ps))
            ws = list(set(wealth_lords).intersection(ps))
            if ks and ts:
                yogas.append({"type": "Raja Yoga", "sign": s, "members": sorted(list(set(ks + ts)))})
            if ws and ts:
                yogas.append({"type": "Dhana Yoga", "sign": s, "members": sorted(list(set(ws + ts)))})

    # Initialize strength and predictive dicts
    # Use full Parashara Shadbala (6-source calculation from Swiss Ephemeris)
    # Falls back to simplified shadbala_v2 if jd/lat/lon not available
    try:
        shadbala_result = calculate_shadbala_full(jd, lat, lon)
    except Exception:
        shadbala_result = shadbala_v2(placements, is_day=(birth_dt_utc.hour >= 6 and birth_dt_utc.hour < 18))
    strength = {
        "shadbala": shadbala_result,
        "ashtakavarga": ashtakavarga_mvp(placements)
    }

    predictive = {
        "vimshottari": dasha
    }

    natal = {
        "placements": placements,
        "houses": houses,
        "bhava_chalit": bhava_chalit,
        "chara_karakas": ck,
        "yogas": yogas
    }

    # V2 ENHANCEMENTS - Full Ashtakavarga
    try:
        av_engine = AshtakavargaEngine(jd, lat, lon)
        sav_scores = [av_engine.get_house_strength(i) for i in range(1, 13)]

        strength["ashtakavarga_full"] = {
            "sarva": av_engine.sarva_ashtakavarga,
            "bhinna": av_engine.bhinna_ashtakavarga,
            "house_strengths": sav_scores
        }
    except Exception as e:
        strength["ashtakavarga_full"] = {"error": str(e)}

    # V2 ENHANCEMENTS - Divisional Charts
    try:
        varga_engine = DivisionalCharts(jd, lat, lon)
        natal["vargas"] = varga_engine.get_all_vargas()
    except Exception as e:
        natal["vargas"] = {"error": str(e)}

    # V2 ENHANCEMENTS - Tajaka (Vedic_engine Solar Return) — 15-year window
    try:
        tajaka_engine = TajakaEngine(jd, lat, lon)
        current_year = datetime.now().year
        tajaka_years = [current_year + i for i in range(15)]
        predictive["tajaka"] = [tajaka_engine.calculate_tajaka(y) for y in tajaka_years]
    except Exception as e:
        predictive["tajaka"] = {"error": str(e)}

    return {
        "natal": natal,
        "strength": strength,
        "predictive": predictive
    }


# Export these for orchestrator imports
__all__ = ['calculate_vedic', 'AshtakavargaEngine', 'DivisionalCharts']
