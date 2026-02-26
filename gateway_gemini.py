"""LLM Gateway — Unified interface for OpenAI and Google Gemini models.

Routing logic:
  - Model strings starting with "gemini-" → Google GenAI SDK
  - All other model strings             → OpenAI SDK (legacy / fallback)

This means you can mix models per role simply by changing model strings
in config.py — no other code changes required.
"""

import json
import time
import logging
from typing import Dict, Any, Optional

from config import settings

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Lazy-initialise clients so unused SDKs don't cause import errors
# ─────────────────────────────────────────────────────────────────────────────

_openai_client   = None
_gemini_client   = None  # google.generativeai module handle


def _get_openai():
    global _openai_client
    if _openai_client is None:
        from openai import OpenAI
        _openai_client = OpenAI(
            api_key   = settings.openai_api_key,
            timeout   = 300.0,
            max_retries = 3,
        )
    return _openai_client


def _get_gemini():
    """Return configured google.generativeai module."""
    global _gemini_client
    if _gemini_client is None:
        try:
            import google.generativeai as genai
            genai.configure(api_key=settings.google_api_key)
            _gemini_client = genai
        except ImportError:
            raise ImportError(
                "google-generativeai package not installed. "
                "Run: pip install google-generativeai"
            )
    return _gemini_client


def _is_gemini(model: str) -> bool:
    return model.lower().startswith("gemini")


# ─────────────────────────────────────────────────────────────────────────────
# Gemini helpers
# ─────────────────────────────────────────────────────────────────────────────

def _gemini_thinking_level(reasoning_effort: Optional[str]) -> Optional[str]:
    """Map OpenAI-style reasoning_effort → Gemini 3 thinking_level."""
    mapping = {
        "low":    "minimal",
        "medium": "low",
        "high":   "medium",
        "max":    "high",
    }
    return mapping.get(str(reasoning_effort).lower()) if reasoning_effort else None


def _gemini_generate(model: str, system_prompt: str, user_prompt: str,
                     max_tokens: int, temperature: float,
                     reasoning_effort: Optional[str] = None,
                     json_mode: bool = False) -> Dict[str, Any]:
    """
    Call Google Gemini via google-generativeai SDK.
    Handles Gemini 2.x and Gemini 3.x models.
    """
    genai = _get_gemini()

    # Build generation config
    gen_cfg: Dict[str, Any] = {
        "max_output_tokens": max_tokens,
        "temperature":       temperature,
    }

    # Gemini 3 models support thinking_level
    if reasoning_effort and any(m in model for m in ["gemini-3", "gemini-3."]):
        tl = _gemini_thinking_level(reasoning_effort)
        if tl:
            gen_cfg["thinking_config"] = {"thinking_level": tl}

    # JSON output mode
    if json_mode:
        gen_cfg["response_mime_type"] = "application/json"

    # System instruction
    generation_config = genai.GenerationConfig(**gen_cfg)

    try:
        m = genai.GenerativeModel(
            model_name        = model,
            generation_config = generation_config,
            system_instruction = system_prompt,
        )

        response = m.generate_content(user_prompt)

        # Extract text safely
        try:
            content = response.text
        except Exception:
            # Some Gemini 3 responses need part-level extraction
            parts = []
            for candidate in response.candidates:
                for part in candidate.content.parts:
                    if hasattr(part, "text") and part.text:
                        parts.append(part.text)
            content = "\n".join(parts)

        # Usage metadata (not always present)
        usage = {}
        if hasattr(response, "usage_metadata") and response.usage_metadata:
            um = response.usage_metadata
            usage = {
                "input_tokens":  getattr(um, "prompt_token_count",      0),
                "output_tokens": getattr(um, "candidates_token_count",  0),
            }

        return {
            "success": True,
            "content": content,
            "model":   model,
            "usage":   usage,
        }

    except Exception as e:
        logger.error(f"Gemini {model} error: {e}")
        return {"success": False, "error": str(e), "content": None}


# ─────────────────────────────────────────────────────────────────────────────
# OpenAI helper (preserved from original gateway)
# ─────────────────────────────────────────────────────────────────────────────

def _openai_generate(model: str, system_prompt: str, user_prompt: str,
                     max_tokens: int, temperature: float,
                     reasoning_effort: Optional[str] = None,
                     json_mode: bool = False) -> Dict[str, Any]:
    client = _get_openai()

    # Reasoning models require temperature=1
    if any(m in model.lower() for m in ["o1", "o3", "gpt-5"]):
        temperature = 1.0

    params: Dict[str, Any] = {
        "model":    model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user",   "content": user_prompt},
        ],
        "max_completion_tokens": max_tokens,
        "temperature":           temperature,
        "stream":                False,
    }
    if reasoning_effort:
        params["reasoning_effort"] = reasoning_effort
    if json_mode:
        params["response_format"] = {"type": "json_object"}

    max_retries = 3
    for attempt in range(max_retries):
        try:
            response = client.chat.completions.create(**params)
            return {
                "success": True,
                "content": response.choices[0].message.content,
                "model":   model,
                "usage": {
                    "input_tokens":  response.usage.prompt_tokens,
                    "output_tokens": response.usage.completion_tokens,
                },
            }
        except Exception as e:
            err = str(e).lower()
            is_retryable = any(t in err for t in
                               ["rate limit", "connection", "timeout", "503", "502"])
            if is_retryable and attempt < max_retries - 1:
                wait = 20 * (2 ** attempt)
                logger.warning(f"OpenAI retry {attempt + 1} in {wait}s: {e}")
                time.sleep(wait)
            else:
                logger.error(f"OpenAI {model} error: {e}")
                return {"success": False, "error": str(e), "content": None}

    return {"success": False, "error": "Max retries exceeded", "content": None}


