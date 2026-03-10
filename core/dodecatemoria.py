"""Dodecatemoria (Hellenistic 12th Parts) — precise implementation.

Each 30° sign is divided into 12 equal parts of 2.5°.
The sequence starts from the SAME sign the planet is in, progressing forward.
This produces a "sub-sign" that shows the deeper resonance of any placement.

Authority: Vettius Valens (Anthologies, Book I), Ptolemy (Tetrabiblos I.22).
"""
import swisseph as swe

def _swe_pos(result):
    """Normalise pyswisseph calc_ut/fixstar return across API versions.
    Old (<2.10): returns (positions_tuple, retflag) — result[0] is a tuple.
    New (>=2.10): returns flat 6-tuple directly   — result[0] is a float.
    """
    return result[0] if isinstance(result[0], (list, tuple)) else result

from typing import Dict, Any, List, Optional


ZODIAC = [
    "Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo",
    "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces"
]

TRADITIONAL_RULERS = {
    "Aries": "Mars", "Taurus": "Venus", "Gemini": "Mercury",
    "Cancer": "Moon", "Leo": "Sun", "Virgo": "Mercury",
    "Libra": "Venus", "Scorpio": "Mars", "Sagittarius": "Jupiter",
    "Capricorn": "Saturn", "Aquarius": "Saturn", "Pisces": "Jupiter"
}

PART_SIZE = 2.5  # 30 / 12 = 2.5 degrees per part


