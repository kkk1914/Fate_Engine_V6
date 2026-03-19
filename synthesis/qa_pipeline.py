"""Per-Question Multi-Step QA Pipeline with Agentic Self-Correction.

Replaces monolithic Q&A generation with:
  Step 1: REASON — structured JSON verdict from evidence
  Step 2: VERIFY — programmatic claim validation
  Step 3: NARRATE — final prose from verified data

ClaimExtractor unifies degree validation + date auditing into one pass.

v2.1 upgrades:
  - Accepts arbiter_context (verdict ledger + section memory) as binding constraint
  - REASON max_tokens increased 3000 → 8000 to prevent JSON truncation
  - JSON retry logic: if first attempt fails, retries with increased tokens
  - NARRATE reasoning_effort raised from "low" to "medium" for better reasoning
"""

import re
import json
import logging
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional

from experts.gateway import gateway
from config import settings

logger = logging.getLogger(__name__)


class ClaimExtractor:
    """Extracts and validates factual claims from generated text.

    Unifies the logic from Archon._validate_degrees_internal and
    Archon._audit_past_dates into a single claim-extraction pass.
    """

    # Expanded house lord detection patterns (mirrors post_validator.py)
    _HOUSE_LORD_PATTERNS = [
        # "{Planet} is the lord of your {N}th house"
        re.compile(
            r'\b(\w+)\b[,]?\s+(?:(?:is|holds\s+\w+\s+(?:\w+\s+)?as)\s+)?'
            r'(?:the\s+)?(?:lord|ruler|master|governor)\s+of\s+'
            r'(?:the\s+|your\s+)?(\d{1,2})(?:th|st|nd|rd)?\s*(?:house|bhava)',
            re.IGNORECASE
        ),
        # "the {N}th house lord {Planet}"
        re.compile(
            r'\b(?:the\s+)?(\d{1,2})(?:th|st|nd|rd)?\s*(?:house|bhava)\s+'
            r'(?:lord|ruler),?\s*(?:is\s+)?(\w+)\b',
            re.IGNORECASE
        ),
        # "{Planet} rules/governs house {N}"
        re.compile(
            r'\b(\w+)\b\s+(?:rules?|governs?)\s+'
            r'(?:the\s+)?(?:house\s+|H)?(\d{1,2})(?:th|st|nd|rd)?',
            re.IGNORECASE
        ),
    ]

    # Domain-to-house mapping for "ruler of your wealth" patterns
    _DOMAIN_HOUSE_MAP = {
        "wealth": 2, "finance": 2, "money": 2, "income": 2,
        "children": 5, "creativity": 5, "fertility": 5,
        "marriage": 7, "partnership": 7, "spouse": 7,
        "career": 10, "profession": 10,
        "health": 6, "home": 4, "property": 4,
    }

    def __init__(self, ref: dict, citation_registry: dict,
                 house_lords: Optional[Dict] = None):
        self.ref = ref
        self.registry = citation_registry
        self.today = datetime.now(timezone.utc)
        self.house_lords = house_lords or {}

    def extract_and_verify(self, text: str) -> Dict[str, Any]:
        """Extract all factual claims and verify against reference data.

        Returns:
            {
                "claims": [...],  # list of extracted claims
                "errors": [...],  # list of verified errors with corrections
                "passed": bool,   # True if no errors found
            }
        """
        claims = []
        errors = []

        # 1. Degree claims: "27° 10' Cancer" or "14°55' Capricorn"
        for m in re.finditer(r'(\d{1,2})°\s*(\d{2})\'?\s*([A-Z][a-z]+)', text):
            claimed_deg = int(m.group(1)) + int(m.group(2)) / 60.0
            claimed_sign = m.group(3)
            claim = {"type": "degree", "value": m.group(0), "sign": claimed_sign, "degree": claimed_deg}
            claims.append(claim)

            # Find matching planet in ref
            for planet, data in self.ref.items():
                if isinstance(data, dict) and data.get("sign") == claimed_sign:
                    actual_deg = data.get("degree", 0)
                    if abs(claimed_deg - actual_deg) > 3.0:
                        errors.append({
                            "type": "degree_mismatch",
                            "claimed": m.group(0),
                            "actual": f"{data.get('dms', '')}' {claimed_sign}",
                            "planet": planet,
                            "delta": abs(claimed_deg - actual_deg),
                        })

        # 2. Date claims: "2025-03-14" or "March 2025" etc
        current_year = self.today.year
        for m in re.finditer(r'\b(20\d{2})-(\d{2})-(\d{2})\b', text):
            year = int(m.group(1))
            claim = {"type": "date", "value": m.group(0), "year": year}
            claims.append(claim)
            if year < current_year:
                errors.append({
                    "type": "past_date",
                    "claimed": m.group(0),
                    "reason": f"Date is before current year {current_year}",
                })

        # 3. Confidence label claims
        for m in re.finditer(r'(NEAR-CERTAIN|HIGH-CONFIDENCE|MODERATE-CONFIDENCE|LOW-CONFIDENCE)', text):
            claims.append({"type": "confidence_label", "value": m.group(1)})

        # 4. House lord claims — expanded regex patterns
        seen_lord_claims = set()  # dedup: (planet, house)
        for pattern in self._HOUSE_LORD_PATTERNS:
            for m in pattern.finditer(text):
                g1, g2 = m.group(1), m.group(2)
                # Determine which group is planet and which is house number
                try:
                    house_num = int(g2)
                    planet = g1
                except ValueError:
                    try:
                        house_num = int(g1)
                        planet = g2
                    except ValueError:
                        continue

                if not (1 <= house_num <= 12):
                    continue

                key = (planet.lower(), house_num)
                if key in seen_lord_claims:
                    continue
                seen_lord_claims.add(key)

                claim = {"type": "house_lord", "planet": planet, "house": house_num}
                claims.append(claim)

                # Verify against computed house lords if available
                if self.house_lords:
                    vedic_lords = self.house_lords.get("vedic_lords", {})
                    western_lords = self.house_lords.get("western_lords", {})
                    correct_v = vedic_lords.get(house_num, "")
                    correct_w = western_lords.get(house_num, "")
                    planet_norm = planet.strip().title()
                    if (correct_v and correct_w
                            and planet_norm != correct_v
                            and planet_norm != correct_w):
                        errors.append({
                            "type": "house_lord_mismatch",
                            "claimed": f"{planet} rules house {house_num}",
                            "vedic_correct": correct_v,
                            "western_correct": correct_w,
                        })

        # 4b. Domain-based house lord claims: "{Planet}, ruler of your wealth"
        domain_pat = re.compile(
            r'\b(\w+)\b[,]?\s+(?:the\s+)?(?:Vedic\s+|Western\s+)?'
            r'(?:lord|ruler)\s+of\s+(?:your\s+)?(\w+)',
            re.IGNORECASE
        )
        for m in domain_pat.finditer(text):
            planet = m.group(1)
            domain = m.group(2).lower()
            house_num = self._DOMAIN_HOUSE_MAP.get(domain)
            if house_num and planet.title() in [
                "Sun", "Moon", "Mercury", "Venus", "Mars",
                "Jupiter", "Saturn", "Rahu", "Ketu",
            ]:
                claim = {"type": "house_lord", "planet": planet, "house": house_num}
                claims.append(claim)

        return {
            "claims": claims,
            "errors": errors,
            "passed": len(errors) == 0,
            "n_claims": len(claims),
            "n_errors": len(errors),
        }

    def build_correction_prompt(self, errors: list) -> str:
        """Build a correction prompt from verified errors."""
        lines = ["The following factual errors were found in your answer. Correct them:\n"]
        for err in errors:
            if err["type"] == "degree_mismatch":
                lines.append(f"- WRONG: {err['claimed']} for {err['planet']}. CORRECT: {err['actual']}")
            elif err["type"] == "past_date":
                lines.append(f"- PAST DATE: {err['claimed']} is before today. Use only future dates.")
        lines.append("\nRewrite the answer with these corrections applied. Keep all other content unchanged.")
        return "\n".join(lines)


