"""Persistence port for evaluation history and forbidden-list versions."""

from typing import Protocol

from app.domain.models import EvaluationResult, StoredEvaluation


class EvaluationRepository(Protocol):
    def save_evaluation(
        self, result: EvaluationResult, *, product_id: str | None = None
    ) -> StoredEvaluation: ...

    def list_evaluations(self, limit: int = 50, offset: int = 0) -> list[StoredEvaluation]: ...

    def save_forbidden_list_version(self, entries: list[str]) -> None: ...
