"""Tajaka (Vedic_engine Solar Return) system."""
import swisseph as swe
from datetime import datetime
from typing import Dict, Any, List



class TajakaEngine:
    """
    Tajaka Shashtra - Vedic_engine Annual Horoscopy.
    Calculates Muntha (yearly ascendant) and Tajaka charts.
    """

    def __init__(self, natal_jd: float, lat: float, lon: float):
        self.natal_jd = natal_jd
        self.lat = lat
        self.lon = lon

    def calculate_tajaka(self, year: int) -> Dict[str, Any]:
        """
        Calculate Tajaka chart for year.
        Muntha = Natal Ascendant + (Year - Birth Year) * 30°
        """
        # Get natal data
        birth_year = int(swe.revjul(self.natal_jd)[0])
        years_elapsed = year - birth_year

        # Calculate Muntha (yearly ascendant)
        natal_asc = self._get_natal_ascendant()
        muntha = (natal_asc + (years_elapsed * 30)) % 360

        # Tajaka chart uses Solar Return moment but Vedic_engine (Sidereal) zodiac
        # Simplified: Use current date with Muntha as reference

        return {
            "year": year,
            "muntha": muntha,
            "muntha_sign": self._get_sidereal_sign(muntha),
            "years_elapsed": years_elapsed,
            "lord_of_year": self._get_muntha_lord(muntha),
            "triplicity_ruler": self._get_triplicity_ruler(muntha)
        }

    def _get_natal_ascendant(self) -> float:
        """Get natal ascendant (sidereal)."""
        swe.set_sid_mode(swe.SIDM_LAHIRI)
        cusps, ascmc = swe.houses_ex(self.natal_jd, self.lat, self.lon, b'P',
                                     swe.FLG_SIDEREAL)
        return ascmc[0]

    def _get_sidereal_sign(self, lon: float) -> str:
        signs = ["Mesha", "Vrishabha", "Mithuna", "Karka", "Simha", "Kanya",
                 "Tula", "Vrischika", "Dhanus", "Makara", "Kumbha", "Meena"]
        return signs[int(lon // 30)]

    def _get_muntha_lord(self, muntha: float) -> str:
        sign = self._get_sidereal_sign(muntha)
        rulers = {
            "Mesha": "Mars", "Vrishabha": "Venus", "Mithuna": "Mercury",
            "Karka": "Moon", "Simha": "Sun", "Kanya": "Mercury",
            "Tula": "Venus", "Vrischika": "Mars", "Dhanus": "Jupiter",
            "Makara": "Saturn", "Kumbha": "Saturn", "Meena": "Jupiter"
        }
        return rulers.get(sign, "Unknown")

    def _get_triplicity_ruler(self, muntha: float) -> str:
        """Get triplicity ruler for Muntha."""
        sign_idx = int(muntha // 30)
        elements = {
            "Fire": ["Mesha", "Simha", "Dhanus"],
            "Earth": ["Vrishabha", "Kanya", "Makara"],
            "Air": ["Mithuna", "Tula", "Kumbha"],
            "Water": ["Karka", "Vrischika", "Meena"]
        }

        element = None
        for el, signs in elements.items():
            if self._get_sidereal_sign(muntha) in signs:
                element = el
                break

        triplicity_lords = {
            "Fire": ["Sun", "Jupiter", "Saturn"],
            "Earth": ["Venus", "Moon", "Mars"],
            "Air": ["Saturn", "Mercury", "Jupiter"],
            "Water": ["Venus", "Mars", "Moon"]
        }

        # Day/night calculation simplified
        return triplicity_lords.get(element, ["Unknown"])[0]