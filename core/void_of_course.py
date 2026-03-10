"""Void of Course Moon calculations using Swiss Ephemeris."""
import swisseph as swe

def _swe_pos(result):
    """Normalise pyswisseph calc_ut/fixstar return across API versions.
    Old (<2.10): returns (positions_tuple, retflag) — result[0] is a tuple.
    New (>=2.10): returns flat 6-tuple directly   — result[0] is a float.
    """
    return result[0] if isinstance(result[0], (list, tuple)) else result

from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional, Tuple


# Planets that can make aspects (Ptolemaic 7, excluding Moon itself)
ASPECT_MAKERS = [swe.SUN, swe.MERCURY, swe.VENUS, swe.MARS,
                 swe.JUPITER, swe.SATURN]
ASPECT_ANGLES = [0.0, 60.0, 90.0, 120.0, 180.0]
ASPECT_ORB = 6.0  # Scanning orb


def _lon(jd: float, body: int) -> float:
    pos = _swe_pos(swe.calc_ut(jd, body))
    return float(pos[0])


def _moon_speed(jd: float) -> float:
    """Moon's daily motion in degrees."""
    pos = _swe_pos(swe.calc_ut(jd, swe.MOON, swe.FLG_SPEED))
    return float(pos[3])


def _angular_diff(a: float, b: float) -> float:
    d = (b - a) % 360
    if d > 180:
        d -= 360
    return d


