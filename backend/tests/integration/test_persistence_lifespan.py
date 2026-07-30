"""Verifies the lifespan-driven DI wiring from a fresh interpreter.

A same-process test can't catch a regression of the "create_db_and_tables
forgot to import the table models" bug: once any other test module imports
`app.infra.db.models`, SQLModel's process-global metadata has the tables
registered regardless of what `create_db_and_tables` itself does. Spawning a
subprocess reproduces the real production startup path (nothing else has
imported the models yet) and fails if that import is ever removed.
"""

import json
import subprocess
import sys
from pathlib import Path

from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.main import create_app

_BACKEND_DIR = Path(__file__).resolve().parents[2]

_PROBE_SCRIPT = """
import json
from sqlalchemy import inspect
from fastapi.testclient import TestClient
from app.main import create_app

app = create_app()
with TestClient(app):
    tables = sorted(inspect(app.state.db_engine).get_table_names())
print(json.dumps(tables))
"""


def test_persistence_disabled_boots_with_no_db_engine(monkeypatch) -> None:
    monkeypatch.setenv("ENABLE_PERSISTENCE", "false")
    get_settings.cache_clear()
    try:
        app = create_app()
        with TestClient(app) as client:
            assert client.get("/api/health").status_code == 200
            assert not hasattr(app.state, "db_engine")
    finally:
        get_settings.cache_clear()


def test_persistence_enabled_creates_expected_tables_in_a_fresh_process(tmp_path: Path) -> None:
    db_path = tmp_path / "app.db"
    env = {
        "ENABLE_PERSISTENCE": "true",
        "ENABLE_EMBEDDING_MATCHING": "false",
        "ENABLE_LLM_MATCHING": "false",
        "DATABASE_URL": f"sqlite:///{db_path}",
        "PATH": "/usr/bin:/bin",
    }

    result = subprocess.run(
        [sys.executable, "-c", _PROBE_SCRIPT],
        cwd=_BACKEND_DIR,
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )

    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == ["evaluation_records", "forbidden_list_versions"]
    assert db_path.exists()
