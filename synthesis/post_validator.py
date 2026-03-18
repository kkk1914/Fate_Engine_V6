"""Universal Post-Generation Validator for Archon sections.

Runs on ALL 15 sections + Q&A output to catch and silently fix:
  1. House lord hallucinations (wrong planet assigned to house)
  2. Zodiac system label omissions (missing Western/Vedic labels)
  3. Zodiac system mixing (tropical transit date + sidereal lord in same paragraph)
  4. ZR acute-trigger framing (zodiacal releasing described as daily event)
  5. Hard rule violations (Q&A contradicting Directive constraints)

Each validator follows the same pattern as _validate_degrees_internal:
  - Scan text with regex
  - Compare claims to computed reference data
  - Silently replace errors with correct values
  - Log corrections for audit trail
"""

import re
import logging
from typing import Dict, List, Any, Optional, Tuple

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Constants
# ─────────────────────────────────────────────────────────────────────────────

# All planet names the LLM might use (including aliases)
ALL_PLANETS = [
    "Sun", "Moon", "Mercury", "Venus", "Mars", "Jupiter", "Saturn",
    "Rahu", "Ketu", "Uranus", "Neptune", "Pluto",
]

# Ordinal word → house number mapping
ORDINAL_TO_NUM = {
    "first": 1, "second": 2, "third": 3, "fourth": 4, "fifth": 5,
    "sixth": 6, "seventh": 7, "eighth": 8, "ninth": 9, "tenth": 10,
    "eleventh": 11, "twelfth": 12,
    "1st": 1, "2nd": 2, "3rd": 3, "4th": 4, "5th": 5,
    "6th": 6, "7th": 7, "8th": 8, "9th": 9, "10th": 10,
    "11th": 11, "12th": 12,
}

# Life-domain → house number mapping (for "ruler of your wealth" patterns)
DOMAIN_TO_HOUSE = {
    "wealth": 2, "finance": 2, "finances": 2, "money": 2, "income": 2,
    "financial": 2, "resources": 2,
    "communication": 3, "siblings": 3,
    "home": 4, "property": 4, "real estate": 4, "mother": 4, "roots": 4,
    "children": 5, "creativity": 5, "romance": 5, "fertility": 5,
    "health": 6, "disease": 6, "service": 6, "work": 6,
    "marriage": 7, "partnership": 7, "spouse": 7, "relationships": 7,
    "transformation": 8, "death": 8, "inheritance": 8, "shared resources": 8,
    "higher learning": 9, "spirituality": 9, "dharma": 9, "wisdom": 9,
    "father": 9, "religion": 9,
    "career": 10, "profession": 10, "public life": 10, "reputation": 10,
    "status": 10, "vocation": 10,
    "gains": 11, "friends": 11, "hopes": 11, "aspirations": 11,
    "loss": 12, "isolation": 12, "liberation": 12, "moksha": 12,
    "foreign lands": 12, "expenses": 12,
}

# Vedic context markers (if any of these appear near a claim, use vedic_lords)
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
# 1. House Lord Validator
# ─────────────────────────────────────────────────────────────────────────────

