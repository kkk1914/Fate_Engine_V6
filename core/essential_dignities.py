"""Essential Dignities - Ptolemaic & Egyptian Systems."""
import swisseph as swe
from typing import Dict, Any, Tuple, Optional
from dataclasses import dataclass


@dataclass
class DignityScore:
    planet: str
    sign: str
    degree: float
    rulership: int = 0
    exaltation: int = 0
    triplicity: int = 0
    term: int = 0
    face: int = 0
    detriment: int = 0
    fall: int = 0
    total_score: int = 0
    reception_from: Optional[str] = None


class EssentialDignities:
    """Traditional essential dignity calculations."""

    # Traditional Rulerships (Hellenistic/Ptolemaic)
    RULERS = {
        "Aries": "Mars", "Taurus": "Venus", "Gemini": "Mercury",
        "Cancer": "Moon", "Leo": "Sun", "Virgo": "Mercury",
        "Libra": "Venus", "Scorpio": "Mars", "Sagittarius": "Jupiter",
        "Capricorn": "Saturn", "Aquarius": "Saturn", "Pisces": "Jupiter"
    }

    DETRIMENTS = {
        "Aries": "Venus", "Taurus": "Mars", "Gemini": "Jupiter",
        "Cancer": "Saturn", "Leo": "Saturn", "Virgo": "Jupiter",
        "Libra": "Mars", "Scorpio": "Venus", "Sagittarius": "Mercury",
        "Capricorn": "Moon", "Aquarius": "Sun", "Pisces": "Mercury"
    }

    # Exaltations with specific degrees
    EXALTATIONS = {
        "Sun": ("Aries", 19),
        "Moon": ("Taurus", 3),
        "Mercury": ("Virgo", 15),
        "Venus": ("Pisces", 27),
        "Mars": ("Capricorn", 28),
        "Jupiter": ("Cancer", 15),
        "Saturn": ("Libra", 21)
    }

    FALLS = {
        "Sun": "Libra", "Moon": "Scorpio", "Mercury": "Pisces",
        "Venus": "Virgo", "Mars": "Cancer", "Jupiter": "Capricorn",
        "Saturn": "Aries"
    }

    # Triplicity rulers (Day, Night, Participating)
    TRIPLICITIES = {
        "Fire": ("Sun", "Jupiter", "Saturn"),
        "Earth": ("Venus", "Moon", "Mars"),
        "Air": ("Saturn", "Mercury", "Jupiter"),
        "Water": ("Venus", "Mars", "Moon")
    }

    # Egyptian Terms (Ptolemaic alternative available if needed)
    EGYPTIAN_TERMS = {
        "Aries": [(0, 6, "Jupiter"), (6, 14, "Venus"), (14, 21, "Mercury"), (21, 26, "Mars"), (26, 30, "Saturn")],
        "Taurus": [(0, 8, "Venus"), (8, 15, "Mercury"), (15, 22, "Jupiter"), (22, 26, "Saturn"), (26, 30, "Mars")],
        "Gemini": [(0, 7, "Mercury"), (7, 14, "Jupiter"), (14, 21, "Venus"), (21, 25, "Saturn"), (25, 30, "Mars")],
        "Cancer": [(0, 6, "Mars"), (6, 13, "Jupiter"), (13, 20, "Mercury"), (20, 27, "Venus"), (27, 30, "Saturn")],
        "Leo": [(0, 6, "Jupiter"), (6, 11, "Venus"), (11, 18, "Saturn"), (18, 24, "Mercury"), (24, 30, "Mars")],
        "Virgo": [(0, 7, "Mercury"), (7, 14, "Venus"), (14, 18, "Jupiter"), (18, 24, "Saturn"), (24, 30, "Mars")],
        "Libra": [(0, 6, "Saturn"), (6, 14, "Mercury"), (14, 21, "Jupiter"), (21, 28, "Venus"), (28, 30, "Mars")],
        "Scorpio": [(0, 7, "Mars"), (7, 11, "Jupiter"), (11, 18, "Mercury"), (18, 24, "Venus"), (24, 30, "Saturn")],
        "Sagittarius": [(0, 6, "Jupiter"), (6, 12, "Venus"), (12, 17, "Mercury"), (17, 21, "Saturn"), (21, 26, "Mars"), (26, 30, "Saturn")],
        "Capricorn": [(0, 6, "Mercury"), (6, 12, "Jupiter"), (12, 19, "Venus"), (19, 25, "Saturn"), (25, 30, "Mars")],
        "Aquarius": [(0, 6, "Mercury"), (6, 12, "Venus"), (12, 20, "Jupiter"), (20, 25, "Mars"), (25, 30, "Saturn")],
        "Pisces": [(0, 8, "Venus"), (8, 14, "Jupiter"), (14, 20, "Mercury"), (20, 26, "Mars"), (26, 30, "Saturn")]
    }

    # Decan/Face rulers (Chaldean order starting from Mars at 0° Aries)
    FACES = {
        "Aries": ["Mars", "Sun", "Venus"], "Taurus": ["Mercury", "Moon", "Saturn"],
        "Gemini": ["Jupiter", "Mars", "Sun"], "Cancer": ["Venus", "Mercury", "Moon"],
        "Leo": ["Saturn", "Jupiter", "Mars"], "Virgo": ["Sun", "Venus", "Mercury"],
        "Libra": ["Moon", "Saturn", "Jupiter"], "Scorpio": ["Mars", "Sun", "Venus"],
        "Sagittarius": ["Mercury", "Moon", "Saturn"], "Capricorn": ["Jupiter", "Mars", "Sun"],
        "Aquarius": ["Venus", "Mercury", "Moon"], "Pisces": ["Saturn", "Jupiter", "Mars"]
    }

    def __init__(self, use_ptolemaic_terms: bool = False):
        self.use_ptolemaic = use_ptolemaic_terms

    def calculate_dignity(self, planet: str, sign: str, degree: float,
                          is_day_chart: bool = True) -> DignityScore:
        """Calculate complete dignity score for a planet in a sign/degree."""
        score = DignityScore(planet=planet, sign=sign, degree=degree)

        # Rulership (+5)
        if self.RULERS.get(sign) == planet:
            score.rulership = 5

        # Detriment (-5)
        if self.DETRIMENTS.get(sign) == planet:
            score.detriment = -5

        # Exaltation (+4)
        exalt_sign, exalt_deg = self.EXALTATIONS.get(planet, (None, 0))
        if exalt_sign == sign:
            score.exaltation = 4

        # Fall (-4)
        if self.FALLS.get(planet) == sign:
            score.fall = -4

        # Triplicity (+3)
        element = self._get_element(sign)
        if element:
            day_lord, night_lord, part_lord = self.TRIPLICITIES[element]
            if is_day_chart and planet == day_lord:
                score.triplicity = 3
            elif not is_day_chart and planet == night_lord:
                score.triplicity = 3
            elif planet == part_lord:
                score.triplicity = 3

        # Term (+2)
        term_ruler = self._get_term_ruler(sign, degree)
        if term_ruler == planet:
            score.term = 2

        # Face (+1)
        face_ruler = self._get_face_ruler(sign, degree)
        if face_ruler == planet:
            score.face = 1

        score.total_score = (score.rulership + score.exaltation + score.triplicity +
                             score.term + score.face + score.detriment + score.fall)

        return score

    def calculate_dignities(self, placements: Dict[str, Any], is_day: bool = True) -> Dict[str, Any]:
        """Batch calculate dignities for all planets."""
        positions = {}
        for planet, data in placements.items():
            if isinstance(data, dict) and 'sign' in data and 'degree' in data:
                positions[planet] = (data['sign'], data['degree'])

        dignities = {}
        for planet, (sign, deg) in positions.items():
            dignities[planet] = self.calculate_dignity(planet, sign, deg, is_day).__dict__

        receptions = self.find_receptions(positions, is_day)
        almuten = self.calculate_almuten(positions, is_day)

        return {
            'planet_dignities': dignities,
            'receptions': receptions,
            'almuten': almuten
        }

    def _get_element(self, sign: str) -> Optional[str]:
        elements = {
            "Aries": "Fire", "Leo": "Fire", "Sagittarius": "Fire",
            "Taurus": "Earth", "Virgo": "Earth", "Capricorn": "Earth",
            "Gemini": "Air", "Libra": "Air", "Aquarius": "Air",
            "Cancer": "Water", "Scorpio": "Water", "Pisces": "Water"
        }
        return elements.get(sign)

    def _get_term_ruler(self, sign: str, degree: float) -> Optional[str]:
        terms = self.EGYPTIAN_TERMS.get(sign, [])
        for start, end, ruler in terms:
            if start <= degree < end:
                return ruler
        return None

    def _get_face_ruler(self, sign: str, degree: float) -> Optional[str]:
        faces = self.FACES.get(sign, [])
        decan = int(degree // 10)
        if 0 <= decan < 3:
            return faces[decan]
        return None

    def find_receptions(self, positions: Dict[str, Tuple[str, float]],
                        is_day: bool = True) -> Dict[str, Any]:
        """Detect mutual reception and generosity."""
        receptions = {}
        planets = list(positions.keys())

        for i, p1 in enumerate(planets):
            sign1, deg1 = positions[p1]
            ruler1 = self.RULERS.get(sign1)

            for p2 in planets[i + 1:]:
                sign2, deg2 = positions[p2]
                ruler2 = self.RULERS.get(sign2)

                # Mutual Reception
                if ruler1 == p2 and ruler2 == p1:
                    key = f"{p1}-{p2}"
                    receptions[key] = {
                        'type': 'mutual',
                        'planets': [p1, p2],
                        'description': f"{p1} in {sign1} ({p2}'s sign), {p2} in {sign2} ({p1}'s sign)"
                    }
                # Generosity (one planet in another's sign while the other is exalted)
                elif ruler1 == p2:
                    p2_dignity = self.calculate_dignity(p2, sign2, deg2, is_day)
                    if p2_dignity.exaltation > 0:
                        key = f"{p1}-{p2}"
                        receptions[key] = {
                            'type': 'generosity',
                            'planets': [p1, p2],
                            'description': f"{p2} exalted in {p2}'s sign while hosting {p1}"
                        }

        return receptions

    def calculate_almuten(self, positions: Dict[str, Tuple[str, float]],
                          is_day: bool = True) -> Dict[str, Any]:
        """Calculate Almuten (planet with most dignity points)."""
        scores = {}
        for planet, (sign, deg) in positions.items():
            dignity = self.calculate_dignity(planet, sign, deg, is_day)
            scores[planet] = dignity.total_score

        sorted_scores = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        return {
            'almuten': sorted_scores[0][0] if sorted_scores else None,
            'scores': dict(sorted_scores),
            'details': {p: self.calculate_dignity(p, positions[p][0], positions[p][1], is_day).__dict__
                        for p in positions}
        }