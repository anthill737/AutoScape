"""P7 regressions for root causes captured in the P7-T1 diagnostic log."""

import pathlib
from typing import Generator
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import app.main as main_module
from app.database import get_db
from app.main import app, get_data_dir
from app.models import Base
from app.providers.gemini_flash import GeminiFlashImageAdapter

_FAKE_JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 100

_VALID_DESIGN_REQUEST = {
    "image_provider": "gemini_flash_image",
    "feature_categories": ["Patio", "Pergola", "Native plant beds"],
    "style": "Modern farmhouse",
    "quality_tier": "Standard",
    "composed_prompt": (
        "Transform the backyard with a paver patio, cedar pergola, native plant beds, "
        "warm path lighting, and a small seating area while preserving the house facade."
    ),
}


def test_lifespan_emits_schema_ready_log_after_alembic_startup(
    tmp_path, monkeypatch, capsys
):
    db_path = tmp_path / "fresh.db"
    data_dir = tmp_path / "data"

    monkeypatch.setattr(main_module, "DATABASE_URL", f"sqlite:///{db_path}")
    monkeypatch.setenv("AUTOSCAPE_DATA_DIR", str(data_dir))

    with TestClient(app) as client:
        resp = client.get("/health")

    startup_log = capsys.readouterr().err
    assert resp.status_code == 200
    assert "[startup] schema ready" in startup_log
    assert str(data_dir.resolve()) in startup_log
    assert str(db_path.resolve()) in startup_log


def test_design_request_provider_quota_failure_returns_structured_503_and_rolls_back(
    tmp_path,
):
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

    try:
        with TestClient(app, raise_server_exceptions=False) as client:
            project_resp = client.post(
                "/api/projects",
                data={
                    "address": "123 P7 Regression Ln",
                    "lot_size_sqft": "5200",
                    "house_sqft": "1800",
                },
                files={"site_photo": ("photo.jpg", _FAKE_JPEG, "image/jpeg")},
            )
            assert project_resp.status_code == 201
            project_id = project_resp.json()["id"]

            provider_error = RuntimeError("429 RESOURCE_EXHAUSTED quota exceeded")
            with patch.object(
                GeminiFlashImageAdapter, "generate", new_callable=AsyncMock
            ) as mock_generate:
                mock_generate.side_effect = provider_error
                resp = client.post(
                    f"/api/projects/{project_id}/design-requests",
                    json=_VALID_DESIGN_REQUEST,
                )

            assert resp.status_code == 503
            assert resp.json() == {
                "detail": (
                    "Image provider failed: RuntimeError: "
                    "429 RESOURCE_EXHAUSTED quota exceeded"
                )
            }

            project_detail_resp = client.get(f"/api/projects/{project_id}")
            assert project_detail_resp.status_code == 200
            assert project_detail_resp.json()["design_requests"] == []
    finally:
        app.dependency_overrides.clear()
        engine.dispose()
