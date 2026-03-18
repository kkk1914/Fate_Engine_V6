"""Multi-Model Ensemble for Expert Layer.

Each expert analysis runs TWO parallel interpretations:
  1. Strict  (temp=0.0, high reasoning) — maximizes data fidelity
  2. Creative (temp=0.3, medium reasoning) — maximizes interpretive insight

A lightweight judge call then selects the superior output based on:
  - Data accuracy (correct degrees, signs, dates)
  - Interpretive depth (psychological/karmic/strategic nuance)
  - Specificity (concrete predictions, not vague)
  - Completeness (all required sections present)

Cost: ~3x per expert (2 generation + 1 cheap judge), but eliminates
single-call variance and captures both precision AND insight.

The ensemble can be disabled via config.ensemble_mode = False to fall
back to single-call behavior (faster, cheaper, less reliable).
"""

import logging
from typing import Dict, Any, Optional
from experts.gateway import gateway

logger = logging.getLogger(__name__)

# Judge system prompt — kept minimal to reduce token cost
JUDGE_SYSTEM = """You are a senior astrology editor. You will be shown two analyses of the same chart.
Pick the better one. Be decisive — do not hedge.

Criteria (in priority order):
1. DATA ACCURACY: Are planetary degrees, signs, houses, dates correct and consistent with the provided data?
2. SPECIFICITY: Does it cite exact degrees, dates, aspects, or is it vague and generic?
3. INTERPRETIVE DEPTH: Does it reveal non-obvious patterns, psychological tensions, karmic themes?
4. COMPLETENESS: Are all required sections present with substance?
5. WRITING QUALITY: Is it vivid, precise, and free of banned filler words?

Reply in EXACTLY this format (no other text):
WINNER: A or B
REASON: one sentence explaining why"""


def ensemble_generate(
    system_prompt: str,
    user_prompt: str,
    model: str,
    max_tokens: int = 3000,
    seed: int = 42,
    **kwargs,
) -> Dict[str, Any]:
    """Run ensemble: strict + creative generation, then judge picks winner.

    Returns the same dict format as gateway.generate() so it's a
    drop-in replacement.
    """
    # ── Call 1: Strict (precision-optimized) ─────────────────────────
    strict = gateway.generate(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        model=model,
        max_tokens=max_tokens,
        temperature=0.0,
        seed=seed,
        reasoning_effort="high",
    )

    # ── Call 2: Creative (insight-optimized) ─────────────────────────
    creative = gateway.generate(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        model=model,
        max_tokens=max_tokens,
        temperature=0.3,
        seed=seed + 7,  # different seed for diversity
        reasoning_effort="medium",
    )

    # If either call failed, return whichever succeeded
    if not strict.get("success") and not creative.get("success"):
        return strict  # both failed, return first error
    if not strict.get("success"):
        logger.warning("Ensemble: strict call failed, using creative only")
        creative["ensemble"] = "creative_only"
        return creative
    if not creative.get("success"):
        logger.warning("Ensemble: creative call failed, using strict only")
        strict["ensemble"] = "strict_only"
        return strict

    strict_text = strict.get("content", "")
    creative_text = creative.get("content", "")

    # If texts are nearly identical, skip judge call (save cost)
    if _texts_similar(strict_text, creative_text):
        logger.info("Ensemble: outputs nearly identical, skipping judge")
        strict["ensemble"] = "identical_skip"
        return strict

    # ── Judge Call: cheap, fast, decisive ─────────────────────────────
    judge_prompt = (
        "Compare these two astrological analyses of the SAME chart data.\n\n"
        "═══ ANALYSIS A (Strict) ═══\n"
        f"{strict_text}\n\n"
        "═══ ANALYSIS B (Creative) ═══\n"
        f"{creative_text}\n\n"
        "Which is better? Reply EXACTLY as instructed."
    )

    judge_result = gateway.generate(
        system_prompt=JUDGE_SYSTEM,
        user_prompt=judge_prompt,
        model=model,
        max_tokens=100,
        temperature=0.0,
        seed=seed,
    )

    # Parse judge verdict
    winner = _parse_judge_verdict(judge_result)

    if winner == "B":
        logger.info("Ensemble: judge picked CREATIVE")
        creative["ensemble"] = "creative_won"
        creative["ensemble_reason"] = _extract_reason(judge_result)
        # Merge usage from all 3 calls
        creative["usage"] = _merge_usage(strict, creative, judge_result)
        return creative
    else:
        logger.info("Ensemble: judge picked STRICT")
        strict["ensemble"] = "strict_won"
        strict["ensemble_reason"] = _extract_reason(judge_result)
        strict["usage"] = _merge_usage(strict, creative, judge_result)
        return strict


def _texts_similar(a: str, b: str, threshold: float = 0.85) -> bool:
    """Quick similarity check — if >85% of words overlap, texts are similar enough."""
    if not a or not b:
        return False
    words_a = set(a.lower().split())
    words_b = set(b.lower().split())
    if not words_a or not words_b:
        return False
    overlap = len(words_a & words_b)
    total = max(len(words_a), len(words_b))
    return (overlap / total) > threshold


def _parse_judge_verdict(result: Dict) -> str:
    """Extract A or B from judge response."""
    if not result.get("success"):
        return "A"  # default to strict on judge failure
    text = result.get("content", "").upper()
    if "WINNER: B" in text or "WINNER:B" in text:
        return "B"
    return "A"  # default to strict


def _extract_reason(result: Dict) -> str:
    """Extract the REASON line from judge response."""
    if not result.get("success"):
        return ""
    text = result.get("content", "")
    for line in text.split("\n"):
        if line.strip().upper().startswith("REASON:"):
            return line.strip()[7:].strip()
    return ""


def _merge_usage(strict: Dict, creative: Dict, judge: Dict) -> Dict:
    """Sum up token usage across all 3 calls for cost tracking."""
    total_input = 0
    total_output = 0
    for r in (strict, creative, judge):
        usage = r.get("usage", {})
        total_input += usage.get("input_tokens", 0)
        total_output += usage.get("output_tokens", 0)
    return {"input_tokens": total_input, "output_tokens": total_output}
