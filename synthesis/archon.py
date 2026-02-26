"""
Archon v2 — The Celestial Dossier
Master narrative architect for the 13-Section premium astrological report.

STRUCTURE:
  PART I:   THE NATIVITY     (5 sections — natal portrait)
  PART II:  THE ALMANAC      (6 sections — year-by-year chronological forecast)
  PART III: THE DIRECTIVE    (2 sections — mandate and warning)

UPGRADE FROM v1:
  v1: 10 chapters; predictive split by domain (finances/career/health × 3 years)
  v2: 13 sections; predictive chronological (all domains per year × 5 years)
      + Oracle Opening hook, Current Configuration bridge, merged natal chapters
"""

import logging
import json
import re
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional

from experts.gateway import gateway
from config import settings

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
        "words": (380, 420),
        "focus": (
            "Write as if you have known this person for 20 years. "
            "Zero jargon. Zero sign names in the first paragraph. "
            "Pure mirror — name the core paradox of their existence in plain language. "
            "Every sentence should produce a gut-punch of recognition. "
            "Build to a single closing sentence that names the central paradox of this chart "
            "in language a non-astrologer immediately understands."
        ),
        "domains": [],
    },

    1: {
        "id": "architecture_of_self",
        "part": "I",
        "title": "I. THE ARCHITECTURE OF SELF",
        "header": "I. THE ARCHITECTURE OF SELF",
        "type": "natal",
        "words": (680, 740),
        "focus": (
            "The deep natal portrait: core identity, soul myth, psychological engine. "
            "Synthesize Sun + Moon + Ascendant + Atmakaraka + Day Master + Almuten. "
            "Name the ONE central myth this chart is living. "
            "Include fixed star parans if present — Brady-style fate signatures. "
            "End with the wound and its medicine — specific, unflinching."
        ),
        "domains": ["Sun", "Moon", "Ascendant", "Atmakaraka", "Fixed Stars", "Almuten"],
    },

    2: {
        "id": "material_world",
        "part": "I",
        "title": "II. THE MATERIAL WORLD",
        "header": "II. THE MATERIAL WORLD",
        "type": "natal",
        "words": (680, 740),
        "focus": (
            "Finances AND career as a single unified portrait — they share the same root. "
            "How does this chart build material reality? What does it attract and repel? "
            "The wealth trap, the career trap, the legacy mechanism. "
            "Saturn, MC, House 2, Lot of Fortune, Amatyakaraka, Useful God must all appear. "
            "Name the specific financial behavior pattern and the specific professional blindspot."
        ),
        "domains": ["House 2", "MC", "Saturn", "Lot of Fortune", "Amatyakaraka", "Useful God"],
    },

    3: {
        "id": "inner_world",
        "part": "I",
        "title": "III. THE INNER WORLD",
        "header": "III. THE INNER WORLD",
        "type": "natal",
        "words": (680, 740),
        "focus": (
            "Relationships AND health as a single portrait — both reveal how the person "
            "sustains themselves under pressure. The love wound alongside the body that carries it. "
            "Venus, Mars, Moon, Darakaraka, Descendant, House 6, House 7 must all appear. "
            "Name the specific attachment pattern. Name the 2-3 bodily vulnerabilities. "
            "Show how the emotional wound and the physical symptom are the same energy."
        ),
        "domains": ["Venus", "Mars", "Moon", "Darakaraka", "House 6", "House 7", "Constitution"],
    },

    4: {
        "id": "karmic_mandate",
        "part": "I",
        "title": "IV. THE KARMIC MANDATE",
        "header": "IV. THE KARMIC MANDATE",
        "type": "natal",
        "words": (680, 740),
        "focus": (
            "The WHY of this incarnation. Elevated, sacred, serious. "
            "North Node, Ketu, Atmakaraka curriculum, Lot of Spirit, Syzygy, fixed star fate signatures. "
            "Name the karmic debt (South Node theme) and the karmic credit (North Node destination). "
            "What must be burned through? What is being built across lifetimes? "
            "Current dasha as the karmic instrument active right now."
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

    6: {
        "id": "year_2026",
        "part": "II",
        "title": "YEAR 2026",
        "header": "YEAR 2026",
        "type": "year_forecast",
        "target_year": 2026,
        "words": (580, 640),
        "focus": (
            "ALL domains in one chronological flow for 2026. "
            "Career/Finance windows → Relationship signals → Health vulnerabilities → "
            "Critical convergence dates. "
            "End with THE ONE ACTION this year demands — specific, dated, concrete. "
            "Include a thematic title in the format: **2026: [Evocative 3-5 word title]**"
        ),
        "domains": ["Profection 2026", "Transits 2026", "Tajaka 2026", "Liu Nian 2026", "Kakshya"],
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
            "ALL domains in one chronological flow for 2027. "
            "Career/Finance windows → Relationship signals → Health vulnerabilities → "
            "Critical convergence dates. "
            "End with THE ONE ACTION this year demands. "
            "Include thematic title: **2027: [Evocative 3-5 word title]**"
        ),
        "domains": ["Profection 2027", "Transits 2027", "Tajaka 2027", "Dasha shifts 2027"],
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
            "ALL domains in one chronological flow for 2028. "
            "Career/Finance → Relationships → Health → Convergence dates. "
            "One action demanded. "
            "Thematic title: **2028: [Evocative 3-5 word title]**"
        ),
        "domains": ["Profection 2028", "Transits 2028", "Tajaka 2028", "Da Yun shifts"],
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
            "ALL domains in one chronological flow for 2029. "
            "Career/Finance → Relationships → Health → Convergence dates. "
            "One action demanded. "
            "Thematic title: **2029: [Evocative 3-5 word title]**"
        ),
        "domains": ["Profection 2029", "Uranus conjunct Venus", "Transits 2029", "Tajaka 2029"],
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
            "ALL domains in one chronological flow for 2030. "
            "Career/Finance → Relationships → Health → Convergence dates (incl. Oct 13 Primary Directions). "
            "One action demanded. "
            "Thematic title: **2030: [Evocative 3-5 word title]**"
        ),
        "domains": ["Profection 2030", "Primary Directions Oct 2030", "Transits 2030", "Tajaka 2030"],
    },

    # ── PART III: THE DIRECTIVE ───────────────────────────────────────────────

    11: {
        "id": "directive",
        "part": "III",
        "title": "◈ THE FIVE-YEAR DIRECTIVE",
        "header": "◈ THE FIVE-YEAR DIRECTIVE",
        "type": "directive",
        "words": (280, 340),
        "focus": (
            "Three elements, in this order:\n"
            "1. THE RED THREAD: One sentence only. Must name the specific Sun/Moon/Asc combination "
            "and the core paradox. Could ONLY be written about this exact chart. "
            "No vague spiritual language.\n"
            "2. THE FIVE-YEAR ORDERS: One concrete, dated, technical action per year 2026–2030. "
            "Reads like orders, not suggestions. Name the technique, the window, the practice.\n"
            "3. No padding. No encouragement. Only the mandate."
        ),
        "domains": ["Synthesis", "Red Thread", "Dated Actions"],
    },

    12: {
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
}


