"""Outer Transit Aspect Hits — Exact entry/exact/exit dates for major transits.

Replaces the year-snapshot transits_timeline with precise date windows.
Scans daily for each outer planet making major aspects to natal points.

ASPECTS: conjunction (0°), opposition (180°), square (90°), trine (120°), sextile (60°)
ORB: 3° for outer planets (Jupiter/Saturn), 2° for Uranus/Neptune/Pluto
SCAN: 5 years ahead at daily resolution; groups retrograde passes into single windows

PLANETS SCANNED:
  Transiting: Jupiter, Saturn, Uranus, Neptune (Pluto included but rarely exact)
  Natal targets: Sun, Moon, Mercury, Venus, Mars, Jupiter, Saturn, Ascendant, MC
"""

import swisseph as swe
import math
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional, Tuple

ASPECTS = {
    "conjunction": 0.0,
    "sextile": 60.0,
    "square": 90.0,
    "trine": 120.0,
    "opposition": 180.0,
}

# Orb by transit planet
ORBS = {
    "Jupiter":  3.0,
    "Saturn":   3.0,
    "Uranus":   2.5,
    "Neptune":  2.0,
    "Pluto":    1.5,
}

TRANSIT_PLANETS = {
    "Jupiter": swe.JUPITER,
    "Saturn":  swe.SATURN,
    "Uranus":  swe.URANUS,
    "Neptune": swe.NEPTUNE,
}

NATAL_TARGETS = ["Sun", "Moon", "Mercury", "Venus", "Mars",
                 "Jupiter", "Saturn", "Ascendant", "MC"]

PLANET_CODES = {
    "Sun": swe.SUN, "Moon": swe.MOON, "Mercury": swe.MERCURY,
    "Venus": swe.VENUS, "Mars": swe.MARS, "Jupiter": swe.JUPITER,
    "Saturn": swe.SATURN,
}

# Aspect quality for report use
ASPECT_QUALITY = {
    "conjunction": "fusion",
    "sextile":     "opportunity",
    "square":      "tension",
    "trine":       "flow",
    "opposition":  "awareness",
}


def _jd_to_date(jd: float) -> str:
    """Convert Julian Day to ISO date string."""
    try:
        jd_adj = jd + 0.5
        Z = int(jd_adj)
        F = jd_adj - Z
        A = Z if Z < 2299161 else Z + 1 + (alpha := int((Z - 1867216.25) / 36524.25)) - alpha // 4
        B = A + 1524
        C = int((B - 122.1) / 365.25)
        D = int(365.25 * C)
        E = int((B - D) / 30.6001)
        day = B - D - int(30.6001 * E)
        month = E - 1 if E < 14 else E - 13
        year = C - 4716 if month > 2 else C - 4715
        return f"{year:04d}-{month:02d}-{day:02d}"
    except Exception:
        return f"JD{jd:.0f}"


