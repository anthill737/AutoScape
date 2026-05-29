"""Tests for Project CRUD API (P1-T3)."""

import pathlib
from datetime import datetime, timezone
from io import BytesIO
from typing import Generator

import pytest
from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import get_db
from app.main import app, get_data_dir
from app.models import Base, BuildSheet, DesignRequest, Render
from app.thumbnails import ensure_site_photo_thumbnail, site_photo_thumbnail_path

BACKEND_DIR = pathlib.Path(__file__).parent.parent

# Minimal magic-byte prefixes so content is recognisable (content_type drives validation).
_FAKE_JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 100
_FAKE_PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100


def _valid_jpeg(size: tuple[int, int] = (640, 360)) -> bytes:
    buffer = BytesIO()
    Image.new("RGB", size, (82, 128, 96)).save(buffer, format="JPEG")
    return buffer.getvalue()


@pytest.fixture
def client(tmp_path):
    """TestClient backed by a real file-based SQLite DB and real temp filesystem."""
    db_path = tmp_path / "test.db"
    engine = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    _SessionLocal = sessionmaker(bind=engine)
    data_dir = tmp_path / "data"

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

    with TestClient(app) as c:
        yield c, tmp_path

    app.dependency_overrides.clear()
    engine.dispose()


# ---------------------------------------------------------------------------
# POST /api/projects
# ---------------------------------------------------------------------------


class TestCreateProject:
    def test_frontend_multipart_shape_returns_201_project_json(self, client):
        c, tmp_path = client
        resp = c.post(
            "/api/projects",
            data={"address": "123 Frontend St", "lot_size": "5000", "house_sqft": "2000"},
            files={"site_photo": ("yard.jpg", _FAKE_JPEG, "image/jpeg")},
        )

        assert resp.status_code == 201
        body = resp.json()
        assert isinstance(body["id"], int)
        assert body["project_id"] == body["id"]
        assert body["address"] == "123 Frontend St"
        assert "created_at" in body

        photo_path = tmp_path / "data" / "images" / str(body["id"]) / "site_photo.jpg"
        assert photo_path.exists()
        assert photo_path.read_bytes() == _FAKE_JPEG

        detail_resp = c.get(f"/api/projects/{body['id']}")
        assert detail_resp.status_code == 200
        detail = detail_resp.json()
        assert detail["lot_size_sqft"] == 5000.0
        assert detail["house_sqft"] == 2000.0

    def test_valid_jpeg_returns_201_with_id(self, client):
        c, tmp_path = client
        resp = c.post(
            "/api/projects",
            data={"address": "123 Main St", "lot_size_sqft": "5000", "house_sqft": "2000"},
            files={"site_photo": ("photo.jpg", _FAKE_JPEG, "image/jpeg")},
        )
        assert resp.status_code == 201
        body = resp.json()
        assert "id" in body
        project_id = body["id"]
        assert isinstance(project_id, int)
        assert body["project_id"] == project_id

        # Site Photo must be saved at the canonical path.
        photo_path = tmp_path / "data" / "images" / str(project_id) / "site_photo.jpg"
        assert photo_path.exists(), f"Expected Site Photo at {photo_path}"
        assert photo_path.read_bytes() == _FAKE_JPEG

    def test_valid_png_returns_201(self, client):
        c, tmp_path = client
        resp = c.post(
            "/api/projects",
            data={"address": "456 Oak Ave", "lot_size_sqft": "7500", "house_sqft": "3000"},
            files={"site_photo": ("yard.png", _FAKE_PNG, "image/png")},
        )
        assert resp.status_code == 201
        body = resp.json()
        assert "id" in body
        project_id = body["id"]
        photo_path = tmp_path / "data" / "images" / str(project_id) / "site_photo.jpg"
        assert photo_path.exists()

    def test_non_image_returns_422_with_message(self, client):
        c, _ = client
        resp = c.post(
            "/api/projects",
            data={"address": "789 Pine Rd", "lot_size_sqft": "4000", "house_sqft": "1500"},
            files={"site_photo": ("notes.txt", b"just some text", "text/plain")},
        )
        assert resp.status_code == 422
        detail = resp.json().get("detail", "")
        # Must include a description referencing the expected formats.
        assert any(word in detail for word in ("JPEG", "PNG", "image"))

    def test_octet_stream_returns_422(self, client):
        c, _ = client
        resp = c.post(
            "/api/projects",
            data={"address": "1 Byte Rd", "lot_size_sqft": "1000", "house_sqft": "500"},
            files={"site_photo": ("bin.bin", b"\x00\x01\x02", "application/octet-stream")},
        )
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# GET /api/projects
# ---------------------------------------------------------------------------


