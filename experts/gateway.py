"""LLM Gateway — Gemini API via google-genai SDK.

Supports:
  - generate()           : free-text generation (experts, archon narrative)
  - structured_generate(): JSON-mode output (arbiter schema enforcement)

Model routing follows config.py:
  experts   → gemini-2.5-flash  (thinking-capable, temp=0.0 for determinism)
  arbiter   → gemini-3-flash-preview
  archon    → gemini-2.5-pro

Reproducibility: seed=42 by default on all calls for consistent outputs.

reasoning_effort mapping  (experts and archon pass this kwarg):
  "low"    → thinking_budget = 512
  "medium" → thinking_budget = 1024
  "high"   → thinking_budget = 2048
  None     → thinking disabled (fastest, cheapest)

Thinking is only applied to models that support it (2.5-pro, 2.5-flash).
Flash-lite calls skip thinking entirely.
"""

from google import genai
from google.genai import types
from typing import Dict, Any, Optional
from config import settings
import json
import time
import logging

logger = logging.getLogger(__name__)

EFFORT_BUDGET = {
    "low":    512,
    "medium": 1024,
    "high":   2048,
}


def _supports_thinking(model: str) -> bool:
    """Check if model supports thinking/reasoning tokens.
    Flash-lite does NOT support thinking — exclude it explicitly."""
    if "flash-lite" in model:
        return False
    return any(cap in model for cap in ("2.5-pro", "2.5-flash", "3-flash-preview", "3.1"))


def _build_thinking_config(model: str, reasoning_effort: Optional[str]) -> Optional[types.ThinkingConfig]:
    if not reasoning_effort:
        return None
    if not _supports_thinking(model):
        return None
    budget = EFFORT_BUDGET.get(reasoning_effort, 1024)
    return types.ThinkingConfig(thinking_budget=budget)


