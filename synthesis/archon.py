
"""
Archon v2 — The Celestial Dossier
Master narrative architect for the 15-Section premium astrological report.

STRUCTURE:
  PART I:   THE NATIVITY     (5 sections — natal portrait)
  PART II:  THE ALMANAC      (7 sections — current config + 5 year chapters + 15yr arc map)
  PART III: THE DIRECTIVE    (2 sections — mandate and warning)
  PART IV:  YOUR QUESTIONS   (1 section — generated only when questions submitted)

UPGRADE FROM v1:
  v1: 10 chapters; predictive split by domain (finances/career/health × 3 years)
  v2: 15 sections; year-by-year chapters 2026–2030 (full-domain per year) +
      15-year window arc map + Oracle Opening hook + Current Configuration bridge
"""

import logging
import json
import re
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional

from experts.gateway import gateway
from config import settings
from synthesis.qa_pipeline import QAPipeline
from synthesis.post_validator import PostValidator, HardRuleEnforcer

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Section Definitions
# ─────────────────────────────────────────────────────────────────────────────

SECTION_DEFS = {

    # ── PART I: THE NATIVITY ─────────────────────────────────────────────────

    0: {
        "id": "oracle_opening",
        "part": "I",
        "title": "THE ORACLE'S OPENING",
        "header": "◈ THE ORACLE'S OPENING",
        "type": "oracle",
        "words": (200, 230),
        "focus": (
            "Cold read. 5-6 surgical observations. NO explanation, NO astrology, NO jargon. "
            "Each sentence names a behavior, compulsion, or wound that would make the reader say "
            "'how does it know that?' about their private self. "
            "NOT personality description — behavioral tells. The things they do in private. "
            "The patterns they haven't named yet. "
            "FINAL SENTENCE ONLY: the core paradox of this chart in plain language. "
            "Format: 'The trap is: [specific paradox that could only be this person].'\n\n"
            "GROUNDING RULE (internal — do NOT show this reasoning in output):\n"
            "Before writing each observation, mentally identify which specific placement "
            "(planet, sign, house, aspect) drives it. If you cannot name the placement, "
            "do NOT write the observation — it is a generic projection, not a chart reading. "
            "Every sentence must be derivable from THIS chart's specific configurations. "
            "A correct oracle for Sun-Cancer-Moon-Capricorn should read differently from "
            "Sun-Aries-Moon-Libra. If swapping the signs wouldn't change your sentence, delete it."
        ),
        "domains": [],
    },

    1: {
        "id": "architecture_of_self",
        "part": "I",
        "title": "I. THE ARCHITECTURE OF SELF",
        "header": "I. THE ARCHITECTURE OF SELF",
        "type": "natal",
        "words": (420, 480),
        "focus": (
            "BLUEPRINT — not a portrait. Oracle already painted the human picture. "
            "This section explains the MECHANICS. "
            "Use 4-6 labeled mechanisms with bold headers. Each mechanism: "
            "[NAME] → placement evidence → what this produces in real life (behavior/outcome). "
            "Every claim needs a consequence: 'X placement PRODUCES/CREATES/FORCES Y in real life.' "
            "MANDATORY: Include at least one mechanism named as a clear STRENGTH "
            "(e.g. **THE STRUCTURAL AUTHORITY**, **THE COMMUNICATION GIFT**). "
            "State what Saturn-as-dignified-Almuten actually BUILDS over a lifetime. "
            "Cover: core identity engine (Sun+Moon+Asc), the authority structure (Almuten/Saturn), "
            "the mind's specific pattern (Mercury), the soul curriculum (Atmakaraka). "
            "Include fixed star parans if present — named as fate signatures. "
            "Final sentence: the chart's single greatest structural advantage in plain language.\n\n"
            "CROSS-SECTION OWNERSHIP RULES — THIS SECTION OWNS:\n"
            "  • Saturn/Almuten as Structural Authority — explain it fully HERE and ONLY HERE.\n"
            "  • The Sun/Moon/Asc identity triad\n"
            "  • Mercury's mental pattern\n"
            "  • Atmakaraka soul curriculum\n"
            "SECTIONS 2, 3, 4 MUST NOT re-explain these. They may reference them in ONE sentence max.\n"
            "DO NOT include: relationship patterns, wealth accumulation advice, karmic debt discussion "
            "— those belong in their respective sections.\n"
            "ADVICE FORMAT: Weave practical implication into 'What this means' prose naturally. "
            "Do NOT add a separate 'What to do with it' heading or bullet list."
        ),
        "domains": ["Sun", "Moon", "Ascendant", "Atmakaraka", "Fixed Stars", "Almuten"],
    },

    2: {
        "id": "material_world",
        "part": "I",
        "title": "II. THE MATERIAL WORLD",
        "header": "II. THE MATERIAL WORLD",
        "type": "natal",
        "words": (420, 480),
        "focus": (
            "Use 4-5 labeled mechanisms with bold headers. Blueprint format, not essay. "
            "Each mechanism: [NAME] → placement → real-world financial/career consequence. "
            "REQUIRED opening: The WEALTH CAPACITY BLOCK appears verbatim at the top, "
            "before any mechanism. It is provided in the section data — reproduce it exactly as shown. "
            "Do NOT add any numerical score or rating — only the tier label (HIGH, MODERATE, etc). "
            "REQUIRED mechanisms (after the score block): "
            "(1) THE INCOME ENGINE — exactly how this chart generates money. "
            "Name specific industries where this chart is competitive (from FINANCIAL PROFILE). "
            "(2) THE CAREER DESIGN — the specific career structure that will WORK, including industry domain. "
            "(3) THE WEALTH TRAP — the one financial pattern that sabotages income. "
            "State it as a named pattern and its consequence, not a generic warning. "
            "(4) THE LEGACY ASSET — what specifically gets built over decades. Concrete: "
            "what product, institution, or IP does this chart produce?\n\n"
            "CROSS-SECTION OWNERSHIP RULES — THIS SECTION OWNS:\n"
            "  • Income mechanics, wealth channels, industry fit\n"
            "  • Career structure and MC/Amatyakaraka design\n"
            "  • The Lot of Fortune's wealth function\n"
            "DO NOT re-explain: Saturn/Almuten identity (covered in section 1 — one sentence reference max). "
            "DO NOT include: relationship content, karmic debt, spiritual path.\n"
            "ADVICE FORMAT: Weave practical implication into mechanism prose naturally — "
            "e.g. 'This is why roles where your income is tied to how well you explain things "
            "will outperform those where it is not.' "
            "Do NOT add a separate 'What to do with it' heading or bullet list."
        ),
        "domains": ["House 2", "MC", "Saturn", "Lot of Fortune", "Amatyakaraka", "Useful God"],
    },

    3: {
        "id": "inner_world",
        "part": "I",
        "title": "III. THE INNER WORLD",
        "header": "III. THE INNER WORLD",
        "type": "natal",
        "words": (420, 480),
        "focus": (
            "Use 4-5 labeled mechanisms with bold headers. Blueprint format. "
            "Each mechanism: [NAME] → placement → what it compels → real-world relationship or health outcome. "
            "REQUIRED mechanisms: "
            "(1) THE LOVE PATTERN — what Venus+Darakaraka is designed for. "
            "Name the specific type of partner who would WORK for this chart. "
            "(2) THE RELATIONAL DESIGN — what the 7th house and Descendant are built to give and receive. "
            "What does genuine compatibility look like for this specific chart? "
            "(3) THE PHYSICAL CONSTITUTION — 2-3 specific vulnerabilities AND the body's innate strengths. "
            "(4) THE HEALING MECHANISM — the concrete behavior or practice that converts the wound into skill.\n\n"
            "CROSS-SECTION OWNERSHIP RULES — THIS SECTION OWNS:\n"
            "  • Relationships, love patterns, relational design\n"
            "  • Physical constitution and health\n"
            "  • The Moon's emotional architecture (as it affects relationships and body — NOT as identity)\n"
            "DO NOT re-explain: Saturn/Almuten authority (one sentence max), "
            "communication gifts (one sentence max), karmic Node curriculum (belongs in section 4).\n"
            "DO NOT include: wealth advice, career structure, karmic debt framing.\n"
            "BALANCE: The inner world contains genuine capacity for love and connection — name it "
            "alongside the challenge. Do not make every mechanism a wound or trap.\n"
            "ADVICE FORMAT: Weave practical implication into mechanism prose naturally. "
            "Do NOT add a separate 'What to do with it' heading or bullet list."
        ),
        "domains": ["Venus", "Mars", "Moon", "Darakaraka", "House 6", "House 7", "Constitution"],
    },

    4: {
        "id": "karmic_mandate",
        "part": "I",
        "title": "IV. THE KARMIC MANDATE",
        "header": "IV. THE KARMIC MANDATE",
        "type": "natal",
        "words": (380, 440),
        "focus": (
            "The WHY of this incarnation. Elevated tone but still outcome-anchored. "
            "Name the karmic debt (South Node — the default pattern being overused and why it fails), "
            "the karmic payment required (North Node — the specific behavior and attitude change demanded), "
            "the Atmakaraka curriculum (what the soul is here to MASTER — frame as a GIFT, not a burden), "
            "the current dasha arc: State (a) what Ketu is stripping and why, "
            "(b) WHAT THE VENUS DASHA THAT FOLLOWS WILL BUILD — concrete outcomes. "
            "The Ketu period is preparation. The reader must understand what they are being prepared FOR. "
            "End with: the karmic DESTINATION — what this life builds toward in its final form, "
            "stated as a positive fate.\n\n"
            "CROSS-SECTION OWNERSHIP RULES — THIS SECTION OWNS:\n"
            "  • The Nodes (South Node pattern, North Node mandate)\n"
            "  • Dasha arc and what it is preparing the person for\n"
            "  • Syzygy and Lot of Spirit\n"
            "  • Spiritual path and karmic destination\n"
            "DO NOT re-explain: Saturn/Almuten (name only, one sentence max), "
            "communication gifts (one sentence max), relationship design (covered in section 3).\n"
            "DO NOT include: wealth advice, career structure, or relationship advice.\n"
            "CAUSAL LANGUAGE: 'The South Node costs X. The North Node builds Y. The Venus dasha delivers Z.'\n"
            "ADVICE FORMAT: Weave spiritual and practical guidance into prose naturally. "
            "Do NOT add a separate 'What to do with it' heading or bullet list. "
            "End with one sentence on the karmic destination — specific, positive, concrete."
        ),
        "domains": ["Nodes", "Ketu", "Atmakaraka", "Lot of Spirit", "Syzygy", "Fixed Stars"],
    },

    # ── PART II: THE ALMANAC ─────────────────────────────────────────────────

    5: {
        "id": "current_configuration",
        "part": "II",
        "title": "◈ THE CURRENT CONFIGURATION",
        "header": "◈ THE CURRENT CONFIGURATION",
        "type": "current",
        "words": (130, 160),
        "focus": (
            "Where are we RIGHT NOW? A weather briefing, not a forecast. "
            "State: active Maha Dasha + Antardasha, current profection year + time lord, "
            "dominant outer transit in effect today. "
            "Three sentences max. Dense and precise. "
            "End with the single question this year is asking the native."
        ),
        "domains": ["Maha Dasha", "Profection", "Current Transits"],
    },

    # ── PART II: THE ALMANAC — YEAR CHAPTERS (2026–2030) ─────────────────────

    6: {
        "id": "year_2026",
        "part": "II",
        "title": "YEAR 2026",
        "header": "YEAR 2026",
        "type": "year_forecast",
        "target_year": 2026,
        "words": (580, 640),
        "focus": (
            "Full-domain year forecast for 2026. Cover: career/finance (what is available and what is tested), "
            "relationships (what is activated), health (what demands attention), and the most important "
            "single action this year demands. Lead with the year's highest-confidence window. "
            "Name both the peak opportunity window and the peak pressure window explicitly."
        ),
        "domains": ["All 2026 storm windows", "Profection 2026", "Tajaka 2026", "Liu Nian 2026", "Outer transits 2026"],
    },

    7: {
        "id": "year_2027",
        "part": "II",
        "title": "YEAR 2027",
        "header": "YEAR 2027",
        "type": "year_forecast",
        "target_year": 2027,
        "words": (580, 640),
        "focus": (
            "Full-domain year forecast for 2027. Cover: career/finance, relationships, health, "
            "and the single most important action 2027 demands. Lead with the highest-confidence window. "
            "Name both peak opportunity and peak pressure windows explicitly."
        ),
        "domains": ["All 2027 storm windows", "Profection 2027", "Tajaka 2027", "Liu Nian 2027", "Outer transits 2027"],
    },

    8: {
        "id": "year_2028",
        "part": "II",
        "title": "YEAR 2028",
        "header": "YEAR 2028",
        "type": "year_forecast",
        "target_year": 2028,
        "words": (580, 640),
        "focus": (
            "Full-domain year forecast for 2028. Cover: career/finance, relationships, health, "
            "and the single most important action 2028 demands. Lead with the highest-confidence window. "
            "Name both peak opportunity and peak pressure windows explicitly."
        ),
        "domains": ["All 2028 storm windows", "Profection 2028", "Tajaka 2028", "Liu Nian 2028", "Outer transits 2028"],
    },

    9: {
        "id": "year_2029",
        "part": "II",
        "title": "YEAR 2029",
        "header": "YEAR 2029",
        "type": "year_forecast",
        "target_year": 2029,
        "words": (580, 640),
        "focus": (
            "Full-domain year forecast for 2029. Cover: career/finance, relationships, health, "
            "and the single most important action 2029 demands. Lead with the highest-confidence window. "
            "Name both peak opportunity and peak pressure windows explicitly."
        ),
        "domains": ["All 2029 storm windows", "Profection 2029", "Tajaka 2029", "Liu Nian 2029", "Outer transits 2029"],
    },

    10: {
        "id": "year_2030",
        "part": "II",
        "title": "YEAR 2030",
        "header": "YEAR 2030",
        "type": "year_forecast",
        "target_year": 2030,
        "words": (580, 640),
        "focus": (
            "Full-domain year forecast for 2030. Cover: career/finance, relationships, health, "
            "and the single most important action 2030 demands. Lead with the highest-confidence window. "
            "Name both peak opportunity and peak pressure windows explicitly."
        ),
        "domains": ["All 2030 storm windows", "Profection 2030", "Tajaka 2030", "Liu Nian 2030", "Outer transits 2030"],
    },

    # ── PART II: THE ALMANAC — 15-YEAR ARC MAP ───────────────────────────────

    11: {
        "id": "almanac_summary",
        "part": "II",
        "title": "◈ THE FIFTEEN-YEAR WINDOW MAP",
        "header": "◈ THE FIFTEEN-YEAR WINDOW MAP",
        "type": "almanac_summary",
        "words": (800, 1000),
        "focus": (
            "A PRECISE DATE-ANCHORED TIMELINE of the 12-16 most significant windows across 2026–2040. "
            "You have been given computed storm windows, profection years, outer transit hits, "
            "primary directions, solar returns, dashas, ZR phases, and Bazi pillars. "
            "USE THE COMPUTED DATA. Do not invent windows or import general transit knowledge. "
            "Every window must cite its EXACT date range from the data, the specific planets involved, "
            "and which techniques from which systems agree on it.\n\n"
            "FORMAT each entry EXACTLY as:\n\n"
            "**[MONTH YEAR – MONTH YEAR]** · [CONFIDENCE LABEL]\n"
            "[3-4 sentences. SENTENCE 1: what is happening — name the specific planets "
            "and their exact relationship to this chart (e.g. 'Saturn crosses your Ascendant '  "
            "'while Jupiter stations in your 2nd house'). "
            "SENTENCE 2: what this means for the specific domains of life being activated. "
            "SENTENCE 3: the most likely concrete event in this person's life — be specific "
            "(e.g. 'This is the primary window for your first mortgage application' or "
            "'Your private practice registration opens here'). "
            "SENTENCE 4 (if storm window): what the convergence score and systems mean for confidence.]\n"
            "Technique citations: [list 2-4 specific techniques: e.g. Saturn→ASC transit | "
            "Profection H1 | Vimshottari Venus AD | ZR Fortune Scorpio]\n\n"
            "---\n\n"
            "Rules:\n"
            "— Sort chronologically 2026–2040.\n"
            "— Only include NEAR-CERTAIN and HIGH-CONFIDENCE windows.\n"
            "— NEAR-CERTAIN (≥0.85 convergence) maximum 2 entries.\n"
            "— Each window MUST cite at least 2 specific techniques from the data block.\n"
            "— Name the profection house for each year: e.g. '2026 = House 10 profection year → Jupiter TL'.\n"
            "— Name the active Vimshottari Dasha period for each window.\n"
            "— Where a Bazi pillar clashes or combines with the Day Master, name it.\n"
            "— Do NOT repeat natal character analysis. This is a forecast, not a portrait.\n\n"
            "After all windows: one dense paragraph **The Chain** showing how each window "
            "creates the conditions for the next — explicit causal links connecting home, "
            "family, career, and wealth across the full arc 2026–2040. "
            "This paragraph must reference specific years by name and explain why the sequence "
            "matters: not just 'Window A leads to Window B' but specifically HOW and WHY."
        ),
        "domains": ["All storm windows 2026–2040", "Profections", "Primary Directions", "Outer Transits"],
    },

    # ── PART III: THE DIRECTIVE ───────────────────────────────────────────────

    12: {
        "id": "directive",
        "part": "III",
        "title": "◈ THE FIFTEEN-YEAR DIRECTIVE",
        "header": "◈ THE FIFTEEN-YEAR DIRECTIVE",
        "type": "directive",
        "words": (280, 340),
        "focus": (
            "Three elements, in this order:\n"
            "1. THE RED THREAD: One sentence only. Must name the specific Sun/Moon/Asc combination "
            "and the core paradox. Could ONLY be written about this exact chart. "
            "No vague spiritual language.\n"
            "2. THE FIFTEEN-YEAR ORDERS: One concrete, dated, technical action per year 2026–2040. "
            "Group into three 5-year phases if helpful. "
            "Reads like orders, not suggestions. Name the technique, the window, the practice.\n"
            "3. No padding. No encouragement. Only the mandate."
        ),
        "domains": ["Synthesis", "Red Thread", "Dated Actions"],
    },

    13: {
        "id": "warning",
        "part": "III",
        "title": "◈ THE WARNING",
        "header": "◈ THE WARNING",
        "type": "directive",
        "words": (180, 220),
        "focus": (
            "ONE configuration. The specific planetary setup that creates the greatest risk "
            "for this chart. Name: what the planets are, when it peaks (exact date window), "
            "what it destroys if ignored, what it builds if used correctly. "
            "No softening. No generic warnings. Only what is specific to this chart."
        ),
        "domains": ["Peak Risk", "Configuration", "Timing"],
    },

    # ── PART IV: YOUR QUESTIONS ───────────────────────────────────────────────
    # This is the primary deliverable when questions are submitted.
    # Each answer gets full natal + predictive + storm window data routed to it.
    14: {
        "id": "questions",
        "part": "IV",
        "title": "◈ YOUR QUESTIONS ANSWERED",
        "header": "◈ YOUR QUESTIONS ANSWERED",
        "type": "questions",
        "words": (350, 500),  # per question — expanded for depth
        "focus": (
            "Answer each question with precision and depth. Each answer must:\n"
            "1. State a direct verdict in the first sentence (yes/no/when/what form). No hedging.\n"
            "2. Name the 2-3 specific astrological mechanisms that determine this outcome "
            "   — technique name, exact evidence, and what it implies.\n"
            "3. Give the SPECIFIC timing windows that are most relevant to this question — "
            "   drawn from the TEMPORAL STORM WINDOWS data in the prompt. Cite exact date ranges.\n"
            "4. Distinguish between what is near-certain vs. what is probable. If 3+ systems "
            "   agree on a window, say so. If only 1 system flags it, say that too.\n"
            "5. End with a concrete, dated action the person should take.\n"
            "ALL DATES CITED MUST BE AFTER TODAY'S DATE (provided in the data block). "
            "If a window has already passed, do not cite it."
        ),
        "domains": ["User Questions", "All timing data", "Storm windows", "Natal mechanisms"],
    },
}


# ─────────────────────────────────────────────────────────────────────────────
# System Prompts per section type
# ─────────────────────────────────────────────────────────────────────────────

ORACLE_PROMPT = """You are a senior consulting astrologer, opening a premium astrological dossier with a cold read.

Write THE ORACLE'S OPENING for this specific chart.

WHAT THIS SECTION IS: A cold read. Not an essay. Not an introduction. Five to six razor-sharp
observations that make the reader feel seen — the "how does it know that?" shock. No explanation,
no build-up, no astrology. Pure recognition. Like a stranger reading your mail.

ABSOLUTE RULES:
1. ZERO astrological jargon. Zero. No sign names, no house numbers, no technique names.
   Not even in passing. This section is written for someone who knows nothing about astrology.
2. Each sentence is a standalone observation about behavior, compulsion, or wound.
   Short. Precise. Surgical. No sentence longer than 30 words.
3. DO NOT EXPLAIN WHY. The Architecture of Self section explains the mechanics.
   Oracle only names what it sees. No "because your Mercury..." allowed.
4. Every observation must describe a SPECIFIC BEHAVIOR that is testable and observable —
   not an internal feeling state. NOT "you feel pressure to justify your existence" (unfalsifiable).
   YES: "You explain your feelings instead of feeling them — and you mistake the explanation for intimacy."
   NOT: "You struggle with emotions." YES: "You reorganize physical spaces when anxious."
   The test: could a roommate or partner CONFIRM this observation? If not, it's too vague.
5. BANNED WORDS: journey, tapestry, dance, explore, cosmic, realm, energy, vibration, deeply, truly.
   USE INSTEAD: compulsion, trap, hunger, pattern, engine, wound, debt, demand, cost, pressure, precision,
   instinct, architecture, capacity, design, asset, blueprint.
6. BALANCE RULE: At least one of your 5-6 observations must name a genuine, specific strength —
   something this person does that most people cannot. Not a softening compliment.
   A precise observation of genuine capacity. Example: "You can hold the structure of an argument
   in your head longer than anyone in the room — and you know exactly when to deploy it."
7. LENGTH: 200-230 words. Short. Every word earns its place.
8. FINAL SENTENCE: The core paradox. One sentence. Could only be this exact person.
   Format: "The trap is: [plain English paradox that is unique to this chart]."
8. Start with: # ◈ THE ORACLE'S OPENING

EXAMPLE OF THE RIGHT TONE (for a different chart — do not copy, only match the precision):
"You are the most capable person in most rooms you enter, and you know it, and it exhausts you.
You rehearse conversations before they happen. You edit what you say in real time.
You have a version of yourself that is always performing, and you cannot remember when it started.
Intimacy frightens you not because you don't want it but because you don't know how to stop performing long enough to have it.
You protect people from your real opinions, then resent them for not knowing what those opinions are.
The trap is: you are brilliant at building connection and terrified of what happens if someone actually gets close enough to see you clearly.\""""

NATAL_PROMPT = """You are a senior consulting astrologer, master synthesizer of four astrological systems writing a premium astrological dossier.

WHAT THIS SECTION IS: A translation layer. Your reader already lived through this chart.
They don't need to learn astrology. They need to understand themselves.
Your job is to take the technical evidence and convert it into plain-English insight
and integrated practical guidance — the kind that makes someone say "this explains everything."

THE GOLDEN RATIO:
  20% astrological evidence (the proof — brief, specific, cited)
  80% what this means and what follows from it (no jargon — integrated prose)

MANDATORY FORMAT FOR EACH MECHANISM:

  **[NAME OF THE MECHANISM]**
  *Evidence:* [One sentence maximum. Planet, placement, aspect. That's it.]
  **What this means:** [3-5 sentences. Zero jargon. No planet names unless unavoidable.
  Write as if explaining to a sharp friend. What is their actual experience of this?
  What patterns does it produce in their life? What does it cost them, AND what does it build?
  Integrate practical implication naturally into the final sentence — e.g.:
  "This is why [concrete life situation] — and why [specific approach] works better for you
  than [common alternative]." DO NOT add a separate "What to do with it:" heading.
  The advice lives inside the meaning, not below it.]

MANDATORY DEDUPLICATION — READ BEFORE WRITING:
  • SATURN / STRUCTURAL AUTHORITY: Explained in full in Section I (Architecture of Self) ONLY.
    In all other sections: ONE sentence of reference maximum.
    Example: "Saturn's structural advantage — already described — compounds here because..."
    NEVER re-explain it. NEVER repeat the full mechanism text.
  • GEMINI / COMMUNICATION GIFT: Explained in Section I. Do not repeat.
    Reference once if genuinely needed: "The communication channel already described..."
  • NORTH NODE / KARMIC PATH: Explained in Section IV. Do not repeat in Sections I, II, III.
  • LOT OF FORTUNE: Use ONLY the degree from MANDATORY NATAL DATA. Do not substitute the
    Ascendant degree even if they share the same sign. They are different points.

MANDATORY BALANCE RULE:
  Out of 4-6 mechanisms, AT LEAST 2 must be named as genuine strengths.
  Not "gift with a cost" — flat-out advantages this chart has that most people don't.
  Challenge mechanisms must end with: what strength this pressure builds + when it converts to asset.

ADDITIONAL RULES:
1. USE EXACT DEGREES from the MANDATORY NATAL DATA block. In evidence line only. Never invent.
2. Synthesize ALL FOUR SYSTEMS in one voice — one mechanism can draw from multiple systems.
3. WHEN SYSTEMS CONFLICT, STATE IT plainly: "Eastern astrology reads this as X, Western as Y —
   the real experience is both at once." Then explain what that feels like practically.
4. BANNED IN MEANING SECTIONS: planet names, sign names, house numbers, degree citations,
   technique jargon, Latin terms, Sanskrit terms. The evidence line gets all the technical language.
   Everything after "What this means:" must be readable by someone with zero astrology knowledge.
5. LENGTH: 480-560 words total.
6. START with exactly: # {HEADER}
7. Bold key terms only in evidence line: **Atmakaraka**, **Amatyakaraka**, **Almuten**, **Hyleg**
8. When Bazi shows UNAVAILABLE: omit Saju claims entirely.
9. END with one sentence in completely plain language: the single biggest practical takeaway
   from this section — written so a stranger immediately understands the life consequence."""

YEAR_FORECAST_PROMPT = """You are a senior consulting astrologer, writing the predictive almanac section of a premium astrological dossier.

THE FUNDAMENTAL RULE:
People read predictive reports to know what will happen. State the events first.
Explain the astrology second. Never bury a prediction inside a technique explanation.

MANDATORY STRUCTURE:

**{YEAR}: [3–5 word title]**

**What is most likely to happen in {YEAR}:**
3-4 sentences in plain English. No technique names. No jargon.
State the probable events directly — what happens to this person in career, relationships, health, finances.
This is the HEADLINE. The reader must be able to read only this block and understand their year.

**The mechanics — how and when:**
List windows chronologically. For EACH window, state all three:
  "DATE RANGE: [what probably happens in plain English]
   Certainty: [NEAR-CERTAIN / HIGH-CONFIDENCE / MODERATE-CONFIDENCE / LOW-CONFIDENCE]
   — [X] systems agree: [Western], [Vedic], [Saju], [Hellenistic] (list only those that apply)
   Why: [technique attribution with exact date]
   Action: [specific, dated instruction]"

━━━ NEAR-CERTAIN FREQUENCY CAP ━━━
NEAR-CERTAIN is reserved for: convergence_score ≥ 0.85 AND 3+ systems agreeing.
Each year section may contain AT MOST ONE NEAR-CERTAIN label.
If you label two windows near-certain in the same year, downgrade the lower-scoring one to HIGH-CONFIDENCE.
Overuse of NEAR-CERTAIN destroys its meaning. Use it surgically.

━━━ CRITICAL — CONVERGENCE SCORE PROTOCOL ━━━
The TEMPORAL STORM WINDOWS data includes a convergence_score and confidence_label.
YOU MUST name the certainty level for each window. This is the core upgrade.

LANGUAGE CALIBRATION BY CONFIDENCE LABEL:

NEAR-CERTAIN (score ≥ 0.85):
  "[Date range] is the highest-confidence window of {YEAR}. [X] independent systems
  converge here — [Western], [Vedic], [Saju], [Hellenistic]. This is not speculation;
  it is structural. The question is not whether [event] occurs, but how you are positioned
  when it does. Action by [specific date] is non-negotiable."

HIGH-CONFIDENCE (0.70–0.84):
  "Three systems point to [event] in [date range]. This is likely rather than possible —
  plan around it. The one system that dissents ([name it]) reads this as [divergence],
  which means [what the dissent implies]. Weight the majority; note the outlier."

MODERATE-CONFIDENCE (0.55–0.69):
  "Two systems agree on [date range]: [Western] reads it as X, [Vedic] reads it as Y.
  This window is probable but not certain — treat it as your working scenario
  while remaining open to variance of 2–4 weeks in timing."

LOW-CONFIDENCE (<0.55):
  "A single system flags [date range] as significant. Treat as possible, not probable.
  Act if it arrives; do not plan your year around it."

━━━ ADDITIONAL RULES ━━━
0. MANDATORY BALANCE — YEAR SUMMARY MUST NAME BOTH:
   "The highest-opportunity window of {YEAR}: [date range] — [what becomes available]"
   "The highest-pressure window of {YEAR}: [date range] — [what is tested]"
   These are two separate things. Most years contain both. Name both explicitly up front.
   A near-certain Jupiter transit is a near-certain OPPORTUNITY. Name it as such.
   Do not bury positive windows inside the mechanics — surface them in the headline block.
1. LEAD with the year's highest-confidence window — use it as the structural anchor.
   If it is a positive window (Jupiter, Venus, harmonious Primary Direction), name it as the
   year's primary opportunity, not as a secondary footnote after the challenges.
2. YEAR TITLE: Must reflect the year's dominant character honestly.
   If Jupiter dominates → title should reflect expansion/elevation, not just "pressure."
   If Saturn dominates AND Jupiter also present → name both tensions in the title.
   AVOID titles that only name the difficulty (e.g., "Isolation, Sabotage" when there are
   also Jupiter windows of opportunity in the same year).
3. DO NOT re-diagnose the natal chart. One-sentence anchors only where essential.
4. WHEN SYSTEMS DISAGREE within a window: name both readings, state which to weight and why.
5. END with: **The one action {YEAR} demands:** anchored to the highest-confidence window.
   If the highest-confidence window is an opportunity window, the action is to CLAIM it.
6. BANNED: potential, manifestation, journey, tapestry, energies, suggests (without stated consequence).
7. LENGTH: 580-640 words.
8. START with: # YEAR {YEAR}
9. Bold: **Primary Direction**, **Maha Dasha**, **Tajaka**, **Profection**, **Kakshya**
10. REALISTIC PACING: When multiple major life domains (career, family, property,
    health) have events in overlapping or adjacent windows, do NOT present them
    all as simultaneous certainties. A single 4-month window cannot realistically
    deliver a career change + financial windfall + baby + house purchase.
    Instead: rank by convergence score, present the highest-confidence domain as
    the PRIMARY outcome, and frame others as "conditions created" or "groundwork
    laid" rather than simultaneous completed events. Spread outcomes across the
    year or into subsequent years where the evidence supports it.
11. OUTER PLANET TRANSITS: Pluto, Neptune, and Uranus transits are GRADUAL
    processes lasting 1-3 years. Never describe them as acute daily stressors
    with strict start/end dates. Use the full entry-to-exit window as the
    active period and describe the process as unfolding gradually.
12. ZODIACAL RELEASING is a thematic timing system, NOT a daily trigger.
    ZR periods describe life chapters lasting months to years. Never present
    a ZR shift as an acute event on a single day. Frame ZR as: "During this
    period, the thematic emphasis shifts to [domain]" not "On March 16, ZR
    activates [event]."

VOICE AND RATIO:
  20% technical (which systems, exact dates, technique names)
  40% what this means in plain English (what will actually happen in the person's life —
      career, money, relationships, health — stated directly without jargon)
  40% what to do (specific, dated, practical actions)

For the "what this means" part: write as if texting a smart friend who has never heard of astrology.
"This is your best window for a promotion or public move this year — Jupiter crossing your
life-force point is the closest thing astrology has to a green light. Don't waste it job-hunting
quietly; this is when being visible pays off."

NOT: "The Jupiter transit conjunct your natal Sun in Cancer activates the 10th house profection
creating synergistic career potential." That is technique. Tell them what to expect."""

