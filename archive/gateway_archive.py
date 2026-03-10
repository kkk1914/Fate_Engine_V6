"""LLM Gateway — Google Gemini via google-genai SDK (not the deprecated google-generativeai).

Install:  pip install google-genai
SDK docs: https://googleapis.github.io/python-genai/

Thinking support by model family:
  gemini-2.5-flash-lite  → NO thinking (ignore reasoning_effort)
  gemini-2.5-flash       → thinking_budget (0 = off, min 128)
  gemini-2.5-pro         → thinking_budget (min 128, cannot turn off)
  gemini-3-flash-*       → thinking_level  (minimal/low/medium/high)
  gemini-3-pro-*         → thinking_level  (low/high)
  gemini-3.1-pro-*       → thinking_level  (low/medium/high)
"""

import json
import time
import logging
from typing import Dict, Any, Optional

from google import genai
from google.genai import types
from google.genai.errors import APIError

from config import settings

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Single shared client (created once at module load)
# ─────────────────────────────────────────────────────────────────────────────

_client: Optional[genai.Client] = None


def _get_client() -> Optional[genai.Client]:
    global _client
    if _client is None:
        key = settings.google_api_key
        if not key:
            logger.error("GOOGLE_API_KEY not set in .env")
            return None
        _client = genai.Client(api_key=key)
    return _client


# ─────────────────────────────────────────────────────────────────────────────
# Thinking config helpers
# ─────────────────────────────────────────────────────────────────────────────

def _supports_thinking(model: str) -> str:
    """
    Returns thinking mode:
      'budget'  → Gemini 2.5 Flash / Pro (uses thinking_budget)
      'level'   → Gemini 3.x (uses thinking_level)
      'none'    → model doesn't support thinking (Flash Lite, etc.)
    """
    m = model.lower()
    if "flash-lite" in m:
        return "none"
    if "2.5-flash" in m or "2.5-pro" in m:
        return "budget"
    if "gemini-3" in m or "gemini-3." in m:
        return "level"
    return "none"


def _effort_to_budget(reasoning_effort: Optional[str]) -> int:
    """Map effort string → thinking_budget tokens for Gemini 2.5."""
    mapping = {"low": 512, "medium": 1024, "high": 2048, "max": 4096}
    return mapping.get(str(reasoning_effort).lower(), 1024) if reasoning_effort else 1024


def _effort_to_level(reasoning_effort: Optional[str]) -> str:
    """Map effort string → thinking_level string for Gemini 3."""
    mapping = {"low": "minimal", "medium": "low", "high": "medium", "max": "high"}
    return mapping.get(str(reasoning_effort).lower(), "low") if reasoning_effort else "low"


def _build_thinking_config(model: str,
                            reasoning_effort: Optional[str]) -> Optional[types.ThinkingConfig]:
    """Return a ThinkingConfig appropriate for this model, or None."""
    mode = _supports_thinking(model)
    if mode == "none" or not reasoning_effort:
        return None
    if mode == "budget":
        budget = _effort_to_budget(reasoning_effort)
        # gemini-2.5-pro minimum is 128; cannot be turned off
        budget = max(128, budget)
        return types.ThinkingConfig(thinking_budget=budget)
    if mode == "level":
        level = _effort_to_level(reasoning_effort)
        return types.ThinkingConfig(thinking_level=level)
    return None


# ─────────────────────────────────────────────────────────────────────────────
# Core generation function
# ─────────────────────────────────────────────────────────────────────────────

def _gemini_call(model: str,
                 system_prompt: str,
                 user_prompt: str,
                 max_tokens: int,
                 temperature: float,
                 reasoning_effort: Optional[str] = None,
                 json_mode: bool = False) -> Dict[str, Any]:
    """
    Single call to Gemini via new google-genai SDK.
    Returns {"success": True, "content": str, "model": str, "usage": dict}
    or      {"success": False, "error": str, "content": None}
    """
    client = _get_client()
    if not client:
        return {"success": False, "error": "GOOGLE_API_KEY not configured", "content": None}

    # Build config kwargs
    cfg: Dict[str, Any] = {
        "system_instruction": system_prompt,
        "max_output_tokens":  max_tokens,
        "temperature":        temperature,
    }

    if json_mode:
        cfg["response_mime_type"] = "application/json"

    thinking = _build_thinking_config(model, reasoning_effort)
    if thinking is not None:
        cfg["thinking_config"] = thinking
        # Some thinking models behave better with temperature=1
        if "gemini-3" in model.lower():
            cfg["temperature"] = 1.0

    try:
        response = client.models.generate_content(
            model    = model,
            contents = user_prompt,
            config   = types.GenerateContentConfig(**cfg),
        )

        # Extract text — filter out thought parts (they have part.thought=True)
        text_parts = []
        try:
            for candidate in response.candidates:
                for part in candidate.content.parts:
                    if not getattr(part, "thought", False) and part.text:
                        text_parts.append(part.text)
            content = "".join(text_parts) if text_parts else response.text
        except Exception:
            content = response.text

        # Usage metadata
        usage = {}
        um = getattr(response, "usage_metadata", None)
        if um:
            usage = {
                "input_tokens":  getattr(um, "prompt_token_count",     0),
                "output_tokens": getattr(um, "candidates_token_count", 0),
                "thinking_tokens": getattr(um, "thoughts_token_count", 0),
            }

        return {"success": True, "content": content, "model": model, "usage": usage}

    except APIError as e:
        logger.error(f"Gemini APIError [{model}]: {e}")
        return {"success": False, "error": str(e), "content": None}
    except Exception as e:
        logger.error(f"Gemini error [{model}]: {e}")
        return {"success": False, "error": str(e), "content": None}


