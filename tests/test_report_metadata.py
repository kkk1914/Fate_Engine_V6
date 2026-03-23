"""Tests for core/report_metadata.py — Phase 3.1.

Covers report_id generation, metadata serialization, and
idempotency cache (without Redis — graceful degradation).
"""
import pytest
import os
import json
import tempfile
from core.report_metadata import (
    generate_report_id,
    ReportMetadata,
    IdempotencyCache,
)


class TestReportIdGeneration:
    """Deterministic report_id from input parameters."""

    def test_same_inputs_same_id(self):
        id1 = generate_report_id("1990-06-15 14:30", "London, UK")
        id2 = generate_report_id("1990-06-15 14:30", "London, UK")
        assert id1 == id2

    def test_different_inputs_different_id(self):
        id1 = generate_report_id("1990-06-15 14:30", "London, UK")
        id2 = generate_report_id("1990-06-15 14:30", "Paris, France")
        assert id1 != id2

    def test_different_questions_different_id(self):
        id1 = generate_report_id("1990-06-15 14:30", "London, UK",
                                  questions=["Will I get rich?"])
        id2 = generate_report_id("1990-06-15 14:30", "London, UK",
                                  questions=["When will I marry?"])
        assert id1 != id2

    def test_question_order_independent(self):
        """Questions are sorted, so order doesn't matter."""
        id1 = generate_report_id("1990-06-15 14:30", "London, UK",
                                  questions=["career", "wealth"])
        id2 = generate_report_id("1990-06-15 14:30", "London, UK",
                                  questions=["wealth", "career"])
        assert id1 == id2

    def test_different_engine_version_different_id(self):
        id1 = generate_report_id("1990-06-15 14:30", "London, UK",
                                  engine_version="2.1.0")
        id2 = generate_report_id("1990-06-15 14:30", "London, UK",
                                  engine_version="2.2.0")
        assert id1 != id2

    def test_id_is_hex_string(self):
        rid = generate_report_id("1990-06-15 14:30", "London, UK")
        assert len(rid) == 16
        assert all(c in "0123456789abcdef" for c in rid)

    def test_none_questions_stable(self):
        id1 = generate_report_id("1990-06-15 14:30", "London, UK", questions=None)
        id2 = generate_report_id("1990-06-15 14:30", "London, UK", questions=[])
        assert id1 == id2


class TestReportMetadata:
    """Metadata serialization and file saving."""

    def test_to_dict(self):
        meta = ReportMetadata(
            report_id="abc123",
            engine_version="2.2.0",
            cost_usd=3.45,
            total_tokens=50000,
        )
        d = meta.to_dict()
        assert d["report_id"] == "abc123"
        assert d["cost_usd"] == 3.45
        assert d["total_tokens"] == 50000
        assert "generated_at" in d

    def test_save_alongside(self):
        with tempfile.NamedTemporaryFile(suffix=".md", delete=False, mode="w") as f:
            f.write("test report")
            report_path = f.name

        try:
            meta = ReportMetadata(
                report_id="test123",
                engine_version="2.2.0",
            )
            meta_path = meta.save_alongside(report_path)
            assert meta_path.endswith("_meta.json")
            assert os.path.exists(meta_path)

            with open(meta_path, "r") as f:
                saved = json.load(f)
            assert saved["report_id"] == "test123"
        finally:
            os.unlink(report_path)
            if os.path.exists(meta_path):
                os.unlink(meta_path)


class TestIdempotencyCacheNoRedis:
    """Idempotency cache graceful degradation without Redis."""

    def test_disabled_without_redis(self):
        cache = IdempotencyCache(redis_url="")
        assert not cache.enabled

    def test_get_returns_none(self):
        cache = IdempotencyCache(redis_url="")
        assert cache.get("any_id") is None

    def test_set_is_noop(self):
        cache = IdempotencyCache(redis_url="")
        cache.set("id", "/path", {})  # Should not raise

    def test_invalidate_is_noop(self):
        cache = IdempotencyCache(redis_url="")
        cache.invalidate("id")  # Should not raise