CURRENT_CONFIG_PROMPT = """You are a senior consulting astrologer, writing a situation report for a premium astrological dossier.

Write THE CURRENT CONFIGURATION — exactly 3 short paragraphs, total 140-170 words.

WHAT THIS IS: A weather briefing. Not a forecast — a current conditions report.
Where is this person RIGHT NOW? What is ending? What is building?

STRUCTURE:
Paragraph 1: Active Maha Dasha + Antardasha. Name what it is DOING to the person's life —
  not just what it "represents." "The Ketu Maha Dasha is actively stripping away X.
  The Jupiter Antardasha, now in its final Y months, is the last window to Z before the shift."
Paragraph 2: Current annual profection. Name the activated house, what it has turned the
  spotlight onto this year, what the time lord is demanding.
Paragraph 3: The single most dominant outer transit in effect right now. Name it, name its
  exact date range, state what it is forcing.

FINAL SENTENCE: Not a question. A statement of the current moment's core demand:
  "The immediate pressure is [X], and the only viable response is [Y]."

RULES:
1. START with: # ◈ THE CURRENT CONFIGURATION
2. No jargon explanations. Assume reader has read sections 1-4.
3. All three paragraphs must name a REAL-WORLD EFFECT, not just an astrological condition."""

DIRECTIVE_PROMPT = """You are a senior consulting astrologer, closing a premium astrological dossier with the mandate.

ABSOLUTE RULES:
1. Section 1 — THE RED THREAD: Exactly one sentence. Must name the Sun/Moon/Asc combination.
   Must name the core paradox. Could ONLY be written about this exact chart. No vague spiritual language.
   Format: **Red Thread:** [sentence]

2. Section 2 — HARD FINANCIAL RULES (from CHART FINANCIAL PROFILE in section data):
   State 1-2 non-negotiable rules derived from the chart's actual wealth structure.
   Not advice — laws. Specific and verifiable. Derived from the 8th house risk flag,
   Almuten dignity, or 2nd house lord condition in the data.
   BANNED: invented percentages like "40% of capital" or "51% control" unless the 8th house
   RISK FLAG is explicitly set in the CHART FINANCIAL PROFILE data. If no risk flag exists,
   the hard rule must be about time, focus, or domain — not financial ratios.
   Format:
   > **HARD RULE:** [specific rule in plain English derived from actual chart data]
   Example (if risk flag set): "Never enter a 50/50 partnership. Your chart's shared-resources
   zone creates structural financial loss when control is divided equally."
   Example (no risk flag): "Never abandon a professional specialization before the 5-year mark.
   Your wealth compounds with depth, not breadth — the chart's income engine requires sustained focus."

3. Section 3 — THE FIFTEEN-YEAR ORDERS: One concrete, dated, technical action per year 2026–2040.
   These are not abstract astrology — they are concrete life moves in specific industries/domains.
   Group into three 5-year phases if helpful for readability.
   Format:
   **2026:** [What to do, in which domain, by when, to what measurable end]
   **2027:** [etc.]
   **2028:** [etc.]
   **2029:** [etc.]
   **2030:** [etc.]
   **2031:** [etc.]
   **2032:** [etc.]
   **2033:** [etc.]
   **2034:** [etc.]
   **2035:** [etc.]
   **2036:** [etc.]
   **2037:** [etc.]
   **2038:** [etc.]
   **2039:** [etc.]
   **2040:** [etc.]
   Use the PRIMARY WEALTH CHANNELS from the FINANCIAL PROFILE when assigning domains.
   Each action must name the technique or window it responds to (e.g. "Saturn return", "Maha Dasha shift").

4. NO padding. NO encouragement. NO "remember that..." NO "trust yourself."
   Reads like a CEO's quarterly brief — ordered, specific, no sentiment.

5. LENGTH: 500-580 words.
6. START with: # ◈ THE FIFTEEN-YEAR DIRECTIVE"""

WARNING_PROMPT = """You are a senior consulting astrologer, writing the final warning of a premium astrological dossier.

Write THE WARNING — 180-220 words.

RULES:
1. ONE configuration only. The specific planetary setup creating the greatest risk OR the greatest
   unrealized opportunity for this chart. (A warning can be: "you are positioned for X and will
   miss it if you do Y" — not only "danger ahead.")
2. State: which planets, which aspect, when it peaks (exact date window from TEMPORAL STORM WINDOWS).
3. State: what it costs or destroys if ignored.
4. State: what it builds or delivers if engaged correctly. THIS IS MANDATORY AND MUST BE SPECIFIC.
   Not "you will forge an indestructible identity" — name the concrete outcome:
   "You will have the professional credibility and earned authority that your Saturn Almuten was
   always designed to produce" or "The Venus dasha that follows will be your most materially
   abundant and relationally fulfilling period — this test is the admission price."
5. FINAL TWO SENTENCES must describe what success looks like on the other side.
   The reader must finish THE WARNING knowing what they are working toward, not only what they risk.
6. NO generic danger language. No "rubble." No "dismantled." Name the specific structure at risk.
7. START with: # ◈ THE WARNING
8. LENGTH: 180-220 words. No more."""

ALMANAC_SUMMARY_PROMPT = """You are a senior consulting astrologer, writing a dated timeline reading for a premium astrological dossier.

Write ◈ THE FIFTEEN-YEAR WINDOW MAP.

THIS IS NOT A CHARACTER ANALYSIS. It is a dated forecast covering 2026–2040.
The reader has already received a full natal portrait in Part I.
They do not need to hear about their Gemini communication gifts again.
They need to know WHEN things happen and WHAT to expect across the next fifteen years.

FORMAT FOR EACH WINDOW:
**[MONTH YEAR – MONTH YEAR]** · [CONFIDENCE LABEL]
[2-3 sentences written in plain English:
 Sentence 1: What is happening — which planets are active, in plain language.
   Example: "Saturn reaches the exact opposition to its own birth position" not "transiting Saturn opposes natal Saturn via outer_transit_aspects."
 Sentence 2-3: What this means for THIS person's life during this window — what is being tested, what becomes available, what action is optimal.
   Be specific to the life domain: career, finance, home, family, health.]
Systems: [name only those that agree]
---

CONFIDENCE LANGUAGE:
NEAR-CERTAIN (≥0.85, 4+ systems): "This is the highest-confidence window of the arc. [X] independent systems converge here. The event is structural, not speculative."
HIGH-CONFIDENCE (0.70–0.84, 3 systems): "Three systems agree on this window. Plan around it."
MODERATE-CONFIDENCE (skip — only include NEAR-CERTAIN and HIGH-CONFIDENCE in this section)

NEAR-CERTAIN CAP: Maximum 2 NEAR-CERTAIN labels in this section. All others must be HIGH-CONFIDENCE or lower.

LONG-RANGE CONFIDENCE DECAY: For windows beyond 2030, downgrade the confidence label by one
tier UNLESS the window is supported by a Primary Direction (0.95 authority) or a Vimshottari
Dasha period boundary. Long-range transit-only windows degrade to MODERATE and should be
excluded from this section. State this honestly: "Beyond 2030, timing precision decreases."

RULES:
1. START with: # ◈ THE FIFTEEN-YEAR WINDOW MAP
2. Sort windows chronologically across 2026–2040. Include 10-15 windows spread across the full arc.
3. Only use windows from TEMPORAL STORM WINDOWS data. Do not invent windows.
4. All dates must be AFTER today's date (stated in the data block).
5. After the window list, write ONE paragraph titled **The Chain:**
   Trace how Window A enables Window B → which creates conditions for Window C.
   Connect the sequence to the specific life questions the user submitted (home, family, wealth, career).
6. DO NOT use mechanism names like "THE INTELLECTUAL WEALTH ENGINE" or "THE STRUCTURAL AUTHORITY".
   Those belong in Part I. This section uses date ranges and life domains.
7. DO NOT add "What to do with it" bullets. Practical guidance is woven into the window reading itself.
8. BANNED: journey, tapestry, energies, cosmic, explore, "your chart says."
9. LENGTH: 550-680 words total (longer than 5-year version to cover the full arc).
10. ZODIACAL RELEASING is a thematic timing system, NOT a daily trigger.
    ZR periods describe life chapters lasting months to years. Never present
    a ZR shift as an acute event on a single day.
11. OUTER PLANET TRANSITS (Pluto, Neptune, Uranus) are GRADUAL processes lasting
    1-3 years. Describe the process as unfolding gradually, not as acute events."""


QUESTIONS_PROMPT = """You are a senior consulting astrologer, the final authority delivering precise, data-backed answers.

═══════════════════════════════════════════════════════════════
CRITICAL RULE 1 — TEMPORAL ACCURACY (READ FIRST, OBEY ALWAYS)
═══════════════════════════════════════════════════════════════
TODAY'S DATE appears at the very top of the data block as "TODAY: YYYY-MM-DD".
FORBIDDEN: Citing ANY date, window, or period BEFORE today's date.
REQUIRED: Every date you write must be AFTER today.
ALL transit dates MUST come from the EVIDENCE BLOCK provided — do NOT use your training
knowledge of where planets are or will be. The evidence block has been computed from
Swiss Ephemeris; your training data has not. If a transit is not in the evidence block,
do not invent it.
═══════════════════════════════════════════════════════════════

═══════════════════════════════════════════════════════════════
CRITICAL RULE 2 — HOUSE LORDSHIP ACCURACY
═══════════════════════════════════════════════════════════════
BEFORE claiming "planet X rules house Y": verify from the HOUSE-BASED ROUTING in the
evidence block which sign is on the cusp of that house, and which planet rules that sign.
The Tier 2 block shows: "HOUSE N: cusp=SIGN, lord=PLANET".
Use those values. DO NOT assume house lordship from memory.
Example: With Gemini Ascendant — House 4 = Virgo → Mercury rules H4, NOT the Sun.
If you name the wrong house lord your answer is factually wrong.
═══════════════════════════════════════════════════════════════

═══════════════════════════════════════════════════════════════
CRITICAL RULE 3 — GENDER PREDICTION
═══════════════════════════════════════════════════════════════
FORBIDDEN: Predicting the gender of a child.
No classical astrological system can reliably determine foetal sex.
If asked, state directly: "Astrology cannot predict gender with any reliability.
The timing of conception and birth can be indicated; the sex cannot."
Then focus entirely on the timing and conditions for pregnancy and birth.
═══════════════════════════════════════════════════════════════

VOICE AND APPROACH:
You are not a checklist generator. You are a trusted advisor who knows this person's chart.
Answer as a senior astrologer who has studied this chart for years would answer a private client —
direct, specific, warm but not sentimental, authoritative but not cold.
The answer should feel like it was written FOR THIS PERSON, not for anyone with this placement.
Personal context is in the data: GP doctor in England, Burmese Buddhist, married, wants children,
first home, multi-millionaire ambition. Use all of this. Make answers UK-specific where relevant.

FORMAT FOR EACH QUESTION:

**Q: [exact question as asked]**

**The direct answer:**
[Give the verdict in the first sentence: yes / no / when / what form. No hedging.
Name the PRIMARY timing window AND the number of systems converging. 3-5 sentences.
This paragraph must feel decisive, structurally grounded, and impossible to dismiss.
Where 3+ systems agree: "Three independent systems — [technique], [technique], [technique] —
all converge on [Month YEAR]–[Month YEAR]. This is structural, not speculative."
For wealth questions: name specific financial mechanisms available to a UK GP —
NHS salary structure, buy-to-let, private practice, portfolio career, locum rates, BMA contracts.
For spiritual questions: name specific practices aligned to Theravada Buddhism and the chart.]

**The full timing landscape:**
[THIS IS THE EXPERT SECTION — the most important part of each answer.
Survey ALL viable timing windows from the evidence — not just the nearest one.
For each window (primary AND secondary/tertiary), explain:
- Which techniques activate it and at what authority level (Gold/High/Moderate)
- How many systems converge on it
- What the structural conditions are (house lord dignity, Shadbala, dasha, profection)
- Why it is stronger or weaker than competing windows

A professional astrologer does NOT rush to the closest upcoming window. If 2030 has
4-system convergence with a primary direction arc, it outranks a 2026 window with only
transit support. COMPARE windows explicitly and explain your reasoning.
5-8 sentences minimum. Be specific about planets, degrees, houses, and lords.]

**Mechanism:**
[Name the 3-4 strongest techniques with evidence. Explain the astrological LOGIC connecting
the planet/house/technique to the life outcome being asked about. Do NOT just list techniques —
explain WHY they produce this outcome. 4-6 sentences.
Example: "Mercury rules your 4th house of property (Virgo cusp). When Jupiter transits
conjunct natal Mercury, it expands 4th house matters — the physical act of acquiring property.
This is reinforced by the Vedic dasha: Jupiter antardasha activates Jupiter as karaka for
property and expansion, doubling the signal."]

**What this means for you:**
[Advisory prose tailored to THIS person's life. Reference their specific situation
(GP in England, Burmese Buddhist, married, wants children, property goals).
Give concrete, actionable guidance with specific dates. What should they prepare?
What should they watch for? What is the risk if they miss the window? 4-6 sentences.
End with: "The single most important action before [DATE] is [specific action]."]

---

NEAR-CERTAIN CAP: Use NEAR-CERTAIN only for convergence_score ≥ 0.85 AND 3+ systems.
Maximum 2 NEAR-CERTAIN labels in the entire Q&A section.

RULES:
1. Answer EVERY question in the order given. Never skip or merge.
2. USE the EVIDENCE block for each question — it contains pre-filtered, computed future dates.
3. CROSS-CHECK every date against the Tier 2 house routing for lordship accuracy.
4. START with: # ◈ YOUR QUESTIONS ANSWERED
5. Separate each answer with ---
6. LENGTH: 600-800 words per question. This is the most important section — depth matters.
7. BANNED: "it depends", "only time will tell", vague spiritual hedges, dates before today,
   numbered action lists in "What this means for you", gender predictions, house lords from memory,
   rushing to the nearest window without comparing alternatives.
8. REQUIRED: Direct verdict + multi-window comparison + specific future dates from evidence block
   + house lords verified from Tier 2 routing + personal advisory tone specific to this person's
   life context + explanation of WHY each technique produces the predicted outcome."""


# ─────────────────────────────────────────────────────────────────────────────
# Utility helpers (preserved from v1)
# ─────────────────────────────────────────────────────────────────────────────

def _deg_to_dms(decimal_deg: float) -> str:
    try:
        decimal_deg = float(decimal_deg)
        d = int(decimal_deg)
        m = int(round((decimal_deg - d) * 60))
        if m >= 60:
            d += 1
            m -= 60
        return f"{d}° {m:02d}'"
    except (TypeError, ValueError):
        return f"{decimal_deg}°"


def _jd_to_str(jd: float) -> str:
    try:
        jd_adj = jd + 0.5
        Z = int(jd_adj)
        if Z < 2299161:
            A = Z
        else:
            alpha = int((Z - 1867216.25) / 36524.25)
            A = Z + 1 + alpha - alpha // 4
        B = A + 1524
        C = int((B - 122.1) / 365.25)
        D = int(365.25 * C)
        E = int((B - D) / 30.6001)
        day   = B - D - int(30.6001 * E)
        month = E - 1 if E < 14 else E - 13
        year  = C - 4716 if month > 2 else C - 4715
        months = ["Jan","Feb","Mar","Apr","May","Jun",
                  "Jul","Aug","Sep","Oct","Nov","Dec"]
        return f"{months[month - 1]} {day}, {year}"
    except Exception:
        return f"JD {jd:.1f}"


# ─────────────────────────────────────────────────────────────────────────────
# Probability / Confidence helpers
# ─────────────────────────────────────────────────────────────────────────────

def _convergence_label(cluster: dict) -> str:
    """Human-readable confidence band for a cluster."""
    return cluster.get("confidence_label", "MODERATE-CONFIDENCE")

def _stoplight(cluster: dict) -> str:
    return cluster.get("stoplight", "🟡")


def _format_clusters(temporal_clusters: list) -> str:
    """
    Format ALL temporal storm windows for the predictive data block.
    Includes convergence scores so the model can rank certainty across all windows.
    """
    if not temporal_clusters:
        return ""
    lines = ["=== TEMPORAL STORM WINDOWS — INCLUDE CONFIDENCE IN PROSE ==="]
    lines.append(
        "Each window = a convergence of multiple independent predictive systems.\n"
        "CONVERGENCE SCORE is a probability-like signal (0-1). Use it to rank certainty:\n"
        "  NEAR-CERTAIN (≥0.85): 4+ systems agree → state as near-certain event\n"
        "  HIGH-CONFIDENCE (0.70-0.84): 3 systems → state as likely\n"
        "  MODERATE-CONFIDENCE (0.55-0.69): 2 systems → state as probable\n"
        "  LOW-CONFIDENCE (<0.55): 1 system echoing → frame as possible\n"
        "NEVER reproduce this table verbatim. Cite naturally in prose."
    )
    for i, cluster in enumerate(temporal_clusters[:14], 1):
        start  = _jd_to_str(cluster.get("start_jd", 0))
        end    = _jd_to_str(cluster.get("end_jd",   0))
        score  = cluster.get("convergence_score", 0.6)
        label  = _convergence_label(cluster)
        light  = _stoplight(cluster)
        n_sys  = cluster.get("n_systems", cluster.get("intensity", 1))
        evts   = cluster.get("events", [])
        sys_list = ", ".join(cluster.get("systems_involved", ["?"]))
        evt_summary = "; ".join(
            f"{ev.get('technique','?')} ({ev.get('system','?')})"
            for ev in evts[:4]
        )
        lines.append(
            f"  {light} [{i}] {start}–{end} | {label} ({score:.2f}) | "
            f"{n_sys} systems: {sys_list}\n"
            f"     Techniques: {evt_summary}"
        )
    lines.append("=== END STORM WINDOWS ===")
    return "\n".join(lines)


def _format_clusters_for_year(temporal_clusters: list, year: int) -> str:
    """
    Extract storm windows for the target year, with full confidence metadata.
    Sorted by convergence score (highest first) so the model leads with the
    most certain windows.
    """
    if not temporal_clusters:
        return ""

    year_clusters = []
    for c in temporal_clusters:
        start_str = _jd_to_str(c.get("start_jd", 0))
        end_str   = _jd_to_str(c.get("end_jd",   0))
        if str(year) in start_str or str(year) in end_str:
            year_clusters.append(c)

    if not year_clusters:
        return f"No multi-system convergences identified for {year}."

    # Sort by convergence score descending (highest certainty first)
    year_clusters.sort(key=lambda c: c.get("convergence_score", 0), reverse=True)

    lines = [
        f"=== {year} STORM WINDOWS — sorted by convergence score (highest = most certain) ===",
        "INSTRUCTION: When writing the year section, state the MOST CERTAIN windows first.",
        "Reference the confidence label explicitly in your prose:",
        '  "This window has the highest convergence of any period this year — [X] independent',
        '   systems agree, making this near-certain rather than speculative."',
        "VS:",
        '  "This window has moderate support from two systems; treat as probable but not certain."',
        "",
    ]

    for i, c in enumerate(year_clusters, 1):
        start  = _jd_to_str(c.get("start_jd", 0))
        end    = _jd_to_str(c.get("end_jd",   0))
        score  = c.get("convergence_score", 0.6)
        label  = _convergence_label(c)
        light  = _stoplight(c)
        n_sys  = c.get("n_systems", len(c.get("systems_involved", [])))
        sys_list = ", ".join(c.get("systems_involved", ["?"]))
        evts   = c.get("events", [])
        evt_lines = [
            f"{ev.get('technique','?')} ({ev.get('system','?')}): {ev.get('description','')}"
            for ev in evts[:5]
        ]
        lines.append(
            f"  {light} Window {i}: {start} → {end}"
        )
        lines.append(
            f"     Confidence: {label} (score {score:.2f}) | "
            f"{n_sys} systems: {sys_list}"
        )
        for el in evt_lines:
            lines.append(f"     • {el}")
        lines.append("")

    lines.append(
        f"INSTRUCTION: Weave windows chronologically but lead with highest-confidence ones. "
        f"DO NOT reproduce this table. State confidence levels naturally in prose."
    )
    return "\n".join(lines)



# ─────────────────────────────────────────────────────────────────────────────
# Year Dashboard generator
# ─────────────────────────────────────────────────────────────────────────────

def _compute_year_dashboard(temporal_clusters: list,
                             years: list = None) -> str:
    """
    Generate an at-a-glance grid showing intensity, financial volatility, and
    relational harmony scores (1–10) for each of the fifteen forecast years.

    Scores are computed purely from the cluster data — no API calls.

    Intensity:           total convergence score of all clusters in the year.
    Financial pressure:  score from clusters whose events involve career/finance domains.
    Relational pressure: score from clusters whose events touch House 7 / Venus / relationships.

    Scale: 1 = very quiet, 10 = peak pressure.
    Stoplight:
      8-10 = 🔴 high pressure / pivotal
      5-7  = 🟠 active / significant
      2-4  = 🟡 steady / building
      1    = 🟢 quiet
    """
    if years is None:
        years = list(range(2026, 2041))

    FINANCE_KEYWORDS  = {"career", "saturn", "jupiter", "money", "2nd", "10th",
                          "profection", "solar return", "primary direction", "tajaka",
                          "amatyakaraka", "useful god", "mc", "midheaven"}
    RELATION_KEYWORDS = {"venus", "7th", "darakaraka", "mars", "relationship",
                          "partner", "lunar return", "peach blossom", "outer transit"}

    def _score_to_light(score: float) -> str:
        if score >= 8:  return "🔴"
        if score >= 5:  return "🟠"
        if score >= 2:  return "🟡"
        return "🟢"

    def _domain_score(clusters_for_year: list, keywords: set) -> float:
        """Score 1-10: how many clusters have events matching this domain."""
        if not clusters_for_year:
            return 1.0
        matched = 0
        for c in clusters_for_year:
            evts = c.get("events", [])
            for ev in evts:
                text = (
                    ev.get("technique", "") + " " +
                    ev.get("description", "") + " " +
                    ev.get("domain", "")
                ).lower()
                if any(kw in text for kw in keywords):
                    matched += c.get("convergence_score", 0.6)
                    break
        raw = matched / max(1, len(clusters_for_year)) * 10
        return round(min(10.0, max(1.0, raw)), 1)

    def _intensity_score(clusters_for_year: list) -> float:
        if not clusters_for_year:
            return 1.0
        total = sum(c.get("convergence_score", 0.6) for c in clusters_for_year)
        # Normalize: 1 cluster at 0.6 = 2, 5 clusters at 0.9 = 10
        raw = total / 0.45  # ~0.45 per unit → scale to 0-10
        return round(min(10.0, max(1.0, raw)), 1)

    rows = []
    for year in years:
        year_clusters = []
        for c in temporal_clusters:
            start_str = _jd_to_str(c.get("start_jd", 0))
            end_str   = _jd_to_str(c.get("end_jd", 0))
            if str(year) in start_str or str(year) in end_str:
                year_clusters.append(c)

        intensity   = _intensity_score(year_clusters)
        finance     = _domain_score(year_clusters, FINANCE_KEYWORDS)
        relational  = _domain_score(year_clusters, RELATION_KEYWORDS)

        # Find the peak window of this year for annotation
        peak_c = max(year_clusters, key=lambda c: c.get("convergence_score", 0), default=None)
        peak_note = ""
        if peak_c:
            peak_start = _jd_to_str(peak_c.get("start_jd", 0))
            peak_end   = _jd_to_str(peak_c.get("end_jd", 0))
            peak_score = peak_c.get("convergence_score", 0)
            peak_label = peak_c.get("confidence_label", "")
            peak_note  = f"Peak window: {peak_start}→{peak_end} ({peak_label}, {peak_score:.2f})"

        rows.append({
            "year":       year,
            "intensity":  intensity,
            "finance":    finance,
            "relational": relational,
            "peak_note":  peak_note,
            "n_windows":  len(year_clusters),
        })

    # Format as a readable table
    lines = [
        "",
        "## ◈ THE FIFTEEN-YEAR AT-A-GLANCE",
        "",
        "*Scores computed from multi-system convergence analysis. "
        "10 = peak pressure / maximum opportunity. 1 = quiet.*",
        "",
        "| Year | Overall Intensity | Financial Pressure | Relational Pressure | Peak Window |",
        "|------|:-----------------:|:------------------:|:-------------------:|-------------|",
    ]

    for r in rows:
        yr      = r["year"]
        i_light = _score_to_light(r["intensity"])
        f_light = _score_to_light(r["finance"])
        rel_light = _score_to_light(r["relational"])
        lines.append(
            f"| **{yr}** | "
            f"{i_light} {r['intensity']:.0f}/10 | "
            f"{f_light} {r['finance']:.0f}/10 | "
            f"{rel_light} {r['relational']:.0f}/10 | "
            f"{r['peak_note']} |"
        )

    lines += [
        "",
        "*Score = intensity of activity, NOT a measure of good or bad luck. "
        "High scores mean pivotal periods — for opportunity AND challenge alike. "
        "A 🔴 10 in a Jupiter year = near-certain breakthrough. A 🔴 10 in a Saturn year = defining test. "
        "Detail for 2026–2030 is in the year chapters below. 2031–2040 detail is in the Window Map.*",
        "",
        "*🔴 8–10 = pivotal / defining  🟠 5–7 = active / significant  "
        "🟡 2–4 = steady / building  🟢 1 = quiet*",
        "",
    ]
    return "\n".join(lines)


# ─────────────────────────────────────────────────────────────────────────────
# Wealth Capacity Score — computed from chart data, no API call
# ─────────────────────────────────────────────────────────────────────────────

