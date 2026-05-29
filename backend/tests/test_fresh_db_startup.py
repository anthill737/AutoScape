"""Regression test: POST /api/projects succeeds on a fresh never-migrated SQLite file.

This test reproduces the original P4 defect: on a clean install the SQLite file
exists but has no tables, causing the first INSERT to fail with "no such table".
The fix (P4-T1 lifespan handler) runs Alembic migrations at startup, so the
schema is present before any request is served.

Without the lifespan handler this test fails with a 500 / OperationalError
("no such table: projects").  With the handler it passes.
"""

import pathlib
from typing import Generator

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import app.main as main_module
from app.database import get_db
from app.main import app, get_data_dir

_FAKE_JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 100


def test_post_project_on_fresh_db_succeeds(tmp_path, monkeypatch, capsys):
    """POST /api/projects returns 201 when the app starts against a SQLite file
    that has never had any schema applied.  The lifespan handler must run Alembic
    migrations before serving the first request.
    """
    db_path = tmp_path / "fresh.db"
    db_url = f"sqlite:///{db_path}"
    data_dir = tmp_path / "data"

    # Point the lifespan Alembic run at our temp, never-migrated DB.
    # DATABASE_URL in app.main is read by the lifespan closure at call time,
    # so patching it here is sufficient.
    monkeypatch.setattr(main_module, "DATABASE_URL", db_url)
    monkeypatch.setenv("AUTOSCAPE_DATA_DIR", str(data_dir))

    # Build a session factory for the same temp DB so all request-level DB
    # operations also land on the fresh file.
    temp_engine = create_engine(db_url, connect_args={"check_same_thread": False})
    _Session = sessionmaker(bind=temp_engine)

    def override_get_db() -> Generator:
        db = _Session()
        try:
            yield db
        finally:
            db.close()

    def override_get_data_dir() -> pathlib.Path:
        return data_dir

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_data_dir] = override_get_data_dir

    try:
        # TestClient context manager triggers the lifespan, which runs Alembic
        # migrations on the fresh DB and creates the data directories.
        with TestClient(app) as client:
            resp = client.post(
                "/api/projects",
                data={
                    "address": "1 Fresh Install Ln",
                    "lot_size_sqft": "4000",
                    "house_sqft": "1500",
                },
                files={"site_photo": ("photo.jpg", _FAKE_JPEG, "image/jpeg")},
            )
            assert resp.status_code == 201, f"Expected 201, got {resp.status_code}: {resp.text}"
            body = resp.json()
            assert "id" in body, f"Response body missing 'id': {body}"
            assert isinstance(body["id"], int), f"'id' is not an int: {body['id']}"
            startup_log = capsys.readouterr().err
            assert "[startup] schema ready" in startup_log
            assert "[startup] provider env vars present" in startup_log
            assert "missing = none" in startup_log
            assert str(data_dir.resolve()) in startup_log
            assert str(db_path.resolve()) in startup_log
    finally:
        app.dependency_overrides.clear()
        temp_engine.dispose()
