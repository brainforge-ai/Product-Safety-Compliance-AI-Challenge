"""No-op `EvaluationRepository` used when `ENABLE_PERSISTENCE=false`.

Performs no writes and requires no database, so the system stays fully
stateless (ARCHITECTURE.md Section 8): every request is recomputed, and
`GET /api/products` (Phase 7) simply has no history to return.
"""

from datetime import UTC, datetime

from app.domain.models import EvaluationResult, StoredEvaluation


class NoopEvaluationRepository:
    def save_evaluation(
        self, result: EvaluationResult, *, product_id: str | None = None
    ) -> StoredEvaluation:
        return StoredEvaluation(
            id=None,
            product_id=product_id,
            created_at=datetime.now(UTC),
            result=result,
        )

    def list_evaluations(self, limit: int = 50, offset: int = 0) -> list[StoredEvaluation]:
        return []

    def save_forbidden_list_version(self, entries: list[str]) -> None:
        return None
