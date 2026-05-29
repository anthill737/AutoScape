"""Tests for Build Sheet endpoints: dimension-defaults, POST/GET build-sheet."""

import pathlib
from typing import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import get_db
from app.domain.retailers import APPROVED_RETAILERS
from app.main import app, get_data_dir
from app.models import Base, DesignRequest, Project, Render

_FAKE_PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100
_HOME_DEPOT = APPROVED_RETAILERS[0]

_MOCK_BUILD_SHEET = {
    "material_items": [
        {
            "name": "Pressure-treated 2x6",
            "quantity": 20,
            "unit": "board",
            "unit_cost_range": "$8 - $12",
            "total_cost_range": "$160 - $240",
            "vendor": _HOME_DEPOT["name"],
            "product_url": f"https://www.{_HOME_DEPOT['domain']}/p/123",
            "notes": "16-foot lengths",
        }
    ],
    "tool_list": ["Circular saw", "Drill"],
    "build_steps": [
        {
            "step_number": 1,
            "description": "Excavate footing locations",
            "estimated_time": "3 hours",
            "skill_notes": "Use a string line",
        }
    ],
    "total_cost_range": "$2,000 - $3,500",
    "skill_level": "Intermediate",
    "assumptions": ["Level ground assumed", "Standard 12x16 ft deck"],
}

_MOSTLY_UNAPPROVED_BUILD_SHEET = {
    **_MOCK_BUILD_SHEET,
    "material_items": [
        {
            **_MOCK_BUILD_SHEET["material_items"][0],
            "name": "Approved deck board",
            "product_url": f"https://www.{_HOME_DEPOT['domain']}/p/123",
        },
        {
            **_MOCK_BUILD_SHEET["material_items"][0],
            "name": "Amazon outdoor light",
            "product_url": "https://www.amazon.com/dp/abc",
        },
        {
            **_MOCK_BUILD_SHEET["material_items"][0],
            "name": "Unknown planter",
            "product_url": "https://example.com/planter",
        },
    ],
    "assumptions": [],
}

_MOCK_DIMENSION_DEFAULTS = {
    "deck_width_ft": "12",
    "deck_length_ft": "16",
    "deck_height_ft": "2",
}

_MOCK_SEARCH_RESULTS = [
    {"category": "Deck", "urls": ["https://example.com/deck"], "snippets": ["Deck materials"]},
]


@pytest.fixture
def setup(tmp_path):
    """Create a test DB with a Project, DesignRequest, and Render seeded directly."""
    db_path = tmp_path / "test.db"
    engine = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)

    # Seed test data
    image_dir = tmp_path / "data" / "images" / "1"
    image_dir.mkdir(parents=True)
    image_path = image_dir / "render_1.png"
    image_path.write_bytes(_FAKE_PNG)

    with SessionLocal() as db:
        project = Project(
            address="1 Test Lane",
            lot_size_sqft=5000.0,
            house_sqft=2000.0,
            site_photo_path=str(image_dir / "site_photo.jpg"),
        )
        db.add(project)
        db.flush()

        dr = DesignRequest(
            project_id=project.id,
            image_provider="gemini_flash_image",
            feature_categories=["Deck", "Garden Beds"],
            style="Modern",
            quality_tier="Budget",
            composed_prompt="Add a deck",
        )
        db.add(dr)
        db.flush()

        render = Render(
            design_request_id=dr.id,
            image_path=str(image_path),
            is_chosen=False,
        )
        db.add(render)
        db.commit()
        db.refresh(render)
        render_id = render.id

    def override_get_db() -> Generator:
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()

    def override_get_data_dir() -> pathlib.Path:
        return tmp_path / "data"

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_data_dir] = override_get_data_dir

    with TestClient(app) as c:
        yield c, render_id

    app.dependency_overrides.clear()
    engine.dispose()


