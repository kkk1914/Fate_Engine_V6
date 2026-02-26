"""Solar Return calculations with precession correction."""
import swisseph as swe
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Tuple, List

class SolarReturnEngine:
    """Calculate precession-corrected Solar Returns."""

    def __init__(self, natal_jd: float, natal_lat: float, natal_lon: float):
        self.natal_jd = natal_jd
        self.natal_lat = natal_lat
        self.natal_lon = natal_lon
        self.natal_sun = self._get_natal_sun()

    def _get_natal_sun(self) -> float:
        """Get natal Sun longitude."""
        pos, _ = swe.calc_ut(self.natal_jd, swe.SUN)
        return pos[0]

    def calculate_return(self, year: int) -> Dict[str, Any]:
        """Calculate Solar Return for specific year."""
        # Get birth date from JD using revjul (returns tuple)
        birth_tuple = swe.revjul(self.natal_jd)
        birth_year = birth_tuple[0]

        # Create target date (birthday in target year)
        target_month = birth_tuple[1]
        target_day = birth_tuple[2]

        # Start search from noon on birthday
        jd_guess = swe.julday(year, target_month, target_day, 12.0)

        # Find exact Sun return to natal longitude
        for _ in range(20):
            pos, _ = swe.calc_ut(jd_guess, swe.SUN)
            diff = (pos[0] - self.natal_sun) % 360
            if diff > 180:
                diff -= 360

            if abs(diff) < 0.0001:
                break

            # Adjust by ~1 day per degree
            jd_guess -= diff / 0.9856

        sr_jd = jd_guess

        # Calculate chart
        cusps, ascmc = swe.houses(sr_jd, self.natal_lat, self.natal_lon, b'P')

        # Get planet positions
        planets = {}
        for name, code in [("Sun", swe.SUN), ("Moon", swe.MOON),
                          ("Mercury", swe.MERCURY), ("Venus", swe.VENUS),
                          ("Mars", swe.MARS), ("Jupiter", swe.JUPITER),
                          ("Saturn", swe.SATURN)]:
            pos, _ = swe.calc_ut(sr_jd, code)
            planets[name] = {
                "lon": pos[0],
                "sign": self._get_sign(pos[0]),
                "house": self._get_house(pos[0], cusps)
            }

        sr_asc = ascmc[0]

        # Format date string
        sr_tuple = swe.revjul(sr_jd)
        sr_year_f, sr_month, sr_day, sr_hour_float = sr_tuple  # <-- renamed locals
        sr_hour = int(sr_hour_float)
        sr_minute = int((sr_hour_float - sr_hour) * 60)
        sr_date = f"{int(sr_year_f)}-{int(sr_month):02d}-{int(sr_day):02d} {sr_hour:02d}:{sr_minute:02d}"


        return {
            "year": year,
            "jd": sr_jd,
            "date": sr_date,
            "ascendant": sr_asc,
            "houses": list(cusps),
            "planets": planets,
            "dominant_house": self._get_dominant_house(sr_asc)
        }

    def _get_sign(self, lon: float) -> str:
        signs = ["Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo",
                "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces"]
        return signs[int(lon // 30)]

    def _get_house(self, lon: float, cusps: list) -> int:
        """Determine house placement."""
        for i in range(12):
            start = cusps[i]
            end = cusps[(i+1) % 12]
            # Handle 0° wrap
            if start <= end:
                if start <= lon < end:
                    return i + 1
            else:
                if lon >= start or lon < end:
                    return i + 1
        return 1

    def _get_dominant_house(self, sr_asc: float) -> int:
        """Which natal house does the SR Ascendant fall in?"""
        # Calculate natal houses
        natal_cusps, _ = swe.houses(self.natal_jd, self.natal_lat, self.natal_lon, b'P')
        return self._get_house(sr_asc, natal_cusps)

    def get_return_series(self, start_year: int, years: int = 5) -> List[Dict]:
        """Calculate series of solar returns."""
        returns = []
        for i in range(years):
            sr = self.calculate_return(start_year + i)
            returns.append(sr)
        return returns

    def analyze_return_vs_natal(self, sr_data: Dict) -> Dict[str, Any]:
        """Compare Solar Return to Natal chart."""
        natal_planets = {}
        for code, name in [(swe.SUN, "Sun"), (swe.MOON, "Moon"),
                          (swe.MERCURY, "Mercury"), (swe.VENUS, "Venus"),
                          (swe.MARS, "Mars"), (swe.JUPITER, "Jupiter"),
                          (swe.SATURN, "Saturn")]:
            pos, _ = swe.calc_ut(self.natal_jd, code)
            natal_planets[name] = pos[0]

        aspects = []
        for sr_pl, sr_data_pl in sr_data["planets"].items():
            for nat_pl, nat_lon in natal_planets.items():
                diff = abs(sr_data_pl["lon"] - nat_lon)
                if diff > 180:
                    diff = 360 - diff

                for angle, name in [(0, "Conjunction"), (60, "Sextile"),
                                   (90, "Square"), (120, "Trine"), (180, "Opposition")]:
                    if abs(diff - angle) <= 3:
                        aspects.append({
                            "sr_planet": sr_pl,
                            "natal_planet": nat_pl,
                            "aspect": name,
                            "orb": round(abs(diff - angle), 2),
                            "is_return": (sr_pl == nat_pl)
                        })

        return {
            "aspects_to_natal": aspects,
            "sr_asc_natal_house": sr_data.get("dominant_house"),
            "emphasized_natal_house": sr_data.get("dominant_house")
        }