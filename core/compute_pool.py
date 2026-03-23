"""Process pool for true memory isolation of swe calculations.

Phase 2.4: Each worker process gets its own copy of the C library's global
state, enabling true parallelism between tropical and sidereal calculations.

PICKLE SAFETY CONTRACT:
- All arguments MUST be pure primitives: float, int, str, bool
- All return values MUST be pure dicts/lists/primitives
- Engine classes are instantiated INSIDE the worker (NOT passed as arguments)
- No open file handles, thread locks, or database connections cross the boundary

Usage:
    from core.compute_pool import compute_pool, submit_western, submit_vedic

    # In async orchestrator:
    loop = asyncio.get_event_loop()
    future = loop.run_in_executor(compute_pool, _calculate_western_process, jd, lat, lon, ...)
"""
import os
import logging
from concurrent.futures import ProcessPoolExecutor
from typing import Dict, Any, Optional

from config import settings

logger = logging.getLogger(__name__)

# ── Top-Level Worker Functions ────────────────────────────────────────────
# MUST be importable top-level functions (not closures or methods).
# multiprocessing requires all arguments and return values to be picklable.


def _calculate_western_process(
    jd: float, lat: float, lon: float, time_known: bool, year: int,
    ephe_path: str,
) -> Dict[str, Any]:
    """Calculate Western chart in an isolated process.

    Instantiates its own WesternEngine — no shared state with main process.
    """
    import swisseph as swe
    swe.set_ephe_path(os.path.abspath(ephe_path))

    from systems.western import WesternEngine
    engine = WesternEngine()
    return engine.calculate(jd, lat, lon, time_known, year)


def _calculate_vedic_process(
    jd: float, lat: float, lon: float, time_known: bool,
    year: int, month: int, day: int, hour: int, minute: int,
    ephe_path: str, ayanamsa: str,
) -> Dict[str, Any]:
    """Calculate Vedic chart in an isolated process."""
    import swisseph as swe
    from datetime import datetime
    swe.set_ephe_path(os.path.abspath(ephe_path))

    dt = datetime(year, month, day, hour, minute)

    from systems.vedic import calculate_vedic
    try:
        return calculate_vedic(jd, lat, lon, time_known, dt)
    except Exception as e:
        logger.error(f"[process] Vedic calculation error: {e}")
        return {"natal": {"placements": {}}, "predictive": {}, "strength": {}}


def _calculate_saju_process(
    year: int, month: int, day: int, hour: int, minute: int,
    time_known: bool, gender: str, jd: float, lon: float,
    ephe_path: str,
) -> Dict[str, Any]:
    """Calculate Saju/Bazi chart in an isolated process."""
    import swisseph as swe
    from datetime import datetime
    swe.set_ephe_path(os.path.abspath(ephe_path))

    dt = datetime(year, month, day, hour, minute)

    from systems.saju import calculate_bazi
    try:
        return calculate_bazi(dt, time_known, gender, jd, lon=lon)
    except Exception as e:
        logger.error(f"[process] Saju calculation error: {e}")
        return {"natal": {}, "strength": {}, "predictive": {}}


def _calculate_hellenistic_process(
    jd: float, lat: float, lon: float, time_known: bool, year: int,
    ephe_path: str,
) -> Dict[str, Any]:
    """Calculate Hellenistic chart in an isolated process."""
    import swisseph as swe
    swe.set_ephe_path(os.path.abspath(ephe_path))

    from systems.hellenistic import HellenisticEngine
    engine = HellenisticEngine()
    try:
        return engine.calculate(jd, lat, lon, time_known, year)
    except Exception as e:
        logger.error(f"[process] Hellenistic calculation error: {e}")
        return {"lots": {}, "zodiacal_releasing": {}, "annual_profections": {}}


# ── Process Pool Management ──────────────────────────────────────────────

# Global process pool — initialized lazily at first use
_pool: Optional[ProcessPoolExecutor] = None


def get_compute_pool(max_workers: int = 3) -> ProcessPoolExecutor:
    """Get or create the global process pool.

    max_workers=3: one per system pair is sufficient. ~100ms creation overhead
    + serialization cost is acceptable for the 3-5s calculation phase.
    """
    global _pool
    if _pool is None or _pool._broken:
        _pool = ProcessPoolExecutor(max_workers=max_workers)
        logger.info(f"Process pool initialized with {max_workers} workers")
    return _pool


def shutdown_pool():
    """Shutdown the process pool gracefully."""
    global _pool
    if _pool is not None:
        _pool.shutdown(wait=True)
        _pool = None
        logger.info("Process pool shut down")
