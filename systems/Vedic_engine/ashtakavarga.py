"""Full Ashtakavarga calculations."""
import swisseph as swe

def _swe_pos(result):
    """Normalise pyswisseph calc_ut/fixstar return across API versions.
    Old (<2.10): returns (positions_tuple, retflag) — result[0] is a tuple.
    New (>=2.10): returns flat 6-tuple directly   — result[0] is a float.
    """
    return result[0] if isinstance(result[0], (list, tuple)) else result

from typing import Dict, Any, List, Tuple
from dataclasses import dataclass


@dataclass
class AshtakavargaBindus:
    """Bindus contributed by each planet to each sign."""
    planet: str
    bindus: Dict[int, int]  # Sign index (0-11) -> bindu count (0-8)


class AshtakavargaEngine:
    """
    Complete Ashtakavarga system including:
    - Bhinna Ashtakavarga (individual)
    - Sarva Ashtakavarga (total)
    - Kakshya (transit) analysis
    """

    # Ashtakavarga contribution matrices
    # 1 = contributes bindu, 0 = does not contribute
    # Rows: Sun, Moon, Mars, Mercury, Jupiter, Venus, Saturn, Ascendant
    # Cols: Signs from planet (1st, 2nd, etc.)

    SUN_CONTRIB = [1, 0, 0, 1, 0, 0, 1, 0, 0, 1, 0, 0]  # 11, 1, 4, 7, 10 (0-indexed)
    MOON_CONTRIB = [1, 0, 1, 0, 0, 1, 0, 1, 0, 0, 1, 0]
    MARS_CONTRIB = [1, 0, 0, 1, 0, 0, 1, 0, 0, 1, 0, 0]
    MERCURY_CONTRIB = [1, 0, 0, 1, 0, 1, 0, 1, 0, 0, 1, 0]
    JUPITER_CONTRIB = [1, 0, 0, 1, 0, 0, 0, 1, 0, 0, 1, 0]
    VENUS_CONTRIB = [1, 0, 0, 1, 0, 1, 0, 1, 0, 0, 1, 0]
    SATURN_CONTRIB = [1, 0, 0, 1, 0, 0, 1, 0, 0, 1, 0, 0]

    PLANET_CONTRIBS = {
        "Sun": SUN_CONTRIB,
        "Moon": MOON_CONTRIB,
        "Mars": MARS_CONTRIB,
        "Mercury": MERCURY_CONTRIB,
        "Jupiter": JUPITER_CONTRIB,
        "Venus": VENUS_CONTRIB,
        "Saturn": SATURN_CONTRIB
    }

    def __init__(self, jd: float, lat: float, lon: float):
        self.jd = jd
        self.lat = lat
        self.lon = lon
        self.positions = self._get_planet_positions()
        self.bhinna_ashtakavarga = self._calc_bhinna()
        self.sarva_ashtakavarga = self._calculate_sarva()

    def _get_planet_positions(self) -> Dict[str, int]:
        """Get sidereal sign positions (0-11)."""
        swe.set_sid_mode(swe.SIDM_LAHIRI)
        positions = {}

        for name, code in [("Sun", swe.SUN), ("Moon", swe.MOON),
                           ("Mars", swe.MARS), ("Mercury", swe.MERCURY),
                           ("Jupiter", swe.JUPITER), ("Venus", swe.VENUS),
                           ("Saturn", swe.SATURN)]:
            pos = _swe_pos(swe.calc_ut(self.jd, code, swe.FLG_SIDEREAL))
            positions[name] = int(pos[0] // 30)

        # Ascendant
        cusps, ascmc = swe.houses_ex(self.jd, self.lat, self.lon, b'P',
                                     swe.FLG_SIDEREAL)
        positions["Ascendant"] = int(ascmc[0] // 30)

        return positions

    def _calc_bhinna(self) -> Dict[str, List[int]]:
        """
        Calculate Bhinna (individual) Ashtakavarga for each planet.

        Algorithm (Parashara):
        For each TARGET planet T and each CONTRIBUTOR planet C:
          C is in sign X (0-11).
          For each offset 0-11: if PLANET_CONTRIBS[C][offset] == 1,
            the sign (X + offset) % 12 receives a bindu in T's BAV.
        Plus: each planet contributes to its own BAV (self-contribution),
        and the Ascendant also contributes.

        Returns: {planet: [bindu_count_per_sign_0..11]}
        """
        # Self-contribution matrices (planet contributes to own BAV from own position)
        SELF_CONTRIB = {
            "Sun": [1, 0, 0, 0, 0, 0, 0, 1, 0, 0, 1, 0],
            "Moon": [1, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0, 0],
            "Mars": [1, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1],
            "Mercury": [1, 0, 0, 0, 0, 0, 0, 0, 0, 1, 0, 1],
            "Jupiter": [1, 0, 0, 0, 0, 0, 1, 0, 0, 0, 1, 0],
            "Venus": [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 1],
            "Saturn": [1, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0, 1],
        }
        # Ascendant contribution to each planet's BAV
        ASC_CONTRIB = {
            "Sun": [1, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0, 0],
            "Moon": [0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 1, 0],
            "Mars": [1, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0],
            "Mercury": [0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0],
            "Jupiter": [0, 0, 0, 0, 0, 0, 1, 0, 0, 0, 1, 0],
            "Venus": [0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 1],
            "Saturn": [1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 0],
        }

        bhinna = {}

        for target in ["Sun", "Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn"]:
            bindus = [0] * 12

            # Contributions from OTHER planets
            for contributor, matrix in self.PLANET_CONTRIBS.items():
                if contributor == target:
                    # Use self-contribution matrix instead
                    self_matrix = SELF_CONTRIB.get(contributor, [0] * 12)
                    contrib_sign = self.positions[contributor]
                    for offset, gives_bindu in enumerate(self_matrix):
                        if gives_bindu == 1:
                            target_sign = (contrib_sign + offset) % 12
                            bindus[target_sign] += 1
                else:
                    contrib_sign = self.positions[contributor]
                    for offset, gives_bindu in enumerate(matrix):
                        if gives_bindu == 1:
                            target_sign = (contrib_sign + offset) % 12
                            bindus[target_sign] += 1

            # Ascendant contribution
            asc_matrix = ASC_CONTRIB.get(target, [0] * 12)
            asc_sign = self.positions["Ascendant"]
            for offset, gives_bindu in enumerate(asc_matrix):
                if gives_bindu == 1:
                    target_sign = (asc_sign + offset) % 12
                    bindus[target_sign] += 1

            bhinna[target] = bindus

        return bhinna

    def _calculate_sarva(self) -> List[int]:
        """Sum all Bhinna Ashtakavargas."""
        sarva = [0] * 12
        for planet, bindus in self.bhinna_ashtakavarga.items():
            for i, count in enumerate(bindus):
                sarva[i] += count
        return sarva

    def get_house_strength(self, house_num: int) -> Dict[str, Any]:
        """
        Get strength of house based on SAV.
        House 1 = sign of Ascendant, etc.
        """
        asc_sign = self.positions["Ascendant"]
        house_sign = (asc_sign + house_num - 1) % 12
        sav_score = self.sarva_ashtakavarga[house_sign]

        # Interpretation thresholds
        if sav_score >= 30:
            strength = "Very Strong"
        elif sav_score >= 25:
            strength = "Strong"
        elif sav_score >= 20:
            strength = "Average"
        elif sav_score >= 15:
            strength = "Weak"
        else:
            strength = "Very Weak"

        return {
            "house": house_num,
            "sign_index": house_sign,
            "sav_score": sav_score,
            "strength": strength,
            "max_possible": 56  # 7 planets * 8 contributions max
        }

    def kakshya_analysis(self, transit_planet: str, sign: int) -> Dict[str, Any]:
        """
        Analyze transit using Kakshya (reduction).
        Each sign divided into 8 kakshyas (sub-divisions).
        If transit planet's kakshya has bindu, transit is favorable.
        """
        # Simplified: Check if transit sign has good SAV
        sav = self.sarva_ashtakavarga[sign]

        # Detailed: Check Bhinna AV of the house lord
        sign_lords = ["Mars", "Venus", "Mercury", "Moon", "Sun", "Mercury",
                      "Venus", "Mars", "Jupiter", "Saturn", "Saturn", "Jupiter"]
        lord = sign_lords[sign]
        lord_av = self.bhinna_ashtakavarga.get(lord, [0] * 12)[sign]

        return {
            "transit_sign": sign,
            "sav_score": sav,
            "lord_bindus_in_sign": lord_av,
            "favorable": sav >= 25 and lord_av >= 4
        }

    def get_prasthanas(self) -> Dict[str, Any]:
        """
        Five Prasthanas (sources) for prediction:
        1. Janma (Natal)
        2. Varsha (Annual/Tajaka)
        3. Dasha (Planetary periods)
        4. Gochara (Transit)
        5. Nakshatra (Lunar mansion)
        """
        return {
            "janma_strength": self._get_prasthana_strength("natal"),
            "transit_strength": self._get_prasthana_strength("transit")
        }

    def _get_prasthana_strength(self, prasthana_type: str) -> Dict[str, Any]:
        """Calculate strength for specific prasthana."""
        # Implementation depends on specific prasthana calculations
        return {"type": prasthana_type, "sav_average": sum(self.sarva_ashtakavarga) / 12}