from datetime import UTC, datetime

from sqlmodel import Session

from app.domain.models import EvaluationResult, MatchMethod, MatchResult
from app.infra.db.evaluation_repository import SqliteEvaluationRepository
from app.infra.db.models import EvaluationRecord
from app.infra.db.session import create_db_and_tables, create_db_engine


def _repo() -> SqliteEvaluationRepository:
    engine = create_db_engine("sqlite://")
    create_db_and_tables(engine)
    return SqliteEvaluationRepository(Session(engine))


def _rejected_result() -> EvaluationResult:
    return EvaluationResult(
        product_name="Pure Lotion",
        status="Rejected",
        reason=["Contains Coumarin"],
        matches=[
            MatchResult(
                forbidden_ingredient="Coumarin",
                matched_text="Coumarin",
                method=MatchMethod.EXACT,
                confidence=1.0,
            )
        ],
    )


def test_save_and_list_round_trips_evaluation() -> None:
    repo = _repo()
    result = _rejected_result()

    stored = repo.save_evaluation(result, product_id="P-2025-0001")

    assert stored.id is not None
    assert stored.product_id == "P-2025-0001"
    assert stored.result == result

    [listed] = repo.list_evaluations()
    assert listed == stored


def test_list_evaluations_orders_most_recent_first() -> None:
    repo = _repo()
    first = repo.save_evaluation(EvaluationResult(product_name="First", status="Accepted"))
    second = repo.save_evaluation(EvaluationResult(product_name="Second", status="Accepted"))

    listed = repo.list_evaluations()

    assert [record.id for record in listed] == [second.id, first.id]


def test_list_evaluations_tiebreaks_equal_timestamps_by_id() -> None:
    repo = _repo()
    same_instant = datetime.now(UTC)
    for name in ("First", "Second"):
        repo._session.add(
            EvaluationRecord(
                product_name=name,
                status="Accepted",
                reason_json="[]",
                matches_json="[]",
                created_at=same_instant,
            )
        )
    repo._session.commit()

    listed = repo.list_evaluations()

    assert [record.result.product_name for record in listed] == ["Second", "First"]


def test_list_evaluations_respects_limit_and_offset() -> None:
    repo = _repo()
    for name in ("A", "B", "C"):
        repo.save_evaluation(EvaluationResult(product_name=name, status="Accepted"))

    page = repo.list_evaluations(limit=1, offset=1)

    assert len(page) == 1
    assert page[0].result.product_name == "B"


def test_save_forbidden_list_version_persists_without_error() -> None:
    repo = _repo()
    repo.save_forbidden_list_version(["Coumarin", "Propylparaben"])
