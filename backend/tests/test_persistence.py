"""Persistence integration test: data survives backend restart (P1-T9).

Verifies that Projects, Design Requests, Renders, and Chosen Render state
written through the API are fully readable after re-initialising the DB
session (simulating a process restart) against the same SQLite file.
"""

import pathlib
from typing import Generator
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import get_db
from app.main import app, get_data_dir
from app.models import Base
from app.providers.gemini_flash import GeminiFlashImageAdapter

_FAKE_JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 100
_FAKE_RENDER_BYTES = b"\x89PNG\r\n\x1a\n" + b"\x01" * 200

_VALID_DR_BODY = {
    "image_provider": "gemini_flash_image",
    "feature_categories": ["Deck"],
    "style": "Modern",
    "quality_tier": "Budget",
    "composed_prompt": "Add a wooden deck",
}


def _setup_overrides(db_path: pathlib.Path, data_dir: pathlib.Path):
    """Wire app dependencies to a specific DB file and data directory.

    Returns the SQLAlchemy engine so the caller can dispose it when done.
    """
    engine = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    _SessionLocal = sessionmaker(bind=engine)

    def override_get_db() -> Generator:
        db = _SessionLocal()
        try:
            yield db
        finally:
            db.close()

    def override_get_data_dir() -> pathlib.Path:
        return data_dir

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_data_dir] = override_get_data_dir

    return engine


class TestPersistenceSurvivesRestart:
    """Full end-to-end persistence: written data is readable after session re-open."""

    def test_project_design_request_renders_and_chosen_render_survive_restart(self, tmp_path):
        db_path = tmp_path / "autoscape.db"
        data_dir = tmp_path / "data"

        # ── Phase 1: first "process" — write data ────────────────────────────
        engine1 = _setup_overrides(db_path, data_dir)
        with TestClient(app) as client1:
            # Create a Project
            resp = client1.post(
                "/api/projects",
                data={
                    "address": "42 Persist Ave",
                    "lot_size_sqft": "6000",
                    "house_sqft": "2500",
                },
                files={"site_photo": ("yard.jpg", _FAKE_JPEG, "image/jpeg")},
            )
            assert resp.status_code == 201
            project_id = resp.json()["id"]

            # Submit a Design Request with a stubbed provider (no real API key)
            with patch.object(
                GeminiFlashImageAdapter, "generate", new_callable=AsyncMock
            ) as mock_gen:
                mock_gen.return_value = [
                    _FAKE_RENDER_BYTES,
                    _FAKE_RENDER_BYTES,
                    _FAKE_RENDER_BYTES,
                ]
                dr_resp = client1.post(
                    f"/api/projects/{project_id}/design-requests",
                    json=_VALID_DR_BODY,
                )
            assert dr_resp.status_code == 201
            dr_body = dr_resp.json()
            dr_id = dr_body["id"]
            renders = dr_body["renders"]
            assert len(renders) == 3

            # Mark the first Render as the Chosen Render
            chosen_render_id = renders[0]["id"]
            choose_resp = client1.patch(f"/api/renders/{chosen_render_id}/choose")
            assert choose_resp.status_code == 200
            assert choose_resp.json()["is_chosen"] is True

        # Dispose engine — closes all connections (simulates process exit)
        engine1.dispose()
        app.dependency_overrides.clear()

        # ── Phase 2: second "process" — fresh engine, same DB file ───────────
        engine2 = _setup_overrides(db_path, data_dir)
        try:
            with TestClient(app) as client2:
                resp2 = client2.get(f"/api/projects/{project_id}")
                assert resp2.status_code == 200
                body = resp2.json()

                # Project fields intact
                assert body["id"] == project_id
                assert body["address"] == "42 Persist Ave"
                assert body["lot_size_sqft"] == 6000.0
                assert body["house_sqft"] == 2500.0

                # Design Request intact
                assert len(body["design_requests"]) == 1
                dr = body["design_requests"][0]
                assert dr["id"] == dr_id
                assert dr["composed_prompt"] == _VALID_DR_BODY["composed_prompt"]
                assert dr["image_provider"] == _VALID_DR_BODY["image_provider"]
                assert dr["style"] == _VALID_DR_BODY["style"]
                assert dr["quality_tier"] == _VALID_DR_BODY["quality_tier"]

                # All 3 Renders present
                assert len(dr["renders"]) == 3

                # Chosen Render state persisted
                chosen = next(r for r in dr["renders"] if r["id"] == chosen_render_id)
                assert chosen["is_chosen"] is True

                # Non-chosen Renders are not marked chosen
                for r in dr["renders"]:
                    if r["id"] != chosen_render_id:
                        assert r["is_chosen"] is False
        finally:
            engine2.dispose()
            app.dependency_overrides.clear()

    def test_render_image_files_exist_on_disk_after_session_reopen(self, tmp_path):
        db_path = tmp_path / "autoscape.db"
        data_dir = tmp_path / "data"

        # ── Phase 1: write renders ────────────────────────────────────────────
        engine1 = _setup_overrides(db_path, data_dir)
        with TestClient(app) as client1:
            resp = client1.post(
                "/api/projects",
                data={
                    "address": "10 Disk Lane",
                    "lot_size_sqft": "4000",
                    "house_sqft": "1500",
                },
                files={"site_photo": ("yard.jpg", _FAKE_JPEG, "image/jpeg")},
            )
            assert resp.status_code == 201
            project_id = resp.json()["id"]

            with patch.object(
                GeminiFlashImageAdapter, "generate", new_callable=AsyncMock
            ) as mock_gen:
                mock_gen.return_value = [
                    _FAKE_RENDER_BYTES,
                    _FAKE_RENDER_BYTES,
                    _FAKE_RENDER_BYTES,
                ]
                dr_resp = client1.post(
                    f"/api/projects/{project_id}/design-requests",
                    json=_VALID_DR_BODY,
                )
            assert dr_resp.status_code == 201

        engine1.dispose()
        app.dependency_overrides.clear()

        # ── Phase 2: re-open session, verify image files exist on disk ────────
        engine2 = _setup_overrides(db_path, data_dir)
        try:
            with TestClient(app) as client2:
                proj_resp = client2.get(f"/api/projects/{project_id}")
                assert proj_resp.status_code == 200
                dr = proj_resp.json()["design_requests"][0]

                for render in dr["renders"]:
                    rid = render["id"]
                    expected_path = data_dir / "images" / str(project_id) / f"{rid}.png"
                    assert expected_path.exists(), (
                        f"Render file missing at {expected_path} after session re-open"
                    )
                    assert expected_path.read_bytes() == _FAKE_RENDER_BYTES
        finally:
            engine2.dispose()
            app.dependency_overrides.clear()
