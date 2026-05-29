"""Tests for Design Request API and Chosen Render endpoint (P1-T6)."""

import logging
import pathlib
import sqlite3
from typing import Generator
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient
from google.genai import errors as genai_errors
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import get_db
from app.main import app, get_data_dir
from app.models import Base
from app.providers.base import MissingApiKeyError
from app.providers.gemini_flash import _GEMINI_MODEL, GeminiFlashImageAdapter

_FAKE_JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 100
_FAKE_PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100
_FAKE_RENDER_BYTES = b"\x89PNG\r\n\x1a\n" + b"\x01" * 200

_GEMINI_SLUG = "gemini_flash_image"
_GPT_SLUG = "gpt_image"

_VALID_BODY = {
    "image_provider": _GEMINI_SLUG,
    "feature_categories": ["Deck", "Pergola"],
    "style": "Modern",
    "quality_tier": "Budget",
    "composed_prompt": "Add a wooden deck and pergola",
}


def _recorded_gemini_quota_error() -> genai_errors.ClientError:
    return genai_errors.ClientError(
        429,
        {
            "error": {
                "code": 429,
                "message": (
                    "You exceeded your current quota, please check your plan and billing "
                    "details. Quota exceeded for metric: "
                    "generativelanguage.googleapis.com/generate_content_free_tier_requests, "
                    f"limit: 0, model: {_GEMINI_MODEL}"
                ),
                "status": "RESOURCE_EXHAUSTED",
                "details": [
                    {
                        "@type": "type.googleapis.com/google.rpc.QuotaFailure",
                        "violations": [
                            {
                                "quotaMetric": (
                                    "generativelanguage.googleapis.com/"
                                    "generate_content_free_tier_requests"
                                ),
                                "quotaId": "GenerateRequestsPerDayPerProjectPerModel-FreeTier",
                                "quotaDimensions": {
                                    "location": "global",
                                    "model": _GEMINI_MODEL,
                                },
                            }
                        ],
                    },
                    {
                        "@type": "type.googleapis.com/google.rpc.RetryInfo",
                        "retryDelay": "44s",
                    },
                ],
            }
        },
    )


def _recorded_gemini_auth_error(code: int = 401) -> genai_errors.ClientError:
    status = "UNAUTHENTICATED" if code == 401 else "PERMISSION_DENIED"
    return genai_errors.ClientError(
        code,
        {
            "error": {
                "code": code,
                "message": "API key not valid. Please pass a valid API key.",
                "status": status,
            }
        },
    )


@pytest.fixture
def client(tmp_path):
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


@pytest.fixture
def project_id(client):
    c, _ = client
    resp = c.post(
        "/api/projects",
        data={"address": "1 Test Lane", "lot_size_sqft": "5000", "house_sqft": "2000"},
        files={"site_photo": ("photo.jpg", _FAKE_JPEG, "image/jpeg")},
    )
    assert resp.status_code == 201
    return resp.json()["id"]


# ---------------------------------------------------------------------------
# POST /api/projects/{id}/design-requests
# ---------------------------------------------------------------------------


class TestListDesignRequests:
    def test_valid_project_returns_200_json_array(self, client, project_id):
        c, _ = client
        resp = c.get(f"/api/projects/{project_id}/design-requests")

        assert resp.status_code == 200
        assert resp.json() == []

    def test_returns_design_requests_with_render_urls(self, client, project_id):
        c, _ = client
        with patch.object(GeminiFlashImageAdapter, "generate", new_callable=AsyncMock) as mock_gen:
            mock_gen.return_value = [_FAKE_RENDER_BYTES, _FAKE_RENDER_BYTES, _FAKE_RENDER_BYTES]
            create_resp = c.post(f"/api/projects/{project_id}/design-requests", json=_VALID_BODY)
        assert create_resp.status_code == 201

        resp = c.get(f"/api/projects/{project_id}/design-requests")

        assert resp.status_code == 200
        body = resp.json()
        assert len(body) == 1
        assert body[0]["project_id"] == project_id
        assert len(body[0]["renders"]) == 3
        for render in body[0]["renders"]:
            assert render["image_url"] == f"/renders/{render['id']}"

    def test_nonexistent_project_returns_404(self, client):
        c, _ = client
        resp = c.get("/api/projects/99999/design-requests")

        assert resp.status_code == 404
        assert resp.json()["detail"] == "Project not found"


