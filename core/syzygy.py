"""Pre-natal Syzygy (Eclipse/Lunation) calculation."""
import swisseph as swe

def _swe_pos(result):
    """Normalise pyswisseph calc_ut/fixstar return across API versions.
    Old (<2.10): returns (positions_tuple, retflag) — result[0] is a tuple.
    New (>=2.10): returns flat 6-tuple directly   — result[0] is a float.
    """
    return result[0] if isinstance(result[0], (list, tuple)) else result

from datetime import datetime
from typing import Dict, Any


class SyzygyEngine:
    """
    Calculate Pre-natal Syzygy (last New or Full Moon before birth).
    Hellenistic technique for conception/ancestral patterns.
    """

    def __init__(self, natal_jd: float):
        self.natal_jd = natal_jd

    def calculate_syzygy(self) -> Dict[str, Any]:
        """
        Find the pre-natal syzygy (last New or Full Moon before birth) to
        exact-minute precision using binary-search refinement.

        OLD APPROACH (bug): stepped every 1 day → could be 6° off because
        the Moon moves ~13°/day. A 1-day step catches the *day* but not the
        exact moment, so the reported longitude and sign can be wrong.

        NEW APPROACH:
        1. Coarse scan every 6 hours (Moon moves ~3.25° per 6h — safe to detect
           any lunation within the 45-day window without ever skipping one).
        2. When phase angle crosses 0° (New Moon) or 180° (Full Moon), refine
           with 50 iterations of binary search → precision to ~1 minute of time,
           which gives ecliptic longitude accuracy to ~0.01°.
        """
        try:
            SIGNS = ["Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo",
                     "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces"]
            RULERS = {
                "Aries": "Mars", "Taurus": "Venus", "Gemini": "Mercury",
                "Cancer": "Moon", "Leo": "Sun", "Virgo": "Mercury",
                "Libra": "Venus", "Scorpio": "Mars", "Sagittarius": "Jupiter",
                "Capricorn": "Saturn", "Aquarius": "Saturn", "Pisces": "Jupiter"
            }

            def phase_angle(jd: float) -> float:
                """Moon elongation from Sun: 0°=New, 180°=Full. Range [0, 360)."""
                sun = _swe_pos(swe.calc_ut(jd, swe.SUN))
                moon = _swe_pos(swe.calc_ut(jd, swe.MOON))
                return (moon[0] - sun[0]) % 360.0

            def find_exact_phase(jd_lo: float, jd_hi: float, target: float) -> float:
                """
                Binary search for exact phase crossing.
                target = 0.0 (New Moon) or 180.0 (Full Moon).
                Works by finding where (phase - target) crosses zero modulo 360.
                50 iterations → time precision ~1 second.
                """
                # Normalise so we're searching for a zero crossing in [-180, 180]
                def f(jd):
                    p = phase_angle(jd) - target
                    # Fold to [-180, 180] to handle the 360→0 wraparound
                    if p > 180:
                        p -= 360
                    elif p < -180:
                        p += 360
                    return p

                fa, fb = f(jd_lo), f(jd_hi)
                if fa * fb > 0:
                    # Same sign — no crossing; return the closer endpoint
                    return jd_lo if abs(fa) < abs(fb) else jd_hi

                for _ in range(50):
                    mid = (jd_lo + jd_hi) / 2.0
                    fm = f(mid)
                    if fa * fm <= 0:
                        jd_hi = mid
                        fb = fm
                    else:
                        jd_lo = mid
                        fa = fm

                return (jd_lo + jd_hi) / 2.0

            # ── Coarse scan: every 6 hours ────────────────────────────────────
            step = 0.25  # days (= 6 hours)
            search_start = self.natal_jd - 45.0
            candidates = []  # (jd_exact, type_str)

            prev_jd = search_start
            prev_p  = phase_angle(prev_jd)

            jd = prev_jd + step
            while jd <= self.natal_jd:
                p = phase_angle(jd)

                # Detect New Moon crossing (phase crosses 0° / 360°)
                # phase goes ... 358° → 359° → 0° → 1° ...
                # Detect as: prev_p > 350 and p < 10  (forward crossing through 0)
                if prev_p > 350.0 and p < 10.0:
                    exact_jd = find_exact_phase(prev_jd, jd, 0.0)
                    if exact_jd < self.natal_jd:
                        candidates.append((exact_jd, "New Moon"))

                # Detect Full Moon crossing (phase crosses 180°)
                # prev_p just below 180, p just above, or vice versa
                if prev_p < 180.0 and p >= 180.0:
                    exact_jd = find_exact_phase(prev_jd, jd, 180.0)
                    if exact_jd < self.natal_jd:
                        candidates.append((exact_jd, "Full Moon"))

                prev_jd = jd
                prev_p  = p
                jd += step

            if not candidates:
                return {"error": "No pre-natal lunation found in 45-day window"}

            # Pick the most recent lunation before birth
            exact_jd, syzygy_type = max(candidates, key=lambda x: x[0])

            # Get precise positions at exact moment
            sun_pos = _swe_pos(swe.calc_ut(exact_jd, swe.SUN))
            moon_pos = _swe_pos(swe.calc_ut(exact_jd, swe.MOON))

            # Format datetime
            y, mo, d, h, mi, s = swe.revjul(exact_jd)
            hours_int   = int(h)
            minutes_int = int((h - hours_int) * 60)
            date_str    = f"{int(y)}-{int(mo):02d}-{int(d):02d} {hours_int:02d}:{minutes_int:02d} UT"

            lon_for_sign = moon_pos[0] if syzygy_type == "New Moon" else moon_pos[0]
            sign = SIGNS[int(lon_for_sign // 30) % 12]

            return {
                "jd":               exact_jd,
                "type":             syzygy_type,
                "date":             date_str,
                "sun_lon":          round(float(sun_pos[0]),  4),
                "moon_lon":         round(float(moon_pos[0]), 4),
                "sign":             sign,
                "degree_in_sign":   round(float(lon_for_sign) % 30, 4),
                "ruler":            RULERS.get(sign, "Unknown"),
                "days_before_birth":round(self.natal_jd - exact_jd, 4),
                "phase":            syzygy_type,
                "exactness":        round(abs(phase_angle(exact_jd) -
                                           (0.0 if syzygy_type == "New Moon" else 180.0)), 4),
                "precision":        "exact-minute (binary search)"
            }

        except Exception as e:
            return {"error": f"Syzygy calculation failed: {str(e)}"}