def _compute_wealth_score(chart_data: dict, ref: dict) -> dict:
    """
    Compute a Wealth Capacity Score (1.0–10.0) from the chart's core wealth indicators.
    Returns a dict with score, tier, profile, and a plain-English summary paragraph.

    This is deterministic — no LLM involved. Based on:
      - Almuten dignity (most dignified planet = structural authority)
      - 2nd house lord strength (Shadbala if Vedic available)
      - Lot of Fortune sign and dignity
      - Dhana Yoga count (from Vedic yogas data)
      - Useful God element (Bazi — fire = tech/energy, water = finance/trade, etc.)
      - 8th house risk flag (planets in 8th opposing 2nd = joint-venture risk)
    """
    score = 5.0  # neutral baseline

    v_natal   = chart_data.get("vedic",  {}).get("natal",    {})
    w_natal   = chart_data.get("western",{}).get("natal",    {})
    bazi      = chart_data.get("bazi",   {}).get("natal",    {})
    shadbala  = chart_data.get("vedic",  {}).get("strength", {}).get("shadbala", {})

    # ── Almuten dignity bonus ────────────────────────────────────────────────
    # Key was "_almuten_planet" but ref stores it as "_almuten" + "_almuten_dignity"
    almuten         = ref.get("_almuten", "")
    almuten_dignity = ref.get("_almuten_dignity", "neutral")
    dignity_map = {"domicile": 1.5, "exaltation": 1.0, "triplicity": 0.5,
                   "detriment": -1.0, "fall": -1.5}
    score += dignity_map.get(almuten_dignity.lower(), 0)

    # ── 2nd house lord Shadbala ────────────────────────────────────────────
    planet_scores = shadbala.get("planet_scores", {})
    lord_2nd = ref.get("_2nd_house_lord", "")
    if lord_2nd and lord_2nd in planet_scores:
        ps = planet_scores[lord_2nd]
        # shadbala.py v1 outputs in Rupas (key: "rupas"); legacy output used "total" in Sha
        shad_rupas = float(ps.get("rupas", ps.get("total", 0) / 60.0)) if isinstance(ps, dict) else 0.0
        # Thresholds calibrated for Rupas (typical range 2–8 Rupas; minimums 5–7)
        if shad_rupas >= 8.0:    score += 1.5   # DOMINANT — well above minimum
        elif shad_rupas >= 6.5:  score += 0.8   # ADEQUATE — above minimum
        elif shad_rupas >= 5.0:  score += 0.3   # at minimum threshold
        elif shad_rupas < 3.5:   score -= 0.5   # SEVERELY WEAKENED

    # ── Dhana Yoga count ────────────────────────────────────────────────────
    yogas = v_natal.get("yogas", [])
    dhana_yogas = [y for y in yogas if isinstance(y, dict) and
                   any(w in str(y.get("name","")).lower() for w in
                       ["dhana", "wealth", "raja", "lakshmi", "gajakesari", "hamsa"])]
    score += min(2.0, len(dhana_yogas) * 0.5)   # cap at +2

    # ── Useful God element bonus (Bazi) ─────────────────────────────────────
    useful_god = ref.get("_useful_god", "")
    if useful_god:
        # All elements indicate wealth capacity — just different channels
        score += 0.5  # any defined Useful God = chart has clear wealth channel

    # ── 8th house risk flag ─────────────────────────────────────────────────
    # Planets in 8th house (shared resources) = joint-venture risk, NOT a score deduction
    # but informs the risk_flag for the report narrative
    w_placements = w_natal.get("placements", {})
    eighth_planets = [p for p, d in w_placements.items()
                      if isinstance(d, dict) and d.get("house") == 8]
    risk_flag = len(eighth_planets) > 0

    # ── Lot of Fortune dignity ──────────────────────────────────────────────
    lof_sign = ref.get("_lot_fortune_sign", "")
    if lof_sign in ("Taurus", "Cancer", "Pisces"):  # dignified/exalted
        score += 0.4
    elif lof_sign in ("Scorpio", "Capricorn", "Virgo"):  # detriment/fall
        score -= 0.2

    # ── Cap and tier ────────────────────────────────────────────────────────
    score = round(min(10.0, max(1.0, score)), 1)

    if score >= 8.5:
        tier = "EXCEPTIONAL"
        tier_desc = "upper-tier generational wealth potential"
    elif score >= 7.0:
        tier = "HIGH"
        tier_desc = "substantial long-term wealth — multi-million stability is structurally supported"
    elif score >= 5.5:
        tier = "SOLID"
        tier_desc = "above-average earning and asset-building capacity"
    elif score >= 4.0:
        tier = "MODERATE"
        tier_desc = "stable income with selective wealth windows"
    else:
        tier = "CONSTRAINED"
        tier_desc = "wealth requires deliberate structural effort to unlock"

    # ── Industry mapping from available signals ──────────────────────────────
    industry_signals = []
    second_house_sign = ref.get("_2nd_house_sign", "")
    mc_sign = ref.get("_mc_sign", "")

    sign_to_industry = {
        "Cancer":      ["real estate", "food & hospitality", "childcare", "healthcare", "advisory/coaching"],
        "Taurus":      ["real estate", "luxury goods", "agriculture", "finance", "art"],
        "Leo":         ["entertainment", "leadership roles", "luxury brands", "self-employment"],
        "Scorpio":     ["finance/investing", "research", "insurance", "transformation industries"],
        "Virgo":       ["health & wellness", "data/analytics", "consulting", "pharmaceuticals"],
        "Gemini":      ["media", "publishing", "education", "technology", "communications"],
        "Aquarius":    ["technology", "social enterprise", "engineering", "AI/software"],
        "Capricorn":   ["construction", "government", "finance", "established institutions"],
        "Sagittarius": ["education", "publishing", "law", "international business", "philosophy"],
        "Pisces":      ["arts", "spirituality", "healthcare", "film/music", "NGO/non-profit"],
        "Aries":       ["sports", "military/security", "entrepreneurship", "manufacturing"],
        "Libra":       ["law", "design", "luxury goods", "diplomacy", "partnerships"],
    }
    useful_element_to_industry = {
        "Fire":  ["technology", "AI/software", "energy", "entertainment", "startups"],
        "Water": ["finance/investing", "healthcare", "real estate", "import/export", "luxury"],
        "Wood":  ["education", "media", "publishing", "agriculture", "consulting"],
        "Metal": ["finance", "law", "manufacturing", "engineering", "government"],
        "Earth": ["real estate", "food", "construction", "retail", "hospitality"],
    }

    if second_house_sign in sign_to_industry:
        industry_signals.extend(sign_to_industry[second_house_sign][:3])

    ug_element = useful_god.split()[0] if useful_god else ""
    if ug_element in useful_element_to_industry:
        industry_signals.extend(useful_element_to_industry[ug_element][:2])

    # Deduplicate while preserving order
    seen = set()
    industries = []
    for ind in industry_signals:
        if ind not in seen:
            seen.add(ind)
            industries.append(ind)

    return {
        "score": score,
        "tier": tier,
        "tier_desc": tier_desc,
        "dhana_yoga_count": len(dhana_yogas),
        "risk_flag": risk_flag,
        "eighth_planets": eighth_planets,
        "industries": industries[:5],
        "useful_god": useful_god,
        "almuten_dignity": almuten_dignity,
    }


def _format_wealth_score_block(ws: dict) -> str:
    """Format the wealth score into a report-ready block for injection into Material World."""
    tier  = ws["tier"]
    desc  = ws["tier_desc"]
    industries = ws["industries"]
    risk  = ws["risk_flag"]
    eighth = ws["eighth_planets"]
    yogas = ws["dhana_yoga_count"]

    ind_str = ", ".join(industries) if industries else "advisory and relationship-based work"

    risk_sentence = ""
    if risk and eighth:
        planets_str = ", ".join(eighth[:3])
        risk_sentence = (
            f"\n> ⚠️ **Joint-Venture Risk Flag:** {planets_str} in the shared-resources zone "
            f"of the chart. Mixing finances with partners or investing in speculative/uncontrolled "
            f"ventures carries above-average risk of sudden loss. Maintain sole asset control."
        )

    yoga_note = ""
    if yogas > 0:
        yoga_note = f" ({yogas} Vedic wealth combination{'s' if yogas > 1 else ''} confirmed)"

    block = (
        f"\n> **◈ WEALTH CAPACITY: {tier}**{yoga_note}\n"
        f"> *{desc}.*\n"
        f"> **Primary wealth channels:** {ind_str}\n"
        f"> **Wealth profile:** slow-compounding, authority-based — peak wealth arrives in the "
        f"second half of life, driven by reputation and systems built over decades.\n"
        f"{risk_sentence}\n"
    )
    return block


# ─────────────────────────────────────────────────────────────────────────────
# Rule querier (optional Neo4j dependency)
# ─────────────────────────────────────────────────────────────────────────────
_rule_querier = None
try:
    from graph.rule_querier import GraphRuleQuerier as RuleQuerier
    _rule_querier = RuleQuerier()
except Exception:
    pass


# ─────────────────────────────────────────────────────────────────────────────
# QuestionRouter — semantic question-to-data mapper
# ─────────────────────────────────────────────────────────────────────────────

class QuestionRouter:
    """
    House-based evidence router for Part IV questions.

    Architecture:
      Tier 1 — Universal core: Shadbala, all yogas, ZR phase, element balance.
               Injected for EVERY question regardless of topic.
      Tier 2 — House-based routing: question text → house numbers → lords,
               conditions, Shadbala of lords, transits, all four systems.
      Tier 3 — Natural significators: topic-specific planets added automatically.
    """

    # ── House → topic keyword mapping ────────────────────────────────────────
    HOUSE_TOPIC_MAP = {
        1:  ["self", "identity", "appearance", "body", "health", "personality", "who am i"],
        2:  ["wealth", "money", "income", "earn", "rich", "savings", "fortune", "financial",
             "afford", "net worth"],
        3:  ["siblings", "communication", "writing", "media", "short travel", "content",
             "publishing", "courses", "learning"],
        4:  ["home", "house", "property", "buy", "own", "flat", "apartment", "mortgage",
             "real estate", "parents", "mother", "homeland"],
        5:  ["children", "child", "baby", "pregnant", "pregnancy", "creative", "romance",
             "gambling", "speculative", "offspring", "conceive", "fertility"],
        6:  ["health", "illness", "disease", "work", "service", "daily routine", "employees",
             "diet", "exercise", "pets"],
        7:  ["partner", "relationship", "marriage", "marry", "spouse", "love", "boyfriend",
             "girlfriend", "soulmate", "divorce", "separation"],
        8:  ["death", "inheritance", "shared finances", "transformation", "occult", "crisis",
             "surgery", "taxes", "joint"],
        9:  ["travel", "foreign", "abroad", "immigration", "philosophy", "religion", "spiritual",
             "higher education", "university", "legal", "law", "court", "judge"],
        10: ["career", "job", "profession", "work", "boss", "promotion", "public", "reputation",
             "business", "entrepreneurship", "startup"],
        11: ["friends", "network", "passive income", "side income", "groups", "social",
             "goals", "wishes", "online", "community", "investor"],
        12: ["foreign", "isolation", "retreat", "hidden", "meditation", "hospital",
             "prison", "karma", "past life", "loss", "enemy"],
    }

    # ── Natural significators per house ──────────────────────────────────────
    HOUSE_SIGNIFICATORS = {
        1:  ["Sun", "Mars", "Ascendant"],
        2:  ["Jupiter", "Venus", "Moon"],
        3:  ["Mercury", "Mars"],
        4:  ["Moon", "Saturn"],
        5:  ["Jupiter", "Venus", "Moon"],
        6:  ["Mars", "Saturn", "Mercury"],
        7:  ["Venus", "Jupiter", "Mars"],
        8:  ["Saturn", "Mars", "Pluto"],
        9:  ["Jupiter", "Sun"],
        10: ["Saturn", "Sun", "Mercury"],
        11: ["Jupiter", "Saturn"],
        12: ["Saturn", "Jupiter"],
    }

    # ── Sign rulers (traditional) ─────────────────────────────────────────────
    SIGN_RULERS = {
        "Aries": "Mars", "Taurus": "Venus", "Gemini": "Mercury",
        "Cancer": "Moon", "Leo": "Sun", "Virgo": "Mercury",
        "Libra": "Venus", "Scorpio": "Mars", "Sagittarius": "Jupiter",
        "Capricorn": "Saturn", "Aquarius": "Saturn", "Pisces": "Jupiter",
    }

    def __init__(self, today: datetime):
        self.today    = today
        self.today_jd = self._dt_to_jd(today)
        self.today_str = today.strftime("%Y-%m-%d")

    @staticmethod
    def _dt_to_jd(dt: datetime) -> float:
        import swisseph as swe
        return swe.julday(dt.year, dt.month, dt.day,
                          dt.hour + dt.minute / 60.0 + dt.second / 3600.0)

    def _detect_houses(self, question: str) -> list:
        """Map question text to relevant house numbers, ranked by keyword hits."""
        q = question.lower()
        scores = {}
        for house, keywords in self.HOUSE_TOPIC_MAP.items():
            hits = sum(1 for kw in keywords if kw in q)
            if hits:
                scores[house] = hits
        if not scores:
            return [1, 10, 2]  # default: self, career, wealth
        return sorted(scores, key=lambda h: scores[h], reverse=True)[:3]

    def _house_lord(self, house_num: int, w_nat: dict) -> str:
        """Get the traditional lord of a house from its cusp sign."""
        houses = w_nat.get("houses", {})
        h_data = houses.get(f"House_{house_num}", {})
        sign   = (h_data.get("sign") or h_data.get("cusp_sign") or
                  h_data.get("sign_name", ""))
        return self.SIGN_RULERS.get(sign, "")

    def _shadbala_for_planet(self, planet: str, chart_data: dict) -> str:
        """Return formatted Shadbala string for a planet."""
        shadbala = chart_data.get("vedic", {}).get("strength", {}).get("shadbala", {})
        ps = shadbala.get("planet_scores", {}).get(planet, {})
        if not ps:
            return "N/A"
        rupas = ps.get("rupas", ps.get("total", 0) / 60.0 if ps.get("total") else None)
        if rupas is None:
            return "N/A"
        try:
            r = float(rupas)
            label = "STRONG" if r >= 7 else ("ADEQUATE" if r >= 5 else ("WEAK" if r >= 3.5 else "VERY WEAK"))
            return f"{r:.2f} Rupas ({label})"
        except (TypeError, ValueError):
            return str(rupas)

    def _future_storm_windows(self, temporal_clusters: list, max_windows: int = 15) -> list:
        future = [c for c in temporal_clusters if c.get("end_jd", 0) > self.today_jd]
        future.sort(key=lambda c: c.get("start_jd", 0))
        return future[:max_windows]

    def _future_transit_hits(self, outer_transit_data: dict,
                              relevant_planets: list = None) -> list:
        hits = outer_transit_data.get("hits") or outer_transit_data.get("all_hits", [])
        future = []
        for h in hits:
            iso_date = h.get("exact_date_iso", "")
            exact_jd = h.get("exact_jd", 0)
            try:
                if iso_date:
                    y, mo, d = map(int, iso_date.split("-"))
                    is_future = datetime(y, mo, d, tzinfo=timezone.utc) > self.today
                else:
                    is_future = exact_jd > self.today_jd
                if is_future:
                    planet = h.get("transiting") or h.get("planet", "Unknown")
                    if relevant_planets is None or planet in relevant_planets:
                        future.append(h)
            except Exception:
                pass
        return sorted(future, key=lambda h: h.get("exact_jd", 0))

    def _build_tier1_universal(self, chart_data: dict, ref: dict) -> list:
        """
        Tier 1: Universal strength fabric — injected for EVERY question.
        Shadbala all planets, all yogas, ZR current phase, element balance.
        """
        lines = ["── TIER 1: UNIVERSAL CHART STRENGTH (relevant to every question) ──"]

        v_nat    = chart_data.get("vedic", {}).get("natal", {})
        shadbala = chart_data.get("vedic", {}).get("strength", {}).get("shadbala", {})
        hell     = chart_data.get("hellenistic", {})
        bazi_nat = chart_data.get("bazi", {}).get("natal", {})

        # Shadbala all 9 planets
        planet_scores = shadbala.get("planet_scores", {})
        if planet_scores:
            lines.append("Shadbala (Vedic planetary strength — higher Rupas = stronger):")
            lines.append("  Min adequate: Sun/Moon ~5.0+, others ~3.5+ Rupas")
            for p in ["Sun","Moon","Mercury","Venus","Mars","Jupiter","Saturn"]:
                s = self._shadbala_for_planet(p, chart_data)
                lines.append(f"  {p}: {s}")

        # All yogas
        yogas = v_nat.get("yogas", [])
        if yogas:
            lines.append(f"All active Vedic yogas ({len(yogas)} total):")
            for y in yogas[:10]:
                name = y.get("name", "?") if isinstance(y, dict) else str(y)
                eff  = y.get("effect", y.get("description", "")) if isinstance(y, dict) else ""
                str_ = y.get("strength", "") if isinstance(y, dict) else ""
                line = f"  • {name}"
                if str_: line += f" ({str_})"
                if eff:  line += f": {eff[:70]}"
                lines.append(line)

        # ZR current phase
        zr = hell.get("zodiacal_releasing", {})
        if zr:
            lines.append("Zodiacal Releasing current phase:")
            for lot in ["Fortune", "Spirit"]:
                zr_d = zr.get(lot)
                if isinstance(zr_d, list) and zr_d:
                    p = zr_d[0]
                    lines.append(f"  ZR {lot}: {p.get('sign','?')} lord={p.get('lord','?')} → {p.get('end_date', p.get('end','?'))}")
                elif isinstance(zr_d, dict) and zr_d:
                    lines.append(f"  ZR {lot}: {zr_d.get('sign','?')} lord={zr_d.get('lord','?')} → {zr_d.get('end_date','?')}")

        # Bazi element balance + Useful God
        elem = bazi_nat.get("element_balance", bazi_nat.get("elements", {}))
        if elem:
            elem_str = ", ".join(f"{k}:{v}" for k, v in elem.items())
            lines.append(f"Bazi element balance: {elem_str}")
        if ref.get("_useful_god") and ref["_useful_god"] not in ("UNAVAILABLE", "Unknown", ""):
            lines.append(f"Bazi Useful God: {ref['_useful_god']} "
                         f"(Day Master: {ref.get('_dm_stem','')} {ref.get('_dm_element','')} — {ref.get('_dm_tier','')})")

        # Western dignities summary
        w_nat  = chart_data.get("western", {}).get("natal", {})
        pd_dig = w_nat.get("dignities", {}).get("planet_dignities", {})
        if pd_dig:
            lines.append("Western dignity scores (total):")
            for p in ["Sun","Moon","Mercury","Venus","Mars","Jupiter","Saturn"]:
                d = pd_dig.get(p, {})
                if isinstance(d, dict):
                    score = d.get("total_score", "?")
                    state = d.get("state", "")
                    lines.append(f"  {p}: {score}" + (f" ({state})" if state else ""))

        return lines

    def _build_tier2_house_routing(self, houses: list, chart_data: dict,
                                    ref: dict, w_nat: dict, v_nat: dict) -> list:
        """
        Tier 2: House-based routing — all four systems for the relevant houses.
        """
        lines = [f"── TIER 2: HOUSE-BASED ROUTING (houses {houses}) ──"]
        lines.append("(Houses most relevant to this question — lords, conditions, all 4 systems)")

        v_houses    = v_nat.get("houses", {})
        w_houses    = w_nat.get("houses", {})
        v_placement = v_nat.get("placements", {})
        bazi_nat    = chart_data.get("bazi", {}).get("natal", {})
        hell        = chart_data.get("hellenistic", {})

        for h in houses:
            lines.append(f"\n  HOUSE {h}:")

            # Western: house data + lord
            wh = w_houses.get(f"House_{h}", {})
            cusp_sign = (wh.get("sign") or wh.get("cusp_sign") or
                         wh.get("sign_name", "?"))
            lord = self.SIGN_RULERS.get(cusp_sign, "?")
            planets_in = wh.get("planets", wh.get("occupants", []))
            lines.append(f"    Western: cusp={cusp_sign}, lord={lord}, "
                         f"planets_in_house={planets_in}")

            # Lord's condition
            if lord and lord != "?":
                lord_data = ref.get(lord, {})
                lord_sign = lord_data.get("sign", "?")
                lord_deg  = lord_data.get("dms", "?")
                lord_shad = self._shadbala_for_planet(lord, chart_data)
                lord_dig  = (w_nat.get("dignities", {}).get("planet_dignities", {})
                             .get(lord, {}).get("total_score", "?"))
                lines.append(f"    {lord} (house lord): {lord_deg} {lord_sign} | "
                             f"Shadbala={lord_shad} | Western dignity={lord_dig}")

                # D9/D10 placement of lord
                lord_v = v_placement.get(lord, {})
                if lord_v.get("d9"):
                    lines.append(f"    {lord} in D9 (Navamsha): {lord_v['d9']}")
                if lord_v.get("d10"):
                    lines.append(f"    {lord} in D10 (Dasamsha): {lord_v['d10']}")

            # Vedic: Bhava data
            vh = v_houses.get(f"Bhava_{h}", {})
            if vh:
                v_lord      = vh.get("lord", vh.get("sign_lord", "?"))
                v_cusp_sign = vh.get("sign", vh.get("rashi", "?"))
                v_planets   = vh.get("planets", vh.get("occupants", []))
                lines.append(f"    Vedic Bhava {h}: sign={v_cusp_sign}, lord={v_lord}, "
                             f"planets={v_planets}")
                if v_lord and v_lord != lord:
                    v_lord_shad = self._shadbala_for_planet(v_lord, chart_data)
                    lines.append(f"    Vedic lord {v_lord}: Shadbala={v_lord_shad}")

            # Natural significators for this house
            natsigs = self.HOUSE_SIGNIFICATORS.get(h, [])
            if natsigs:
                lines.append(f"    Natural significators: {', '.join(natsigs)}")
                for sig in natsigs[:2]:
                    sig_data = ref.get(sig, {})
                    sig_sign = sig_data.get("sign", "?")
                    sig_dms  = sig_data.get("dms", "?")
                    sig_shad = self._shadbala_for_planet(sig, chart_data)
                    lines.append(f"      {sig}: {sig_dms} {sig_sign} | Shadbala={sig_shad}")

            # Hellenistic: relevant Lot
            lot_map = {2: "fortune", 5: "spirit", 7: "marriage", 10: "spirit"}
            lot_key = lot_map.get(h)
            if lot_key:
                lots = hell.get("lots", {})
                lot  = lots.get(lot_key, {})
                if lot:
                    lines.append(f"    Hellenistic Lot of {lot_key.capitalize()}: "
                                 f"{lot.get('sign','?')} {_deg_to_dms(lot.get('longitude',0) % 30)}")

            # Bazi 10-god relevant to this house
            ten_gods_map = {
                2: ["Output", "Wealth"], 5: ["Output", "Seal"],
                7: ["Companion", "Influence"], 10: ["Officer", "Wealth"],
            }
            relevant_gods = ten_gods_map.get(h, [])
            if relevant_gods and bazi_nat.get("ten_gods"):
                tg = bazi_nat["ten_gods"]
                for pillar, gdata in tg.items():
                    if isinstance(gdata, dict):
                        for key in ["stem_god", "branch_god"]:
                            god = gdata.get(key, "")
                            if any(rg.lower() in god.lower() for rg in relevant_gods):
                                lines.append(f"    Bazi {pillar} {key}={god} (relevant to H{h})")

            # Ashtakavarga house strength (raw Layer 1 data)
            av_full = chart_data.get("vedic", {}).get("strength", {}).get("ashtakavarga_full", {})
            av_house_strengths = av_full.get("house_strengths", [])
            for hs in av_house_strengths:
                if isinstance(hs, dict) and hs.get("house") == h:
                    lines.append(f"    Ashtakavarga H{h}: SAV={hs.get('sav_score','?')}, "
                                 f"strength={hs.get('strength','?')}")

        # ── Vedic Yogas relevant to detected houses/planets ──────────────
        yogas = v_nat.get("yogas", [])
        if yogas:
            relevant_yogas = [
                y for y in yogas
                if (isinstance(y, dict) and (
                    y.get("house") in houses
                    or any(p in (y.get("planets") or []) for p in
                           [self.SIGN_RULERS.get(v_houses.get(f"Bhava_{h}", {}).get("sign", ""), "")
                            for h in houses])
                ))
            ]
            if relevant_yogas:
                lines.append("\n── VEDIC YOGAS (relevant to this question) ──")
                for y in relevant_yogas[:5]:
                    strength = y.get("strength", "?")
                    planets_str = ", ".join(y.get("planets", []))
                    lines.append(f"  {y.get('name','?')} ({y.get('type','?')}): "
                                 f"planets={planets_str}, house={y.get('house','?')}, "
                                 f"strength={strength}")
                    desc = y.get("description", "")
                    if desc:
                        lines.append(f"    → {desc[:150]}")

        return lines

    def _build_tier3_timing(self, relevant_planets: list, relevant_houses: list,
                             chart_data: dict, ref: dict,
                             temporal_clusters: list,
                             validation_matrix=None,
                             domain_keywords: list = None) -> list:
        """
        Tier 3: Future timing — transits, profections, dashas, storm windows.

        When validation_matrix + domain_keywords are provided, replaces raw
        data dumps with pre-scored top-3 convergence windows. The LLM receives
        only mathematically proven timing instead of picking dates freely.
        """
        lines = ["── TIER 3: FUTURE TIMING (all dates after TODAY) ──"]

        w_pred      = chart_data.get("western", {}).get("predictive", {})
        v_pred      = chart_data.get("vedic",   {}).get("predictive", {})
        b_pred      = chart_data.get("bazi",    {}).get("predictive", {})
        profecs     = w_pred.get("profections_timeline", [])
        outer       = w_pred.get("outer_transit_aspects", {})
        primary_dirs = w_pred.get("primary_directions", {})
        progressions = w_pred.get("progressions", {})
        dasha       = v_pred.get("vimshottari", {})
        liu_nian    = b_pred.get("liu_nian_timeline", [])

        # Active time lords (always included — factual state, not raw dumps)
        lines.append(f"Active Dasha: {dasha.get('maha_lord','?')} MD / "
                     f"{dasha.get('antar_lord','?')} AD")
        lines.append(f"Current Profection: House {ref.get('_profection_house','?')}, "
                     f"Time Lord={ref.get('_time_lord','?')}")

        # ── Pre-scored convergence windows (replaces raw data dumps) ──────
        if validation_matrix and domain_keywords:
            clusters = validation_matrix.query_temporal_clusters(
                domain_keywords, tolerance_days=30, top_n=3)
            if clusters:
                lines.append("")
                lines.append("MATHEMATICALLY PROVEN TIMING WINDOWS (top 3 convergences):")
                lines.append("CRITICAL: Use ONLY these windows for timing predictions.")
                lines.append("Do NOT invent dates or cite raw transits not listed here.")
                for i, c in enumerate(clusters, 1):
                    date_str = c["convergence_date"].strftime("%Y-%m-%d")
                    lines.append(
                        f"  [{i}] ~{date_str} | "
                        f"confidence={c['combined_confidence']:.3f} | "
                        f"systems: {', '.join(c['systems'])} | "
                        f"techniques: {', '.join(c['techniques'])} | "
                        f"theme: {c['theme_consensus']}"
                    )
                lines.append("")
                return lines  # Skip raw dumps — LLM has mathematically proven windows

        # Profection years — show ALL so LLM can compare across full timeline
        if profecs:
            lines.append(f"Full Profection Timeline (relevant houses for this question: {relevant_houses}):")
            for p in profecs:
                h_act = p.get("activated_house")
                marker = " ◀ RELEVANT" if h_act in relevant_houses else ""
                lines.append(f"  {p.get('year')}: H{h_act} activates, "
                             f"sign={p.get('profected_sign')}, TL={p.get('time_lord')}{marker}")

        # Future storm windows — show ALL viable windows so LLM can compare
        future_windows = self._future_storm_windows(temporal_clusters, max_windows=15)
        if future_windows:
            lines.append("Future storm windows (multi-system convergences):")
            for i, c in enumerate(future_windows, 1):
                start = _jd_to_str(c.get("start_jd", 0))
                end   = _jd_to_str(c.get("end_jd",   0))
                label = c.get("confidence_label", "?")
                score = c.get("convergence_score", 0)
                n_sys = c.get("n_systems", 1)
                sys_l = ", ".join(c.get("systems_involved", ["?"]))
                techs = "; ".join(
                    f"{ev.get('technique','?')} ({ev.get('system','?')})"
                    for ev in c.get("events", [])[:3]
                )
                lines.append(f"  [{i}] {start}–{end} | {label} ({score:.2f}) | {n_sys} systems: {sys_l}")
                lines.append(f"       {techs}")

        # Outer planet transit hits to relevant planets
        transit_hits = self._future_transit_hits(outer, relevant_planets=None)
        relevant_hits = [h for h in transit_hits
                         if h.get("transiting") in relevant_planets
                         or h.get("natal_point") in relevant_planets][:20]
        if relevant_hits:
            lines.append("Outer planet transit hits (future, to question-relevant planets):")
            for h in relevant_hits:
                planet   = h.get("transiting") or h.get("planet", "?")
                iso_date = h.get("exact_date_iso") or h.get("exact_date", "?")
                entry    = h.get("entry_date", "")
                exit_    = h.get("exit_date",  "")
                lines.append(f"  {iso_date}: {planet} {h.get('aspect','?')} "
                             f"natal {h.get('natal_point','?')}  "
                             f"[window: {entry}–{exit_}]")

        # Primary Directions — show more arcs for full landscape
        all_dirs = []
        for cat in primary_dirs.values():
            if isinstance(cat, list):
                all_dirs.extend(cat[:4])
        if all_dirs:
            lines.append("Primary Directions (future arcs — Gold Standard timing):")
            for d in all_dirs[:10]:
                lines.append(f"  {json.dumps(d, default=str)}")

        # Progressions
        for pname in relevant_planets:
            pk = f"Progressed_{pname}"
            if pk in progressions:
                pd = progressions[pk]
                lines.append(f"  {pk}: {pd.get('degree',0):.1f}° {pd.get('sign','?')} "
                             f"{'(Rx)' if pd.get('retrograde') else ''}")

        # Da Yun (10-year luck pillars) — critical for timing questions
        da_yun = b_pred.get("da_yun", {})
        da_yun_pillars = da_yun.get("pillars", [])
        if da_yun_pillars:
            lines.append(f"Bazi Da Yun (10-year luck pillars, direction={da_yun.get('direction','?')}):")
            for dy in da_yun_pillars:
                if isinstance(dy, dict):
                    lines.append(f"  Age {dy.get('start_age','?')}-{dy.get('end_age','?')}: "
                                 f"{dy.get('stem','?')}{dy.get('branch','?')} "
                                 f"({dy.get('stem_element','?')}/{dy.get('branch_element','?')})")

        # Solar Returns (Gold Standard annual timing)
        solar_returns = w_pred.get("solar_returns", [])
        if solar_returns:
            lines.append("Solar Returns (Gold Standard — annual chart, future only):")
            for sr in solar_returns[:10]:
                if isinstance(sr, dict):
                    sr_date = sr.get("date", "?")
                    sr_asc = sr.get("ascendant", sr.get("asc_sign", "?"))
                    sr_mc = sr.get("mc_sign", sr.get("midheaven", "?"))
                    lines.append(f"  {sr_date}: SR Asc={sr_asc}, MC={sr_mc}")

        # Tajaka (Vedic solar return) — can be a list of yearly dicts or a single dict
        tajaka_raw = v_pred.get("tajaka", [])
        tajaka_list = tajaka_raw if isinstance(tajaka_raw, list) else [tajaka_raw] if isinstance(tajaka_raw, dict) else []
        if tajaka_list:
            lines.append("Tajaka (Vedic Solar Return):")
            for taj in tajaka_list[:5]:
                if not isinstance(taj, dict):
                    continue
                muntha = taj.get("muntha", taj.get("muntha_sign", "?"))
                year = taj.get("year", "?")
                lord = taj.get("lord_of_year", taj.get("year_lord", "?"))
                lines.append(f"  {year}: Muntha={muntha}, Year Lord={lord}")
                sahams = taj.get("sahams", {})
                if isinstance(sahams, dict):
                    for sname, sdata in list(sahams.items())[:3]:
                        if isinstance(sdata, dict):
                            lines.append(f"    Saham {sname}: {sdata.get('sign', '?')}")

        # Liu Nian relevant years — full 15-year window
        lines.append("Bazi Liu Nian (annual pillars 2026-2040):")
        for ln in liu_nian[:15]:
            if isinstance(ln, dict):
                yr     = ln.get("year", "?")
                pillar = f"{ln.get('stem','?')}{ln.get('branch','?')}"
                s_el   = ln.get("stem_element", "?")
                b_el   = ln.get("branch_element", "?")
                gods   = ln.get("ten_gods", {})
                god_str = (" | " + ", ".join(f"{k}={v}" for k, v in gods.items() if v)) if gods else ""
                lines.append(f"  {yr}: {pillar} ({s_el}/{b_el}){god_str}")

        # Dasha sub-periods (antardasha timeline)
        antar_timeline = dasha.get("antardasha_timeline", [])
        if antar_timeline:
            lines.append("Vimshottari Antardasha timeline (sub-periods):")
            for ad in antar_timeline:
                if isinstance(ad, dict):
                    lines.append(f"  {ad.get('lord','?')}: {ad.get('start','?')} – {ad.get('end','?')}")

        # Kakshya transit peak windows (Ashtakavarga-scored timing)
        kakshya = chart_data.get("kakshya_transit", {})
        peak_windows = kakshya.get("peak_windows", [])
        if peak_windows:
            relevant_peaks = [
                pw for pw in peak_windows
                if isinstance(pw, dict) and pw.get("planet") in relevant_planets
            ][:8]
            if relevant_peaks:
                lines.append("Kakshya transit peak windows (Ashtakavarga-scored, relevant planets):")
                for pw in relevant_peaks:
                    lines.append(f"  {pw.get('planet','?')} in {pw.get('sign','?')}: "
                                 f"{pw.get('start_date','?')}–{pw.get('end_date','?')} | "
                                 f"quality={pw.get('quality','?')}, SAV={pw.get('sav','?')}")

        return lines

    def build_evidence_block(self,
                              question: str,
                              chart_data: dict,
                              temporal_clusters: list,
                              ref: dict,
                              question_num: int,
                              validation_matrix=None,
                              target_houses: list = None) -> str:
        """
        Build a tailored, future-filtered evidence block for a single question.
        Three-tier architecture: Universal → House-based → Timing.

        target_houses: Pre-detected house numbers from QueryEngine's structured
          LLM call.  Merged with keyword-detected houses to ensure no topic is
          missed due to misspelled keywords.
        """
        w_nat = chart_data.get("western", {}).get("natal", {})
        v_nat = chart_data.get("vedic",   {}).get("natal", {})

        # Detect relevant houses from question text, merge with pre-detected
        relevant_houses  = self._detect_houses(question)
        if target_houses:
            relevant_houses = sorted(set(relevant_houses) | set(target_houses))
        # Collect all significator planets for those houses
        relevant_planets = list({
            planet
            for h in relevant_houses
            for planet in self.HOUSE_SIGNIFICATORS.get(h, [])
        })
        # Always include core timing planets
        for p in ["Saturn", "Jupiter", "Sun", "Moon"]:
            if p not in relevant_planets:
                relevant_planets.append(p)

        lines = [f"═══ EVIDENCE BLOCK: Question {question_num} ═══"]
        lines.append(f"QUESTION: {question}")
        lines.append(f"HOUSES DETECTED: {relevant_houses}")
        lines.append(f"KEY PLANETS: {relevant_planets}")
        lines.append(f"TODAY: {self.today_str}  ← Hard boundary. Every date must be after this.")
        lines.append("")

        # ── HOUSE LORD VERIFICATION TABLE ──────────────────────────────────
        # Use the full pre-computed reference block (Western + Vedic + Bazi)
        # from orchestrator._compute_house_lords() — prevents hallucination
        lord_ref = chart_data.get("_house_lord_reference_block", "")
        if lord_ref:
            lines.append(lord_ref)
        else:
            # Fallback: compute Western-only from chart data
            w_houses = w_nat.get("houses", {})
            lines.append("── HOUSE LORD VERIFICATION (use these, not memory) ──")
            for h in range(1, 13):
                wh = w_houses.get(f"House_{h}", {})
                cusp_sign = (wh.get("sign") or wh.get("cusp_sign") or
                             wh.get("sign_name", "?"))
                lord = self.SIGN_RULERS.get(cusp_sign, "?")
                lines.append(f"  H{h}: cusp={cusp_sign} → lord={lord}")
            lines.append("CRITICAL: These are the actual house lords for THIS chart.")
        lines.append("")

        # TIER 1 — Universal
        lines.extend(self._build_tier1_universal(chart_data, ref))
        lines.append("")

        # TIER 2 — House routing
        lines.extend(self._build_tier2_house_routing(
            relevant_houses, chart_data, ref, w_nat, v_nat))
        lines.append("")

        # TIER 3 — Future timing
        # Derive domain keywords from detected houses for cluster filtering
        domain_keywords: list = []
        if validation_matrix is not None:
            from synthesis.validation_matrix import ValidationMatrix
            for h in relevant_houses:
                domain_keywords.extend(ValidationMatrix.HOUSE_THEMES.get(h, []))
        lines.extend(self._build_tier3_timing(
            relevant_planets, relevant_houses, chart_data, ref, temporal_clusters,
            validation_matrix=validation_matrix, domain_keywords=domain_keywords))

        lines.append("")
        lines.append(f"═══ END EVIDENCE: Question {question_num} ═══")
        return "\n".join(lines)


