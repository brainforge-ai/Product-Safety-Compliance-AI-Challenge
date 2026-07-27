"""Base class for evaluation history and forbidden-list persistence."""

from abc import ABC, abstractmethod

from app.domain.models import EvaluationResult, StoredEvaluation


class EvaluationRepository(ABC):
    @abstractmethod
    def save_evaluation(
        self, result: EvaluationResult, *, product_id: str | None = None
    ) -> StoredEvaluation:
        """Persist one evaluation result."""

    @abstractmethod
    def list_evaluations(self, limit: int = 50, offset: int = 0) -> list[StoredEvaluation]:
        """Return stored evaluations, newest first."""

    @abstractmethod
    def save_forbidden_list_version(self, entries: list[str]) -> None:
        """Record a snapshot of the forbidden list after an upload."""
