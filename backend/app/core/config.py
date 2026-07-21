"""Application settings.

Every flag here has a safe default so the app runs with zero configuration
(the "deterministic-first, AI-assisted fallback" principle in
docs/ARCHITECTURE.md, Section 3). Nothing that requires a real dependency
(an API key, a database) is ever required just to boot the app.
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # --- Logging ---
    log_level: str = "INFO"

    # --- Optional LLM matching tier (ARCHITECTURE.md Section 7) ---
    enable_llm_matching: bool = False
    llm_provider: str = "pydantic_ai"
    llm_model: str = "google:gemini-3.1-flash-lite"
    google_api_key: str | None = None

    # --- Optional local embedding matching tier (ARCHITECTURE.md Section 6) ---
    enable_embedding_matching: bool = False

    # --- Persistence (ARCHITECTURE.md Section 8) ---
    enable_persistence: bool = False
    database_url: str = "sqlite:///./data/app.db"


@lru_cache
def get_settings() -> Settings:
    """Cached settings accessor, suitable for use as a FastAPI dependency."""
    return Settings()
