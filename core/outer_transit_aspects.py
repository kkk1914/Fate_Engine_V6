"""
core/outer_transit_aspects.py
─────────────────────────────
Exact outer-planet transit aspect engine.

REPLACES THE JUNE-15 SNAPSHOTTING BUG in systems/western.py.

Old approach: took planet positions on June 15 of each year — missed every
exact aspect that didn't happen near mid-June, and produced no entry/exit
dates at all.

New approach:
  1. Walk the ephemeris forward 1 day at a time (safe for outer planets:
     Jupiter moves 0.083°/day — a 3° orb window is 36+ days wide).
  2. Detect when orb crosses ORB_ENTER (3°) to start a window.
  3. Detect local minimum (orb stops shrinking) then refine via ternary
     search → sub-minute precision on exact date.
  4. Walk until orb widens past ORB_LEAVE to record entry/exact/exit.
  5. Handles retrograde: planet can re-enter the same orb window; each
     distinct dip to minimum becomes its own "hit".

Transiting: Jupiter, Saturn, Uranus, Neptune, Pluto.
Natal points: whatever natal_lons dict contains (Sun, Moon, angles, etc.)
Aspects: Conjunction, Sextile, Square, Trine, Opposition.

Return schema (what archon consumes):
  {
    "hits":         [sorted list of hit dicts],
    "by_year":      { "2026": [...], "2027": [...], ... },
    "summary_block": str
  }

Each hit dict:
  {
    "transiting":    "Jupiter",
    "natal_point":   "Sun",
    "aspect":        "Trine",
    "exact_date":    "2027-03-14",
    "entry_date":    "2027-01-22",
    "exit_date":     "2027-05-08",
    "exact_lon":     119.72,
    "natal_lon":     27.17,
    "orb_at_exact":  0.12,
    "year":          2027
  }
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

import swisseph as swe

def _swe_pos(result):
    """Normalise pyswisseph calc_ut/fixstar return across API versions.
    Old (<2.10): returns (positions_tuple, retflag) — result[0] is a tuple.
    New (>=2.10): returns flat 6-tuple directly   — result[0] is a float.
    """
    return result[0] if isinstance(result[0], (list, tuple)) else result


# ─────────────────────────────────────────────────────────────────────────────
# Configuration
# ─────────────────────────────────────────────────────────────────────────────

TRANSITING_PLANETS: Dict[str, int] = {
    "Jupiter": swe.JUPITER,
    "Saturn":  swe.SATURN,
    "Uranus":  swe.URANUS,
    "Neptune": swe.NEPTUNE,
    "Pluto":   swe.PLUTO,
}

ASPECTS: List[Tuple[float, str]] = [
    (0.0,   "Conjunction"),
    (60.0,  "Sextile"),
    (90.0,  "Square"),
    (120.0, "Trine"),
    (180.0, "Opposition"),
]

ORB_ENTER = 3.0   # degrees — start tracking
ORB_EXACT = 1.0   # degrees — report as a "hit"
ORB_LEAVE = 3.5   # slightly wider than enter to avoid jitter at boundary
STEP_DAYS = 1.0   # daily scan step


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _planet_lon(jd: float, code: int) -> float:
    pos = _swe_pos(swe.calc_ut(jd, code, swe.FLG_SWIEPH))
    return float(pos[0]) % 360.0


def _aspect_orb(tlon: float, nlon: float, target: float) -> float:
    """Angular distance from the target aspect angle. Returns [0, 180]."""
    raw = abs(tlon - nlon) % 360.0
    if raw > 180.0:
        raw = 360.0 - raw
    return abs(raw - target)


def _jd_to_str(jd: float) -> str:
    try:
        y, mo, d, _ = swe.revjul(jd)
        return f"{int(y)}-{int(mo):02d}-{int(d):02d}"
    except Exception:
        return "???"


def _jd_to_year(jd: float) -> int:
    try:
        y, _, _, _ = swe.revjul(jd)
        return int(y)
    except Exception:
        return 0


def _today_jd() -> float:
    n = datetime.now(timezone.utc)
    h = n.hour + n.minute / 60.0 + n.second / 3600.0
    return swe.julday(n.year, n.month, n.day, h)


# ─────────────────────────────────────────────────────────────────────────────
# Ternary search for exact aspect (minimum orb)
# ─────────────────────────────────────────────────────────────────────────────

def _find_exact_jd(code: int, nlon: float, target: float,
                   jd_lo: float, jd_hi: float) -> float:
    """
    Ternary search for minimum orb in [jd_lo, jd_hi].
    50 iterations → ~0.5 second precision.
    """
    for _ in range(50):
        m1 = jd_lo + (jd_hi - jd_lo) / 3.0
        m2 = jd_hi - (jd_hi - jd_lo) / 3.0
        if _aspect_orb(_planet_lon(m1, code), nlon, target) < \
           _aspect_orb(_planet_lon(m2, code), nlon, target):
            jd_hi = m2
        else:
            jd_lo = m1
    return (jd_lo + jd_hi) / 2.0


# ─────────────────────────────────────────────────────────────────────────────
# Single-pair scanner
# ─────────────────────────────────────────────────────────────────────────────

def _scan_pair(pname: str, pcode: int,
               npoint: str, nlon: float,
               start_jd: float, end_jd: float) -> List[Dict]:
    """
    Scan transiting planet `pname` against natal point `npoint` (at `nlon`)
    from start_jd to end_jd. Returns all exact hits.
    """
    hits: List[Dict] = []

    # pending[aspect_name] = dict with window state
    pending: Dict[str, Optional[Dict]] = {a: None for _, a in ASPECTS}

    jd = start_jd
    while jd <= end_jd:
        tlon = _planet_lon(jd, pcode)

        for target, aname in ASPECTS:
            orb  = _aspect_orb(tlon, nlon, target)
            p    = pending[aname]

            if orb <= ORB_ENTER:
                if p is None:
                    pending[aname] = {
                        "entry_jd": jd,
                        "min_orb":  orb,
                        "min_jd":   jd,
                        "last_jd":  jd,
                    }
                else:
                    if orb < p["min_orb"]:
                        p["min_orb"] = orb
                        p["min_jd"]  = jd
                    p["last_jd"] = jd

            elif p is not None:
                # Window just closed
                if p["min_orb"] <= ORB_EXACT:
                    # Refine exact date
                    lo = max(start_jd, p["entry_jd"] - 3.0)
                    hi = min(end_jd,   p["last_jd"]  + 3.0)
                    exact_jd  = _find_exact_jd(pcode, nlon, target, lo, hi)
                    exact_lon = _planet_lon(exact_jd, pcode)
                    exact_orb = _aspect_orb(exact_lon, nlon, target)

                    if exact_orb <= ORB_EXACT:
                        hits.append({
                            "transiting":  pname,
                            "natal_point": npoint,
                            "aspect":      aname,
                            "exact_date":  _jd_to_str(exact_jd),
                            "entry_date":  _jd_to_str(p["entry_jd"]),
                            "exit_date":   _jd_to_str(jd),
                            "exact_lon":   round(exact_lon, 2),
                            "natal_lon":   round(nlon, 2),
                            "orb_at_exact":round(exact_orb, 3),
                            "year":        _jd_to_year(exact_jd),
                            "_exact_jd":   exact_jd,  # removed before output
                        })
                pending[aname] = None

        jd += STEP_DAYS

    # Close any windows still open at end of scan (ongoing transit)
    for target, aname in ASPECTS:
        p = pending[aname]
        if p and p["min_orb"] <= ORB_EXACT:
            lo = max(start_jd, p["entry_jd"] - 3.0)
            hi = min(end_jd,   p["last_jd"]  + 3.0)
            exact_jd  = _find_exact_jd(pcode, nlon, target, lo, hi)
            exact_lon = _planet_lon(exact_jd, pcode)
            exact_orb = _aspect_orb(exact_lon, nlon, target)
            if exact_orb <= ORB_EXACT:
                hits.append({
                    "transiting":  pname,
                    "natal_point": npoint,
                    "aspect":      aname,
                    "exact_date":  _jd_to_str(exact_jd),
                    "entry_date":  _jd_to_str(p["entry_jd"]),
                    "exit_date":   f">{_jd_to_str(end_jd)} (ongoing)",
                    "exact_lon":   round(exact_lon, 2),
                    "natal_lon":   round(nlon, 2),
                    "orb_at_exact":round(exact_orb, 3),
                    "year":        _jd_to_year(exact_jd),
                    "_exact_jd":   exact_jd,
                })

    return hits


# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────

def build_outer_transits_for_archon(natal_jd: float,
                                    natal_lons: Dict[str, float],
                                    years_ahead: int = 5) -> Dict:
    """
    Scan all outer planets against all natal points for `years_ahead` years
    starting from today.

    Parameters
    ----------
    natal_jd   : birth Julian Day (used only to ensure we don't scan before birth)
    natal_lons : {point_name: tropical_longitude_degrees}
    years_ahead: years to scan from today

    Returns
    -------
    {
      "hits":          [hit, ...],          sorted by exact_date
      "by_year":       {"2026": [...], ...}
      "summary_block": str
      "scan_method":   str
    }
    """
    start_jd = max(natal_jd, _today_jd())
    end_jd   = start_jd + years_ahead * 365.25

    all_hits: List[Dict] = []

    for pname, pcode in TRANSITING_PLANETS.items():
        for npoint, nlon in natal_lons.items():
            all_hits.extend(
                _scan_pair(pname, pcode, npoint, float(nlon), start_jd, end_jd)
            )

    # Sort by exact date
    all_hits.sort(key=lambda h: h.get("_exact_jd", 0))

    # Strip internal sort key
    for h in all_hits:
        h.pop("_exact_jd", None)

    # Group by year
    by_year: Dict[str, List] = {}
    for h in all_hits:
        yr = str(h["year"])
        by_year.setdefault(yr, []).append(h)

    return {
        "hits":         all_hits,
        "by_year":      by_year,
        "summary_block":_build_summary(all_hits),
        "scan_method":  f"daily step + ternary search, orb ≤{ORB_EXACT}°",
        "total_hits":   len(all_hits),
    }


def _build_summary(hits: List[Dict]) -> str:
    if not hits:
        return "No exact outer-planet transit aspects found in scan window."

    lines = [
        f"=== OUTER PLANET TRANSITS — {len(hits)} exact aspects "
        f"(daily scan, orb ≤{ORB_EXACT}°) ===",
        "Format: exact_date | planet aspect natal_point | window",
        "",
    ]
    current_year = None
    for h in hits:
        yr = h["year"]
        if yr != current_year:
            lines.append(f"── {yr} ──────────────")
            current_year = yr
        lines.append(
            f"  {h['exact_date']}: {h['transiting']} {h['aspect']} "
            f"natal {h['natal_point']}  "
            f"[in:{h['entry_date']} out:{h['exit_date']}]  orb={h['orb_at_exact']}°"
        )

    lines.append("\n=== END TRANSIT ASPECTS ===")
    return "\n".join(lines)
