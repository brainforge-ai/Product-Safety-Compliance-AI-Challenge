from app.domain.models import EvaluationResult
from app.domain.persistence.noop_evaluation_repository import NoopEvaluationRepository


def test_save_evaluation_does_not_raise_and_requires_no_database() -> None:
    repo = NoopEvaluationRepository()
    result = EvaluationResult(product_name="Pure Lotion", status="Accepted")

    stored = repo.save_evaluation(result, product_id="P-2025-0001")

    assert stored.id is None
    assert stored.product_id == "P-2025-0001"
    assert stored.result == result


def test_list_evaluations_is_always_empty() -> None:
    repo = NoopEvaluationRepository()
    repo.save_evaluation(EvaluationResult(product_name="X", status="Rejected"))

    assert repo.list_evaluations() == []


def test_save_forbidden_list_version_is_a_no_op() -> None:
    repo = NoopEvaluationRepository()
    assert repo.save_forbidden_list_version(["Coumarin"]) is None
