from app.domain.models import MatchMethod, MatchResult
from app.infra.cache.llm_response_cache import LlmResponseCache

_RESULT = MatchResult(
    forbidden_ingredient="Coumarin",
    matched_text="Coumarin",
    method=MatchMethod.LLM,
    confidence=0.95,
)


def test_miss_reports_hit_false() -> None:
    cache = LlmResponseCache()
    hit, result = cache.get("coumarin", "v1")
    assert hit is False
    assert result is None


def test_set_then_get_positive_result() -> None:
    cache = LlmResponseCache()
    cache.set("coumarin", "v1", _RESULT)
    hit, result = cache.get("coumarin", "v1")
    assert hit is True
    assert result == _RESULT


def test_negative_result_is_cached_and_distinguishable_from_a_miss() -> None:
    cache = LlmResponseCache()
    cache.set("water", "v1", None)
    hit, result = cache.get("water", "v1")
    assert hit is True
    assert result is None


def test_different_forbidden_list_versions_are_independent() -> None:
    cache = LlmResponseCache()
    cache.set("coumarin", "v1", _RESULT)
    hit, result = cache.get("coumarin", "v2")
    assert hit is False
    assert result is None
