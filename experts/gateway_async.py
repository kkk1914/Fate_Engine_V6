"""Async LLM Gateway — Gemini API via httpx.

Phase 2.1: Non-blocking async gateway using httpx.AsyncClient for direct
Gemini REST API calls. Replaces time.sleep() backoff with asyncio.sleep().

Same interface as sync gateway.py:
  - generate()           : free-text generation
  - structured_generate(): JSON-mode output

Usage:
    from experts.gateway_async import async_gateway

    result = await async_gateway.generate(
        system_prompt="...", user_prompt="...", model="gemini-2.5-flash"
    )
"""
import asyncio
import httpx
import json
import time
import logging
from typing import Dict, Any, Optional

from config import settings
from core.telemetry import get_cost_tracker

logger = logging.getLogger(__name__)

EFFORT_BUDGET = {
    "low": 512,
    "medium": 1024,
    "high": 2048,
}

# Gemini REST API base URL
_API_BASE = "https://generativelanguage.googleapis.com/v1beta"


def _supports_thinking(model: str) -> bool:
    """Check if model supports thinking/reasoning tokens."""
    if "flash-lite" in model:
        return False
    return any(cap in model for cap in ("2.5-pro", "2.5-flash", "3-flash-preview", "3.1"))


def _build_generation_config(
    model: str,
    max_tokens: int,
    temperature: float,
    seed: int,
    reasoning_effort: Optional[str] = None,
    response_mime_type: Optional[str] = None,
    response_schema: Optional[dict] = None,
) -> dict:
    """Build generationConfig for the REST API."""
    config: Dict[str, Any] = {
        "maxOutputTokens": max_tokens,
        "seed": seed,
    }
    if "flash-lite" not in model:
        config["temperature"] = temperature
    if response_mime_type:
        config["responseMimeType"] = response_mime_type
    if response_schema:
        config["responseSchema"] = response_schema

    # Thinking config
    if reasoning_effort and _supports_thinking(model):
        budget = EFFORT_BUDGET.get(reasoning_effort, 1024)
        config["thinkingConfig"] = {"thinkingBudget": budget}

    return config


