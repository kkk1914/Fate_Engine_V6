"""Full Ashtakavarga calculations."""
import swisseph as swe
from core.ayanamsa import AyanamsaManager
from config import settings

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

    # ── Ashtakavarga Contribution Matrices (BPHS — Brihat Parashara Hora Shastra) ──
    #
    # STRUCTURE: CONTRIB_MATRIX[target_planet][contributor] = [12 offsets from contributor's sign]
    # 1 = contributes bindu at that offset, 0 = does not
    # offset 0 = same sign as contributor, offset 1 = 2nd from contributor, etc.
    #
    # Source: BPHS chapters 66-72, cross-referenced with B.V. Raman's Ashtakavarga System.
    # Each target planet requires unique contribution arrays from each of the 8 contributors.
    #
    # NOTE: Self-contribution and Ascendant contribution are in SELF_CONTRIB and ASC_CONTRIB
    # below (in _calc_bhinna). The CONTRIB_MATRIX here covers ONLY cross-planet contributions.

    CONTRIB_MATRIX = {
        # ── SUN's BAV (total=48: self=8, Moon=6, Mars=8, Merc=7, Jup=4, Ven=3, Sat=8, Asc=4)
        "Sun": {
            "Moon":    [0, 0, 1, 0, 0, 1, 1, 1, 0, 1, 1, 0],  # 3,6,7,8,10,11
            "Mars":    [1, 1, 0, 1, 0, 0, 1, 1, 1, 1, 1, 0],  # 1,2,4,7,8,9,10,11
            "Mercury": [0, 0, 1, 0, 1, 1, 0, 0, 1, 1, 1, 1],  # 3,5,6,9,10,11,12
            "Jupiter": [0, 0, 0, 0, 1, 1, 0, 0, 1, 0, 1, 0],  # 5,6,9,11
            "Venus":   [0, 0, 0, 0, 0, 1, 1, 0, 0, 0, 0, 1],  # 6,7,12
            "Saturn":  [1, 1, 0, 1, 0, 0, 1, 1, 1, 1, 1, 0],  # 1,2,4,7,8,9,10,11
        },
        # ── MOON's BAV (total=49: self=6, Sun=6, Mars=7, Merc=8, Jup=7, Ven=7, Sat=4, Asc=4)
        "Moon": {
            "Sun":     [0, 0, 1, 0, 0, 1, 1, 1, 0, 1, 1, 0],  # 3,6,7,8,10,11
            "Mars":    [0, 1, 1, 0, 1, 1, 0, 0, 1, 1, 1, 0],  # 2,3,5,6,9,10,11
            "Mercury": [1, 0, 1, 1, 1, 0, 1, 1, 0, 1, 1, 0],  # 1,3,4,5,7,8,10,11
            "Jupiter": [1, 0, 0, 1, 0, 0, 1, 1, 0, 1, 1, 1],  # 1,4,7,8,10,11,12
            "Venus":   [0, 0, 1, 1, 1, 0, 1, 0, 1, 1, 1, 0],  # 3,4,5,7,9,10,11
            "Saturn":  [0, 0, 1, 0, 1, 1, 0, 0, 0, 0, 1, 0],  # 3,5,6,11
        },
        # ── MARS' BAV (total=39: self=7, Sun=5, Moon=3, Merc=4, Jup=4, Ven=4, Sat=7, Asc=5)
        "Mars": {
            "Sun":     [0, 0, 1, 0, 1, 1, 0, 0, 0, 1, 1, 0],  # 3,5,6,10,11
            "Moon":    [0, 0, 1, 0, 0, 1, 0, 0, 0, 0, 1, 0],  # 3,6,11
            "Mercury": [0, 0, 1, 0, 1, 1, 0, 0, 0, 0, 1, 0],  # 3,5,6,11
            "Jupiter": [0, 0, 0, 0, 0, 1, 0, 0, 0, 1, 1, 1],  # 6,10,11,12
            "Venus":   [0, 0, 0, 0, 0, 1, 0, 1, 0, 0, 1, 1],  # 6,8,11,12
            "Saturn":  [1, 0, 0, 1, 0, 0, 1, 1, 1, 1, 1, 0],  # 1,4,7,8,9,10,11
        },
        # ── MERCURY's BAV (total=54: self=8, Sun=5, Moon=6, Mars=8, Jup=4, Ven=8, Sat=8, Asc=7)
        "Mercury": {
            "Sun":     [0, 0, 0, 0, 1, 1, 0, 0, 1, 0, 1, 1],  # 5,6,9,11,12
            "Moon":    [0, 1, 0, 1, 0, 1, 0, 1, 0, 1, 1, 0],  # 2,4,6,8,10,11
            "Mars":    [1, 1, 0, 1, 0, 0, 1, 1, 1, 1, 1, 0],  # 1,2,4,7,8,9,10,11
            "Jupiter": [0, 0, 0, 0, 0, 1, 0, 1, 0, 0, 1, 1],  # 6,8,11,12
            "Venus":   [1, 1, 1, 1, 1, 0, 0, 1, 1, 0, 1, 0],  # 1,2,3,4,5,8,9,11
            "Saturn":  [1, 1, 0, 1, 0, 0, 1, 1, 1, 1, 1, 0],  # 1,2,4,7,8,9,10,11
        },
        # ── JUPITER's BAV (total=56: self=8, Sun=9, Moon=5, Mars=7, Merc=8, Ven=6, Sat=4, Asc=9)
        "Jupiter": {
            "Sun":     [1, 1, 1, 1, 0, 0, 1, 1, 1, 1, 1, 0],  # 1,2,3,4,7,8,9,10,11
            "Moon":    [0, 1, 0, 0, 1, 0, 1, 0, 1, 0, 1, 0],  # 2,5,7,9,11
            "Mars":    [1, 1, 0, 1, 0, 0, 1, 1, 0, 1, 1, 0],  # 1,2,4,7,8,10,11
            "Mercury": [1, 1, 0, 1, 1, 1, 0, 0, 1, 1, 1, 0],  # 1,2,4,5,6,9,10,11
            "Venus":   [0, 1, 0, 0, 1, 1, 0, 0, 1, 1, 1, 0],  # 2,5,6,9,10,11
            "Saturn":  [0, 0, 1, 0, 1, 1, 0, 0, 0, 0, 0, 1],  # 3,5,6,12
        },
        # ── VENUS' BAV (total=52: self=9, Sun=3, Moon=9, Mars=6, Merc=5, Jup=5, Sat=7, Asc=8)
        "Venus": {
            "Sun":     [0, 0, 0, 0, 0, 0, 0, 1, 0, 0, 1, 1],  # 8,11,12
            "Moon":    [1, 1, 1, 1, 1, 0, 0, 1, 1, 0, 1, 1],  # 1,2,3,4,5,8,9,11,12
            "Mars":    [0, 0, 1, 0, 1, 1, 0, 0, 1, 0, 1, 1],  # 3,5,6,9,11,12
            "Mercury": [0, 0, 1, 0, 1, 1, 0, 0, 1, 0, 1, 0],  # 3,5,6,9,11
            "Jupiter": [0, 0, 0, 0, 1, 0, 0, 1, 1, 1, 1, 0],  # 5,8,9,10,11
            "Saturn":  [0, 0, 1, 1, 1, 0, 0, 1, 1, 1, 1, 0],  # 3,4,5,8,9,10,11
        },
        # ── SATURN's BAV (total=39: self=4, Sun=7, Moon=3, Mars=6, Merc=6, Jup=4, Ven=3, Asc=6)
        "Saturn": {
            "Sun":     [1, 1, 0, 1, 0, 0, 1, 1, 0, 1, 1, 0],  # 1,2,4,7,8,10,11
            "Moon":    [0, 0, 1, 0, 0, 1, 0, 0, 0, 0, 1, 0],  # 3,6,11
            "Mars":    [0, 0, 1, 0, 1, 1, 0, 0, 0, 1, 1, 1],  # 3,5,6,10,11,12
            "Mercury": [0, 0, 0, 0, 0, 1, 0, 1, 1, 1, 1, 1],  # 6,8,9,10,11,12
            "Jupiter": [0, 0, 0, 0, 1, 1, 0, 0, 0, 0, 1, 1],  # 5,6,11,12
            "Venus":   [0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 1],  # 6,11,12
        },
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
        AyanamsaManager.set_ayanamsa(settings.ayanamsa)
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
        # Source: BPHS chapters 66-72
        SELF_CONTRIB = {
            "Sun":     [1, 1, 0, 1, 0, 0, 1, 1, 1, 1, 1, 0],  # 1,2,4,7,8,9,10,11 [8]
            "Moon":    [1, 0, 1, 0, 0, 1, 1, 0, 0, 1, 1, 0],  # 1,3,6,7,10,11 [6]
            "Mars":    [1, 1, 0, 1, 0, 0, 1, 1, 0, 1, 1, 0],  # 1,2,4,7,8,10,11 [7]
            "Mercury": [1, 0, 1, 0, 1, 1, 0, 0, 1, 1, 1, 1],  # 1,3,5,6,9,10,11,12 [8]
            "Jupiter": [1, 1, 1, 1, 0, 0, 1, 1, 0, 1, 1, 0],  # 1,2,3,4,7,8,10,11 [8]
            "Venus":   [1, 1, 1, 1, 1, 0, 0, 1, 1, 1, 1, 0],  # 1,2,3,4,5,8,9,10,11 [9]
            "Saturn":  [0, 0, 1, 0, 1, 1, 0, 0, 0, 0, 1, 0],  # 3,5,6,11 [4]
        }
        # Ascendant contribution to each planet's BAV
        ASC_CONTRIB = {
            "Sun":     [0, 0, 1, 1, 0, 1, 0, 0, 0, 1, 0, 0],  # 3,4,6,10 [4]
            "Moon":    [0, 0, 1, 0, 0, 1, 0, 0, 0, 1, 1, 0],  # 3,6,10,11 [4]
            "Mars":    [1, 0, 1, 0, 0, 1, 0, 0, 0, 1, 1, 0],  # 1,3,6,10,11 [5]
            "Mercury": [1, 1, 0, 1, 0, 1, 0, 1, 0, 1, 1, 0],  # 1,2,4,6,8,10,11 [7]
            "Jupiter": [1, 1, 0, 1, 1, 1, 1, 0, 1, 1, 1, 0],  # 1,2,4,5,6,7,9,10,11 [9]
            "Venus":   [1, 1, 1, 1, 1, 0, 0, 1, 1, 0, 1, 0],  # 1,2,3,4,5,8,9,11 [8]
            "Saturn":  [1, 0, 1, 1, 0, 1, 0, 0, 0, 1, 1, 0],  # 1,3,4,6,10,11 [6]
        }

        bhinna = {}

        for target in ["Sun", "Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn"]:
            bindus = [0] * 12
            target_matrices = self.CONTRIB_MATRIX.get(target, {})

            # Contributions from each planet
            for contributor in ["Sun", "Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn"]:
                contrib_sign = self.positions[contributor]
                if contributor == target:
                    # Use self-contribution matrix
                    matrix = SELF_CONTRIB.get(contributor, [0] * 12)
                else:
                    # Use per-target-per-contributor matrix (BPHS)
                    matrix = target_matrices.get(contributor, [0] * 12)
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

    def validate_matrices(self) -> Dict[str, Any]:
        """Validate Ashtakavarga matrices against BPHS expected totals.

        Standard BPHS bindu totals per planet's BAV (sum across 12 signs):
          Sun=48, Moon=49, Mars=39, Mercury=54, Jupiter=56, Venus=52, Saturn=39
          Total SAV = 337

        Returns dict with pass/fail status and any discrepancies.
        """
        EXPECTED_TOTALS = {
            "Sun": 48, "Moon": 49, "Mars": 39, "Mercury": 54,
            "Jupiter": 56, "Venus": 52, "Saturn": 39,
        }
        EXPECTED_SAV = 337

        results = {"passed": True, "discrepancies": [], "bhinna_totals": {}}

        for planet, bindus in self.bhinna_ashtakavarga.items():
            actual = sum(bindus)
            expected = EXPECTED_TOTALS.get(planet, 0)
            results["bhinna_totals"][planet] = actual
            if actual != expected:
                results["passed"] = False
                results["discrepancies"].append(
                    f"{planet}: got {actual} bindus, expected {expected} (BPHS)"
                )

        actual_sav = sum(self.sarva_ashtakavarga)
        results["sav_total"] = actual_sav
        if actual_sav != EXPECTED_SAV:
            results["passed"] = False
            results["discrepancies"].append(
                f"SAV total: got {actual_sav}, expected {EXPECTED_SAV}"
            )

        return results