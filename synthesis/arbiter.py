"""The Arbiter - Reconciles contradictions between systems.
v2.2:
  - Expert truncation raised to 4500 chars each
  - Temporal clusters and convergences now passed as actual data (not just counts)
  - Schema enriched: section_steers, top_predictions, key_planets
  - unified_narrative requirement raised to 600+ words
  - archon.py synth_trunc fix coordinated: Arbiter output structured for targeted extraction
"""
import logging
from experts.gateway import gateway
from config import settings
from typing import Dict, List, Any
import json

logger = logging.getLogger(__name__)


class Arbiter:
    """First-level synthesis: resolves conflicts between 4 experts."""

    SYSTEM_PROMPT = """You are the Arbiter, a meta-astrologer who synthesises Western (Tropical), Vedic (Sidereal), Saju (Bazi), and Hellenistic analyses into a coherent whole.

SYNTHESIS PROTOCOL:
1. CONSENSUS DETECTION: Identify where 2+ systems agree on timing, themes, or outcomes. Amplify these — cross-system agreement = high-confidence prediction.
2. CONTRADICTION HANDLING: Analyse the nature of disagreement:
   - Different metaphors pointing to same reality (synthesise into unified insight)
   - Genuine tension (note the paradox; weight by technique authority)
   - Different timing windows (both valid — state "Western transits suggest X by [date], Vedic Dasha ripens Y by [date]")
3. EMERGENT PATTERNS: Find patterns visible ONLY across all four systems (cross-system Almuten, dual testimony on same house, etc.)
4. CONFIDENCE SCORING: 0-100 based on: technique weight × number of agreeing systems × thematic coherence
5. QUESTION STEERING: Weight synthesis toward user's questions where chart supports it
6. SEVERITY FLAGGING: When 3+ systems flag the same vulnerability window, mark as HIGH ALERT with exact dates
7. STORM WINDOW INTEGRATION: The temporal_storm_windows below are algorithmically computed multi-system convergences — treat high-convergence windows as the highest-authority timing data in your synthesis
8. TRANSIT PRECISION: The Western analysis contains exact outer-planet transit entry/exit dates from a daily ephemeris scan. For every transit you mention in top_predictions or critical_periods, extract its exact entry date and exit date. Never say "late 2027" when you have "entry:2027-01-22 exit:2027-05-08" in the data.
9. BONIFICATION INTEGRATION: The Hellenistic analysis includes bonification (benefic reception) and maltreatment (out-of-sect malefic stress) data. A planet that is maltreated AND under hard transit from the same malefic = double-flagged — include in critical_periods with elevated intensity. A planet that is bonified AND under a benefic transit = elevated opportunity — include in top_predictions.

CROSS-SYSTEM MAPPINGS (use these to unify language):
- Western Sun ~= Vedic Sun ~= Saju Day Master (core identity/vitality)
- Western Moon ~= Vedic Moon (emotions, mind, mother, public)
- Western Ascendant ~= Vedic Lagna ~= Saju Day Pillar (body, self-expression)
- Western Saturn transit ~= Vedic Sade Sati / Saturn Dasha ~= Saju challenging luck pillar
- Western Solar Arc direction ~= Vedic Secondary Progression ~= Saju Da Yun (developmental timing)
- Hellenistic Time Lord ~= Vedic Dasha lord ~= Saju current Da Yun stem (annual ruler)
- Western Jupiter transit ~= Vedic Jupiter Dasha ~= Saju favorable Wu Xing (expansion timing)

SHADBALA GATE RULE:
- If a planet's Shadbala is SEVERELY WEAKENED (below minimum Rupas) AND no cancellation yoga (Neecha Bhanga Raja Yoga, debilitation cancellation) is present in the Vedic data, any prediction primarily driven by that planet MUST be downgraded by one confidence tier. State the weakness explicitly: "Mars is severely weakened in Shadbala; this career prediction requires conscious effort and external support."
- Do NOT predict "near-certain" outcomes from severely weakened planets without explicit cancellation justification.

SYNTHESIS DEPTH REQUIREMENTS:
- Every consensus_point MUST cite specific system evidence with dates where available
- critical_periods MUST have ISO date ranges, not vague year references
- unified_narrative: 600+ words; write as if advising an intelligent client — specific, actionable, names exact dates, no generic astrology platitudes
- section_steers: for each major report section, write a 1-2 sentence directive telling the writer what the synthesis reveals that section should emphasise. Keys must be: architecture_of_self, inner_world, material_world, soul_contract, directive
- top_predictions: 4-6 highest-confidence future events/periods with ISO dates and cross-system evidence
- contradictions: resolve WHERE POSSIBLE by weighting higher-authority technique; flag unresolvable ones honestly
- key_planets: list the 3-5 most activated or significant planets in this chart based on cross-system synthesis

OUTPUT FORMAT: Strict JSON only. No markdown. No preamble."""

    def reconcile(self, analyses: List[Dict], chart_data: Dict,
                  convergences: List[Dict] = None,
                  contradictions: List[Dict] = None,
                  temporal_clusters: List[Dict] = None,
                  user_questions: list = None) -> Dict[str, Any]:
        """Reconcile four expert analyses."""
        prompt = self._build_prompt(
            analyses, chart_data, convergences, contradictions,
            temporal_clusters, user_questions
        )

        schema = {
            "type": "object",
            "properties": {
                "executive_summary": {"type": "string"},
                "key_planets": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "3-5 most activated/significant planets per cross-system synthesis"
                },
                "consensus_points": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "theme":           {"type": "string"},
                            "systems_agreeing":{"type": "array", "items": {"type": "string"}},
                            "confidence":      {"type": "number"},
                            "description":     {"type": "string"}
                        }
                    }
                },
                "contradictions": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "systems":    {"type": "array", "items": {"type": "string"}},
                            "tension":    {"type": "string"},
                            "resolution": {"type": "string"},
                            "navigate_by":{"type": "string"}
                        }
                    }
                },
                "critical_periods": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "period":           {"type": "string"},
                            "systems_agreeing": {"type": "array", "items": {"type": "string"}},
                            "intensity":        {"type": "number"},
                            "meaning":          {"type": "string"},
                            "action":           {"type": "string"}
                        }
                    }
                },
                "top_predictions": {
                    "type": "array",
                    "description": "4-6 highest-confidence future predictions with specific ISO dates",
                    "items": {
                        "type": "object",
                        "properties": {
                            "prediction":   {"type": "string"},
                            "date_range":   {"type": "string"},
                            "confidence":   {"type": "number"},
                            "systems":      {"type": "array", "items": {"type": "string"}},
                            "evidence":     {"type": "string"}
                        }
                    }
                },
                "section_steers": {
                    "type": "object",
                    "description": "Per-section narrative steering for the report writer",
                    "properties": {
                        "architecture_of_self": {"type": "string"},
                        "inner_world":          {"type": "string"},
                        "material_world":       {"type": "string"},
                        "soul_contract":        {"type": "string"},
                        "directive":            {"type": "string"}
                    }
                },
                "system_tensions":  {"type": "array", "items": {"type": "string"}},
                "unified_narrative":{"type": "string"}
            },
            "required": [
                "executive_summary", "consensus_points", "critical_periods",
                "unified_narrative", "section_steers", "top_predictions"
            ]
        }

        response = gateway.structured_generate(
            system_prompt=self.SYSTEM_PROMPT,
            user_prompt=prompt,
            output_schema=schema,
            model=settings.arbiter_model,
            temperature=0.0,
            reasoning_effort="high",
            max_tokens=8000
        )

        if response.get("success") and response.get("data"):
            result = response["data"]
            # Pass raw convergences/contradictions through so Archon can use them directly
            result["convergences"]        = convergences     or []
            result["contradictions_raw"]  = contradictions   or []
            result["temporal_clusters"]   = temporal_clusters or []
            return result
        else:
            logger.error(f"Arbiter synthesis failed: {response.get('error', 'Unknown error')}")
            return self._fallback_reconciliation(analyses, convergences, contradictions)

    def _build_prompt(self, analyses: List[Dict], chart_data: Dict,
                      convergences: List[Dict] = None,
                      contradictions: List[Dict] = None,
                      temporal_clusters: List[Dict] = None,
                      user_questions: list = None) -> str:
        """Build reconciliation prompt.
        Expert truncation: 4500 chars each.
        Temporal clusters and convergences passed as actual structured data.
        """

        def _extract_timing_dates(text: str) -> str:
            """Regex-extract date patterns from expert text before truncation.
            Preserves the highest-value timing data that would otherwise be lost."""
            import re
            date_patterns = re.findall(
                r'(?:exact|entry|exit|from|until|peak|window)[^\n]{0,120}(?:\d{4}-\d{2}-\d{2})[^\n]{0,60}',
                text, re.IGNORECASE
            )
            if not date_patterns:
                return ""
            unique = list(dict.fromkeys(date_patterns))[:15]  # dedupe, cap at 15
            return "\n\nTIMING DATA PRESERVED:\n" + "\n".join(f"  • {d.strip()}" for d in unique)

        def truncate(text, max_len=4500):
            if not text or len(text) <= max_len:
                return text
            # Extract timing dates BEFORE truncation
            timing_block = _extract_timing_dates(text)
            # Find the last sentence boundary before max_len to avoid mid-sentence cuts
            cut = text[:max_len]
            last_period = max(cut.rfind('. '), cut.rfind('.\n'), cut.rfind('.\r'))
            if last_period > max_len * 0.8:  # only use boundary if it preserves >80%
                cut = text[:last_period + 1]
            omitted = len(text) - len(cut)
            return cut + timing_block + f"\n\n[... {omitted} chars truncated]"

        def truncate_western(text):
            # Western carries the most predictive date evidence (transit entry/exit windows,
            # progressions, solar returns) — raise its cap to preserve full timing data.
            return truncate(text, max_len=6000)

        def truncate_vedic(text):
            # Vedic carries dasha sequences, ashtakavarga scores, yogas — raise cap.
            return truncate(text, max_len=5500)

        def truncate_saju(text):
            # Saju carries elemental analysis, spirit stars, Da Yun — raise from default 4500.
            return truncate(text, max_len=5500)

        def truncate_hellenistic(text):
            # Hellenistic carries ZR L2 periods, profections, LOB windows — raise from default 4500.
            return truncate(text, max_len=5500)

        western     = next((a for a in analyses if a.get("system") == "Western"),     {})
        vedic       = next((a for a in analyses if a.get("system") == "Vedic"),        {})
        saju        = next((a for a in analyses if a.get("system") == "Saju"),         {})
        hellenistic = next((a for a in analyses if a.get("system") == "Hellenistic"), {})

        w_natal   = chart_data.get("western", {}).get("natal", {})
        sun_sign  = w_natal.get("placements", {}).get("Sun",  {}).get("sign", "Unknown")
        moon_sign = w_natal.get("placements", {}).get("Moon", {}).get("sign", "Unknown")
        asc_sign  = w_natal.get("angles",     {}).get("Ascendant", {}).get("sign", "Unknown")

        # ── Temporal storm windows — pass actual data, not just count ─────────
        cluster_block = ""
        if temporal_clusters:
            cluster_block = "\n=== TEMPORAL STORM WINDOWS (algorithmically computed multi-system convergences) ===\n"
            cluster_block += "These are the highest-authority timing data. Reference specific windows by date in your synthesis.\n"
            # Top 10 with full detail
            for i, c in enumerate(temporal_clusters[:10], 1):
                start  = c.get("start_date", c.get("start", "?"))
                end    = c.get("end_date",   c.get("end",   "?"))
                score  = c.get("convergence_score", 0)
                label  = c.get("confidence_label", "?")
                n_sys  = c.get("n_systems", 1)
                sys_l  = ", ".join(c.get("systems_involved", ["?"]))
                events = "; ".join(
                    f"{ev.get('technique','?')}/{ev.get('system','?')}"
                    for ev in c.get("events", [])[:4]
                )
                cluster_block += (
                    f"  [{i}] {start}–{end} | score={score:.2f} | {label} | "
                    f"{n_sys} systems: {sys_l}\n"
                    f"       techniques: {events}\n"
                )
            # Next 5 as one-line summaries (preserves windows without bloating prompt)
            for i, c in enumerate(temporal_clusters[10:15], 11):
                start = c.get("start_date", c.get("start", "?"))
                end   = c.get("end_date",   c.get("end",   "?"))
                score = c.get("convergence_score", 0)
                label = c.get("confidence_label", "?")
                sys_l = ", ".join(c.get("systems_involved", ["?"]))
                cluster_block += f"  [{i}] {start}–{end} | score={score:.2f} | {label} | {sys_l}\n"
            cluster_block += "=== END STORM WINDOWS ===\n"

        # ── Convergences — top items as structured data ───────────────────────
        conv_block = ""
        if convergences:
            conv_block = f"\n=== CROSS-SYSTEM CONVERGENCES ({len(convergences)} detected) ===\n"
            for cv in convergences[:6]:
                theme   = cv.get("theme", cv.get("type", "?"))
                systems = ", ".join(cv.get("systems", []))
                desc    = cv.get("description", cv.get("detail", ""))[:250]
                conv_block += f"  • {theme} [{systems}]: {desc}\n"
            conv_block += "=== END CONVERGENCES ===\n"

        # ── Contradictions — as structured data ───────────────────────────────
        contrad_block = ""
        if contradictions:
            contrad_block = f"\n=== SYSTEM CONTRADICTIONS ({len(contradictions)} flagged) ===\n"
            for ct in contradictions[:4]:
                systems = ", ".join(ct.get("systems", []))
                tension = ct.get("tension", ct.get("description", ""))[:250]
                contrad_block += f"  • [{systems}]: {tension}\n"
            contrad_block += "=== END CONTRADICTIONS ===\n"

        # ── User questions ────────────────────────────────────────────────────
        question_block = ""
        if user_questions:
            clean = [q.strip() for q in user_questions if q and q.strip()][:5]
            if clean:
                question_block = (
                    "\n=== USER QUESTIONS — WEIGHT SYNTHESIS TOWARD THESE THEMES ===\n"
                    + "\n".join(f"  Q{i+1}: {q}" for i, q in enumerate(clean))
                    + "\nEnsure critical_periods and consensus_points address these questions where chart supports it.\n"
                )

        return f"""SYNTHESISE THESE FOUR EXPERT ANALYSES INTO A UNIFIED PICTURE:

=== WESTERN (Tropical) ===
{truncate_western(western.get("analysis", "No analysis"))}

=== VEDIC (Sidereal) ===
{truncate_vedic(vedic.get("analysis", "No analysis"))}

=== SAJU (Bazi) ===
{truncate_saju(saju.get("analysis", "No analysis"))}

=== HELLENISTIC (Ancient) ===
{truncate_hellenistic(hellenistic.get("analysis", "No analysis"))}
{cluster_block}{conv_block}{contrad_block}
Chart basics: Sun {sun_sign}, Moon {moon_sign}, Asc {asc_sign}
{self._format_degradation_flags(chart_data)}{question_block}
SYNTHESIS REQUIREMENTS:
1. consensus_points: minimum 6 points. Each MUST cite specific evidence from 2+ systems with dates.
   For any transit in consensus_points, include the entry AND exit date if available from the Western analysis.
2. critical_periods: minimum 5 periods with start/end ISO dates, intensity 0-100, and action.
   REQUIRED: for each transit-based critical_period, extract the exact entry/exit window
   (e.g. "in:2026-01-22 out:2027-05-08") from the OUTER PLANET TRANSIT ASPECTS data
   in the Western analysis. These are real ephemeris windows, not estimates — use them.
3. contradictions: resolve each — state which system to weight and why (technique authority).
4. unified_narrative: 600+ words. Specific, actionable, names exact dates. No vague language.
   REQUIRED in unified_narrative: name the single highest-convergence storm window and
   state exactly what it demands from the person. Name the year's defining outer transit
   with its precise entry/exit window from the Western analysis.
5. section_steers: targeted 1-2 sentence directives for each of: architecture_of_self,
   inner_world, material_world, soul_contract, directive. These must be SPECIFIC TO THIS
   CHART — not generic section descriptions. Reference actual techniques and their findings.
6. top_predictions: 4-6 highest-confidence predictions with ISO date ranges.
   REQUIRED: each prediction must name (a) which systems agree, (b) the specific technique
   evidence (e.g. "Jupiter trine natal Sun exact Mar 14 2027, entry Jan 22 exit May 8"),
   (c) the convergence score from the storm window if applicable.
   Do NOT use vague date ranges like "late 2027" — use the exact dates from the data.
7. key_planets: 3-5 most activated planets cross-system.
8. system_tensions: note unresolvable cross-system conflicts honestly.

BONIFICATION NOTE: The Hellenistic analysis now includes bonification/maltreatment data per
planet. When the same planet is flagged as maltreated by an out-of-sect malefic AND under
a difficult transit in Western/Vedic, treat this as a HIGH-ALERT convergence.

Output valid JSON matching the required schema exactly."""

    @staticmethod
    def _format_degradation_flags(chart_data: Dict) -> str:
        """Inject system degradation warnings so the Arbiter knows which systems are missing."""
        flags = chart_data.get("degradation_flags", {})
        if not flags:
            return ""
        lines = ["\n⚠️  SYSTEM DEGRADATION — these systems returned incomplete data:"]
        for system, reason in flags.items():
            lines.append(f"  • {system}: {reason}")
        lines.append("DO NOT claim cross-system convergence involving degraded systems.\n")
        return "\n".join(lines) + "\n"

    def _fallback_reconciliation(self, analyses: List[Dict],
                                  convergences: List[Dict] = None,
                                  contradictions: List[Dict] = None) -> Dict:
        """Simple fallback if LLM fails."""
        return {
            "executive_summary":  "Multi-system chart analysis indicates significant transformation potential.",
            "key_planets":        ["Saturn", "Jupiter", "Sun"],
            "consensus_points":   [{
                "theme":            "Transformation",
                "systems_agreeing": ["Western", "Vedic", "Hellenistic"],
                "confidence":       75,
                "description":      "All systems indicate a period of change and development"
            }],
            "contradictions":     [],
            "critical_periods":   [],
            "top_predictions":    [],
            "section_steers":     {
                "architecture_of_self": "Focus on core identity themes.",
                "inner_world":          "Explore emotional and psychological patterns.",
                "material_world":       "Examine wealth and career indicators.",
                "soul_contract":        "Discuss life purpose and karmic themes.",
                "directive":            "Provide practical strategic guidance."
            },
            "system_tensions":    ["Different timing mechanisms between systems"],
            "unified_narrative":  "Multiple systems point to a significant developmental period.",
            "convergences":       convergences  or [],
            "contradictions_raw": contradictions or [],
            "temporal_clusters":  [],
        }
