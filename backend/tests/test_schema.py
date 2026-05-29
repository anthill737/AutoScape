"""Tests for the SQLite schema and Alembic migration (P1-T2, P2-T1)."""

import os
import pathlib
import tempfile

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import Base, BuildSheet, DesignRequest, Project, ProjectDimensions, Render

BACKEND_DIR = pathlib.Path(__file__).parent.parent


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _alembic_cfg(db_url: str) -> Config:
    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    # Use absolute path for script_location so tests pass regardless of CWD.
    cfg.set_main_option("script_location", str(BACKEND_DIR / "migrations"))
    cfg.set_main_option("sqlalchemy.url", db_url)
    return cfg


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="function")
def mem_engine():
    """In-memory SQLite engine with schema created via ORM (fast unit tests)."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    yield engine
    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture
def session(mem_engine):
    with Session(mem_engine) as s:
        yield s


@pytest.fixture
def session_with_render(session):
    """Session pre-populated with a Project, DesignRequest, and Render."""
    p = Project(address="1 Test St")
    session.add(p)
    session.flush()

    dr = DesignRequest(
        project_id=p.id,
        parent_render_id=None,
        image_provider="GeminiFlashImage",
        feature_categories=["Deck"],
        style="Modern",
        quality_tier="Budget",
        composed_prompt="Add a deck",
    )
    session.add(dr)
    session.flush()

    r = Render(design_request_id=dr.id, image_path="/renders/test.png", is_chosen=True)
    session.add(r)
    session.flush()

    return session, r


# ---------------------------------------------------------------------------
# Migration tests — run Alembic upgrade head against a temp file DB
# ---------------------------------------------------------------------------


def test_alembic_upgrade_creates_all_tables():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        db_path = tmp.name
    try:
        command.upgrade(_alembic_cfg(f"sqlite:///{db_path}"), "head")
        engine = create_engine(f"sqlite:///{db_path}")
        tables = set(inspect(engine).get_table_names())
        engine.dispose()
        expected = {"project", "design_request", "render", "build_sheet", "project_dimensions"}
        assert expected <= tables
    finally:
        os.unlink(db_path)


def test_alembic_project_columns():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        db_path = tmp.name
    try:
        command.upgrade(_alembic_cfg(f"sqlite:///{db_path}"), "head")
        engine = create_engine(f"sqlite:///{db_path}")
        cols = {c["name"] for c in inspect(engine).get_columns("project")}
        engine.dispose()
        expected = {"id", "address", "lot_size_sqft", "house_sqft", "site_photo_path", "created_at"}
        assert expected <= cols
    finally:
        os.unlink(db_path)


def test_alembic_design_request_columns():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        db_path = tmp.name
    try:
        command.upgrade(_alembic_cfg(f"sqlite:///{db_path}"), "head")
        engine = create_engine(f"sqlite:///{db_path}")
        cols = {c["name"] for c in inspect(engine).get_columns("design_request")}
        engine.dispose()
        assert {
            "id",
            "project_id",
            "parent_render_id",
            "image_provider",
            "feature_categories",
            "style",
            "quality_tier",
            "composed_prompt",
            "created_at",
        } <= cols
    finally:
        os.unlink(db_path)


def test_alembic_render_columns():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        db_path = tmp.name
    try:
        command.upgrade(_alembic_cfg(f"sqlite:///{db_path}"), "head")
        engine = create_engine(f"sqlite:///{db_path}")
        cols = {c["name"] for c in inspect(engine).get_columns("render")}
        engine.dispose()
        assert {"id", "design_request_id", "image_path", "is_chosen", "created_at"} <= cols
    finally:
        os.unlink(db_path)


def test_alembic_build_sheet_columns():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        db_path = tmp.name
    try:
        command.upgrade(_alembic_cfg(f"sqlite:///{db_path}"), "head")
        engine = create_engine(f"sqlite:///{db_path}")
        cols = {c["name"] for c in inspect(engine).get_columns("build_sheet")}
        engine.dispose()
        assert {"id", "render_id", "materials_llm", "content_json", "created_at"} <= cols
    finally:
        os.unlink(db_path)


def test_alembic_project_dimensions_columns():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        db_path = tmp.name
    try:
        command.upgrade(_alembic_cfg(f"sqlite:///{db_path}"), "head")
        engine = create_engine(f"sqlite:///{db_path}")
        cols = {c["name"] for c in inspect(engine).get_columns("project_dimensions")}
        engine.dispose()
        assert {"id", "render_id", "dimensions_json", "created_at"} <= cols
    finally:
        os.unlink(db_path)


def test_alembic_downgrade_removes_tables():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        db_path = tmp.name
    try:
        cfg = _alembic_cfg(f"sqlite:///{db_path}")
        command.upgrade(cfg, "head")
        command.downgrade(cfg, "base")
        engine = create_engine(f"sqlite:///{db_path}")
        tables = set(inspect(engine).get_table_names())
        engine.dispose()
        assert "project" not in tables
        assert "design_request" not in tables
        assert "render" not in tables
        assert "build_sheet" not in tables
        assert "project_dimensions" not in tables
    finally:
        os.unlink(db_path)


# ---------------------------------------------------------------------------
# ORM / insert behaviour tests
# ---------------------------------------------------------------------------


def test_tables_exist_via_orm(mem_engine):
    tables = set(inspect(mem_engine).get_table_names())
    expected = {"project", "design_request", "render", "build_sheet", "project_dimensions"}
    assert expected <= tables


def test_insert_project(session):
    p = Project(
        address="123 Main St",
        lot_size_sqft=5000.0,
        house_sqft=2000.0,
        site_photo_path="/photos/yard.jpg",
    )
    session.add(p)
    session.flush()
    assert p.id is not None
    assert p.address == "123 Main St"


def test_design_request_null_parent_render_id(session):
    p = Project(address="456 Oak Ave")
    session.add(p)
    session.flush()

    dr = DesignRequest(
        project_id=p.id,
        parent_render_id=None,
        image_provider="GeminiFlashImage",
        feature_categories=["Deck", "Garden Beds"],
        style="Modern",
        quality_tier="Mid-range",
        composed_prompt="Add a modern deck with garden beds",
    )
    session.add(dr)
    session.flush()

    assert dr.id is not None
    assert dr.parent_render_id is None


def test_design_request_with_valid_parent_render_id(session):
    p = Project(address="789 Pine Rd")
    session.add(p)
    session.flush()

    dr1 = DesignRequest(
        project_id=p.id,
        parent_render_id=None,
        image_provider="GptImage",
        feature_categories=["Pool"],
        style="Tropical",
        quality_tier="Premium",
        composed_prompt="Add a tropical pool",
    )
    session.add(dr1)
    session.flush()

    render = Render(design_request_id=dr1.id, image_path="/renders/pool1.png", is_chosen=True)
    session.add(render)
    session.flush()

    dr2 = DesignRequest(
        project_id=p.id,
        parent_render_id=render.id,
        image_provider="GptImage",
        feature_categories=["Pool"],
        style="Tropical",
        quality_tier="Premium",
        composed_prompt="Refine the tropical pool — cedar decking instead",
    )
    session.add(dr2)
    session.flush()

    assert dr2.id is not None
    assert dr2.parent_render_id == render.id


def test_render_is_chosen_defaults_false(session):
    p = Project(address="100 Elm St")
    session.add(p)
    session.flush()

    dr = DesignRequest(
        project_id=p.id,
        parent_render_id=None,
        image_provider="GeminiFlashImage",
        feature_categories=["Pergola"],
        style="Rustic",
        quality_tier="Budget",
        composed_prompt="Add a rustic pergola",
    )
    session.add(dr)
    session.flush()

    r = Render(design_request_id=dr.id, image_path="/renders/pergola.png")
    session.add(r)
    session.flush()
    assert r.is_chosen is False


def test_feature_categories_stored_as_json(session):
    p = Project(address="200 Maple Dr")
    session.add(p)
    session.flush()

    categories = ["Deck", "Fire Feature", "Garden Beds"]
    dr = DesignRequest(
        project_id=p.id,
        parent_render_id=None,
        image_provider="GeminiFlashImage",
        feature_categories=categories,
        style="Cottage",
        quality_tier="Mid-range",
        composed_prompt="Add a cottage-style deck, fire feature, and garden beds",
    )
    session.add(dr)
    session.commit()

    session.expire(dr)
    reloaded = session.get(DesignRequest, dr.id)
    assert reloaded.feature_categories == categories


# ---------------------------------------------------------------------------
# BuildSheet tests
# ---------------------------------------------------------------------------


def test_insert_build_sheet(session_with_render):
    session, render = session_with_render
    bs = BuildSheet(
        render_id=render.id,
        materials_llm="ClaudeSonnet",
        content_json='{"materials": [], "steps": []}',
    )
    session.add(bs)
    session.flush()
    assert bs.id is not None
    assert bs.render_id == render.id
    assert bs.materials_llm == "ClaudeSonnet"


def test_build_sheet_unique_constraint_per_render(session_with_render):
    """A second BuildSheet for the same Render must raise IntegrityError."""
    session, render = session_with_render
    bs1 = BuildSheet(
        render_id=render.id,
        materials_llm="ClaudeSonnet",
        content_json='{"materials": []}',
    )
    session.add(bs1)
    session.flush()

    bs2 = BuildSheet(
        render_id=render.id,
        materials_llm="Gpt5",
        content_json='{"materials": []}',
    )
    session.add(bs2)
    with pytest.raises(IntegrityError):
        session.flush()


def test_build_sheet_relationship(session_with_render):
    session, render = session_with_render
    bs = BuildSheet(
        render_id=render.id,
        materials_llm="GeminiPro",
        content_json="{}",
    )
    session.add(bs)
    session.commit()

    session.expire_all()
    reloaded_render = session.get(Render, render.id)
    assert reloaded_render.build_sheet is not None
    assert reloaded_render.build_sheet.materials_llm == "GeminiPro"


# ---------------------------------------------------------------------------
# ProjectDimensions tests
# ---------------------------------------------------------------------------


def test_insert_project_dimensions(session_with_render):
    session, render = session_with_render
    pd = ProjectDimensions(
        render_id=render.id,
        dimensions_json='{"deck_width": 12, "deck_length": 16}',
    )
    session.add(pd)
    session.flush()
    assert pd.id is not None
    assert pd.render_id == render.id


def test_project_dimensions_relationship(session_with_render):
    session, render = session_with_render
    pd = ProjectDimensions(
        render_id=render.id,
        dimensions_json='{"garden_length": 8, "garden_width": 4}',
    )
    session.add(pd)
    session.commit()

    session.expire_all()
    reloaded_render = session.get(Render, render.id)
    assert reloaded_render.project_dimensions is not None
    assert "garden_length" in reloaded_render.project_dimensions.dimensions_json


def test_multiple_renders_can_have_separate_build_sheets(session):
    """Each Render gets its own BuildSheet; uniqueness is per-render."""
    p = Project(address="300 Cedar Ln")
    session.add(p)
    session.flush()

    dr = DesignRequest(
        project_id=p.id,
        parent_render_id=None,
        image_provider="GeminiFlashImage",
        feature_categories=["Patio"],
        style="Modern",
        quality_tier="Mid-range",
        composed_prompt="Add a patio",
    )
    session.add(dr)
    session.flush()

    r1 = Render(design_request_id=dr.id, image_path="/renders/patio1.png")
    r2 = Render(design_request_id=dr.id, image_path="/renders/patio2.png")
    session.add_all([r1, r2])
    session.flush()

    bs1 = BuildSheet(render_id=r1.id, materials_llm="ClaudeSonnet", content_json="{}")
    bs2 = BuildSheet(render_id=r2.id, materials_llm="ClaudeSonnet", content_json="{}")
    session.add_all([bs1, bs2])
    session.flush()

    assert bs1.id != bs2.id