# ─────────────────────────────────────────────────────────────────────────────
# System Prompts per section type
# ─────────────────────────────────────────────────────────────────────────────

ORACLE_PROMPT = """You are the Archon, opening a premium astrological dossier.

Write THE ORACLE'S OPENING for this specific chart.

ABSOLUTE RULES:
1. First paragraph: ZERO astrological jargon. No sign names. No degrees. No technique names.
   Write as if you have known this person for 20 years and are speaking directly to them.
2. Second paragraph: Begin weaving in chart evidence, but only after you have hooked the reader.
3. Every sentence must produce recognition — the "how does it know that?" feeling.
4. BANNED WORDS: journey, tapestry, dance, weave, explore, cosmic, realm, universe, energy, vibration.
   USE INSTEAD: compulsion, trap, pressure, hunger, pattern, engine, wound, debt, credit, demand.
5. LENGTH: 380-420 words exactly. Dense. Every sentence earns its place.
6. FINAL SENTENCE: Name the core paradox in plain language. Could ONLY be this chart.
7. Start with: # ◈ THE ORACLE'S OPENING"""

NATAL_PROMPT = """You are the Archon, master synthesizer of four astrological systems writing a premium astrological dossier.

ABSOLUTE RULES:
1. USE EXACT DEGREES from the MANDATORY NATAL DATA block. Format: 19° 43' Cancer. Never invent.
2. NO SUBHEADINGS for individual systems. Synthesize — Western, Vedic, Saju, Hellenistic in one voice.
3. CITE TECHNICAL EVIDENCE in parentheses: (Sun 27° 10' Cancer, Mercury Dasha, Lot of Fortune Gemini)
4. WHEN SYSTEMS CONFLICT, STATE IT DIRECTLY: "Western suggests X; Saju indicates Y — this means Z."
5. BANNED WORDS: journey, tapestry, dance, weave, explore, intricate, realm, dynamic interplay, multifaceted, embody.
   USE INSTEAD: compulsion, trap, pressure, gift, blindspot, medicine, hunger, pattern, force, engine, wound.
6. LENGTH: 680-740 words. Dense. No padding. Every sentence earns its place.
7. START with exactly: # {HEADER}
8. Bold key terms: **Atmakaraka**, **Amatyakaraka**, **Maha Dasha**, **Almuten**, **Hyleg**, **Naibod Arc**
9. When Bazi shows UNAVAILABLE: omit Saju claims entirely.
10. PREMIUM VOICE: Precise, unflinching diagnosis. Name the specific trap, gift, medicine. No encouragement."""

