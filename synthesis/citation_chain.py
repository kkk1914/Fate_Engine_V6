"""Evidence Citation Chain Formatter.

Converts convergence clusters from the Validation Matrix into structured
evidence chains that the Archon must include verbatim in the report.

This ensures traceable, verifiable predictions:
  **Property acquisition: Summer 2027** (NEAR-CERTAIN, 4-system convergence)
  Evidence chain:
  - [VED] Jupiter Mahadasha + Venus Antardasha activates 4th lord
  - [WES] Solar Arc Jupiter conjunct natal IC exact Aug 2027
  - [HEL] Profected Year Lord = Venus (4th house profection)
  - [SAJ] Da Yun Metal phase = resource accumulation
  - [MATRIX] Convergence score: 0.91 (4 systems, 3 gold-standard techniques)
"""

from typing import Dict, Any, List
from datetime import datetime, timezone
from synthesis.validation_matrix import ValidationMatrix


# Confidence band labels (same as temporal_aligner.py)
def _confidence_label(score: float) -> str:
    if score >= 0.85:
        return "NEAR-CERTAIN"
    elif score >= 0.75:
        return "HIGH-CONFIDENCE"
    elif score >= 0.55:
        return "MODERATE-CONFIDENCE"
    return "LOW-CONFIDENCE"


# System abbreviation map
SYSTEM_ABBR = {
    "Western": "WES",
    "Vedic": "VED",
    "Saju": "SAJ",
    "Hellenistic": "HEL",
    "Cross-System": "XSYS",
}

# Technique → readable label
TECHNIQUE_LABEL = {
    "Primary Direction": "Primary Direction (Ptolemaic)",
    "Vimshottari Dasha": "Vimshottari Dasha",
    "Vimshottari_Antardasha": "Antardasha Sub-Period",
    "Solar Return": "Solar Return (Annual)",
    "Lunar Return": "Lunar Return (Monthly)",
    "LUNAR_RETURN": "Lunar Return (Monthly)",
    "Transit_Aspect": "Exact Transit Aspect",
    "Transit": "Transit",
    "Profection": "Annual Profection (Hellenistic)",
    "Zodiacal_Releasing": "Zodiacal Releasing (Valens)",
    "Da Yun": "Da Yun (10-Year Luck Pillar)",
    "Liu_Nian": "Liu Nian (Annual Pillar)",
    "Tajaka": "Tajaka (Vedic Solar Return)",
    "Solar Arc": "Solar Arc Direction",
    "Progression": "Secondary Progression",
    "CROSS_SYSTEM_LORD": "Cross-System Lord Activation",
    "Shadbala": "Shadbala Strength",
    "Kakshya": "Kakshya Transit Quality",
}


