"""No-op EvaluationRepository when persistence is disabled."""

from datetime import UTC, datetime

from app.domain.models import EvaluationResult, StoredEvaluation


class NoopEvaluationRepository:
    def save_evaluation(
        self, result: EvaluationResult, *, product_id: str | None = None
    ) -> StoredEvaluation:
        """Return a synthetic stored record without persisting anything."""
        return StoredEvaluation(
            id=None,
            product_id=product_id,
            created_at=datetime.now(UTC),
            result=result,
        )

    def list_evaluations(self, limit: int = 50, offset: int = 0) -> list[StoredEvaluation]:
        """Return an empty history when persistence is disabled."""
        return []

    def save_forbidden_list_version(self, entries: list[str]) -> None:
        """No-op when persistence is disabled."""
        return None
