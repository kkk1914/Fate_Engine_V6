"""FastAPI endpoints for Fates Engine."""
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional
from orchestrator import orchestrator

app = FastAPI(
    title="Fates Engine API",
    description="Multi-system astrological calculation and synthesis using GPT-5.2",
    version="1.0.0"
)

class ChartRequest(BaseModel):
    birth_datetime: str  # "1990-06-15 14:30"
    location: str        # "London, UK"
    gender: Optional[str] = "unspecified"
    name: Optional[str] = "Unknown"
    output_dir: Optional[str] = "./reports"

class ChartResponse(BaseModel):
    report_path: str
    summary: str
    systems_analyzed: list
    status: str

@app.post("/generate", response_model=ChartResponse)
async def generate_report(request: ChartRequest):
    """Generate master astrological report."""
    try:
        path = orchestrator.generate_report(
            birth_datetime=request.birth_datetime,
            location=request.location,
            gender=request.gender,
            name=request.name,
            output_dir=request.output_dir
        )

        return {
            "report_path": path,
            "summary": "Multi-system analysis complete (Western/Vedic_engine/Saju/Hellenistic)",
            "systems_analyzed": ["Western", "Vedic_engine", "Saju", "Hellenistic"],
            "status": "success"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "operational",
        "engine": "Fates Core v1.0",
        "models": ["gpt-5.2", "gpt-5.2-pro"]
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)