@pytest.fixture
def sparse_setup(tmp_path):
    """Create a Render whose parent DesignRequest has no Feature Categories."""
    db_path = tmp_path / "test.db"
    engine = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)

    image_dir = tmp_path / "data" / "images" / "1"
    image_dir.mkdir(parents=True)
    image_path = image_dir / "render_1.png"
    image_path.write_bytes(_FAKE_PNG)

    with SessionLocal() as db:
        project = Project(
            address="1 Sparse Lane",
            lot_size_sqft=None,
            house_sqft=None,
            site_photo_path=str(image_dir / "site_photo.jpg"),
        )
        db.add(project)
        db.flush()

        dr = DesignRequest(
            project_id=project.id,
            image_provider="gemini_flash_image",
            feature_categories=[],
            style="Modern",
            quality_tier="Budget",
            composed_prompt="General landscaping",
        )
        db.add(dr)
        db.flush()

        render = Render(
            design_request_id=dr.id,
            image_path=str(image_path),
            is_chosen=False,
        )
        db.add(render)
        db.commit()
        db.refresh(render)
        render_id = render.id

    def override_get_db() -> Generator:
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()

    def override_get_data_dir() -> pathlib.Path:
        return tmp_path / "data"

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_data_dir] = override_get_data_dir

    with TestClient(app) as c:
        yield c, render_id

    app.dependency_overrides.clear()
    engine.dispose()


# ---------------------------------------------------------------------------
# GET/POST /api/renders/{id}/dimension-defaults
# ---------------------------------------------------------------------------


class TestDimensionDefaults:
    def test_returns_200_with_dict(self, setup, monkeypatch):
        c, render_id = setup
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test-fake")

        with patch(
            "app.main.suggest_dimension_defaults",
            new=AsyncMock(return_value=_MOCK_DIMENSION_DEFAULTS),
        ):
            resp = c.post(f"/api/renders/{render_id}/dimension-defaults")

        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, dict)
        assert "deck_width_ft" in data
        assert data["deck_width_ft"] == "12"

    def test_get_returns_200_with_dict(self, setup, monkeypatch):
        c, render_id = setup
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test-fake")

        with patch(
            "app.main.suggest_dimension_defaults",
            new=AsyncMock(return_value=_MOCK_DIMENSION_DEFAULTS),
        ):
            resp = c.get(f"/api/renders/{render_id}/dimension-defaults")

        assert resp.status_code == 200
        assert resp.json()["deck_width_ft"] == "12"

    def test_values_are_strings(self, setup, monkeypatch):
        c, render_id = setup
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test-fake")

        with patch(
            "app.main.suggest_dimension_defaults",
            new=AsyncMock(return_value=_MOCK_DIMENSION_DEFAULTS),
        ):
            resp = c.post(f"/api/renders/{render_id}/dimension-defaults")

        assert resp.status_code == 200
        for v in resp.json().values():
            assert isinstance(v, str), f"Expected string value, got {type(v)}: {v!r}"

    def test_missing_anthropic_key_returns_400(self, setup, monkeypatch):
        c, render_id = setup
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

        from app.providers.base import MissingApiKeyError

        with patch(
            "app.main.suggest_dimension_defaults",
            new=AsyncMock(
                side_effect=MissingApiKeyError("ANTHROPIC_API_KEY is not set in the environment.")
            ),
        ):
            resp = c.post(f"/api/renders/{render_id}/dimension-defaults")

        assert resp.status_code == 400
        assert "ANTHROPIC_API_KEY" in resp.json()["detail"]

    def test_unknown_render_returns_404(self, setup):
        c, _ = setup
        resp = c.post("/api/renders/99999/dimension-defaults")
        assert resp.status_code == 404

    def test_empty_feature_categories_return_empty_defaults_without_llm(self, sparse_setup):
        c, render_id = sparse_setup

        with patch("app.main.suggest_dimension_defaults", new=AsyncMock()) as mock_suggest:
            resp = c.get(f"/api/renders/{render_id}/dimension-defaults")

        assert resp.status_code == 200
        assert resp.json() == {}
        mock_suggest.assert_not_awaited()


