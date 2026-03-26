"""Quick test script for Fates Engine.

Usage:
    python run.py          # Generate a test report with hardcoded data
    python run.py --api    # Launch FastAPI server
"""
from config import settings


def run_report():
    """Generate a test report with sample birth data."""
    from orchestrator import orchestrator
    from core.compute_pool import shutdown_pool

    print(f"🌟 Fates Engine v{settings.engine_version} — Test Run")
    print("=" * 60)

    try:
        report_path = orchestrator.generate_report(
            birth_datetime="1956-02-04 23:45",
            location="Salin, Magway Region, Myanmar",
            gender="male",
            name="Kyaw Kyaw Wynn",
            output_dir="./reports",
            lat=20.57,
            lon=94.65,
        )
        print(f"\n✨ Report saved to: {report_path}")
    finally:
        shutdown_pool()


def run_api():
    """Launch the FastAPI server."""
    import uvicorn
    print(f"🚀 Fates Engine v{settings.engine_version} — Starting API server")
    print(f"   Host: {settings.api_host}  Port: {settings.api_port}")
    print("=" * 60)
    uvicorn.run("api.main:app", host=settings.api_host, port=settings.api_port, reload=False)


if __name__ == "__main__":
    import sys
    if "--api" in sys.argv:
        run_api()
    else:
        run_report()