class HouseLordValidator:
    """Detects and silently corrects house lord hallucinations in generated text.

    Uses expanded regex patterns to catch natural-language house lord claims,
    determines zodiac system context, and replaces wrong planets with correct ones.
    """

    def __init__(self, house_lords: Dict[str, Any]):
        """
        Args:
            house_lords: Dict from chart_data["house_lords"] containing:
                western_lords: {1: "Mercury", 2: "Moon", ...}
                vedic_lords:   {1: "Venus", 2: "Mercury", ...}
        """
        self.western_lords = house_lords.get("western_lords", {})
        self.vedic_lords = house_lords.get("vedic_lords", {})

        # Build reverse lookups: planet → list of houses it rules
        self.western_planet_houses = self._build_reverse(self.western_lords)
        self.vedic_planet_houses = self._build_reverse(self.vedic_lords)

        # Planet name pattern for regex (case-insensitive matching)
        planet_names = "|".join(ALL_PLANETS)
        self._planet_pat = f"(?:{planet_names})"

        # Ordinal pattern
        ordinals = "|".join(ORDINAL_TO_NUM.keys())
        self._ordinal_pat = f"(?:{ordinals})"

        # House number pattern: "1st", "2nd", ..., "12th", "1", "2", ..., "12",
        # "first", "second", etc.
        self._house_num_pat = rf"(?:{self._ordinal_pat}|\d{{1,2}})"

        # Domain pattern for "ruler of your wealth" style
        domains = "|".join(sorted(DOMAIN_TO_HOUSE.keys(), key=len, reverse=True))
        self._domain_pat = f"(?:{domains})"

        # Compile the detection patterns
        self._patterns = self._build_patterns()

    @staticmethod
    def _build_reverse(lords: dict) -> dict:
        """Build planet → [house_numbers] reverse lookup."""
        rev = {}
        for house, planet in lords.items():
            rev.setdefault(planet, []).append(int(house))
        return rev

    def _build_patterns(self) -> List[Tuple[re.Pattern, str]]:
        """Build compiled regex patterns for house lord claim detection.

        Each pattern returns groups: (planet_name, house_identifier)
        The format string indicates which group is planet and which is house.
        """
        P = self._planet_pat
        H = self._house_num_pat
        D = self._domain_pat
        patterns = []

        # Pattern 1: "{Planet} is the lord of your {N}th house"
        # Also: "{Planet} is lord of the {N}th house"
        # Also: "{Planet}, lord of the {N}th house"
        # Also: "as {Planet} is the lord of your {N}th house"
        # Also: "{Planet} holds a position as the lord of your {N}th house"
        patterns.append((
            re.compile(
                rf'\b({P})\b[,]?\s+(?:(?:is|holds\s+\w+\s+(?:\w+\s+)?as)\s+)?'
                rf'(?:the\s+)?(?:lord|ruler|master|governor)\s+of\s+'
                rf'(?:the\s+|your\s+)?({H})(?:th|st|nd|rd)?\s*(?:house|bhava)',
                re.IGNORECASE
            ),
            "planet_house"
        ))

        # Pattern 1b: "{Planet} is the lord of your {N}th house" with filler words
        # Catches: "the Sun holds a position of critical importance as the lord of your 5th house"
        patterns.append((
            re.compile(
                rf'\b({P})\b\s+(?:[\w\s,]+?\s+)?'
                rf'(?:as\s+)?(?:the\s+)?(?:lord|ruler|master|governor)\s+of\s+'
                rf'(?:the\s+|your\s+)?({H})(?:th|st|nd|rd)?\s*(?:house|bhava)',
                re.IGNORECASE
            ),
            "planet_house"
        ))

        # Pattern 2: "the {N}th house lord {Planet}" / "the {N}th house lord, {Planet}"
        # Also: "{N}th house lord is {Planet}"
        patterns.append((
            re.compile(
                rf'\b(?:the\s+)?({H})(?:th|st|nd|rd)?\s*(?:house|bhava)\s+'
                rf'(?:lord|ruler),?\s*(?:is\s+)?({P})\b',
                re.IGNORECASE
            ),
            "house_planet"
        ))

        # Pattern 3: "{Planet}, the Vedic/Western ruler of your {domain}"
        # Also: "{Planet}, ruler of your {domain}"
        # Also: "as {Planet} is the Vedic ruler of your {domain}"
        patterns.append((
            re.compile(
                rf'\b({P})\b[,]?\s+(?:is\s+)?(?:the\s+)?'
                rf'(?:Vedic\s+|Western\s+|Tropical\s+|Sidereal\s+)?'
                rf'(?:lord|ruler|master|governor)\s+of\s+(?:the\s+|your\s+)?'
                rf'({D})',
                re.IGNORECASE
            ),
            "planet_domain"
        ))

        # Pattern 4: "{Planet} rules/governs house {N}" or "{Planet} rules the {N}th"
        patterns.append((
            re.compile(
                rf'\b({P})\b\s+(?:rules?|governs?|lords?\s+over)\s+'
                rf'(?:the\s+)?(?:house\s+|H)?({H})(?:th|st|nd|rd)?',
                re.IGNORECASE
            ),
            "planet_house"
        ))

        # Pattern 5: "lord of house {N} is {Planet}" / "lord of the {N}th is {Planet}"
        patterns.append((
            re.compile(
                rf'\blord\s+of\s+(?:the\s+|your\s+)?(?:house\s+)?'
                rf'({H})(?:th|st|nd|rd)?\s+(?:is\s+)?({P})\b',
                re.IGNORECASE
            ),
            "house_planet"
        ))

        return patterns

    def _resolve_house_number(self, raw: str) -> Optional[int]:
        """Convert a raw house identifier to an integer 1-12."""
        raw_lower = raw.lower().strip()
        if raw_lower in ORDINAL_TO_NUM:
            return ORDINAL_TO_NUM[raw_lower]
        try:
            n = int(raw_lower)
            if 1 <= n <= 12:
                return n
        except ValueError:
            pass
        return None

    def _resolve_domain_to_house(self, domain: str) -> Optional[int]:
        """Convert a domain string (e.g., 'wealth') to house number."""
        return DOMAIN_TO_HOUSE.get(domain.lower().strip())

    def _detect_system_context(self, text: str, pos: int) -> str:
        """Detect whether the surrounding context is Vedic or Western.

        Scans ±200 characters around the match position.
        Returns "vedic" or "western" (defaults to "western" if ambiguous).
        """
        start = max(0, pos - 200)
        end = min(len(text), pos + 200)
        window = text[start:end]

        vedic_hits = len(VEDIC_MARKERS.findall(window))
        western_hits = len(WESTERN_MARKERS.findall(window))

        if vedic_hits > western_hits:
            return "vedic"
        elif western_hits > vedic_hits:
            return "western"
        else:
            # Ambiguous — default to vedic since Vedic lords are the more
            # common source of hallucination (sidereal shift confuses LLMs)
            return "vedic"

    def validate_and_fix(self, content: str, sec_num: int = -1) -> str:
        """Scan content for house lord claims and silently fix errors.

        Returns corrected content string.
        """
        corrections = 0

        for pattern, fmt in self._patterns:
            # We need to process matches from end to start to preserve positions
            matches = list(pattern.finditer(content))
            for m in reversed(matches):
                if fmt == "planet_house":
                    claimed_planet = m.group(1)
                    house_raw = m.group(2)
                    house_num = self._resolve_house_number(house_raw)
                elif fmt == "house_planet":
                    house_raw = m.group(1)
                    claimed_planet = m.group(2)
                    house_num = self._resolve_house_number(house_raw)
                elif fmt == "planet_domain":
                    claimed_planet = m.group(1)
                    domain = m.group(2)
                    house_num = self._resolve_domain_to_house(domain)
                else:
                    continue

                if house_num is None:
                    continue

                # Normalize planet name to title case for lookup
                claimed_planet_norm = claimed_planet.strip().title()
                if claimed_planet_norm not in ALL_PLANETS:
                    # Try exact match from the planet list
                    found = False
                    for p in ALL_PLANETS:
                        if p.lower() == claimed_planet_norm.lower():
                            claimed_planet_norm = p
                            found = True
                            break
                    if not found:
                        continue

                # Determine which system to check
                system = self._detect_system_context(content, m.start())
                if system == "vedic":
                    correct_planet = self.vedic_lords.get(house_num)
                    system_label = "Vedic"
                else:
                    correct_planet = self.western_lords.get(house_num)
                    system_label = "Western"

                if correct_planet is None:
                    continue

                # Check if the claimed planet is correct
                if claimed_planet_norm.lower() != correct_planet.lower():
                    # MISMATCH — silently replace planet name in the match
                    original_span = content[m.start():m.end()]

                    # Preserve the original case pattern of the planet name
                    if claimed_planet[0].isupper():
                        replacement_planet = correct_planet.title()
                    else:
                        replacement_planet = correct_planet.lower()

                    # Replace the planet name within the matched span
                    fixed_span = original_span.replace(
                        claimed_planet, replacement_planet, 1
                    )
                    content = content[:m.start()] + fixed_span + content[m.end():]

                    corrections += 1
                    logger.info(
                        f"Sec{sec_num} HOUSE LORD FIX ({system_label}): "
                        f"H{house_num} claimed={claimed_planet} → "
                        f"correct={correct_planet} | "
                        f"context: ...{original_span[:80]}..."
                    )

        if corrections:
            logger.info(
                f"Sec{sec_num}: corrected {corrections} house lord hallucination(s)"
            )
        return content


