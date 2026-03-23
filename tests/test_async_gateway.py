"""Tests for experts/gateway_async.py — async LLM gateway.

Phase 2.1: Tests async gateway initialization, error handling,
REST API payload construction, and response parsing.
Does NOT make actual API calls.
"""
import pytest
import json
from unittest.mock import AsyncMock, MagicMock, patch
from experts.gateway_async import (
    AsyncLLMGateway, _supports_thinking, _build_generation_config,
)


class TestThinkingConfig:
    """Verify thinking config for REST API."""

    def test_flash_lite_no_thinking(self):
        assert not _supports_thinking("gemini-2.5-flash-lite")

    def test_flash_supports(self):
        assert _supports_thinking("gemini-2.5-flash")

    def test_pro_supports(self):
        assert _supports_thinking("gemini-2.5-pro")


class TestGenerationConfig:
    """Verify REST API generation config builder."""

    def test_basic_config(self):
        config = _build_generation_config("gemini-2.5-flash", 2000, 0.7, 42)
        assert config["maxOutputTokens"] == 2000
        assert config["seed"] == 42
        assert config["temperature"] == 0.7

    def test_flash_lite_no_temperature(self):
        config = _build_generation_config("gemini-2.5-flash-lite", 2000, 0.7, 42)
        assert "temperature" not in config

    def test_json_mode(self):
        config = _build_generation_config(
            "gemini-2.5-flash", 2000, 0.7, 42,
            response_mime_type="application/json",
        )
        assert config["responseMimeType"] == "application/json"

    def test_thinking_budget(self):
        config = _build_generation_config(
            "gemini-2.5-pro", 2000, 0.7, 42,
            reasoning_effort="high",
        )
        assert config["thinkingConfig"]["thinkingBudget"] == 2048

    def test_no_thinking_for_lite(self):
        config = _build_generation_config(
            "gemini-2.5-flash-lite", 2000, 0.7, 42,
            reasoning_effort="high",
        )
        assert "thinkingConfig" not in config


class TestAsyncGatewayInit:
    """Initialization tests."""

    def test_no_api_key(self):
        with patch("experts.gateway_async.settings") as mock_settings:
            mock_settings.google_api_key = ""
            gw = AsyncLLMGateway()
            err = gw._check_ready()
            assert err is not None
            assert err["success"] is False

    def test_with_api_key(self):
        with patch("experts.gateway_async.settings") as mock_settings:
            mock_settings.google_api_key = "test-key"
            gw = AsyncLLMGateway()
            assert gw._check_ready() is None


class TestResponseParsing:
    """Test static helper methods."""

    def test_extract_text(self):
        data = {
            "candidates": [{
                "content": {
                    "parts": [{"text": "Hello world"}]
                }
            }]
        }
        assert AsyncLLMGateway._extract_text(data) == "Hello world"

    def test_extract_text_empty(self):
        assert AsyncLLMGateway._extract_text({}) == ""
        assert AsyncLLMGateway._extract_text({"candidates": []}) == ""

    def test_extract_usage(self):
        data = {
            "usageMetadata": {
                "promptTokenCount": 500,
                "candidatesTokenCount": 200,
            }
        }
        input_t, output_t = AsyncLLMGateway._extract_usage(data)
        assert input_t == 500
        assert output_t == 200

    def test_extract_usage_missing(self):
        input_t, output_t = AsyncLLMGateway._extract_usage({})
        assert input_t == 0
        assert output_t == 0

    def test_clean_json_plain(self):
        assert AsyncLLMGateway._clean_json('{"key": "value"}') == '{"key": "value"}'

    def test_clean_json_fenced(self):
        raw = '```json\n{"key": "value"}\n```'
        assert AsyncLLMGateway._clean_json(raw) == '{"key": "value"}'

    def test_clean_json_double_fenced(self):
        raw = '```\n{"key": "value"}\n```'
        assert AsyncLLMGateway._clean_json(raw) == '{"key": "value"}'


class TestAsyncGatewayErrors:
    """Error path tests (no actual API calls)."""

    @pytest.mark.asyncio
    async def test_generate_no_api_key(self):
        gw = AsyncLLMGateway()
        gw.api_key = ""
        result = await gw.generate("sys", "user")
        assert result["success"] is False

    @pytest.mark.asyncio
    async def test_structured_generate_no_api_key(self):
        gw = AsyncLLMGateway()
        gw.api_key = ""
        result = await gw.structured_generate("sys", "user", {"type": "object"})
        assert result["success"] is False

    @pytest.mark.asyncio
    async def test_structured_generate_too_large(self):
        gw = AsyncLLMGateway()
        gw.api_key = "test-key"
        result = await gw.structured_generate(
            "x" * 200_000, "x" * 300_000, {"type": "object"},
        )
        assert result["success"] is False
        assert "too large" in result["error"].lower()
