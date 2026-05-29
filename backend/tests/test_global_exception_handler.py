"""Tests for the app-level unhandled exception handler."""

import logging
import pathlib
from typing import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import get_db
from app.main import app, get_data_dir
from app.models import Base

_FAKE_JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 100


@pytest.fixture
def client(tmp_path):
    db_path = tmp_path / "test.db"
    engine = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    session_local = sessionmaker(bind=engine)
    data_dir = tmp_path / "data"

    def override_get_db() -> Generator:
        db = session_local()
        try:
            yield db
        finally:
            db.close()

    def override_get_data_dir() -> pathlib.Path:
        return data_dir

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_data_dir] = override_get_data_dir

    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client, data_dir

    app.dependency_overrides.clear()
    engine.dispose()


def test_unhandled_route_exception_returns_json_500_and_logs_trace_id(client, caplog):
    test_client, data_dir = client
    caplog.set_level(logging.ERROR, logger="app.main")

    create_resp = test_client.post(
        "/api/projects",
        data={"address": "1 Missing Photo Way", "lot_size_sqft": "5000", "house_sqft": "2000"},
        files={"site_photo": ("photo.jpg", _FAKE_JPEG, "image/jpeg")},
    )
    assert create_resp.status_code == 201
    project_id = create_resp.json()["id"]
    (data_dir / "images" / str(project_id) / "site_photo.jpg").unlink()

    resp = test_client.post(
        f"/api/projects/{project_id}/design-requests",
        json={
            "image_provider": "gemini_flash_image",
            "feature_categories": ["Deck"],
            "style": "Modern",
            "quality_tier": "Budget",
            "composed_prompt": "Add a deck",
        },
    )

    assert resp.status_code == 500
    body = resp.json()
    assert body["detail"].startswith("FileNotFoundError: ")
    assert isinstance(body["trace_id"], str)
    assert len(body["trace_id"]) == 8
    assert body["trace_id"] in caplog.text
    assert "FileNotFoundError" in caplog.text
    assert "Traceback (most recent call last)" in caplog.text


def test_http_exception_responses_keep_original_status_and_detail(client):
    test_client, _ = client

    resp = test_client.get("/api/projects/99999")

    assert resp.status_code == 404
    assert resp.json() == {"detail": "Project not found"}
