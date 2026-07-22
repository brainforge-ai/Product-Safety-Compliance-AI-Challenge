"""SQLite-backed `EvaluationRepository` (ARCHITECTURE.md Section 8)."""

import json

from sqlmodel import Session, select

from app.domain.models import EvaluationResult, MatchResult, StoredEvaluation
from app.infra.db.models import EvaluationRecord, ForbiddenListVersion


class SqliteEvaluationRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def save_evaluation(
        self, result: EvaluationResult, *, product_id: str | None = None
    ) -> StoredEvaluation:
        record = EvaluationRecord(
            product_id=product_id,
            product_name=result.product_name,
            status=result.status,
            reason_json=json.dumps(result.reason),
            matches_json=json.dumps([m.model_dump(mode="json") for m in result.matches]),
        )
        self._session.add(record)
        self._session.commit()
        self._session.refresh(record)
        return _to_stored_evaluation(record)

    def list_evaluations(self, limit: int = 50, offset: int = 0) -> list[StoredEvaluation]:
        # created_at alone isn't a unique sort key (concurrent writes can share
        # a timestamp); tie-break on id so offset pagination never skips or
        # duplicates rows.
        statement = (
            select(EvaluationRecord)
            .order_by(EvaluationRecord.created_at.desc(), EvaluationRecord.id.desc())
            .offset(offset)
            .limit(limit)
        )
        records = self._session.exec(statement).all()
        return [_to_stored_evaluation(r) for r in records]

    def save_forbidden_list_version(self, entries: list[str]) -> None:
        version = ForbiddenListVersion(entries_json=json.dumps(entries))
        self._session.add(version)
        self._session.commit()


def _to_stored_evaluation(record: EvaluationRecord) -> StoredEvaluation:
    return StoredEvaluation(
        id=record.id,
        product_id=record.product_id,
        created_at=record.created_at,
        result=EvaluationResult(
            product_name=record.product_name,
            status=record.status,
            reason=json.loads(record.reason_json),
            matches=[MatchResult(**m) for m in json.loads(record.matches_json)],
        ),
    )