# ---------------------------------------------------------------------------
# POST /api/renders/{id}/build-sheet
# ---------------------------------------------------------------------------


_VALID_POST_BODY = {
    "materials_llm": "claude_sonnet",
    "dimensions": {"deck_width_ft": 12, "deck_length_ft": 16},
}


class TestCreateBuildSheet:
    def _post_build_sheet(self, c, render_id, body=None):
        body = body or _VALID_POST_BODY
        with patch(
            "app.main.SearchGrounding.search",
            new=AsyncMock(return_value=_MOCK_SEARCH_RESULTS),
        ):
            mock_adapter = MagicMock()
            mock_adapter.generate_build_sheet = AsyncMock(return_value=_MOCK_BUILD_SHEET)
            with patch(
                "app.main.MaterialsLLM.make_adapter",
                return_value=mock_adapter,
            ):
                with patch(
                    "app.domain.build_sheet_validation.validate_material_item_url",
                    return_value=(True, "URL passed validation."),
                ):
                    return c.post(f"/api/renders/{render_id}/build-sheet", json=body)

    def test_returns_201_with_all_required_fields(self, setup, monkeypatch):
        c, render_id = setup
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
        monkeypatch.setenv("PERPLEXITY_API_KEY", "px-test")

        resp = self._post_build_sheet(c, render_id)

        assert resp.status_code == 201
        data = resp.json()
        assert "id" in data
        assert isinstance(data["material_items"], list)
        assert len(data["material_items"]) >= 1
        assert isinstance(data["tool_list"], list)
        assert len(data["tool_list"]) >= 1
        assert isinstance(data["build_steps"], list)
        assert len(data["build_steps"]) >= 1
        assert "total_cost_range" in data
        assert "skill_level" in data
        assert "assumptions" in data

    def test_keeps_all_items_and_rewrites_to_search_links(
        self, setup, monkeypatch
    ):
        c, render_id = setup
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
        monkeypatch.setenv("PERPLEXITY_API_KEY", "px-test")
        draft = {
            **_MOCK_BUILD_SHEET,
            "material_items": [
                {
                    **_MOCK_BUILD_SHEET["material_items"][0],
                    "name": "Approved deck board",
                    "product_url": f"https://www.{_HOME_DEPOT['domain']}/p/123",
                },
                {
                    **_MOCK_BUILD_SHEET["material_items"][0],
                    "name": "Search result lumber",
                    "product_url": f"https://www.{_HOME_DEPOT['domain']}/s/lumber",
                },
            ],
            "assumptions": [],
        }

        def fake_validate(item_name, candidate_url):
            if "Search result" in item_name:
                return False, "URL appears to be a search/category page."
            return True, "URL passed validation."

        with patch(
            "app.main.SearchGrounding.search",
            new=AsyncMock(return_value=_MOCK_SEARCH_RESULTS),
        ):
            mock_adapter = MagicMock()
            mock_adapter.generate_build_sheet = AsyncMock(return_value=draft)
            with patch("app.main.MaterialsLLM.make_adapter", return_value=mock_adapter):
                with patch(
                    "app.domain.build_sheet_validation.validate_material_item_url",
                    side_effect=fake_validate,
                ):
                    resp = c.post(f"/api/renders/{render_id}/build-sheet", json=_VALID_POST_BODY)

        assert resp.status_code == 201
        data = resp.json()
        # No items are dropped anymore — every material gets a working search link.
        assert [item["name"] for item in data["material_items"]] == [
            "Approved deck board",
            "Search result lumber",
        ]
        assert not any("failed validation" in a for a in data["assumptions"])
        for item in data["material_items"]:
            assert item["product_url"].startswith(f"https://www.{_HOME_DEPOT['domain']}/s/")

        get_resp = c.get(f"/api/renders/{render_id}/build-sheet")
        assert get_resp.status_code == 200
        assert get_resp.json()["material_items"] == data["material_items"]
        assert get_resp.json()["assumptions"] == data["assumptions"]

    def test_unknown_render_returns_404(self, setup):
        c, _ = setup
        resp = c.post("/api/renders/99999/build-sheet", json=_VALID_POST_BODY)
        assert resp.status_code == 404

    def test_invalid_materials_llm_returns_422(self, setup):
        c, render_id = setup
        resp = c.post(
            f"/api/renders/{render_id}/build-sheet",
            json={"materials_llm": "not_a_real_llm", "dimensions": {}},
        )
        assert resp.status_code == 422

    def test_missing_perplexity_key_returns_400(self, setup, monkeypatch):
        c, render_id = setup
        monkeypatch.delenv("PERPLEXITY_API_KEY", raising=False)

        from app.providers.base import MissingApiKeyError

        with patch(
            "app.main.SearchGrounding.search",
            new=AsyncMock(
                side_effect=MissingApiKeyError("PERPLEXITY_API_KEY is not set in the environment.")
            ),
        ):
            resp = c.post(f"/api/renders/{render_id}/build-sheet", json=_VALID_POST_BODY)

        assert resp.status_code == 400
        assert "PERPLEXITY_API_KEY" in resp.json()["detail"]

    def test_missing_llm_key_returns_400(self, setup, monkeypatch):
        c, render_id = setup
        monkeypatch.setenv("PERPLEXITY_API_KEY", "px-test")
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

        from app.providers.base import MissingApiKeyError

        with patch(
            "app.main.SearchGrounding.search",
            new=AsyncMock(return_value=_MOCK_SEARCH_RESULTS),
        ):
            mock_adapter = MagicMock()
            mock_adapter.generate_build_sheet = AsyncMock(
                side_effect=MissingApiKeyError("ANTHROPIC_API_KEY is not set in the environment.")
            )
            with patch("app.main.MaterialsLLM.make_adapter", return_value=mock_adapter):
                resp = c.post(f"/api/renders/{render_id}/build-sheet", json=_VALID_POST_BODY)

        assert resp.status_code == 400
        assert "ANTHROPIC_API_KEY" in resp.json()["detail"]

    def test_llm_quota_error_returns_provider_status(self, setup, monkeypatch):
        c, render_id = setup
        monkeypatch.setenv("PERPLEXITY_API_KEY", "px-test")

        with patch(
            "app.main.SearchGrounding.search",
            new=AsyncMock(return_value=_MOCK_SEARCH_RESULTS),
        ):
            mock_adapter = MagicMock()
            mock_adapter.generate_build_sheet = AsyncMock(
                side_effect=RuntimeError("429 RESOURCE_EXHAUSTED quota exceeded")
            )
            with patch("app.main.MaterialsLLM.make_adapter", return_value=mock_adapter):
                with patch(
                    "app.domain.build_sheet_validation.validate_material_item_url",
                    return_value=(True, "URL passed validation."),
                ):
                    resp = c.post(f"/api/renders/{render_id}/build-sheet", json=_VALID_POST_BODY)

        assert resp.status_code == 503
        assert "Materials LLM failed" in resp.json()["detail"]
        assert "RESOURCE_EXHAUSTED" in resp.json()["detail"]

    def test_upsert_replaces_existing_build_sheet(self, setup, monkeypatch):
        c, render_id = setup
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
        monkeypatch.setenv("PERPLEXITY_API_KEY", "px-test")

        # First POST
        resp1 = self._post_build_sheet(c, render_id)
        assert resp1.status_code == 201

        # Second POST — should replace, not duplicate
        resp2 = self._post_build_sheet(c, render_id)
        assert resp2.status_code == 201
        id2 = resp2.json()["id"]

        # GET should still return one result, matching the second POST's ID
        get_resp = c.get(f"/api/renders/{render_id}/build-sheet")
        assert get_resp.status_code == 200
        assert get_resp.json()["id"] == id2

    def test_unapproved_items_are_rewritten_not_dropped(
        self, setup, monkeypatch
    ):
        c, render_id = setup
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
        monkeypatch.setenv("PERPLEXITY_API_KEY", "px-test")

        with patch(
            "app.main.SearchGrounding.search",
            new=AsyncMock(return_value=_MOCK_SEARCH_RESULTS),
        ):
            mock_adapter = MagicMock()
            mock_adapter.generate_build_sheet = AsyncMock(
                return_value=_MOSTLY_UNAPPROVED_BUILD_SHEET
            )
            with patch("app.main.MaterialsLLM.make_adapter", return_value=mock_adapter):
                with patch(
                    "app.domain.build_sheet_validation.validate_material_item_url",
                    return_value=(True, "URL passed validation."),
                ):
                    resp = c.post(f"/api/renders/{render_id}/build-sheet", json=_VALID_POST_BODY)

        assert resp.status_code == 201
        data = resp.json()
        # Items are no longer dropped for unapproved/unreachable URLs; each is
        # rewritten to a working approved-retailer search link instead.
        assert len(data["material_items"]) == len(
            _MOSTLY_UNAPPROVED_BUILD_SHEET["material_items"]
        )
        assert not data["warning"]  # nullable field exists in the schema, but is unset
        for item in data["material_items"]:
            assert "/s/" in item["product_url"] or "search" in item["product_url"]


