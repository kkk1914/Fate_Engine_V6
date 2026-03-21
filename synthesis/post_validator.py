"""Universal Post-Generation Validator for Archon sections.

Runs on ALL 15 sections + Q&A output to catch and silently fix:
  1. Zodiac system mixing (tropical transit date + sidereal lord in same paragraph)
  2. ZR acute-trigger framing (zodiacal releasing described as daily event)
  3. Hard rule violations (Q&A contradicting Directive constraints)

HouseLordValidator and ZodiacSystemLabeler have been removed — with strict
JSON Evidence Plans enforced before prose generation, regex-based post-hoc
fixes are no longer needed (per CLAUDE.md: "No Regex Band-Aids").
"""

import re
import logging
from typing import Dict, List, Any, Optional

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Constants
# ─────────────────────────────────────────────────────────────────────────────

# Vedic context markers (used by SystemMixingDetector)
VEDIC_MARKERS = re.compile(
    r'\b(?:Vedic|sidereal|Dasha|Nakshatra|Karaka|Atmakaraka|Amatyakaraka|'
    r'Putrakaraka|Darakaraka|Matrikaraka|Parashari|Jyotish|Vimshottari|'
    r'Bhava|Rashi|Mesha|Vrishabha|Mithuna|Karka|Simha|Kanya|Tula|'
    r'Vrischika|Dhanus|Makara|Kumbha|Meena|Shadbala|Ashtakavarga|'
    r'Tajaka|Kakshya|Upaya|Yoga|Vargottama|Antardasha)\b',
    re.IGNORECASE,
)

# Western context markers
WESTERN_MARKERS = re.compile(
    r'\b(?:Western|tropical|Placidus|Primary Direction|Solar Arc|'
    r'Solar Return|Lunar Return|Profection|Firdaria)\b',
    re.IGNORECASE,
)


# ─────────────────────────────────────────────────────────────────────────────
# 1. System Mixing Detector
# ─────────────────────────────────────────────────────────────────────────────

class SystemMixingDetector:
    """Detects paragraphs that mix Western transit dates with Vedic rulerships.

    When found, inserts a system boundary note for transparency.
    """

    def __init__(self, chart_data: Dict):
        # Extract known Western transit dates for detection
        self.transit_dates = set()
        outer_aspects = (chart_data.get("western", {})
                         .get("predictive", {})
                         .get("outer_transit_aspects", []))
        if isinstance(outer_aspects, list):
            for asp in outer_aspects:
                if isinstance(asp, dict):
                    for key in ("exact_date", "entry_date", "exit_date"):
                        d = asp.get(key, "")
                        if d:
                            self.transit_dates.add(str(d)[:10])

        # Western vs Vedic lords for quick lookup
        house_lords = chart_data.get("house_lords", {})
        self.western_lords = house_lords.get("western_lords", {})
        self.vedic_lords = house_lords.get("vedic_lords", {})

        # Find houses where lords differ between systems
        self.differing_houses = {}
        for h in range(1, 13):
            w = self.western_lords.get(h, "")
            v = self.vedic_lords.get(h, "")
            if w and v and w.lower() != v.lower():
                self.differing_houses[h] = {"western": w, "vedic": v}

    def validate_and_fix(self, content: str, sec_num: int = -1) -> str:
        """Detect and annotate paragraphs mixing tropical transit dates with sidereal lords."""
        if not self.transit_dates or not self.differing_houses:
            return content

        paragraphs = content.split("\n\n")
        corrections = 0
        fixed_paragraphs = []

        for para in paragraphs:
            # Check if paragraph contains a Western transit date
            has_transit_date = any(d in para for d in self.transit_dates)
            if not has_transit_date:
                fixed_paragraphs.append(para)
                continue

            # Check if same paragraph contains a Vedic-context house lord claim
            has_vedic_context = bool(VEDIC_MARKERS.search(para))
            if not has_vedic_context:
                fixed_paragraphs.append(para)
                continue

            # Mixing detected — add a system boundary note at end of paragraph
            # Only add if not already annotated
            if "system boundary" not in para.lower() and "coordinate system" not in para.lower():
                note = (
                    " *(Note: The transit date above uses the Western Tropical "
                    "zodiac; the house lordship cited uses the Vedic Sidereal "
                    "system, which shifts positions by approximately 24°.)*"
                )
                para = para.rstrip() + note
                corrections += 1
                logger.info(
                    f"Sec{sec_num} SYSTEM MIXING: annotated paragraph with "
                    f"tropical transit + Vedic lord"
                )

            fixed_paragraphs.append(para)

        if corrections:
            logger.info(
                f"Sec{sec_num}: annotated {corrections} mixed-system paragraph(s)"
            )
        return "\n\n".join(fixed_paragraphs)


