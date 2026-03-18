# Fate Engine V6 - Core Directives

## Project Overview
A deterministic, multi-tradition astrological calculation engine. It calculates raw ephemeris data using `pyswisseph`, normalizes it via `validation_matrix.py`, and synthesizes reports via `archon.py` and `gateway_gemini.py`.

## Core Architectural Rules (STRICT)
1. **The Separation of Math and Prose:** LLMs are forbidden from doing math or deducing planetary degrees. All planetary positions MUST be routed from `core/ephemeris.py` and passed directly into the final text.
2. **No Regex Band-Aids:** We do not use regex to fix LLM hallucinations post-generation (e.g., `_validate_degrees_internal`). If an LLM hallucinates, the prompt architecture or data pipeline must be fixed.
3. **System Isolation:** Western (Tropical) and Vedic (Sidereal) logic must never bleed together. House lord routing is strictly pre-computed in `orchestrator._compute_house_lords()`.

## Coding Standards
* **Language:** Python 3.10+. Strict PEP-8.
* **Typing:** Use explicit typing (`Dict[str, Any]`, `List[PredictionEvent]`).
* **Gateway Usage:** When modifying `archon.py` or AI pipelines, prioritize `gateway.structured_generate()` (JSON schema) over `gateway.generate()` whenever factual accuracy is required.

## The Hallucination Protocol
Before writing any code that modifies LLM prompts, you MUST force the LLM to output a JSON "Plan" (mapping exactly which evidence blocks it will use) before it is allowed to write a single word of Markdown prose.