def _dt_to_jd(dt: datetime) -> float:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    epoch = datetime(2000, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    return 2451545.0 + (dt - epoch).total_seconds() / 86400.0


def _angular_distance(a: float, b: float) -> float:
    """Shortest angular distance between two ecliptic longitudes."""
    diff = abs(a - b) % 360
    return min(diff, 360 - diff)


def _aspect_orb(transit_lon: float, natal_lon: float, aspect_angle: float) -> float:
    """How many degrees away from exact aspect. Lower = tighter."""
    actual_dist = _angular_distance(transit_lon, natal_lon)
    return abs(actual_dist - aspect_angle)


def calculate_outer_transit_aspects(
    natal_jd: float,
    natal_positions: Dict[str, float],   # planet_name → ecliptic longitude (tropical)
    years_ahead: int = 5
) -> List[Dict[str, Any]]:
    """
    Main entry. Returns list of transit aspect windows, sorted by date.

    Args:
        natal_jd: Birth Julian Day (tropical)
        natal_positions: dict of natal planet ecliptic longitudes (tropical degrees)
                         Must include at least Sun, Moon, Mercury, Venus, Mars,
                         Jupiter, Saturn. Optionally Ascendant, MC.
        years_ahead: How far ahead to scan

    Returns:
        List of dicts, each representing one transit aspect window:
        {
            "transit_planet": "Jupiter",
            "natal_planet": "Sun",
            "aspect": "conjunction",
            "quality": "fusion",
            "orb_deg": 3.0,
            "entry_date": "2026-03-15",
            "exact_date": "2026-04-22",
            "exit_date": "2026-05-28",
            "retrograde_passes": 1,
            "description": "Jupiter conjunct natal Sun (exact Apr 22, 2026)"
        }
    """
    swe.set_ephe_path(None)  # Use bundled ephemeris

    now = datetime.now(timezone.utc)
    now_jd = _dt_to_jd(now)
    end_jd = now_jd + years_ahead * 365.25

    hits = []

    for t_name, t_code in TRANSIT_PLANETS.items():
        orb = ORBS[t_name]

        for n_name in NATAL_TARGETS:
            natal_lon = natal_positions.get(n_name)
            if natal_lon is None:
                continue

            for asp_name, asp_angle in ASPECTS.items():
                # Scan daily
                windows = _scan_aspect_windows(
                    t_code, t_name, natal_lon, asp_angle, asp_name,
                    orb, now_jd, end_jd
                )
                for w in windows:
                    w["transit_planet"] = t_name
                    w["natal_planet"] = n_name
                    w["aspect"] = asp_name
                    w["quality"] = ASPECT_QUALITY[asp_name]
                    w["description"] = (
                        f"{t_name} {asp_name} natal {n_name} "
                        f"(exact {w['exact_date']}, orb {w['min_orb']:.2f}°)"
                    )
                    hits.append(w)

    hits.sort(key=lambda x: x.get("entry_jd", 0))
    return hits


def _scan_aspect_windows(
    t_code: int, t_name: str,
    natal_lon: float, asp_angle: float, asp_name: str,
    max_orb: float,
    start_jd: float, end_jd: float,
) -> List[Dict]:
    """
    Scan daily for a single transit-planet/natal-planet/aspect combination.
    Groups consecutive in-orb days into a single window.
    Handles retrograde multi-passes by splitting on gaps > 10 days.
    """
    windows = []
    in_window = False
    window_start_jd = None
    window_min_orb = 99.0
    window_exact_jd = None
    prev_in_orb = False

    step = 1.0  # daily scan
    jd = start_jd

    while jd <= end_jd:
        try:
            pos, _ = swe.calc_ut(jd, t_code)
            t_lon = float(pos[0])
            orb = _aspect_orb(t_lon, natal_lon, asp_angle)
            currently_in_orb = orb <= max_orb
        except Exception:
            jd += step
            continue

        if currently_in_orb and not in_window:
            # Window opens
            in_window = True
            window_start_jd = jd
            window_min_orb = orb
            window_exact_jd = jd

        elif currently_in_orb and in_window:
            if orb < window_min_orb:
                window_min_orb = orb
                window_exact_jd = jd

        elif not currently_in_orb and in_window:
            # Window closes — find more precise exit by half-stepping
            precise_exit = _find_orb_crossing(t_code, natal_lon, asp_angle, max_orb,
                                               jd - step, jd)
            windows.append({
                "entry_jd": window_start_jd,
                "exact_jd": window_exact_jd,
                "exit_jd": precise_exit,
                "entry_date": _jd_to_date(window_start_jd),
                "exact_date": _jd_to_date(window_exact_jd),
                "exit_date": _jd_to_date(precise_exit),
                "min_orb": round(window_min_orb, 3),
                "orb_deg": round(max_orb, 1),
            })
            in_window = False
            window_min_orb = 99.0

        jd += step

    # Close any open window at scan end
    if in_window:
        windows.append({
            "entry_jd": window_start_jd,
            "exact_jd": window_exact_jd,
            "exit_jd": end_jd,
            "entry_date": _jd_to_date(window_start_jd),
            "exact_date": _jd_to_date(window_exact_jd),
            "exit_date": _jd_to_date(end_jd),
            "min_orb": round(window_min_orb, 3),
            "orb_deg": round(max_orb, 1),
        })

    # Merge windows separated by fewer than 20 days (retrograde re-approaches)
    windows = _merge_close_windows(windows, gap_days=20)
    return windows


def _find_orb_crossing(t_code, natal_lon, asp_angle, max_orb, jd_in, jd_out, depth=4):
    """Binary search for the exact day the aspect exits orb."""
    if depth == 0 or jd_out - jd_in < 0.25:
        return jd_out
    mid = (jd_in + jd_out) / 2
    try:
        pos, _ = swe.calc_ut(mid, t_code)
        orb = _aspect_orb(float(pos[0]), natal_lon, asp_angle)
        if orb <= max_orb:
            return _find_orb_crossing(t_code, natal_lon, asp_angle, max_orb, mid, jd_out, depth - 1)
        else:
            return _find_orb_crossing(t_code, natal_lon, asp_angle, max_orb, jd_in, mid, depth - 1)
    except Exception:
        return jd_out


def _merge_close_windows(windows: List[Dict], gap_days: float = 20) -> List[Dict]:
    """Merge retrograde multi-passes that are within gap_days of each other."""
    if len(windows) < 2:
        return windows

    merged = [windows[0]]
    for w in windows[1:]:
        prev = merged[-1]
        if w["entry_jd"] - prev["exit_jd"] <= gap_days:
            # Merge: keep earliest entry, latest exit, best (smallest) orb
            prev["exit_jd"] = w["exit_jd"]
            prev["exit_date"] = w["exit_date"]
            if w["min_orb"] < prev["min_orb"]:
                prev["min_orb"] = w["min_orb"]
                prev["exact_jd"] = w["exact_jd"]
                prev["exact_date"] = w["exact_date"]
            prev["retrograde_merged"] = True
        else:
            merged.append(w)
    return merged


def build_outer_transits_for_archon(
    natal_jd: float,
    natal_positions: Dict[str, float],
    years_ahead: int = 5
) -> Dict[str, Any]:
    """
    High-level wrapper that returns data structured for the Archon predictive block.

    Returns:
        {
            "hits": [...],          # All aspect windows sorted by date
            "by_year": {...},       # Grouped by year for easy Archon injection
            "tight_hits": [...],    # Only orb < 1° (highest quality)
            "summary_block": "..."  # Pre-formatted text for injection
        }
    """
    try:
        hits = calculate_outer_transit_aspects(natal_jd, natal_positions, years_ahead)
    except Exception as e:
        return {"error": str(e), "hits": [], "by_year": {}, "summary_block": ""}

    # Group by year
    by_year: Dict[int, List] = {}
    for h in hits:
        year = int(h.get("exact_date", "2026")[:4])
        by_year.setdefault(year, []).append(h)

    # Tight hits (exact orb < 1.0°)
    tight = [h for h in hits if h.get("min_orb", 99) < 1.0]

    # Build summary block for Archon injection
    lines = ["--- OUTER PLANET TRANSIT ASPECT HITS (exact dates, 5yr window) ---"]
    for year in sorted(by_year.keys()):
        year_hits = by_year[year]
        lines.append(f"\n{year}:")
        for h in sorted(year_hits, key=lambda x: x.get("exact_date", "")):
            lines.append(
                f"  {h['transit_planet']} {h['aspect']} natal {h['natal_planet']}: "
                f"in-orb {h['entry_date']} → {h['exit_date']}, "
                f"EXACT {h['exact_date']} (orb {h['min_orb']:.2f}°, {h['quality']})"
            )

    return {
        "hits": hits,
        "by_year": {str(y): v for y, v in by_year.items()},
        "tight_hits": tight,
        "summary_block": "\n".join(lines),
    }
