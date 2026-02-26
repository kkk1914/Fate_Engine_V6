"""Configuration management for Fates Engine."""
from pydantic_settings import BaseSettings
from typing import Optional
import warnings


class Settings(BaseSettings):

    # ── Neo4j AuraDB ─────────────────────────────────────────────────────────
    neo4j_uri:      str = "neo4j+s://your-instance.databases.neo4j.io"
    neo4j_user:     str = "neo4j"
    neo4j_password: str = ""

    # ── API Keys ──────────────────────────────────────────────────────────────
    # Set GOOGLE_API_KEY in your .env file.
    # OPENAI_API_KEY is optional — only needed if you keep any gpt-* models.
    google_api_key: str = ""
    openai_api_key: str = ""

    # ── Reasoning / output defaults ───────────────────────────────────────────
    default_reasoning_effort: str = "medium"
    default_verbosity:        str = "high"

    # ── Model Assignments ─────────────────────────────────────────────────────
    #
    # COST BREAKDOWN (per run, approx):
    #   4 experts  @ Flash Lite  ~$0.004   ($0.10/$0.40 per 1M)
    #   Arbiter    @ Gemini 3 Flash ~$0.01  ($0.50/$3.00 per 1M)
    #   Archon     @ Gemini 2.5 Pro ~$0.34  ($1.25/$10.00 per 1M)
    #   TOTAL:  ~$0.35/run  vs $0.74 with GPT-5.2  (53% cheaper)
    #
    # NOTE: gemini-3.1-pro-preview is rolling out now but is still preview-only.
    #       Switch archon_model to "gemini-3.1-pro-preview" when it goes stable.
    #       Gemini 3 Flash is also preview — swap to stable string when available.
    #
    western_expert_model:    str = "gemini-2.5-flash-lite"
    vedic_expert_model:      str = "gemini-2.5-flash-lite"
    saju_expert_model:       str = "gemini-2.5-flash-lite"
    hellenistic_expert_model:str = "gemini-2.5-flash-lite"
    arbiter_model:           str = "gemini-3-flash-preview"
    archon_model:            str = "gemini-2.5-pro"

    # ── Ephemeris ─────────────────────────────────────────────────────────────
    ephe_path: str = "./ephe"

    # ── API Server ────────────────────────────────────────────────────────────
    api_host: str = "0.0.0.0"
    api_port: int = 8000

    # ── Test Mode ─────────────────────────────────────────────────────────────
    test_mode: bool = False

    class Config:
        env_file          = ".env"
        env_file_encoding = "utf-8"

    def validate(self):
        """Validate settings with graceful degradation."""
        has_google = bool(self.google_api_key)
        has_openai = bool(self.openai_api_key)

        if not has_google and not has_openai and not self.test_mode:
            warnings.warn(
                "Neither GOOGLE_API_KEY nor OPENAI_API_KEY is set. "
                "Set GOOGLE_API_KEY in your .env file. "
                "Falling back to test_mode=True (calculations only)."
            )
            self.test_mode = True

        if not has_google:
            # Check if any Gemini models are configured
            gemini_models = [
                self.western_expert_model, self.vedic_expert_model,
                self.saju_expert_model, self.hellenistic_expert_model,
                self.arbiter_model, self.archon_model,
            ]
            if any(m.startswith("gemini") for m in gemini_models):
                warnings.warn(
                    "GOOGLE_API_KEY not set but Gemini models are configured. "
                    "Add GOOGLE_API_KEY=your_key to your .env file."
                )


settings = Settings()
settings.validate()