class TestCreateDesignRequest:
    def test_valid_request_returns_201(self, client, project_id):
        c, _ = client
        with patch.object(GeminiFlashImageAdapter, "generate", new_callable=AsyncMock) as mock_gen:
            mock_gen.return_value = [_FAKE_RENDER_BYTES, _FAKE_RENDER_BYTES, _FAKE_RENDER_BYTES]
            resp = c.post(f"/api/projects/{project_id}/design-requests", json=_VALID_BODY)

        assert resp.status_code == 201
        body = resp.json()
        assert "id" in body
        assert body["project_id"] == project_id

    def test_response_has_exactly_3_renders(self, client, project_id):
        c, _ = client
        with patch.object(GeminiFlashImageAdapter, "generate", new_callable=AsyncMock) as mock_gen:
            mock_gen.return_value = [_FAKE_RENDER_BYTES, _FAKE_RENDER_BYTES, _FAKE_RENDER_BYTES]
            resp = c.post(f"/api/projects/{project_id}/design-requests", json=_VALID_BODY)

        assert resp.status_code == 201
        renders = resp.json()["renders"]
        assert len(renders) == 3
        for r in renders:
            assert "id" in r
            assert "image_url" in r
            assert r["image_url"] is not None
            assert r["is_chosen"] is False

    def test_renders_saved_to_disk(self, client, project_id):
        c, tmp_path = client
        with patch.object(GeminiFlashImageAdapter, "generate", new_callable=AsyncMock) as mock_gen:
            mock_gen.return_value = [_FAKE_RENDER_BYTES, _FAKE_RENDER_BYTES, _FAKE_RENDER_BYTES]
            resp = c.post(f"/api/projects/{project_id}/design-requests", json=_VALID_BODY)

        assert resp.status_code == 201
        renders = resp.json()["renders"]
        for r in renders:
            render_id = r["id"]
            expected_path = tmp_path / "data" / "images" / str(project_id) / f"{render_id}.png"
            assert expected_path.exists(), f"Expected Render file at {expected_path}"
            assert expected_path.read_bytes() == _FAKE_RENDER_BYTES

    def test_render_directory_is_created_if_missing_before_save(self, client, project_id):
        c, tmp_path = client
        source_photo_path = tmp_path / "source_photo.jpg"
        source_photo_path.write_bytes(_FAKE_JPEG)

        render_dir = tmp_path / "data" / "images" / str(project_id)
        for child in render_dir.iterdir():
            child.unlink()
        render_dir.rmdir()
        assert not render_dir.exists()

        with sqlite3.connect(tmp_path / "test.db") as conn:
            conn.execute(
                "UPDATE project SET site_photo_path = ? WHERE id = ?",
                (str(source_photo_path), project_id),
            )

        with patch.object(GeminiFlashImageAdapter, "generate", new_callable=AsyncMock) as mock_gen:
            mock_gen.return_value = [_FAKE_RENDER_BYTES, _FAKE_RENDER_BYTES, _FAKE_RENDER_BYTES]
            resp = c.post(f"/api/projects/{project_id}/design-requests", json=_VALID_BODY)

        assert resp.status_code == 201
        assert render_dir.is_dir()
        for r in resp.json()["renders"]:
            render_path = render_dir / f"{r['id']}.png"
            assert render_path.exists()
            assert render_path.read_bytes() == _FAKE_RENDER_BYTES

    def test_composed_prompt_passed_to_provider(self, client, project_id):
        c, _ = client
        prompt = "Add a cedar deck with railings"
        body = {**_VALID_BODY, "composed_prompt": prompt}
        with patch.object(GeminiFlashImageAdapter, "generate", new_callable=AsyncMock) as mock_gen:
            mock_gen.return_value = [_FAKE_RENDER_BYTES, _FAKE_RENDER_BYTES, _FAKE_RENDER_BYTES]
            c.post(f"/api/projects/{project_id}/design-requests", json=body)
            _, call_prompt = mock_gen.call_args[0]
        assert call_prompt == prompt

    def test_nonexistent_project_returns_404(self, client):
        c, _ = client
        resp = c.post("/api/projects/99999/design-requests", json=_VALID_BODY)
        assert resp.status_code == 404

    def test_invalid_provider_returns_422(self, client, project_id):
        c, _ = client
        body = {**_VALID_BODY, "image_provider": "bad_provider"}
        resp = c.post(f"/api/projects/{project_id}/design-requests", json=body)
        assert resp.status_code == 422

    def test_missing_api_key_returns_400_not_500(self, client, project_id):
        c, _ = client
        error_msg = "GOOGLE_API_KEY is not set. Add it to .env.local."
        with patch.object(GeminiFlashImageAdapter, "generate", new_callable=AsyncMock) as mock_gen:
            mock_gen.side_effect = MissingApiKeyError(error_msg)
            resp = c.post(f"/api/projects/{project_id}/design-requests", json=_VALID_BODY)

        assert resp.status_code == 400
        detail = resp.json()["detail"]
        assert "GOOGLE_API_KEY" in detail

    def test_missing_api_key_detail_names_env_var(self, client, project_id):
        c, _ = client
        error_msg = "OPENAI_API_KEY is not set. Add it to .env.local."
        body = {**_VALID_BODY, "image_provider": _GPT_SLUG}
        from app.providers.gpt_image import GptImageAdapter

        with patch.object(GptImageAdapter, "generate", new_callable=AsyncMock) as mock_gen:
            mock_gen.side_effect = MissingApiKeyError(error_msg)
            resp = c.post(f"/api/projects/{project_id}/design-requests", json=body)

        assert resp.status_code == 400
        assert "OPENAI_API_KEY" in resp.json()["detail"]

    def test_provider_quota_error_returns_structured_503_not_500(self, client, project_id):
        c, _ = client
        provider_error = RuntimeError("429 RESOURCE_EXHAUSTED quota exceeded")

        with patch.object(GeminiFlashImageAdapter, "generate", new_callable=AsyncMock) as mock_gen:
            mock_gen.side_effect = provider_error
            resp = c.post(f"/api/projects/{project_id}/design-requests", json=_VALID_BODY)

        assert resp.status_code == 503
        detail = resp.json()["detail"]
        assert detail == (
            "Image provider failed: RuntimeError: 429 RESOURCE_EXHAUSTED quota exceeded"
        )

        project_resp = c.get(f"/api/projects/{project_id}")
        assert project_resp.status_code == 200
        assert project_resp.json()["design_requests"] == []

    def test_provider_error_is_handled_without_traceback_log(self, client, project_id, caplog):
        c, _ = client
        provider_error = RuntimeError("429 RESOURCE_EXHAUSTED quota exceeded")

        with caplog.at_level(logging.WARNING, logger="app.main"):
            with patch.object(
                GeminiFlashImageAdapter, "generate", new_callable=AsyncMock
            ) as mock_gen:
                mock_gen.side_effect = provider_error
                resp = c.post(f"/api/projects/{project_id}/design-requests", json=_VALID_BODY)

        assert resp.status_code == 503
        assert resp.json()["detail"] == (
            "Image provider failed: RuntimeError: 429 RESOURCE_EXHAUSTED quota exceeded"
        )
        assert "Image provider request failed; returning HTTP 503" in caplog.text
        assert "Traceback (most recent call last)" not in caplog.text
        assert "RuntimeError: 429 RESOURCE_EXHAUSTED quota exceeded" not in caplog.text

    def test_non_quota_non_auth_provider_error_returns_500(self, client, project_id):
        c, _ = client
        provider_error = RuntimeError("provider unavailable")

        with patch.object(GeminiFlashImageAdapter, "generate", new_callable=AsyncMock) as mock_gen:
            mock_gen.side_effect = provider_error
            resp = c.post(f"/api/projects/{project_id}/design-requests", json=_VALID_BODY)

        assert resp.status_code == 500
        assert resp.json()["detail"] == (
            "Image provider failed: RuntimeError: provider unavailable"
        )

        project_resp = c.get(f"/api/projects/{project_id}")
        assert project_resp.status_code == 200
        assert project_resp.json()["design_requests"] == []

    def test_recorded_gemini_quota_response_returns_503_and_rolls_back(
        self, client, project_id
    ):
        c, _ = client

        with patch.object(GeminiFlashImageAdapter, "generate", new_callable=AsyncMock) as mock_gen:
            mock_gen.side_effect = _recorded_gemini_quota_error()
            resp = c.post(f"/api/projects/{project_id}/design-requests", json=_VALID_BODY)

        assert resp.status_code == 503
        detail = resp.json()["detail"]
        assert detail.startswith("Image provider failed: ClientError: 429 RESOURCE_EXHAUSTED.")
        assert "generate_content_free_tier_requests" in detail
        assert _GEMINI_MODEL in detail

        project_resp = c.get(f"/api/projects/{project_id}")
        assert project_resp.status_code == 200
        assert project_resp.json()["design_requests"] == []

    def test_gemini_sdk_quota_error_returns_429_with_actionable_detail(
        self, client, project_id, monkeypatch
    ):
        c, _ = client
        monkeypatch.setenv("GOOGLE_API_KEY", "test-key")

        with patch.object(
            GeminiFlashImageAdapter, "_generate_one", new_callable=AsyncMock
        ) as mock_gen:
            mock_gen.side_effect = _recorded_gemini_quota_error()
            resp = c.post(f"/api/projects/{project_id}/design-requests", json=_VALID_BODY)

        assert resp.status_code == 429
        assert resp.json()["detail"] == (
            f"Gemini quota exceeded for model {_GEMINI_MODEL}. Enable billing at "
            "https://aistudio.google.com/app/apikey or switch the Image Provider dropdown "
            "to GptImage for this request."
        )

        project_resp = c.get(f"/api/projects/{project_id}")
        assert project_resp.status_code == 200
        assert project_resp.json()["design_requests"] == []

    @pytest.mark.parametrize("status_code", [401, 403])
    def test_gemini_sdk_auth_error_returns_401_with_key_file_detail(
        self, client, project_id, monkeypatch, status_code
    ):
        c, _ = client
        monkeypatch.setenv("GOOGLE_API_KEY", "test-key")

        with patch.object(
            GeminiFlashImageAdapter, "_generate_one", new_callable=AsyncMock
        ) as mock_gen:
            mock_gen.side_effect = _recorded_gemini_auth_error(status_code)
            resp = c.post(f"/api/projects/{project_id}/design-requests", json=_VALID_BODY)

        assert resp.status_code == 401
        detail = resp.json()["detail"]
        assert "Gemini authentication failed" in detail
        assert f"HTTP {status_code}" in detail
        assert "GOOGLE_API_KEY" in detail
        assert "backend/.env.local" in detail


