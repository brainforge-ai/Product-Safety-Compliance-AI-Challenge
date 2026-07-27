"""App settings with safe zero-config defaults."""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# Repo root from this file's location so sample paths work regardless of cwd.
_REPO_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    log_level: str = "INFO"

    enable_llm_matching: bool = False
    llm_provider: str = "pydantic_ai"
    llm_model: str = "google:gemini-3.1-flash-lite"
    google_api_key: str | None = None
    llm_timeout_seconds: float = 20.0

    enable_embedding_matching: bool = False

    enable_persistence: bool = False
    database_url: str = "sqlite:///./data/app.db"

    default_forbidden_list_path: Path = _REPO_ROOT / "forbidden_ingredients.csv"
    sample_data_dir: Path = _REPO_ROOT


@lru_cache
def get_settings() -> Settings:
    """Return cached application settings loaded from environment and .env."""
    return Settings()
