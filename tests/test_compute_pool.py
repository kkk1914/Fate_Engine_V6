"""Tests for core/compute_pool.py — process pool for swe calculations.

Phase 2.4: Verifies pickle safety and worker function contracts.
Tests run actual process pool workers to validate the full serialization path.
"""
import pytest
import pickle
from core.compute_pool import (
    _calculate_western_process,
    _calculate_vedic_process,
    _calculate_saju_process,
    _calculate_hellenistic_process,
    get_compute_pool,
    shutdown_pool,
)


class TestPickleSafety:
    """Verify all worker arguments and return types are picklable."""

    def test_primitive_args_are_picklable(self):
        """All arguments to worker functions must be picklable primitives."""
        args = {
            "jd": 2448058.104,
            "lat": 51.5074,
            "lon": -0.1278,
            "time_known": True,
            "year": 1990,
            "month": 6,
            "day": 15,
            "hour": 14,
            "minute": 30,
            "gender": "male",
            "ephe_path": "./ephe",
            "ayanamsa": "lahiri",
        }
        # This must not raise
        serialized = pickle.dumps(args)
        deserialized = pickle.loads(serialized)
        assert deserialized == args

    def test_western_worker_returns_picklable(self):
        """Western worker return value must be picklable."""
        result = _calculate_western_process(
            jd=2448058.104, lat=51.5074, lon=-0.1278,
            time_known=True, year=1990, ephe_path="./ephe",
        )
        # Must be a dict
        assert isinstance(result, dict)
        # Must be picklable
        serialized = pickle.dumps(result)
        deserialized = pickle.loads(serialized)
        assert isinstance(deserialized, dict)

    def test_hellenistic_worker_returns_picklable(self):
        """Hellenistic worker return value must be picklable."""
        result = _calculate_hellenistic_process(
            jd=2448058.104, lat=51.5074, lon=-0.1278,
            time_known=True, year=1990, ephe_path="./ephe",
        )
        assert isinstance(result, dict)
        serialized = pickle.dumps(result)
        assert pickle.loads(serialized) is not None


class TestProcessPool:
    """Process pool lifecycle tests."""

    def test_pool_creation(self):
        pool = get_compute_pool(max_workers=2)
        assert pool is not None

    def test_pool_reuse(self):
        pool1 = get_compute_pool()
        pool2 = get_compute_pool()
        assert pool1 is pool2

    def test_shutdown(self):
        get_compute_pool()
        shutdown_pool()
        # After shutdown, next call creates new pool
        pool = get_compute_pool()
        assert pool is not None
        shutdown_pool()  # Clean up


class TestWorkerExecution:
    """Run workers in actual subprocess to validate full path."""

    def test_western_in_process_pool(self):
        """Submit Western calc to process pool and verify result."""
        pool = get_compute_pool(max_workers=1)
        future = pool.submit(
            _calculate_western_process,
            2448058.104, 51.5074, -0.1278, True, 1990, "./ephe",
        )
        result = future.result(timeout=30)
        assert isinstance(result, dict)
        # Should have natal placements
        assert "natal" in result
        shutdown_pool()

    def test_hellenistic_in_process_pool(self):
        """Submit Hellenistic calc to process pool and verify result."""
        pool = get_compute_pool(max_workers=1)
        future = pool.submit(
            _calculate_hellenistic_process,
            2448058.104, 51.5074, -0.1278, True, 1990, "./ephe",
        )
        result = future.result(timeout=30)
        assert isinstance(result, dict)
        shutdown_pool()
