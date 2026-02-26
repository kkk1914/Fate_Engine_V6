"""Cross-system house lord mapping and elemental correspondence."""
from typing import Dict, Any, List


class HouseLordMapper:
    """Maps house lords between Western, Vedic, and Saju systems."""

    # Western traditional rulers
    WESTERN_LORDS = {
        1: "Mars", 2: "Venus", 3: "Mercury", 4: "Moon",
        5: "Sun", 6: "Mercury", 7: "Venus", 8: "Mars",
        9: "Jupiter", 10: "Saturn", 11: "Saturn", 12: "Jupiter"
    }

    # Vedic rulers (same as Western for most, but Scorpio/Ketu, Aquarius/Rahu variations)
    VEDIC_LORDS = {
        1: "Mars", 2: "Venus", 3: "Mercury", 4: "Moon",
        5: "Sun", 6: "Mercury", 7: "Venus", 8: "Mars",  # Some use Ketu for 8
        9: "Jupiter", 10: "Saturn", 11: "Saturn", 12: "Jupiter"
    }

    # Saju elements by house number (derived from Earthly Branches)
    SAJU_ELEMENTS = {
        1: "Water", 2: "Earth", 3: "Wood", 4: "Wood",
        5: "Earth", 6: "Fire", 7: "Fire", 8: "Earth",
        9: "Metal", 10: "Metal", 11: "Earth", 12: "Water"
    }

    # Element to Planet mapping
    ELEMENT_PLANETS = {
        "Fire": ["Sun", "Mars"],
        "Earth": ["Saturn", "Venus"],
        "Metal": ["Saturn", "Venus"],  # Metal akin to Earth/Saturn
        "Wood": ["Jupiter", "Venus"],
        "Water": ["Moon", "Mercury"]
    }

    def map_house(self, house_num: int, system: str = "all") -> Dict[str, Any]:
        """Get lord mapping for a specific house."""
        mapping = {
            'house': house_num,
            'western': self.WESTERN_LORDS.get(house_num),
            'vedic': self.VEDIC_LORDS.get(house_num),
            'saju_element': self.SAJU_ELEMENTS.get(house_num)
        }

        # Cross-correlations
        west_planet = mapping['western']
        vedic_planet = mapping['vedic']
        saju_el = mapping['saju_element']

        mapping['agreement'] = {
            'western_vedic': west_planet == vedic_planet,
            'elemental_correspondence': west_planet in self.ELEMENT_PLANETS.get(saju_el, []),
            'interpretive_consensus': self._get_consensus(house_num, west_planet, saju_el)
        }

        if system == "western":
            return {'house': house_num, 'lord': west_planet}
        elif system == "vedic":
            return {'house': house_num, 'lord': vedic_planet}

        return mapping

    def _get_consensus(self, house: int, west: str, saju_el: str) -> str:
        """Get interpretive consensus between systems."""
        consensuses = {
            1: "Self/Identity", 2: "Resources/Values", 3: "Communication/Siblings",
            4: "Home/Foundation", 5: "Creativity/Children", 6: "Health/Service",
            7: "Partnership", 8: "Transformation/Crisis", 9: "Wisdom/Travel",
            10: "Career/Public", 11: "Community/Gains", 12: "Isolation/Spirit"
        }
        return consensuses.get(house, "Unknown")

    def validate_cross_system(self, western_chart: Dict, vedic_chart: Dict) -> List[Dict]:
        """
        Validate that house lord placements align logically across systems.
        Returns validation errors if contradictions found.
        """
        validations = []

        for house in range(1, 13):
            west_lord = self.WESTERN_LORDS[house]
            vedic_lord = self.VEDIC_LORDS[house]

            # Check if lord is in 8th or 12th in other system (debility)
            west_placement = western_chart.get('placements', {}).get(west_lord, {})
            vedic_placement = vedic_chart.get('placements', {}).get(vedic_lord, {})

            validations.append({
                'house': house,
                'lord': west_lord,
                'western_house': west_placement.get('house'),
                'vedic_house': vedic_placement.get('house'),
                'status': 'conflict' if (vedic_placement.get('house') in [8, 12]) else 'aligned'
            })

        return validations