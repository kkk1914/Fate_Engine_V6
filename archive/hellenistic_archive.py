"""Hellenistic (Ancient) Astrology Engine."""
import math
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional
import swisseph as swe

def _swe_pos(result):
    """Normalise pyswisseph calc_ut/fixstar return across API versions.
    Old (<2.10): returns (positions_tuple, retflag) — result[0] is a tuple.
    New (>=2.10): returns flat 6-tuple directly   — result[0] is a float.
    """
    return result[0] if isinstance(result[0], (list, tuple)) else result


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
        sun_lon = _swe_pos(swe.calc_ut(jd, swe.SUN))[0]
        moon_lon = _swe_pos(swe.calc_ut(jd, swe.MOON))[0]
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

        # Bonifications and maltreatments (Paulus Alexandrinus method)
        bonifications = {}
        try:
            bonifications = self._compute_bonifications(jd, is_day)
        except Exception as e:
            bonifications = {"error": str(e)}

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
            "bonifications": bonifications,
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
        """
        Zodiacal Releasing Levels 1, 2, and 3.
        FIX: Original only computed L1 (8–30-year periods).
        L2/L3 provide the 1–5 year and month-scale precision critical for timing.

        Algorithm (Valens / Schmidt):
          Total cycle = 129 years (sum of all sign periods).
          L1 period for sign X = ZR_PERIODS[X] years.
          L2 period for sign Y within L1-X = L1_X_duration * (ZR_PERIODS[Y] / 129).
          L3 period for sign Z within L2-Y = L2_Y_duration * (ZR_PERIODS[Z] / 129).
          Each level starts from the same sign as its parent level
          and proceeds sign by sign in zodiacal order.
        """
        TOTAL_CYCLE = sum(self.ZR_PERIODS.values())  # 129
        start_idx = ZODIAC.index(start_sign)
        lob_idx   = (start_idx + 6) % 12  # Loosing of the Bond (7th from start)

        l1_periods = []
        current_time  = start_dt
        remaining_yrs = years

        l1_i = 0
        while remaining_yrs > 0 and l1_i < 20:
            l1_sign_idx  = (start_idx + l1_i) % 12
            l1_sign      = ZODIAC[l1_sign_idx]
            l1_dur       = self.ZR_PERIODS[l1_sign]
            l1_actual    = min(l1_dur, remaining_yrs)
            l1_end       = current_time + timedelta(days=l1_actual * 365.2425)
            is_lob_l1    = l1_sign_idx == lob_idx

            # ── Build L2 sub-periods within this L1 ──────────────────────────
            l2_periods   = []
            l2_time      = current_time
            l2_remaining = l1_actual

            l2_i = 0
            while l2_remaining > 0 and l2_i < 12:
                l2_sign_idx = (l1_sign_idx + l2_i) % 12
                l2_sign     = ZODIAC[l2_sign_idx]
                # L2 fractional duration within this L1 period
                l2_full     = l1_dur * (self.ZR_PERIODS[l2_sign] / TOTAL_CYCLE)
                l2_actual   = min(l2_full, l2_remaining)
                l2_end      = l2_time + timedelta(days=l2_actual * 365.2425)
                is_lob_l2   = l2_sign_idx == lob_idx

                # ── Build L3 sub-periods within this L2 ──────────────────────
                l3_periods  = []
                l3_time     = l2_time
                l3_remaining = l2_actual

                l3_i = 0
                while l3_remaining > 0 and l3_i < 12:
                    l3_sign_idx = (l2_sign_idx + l3_i) % 12
                    l3_sign     = ZODIAC[l3_sign_idx]
                    l3_full     = l2_full * (self.ZR_PERIODS[l3_sign] / TOTAL_CYCLE)
                    l3_actual   = min(l3_full, l3_remaining)
                    l3_end      = l3_time + timedelta(days=l3_actual * 365.2425)

                    l3_periods.append({
                        "sign":       l3_sign,
                        "start_date": l3_time.isoformat(),
                        "end_date":   l3_end.isoformat(),
                        "years":      round(l3_actual, 4),
                        "level":      "L3",
                        "is_lob":     l3_sign_idx == lob_idx,
                    })
                    l3_time      = l3_end
                    l3_remaining -= l3_actual
                    l3_i += 1

                l2_periods.append({
                    "sign":            l2_sign,
                    "start_date":      l2_time.isoformat(),
                    "end_date":        l2_end.isoformat(),
                    "years":           round(l2_actual, 4),
                    "level":           "L2",
                    "is_loosing_of_bond": is_lob_l2,
                    "sub_periods_L3":  l3_periods,
                })
                l2_time      = l2_end
                l2_remaining -= l2_actual
                l2_i += 1

            l1_periods.append({
                "sign":            l1_sign,
                "start_date":      current_time.isoformat(),
                "end_date":        l1_end.isoformat(),
                "years":           round(l1_actual, 4),
                "level":           "L1",
                "is_loosing_of_bond": is_lob_l1,
                "sub_periods_L2":  l2_periods,
            })

            current_time  = l1_end
            remaining_yrs -= l1_actual
            l1_i += 1

        return l1_periods

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

    def _compute_bonifications(self, jd: float, is_day: bool) -> Dict[str, Any]:
        """
        Compute bonifications and maltreatments for 7 classical planets.

        Bonification  — a benefic (Jupiter or Venus) applies a Ptolemaic aspect
                        within 3° to the target planet.
        Maltreatment  — an out-of-sect malefic applies a Ptolemaic aspect within 3°.

        Sect membership (Paulus Alexandrinus):
          Day chart:   Sun, Jupiter, Saturn = diurnal (in sect)
                       Moon, Venus, Mars   = nocturnal (out of sect)
          Night chart: Moon, Venus, Mars   = nocturnal (in sect)
                       Sun, Jupiter, Saturn= diurnal (out of sect)

        Out-of-sect malefic = the malefic that is NOT in sect for this chart:
          Day   → Mars is the out-of-sect malefic (nocturnal malefic by day)
          Night → Saturn is the out-of-sect malefic (diurnal malefic by night)
        """
        PLANET_CODES = {
            "Sun": swe.SUN, "Moon": swe.MOON, "Mercury": swe.MERCURY,
            "Venus": swe.VENUS, "Mars": swe.MARS,
            "Jupiter": swe.JUPITER, "Saturn": swe.SATURN,
        }
        SECT_DAY   = {"in_sect":  {"Sun", "Jupiter", "Saturn"},
                       "out_sect": {"Moon", "Venus", "Mars"}}
        SECT_NIGHT = {"in_sect":  {"Moon", "Venus", "Mars"},
                       "out_sect": {"Sun", "Jupiter", "Saturn"}}
        sect = SECT_DAY if is_day else SECT_NIGHT

        # Planets that can bonify (always benefics regardless of sect)
        BENEFICS  = {"Jupiter", "Venus"}
        # Out-of-sect malefic (the one whose harm is hardest to moderate)
        OOS_MALEFIC = "Mars" if is_day else "Saturn"
        # Both malefics can maltreat, but out-of-sect is weighted higher
        ALL_MALEFICS = {"Mars", "Saturn"}

        ASPECT_ANGLES = [0.0, 60.0, 90.0, 120.0, 180.0]
        ORB = 3.0  # degrees

        # Get tropical longitudes
        lons: Dict[str, float] = {}
        for name, code in PLANET_CODES.items():
            pos = _swe_pos(swe.calc_ut(jd, code))
            lons[name] = float(pos[0]) % 360.0

        def _orb(lon_a: float, lon_b: float, angle: float) -> float:
            diff = abs(lon_a - lon_b) % 360.0
            if diff > 180.0:
                diff = 360.0 - diff
            return abs(diff - angle)

        def _is_applying(actor: str, target: str, angle: float) -> bool:
            """True if actor is moving toward target aspect (decreasing orb)."""
            step = 0.5 / 24.0  # 30-min step
            jd1 = jd + step
            pos_a1 = _swe_pos(swe.calc_ut(jd1, PLANET_CODES[actor]))
            lon_a1 = float(pos_a1[0]) % 360.0
            return _orb(lon_a1, lons[target], angle) < _orb(lons[actor], lons[target], angle)

        result: Dict[str, Any] = {}

        for target in PLANET_CODES:
            bonified    = False
            maltreated  = False
            bon_by:     list = []
            malt_by:    list = []
            sect_match  = target in sect["in_sect"]

            for actor, actor_lon in lons.items():
                if actor == target:
                    continue
                for ang in ASPECT_ANGLES:
                    o = _orb(actor_lon, lons[target], ang)
                    if o <= ORB and _is_applying(actor, target, ang):
                        if actor in BENEFICS:
                            bonified = True
                            bon_by.append(f"{actor} ({ang:.0f}°, orb {o:.2f}°)")
                        elif actor in ALL_MALEFICS:
                            maltreated = True
                            severity = "OUT_OF_SECT" if actor == OOS_MALEFIC else "in_sect"
                            malt_by.append(f"{actor} ({ang:.0f}°, orb {o:.2f}°, {severity})")

            result[target] = {
                "sect_match":       sect_match,
                "bonification":     bonified,
                "maltreatment":     maltreated,
                "bonified_by":      bon_by,
                "maltreated_by":    malt_by,
                "in_sect_group":    "diurnal" if target in {"Sun","Jupiter","Saturn"} else "nocturnal",
            }

        return result

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
