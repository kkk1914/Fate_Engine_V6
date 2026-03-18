import ssl
import math
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo
from typing import Any, Dict, List, Optional, Tuple

import swisseph as swe
from core.ayanamsa import AyanamsaManager
from config import settings

def _swe_pos(result):
    """Normalise pyswisseph calc_ut/fixstar return across API versions.
    Old (<2.10): returns (positions_tuple, retflag) — result[0] is a tuple.
    New (>=2.10): returns flat 6-tuple directly   — result[0] is a float.
    """
    return result[0] if isinstance(result[0], (list, tuple)) else result

from geopy.geocoders import Nominatim

# -----------------------------
# Swiss Ephemeris Setup
# -----------------------------
swe.set_ephe_path("./ephe")

# -----------------------------
# Constants / Tables
# -----------------------------
ZODIAC_W = ["Aries","Taurus","Gemini","Cancer","Leo","Virgo","Libra","Scorpio","Sagittarius","Capricorn","Aquarius","Pisces"]
ZODIAC_V = ["Mesha","Vrishabha","Mithuna","Karka","Simha","Kanya","Tula","Vrischika","Dhanus","Makara","Kumbha","Meena"]

ROYAL_FIXED_STARS = [
    "Regulus", "Spica", "Aldebaran", "Antares", "Fomalhaut"
]

# Zodiacal Releasing (sign periods): numeric values are "years" at L1, "months" at L2 (same numbers).
ZR_SIGN_PERIODS = {
    "Aries": 15, "Taurus": 8, "Gemini": 20, "Cancer": 25, "Leo": 19, "Virgo": 20,
    "Libra": 8, "Scorpio": 15, "Sagittarius": 12, "Capricorn": 27, "Aquarius": 30, "Pisces": 12
}

PLANETS_W = {
    "Sun": swe.SUN, "Moon": swe.MOON, "Mercury": swe.MERCURY, "Venus": swe.VENUS, "Mars": swe.MARS,
    "Jupiter": swe.JUPITER, "Saturn": swe.SATURN, "Uranus": swe.URANUS, "Neptune": swe.NEPTUNE, "Pluto": swe.PLUTO
}

OOB_LIMIT = 23.4392911  # Earth axial tilt approx


# -----------------------------
# Helpers
# -----------------------------
def clamp360(x: float) -> float:
    return x % 360.0

