"""SQLModel tables backing the toggleable persistence layer (ARCHITECTURE.md Section 8).

Ingredient lists and match results are stored as JSON text columns rather than
normalized child tables: evaluation history is append-only and read back
whole, so there's nothing a join would buy us here.
"""

from datetime import UTC, datetime

from sqlmodel import Field, SQLModel


class EvaluationRecord(SQLModel, table=True):
    __tablename__ = "evaluation_records"

    id: int | None = Field(default=None, primary_key=True)
    product_id: str | None = None
    product_name: str
    status: str
    reason_json: str
    matches_json: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class ForbiddenListVersion(SQLModel, table=True):
    __tablename__ = "forbidden_list_versions"

    id: int | None = Field(default=None, primary_key=True)
    entries_json: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
