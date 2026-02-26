"""Western Tropical Astrology Engine."""
import math
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Tuple, Optional

import swisseph as swe

from core.ephemeris import ephe
from core.primary_directions import PrimaryDirections
from core.solar_return import SolarReturnEngine
from core.lunar_return import LunarReturnEngine
from core.syzygy import SyzygyEngine
from core.essential_dignities import EssentialDignities

# Constants
ZODIAC = ["Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo",
          "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces"]

PLANETS = {
    "Sun": swe.SUN, "Moon": swe.MOON, "Mercury": swe.MERCURY,
    "Venus": swe.VENUS, "Mars": swe.MARS, "Jupiter": swe.JUPITER,
    "Saturn": swe.SATURN, "Uranus": swe.URANUS, "Neptune": swe.NEPTUNE,
    "Pluto": swe.PLUTO
}

ASPECTS = [(0, "Conjunction"), (60, "Sextile"), (90, "Square"),
           (120, "Trine"), (180, "Opposition")]
OOB_LIMIT = 23.4392911

def clamp360(x: float) -> float:
    return x % 360.0

def midpoint(d1: float, d2: float) -> float:
    a, b = clamp360(d1), clamp360(d2)
    diff = abs(a - b)
    if diff > 180:
        return clamp360((a + b + 360) / 2)
    return clamp360((a + b) / 2)

