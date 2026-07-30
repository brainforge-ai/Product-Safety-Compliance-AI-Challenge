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


def test_cache_is_bounded_and_evicts_least_recently_used_entry() -> None:
    cache = LlmResponseCache(max_entries=2)
    cache.set("a", "v1", None)
    cache.set("b", "v1", None)
    cache.get("a", "v1")
    cache.set("c", "v1", None)

    assert cache.get("a", "v1")[0] is True
    assert cache.get("b", "v1")[0] is False
    assert cache.get("c", "v1")[0] is True