YEAR_FORECAST_PROMPT = """You are the Archon, writing the predictive almanac section of a premium astrological dossier.

ABSOLUTE RULES:
1. DO NOT re-diagnose the natal chart. Chapters 1-4 covered the nativity. Brief anchors only.
2. ALL DOMAINS IN ONE FLOW: Career/Finance → Relationships → Health → Critical dates.
   Do NOT use subheadings for each domain — weave them together chronologically.
3. USE EXACT DATE WINDOWS from the TEMPORAL STORM WINDOWS block. Write "Jun 28–Aug 11, 2026" not "summer."
4. TECHNIQUE ATTRIBUTION: "Jupiter transit conjunct natal Sun (exact Jun 28, orb 0.12°) + Tajaka Saturn year"
5. SYSTEM CONVERGENCE FORMAT within the prose:
   — State the date window inline
   — Name which techniques agree
   — Give the meaning
   — Give the concrete action
6. STATE DIVERGENCES when systems disagree — name both, say which to weight and why.
7. THEMATIC TITLE: Begin with **{YEAR}: [Evocative 3–5 word title for this year's energy]**
8. END with: "**The one action {YEAR} demands:** [specific, dated, technical instruction]"
9. BANNED WORDS: journey, tapestry, dance, potential, manifestation, weave.
10. LENGTH: 580-640 words.
11. START with: # YEAR {YEAR}
12. Bold key terms: **Primary Direction**, **Maha Dasha**, **Liu Nian**, **Tajaka**, **Kakshya**"""

CURRENT_CONFIG_PROMPT = """You are the Archon, writing a brief weather briefing for a premium astrological dossier.

Write THE CURRENT CONFIGURATION — 3 tight paragraphs, total 130-160 words.

RULES:
1. Paragraph 1: Active Maha Dasha + Antardasha (name the lord, years remaining, what it strips or builds).
2. Paragraph 2: Current annual profection + time lord (name the activated house, what it emphasizes).
3. Paragraph 3: The single most dominant outer transit in effect RIGHT NOW.
4. Final sentence: The one question this year is asking the native. Specific to this chart.
5. START with: # ◈ THE CURRENT CONFIGURATION
6. NO jargon explanations. Assume the reader knows what a dasha is."""

DIRECTIVE_PROMPT = """You are the Archon, closing a premium astrological dossier with the mandate.

ABSOLUTE RULES:
1. Section 1 — THE RED THREAD: Exactly one sentence. Must name the Sun/Moon/Asc combination.
   Must name the core paradox. Could ONLY be written about this exact chart. No vague spiritual language.
   Format: **Red Thread:** [sentence]

2. Section 2 — THE FIVE-YEAR ORDERS: Five dated, concrete, technical actions.
   One per year. Format:
   **2026:** [Action — name the technique, the exact window, the specific practice]
   **2027:** [Action]
   **2028:** [Action]
   **2029:** [Action]
   **2030:** [Action]

3. NO padding. NO encouragement. NO "remember that..." NO "trust yourself."
   Only the mandate. Reads like orders, not suggestions.

4. LENGTH: 280-340 words.
5. START with: # ◈ THE FIVE-YEAR DIRECTIVE"""

WARNING_PROMPT = """You are the Archon, writing the final warning of a premium astrological dossier.

Write THE WARNING — 180-220 words.

RULES:
1. ONE configuration only. The specific planetary setup creating the greatest risk for this chart.
2. State: which planets, which aspect, when it peaks (exact date window from TEMPORAL STORM WINDOWS).
3. State: what it destroys if the native ignores it.
4. State: what it builds if the native uses it correctly.
5. NO softening. NO "this could be challenging." NO generic risk language.
   Only what is specific to this chart and this period.
6. If it has already peaked, say when it peaked and what it was.
7. START with: # ◈ THE WARNING
8. LENGTH: 180-220 words. No more."""


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


def _format_clusters(temporal_clusters: list) -> str:
    """
    Format ALL temporal storm windows into a dense prose block.
    Used for the predictive data block (context). Prose format prevents raw
    data echoing — the LLM reads it as reference material, not template text.
    """
    if not temporal_clusters:
        return ""
    lines = ["=== TEMPORAL STORM WINDOWS — USE EXACT DATES IN PROSE ==="]
    lines.append("Each entry = a convergence of multiple predictive systems. "
                 "Cite the date range naturally in your writing. Never echo this table verbatim.")
    for i, cluster in enumerate(temporal_clusters[:14], 1):
        start  = _jd_to_str(cluster.get("start_jd", 0))
        end    = _jd_to_str(cluster.get("end_jd",   0))
        intens = cluster.get("intensity", 0)
        evts   = cluster.get("events", [])
        # Summarise events as a single readable sentence
        evt_summary = "; ".join(
            f"{ev.get('technique','?')} ({ev.get('system','?')})"
            for ev in evts[:4]
        )
        lines.append(f"  [{i}] {start}–{end} | {intens} systems | {evt_summary}")
    lines.append("=== END STORM WINDOWS ===")
    return "\n".join(lines)


