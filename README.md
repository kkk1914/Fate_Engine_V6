# Fates Engine Core v1.0

**World-Class Multi-System Astrological Analysis**

A professional-grade astrology engine synthesizing Western Tropical, Vedic Sidereal, Chinese Bazi (Saju), and Hellenistic techniques using GPT-5.2 for intelligent report generation.

## 🏗️ Architecture
Layer 0: Data Foundation (Swiss Ephemeris, 0.001" precision)
Layer 1: Multi-System Calculation (Western/Vedic/Saju/Hellenistic)
Layer 2: Neo4j Knowledge Graph (Cross-system relationships)
Layer 3: Oracle Intelligence (Pattern matching, conflict detection)
Layer 4: Expert LLM Swarm (GPT-5.2 specialized agents)
Layer 5: The Arbiter (Reconciliation & synthesis)
Layer 6: The Archon (Master narrative generation)


## 🚀 Quick Start

### Prerequisites
- Python 3.10+
- OpenAI API key (with GPT-5.2 access)
- Neo4j AuraDB account (free tier works)
- Swiss Ephemeris files

### 1. Environment Setup

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
    pip install -r requirements.txt


## Command-Line Usage

    ```bash
    
    python cli.py generate -b "1990-06-15 14:30" -l "London, UK" -n "Sarah"

# With gender for Bazi
    python cli.py generate -b "1985-03-20 08:30" -l "New York, USA" -g "female" -n "Alex"

# Custom output directory
    python cli.py generate -b "1992-11-15 14:00" -l "Tokyo, Japan" -n "Yuki" -o "./my_reports"



# FastAPI Server

    python api/main.py
    
    # Or: uvicorn api.main:app --host 0.0.0.0 --port 8000

    # Test with curl:
    
    curl -X POST "http://localhost:8000/generate" \
      -H "Content-Type: application/json" \
      -d '{
        "birth_datetime": "1990-06-15 14:30",
        "location": "London, UK",
        "name": "Sarah",
        "gender": "female"
      }'



##Python API

from orchestrator import orchestrator

report_path = orchestrator.generate_report(
    birth_datetime="1990-06-15 14:30",
    location="London, UK",
    gender="female",
    name="Sarah",
    output_dir="./reports"
)
print(f"Report saved to: {report_path}")