# ─────────────────────────────────────────────────────────────────────────────
# 2. Zodiac System Labeler
# ─────────────────────────────────────────────────────────────────────────────

class ZodiacSystemLabeler:
    """Inserts system labels when a planet's house differs between Western and Vedic.

    When the report says "Ketu in 1st house" but Western=1st, Vedic=2nd,
    inserts "(Western Tropical)" or "(Vedic Sidereal)" to prevent confusion.
    """

    def __init__(self, house_lords: Dict[str, Any], chart_data: Dict):
        self.discrepancies = house_lords.get("house_discrepancies", [])

        # Build planet → {western_house, vedic_house} from chart data
        self.planet_houses = {}
        w_placements = (chart_data.get("western", {})
                        .get("natal", {}).get("placements", {}))
        v_placements = (chart_data.get("vedic", {})
                        .get("natal", {}).get("placements", {}))

        for planet in ALL_PLANETS:
            w_house = w_placements.get(planet, {}).get("house")
            v_house = v_placements.get(planet, {}).get("house")
            if w_house and v_house and w_house != v_house:
                self.planet_houses[planet] = {
                    "western": int(w_house),
                    "vedic": int(v_house),
                }

    def validate_and_fix(self, content: str, sec_num: int = -1) -> str:
        """Add system labels where planet house placement is ambiguous."""
        if not self.planet_houses:
            return content

        corrections = 0
        for planet, houses in self.planet_houses.items():
            w_h = houses["western"]
            v_h = houses["vedic"]

            # Pattern: "{Planet} in {N}th house" or "{Planet} in the {N}th house"
            # WITHOUT an existing system label nearby
            for house_num, sys_label in [(w_h, "Western Tropical"),
                                         (v_h, "Vedic Sidereal")]:
                ordinals = [str(house_num)]
                for word, num in ORDINAL_TO_NUM.items():
                    if num == house_num:
                        ordinals.append(word)
                ord_pat = "|".join(re.escape(o) for o in ordinals)

                pattern = re.compile(
                    rf'\b({re.escape(planet)})\s+'
                    rf'(?:is\s+)?(?:in\s+|placed\s+in\s+|natally\s+placed\s+in\s+)?'
                    rf'(?:the\s+|your\s+)?'
                    rf'({ord_pat})(?:th|st|nd|rd)?\s*(?:house|bhava)',
                    re.IGNORECASE
                )

                for m in pattern.finditer(content):
                    # Check if a system label already exists within ±50 chars
                    start = max(0, m.start() - 50)
                    end = min(len(content), m.end() + 50)
                    window = content[start:end]

                    has_label = bool(re.search(
                        r'\b(?:Western|Tropical|Vedic|Sidereal)\b',
                        window, re.IGNORECASE
                    ))
                    if not has_label:
                        # Insert system label after "house"
                        insert_pos = m.end()
                        content = (
                            content[:insert_pos]
                            + f" ({sys_label})"
                            + content[insert_pos:]
                        )
                        corrections += 1
                        logger.info(
                            f"Sec{sec_num} SYSTEM LABEL: {planet} H{house_num} "
                            f"→ added ({sys_label})"
                        )
                        break  # Only label first occurrence per planet per system

        if corrections:
            logger.info(
                f"Sec{sec_num}: added {corrections} zodiac system label(s)"
            )
        return content


