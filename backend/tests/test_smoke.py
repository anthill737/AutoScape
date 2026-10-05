"""Regression tests for the backend root JSON pointer and health endpoints.

The launcher tells the user which backend port it picked, so a user who visits
that port directly must see something meaningful rather than a bare 404, and
`/api/health` must answer 200 because the launcher's readiness probe gates the
"ready" banner on it.

The client fixture points the app at a temp database and data directory so the
tests never touch the developer's real `autoscape.db` or `~/.autoscape`.
"""

from typing import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import app.main as main_module
from app.database import get_db
from app.main import app


@pytest.fixture
def client(tmp_path, monkeypatch):
    """Provide a TestClient bound to an isolated database and data directory."""
    db_url = f"sqlite:///{tmp_path / 'smoke.db'}"
    monkeypatch.setattr(main_module, "DATABASE_URL", db_url)
    monkeypatch.setenv("AUTOSCAPE_DATA_DIR", str(tmp_path / "data"))
    # Removed so the default frontend URL is what the root route reports.
    monkeypatch.delenv("FRONTEND_URL", raising=False)
    # Point the runtime frontend-url file at a nonexistent path so the fixture's
    # base case resolves to DEFAULT_FRONTEND_URL instead of reading the real
    # backend/.runtime-frontend-url the launcher may have left on disk (a bumped
    # Vite port there would otherwise leak into these tests). Tests that need a
    # populated runtime file re-patch this attribute themselves.
    monkeypatch.setattr(main_module, "_runtime_frontend_url_file", tmp_path / ".runtime-frontend-url")

    engine = create_engine(db_url, connect_args={"check_same_thread": False})
    session_factory = sessionmaker(bind=engine)

    def override_get_db() -> Generator:
        db = session_factory()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.pop(get_db, None)


def test_root_endpoint_default(client):
    """GET / returns the app info JSON pointer with the default frontend URL."""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["app"] == "AutoScape"
    assert data["frontend_url"] == "http://127.0.0.1:5173"
    assert data["health_check"] == "/api/health"


def test_root_endpoint_override(client, monkeypatch):
    """GET / respects the FRONTEND_URL env var so an alternate Vite port shows up."""
    monkeypatch.setenv("FRONTEND_URL", "http://localhost:5174")
    response = client.get("/")
    assert response.status_code == 200
    assert response.json()["frontend_url"] == "http://localhost:5174"


def test_api_health_endpoint(client):
    """GET /api/health reports the backend is healthy."""
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_root_route_does_not_shadow_existing_routes(client):
    """Registering / must leave the existing API routes reachable."""
    response = client.get("/api/projects")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_root_reports_the_url_the_launcher_verified(client, monkeypatch, tmp_path):
    """AutoScape.bat writes the verified URL; the root pointer must use it, bumped port and all."""
    verified = tmp_path / ".runtime-frontend-url"
    verified.write_text("http://127.0.0.1:5174\n", encoding="utf-8")
    monkeypatch.setattr(main_module, "_runtime_frontend_url_file", verified)

    response = client.get("/")
    assert response.status_code == 200
    assert response.json()["frontend_url"] == "http://127.0.0.1:5174"


def test_explicit_frontend_url_env_beats_the_runtime_file(client, monkeypatch, tmp_path):
    verified = tmp_path / ".runtime-frontend-url"
    verified.write_text("http://127.0.0.1:5174\n", encoding="utf-8")
    monkeypatch.setattr(main_module, "_runtime_frontend_url_file", verified)
    monkeypatch.setenv("FRONTEND_URL", "http://127.0.0.1:4200")

    assert client.get("/").json()["frontend_url"] == "http://127.0.0.1:4200"


def test_root_falls_back_to_default_when_runtime_file_is_missing_or_blank(
    client, monkeypatch, tmp_path
):
    monkeypatch.setattr(main_module, "_runtime_frontend_url_file", tmp_path / "absent")
    assert client.get("/").json()["frontend_url"] == "http://127.0.0.1:5173"

    blank = tmp_path / "blank"
    blank.write_text("   \n", encoding="utf-8")
    monkeypatch.setattr(main_module, "_runtime_frontend_url_file", blank)
    assert client.get("/").json()["frontend_url"] == "http://127.0.0.1:5173"
