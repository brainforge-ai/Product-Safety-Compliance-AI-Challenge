import pytest
from pydantic import ValidationError

from app.domain.models import EvaluationResult, MatchMethod, MatchResult


def test_evaluation_result_accepts_valid_status() -> None:
    result = EvaluationResult(product_name="Pure Lotion", status="Accepted")
    assert result.status == "Accepted"
    assert result.reason == []
    assert result.matches == []


def test_evaluation_result_rejects_invalid_status() -> None:
    with pytest.raises(ValidationError):
        EvaluationResult(product_name="Pure Lotion", status="Maybe")


def test_match_result_confidence_must_be_within_bounds() -> None:
    MatchResult(
        forbidden_ingredient="Coumarin",
        matched_text="Coumarin",
        method=MatchMethod.EXACT,
        confidence=1.0,
    )

    with pytest.raises(ValidationError):
        MatchResult(
            forbidden_ingredient="Coumarin",
            matched_text="Coumarin",
            method=MatchMethod.EXACT,
            confidence=1.5,
        )


def test_evaluation_result_with_matches_and_reasons() -> None:
    match = MatchResult(
        forbidden_ingredient="Coumarin",
        matched_text="Coumarin",
        method=MatchMethod.EXACT,
        confidence=1.0,
    )
    result = EvaluationResult(
        product_name="Pure Lotion",
        status="Rejected",
        reason=["Contains Coumarin"],
        matches=[match],
    )
    assert result.status == "Rejected"
    assert result.reason == ["Contains Coumarin"]
    assert result.matches[0].method == MatchMethod.EXACT