# ─────────────────────────────────────────────────────────────────────────────
# LLMGateway — public interface (same API as original, no caller changes needed)
# ─────────────────────────────────────────────────────────────────────────────

class LLMGateway:
    """
    Unified gateway. Route to Gemini or OpenAI based on model string.
    All existing callers (experts, arbiter, archon) work unchanged.
    """

    def generate(self,
                 system_prompt: str,
                 user_prompt: str,
                 model: str = None,
                 max_tokens: int = 2800,
                 temperature: float = 0.7,
                 **kwargs) -> Dict[str, Any]:
        """
        Generate free-form text.
        Automatically routes to Gemini or OpenAI based on model string.
        """
        model = model or settings.archon_model

        # Safety: truncate enormous prompts
        total_chars = len(system_prompt) + len(user_prompt)
        if total_chars > 500_000:  # Gemini supports 1M context; keep buffer
            logger.warning(f"Prompt very large ({total_chars} chars), truncating user prompt...")
            user_prompt = user_prompt[:480_000] + "\n\n[truncated]"

        reasoning_effort = kwargs.get("reasoning_effort")

        if _is_gemini(model):
            result = _gemini_generate(
                model, system_prompt, user_prompt,
                max_tokens, temperature, reasoning_effort,
                json_mode=False,
            )
            # Retry once on transient connection errors
            if not result.get("success") and any(
                t in str(result.get("error", "")).lower()
                for t in ["connection", "timeout", "503", "unavailable"]
            ):
                logger.warning(f"Gemini transient error, retrying in 5s...")
                time.sleep(5)
                result = _gemini_generate(
                    model, system_prompt, user_prompt,
                    max_tokens, temperature, reasoning_effort, False
                )
            return result
        else:
            return _openai_generate(
                model, system_prompt, user_prompt,
                max_tokens, temperature, reasoning_effort,
                json_mode=False,
            )

    def structured_generate(self,
                             system_prompt: str,
                             user_prompt: str,
                             output_schema: dict,
                             model: str = None,
                             max_tokens: int = 4000,
                             temperature: float = 0.7,
                             **kwargs) -> Dict[str, Any]:
        """
        Generate structured JSON output matching output_schema.
        For Gemini: uses response_mime_type="application/json" + schema in prompt.
        For OpenAI: uses response_format={"type":"json_object"}.
        """
        model = model or settings.arbiter_model

        # Embed schema in system prompt for both providers
        schema_instruction = (
            f"\n\nYou must respond with valid JSON matching this schema exactly:\n"
            f"{json.dumps(output_schema, indent=2)}\n"
            f"Respond ONLY with the JSON object. No markdown. No ```json blocks."
        )
        system_with_schema = system_prompt + schema_instruction

        reasoning_effort = kwargs.get("reasoning_effort")

        max_retries = 3
        last_error  = "Unknown"

        for attempt in range(1, max_retries + 1):
            if _is_gemini(model):
                result = _gemini_generate(
                    model, system_with_schema, user_prompt,
                    max_tokens, temperature, reasoning_effort,
                    json_mode=True,
                )
            else:
                result = _openai_generate(
                    model, system_with_schema, user_prompt,
                    max_tokens, temperature, reasoning_effort,
                    json_mode=True,
                )

            if not result.get("success"):
                last_error = result.get("error", "Unknown")
                err_lower  = str(last_error).lower()
                is_retry   = any(t in err_lower for t in
                                 ["connection", "timeout", "503", "502",
                                  "unavailable", "rate limit"])
                if is_retry and attempt < max_retries:
                    wait = 5 * attempt
                    logger.warning(f"structured_generate attempt {attempt} failed "
                                   f"({last_error}). Retry in {wait}s...")
                    time.sleep(wait)
                    continue
                return {"success": False, "error": last_error, "data": None}

            # Parse JSON from content
            content = result.get("content", "")
            # Strip markdown code fences if present
            clean = content.strip()
            if clean.startswith("```"):
                clean = clean.split("\n", 1)[-1]
                clean = clean.rsplit("```", 1)[0].strip()

            try:
                data = json.loads(clean)
                return {
                    "success": True,
                    "data":    data,
                    "model":   model,
                    "usage":   result.get("usage", {}),
                }
            except json.JSONDecodeError as e:
                logger.error(f"JSON decode error (attempt {attempt}): {e}\n"
                             f"Content: {clean[:400]}")
                if attempt < max_retries:
                    time.sleep(3)
                    continue
                return {
                    "success":     False,
                    "error":       f"Invalid JSON: {e}",
                    "raw_content": clean[:1000],
                    "data":        None,
                }

        return {"success": False, "error": f"All retries failed: {last_error}", "data": None}

    # Backwards-compat alias used by archon v1
    def generate_chapter(self, system_prompt: str, chapter_context: str,
                         chapter_num: int, model: str = None) -> Dict[str, Any]:
        model = model or settings.archon_model
        return self.generate(
            system_prompt = system_prompt,
            user_prompt   = f"CHAPTER {chapter_num} CONTEXT:\n\n{chapter_context}\n\nWrite 300–500 words.",
            model         = model,
            max_tokens    = 1500,
            temperature   = 0.7,
        )


gateway = LLMGateway()
