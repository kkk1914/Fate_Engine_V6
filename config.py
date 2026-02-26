"""Configuration management for Fates Engine."""
from pydantic_settings import BaseSettings
from typing import Optional
import os
import warnings

class Settings(BaseSettings):
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
    # COST: ~$0.35/run vs $0.74 with gpt-5.2 (53% cheaper)
    # Experts  @ gemini-2.5-flash-lite : $0.10/$0.40 per 1M tokens
    # Arbiter  @ gemini-3-flash-preview : $0.50/$3.00 per 1M tokens
    # Archon   @ gemini-2.5-pro         : $1.25/$10.00 per 1M tokens
    # NOTE: Switch archon_model to "gemini-3.1-pro-preview" when stable (Q2 2026)
    western_expert_model:     str = "gemini-2.5-flash-lite"
    vedic_expert_model:       str = "gemini-2.5-flash-lite"
    saju_expert_model:        str = "gemini-2.5-flash-lite"
    hellenistic_expert_model: str = "gemini-2.5-flash-lite"
    arbiter_model:            str = "gemini-3-flash-preview"
    archon_model:             str = "gemini-2.5-pro"

    # Ephemeris Path
    ephe_path: str = "./ephe"

    # API Settings
    api_host: str = "0.0.0.0"
    api_port: int = 8000

    # Test Mode (skip API calls if True)
    test_mode: bool = False

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

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