"""Persistence port for evaluation history and forbidden-list versions.

Framework-free per docs/ARCHITECTURE.md Section 3: this protocol knows
nothing about SQLModel or SQLite. Concrete adapters live in `app/infra/db/`
(`SqliteEvaluationRepository`) and here (`NoopEvaluationRepository`), selected
at startup via `ENABLE_PERSISTENCE` (Section 8).
"""

from typing import Protocol

from app.domain.models import EvaluationResult, StoredEvaluation


class EvaluationRepository(Protocol):
    def save_evaluation(
        self, result: EvaluationResult, *, product_id: str | None = None
    ) -> StoredEvaluation: ...

    def list_evaluations(self, limit: int = 50, offset: int = 0) -> list[StoredEvaluation]: ...

    def save_forbidden_list_version(self, entries: list[str]) -> None: ...