class VoidOfCourseMoon:
    """
    Calculate Void of Course (VOC) Moon periods.
    Moon is VOC from its last applying Ptolemaic aspect until it enters the next sign.
    """

    PLANET_NAMES = {
        swe.SUN: "Sun", swe.MERCURY: "Mercury", swe.VENUS: "Venus",
        swe.MARS: "Mars", swe.JUPITER: "Jupiter", swe.SATURN: "Saturn"
    }
    ASPECT_NAMES = {0: "Conjunction", 60: "Sextile", 90: "Square",
                    120: "Trine", 180: "Opposition"}
    SIGNS = ["Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo",
             "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces"]

    def is_void_at(self, jd: float) -> Dict[str, Any]:
        """
        Check if Moon is Void of Course at the given Julian Day.
        Returns status and timing information.
        """
        moon_lon = _lon(jd, swe.MOON)
        sign_idx = int(moon_lon // 30)
        current_sign = self.SIGNS[sign_idx]
        deg_in_sign = moon_lon % 30

        # Find next sign ingress
        next_sign_entry_jd = self._find_next_sign_ingress(jd, moon_lon)
        next_sign = self.SIGNS[(sign_idx + 1) % 12]

        # Find the last applying aspect before sign change
        last_asp = self._last_aspect_before_sign_change(jd, moon_lon, next_sign_entry_jd)

        if last_asp is None:
            # No applying aspect found in remaining sign traversal = VOC now
            is_void = True
            void_since_jd = self._find_void_start(jd, sign_idx)
        else:
            # VOC only if that last aspect is already in the past
            is_void = last_asp["jd"] <= jd
            void_since_jd = last_asp["jd"] if is_void else None

        result = {
            "is_void": is_void,
            "moon_sign": current_sign,
            "moon_lon": round(moon_lon, 4),
            "deg_in_sign": round(deg_in_sign, 3),
            "void_ends_sign": next_sign,
            "void_ends_jd": next_sign_entry_jd,
        }

        end_dt = self._jd_to_datetime(next_sign_entry_jd)
        result["void_ends"] = end_dt.strftime("%Y-%m-%d %H:%M UTC") if end_dt else None

        if is_void and void_since_jd:
            result["void_since_jd"] = void_since_jd
            void_dt = self._jd_to_datetime(void_since_jd)
            result["void_since"] = void_dt.strftime("%Y-%m-%d %H:%M UTC") if void_dt else None

        if last_asp:
            result["last_aspect"] = {
                "planet": last_asp["planet"],
                "aspect": last_asp["aspect"],
                "orb": last_asp["orb"],
            }

        return result

    def get_voc_periods(self, start_jd: float, days_ahead: int = 30) -> List[Dict[str, Any]]:
        """
        List all Void of Course Moon periods within a date range.

        Algorithm:
        - Walk sign by sign through the window.
        - For each sign, check if Moon becomes VOC before leaving.
        - Jump to the NEXT sign's ingress after processing each sign.
          (The old code backed up before the ingress → infinite loop.)
        """
        periods = []
        end_jd = start_jd + days_ahead

        jd = start_jd

        # Safety counter — 30 days / ~2.25 days per sign ≈ 13 signs max
        for _ in range(60):
            if jd >= end_jd:
                break

            moon_lon = _lon(jd, swe.MOON)
            sign_idx = int(moon_lon // 30)

            # Find when Moon leaves this sign
            ingress_jd = self._find_next_sign_ingress(jd, moon_lon)

            # Cap to our window
            scan_end = min(ingress_jd, end_jd)

            # Find last applying aspect between now and sign change
            last_asp = self._last_aspect_before_sign_change(jd, moon_lon, ingress_jd)

            if last_asp is None:
                # Moon is already VOC for the rest of this sign
                void_start_jd = jd
                void_end_jd = ingress_jd
                dt_start = self._jd_to_datetime(void_start_jd)
                dt_end = self._jd_to_datetime(void_end_jd)
                duration_hours = (void_end_jd - void_start_jd) * 24

                if void_end_jd > start_jd:  # Only include if it ends after our window start
                    periods.append({
                        "sign": self.SIGNS[sign_idx],
                        "void_start_jd": void_start_jd,
                        "void_end_jd": void_end_jd,
                        "void_start": dt_start.strftime("%Y-%m-%d %H:%M UTC") if dt_start else None,
                        "void_end": dt_end.strftime("%Y-%m-%d %H:%M UTC") if dt_end else None,
                        "enters_sign": self.SIGNS[(sign_idx + 1) % 12],
                        "duration_hours": round(duration_hours, 1),
                        "last_aspect": None,
                        "significance": self._voc_significance(self.SIGNS[sign_idx])
                    })
            else:
                # VOC starts after last_asp["jd"] if that time is before ingress
                void_start_jd = last_asp["jd"]
                void_end_jd = ingress_jd

                # Only record if void period is within our window
                if void_start_jd < end_jd and void_end_jd > start_jd:
                    dt_start = self._jd_to_datetime(void_start_jd)
                    dt_end = self._jd_to_datetime(void_end_jd)
                    duration_hours = (void_end_jd - void_start_jd) * 24

                    periods.append({
                        "sign": self.SIGNS[sign_idx],
                        "void_start_jd": void_start_jd,
                        "void_end_jd": void_end_jd,
                        "void_start": dt_start.strftime("%Y-%m-%d %H:%M UTC") if dt_start else None,
                        "void_end": dt_end.strftime("%Y-%m-%d %H:%M UTC") if dt_end else None,
                        "enters_sign": self.SIGNS[(sign_idx + 1) % 12],
                        "duration_hours": round(duration_hours, 1),
                        "last_aspect": {
                            "planet": last_asp["planet"],
                            "aspect": last_asp["aspect"],
                            "orb": last_asp["orb"],
                        },
                        "significance": self._voc_significance(self.SIGNS[sign_idx])
                    })

            # ── KEY FIX: always advance PAST the sign ingress ─────────────────
            # Old code did: jd = next_ingress - 0.5 + 0.1  → stayed before ingress → infinite loop
            # New code: jump to just after the ingress and continue
            jd = ingress_jd + 0.01

        return periods

    def _last_aspect_before_sign_change(self, jd: float, moon_lon0: float,
                                        ingress_jd: float) -> Optional[Dict[str, Any]]:
        """
        Scan forward from jd to ingress_jd (30-min steps).
        Return the LAST applying aspect Moon makes before leaving its sign.
        Returns None if no applying aspect is found (Moon is already VOC).
        """
        sign0 = int(moon_lon0 // 30)
        step = 0.5 / 24  # 30 minutes

        last_aspect = None
        jd_scan = jd

        while jd_scan < ingress_jd:
            moon_lon = _lon(jd_scan, swe.MOON)

            # Stop if Moon crossed sign boundary
            if int(moon_lon // 30) != sign0:
                break

            for planet_code in ASPECT_MAKERS:
                planet_lon = _lon(jd_scan, planet_code)

                for angle in ASPECT_ANGLES:
                    diff = abs(_angular_diff(moon_lon, planet_lon) - angle)
                    if diff <= ASPECT_ORB:
                        # Check if applying: orb decreases one step ahead
                        moon_next = _lon(jd_scan + step, swe.MOON)
                        diff_next = abs(_angular_diff(moon_next, planet_lon) - angle)
                        if diff_next < diff:
                            last_aspect = {
                                "jd": jd_scan,
                                "planet": self.PLANET_NAMES.get(planet_code, str(planet_code)),
                                "aspect": self.ASPECT_NAMES.get(int(angle), f"{angle}°"),
                                "orb": round(diff, 3),
                                "moon_lon": moon_lon,
                            }
            jd_scan += step

        return last_aspect

    def _find_next_sign_ingress(self, jd: float, moon_lon: float) -> float:
        """Find exact JD when Moon enters next sign using coarse scan + binary refinement."""
        sign0 = int(moon_lon // 30)
        step = 0.5 / 24  # 30 min steps

        jd_scan = jd
        for _ in range(250):  # Max ~5 days
            jd_scan += step
            lon = _lon(jd_scan, swe.MOON)
            if int(lon // 30) != sign0:
                # Binary refinement
                lo, hi = jd_scan - step, jd_scan
                for _ in range(20):
                    mid = (lo + hi) / 2
                    if int(_lon(mid, swe.MOON) // 30) == sign0:
                        lo = mid
                    else:
                        hi = mid
                return hi

        return jd + 2.5  # Fallback: ~2.5 days max for any sign

    def _find_void_start(self, jd: float, sign_idx: int) -> Optional[float]:
        """
        Scan backward to find when the current VOC began.
        Stops as soon as we find an applying aspect or the Moon was in a different sign.
        Uses a single backward pass — no recursive calls to _last_aspect_before_sign_change.
        """
        step = 0.5 / 24  # 30 min steps back
        jd_scan = jd

        for _ in range(250):  # Max ~5 days back
            jd_scan -= step
            moon_lon = _lon(jd_scan, swe.MOON)

            # Stop if Moon was in a different sign
            if int(moon_lon // 30) != sign_idx:
                return jd_scan + step

            # Check for any applying aspect at this point
            moon_next = _lon(jd_scan + step, swe.MOON)
            for planet_code in ASPECT_MAKERS:
                planet_lon = _lon(jd_scan, planet_code)
                for angle in ASPECT_ANGLES:
                    diff = abs(_angular_diff(moon_lon, planet_lon) - angle)
                    if diff <= ASPECT_ORB:
                        diff_next = abs(_angular_diff(moon_next, planet_lon) - angle)
                        if diff_next < diff:
                            # Found the aspect that started the void — jd_scan is when it ended
                            return jd_scan

        return jd - 1.0  # Fallback

    def _jd_to_datetime(self, jd: float) -> Optional[datetime]:
        try:
            t = swe.revjul(jd)
            hour = t[3]
            h = int(hour)
            m = int((hour - h) * 60)
            return datetime(int(t[0]), int(t[1]), int(t[2]), h, m, tzinfo=timezone.utc)
        except Exception:
            return None

    def _voc_significance(self, sign: str) -> str:
        """Traditional VOC significance by sign."""
        good_voc = {"Cancer", "Taurus", "Sagittarius", "Pisces"}
        caution = {"Aries", "Scorpio", "Capricorn"}
        if sign in good_voc:
            return "FAVORABLE — Moon VOC in this sign produces unexpectedly good results"
        elif sign in caution:
            return "CAUTION — VOC Moon here indicates delays and frustration; avoid new starts"
        else:
            return "NEUTRAL — Standard caution: avoid signing contracts or starting new ventures"