class TestListProjects:
    def test_empty_returns_empty_list(self, client):
        c, _ = client
        resp = c.get("/api/projects")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_returns_all_created_projects(self, client):
        c, _ = client
        c.post(
            "/api/projects",
            data={"address": "123 Main St", "lot_size_sqft": "5000", "house_sqft": "2000"},
            files={"site_photo": ("p.jpg", _FAKE_JPEG, "image/jpeg")},
        )
        c.post(
            "/api/projects",
            data={"address": "456 Oak Ave", "lot_size_sqft": "7500", "house_sqft": "3000"},
            files={"site_photo": ("p.jpg", _FAKE_JPEG, "image/jpeg")},
        )
        resp = c.get("/api/projects")
        assert resp.status_code == 200
        projects = resp.json()
        assert len(projects) == 2
        addresses = {p["address"] for p in projects}
        assert addresses == {"123 Main St", "456 Oak Ave"}

    def test_list_item_has_id_address_site_photo_url(self, client):
        c, _ = client
        c.post(
            "/api/projects",
            data={"address": "123 Main St", "lot_size_sqft": "5000", "house_sqft": "2000"},
            files={"site_photo": ("p.jpg", _FAKE_JPEG, "image/jpeg")},
        )
        resp = c.get("/api/projects")
        assert resp.status_code == 200
        item = resp.json()[0]
        assert "id" in item
        assert "address" in item
        assert "site_photo_url" in item
        assert item["site_photo_url"] is not None

    def test_list_item_includes_history_fields_and_cached_thumbnail(self, client):
        c, tmp_path = client
        create_resp = c.post(
            "/api/projects",
            data={"address": "123 Main St", "lot_size_sqft": "5000", "house_sqft": "2000"},
            files={"site_photo": ("p.jpg", _valid_jpeg((900, 500)), "image/jpeg")},
        )
        project_id = create_resp.json()["id"]

        db_path = tmp_path / "test.db"
        engine = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})
        SessionLocal = sessionmaker(bind=engine)
        session = SessionLocal()
        try:
            first_request = DesignRequest(
                project_id=project_id,
                image_provider="GeminiFlash",
                feature_categories=["patio"],
                style="Modern",
                quality_tier="Budget",
                composed_prompt="first prompt",
                created_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
            )
            session.add(first_request)
            session.flush()

            chosen_render = Render(
                design_request_id=first_request.id,
                image_path=str(tmp_path / "render-1.png"),
                is_chosen=True,
            )
            other_render = Render(
                design_request_id=first_request.id,
                image_path=str(tmp_path / "render-2.png"),
                is_chosen=False,
            )
            session.add_all([chosen_render, other_render])
            session.flush()

            iteration_request = DesignRequest(
                project_id=project_id,
                parent_render_id=chosen_render.id,
                image_provider="OpenAI",
                feature_categories=["patio", "lighting"],
                style="Craftsman",
                quality_tier="Premium",
                composed_prompt="iteration prompt",
                created_at=datetime(2024, 1, 2, tzinfo=timezone.utc),
            )
            session.add(iteration_request)
            session.flush()

            session.add(
                Render(
                    design_request_id=iteration_request.id,
                    image_path=str(tmp_path / "render-3.png"),
                    is_chosen=False,
                )
            )
            session.add(
                BuildSheet(
                    render_id=chosen_render.id,
                    materials_llm="ClaudeSonnet",
                    content_json=(
                        '{"material_items":[],"tool_list":[],"build_steps":[],'
                        '"total_cost_range":"","skill_level":"","assumptions":[]}'
                    ),
                )
            )
            session.commit()
        finally:
            session.close()
            engine.dispose()

        resp = c.get("/api/projects")
        assert resp.status_code == 200
        item = resp.json()[0]

        expected_fields = {
            "latest_design_request_at",
            "design_request_count",
            "render_count",
            "iteration_count",
            "has_chosen_render",
            "has_build_sheet",
            "latest_quality_tier",
            "site_photo_thumb_url",
        }
        assert expected_fields <= set(item)
        assert item["latest_design_request_at"].startswith("2024-01-02T00:00:00")
        assert item["design_request_count"] == 2
        assert item["render_count"] == 3
        assert item["iteration_count"] == 1
        assert item["has_chosen_render"] is True
        assert item["has_build_sheet"] is True
        assert item["latest_quality_tier"] == "Premium"

        thumb_url = item["site_photo_thumb_url"]
        assert thumb_url == f"/thumbnails/{project_id}_256.jpg"
        thumb_path = tmp_path / "data" / "thumbnails" / f"{project_id}_256.jpg"
        assert thumb_path.exists()
        with Image.open(thumb_path) as thumbnail:
            assert max(thumbnail.size) <= 256

        thumb_resp = c.get(thumb_url)
        assert thumb_resp.status_code == 200
        assert thumb_resp.headers["content-type"] == "image/jpeg"

        cached_mtime = thumb_path.stat().st_mtime_ns
        second_resp = c.get("/api/projects")
        assert second_resp.status_code == 200
        assert thumb_path.stat().st_mtime_ns == cached_mtime
        assert second_resp.json()[0]["site_photo_thumb_url"] == thumb_url