def _scrub_scores(verdict_data: dict) -> dict:
    """Remove convergence_score from timing_windows before NARRATE.

    The NARRATE prompt must never see raw floats — it should use
    confidence labels (NEAR-CERTAIN, HIGH-CONFIDENCE, etc.) instead.
    Prevents the LLM from leaking decimal scores into prose output.
    """
    import copy
    scrubbed = copy.deepcopy(verdict_data)
    for window in scrubbed.get("timing_windows", []):
        if "convergence_score" in window:
            del window["convergence_score"]
    return scrubbed


class QAPipeline:
    """Per-question multi-step reasoning pipeline.

    For each question:
      1. REASON: Generate structured verdict from evidence
      2. VERIFY: Programmatic claim validation via ClaimExtractor
      3. NARRATE: Generate final prose (with self-correction if needed)
    """

    REASON_SCHEMA = {
        "type": "object",
        "properties": {
            "verdict": {"type": "string", "description": "Direct answer: yes/no/when/what — primary window AND secondary windows"},
            "confidence": {"type": "string", "enum": ["NEAR-CERTAIN", "HIGH-CONFIDENCE", "MODERATE-CONFIDENCE", "LOW-CONFIDENCE"]},
            "confidence_reason": {"type": "string", "description": "Why this confidence level (technique + system count)"},
            "timing_windows": {
                "type": "array",
                "description": "ALL viable timing windows across the full 15-year forecast, ranked by structural strength",
                "items": {
                    "type": "object",
                    "properties": {
                        "rank": {"type": "integer", "description": "1 = strongest structural support"},
                        "window": {"type": "string", "description": "Date range: Month Year – Month Year"},
                        "systems_converging": {"type": "integer", "description": "How many systems agree"},
                        "techniques": {"type": "array", "items": {"type": "string"}},
                        "strength_reason": {"type": "string", "description": "WHY this window is strong/weak structurally"},
                        "convergence_score": {"type": "number", "description": "0.0-1.0 from evidence block if available"}
                    }
                }
            },
            "supporting_evidence": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "source": {"type": "string"},
                        "date": {"type": "string"},
                        "value": {"type": "string"},
                        "technique_weight": {"type": "string", "description": "Gold/High/Moderate authority"}
                    }
                }
            },
            "contrary_evidence": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "source": {"type": "string"},
                        "date": {"type": "string"},
                        "value": {"type": "string"},
                        "weight": {"type": "string", "description": "How much this weakens the verdict"}
                    }
                }
            },
            "reasoning_chain": {
                "type": "string",
                "description": "Step-by-step reasoning: which technique says what, where they agree/disagree, and WHY the primary window wins over alternatives"
            },
            "key_dates": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Most important future dates for this question, across ALL windows"
            },
            "action": {"type": "string", "description": "Concrete dated action recommendation"}
        },
        "required": ["verdict", "confidence", "timing_windows", "supporting_evidence", "reasoning_chain", "key_dates", "action"]
    }

    REASON_PROMPT = """You are a senior consulting astrologer analyzing evidence to answer a specific question.
Your analysis must be thorough, expert-level, and consider the FULL 15-year forecast horizon.

═══════════════════════════════════════════════════════════════
CRITICAL: MULTI-WINDOW COMPARATIVE ANALYSIS REQUIRED
═══════════════════════════════════════════════════════════════
Do NOT rush to the nearest upcoming window. A professional astrologer surveys ALL
viable windows across the entire 15-year timeline, then weighs which has the
strongest STRUCTURAL support (most systems converging, highest-authority techniques,
best house lord conditions).

For timing questions: identify EVERY window where the relevant houses are activated
(by profection, transit, dasha, ZR phase, Da Yun, primary direction). Then RANK them
by structural strength, not chronological proximity.

The closest window is NOT automatically the best answer. A 2030 window with 4-system
convergence outweighs a 2026 window with 2-system convergence.
═══════════════════════════════════════════════════════════════

RULES:
1. verdict: Direct answer naming the PRIMARY window AND acknowledging secondary windows.
   Example: "Primary window: Oct 2026–Jan 2027 (4 systems). Secondary: Q3 2030 (3 systems)."
2. timing_windows: List ALL viable windows ranked by structural strength (not by date).
   Include convergence score, number of systems, and specific techniques for each.
3. confidence: Based on convergence data. NEAR-CERTAIN only if score >= 0.85 AND 3+ systems.
4. supporting_evidence: Name specific techniques, planets, dates. Include technique authority
   (Gold Standard = Primary Direction/Vimshottari/Solar Return, High = Profection/Solar Arc,
   Moderate = Transit/Liu Nian).
5. contrary_evidence: Name dissenting systems honestly. Explain WHY they dissent.
6. reasoning_chain: Walk through the logic step-by-step. Which technique says what?
   Where do they agree? Where do they conflict? Why does the primary window win?
   This is the most important field — it must show expert-level deductive reasoning.
7. key_dates: Future dates across ALL windows, not just the primary one.
8. action: Concrete dated action tied to the primary window.

{arbiter_constraint}

QUESTION: {question}

EVIDENCE:
{evidence}

TODAY'S DATE: {today}

Output valid JSON matching the schema. Be thorough — this is a premium consultation."""

    NARRATE_PROMPT = """You are a senior consulting astrologer — the final authority of a premium astrological dossier.
This is the section the client cares about MOST. Every answer must demonstrate deep expertise,
rigorous multi-system reasoning, and the kind of insight that justifies a premium consultation.

Convert this verified analysis into authoritative advisory prose for this specific person.

STRUCTURE — VARY your approach. Do NOT use the same structure for every answer.
Choose the format that best serves THIS specific question:

**Q: {question}**

Then write your answer using ONE of these approaches (vary across questions):
A) Lead with the TIMING if the question is "when" — open with the specific window, then
   explain why that window is strongest, then give practical guidance.
B) Lead with the STORY if the question is about life direction — weave the astrological
   logic into a narrative arc, then narrow to specific dates and actions.
C) Lead with the MECHANISM if the question is technical — explain the planetary logic first,
   then show when it activates, then give the verdict.
D) Lead with the VERDICT if the question is yes/no — state your answer in one sentence,
   then build the case with evidence, then close with practical next steps.

REQUIRED ELEMENTS (weave these in naturally, do not use rigid subheadings for every one):
- The direct verdict (which timing window, what confidence level)
- The full timing landscape (ALL viable windows, not just the nearest one)
- The astrological mechanism (WHY these techniques produce this outcome)
- Practical guidance tailored to THIS person with specific dates

When comparing timing windows, use natural language: "The 2030 window carries more weight
because four independent systems converge — including a primary direction, which is the
gold-standard technique for life-altering events."

---

VERIFIED DATA:
{verified_json}

VOICE: You are a senior consulting astrologer who has studied this chart for years.
Write as you would to a private client paying £2000 for this consultation.
Be direct, warm, authoritative — not sentimental. Every sentence must earn its place.
Personal context: GP doctor in England, Burmese Buddhist, married, wants children,
first home, multi-millionaire ambition. Make answers UK-specific where relevant.

ABSOLUTE RULES:
- NEVER output numerical scores, convergence values, or confidence percentages.
  Express certainty through prose: "strongly indicated", "the evidence overwhelmingly
  points to", "moderately supported". NOT "convergence score of 0.89".
- NEVER use absolute certainty language: "my certainty is absolute", "non-negotiable",
  "guaranteed". Always preserve space for free will.
- NEVER give specific legal, financial, or medical advice (no ownership percentages,
  contract terms, dosages). Frame as: "consult a [professional] about [topic]".
- When citing house lords, use ONLY the values from the MANDATORY HOUSE LORD REFERENCE
  if provided. Do NOT compute your own house lords.
- NEVER refer to yourself by any name or title in the output. Never use first-person
  pronouns (I, me, my) unless quoting the client. Write in authoritative advisory voice.
- FORBIDDEN OUTPUT PATTERNS: "To:", "From:", "Subject:", "Section:", "**To:**",
  letter-style headers, memo formatting, numbered action lists as main structure.
  Each answer begins with the bold question header and flows into advisory prose.

QUALITY STANDARD: Each answer should be 500-800 words. The reader should finish thinking
"this person actually understands my chart and has thought deeply about my question" —
not "this is a generic astrology answer with my dates plugged in."

CRITICAL: All dates must be AFTER {today}. Do not cite past dates."""

    def __init__(self, ref: dict, citation_registry: dict,
                 house_lords: Optional[Dict] = None):
        self.claim_extractor = ClaimExtractor(ref, citation_registry,
                                              house_lords=house_lords)
        self.today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    def _reason_with_retry(self, reason_prompt: str, question: str) -> Optional[dict]:
        """REASON step with JSON retry logic.

        If the first attempt returns truncated/invalid JSON, retries with
        increased max_tokens. This prevents the JSON decode errors that
        caused Q&A failures in previous runs.
        """
        for attempt, max_tokens in enumerate([8000, 12000], 1):
            reason_response = gateway.structured_generate(
                system_prompt="You are a precise astrological analyst producing structured verdicts.",
                user_prompt=reason_prompt,
                output_schema=self.REASON_SCHEMA,
                model=settings.archon_model,
                temperature=0.0,
                reasoning_effort="high",
                max_tokens=max_tokens,
            )

            if reason_response.get("success") and reason_response.get("data"):
                return reason_response["data"]

            error_msg = reason_response.get("error", "Unknown")
            logger.warning(
                f"QAPipeline REASON attempt {attempt} failed for: {question[:50]}... "
                f"Error: {error_msg[:100]}"
            )

            # If it's a JSON decode error (truncated output), retry with more tokens
            if "JSON" in str(error_msg) or "decode" in str(error_msg).lower():
                logger.info(f"Retrying REASON with max_tokens={12000}")
                continue
            else:
                # Non-JSON error (API error, etc.) — don't retry
                break

        return None

    def answer_question(self, question: str, evidence_block: str,
                        domain_context: str = "",
                        arbiter_context: str = "") -> str:
        """Full pipeline for one question: REASON -> VERIFY -> NARRATE.

        arbiter_context: Verdict ledger + section memory from the Arbiter.
          When provided, the REASON step must produce verdicts consistent
          with what the Arbiter and previous report sections have stated.
        """

        # Append domain context if available
        full_evidence = evidence_block
        if domain_context:
            full_evidence += f"\n\nDOMAIN CONTEXT (real-world facts):\n{domain_context}"

        # Build arbiter constraint block for the REASON prompt
        arbiter_constraint = ""
        if arbiter_context:
            arbiter_constraint = (
                "BINDING CONSTRAINT — The Arbiter and previous report sections have already "
                "established these predictions. Your verdict MUST be consistent with them. "
                "Do not contradict the Arbiter's conclusions:\n"
                f"{arbiter_context}\n"
                "If the evidence supports the Arbiter's verdict, reinforce it. "
                "If you find genuinely contrary evidence, note it but weight the "
                "multi-system Arbiter verdict higher."
            )

        # Step 1: REASON — structured verdict (with retry for JSON errors)
        reason_prompt = self.REASON_PROMPT.format(
            question=question,
            evidence=full_evidence,
            today=self.today_str,
            arbiter_constraint=arbiter_constraint,
        )

        verdict_data = self._reason_with_retry(reason_prompt, question)

        if not verdict_data:
            logger.error(f"QAPipeline REASON step failed for: {question[:50]}")
            return f"**Q: {question}**\n\n[Analysis generation failed — insufficient evidence]\n\n---"

        # Step 1b: ARBITER CONSTRAINT CHECK — verify verdict doesn't contradict Arbiter
        if arbiter_context and verdict_data:
            verdict_text = json.dumps(verdict_data).lower()
            # Check if verdict confidence wildly contradicts arbiter's established confidence
            arbiter_lower = arbiter_context.lower()
            if ("near-certain" in arbiter_lower and "low-confidence" in verdict_text):
                logger.warning(
                    f"QA verdict contradicts Arbiter (Arbiter=NEAR-CERTAIN, QA=LOW). "
                    f"Upgrading to match Arbiter for: {question[:50]}"
                )
                verdict_data["confidence"] = "HIGH-CONFIDENCE"
                verdict_data["confidence_reason"] = (
                    verdict_data.get("confidence_reason", "") +
                    " [Adjusted: multi-system Arbiter synthesis carries higher authority]"
                )

        # Step 2: VERIFY — programmatic claim checks on key_dates and evidence
        verification_text = str(verdict_data)
        verification = self.claim_extractor.extract_and_verify(verification_text)

        if not verification["passed"]:
            logger.warning(
                f"QAPipeline VERIFY found {verification['n_errors']} errors for: {question[:50]}"
            )
            # Fix past dates in verdict data
            for err in verification["errors"]:
                if err["type"] == "past_date":
                    # Remove past dates from key_dates
                    verdict_data["key_dates"] = [
                        d for d in verdict_data.get("key_dates", [])
                        if err["claimed"] not in d
                    ]

        # Step 3: NARRATE — final prose (reasoning_effort="medium" for better quality)
        # Scrub raw convergence_score floats before NARRATE to prevent decimal leakage
        narrate_data = _scrub_scores(verdict_data)
        narrate_prompt = self.NARRATE_PROMPT.format(
            question=question,
            confidence=narrate_data.get("confidence", "MODERATE-CONFIDENCE"),
            confidence_reason=narrate_data.get("confidence_reason", ""),
            verified_json=json.dumps(narrate_data, indent=2),
            today=self.today_str,
        )

        narrate_response = gateway.generate(
            system_prompt="You are a senior consulting astrologer writing the most important section of a premium dossier. Every answer must demonstrate deep expertise and multi-window comparative reasoning.",
            user_prompt=narrate_prompt,
            model=settings.archon_model,
            max_tokens=5000,
            temperature=0.30,
            reasoning_effort="high",
        )

        if narrate_response.get("success"):
            answer = narrate_response["content"]

            # Post-generation verification (iteration 2 if needed)
            final_check = self.claim_extractor.extract_and_verify(answer)
            if not final_check["passed"] and final_check["n_errors"] <= 3:
                # Apply programmatic fixes for degree mismatches
                for err in final_check["errors"]:
                    if err["type"] == "degree_mismatch":
                        answer = answer.replace(err["claimed"], err["actual"])
                logger.info(f"QAPipeline applied {final_check['n_errors']} programmatic fixes")

            return answer
        else:
            logger.error(f"QAPipeline NARRATE step failed for: {question[:50]}")
            return f"**Q: {question}**\n\n[Narrative generation failed]\n\n---"

    def answer_all(self, questions: list, evidence_blocks: dict,
                   domain_contexts: dict = None,
                   arbiter_context: str = "") -> str:
        """Answer all questions with the pipeline. Returns combined markdown.

        arbiter_context: Verdict ledger + section memory passed to each question's
          REASON step to ensure consistency with the rest of the report.
        """
        if not questions:
            return ""

        domain_contexts = domain_contexts or {}
        answers = ["# ◈ YOUR QUESTIONS ANSWERED\n"]

        for i, question in enumerate(questions):
            logger.info(f"QAPipeline: answering Q{i+1}/{len(questions)}: {question[:60]}")
            evidence = evidence_blocks.get(i, evidence_blocks.get(question, ""))
            domain_ctx = domain_contexts.get(i, domain_contexts.get(question, ""))
            answer = self.answer_question(
                question, evidence, domain_ctx,
                arbiter_context=arbiter_context,
            )
            answers.append(answer)

        return "\n\n".join(answers)
