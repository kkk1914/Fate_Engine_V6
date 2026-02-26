"""Hellenistic (Ancient) Astrology Engine."""
import math
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional
import swisseph as swe

from core.ephemeris import ephe
from systems.western import clamp360, ZODIAC

class HellenisticEngine:
    """Ancient techniques: Lots, Profections, Zodiacal Releasing, Dodecatemoria."""

    # Zodiacal Releasing periods (Schmidt/Valens based)
    ZR_PERIODS = {
        "Aries": 15, "Taurus": 8, "Gemini": 20, "Cancer": 25,
        "Leo": 19, "Virgo": 20, "Libra": 8, "Scorpio": 15,
        "Sagittarius": 12, "Capricorn": 27, "Aquarius": 30, "Pisces": 12
    }

    def calculate(self, jd: float, lat: float, lon: float,
                  time_known: bool, birth_year: int) -> Dict[str, Any]:
        """Calculate Hellenistic techniques."""
        if not time_known:
            return {"error": "Hellenistic techniques require birth time"}

        # Get basic chart data
        cusps, ascmc = ephe.houses(jd, lat, lon, b'W')  # Whole Sign for Hellenistic
        asc_sign_idx = int(ascmc[0] // 30)

        # Calculate Lots
        sun_lon = swe.calc_ut(jd, swe.SUN)[0][0]
        moon_lon = swe.calc_ut(jd, swe.MOON)[0][0]
        asc_lon = ascmc[0]

        is_day = self._is_day_chart(asc_lon, sun_lon)
        fortune_lon = self._calc_fortune(asc_lon, sun_lon, moon_lon, is_day)
        spirit_lon = self._calc_spirit(asc_lon, sun_lon, moon_lon, is_day)

        fortune_sign = ZODIAC[int(fortune_lon // 30)]
        spirit_sign = ZODIAC[int(spirit_lon // 30)]

        # Zodiacal Releasing from Fortune and Spirit
        now = datetime.now(timezone.utc)
        zr_fortune = self._zodiacal_releasing(fortune_sign, now, years=5)
        zr_spirit = self._zodiacal_releasing(spirit_sign, now, years=5)

        # Detailed Profections
        current_age = max(0, now.year - birth_year)
        profections = self._detailed_profections(asc_sign_idx, current_age)

        # Find Hyleg (giver of life)
        hyleg = self._find_hyleg(jd, asc_lon, sun_lon, moon_lon, is_day)

        # Dodecatemoria (Phase 5)
        dodecatemoria = {}
        try:
            from core.dodecatemoria import DodecatemoriaEngine
            dodec_engine = DodecatemoriaEngine()
            dodecatemoria = dodec_engine.calculate(jd, lat, lon, time_known)
        except Exception as e:
            dodecatemoria = {"error": str(e)}

        return {
            "lots": {
                "fortune": {
                    "longitude": fortune_lon,
                    "sign": fortune_sign,
                    "is_day_chart": is_day
                },
                "spirit": {
                    "longitude": spirit_lon,
                    "sign": spirit_sign,
                    "is_day_chart": is_day
                }
            },
            "zodiacal_releasing": {
                "fortune": zr_fortune,
                "spirit": zr_spirit
            },
            "annual_profections": profections,
            "hyleg": hyleg,
            "predominator": self._find_predominator(asc_lon, sun_lon, moon_lon, is_day),
            "dodecatemoria": dodecatemoria,
        }

    def _is_day_chart(self, asc: float, sun: float) -> bool:
        """Determine if day or night chart.

        Sun above horizon = Sun is 0-180° ahead of Ascendant in zodiac order.
        """
        diff = (sun - asc) % 360
        return 0 < diff < 180

    def _calc_fortune(self, asc: float, sun: float, moon: float, is_day: bool) -> float:
        """Lot of Fortune formula."""
        if is_day:
            return clamp360(asc + moon - sun)
        return clamp360(asc + sun - moon)

    def _calc_spirit(self, asc: float, sun: float, moon: float, is_day: bool) -> float:
        """Lot of Spirit formula."""
        if is_day:
            return clamp360(asc + sun - moon)
        return clamp360(asc + moon - sun)

    def _zodiacal_releasing(self, start_sign: str, start_dt: datetime,
                           years: float = 5) -> List[Dict]:
        """Calculate Zodiacal Releasing periods (L1 only for now)."""
        start_idx = ZODIAC.index(start_sign)
        lob_idx = (start_idx + 6) % 12  # Loosing of the Bond (opposite sign)

        periods = []
        current_time = start_dt
        remaining_years = years

        i = 0
        while remaining_years > 0 and i < 20:  # Safety limit
            sign = ZODIAC[(start_idx + i) % 12]
            period_years = min(self.ZR_PERIODS[sign], remaining_years)

            end_time = current_time + timedelta(days=period_years * 365.2425)

            periods.append({
                "sign": sign,
                "start_date": current_time.isoformat(),
                "end_date": end_time.isoformat(),
                "years": period_years,
                "is_loosing_of_bond": ((start_idx + i) % 12) == lob_idx,
                "level": "L1"
            })

            current_time = end_time
            remaining_years -= period_years
            i += 1

        return periods

    def _detailed_profections(self, asc_idx: int, current_age: int) -> Dict[str, Any]:
        """Calculate annual profections with detailed info."""
        profected_idx = (asc_idx + current_age) % 12
        profected_sign = ZODIAC[profected_idx]

        # Traditional rulerships (sect aware)
        rulers = {
            "Aries": "Mars", "Taurus": "Venus", "Gemini": "Mercury",
            "Cancer": "Moon", "Leo": "Sun", "Virgo": "Mercury",
            "Libra": "Venus", "Scorpio": "Mars", "Sagittarius": "Jupiter",
            "Capricorn": "Saturn", "Aquarius": "Saturn", "Pisces": "Jupiter"
        }

        # Triplicity rulers (simplified)
        triplicity_rulers = {
            "Fire": ["Sun", "Jupiter", "Saturn"],
            "Earth": ["Venus", "Moon", "Mars"],
            "Air": ["Saturn", "Mercury", "Jupiter"],
            "Water": ["Venus", "Mars", "Moon"]
        }

        element = self._get_element(profected_sign)

        return {
            "current_age": current_age,
            "profected_sign": profected_sign,
            "time_lord": rulers[profected_sign],
            "activated_house": (current_age % 12) + 1,
            "element": element,
            "triplicity_rulers": triplicity_rulers.get(element, []),
            "sequence": [ZODIAC[(asc_idx + age) % 12] for age in range(12)]
        }

    def _get_element(self, sign: str) -> str:
        elements = {
            "Aries": "Fire", "Leo": "Fire", "Sagittarius": "Fire",
            "Taurus": "Earth", "Virgo": "Earth", "Capricorn": "Earth",
            "Gemini": "Air", "Libra": "Air", "Aquarius": "Air",
            "Cancer": "Water", "Scorpio": "Water", "Pisces": "Water"
        }
        return elements.get(sign, "Unknown")

    def _find_hyleg(self, jd: float, asc: float, sun: float, moon: float, is_day: bool) -> Optional[str]:
        """Find Hyleg (giver of life) - simplified Valens method."""
        if is_day:
            # Day: Sun above horizon, or Moon, or Ascendant
            if (sun - asc) % 360 < 180:
                return "Sun"
            elif (moon - asc) % 360 < 180:
                return "Moon"
            else:
                return "Ascendant"
        else:
            # Night: Moon above horizon, or Sun, or Fortune
            if (moon - asc) % 360 < 180:
                return "Moon"
            elif (sun - asc) % 360 < 180:
                return "Sun"
            else:
                return "Moon"

    def _find_predominator(self, asc: float, sun: float, moon: float, is_day: bool) -> Optional[str]:
        """Find Predominator (epikratetor)."""
        if is_day:
            if (sun - asc) % 360 < 180:
                return "Sun"
            return "Moon"
        else:
            if (moon - asc) % 360 < 180:
                return "Moon"
            return "Sun"