class CitationChainFormatter:
    """Formats convergence clusters into structured evidence citation blocks.

    Usage:
        formatter = CitationChainFormatter(convergences, contradictions)
        citation_block = formatter.format_top_predictions(n=10)
        per_house_blocks = formatter.format_by_house()
    """

    def __init__(self, convergences: List[Dict], contradictions: List[Dict] = None):
        self.convergences = convergences
        self.contradictions = contradictions or []

    def format_top_predictions(self, n: int = 10) -> str:
        """Format the top N convergence clusters as citation chains.

        Returns a formatted block suitable for injection into Archon prompts.
        """
        if not self.convergences:
            return ""

        lines = [
            "══════════════════════════════════════════════════════════════",
            "  EVIDENCE-BACKED PREDICTIONS (cite these verbatim in report)",
            "══════════════════════════════════════════════════════════════",
            "",
        ]

        for i, conv in enumerate(self.convergences[:n], 1):
            lines.append(self._format_single_prediction(i, conv))
            lines.append("")

        # Contradictions
        if self.contradictions:
            lines.append("── CONTRADICTIONS (acknowledge in narrative) ─────────────")
            for j, contra in enumerate(self.contradictions[:5], 1):
                lines.append(self._format_contradiction(j, contra))
            lines.append("")

        lines.append("══════════════════════════════════════════════════════════════")
        return "\n".join(lines)

    def format_by_house(self) -> Dict[int, str]:
        """Group predictions by house and return per-house citation blocks.

        Useful for the Archon's year-chapter sections where each chapter
        focuses on specific life domains.
        """
        house_blocks = {}

        for conv in self.convergences:
            events = conv.get("events", [])
            if not events:
                continue

            # Get primary house from events
            houses = [e.house_involved for e in events if hasattr(e, 'house_involved')]
            if not houses:
                continue
            primary_house = max(set(houses), key=houses.count)

            if primary_house not in house_blocks:
                house_blocks[primary_house] = []
            house_blocks[primary_house].append(conv)

        result = {}
        for house, convs in house_blocks.items():
            lines = [f"── H{house} Evidence ──"]
            for i, conv in enumerate(convs[:5], 1):
                lines.append(self._format_compact_prediction(conv))
            result[house] = "\n".join(lines)

        return result

    def format_for_question(self, question: str, theme_houses: List[int]) -> str:
        """Format evidence relevant to a specific user question.

        Filters convergences to only those matching the question's
        thematic houses, then formats as a citation chain.
        """
        relevant = []
        for conv in self.convergences:
            events = conv.get("events", [])
            event_houses = {e.house_involved for e in events
                           if hasattr(e, 'house_involved')}
            if event_houses & set(theme_houses):
                relevant.append(conv)

        if not relevant:
            return ""

        lines = [f"── Evidence for: {question[:80]} ──"]
        for conv in relevant[:5]:
            lines.append(self._format_compact_prediction(conv))
        return "\n".join(lines)

    def _format_single_prediction(self, idx: int, conv: Dict) -> str:
        """Format a single convergence as a full citation chain."""
        events = conv.get("events", [])
        confidence = conv.get("combined_confidence", 0)
        theme = conv.get("theme_consensus", "Unknown")
        systems = conv.get("systems", [])
        techniques = conv.get("techniques", [])
        conv_date = conv.get("convergence_date")

        label = _confidence_label(confidence)
        n_systems = len(systems)

        # Date formatting
        if conv_date:
            if isinstance(conv_date, datetime):
                date_str = conv_date.strftime("%B %Y")
            else:
                date_str = str(conv_date)
        else:
            date_str = "TBD"

        lines = [
            f"  [{idx}] {theme}: {date_str} "
            f"({label}, {n_systems}-system convergence, "
            f"score: {confidence:.2f})",
        ]

        # Evidence chain — one line per contributing event
        lines.append("      Evidence chain:")
        for event in events[:6]:
            sys_abbr = SYSTEM_ABBR.get(event.system, event.system[:3].upper())
            tech_label = TECHNIQUE_LABEL.get(event.technique, event.technique)

            # Truncate description for readability
            desc = event.description
            if len(desc) > 100:
                desc = desc[:97] + "..."

            lines.append(f"        [{sys_abbr}] {tech_label}: {desc}")

        # Convergence metadata
        tech_list = ", ".join(
            TECHNIQUE_LABEL.get(t, t) for t in techniques[:4])
        lines.append(
            f"      Techniques: {tech_list}")
        lines.append(
            f"      Systems: {', '.join(systems)}")

        return "\n".join(lines)

    def _format_compact_prediction(self, conv: Dict) -> str:
        """Compact single-line format for per-house/per-question use."""
        confidence = conv.get("combined_confidence", 0)
        theme = conv.get("theme_consensus", "Unknown")
        systems = conv.get("systems", [])
        conv_date = conv.get("convergence_date")
        events = conv.get("events", [])

        label = _confidence_label(confidence)
        date_str = ""
        if conv_date:
            if isinstance(conv_date, datetime):
                date_str = conv_date.strftime("%b %Y")
            else:
                date_str = str(conv_date)

        # Build compact evidence
        evidence_parts = []
        for event in events[:4]:
            sys_abbr = SYSTEM_ABBR.get(event.system, event.system[:3])
            evidence_parts.append(f"[{sys_abbr}] {event.technique}")

        evidence_str = " + ".join(evidence_parts)

        return (
            f"  • {theme} ({date_str}) — {label} ({confidence:.2f}) — "
            f"{len(systems)} systems: {evidence_str}"
        )

    def _format_contradiction(self, idx: int, contra: Dict) -> str:
        """Format a contradiction for acknowledgement."""
        event_a = contra.get("event_a")
        event_b = contra.get("event_b")
        nature = contra.get("nature", "Unknown")
        resolution = contra.get("resolution_heuristic", "")

        if not event_a or not event_b:
            return f"  [{idx}] Contradiction data incomplete"

        return (
            f"  [{idx}] {nature}: "
            f"{event_a.system}/{event_a.technique} vs "
            f"{event_b.system}/{event_b.technique} — "
            f"Resolution: {resolution}"
        )


def build_citation_chains(convergences: List[Dict],
                          contradictions: List[Dict] = None,
                          top_n: int = 10) -> Dict[str, Any]:
    """Convenience function to build all citation chain formats at once.

    Returns:
        {
            "top_predictions_block": str,   # for Archon main prompt
            "per_house_blocks": Dict[int, str],  # for year chapters
            "formatter": CitationChainFormatter,  # for per-question use
        }
    """
    formatter = CitationChainFormatter(convergences, contradictions)
    return {
        "top_predictions_block": formatter.format_top_predictions(top_n),
        "per_house_blocks": formatter.format_by_house(),
        "formatter": formatter,
    }