# ─────────────────────────────────────────────────────────────────────────────
# 3. Hard Rule Enforcer
# ─────────────────────────────────────────────────────────────────────────────

class HardRuleEnforcer:
    """Enforces Part III Directive HARD RULES across Part IV Q&A output.

    Detects when Q&A answers recommend actions that contradict the
    Directive's hard financial/career rules.
    """

    def __init__(self, hard_rules: List[Dict[str, Any]]):
        self.hard_rules = hard_rules

    @staticmethod
    def parse_hard_rule(rule_text: str) -> Dict[str, Any]:
        """Parse a hard rule string into structured form."""
        rule_lower = rule_text.lower()
        forbidden = []
        allowed = []

        for m in re.finditer(
            r'(?:never|do\s+not|avoid|not\s+from)\s+(.+?)(?:[.;,]|$)',
            rule_lower
        ):
            phrase = m.group(1).strip()
            words = [w.strip() for w in re.split(r'\s+(?:or|and|,)\s+', phrase)]
            forbidden.extend(words)

        for m in re.finditer(
            r'(?:must\s+(?:derive|come|originate)\s+(?:from|through)|'
            r'only\s+(?:from|through)|directly\s+from)\s+(.+?)(?:[.;,]|$)',
            rule_lower
        ):
            phrase = m.group(1).strip()
            words = [w.strip() for w in re.split(r'\s+(?:or|and|,)\s+', phrase)]
            allowed.extend(words)

        return {
            "rule_text": rule_text,
            "forbidden_keywords": [f for f in forbidden if len(f) > 2],
            "allowed_keywords": [a for a in allowed if len(a) > 2],
        }

    def validate_and_fix(self, content: str, sec_num: int = -1) -> str:
        """Check Q&A content for hard rule violations. Append notes where found."""
        if not self.hard_rules:
            return content

        violations_found = 0
        content_lower = content.lower()

        for rule in self.hard_rules:
            forbidden = rule.get("forbidden_keywords", [])
            rule_text = rule.get("rule_text", "")

            for keyword in forbidden:
                if keyword.lower() in content_lower:
                    kw_pattern = re.compile(
                        rf'(?:will|should|expect|promising|likely|indicates?|'
                        rf'anticipate|promising|opportunity\s+for|'
                        rf'window\s+for)\s+.*?\b{re.escape(keyword)}\b',
                        re.IGNORECASE
                    )
                    if kw_pattern.search(content):
                        violations_found += 1
                        logger.warning(
                            f"Sec{sec_num} HARD RULE VIOLATION: "
                            f"Q&A promotes '{keyword}' which contradicts: "
                            f"{rule_text[:100]}..."
                        )

        if violations_found > 0:
            note = (
                "\n\n*Note: The specific financial pathways described above "
                "should be evaluated in context of the chart's structural "
                "wealth rules established in the Directive section. Consult "
                "a qualified financial advisor before making major financial "
                "decisions.*"
            )
            if note.strip() not in content:
                content = content.rstrip() + note
            logger.info(
                f"Sec{sec_num}: flagged {violations_found} hard rule violation(s)"
            )

        return content


# ─────────────────────────────────────────────────────────────────────────────
# 4. Unified Validation Pipeline
# ─────────────────────────────────────────────────────────────────────────────

class PostValidator:
    """Unified post-generation validation pipeline.

    Instantiates all validators once and provides a single entry point
    for validating any section's content.
    """

    def __init__(self, chart_data: Dict, hard_rules: Optional[List[Dict]] = None):
        self.mixing_detector = SystemMixingDetector(chart_data)
        self.hard_rule_enforcer = HardRuleEnforcer(hard_rules or [])

    def validate_section(self, content: str, sec_num: int = -1,
                         is_qa: bool = False) -> str:
        """Run all applicable validators on a section's content."""
        content = self.mixing_detector.validate_and_fix(content, sec_num)

        if is_qa:
            content = self.hard_rule_enforcer.validate_and_fix(content, sec_num)

        return content

    def update_hard_rules(self, hard_rules: List[Dict]):
        """Update hard rules after Directive section is generated."""
        self.hard_rule_enforcer = HardRuleEnforcer(hard_rules)
