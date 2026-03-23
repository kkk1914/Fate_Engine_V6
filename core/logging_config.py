"""Structured logging with request-scoped tracing.

Phase 1.2: JSON-formatted logs with contextvar-based request_id propagation.
Every log line includes the request_id when set, enabling grep-based tracing
of concurrent reports.

Usage:
    from core.logging_config import setup_logging, set_request_id, get_request_id

    setup_logging()  # Call once at startup
    set_request_id("abc-123")  # Call at start of each request
"""
import logging
import json
import sys
from contextvars import ContextVar
from datetime import datetime, timezone
from typing import Optional
from uuid import uuid4

# ── Request ID propagation ─────────────────────────────────────────────────
# ContextVar is async-safe: each asyncio task inherits the parent's value,
# and ThreadPoolExecutor.submit() copies contextvars automatically in Python 3.12+.
_request_id: ContextVar[Optional[str]] = ContextVar("request_id", default=None)


def set_request_id(rid: Optional[str] = None) -> str:
    """Set (or generate) a request ID for the current context. Returns the ID."""
    rid = rid or uuid4().hex[:12]
    _request_id.set(rid)
    return rid


def get_request_id() -> Optional[str]:
    """Get the current request ID, or None if not set."""
    return _request_id.get()


class JSONFormatter(logging.Formatter):
    """Structured JSON log formatter with request_id injection."""

    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }

        # Inject request_id if present
        rid = _request_id.get()
        if rid:
            log_entry["request_id"] = rid

        # Include exception info if present
        if record.exc_info and record.exc_info[0] is not None:
            log_entry["exception"] = self.formatException(record.exc_info)

        # Include any extra fields attached to the record
        for key in ("model", "tokens", "cost_usd", "phase", "latency_ms"):
            val = getattr(record, key, None)
            if val is not None:
                log_entry[key] = val

        return json.dumps(log_entry, ensure_ascii=False)


class HumanFormatter(logging.Formatter):
    """Human-readable formatter for CLI usage. Includes request_id when set."""

    def format(self, record: logging.LogRecord) -> str:
        rid = _request_id.get()
        rid_prefix = f"[{rid}] " if rid else ""
        ts = datetime.now(timezone.utc).strftime("%H:%M:%S")
        msg = f"{ts} {record.levelname:<7} {rid_prefix}{record.name}: {record.getMessage()}"
        if record.exc_info and record.exc_info[0] is not None:
            msg += "\n" + self.formatException(record.exc_info)
        return msg


def setup_logging(level: str = "INFO", json_mode: bool = False) -> None:
    """Configure root logger with structured or human-readable output.

    Args:
        level: Log level string (DEBUG, INFO, WARNING, ERROR).
        json_mode: If True, emit JSON lines. If False, emit human-readable lines.
    """
    root = logging.getLogger()

    # Clear existing handlers to avoid duplicates on re-init
    root.handlers.clear()

    handler = logging.StreamHandler(sys.stderr)
    if json_mode:
        handler.setFormatter(JSONFormatter())
    else:
        handler.setFormatter(HumanFormatter())

    root.addHandler(handler)
    root.setLevel(getattr(logging, level.upper(), logging.INFO))

    # Quiet noisy third-party loggers
    for noisy in ("httpx", "httpcore", "urllib3", "google", "neo4j"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
