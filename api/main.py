"""FastAPI endpoints for Fates Engine.

Phase 2.2: Async orchestrator for non-blocking report generation.
Phase 2.3: Request semaphore to limit concurrent reports.
Phase 3.3: Streaming SSE endpoint for progressive report delivery.
"""
import asyncio
import json
import os
import re
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any

from config import settings
from core.logging_config import setup_logging, set_request_id

# Initialize structured logging (Phase 1.2)
setup_logging(level=settings.log_level, json_mode=settings.log_json)

import logging
logger = logging.getLogger(__name__)


# ── Request Semaphore (Phase 2.3) ─────────────────────────────────────────
# Limits concurrent report generation to prevent Gemini rate-limit storms.
# 10 concurrent users × 15+ LLM calls = 150+ API calls without throttling.
_report_semaphore: Optional[asyncio.Semaphore] = None


# ── Lifespan (Phase 1.5 + 2.2) ───────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: startup + graceful shutdown."""
    global _report_semaphore
    _report_semaphore = asyncio.Semaphore(settings.max_concurrent_reports)
    logger.info(
        f"Fates Engine v{settings.engine_version} starting "
        f"(max_concurrent_reports={settings.max_concurrent_reports})"
    )
    yield
    # Graceful shutdown: close async gateway HTTP client
    try:
        from experts.gateway_async import async_gateway
        await async_gateway.close()
    except Exception:
        pass
    logger.info("Fates Engine shutting down gracefully")


app = FastAPI(
    title="Fates Engine API",
    description="Multi-system astrological calculation and synthesis engine",
    version=settings.engine_version,
    lifespan=lifespan,
)


# ── Request ID Middleware (Phase 1.2) ─────────────────────────────────────
@app.middleware("http")
async def request_id_middleware(request: Request, call_next):
    """Inject request_id from X-Request-ID header or generate one."""
    rid = request.headers.get("X-Request-ID") or None
    rid = set_request_id(rid)
    response = await call_next(request)
    response.headers["X-Request-ID"] = rid
    return response


# ── Models ────────────────────────────────────────────────────────────────
class ChartRequest(BaseModel):
    birth_datetime: str  # "1990-06-15 14:30"
    location: str        # "London, UK"
    gender: Optional[str] = "unspecified"
    name: Optional[str] = "Unknown"
    output_dir: Optional[str] = "./reports"
    lat: Optional[float] = Field(None, ge=-90, le=90, description="Latitude (-90 to 90)")
    lon: Optional[float] = Field(None, ge=-180, le=180, description="Longitude (-180 to 180)")


class ChartResponse(BaseModel):
    report_path: str
    summary: str
    systems_analyzed: list
    status: str
    degraded_systems: List[str] = []
    engine_version: str = ""
    cost_usd: Optional[float] = None
    token_usage: Optional[Dict[str, Any]] = None
    elapsed_seconds: Optional[float] = None


