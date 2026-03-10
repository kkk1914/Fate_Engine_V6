"""Divisional Charts (Varga) calculations."""
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
class VargaChart:
    name: str
    number: int
    planets: Dict[str, Dict[str, Any]]
    ascendant: float


class DivisionalCharts:
    """
    Calculate all important divisional charts.
    D9 (Navamsa), D10 (Dasamsa), D7 (Saptamsa), D12 (Dwadasamsa),
    D16 (Shodasamsa), D30 (Trimsamsa), D60 (Shashtyamsa)
    """

    VARGAS = {
        "D1": 1,  # Rasi (main chart)
        "D2": 2,  # Hora (wealth)
        "D3": 3,  # Drekkana (siblings/courage)
        "D7": 7,  # Saptamsa (children/progeny)
        "D9": 9,  # Navamsa (spouse/dharma)
        "D10": 10,  # Dasamsa (career/status)
        "D12": 12,  # Dwadasamsa (parents/lineage)
        "D16": 16,  # Shodasamsa (vehicles/comforts)
        "D20": 20,  # Vimsamsa (spiritual)
        "D24": 24,  # Chaturvimsamsa (education)
        "D27": 27,  # Saptavimsamsa (strength)
        "D30": 30,  # Trimsamsa (evils/diseases)
        "D40": 40,  # Khavedamsa (auspicious/inauspicious)
        "D45": 45,  # Akshavedamsa (character)
        "D60": 60  # Shashtyamsa (past life/general)
    }

    def __init__(self, jd: float, lat: float, lon: float):
        self.jd = jd
        self.lat = lat
        self.lon = lon
        self.natal_positions = self._get_natal_positions()

    def _get_natal_positions(self) -> Dict[str, float]:
        """Get tropical longitudes."""
        positions = {}
        for name, code in [("Sun", swe.SUN), ("Moon", swe.MOON),
                           ("Mars", swe.MARS), ("Mercury", swe.MERCURY),
                           ("Jupiter", swe.JUPITER), ("Venus", swe.VENUS),
                           ("Saturn", swe.SATURN), ("Rahu", swe.MEAN_NODE)]:
            pos = _swe_pos(swe.calc_ut(self.jd, code))
            positions[name] = pos[0]
        return positions

    def calculate_varga(self, varga_num: int) -> Dict[str, Any]:
        """
        Calculate specific varga positions.
        Uses standard Parashari methods.
        """
        varga_positions = {}

        for planet, lon in self.natal_positions.items():
            if varga_num == 9:  # Navamsa
                pos = self._navamsa_position(lon)
            elif varga_num == 10:  # Dasamsa
                pos = self._dasamsa_position(lon)
            elif varga_num == 7:  # Saptamsa
                pos = self._saptamsa_position(lon)
            elif varga_num == 12:  # Dwadasamsa
                pos = self._dwadasamsa_position(lon)
            elif varga_num == 16:  # Shodasamsa
                pos = self._shodasamsa_position(lon)
            elif varga_num == 30:  # Trimsamsa
                pos = self._trimsamsa_position(lon)
            elif varga_num == 60:  # Shashtyamsa
                pos = self._shashtyamsa_position(lon)
            else:
                pos = self._generic_varga(lon, varga_num)

            varga_positions[planet] = {
                "longitude": pos,
                "sign": self._get_sign(pos),
                "sign_num": int(pos // 30)
            }

        return {
            "varga": f"D{varga_num}",
            "planets": varga_positions,
            "ascendant": self._calculate_varga_ascendant(varga_num)
        }

    def _get_sign(self, lon: float) -> str:
        signs = ["Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo",
                 "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces"]
        return signs[int(lon // 30) % 12]

    def _navamsa_position(self, lon: float) -> float:
        """D9 calculation."""
        sign = int(lon // 30)
        within = lon % 30
        part = int(within // (30 / 9))

        # Movable: start from same sign; Fixed: 9th; Dual: 5th
        if sign in [0, 3, 6, 9]:  # Movable
            start = sign
        elif sign in [1, 4, 7, 10]:  # Fixed
            start = (sign + 8) % 12
        else:  # Dual
            start = (sign + 4) % 12

        return ((start + part) % 12) * 30 + (within % (30 / 9))

    def _dasamsa_position(self, lon: float) -> float:
        """D10 calculation."""
        sign = int(lon // 30)
        within = lon % 30
        part = int(within // 3)  # 10 parts of 3 degrees

        if sign in [0, 3, 6, 9]:
            start = sign
        elif sign in [1, 4, 7, 10]:
            start = (sign + 8) % 12
        else:
            start = (sign + 4) % 12

        return ((start + part) % 12) * 30 + (within % 3)

    def _saptamsa_position(self, lon: float) -> float:
        """D7 calculation."""
        sign = int(lon // 30)
        within = lon % 30
        part = int(within // (30 / 7))

        # Odd signs: start from sign, Even signs: start from 7th
        if sign % 2 == 0:  # Odd (0-indexed even)
            start = sign
        else:
            start = (sign + 6) % 12

        return ((start + part) % 12) * 30 + (within % (30 / 7))

    def _dwadasamsa_position(self, lon: float) -> float:
        """D12 calculation."""
        sign = int(lon // 30)
        within = lon % 30
        part = int(within // (30 / 12))

        return ((sign + part) % 12) * 30 + (within % (30 / 12))

    def _shodasamsa_position(self, lon: float) -> float:
        """D16 calculation."""
        sign = int(lon // 30)
        within = lon % 30
        part = int(within // (30 / 16))

        # Movable: 1st; Fixed: 5th; Dual: 9th
        if sign in [0, 3, 6, 9]:
            start = 0
        elif sign in [1, 4, 7, 10]:
            start = 4
        else:
            start = 8

        return ((start + part) % 12) * 30 + (within % (30 / 16))

    def _trimsamsa_position(self, lon: float) -> float:
        """D30 calculation."""
        sign = int(lon // 30)
        within = lon % 30

        # Complex Trimsamsa rules based on sign odd/even and degrees
        # Simplified version
        if sign % 2 == 0:  # Odd sign
            if 0 <= within < 5:
                return 0 * 30 + within * 6  # Aries
            elif 5 <= within < 10:
                return 1 * 30 + (within - 5) * 6  # Taurus
            elif 10 <= within < 18:
                return 2 * 30 + (within - 10) * 3.75  # Gemini
            elif 18 <= within < 25:
                return 3 * 30 + (within - 18) * 4.285  # Cancer
            else:
                return 4 * 30 + (within - 25) * 7.5  # Leo
        else:  # Even sign
            if 0 <= within < 5:
                return 11 * 30 + within * 6  # Pisces
            elif 5 <= within < 12:
                return 10 * 30 + (within - 5) * 4.285  # Aquarius
            elif 12 <= within < 20:
                return 9 * 30 + (within - 12) * 3.75  # Capricorn
            elif 20 <= within < 25:
                return 8 * 30 + (within - 20) * 6  # Sagittarius
            else:
                return 7 * 30 + (within - 25) * 6  # Scorpio

    def _shashtyamsa_position(self, lon: float) -> float:
        """D60 calculation."""
        sign = int(lon // 30)
        within = lon % 30
        part = int(within // 0.5)  # 60 parts of 0.5 degrees

        # For D60, start from sign itself or specific rules based on deity
        return ((sign + part) % 12) * 30 + (within % 0.5)

    def _generic_varga(self, lon: float, d: int) -> float:
        """Generic equal division."""
        sign = int(lon // 30)
        within = lon % 30
        part = int(within // (30 / d))
        return ((sign * d + part) % 12) * 30 + (within % (30 / d))

    def _calculate_varga_ascendant(self, varga_num: int) -> float:
        """Calculate Varga Ascendant."""
        # Get tropical ascendant
        cusps, ascmc = swe.houses(self.jd, self.lat, self.lon, b'P')
        asc = ascmc[0]

        # Convert to varga
        if varga_num == 9:
            return self._navamsa_position(asc)
        elif varga_num == 10:
            return self._dasamsa_position(asc)
        # ... etc for other vargas
        return self._generic_varga(asc, varga_num)

    def get_all_vargas(self) -> Dict[str, Any]:
        """Calculate all important vargas."""
        important = [9, 10, 7, 12, 16, 30, 60]
        results = {}

        for d in important:
            results[f"D{d}"] = self.calculate_varga(d)

        return results

    def varga_bala(self, planet: str) -> Dict[str, Any]:
        """
        Calculate Varga Bala (strength across divisionals).
        Planet strong in multiple vargas = high dignity.
        """
        vargas = self.get_all_vargas()
        strengths = {}

        # Count how many vargas planet occupies own/exalted sign
        # Simplified - needs exaltation tables per varga
        return {
            "planet": planet,
            "varga_occupancy": {k: v["planets"].get(planet, {}).get("sign")
                                for k, v in vargas.items()}
        }