class LLMGateway:
    def __init__(self):
        if settings.google_api_key:
            self.client = genai.Client(api_key=settings.google_api_key)
        else:
            self.client = None
            logger.warning("GOOGLE_API_KEY not set — all LLM calls will fail")

    def _check_ready(self) -> Optional[Dict]:
        if not self.client:
            return {
                "success": False,
                "error": "GOOGLE_API_KEY not configured in .env",
                "data": None,
                "content": None,
            }
        return None

    def structured_generate(self,
                            system_prompt: str,
                            user_prompt: str,
                            output_schema: dict,
                            model: str = "gemini-2.5-flash-lite",
                            max_tokens: int = 4000,
                            temperature: float = 0.7,
                            seed: int = 42,
                            **kwargs) -> Dict[str, Any]:
        """Generate structured JSON output matching output_schema."""
        err = self._check_ready()
        if err:
            return err

        total_chars = len(system_prompt) + len(user_prompt) + len(str(output_schema))
        est_tokens = total_chars // 4
        if est_tokens > 120000:
            return {
                "success": False,
                "error": f"Prompt too large: ~{est_tokens} estimated tokens",
                "data": None,
            }

        schema_instruction = (
            f"\n\nYou must respond with valid JSON matching this schema:\n"
            f"{json.dumps(output_schema, indent=2)}\n"
            "Respond ONLY with the JSON object. No markdown fences, no preamble."
        )
        combined_system = system_prompt + schema_instruction

        reasoning_effort = kwargs.get("reasoning_effort")
        thinking_cfg = _build_thinking_config(model, reasoning_effort)

        config_kwargs: Dict[str, Any] = {
            "max_output_tokens": max_tokens,
            "response_mime_type": "application/json",
            "seed": seed,
        }
        if "flash-lite" not in model:
            config_kwargs["temperature"] = temperature
        if thinking_cfg:
            config_kwargs["thinking_config"] = thinking_cfg

        try:
            logger.info(f"Calling Gemini {model} structured (~{est_tokens} tokens)")
            response = self.client.models.generate_content(
                model=model,
                contents=user_prompt,
                config=types.GenerateContentConfig(
                    system_instruction=combined_system,
                    **config_kwargs,
                ),
            )

            raw = response.text or ""
            clean = raw.strip()
            if clean.startswith("```"):
                clean = clean.split("```", 2)[1]
                if clean.startswith("json"):
                    clean = clean[4:]
                clean = clean.rsplit("```", 1)[0].strip()

            try:
                data = json.loads(clean)
                return {
                    "success": True,
                    "data": data,
                    "model": model,
                    "usage": {
                        "input_tokens":  getattr(response.usage_metadata, "prompt_token_count", 0),
                        "output_tokens": getattr(response.usage_metadata, "candidates_token_count", 0),
                    },
                }
            except json.JSONDecodeError as e:
                logger.error(f"JSON decode error: {e}\nRaw: {raw[:500]}")
                return {
                    "success": False,
                    "error": f"Invalid JSON response: {e}",
                    "raw_content": raw[:1000],
                    "data": None,
                }

        except Exception as e:
            logger.error(f"Structured generation error ({model}): {e}")
            return {"success": False, "error": str(e), "data": None}

    def generate(self,
                 system_prompt: str,
                 user_prompt: str,
                 model: str = "gemini-2.5-flash-lite",
                 max_tokens: int = 2000,
                 temperature: float = 0.7,
                 seed: int = 42,
                 **kwargs) -> Dict[str, Any]:
        """Free-text generation with retry on quota/rate errors."""
        err = self._check_ready()
        if err:
            return err

        total_chars = len(system_prompt) + len(user_prompt)
        est_tokens = total_chars // 4
        if est_tokens > 25000:
            logger.warning(f"Prompt large ({est_tokens} est. tokens) — truncating from {len(user_prompt)} chars")
            max_chars = 100_000
            if len(user_prompt) > max_chars:
                chars_removed = len(user_prompt) - max_chars
                user_prompt = (
                    user_prompt[:max_chars]
                    + f"\n\n[TRUNCATION WARNING: {chars_removed} characters (~{chars_removed // 4} tokens) "
                    f"removed from end of prompt. The removed content included additional chart data "
                    f"and event details. Do NOT hallucinate or invent data to fill gaps — "
                    f"work only with the data provided above.]"
                )

        reasoning_effort = kwargs.get("reasoning_effort")
        thinking_cfg = _build_thinking_config(model, reasoning_effort)

        config_kwargs: Dict[str, Any] = {
            "max_output_tokens": max_tokens,
            "seed": seed,
        }
        if "flash-lite" not in model:
            config_kwargs["temperature"] = temperature
        if thinking_cfg:
            config_kwargs["thinking_config"] = thinking_cfg

        max_retries = 3
        base_delay = 20

        for attempt in range(max_retries):
            try:
                logger.info(f"Calling Gemini {model} (attempt {attempt + 1}, ~{est_tokens} tokens)")
                response = self.client.models.generate_content(
                    model=model,
                    contents=user_prompt,
                    config=types.GenerateContentConfig(
                        system_instruction=system_prompt,
                        **config_kwargs,
                    ),
                )

                return {
                    "success": True,
                    "content": response.text or "",
                    "model": model,
                    "usage": {
                        "input_tokens":  getattr(response.usage_metadata, "prompt_token_count", 0),
                        "output_tokens": getattr(response.usage_metadata, "candidates_token_count", 0),
                    },
                }

            except Exception as e:
                err_str = str(e).lower()
                is_rate = any(kw in err_str for kw in ("quota", "rate", "429", "resource exhausted"))
                if is_rate and attempt < max_retries - 1:
                    delay = base_delay * (2 ** attempt)
                    logger.warning(f"Rate limit — waiting {delay}s before retry {attempt + 2}")
                    time.sleep(delay)
                else:
                    logger.error(f"Gemini generation error ({model}): {e}")
                    return {"success": False, "error": str(e), "content": None}

        return {"success": False, "error": "Max retries exceeded", "content": None}


gateway = LLMGateway()
