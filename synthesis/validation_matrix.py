"""Cross-system validation matrix."""
from typing import Dict, Any, List, Tuple
from dataclasses import dataclass
from datetime import datetime


@dataclass
class PredictionEvent:
    system: str
    technique: str
    date_range: Tuple[datetime, datetime]
    theme: str
    confidence: float  # 0.0 - 1.0
    description: str
    house_involved: int
    planets_involved: List[str]


class ValidationMatrix:
    """
    Algorithmic reconciliation of predictions across systems.
    Resolves contradictions mathematically before LLM synthesis.
    """

    # Technique reliability weights
    TECHNIQUE_WEIGHTS = {
        "Primary Direction": 0.95,
        "Solar Return": 0.90,
        "Vimshottari Dasha": 0.88,
        "Tajaka": 0.85,
        "Solar Arc": 0.75,
        "Profection": 0.70,
        "Transit": 0.60,
        # Phase 3 additions
        "LUNAR_RETURN": 0.82,
        "SYZYGY": 0.75,
        "ESSENTIAL_DIGNITY": 0.70,
        "CROSS_SYSTEM_LORD": 0.90,
        "Da Yun": 0.80,
        # Add to TECHNIQUE_WEIGHTS dict:
        "Grand Trine": 0.80,
        "T-Square": 0.82,
        "Grand Cross": 0.85,
        "Yod": 0.78,
        "Stellium": 0.75,
        "VOC_Moon": 0.65,
        "Shadbala": 0.72,         # Positional + temporal strength (Parashara authority)
        "Transit_Aspect": 0.62,   # Precise natal aspect hit (vs. sign-level transit)
    }

    # House theme mappings (Western = Vedic_engine = Saju)
    HOUSE_THEMES = {
        1: ["Identity", "Body", "Self", "Personality"],
        2: ["Money", "Resources", "Values", "Speech"],
        3: ["Communication", "Siblings", "Short trips", "Skills"],
        4: ["Home", "Mother", "Real estate", "Emotions"],
        5: ["Children", "Creativity", "Romance", "Speculation"],
        6: ["Health", "Service", "Routines", "Debts"],
        7: ["Partnership", "Marriage", "Contracts", "Enemies"],
        8: ["Transformation", "Inheritance", "Death", "Occult"],
        9: ["Philosophy", "Travel", "Higher learning", "Father"],
        10: ["Career", "Status", "Authority", "Reputation"],
        11: ["Friends", "Groups", "Hopes", "Income"],
        12: ["Isolation", "Loss", "Spirituality", "Foreign"]
    }

    def __init__(self):
        self.events: List[PredictionEvent] = []

    def add_prediction(self, event: PredictionEvent):
        """Add prediction from any system."""
        # Normalize confidence by technique
        weight = self.TECHNIQUE_WEIGHTS.get(event.technique, 0.5)
        event.confidence = min(1.0, event.confidence * weight)
        self.events.append(event)

    def find_convergences(self, tolerance_days: int = 30) -> List[Dict[str, Any]]:
        """
        Find where 3+ systems agree on timing and theme.
        Returns convergence events with combined confidence.
        """
        convergences = []

        for i, event1 in enumerate(self.events):
            matches = [event1]

            for event2 in self.events[i + 1:]:
                if self._is_temporal_match(event1, event2, tolerance_days):
                    if self._is_thematic_match(event1, event2):
                        matches.append(event2)

            if len(matches) >= 3:  # 3+ systems agree
                convergences.append({
                    "events": matches,
                    "convergence_date": self._average_date(matches),
                    "combined_confidence": sum(e.confidence for e in matches) / len(matches),
                    "theme_consensus": self._extract_common_theme(matches),
                    "systems": list(set(e.system for e in matches)),
                    "intensity": len(matches)  # How many systems agree
                })

        # Sort by intensity then confidence
        convergences.sort(key=lambda x: (x["intensity"], x["combined_confidence"]),
                          reverse=True)
        return convergences

    def find_contradictions(self) -> List[Dict[str, Any]]:
        """
        Find genuine contradictions (same time, opposite outcomes).
        These need human/LLM resolution with context.
        """
        contradictions = []

        for i, event1 in enumerate(self.events):
            for event2 in self.events[i + 1:]:
                if self._is_temporal_match(event1, event2, 15):  # Closer tolerance
                    if self._is_contradictory(event1, event2):
                        contradictions.append({
                            "event_a": event1,
                            "event_b": event2,
                            "nature": self._classify_contradiction(event1, event2),
                            "resolution_heuristic": self._suggest_resolution(event1, event2)
                        })

        return contradictions

    def _is_temporal_match(self, e1: PredictionEvent, e2: PredictionEvent,
                           days: int) -> bool:
        """Check if two events overlap within tolerance."""
        # Check if date ranges overlap
        start1, end1 = e1.date_range
        start2, end2 = e2.date_range

        # Extend ranges by tolerance
        from datetime import timedelta
        start1 -= timedelta(days=days)
        end1 += timedelta(days=days)

        return (start1 <= end2) and (start2 <= end1)

    def _is_thematic_match(self, e1: PredictionEvent, e2: PredictionEvent) -> bool:
        """Check if themes align."""
        # Direct theme match
        if e1.theme == e2.theme:
            return True

        # House match (same house number)
        if e1.house_involved == e2.house_involved:
            return True

        # Check overlapping keywords
        themes1 = set(self.HOUSE_THEMES.get(e1.house_involved, []))
        themes2 = set(self.HOUSE_THEMES.get(e2.house_involved, []))

        return len(themes1 & themes2) > 0

    def _is_contradictory(self, e1: PredictionEvent, e2: PredictionEvent) -> bool:
        """Determine if two predictions contradict."""
        # Same house but opposite planets (e.g., Jupiter vs Saturn)
        if (e1.house_involved == e2.house_involved and
                len(set(e1.planets_involved) & set(e2.planets_involved)) == 0):

            # Check if one is benefic heavy, other malefic heavy
            benefics = {"Jupiter", "Venus", "Sun", "Moon", "Mercury"}
            malefics = {"Saturn", "Mars", "Rahu", "Ketu"}

            e1_benefic = any(p in benefics for p in e1.planets_involved)
            e1_malefic = any(p in malefics for p in e1.planets_involved)
            e2_benefic = any(p in benefics for p in e2.planets_involved)
            e2_malefic = any(p in malefics for p in e2.planets_involved)

            if (e1_benefic and e2_malefic) or (e1_malefic and e2_benefic):
                return True

        return False

    def _classify_contradiction(self, e1: PredictionEvent, e2: PredictionEvent) -> str:
        """Classify type of contradiction."""
        if e1.system != e2.system:
            return "Cross-System Tension"
        elif e1.technique != e2.technique:
            return "Technique Variance"
        else:
            return "Ambiguous Indication"

    def _suggest_resolution(self, e1: PredictionEvent, e2: PredictionEvent) -> str:
        """Suggest how to resolve contradiction."""
        # Higher confidence technique wins
        if e1.confidence > e2.confidence + 0.2:
            return f"Favor {e1.system} {e1.technique} (higher reliability)"
        elif e2.confidence > e1.confidence + 0.2:
            return f"Favor {e2.system} {e2.technique} (higher reliability)"
        else:
            return "Synthesize: Both valid, different expressions"

    def _average_date(self, events: List[PredictionEvent]) -> datetime:
        """Calculate centroid date of events."""
        from datetime import timezone
        timestamps = []
        for e in events:
            mid = e.date_range[0] + (e.date_range[1] - e.date_range[0]) / 2
            # Convert to Unix timestamp (float) for math
            timestamps.append(mid.timestamp())

        # Average the timestamps
        avg_timestamp = sum(timestamps) / len(timestamps)

        # Convert back to datetime
        return datetime.fromtimestamp(avg_timestamp, tz=timezone.utc)

    def _extract_common_theme(self, events: List[PredictionEvent]) -> str:
        """Find common theme among events."""
        themes = [e.theme for e in events]
        # Return most common
        return max(set(themes), key=themes.count)

    def generate_weighted_timeline(self) -> List[Dict[str, Any]]:
        """Generate final weighted timeline for next 5 years."""
        convergences = self.find_convergences()
        contradictions = self.find_contradictions()

        # Filter to high-confidence events
        high_confidence = [c for c in convergences if c["combined_confidence"] > 0.75]

        return {
            "critical_dates": high_confidence[:10],  # Top 10
            "contradictions_to_resolve": contradictions,
            "all_events": sorted(self.events, key=lambda x: x.date_range[0])
        }

    def validate_factual_claim(self, claim: str, chart_data: Dict) -> Dict[str, Any]:
        """
        Verify specific astrological claims against calculated data.
        Prevents hallucinations like 'Sun in Gemini' when it's in Cancer.
        """
        verification = {
            'claim': claim,
            'valid': False,
            'calculated_value': None,
            'error': None
        }

        # Parse claim patterns
        if 'Sun' in claim and '°' in claim:
            calc_sun = chart_data.get('western', {}).get('natal', {}).get('placements', {}).get('Sun', {})
            verification['calculated_value'] = f"{calc_sun.get('degree', 0):.1f}° {calc_sun.get('sign', 'Unknown')}"

            # Extract claimed degree
            import re
            match = re.search(r'(\d+)°\s*(\w+)', claim)
            if match:
                claimed_deg, claimed_sign = int(match.group(1)), match.group(2)
                actual_sign = calc_sun.get('sign')
                actual_deg = calc_sun.get('degree', 0)

                if claimed_sign == actual_sign and abs(claimed_deg - actual_deg) < 2:
                    verification['valid'] = True
                else:
                    verification['error'] = f"Claim {claimed_deg}° {claimed_sign} != {actual_deg:.1f}° {actual_sign}"

        elif 'Ascendant' in claim:
            calc_asc = chart_data.get('western', {}).get('natal', {}).get('angles', {}).get('Ascendant', {})
            verification['calculated_value'] = calc_asc.get('sign')
            if calc_asc.get('sign') in claim:
                verification['valid'] = True

        return verification