# ─────────────────────────────────────────────────────────────────────────────
# LLMGateway — public interface unchanged from previous versions
# ─────────────────────────────────────────────────────────────────────────────

class LLMGateway:
    """
    Gateway to Gemini models via google-genai SDK.
    Public API is identical to previous versions — no caller changes needed.
    """

    def generate(self,
                 system_prompt: str,
                 user_prompt: str,
                 model: str = None,
                 max_tokens: int = 2800,
                 temperature: float = 0.7,
                 **kwargs) -> Dict[str, Any]:
        """Free-form text generation."""
        model = model or settings.archon_model
        reasoning_effort = kwargs.get("reasoning_effort")

        # Truncate enormous prompts (safety net)
        if len(system_prompt) + len(user_prompt) > 500_000:
            logger.warning("Prompt > 500K chars, truncating user_prompt...")
            user_prompt = user_prompt[:480_000] + "\n\n[truncated]"

        max_retries = 3
        for attempt in range(1, max_retries + 1):
            result = _gemini_call(
                model, system_prompt, user_prompt,
                max_tokens, temperature, reasoning_effort,
                json_mode=False,
            )
            if result["success"]:
                if attempt > 1:
                    logger.info(f"Succeeded on attempt {attempt}")
                return result

            err = str(result.get("error", "")).lower()
            is_retryable = any(t in err for t in
                               ["connection", "timeout", "503", "unavailable",
                                "resource exhausted", "rate limit"])
            if is_retryable and attempt < max_retries:
                wait = 5 * attempt
                logger.warning(f"Transient error, retry {attempt}/{max_retries} in {wait}s: {result['error']}")
                time.sleep(wait)
            else:
                return result

        return {"success": False, "error": "Max retries exceeded", "content": None}

    def structured_generate(self,
                             system_prompt: str,
                             user_prompt: str,
                             output_schema: dict,
                             model: str = None,
                             max_tokens: int = 4000,
                             temperature: float = 0.7,
                             **kwargs) -> Dict[str, Any]:
        """
        Structured JSON generation.
        Uses Gemini's native JSON mode (response_mime_type=application/json)
        with the schema embedded in the system prompt.
        """
        model = model or settings.arbiter_model
        reasoning_effort = kwargs.get("reasoning_effort")

        schema_instruction = (
            f"\n\nRespond ONLY with valid JSON matching this schema exactly:\n"
            f"{json.dumps(output_schema, indent=2)}\n"
            f"Do not include markdown, code fences, or any explanation."
        )
        full_system = system_prompt + schema_instruction

        max_retries = 3
        last_error = "Unknown"

        for attempt in range(1, max_retries + 1):
            result = _gemini_call(
                model, full_system, user_prompt,
                max_tokens, temperature, reasoning_effort,
                json_mode=True,
            )

            if not result["success"]:
                last_error = result.get("error", "Unknown")
                err = str(last_error).lower()
                is_retryable = any(t in err for t in
                                   ["connection", "timeout", "503", "502",
                                    "unavailable", "resource exhausted", "rate limit"])
                if is_retryable and attempt < max_retries:
                    wait = 5 * attempt
                    logger.warning(f"structured_generate retry {attempt} in {wait}s: {last_error}")
                    time.sleep(wait)
                    continue
                return {"success": False, "error": last_error, "data": None}

            # Parse JSON — strip any accidental fences
            content = result.get("content", "").strip()
            if content.startswith("```"):
                content = content.split("\n", 1)[-1]
                content = content.rsplit("```", 1)[0].strip()

            try:
                data = json.loads(content)
                return {
                    "success": True,
                    "data":    data,
                    "model":   model,
                    "usage":   result.get("usage", {}),
                }
            except json.JSONDecodeError as e:
                logger.error(f"JSON decode error (attempt {attempt}): {e}\n"
                             f"Content preview: {content[:400]}")
                if attempt < max_retries:
                    time.sleep(3)
                    continue
                return {
                    "success":     False,
                    "error":       f"Invalid JSON: {e}",
                    "raw_content": content[:1000],
                    "data":        None,
                }

        return {"success": False, "error": f"All retries failed: {last_error}", "data": None}

    # Backwards-compatibility alias (used by archon v1)
    def generate_chapter(self, system_prompt: str, chapter_context: str,
                         chapter_num: int, model: str = None) -> Dict[str, Any]:
        model = model or settings.archon_model
        return self.generate(
            system_prompt = system_prompt,
            user_prompt   = (f"CHAPTER {chapter_num} CONTEXT:\n\n"
                             f"{chapter_context}\n\nWrite 300–500 words."),
            model         = model,
            max_tokens    = 1500,
            temperature   = 0.7,
        )


gateway = LLMGateway()