def zodiac_sign_w(deg: float) -> str:
    return ZODIAC_W[int(clamp360(deg) // 30)]

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

def aspect_type(d1: float, d2: float, orb: float = 8.0) -> Optional[str]:
    diff = abs(clamp360(d1) - clamp360(d2))
    dist = min(diff, 360 - diff)
    for ang, name in [(0,"Conjunction"),(60,"Sextile"),(90,"Square"),(120,"Trine"),(180,"Opposition")]:
        if abs(dist - ang) <= orb:
            return name
    return None

def lot_of_fortune(asc: float, sun: float, moon: float, is_day: bool) -> float:
    return clamp360(asc + (moon - sun) if is_day else asc + (sun - moon))

def lot_of_spirit(asc: float, sun: float, moon: float, is_day: bool) -> float:
    return clamp360(asc + (sun - moon) if is_day else asc + (moon - sun))

def geocode(city: str, country: str) -> Tuple[Optional[float], Optional[float]]:
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    geolocator = Nominatim(user_agent="fates_app_pro_v4", ssl_context=ctx)
    loc = geolocator.geocode({"city": city, "country": country})
    if not loc:
        return None, None
    return float(loc.latitude), float(loc.longitude)

def infer_tz(country: str) -> str:
    c = (country or "").strip().lower()
    if c in ["uk","united kingdom","great britain","england","scotland","wales","northern ireland"]:
        return "Europe/London"
    return "UTC"

def to_utc_datetime(year: int, month: int, day: int, time_input: str, tz_name: Optional[str]) -> Tuple[datetime, bool]:
    time_known = (time_input or "").strip().lower() != "unknown"
    if not time_known:
        # noon fallback
        hh, mm = 12, 0
    else:
        hh, mm = map(int, time_input.split(":"))

    tz = ZoneInfo(tz_name or "UTC")
    local_dt = datetime(year, month, day, hh, mm, 0, tzinfo=tz)
    return local_dt.astimezone(timezone.utc), time_known

def jd_from_utc(dt_utc: datetime) -> float:
    return swe.julday(dt_utc.year, dt_utc.month, dt_utc.day, dt_utc.hour + dt_utc.minute/60.0 + dt_utc.second/3600.0)

def calc_lon_lat(jd: float, pcode: int, flags: int = 0) -> Tuple[float,float]:
    pos = _swe_pos(swe.calc_ut(jd, pcode, flags))
    return float(pos[0]), float(pos[1])

def calc_declination(jd: float, pcode: int) -> float:
    pos_equ = _swe_pos(swe.calc_ut(jd, pcode, swe.FLG_EQUATORIAL))
    # pos_equ[1] declination
    return float(pos_equ[1])

def fixed_star_lon(jd: float, star_name: str) -> Optional[float]:
    try:
        _star_raw = _swe_pos(swe.fixstar2_ut(star_name, jd))
        lon, lat, dist = _star_raw[0], _star_raw[1], _star_raw[2]
        return float(lon)
    except Exception:
        return None

def is_conj(a: float, b: float, orb: float = 1.0) -> bool:
    diff = abs(clamp360(a)-clamp360(b))
    dist = min(diff, 360-diff)
    return dist <= orb

def get_ruler(sign_name: str) -> str:
    """
    Returns the ruling planet of a given Western Zodiac sign.
    Uses strict Traditional (Hellenistic) Rulerships for accurate Time Lord calculations.
    """
    rulers = {
        "Aries": "Mars", "Taurus": "Venus", "Gemini": "Mercury", "Cancer": "Moon",
        "Leo": "Sun", "Virgo": "Mercury", "Libra": "Venus", "Scorpio": "Mars",
        "Sagittarius": "Jupiter", "Capricorn": "Saturn", "Aquarius": "Saturn", "Pisces": "Jupiter"
    }
    return rulers.get(sign_name, "Unknown")


# -----------------------------
# Zodiacal Releasing (L1 + L2)
# -----------------------------
def zr_timeline(start_deg: float, start_dt_utc: datetime, years: float = 5.0) -> Dict[str, Any]:
    """
    Output:
      {
        "lot_sign": "...",
        "L1": [ {sign, start, end, years, flags:[]}, ... ],
        "L2": [ {parent_index, sign, start, end, months, flags:[]}, ... ],
      }
    """
    start_sign = zodiac_sign_w(start_deg)
    start_idx = ZODIAC_W.index(start_sign)
    lob_idx = (start_idx + 6) % 12  # Loosing of the Bond marker (simple implementation)

    out = {"lot_sign": start_sign, "L1": [], "L2": []}

    # L1
    t = start_dt_utc
    remaining = years
    i = 0
    while remaining > 0:
        sign = ZODIAC_W[(start_idx + i) % 12]
        dur_years = float(ZR_SIGN_PERIODS[sign])
        if dur_years > remaining:
            dur_years = remaining
        end = t + timedelta(days=dur_years * 365.2425)
        flags = []
        if ((start_idx + i) % 12) == lob_idx:
            flags.append("LOOSING_OF_BOND")
        out["L1"].append({
            "sign": sign,
            "start_utc": t.isoformat(),
            "end_utc": end.isoformat(),
            "years": round(dur_years, 4),
            "flags": flags
        })
        t = end
        remaining -= dur_years
        i += 1

    # L2: months (numeric values same as L1 table)
    # For each L1 period, walk L2 signs starting from that L1 sign.
    for p_idx, p in enumerate(out["L1"]):
        parent_start = datetime.fromisoformat(p["start_utc"])
        parent_end = datetime.fromisoformat(p["end_utc"])
        parent_months = max(1, int(round((parent_end - parent_start).days / 30.436875)))
        l2_start_idx = ZODIAC_W.index(p["sign"])
        m_left = parent_months
        k = 0
        t2 = parent_start
        while m_left > 0:
            sign = ZODIAC_W[(l2_start_idx + k) % 12]
            dur_months = int(ZR_SIGN_PERIODS[sign])  # numeric months
            if dur_months > m_left:
                dur_months = m_left
            end2 = t2 + timedelta(days=dur_months * 30.436875)
            flags = []
            if ((l2_start_idx + k) % 12) == lob_idx:
                flags.append("LOOSING_OF_BOND")
            out["L2"].append({
                "parent_index": p_idx,
                "sign": sign,
                "start_utc": t2.isoformat(),
                "end_utc": end2.isoformat(),
                "months": int(dur_months),
                "flags": flags
            })
            t2 = end2
            m_left -= dur_months
            k += 1

    return out

# -----------------------------
# Western Engine
# -----------------------------
def calculate_western(jd: float, lat: float, lon: float, time_known: bool, birth_year: int) -> Dict[str, Any]:
    now = datetime.now(timezone.utc)
    jd_now = jd_from_utc(now)

    placements = {}
    fixed_stars_hits = []
    oob_hits = []
    aspects = []

    # Planet positions
    for name, pcode in PLANETS_W.items():
        plon, _ = calc_lon_lat(jd, pcode, 0)
        dec = calc_declination(jd, pcode)
        oob = abs(dec) > OOB_LIMIT
        placements[name] = {
            "lon": plon,
            "sign": zodiac_sign_w(plon),
            "deg_in_sign": deg_in_sign(plon),
            "declination": dec,
            "out_of_bounds": bool(oob)
        }
        if oob:
            oob_hits.append({"planet": name, "declination": dec})

    # Fixed stars (Royal)
    for star in ROYAL_FIXED_STARS:
        s_lon = fixed_star_lon(jd, star)
        if s_lon is None:
            continue
        for pname, pdata in placements.items():
            if is_conj(pdata["lon"], s_lon, orb=1.0):
                fixed_stars_hits.append({"planet": pname, "star": star, "orb_deg": round(abs(pdata["lon"] - s_lon), 3)})

    # Houses / Angles
    houses = {}
    angles = {}
    if time_known:
        cusps, ascmc = swe.houses(jd, lat, lon, b'P')
        asc = float(ascmc[0])
        mc = float(ascmc[1])
        angles = {
            "Ascendant": {"lon": asc, "sign": zodiac_sign_w(asc), "deg_in_sign": deg_in_sign(asc)},
            "Midheaven": {"lon": mc, "sign": zodiac_sign_w(mc), "deg_in_sign": deg_in_sign(mc)}
        }
        for i in range(12):
            c = float(cusps[i])
            houses[f"House_{i+1}"] = {"lon": c, "sign": zodiac_sign_w(c), "deg_in_sign": deg_in_sign(c)}

    # Aspects (planet-planet)
    names = list(PLANETS_W.keys())
    for i in range(len(names)):
        for j in range(i+1, len(names)):
            p1, p2 = names[i], names[j]
            a = aspect_type(placements[p1]["lon"], placements[p2]["lon"], orb=8.0)
            if a:
                aspects.append({"p1": p1, "p2": p2, "type": a})

    # Midpoints (a few key ones)
    midpoints = []
    midpoints.append({
        "name": "Sun/Moon",
        "lon": midpoint(placements["Sun"]["lon"], placements["Moon"]["lon"]),
    })
    if time_known and "Ascendant" in angles and "Midheaven" in angles:
        midpoints.append({
            "name": "ASC/MC",
            "lon": midpoint(angles["Ascendant"]["lon"], angles["Midheaven"]["lon"])
        })
    for m in midpoints:
        m["sign"] = zodiac_sign_w(m["lon"])
        m["deg_in_sign"] = deg_in_sign(m["lon"])

    # --- defaults so unknown-time charts don't crash ---
    transits_timeline: List[Dict[str, Any]] = []
    profections_timeline: List[Dict[str, Any]] = []
    progressions: Dict[str, Any] = {}
    solar_arc: Optional[Dict[str, Any]] = None
    directed: Dict[str, Any] = {}


    # Lots: Fortune + Spirit (requires Asc)
    lots = {}
    if time_known and "Ascendant" in angles:
        asc = angles["Ascendant"]["lon"]
        sun = placements["Sun"]["lon"]
        moon = placements["Moon"]["lon"]
        # Simple day/night test: sun above horizon approximated by relation to asc
        is_day = (sun - asc) % 360 > 180
        lof = lot_of_fortune(asc, sun, moon, is_day)
        los = lot_of_spirit(asc, sun, moon, is_day)
        lots = {
            "Lot_of_Fortune": {"lon": lof, "sign": zodiac_sign_w(lof), "deg_in_sign": deg_in_sign(lof), "is_day_birth": bool(is_day)},
            "Lot_of_Spirit": {"lon": los, "sign": zodiac_sign_w(los), "deg_in_sign": deg_in_sign(los), "is_day_birth": bool(is_day)}
        }

        # --- GOD TIER PREDICTIVE LOOP (5 YEARS) ---
        current_age_base = max(0, now.year - birth_year)
        forecast_years = 5
        transits_timeline = []
        profections_timeline = []

        for y_offset in range(forecast_years):
            target_now = now + timedelta(days=365.2425 * y_offset)
            target_jd = jd_from_utc(target_now)
            target_age = current_age_base + y_offset

            # 1. Transits for this specific year
            yearly_transits = {}
            for name in ["Jupiter", "Saturn", "Uranus", "Neptune", "Pluto"]:
                pcode = PLANETS_W[name]
                tlon, _ = calc_lon_lat(target_jd, pcode, 0)
                yearly_transits[name] = {"lon": tlon, "sign": zodiac_sign_w(tlon), "deg_in_sign": deg_in_sign(tlon)}
            transits_timeline.append({"year": target_now.year, "transits": yearly_transits})

            # 2. Profections for this specific year
            if time_known and "Ascendant" in angles:
                asc_sign_idx = ZODIAC_W.index(angles["Ascendant"]["sign"])
                prof_idx = (asc_sign_idx + target_age) % 12
                prof_sign = ZODIAC_W[prof_idx]

                # --- THE FIX: We must calculate the Time Lord! ---
                time_lord = get_ruler(prof_sign)
                profections_timeline.append(
                    {"year": target_now.year, "age": target_age, "profected_sign": prof_sign, "time_lord": time_lord})



        # Secondary progressions (We keep this as a slow-moving snapshot of current inner identity)
        jd_prog = jd + float(current_age_base)  # 1 day = 1 year
        psun, _ = calc_lon_lat(jd_prog, swe.SUN, 0)
        pmoon, _ = calc_lon_lat(jd_prog, swe.MOON, 0)
        progressions = {
            "Progressed_Sun": {"lon": psun, "sign": zodiac_sign_w(psun), "deg_in_sign": deg_in_sign(psun)},
            "Progressed_Moon": {"lon": pmoon, "sign": zodiac_sign_w(pmoon), "deg_in_sign": deg_in_sign(pmoon)}
        }

        # Solar Arc (directed): arc = progressed sun - natal sun
        solar_arc = None
        directed = {}
        if "Sun" in placements:
            arc = clamp360(psun - placements["Sun"]["lon"])
            solar_arc = {"arc_deg": arc}
            # Apply to a few points
            for key in ["Sun", "Moon", "Mercury", "Venus", "Mars", "Jupiter", "Saturn", "Uranus", "Neptune", "Pluto"]:
                lon0 = placements[key]["lon"]
                dlon = clamp360(lon0 + arc)
                directed[key] = {"lon": dlon, "sign": zodiac_sign_w(dlon), "deg_in_sign": deg_in_sign(dlon)}


    # Zodiacal Releasing (Fortune/Spirit)
    zr = {}
    if lots.get("Lot_of_Fortune"):
        zr["Fortune"] = zr_timeline(lots["Lot_of_Fortune"]["lon"], now, years=5.0)
    if lots.get("Lot_of_Spirit"):
        zr["Spirit"] = zr_timeline(lots["Lot_of_Spirit"]["lon"], now, years=5.0)

    return {
        "natal": {
            "placements": placements,
            "houses": houses,
            "angles": angles,
            "aspects": aspects,
            "midpoints": midpoints,
            "lots": lots,
            "fixed_stars": fixed_stars_hits,
            "out_of_bounds": oob_hits
        },
        "predictive": {
            "transits_timeline": transits_timeline,
            "progressions": progressions,
            "solar_arc": solar_arc,
            "directed_positions": directed,
            "profections_timeline": profections_timeline,
            "zodiacal_releasing": zr
        }
    }


# -----------------------------
# Vedic_engine Helpers (Sidereal)
# -----------------------------
NAKSHATRAS = [
    "Ashwini","Bharani","Krittika","Rohini","Mrigashira","Ardra","Punarvasu","Pushya","Ashlesha",
    "Magha","Purva Phalguni","Uttara Phalguni","Hasta","Chitra","Swati","Vishakha","Anuradha",
    "Jyeshtha","Mula","Purva Ashadha","Uttara Ashadha","Shravana","Dhanishta","Shatabhisha",
    "Purva Bhadrapada","Uttara Bhadrapada","Revati"
]

VEDIC_GRAHAS = ["Sun","Moon","Mars","Mercury","Jupiter","Venus","Saturn","Rahu","Ketu"]

def nakshatra_and_pada(sid_lon: float) -> Dict[str, Any]:
    size = 360 / 27.0
    idx = int(clamp360(sid_lon) / size)
    deg_in = clamp360(sid_lon) % size
    pada = int(deg_in / (size / 4.0)) + 1
    return {"nakshatra": NAKSHATRAS[idx], "pada": int(pada)}

def varga_sign_sidereal(sid_lon: float, n: int) -> str:
    """
    Generic varga sign chooser (simple equal division).
    NOTE: For D9 and D10, traditional mapping rules differ.
    We'll use specific D9/D10 functions below for correctness.
    """
    seg = 30.0 / n
    sign_idx = int(clamp360(sid_lon) // 30)
    within = clamp360(sid_lon) % 30.0
    part = int(within // seg)
    return ZODIAC_V[(sign_idx * n + part) % 12]

def navamsa_sign(sid_lon: float) -> str:
    # Classic D9 mapping by sign modality
    sign_idx = int(clamp360(sid_lon) // 30)
    within = clamp360(sid_lon) % 30.0
    part = int(within // (30.0 / 9.0))
    # Movable: start from same sign; Fixed: 9th; Dual: 5th
    if sign_idx in [0,3,6,9]:
        start = sign_idx
    elif sign_idx in [1,4,7,10]:
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
    if sign_idx in [0,3,6,9]:
        start = sign_idx
    elif sign_idx in [1,4,7,10]:
        start = (sign_idx + 8) % 12
    else:
        start = (sign_idx + 4) % 12
    return ZODIAC_V[(start + part) % 12]

VEDIC_RULERS = {
    "Mesha":"Mars","Vrishabha":"Venus","Mithuna":"Mercury","Karka":"Moon","Simha":"Sun","Kanya":"Mercury",
    "Tula":"Venus","Vrischika":"Mars","Dhanus":"Jupiter","Makara":"Saturn","Kumbha":"Saturn","Meena":"Jupiter"
}

EXALT = {"Sun":"Mesha","Moon":"Vrishabha","Mars":"Makara","Mercury":"Kanya","Jupiter":"Karka","Venus":"Meena","Saturn":"Tula","Rahu":"Vrishabha","Ketu":"Vrischika"}
DEBIL = {"Sun":"Tula","Moon":"Vrischika","Mars":"Karka","Mercury":"Meena","Jupiter":"Makara","Venus":"Kanya","Saturn":"Mesha","Rahu":"Vrischika","Ketu":"Vrishabha"}

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
    candidates = ["Sun","Moon","Mars","Mercury","Jupiter","Venus","Saturn"]
    vals = []
    for p in candidates:
        if p in placements:
            vals.append((p, float(placements[p]["deg_in_sign"])))
    vals.sort(key=lambda x: x[1], reverse=True)
    labels = ["Atmakaraka","Amatyakaraka","Bhratrikaraka","Matrikaraka","Putrakaraka","Gnatikaraka","Darakaraka"]
    out = {}
    for i, (p, _) in enumerate(vals[:7]):
        out[labels[i]] = p
    return out

def vimshottari_maha_lord(moon_sid_lon: float, age_years: float) -> Dict[str, Any]:
    """
    Returns current Maha Dasha lord + rough remaining years in that MD.
    (You can later extend to full maha/antar/pratyantar timelines.)
    """
    dasha_lords = ["Ketu","Venus","Sun","Moon","Mars","Rahu","Jupiter","Saturn","Mercury"]
    dasha_years = [7,20,6,10,7,18,16,19,17]
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

def shadbala_mvp(placements: Dict[str, Any]) -> Dict[str, Any]:
    """
    MVP strength score 0-100 (NOT classical full Shadbala).
    Built so Oracle can tier: WEAKENED / BALANCED / DOMINANT.
    """
    score = {}
    for p, d in placements.items():
        base = 50.0
        dig = d.get("dignity","Neutral")
        if dig == "Exalted": base += 25
        elif dig == "Own Sign": base += 18
        elif dig == "Debilitated": base -= 20
        if d.get("is_vargottama"): base += 10
        # slight nakshatra pada emphasis (later you can refine)
        base += (0.5 * (d.get("pada", 1) - 1))
        score[p] = max(0.0, min(100.0, round(base, 2)))
    return {"planet_scores": score, "method": "MVP_v1"}

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

def calculate_vedic(jd: float, lat: float, lon: float, time_known: bool, birth_dt_utc: datetime) -> Dict[str, Any]:
    AyanamsaManager.set_ayanamsa(settings.ayanamsa)
    v_flags = swe.FLG_SWIEPH | swe.FLG_SIDEREAL

    placements = {}
    # 7 classical + outer for placement context
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

    # Ascendant + Houses (sidereal)
    houses = {}
    bhava_chalit = {}
    if time_known:
        cv, av = swe.houses_ex(jd, lat, lon, b'P', v_flags)
        asc = float(av[0])
        placements["Ascendant"] = {"lon": asc, "sign": zodiac_sign_v(asc), "deg_in_sign": deg_in_sign(asc)}
        # House signs (sidereal)
        cusp_lons = [float(x) for x in cv[:12]]
        for i in range(12):
            houses[f"Bhava_{i+1}"] = {"cusp_lon": cusp_lons[i], "sign": zodiac_sign_v(cusp_lons[i]), "lord": VEDIC_RULERS[zodiac_sign_v(cusp_lons[i])]}
        # Bhava Chalit assignment: boundaries midpoint between cusps
        bounds = []
        for i in range(12):
            a = cusp_lons[i]
            b = cusp_lons[(i+1) % 12]
            bounds.append(midpoint(a, b))
        # Determine house by "between previous bound and next bound"
        def bhava_index(plon: float) -> int:
            # find nearest cusp interval
            # Use cusp ordering; this is a simplification but works for most charts
            for i in range(12):
                start = bounds[i-1]
                end = bounds[i]
                x = clamp360(plon)
                if start <= end:
                    if start <= x < end:
                        return i+1
                else:
                    # wrap
                    if x >= start or x < end:
                        return i+1
            return 1

        for p, d in placements.items():
            if p in ["Ascendant"]:
                continue
            if "lon" in d:
                bhava_chalit[p] = {"bhava": bhava_index(d["lon"])}

    # Jaimini Chara Karakas
    ck = chara_karakas(placements)

    # Vimshottari (current lord)
    now = datetime.now(timezone.utc)
    age_years = (now - birth_dt_utc).days / 365.2425
    moon_lon = placements["Moon"]["lon"]
    dasha = vimshottari_maha_lord(moon_lon, age_years)

    # Yogas (basic)
    yogas = []
    if time_known and "Ascendant" in placements:
        # extremely simplified: if kendra lord and trikona lord conjoin in same sign
        # (you can expand to aspects/exchanges later)
        house_signs = [houses[f"Bhava_{i+1}"]["sign"] for i in range(12)]
        kendra_lords = [VEDIC_RULERS[house_signs[0]], VEDIC_RULERS[house_signs[3]], VEDIC_RULERS[house_signs[6]], VEDIC_RULERS[house_signs[9]]]
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
                yogas.append({"type":"Raja Yoga","sign":s,"members":sorted(list(set(ks+ts)))})
            if ws and ts:
                yogas.append({"type":"Dhana Yoga","sign":s,"members":sorted(list(set(ws+ts)))})

    strength = {
        "shadbala": shadbala_mvp(placements),
        "ashtakavarga": ashtakavarga_mvp(placements)
    }

    return {
        "natal": {
            "placements": placements,
            "houses": houses,
            "bhava_chalit": bhava_chalit,
            "chara_karakas": ck,
            "yogas": yogas
        },
        "strength": strength,
        "predictive": {
            "vimshottari": dasha
        }
    }




# -----------------------------
# Bazi (Saju) Helpers
# -----------------------------
try:
    from lunar_python import Solar
except Exception as e:
    Solar = None

STEMS = ["甲","乙","丙","丁","戊","己","庚","辛","壬","癸"]
BRANCHES = ["子","丑","寅","卯","辰","巳","午","未","申","酉","戌","亥"]

STEM_ELEMENT = {"甲":"Wood","乙":"Wood","丙":"Fire","丁":"Fire","戊":"Earth","己":"Earth","庚":"Metal","辛":"Metal","壬":"Water","癸":"Water"}
BRANCH_ELEMENT = {"子":"Water","丑":"Earth","寅":"Wood","卯":"Wood","辰":"Earth","巳":"Fire","午":"Fire","未":"Earth","申":"Metal","酉":"Metal","戌":"Earth","亥":"Water"}

HIDDEN_STEMS = {
    "子":["癸"],
    "丑":["己","癸","辛"],
    "寅":["甲","丙","戊"],
    "卯":["乙"],
    "辰":["戊","乙","癸"],
    "巳":["丙","庚","戊"],
    "午":["丁","己"],
    "未":["己","丁","乙"],
    "申":["庚","壬","戊"],
    "酉":["辛"],
    "戌":["戊","辛","丁"],
    "亥":["壬","甲"]
}

GEN_CYCLE = {"Wood":"Fire","Fire":"Earth","Earth":"Metal","Metal":"Water","Water":"Wood"}
CTRL_CYCLE = {"Wood":"Earth","Earth":"Water","Water":"Fire","Fire":"Metal","Metal":"Wood"}

def ten_god(dm_el: str, target_el: str) -> str:
    if dm_el == target_el:
        return "Companion"
    if GEN_CYCLE[dm_el] == target_el:
        return "Output"
    if CTRL_CYCLE[dm_el] == target_el:
        return "Wealth"
    if CTRL_CYCLE[target_el] == dm_el:
        return "Power"
    if GEN_CYCLE[target_el] == dm_el:
        return "Resource"
    return "Unknown"

# Chang Sheng 12 stages mapping start branch (长生) per stem
# Using common mnemonic: 甲亥 乙午 丙寅 丁酉 戊寅 己酉 庚巳 辛子 壬申 癸卯
CS_START = {
    "甲":"亥","乙":"午","丙":"寅","丁":"酉","戊":"寅","己":"酉","庚":"巳","辛":"子","壬":"申","癸":"卯"
}
CS_STAGES = ["ChangSheng","MuYu","GuanDai","LinGuan","DiWang","Shuai","Bing","Si","Mu","Jue","Tai","Yang"]

def qi_phase(stem: str, branch: str) -> Optional[str]:
    if stem not in CS_START or branch not in BRANCHES:
        return None
    start = CS_START[stem]
    sidx = BRANCHES.index(start)
    bidx = BRANCHES.index(branch)
    # Yang stems forward, Yin stems backward
    is_yang = STEMS.index(stem) % 2 == 0
    if is_yang:
        offset = (bidx - sidx) % 12
    else:
        offset = (sidx - bidx) % 12
    return CS_STAGES[offset]

# Shen Sha (a few high-impact ones)
PEACH_BLOSSOM = {
    frozenset(["申","子","辰"]): "酉",
    frozenset(["亥","卯","未"]): "子",
    frozenset(["寅","午","戌"]): "卯",
    frozenset(["巳","酉","丑"]): "午"
}
TRAVEL_HORSE = {
    frozenset(["申","子","辰"]): "寅",
    frozenset(["亥","卯","未"]): "巳",
    frozenset(["寅","午","戌"]): "申",
    frozenset(["巳","酉","丑"]): "亥"
}
# Tian Yi Nobleman by Day Stem (common table)
TIANYI = {
    "甲":["丑","未"], "己":["丑","未"],
    "乙":["子","申"], "庚":["子","申"],
    "丙":["亥","酉"], "辛":["亥","酉"],
    "丁":["酉","亥"], "壬":["酉","亥"],
    "戊":["卯","巳"], "癸":["卯","巳"]
}

# Harms / Punishments / Destructions
LIU_HAI = [("子","未"),("丑","午"),("寅","巳"),("卯","辰"),("申","亥"),("酉","戌")]
PO = [("子","酉"),("丑","辰"),("寅","亥"),("卯","午"),("巳","申"),("未","戌")]
# Basic "punishments" incl 3-penalties
SAN_XING = [
    ("寅","巳","申"),
    ("丑","未","戌"),
    ("子","卯")  # zi-mao punishment
]

CLASHES = [
    ({"子","午"},"Rat-Horse Clash"),
    ({"丑","未"},"Ox-Goat Clash"),
    ({"寅","申"},"Tiger-Monkey Clash"),
    ({"卯","酉"},"Rabbit-Rooster Clash"),
    ({"辰","戌"},"Dragon-Dog Clash"),
    ({"巳","亥"},"Snake-Pig Clash"),
]

def void_emptiness(day_stem: str, day_branch: str) -> List[str]:
    if day_stem not in STEMS or day_branch not in BRANCHES:
        return []
    s = STEMS.index(day_stem)
    b = BRANCHES.index(day_branch)
    v1 = (b - s + 10) % 12
    v2 = (v1 + 1) % 12
    return [BRANCHES[v1], BRANCHES[v2]]

def bazi_interactions(branches_by_pillar: Dict[str, str]) -> Dict[str, Any]:
    brs = list(branches_by_pillar.items())
    out = {"clashes": [], "harms": [], "destructions": [], "punishments": []}

    # clashes
    for i in range(len(brs)):
        for j in range(i+1, len(brs)):
            a = branches_by_pillar[brs[i][0]]
            b = branches_by_pillar[brs[j][0]]
            for pair, name in CLASHES:
                if {a,b} == pair:
                    out["clashes"].append({"p1": brs[i][0], "p2": brs[j][0], "type": name})

            for x,y in LIU_HAI:
                if {a,b} == {x,y}:
                    out["harms"].append({"p1": brs[i][0], "p2": brs[j][0], "type": f"{x}-{y} Harm"})
            for x,y in PO:
                if {a,b} == {x,y}:
                    out["destructions"].append({"p1": brs[i][0], "p2": brs[j][0], "type": f"{x}-{y} Destruction"})

    # punishments
    all_br = set(branches_by_pillar.values())
    for s in SAN_XING:
        if len(s) == 2:
            if set(s).issubset(all_br):
                out["punishments"].append({"type":"Zi-Mao Punishment","branches":list(s)})
        else:
            if set(s).issubset(all_br):
                out["punishments"].append({"type":"Three Penalties","branches":list(s)})

    return out

def dm_strength_and_useful_god(pillars: Dict[str, Any]) -> Dict[str, Any]:
    dm_stem = pillars["Day"]["stem"]
    dm_el = STEM_ELEMENT.get(dm_stem, "Unknown")
    month_branch = pillars["Month"]["branch"]
    season_el = BRANCH_ELEMENT.get(month_branch, "Unknown")

    score = 50.0
    # seasonal support
    if season_el == dm_el:
        score += 12
    if GEN_CYCLE.get(season_el) == dm_el:
        score += 8
    if GEN_CYCLE.get(dm_el) == season_el:
        score -= 6

    # roots: hidden stems containing dm stem element
    root_count = 0
    for p in pillars.values():
        br = p["branch"]
        hs = HIDDEN_STEMS.get(br, [])
        for h in hs:
            if STEM_ELEMENT.get(h) == dm_el:
                root_count += 1
    score += min(18, root_count * 6)

    # supporting vs draining elements in all stems/branches
    sup = 0
    drain = 0
    for p in pillars.values():
        sup += 1 if ten_god(dm_el, STEM_ELEMENT.get(p["stem"],"Unknown")) in ["Companion","Resource"] else 0
        drain += 1 if ten_god(dm_el, STEM_ELEMENT.get(p["stem"],"Unknown")) in ["Wealth","Output","Power"] else 0
        sup += 1 if ten_god(dm_el, BRANCH_ELEMENT.get(p["branch"],"Unknown")) in ["Companion","Resource"] else 0
        drain += 1 if ten_god(dm_el, BRANCH_ELEMENT.get(p["branch"],"Unknown")) in ["Wealth","Output","Power"] else 0

    score += (sup - drain) * 2.5
    score = max(0.0, min(100.0, score))

    tier = "BALANCED"
    if score < 40: tier = "WEAK"
    if score > 60: tier = "STRONG"

    # Useful God heuristic:
    # - if DM is strong -> favor draining/controlling elements (Wealth/Output/Power)
    # - if DM is weak -> favor supporting (Resource/Companion)
    if tier == "STRONG":
        # choose Wealth or Output depending on cycles
        useful = CTRL_CYCLE[dm_el]  # wealth element
        alt = GEN_CYCLE[dm_el]      # output element
        useful_god = useful
        secondary = alt
    elif tier == "WEAK":
        useful = GEN_CYCLE[dm_el]   # resource produces DM? careful: Resource is element that produces DM, which is prev in gen cycle.
        # producer:
        producer = None
        for e, nxt in GEN_CYCLE.items():
            if nxt == dm_el:
                producer = e
        useful_god = producer or "Unknown"
        secondary = dm_el
    else:
        # balanced -> pick element that smooths extremes: often Wealth or Output
        useful_god = CTRL_CYCLE[dm_el]
        secondary = GEN_CYCLE[dm_el]

    return {
        "day_master": {"stem": dm_stem, "element": dm_el},
        "score": round(score, 2),
        "tier": tier,
        "useful_god": useful_god,
        "secondary_support": secondary
    }

def sexagenary_step(stem: str, branch: str, step: int) -> Tuple[str,str]:
    si = STEMS.index(stem)
    bi = BRANCHES.index(branch)
    return STEMS[(si + step) % 10], BRANCHES[(bi + step) % 12]

def sun_lon_tropical(jd: float) -> float:
    lon, _ = calc_lon_lat(jd, swe.SUN, 0)
    return lon

def next_jieqi_days(birth_jd: float, forward: bool = True) -> float:
    """
    Approx: find next (or prev) 15° solar longitude boundary (JieQi step).
    Used for Da Yun start age: days / 3.
    """
    lon0 = sun_lon_tropical(birth_jd)
    boundary = (math.floor(lon0 / 15.0) + (1 if forward else 0)) * 15.0
    boundary = clamp360(boundary)
    # iterate day by day then refine
    step = 1 if forward else -1
    jd = birth_jd
    for _ in range(90):  # within 3 months window
        jd2 = jd + step
        lon = sun_lon_tropical(jd2)
        # detect crossing
        if forward:
            if (lon0 <= boundary <= lon) or (lon < lon0 and boundary >= lon0):  # wrap guard
                return abs(jd2 - birth_jd)
        else:
            if (lon <= boundary <= lon0) or (lon0 < lon and boundary <= lon0):
                return abs(jd2 - birth_jd)
        jd = jd2
        lon0 = lon
    # fallback
    return 30.0

def da_yun_direction(year_stem: str, gender: str) -> bool:
    """
    forward=True means step forward through sexagenary.
    Rule (common): Yang year stem + male => forward; Yin year stem + male => backward; female opposite.
    """
    is_yang = STEMS.index(year_stem) % 2 == 0
    g = (gender or "male").strip().lower()
    male = g.startswith("m")
    if male:
        return is_yang
    else:
        return not is_yang

def build_da_yun(pillars: Dict[str, Any], birth_jd: float, gender: str) -> Dict[str, Any]:
    year_stem = pillars["Year"]["stem"]
    forward = da_yun_direction(year_stem, gender)
    days = next_jieqi_days(birth_jd, forward=forward)
    start_age = round(days / 3.0, 2)  # days/3 => years (common convention)
    # start from month pillar
    ms, mb = pillars["Month"]["stem"], pillars["Month"]["branch"]
    luck = []
    step = 1 if forward else -1
    cur_s, cur_b = ms, mb
    for i in range(8):
        cur_s, cur_b = sexagenary_step(cur_s, cur_b, step)
        luck.append({
            "index": i+1,
            "stem": cur_s,
            "branch": cur_b,
            "start_age": round(start_age + i*10, 2),
            "end_age": round(start_age + (i+1)*10, 2),
            "stem_element": STEM_ELEMENT.get(cur_s),
            "branch_element": BRANCH_ELEMENT.get(cur_b),
        })
    return {"direction": "forward" if forward else "backward", "start_age": start_age, "pillars": luck}

def shensha(pillars: Dict[str, Any]) -> List[Dict[str, Any]]:
    year_br = pillars["Year"]["branch"]
    day_br = pillars["Day"]["branch"]
    day_stem = pillars["Day"]["stem"]

    def group(branch: str) -> frozenset:
        for g in PEACH_BLOSSOM.keys():
            if branch in g:
                return g
        return frozenset()

    pb = PEACH_BLOSSOM.get(group(day_br)) or PEACH_BLOSSOM.get(group(year_br))
    th = TRAVEL_HORSE.get(group(day_br)) or TRAVEL_HORSE.get(group(year_br))

    out = []
    if pb:
        out.append({"type":"Peach Blossom","branch":pb})
    if th:
        out.append({"type":"Traveling Horse","branch":th})

    nobles = TIANYI.get(day_stem, [])
    for b in nobles:
        out.append({"type":"TianYi Nobleman","branch":b})

    return out

def calculate_bazi(birth_dt_utc: datetime, time_known: bool, gender: str, birth_jd: float) -> Dict[str, Any]:
    if Solar is None:
        raise ImportError("lunar_python not installed. pip install lunar-python")

    # Convert UTC -> local Beijing? lunar_python expects local time; we keep UTC but it’s okay if you later pass local.
    solar = Solar.fromYmdHms(birth_dt_utc.year, birth_dt_utc.month, birth_dt_utc.day, birth_dt_utc.hour, birth_dt_utc.minute, 0)
    eight = solar.getLunar().getEightChar()

    raw = {
        "Year": {"stem": eight.getYearGan(), "branch": eight.getYearZhi()},
        "Month": {"stem": eight.getMonthGan(), "branch": eight.getMonthZhi()},
        "Day": {"stem": eight.getDayGan(), "branch": eight.getDayZhi()},
    }
    if time_known:
        raw["Hour"] = {"stem": eight.getTimeGan(), "branch": eight.getTimeZhi()}

    voids = void_emptiness(raw["Day"]["stem"], raw["Day"]["branch"])
    # annotate pillars
    dm_el = STEM_ELEMENT.get(raw["Day"]["stem"], "Unknown")
    annotated = {}
    branch_only = {}
    for k, v in raw.items():
        s_el = STEM_ELEMENT.get(v["stem"], "Unknown")
        b_el = BRANCH_ELEMENT.get(v["branch"], "Unknown")
        branch_only[k] = v["branch"]
        annotated[k] = {
            "stem": v["stem"],
            "stem_element": s_el,
            "stem_10_god": ten_god(dm_el, s_el),
            "branch": v["branch"],
            "branch_element": b_el,
            "branch_10_god": ten_god(dm_el, b_el),
            "hidden_stems": HIDDEN_STEMS.get(v["branch"], []),
            "is_void": v["branch"] in voids,
            "qi_phase": qi_phase(raw["Day"]["stem"], v["branch"])
        }

    strength = dm_strength_and_useful_god(raw)
    luck = build_da_yun(raw, birth_jd, gender)
    inter = bazi_interactions(branch_only)
    ss = shensha(raw)

    # --- BAZI 5-YEAR LIU NIAN TIMELINE ---
    forecast_years = 5
    now = datetime.now(timezone.utc)
    liu_nian_timeline = []

    for y_offset in range(forecast_years):
        target_now = now + timedelta(days=365.25 * y_offset)
        solar_now = Solar.fromYmdHms(target_now.year, target_now.month, target_now.day, target_now.hour,
                                     target_now.minute, 0)
        eight_now = solar_now.getLunar().getEightChar()

        liu_nian_timeline.append({
            "year": target_now.year,
            "stem": eight_now.getYearGan(),
            "branch": eight_now.getYearZhi()
        })

    return {
        "natal": {"pillars": annotated, "void_emptiness": voids, "shensha": ss, "interactions": inter},
        "strength": strength,
        "predictive": {"da_yun": luck, "liu_nian_timeline": liu_nian_timeline}
    }


# -----------------------------
# Master Orchestrator
# -----------------------------
def calculate_all_charts(year: int, month: int, day: int, time_input: str, city: str, country: str,
                         tz_name: Optional[str] = None, gender: str = "male") -> Dict[str, Any]:

    tz = tz_name or infer_tz(country)
    birth_dt_utc, time_known = to_utc_datetime(year, month, day, time_input, tz)

    lat, lon = geocode(city, country)
    if lat is None:
        return {"error": "Could not locate city/country.", "meta": {"city": city, "country": country}}

    jd = jd_from_utc(birth_dt_utc)

    western = calculate_western(jd, lat, lon, time_known, birth_year=year)
    vedic = calculate_vedic(jd, lat, lon, time_known, birth_dt_utc=birth_dt_utc)
    bazi = calculate_bazi(birth_dt_utc, time_known, gender=gender, birth_jd=jd)

    return {
        "meta": {
            "birth_utc": birth_dt_utc.isoformat(),
            "time_known": bool(time_known),
            "city": city,
            "country": country,
            "tz_used": tz,
            "lat": lat,
            "lon": lon,
            "warnings": []
        },
        "western": western,
        "vedic": vedic,
        "bazi": bazi
    }


if __name__ == "__main__":
    import json
    data = calculate_all_charts(1993, 7, 19, "14:30", "London", "UK", tz_name="Europe/London", gender="male")
    print(json.dumps(data, ensure_ascii=False, indent=2))