# ─────────────────────────────────────────────────────────────────────────────
# 3. System Mixing Detector
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
# 4. ZR Framing Validator
# ─────────────────────────────────────────────────────────────────────────────

class ZRFramingValidator:
    """Detects and corrects acute-trigger framing of Zodiacal Releasing.

    ZR defines thematic life chapters lasting months to years.
    The LLM must never frame it as a daily event trigger.
    """

    # Acute trigger phrases that should never co-occur with ZR
    TRIGGER_PHRASES = re.compile(
        r'(?:activat\w+\s+(?:for\s+you\s+)?on\s+'
        r'|fires?\s+on\s+'
        r'|triggers?\s+on\s+'
        r'|kicks?\s+in\s+on\s+'
        r'|hits?\s+on\s+'
        r'|switches?\s+on\s+'
        r'|key\s+turn\w+\s+in\s+a\s+lock'
        r'|alarm\s+clock'
        r'|switch\s+flips?'
        r'|mechanism\s+fires?'
        r'|mechanism\s+activat\w+'
        r'|astrological\s+equivalent\s+of\s+a\s+key'
        r'|ignites?\s+on\s+)',
        re.IGNORECASE,
    )

    # ZR-specific metaphors that are ALWAYS wrong regardless of context
    # (these are exclusively used to describe ZR in practice)
    ZR_EXCLUSIVE_METAPHORS = re.compile(
        r'(?:key\s+turn\w+\s+in\s+a\s+lock'
        r'|astrological\s+equivalent\s+of\s+a\s+key'
        r'|alarm\s+clock\s+(?:for|of)\s+\w+'
        r'|the\s+mechanism\s+activat\w+\s+(?:for\s+you\s+)?on\s+)',
        re.IGNORECASE,
    )

    # ZR mention pattern
    ZR_MENTION = re.compile(
        r'\b(?:zodiacal\s+releas\w+|ZR)\b',
        re.IGNORECASE,
    )

    def validate_and_fix(self, content: str, sec_num: int = -1) -> str:
        """Find ZR + acute trigger co-occurrences and replace with thematic framing."""
        corrections = 0

        # Split into sentences for targeted replacement
        # Use a simple sentence splitter (period + space + capital, or newline)
        sentences = re.split(r'(?<=[.!?])\s+(?=[A-Z])', content)
        fixed_sentences = []

        for sent in sentences:
            has_zr = bool(self.ZR_MENTION.search(sent))
            has_trigger = bool(self.TRIGGER_PHRASES.search(sent))
            # Also catch ZR-exclusive metaphors even without explicit ZR mention
            has_exclusive = bool(self.ZR_EXCLUSIVE_METAPHORS.search(sent))

            if has_exclusive or (has_zr and has_trigger):
                # Replace the trigger sentence with thematic framing
                # Keep any date references but reframe them
                replacement = re.sub(
                    self.TRIGGER_PHRASES,
                    "shifts its thematic emphasis around ",
                    sent,
                    count=1,
                )
                # Also remove "alarm clock" and "key turning" metaphors
                replacement = re.sub(
                    r'(?:the\s+)?(?:astrological\s+)?equivalent\s+of\s+a\s+'
                    r'(?:key\s+turning\s+in\s+a\s+lock|alarm\s+clock|'
                    r'switch\s+flipping)',
                    "a gradual thematic transition",
                    replacement,
                    flags=re.IGNORECASE,
                )
                fixed_sentences.append(replacement)
                corrections += 1
                logger.info(
                    f"Sec{sec_num} ZR FRAMING FIX: replaced acute trigger → "
                    f"thematic framing in: {sent[:80]}..."
                )
            else:
                fixed_sentences.append(sent)

        if corrections:
            logger.info(
                f"Sec{sec_num}: corrected {corrections} ZR acute-trigger framing(s)"
            )
        return " ".join(fixed_sentences)


