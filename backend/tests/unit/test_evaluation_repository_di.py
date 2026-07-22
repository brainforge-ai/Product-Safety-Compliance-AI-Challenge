from types import SimpleNamespace

from app.api.deps import get_evaluation_repository
from app.core.config import Settings
from app.domain.persistence.noop_evaluation_repository import NoopEvaluationRepository
from app.infra.db.evaluation_repository import SqliteEvaluationRepository
from app.infra.db.session import create_db_and_tables, create_db_engine


def _fake_request(app_state: SimpleNamespace) -> SimpleNamespace:
    return SimpleNamespace(app=SimpleNamespace(state=app_state))


def test_yields_noop_repository_when_persistence_disabled() -> None:
    settings = Settings(_env_file=None, enable_persistence=False)
    request = _fake_request(SimpleNamespace(settings=settings))

    repo = next(get_evaluation_repository(request))

    assert isinstance(repo, NoopEvaluationRepository)


def test_yields_sqlite_repository_when_persistence_enabled() -> None:
    settings = Settings(_env_file=None, enable_persistence=True)
    engine = create_db_engine("sqlite://")
    create_db_and_tables(engine)
    request = _fake_request(SimpleNamespace(settings=settings, db_engine=engine))

    repo = next(get_evaluation_repository(request))

    assert isinstance(repo, SqliteEvaluationRepository)
