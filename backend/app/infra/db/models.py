"""SQLModel tables for optional persistence (JSON columns for append-only history)."""

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