class WesternEngine:
    """Tropical astrology with predictive techniques."""

    def __init__(self):
        self.dignity_engine = EssentialDignities()

    def calculate(self, jd: float, lat: float, lon: float,
                  time_known: bool, birth_year: int) -> Dict[str, Any]:
        """Calculate complete Western chart."""
        natal = self._calc_natal(jd, lat, lon, time_known)
        predictive = self._calc_predictive(jd, birth_year, natal, time_known)

        # Primary Directions (5-year)
        pd_engine = PrimaryDirections(jd, lat, lon)
        primary_dirs = pd_engine.get_critical_directions(years_ahead=5)

        # Solar Returns (5-year)
        sr_engine = SolarReturnEngine(jd, lat, lon)
        current_year = datetime.now().year
        solar_returns = sr_engine.get_return_series(current_year, years=5)

        # Analyze each return
        sr_analysis = [sr_engine.analyze_return_vs_natal(sr) for sr in solar_returns]

        predictive["primary_directions"] = primary_dirs
        predictive["solar_returns"] = solar_returns
        predictive["solar_return_analysis"] = sr_analysis

        # Phase 4: Void of Course Moon (next 30 days)
        try:
            from core.void_of_course import VoidOfCourseMoon
            voc_engine = VoidOfCourseMoon()
            now_jd = ephe.julian_day(datetime.now(timezone.utc))
            predictive["voc_current"] = voc_engine.is_void_at(now_jd)
            predictive["voc_periods_30d"] = voc_engine.get_voc_periods(now_jd, days_ahead=30)
        except Exception as e:
            predictive["voc_current"] = {"error": str(e)}
            predictive["voc_periods_30d"] = []

        return {"natal": natal, "predictive": predictive}

    def _calc_natal(self, jd: float, lat: float, lon: float,
                    time_known: bool) -> Dict[str, Any]:
        """Calculate natal positions."""
        placements = {}

        # Planet positions
        for name, code in PLANETS.items():
            lon_val, lat_val = ephe.planet_longitude(jd, code)
            dec = self._calc_declination(jd, code)

            placements[name] = {
                "longitude": lon_val,
                "sign": ZODIAC[int(clamp360(lon_val) // 30)],
                "degree": clamp360(lon_val) % 30,
                "latitude": lat_val,
                "declination": dec,
                "out_of_bounds": abs(dec) > OOB_LIMIT,
                "retrograde": ephe.is_retrograde(jd, code)
            }

        # Houses & Angles
        houses, angles = {}, {}
        if time_known:
            cusps, ascmc = ephe.houses(jd, lat, lon, b'P')  # Placidus default
            asc = float(ascmc[0])
            mc = float(ascmc[1])

            angles = {
                "Ascendant": {
                    "longitude": asc,
                    "sign": ZODIAC[int(clamp360(asc) // 30)],
                    "degree": clamp360(asc) % 30
                },
                "Midheaven": {
                    "longitude": mc,
                    "sign": ZODIAC[int(clamp360(mc) // 30)],
                    "degree": clamp360(mc) % 30
                }
            }

            for i in range(12):
                c = float(cusps[i])
                houses[f"House_{i+1}"] = {
                    "longitude": c,
                    "sign": ZODIAC[int(clamp360(c) // 30)],
                    "degree": clamp360(c) % 30
                }

        # Add North/South Nodes
        from swisseph import MEAN_NODE
        node_pos, _ = swe.calc_ut(jd, MEAN_NODE)
        placements["North Node"] = {
            "longitude": node_pos[0],
            "sign": ZODIAC[int(clamp360(node_pos[0]) // 30)],
            "degree": clamp360(node_pos[0]) % 30,
            "latitude": 0.0,
            "declination": 0.0,
            "out_of_bounds": False,
            "retrograde": True  # Nodes are always retrograde
        }
        placements["South Node"] = {
            "longitude": clamp360(node_pos[0] + 180),
            "sign": ZODIAC[int(clamp360(node_pos[0] + 180) // 30)],
            "degree": clamp360(node_pos[0] + 180) % 30,
            "latitude": 0.0,
            "declination": 0.0,
            "out_of_bounds": False,
            "retrograde": True
        }

        # Add Descendant (opposite Ascendant)
        if "Ascendant" in angles:
            desc_lon = clamp360(angles["Ascendant"]["longitude"] + 180)
            angles["Descendant"] = {
                "longitude": desc_lon,
                "sign": ZODIAC[int(desc_lon // 30)],
                "deg_in_sign": desc_lon % 30
            }

        # Aspects
        aspects = self._calc_aspects(placements)

        # Lots (Fortune & Spirit)
        lots = {}
        if time_known and "Ascendant" in angles:
            lots = self._calc_lots(
                angles["Ascendant"]["longitude"],
                placements["Sun"]["longitude"],
                placements["Moon"]["longitude"]
            )

        # Fixed Stars (Royal)
        fixed_stars = self._calc_fixed_stars(jd, placements)

        # Phase 4: Geometric Pattern Detection
        try:
            from core.pattern_detection import PatternDetector
            detector = PatternDetector()
            patterns = detector.detect_all(placements, angles)
        except Exception as e:
            patterns = {"error": str(e), "summary": {}}

        return {
            "placements": placements,
            "houses": houses,
            "angles": angles,
            "aspects": aspects,
            "lots": lots,
            "fixed_stars": fixed_stars,
            "patterns": patterns
        }

    def _calc_declination(self, jd: float, planet: int) -> float:
        """Calculate declination."""
        pos_equ, _ = swe.calc_ut(jd, planet, swe.FLG_EQUATORIAL)
        return float(pos_equ[1])

    def _calc_aspects(self, placements: Dict) -> List[Dict]:
        """Calculate Ptolemaic aspects with 8° orb."""
        aspects = []
        names = list(placements.keys())

        for i in range(len(names)):
            for j in range(i+1, len(names)):
                p1, p2 = names[i], names[j]
                lon1 = placements[p1]["longitude"]
                lon2 = placements[p2]["longitude"]

                diff = abs(clamp360(lon1) - clamp360(lon2))
                dist = min(diff, 360 - diff)

                for angle, name in ASPECTS:
                    if abs(dist - angle) <= 8.0:
                        aspects.append({
                            "p1": p1,
                            "p2": p2,
                            "type": name,
                            "orb": round(abs(dist - angle), 2),
                            "degrees": round(dist, 2)
                        })
        return aspects

    def _calc_lots(self, asc: float, sun: float, moon: float) -> Dict[str, Any]:
        """Calculate Arabic Parts (Lots of Fortune and Spirit).

        Day chart: Sun is 0-180° ahead of Ascendant in zodiac order (above horizon).
        This matches the Hellenistic engine formula exactly.
        Day formula:   Fortune = Asc + Moon - Sun
        Night formula: Fortune = Asc + Sun - Moon
        Spirit is always the reverse of Fortune.
        """
        diff = (sun - asc) % 360
        is_day = 0.0 < diff < 180.0

        if is_day:
            fortune = clamp360(asc + moon - sun)
            spirit = clamp360(asc + sun - moon)
        else:
            fortune = clamp360(asc + sun - moon)
            spirit = clamp360(asc + moon - sun)

        return {
            "Lot_of_Fortune": {
                "longitude": fortune,
                "sign": ZODIAC[int(clamp360(fortune) // 30)],
                "degree": clamp360(fortune) % 30
            },
            "Lot_of_Spirit": {
                "longitude": spirit,
                "sign": ZODIAC[int(clamp360(spirit) // 30)],
                "degree": clamp360(spirit) % 30
            }
        }

    def _calc_fixed_stars(self, jd: float, placements: Dict) -> List[Dict]:
        """Check conjunctions to Royal Fixed Stars."""
        royal_stars = ["Regulus", "Spica", "Aldebaran", "Antares", "Fomalhaut"]
        hits = []

        for star in royal_stars:
            s_lon = ephe.fixstar(star, jd)
            if s_lon is None:
                continue

            for pname, pdata in placements.items():
                lon = pdata["longitude"]
                diff = abs(clamp360(lon) - clamp360(s_lon))
                dist = min(diff, 360 - diff)

                if dist <= 1.0:  # 1 degree orb
                    hits.append({
                        "planet": pname,
                        "star": star,
                        "orb": round(dist, 3)
                    })
        return hits

    def _calc_predictive(self, jd: float, birth_year: int,
                         natal: Dict, time_known: bool) -> Dict[str, Any]:
        """Calculate predictive elements (5-year timeline)."""
        now = datetime.now(timezone.utc)
        current_age = max(0, now.year - birth_year)

        # ── Secondary Progressions ────────────────────────────────────────────
        prog_jd = jd + current_age  # 1 day = 1 year
        progressions = {}

        for name, code in [("Sun", swe.SUN), ("Moon", swe.MOON)]:
            lon, _ = ephe.planet_longitude(prog_jd, code)
            progressions[f"Progressed_{name}"] = {
                "longitude": lon,
                "sign": ZODIAC[int(clamp360(lon) // 30)],
                "degree": clamp360(lon) % 30
            }

        # ── Solar Arc ─────────────────────────────────────────────────────────
        solar_arc = 0
        if "Sun" in natal["placements"]:
            natal_sun = natal["placements"]["Sun"]["longitude"]
            prog_sun = progressions["Progressed_Sun"]["longitude"]
            solar_arc = clamp360(prog_sun - natal_sun)

        # ── Solar Arc Directions ──────────────────────────────────────────────
        directed = {}
        if solar_arc > 0:
            for key in ["Sun", "Moon", "Mercury", "Venus", "Mars", "Ascendant"]:
                if key in natal["placements"] or key in natal.get("angles", {}):
                    base = natal["placements"].get(key, natal["angles"].get(key, {}))
                    if base and "longitude" in base:
                        dlon = clamp360(base["longitude"] + solar_arc)
                        directed[key] = {
                            "longitude": dlon,
                            "sign": ZODIAC[int(clamp360(dlon) // 30)],
                            "degree": clamp360(dlon) % 30
                        }

        # ── Annual Profections (5-year) ───────────────────────────────────────
        profections = []
        rulers = {
            "Aries": "Mars", "Taurus": "Venus", "Gemini": "Mercury",
            "Cancer": "Moon", "Leo": "Sun", "Virgo": "Mercury",
            "Libra": "Venus", "Scorpio": "Mars", "Sagittarius": "Jupiter",
            "Capricorn": "Saturn", "Aquarius": "Saturn", "Pisces": "Jupiter"
        }

        asc_sign_idx = 0
        if time_known and "Ascendant" in natal.get("angles", {}):
            asc_sign = natal["angles"]["Ascendant"]["sign"]
            if asc_sign in ZODIAC:
                asc_sign_idx = ZODIAC.index(asc_sign)

        for offset in range(5):
            year = now.year + offset
            age = current_age + offset
            prof_idx = (asc_sign_idx + age) % 12
            prof_sign = ZODIAC[prof_idx]
            profections.append({
                "year": year,
                "age": age,
                "profected_sign": prof_sign,
                "time_lord": rulers[prof_sign],
                "activated_house": (age % 12) + 1
            })

        # ── Year-level transit snapshots (retained for Kakshya compatibility) ─
        transits = []
        for offset in range(5):
            target_year = now.year + offset
            target_dt = datetime(target_year, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
            target_jd = ephe.julian_day(target_dt)

            yearly_transits = {}
            for name in ["Jupiter", "Saturn", "Uranus", "Neptune", "Pluto"]:
                lon, _ = ephe.planet_longitude(target_jd, PLANETS[name])
                yearly_transits[name] = {
                    "sign": ZODIAC[int(clamp360(lon) // 30)],
                    "degree": round(clamp360(lon) % 30, 2),
                    "longitude": round(lon, 4)
                }
            transits.append({"year": target_year, "positions": yearly_transits})

        # ── Exact Outer Transit Aspect Hit Windows (daily scan, 5-year) ───────
        # This produces entry/exact/exit dates for every major aspect
        # between transiting outer planets and natal points.
        # Falls back gracefully if the engine is not yet installed.
        outer_transit_data = {}
        try:
            from core.outer_transit_aspects import build_outer_transits_for_archon

            # Collect natal ecliptic longitudes (tropical)
            natal_lons = {
                name: data["longitude"]
                for name, data in natal.get("placements", {}).items()
                if "longitude" in data
                   and name in ["Sun", "Moon", "Mercury", "Venus", "Mars",
                                "Jupiter", "Saturn"]
            }
            angles = natal.get("angles", {})
            if "Ascendant" in angles and "longitude" in angles["Ascendant"]:
                natal_lons["Ascendant"] = angles["Ascendant"]["longitude"]
            if "Midheaven" in angles and "longitude" in angles["Midheaven"]:
                natal_lons["MC"] = angles["Midheaven"]["longitude"]

            if natal_lons:
                outer_transit_data = build_outer_transits_for_archon(jd, natal_lons, years_ahead=5)
        except ImportError:
            # Engine not yet installed — silent fallback, Archon uses year snapshots
            outer_transit_data = {"hits": [], "summary_block": "", "note": "outer_transit_aspects not installed"}
        except Exception as e:
            outer_transit_data = {"error": str(e), "hits": [], "summary_block": ""}

        return {
            "current_age": current_age,
            "progressions": progressions,
            "solar_arc_degrees": round(solar_arc, 2),
            "directed_positions": directed,
            "profections_timeline": profections,
            "transits_timeline": transits,
            "outer_transit_aspects": outer_transit_data  # exact entry/exact/exit dates
        }

    def calculate_lunar_returns(self, natal_jd: float, natal_moon_lon: float, years: int = 1) -> List[Dict]:
        """Calculate lunar returns for monthly precision."""
        from core.lunar_return import LunarReturnEngine
        engine = LunarReturnEngine(natal_jd, natal_moon_lon)
        return engine.get_return_series(datetime.now().year, months=12 * years)

    def calculate_syzygy(self, natal_jd: float) -> Dict[str, Any]:
        """Calculate pre-natal syzygy."""
        from core.syzygy import SyzygyEngine
        engine = SyzygyEngine(natal_jd)
        return engine.calculate_syzygy()

    def calculate_dignities(self, placements: Dict[str, Any], is_day: bool = True) -> Dict[str, Any]:
        """Calculate essential dignities for all planets."""
        from core.essential_dignities import EssentialDignities
        dignity_engine = EssentialDignities()

        positions = {p: (data['sign'], data['degree']) for p, data in placements.items() if
                     'sign' in data and 'degree' in data}

        dignities = {}
        for planet, (sign, deg) in positions.items():
            dignities[planet] = dignity_engine.calculate_dignity(
                planet, sign, deg, is_day
            ).__dict__

        # Find receptions
        receptions = dignity_engine.find_receptions(positions, is_day)
        almuten = dignity_engine.calculate_almuten(positions, is_day)

        return {
            'planet_dignities': dignities,
            'receptions': receptions,
            'almuten': almuten
        }

# Export for other modules
__all__ = ['WesternEngine', 'ZODIAC', 'clamp360']
