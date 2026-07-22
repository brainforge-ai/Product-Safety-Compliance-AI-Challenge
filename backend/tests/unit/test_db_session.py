from pathlib import Path

from sqlmodel import Session, select

from app.infra.db.models import EvaluationRecord
from app.infra.db.session import create_db_and_tables, create_db_engine


def test_in_memory_engine_shares_one_connection_across_sessions() -> None:
    engine = create_db_engine("sqlite://")
    create_db_and_tables(engine)

    with Session(engine) as session:
        session.add(
            EvaluationRecord(
                product_name="P", status="Accepted", reason_json="[]", matches_json="[]"
            )
        )
        session.commit()

    with Session(engine) as session:
        assert session.exec(select(EvaluationRecord)).all()


def test_file_engine_creates_parent_directory(tmp_path: Path) -> None:
    db_path = tmp_path / "nested" / "app.db"
    engine = create_db_engine(f"sqlite:///{db_path}")
    create_db_and_tables(engine)

    assert db_path.parent.is_dir()
    assert db_path.exists()
