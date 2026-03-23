"""Report metadata and idempotency — Phase 3.1.

Generates deterministic report_id from input parameters, stores metadata
alongside reports, and provides an optional Redis-backed idempotency cache.

Usage:
    from core.report_metadata import generate_report_id, ReportMetadata, idempotency_cache

    rid = generate_report_id(birth_datetime="1990-06-15 14:30", location="London, UK")
    meta = ReportMetadata(report_id=rid, ...)
    meta.save_alongside(report_path)

    # Idempotency:
    cached = idempotency_cache.get(rid)
    if cached:
        return cached  # skip regeneration
"""
import hashlib
import json
import time
import logging
from datetime import datetime, timezone
from dataclasses import dataclass, field, asdict
from typing import Optional, Dict, Any, List

from config import settings

logger = logging.getLogger(__name__)


def generate_report_id(
    birth_datetime: str,
    location: str,
    lat: Optional[float] = None,
    lon: Optional[float] = None,
    questions: Optional[List[str]] = None,
    engine_version: Optional[str] = None,
) -> str:
    """Generate deterministic report_id from input parameters.

    Same inputs always produce the same report_id, enabling idempotency.
    Changes to engine_version or questions produce a different ID.
    """
    version = engine_version or settings.engine_version
    q_block = "|".join(sorted(q.strip().lower() for q in (questions or []) if q))

    key = f"{birth_datetime}|{location}|{lat}|{lon}|{version}|{q_block}"
    return hashlib.sha256(key.encode()).hexdigest()[:16]


@dataclass
class ReportMetadata:
    """Metadata stored alongside each generated report."""
    report_id: str
    engine_version: str
    generated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    generation_time_seconds: float = 0.0
    cost_usd: float = 0.0
    total_tokens: int = 0
    total_llm_calls: int = 0
    input_params: Dict[str, Any] = field(default_factory=dict)
    degraded_systems: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def save_alongside(self, report_path: str) -> str:
        """Save metadata as JSON next to the report file.

        Returns path to metadata file.
        """
        meta_path = report_path.rsplit(".", 1)[0] + "_meta.json"
        try:
            with open(meta_path, "w", encoding="utf-8") as f:
                json.dump(self.to_dict(), f, indent=2, ensure_ascii=False)
            logger.info(f"Report metadata saved: {meta_path}")
            return meta_path
        except Exception as e:
            logger.error(f"Failed to save report metadata: {e}")
            return ""


class IdempotencyCache:
    """Redis-backed idempotency cache for report deduplication.

    If Redis is not configured, all operations are no-ops (graceful degradation).

    Cache key: report_id → {storage_path, generated_at, cost_usd}
    Default TTL: 24 hours.
    """

    def __init__(self, redis_url: str = "", ttl_seconds: int = 86400):
        self._redis = None
        self._ttl = ttl_seconds
        if redis_url:
            try:
                import redis
                self._redis = redis.from_url(redis_url, decode_responses=True)
                self._redis.ping()
                logger.info("Idempotency cache connected to Redis")
            except Exception as e:
                logger.warning(f"Redis unavailable for idempotency cache: {e}")
                self._redis = None

    @property
    def enabled(self) -> bool:
        return self._redis is not None

    def get(self, report_id: str) -> Optional[Dict[str, Any]]:
        """Check if a report with this ID already exists."""
        if not self._redis:
            return None
        try:
            data = self._redis.get(f"report:{report_id}")
            if data:
                logger.info(f"Idempotency cache hit: {report_id}")
                return json.loads(data)
        except Exception as e:
            logger.warning(f"Redis get error: {e}")
        return None

    def set(self, report_id: str, storage_path: str, metadata: Dict[str, Any]) -> None:
        """Cache a completed report for idempotency."""
        if not self._redis:
            return
        try:
            cache_data = {
                "storage_path": storage_path,
                "generated_at": datetime.now(timezone.utc).isoformat(),
                **{k: v for k, v in metadata.items()
                   if k in ("cost_usd", "total_tokens", "engine_version")},
            }
            self._redis.setex(
                f"report:{report_id}",
                self._ttl,
                json.dumps(cache_data),
            )
            logger.info(f"Idempotency cache set: {report_id}")
        except Exception as e:
            logger.warning(f"Redis set error: {e}")

    def invalidate(self, report_id: str) -> None:
        """Remove a cached report (e.g., after engine upgrade)."""
        if not self._redis:
            return
        try:
            self._redis.delete(f"report:{report_id}")
        except Exception:
            pass


# Global cache instance — initialized from config
_cache: Optional[IdempotencyCache] = None


def get_idempotency_cache() -> IdempotencyCache:
    """Get or create the global idempotency cache."""
    global _cache
    if _cache is None:
        redis_url = getattr(settings, "redis_url", "")
        _cache = IdempotencyCache(redis_url=redis_url)
    return _cache