# ---------------------------------------------------------------------------
# GET /api/renders/{id}/build-sheet
# ---------------------------------------------------------------------------


class TestGetBuildSheet:
    def _post_build_sheet(self, c, render_id):
        with patch(
            "app.main.SearchGrounding.search",
            new=AsyncMock(return_value=_MOCK_SEARCH_RESULTS),
        ):
            mock_adapter = MagicMock()
            mock_adapter.generate_build_sheet = AsyncMock(return_value=_MOCK_BUILD_SHEET)
            with patch("app.main.MaterialsLLM.make_adapter", return_value=mock_adapter):
                with patch(
                    "app.domain.build_sheet_validation.validate_material_item_url",
                    return_value=(True, "URL passed validation."),
                ):
                    return c.post(f"/api/renders/{render_id}/build-sheet", json=_VALID_POST_BODY)

    def test_returns_404_when_no_build_sheet(self, setup):
        c, render_id = setup
        resp = c.get(f"/api/renders/{render_id}/build-sheet")
        assert resp.status_code == 404

    def test_returns_404_for_unknown_render(self, setup):
        c, _ = setup
        resp = c.get("/api/renders/99999/build-sheet")
        assert resp.status_code == 404

    def test_returns_200_with_same_content_after_post(self, setup, monkeypatch):
        c, render_id = setup
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
        monkeypatch.setenv("PERPLEXITY_API_KEY", "px-test")

        post_resp = self._post_build_sheet(c, render_id)
        assert post_resp.status_code == 201

        get_resp = c.get(f"/api/renders/{render_id}/build-sheet")
        assert get_resp.status_code == 200

        post_data = post_resp.json()
        get_data = get_resp.json()
        assert get_data["id"] == post_data["id"]
        assert get_data["material_items"] == post_data["material_items"]
        assert get_data["tool_list"] == post_data["tool_list"]
        assert get_data["build_steps"] == post_data["build_steps"]
        assert get_data["total_cost_range"] == post_data["total_cost_range"]
        assert get_data["skill_level"] == post_data["skill_level"]
        assert get_data["assumptions"] == post_data["assumptions"]

    def test_get_does_not_make_ai_calls(self, setup, monkeypatch):
        """GET /build-sheet must not invoke any AI provider."""
        c, render_id = setup
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
        monkeypatch.setenv("PERPLEXITY_API_KEY", "px-test")

        self._post_build_sheet(c, render_id)

        # If GET were to call an AI provider, removing keys would cause it to fail.
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        monkeypatch.delenv("PERPLEXITY_API_KEY", raising=False)

        resp = c.get(f"/api/renders/{render_id}/build-sheet")
        assert resp.status_code == 200