def _format_clusters_for_year(temporal_clusters: list, year: int) -> str:
    """
    Extract only the storm windows that fall within the target year.
    Much tighter injection — prevents other years' data from bleeding in.
    """
    if not temporal_clusters:
        return ""

    year_clusters = []
    for c in temporal_clusters:
        # Convert JD to calendar year check
        start_str = _jd_to_str(c.get("start_jd", 0))
        end_str   = _jd_to_str(c.get("end_jd",   0))
        if str(year) in start_str or str(year) in end_str:
            year_clusters.append(c)

    if not year_clusters:
        return f"No multi-system convergences identified for {year}."

    lines = [f"=== {year} STORM WINDOWS (multi-system convergences) ==="]
    for i, c in enumerate(year_clusters, 1):
        start  = _jd_to_str(c.get("start_jd", 0))
        end    = _jd_to_str(c.get("end_jd",   0))
        intens = c.get("intensity", 0)
        evts   = c.get("events", [])
        evt_lines = [f"{ev.get('technique','?')} ({ev.get('system','?')}): {ev.get('description','')}"
                     for ev in evts[:5]]
        lines.append(f"  Window {i}: {start} → {end}  [{intens} systems converge]")
        for el in evt_lines:
            lines.append(f"    • {el}")
    lines.append(f"INSTRUCTION: Weave these windows chronologically into your {year} prose. "
                 f"Do NOT reproduce this table. Cite dates naturally: 'In July {year}...' ")
    return "\n".join(lines)


# ─────────────────────────────────────────────────────────────────────────────
# Rule querier (optional Neo4j dependency)
# ─────────────────────────────────────────────────────────────────────────────
_rule_querier = None
try:
    from synthesis.rule_querier import RuleQuerier
    _rule_querier = RuleQuerier()
except Exception:
    pass


# ─────────────────────────────────────────────────────────────────────────────
# Archon
# ─────────────────────────────────────────────────────────────────────────────

