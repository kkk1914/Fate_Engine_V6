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

        # Firdaria (75-year Persian time-lord system)
        current_age = max(0, now.year - birth_year)
        firdaria = self._calculate_firdaria(jd, is_day, current_age, now)

        # Alcocoden (planet that "gives years" — dispositor of the Hyleg)
        alcocoden = self._calculate_alcocoden(jd, asc_lon, sun_lon, moon_lon, is_day, hyleg)

        # Sect analysis (day/night chart planet classification)
        sect = self._compute_sect(jd, is_day, asc_lon)

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
            "alcocoden": alcocoden,
            "firdaria": firdaria,
            "predominator": self._find_predominator(asc_lon, sun_lon, moon_lon, is_day),
            "bonifications": bonifications,
            "dodecatemoria": dodecatemoria,
            "sect": sect,
        }

    def _is_day_chart(self, asc: float, sun: float) -> bool:
        """Determine if day or night chart.

        Sun above horizon = Sun is 0-180° ahead of Ascendant in zodiac order.
        """
        diff = (sun - asc) % 360
        return 0 < diff < 180

    def _compute_sect(self, jd: float, is_day: bool, asc_lon: float) -> Dict[str, Any]:
        """Compute Hellenistic Sect analysis.

        Sect is THE foundational concept of Hellenistic astrology that
        determines which planets are most benefic/malefic for this chart.

        Day chart:
          - Sect light: Sun  |  Sect benefic: Jupiter  |  Sect malefic: Saturn
          - Out-of-sect light: Moon  |  Out-of-sect benefic: Venus  |  Malefic: Mars

        Night chart:
          - Sect light: Moon  |  Sect benefic: Venus  |  Sect malefic: Mars
          - Out-of-sect light: Sun  |  Out-of-sect benefic: Jupiter  |  Malefic: Saturn

        Planets also get a bonus/penalty for being in a sign of their sect
        (above/below horizon matching their day/night nature).

        A planet IN SECT and in a sign of its sect = most benefic possible.
        A planet CONTRARY TO SECT and in the wrong hemisphere = most malefic.
        """
        # Get planet positions
        planets = {}
        planet_codes = {
            "Sun": swe.SUN, "Moon": swe.MOON, "Mercury": swe.MERCURY,
            "Venus": swe.VENUS, "Mars": swe.MARS, "Jupiter": swe.JUPITER,
            "Saturn": swe.SATURN,
        }

        for name, code in planet_codes.items():
            lon = float(_swe_pos(swe.calc_ut(jd, code))[0])
            # Above horizon = 0-180° ahead of Asc
            above_horizon = 0 < ((lon - asc_lon) % 360) < 180
            planets[name] = {"longitude": lon, "above_horizon": above_horizon}

        # Sect assignment
        if is_day:
            sect_light = "Sun"
            sect_benefic = "Jupiter"
            sect_malefic = "Saturn"
            contrary_light = "Moon"
            contrary_benefic = "Venus"
            contrary_malefic = "Mars"
        else:
            sect_light = "Moon"
            sect_benefic = "Venus"
            sect_malefic = "Mars"
            contrary_light = "Sun"
            contrary_benefic = "Jupiter"
            contrary_malefic = "Saturn"

        # Mercury's sect depends on whether it rises before or after the Sun
        merc_lon = planets["Mercury"]["longitude"]
        sun_lon_val = planets["Sun"]["longitude"]
        merc_morning = ((sun_lon_val - merc_lon) % 360) < 180
        mercury_sect = "day" if merc_morning else "night"

        # Score each planet's sect condition (-2 to +2)
        # +2 = in sect + correct hemisphere (most benefic expression)
        # +1 = in sect but wrong hemisphere
        # -1 = contrary to sect but right hemisphere
        # -2 = contrary to sect + wrong hemisphere (most malefic expression)
        planet_sect = {}
        day_planets = {"Sun", "Jupiter", "Saturn"}
        night_planets = {"Moon", "Venus", "Mars"}

        for name, data in planets.items():
            if name == "Mercury":
                in_sect = (mercury_sect == "day" and is_day) or (
                    mercury_sect == "night" and not is_day)
            elif name in day_planets:
                in_sect = is_day
            else:
                in_sect = not is_day

            # Hemisphere check: day planets prefer above horizon,
            # night planets prefer below
            if name in day_planets:
                correct_hemisphere = data["above_horizon"]
            elif name in night_planets:
                correct_hemisphere = not data["above_horizon"]
            else:
                correct_hemisphere = in_sect  # Mercury follows its sect

            if in_sect and correct_hemisphere:
                score = 2
                condition = "In Sect + Correct Hemisphere (strongest benefic)"
            elif in_sect and not correct_hemisphere:
                score = 1
                condition = "In Sect but wrong hemisphere"
            elif not in_sect and correct_hemisphere:
                score = -1
                condition = "Contrary to Sect but correct hemisphere"
            else:
                score = -2
                condition = "Contrary to Sect + wrong hemisphere (most malefic)"

            planet_sect[name] = {
                "in_sect": in_sect,
                "above_horizon": data["above_horizon"],
                "score": score,
                "condition": condition,
            }

        return {
            "is_day_chart": is_day,
            "sect_light": sect_light,
            "sect_benefic": sect_benefic,
            "sect_malefic": sect_malefic,
            "contrary_light": contrary_light,
            "contrary_benefic": contrary_benefic,
            "contrary_malefic": contrary_malefic,
            "mercury_sect": mercury_sect,
            "planets": planet_sect,
            "most_benefic": sect_benefic,
            "most_malefic": contrary_malefic,
            "summary": (
                f"{'Day' if is_day else 'Night'} chart — "
                f"{sect_benefic} is the most powerful benefic, "
                f"{contrary_malefic} is the most problematic malefic. "
                f"Sect light: {sect_light}."
            ),
        }

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

    def _calculate_firdaria(self, jd: float, is_day: bool,
                             current_age: int, now: datetime) -> Dict[str, Any]:
        """
        Calculate Firdaria time-lords for the native's life.

        Persian/Arabic 75-year system; each planet rules a major period
        whose sub-periods are divided among the 7 planets in turn.

        Day chart order:  Sun(10), Venus(8), Mercury(13), Moon(9),
                          Saturn(11), Jupiter(12), Mars(7), Rahu(3), Ketu(2) = 75 yrs
        Night chart order: Moon(9), Saturn(11), Mercury(13), Venus(8),
                           Sun(10), Mars(7), Jupiter(12), Ketu(2), Rahu(3) = 75 yrs
        """
        FIRDARIA_YEARS = {
            "Sun": 10, "Venus": 8, "Mercury": 13, "Moon": 9,
            "Saturn": 11, "Jupiter": 12, "Mars": 7, "Rahu": 3, "Ketu": 2
        }
        DAY_ORDER   = ["Sun",  "Venus",   "Mercury", "Moon",  "Saturn", "Jupiter", "Mars", "Rahu", "Ketu"]
        NIGHT_ORDER = ["Moon", "Saturn",  "Mercury", "Venus", "Sun",    "Mars", "Jupiter", "Ketu", "Rahu"]
        order = DAY_ORDER if is_day else NIGHT_ORDER

        # Retrieve birth datetime for exact start
        import swisseph as _swe
        year_f, month_f, day_f, hour_f = _swe.revjul(jd)
        birth_year = int(year_f)

        periods     = []
        current_age_yrs = current_age  # integer age at now

        # Build 75-year sequence starting from birth
        accum_yrs = 0.0
        for major_planet in order:
            major_dur = float(FIRDARIA_YEARS[major_planet])
            major_start_age = accum_yrs
            major_end_age   = accum_yrs + major_dur

            # Start datetime for this major period
            major_start_dt = datetime(birth_year, int(month_f), max(1, int(day_f)),
                                       tzinfo=timezone.utc) + timedelta(days=major_start_age * 365.25)
            major_end_dt   = major_start_dt + timedelta(days=major_dur * 365.25)

            periods.append({
                "planet":     major_planet,
                "level":      "major",
                "duration_years": major_dur,
                "start_date": major_start_dt.isoformat(),
                "end_date":   major_end_dt.isoformat(),
                "start_age":  round(major_start_age, 2),
                "end_age":    round(major_end_age, 2),
            })

            # Sub-periods: each sub-period length = major_dur * (sub_planet_yrs / 75)
            # Sub-period order starts with the same planet as major period, cycles through order
            major_idx = order.index(major_planet)
            sub_accum = 0.0
            for sub_i in range(len(order)):
                sub_planet = order[(major_idx + sub_i) % len(order)]
                sub_dur    = major_dur * (FIRDARIA_YEARS[sub_planet] / 75.0)
                sub_start_dt = major_start_dt + timedelta(days=sub_accum * 365.25)
                sub_end_dt   = sub_start_dt  + timedelta(days=sub_dur * 365.25)
                periods.append({
                    "planet":     sub_planet,
                    "level":      "sub",
                    "major":      major_planet,
                    "duration_years": round(sub_dur, 4),
                    "start_date": sub_start_dt.isoformat(),
                    "end_date":   sub_end_dt.isoformat(),
                    "start_age":  round(major_start_age + sub_accum, 2),
                    "end_age":    round(major_start_age + sub_accum + sub_dur, 2),
                })
                sub_accum += sub_dur

            accum_yrs += major_dur

        # Find active major and sub period
        active_major = {}
        active_sub   = {}
        for p in periods:
            if p["start_age"] <= current_age_yrs < p["end_age"]:
                if p["level"] == "major":
                    active_major = p
                elif p["level"] == "sub":
                    active_sub = p

        return {
            "is_day_chart": is_day,
            "order":        order,
            "active_major": active_major,
            "active_sub":   active_sub,
            "periods":      periods,
        }

    def _calculate_alcocoden(self, jd: float, asc: float, sun: float,
                              moon: float, is_day: bool,
                              hyleg: Optional[str]) -> Dict[str, Any]:
        """
        Calculate the Alcocoden — the planet that 'gives years' (determiner of vitality).

        Method (simplified Valens / Bonatti):
        1. Identify the Hyleg (already computed).
        2. Find the almuten of the Hyleg's degree — the planet with the most essential
           dignities at that precise degree (domicile=5, exaltation=4, triplicity=3,
           bound/term=2, face/decan=1).
        3. The Alcocoden's dignity-weighted position modifies the life-force contribution.

        Returns a dict with the Alcocoden planet name, its dignity at the Hyleg point,
        and the traditional 'years given' based on its chart placement quality.
        """
        # Dignity tables (tropical)
        DOMICILE = {
            "Aries": "Mars",  "Taurus": "Venus",  "Gemini": "Mercury",
            "Cancer": "Moon", "Leo": "Sun",        "Virgo": "Mercury",
            "Libra": "Venus", "Scorpio": "Mars",   "Sagittarius": "Jupiter",
            "Capricorn": "Saturn", "Aquarius": "Saturn", "Pisces": "Jupiter"
        }
        EXALTATION = {
            "Aries": "Sun",    "Taurus": "Moon",    "Cancer": "Jupiter",
            "Virgo": "Mercury","Libra":  "Saturn",   "Capricorn": "Mars",
            "Pisces": "Venus"
        }
        # Ptolemaic terms (bounds) — simplified by sign 0-30°
        TERMS = [
            # [planet, start_deg, end_deg]
            # Aries
            [["Jupiter",0,6],["Venus",6,12],["Mercury",12,20],["Mars",20,25],["Saturn",25,30]],
            # Taurus
            [["Venus",0,8],["Mercury",8,14],["Jupiter",14,22],["Saturn",22,27],["Mars",27,30]],
            # Gemini
            [["Mercury",0,6],["Jupiter",6,12],["Venus",12,17],["Mars",17,24],["Saturn",24,30]],
            # Cancer
            [["Mars",0,7],["Venus",7,13],["Mercury",13,19],["Jupiter",19,26],["Saturn",26,30]],
            # Leo
            [["Jupiter",0,6],["Venus",6,11],["Saturn",11,18],["Mercury",18,24],["Mars",24,30]],
            # Virgo
            [["Mercury",0,7],["Venus",7,13],["Jupiter",13,18],["Saturn",18,24],["Mars",24,30]],
            # Libra
            [["Saturn",0,6],["Mercury",6,14],["Jupiter",14,21],["Venus",21,28],["Mars",28,30]],
            # Scorpio
            [["Mars",0,7],["Venus",7,11],["Mercury",11,19],["Jupiter",19,24],["Saturn",24,30]],
            # Sagittarius
            [["Jupiter",0,8],["Venus",8,14],["Mercury",14,19],["Saturn",19,25],["Mars",25,30]],
            # Capricorn
            [["Mercury",0,6],["Jupiter",6,12],["Venus",12,19],["Saturn",19,25],["Mars",25,30]],
            # Aquarius
            [["Mercury",0,7],["Venus",7,13],["Jupiter",13,20],["Mars",20,25],["Saturn",25,30]],
            # Pisces
            [["Venus",0,8],["Jupiter",8,14],["Mercury",14,20],["Mars",20,26],["Saturn",26,30]],
        ]

        # Get Hyleg longitude
        if not hyleg:
            return {"planet": None, "reason": "No Hyleg found"}

        try:
            if hyleg == "Sun":
                hyleg_lon = float(clamp360(sun))
            elif hyleg == "Moon":
                hyleg_lon = float(clamp360(moon))
            else:  # Ascendant
                hyleg_lon = float(clamp360(asc))

            sign_idx   = int(hyleg_lon // 30)
            deg_in_sign = hyleg_lon % 30
            sign_name  = ZODIAC[sign_idx]

            # Score each planet by dignity at Hyleg degree
            planets = ["Sun", "Moon", "Mercury", "Venus", "Mars", "Jupiter", "Saturn"]
            scores: Dict[str, int] = {p: 0 for p in planets}

            # Domicile (+5)
            dom = DOMICILE.get(sign_name)
            if dom and dom in scores:
                scores[dom] += 5

            # Exaltation (+4)
            exalt = EXALTATION.get(sign_name)
            if exalt and exalt in scores:
                scores[exalt] += 4

            # Terms/Bounds (+2)
            sign_terms = TERMS[sign_idx]
            for term_planet, t_start, t_end in sign_terms:
                if t_start <= deg_in_sign < t_end and term_planet in scores:
                    scores[term_planet] += 2
                    break

            # Face/Decan (+1): each 10° is ruled by a planet in Chaldean order
            CHALDEAN = ["Mars", "Sun", "Venus", "Mercury", "Moon", "Saturn", "Jupiter"]
            decan_num = int(deg_in_sign // 10)
            face_ruler = CHALDEAN[(sign_idx * 3 + decan_num) % 7]
            if face_ruler in scores:
                scores[face_ruler] += 1

            # Alcocoden = planet with highest score; ties broken by Chaldean order
            alcocoden = max(scores, key=lambda p: (scores[p], -CHALDEAN.index(p) if p in CHALDEAN else 0))
            dignity_score = scores[alcocoden]

            # Traditional years given (Major/Minor/Middle) by placement quality
            # Simplified: DOMINANT/Exalted = major years, other = minor years
            MAJOR_YEARS = {"Sun":120,"Moon":108,"Mercury":76,"Venus":82,
                           "Mars":66,"Jupiter":79,"Saturn":57}
            MINOR_YEARS = {"Sun":19,"Moon":25,"Mercury":20,"Venus":8,
                           "Mars":15,"Jupiter":12,"Saturn":30}
            years_given = MAJOR_YEARS.get(alcocoden, 60) if dignity_score >= 5 else MINOR_YEARS.get(alcocoden, 15)

            return {
                "planet":        alcocoden,
                "hyleg":         hyleg,
                "hyleg_sign":    sign_name,
                "hyleg_degree":  round(deg_in_sign, 2),
                "dignity_score": dignity_score,
                "years_given":   years_given,
                "scores":        {k: v for k, v in scores.items() if v > 0},
            }
        except Exception as e:
            return {"planet": None, "reason": str(e)}

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