# ── Endpoints ─────────────────────────────────────────────────────────────
@app.post("/generate", response_model=ChartResponse)
async def generate_report(request: ChartRequest):
    """Generate master astrological report (async with concurrency control).

    Uses the async orchestrator for non-blocking I/O. Reports are queued
    behind a semaphore — if max_concurrent_reports slots are full, the
    request waits up to queue_timeout seconds before returning HTTP 429.
    """
    t_start = time.time()

    # Phase 2.3: Acquire semaphore with timeout
    try:
        acquired = await asyncio.wait_for(
            _report_semaphore.acquire(),
            timeout=settings.queue_timeout,
        )
    except asyncio.TimeoutError:
        raise HTTPException(
            status_code=429,
            detail=f"Server busy — {settings.max_concurrent_reports} reports already in progress. "
                   f"Try again in a few minutes.",
        )

    try:
        # Phase 2.2: Use async orchestrator
        from orchestrator_async import async_orchestrator

        path = await async_orchestrator.generate_report_async(
            birth_datetime=request.birth_datetime,
            location=request.location,
            gender=request.gender,
            name=request.name,
            output_dir=request.output_dir,
            lat=request.lat,
            lon=request.lon,
        )

        degraded = async_orchestrator.last_degraded_systems
        cost_summary = async_orchestrator.last_cost_summary
        elapsed = round(time.time() - t_start, 1)

        return {
            "report_path": path,
            "summary": "Multi-system analysis complete (Western/Vedic_engine/Saju/Hellenistic)",
            "systems_analyzed": ["Western", "Vedic_engine", "Saju", "Hellenistic"],
            "status": "success" if not degraded else "degraded",
            "degraded_systems": degraded,
            "engine_version": settings.engine_version,
            "cost_usd": cost_summary.get("total_cost_usd"),
            "token_usage": {
                "total_tokens": cost_summary.get("total_tokens", 0),
                "total_calls": cost_summary.get("total_calls", 0),
                "by_phase": cost_summary.get("by_phase", {}),
            } if cost_summary else None,
            "elapsed_seconds": elapsed,
        }
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        logger.error(f"Report generation failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        _report_semaphore.release()


@app.post("/generate/stream")
async def generate_report_stream(request: ChartRequest):
    """Generate report with Server-Sent Events for progressive delivery.

    Phase 3.3: Client receives status events during calculation, then
    section content as each completes. Enables progressive rendering.

    Event types:
      - status: {"phase": "...", "message": "..."}
      - section: {"index": N, "title": "...", "content": "..."}
      - complete: {"report_path": "...", "elapsed_seconds": N}
      - error: {"detail": "..."}
    """
    from sse_starlette.sse import EventSourceResponse

    async def event_generator():
        t_start = time.time()

        # Acquire semaphore
        try:
            acquired = await asyncio.wait_for(
                _report_semaphore.acquire(),
                timeout=settings.queue_timeout,
            )
        except asyncio.TimeoutError:
            yield {"event": "error", "data": json.dumps({
                "detail": "Server busy — try again later"
            })}
            return

        try:
            yield {"event": "status", "data": json.dumps({
                "phase": "init", "message": "Initializing calculation engines..."
            })}

            from orchestrator_async import async_orchestrator

            # Layer 1: Calculations
            yield {"event": "status", "data": json.dumps({
                "phase": "calculation", "message": "Computing planetary positions (4 systems)..."
            })}

            chart_data = await asyncio.to_thread(
                async_orchestrator._sync._calculate_charts,
                request.birth_datetime, request.location,
                request.gender or "unspecified",
                lat=request.lat, lon=request.lon,
            )

            yield {"event": "status", "data": json.dumps({
                "phase": "calculation", "message": "Chart calculations complete"
            })}

            # Layer 2: Expert analysis
            yield {"event": "status", "data": json.dumps({
                "phase": "experts", "message": "Running expert analysis (4 concurrent)..."
            })}

            # Run full report generation (non-streaming internally)
            path = await async_orchestrator.generate_report_async(
                birth_datetime=request.birth_datetime,
                location=request.location,
                gender=request.gender,
                name=request.name,
                output_dir=request.output_dir,
                lat=request.lat,
                lon=request.lon,
            )

            yield {"event": "status", "data": json.dumps({
                "phase": "complete", "message": "Report generation complete"
            })}

            # Stream the report content section by section
            if path and os.path.exists(path):
                with open(path, "r", encoding="utf-8") as f:
                    content = f.read()

                # Split by section headers (# or ##)
                sections = re.split(r'(?=^#{1,2}\s)', content, flags=re.MULTILINE)
                for i, section in enumerate(sections):
                    if section.strip():
                        # Extract title from first line
                        first_line = section.strip().split("\n")[0].strip("# ").strip()
                        yield {"event": "section", "data": json.dumps({
                            "index": i,
                            "title": first_line[:100],
                            "content": section,
                        })}

            elapsed = round(time.time() - t_start, 1)
            degraded = async_orchestrator.last_degraded_systems
            cost_summary = async_orchestrator.last_cost_summary

            yield {"event": "complete", "data": json.dumps({
                "report_path": path,
                "elapsed_seconds": elapsed,
                "status": "success" if not degraded else "degraded",
                "cost_usd": cost_summary.get("total_cost_usd"),
                "engine_version": settings.engine_version,
            })}

        except Exception as e:
            logger.error(f"Streaming generation failed: {e}", exc_info=True)
            yield {"event": "error", "data": json.dumps({"detail": str(e)})}
        finally:
            _report_semaphore.release()

    return EventSourceResponse(event_generator())


@app.get("/reports/{report_id}")
async def get_report(report_id: str):
    """Retrieve a previously generated report by its deterministic ID.

    Phase 3.1: Reports are keyed by a SHA-256 hash of input parameters.
    Same inputs → same report_id → cache hit.
    """
    from core.report_metadata import get_idempotency_cache

    cache = get_idempotency_cache()
    cached = cache.get(report_id)
    if not cached:
        raise HTTPException(status_code=404, detail=f"Report {report_id} not found or expired")

    storage_path = cached.get("storage_path", "")
    if storage_path and os.path.exists(storage_path):
        try:
            with open(storage_path, "r", encoding="utf-8") as f:
                content = f.read()
            return {
                "report_id": report_id,
                "storage_path": storage_path,
                "content_length": len(content),
                "generated_at": cached.get("generated_at"),
                "engine_version": cached.get("engine_version"),
                "content_preview": content[:500],
            }
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error reading report: {e}")
    else:
        raise HTTPException(status_code=404, detail=f"Report file not found at {storage_path}")


@app.get("/health")
async def health_check():
    """Liveness probe — always returns if the process is running."""
    ephe_exists = os.path.exists(os.path.abspath(settings.ephe_path))
    api_key_set = bool(settings.google_api_key)

    return {
        "status": "operational" if (ephe_exists and api_key_set) else "degraded",
        "engine_version": settings.engine_version,
        "ephemeris_available": ephe_exists,
        "api_key_configured": api_key_set,
    }


@app.get("/ready")
async def readiness_check():
    """Readiness probe — checks if dependencies are available."""
    from experts.gateway import gateway

    gateway_ready = gateway.client is not None
    ephe_exists = os.path.exists(os.path.abspath(settings.ephe_path))

    ready = gateway_ready and ephe_exists
    status_code = 200 if ready else 503

    return JSONResponse(
        status_code=status_code,
        content={
            "ready": ready,
            "engine_version": settings.engine_version,
            "checks": {
                "llm_gateway": "ok" if gateway_ready else "no_api_key",
                "ephemeris": "ok" if ephe_exists else "missing",
            },
        },
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=settings.api_host, port=settings.api_port)