# ─────────────────────────────────────────────────────────────────────────────
# 5. Hard Rule Enforcer
# ─────────────────────────────────────────────────────────────────────────────

class HardRuleEnforcer:
    """Enforces Part III Directive HARD RULES across Part IV Q&A output.

    Detects when Q&A answers recommend actions that contradict the
    Directive's hard financial/career rules.
    """

    def __init__(self, hard_rules: List[Dict[str, Any]]):
        """
        Args:
            hard_rules: List of dicts, each with:
                rule_text: str — the full rule text
                forbidden_keywords: list[str] — keywords that indicate violation
                allowed_keywords: list[str] — keywords that are acceptable
        """
        self.hard_rules = hard_rules

    @staticmethod
    def parse_hard_rule(rule_text: str) -> Dict[str, Any]:
        """Parse a hard rule string into structured form.

        Extracts forbidden categories from "never" / "do not" clauses
        and allowed categories from "must" / "only" / "directly from" clauses.
        """
        rule_lower = rule_text.lower()
        forbidden = []
        allowed = []

        # Extract forbidden patterns: "never X", "do not X", "avoid X"
        for m in re.finditer(
            r'(?:never|do\s+not|avoid|not\s+from)\s+(.+?)(?:[.;,]|$)',
            rule_lower
        ):
            phrase = m.group(1).strip()
            # Extract key nouns/phrases
            words = [w.strip() for w in re.split(r'\s+(?:or|and|,)\s+', phrase)]
            forbidden.extend(words)

        # Extract allowed patterns: "must derive from X", "only from X", "directly from X"
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
                    # Check if the keyword appears in a permissive/positive context
                    # (not in a warning or caveat)
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
            # Append a constraint note at the end of the Q&A section
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
# 6. Unified Validation Pipeline
# ─────────────────────────────────────────────────────────────────────────────