class Archon:
    """Master narrative architect for the 13-Section Celestial Dossier."""

    # ── Model selection per section type ─────────────────────────────────────
    # Override in config.py/settings if desired.
    MODEL_MAP = {
        "oracle":       getattr(settings, "archon_model",       "gpt-4o"),
        "natal":        getattr(settings, "archon_model",       "gpt-4o"),
        "current":      getattr(settings, "archon_model",       "gpt-4o"),
        "year_forecast":getattr(settings, "archon_model",       "gpt-4o"),
        "directive":    getattr(settings, "archon_model",       "gpt-4o"),
    }

    TEMP_MAP = {
        "oracle":        0.82,   # slightly warmer — hook writing
        "natal":         0.70,   # precise diagnosis
        "current":       0.60,   # factual briefing
        "year_forecast": 0.68,   # precise + vivid
        "directive":     0.55,   # crisp orders
    }

    # gemini-2.5-pro counts thinking tokens against max_output_tokens.
    # At reasoning_effort="low": ~300-500 thinking tokens consumed.
    # Budget = (prose_words × 1.5 tokens/word) + 800 thinking buffer.
    MAX_TOKENS_MAP = {
        "oracle":        3500,   # target ~420w prose
        "natal":         6000,   # target ~720w prose
        "current":       2000,   # target ~150w prose
        "year_forecast": 5500,   # target ~620w prose
        "directive":     3200,   # target ~310w prose
    }

    # Keep thinking minimal for creative writing — output tokens matter more than reasoning depth
    ARCHON_REASONING_EFFORT = "low"

    def generate_report(self,
                        arbiter_synthesis: dict,
                        chart_data: dict,
                        metadata: dict,
                        temporal_clusters: list = None) -> str:
        """
        Generate the 13-Section Celestial Dossier.
        """
        ref           = self._extract_reference_positions(chart_data)
        cluster_block = _format_clusters(temporal_clusters or [])

        header   = self._generate_header(metadata, chart_data, ref)
        sections = []
        total    = len(SECTION_DEFS)

        for sec_num in sorted(SECTION_DEFS.keys()):
            sd = SECTION_DEFS[sec_num]
            print(f"   [Archon] Generating section {sec_num + 1}/{total}: {sd['title']}...")

            prompt = self._build_section_prompt(
                sec_num, sd, arbiter_synthesis, chart_data, ref,
                cluster_block, temporal_clusters_raw=temporal_clusters or []
            )
            sys_prompt = self._get_system_prompt(sd)

            response = gateway.generate(
                system_prompt    = sys_prompt,
                user_prompt      = prompt,
                model            = self.MODEL_MAP.get(sd["type"], settings.archon_model),
                max_tokens       = self.MAX_TOKENS_MAP.get(sd["type"], 5000),
                temperature      = self.TEMP_MAP.get(sd["type"], 0.70),
                reasoning_effort = self.ARCHON_REASONING_EFFORT,
            )

            if response.get("success"):
                content = response["content"]
                content = self._enforce_section_header(content, sd)
                content = self._validate_degrees_internal(content, ref, sec_num)
                sections.append(content)
            else:
                err = response.get("error", "Unknown error")
                sections.append(
                    f"\n\n# {sd['header']}\n\n**[Generation Failed: {err}]**\n\n"
                )
                logger.error(f"Section {sec_num} ({sd['id']}) failed: {err}")

        # ── Assemble with part dividers ────────────────────────────────────
        full_report = header
        part_labels = {
            "I":   "\n\n---\n\n# PART I: THE NATIVITY\n\n---\n\n",
            "II":  "\n\n---\n\n# PART II: THE FIVE-YEAR ALMANAC\n\n---\n\n",
            "III": "\n\n---\n\n# PART III: THE DIRECTIVE\n\n---\n\n",
        }
        current_part = None
        for sec_num, content in zip(sorted(SECTION_DEFS.keys()), sections):
            sd   = SECTION_DEFS[sec_num]
            part = sd["part"]
            if part != current_part:
                full_report += part_labels[part]
                current_part = part
            full_report += content + "\n\n"

        full_report += (
            "\n\n---\n\n"
            "*All planetary positions verified against Swiss Ephemeris. "
            "Primary Direction arcs calculated via Regiomontanus method. "
            "Parans computed using RAMC horizon-crossing method (Brady 1998).*"
        )

        return full_report

    # ─────────────────────────────────────────────────────────────────────────
    # System Prompt Selector
    # ─────────────────────────────────────────────────────────────────────────

    def _get_system_prompt(self, sd: dict) -> str:
        t = sd["type"]
        header = sd["header"]
        if t == "oracle":
            return ORACLE_PROMPT
        elif t == "natal":
            return NATAL_PROMPT.replace("{HEADER}", header)
        elif t == "current":
            return CURRENT_CONFIG_PROMPT
        elif t == "year_forecast":
            year = str(sd.get("target_year", ""))
            return YEAR_FORECAST_PROMPT.replace("{YEAR}", year).replace("{YEAR}", year)
        elif t == "directive":
            if sd["id"] == "warning":
                return WARNING_PROMPT
            return DIRECTIVE_PROMPT
        return NATAL_PROMPT.replace("{HEADER}", header)

    # ─────────────────────────────────────────────────────────────────────────
    # Section Prompt Builder
    # ─────────────────────────────────────────────────────────────────────────

    def _build_section_prompt(self, sec_num: int, sd: dict,
                               synthesis: dict, chart_data: dict,
                               ref: dict, cluster_block: str,
                               temporal_clusters_raw: list = None) -> str:
        is_predictive = sd["type"] in ("year_forecast", "current", "directive")

        if is_predictive:
            data_block = self._build_predictive_block(ref, chart_data)
        else:
            data_block = self._build_natal_block(ref)

        synth_str    = json.dumps(synthesis, default=str)
        synth_trunc  = synth_str[:1800] if len(synth_str) > 1800 else synth_str

        extra        = self._section_specific_data(sec_num, sd, chart_data, ref, synthesis)

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

        return f"""{data_block}

=== SECTION FOCUS ===
Section: {sd['title']}
Focus: {sd['focus']}
Key domains: {', '.join(sd['domains']) if sd['domains'] else 'See focus above'}

=== SYNTHESIS DATA ===
{synth_trunc}
{graph_section}{cluster_section}
=== SECTION-SPECIFIC DATA ===
{extra}

Write: {sd['title']}
Requirements:
- Start with exactly: # {sd['header']}
- Length: {min_w}–{max_w} words
- {'Use DMS positions from MANDATORY NATAL DATA' if not is_predictive else 'Use exact date windows from TEMPORAL STORM WINDOWS'}
- State system conflicts explicitly
- Every claim must reference specific planetary evidence"""

    # ─────────────────────────────────────────────────────────────────────────
    # Section-specific data injections
    # ─────────────────────────────────────────────────────────────────────────

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
            return (
                f"Tightest aspects: {json.dumps(tight, default=str)}\n"
                f"Yogas: {json.dumps(v_natal.get('yogas', [])[:3], default=str)}\n"
                f"Chart pattern: {json.dumps(ref.get('_patterns_summary', {}), default=str)}\n"
                f"True Parans (RAMC method): {json.dumps(parans, default=str)}\n"
                f"Fixed Star contacts: {json.dumps(stars, default=str)}\n"
                f"Dodecatemoria dominant: {ref.get('_dodec_dominant_sign')} "
                f"(ruler {ref.get('_dodec_dominant_ruler')})\n"
                f"Pre-natal syzygy: {ref.get('_syzygy_type')} in {ref.get('_syzygy_sign')}, "
                f"{ref.get('_syzygy_days_before')} days before birth"
            )

        # ── Material World ────────────────────────────────────────────────────
        elif sid == "material_world":
            houses = w_natal.get("houses", {})
            lots   = w_natal.get("lots",   {})
            dirs   = chart_data.get("western", {}).get("predictive", {}).get(
                        "primary_directions", {}).get("career", [])[:3]
            return (
                f"House 2: {json.dumps(houses.get('House_2', {}), default=str)}\n"
                f"House 10: {json.dumps(houses.get('House_10', {}), default=str)}\n"
                f"Lots: {json.dumps(lots, default=str)}\n"
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
            return (
                f"Descendant: {json.dumps(desc, default=str)}\n"
                f"House 6: {json.dumps(w_natal.get('houses', {}).get('House_6', {}), default=str)}\n"
                f"House 7: {json.dumps(w_natal.get('houses', {}).get('House_7', {}), default=str)}\n"
                f"Venus dignities: {json.dumps(venus_dig, default=str)}\n"
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
            kakshya = chart_data.get("vedic", {}).get("predictive", {}).get(
                        "kakshya_transits", {}).get(str(year), {})
            outer   = w_pred.get("outer_transit_aspects", {}).get("by_year", {}).get(str(year), [])
            lr      = [l for l in w_pred.get("lunar_returns", [])
                       if str(l.get("year", "")) == str(year)][:2]
            return (
                f"YEAR: {year}\n"
                f"Profection {year}: {json.dumps(prof_yr, default=str)}\n"
                f"Tajaka {year}: {json.dumps(taj_yr, default=str)}\n"
                f"Liu Nian {year}: {json.dumps(liu, default=str)}\n"
                f"Vimshottari active: Maha {dasha.get('maha_lord','?')} / "
                f"Antar {dasha.get('antar_lord','?')} "
                f"({dasha.get('antar_remaining_years','?')} yrs left)\n"
                f"Kakshya {year}: {json.dumps(kakshya, default=str)}\n"
                f"Outer transit aspects {year}: {json.dumps(outer[:8], default=str)}\n"
                f"Lunar returns sample: {json.dumps(lr, default=str)}"
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
            return (
                f"Consensus points: {json.dumps(synth.get('consensus_points', [])[:5], default=str)}\n"
                f"Unified narrative: {synth.get('unified_narrative', '')}\n"
                f"Key contradictions: {json.dumps(synth.get('contradictions', [])[:3], default=str)}\n"
                f"Primary Directions: {json.dumps(all_dirs[:4], default=str)}\n"
                f"Peak risk window: {json.dumps(synth.get('critical_periods', [{}])[0], default=str)}"
            )

        return ""

    # ─────────────────────────────────────────────────────────────────────────
    # Mandatory data blocks (preserved from v1 + parans upgrade)
    # ─────────────────────────────────────────────────────────────────────────

    def _build_natal_block(self, ref: dict) -> str:
        lines = ["=== MANDATORY NATAL DATA — USE THESE EXACT VALUES ==="]
        lines.append("FORMAT: DEGREES° ARCMINUTES' SIGN  (e.g., '19° 43' Cancer')")
        lines.append("")

        ZODIAC = ["Aries","Taurus","Gemini","Cancer","Leo","Virgo",
                  "Libra","Scorpio","Sagittarius","Capricorn","Aquarius","Pisces"]
        planet_order = ["Sun","Moon","Mercury","Venus","Mars","Jupiter","Saturn",
                        "Uranus","Neptune","Pluto","North Node","South Node",
                        "Chiron","Ascendant","Midheaven","Descendant","IC"]

        lines.append("--- PLANETARY POSITIONS ---")
        for planet in planet_order:
            data = ref.get(planet)
            if data and isinstance(data, dict):
                lines.append(f"{planet}: {data['dms']} {data['sign']}  (lon: {data['longitude']:.4f}°)")

        lines.append("")
        lines.append("--- ESSENTIAL CHART FACTORS ---")
        lines.append(f"Chart sect: {'Day chart' if ref.get('_is_day_chart') else 'Night chart'}")
        lines.append(f"Hyleg: {ref.get('_hyleg', 'Unknown')}")
        lines.append(f"Almuten: {ref.get('_almuten', 'Unknown')}")
        lines.append(f"Most dignified planet: {ref.get('_most_dignified', 'Unknown')} (score {ref.get('_most_dignified_score', 'N/A')})")
        lines.append(f"Dominant chart pattern: {ref.get('_dominant_pattern', 'None')}")
        lines.append("")
        lines.append("--- HELLENISTIC LOTS ---")
        lines.append(f"Lot of Fortune: {ref.get('_lot_fortune_sign', '?')} {ref.get('_lot_fortune_deg', '?')}")
        lines.append(f"Lot of Spirit:  {ref.get('_lot_spirit_sign', '?')}")
        lines.append("")
        lines.append("--- VEDIC FACTORS ---")
        lines.append(f"Atmakaraka:    {ref.get('_vedic_ak', 'Unknown')}")
        lines.append(f"Amatyakaraka:  {ref.get('_vedic_amatyakaraka', 'Unknown')}")
        lines.append(f"Darakaraka:    {ref.get('_vedic_darakaraka', 'Unknown')}")
        lines.append(f"Moon Nakshatra: {ref.get('_moon_nakshatra', 'Unknown')} pada {ref.get('_moon_pada', '?')}")
        lines.append("")
        lines.append("--- SAJU (BAZI) ---")
        if ref.get("_saju_available"):
            for pillar in ["Year", "Month", "Day", "Hour"]:
                val = ref.get(f"_saju_{pillar}", "?")
                lines.append(f"{pillar} Pillar: {val}")
            lines.append(f"Day Master: {ref.get('_dm_stem')} {ref.get('_dm_element')} — {ref.get('_dm_tier')}")
            lines.append(f"Useful God: {ref.get('_useful_god', '?')}")
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
        w_pred    = chart_data.get("western", {}).get("predictive", {})
        profecs   = w_pred.get("profections_timeline", [])
        transits  = w_pred.get("transits_timeline", [])
        sr        = w_pred.get("solar_returns", [])[:5]
        sr_brief  = [{"year": s.get("year"), "asc": s.get("ascendant"),
                      "dom_house": s.get("dominant_house")} for s in sr]
        tajaka    = chart_data.get("vedic", {}).get("predictive", {}).get("tajaka", [])[:5]
        liu_nian  = chart_data.get("bazi", {}).get("predictive", {}).get("liu_nian_timeline", [])
        da_yun    = chart_data.get("bazi", {}).get("predictive", {}).get("da_yun", {})
        zr        = chart_data.get("hellenistic", {}).get("zodiacal_releasing", {})
        outer     = w_pred.get("outer_transit_aspects", {})

        lines = ["=== PREDICTIVE DATA BLOCK (Almanac sections) ==="]
        lines.append("Do not re-diagnose the natal chart. Use natal positions only as brief anchors.")
        lines.append("")
        lines.append("--- NATAL ANCHORS (reference only) ---")
        for p in ["Sun", "Moon", "Ascendant", "Midheaven", "Saturn"]:
            if p in ref:
                d = ref[p]
                lines.append(f"{p}: {d.get('dms','?')} {d.get('sign','?')}")
        lines.append("")
        lines.append("--- ACTIVE TIME LORDS ---")
        lines.append(f"Maha Dasha: {ref.get('_maha_dasha')} ({ref.get('_dasha_years_left')} yrs remaining)")
        lines.append(f"Antardasha: {ref.get('_antar_dasha')} ({ref.get('_antar_dasha_years')} yrs remaining)")
        lines.append(f"Current Profection: {ref.get('_profection_sign')} "
                     f"(House {ref.get('_profection_house')}, Time Lord: {ref.get('_time_lord')})")
        if ref.get("_saju_available") and ref.get("_current_da_yun"):
            cyun = ref["_current_da_yun"]
            lines.append(f"Current Da Yun: {cyun.get('stem','?')}{cyun.get('branch','?')} "
                         f"({cyun.get('stem_element','?')}/{cyun.get('branch_element','?')}, "
                         f"age {cyun.get('start_age','?')}–{cyun.get('end_age','?')})")
        lines.append("")
        lines.append("--- PROFECTIONS 2026-2030 ---")
        lines.append(json.dumps(profecs, default=str, indent=None))
        lines.append("")
        lines.append("--- OUTER PLANET TRANSIT ASPECT HITS (exact dates) ---")
        if outer.get("summary_block"):
            lines.append(outer["summary_block"])
        else:
            lines.append(json.dumps(transits, default=str, indent=None))
        lines.append("")
        lines.append("--- SOLAR RETURNS ---")
        lines.append(json.dumps(sr_brief, default=str))
        lines.append("")
        lines.append("--- TAJAKA (VEDIC ANNUAL) ---")
        lines.append(json.dumps(tajaka, default=str, indent=None))
        lines.append("")
        lines.append("--- LIU NIAN (SAJU ANNUAL) ---")
        lines.append(json.dumps(liu_nian[:5], default=str, indent=None))
        lines.append("")
        lines.append("--- DA YUN CURRENT ---")
        lines.append(json.dumps(ref.get("_liu_nian", []), default=str, indent=None))
        lines.append("")
        lines.append("--- KAKSHYA TRANSITS ---")
        kakshya = chart_data.get("vedic", {}).get("predictive", {}).get("kakshya_transits", {})
        lines.append(json.dumps(kakshya, default=str, indent=None)[:1500])
        lines.append("")
        lines.append("--- PRIMARY DIRECTIONS (Key) ---")
        pd = chart_data.get("western", {}).get("predictive", {}).get("primary_directions", {})
        all_dirs = []
        for cat in pd.values():
            if isinstance(cat, list):
                all_dirs.extend(cat[:2])
        lines.append(json.dumps(all_dirs[:6], default=str, indent=None))

        return "\n".join(lines)

    # ─────────────────────────────────────────────────────────────────────────
    # Reference Position Extractor (preserved from v1)
    # ─────────────────────────────────────────────────────────────────────────

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
        ref["_liu_nian"] = liu_nian[:5]

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
        sig = f"{sun_sign} Sun · {moon_sign} Moon · {asc_sign} Ascendant" if all([sun_sign, moon_sign, asc_sign]) else ""

        return f"""# THE CELESTIAL DOSSIER
## {name}

{f'*{sig}*' if sig else ''}

**Prepared:** {timestamp}  
**Birth:** {bt} · {loc}  
**Systems:** Western Tropical · Vedic Sidereal · Saju (Bazi) · Hellenistic  
**Methods:** Primary Directions (Regiomontanus) · Vimshottari Dasha · Annual Profections · Tajaka · Kakshya · True RAMC Parans

---

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

    def _validate_degrees_internal(self, content: str, ref: dict, sec_num: int) -> str:
        """
        Find and FIX degree hallucinations in natal/oracle sections.
        Replaces wrong degree strings with the verified value from the ref dict.
        Returns corrected content.

        Strategy: if LLM writes "12° 33' Leo" but ref shows Sun at 27° 10' Leo,
        and no other planet is in Leo, we replace the wrong value with the correct one.
        Only corrects when match is unambiguous (exactly one planet in that sign).
        """
        sd = SECTION_DEFS.get(sec_num, {})
        if sd.get("type") not in ("natal", "oracle"):
            return content

        # Build sign → [(planet, degree, dms)] lookup
        sign_to_planets: dict = {}
        for planet, data in ref.items():
            if not isinstance(data, dict):
                continue
            sign = data.get("sign", "")
            if not sign:
                continue
            sign_to_planets.setdefault(sign, []).append({
                "planet":  planet,
                "degree":  data.get("degree", 0),
                "dms":     data.get("dms", _deg_to_dms(data.get("degree", 0))),
            })

        pattern = r'(\d{1,2})°\s*(\d{2})\'?\s*([A-Z][a-z]+)'
        corrections = 0

        def _replace_match(m: re.Match) -> str:
            nonlocal corrections
            claimed_d    = int(m.group(1))
            claimed_m    = int(m.group(2))
            claimed_sign = m.group(3)
            claimed_dec  = claimed_d + claimed_m / 60.0
            original     = m.group(0)

            planets_in_sign = sign_to_planets.get(claimed_sign, [])
            if not planets_in_sign:
                return original  # Unknown sign label — leave it

            if len(planets_in_sign) == 1:
                # Unambiguous: exactly one body in this sign
                truth = planets_in_sign[0]
                delta = abs(claimed_dec - truth["degree"])
                if delta > 1.0:
                    correct_str = f"{truth['dms']}' {claimed_sign}"
                    logger.info(
                        f"Sec{sec_num} DEGREE FIX: {original} → {correct_str} "
                        f"({truth['planet']}, delta {delta:.2f}°)"
                    )
                    corrections += 1
                    return correct_str
            else:
                # Multiple planets in same sign — find closest match
                best = min(planets_in_sign, key=lambda p: abs(p["degree"] - claimed_dec))
                delta = abs(claimed_dec - best["degree"])
                if delta > 2.0:  # Higher threshold when ambiguous
                    correct_str = f"{best['dms']}' {claimed_sign}"
                    logger.info(
                        f"Sec{sec_num} DEGREE FIX (ambiguous): {original} → {correct_str} "
                        f"(best match {best['planet']}, delta {delta:.2f}°)"
                    )
                    corrections += 1
                    return correct_str

            return original

        corrected = re.sub(pattern, _replace_match, content)
        if corrections:
            logger.info(f"Sec{sec_num}: corrected {corrections} hallucinated degree(s)")
        return corrected
