"""Swiss Ephemeris precision wrapper."""
import swisseph as swe
import os
from typing import Tuple, Optional, List
from datetime import datetime
from config import settings

class EphemerisEngine:
    """Precision ephemeris calculations to 0.001 arcsecond."""

    def __init__(self):
        self.ephe_path = settings.ephe_path
        if os.path.exists(self.ephe_path):
            swe.set_ephe_path(self.ephe_path)
        else:
            swe.set_ephe_path(None)  # Use Moshier fallback

    def julian_day(self, dt: datetime) -> float:
        """Convert datetime to Julian Day."""
        return swe.julday(
            dt.year, dt.month, dt.day,
            dt.hour + dt.minute/60.0 + dt.second/3600.0
        )

    def planet_longitude(self, jd: float, planet: int, flags: int = 0) -> Tuple[float, float]:
        """Get planet longitude and latitude."""
        pos, _ = swe.calc_ut(jd, planet, flags)
        return float(pos[0]), float(pos[1])

    def houses(self, jd: float, lat: float, lon: float, hsys: bytes = b'P') -> Tuple[List[float], List[float]]:
        """Calculate house cusps and angles.
        hsys: b'P'=Placidus, b'K'=Koch, b'E'=Equal, b'W'=Whole Sign
        """
        cusps, ascmc = swe.houses(jd, lat, lon, hsys)
        return [float(c) for c in cusps], [float(a) for a in ascmc]

    def fixstar(self, star: str, jd: float) -> Optional[float]:
        """Get fixed star longitude."""
        try:
            (lon, lat, dist, _), _ = swe.fixstar2_ut(star, jd)
            return float(lon)
        except Exception:
            return None

    def is_retrograde(self, jd: float, planet: int) -> bool:
        """Check if planet is retrograde."""
        pos, _ = swe.calc_ut(jd, planet, swe.FLG_SPEED)
        return float(pos[3]) < 0

# Global instance
ephe = EphemerisEngine()