class PostValidator:
    """Unified post-generation validation pipeline.

    Instantiates all validators once and provides a single entry point
    for validating any section's content.
    """

    def __init__(self, chart_data: Dict, hard_rules: Optional[List[Dict]] = None):
        house_lords = chart_data.get("house_lords", {})

        self.house_lord_validator = HouseLordValidator(house_lords)
        self.system_labeler = ZodiacSystemLabeler(house_lords, chart_data)
        self.mixing_detector = SystemMixingDetector(chart_data)
        self.zr_validator = ZRFramingValidator()
        self.hard_rule_enforcer = HardRuleEnforcer(hard_rules or [])

    def validate_section(self, content: str, sec_num: int = -1,
                         is_qa: bool = False) -> str:
        """Run all applicable validators on a section's content.

        Args:
            content: The generated section text
            sec_num: Section number for logging
            is_qa: If True, also runs hard rule enforcement
        """
        content = self.house_lord_validator.validate_and_fix(content, sec_num)
        content = self.system_labeler.validate_and_fix(content, sec_num)
        content = self.mixing_detector.validate_and_fix(content, sec_num)
        content = self.zr_validator.validate_and_fix(content, sec_num)

        if is_qa:
            content = self.hard_rule_enforcer.validate_and_fix(content, sec_num)

        return content

    def update_hard_rules(self, hard_rules: List[Dict]):
        """Update hard rules after Directive section is generated."""
        self.hard_rule_enforcer = HardRuleEnforcer(hard_rules)
