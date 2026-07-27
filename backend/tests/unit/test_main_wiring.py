"""Unit tests for the Phase 8 startup wiring in main.py: whether tier 6 gets
registered depends on both flags being satisfied, and whether tier 5 gets
registered depends only on its own flag.

Constructing a `PydanticAiLlmClient`/`Agent` does not make any network call
(only `.run()` does), so `_build_llm_matcher` is safe to exercise fully
offline with a fake API key.
"""

import logging

import pytest

from app.core.config import Settings
from app.domain.matching.llm_matcher import LlmMatcher
from app.domain.matching.pipeline import MatchPipeline
from app.main import _build_llm_matcher, _default_match_pipeline


def _pydantic_ai_available() -> bool:
    try:
        import pydantic_ai  # noqa: F401
    except ImportError:
        return False
    return True


requires_pydantic_ai = pytest.mark.skipif(
    not _pydantic_ai_available(),
    reason=(
        "pydantic-ai not installed (requirements-ai.txt); "
        "_build_llm_matcher imports it lazily, so pytest must still pass "
        "fully offline with only requirements-dev.txt installed."
    ),
)


def test_llm_matcher_not_built_when_flag_disabled() -> None:
    settings = Settings(_env_file=None, enable_llm_matching=False)

    assert _build_llm_matcher(settings) is None


def test_llm_matcher_not_built_when_key_missing(caplog: pytest.LogCaptureFixture) -> None:
    settings = Settings(_env_file=None, enable_llm_matching=True, google_api_key=None)

    with caplog.at_level(logging.WARNING):
        result = _build_llm_matcher(settings)

    assert result is None
    assert "GOOGLE_API_KEY" in caplog.text


@requires_pydantic_ai
def test_llm_matcher_built_when_enabled_and_key_present() -> None:
    settings = Settings(_env_file=None, enable_llm_matching=True, google_api_key="test-key")

    result = _build_llm_matcher(settings)

    assert isinstance(result, LlmMatcher)


def test_llm_matcher_not_built_when_key_is_empty_string() -> None:
    # `.env.example` ships GOOGLE_API_KEY= (empty); a user who copies it to
    # .env and only flips ENABLE_LLM_MATCHING would get an empty string, not
    # None, from pydantic-settings -- confirm the guard covers that too.
    settings = Settings(_env_file=None, enable_llm_matching=True, google_api_key="")

    assert _build_llm_matcher(settings) is None


@requires_pydantic_ai
def test_llm_matcher_is_wired_with_the_configured_timeout() -> None:
    settings = Settings(
        _env_file=None,
        enable_llm_matching=True,
        google_api_key="test-key",
        llm_timeout_seconds=42.0,
    )

    result = _build_llm_matcher(settings)

    assert isinstance(result, LlmMatcher)
    assert result.timeout_seconds == 42.0


def test_default_pipeline_is_functional_with_embedding_tier_disabled() -> None:
    settings = Settings(_env_file=None, enable_embedding_matching=False)

    pipeline = _default_match_pipeline(settings)

    assert isinstance(pipeline, MatchPipeline)
    result = pipeline.match_ingredient("Coumarin", ["Coumarin"])
    assert result is not None
    assert result.method == "exact"