class AsyncLLMGateway:
    """Async LLM gateway using httpx for non-blocking I/O."""

    def __init__(self):
        self.api_key = settings.google_api_key
        if not self.api_key:
            logger.warning("GOOGLE_API_KEY not set — all async LLM calls will fail")
        # Persistent client with connection pooling — reused across all calls
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Lazy-initialize the async HTTP client."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(300.0, connect=10.0),
                limits=httpx.Limits(max_connections=20, max_keepalive_connections=10),
            )
        return self._client

    def _check_ready(self) -> Optional[Dict]:
        if not self.api_key:
            return {
                "success": False,
                "error": "GOOGLE_API_KEY not configured in .env",
                "data": None,
                "content": None,
            }
        return None

    async def structured_generate(
        self,
        system_prompt: str,
        user_prompt: str,
        output_schema: dict,
        model: str = "gemini-2.5-flash-lite",
        max_tokens: int = 4000,
        temperature: float = 0.7,
        seed: int = 42,
        **kwargs,
    ) -> Dict[str, Any]:
        """Generate structured JSON output matching output_schema (async)."""
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
        gen_config = _build_generation_config(
            model, max_tokens, temperature, seed,
            reasoning_effort=reasoning_effort,
            response_mime_type="application/json",
            response_schema=output_schema if output_schema else None,
        )

        payload = {
            "system_instruction": {"parts": [{"text": combined_system}]},
            "contents": [{"parts": [{"text": user_prompt}]}],
            "generationConfig": gen_config,
        }

        try:
            t0 = time.time()
            logger.info(f"[async] Calling Gemini {model} structured (~{est_tokens} tokens)")
            client = await self._get_client()
            url = f"{_API_BASE}/models/{model}:generateContent?key={self.api_key}"
            resp = await client.post(url, json=payload)
            latency_ms = (time.time() - t0) * 1000

            if resp.status_code != 200:
                error_detail = resp.text[:500]
                logger.error(f"[async] Gemini API error {resp.status_code}: {error_detail}")
                return {"success": False, "error": f"API error {resp.status_code}: {error_detail}", "data": None}

            data = resp.json()
            raw = self._extract_text(data)
            clean = self._clean_json(raw)
            input_tokens, output_tokens = self._extract_usage(data)

            # Record telemetry
            tracker = get_cost_tracker()
            if tracker:
                phase = kwargs.get("phase", "structured")
                tracker.record(model=model, input_tokens=input_tokens,
                               output_tokens=output_tokens, phase=phase,
                               latency_ms=latency_ms)

            try:
                parsed = json.loads(clean)
                return {
                    "success": True,
                    "data": parsed,
                    "model": model,
                    "usage": {"input_tokens": input_tokens, "output_tokens": output_tokens},
                }
            except json.JSONDecodeError as e:
                logger.error(f"[async] JSON decode error: {e}\nRaw: {raw[:500]}")
                return {"success": False, "error": f"Invalid JSON: {e}", "raw_content": raw[:1000], "data": None}

        except Exception as e:
            logger.error(f"[async] Structured generation error ({model}): {e}")
            return {"success": False, "error": str(e), "data": None}

    async def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        model: str = "gemini-2.5-flash-lite",
        max_tokens: int = 2000,
        temperature: float = 0.7,
        seed: int = 42,
        **kwargs,
    ) -> Dict[str, Any]:
        """Free-text generation with async retry on quota/rate errors."""
        err = self._check_ready()
        if err:
            return err

        total_chars = len(system_prompt) + len(user_prompt)
        est_tokens = total_chars // 4
        if est_tokens > 25000:
            logger.warning(f"[async] Prompt large ({est_tokens} est. tokens)")
            max_chars = 100_000
            if len(user_prompt) > max_chars:
                chars_removed = len(user_prompt) - max_chars
                user_prompt = (
                    user_prompt[:max_chars]
                    + f"\n\n[TRUNCATION WARNING: {chars_removed} characters removed. "
                    f"Do NOT hallucinate — work only with data above.]"
                )

        reasoning_effort = kwargs.get("reasoning_effort")
        gen_config = _build_generation_config(
            model, max_tokens, temperature, seed,
            reasoning_effort=reasoning_effort,
        )

        payload = {
            "system_instruction": {"parts": [{"text": system_prompt}]},
            "contents": [{"parts": [{"text": user_prompt}]}],
            "generationConfig": gen_config,
        }

        max_retries = 3
        base_delay = 20

        for attempt in range(max_retries):
            try:
                t0 = time.time()
                logger.info(f"[async] Calling Gemini {model} (attempt {attempt + 1}, ~{est_tokens} tokens)")
                client = await self._get_client()
                url = f"{_API_BASE}/models/{model}:generateContent?key={self.api_key}"
                resp = await client.post(url, json=payload)
                latency_ms = (time.time() - t0) * 1000

                if resp.status_code == 429 or resp.status_code == 503:
                    if attempt < max_retries - 1:
                        delay = base_delay * (2 ** attempt)
                        logger.warning(f"[async] Rate limit {resp.status_code} — waiting {delay}s")
                        await asyncio.sleep(delay)
                        continue
                    return {"success": False, "error": f"Rate limited after {max_retries} attempts", "content": None}

                if resp.status_code != 200:
                    error_detail = resp.text[:500]
                    logger.error(f"[async] Gemini API error {resp.status_code}: {error_detail}")
                    return {"success": False, "error": f"API error {resp.status_code}", "content": None}

                data = resp.json()
                text = self._extract_text(data)
                input_tokens, output_tokens = self._extract_usage(data)

                # Record telemetry
                tracker = get_cost_tracker()
                if tracker:
                    phase = kwargs.get("phase", "generate")
                    tracker.record(model=model, input_tokens=input_tokens,
                                   output_tokens=output_tokens, phase=phase,
                                   latency_ms=latency_ms)

                return {
                    "success": True,
                    "content": text,
                    "model": model,
                    "usage": {"input_tokens": input_tokens, "output_tokens": output_tokens},
                }

            except httpx.TimeoutException:
                if attempt < max_retries - 1:
                    delay = base_delay * (2 ** attempt)
                    logger.warning(f"[async] Timeout — waiting {delay}s before retry")
                    await asyncio.sleep(delay)
                else:
                    return {"success": False, "error": "Request timed out after retries", "content": None}

            except Exception as e:
                err_str = str(e).lower()
                is_rate = any(kw in err_str for kw in ("quota", "rate", "429", "resource exhausted"))
                if is_rate and attempt < max_retries - 1:
                    delay = base_delay * (2 ** attempt)
                    logger.warning(f"[async] Rate limit — waiting {delay}s")
                    await asyncio.sleep(delay)
                else:
                    logger.error(f"[async] Generation error ({model}): {e}")
                    return {"success": False, "error": str(e), "content": None}

        return {"success": False, "error": "Max retries exceeded", "content": None}

    async def close(self):
        """Close the HTTP client. Call on shutdown."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    # ── Helpers ───────────────────────────────────────────────────────────

    @staticmethod
    def _extract_text(response_data: dict) -> str:
        """Extract text from Gemini REST API response."""
        try:
            candidates = response_data.get("candidates", [])
            if candidates:
                parts = candidates[0].get("content", {}).get("parts", [])
                texts = [p.get("text", "") for p in parts if "text" in p]
                return "".join(texts)
        except (KeyError, IndexError):
            pass
        return ""

    @staticmethod
    def _extract_usage(response_data: dict) -> tuple:
        """Extract token counts from Gemini REST API response."""
        usage = response_data.get("usageMetadata", {})
        input_tokens = usage.get("promptTokenCount", 0)
        output_tokens = usage.get("candidatesTokenCount", 0)
        return input_tokens, output_tokens

    @staticmethod
    def _clean_json(raw: str) -> str:
        """Strip markdown fences from JSON responses."""
        clean = raw.strip()
        if clean.startswith("```"):
            clean = clean.split("```", 2)[1]
            if clean.startswith("json"):
                clean = clean[4:]
            clean = clean.rsplit("```", 1)[0].strip()
        return clean


# ── Factory ───────────────────────────────────────────────────────────────
def get_gateway(async_mode: bool = False):
    """Factory: returns sync or async gateway based on mode."""
    if async_mode:
        return AsyncLLMGateway()
    from experts.gateway import LLMGateway
    return LLMGateway()


# Global async instance
async_gateway = AsyncLLMGateway()
