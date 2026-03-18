"""Vedic V2 Mathematical Engines (Ashtakavarga & Divisional Charts)."""
import swisseph as swe
from core.ayanamsa import AyanamsaManager
from config import settings

def _swe_pos(result):
    """Normalise pyswisseph calc_ut/fixstar return across API versions.
    Old (<2.10): returns (positions_tuple, retflag) — result[0] is a tuple.
    New (>=2.10): returns flat 6-tuple directly   — result[0] is a float.
    """
    return result[0] if isinstance(result[0], (list, tuple)) else result

from typing import Dict, Any, List
from dataclasses import dataclass


# Ashtakavarga Engine
class AshtakavargaEngine:
    PLANET_CONTRIBS = {
        "Sun": [1, 0, 0, 1, 0, 0, 1, 0, 0, 1, 0, 0],
        "Moon": [1, 0, 1, 0, 0, 1, 0, 1, 0, 0, 1, 0],
        "Mars": [1, 0, 0, 1, 0, 0, 1, 0, 0, 1, 0, 0],
        "Mercury": [1, 0, 0, 1, 0, 1, 0, 1, 0, 0, 1, 0],
        "Jupiter": [1, 0, 0, 1, 0, 0, 0, 1, 0, 0, 1, 0],
        "Venus": [1, 0, 0, 1, 0, 1, 0, 1, 0, 0, 1, 0],
        "Saturn": [1, 0, 0, 1, 0, 0, 1, 0, 0, 1, 0, 0]
    }

    def __init__(self, jd: float, lat: float, lon: float):
        self.jd = jd
        self.lat = lat
        self.lon = lon
        self.positions = self._get_positions()
        self.bhinna_ashtakavarga = self._calc_bhinna()
        self.sarva_ashtakavarga = self._calc_sarva()

    def _get_positions(self) -> Dict[str, int]:
        AyanamsaManager.set_ayanamsa(settings.ayanamsa)
        positions = {}
        for name, code in [("Sun", swe.SUN), ("Moon", swe.MOON),
                           ("Mars", swe.MARS), ("Mercury", swe.MERCURY),
                           ("Jupiter", swe.JUPITER), ("Venus", swe.VENUS),
                           ("Saturn", swe.SATURN)]:
            pos = _swe_pos(swe.calc_ut(self.jd, code, swe.FLG_SIDEREAL))
            positions[name] = int(pos[0] // 30)
        cusps, ascmc = swe.houses_ex(self.jd, self.lat, self.lon, b'P', swe.FLG_SIDEREAL)
        positions["Ascendant"] = int(ascmc[0] // 30)
        return positions

    def _calc_bhinna(self) -> dict:
        """
        Corrected Bhinna Ashtakavarga calculation.
        FIXED: iterates all 12 offsets; writes to (contributor_sign + offset) % 12.
        Includes self-contribution and Ascendant contribution matrices.
        """
        SELF_CONTRIB = {
            "Sun":     [1, 0, 0, 0, 0, 0, 0, 1, 0, 0, 1, 0],
            "Moon":    [1, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0, 0],
            "Mars":    [1, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1],
            "Mercury": [1, 0, 0, 0, 0, 0, 0, 0, 0, 1, 0, 1],
            "Jupiter": [1, 0, 0, 0, 0, 0, 1, 0, 0, 0, 1, 0],
            "Venus":   [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 1],
            "Saturn":  [1, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0, 1],
        }
        ASC_CONTRIB = {
            "Sun":     [1, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0, 0],
            "Moon":    [0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 1, 0],
            "Mars":    [1, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0],
            "Mercury": [0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0],
            "Jupiter": [0, 0, 0, 0, 0, 0, 1, 0, 0, 0, 1, 0],
            "Venus":   [0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 1],
            "Saturn":  [1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 0],
        }
        bhinna = {}
        for target in ["Sun", "Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn"]:
            bindus = [0] * 12
            for contributor, matrix in self.PLANET_CONTRIBS.items():
                if contributor == target:
                    self_matrix = SELF_CONTRIB[target]
                    contrib_sign = self.positions[contributor]
                    for offset, gives_bindu in enumerate(self_matrix):
                        if gives_bindu == 1:
                            bindus[(contrib_sign + offset) % 12] += 1
                else:
                    contrib_sign = self.positions[contributor]
                    for offset, gives_bindu in enumerate(matrix):
                        if gives_bindu == 1:
                            bindus[(contrib_sign + offset) % 12] += 1
            asc_matrix = ASC_CONTRIB[target]
            asc_sign = self.positions["Ascendant"]
            for offset, gives_bindu in enumerate(asc_matrix):
                if gives_bindu == 1:
                    bindus[(asc_sign + offset) % 12] += 1
            bhinna[target] = bindus
        return bhinna


    def _calc_sarva(self) -> List[int]:
        sarva = [0] * 12
        for bindus in self.bhinna_ashtakavarga.values():
            for i, count in enumerate(bindus):
                sarva[i] += count
        return sarva

    def get_house_strength(self, house_num: int) -> Dict[str, Any]:
        asc_sign = self.positions["Ascendant"]
        house_sign = (asc_sign + house_num - 1) % 12
        score = self.sarva_ashtakavarga[house_sign]
        strength = "Very Strong" if score >= 30 else "Strong" if score >= 25 else "Average" if score >= 20 else "Weak"
        return {"house": house_num, "sav_score": score, "strength": strength}


# Divisional Charts Engine
class DivisionalCharts:
    ZODIAC_V = ["Mesha", "Vrishabha", "Mithuna", "Karka", "Simha", "Kanya", "Tula", "Vrischika", "Dhanus", "Makara",
                "Kumbha", "Meena"]

    def __init__(self, jd: float, lat: float, lon: float):
        self.jd = jd
        self.lat = lat
        self.lon = lon
        self.natal = self._get_natal()

    def _get_natal(self) -> Dict[str, float]:
        positions = {}
        for name, code in [("Sun", swe.SUN), ("Moon", swe.MOON),
                           ("Mars", swe.MARS), ("Mercury", swe.MERCURY),
                           ("Jupiter", swe.JUPITER), ("Venus", swe.VENUS),
                           ("Saturn", swe.SATURN)]:
            pos = _swe_pos(swe.calc_ut(self.jd, code))
            positions[name] = pos[0]
        return positions

    def _navamsa(self, lon: float) -> str:
        sign = int(lon // 30)
        within = lon % 30
        part = int(within // (30 / 9))
        if sign in [0, 3, 6, 9]:
            start = sign
        elif sign in [1, 4, 7, 10]:
            start = (sign + 8) % 12
        else:
            start = (sign + 4) % 12
        return self.ZODIAC_V[(start + part) % 12]

    def get_all_vargas(self) -> Dict[str, Any]:
        return {"D9": {p: self._navamsa(lon) for p, lon in self.natal.items()}}