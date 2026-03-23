"""Configuration management for Fates Engine."""
from pydantic_settings import BaseSettings
from pydantic import ConfigDict
from typing import Optional, List
import os
import warnings

class Settings(BaseSettings):
    model_config = ConfigDict(env_file=".env", env_file_encoding="utf-8")

    # Neo4j AuraDB Configuration
    neo4j_uri: str = "neo4j+s://your-instance.databases.neo4j.io"
    neo4j_user: str = "neo4j"
    neo4j_password: str = ""

    # API Keys
    # Set GOOGLE_API_KEY in your .env file.
    # OPENAI_API_KEY is optional — only needed if you keep any gpt-* models.
    google_api_key: str = ""
    openai_api_key: str = ""
    default_reasoning_effort: str = "medium"

    # Model Assignments
    # Experts  @ gemini-2.5-flash        : $0.15/$0.60 per 1M tokens (thinking enabled)
    # Arbiter  @ gemini-3-flash-preview   : $0.50/$3.00 per 1M tokens
    # Archon   @ gemini-2.5-pro           : $1.25/$10.00 per 1M tokens
    # NOTE: flash-lite silently ignores reasoning_effort — experts MUST use 2.5-flash+
    western_expert_model:     str = "gemini-2.5-flash"
    vedic_expert_model:       str = "gemini-2.5-flash"
    saju_expert_model:        str = "gemini-2.5-flash"
    hellenistic_expert_model: str = "gemini-2.5-flash"
    arbiter_model:            str = "gemini-3-flash-preview"
    archon_model:             str = "gemini-2.5-pro"
    translation_model:        str = "gemini-2.5-flash"

    # Multi-Model Ensemble (2 calls + judge per expert — higher quality, 3x cost)
    # Default False: exemplars + graph rules + prediction engine already eliminate
    # the variance the ensemble was designed to solve. Set True for A/B testing.
    ensemble_mode: bool = False

    # Report Language ("en" = English, "my" = Burmese/Myanmar)
    report_language: str = "en"

    # Report Parts to generate (I=Nativity, II=Almanac, III=Directive, IV=Questions)
    # Generate all by default. Set to subset like ["I", "IV"] for targeted reports.
    # Pipeline quality is NOT affected — all chart computations still run regardless.
    include_parts: List[str] = ["I", "II", "III", "IV"]

    # Include PART III: THE DIRECTIVE (sections 12-13: Fifteen-Year Directive + Warning)
    # Set False to skip — saves 2 Archon LLM calls (~8000 tokens @ gemini-2.5-pro)
    # Legacy alias — if False AND "III" is in include_parts, "III" is removed.
    include_directive: bool = False

    # Ayanamsa (sidereal mode for Vedic calculations)
    # Options: lahiri, raman, krishnamurti, de_luce, yukteswar
    ayanamsa: str = "lahiri"

    # Ephemeris Path
    ephe_path: str = "./ephe"

    # API Settings
    api_host: str = "0.0.0.0"
    api_port: int = 8000

    # Logging (Phase 1.2)
    log_level: str = "INFO"
    log_json: bool = False  # True for structured JSON logs (production/Docker)

    # Storage Backend (Phase 1.4)
    # "local" = filesystem (default), "gcs" = Google Cloud Storage
    storage_backend: str = "local"
    gcs_bucket: str = ""

    # Engine Version (Phase 1.5)
    engine_version: str = "3.0.0"

    # Redis (Phase 3.1: idempotency cache, geocoding cache)
    # If empty, Redis features are disabled (graceful degradation).
    redis_url: str = ""

    # Concurrency Control (Phase 2.3)
    # Max concurrent report generations behind the API semaphore.
    # 10 users × 15+ LLM calls = 150+ concurrent API calls → Gemini rate limits.
    max_concurrent_reports: int = 3
    # Seconds to wait for a semaphore slot before returning HTTP 429.
    queue_timeout: int = 300

    # Test Mode (skip API calls if True)
    test_mode: bool = False

    def validate(self):
        """Validate settings with graceful degradation."""
        if not self.google_api_key and not self.openai_api_key and not self.test_mode:
            warnings.warn(
                "Neither GOOGLE_API_KEY nor OPENAI_API_KEY is set in .env. "
                "Add GOOGLE_API_KEY=your_key to your .env file."
            )
            self.test_mode = True

settings = Settings()
settings.validate()