class Archon:
    """Master narrative architect for the 13-Section Celestial Dossier."""

    # ── Model selection per section type ─────────────────────────────────────
    # Override in config.py/settings if desired.
    MODEL_MAP = {
        "oracle":          getattr(settings, "archon_model", "gpt-4o"),
        "natal":           getattr(settings, "archon_model", "gpt-4o"),
        "current":         getattr(settings, "archon_model", "gpt-4o"),
        "year_forecast":   getattr(settings, "archon_model", "gpt-4o"),
        "almanac_summary": getattr(settings, "archon_model", "gpt-4o"),
        "directive":       getattr(settings, "archon_model", "gpt-4o"),
    }

    TEMP_MAP = {
        "oracle":          0.0,    # deterministic — evidence retrieval
        "natal":           0.0,    # deterministic — evidence retrieval
        "current":         0.0,    # deterministic — evidence retrieval
        "year_forecast":   0.0,    # deterministic — evidence retrieval
        "almanac_summary": 0.0,    # deterministic — evidence retrieval
        "directive":       0.0,    # deterministic — evidence retrieval
        "questions":       0.0,    # deterministic — evidence retrieval
    }

    # gemini-2.5-pro counts thinking tokens against max_output_tokens.
    # At reasoning_effort="low": ~300-500 thinking tokens consumed.
    # Budget = (prose_words × 1.5 tokens/word) + 800 thinking buffer.
    MAX_TOKENS_MAP = {
        "oracle":          1800,   # target ~220w prose + 800 thinking buffer (shorter cold read)
        "natal":           4500,   # target ~460w prose + 800 thinking buffer (mechanisms format)
        "current":         2000,   # target ~155w prose + 800 thinking buffer
        "year_forecast":   5500,   # target ~620w prose + 800 thinking buffer
        "almanac_summary": 6000,   # target ~900w + technique citations + The Chain paragraph
        "directive":       4000,   # target ~540w prose (15yr orders × 2) + 800 buffer
        "questions":      18000,   # 5 questions × ~700-800w + timing landscape + evidence blocks
    }

    # Keep thinking minimal for creative writing — output tokens matter more than reasoning depth
    ARCHON_REASONING_EFFORT = "low"

    # ── Evidence Plan schema for two-pass generation ─────────────────────────
    # First pass: LLM outputs structured JSON declaring which facts it will cite.
    # Second pass: validated plan constrains prose generation.
    EVIDENCE_PLAN_SCHEMA = {
        "type": "object",
        "properties": {
            "section_theme": {"type": "string"},
            "planet_citations": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "planet":            {"type": "string"},
                        "degree_dms":        {"type": "string"},
                        "sign":              {"type": "string"},
                        "house":             {"type": "integer"},
                        "role_in_argument":  {"type": "string"},
                    },
                    "required": ["planet", "degree_dms", "sign"],
                },
            },
            "transit_citations": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "transiting_planet": {"type": "string"},
                        "aspect":            {"type": "string"},
                        "natal_point":       {"type": "string"},
                        "exact_date":        {"type": "string"},
                        "entry_date":        {"type": "string"},
                        "exit_date":         {"type": "string"},
                        "significance":      {"type": "string"},
                    },
                    "required": ["transiting_planet", "aspect", "natal_point"],
                },
            },
            "dasha_citations": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "level":     {"type": "string"},
                        "lord":      {"type": "string"},
                        "relevance": {"type": "string"},
                    },
                    "required": ["level", "lord"],
                },
            },
            "storm_windows": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "window_id":  {"type": "string"},
                        "start_date": {"type": "string"},
                        "end_date":   {"type": "string"},
                        "score":      {"type": "number"},
                        "usage":      {"type": "string"},
                    },
                    "required": ["window_id", "start_date", "end_date"],
                },
            },
            "key_claims": {
                "type": "array",
                "items": {"type": "string"},
            },
        },
        "required": ["section_theme", "planet_citations", "key_claims"],
    }

    # ── Domain Ledger schema — structured extraction of expert findings ────────
    DOMAIN_LEDGER_SCHEMA = {
        "type": "object",
        "properties": {
            "domains": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "domain": {"type": "string"},
                        "bullets": {"type": "array", "items": {"type": "string"}},
                    },
                    "required": ["domain", "bullets"],
                },
            },
        },
        "required": ["domains"],
    }

    def __init__(self):
        # Issue 5: caches year chapter summaries so Q&A can reference them
        self._almanac_cache: dict = {}
        # Cross-section memory: tracks key predictions from each generated section
        # so subsequent sections can be constrained to consistency
        self._section_memory: list = []
        # Verdict ledger: binding constraints from the Arbiter
        self._verdict_ledger_block: str = ""

    def _generate_single_section(
        self, sec_num: int, sd: dict, arbiter_synthesis: dict,
        chart_data: dict, ref: dict, cluster_block: str,
        temporal_clusters: list, clean_questions: list,
        query_context: dict, expert_block: str,
        wealth_block: str, wealth_score: float,
        citation_registry: dict, expert_analyses: list,
        correction_note: str = "",
    ) -> Optional[str]:
        """Generate a single section (evidence plan → prose → validation).

        Thread-safe: reads only from immutable inputs (ref, chart_data,
        arbiter_synthesis) and stateless validators. Section memory is
        NOT updated here — caller handles that after all futures complete.

        correction_note: Phase 3.2 — if provided, appended to the prompt
        to fix voice consistency issues detected in a previous generation.
        """
        prompt = self._build_section_prompt(
            sec_num, sd, arbiter_synthesis, chart_data, ref,
            cluster_block, temporal_clusters_raw=temporal_clusters or [],
            user_questions=clean_questions if sd["id"] == "questions" else None,
            wealth_block=wealth_block if sd["id"] == "material_world" else None,
            wealth_score=wealth_score if sd["id"] in ("material_world", "directive", "questions") else None,
            query_context=query_context,
            expert_block=expert_block,
        )
        sys_prompt = self._get_system_prompt(sd)

        # Two-pass evidence-validated generation
        evidence_plan = self._generate_evidence_plan(
            prompt, sd, citation_registry)
        if evidence_plan:
            validated_plan = self._validate_evidence_plan(
                evidence_plan, citation_registry, ref=ref)
            prose_prompt = self._build_prose_from_plan(
                prompt, validated_plan, sd)
        else:
            prose_prompt = prompt  # graceful degradation

        # Phase 3.2: Append correction note if regenerating for voice consistency
        if correction_note:
            prose_prompt += f"\n\n═══ CORRECTION NOTE ═══\n{correction_note}\n═══════════════════════"

        response = gateway.generate(
            system_prompt=sys_prompt,
            user_prompt=prose_prompt,
            model=self.MODEL_MAP.get(sd["type"], settings.archon_model),
            max_tokens=self.MAX_TOKENS_MAP.get(sd["type"], 5000),
            temperature=self.TEMP_MAP.get(sd["type"], 0.0),
            reasoning_effort=(
                "high" if sd.get("id") == "questions"
                else "medium" if sd.get("type") in ("year_forecast", "almanac_summary")
                else self.ARCHON_REASONING_EFFORT
            ),
        )

        if response.get("success"):
            content = response["content"]
            content = self._enforce_section_header(content, sd)
            content = self._post_validator.validate_section(content, sec_num)
            content = self._audit_past_dates(content, sec_num)
            content = self._validate_citations(content, citation_registry)
            if expert_analyses:
                content = self._validate_consensus_claims(content, expert_analyses)
            return content
        else:
            err = response.get("error", "Unknown error")
            logger.error(f"Section {sec_num} ({sd['id']}) failed: {err}")
            return f"\n\n# {sd['header']}\n\n**[Generation Failed: {err}]**\n\n"

    def generate_report(self,
                        arbiter_synthesis: dict,
                        chart_data: dict,
                        metadata: dict,
                        temporal_clusters: list = None,
                        user_questions: list = None,
                        query_context: dict = None,
                        expert_analyses: list = None,
                        language: str = "en",
                        original_questions: list = None,
                        verdict_ledger: dict = None,
                        citation_data: dict = None,
                        validation_matrix=None) -> dict:
        """
        Generate the Celestial Dossier.
        user_questions: list of up to 5 question strings (English).
        query_context: pre-built QueryContext dict from QueryEngine.
          If provided, steers every section toward the user's questions.
          If not provided but user_questions is, a simple Part IV is still generated.
        expert_analyses: list of dicts with keys 'system' and 'analysis' — raw expert
          outputs passed directly, bypassing Arbiter truncation (Issue 3).
        language: "en" for English, "my" for Burmese (Myanmar). Burmese generates
          both English and Burmese reports.
        original_questions: original Burmese question strings (if input was Burmese),
          used to display the original phrasing in the translated report.
        verdict_ledger: dict with 'entries' and 'formatted_block' — binding predictions
          from the Arbiter that all downstream sections must be consistent with.
        citation_data: dict with 'top_predictions_block', 'per_house_blocks', 'formatter'
          — evidence citation chains for traceable predictions.

        Returns: dict with keys "en" (always) and optionally "my".
        """
        ref           = self._extract_reference_positions(chart_data)
        cluster_block = _format_clusters(temporal_clusters or [])

        # Compute wealth score deterministically (no API call)
        wealth_score  = _compute_wealth_score(chart_data, ref)
        wealth_block  = _format_wealth_score_block(wealth_score)

        # Domain Ledger: structured extraction replaces character truncation
        expert_block = self._build_domain_ledger(expert_analyses)
        if not expert_block:
            # Graceful degradation: fall back to truncated expert block
            expert_block = self._build_expert_block(expert_analyses)

        # Build citation registry for post-generation validation
        citation_registry = self._build_citation_registry(chart_data, ref, temporal_clusters or [])

        # Store verdict ledger for injection into all section prompts
        self._verdict_ledger_block = (verdict_ledger or {}).get("formatted_block", "")

        # Store citation chains for injection into predictive sections
        self._citation_block = (citation_data or {}).get("top_predictions_block", "")
        self._citation_per_house = (citation_data or {}).get("per_house_blocks", {})
        self._citation_formatter = (citation_data or {}).get("formatter", None)

        # Reset per-run state
        self._almanac_cache = {}
        self._section_memory = []
        self._hard_rules = []
        self._validation_matrix = validation_matrix
        self._query_context = query_context

        # Initialize universal post-generation validator
        self._post_validator = PostValidator(chart_data)

        header   = self._generate_header(metadata, chart_data, ref)
        sections = []
        total    = len(SECTION_DEFS)

        clean_questions = [q.strip() for q in (user_questions or []) if q and q.strip()][:5]

        # Resolve which parts to generate
        active_parts = set(settings.include_parts)
        # Legacy alias: include_directive=False removes "III"
        if not settings.include_directive and "III" in active_parts:
            active_parts.discard("III")
        print(f"   [Archon] Active parts: {sorted(active_parts)}")

        # ── Batched Parallel Section Generation ──────────────────────────
        # Sections within a Part are thematically independent and can run
        # in parallel. Between Parts, _section_memory must synchronize.
        from concurrent.futures import ThreadPoolExecutor, as_completed

        PART_ORDER = ["I", "II", "III", "IV"]

        with ThreadPoolExecutor(max_workers=15) as executor:
            for part in PART_ORDER:
                if part not in active_parts:
                    continue

                # Collect sections for this part
                part_sections = [
                    (n, SECTION_DEFS[n]) for n in sorted(SECTION_DEFS.keys())
                    if SECTION_DEFS[n]["part"] == part
                    and not (SECTION_DEFS[n]["id"] == "questions" and not clean_questions)
                ]

                if not part_sections:
                    continue

                # Part IV (questions) always sequential — needs hard rules from Part III
                if part == "IV":
                    for sec_num, sd in part_sections:
                        print(f"   [Archon] Generating section {sec_num + 1}/{total}: {sd['title']}...")
                        if sd["id"] == "questions" and clean_questions:
                            try:
                                content = self._generate_questions_via_pipeline(
                                    questions=clean_questions,
                                    chart_data=chart_data,
                                    ref=ref,
                                    temporal_clusters=temporal_clusters or [],
                                    citation_registry=citation_registry,
                                    verdict_ledger_block=self._verdict_ledger_block,
                                )
                                content = self._post_validator.validate_section(content, sec_num, is_qa=True)
                                content = self._audit_past_dates(content, sec_num)
                                content = self._validate_citations(content, citation_registry)
                                if expert_analyses:
                                    content = self._validate_consensus_claims(content, expert_analyses)
                                sections.append(content)
                                self._extract_section_predictions(sd, content)
                                continue
                            except Exception as e:
                                logger.error(f"QA pipeline failed, falling back to monolithic: {e}")
                                sd["_pipeline_failed"] = True

                        # Monolithic fallback for questions or non-question Part IV sections
                        result_content = self._generate_single_section(
                            sec_num, sd, arbiter_synthesis, chart_data, ref,
                            cluster_block, temporal_clusters, clean_questions,
                            query_context, expert_block, wealth_block, wealth_score,
                            citation_registry, expert_analyses,
                        )
                        if result_content:
                            sections.append(result_content)
                    print(f"   [Archon] Part {part} complete ({len(part_sections)} sections)")
                    continue

                # Submit all sections in this part in parallel
                futures = {}
                for sec_num, sd in part_sections:
                    print(f"   [Archon] Submitting section {sec_num + 1}/{total}: {sd['title']}...")
                    fut = executor.submit(
                        self._generate_single_section,
                        sec_num, sd, arbiter_synthesis, chart_data, ref,
                        cluster_block, temporal_clusters, clean_questions,
                        query_context, expert_block, wealth_block, wealth_score,
                        citation_registry, expert_analyses,
                    )
                    futures[fut] = (sec_num, sd)

                # Collect results in section order
                part_results = {}
                for fut in as_completed(futures):
                    sec_num, sd = futures[fut]
                    try:
                        content = fut.result()
                        part_results[sec_num] = (sd, content)
                    except Exception as e:
                        logger.error(f"Section {sec_num} ({sd['id']}) parallel gen failed: {e}")
                        part_results[sec_num] = (
                            sd, f"\n\n# {sd['header']}\n\n**[Generation Failed: {e}]**\n\n"
                        )

                # Append in order and update section memory
                for sec_num in sorted(part_results.keys()):
                    sd, content = part_results[sec_num]
                    if content:
                        sections.append(content)
                        self._extract_section_predictions(sd, content)
                        if sd.get("id") == "directive":
                            self._extract_hard_rules(content)
                        if sd.get("type") == "year_forecast":
                            year_key = str(sd.get("target_year", ""))
                            if year_key:
                                self._almanac_cache[year_key] = content[:2000]

                print(f"   [Archon] Part {part} complete ({len(part_results)} sections)")

        # ── Assemble English report ────────────────────────────────────────
        generated_sec_nums = [
            n for n in sorted(SECTION_DEFS.keys())
            if not (SECTION_DEFS[n]["id"] == "questions" and not clean_questions)
            and not (SECTION_DEFS[n]["part"] == "III" and not settings.include_directive)
        ]
        english_report = self._assemble_report(
            header, sections, generated_sec_nums, clean_questions, temporal_clusters
        )

        # ── Phase 3.2: Voice Consistency Verification ────────────────────
        consistency_issues = self._check_voice_consistency(sections, generated_sec_nums)
        if consistency_issues:
            logger.warning(f"Voice consistency check found {len(consistency_issues)} issues")
            for issue in consistency_issues:
                if issue.get("severity") == "HIGH":
                    # Regenerate offending section with corrective instruction
                    sec_idx = issue.get("section_index")
                    if sec_idx is not None and 0 <= sec_idx < len(sections):
                        logger.info(f"Regenerating section {sec_idx} due to HIGH severity issue")
                        sec_num = generated_sec_nums[sec_idx]
                        sd = SECTION_DEFS[sec_num]
                        corrected = self._generate_single_section(
                            sec_num, sd, arbiter_synthesis, chart_data, ref,
                            cluster_block, temporal_clusters, clean_questions,
                            query_context, expert_block, wealth_block, wealth_score,
                            citation_registry, expert_analyses,
                            correction_note=f"CORRECTION REQUIRED: {issue.get('issue', '')}",
                        )
                        if corrected:
                            sections[sec_idx] = corrected
                            # Reassemble after correction
                            english_report = self._assemble_report(
                                header, sections, generated_sec_nums,
                                clean_questions, temporal_clusters
                            )

        result = {"en": english_report}

        # ── Burmese translation pass (Phase 2.5: concurrent) ──────────────
        if language == "my":
            glossary = self._load_burmese_glossary()
            if glossary:
                print("   [Archon] Translating report to Burmese (concurrent)...")
                burmese_header = self._translate_header(header, glossary)

                # Phase 2.5: Translate all sections concurrently via thread pool
                # Each _translate_section() calls gemini-2.5-flash (translation_model)
                # Sequential: ~30s for 10 sections. Concurrent: ~5s.
                from concurrent.futures import ThreadPoolExecutor

                section_data = list(zip(generated_sec_nums, sections))

                def _translate_one(args):
                    idx, sec_num, eng_content = args
                    sd = SECTION_DEFS[sec_num]
                    print(f"   [Archon] Translating {idx+1}/{len(section_data)}: {sd['title']}...")
                    return self._translate_section(
                        eng_content, glossary, sd.get("type", "")
                    )

                with ThreadPoolExecutor(max_workers=min(len(section_data), 8)) as pool:
                    burmese_sections = list(pool.map(
                        _translate_one,
                        [(i, sn, ec) for i, (sn, ec) in enumerate(section_data)],
                    ))

                burmese_report = self._assemble_report(
                    burmese_header, burmese_sections, generated_sec_nums,
                    original_questions or clean_questions, temporal_clusters,
                    burmese=True, glossary=glossary
                )
                result["my"] = burmese_report
            else:
                logger.error("Burmese glossary not found — skipping translation")

        return result

    def _assemble_report(self, header: str, sections: list,
                         generated_sec_nums: list, clean_questions: list,
                         temporal_clusters: list, burmese: bool = False,
                         glossary: dict = None) -> str:
        """Assemble final report from header + sections with part dividers."""
        full_report = header

        # Dashboard — immediately after header, before Part I
        show_dashboard = temporal_clusters and not clean_questions
        if show_dashboard:
            full_report += _compute_year_dashboard(temporal_clusters)

        if burmese and glossary:
            part_labels = self._get_burmese_part_labels(glossary)
        else:
            part_labels = {
                "I":   "\n\n---\n\n# PART I: THE NATIVITY\n\n---\n\n",
                "II":  "\n\n---\n\n# PART II: THE FIFTEEN-YEAR ALMANAC\n\n---\n\n",
                "III": "\n\n---\n\n# PART III: THE DIRECTIVE\n\n---\n\n",
                "IV":  "\n\n---\n\n# PART IV: YOUR QUESTIONS\n\n---\n\n",
            }

        current_part = None
        for sec_num, sec_content in zip(generated_sec_nums, sections):
            sd   = SECTION_DEFS[sec_num]
            part = sd["part"]
            if part != current_part:
                full_report += part_labels[part]
                current_part = part
            full_report += sec_content + "\n\n"

        if burmese:
            full_report += (
                "\n\n---\n\n"
                "*ဂြိုဟ်အနေအထားအားလုံးကို Swiss Ephemeris ဖြင့် အတည်ပြုထားပါသည်။ "
                "အယ်ဂိုရစ်သမ် ပေါင်းစပ်မှုနှင့် စနစ်ဗိသုကာ - Kyaw Ko Ko*"
            )
        else:
            full_report += (
                "\n\n---\n\n"
                "*All planetary positions verified against Swiss Ephemeris. "
                "Primary Direction arcs calculated via Regiomontanus method. "
                "Parans computed using RAMC horizon-crossing method (Brady 1998)."
                "Algorithmic synthesis and system architecture by Kyaw Ko Ko*"
            )

        return full_report

    # ─────────────────────────────────────────────────────────────────────────
    # System Prompt Selector
    # ─────────────────────────────────────────────────────────────────────────

    # Global narrative guardrails applied to EVERY section
    _GLOBAL_NARRATIVE_RULES = """
ABSOLUTE RULES (apply to ALL sections):
1. NEVER output numerical scores, convergence values, or confidence percentages.
   Use ONLY natural-language confidence tiers: "near-certain", "high-confidence",
   "moderate", "emerging". Express certainty through prose, not numbers.
2. NEVER use absolute certainty language: "absolute", "non-negotiable", "guaranteed",
   "100%", "certain beyond doubt", "my certainty is absolute". Always preserve space
   for free will and agency. Use: "strongly indicated", "the pattern powerfully
   suggests", "the evidence overwhelmingly points to".
3. NEVER give specific legal, financial, or medical advice. Do not cite specific
   percentages for ownership, contract terms, dosages, or investment products.
   Frame actionable guidance as: "the astrological pattern suggests consulting
   a [financial advisor/solicitor/GP] about [topic]".
4. SHADBALA INTEGRITY (HIGH PRIORITY): When a planet driving a positive prediction
   is SEVERELY WEAKENED (< 3.5 Rupas) in Shadbala, you MUST:
   (a) Name the weakness explicitly: "despite [planet]'s constitutionally low reserves..."
   (b) Either cite a cancellation yoga or dasha support that compensates, OR
   (c) Downgrade the prediction: "this outcome requires conscious effort and may
       arrive with greater difficulty than the timing alone suggests."
   NEVER predict "peaks of vitality" or "effortless success" for a weak planet.
5. NEVER calculate or deduce planetary rulerships yourself. You MUST ONLY use the
   house lordships explicitly provided in the HOUSE LORD REFERENCE block. If you
   cannot find the lord for a house in the reference, do not claim one.
6. NEVER refer to yourself by any name or title in the output. Never use first-person
   pronouns (I, me, my) unless quoting the client. Never use "As your [title]...",
   "To/From" headers, or letter-style formatting. Write in authoritative advisory voice.
7. SYSTEM INTEGRITY: Western Tropical transit dates use Tropical house lords.
   Vedic techniques (Dasha, Tajaka, Yogas) use Sidereal house lords.
   NEVER cross-apply: e.g., do not say "Jupiter conjunct Sun activates the
   5th house lord" if the house lord comes from the wrong zodiac system.
   When systems agree on an outcome through DIFFERENT mechanisms, state both.
8. BANNED WORDS (never use these in any section):
   journey, tapestry, dance, weave, cosmic, realm, vibration, manifest,
   manifestation, universe, perhaps, maybe, might suggest, intricate,
   multifaceted, dynamic interplay, embody, explore, trust yourself,
   remember that, you deserve, nurture, this is not speculation.
   Use instead: path, structure, outcome, complex, capacity, examine, develop.
9. ZODIACAL RELEASING FRAMING (MANDATORY):
   Zodiacal Releasing defines thematic life chapters lasting months to years.
   NEVER use acute-trigger language for ZR: "activates on [date]", "triggers on",
   "kicks in on", "fires on", "switches on [date]", "key turning in a lock",
   "alarm clock", "switch flips", "mechanism activates".
   ALWAYS use thematic language: "shifts emphasis", "opens a chapter",
   "enters a period characterized by", "a gradual thematic transition".
"""

    def _get_system_prompt(self, sd: dict) -> str:
        t = sd["type"]
        header = sd["header"]
        if t == "oracle":
            base = ORACLE_PROMPT
        elif t == "natal":
            base = NATAL_PROMPT.replace("{HEADER}", header)
        elif t == "current":
            base = CURRENT_CONFIG_PROMPT
        elif t == "year_forecast":
            year = str(sd.get("target_year", ""))
            base = YEAR_FORECAST_PROMPT.replace("{YEAR}", year).replace("{YEAR}", year)
        elif t == "almanac_summary":
            base = ALMANAC_SUMMARY_PROMPT
        elif t == "questions":
            base = QUESTIONS_PROMPT
        elif t == "directive":
            if sd["id"] == "warning":
                base = WARNING_PROMPT
            else:
                base = DIRECTIVE_PROMPT
        else:
            base = NATAL_PROMPT.replace("{HEADER}", header)
        return base + self._GLOBAL_NARRATIVE_RULES

    # ─────────────────────────────────────────────────────────────────────────
    # Section Prompt Builder
    # ─────────────────────────────────────────────────────────────────────────

    def _build_section_prompt(self, sec_num: int, sd: dict,
                               synthesis: dict, chart_data: dict,
                               ref: dict, cluster_block: str,
                               temporal_clusters_raw: list = None,
                               user_questions: list = None,
                               wealth_block: str = None,
                               wealth_score: dict = None,
                               query_context: dict = None,
                               expert_block: str = None) -> str:  # Issue 3
        is_predictive = sd["type"] in ("year_forecast", "current", "directive", "almanac_summary")

        if is_predictive:
            data_block = self._build_predictive_block(ref, chart_data)
        else:
            data_block = self._build_natal_block(ref, chart_data)

        # ── Degradation Warning: tell LLM which systems failed ────────────────
        degraded = chart_data.get("degradation_flags", {})
        if degraded:
            failed = [sys for sys, status in degraded.items() if status == "calculation_failed"]
            if failed:
                warning_lines = [
                    "=== ⚠ SYSTEM DEGRADATION WARNING ===",
                    f"The following systems FAILED during calculation: {', '.join(failed)}.",
                    "You MUST NOT cite evidence from these systems.",
                    "Do NOT invent or hallucinate data for failed systems.",
                    "Base your analysis ONLY on the systems that produced valid data.",
                    "=== END DEGRADATION WARNING ===",
                ]
                data_block = "\n".join(warning_lines) + "\n\n" + data_block

        # ── Query Architecture: inject header_block into data_block ──────────────
        if query_context:
            header = query_context.get("header_block", "")
            if header:
                data_block = header + data_block

        synth_trunc  = self._extract_synthesis_for_section(synthesis, sd)

        extra        = self._section_specific_data(sec_num, sd, chart_data, ref, synthesis)

        # Inject wealth score block into material_world section
        if wealth_block and sd.get("id") == "material_world":
            extra = (
                "=== WEALTH CAPACITY BLOCK (pre-computed from chart data) ===\n"
                + wealth_block
                + "\nInclude this block verbatim as the very first element of the section, "
                  "before any mechanism header. Do NOT add numerical scores or ratings "
                  "beyond what is shown. Present exactly as provided.\n"
                + "=== END WEALTH BLOCK ===\n\n"
                + extra
            )

        # Inject hard financial rules context into directive sections
        if wealth_score and sd.get("id") in ("directive", "warning"):
            industries = ", ".join(wealth_score.get("industries", [])[:4])
            risk = wealth_score.get("risk_flag", False)
            eighth = wealth_score.get("eighth_planets", [])
            tier = wealth_score.get("tier", "")
            hard_rules_ctx = (
                "=== CHART FINANCIAL PROFILE (for Directive hard rules) ===\n"
                f"Wealth Capacity: {tier}\n"
                f"Primary wealth channels: {industries}\n"
            )
            if risk and eighth:
                hard_rules_ctx += (
                    f"RISK FLAG: {chr(39).join(eighth[:3])} in shared-resources zone. "
                    "This chart has a structural vulnerability to financial loss through partnerships.\n"
                    "REQUIRED: The Directive must include at least one HARD RULE about financial "
                    "independence — specific, non-negotiable, written in bold. Example format:\n"
                    "> **HARD RULE: Never sign a 50/50 equity split. Maintain 51%+ control of "
                    "any business you build.**\n"
                )
            hard_rules_ctx += "=== END FINANCIAL PROFILE ===\n"
            extra = hard_rules_ctx + extra

        # ── Query Architecture: inject per-section steering into extra ───────────
        if query_context:
            section_id = sd.get("id", "")
            steering_map = query_context.get("steering", {})
            steering_block = steering_map.get(section_id, "")
            if steering_block:
                extra = steering_block + "\n\n" + extra

        # ── Template Fact Anchoring: inject per-section house lord facts ───────
        # Pre-fills correct house lords so the LLM writes around facts, not guesses
        house_lord_facts = self._build_house_lord_facts(sd, chart_data)
        if house_lord_facts:
            extra = house_lord_facts + "\n\n" + extra

        graph_section = ""
        if _rule_querier is not None:
            try:
                rules = _rule_querier.get_chapter_rules(sec_num, chart_data)
                if rules:
                    graph_section = f"\n{rules}\n"
            except Exception:
                pass

        cluster_section = ""
        if is_predictive and temporal_clusters_raw:
            if sd.get("type") == "year_forecast":
                # Inject only THIS year's windows — prevents cross-year data bleeding
                year = sd.get("target_year")
                year_block = _format_clusters_for_year(temporal_clusters_raw, year) if year else cluster_block
                cluster_section = f"\n{year_block}\n"
            else:
                cluster_section = f"\n{cluster_block}\n"

        min_w, max_w = sd.get("words", (500, 700))

        # Questions section — uses QuestionRouter for tailored per-question evidence
        if sd.get("id") == "questions" and user_questions:
            today = datetime.now(timezone.utc)
            today_str = today.strftime("%Y-%m-%d")
            router = QuestionRouter(today)

            # Build evidence block for each question individually
            evidence_blocks = []
            for i, q in enumerate(user_questions, 1):
                # Pass target_houses from query_context so evidence block
                # covers all relevant houses without keyword guessing
                _target_houses = (
                    query_context.get("target_houses", [])
                    if query_context else []
                )
                eb = router.build_evidence_block(
                    question=q,
                    chart_data=chart_data,
                    temporal_clusters=temporal_clusters_raw or [],
                    ref=ref,
                    question_num=i,
                    validation_matrix=self._validation_matrix,
                    target_houses=_target_houses,
                )
                evidence_blocks.append(eb)

            all_evidence = "\n\n".join(evidence_blocks)

            parts = [
                f"TODAY: {today_str}  ← HARD DATE BOUNDARY. Every date you write MUST be after this.",
                "",
                data_block,
                "=== SYNTHESIS DATA (arbiter) ===",
                synth_trunc,
                "",
            ]

            # Issue 3: inject expert analyses if available
            if expert_block:
                parts += [
                    "=== EXPERT ANALYSES (raw — use for specific observations and vivid detail) ===",
                    expert_block,
                    "=== END EXPERT ANALYSES ===",
                    "",
                ]

            # Inject verdict ledger as binding constraint for Q&A answers
            if self._verdict_ledger_block:
                parts += [self._verdict_ledger_block, ""]

            # Inject evidence citation chains for Q&A answers
            if self._citation_block:
                parts += [self._citation_block, ""]

            # Inject cross-section memory so Q&A is consistent with year chapters
            if self._section_memory:
                memory_block = self._format_section_memory()
                if memory_block:
                    parts += [memory_block, ""]

            # Inject master timeline so Q&A uses same date windows as Almanac
            master_tl = self._build_master_timeline()
            if master_tl:
                parts += [master_tl, ""]

            # Issue 5: inject almanac context so Q&A can reference year windows
            if self._almanac_cache:
                almanac_lines = ["=== ALMANAC CONTEXT (reference these windows when answering timing questions) ==="]
                for yr, snippet in sorted(self._almanac_cache.items()):
                    almanac_lines.append(f"[{yr}]: {snippet}")
                almanac_lines.append("=== END ALMANAC CONTEXT ===")
                parts += almanac_lines + [""]

            parts += [
                "=== TAILORED EVIDENCE BLOCKS (one per question, pre-filtered to future dates) ===",
                "Each block below contains ONLY future-dated data relevant to that specific question.",
                "Use the data in these blocks as your primary source. Do not substitute dates from memory.",
                "",
                all_evidence,
                "",
                "=== WRITE THE ANSWERS ===",
                f"Start with: # {sd['header']}",
                f"Answer {len(user_questions)} question(s) in order. Separate with ---.",
                "For each answer: direct verdict first, then cite 2+ specific dates from the evidence block above.",
                f"TODAY IS {today_str}. Any date before this is FORBIDDEN.",
            ]
            return "\n\n".join(p for p in parts if p)

        parts = [
            data_block,
            "=== SECTION FOCUS ===",
            f"Section: {sd['title']}",
            f"Focus: {sd['focus']}",
            f"Key domains: {', '.join(sd['domains']) if sd['domains'] else 'See focus above'}",
            "=== SYNTHESIS DATA ===",
            synth_trunc,
        ]

        # Issue 3: inject expert analyses for richer source material
        if expert_block:
            parts += [
                "=== EXPERT ANALYSES (raw — draw specific observations from here) ===",
                expert_block,
                "=== END EXPERT ANALYSES ===",
            ]

        # Inject verdict ledger as binding constraint (for predictive sections)
        if is_predictive and self._verdict_ledger_block:
            parts.append(self._verdict_ledger_block)

        # Inject evidence citation chains (for predictive sections)
        if is_predictive and self._citation_block:
            parts.append(self._citation_block)

        # Inject cross-section memory for consistency + deduplication (all sections after first)
        if self._section_memory:
            memory_block = self._format_section_memory()
            if memory_block:
                parts.append(memory_block)

        parts += [
            graph_section,
            cluster_section,
            "=== SECTION-SPECIFIC DATA ===",
            extra,
            f"Write: {sd['title']}",
            "Requirements:",
            f"- Start with exactly: # {sd['header']}",
            f"- Length: {min_w}-{max_w} words",
            f"- {'Use DMS positions from MANDATORY NATAL DATA' if not is_predictive else 'Use exact date windows from TEMPORAL STORM WINDOWS'}",
            "- State system conflicts explicitly",
            "- Every claim must reference specific planetary evidence",
        ]
        return "\n\n".join(p for p in parts if p)

    # ─────────────────────────────────────────────────────────────────────────
    # Two-pass evidence-validated generation
    # ─────────────────────────────────────────────────────────────────────────

    def _generate_evidence_plan(self, prompt: str, sd: dict,
                                 citation_registry: dict):
        """First pass: LLM outputs a structured evidence plan declaring which
        facts it will cite.  Returns validated plan dict, or None on failure."""
        import json as _json

        registry_json = _json.dumps(citation_registry, indent=2, default=str)
        evidence_prompt = (
            "You are planning the evidence for an astrological report section.\n"
            "Given the chart data below, output a JSON evidence plan listing "
            "ONLY facts you can verify from the CITATION REGISTRY.\n"
            "Do NOT invent degrees, dates, or positions.\n\n"
            f"=== CITATION REGISTRY (ground truth) ===\n{registry_json}\n"
            f"=== END REGISTRY ===\n\n"
            f"SECTION DATA AND CONTEXT:\n{prompt}\n\n"
            "Output your evidence plan as JSON matching the schema."
        )

        response = gateway.structured_generate(
            system_prompt="You are a factual evidence planner for astrological reports. "
                          "Extract ONLY verifiable facts from the registry.",
            user_prompt=evidence_prompt,
            output_schema=self.EVIDENCE_PLAN_SCHEMA,
            model=self.MODEL_MAP.get(sd["type"], settings.archon_model),
            max_tokens=3000,
            temperature=0.0,
            reasoning_effort="low",
        )

        if not response.get("success") or not response.get("data"):
            logger.warning(f"Evidence plan failed for {sd.get('id', '?')}: "
                           f"{response.get('error', 'no data')}")
            return None

        return response["data"]

    def _validate_evidence_plan(self, plan: dict, citation_registry: dict,
                                ref: dict = None) -> dict:
        """Validate each fact in the evidence plan against the citation registry
        and ref dict.  Drops invalid claims; overwrites with ground-truth."""

        validated_planets = []
        for pc in plan.get("planet_citations", []):
            planet = pc.get("planet", "")
            registry_val = citation_registry.get(planet, "")
            if not registry_val:
                logger.warning(f"Evidence plan: planet '{planet}' not in registry — dropped")
                continue
            # Force-correct degree/sign from ref (ground truth)
            if ref and planet in ref:
                truth = ref[planet]
                pc["degree_dms"] = truth.get("dms", pc.get("degree_dms", ""))
                pc["sign"] = truth.get("sign", pc.get("sign", ""))
            elif registry_val:
                claimed_sign = pc.get("sign", "")
                if claimed_sign and claimed_sign not in registry_val:
                    logger.warning(f"Evidence plan: {planet} claimed {claimed_sign}, "
                                   f"registry has {registry_val} — correcting")
                    if "'" in registry_val:
                        pc["degree_dms"] = registry_val.split("'")[0] + "'"
                        pc["sign"] = registry_val.split("'")[-1].strip()
            validated_planets.append(pc)

        validated_transits = []
        for tc in plan.get("transit_citations", []):
            key = (f"{tc.get('transiting_planet', '?')}_"
                   f"{tc.get('aspect', '?')}_"
                   f"{tc.get('natal_point', '?')}")
            registry_val = citation_registry.get(key, "")
            if not registry_val:
                logger.warning(f"Evidence plan: transit '{key}' not in registry — dropped")
                continue
            # Overwrite dates with registry ground truth
            for part in registry_val.split(", "):
                if part.startswith("exact "):
                    tc["exact_date"] = part[6:]
                elif part.startswith("entry "):
                    tc["entry_date"] = part[6:]
                elif part.startswith("exit "):
                    tc["exit_date"] = part[5:]
            validated_transits.append(tc)

        validated_dasha = []
        for dc in plan.get("dasha_citations", []):
            level = dc.get("level", "").lower()
            reg_key = "Maha_Dasha" if "maha" in level else "Antar_Dasha"
            if citation_registry.get(reg_key):
                validated_dasha.append(dc)
            else:
                logger.warning(f"Evidence plan: dasha '{level}' not in registry — dropped")

        validated_storms = []
        for sw in plan.get("storm_windows", []):
            wid = sw.get("window_id", "")
            if citation_registry.get(wid):
                validated_storms.append(sw)

        plan["planet_citations"] = validated_planets
        plan["transit_citations"] = validated_transits
        plan["dasha_citations"] = validated_dasha
        plan["storm_windows"] = validated_storms

        logger.info(
            f"Evidence plan validated: {len(validated_planets)} planets, "
            f"{len(validated_transits)} transits, {len(validated_dasha)} dasha, "
            f"{len(validated_storms)} storm windows"
        )
        return plan

    def _build_prose_from_plan(self, original_prompt: str,
                                validated_plan: dict, sd: dict) -> str:
        """Prepend the validated evidence plan to the prose prompt as a
        hard constraint."""
        import json as _json

        plan_json = _json.dumps(validated_plan, indent=2, default=str)
        # Build degree facts block from validated planet_citations
        degree_lines = []
        for pc in validated_plan.get("planet_citations", []):
            p = pc.get("planet", "")
            dms = pc.get("degree_dms", "")
            sign = pc.get("sign", "")
            if p and dms and sign:
                degree_lines.append(f"  {p}: {dms} {sign}")
        degree_block = ""
        if degree_lines:
            degree_block = (
                "\nDEGREE FACTS (BINDING — copy these exactly, do not round or modify):\n"
                + "\n".join(degree_lines) + "\n"
            )

        plan_block = (
            "=== VALIDATED EVIDENCE PLAN (MANDATORY — use ONLY these facts) ===\n"
            f"{plan_json}\n"
            "=== END EVIDENCE PLAN ===\n\n"
            f"{degree_block}\n"
            "CRITICAL RULES:\n"
            "1. You may ONLY cite planets, degrees, dates, and dasha lords "
            "listed in the evidence plan above.\n"
            "2. Do NOT invent, round, or approximate any degree or date "
            "not in the plan. Copy degree strings EXACTLY from DEGREE FACTS.\n"
            "3. Every [bracketed citation] must correspond to an entry in "
            "the evidence plan.\n"
            "4. If the plan has no transit citations, do NOT mention "
            "transit dates.\n"
            "5. You may make interpretive claims, but every factual anchor "
            "must come from the plan.\n\n"
        )
        return plan_block + original_prompt

    # ─────────────────────────────────────────────────────────────────────────
    # Cross-section memory — consistency enforcement
    # ─────────────────────────────────────────────────────────────────────────

    def _extract_section_predictions(self, sd: dict, content: str):
        """Extract key predictions AND explained themes from a generated section.

        Captures:
        1. Date-anchored predictions for consistency (predictive sections only)
        2. Explained mechanisms/themes for deduplication (all sections)
        """
        import re
        section_id = sd.get("id", "unknown")
        predictions = []
        themes_explained = []

        # ── Theme extraction (all sections) ──────────────────────────────────
        # Capture bold mechanism headers like **THE STRUCTURAL AUTHORITY**
        for m in re.finditer(r'\*\*([A-Z][A-Z\s\':–-]{4,50})\*\*', content):
            theme = m.group(1).strip()
            if len(theme) > 5:
                themes_explained.append(theme)

        # Capture planet-theme patterns mentioned in depth (2+ sentences)
        planet_themes = set()
        for planet in ["Saturn", "Jupiter", "Mars", "Venus", "Mercury", "Sun", "Moon"]:
            count = content.count(planet)
            if count >= 3:  # mentioned 3+ times = explained in depth
                planet_themes.add(planet)

        # ── Prediction extraction (predictive sections only) ─────────────────
        if sd.get("type") in ("year_forecast", "almanac_summary", "directive"):
            likely_match = re.search(
                r'(?:What is most likely to happen[^:]*:)\s*(.+?)(?:\n\n|\*\*)',
                content, re.DOTALL
            )
            if likely_match:
                predictions.append(likely_match.group(1).strip()[:300])

            for m in re.finditer(
                r'((?:NEAR-CERTAIN|HIGH-CONFIDENCE)[^\n]*(?:\n[^\n]+){0,2})',
                content
            ):
                pred_text = m.group(1).strip()[:200]
                if pred_text:
                    predictions.append(pred_text)

            action_match = re.search(
                r'(?:The one action \d{4} demands:)\s*(.+?)(?:\n\n|$)',
                content, re.DOTALL
            )
            if action_match:
                predictions.append(action_match.group(1).strip()[:200])

            # Extract HARD RULE text from directive sections for Q&A binding
            if sd.get("id") == "directive":
                for m in re.finditer(r'\*\*HARD RULE[:\s]*\*\*\s*(.+?)(?:\n|$)', content):
                    predictions.append(f"HARD RULE: {m.group(1).strip()}")

        if predictions or themes_explained:
            self._section_memory.append({
                "section": section_id,
                "title": sd.get("title", ""),
                "predictions": predictions[:4],
                "themes": themes_explained[:6],
                "planets_explained": sorted(planet_themes),
            })

    def _extract_hard_rules(self, directive_content: str):
        """Extract HARD RULE constraints from generated Directive section.

        Parses rules into structured form and updates the PostValidator
        so that subsequent Q&A sections are checked for violations.
        """
        import re
        parsed_rules = []
        for m in re.finditer(
            r'\*\*HARD RULE[:\s]*\*\*\s*(.+?)(?:\n|$)', directive_content
        ):
            rule_text = m.group(1).strip()
            parsed = HardRuleEnforcer.parse_hard_rule(rule_text)
            parsed_rules.append(parsed)
            logger.info(f"Extracted hard rule: {rule_text[:80]}...")

        if parsed_rules:
            self._hard_rules = parsed_rules
            self._post_validator.update_hard_rules(parsed_rules)
            logger.info(
                f"PostValidator updated with {len(parsed_rules)} hard rule(s) "
                f"for Q&A enforcement"
            )

    def _format_section_memory(self) -> str:
        """Format cross-section memory into a constraint block for prompts.

        Includes both consistency rules (don't contradict) and dedup rules
        (don't re-explain themes already covered in earlier sections).
        """
        if not self._section_memory:
            return ""

        lines = [
            "═══ CROSS-SECTION MEMORY (previous sections — be consistent, avoid repetition) ═══",
            "CONSISTENCY: Do NOT contradict these predictions. Use the same date windows.",
            "DEDUP: Themes already explained MUST NOT be re-explained. Reference in ONE sentence max.",
            "",
        ]

        all_themes = []
        for mem in self._section_memory[-8:]:
            section_lines = [f"[{mem['title']}]:"]
            for pred in mem.get("predictions", []):
                section_lines.append(f"  • {pred}")
            themes = mem.get("themes", [])
            if themes:
                section_lines.append(f"  Themes covered: {', '.join(themes)}")
                all_themes.extend(themes)
            planets = mem.get("planets_explained", [])
            if planets:
                section_lines.append(f"  Planets explained in depth: {', '.join(planets)}")
            lines.extend(section_lines)
            lines.append("")

        if all_themes:
            lines.append("DO NOT RE-EXPLAIN these themes (one-sentence reference max):")
            for t in dict.fromkeys(all_themes):  # deduplicate while preserving order
                lines.append(f"  ✗ {t}")
            lines.append("")

        lines.append("═══ END CROSS-SECTION MEMORY ═══")
        return "\n".join(lines)

    def _build_master_timeline(self) -> str:
        """Extract key date windows from year chapters for Q&A binding."""
        if not self._section_memory:
            return ""
        lines = [
            "=== MASTER TIMELINE (binding — use these exact date windows) ===",
            "The Almanac sections established these windows. Q&A answers MUST",
            "reference the SAME date ranges for the same events. Do NOT invent",
            "different dates for events already timed in the Almanac.",
        ]
        has_predictions = False
        for mem in self._section_memory:
            preds = mem.get("predictions", [])
            if preds:
                has_predictions = True
                lines.append(f"\n[{mem['title']}]:")
                for pred in preds:
                    lines.append(f"  • {pred}")
        if not has_predictions:
            return ""
        lines.append("\n=== END MASTER TIMELINE ===")
        return "\n".join(lines)

    # ─────────────────────────────────────────────────────────────────────────
    # Section-specific data injections
    # ─────────────────────────────────────────────────────────────────────────

    # ── Template Fact Anchoring ─────────────────────────────────────────────

    # Maps section domains to house numbers that MUST have correct lords cited
    _SECTION_HOUSE_MAP = {
        "material_world":  [2, 6, 10, 11],    # wealth, work, career, gains
        "inner_world":     [5, 7],             # romance, marriage
        "karmic_mandate":  [1, 8, 12],         # self, transformation, liberation
        "year_2026":       [1, 2, 7, 10],      # commonly referenced houses
        "year_2027":       [1, 2, 5, 7, 10],
        "year_2028":       [1, 2, 4, 5, 10],
        "year_2029":       [1, 2, 5, 7, 10],
        "year_2030":       [1, 2, 4, 5, 10],
        "directive":       [2, 5, 7, 10],
        "almanac_summary": [2, 4, 5, 7, 10],
        "questions":       [1, 2, 4, 5, 7, 10],  # broad coverage for Q&A
    }

    def _build_house_lord_facts(self, sd: dict, chart_data: dict) -> str:
        """Build a MANDATORY FACTS block with pre-computed house lords for this section.

        This pre-fills correct house lords into the prompt so the LLM writes
        around verified facts rather than guessing from memory.
        """
        section_id = sd.get("id", "")
        houses = self._SECTION_HOUSE_MAP.get(section_id)
        if not houses:
            return ""

        house_lords = chart_data.get("house_lords", {})
        western_lords = house_lords.get("western_lords", {})
        vedic_lords = house_lords.get("vedic_lords", {})

        if not western_lords and not vedic_lords:
            return ""

        v_natal = chart_data.get("vedic", {}).get("natal", {})
        v_asc_sign = v_natal.get("ascendant_sign", "")
        vedic_sign_list = list({
            "Mesha": "Mars", "Vrishabha": "Venus", "Mithuna": "Mercury",
            "Karka": "Moon", "Simha": "Sun", "Kanya": "Mercury",
            "Tula": "Venus", "Vrischika": "Mars", "Dhanus": "Jupiter",
            "Makara": "Saturn", "Kumbha": "Saturn", "Meena": "Jupiter",
        }.keys())

        # House domain names for context
        HOUSE_DOMAINS = {
            1: "self/body", 2: "wealth/finance", 3: "communication",
            4: "home/property", 5: "children/creativity", 6: "health/work",
            7: "marriage/partnership", 8: "transformation/shared resources",
            9: "higher learning/dharma", 10: "career/public life",
            11: "gains/aspirations", 12: "liberation/loss",
        }

        lines = [
            "=== MANDATORY HOUSE LORD FACTS (pre-computed — use these, NEVER deduce your own) ===",
        ]

        for h in sorted(houses):
            domain = HOUSE_DOMAINS.get(h, "")
            v_lord = vedic_lords.get(h, "")
            w_lord = western_lords.get(h, "")

            # Compute Vedic sign for this house
            v_sign = ""
            if v_asc_sign and v_asc_sign in vedic_sign_list:
                asc_idx = vedic_sign_list.index(v_asc_sign)
                v_sign = vedic_sign_list[(asc_idx + h - 1) % 12]

            parts = []
            if v_lord:
                vedic_desc = f"Vedic: {v_sign + ' → ' if v_sign else ''}{v_lord}"
                parts.append(vedic_desc)
            if w_lord:
                parts.append(f"Western: {w_lord}")

            if parts:
                lines.append(
                    f"  House {h} ({domain}): {' | '.join(parts)}"
                )

        lines.append("When citing house lords, use ONLY the values above. "
                      "If a house lord differs between systems, specify which system.")
        lines.append("=== END HOUSE LORD FACTS ===")

        return "\n".join(lines)

    def _section_specific_data(self, sec_num: int, sd: dict,
                                chart_data: dict, ref: dict,
                                synthesis: dict = None) -> str:
        w_natal = chart_data.get("western", {}).get("natal", {})
        v_natal = chart_data.get("vedic",   {}).get("natal", {})
        w_pred  = chart_data.get("western", {}).get("predictive", {})

        sid = sd["id"]

        # ── Oracle Opening ────────────────────────────────────────────────────
        if sid == "oracle_opening":
            tight = [a for a in w_natal.get("aspects", [])
                     if a.get("orb", 99) <= 2.0][:3]
            yogas = v_natal.get("yogas", [])[:2]
            return (
                f"Tightest aspects (≤2°): {json.dumps(tight, default=str)}\n"
                f"Key yogas: {json.dumps(yogas, default=str)}\n"
                f"Maha Dasha: {ref.get('_maha_dasha')} — Antardasha: {ref.get('_antar_dasha')}\n"
                f"Fixed Star parans: {json.dumps(ref.get('_parans', [])[:4], default=str)}\n"
                f"Chart pattern: {ref.get('_dominant_pattern', 'N/A')}\n"
                f"Almuten: {ref.get('_almuten')} | Hyleg: {ref.get('_hyleg')}\n"
                f"Saju Day Master: {ref.get('_dm_stem', 'N/A')} {ref.get('_dm_tier', 'N/A')} | "
                f"Useful God: {ref.get('_useful_god', 'N/A')}"
            )

        # ── Architecture of Self ──────────────────────────────────────────────
        elif sid == "architecture_of_self":
            tight = [a for a in w_natal.get("aspects", [])
                     if a.get("orb", 99) <= 3.0][:5]
            parans = ref.get("_parans", [])[:4]
            stars  = ref.get("_significant_stars", ref.get("_fixed_stars", []))[:4]
            asc_data = ref.get("Ascendant", {})
            lof_deg  = ref.get("_lot_fortune_deg", "?")
            lof_sign = ref.get("_lot_fortune_sign", "?")
            asc_dms  = asc_data.get("dms", "?")
            asc_sign = asc_data.get("sign", "?")
            # Parans 5-year activation windows
            star_windows = w_natal.get("star_windows", [])
            sw_str = json.dumps(star_windows[:3], default=str) if star_windows else "None"
            # Mutual receptions
            receptions_raw = w_natal.get("receptions", {})
            receptions = list(receptions_raw.values()) if isinstance(receptions_raw, dict) else receptions_raw
            rec_str = json.dumps(receptions[:5], default=str) if receptions else "None"
            return (
                f"Tightest aspects: {json.dumps(tight, default=str)}\n"
                f"Yogas: {json.dumps(v_natal.get('yogas', [])[:3], default=str)}\n"
                f"Chart pattern: {json.dumps(ref.get('_patterns_summary', {}), default=str)}\n"
                f"True Parans (RAMC method): {json.dumps(parans, default=str)}\n"
                f"Fixed Star contacts: {json.dumps(stars, default=str)}\n"
                f"Fixed Star 5-year activation windows: {sw_str}\n"
                f"Mutual Receptions: {rec_str}\n"
                f"Dodecatemoria dominant: {ref.get('_dodec_dominant_sign')} "
                f"(ruler {ref.get('_dodec_dominant_ruler')})\n"
                f"Pre-natal syzygy: {ref.get('_syzygy_type')} in {ref.get('_syzygy_sign')}, "
                f"{ref.get('_syzygy_days_before')} days before birth\n"
                f"⚠️ LOF DISAMBIGUATION — TWO DISTINCT POINTS IN SAME SIGN:\n"
                f"  Ascendant      = {asc_dms} {asc_sign}  ← identity / personality\n"
                f"  Lot of Fortune = {lof_deg} {lof_sign}  ← wealth / circumstances\n"
                f"  These are DIFFERENT positions. Do NOT cite the Ascendant degree as the Lot of Fortune."
            )

        # ── Material World ────────────────────────────────────────────────────
        elif sid == "material_world":
            houses = w_natal.get("houses", {})
            lots   = w_natal.get("lots",   {})
            dirs   = chart_data.get("western", {}).get("predictive", {}).get(
                        "primary_directions", {}).get("career", [])[:3]
            asc_data = ref.get("Ascendant", {})
            lof_deg  = ref.get("_lot_fortune_deg", "?")
            lof_sign = ref.get("_lot_fortune_sign", "?")
            asc_dms  = asc_data.get("dms", "?")
            asc_sign = asc_data.get("sign", "?")
            # Explicit LOF value for material world — prevents Ascendant substitution
            lof_explicit = (
                f"Lot of Fortune = {lof_deg} {lof_sign}  "
                f"(NOT the Ascendant at {asc_dms} {asc_sign} — different point in same sign)"
            )
            return (
                f"⚠️ LOT OF FORTUNE (EXACT): {lof_explicit}\n"
                f"House 2: {json.dumps(houses.get('House_2', {}), default=str)}\n"
                f"House 10: {json.dumps(houses.get('House_10', {}), default=str)}\n"
                f"Lots (all): {json.dumps(lots, default=str)}\n"
                f"MC: {json.dumps(w_natal.get('angles', {}).get('Midheaven', {}), default=str)}\n"
                f"Career Primary Directions: {json.dumps(dirs, default=str)}\n"
                f"Vedic 2nd/11th: {json.dumps(v_natal.get('houses', {}).get('Bhava_2', {}), default=str)}\n"
                f"D10 Sun: {v_natal.get('placements', {}).get('Sun', {}).get('d10', 'N/A')}\n"
                f"Amatyakaraka: {ref.get('_vedic_amatyakaraka')}"
            )

        # ── Inner World ───────────────────────────────────────────────────────
        elif sid == "inner_world":
            desc        = w_natal.get("angles", {}).get("Descendant", {})
            shadbala    = chart_data.get("vedic", {}).get("strength", {}).get("shadbala", {})
            interactions= chart_data.get("bazi", {}).get("natal", {}).get("interactions", {})
            venus_dig   = (w_natal.get("dignities", {})
                                  .get("planet_dignities", {}).get("Venus", {}))
            peach       = next((s for s in chart_data.get("bazi", {})
                                              .get("natal", {}).get("shensha", [])
                                if "Peach" in s.get("type", "")), None)
            receptions_raw = w_natal.get("receptions", {})
            receptions  = list(receptions_raw.values()) if isinstance(receptions_raw, dict) else receptions_raw
            rel_recs    = [r for r in receptions
                           if any(p in r.get("planets", [r.get("planet1",""), r.get("planet2","")])
                                  for p in ("Venus","Moon","Mars","Sun"))][:4]
            return (
                f"Descendant: {json.dumps(desc, default=str)}\n"
                f"House 6: {json.dumps(w_natal.get('houses', {}).get('House_6', {}), default=str)}\n"
                f"House 7: {json.dumps(w_natal.get('houses', {}).get('House_7', {}), default=str)}\n"
                f"Venus dignities: {json.dumps(venus_dig, default=str)}\n"
                f"Mutual Receptions (relational planets): {json.dumps(rel_recs, default=str)}\n"
                f"Darakaraka: {ref.get('_vedic_darakaraka')}\n"
                f"D9 Venus: {v_natal.get('placements', {}).get('Venus', {}).get('d9', 'N/A')}\n"
                f"Peach Blossom: {json.dumps(peach, default=str)}\n"
                f"Shadbala Moon/Mars: "
                f"{json.dumps({k: v for k, v in shadbala.get('planet_scores', {}).items() if k in ['Moon', 'Mars']}, default=str)}\n"
                f"Saju interactions: {json.dumps(interactions, default=str)}"
            )

        # ── Karmic Mandate ────────────────────────────────────────────────────
        elif sid == "karmic_mandate":
            north_node = w_natal.get("placements", {}).get("North Node", {})
            ketu_v     = v_natal.get("placements", {}).get("Ketu", {})
            zr         = chart_data.get("hellenistic", {}).get("zodiacal_releasing", {})
            dodec      = chart_data.get("hellenistic", {}).get("dodecatemoria", {})
            stars      = ref.get("_parans", [])[:4] or ref.get("_significant_stars", [])[:4]
            return (
                f"North Node: {json.dumps(north_node, default=str)}\n"
                f"Ketu (Vedic): {json.dumps(ketu_v, default=str)}\n"
                f"ZR brief: {json.dumps({'fortune_L1': zr.get('fortune', [])[:2], 'spirit_L1': zr.get('spirit', [])[:2]}, default=str)}\n"
                f"Syzygy: {json.dumps(chart_data.get('western', {}).get('natal', {}).get('syzygy', {}), default=str)}\n"
                f"Star fate signatures: {json.dumps(stars, default=str)}\n"
                f"Dodecatemoria Node: {json.dumps(dodec.get('placements', {}).get('North Node', {}), default=str)}"
            )

        # ── Current Configuration ─────────────────────────────────────────────
        elif sid == "current_configuration":
            dasha    = chart_data.get("vedic", {}).get("predictive", {}).get("vimshottari", {})
            outer_t  = w_pred.get("outer_transit_aspects", {}).get("summary_block", "")[:400]
            return (
                f"Maha Dasha: {ref.get('_maha_dasha')} "
                f"({ref.get('_dasha_years_left')} yrs remaining)\n"
                f"Antardasha: {ref.get('_antar_dasha')} "
                f"({ref.get('_antar_dasha_years')} yrs remaining)\n"
                f"Current Profection: {ref.get('_profection_sign')} "
                f"House {ref.get('_profection_house')}, Time Lord: {ref.get('_time_lord')}\n"
                f"Dominant transits today:\n{outer_t}"
            )

        # ── Year Forecast Sections (2026–2030) ───────────────────────────────
        elif sd["type"] == "year_forecast":
            year    = sd.get("target_year", 2026)
            profecs = w_pred.get("profections_timeline", [])
            prof_yr = next((p for p in profecs if p.get("year") == year), {})
            tajaka  = chart_data.get("vedic", {}).get("predictive", {}).get("tajaka", [])
            taj_yr  = next((t for t in tajaka  if t.get("year") == year), {})
            dasha   = chart_data.get("vedic", {}).get("predictive", {}).get("vimshottari", {})
            liu     = [l for l in chart_data.get("bazi", {}).get("predictive", {})
                                 .get("liu_nian_timeline", []) if l.get("year") == year]
            # Kakshya: filter peak_windows for target year (no year-key structure)
            kakshya_data = chart_data.get("vedic", {}).get("predictive", {}).get(
                            "kakshya_transits", {})
            kakshya_peaks = [
                pw for pw in kakshya_data.get("peak_windows", [])
                if str(year) in str(pw.get("start_date", "")) or
                   str(year) in str(pw.get("end_date",   ""))
            ][:4]
            kakshya = {"peak_windows": kakshya_peaks} if kakshya_peaks else {}
            # All transit hits for this year (exact dates)
            outer_all = self._all_transit_hits_for_year(
                w_pred.get("outer_transit_aspects", {}), year
            )
            lr_all  = [l for l in w_pred.get("lunar_returns", [])
                       if str(l.get("year", "")) == str(year)]
            # Surface key monthly anchors: date + confidence score
            lr      = lr_all[:4]  # up to 4 per year (quarterly anchors)
            # Solar return analysis for this year (analyzed SR vs natal)
            sr_analysis = w_pred.get("solar_return_analysis", [])
            sr_yr_analysis = next(
                (a for a in sr_analysis if isinstance(a, dict) and a.get("year") == year), {}
            )
            sr_analysis_str = ""
            if sr_yr_analysis:
                summ = sr_yr_analysis.get("summary", sr_yr_analysis.get("interpretation", ""))
                if summ:
                    sr_analysis_str = str(summ)[:400]
            # Parans star windows active in this year
            star_windows = chart_data.get("western", {}).get("natal", {}).get("star_windows", [])
            sw_yr = [sw for sw in star_windows
                     if str(sw.get("start",""))[:4] == str(year)
                     or str(sw.get("end",""))[:4] == str(year)][:2]
            # Progressed Moon sign changes in target year (Fix 12)
            prog_moon_tl = w_pred.get("prog_moon_timeline", {})
            pm_sign_changes_yr = [
                sc for sc in prog_moon_tl.get("sign_changes", [])
                if str(year) in sc.get("date", "")
            ]
            pm_conjunctions_yr = [
                c for c in prog_moon_tl.get("natal_conjunctions", [])
                if str(year) in c.get("date", "")
            ][:3]
            pm_block = ""
            if pm_sign_changes_yr or pm_conjunctions_yr:
                pm_block = (
                    f"Progressed Moon {year}: "
                    f"sign changes={json.dumps(pm_sign_changes_yr, default=str)}, "
                    f"natal conjunctions={json.dumps(pm_conjunctions_yr, default=str)}\n"
                )
            # Firdaria active period this year (Fix 7)
            firdaria = chart_data.get("hellenistic", {}).get("firdaria", {})
            fird_major = firdaria.get("active_major", {})
            fird_sub   = firdaria.get("active_sub",   {})
            fird_block = ""
            if fird_major:
                fird_block = (
                    f"Firdaria: major={fird_major.get('planet','?')} "
                    f"(ends age {fird_major.get('end_age','?')}), "
                    f"sub={fird_sub.get('planet','?') if fird_sub else '?'}\n"
                )
            # Alcocoden (Fix 8)
            alcocoden = chart_data.get("hellenistic", {}).get("alcocoden", {})
            alc_block = ""
            if alcocoden.get("planet"):
                alc_block = (
                    f"Alcocoden: {alcocoden['planet']} "
                    f"(hyleg={alcocoden.get('hyleg','?')}, "
                    f"dignity={alcocoden.get('dignity_score',0)}, "
                    f"years_given={alcocoden.get('years_given','?')})\n"
                )
            return (
                f"YEAR: {year}\n"
                f"Profection {year}: {json.dumps(prof_yr, default=str)}\n"
                f"Tajaka {year}: {json.dumps(taj_yr, default=str)}\n"
                f"Liu Nian {year}: {json.dumps(liu, default=str)}\n"
                f"Vimshottari active: Maha {dasha.get('maha_lord','?')} / "
                f"Antar {dasha.get('antar_lord','?')} "
                f"({dasha.get('antar_remaining_years','?')} yrs left)\n"
                f"Kakshya {year}: {json.dumps(kakshya, default=str)}\n"
                f"ALL outer transit hits {year} (exact dates):\n{outer_all}\n"
                f"Lunar return anchors: {json.dumps(lr, default=str)}\n"
                f"Solar Return analysis {year}: {sr_analysis_str if sr_analysis_str else 'see raw SR data'}\n"
                f"Fixed star activation windows {year}: {json.dumps(sw_yr, default=str)}\n"
                f"{pm_block}{fird_block}{alc_block}"
            )

        # ── Directive & Warning ───────────────────────────────────────────────
        elif sd["type"] == "directive":
            synth = synthesis or {}
            pd    = chart_data.get("western", {}).get("predictive", {}).get(
                        "primary_directions", {})
            all_dirs = []
            for cat in pd.values():
                if isinstance(cat, list):
                    all_dirs.extend(cat[:2])
            # Cross-system house lord agreement — confirms or qualifies synthesis
            lord_val = chart_data.get("lord_validations", {})
            lv_str = ""
            if lord_val:
                # lord_validations is a List[Dict] from validate_cross_system()
                # each dict has keys: house, lord, western_house, vedic_house, status
                if isinstance(lord_val, list):
                    agreements = [v for v in lord_val if v.get("status") == "aligned"]
                    conflicts  = [v for v in lord_val if v.get("status") == "conflict"]
                else:
                    agreements = lord_val.get("agreements", [])
                    conflicts  = lord_val.get("conflicts", [])
                if agreements:
                    lv_str += f"Cross-system lord AGREEMENTS: {json.dumps(agreements[:4], default=str)}\n"
                if conflicts:
                    lv_str += f"Cross-system lord CONFLICTS: {json.dumps(conflicts[:3], default=str)}\n"
            return (
                f"Consensus points: {json.dumps(synth.get('consensus_points', [])[:5], default=str)}\n"
                f"Unified narrative: {synth.get('unified_narrative', '')}\n"
                f"Key contradictions: {json.dumps(synth.get('contradictions', [])[:3], default=str)}\n"
                f"Primary Directions: {json.dumps(all_dirs[:4], default=str)}\n"
                f"Peak risk window: {json.dumps(next(iter(synth.get('critical_periods') or [{}]), {}), default=str)}\n"
                f"{lv_str}"
            )

        return ""

    # ─────────────────────────────────────────────────────────────────────────
    # Domain Ledger: structured extraction replacing character truncation
    # ─────────────────────────────────────────────────────────────────────────

    def _extract_domain_bullets(self, system_name: str, analysis_text: str) -> Optional[Dict[str, List[str]]]:
        """Extract all astrological findings from one expert into domain-keyed bullets.

        Returns dict mapping domain name → list of bullet strings, or None on failure.
        Uses structured_generate with DOMAIN_LEDGER_SCHEMA for guaranteed JSON.
        """
        system_prompt = (
            "You are an astrological data extraction engine. "
            "Extract ALL findings from the expert analysis into bullet points "
            "organized by life domain (Career, Relationships, Health, Finances, "
            "Identity, Family, Spirituality, Communication, etc.). "
            "Preserve ALL dates, degrees, planet positions, house numbers, "
            "and aspect descriptions exactly as stated. "
            "Do NOT interpret or editorialise — categorize and list."
        )
        user_prompt = f"SYSTEM: {system_name}\n\nANALYSIS:\n{analysis_text}"

        result = gateway.structured_generate(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            output_schema=self.DOMAIN_LEDGER_SCHEMA,
            model="gemini-2.5-flash-lite",
            max_tokens=2000,
            temperature=0.0,
        )

        if not result.get("success") or not result.get("data"):
            logger.warning(f"Domain ledger extraction failed for {system_name}: "
                           f"{result.get('error', 'unknown')}")
            return None

        # Parse into domain → bullets dict
        domains_data = result["data"].get("domains", [])
        domain_dict: Dict[str, List[str]] = {}
        for entry in domains_data:
            domain = entry.get("domain", "Other")
            bullets = entry.get("bullets", [])
            if bullets:
                domain_dict[domain] = [f"[{system_name}] {b}" for b in bullets]
        return domain_dict

    def _build_domain_ledger(self, expert_analyses: list) -> str:
        """Build a Domain Ledger by extracting expert outputs into domain-keyed bullets.

        Calls gemini-2.5-flash-lite for each expert system in parallel, merges results
        by life domain, and formats as a structured evidence block. Falls back to
        _build_expert_block() if all extractions fail.
        """
        from concurrent.futures import ThreadPoolExecutor, as_completed

        if not expert_analyses:
            return ""

        # Filter to experts with actual analysis text
        valid_experts = [
            a for a in expert_analyses
            if a.get("analysis") and a.get("system")
        ]
        if not valid_experts:
            return ""

        # Parallel extraction — 4 experts, 4 workers
        merged: Dict[str, List[str]] = {}
        futures = {}
        with ThreadPoolExecutor(max_workers=4) as executor:
            for exp in valid_experts:
                fut = executor.submit(
                    self._extract_domain_bullets,
                    exp["system"],
                    exp["analysis"],
                )
                futures[fut] = exp["system"]

            for fut in as_completed(futures):
                system_name = futures[fut]
                try:
                    domain_dict = fut.result()
                    if domain_dict:
                        for domain, bullets in domain_dict.items():
                            merged.setdefault(domain, []).extend(bullets)
                except Exception as e:
                    logger.warning(f"Domain ledger thread failed for {system_name}: {e}")

        if not merged:
            logger.warning("All domain ledger extractions failed, falling back to expert block")
            return ""

        # Format into structured text block
        lines = ["═══ DOMAIN LEDGER (structured expert evidence) ═══", ""]
        # Sort domains for consistent output
        for domain in sorted(merged.keys()):
            lines.append(f"▸ {domain.upper()}")
            for bullet in merged[domain]:
                lines.append(f"  • {bullet}")
            lines.append("")

        lines.append("═══ END DOMAIN LEDGER ═══")
        return "\n".join(lines)

    # ─────────────────────────────────────────────────────────────────────────
    # Issue 3: Expert block builder (bypasses Arbiter truncation)
    # ─────────────────────────────────────────────────────────────────────────

    def _build_expert_block(self, expert_analyses: list) -> str:
        """
        Format raw expert analyses for injection into section prompts.
        Per-system char limits now match arbiter.py:
          Western   → 6000 (carries most predictive date evidence + transit windows)
          Vedic     → 5500 (carries dasha sequences, AV scores, yogas)
          Saju      → 4500 (standard)
          Hellenistic → 4500 (standard)
        """
        EXPERT_CHAR_LIMITS = {
            "Western":     6000,
            "Vedic":       5500,
            "Saju":        4500,
            "Hellenistic": 4500,
        }
        EXPERT_CHAR_LIMIT = 4500   # fallback for unknown systems
        if not expert_analyses:
            return ""
        lines = []
        for system_name in ["Western", "Vedic", "Saju", "Hellenistic"]:
            exp = next(
                (a for a in expert_analyses if a.get("system") == system_name), None
            )
            if not exp:
                continue
            text = exp.get("analysis", "") or ""
            if not text:
                continue
            limit = EXPERT_CHAR_LIMITS.get(system_name, EXPERT_CHAR_LIMIT)
            if len(text) > limit:
                # Sentence-boundary truncation: avoid mid-sentence cuts
                cut = text[:limit]
                last_period = max(cut.rfind('. '), cut.rfind('.\n'), cut.rfind('.\r'))
                if last_period > limit * 0.8:
                    cut = text[:last_period + 1]
                omitted = len(text) - len(cut)
                truncated = cut + f"\n[...{omitted} chars omitted]"
            else:
                truncated = text
            lines.append(f"--- {system_name} Expert ---")
            lines.append(truncated)
            lines.append("")
        return "\n".join(lines)

    # ─────────────────────────────────────────────────────────────────────────
    # Issue 6: Extract ALL outer transit hits for a given year
    # ─────────────────────────────────────────────────────────────────────────

    def _all_transit_hits_for_year(self, outer_transit_data: dict, year: int) -> str:
        """
        Pull every outer planet transit hit for `year` from both the exact-hit
        list and the by_year summary. Returns a formatted string with entry/exit
        windows so the LLM can write real date ranges.
        """
        hits = []

        # Source 1: exact hits list (most precise — includes entry/exit dates)
        all_hits = outer_transit_data.get("hits") or outer_transit_data.get("all_hits", [])
        for h in all_hits:
            try:
                iso = h.get("exact_date_iso", "") or h.get("exact_date", "")
                hit_year = int(str(iso)[:4]) if iso else None
                if hit_year == year:
                    hits.append({
                        "date":   iso,
                        "planet": h.get("transiting") or h.get("planet", "?"),
                        "aspect": h.get("aspect", "?"),
                        "natal":  h.get("natal_point", "?"),
                        "entry":  h.get("entry_date", ""),
                        "exit":   h.get("exit_date", ""),
                    })
            except Exception:
                continue

        # Source 2: by_year summary (catches any hits not in the flat list)
        for item in outer_transit_data.get("by_year", {}).get(str(year), []):
            try:
                hits.append({
                    "date":   f"{year}-{str(item.get('month','01')).zfill(2)}-01",
                    "planet": item.get("transiting") or item.get("planet", "?"),
                    "aspect": item.get("type") or item.get("aspect", "?"),
                    "natal":  item.get("natal") or item.get("natal_point", "?"),
                    "entry":  item.get("entry_date", ""),
                    "exit":   item.get("exit_date", ""),
                })
            except Exception:
                continue

        if not hits:
            return f"No outer transit hits found for {year}."

        # Deduplicate by (planet, aspect, natal) and sort chronologically
        seen = set()
        unique = []
        for h in sorted(hits, key=lambda x: str(x.get("date", ""))):
            key = (h["planet"], h["aspect"], h["natal"])
            if key not in seen:
                seen.add(key)
                unique.append(h)

        lines = [f"ALL outer transit exact hits for {year}:"]
        for h in unique:
            window = (f" (window: {h['entry']} → {h['exit']})"
                      if h.get("entry") and h.get("exit") else "")
            lines.append(
                f"  • {h['date']}: {h['planet']} {h['aspect']} natal {h['natal']}{window}"
            )
        return "\n".join(lines)

    # ─────────────────────────────────────────────────────────────────────────
    # Mandatory data blocks (preserved from v1 + parans upgrade)
    # ─────────────────────────────────────────────────────────────────────────

    def _extract_synthesis_for_section(self, synthesis: dict, sd: dict) -> str:
        """
        Extract targeted fields from Arbiter synthesis rather than raw JSON truncation.

        Old approach: json.dumps(synthesis)[:1800] — cut a 6000+ char JSON at 1800,
        discarding critical_periods, unified_narrative, and everything after the first
        two consensus_points.

        New approach: extract the fields most useful for this specific section type,
        with generous char budgets per field (~3500 total usable content).
        """
        if not synthesis:
            return ""

        section_id   = sd.get("id", "")
        section_type = sd.get("type", "natal")
        lines        = ["=== ARBITER SYNTHESIS ==="]

        # ── Executive summary — always useful ────────────────────────────────
        exec_sum = synthesis.get("executive_summary", "")
        if exec_sum:
            lines.append(f"Executive summary: {exec_sum[:500]}")

        # ── Key planets — always useful ───────────────────────────────────────
        key_planets = synthesis.get("key_planets", [])
        if key_planets:
            lines.append(f"Key activated planets (cross-system): {', '.join(key_planets)}")

        # ── Section steer — targeted directive for this exact section ─────────
        steers     = synthesis.get("section_steers", {})
        steer_text = steers.get(section_id, "")
        if steer_text:
            lines.append(f"SYNTHESIS STEER FOR THIS SECTION: {steer_text}")

        # ── Consensus points — always valuable ────────────────────────────────
        consensus = synthesis.get("consensus_points", [])
        if consensus:
            lines.append("Consensus points (cross-system agreements):")
            # Natal sections: focus on character/potential consensus
            # Predictive sections: include all consensus with dates
            for cp in consensus[:6]:
                theme   = cp.get("theme", "?")
                conf    = cp.get("confidence", 0)
                systems = ", ".join(cp.get("systems_agreeing", []))
                desc    = cp.get("description", "")[:350]
                lines.append(f"  • [{conf:.0f}%] {theme} [{systems}]: {desc}")

        # ── Top predictions — for predictive sections ─────────────────────────
        if section_type in ("year_forecast", "current", "directive", "almanac_summary"):
            top_preds = synthesis.get("top_predictions", [])
            if top_preds:
                lines.append("Highest-confidence predictions:")
                for pred in top_preds[:5]:
                    prediction = pred.get("prediction", "?")
                    dates      = pred.get("date_range", "?")
                    conf       = pred.get("confidence", 0)
                    systems    = ", ".join(pred.get("systems", []))
                    evidence   = pred.get("evidence", "")[:250]
                    lines.append(f"  • [{conf:.0f}%] {dates}: {prediction} [{systems}]")
                    if evidence:
                        lines.append(f"    Evidence: {evidence}")

        # ── Critical periods — for predictive sections ────────────────────────
        if section_type in ("year_forecast", "current", "directive", "almanac_summary"):
            crit = synthesis.get("critical_periods", [])
            if crit:
                lines.append("Critical periods:")
                for cp in crit[:6]:
                    period   = cp.get("period", "?")
                    intensity = cp.get("intensity", 0)
                    meaning  = cp.get("meaning", "")[:250]
                    action   = cp.get("action",  "")[:200]
                    systems  = ", ".join(cp.get("systems_agreeing", []))
                    lines.append(f"  • [{intensity:.0f}] {period} [{systems}]: {meaning}")
                    if action:
                        lines.append(f"    Action: {action}")

        # ── Unified narrative — most valuable field, now fully preserved ───────
        narrative = synthesis.get("unified_narrative", "")
        if narrative:
            # Natal sections: full narrative (it's the synthesis of the whole chart)
            # Predictive sections: first 2000 chars (narrative covers all years)
            if section_type == "natal":
                lines.append(f"Unified synthesis narrative:\n{narrative[:3000]}")
            else:
                lines.append(f"Unified synthesis narrative:\n{narrative[:3000]}")

        # ── Contradictions — natal sections benefit from knowing tensions ──────
        if section_type == "natal":
            contradictions = synthesis.get("contradictions", [])
            if contradictions:
                lines.append("Cross-system tensions to acknowledge:")
                for ct in contradictions[:3]:
                    tension    = ct.get("tension", "?")
                    resolution = ct.get("resolution", "")
                    navigate   = ct.get("navigate_by", "")
                    lines.append(f"  • Tension: {tension[:200]}")
                    if resolution:
                        lines.append(f"    Resolution: {resolution[:200]}")
                    if navigate:
                        lines.append(f"    Navigate by: {navigate[:150]}")

        lines.append("=== END SYNTHESIS ===")
        return "\n".join(lines)

    def _build_natal_placements_header(self, chart_data: dict) -> str:
        """Build an immutable planet→house mapping header to prevent cross-section contradictions."""
        lines = [
            "=== MANDATORY NATAL PLACEMENTS (immutable — use these exact house placements) ===",
        ]
        # Western (Tropical / Placidus)
        w_plac = chart_data.get("western", {}).get("natal", {}).get("placements", {})
        if w_plac:
            lines.append("WESTERN (Tropical/Placidus):")
            planet_order = ["Sun","Moon","Mercury","Venus","Mars","Jupiter","Saturn",
                            "Uranus","Neptune","Pluto","North Node","South Node",
                            "Chiron","Ascendant","Midheaven"]
            for p in planet_order:
                pd = w_plac.get(p, {})
                if isinstance(pd, dict) and pd.get("sign"):
                    house = pd.get("house", "?")
                    sign = pd.get("sign", "?")
                    deg = pd.get("degree", pd.get("deg_in_sign", "?"))
                    lines.append(f"  {p}: House {house}, {sign} {deg}")
        # Vedic (Sidereal / Whole Sign)
        v_plac = chart_data.get("vedic", {}).get("natal", {}).get("placements", {})
        if v_plac:
            lines.append("VEDIC (Sidereal/Whole Sign):")
            for p in ["Sun","Moon","Mercury","Venus","Mars","Jupiter","Saturn",
                       "Rahu","Ketu","Ascendant"]:
                pd = v_plac.get(p, {})
                if isinstance(pd, dict) and (pd.get("sign") or pd.get("rashi")):
                    house = pd.get("house", pd.get("bhava", "?"))
                    sign = pd.get("sign", pd.get("rashi", "?"))
                    deg = pd.get("degree", pd.get("deg_in_sign", "?"))
                    lines.append(f"  {p}: House {house}, {sign} {deg}")
        lines.append("CRITICAL: These placements are computed from the birth chart. NEVER assign a")
        lines.append("planet to a different house than shown here. If Western and Vedic differ, state BOTH.")
        lines.append("=== END NATAL PLACEMENTS ===")
        return "\n".join(lines)

    def _build_natal_block(self, ref: dict, chart_data: dict = None) -> str:
        today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        lines = [f"TODAY: {today_str}  ← All timing must be AFTER this date.",
                 "=== MANDATORY NATAL DATA — USE THESE EXACT VALUES ==="
        ]
        # ── Immutable natal placements header ──
        if chart_data:
            lines.append(self._build_natal_placements_header(chart_data))
            lines.append("")
        lines.append("FORMAT: DEGREES° ARCMINUTES' SIGN  (e.g., '19° 43' Cancer')")
        lines.append("")

        planet_order = ["Sun","Moon","Mercury","Venus","Mars","Jupiter","Saturn",
                        "Uranus","Neptune","Pluto","North Node","South Node",
                        "Chiron","Ascendant","Midheaven","Descendant","IC"]

        lines.append("--- PLANETARY POSITIONS ---")
        for planet in planet_order:
            data = ref.get(planet)
            if data and isinstance(data, dict):
                lines.append(f"{planet}: {data['dms']} {data['sign']}  (lon: {data['longitude']:.4f}°)")

        # ── House Lord Reference (mandatory — prevents LLM hallucination) ────
        hlr = chart_data.get("_house_lord_reference_block", "") if chart_data else ""
        if hlr:
            lines.append("")
            lines.append("--- HOUSE LORD REFERENCE (MANDATORY — use these, NEVER deduce your own) ---")
            lines.append(hlr)
            lines.append("--- END HOUSE LORD REFERENCE ---")

        lines.append("")
        lines.append("--- ESSENTIAL CHART FACTORS ---")
        lines.append(f"Chart sect: {'Day chart' if ref.get('_is_day_chart') else 'Night chart'}")
        lines.append(f"Hyleg: {ref.get('_hyleg', 'Unknown')}")
        lines.append(f"Almuten: {ref.get('_almuten', 'Unknown')} (dignity: {ref.get('_almuten_dignity', 'Unknown')})")
        lines.append(f"Most dignified planet: {ref.get('_most_dignified', 'Unknown')} (score {ref.get('_most_dignified_score', 'N/A')})")
        lines.append(f"Dominant chart pattern: {ref.get('_dominant_pattern', 'None')}")

        # ── Western dignity scores — full table ──────────────────────────────
        if chart_data:
            w_nat = chart_data.get("western", {}).get("natal", {})
            pd_dig = w_nat.get("dignities", {}).get("planet_dignities", {})
            if pd_dig:
                lines.append("")
                lines.append("--- WESTERN DIGNITY SCORES (total score per planet) ---")
                for p, d in pd_dig.items():
                    if isinstance(d, dict):
                        score = d.get("total_score", "?")
                        state = d.get("state", "")
                        lines.append(f"  {p}: {score} ({state})" if state else f"  {p}: {score}")

        lines.append("")
        lines.append("--- HELLENISTIC LOTS ---")
        lof_sign = ref.get('_lot_fortune_sign', '?')
        lof_deg  = ref.get('_lot_fortune_deg', '?')
        asc_data = ref.get('Ascendant', {})
        asc_sign = asc_data.get('sign', '')
        asc_dms  = asc_data.get('dms', '')
        lof_line = f"Lot of Fortune: {lof_sign} {lof_deg}"
        if lof_sign == asc_sign:
            lof_line += (
                f"  ⚠️ DIFFERENT POINT FROM ASCENDANT — "
                f"Ascendant is {asc_dms} {asc_sign}, Lot of Fortune is {lof_deg} {lof_sign}. "
                f"These are two distinct points. Do NOT cite the Ascendant degree as the Lot of Fortune degree."
            )
        lines.append(lof_line)
        lines.append(f"Lot of Spirit:  {ref.get('_lot_spirit_sign', '?')}")

        # ── Hellenistic: ZR current phase ────────────────────────────────────
        if chart_data:
            hell = chart_data.get("hellenistic", {})
            zr   = hell.get("zodiacal_releasing", {})
            zr_fortune = zr.get("Fortune", {})
            zr_spirit  = zr.get("Spirit",  {})
            if zr_fortune or zr_spirit:
                lines.append("")
                lines.append("--- ZODIACAL RELEASING (current phases) ---")
                for lot_name, zr_data in [("Fortune", zr_fortune), ("Spirit", zr_spirit)]:
                    if isinstance(zr_data, list) and zr_data:
                        current = zr_data[0] if zr_data else {}
                        sign    = current.get("sign", "?")
                        lord    = current.get("lord", "?")
                        end     = current.get("end_date", "?") or current.get("end", "?")
                        level   = current.get("level", "L1")
                        lines.append(f"  ZR {lot_name} ({level}): {sign} (lord: {lord}) → ends {end}")
                    elif isinstance(zr_data, dict):
                        sign  = zr_data.get("sign", "?")
                        lord  = zr_data.get("lord", "?")
                        end   = zr_data.get("end_date", "?") or zr_data.get("end", "?")
                        lines.append(f"  ZR {lot_name}: {sign} (lord: {lord}) → ends {end}")

            # ── Hellenistic sect dignity ──────────────────────────────────────
            bonds = hell.get("bonifications", {})
            if bonds:
                lines.append("")
                lines.append("--- SECT & BONIFICATION ---")
                for planet, bdata in list(bonds.items())[:7]:
                    if isinstance(bdata, dict):
                        sect_ok = bdata.get("sect_match", "?")
                        bon     = bdata.get("bonification", "?")
                        lines.append(f"  {planet}: sect_match={sect_ok}, bonification={bon}")

        lines.append("")
        lines.append("--- VEDIC FACTORS ---")
        lines.append(f"Atmakaraka:    {ref.get('_vedic_ak', 'Unknown')}")
        lines.append(f"Amatyakaraka:  {ref.get('_vedic_amatyakaraka', 'Unknown')}")
        lines.append(f"Darakaraka:    {ref.get('_vedic_darakaraka', 'Unknown')}")
        lines.append(f"Moon Nakshatra: {ref.get('_moon_nakshatra', 'Unknown')} pada {ref.get('_moon_pada', '?')}")

        # ── Shadbala — all 9 planets ──────────────────────────────────────────
        if chart_data:
            v_nat    = chart_data.get("vedic", {}).get("natal", {})
            shadbala = chart_data.get("vedic", {}).get("strength", {}).get("shadbala", {})
            planet_scores = shadbala.get("planet_scores", {})
            if planet_scores:
                lines.append("")
                lines.append("--- SHADBALA (Vedic planetary strength, Rupas) ---")
                lines.append("  Minimum adequate: Sun/Moon/Asc lord ~5.0, others ~3.5-5.0 Rupas")
                for p, ps in planet_scores.items():
                    if isinstance(ps, dict):
                        rupas = ps.get("rupas", ps.get("total", 0) / 60.0 if ps.get("total") else "?")
                        ishta = ps.get("ishta_phala", "?")
                        kashta = ps.get("kashta_phala", "?")
                        try:
                            r = float(rupas)
                            strength_label = "STRONG" if r >= 7 else ("ADEQUATE" if r >= 5 else ("WEAK" if r >= 3.5 else "VERY WEAK"))
                            if r < 3.5:
                                lines.append(f"  {p}: {r:.2f} Rupas — ⚠️ SEVERELY WEAKENED ⚠️  (ishta={ishta}, kashta={kashta})")
                                lines.append(f"    → If {p} anchors a prediction, you MUST acknowledge this weakness.")
                                lines.append(f"    → Explain HOW the prediction manifests DESPITE weakness (cancellation yoga, dasha support, etc.)")
                            else:
                                lines.append(f"  {p}: {r:.2f} Rupas — {strength_label}  (ishta={ishta}, kashta={kashta})")
                        except (TypeError, ValueError):
                            lines.append(f"  {p}: {rupas} Rupas")

            # ── Ashtakavarga — use full engine data, not MVP fallback ────────
            # Real data: chart_data["vedic"]["strength"]["ashtakavarga_full"]
            # {sarva: [int×12], bhinna: {planet: [int×12]}, house_strengths: [score×12]}
            ashta_full = chart_data.get("vedic", {}).get("strength", {}).get("ashtakavarga_full", {})
            ashta = ashta_full  # prefer full engine output
            if not ashta or "error" in ashta:
                # fall back to natal MVP dict
                ashta = v_nat.get("ashtakavarga", {})
            if ashta:
                lines.append("")
                lines.append("--- ASHTAKAVARGA (bindus — higher = more support) ---")
                # ashtakavarga_full format: {sarva: [int×12], bhinna: {planet: [int×12]}, house_strengths: []}
                # MVP format: {sarvashtakavarga: {sign: int}, planet_scores/bhinnashtakavarga: {planet: int}}
                sarva_list = ashta.get("sarva", [])   # full engine: list of 12 house totals
                sarva_dict = ashta.get("sarvashtakavarga", {})  # MVP format
                if sarva_list and isinstance(sarva_list, list):
                    SIGNS = ["Ari","Tau","Gem","Can","Leo","Vir","Lib","Sco","Sag","Cap","Aqu","Pis"]
                    lines.append("  Sarvashtakavarga (total bindus by sign/house):")
                    parts = [f"{SIGNS[i] if i < len(SIGNS) else i+1}:{sarva_list[i]}"
                             for i in range(min(12, len(sarva_list)))]
                    lines.append("    " + "  ".join(parts))
                elif sarva_dict:
                    lines.append("  Sarvashtakavarga (total bindus per sign):")
                    for sign, score in sarva_dict.items():
                        lines.append(f"    {sign}: {score}")
                # Per-planet bindu totals
                bhinna = ashta.get("bhinna", {})   # full engine: {planet: [int×12]}
                if bhinna and isinstance(bhinna, dict):
                    lines.append("  Per-planet total bindus (sum across 12 signs):")
                    for planet, scores in bhinna.items():
                        if isinstance(scores, list):
                            total = sum(scores)
                            lines.append(f"    {planet}: {total} total bindus")
                        elif isinstance(scores, (int, float)):
                            lines.append(f"    {planet}: {scores} bindus")
                else:
                    planet_ashta = ashta.get("planet_scores", ashta.get("bhinnashtakavarga", {}))
                    if planet_ashta:
                        lines.append("  Per-planet bindu totals:")
                        for p, score in planet_ashta.items():
                            if isinstance(score, (int, float)):
                                lines.append(f"    {p}: {score} bindus")
                            elif isinstance(score, dict):
                                total = score.get("total", score.get("bindus", "?"))
                                lines.append(f"    {p}: {total} bindus")

            # ── All Yogas ─────────────────────────────────────────────────────
            yogas = v_nat.get("yogas", [])
            if yogas:
                lines.append("")
                lines.append("--- VEDIC YOGAS (all active) ---")
                for y in yogas[:12]:
                    name   = y.get("name", "?") if isinstance(y, dict) else str(y)
                    effect = y.get("effect", y.get("description", "")) if isinstance(y, dict) else ""
                    strength = y.get("strength", "") if isinstance(y, dict) else ""
                    line = f"  • {name}"
                    if strength:
                        line += f" ({strength})"
                    if effect:
                        line += f": {effect[:80]}"
                    lines.append(line)

            # ── D9 Navamsha key placements ────────────────────────────────────
            v_placements = v_nat.get("placements", {})
            d9_planets = {}
            for p, pdata in v_placements.items():
                if isinstance(pdata, dict) and pdata.get("d9"):
                    d9_planets[p] = pdata["d9"]
            if d9_planets:
                lines.append("")
                lines.append("--- D9 NAVAMSHA (soul/marriage chart placements) ---")
                for p in ["Sun","Moon","Venus","Mars","Jupiter","Saturn","Ascendant"]:
                    if p in d9_planets:
                        lines.append(f"  {p} in D9: {d9_planets[p]}")

            # ── D10 Dasamsha key placements ───────────────────────────────────
            d10_planets = {}
            for p, pdata in v_placements.items():
                if isinstance(pdata, dict) and pdata.get("d10"):
                    d10_planets[p] = pdata["d10"]
            if d10_planets:
                lines.append("")
                lines.append("--- D10 DASAMSHA (career/public life chart placements) ---")
                for p in ["Sun","Moon","Mercury","Jupiter","Saturn","MC"]:
                    if p in d10_planets:
                        lines.append(f"  {p} in D10: {d10_planets[p]}")

        lines.append("")
        lines.append("--- SAJU (BAZI) ---")
        if ref.get("_saju_available"):
            for pillar in ["Year", "Month", "Day", "Hour"]:
                val = ref.get(f"_saju_{pillar}", "?")
                lines.append(f"{pillar} Pillar: {val}")
            lines.append(f"Day Master: {ref.get('_dm_stem')} {ref.get('_dm_element')} — {ref.get('_dm_tier')}")
            lines.append(f"Useful God: {ref.get('_useful_god', '?')}")

            # ── Bazi 10-god analysis & element balance ────────────────────────
            if chart_data:
                bazi_nat = chart_data.get("bazi", {}).get("natal", {})
                ten_gods = bazi_nat.get("ten_gods", {})
                if ten_gods:
                    lines.append("")
                    lines.append("--- BAZI 10-GOD ANALYSIS ---")
                    lines.append("  (Each pillar's relationship to Day Master — key for life domain diagnosis)")
                    for pillar, god_data in ten_gods.items():
                        if isinstance(god_data, dict):
                            stem_god   = god_data.get("stem_god", "?")
                            branch_god = god_data.get("branch_god", "?")
                            lines.append(f"  {pillar}: stem={stem_god}, branch={branch_god}")
                        else:
                            lines.append(f"  {pillar}: {god_data}")

                elem_balance = bazi_nat.get("element_balance", bazi_nat.get("elements", {}))
                if elem_balance:
                    lines.append("")
                    lines.append("--- BAZI ELEMENT BALANCE ---")
                    for elem, count in elem_balance.items():
                        lines.append(f"  {elem}: {count}")

                shensha = bazi_nat.get("shensha", [])
                if shensha:
                    lines.append("")
                    lines.append("--- BAZI SHENSHA (special stars) ---")
                    for s in shensha[:6]:
                        stype = s.get("type", "?") if isinstance(s, dict) else str(s)
                        interp = s.get("interpretation", s.get("meaning", "")) if isinstance(s, dict) else ""
                        lines.append(f"  • {stype}: {interp[:80]}" if interp else f"  • {stype}")
        else:
            lines.append("Saju: UNAVAILABLE")

        lines.append("")
        lines.append("--- TIMING CONTEXT ---")
        lines.append(f"Maha Dasha: {ref.get('_maha_dasha')} ({ref.get('_dasha_years_left')} yrs remaining)")
        lines.append(f"Antardasha: {ref.get('_antar_dasha')} ({ref.get('_antar_dasha_years')} yrs remaining)")
        lines.append(f"Current Profection: {ref.get('_profection_sign')} "
                     f"(House {ref.get('_profection_house')}, Time Lord: {ref.get('_time_lord')})")
        lines.append("")
        lines.append("--- TRUE PARANS (RAMC horizon method) ---")
        parans = ref.get("_parans", [])[:6]
        if parans:
            for p in parans:
                lines.append(f"  • {p.get('interpretation', json.dumps(p, default=str))}")
        else:
            stars = ref.get("_significant_stars", ref.get("_fixed_stars", []))[:4]
            if stars:
                for s in stars:
                    lines.append(f"  • {s.get('interpretation', json.dumps(s, default=str))}")
            else:
                lines.append("  No star contacts above threshold")
        lines.append("")
        lines.append("--- HELIACAL EVENTS ---")
        for ev in ref.get("_heliacal_events", [])[:3]:
            lines.append(f"  • {ev.get('interpretation', str(ev))}")

        return "\n".join(lines)

    def _build_predictive_block(self, ref: dict, chart_data: dict) -> str:
        today = datetime.now(timezone.utc)
        today_str = today.strftime("%Y-%m-%d")

        w_pred = chart_data.get("western",    {}).get("predictive", {})
        v_pred = chart_data.get("vedic",       {}).get("predictive", {})
        b_pred = chart_data.get("bazi",        {}).get("predictive", {})
        hell   = chart_data.get("hellenistic", {})

        profecs  = w_pred.get("profections_timeline", [])
        transits = w_pred.get("transits_timeline", [])
        sr       = w_pred.get("solar_returns", [])[:15]
        tajaka   = v_pred.get("tajaka", [])[:15]
        liu_nian = b_pred.get("liu_nian_timeline", [])
        da_yun   = b_pred.get("da_yun", {})
        zr       = hell.get("zodiacal_releasing", {})
        outer    = w_pred.get("outer_transit_aspects", {})

        out = []
        out.append(f"TODAY: {today_str}  \u2190 THIS IS THE HARD DATE BOUNDARY. NO DATES BEFORE THIS.")
        out.append("=== PREDICTIVE DATA BLOCK (Almanac sections — 15-YEAR WINDOW 2026–2040) ===")
        out.append("Do not re-diagnose the natal chart. Use natal positions only as brief anchors.")
        # ── Immutable natal placements header ──
        out.append("")
        out.append(self._build_natal_placements_header(chart_data))
        out.append("")
        out.append("--- NATAL ANCHORS (reference only) ---")
        for p in ["Sun", "Moon", "Ascendant", "Midheaven", "Saturn"]:
            if p in ref:
                d = ref[p]
                out.append(f"{p}: {d.get('dms','?')} {d.get('sign','?')}")
        # ── House Lord Reference (mandatory — prevents hallucination) ────
        hlr = chart_data.get("_house_lord_reference_block", "")
        if hlr:
            out.append("")
            out.append("--- HOUSE LORD REFERENCE (MANDATORY — use these, NEVER deduce your own) ---")
            out.append(hlr)
            out.append("--- END HOUSE LORD REFERENCE ---")

        out.append("")
        out.append("--- ACTIVE TIME LORDS ---")
        out.append(f"Maha Dasha: {ref.get('_maha_dasha')} ({ref.get('_dasha_years_left')} yrs remaining)")
        out.append(f"Antardasha: {ref.get('_antar_dasha')} ({ref.get('_antar_dasha_years')} yrs remaining)")
        out.append(f"Current Profection: {ref.get('_profection_sign')} "
                   f"(House {ref.get('_profection_house')}, Time Lord: {ref.get('_time_lord')})")
        if ref.get("_saju_available") and ref.get("_current_da_yun"):
            cyun = ref["_current_da_yun"]
            out.append(f"Current Da Yun: {cyun.get('stem','?')}{cyun.get('branch','?')} "
                       f"({cyun.get('stem_element','?')}/{cyun.get('branch_element','?')}, "
                       f"age {cyun.get('start_age','?')}–{cyun.get('end_age','?')})")
        out.append("")
        out.append("--- PROFECTIONS 2026-2040 (Western annual — all 15 years) ---")
        out.append(json.dumps(profecs, default=str, indent=None))

        # Hellenistic annual profection
        hell_prof = hell.get("annual_profections", {})
        if hell_prof:
            out.append("")
            out.append("--- HELLENISTIC ANNUAL PROFECTION (current year) ---")
            out.append(f"  Profected sign: {hell_prof.get('profected_sign','?')}")
            out.append(f"  Activated house: {hell_prof.get('activated_house','?')}")
            out.append(f"  Time Lord: {hell_prof.get('time_lord','?')}")
            out.append(f"  Theme: {hell_prof.get('theme', hell_prof.get('interpretation','?'))}")

        out.append("")
        out.append("--- OUTER PLANET TRANSIT ASPECT HITS (exact dates — WESTERN TROPICAL zodiac) ---")
        out.append("NOTE: All outer transit dates below are computed in the WESTERN TROPICAL zodiac.")
        out.append("When citing these dates, use ONLY Western/Tropical house lords and sign placements.")
        out.append("Do NOT apply Vedic/Sidereal house rulers to Western transit dates.")
        if outer.get("summary_block"):
            out.append(outer["summary_block"])
        else:
            out.append(json.dumps(transits, default=str, indent=None))

        # Solar Returns — expanded fields
        out.append("")
        out.append("--- SOLAR RETURNS (annual charts) ---")
        for s in sr:
            year   = s.get("year", "?")
            asc    = s.get("ascendant", s.get("asc_sign", "?"))
            dom_h  = s.get("dominant_house", "?")
            sr_mc  = s.get("mc_sign", s.get("mc", "?"))
            sr_sun = s.get("sun_sign", s.get("sun", "?"))
            sr_moon= s.get("moon_sign", s.get("moon", "?"))
            sr_jup = s.get("jupiter_sign", s.get("jupiter", "?"))
            sr_sat = s.get("saturn_sign",  s.get("saturn",  "?"))
            out.append(f"  {year}: ASC={asc}, MC={sr_mc}, dom_house={dom_h} | "
                       f"Sun={sr_sun}, Moon={sr_moon}, Jup={sr_jup}, Sat={sr_sat}")

        out.append("")
        out.append("--- TAJAKA (VEDIC ANNUAL CHARTS) ---")
        out.append(json.dumps(tajaka, default=str, indent=None))

        # Liu Nian with 10-god labels — full 15-year window
        out.append("")
        out.append("--- LIU NIAN (BAZI ANNUAL PILLARS 2026-2040) ---")
        for ln in liu_nian[:15]:
            if isinstance(ln, dict):
                yr     = ln.get("year", "?")
                pillar = f"{ln.get('stem','?')}{ln.get('branch','?')}"
                s_el   = ln.get("stem_element", "?")
                b_el   = ln.get("branch_element", "?")
                gods   = ln.get("ten_gods", {})
                god_str = (" | 10-gods: " + ", ".join(f"{k}={v}" for k, v in gods.items() if v)) if gods else ""
                out.append(f"  {yr}: {pillar} ({s_el}/{b_el}){god_str}")
            else:
                out.append(f"  {ln}")

        # Da Yun sequence — not just current
        out.append("")
        out.append("--- DA YUN SEQUENCE (10-year pillars) ---")
        yun_pills = da_yun.get("pillars", [])
        for yp in yun_pills[:6]:
            if isinstance(yp, dict):
                pillar    = f"{yp.get('stem','?')}{yp.get('branch','?')}"
                s_el      = yp.get("stem_element", "?")
                b_el      = yp.get("branch_element", "?")
                start_age = yp.get("start_age", "?")
                end_age   = yp.get("end_age", "?")
                start_yr  = yp.get("start_year", "?")
                end_yr    = yp.get("end_year", "?")
                out.append(f"  Age {start_age}–{end_age} ({start_yr}–{end_yr}): {pillar} ({s_el}/{b_el})")

        out.append("")
        out.append("--- KAKSHYA TRANSITS ---")
        kakshya = v_pred.get("kakshya_transits", {})
        out.append(json.dumps(kakshya, default=str, indent=None)[:1500])

        out.append("")
        out.append("--- PRIMARY DIRECTIONS 2026-2040 (all arcs) ---")
        pd_dirs = w_pred.get("primary_directions", {})
        all_dirs = []
        for cat in pd_dirs.values():
            if isinstance(cat, list):
                all_dirs.extend(cat[:5])
        out.append(json.dumps(all_dirs[:20], default=str, indent=None))

        # Zodiacal Releasing — formatted text, not raw dict
        if zr:
            out.append("")
            out.append("--- ZODIACAL RELEASING (Hellenistic timing) ---")
            for lot_name in ["Fortune", "Spirit"]:
                zr_data = zr.get(lot_name, {})
                if not zr_data:
                    continue
                out.append(f"  Lot of {lot_name}:")
                if isinstance(zr_data, list):
                    for period in zr_data[:4]:
                        if isinstance(period, dict):
                            level = period.get("level", "L1")
                            sign  = period.get("sign", "?")
                            lord  = period.get("lord", "?")
                            start = period.get("start_date", period.get("start", "?"))
                            end   = period.get("end_date",   period.get("end",   "?"))
                            lob   = " ← LOOSING OF THE BOND" if period.get("is_loosing_of_bond") else ""
                            out.append(f"    {level}: {sign} (lord: {lord}) | {start} → {end}{lob}")
                elif isinstance(zr_data, dict):
                    sign  = zr_data.get("sign", "?")
                    lord  = zr_data.get("lord", "?")
                    start = zr_data.get("start_date", "?")
                    end   = zr_data.get("end_date", "?")
                    out.append(f"    Current: {sign} (lord: {lord}) | {start} → {end}")
                    for sub_key in ["l2", "L2", "sub_periods"]:
                        sub = zr_data.get(sub_key)
                        if sub:
                            subs = sub if isinstance(sub, list) else [sub]
                            for s in subs[:3]:
                                if isinstance(s, dict):
                                    out.append(
                                        f"    L2: {s.get('sign','?')} (lord: {s.get('lord','?')}) "
                                        f"| {s.get('start_date','?')} → {s.get('end_date','?')}"
                                    )
                            break

        return "\n".join(out)

    def _extract_reference_positions(self, chart_data: dict) -> dict:
        ref = {}
        w   = chart_data.get("western", {}).get("natal", {})
        for planet, data in w.get("placements", {}).items():
            if isinstance(data, dict):
                sign = data.get("sign") or data.get("sign_name", "")
                deg  = data.get("degree") or data.get("deg_in_sign", 0) or 0
                lon  = data.get("longitude") or data.get("lon", 0) or 0
                if sign:
                    ref[planet] = {
                        "sign":      sign,
                        "degree":    round(float(deg), 4),
                        "longitude": round(float(lon), 4),
                        "dms":       _deg_to_dms(float(deg))
                    }
        for angle, data in w.get("angles", {}).items():
            if isinstance(data, dict):
                sign = data.get("sign", "")
                deg  = data.get("degree") or data.get("deg_in_sign", 0) or 0
                lon  = data.get("longitude") or data.get("lon", 0) or 0
                if sign:
                    ref[angle] = {
                        "sign":      sign,
                        "degree":    round(float(deg), 4),
                        "longitude": round(float(lon), 4),
                        "dms":       _deg_to_dms(float(deg))
                    }

        vedic = chart_data.get("vedic", {}).get("natal", {})
        ref["_vedic_ak"]           = vedic.get("chara_karakas", {}).get("Atmakaraka",   "Unknown")
        ref["_vedic_amatyakaraka"] = vedic.get("chara_karakas", {}).get("Amatyakaraka", "Unknown")
        ref["_vedic_darakaraka"]   = vedic.get("chara_karakas", {}).get("Darakaraka",   "Unknown")

        moon_v = vedic.get("placements", {}).get("Moon", {})
        ref["_moon_nakshatra"] = moon_v.get("nakshatra", "Unknown")
        ref["_moon_pada"]      = moon_v.get("pada",      "Unknown")

        dasha = chart_data.get("vedic", {}).get("predictive", {}).get("vimshottari", {})
        ref["_maha_dasha"]         = dasha.get("maha_lord",              "Unknown")
        ref["_dasha_years_left"]   = dasha.get("approx_remaining_years", "Unknown")
        ref["_antar_dasha"]        = dasha.get("antar_lord",             "Unknown")
        ref["_antar_dasha_years"]  = dasha.get("antar_remaining_years",  "Unknown")

        strength = chart_data.get("bazi", {}).get("strength", {})
        dm       = strength.get("day_master", {})
        dm_stem  = dm.get("stem",    "")
        dm_elem  = dm.get("element", "")
        if dm_stem and dm_elem and dm_elem not in ("", "Unknown"):
            ref["_saju_available"] = True
            ref["_dm_stem"]        = dm_stem
            ref["_dm_element"]     = dm_elem
            ref["_dm_tier"]        = strength.get("tier",       "Unknown")
            ref["_useful_god"]     = strength.get("useful_god", "Unknown")
        else:
            ref["_saju_available"] = False
            ref["_dm_stem"]        = "UNAVAILABLE"
            ref["_dm_element"]     = "UNAVAILABLE"
            ref["_dm_tier"]        = "UNAVAILABLE"
            ref["_useful_god"]     = "UNAVAILABLE"

        pillars = chart_data.get("bazi", {}).get("natal", {}).get("pillars", {})
        for pname, pdata in pillars.items():
            if isinstance(pdata, dict):
                stem   = pdata.get("stem",         "?")
                branch = pdata.get("branch",        "?")
                s_el   = pdata.get("stem_element",  "?")
                b_el   = pdata.get("branch_element","?")
                void   = " [VOID]" if pdata.get("is_void") else ""
                ref[f"_saju_{pname}"] = f"{stem}{branch} ({s_el}/{b_el}){void}"

        da_yun    = chart_data.get("bazi", {}).get("predictive", {}).get("da_yun", {})
        yun_pills = da_yun.get("pillars", [])
        if yun_pills:
            ref["_current_da_yun"] = yun_pills[0]
        liu_nian = chart_data.get("bazi", {}).get("predictive", {}).get("liu_nian_timeline", [])
        ref["_liu_nian"] = liu_nian[:15]

        hell    = chart_data.get("hellenistic", {})
        lots    = hell.get("lots", {})
        fortune = lots.get("fortune", {})
        spirit  = lots.get("spirit",  {})
        prof    = hell.get("annual_profections", {})

        ref["_lot_fortune_sign"] = fortune.get("sign", "Unknown")
        ref["_lot_fortune_deg"]  = (_deg_to_dms(fortune.get("longitude", 0) % 30)
                                    if fortune.get("longitude") else "Unknown")
        ref["_lot_spirit_sign"]  = spirit.get("sign", "Unknown")
        ref["_is_day_chart"]     = fortune.get("is_day_chart", True)
        ref["_profection_sign"]  = prof.get("profected_sign",  "Unknown")
        ref["_profection_house"] = prof.get("activated_house", "Unknown")
        ref["_time_lord"]        = prof.get("time_lord",        "Unknown")
        ref["_hyleg"]            = hell.get("hyleg", "Unknown")

        patterns = w.get("patterns", {})
        ref["_patterns_summary"]  = patterns.get("summary", {})
        ref["_dominant_pattern"]  = patterns.get("summary", {}).get("dominant_pattern", "None")

        # Paran data — prefer true RAMC parans, fall back to conjunctions
        paran_data = w.get("parans", {})
        if isinstance(paran_data, dict):
            true_parans = paran_data.get("natal_parans", [])
            conj_parans = paran_data.get("conjunctions", [])
            ref["_parans"]           = (true_parans or conj_parans)[:8]
            ref["_significant_stars"] = paran_data.get("significant_stars", [])[:6]
            ref["_heliacal_events"]  = paran_data.get("heliacal_events", [])[:4]
        elif isinstance(paran_data, list):
            # orchestrator stores natal_parans list directly at western["natal"]["parans"]
            ref["_parans"]           = paran_data[:8]
            ref["_significant_stars"] = w.get("significant_stars", [])[:6]
            ref["_heliacal_events"]  = w.get("heliacal_events", [])[:4]
        else:
            ref["_parans"]           = []
            ref["_significant_stars"] = w.get("significant_stars", [])[:6]
            ref["_heliacal_events"]  = w.get("heliacal_events", [])[:4]

        pd       = chart_data.get("western", {}).get("predictive", {}).get("primary_directions", {})
        all_dirs = []
        for cat in pd.values():
            if isinstance(cat, list):
                all_dirs.extend(cat[:2])
        ref["_primary_directions"] = all_dirs[:4]

        syzygy = w.get("syzygy", {})
        ref["_syzygy_type"]       = syzygy.get("type",            "Unknown")
        ref["_syzygy_sign"]       = syzygy.get("sign",            "Unknown")
        ref["_syzygy_days_before"]= syzygy.get("days_before_birth","Unknown")

        dignities   = w.get("dignities", {})
        pd_dig      = dignities.get("planet_dignities", {})
        ref["_almuten"] = dignities.get("almuten", {}).get("almuten", "Unknown")

        # ── Almuten dignity (needed by _compute_wealth_score) ─────────────────
        _SIGN_RULERS = {
            "Aries": "Mars", "Taurus": "Venus", "Gemini": "Mercury",
            "Cancer": "Moon", "Leo": "Sun", "Virgo": "Mercury",
            "Libra": "Venus", "Scorpio": "Mars", "Sagittarius": "Jupiter",
            "Capricorn": "Saturn", "Aquarius": "Saturn", "Pisces": "Jupiter"
        }
        almuten_name = ref["_almuten"]
        alm_dig_data = pd_dig.get(almuten_name, {})
        if isinstance(alm_dig_data, dict):
            if alm_dig_data.get("rulership", 0) > 0:
                ref["_almuten_dignity"] = "domicile"
            elif alm_dig_data.get("exaltation", 0) > 0:
                ref["_almuten_dignity"] = "exaltation"
            elif alm_dig_data.get("triplicity", 0) > 0:
                ref["_almuten_dignity"] = "triplicity"
            elif alm_dig_data.get("detriment", 0) < 0:
                ref["_almuten_dignity"] = "detriment"
            elif alm_dig_data.get("fall", 0) < 0:
                ref["_almuten_dignity"] = "fall"
            else:
                ref["_almuten_dignity"] = "neutral"
        else:
            ref["_almuten_dignity"] = "neutral"

        # ── House signs & lords (needed by _compute_wealth_score) ─────────────
        # 2nd house sign and its traditional lord
        houses_w = w.get("houses", {})
        h2_data  = houses_w.get("House_2", {})
        h2_sign  = (h2_data.get("sign") or h2_data.get("cusp_sign") or
                    h2_data.get("sign_name", ""))
        ref["_2nd_house_sign"] = h2_sign
        ref["_2nd_house_lord"] = _SIGN_RULERS.get(h2_sign, "")

        # MC sign (for industry mapping in wealth score)
        mc_data = w.get("angles", {}).get("Midheaven", {})
        ref["_mc_sign"] = (mc_data.get("sign") or mc_data.get("sign_name", "")
                           if isinstance(mc_data, dict) else "")
        best_p, best_s = None, -99
        for p, d in pd_dig.items():
            if isinstance(d, dict) and d.get("total_score", -99) > best_s:
                best_s = d.get("total_score", -99)
                best_p = p
        ref["_most_dignified"]       = best_p or "Unknown"
        ref["_most_dignified_score"] = best_s

        dodec     = hell.get("dodecatemoria", {})
        dodec_sum = dodec.get("summary", {})
        ref["_dodec_dominant_sign"]  = dodec_sum.get("dominant_dodecatemoria_sign",   "Unknown")
        ref["_dodec_dominant_ruler"] = dodec_sum.get("dominant_dodecatemoria_ruler",  "Unknown")
        ref["_dodec_own_planets"]    = dodec_sum.get("own_dodecatemoria_planets",     {})

        # Bonifications summary — available in all section prompts via ref
        bonds = hell.get("bonifications", {})
        if bonds and isinstance(bonds, dict) and "error" not in bonds:
            maltreated = [p for p, d in bonds.items()
                          if isinstance(d, dict) and d.get("maltreatment")]
            bonified   = [p for p, d in bonds.items()
                          if isinstance(d, dict) and d.get("bonification")]
            ref["_maltreated_planets"] = maltreated
            ref["_bonified_planets"]   = bonified
            ref["_bonifications"]      = bonds
        else:
            ref["_maltreated_planets"] = []
            ref["_bonified_planets"]   = []
            ref["_bonifications"]      = {}

        return ref

    # ─────────────────────────────────────────────────────────────────────────
    # Header
    # ─────────────────────────────────────────────────────────────────────────

    def _generate_header(self, metadata: dict, chart_data: dict = None,
                         ref: dict = None) -> str:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
        name      = metadata.get("name", "Unknown")
        loc       = metadata.get("location", "")
        bt        = metadata.get("birth_time", "")

        # Extract key chart signature for subtitle
        sun_sign  = ""
        moon_sign = ""
        asc_sign  = ""
        if ref:
            sun_sign  = ref.get("Sun",       {}).get("sign", "") if isinstance(ref.get("Sun"), dict) else ""
            moon_sign = ref.get("Moon",      {}).get("sign", "") if isinstance(ref.get("Moon"), dict) else ""
            asc_sign  = ref.get("Ascendant", {}).get("sign", "") if isinstance(ref.get("Ascendant"), dict) else ""
        if all([sun_sign, moon_sign, asc_sign]):
            sig = f"{sun_sign} Sun · {moon_sign} Moon · {asc_sign} Ascendant"
        elif sun_sign and moon_sign:
            sig = f"{sun_sign} Sun · {moon_sign} Moon · Time Unknown"
        elif sun_sign:
            sig = f"{sun_sign} Sun · Time Unknown"
        else:
            sig = ""

        time_known = chart_data.get("meta", {}).get("time_known", True) if chart_data else True
        time_note  = "" if time_known else "\n> ⚠️ **Birth time unknown** — house-sensitive techniques (Ascendant, house lords, Parans, ZR) are suppressed. All planet-based calculations remain active.\n"

        return f"""# THE CELESTIAL DOSSIER
## {name}

{f'*{sig}*' if sig else ''}

**Prepared:** {timestamp}  
**Birth:** {bt} · {loc}  
**Systems:** Western Tropical · Vedic Sidereal · Saju (Bazi) · Hellenistic  
**Methods:** Primary Directions (Regiomontanus) · Vimshottari Dasha · Annual Profections · Firdaria · Tajaka · Kakshya · Shadbala (Parashara) · True RAMC Parans · Zodiacal Releasing L1–L3

---
{time_note}
*This dossier synthesises four independent astrological traditions into a single coherent portrait.
Where systems agree, confidence is high. Where they diverge, both signals are named and weighted.*

---

"""

    # ─────────────────────────────────────────────────────────────────────────
    # Enforcement & Validation (preserved from v1)
    # ─────────────────────────────────────────────────────────────────────────

    def _enforce_section_header(self, content: str, sd: dict) -> str:
        expected = f"# {sd['header']}"
        if not content.strip().startswith(expected):
            content = f"{expected}\n\n" + content.lstrip()
        return content


    def _audit_past_dates(self, content: str, sec_num: int) -> str:
        """
        For the questions section only: scan for past-year citations and correct them.
        Replaces past year references with current/future equivalents.
        """
        today = datetime.now(timezone.utc)
        current_year = today.year

        sd_id = SECTION_DEFS.get(sec_num, {}).get("id", f"sec{sec_num}")
        if sd_id != "questions":
            return content

        # Find all 4-digit year patterns in the text
        year_mentions = re.findall(r'\b(20\d{2})\b', content)
        past_years = [y for y in year_mentions if int(y) < current_year]

        if not past_years:
            logger.info("Questions date audit: CLEAN — no past years found.")
            return content

        unique_past = sorted(set(past_years))
        logger.warning(
            f"PAST DATE VIOLATION in questions section: "
            f"Past years cited: {unique_past}. Correcting..."
        )

        # Replace past year references with current year
        for past_year in unique_past:
            past_int = int(past_year)
            offset = current_year - past_int
            replacement_year = str(current_year + max(0, offset - 1))
            content = re.sub(rf'\b{past_year}\b', replacement_year, content)
            logger.info(f"  Replaced year {past_year} → {replacement_year}")

        # Fix "Month Year" patterns where month in current year is already past
        months = ["January", "February", "March", "April", "May", "June",
                  "July", "August", "September", "October", "November", "December"]
        current_month = today.month
        for m_idx, month_name in enumerate(months, 1):
            pattern = rf'\b({month_name})\s+({current_year})\b'
            for match in re.finditer(pattern, content):
                if m_idx < current_month:
                    content = content.replace(
                        match.group(0),
                        f"{month_name} {current_year + 1}"
                    )
                    logger.info(f"  Shifted past month: {match.group(0)} → {month_name} {current_year + 1}")

        return content

    # ─────────────────────────────────────────────────────────────────────────
    # Phase 3.2: Voice Consistency Verification
    # ─────────────────────────────────────────────────────────────────────────

    VOICE_CHECK_SCHEMA = {
        "type": "object",
        "properties": {
            "issues": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "section_index": {"type": "integer", "description": "0-based index of the problematic section"},
                        "issue": {"type": "string", "description": "Description of the consistency problem"},
                        "severity": {"type": "string", "enum": ["HIGH", "MEDIUM", "LOW"]},
                    },
                    "required": ["section_index", "issue", "severity"],
                },
            },
            "overall_coherent": {"type": "boolean"},
        },
        "required": ["issues", "overall_coherent"],
    }

    def _check_voice_consistency(self, sections: list, sec_nums: list) -> list:
        """Run lightweight voice consistency check across all sections.

        Phase 3.2: After all sections are generated, scan for:
        - Tone shifts (formal ↔ casual within the report)
        - Contradictory planet descriptions (e.g., "Mars is strong" vs "Mars is debilitated")
        - Date/prediction contradictions between sections
        - Cross-section factual inconsistencies

        Cost: ~$0.10 per check (gemini-2.5-flash).
        Returns list of issue dicts with section_index, issue, severity.
        """
        if len(sections) < 3:
            return []  # Not enough sections to check

        # Build condensed section summaries (first 300 chars each) to stay under token limits
        section_summaries = []
        for i, (sec_num, content) in enumerate(zip(sec_nums, sections)):
            sd = SECTION_DEFS.get(sec_num, {})
            title = sd.get("title", f"Section {sec_num}")
            # Take first 300 chars of content, excluding headers
            lines = [l for l in content.split("\n") if l.strip() and not l.startswith("#")]
            snippet = " ".join(lines)[:300]
            section_summaries.append(f"[{i}] {title}: {snippet}")

        check_prompt = (
            "Review these report sections for cross-section consistency.\n"
            "Flag any: (1) contradictory planet descriptions, (2) contradictory date claims,\n"
            "(3) tone shifts between sections, (4) facts stated in one section that are\n"
            "contradicted in another.\n\n"
            "Only flag HIGH severity for genuine factual contradictions.\n"
            "Flag MEDIUM for tone inconsistencies. Flag LOW for minor style variance.\n\n"
            "SECTIONS:\n" + "\n\n".join(section_summaries)
        )

        try:
            result = gateway.structured_generate(
                system_prompt="You are a report quality auditor checking for cross-section consistency.",
                user_prompt=check_prompt,
                output_schema=self.VOICE_CHECK_SCHEMA,
                model=settings.translation_model,  # gemini-2.5-flash — fast + cheap
                max_tokens=2000,
                temperature=0.0,
            )

            if result.get("success") and result.get("data"):
                issues = result["data"].get("issues", [])
                coherent = result["data"].get("overall_coherent", True)
                if issues:
                    logger.info(
                        f"Voice consistency: {len(issues)} issues, coherent={coherent}"
                    )
                    for issue in issues:
                        logger.info(
                            f"  [{issue.get('severity')}] Section {issue.get('section_index')}: "
                            f"{issue.get('issue', '')[:100]}"
                        )
                return issues
        except Exception as e:
            logger.warning(f"Voice consistency check failed: {e}")

        return []

    # ─────────────────────────────────────────────────────────────────────────
    # Burmese Translation Layer
    # ─────────────────────────────────────────────────────────────────────────

    _BURMESE_GLOSSARY: Optional[dict] = None

    @classmethod
    def _load_burmese_glossary(cls) -> dict:
        """Load Burmese astrology glossary, cached after first load."""
        if cls._BURMESE_GLOSSARY is not None:
            return cls._BURMESE_GLOSSARY
        import os
        path = os.path.join(os.path.dirname(os.path.dirname(__file__)),
                            "data", "burmese_glossary.json")
        try:
            with open(path, "r", encoding="utf-8") as f:
                cls._BURMESE_GLOSSARY = json.load(f)
                return cls._BURMESE_GLOSSARY
        except (FileNotFoundError, json.JSONDecodeError) as e:
            logger.warning(f"Burmese glossary unavailable: {e}")
            return {}

    def _translate_section(self, content: str, glossary: dict,
                           section_type: str = "") -> str:
        """Translate one English report section to Burmese via LLM."""
        glossary_compact = json.dumps(glossary, ensure_ascii=False, indent=1)

        sys_prompt = (
            "You are an expert translator specializing in astrology (ဗေဒင်) texts. "
            "Translate the following English astrological report section into natural, "
            "fluent Burmese (Myanmar Unicode / ယူနီကုဒ်).\n\n"
            "RULES:\n"
            "1. Use the GLOSSARY below for all astrological terms — do not invent translations.\n"
            "2. Preserve ALL [bracketed citations] VERBATIM in English — do not translate inside [].\n"
            "3. Preserve all dates in YYYY-MM-DD format exactly as written.\n"
            "4. Preserve all markdown formatting: # headers, **bold**, *italic*, ---, bullet points.\n"
            "5. Use Myanmar numerals (၁၂၃၄၅၆၇၈၉) for general numbers but keep Arabic numerals "
            "in dates (2027-03-14) and degrees (23° 42').\n"
            "6. Write in a warm, authoritative advisory tone — not academic, not casual.\n"
            "7. Burmese astrology readers are familiar with both Baydin and Hindu-derived terms.\n"
            "8. Do NOT add content, commentary, or explanations. Translate only.\n\n"
            f"GLOSSARY:\n{glossary_compact}"
        )

        # Estimate output tokens — Burmese Unicode is ~1.3-1.5x more tokens than English
        est_output_tokens = max(2000, int(len(content) / 3 * 1.5))

        response = gateway.generate(
            system_prompt=sys_prompt,
            user_prompt=f"Translate this section to Burmese:\n\n{content}",
            model=settings.translation_model,
            max_tokens=est_output_tokens,
            temperature=0.3,
            reasoning_effort="low",
        )

        if response.get("success"):
            return response["content"]
        else:
            logger.error(f"Translation failed for section ({section_type}): {response.get('error')}")
            return content  # Fallback: return English

    @staticmethod
    def _translate_header(header: str, glossary: dict) -> str:
        """Translate report header using programmatic replacement (no LLM call)."""
        structural = glossary.get("structural", {})
        translated = header

        # Title
        translated = translated.replace(
            "# THE CELESTIAL DOSSIER",
            f"# {structural.get('THE CELESTIAL DOSSIER', 'THE CELESTIAL DOSSIER')}"
        )

        # Metadata labels
        label_map = {
            "**Prepared:**": f"**{structural.get('Prepared', 'Prepared')}:**",
            "**Birth:**": f"**{structural.get('Birth', 'Birth')}:**",
            "**Systems:**": f"**{structural.get('Systems', 'Systems')}:**",
            "**Methods:**": f"**{structural.get('Methods', 'Methods')}:**",
        }
        for eng, bur in label_map.items():
            translated = translated.replace(eng, bur)

        # System names
        system_map = {
            "Western Tropical": structural.get("Western Tropical", "Western Tropical"),
            "Vedic Sidereal": structural.get("Vedic Sidereal", "Vedic Sidereal"),
            "Saju (Bazi)": structural.get("Saju (Bazi)", "Saju (Bazi)"),
            "Hellenistic": structural.get("Hellenistic", "Hellenistic"),
        }
        for eng, bur in system_map.items():
            translated = translated.replace(eng, bur)

        # Footer note
        translated = translated.replace(
            "This dossier synthesises four independent astrological traditions "
            "into a single coherent portrait.",
            "ဤအစီရင်ခံစာသည် လွတ်လပ်သော ဗေဒင်အစဉ်အလာ လေးခုကို "
            "တစ်ခုတည်းသော ပုံတူတစ်ခုအဖြစ် ပေါင်းစပ်ထားပါသည်။"
        )
        translated = translated.replace(
            "Where systems agree, confidence is high. "
            "Where they diverge, both signals are named and weighted.",
            "စနစ်များ သဘောတူညီပါက ယုံကြည်မှုမြင့်မားပါသည်။ "
            "ကွဲလွဲပါက အချက်နှစ်ခုစလုံးကို အလေးချိန်ဖြင့် ဖော်ပြပါသည်။"
        )

        return translated

    @staticmethod
    def _get_burmese_part_labels(glossary: dict) -> dict:
        """Return Burmese part divider labels."""
        structural = glossary.get("structural", {})
        return {
            "I":   f"\n\n---\n\n# {structural.get('PART I: THE NATIVITY', 'PART I: THE NATIVITY')}\n\n---\n\n",
            "II":  f"\n\n---\n\n# {structural.get('PART II: THE FIFTEEN-YEAR ALMANAC', 'PART II: THE FIFTEEN-YEAR ALMANAC')}\n\n---\n\n",
            "III": f"\n\n---\n\n# {structural.get('PART III: THE DIRECTIVE', 'PART III: THE DIRECTIVE')}\n\n---\n\n",
            "IV":  f"\n\n---\n\n# {structural.get('PART IV: YOUR QUESTIONS', 'PART IV: YOUR QUESTIONS')}\n\n---\n\n",
        }

    # ─────────────────────────────────────────────────────────────────────────
    # Per-Question QA Pipeline Integration (Audit 5A/5B/5C)
    # ─────────────────────────────────────────────────────────────────────────

    @staticmethod
    def _load_domain_knowledge() -> dict:
        """Load curated domain knowledge from data/domain_knowledge.json."""
        import os
        path = os.path.join(os.path.dirname(os.path.dirname(__file__)),
                            "data", "domain_knowledge.json")
        try:
            with open(path, "r") as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError) as e:
            logger.warning(f"Domain knowledge unavailable: {e}")
            return {}

    @staticmethod
    def _match_domain_context(question: str, domain_kb: dict) -> str:
        """Match a question to relevant domain knowledge entries."""
        if not domain_kb:
            return ""
        q_lower = question.lower()
        matched = []

        # Theme keywords → domain key prefixes
        theme_map = {
            "career": ["career:", "wealth:business"],
            "job": ["career:"],
            "doctor": ["career:doctor"],
            "gp": ["career:doctor"],
            "money": ["wealth:"],
            "wealth": ["wealth:"],
            "rich": ["wealth:"],
            "property": ["wealth:property"],
            "house": ["wealth:property"],
            "invest": ["wealth:investment"],
            "marriage": ["relationship:marriage"],
            "partner": ["relationship:marriage"],
            "relationship": ["relationship:"],
            "child": ["relationship:children"],
            "baby": ["relationship:children"],
            "health": ["health:"],
            "mental": ["health:mental"],
            "spiritual": ["spiritual:"],
            "meditat": ["spiritual:buddhist"],
            "buddhis": ["spiritual:buddhist"],
            "relocat": ["relocation:"],
            "move": ["relocation:"],
            "timing": ["timing:"],
            "when": ["timing:"],
        }

        matching_prefixes = set()
        for keyword, prefixes in theme_map.items():
            if keyword in q_lower:
                matching_prefixes.update(prefixes)

        # UK-specific if question mentions UK context or user is UK-based
        uk_relevant = "uk" in q_lower or "england" in q_lower or "nhs" in q_lower

        for key, entry in domain_kb.items():
            for prefix in matching_prefixes:
                if key.startswith(prefix):
                    # Prefer UK-specific entries when relevant
                    if uk_relevant and ":UK" in key:
                        matched.insert(0, f"[{key}] {json.dumps(entry)}")
                    elif ":general" in key or (uk_relevant and ":UK" in key):
                        matched.append(f"[{key}] {json.dumps(entry)}")
                    elif not any(f":{country}" in key for country in ["UK", "US", "IN"]):
                        matched.append(f"[{key}] {json.dumps(entry)}")

        # Always include general entries for matched themes
        if not uk_relevant:
            for key, entry in domain_kb.items():
                if ":general" in key and any(key.startswith(p) for p in matching_prefixes):
                    line = f"[{key}] {json.dumps(entry)}"
                    if line not in matched:
                        matched.append(line)

        return "\n".join(matched[:5])  # Cap at 5 entries to avoid token bloat

    def _generate_questions_via_pipeline(
        self,
        questions: list,
        chart_data: dict,
        ref: dict,
        temporal_clusters: list,
        citation_registry: dict,
        verdict_ledger_block: str = "",
    ) -> str:
        """Generate Q&A section using the per-question REASON→VERIFY→NARRATE pipeline."""
        today = datetime.now(timezone.utc)
        router = QuestionRouter(today)
        domain_kb = self._load_domain_knowledge()

        # Build per-question evidence blocks and domain contexts
        evidence_blocks = {}
        domain_contexts = {}
        for i, q in enumerate(questions):
            _target_houses = (
                self._query_context.get("target_houses", [])
                if self._query_context else []
            )
            evidence_blocks[i] = router.build_evidence_block(
                question=q,
                chart_data=chart_data,
                temporal_clusters=temporal_clusters,
                ref=ref,
                question_num=i + 1,
                validation_matrix=self._validation_matrix,
                target_houses=_target_houses,
            )
            domain_contexts[i] = self._match_domain_context(q, domain_kb)

        # Build arbiter context for the pipeline (verdict ledger + section memory)
        arbiter_context = ""
        if verdict_ledger_block:
            arbiter_context += verdict_ledger_block + "\n\n"
        if self._section_memory:
            arbiter_context += self._format_section_memory()

        # Run the pipeline (pass house_lords for claim verification)
        house_lords = chart_data.get("house_lords", {})
        pipeline = QAPipeline(ref=ref, citation_registry=citation_registry,
                              house_lords=house_lords)
        content = pipeline.answer_all(
            questions=questions,
            evidence_blocks=evidence_blocks,
            domain_contexts=domain_contexts,
            arbiter_context=arbiter_context,
        )

        return content

    def _build_citation_registry(self, chart_data: dict, ref: dict, temporal_clusters: list) -> dict:
        """Build flat registry of verifiable astrological facts for citation validation."""
        registry = {}

        # Planet positions from ref dict
        for planet, data in ref.items():
            if isinstance(data, dict) and data.get("sign"):
                dms = data.get("dms", _deg_to_dms(data.get("degree", 0)))
                registry[planet] = f"{dms}' {data['sign']}"

        # Transit dates from western predictive data
        w_pred = chart_data.get("western", {}).get("predictive", {})
        outer = w_pred.get("outer_transit_aspects", {})
        for hit in outer.get("hits") or outer.get("all_hits", []):
            transiting = hit.get("transiting", "?")
            natal_pt = hit.get("natal_point", "?")
            aspect = hit.get("aspect", "?")
            exact = hit.get("exact_date_iso", hit.get("exact_date", ""))
            entry = hit.get("entry_date", "")
            exit_d = hit.get("exit_date", "")
            key = f"{transiting}_{aspect}_{natal_pt}"
            registry[key] = f"exact {exact}, entry {entry}, exit {exit_d}"

        # Dasha info
        v_pred = chart_data.get("vedic", {}).get("predictive", {})
        dasha = v_pred.get("vimshottari", {})
        if dasha:
            registry["Maha_Dasha"] = f"{dasha.get('maha_lord', '?')} ({dasha.get('approx_remaining_years', '?')}yr remaining)"
            registry["Antar_Dasha"] = f"{dasha.get('antar_lord', '?')}"

        # Shadbala scores
        strength = chart_data.get("vedic", {}).get("strength", {})
        shadbala = strength.get("shadbala", {})
        if isinstance(shadbala, dict):
            for planet, sb_data in shadbala.items():
                if isinstance(sb_data, dict):
                    rupas = sb_data.get("total_rupas", sb_data.get("rupas", 0))
                    tier = sb_data.get("tier", "")
                    registry[f"Shadbala_{planet}"] = f"{rupas:.2f} Rupas ({tier})"

        # Storm window dates from temporal clusters
        if temporal_clusters:
            for i, c in enumerate(temporal_clusters[:15]):
                start = c.get("start_date", c.get("start", "?"))
                end = c.get("end_date", c.get("end", "?"))
                score = c.get("convergence_score", 0)
                label = c.get("confidence_label", "?")
                registry[f"storm_window_{i+1}"] = f"{start}\u2013{end} score={score:.2f} {label}"

        return registry

    def _validate_citations(self, content: str, citation_registry: dict) -> str:
        """Validate [bracketed citations] in generated text against the citation registry.

        Checks degree claims and date claims. Logs mismatches.
        Does not strip content \u2014 only logs warnings for now.
        """
        import re

        # Find all bracketed citations
        citations = re.findall(r'\[([^\]]+)\]', content)
        if not citations:
            return content

        validated = 0
        warnings = 0

        for citation in citations:
            # Check degree claims: "Sun at 23\u00b0 42' Cancer" or "Jupiter 14\u00b055' Sag"
            deg_match = re.search(r'(\w+)\s+(?:at\s+)?(\d{1,2})\u00b0\s*(\d{2})\'?\s*(\w+)', citation)
            if deg_match:
                planet = deg_match.group(1)
                claimed_deg = int(deg_match.group(2))
                claimed_sign = deg_match.group(4)
                ref_val = citation_registry.get(planet, "")
                if ref_val and claimed_sign in ref_val:
                    validated += 1
                elif ref_val:
                    logger.warning(f"CITATION MISMATCH: [{citation}] \u2014 registry has {planet}={ref_val}")
                    warnings += 1
                continue

            # Check date claims: "exact 2027-03-14" or "entry 2027-01-22"
            date_match = re.search(r'(?:exact|entry|exit)\s+(\d{4}-\d{2}-\d{2})', citation)
            if date_match:
                claimed_date = date_match.group(1)
                # Search registry for this date
                found = any(claimed_date in v for v in citation_registry.values())
                if found:
                    validated += 1
                else:
                    logger.warning(f"CITATION DATE NOT IN REGISTRY: [{citation}] \u2014 date {claimed_date} not found")
                    warnings += 1

        if validated or warnings:
            logger.info(f"Citation audit: {validated} validated, {warnings} warnings out of {len(citations)} citations")

        return content

    def _validate_consensus_claims(self, content: str, expert_analyses: list) -> str:
        """Validate claims like 'all four systems agree' against actual expert outputs.

        Checks that claimed agreeing systems actually mention the relevant theme.
        Logs corrections but does not modify content (informational audit).
        """
        import re

        if not expert_analyses:
            return content

        # Build system text lookup
        system_texts = {}
        for ea in expert_analyses:
            sys_name = ea.get("system", "").lower()
            text = ea.get("analysis", "").lower()
            if sys_name and text:
                system_texts[sys_name] = text

        # Find consensus claims
        consensus_patterns = [
            (r'all\s+four\s+systems\s+(?:agree|converge|point|confirm)', 4),
            (r'(?:four|4)\s+(?:independent\s+)?systems\s+(?:agree|converge)', 4),
            (r'(?:three|3)\s+(?:independent\s+)?systems\s+(?:agree|converge|point)', 3),
            (r'(\d+)\s+systems\s+(?:agree|converge|point)', None),  # dynamic count
        ]

        for pattern, expected_count in consensus_patterns:
            matches = list(re.finditer(pattern, content, re.IGNORECASE))
            for match in matches:
                if expected_count is None:
                    expected_count = int(match.group(1))

                # Get surrounding context (200 chars) to find theme
                start = max(0, match.start() - 100)
                end = min(len(content), match.end() + 200)
                context = content[start:end].lower()

                # Extract theme keywords from context
                theme_words = re.findall(r'\b(career|wealth|health|relationship|marriage|home|property|children|spiritual|identity|crisis|opportunity|transformation)\b', context)

                if not theme_words:
                    continue

                # Check how many systems actually mention these themes
                confirming_systems = []
                for sys_name, sys_text in system_texts.items():
                    if any(tw in sys_text for tw in theme_words):
                        confirming_systems.append(sys_name)

                actual_count = len(confirming_systems)
                if actual_count < expected_count:
                    logger.warning(
                        f"CONSENSUS OVERCLAIM: '{match.group(0)}' near themes {theme_words} \u2014 "
                        f"only {actual_count} systems ({confirming_systems}) mention these themes, "
                        f"not {expected_count}"
                    )

        return content

