"""Lunar Return calculations - monthly precision timing."""
import swisseph as swe

def _swe_pos(result):
    """Normalise pyswisseph calc_ut/fixstar return across API versions.
    Old (<2.10): returns (positions_tuple, retflag) — result[0] is a tuple.
    New (>=2.10): returns flat 6-tuple directly   — result[0] is a float.
    """
    return result[0] if isinstance(result[0], (list, tuple)) else result

from datetime import datetime, timedelta
from typing import Dict, Any, List, Tuple, Optional

class LunarReturnEngine:
    """Calculate Lunar Returns for monthly predictive timing."""

    def __init__(self, natal_jd: float, natal_moon: float):
        self.natal_jd = natal_jd
        self.natal_moon = natal_moon  # Tropical longitude

    def calculate_return(self, year: int, month: int) -> Dict[str, Any]:
        """
        Calculate Lunar Return for specific month.
        """
        # Search window: target month ± 15 days (wider window)
        start_dt = datetime(year, month, 1, 0, 0, 0)
        if month == 12:
            end_dt = datetime(year + 1, 1, 15, 23, 59, 59)
        else:
            # Go to next month + 15 days
            if month == 11:
                end_dt = datetime(year + 1, 1, 15, 23, 59, 59)
            else:
                end_dt = datetime(year, month + 2, 15, 23, 59, 59)

        # Start a bit earlier to catch returns at month boundary
        if month == 1:
            search_start = datetime(year - 1, 12, 15, 0, 0, 0)
        else:
            search_start = datetime(year, month - 1, 15, 0, 0, 0)

        # Convert to JD
        start_jd = swe.julday(search_start.year, search_start.month, search_start.day, 0.0)
        end_jd = swe.julday(end_dt.year, end_dt.month, end_dt.day, 23.999)

        # Find exact return
        return_jd = self._find_exact_return(start_jd, end_jd)

        if not return_jd:
            return {"error": "Could not find lunar return"}

        # Calculate chart for return moment
        dt = swe.revjul(return_jd)
        return_date = f"{int(dt[0])}-{int(dt[1]):02d}-{int(dt[2]):02d} {int(dt[3]):02d}:{int((dt[3] % 1) * 60):02d}"

        return {
            "year": year,
            "month": month,
            "jd": return_jd,
            "date": return_date,
            "natal_moon": self.natal_moon,
            "return_moon": self.natal_moon,
            "confidence": 0.82
        }

    def _find_exact_return(self, start_jd: float, end_jd: float) -> Optional[float]:
        """Find exact Moon return to natal position using coarse then fine search."""
        # Coarse search: check every 6 hours
        jd = start_jd
        best_jd = None
        best_diff = 999

        while jd < end_jd:
            pos = _swe_pos(swe.calc_ut(jd, swe.MOON))
            diff = (pos[0] - self.natal_moon) % 360
            if diff > 180:
                diff = 360 - diff

            if diff < best_diff:
                best_diff = diff
                best_jd = jd

            if diff < 0.001:  # Found exact match
                return jd

            jd += 0.25  # 6 hour steps

        # If we found something close, refine it
        if best_jd and best_diff < 5.0:
            # Binary search around best candidate
            jd = best_jd
            step = 0.25

            while step > 0.0001:
                pos = _swe_pos(swe.calc_ut(jd, swe.MOON))
                diff = (pos[0] - self.natal_moon) % 360
                if diff > 180:
                    diff -= 360

                if abs(diff) < 0.001:
                    return jd

                if diff > 0:
                    jd -= step
                else:
                    jd += step

                step /= 2

            return jd

        return None

    def get_return_series(self, start_year: int, months: int = 12) -> List[Dict]:
        """Calculate series of lunar returns."""
        returns = []
        now = datetime.now()
        current_year = now.year
        current_month = now.month

        for i in range(months):
            target_month = current_month + i
            target_year = current_year + (target_month - 1) // 12
            target_month = ((target_month - 1) % 12) + 1

            lr = self.calculate_return(target_year, target_month)
            if "error" not in lr:
                returns.append(lr)

        return returns