# ---------------------------------------------------------------------------
# Iteration: parent_render_id
# ---------------------------------------------------------------------------


class TestIterationDesignRequest:
    def _create_dr(self, c, project_id):
        with patch.object(GeminiFlashImageAdapter, "generate", new_callable=AsyncMock) as mock_gen:
            mock_gen.return_value = [_FAKE_RENDER_BYTES, _FAKE_RENDER_BYTES, _FAKE_RENDER_BYTES]
            resp = c.post(f"/api/projects/{project_id}/design-requests", json=_VALID_BODY)
        assert resp.status_code == 201
        return resp.json()

    def test_iteration_sets_parent_render_id(self, client, project_id):
        c, _ = client
        dr1 = self._create_dr(c, project_id)
        parent_render_id = dr1["renders"][0]["id"]

        body = {**_VALID_BODY, "parent_render_id": parent_render_id}
        with patch.object(GeminiFlashImageAdapter, "generate", new_callable=AsyncMock) as mock_gen:
            mock_gen.return_value = [_FAKE_RENDER_BYTES, _FAKE_RENDER_BYTES, _FAKE_RENDER_BYTES]
            resp = c.post(f"/api/projects/{project_id}/design-requests", json=body)

        assert resp.status_code == 201
        body_out = resp.json()
        assert body_out["parent_render_id"] == parent_render_id

    def test_iteration_passes_parent_render_image_to_provider(self, client, project_id):
        c, _ = client
        distinct_bytes = b"\xff\xd8\xff\xe0" + b"\xab" * 150
        dr1 = self._create_dr(c, project_id)
        parent_render_id = dr1["renders"][0]["id"]
        render_id = dr1["renders"][0]["id"]

        # Overwrite the parent render's file on disk with distinct content
        _, tmp_path = client
        image_path = tmp_path / "data" / "images" / str(project_id) / f"{render_id}.png"
        image_path.write_bytes(distinct_bytes)

        body = {**_VALID_BODY, "parent_render_id": parent_render_id}
        captured = {}

        async def fake_generate(self, image_b64, prompt):
            import base64

            captured["image_bytes"] = base64.b64decode(image_b64)
            return [_FAKE_RENDER_BYTES, _FAKE_RENDER_BYTES, _FAKE_RENDER_BYTES]

        with patch.object(GeminiFlashImageAdapter, "generate", new=fake_generate):
            resp = c.post(f"/api/projects/{project_id}/design-requests", json=body)

        assert resp.status_code == 201
        assert captured["image_bytes"] == distinct_bytes

    def test_parent_render_wrong_project_returns_400(self, client, project_id):
        c, tmp_path = client
        # Create a second project
        resp2 = c.post(
            "/api/projects",
            data={"address": "2 Other St", "lot_size_sqft": "3000", "house_sqft": "1500"},
            files={"site_photo": ("p.jpg", _FAKE_JPEG, "image/jpeg")},
        )
        project_id_2 = resp2.json()["id"]

        # Create a render in project 2
        dr2 = self._create_dr(c, project_id_2)
        foreign_render_id = dr2["renders"][0]["id"]

        # Try to use that render as parent in project 1
        body = {**_VALID_BODY, "parent_render_id": foreign_render_id}
        with patch.object(GeminiFlashImageAdapter, "generate", new_callable=AsyncMock) as mock_gen:
            mock_gen.return_value = [_FAKE_RENDER_BYTES, _FAKE_RENDER_BYTES, _FAKE_RENDER_BYTES]
            resp = c.post(f"/api/projects/{project_id}/design-requests", json=body)

        assert resp.status_code == 400

    def test_nonexistent_parent_render_returns_404(self, client, project_id):
        c, _ = client
        body = {**_VALID_BODY, "parent_render_id": 99999}
        resp = c.post(f"/api/projects/{project_id}/design-requests", json=body)
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# PATCH /api/renders/{id}/choose
# ---------------------------------------------------------------------------


