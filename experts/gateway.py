"""LLM Gateway for OpenAI using Chat Completions API."""
from openai import OpenAI, APITimeoutError, APIConnectionError, RateLimitError
from typing import Dict, Any, Optional
from config import settings
import json
import time
import logging

logger = logging.getLogger(__name__)

class LLMGateway:
    def __init__(self):
        self.client = OpenAI(
            api_key=settings.openai_api_key,
            timeout=300.0,  # Increased from 120 to 300 seconds
            max_retries=3   # Built-in retries at client level
        )

    def structured_generate(self,
                            system_prompt: str,
                            user_prompt: str,
                            output_schema: dict,
                            model: str = "gpt-4o",
                            max_tokens: int = 4000,
                            temperature: float = 0.7,
                            **kwargs) -> Dict[str, Any]:
        """
        Generate structured JSON output according to a schema.
        Uses OpenAI's JSON mode for reliable structured outputs.
        """
        if not settings.openai_api_key:
            return {
                "success": False,
                "error": "OpenAI API key not configured in .env",
                "data": None
            }

        # Check prompt size
        total_chars = len(system_prompt) + len(user_prompt) + len(str(output_schema))
        est_tokens = total_chars // 4
        if est_tokens > 120000:
            return {
                "success": False,
                "error": f"Prompt too large: ~{est_tokens} tokens",
                "data": None
            }

        # Append schema instructions to system prompt
        schema_instruction = f"\n\nYou must respond with valid JSON matching this schema:\n{json.dumps(output_schema, indent=2)}\nRespond ONLY with the JSON object, no markdown formatting, no ```json code blocks."

        try:
            # o1/o3 series: use max_completion_tokens, no temperature, add reasoning_effort
            _o1_model = any(model.startswith(p) for p in ("o1", "o3", "o4"))
            reasoning_effort = kwargs.get("reasoning_effort")

            params = {
                "model": model,
                "messages": [
                    {"role": "system", "content": system_prompt + schema_instruction},
                    {"role": "user", "content": user_prompt}
                ],
                "response_format": {"type": "json_object"},
                "stream": False
            }
            if _o1_model:
                params["max_completion_tokens"] = max_tokens
                if reasoning_effort:
                    params["reasoning_effort"] = reasoning_effort
            else:
                params["max_tokens"] = max_tokens
                params["temperature"] = temperature

            logger.info(f"Calling OpenAI {model} for structured output (~{est_tokens} tokens)")
            response = self.client.chat.completions.create(**params)

            content = response.choices[0].message.content

            # Parse and validate JSON
            try:
                data = json.loads(content)
                return {
                    "success": True,
                    "data": data,
                    "model": model,
                    "usage": {
                        "input_tokens": response.usage.prompt_tokens,
                        "output_tokens": response.usage.completion_tokens
                    }
                }
            except json.JSONDecodeError as e:
                logger.error(f"JSON decode error: {e}\nContent: {content[:500]}")
                return {
                    "success": False,
                    "error": f"Invalid JSON response: {str(e)}",
                    "raw_content": content[:1000],
                    "data": None
                }

        except APITimeoutError as e:
            logger.error(f"OpenAI Timeout: {e}")
            return {"success": False, "error": "Request timed out after 300s", "data": None}
        except RateLimitError as e:
            logger.error(f"Rate limit hit: {e}")
            return {"success": False, "error": "Rate limit exceeded. Wait 60 seconds.", "data": None}
        except Exception as e:
            logger.error(f"Structured generation error: {e}")
            return {"success": False, "error": str(e), "data": None}

    def generate(self,
                 system_prompt: str,
                 user_prompt: str,
                 model: str = "gpt-4o",
                 max_tokens: int = 2000,  # Reduced from 4000
                 temperature: float = 0.7,
                 **kwargs) -> Dict[str, Any]:

        # Aggressive token budgeting for 30k TPM limit
        total_chars = len(system_prompt) + len(user_prompt)
        est_tokens = total_chars // 4

        # Hard cap at 25k to stay under 30k limit with buffer
        if est_tokens > 25000:
            logger.warning(f"Prompt too large ({est_tokens} est. tokens), truncating...")
            # Truncate user prompt aggressively
            max_chars = 100000  # ~25k tokens
            if len(user_prompt) > max_chars:
                user_prompt = user_prompt[:max_chars] + "\n\n[Content truncated due to length limits...]"

        if not settings.openai_api_key:
            return {"success": False, "error": "OpenAI API key not configured", "content": None}

        # Retry logic for rate limits
        max_retries = 3
        base_delay = 20  # Start with 20 seconds

        for attempt in range(max_retries):
            try:
                _o1_model = any(model.startswith(p) for p in ("o1", "o3", "o4"))
                reasoning_effort = kwargs.get("reasoning_effort")

                params = {
                    "model": model,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}
                    ],
                    "stream": False
                }
                if _o1_model:
                    params["max_completion_tokens"] = max_tokens
                    if reasoning_effort:
                        params["reasoning_effort"] = reasoning_effort
                else:
                    params["max_tokens"] = max_tokens
                    params["temperature"] = temperature

                logger.info(f"Calling OpenAI {model} (attempt {attempt + 1}, ~{est_tokens} tokens)")
                response = self.client.chat.completions.create(**params)

                return {
                    "success": True,
                    "content": response.choices[0].message.content,
                    "model": model,
                    "usage": {
                        "input_tokens": response.usage.prompt_tokens,
                        "output_tokens": response.usage.completion_tokens
                    }
                }

            except RateLimitError as e:
                if attempt < max_retries - 1:
                    delay = base_delay * (2 ** attempt)  # 20s, 40s, 80s
                    logger.warning(f"Rate limit hit, waiting {delay}s before retry {attempt + 2}...")
                    time.sleep(delay)
                else:
                    logger.error(f"Rate limit persists after {max_retries} retries")
                    return {
                        "success": False,
                        "error": "Rate limit exceeded. Try again in 2 minutes or reduce data.",
                        "content": None
                    }
            except APITimeoutError as e:
                logger.error(f"OpenAI Timeout: {e}")
                return {"success": False, "error": "Request timed out", "content": None}
            except Exception as e:
                logger.error(f"Unexpected error: {e}")
                return {"success": False, "error": str(e), "content": None}

        return {"success": False, "error": "Max retries exceeded", "content": None}

    def generate_chapter(self,
                         system_prompt: str,
                         chapter_context: str,
                         chapter_num: int,
                         model: str = "gpt-4o") -> Dict[str, Any]:
        """Generate a single chapter to avoid token limits."""
        # Use a focused system prompt instead of the full 10-chapter manifesto
        focused_system = f"""You are the Archon writing Chapter {chapter_num} of The Celestial Codex. 
        Synthesize Western Tropical, Vedic Sidereal, Saju (Bazi), and Hellenistic astrology into ONE unified narrative.
        Rules:
        - Cite specific technical evidence: (Sun 24° Gemini, Mercury Dasha, Void Branch 寅)
        - Bold key terms: **Atmakaraka**, **Profection**, **Void Emptiness**
        - When systems conflict, state it explicitly: "While Western suggests expansion, Saju indicates friction"
        - No subheadings for individual systems - weave them into flowing prose"""

        user_prompt = f"CHAPTER {chapter_num} CONTEXT:\n\n{chapter_context}\n\nWrite 300-500 words for Chapter {chapter_num} only."

        return self.generate(
            system_prompt=focused_system,
            user_prompt=user_prompt,
            model=model,
            max_tokens=1500,  # Generous but safe
            temperature=0.7
        )

gateway = LLMGateway()