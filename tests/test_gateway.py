"""Tests for experts/gateway.py — LLM gateway.

Phase 1.7: Tests gateway initialization, error handling, and telemetry
recording. Does NOT make actual API calls (uses mocked client).
"""
import pytest
import json
from unittest.mock import MagicMock, patch, PropertyMock
from core.telemetry import init_cost_tracker, get_cost_tracker


class TestGatewayInit:
    """Gateway initialization tests."""

    def test_gateway_without_api_key(self):
        """Gateway should initialize with client=None when no API key."""
        with patch("experts.gateway.settings") as mock_settings:
            mock_settings.google_api_key = ""
            from experts.gateway import LLMGateway
            gw = LLMGateway()
            assert gw.client is None

    def test_check_ready_returns_error_without_client(self):
        """_check_ready() returns error dict when client is None."""
        from experts.gateway import LLMGateway
        gw = LLMGateway.__new__(LLMGateway)
        gw.client = None
        err = gw._check_ready()
        assert err is not None
        assert err["success"] is False


class TestGenerateErrorHandling:
    """Error handling in generate() method."""

    def test_generate_returns_error_without_client(self):
        """generate() returns error when client is None."""
        from experts.gateway import LLMGateway
        gw = LLMGateway.__new__(LLMGateway)
        gw.client = None
        result = gw.generate(
            system_prompt="test",
            user_prompt="test",
        )
        assert result["success"] is False

    def test_structured_generate_returns_error_without_client(self):
        """structured_generate() returns error when client is None."""
        from experts.gateway import LLMGateway
        gw = LLMGateway.__new__(LLMGateway)
        gw.client = None
        result = gw.structured_generate(
            system_prompt="test",
            user_prompt="test",
            output_schema={"type": "object"},
        )
        assert result["success"] is False

    def test_structured_generate_rejects_oversized_prompt(self):
        """Prompts exceeding 120K estimated tokens are rejected."""
        from experts.gateway import LLMGateway
        gw = LLMGateway.__new__(LLMGateway)
        gw.client = MagicMock()  # Needs non-None client to pass _check_ready
        result = gw.structured_generate(
            system_prompt="x" * 200_000,
            user_prompt="x" * 300_000,
            output_schema={"type": "object"},
        )
        assert result["success"] is False
        assert "too large" in result["error"].lower()


class TestTelemetryRecording:
    """Verify cost telemetry is recorded on successful calls."""

    def test_generate_records_telemetry(self):
        """generate() should record cost to the CostTracker."""
        from experts.gateway import LLMGateway

        # Setup cost tracker
        tracker = init_cost_tracker(request_id="test-123")

        # Create gateway with mocked client
        gw = LLMGateway.__new__(LLMGateway)
        mock_client = MagicMock()
        gw.client = mock_client

        # Mock the response
        mock_response = MagicMock()
        mock_response.text = "Test response"
        mock_response.usage_metadata = MagicMock()
        mock_response.usage_metadata.prompt_token_count = 500
        mock_response.usage_metadata.candidates_token_count = 200
        mock_client.models.generate_content.return_value = mock_response

        result = gw.generate(
            system_prompt="test system",
            user_prompt="test user",
            model="gemini-2.5-flash",
            phase="expert",
        )

        assert result["success"] is True
        assert len(tracker.calls) == 1
        assert tracker.calls[0].model == "gemini-2.5-flash"
        assert tracker.calls[0].input_tokens == 500
        assert tracker.calls[0].output_tokens == 200
        assert tracker.calls[0].phase == "expert"

    def test_structured_generate_records_telemetry(self):
        """structured_generate() should record cost to the CostTracker."""
        from experts.gateway import LLMGateway

        tracker = init_cost_tracker(request_id="test-456")

        gw = LLMGateway.__new__(LLMGateway)
        mock_client = MagicMock()
        gw.client = mock_client

        mock_response = MagicMock()
        mock_response.text = '{"result": "ok"}'
        mock_response.usage_metadata = MagicMock()
        mock_response.usage_metadata.prompt_token_count = 300
        mock_response.usage_metadata.candidates_token_count = 100
        mock_client.models.generate_content.return_value = mock_response

        result = gw.structured_generate(
            system_prompt="test",
            user_prompt="test",
            output_schema={"type": "object", "properties": {"result": {"type": "string"}}},
            model="gemini-2.5-pro",
            phase="arbiter",
        )

        assert result["success"] is True
        assert len(tracker.calls) == 1
        assert tracker.calls[0].model == "gemini-2.5-pro"
        assert tracker.calls[0].phase == "arbiter"


class TestThinkingConfig:
    """Verify thinking config builder."""

    def test_flash_lite_no_thinking(self):
        """flash-lite should never get thinking config."""
        from experts.gateway import _supports_thinking
        assert not _supports_thinking("gemini-2.5-flash-lite")

    def test_flash_supports_thinking(self):
        """gemini-2.5-flash supports thinking."""
        from experts.gateway import _supports_thinking
        assert _supports_thinking("gemini-2.5-flash")

    def test_pro_supports_thinking(self):
        """gemini-2.5-pro supports thinking."""
        from experts.gateway import _supports_thinking
        assert _supports_thinking("gemini-2.5-pro")

    def test_build_thinking_config_none_effort(self):
        """No reasoning_effort → no thinking config."""
        from experts.gateway import _build_thinking_config
        result = _build_thinking_config("gemini-2.5-pro", None)
        assert result is None

    def test_build_thinking_config_medium(self):
        """Medium effort → budget 1024."""
        from experts.gateway import _build_thinking_config
        result = _build_thinking_config("gemini-2.5-pro", "medium")
        assert result is not None
        assert result.thinking_budget == 1024