# ---------------------------------------------------------------------------
# Thumbnail helper
# ---------------------------------------------------------------------------


class TestSitePhotoThumbnail:
    def test_generates_thumbnail_at_expected_path_and_dimensions(self, tmp_path):
        data_dir = tmp_path / "data"
        source_path = tmp_path / "site-photo.jpg"
        source_path.write_bytes(_valid_jpeg((1024, 768)))

        url = ensure_site_photo_thumbnail(
            project_id=42,
            site_photo_path=source_path,
            data_dir=data_dir,
        )

        assert url == "/thumbnails/42_256.jpg"
        thumbnail_path = site_photo_thumbnail_path(data_dir, 42)
        assert thumbnail_path.exists()
        with Image.open(thumbnail_path) as thumbnail:
            assert thumbnail.format == "JPEG"
            assert max(thumbnail.size) <= 256

    def test_reuses_existing_cached_thumbnail(self, tmp_path):
        data_dir = tmp_path / "data"
        source_path = tmp_path / "site-photo.jpg"
        source_path.write_bytes(_valid_jpeg((1024, 768)))

        url = ensure_site_photo_thumbnail(42, source_path, data_dir)
        thumbnail_path = site_photo_thumbnail_path(data_dir, 42)
        cached_mtime = thumbnail_path.stat().st_mtime_ns

        source_path.write_bytes(_valid_jpeg((200, 100)))
        second_url = ensure_site_photo_thumbnail(42, source_path, data_dir)

        assert second_url == url
        assert thumbnail_path.stat().st_mtime_ns == cached_mtime


# ---------------------------------------------------------------------------
# GET /api/projects/{id}
# ---------------------------------------------------------------------------


class TestGetProject:
    def test_returns_project_detail(self, client):
        c, _ = client
        create_resp = c.post(
            "/api/projects",
            data={"address": "123 Main St", "lot_size_sqft": "5000", "house_sqft": "2000"},
            files={"site_photo": ("p.jpg", _FAKE_JPEG, "image/jpeg")},
        )
        project_id = create_resp.json()["id"]

        resp = c.get(f"/api/projects/{project_id}")
        assert resp.status_code == 200
        body = resp.json()
        assert body["id"] == project_id
        assert body["address"] == "123 Main St"
        assert body["lot_size_sqft"] == 5000.0
        assert body["house_sqft"] == 2000.0
        assert "design_requests" in body
        assert isinstance(body["design_requests"], list)
        assert body["design_requests"] == []

    def test_nonexistent_project_returns_404(self, client):
        c, _ = client
        resp = c.get("/api/projects/99999")
        assert resp.status_code == 404