class TestChooseRender:
    def _create_dr_with_renders(self, c, project_id):
        with patch.object(GeminiFlashImageAdapter, "generate", new_callable=AsyncMock) as mock_gen:
            mock_gen.return_value = [_FAKE_RENDER_BYTES, _FAKE_RENDER_BYTES, _FAKE_RENDER_BYTES]
            resp = c.post(f"/api/projects/{project_id}/design-requests", json=_VALID_BODY)
        assert resp.status_code == 201
        return resp.json()["renders"]

    def test_choose_sets_is_chosen_true(self, client, project_id):
        c, _ = client
        renders = self._create_dr_with_renders(c, project_id)
        render_id = renders[0]["id"]

        resp = c.patch(f"/api/renders/{render_id}/choose")
        assert resp.status_code == 200
        assert resp.json()["is_chosen"] is True
        assert resp.json()["id"] == render_id

    def test_choose_clears_previous_chosen_in_same_dr(self, client, project_id):
        c, _ = client
        renders = self._create_dr_with_renders(c, project_id)
        first_id = renders[0]["id"]
        second_id = renders[1]["id"]

        # Choose the first render
        c.patch(f"/api/renders/{first_id}/choose")

        # Now choose the second render
        resp = c.patch(f"/api/renders/{second_id}/choose")
        assert resp.status_code == 200
        assert resp.json()["is_chosen"] is True

        # Verify the first render is no longer chosen via project detail
        project_resp = c.get(f"/api/projects/{project_id}")
        all_renders = project_resp.json()["design_requests"][0]["renders"]
        chosen = [r for r in all_renders if r["is_chosen"]]
        assert len(chosen) == 1
        assert chosen[0]["id"] == second_id

    def test_choose_returns_image_url(self, client, project_id):
        c, _ = client
        renders = self._create_dr_with_renders(c, project_id)
        render_id = renders[0]["id"]

        resp = c.patch(f"/api/renders/{render_id}/choose")
        assert resp.status_code == 200
        body = resp.json()
        assert "image_url" in body
        assert body["image_url"] == f"/renders/{render_id}"

    def test_choose_nonexistent_render_returns_404(self, client):
        c, _ = client
        resp = c.patch("/api/renders/99999/choose")
        assert resp.status_code == 404

    def test_choose_does_not_affect_other_design_requests(self, client, project_id):
        c, _ = client
        # Create two design requests
        renders_dr1 = self._create_dr_with_renders(c, project_id)
        renders_dr2 = self._create_dr_with_renders(c, project_id)

        # Choose render from DR1
        c.patch(f"/api/renders/{renders_dr1[0]['id']}/choose")
        # Choose render from DR2
        c.patch(f"/api/renders/{renders_dr2[0]['id']}/choose")

        # DR1 still has its chosen render
        project_resp = c.get(f"/api/projects/{project_id}")
        drs = project_resp.json()["design_requests"]
        dr1_id = renders_dr1[0]["design_request_id"]
        dr1_renders = next(dr["renders"] for dr in drs if dr["id"] == dr1_id)
        assert any(r["is_chosen"] for r in dr1_renders)