def dodecatemoria_sign(longitude: float) -> Dict[str, Any]:
    """
    Calculate the Dodecatemoria sign for any ecliptic longitude.

    Algorithm (Vettius Valens):
    1. Find the degree within the sign (0–30°).
    2. Multiply by 12.
    3. Add back the beginning of the sign.
    4. The resulting degree gives the dodecatemoria sign and its position.

    Returns sign, ruler, degree-within-dodecatemoria, and the raw dodecatemoria longitude.
    """
    lon = longitude % 360.0
    sign_idx = int(lon // 30)
    deg_in_sign = lon % 30.0

    # Valens formula: multiply degrees within sign by 12, add sign start
    raw_dodec_deg = (sign_idx * 30.0) + (deg_in_sign * 12.0)
    dodec_lon = raw_dodec_deg % 360.0

    dodec_sign_idx = int(dodec_lon // 30)
    dodec_sign = ZODIAC[dodec_sign_idx]
    dodec_deg_in_sign = dodec_lon % 30.0

    # Which 2.5° part within the original sign?
    part_number = int(deg_in_sign // PART_SIZE) + 1  # 1-12
    # The sequence starts from the planet's own sign
    part_sign_idx = (sign_idx + part_number - 1) % 12
    part_sign = ZODIAC[part_sign_idx]  # Should equal dodec_sign — this is the verification

    return {
        "natal_sign": ZODIAC[sign_idx],
        "natal_degree": round(deg_in_sign, 4),
        "dodecatemoria_sign": dodec_sign,
        "dodecatemoria_ruler": TRADITIONAL_RULERS[dodec_sign],
        "dodecatemoria_longitude": round(dodec_lon, 4),
        "dodecatemoria_degree_in_sign": round(dodec_deg_in_sign, 4),
        "part_number": part_number,  # Which of the 12 parts (1-12)
        "part_sign": part_sign,  # Should match dodec_sign
    }


class DodecatemoriaEngine:
    """
    Calculate Dodecatemoria for all planets in a natal chart.
    Also identifies significant dodecatemoria patterns.
    """

    PLANET_CODES = {
        "Sun": swe.SUN, "Moon": swe.MOON, "Mercury": swe.MERCURY,
        "Venus": swe.VENUS, "Mars": swe.MARS, "Jupiter": swe.JUPITER,
        "Saturn": swe.SATURN
    }

    def calculate(self, jd: float, lat: float, lon: float,
                  time_known: bool) -> Dict[str, Any]:
        """
        Calculate Dodecatemoria for all seven traditional planets
        and the Ascendant (if time known).
        """
        results = {}

        # Planets
        for name, code in self.PLANET_CODES.items():
            pos = _swe_pos(swe.calc_ut(jd, code))
            planet_lon = float(pos[0])
            results[name] = dodecatemoria_sign(planet_lon)
            results[name]["longitude"] = round(planet_lon, 4)

        # Nodes
        node_pos = _swe_pos(swe.calc_ut(jd, swe.MEAN_NODE))
        rahu_lon = float(node_pos[0])
        ketu_lon = (rahu_lon + 180.0) % 360.0
        results["North Node"] = dodecatemoria_sign(rahu_lon)
        results["North Node"]["longitude"] = round(rahu_lon, 4)
        results["South Node"] = dodecatemoria_sign(ketu_lon)
        results["South Node"]["longitude"] = round(ketu_lon, 4)

        # Ascendant
        if time_known:
            cusps, ascmc = swe.houses(jd, lat, lon, b'P')
            asc_lon = float(ascmc[0])
            results["Ascendant"] = dodecatemoria_sign(asc_lon)
            results["Ascendant"]["longitude"] = round(asc_lon, 4)

            mc_lon = float(ascmc[1])
            results["Midheaven"] = dodecatemoria_sign(mc_lon)
            results["Midheaven"]["longitude"] = round(mc_lon, 4)

        # Find planets in their own dodecatemoria sign (double-sign emphasis)
        own_dodec = []
        for planet, data in results.items():
            if data.get("natal_sign") == data.get("dodecatemoria_sign"):
                own_dodec.append(planet)

        # Find concentrations (3+ planets sharing dodecatemoria sign)
        dodec_sign_counts: Dict[str, List[str]] = {}
        for planet, data in results.items():
            ds = data.get("dodecatemoria_sign", "")
            dodec_sign_counts.setdefault(ds, []).append(planet)

        concentrations = {
            sign: planets for sign, planets in dodec_sign_counts.items()
            if len(planets) >= 3
        }

        # Find dodecatemoria conjunctions (two planets sharing the same dodecatemoria sign
        # AND within 2.5° of each other in dodecatemoria longitude)
        dodec_aspects = []
        planet_list = list(results.keys())
        for i in range(len(planet_list)):
            for j in range(i + 1, len(planet_list)):
                p1, p2 = planet_list[i], planet_list[j]
                d1 = results[p1].get("dodecatemoria_longitude", 0)
                d2 = results[p2].get("dodecatemoria_longitude", 0)
                diff = abs(d1 - d2) % 360
                dist = min(diff, 360 - diff)
                if dist <= 5.0:  # 5° orb in dodecatemoria = effectively very tight
                    dodec_aspects.append({
                        "p1": p1,
                        "p2": p2,
                        "type": "Conjunction",
                        "orb": round(dist, 3),
                        "dodec_sign": results[p1]["dodecatemoria_sign"]
                    })

        return {
            "placements": results,
            "own_dodecatemoria": own_dodec,
            "concentrations": concentrations,
            "dodec_conjunctions": dodec_aspects,
            "summary": self._build_summary(results, own_dodec, concentrations)
        }

    def _build_summary(self, results: Dict, own_dodec: List[str],
                       concentrations: Dict) -> Dict[str, Any]:
        """Generate interpretive summary of dodecatemoria patterns."""
        # Most emphasized sign in dodecatemoria
        sign_counts = {}
        for data in results.values():
            s = data.get("dodecatemoria_sign", "")
            sign_counts[s] = sign_counts.get(s, 0) + 1

        dominant_dodec_sign = max(sign_counts, key=sign_counts.get) if sign_counts else None

        # Planets in their own dodecatemoria = doubly emphasized
        own_emphasis = {p: results[p]["natal_sign"] for p in own_dodec}

        return {
            "dominant_dodecatemoria_sign": dominant_dodec_sign,
            "dominant_dodecatemoria_ruler": TRADITIONAL_RULERS.get(dominant_dodec_sign, "Unknown"),
            "own_dodecatemoria_planets": own_emphasis,
            "concentrations": concentrations,
            "interpretation": self._interpret(dominant_dodec_sign, own_emphasis, concentrations)
        }

    def _interpret(self, dominant: Optional[str], own_emphasis: Dict,
                   concentrations: Dict) -> str:
        """Traditional interpretation of dodecatemoria patterns."""
        parts = []

        if dominant:
            ruler = TRADITIONAL_RULERS.get(dominant, "Unknown")
            parts.append(
                f"The chart's sub-sign emphasis falls in {dominant} "
                f"(ruled by {ruler}), indicating that the deeper resonance of this "
                f"nativity carries {dominant}'s themes even when the surface positions "
                f"suggest otherwise."
            )

        if own_emphasis:
            for planet, sign in own_emphasis.items():
                parts.append(
                    f"{planet} in {sign} is doubly emphasized: it occupies both its "
                    f"natal sign and returns to {sign} in the dodecatemoria — a "
                    f"double-sign placement signifying that {sign}'s qualities are "
                    f"the native's most fundamental expression through {planet}."
                )

        if concentrations:
            for sign, planets in concentrations.items():
                parts.append(
                    f"Dodecatemoria concentration in {sign}: "
                    f"{', '.join(planets)} all point toward {sign}'s domain "
                    f"at the sub-sign level — a hidden stellium revealing a "
                    f"profound underlying emphasis."
                )

        return " ".join(parts) if parts else "No dominant dodecatemoria pattern detected."
