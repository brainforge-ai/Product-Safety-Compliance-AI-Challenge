from app.core.config import Settings, get_settings


def test_settings_defaults_require_no_configuration() -> None:
    settings = Settings(_env_file=None)

    assert settings.enable_llm_matching is False
    assert settings.enable_embedding_matching is False
    assert settings.enable_persistence is False
    assert settings.google_api_key is None
    assert settings.llm_provider == "pydantic_ai"
    assert settings.llm_model == "google:gemini-3.1-flash-lite"
    assert settings.database_url == "sqlite:///./data/app.db"


def test_settings_override_via_environment(monkeypatch) -> None:
    monkeypatch.setenv("ENABLE_LLM_MATCHING", "true")
    monkeypatch.setenv("GOOGLE_API_KEY", "test-key")
    monkeypatch.setenv("ENABLE_PERSISTENCE", "true")

    settings = Settings(_env_file=None)

    assert settings.enable_llm_matching is True
    assert settings.google_api_key == "test-key"
    assert settings.enable_persistence is True


def test_get_settings_is_cached() -> None:
    assert get_settings() is get_settings()
