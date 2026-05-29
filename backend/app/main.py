import base64
import json
import logging
import os
import traceback
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

from alembic import command as alembic_command
from alembic.config import Config as AlembicConfig
from fastapi import Body, Depends, FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from sqlalchemy.orm import Session

from app.api.settings import router as settings_router
from app.bootstrap import startup_key_presence
from app.database import DATABASE_URL, get_db
from app.domain.build_sheet_validation import validate_build_sheet_material_urls
from app.domain.retailers import APPROVED_RETAILERS
from app.models import BuildSheet, DesignRequest, Project, Render
from app.providers.base import MissingApiKeyError
from app.providers.claude_sonnet import suggest_dimension_defaults
from app.providers.exceptions import ImageProviderAuthError, ImageProviderQuotaError
from app.providers.image_provider import ImageProvider
from app.providers.materials_llm import MaterialsLLM
from app.providers.search_grounding import SearchGrounding
from app.schemas import (
    BuildSheetCreate,
    BuildSheetOut,
    DesignRequestCreate,
    DesignRequestOut,
    ProjectDetail,
    ProjectListItem,
    RenderOut,
)
from app.thumbnails import ensure_site_photo_thumbnail

_backend_dir = Path(__file__).resolve().parent.parent
_alembic_ini = _backend_dir / "alembic.ini"

logger = logging.getLogger(__name__)

ALLOWED_CONTENT_TYPES = {"image/jpeg", "image/png"}


def get_data_dir() -> Path:
    return Path(os.getenv("AUTOSCAPE_DATA_DIR", "./data"))


def _database_location_for_log() -> str:
    if DATABASE_URL == "sqlite:///:memory:":
        return ":memory:"
    if DATABASE_URL.startswith("sqlite:///"):
        return str(Path(DATABASE_URL.removeprefix("sqlite:///")).resolve())
    return DATABASE_URL


def _provider_error_status(exc: Exception) -> int:
    message = f"{exc.__class__.__name__}: {exc}".lower()
    if "429" in message or "quota" in message or "resource_exhausted" in message:
        return 503
    return 500


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Ensure data directories exist before any request is served
    data_dir = get_data_dir()
    (data_dir / "images").mkdir(parents=True, exist_ok=True)

    # Run Alembic migrations so the schema is present on a fresh install
    cfg = AlembicConfig(str(_alembic_ini))
    cfg.set_main_option("sqlalchemy.url", DATABASE_URL)
    cfg.set_main_option("script_location", str(_backend_dir / "migrations"))
    alembic_command.upgrade(cfg, "head")
    # Alembic's fileConfig can disable loggers omitted from alembic.ini.
    logger.disabled = False
    logger.setLevel(logging.INFO)
    logger.info("Database migrations applied successfully")
    logger.info(
        "[startup] schema ready, data dir = %s, db = %s",
        data_dir.resolve(),
        _database_location_for_log(),
    )
    present_keys, missing_keys = startup_key_presence()
    logger.info(
        "[startup] provider env vars present = %s; missing = %s",
        ", ".join(present_keys) or "none",
        ", ".join(missing_keys) or "none",
    )

    yield


app = FastAPI(title="AutoScape API", version="0.1.0", lifespan=lifespan)

app.include_router(settings_router)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    trace_id = uuid.uuid4().hex[:8]
    traceback_text = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__)).rstrip()
    logger.error("Unhandled exception trace_id=%s\n%s", trace_id, traceback_text)
    return JSONResponse(
        status_code=500,
        content={"detail": f"{exc.__class__.__name__}: {exc}", "trace_id": trace_id},
    )


def _render_image_url(render_id: int) -> str:
    return f"/renders/{render_id}"


def _build_sheet_out(bs: BuildSheet) -> BuildSheetOut:
    content = json.loads(bs.content_json)
    return BuildSheetOut(
        id=bs.id,
        render_id=bs.render_id,
        materials_llm=bs.materials_llm,
        material_items=content.get("material_items", []),
        tool_list=content.get("tool_list", []),
        build_steps=content.get("build_steps", []),
        total_cost_range=content.get("total_cost_range", ""),
        skill_level=content.get("skill_level", ""),
        assumptions=content.get("assumptions", []),
        warning=content.get("warning"),
        created_at=bs.created_at,
    )


def _render_out(render: Render) -> RenderOut:
    return RenderOut(
        id=render.id,
        design_request_id=render.design_request_id,
        image_path=render.image_path,
        image_url=_render_image_url(render.id),
        is_chosen=render.is_chosen,
        created_at=render.created_at,
    )


def _design_request_out(dr: DesignRequest) -> DesignRequestOut:
    return DesignRequestOut(
        id=dr.id,
        project_id=dr.project_id,
        parent_render_id=dr.parent_render_id,
        image_provider=dr.image_provider,
        feature_categories=dr.feature_categories,
        style=dr.style,
        quality_tier=dr.quality_tier,
        composed_prompt=dr.composed_prompt,
        created_at=dr.created_at,
        renders=[_render_out(render) for render in dr.renders],
    )


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/approved-retailers")
def list_approved_retailers() -> list[dict[str, str]]:
    return [dict(retailer) for retailer in APPROVED_RETAILERS]


@app.post("/api/projects", status_code=201)
async def create_project(
    address: str = Form(...),
    lot_size_sqft: float | None = Form(None),
    lot_size: float | None = Form(None),
    house_sqft: float = Form(...),
    site_photo: UploadFile = File(...),
    db: Session = Depends(get_db),
    data_dir: Path = Depends(get_data_dir),
) -> dict:
    if site_photo.content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=422,
            detail=(
                f"Site Photo must be a JPEG or PNG image (got '{site_photo.content_type}'). "
                "Please upload a .jpg or .png file."
            ),
        )

    resolved_lot_size_sqft = lot_size_sqft if lot_size_sqft is not None else lot_size
    if resolved_lot_size_sqft is None:
        raise HTTPException(status_code=422, detail="Lot size is required.")

    project = Project(
        address=address,
        lot_size_sqft=resolved_lot_size_sqft,
        house_sqft=house_sqft,
    )
    db.add(project)
    db.flush()

    photo_dir = data_dir / "images" / str(project.id)
    photo_dir.mkdir(parents=True, exist_ok=True)
    photo_path = photo_dir / "site_photo.jpg"
    photo_path.write_bytes(await site_photo.read())

    project.site_photo_path = str(photo_path)
    db.commit()
    db.refresh(project)

    return {
        "id": project.id,
        "project_id": project.id,
        "address": project.address,
        "created_at": project.created_at,
    }


@app.get("/api/projects", response_model=list[ProjectListItem])
def list_projects(
    db: Session = Depends(get_db),
    data_dir: Path = Depends(get_data_dir),
) -> list[ProjectListItem]:
    projects = db.query(Project).all()
    items: list[ProjectListItem] = []
    for p in projects:
        design_requests = list(p.design_requests)
        renders = [render for dr in design_requests for render in dr.renders]
        latest_design_request = max(
            design_requests,
            key=lambda dr: dr.created_at,
            default=None,
        )

        items.append(
            ProjectListItem(
                id=p.id,
                address=p.address,
                site_photo_url=f"/images/{p.id}/site_photo.jpg" if p.site_photo_path else None,
                site_photo_thumb_url=ensure_site_photo_thumbnail(
                    project_id=p.id,
                    site_photo_path=p.site_photo_path,
                    data_dir=data_dir,
                ),
                created_at=p.created_at,
                latest_design_request_at=(
                    latest_design_request.created_at if latest_design_request else None
                ),
                design_request_count=len(design_requests),
                render_count=len(renders),
                iteration_count=sum(
                    1 for dr in design_requests if dr.parent_render_id is not None
                ),
                has_chosen_render=any(render.is_chosen for render in renders),
                has_build_sheet=any(render.build_sheet is not None for render in renders),
                latest_quality_tier=(
                    latest_design_request.quality_tier if latest_design_request else None
                ),
            )
        )
    return items


@app.get("/api/projects/{project_id}", response_model=ProjectDetail)
def get_project(project_id: int, db: Session = Depends(get_db)) -> ProjectDetail:
    project = db.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")

    return ProjectDetail(
        id=project.id,
        address=project.address,
        lot_size_sqft=project.lot_size_sqft,
        house_sqft=project.house_sqft,
        site_photo_url=f"/images/{project.id}/site_photo.jpg" if project.site_photo_path else None,
        created_at=project.created_at,
        design_requests=[_design_request_out(dr) for dr in project.design_requests],
    )


@app.get("/api/projects/{project_id}/design-requests", response_model=list[DesignRequestOut])
def list_design_requests(project_id: int, db: Session = Depends(get_db)) -> list[DesignRequestOut]:
    project = db.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")

    design_requests = (
        db.query(DesignRequest)
        .filter(DesignRequest.project_id == project_id)
        .order_by(DesignRequest.created_at, DesignRequest.id)
        .all()
    )
    return [_design_request_out(dr) for dr in design_requests]


@app.post("/api/projects/{project_id}/design-requests", status_code=201)
async def create_design_request(
    project_id: int,
    body: DesignRequestCreate = Body(...),
    db: Session = Depends(get_db),
    data_dir: Path = Depends(get_data_dir),
) -> dict:
    project = db.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")

    try:
        provider = ImageProvider(body.image_provider)
    except ValueError:
        raise HTTPException(
            status_code=422,
            detail=f"Unknown image_provider: {body.image_provider!r}. "
            f"Valid values: {[p.value for p in ImageProvider]}",
        )

    if body.parent_render_id is not None:
        parent_render = db.get(Render, body.parent_render_id)
        if parent_render is None:
            raise HTTPException(status_code=404, detail="Parent Render not found")
        if parent_render.design_request.project_id != project_id:
            raise HTTPException(
                status_code=400,
                detail="Parent Render does not belong to this Project",
            )
        input_image_bytes = Path(parent_render.image_path).read_bytes()
    else:
        if not project.site_photo_path:
            raise HTTPException(status_code=400, detail="Project has no Site Photo")
        input_image_bytes = Path(project.site_photo_path).read_bytes()

    image_b64 = base64.b64encode(input_image_bytes).decode()

    dr = DesignRequest(
        project_id=project_id,
        parent_render_id=body.parent_render_id,
        image_provider=body.image_provider,
        feature_categories=body.feature_categories,
        style=body.style,
        quality_tier=body.quality_tier,
        composed_prompt=body.composed_prompt,
    )
    db.add(dr)
    db.flush()

    try:
        adapter = provider.make_adapter()
        render_bytes_list = await adapter.generate(image_b64, body.composed_prompt)
    except MissingApiKeyError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc))
    except ImageProviderQuotaError as exc:
        db.rollback()
        raise HTTPException(status_code=429, detail=str(exc))
    except ImageProviderAuthError as exc:
        db.rollback()
        raise HTTPException(status_code=401, detail=str(exc))
    except Exception as exc:
        db.rollback()
        detail = f"Image provider failed: {exc.__class__.__name__}: {exc}"
        status_code = _provider_error_status(exc)
        logger.warning(
            "Image provider request failed; returning HTTP %s for project_id=%s provider=%s",
            status_code,
            project_id,
            body.image_provider,
        )
        raise HTTPException(status_code=status_code, detail=detail)

    render_dir = data_dir / "images" / str(project_id)
    render_dir.mkdir(parents=True, exist_ok=True)

    saved_renders: list[Render] = []
    for render_bytes in render_bytes_list:
        render = Render(design_request_id=dr.id, image_path="", is_chosen=False)
        db.add(render)
        db.flush()

        image_path = render_dir / f"{render.id}.png"
        image_path.write_bytes(render_bytes)
        render.image_path = str(image_path)
        saved_renders.append(render)

    db.commit()
    db.refresh(dr)
    for r in saved_renders:
        db.refresh(r)

    render_outs = [_render_out(r) for r in saved_renders]

    return {
        "id": dr.id,
        "project_id": dr.project_id,
        "parent_render_id": dr.parent_render_id,
        "image_provider": dr.image_provider,
        "feature_categories": dr.feature_categories,
        "style": dr.style,
        "quality_tier": dr.quality_tier,
        "composed_prompt": dr.composed_prompt,
        "created_at": dr.created_at,
        "renders": [ro.model_dump() for ro in render_outs],
    }


@app.patch("/api/renders/{render_id}/choose", status_code=200)
def choose_render(render_id: int, db: Session = Depends(get_db)) -> RenderOut:
    render = db.get(Render, render_id)
    if render is None:
        raise HTTPException(status_code=404, detail="Render not found")

    db.query(Render).filter(
        Render.design_request_id == render.design_request_id,
        Render.is_chosen == True,  # noqa: E712
    ).update({"is_chosen": False})

    render.is_chosen = True
    db.commit()
    db.refresh(render)

    return RenderOut(
        id=render.id,
        design_request_id=render.design_request_id,
        image_path=render.image_path,
        image_url=_render_image_url(render.id),
        is_chosen=render.is_chosen,
        created_at=render.created_at,
    )


@app.get("/images/{project_id}/site_photo.jpg")
def get_site_photo(
    project_id: int,
    data_dir: Path = Depends(get_data_dir),
) -> FileResponse:
    photo_path = data_dir / "images" / str(project_id) / "site_photo.jpg"
    if not photo_path.exists():
        raise HTTPException(status_code=404, detail="Site Photo not found")
    return FileResponse(str(photo_path), media_type="image/jpeg")


@app.get("/thumbnails/{filename}")
def get_thumbnail(
    filename: str,
    data_dir: Path = Depends(get_data_dir),
) -> FileResponse:
    thumbnail_path = data_dir / "thumbnails" / filename
    if not thumbnail_path.exists() or thumbnail_path.suffix.lower() not in {".jpg", ".jpeg"}:
        raise HTTPException(status_code=404, detail="Thumbnail not found")
    return FileResponse(str(thumbnail_path), media_type="image/jpeg")


@app.get("/renders/{render_id}")
def get_render_image(render_id: int, db: Session = Depends(get_db)) -> FileResponse:
    render = db.get(Render, render_id)
    if render is None:
        raise HTTPException(status_code=404, detail="Render not found")
    image_path = Path(render.image_path)
    if not image_path.exists():
        raise HTTPException(status_code=404, detail="Render image not found")
    return FileResponse(str(image_path), media_type="image/png")


# ---------------------------------------------------------------------------
# Build Sheet endpoints
# ---------------------------------------------------------------------------


@app.get("/api/renders/{render_id}/dimension-defaults", status_code=200)
@app.post("/api/renders/{render_id}/dimension-defaults", status_code=200)
async def get_dimension_defaults(
    render_id: int,
    db: Session = Depends(get_db),
) -> dict:
    render = db.get(Render, render_id)
    if render is None:
        raise HTTPException(status_code=404, detail="Render not found")

    dr = render.design_request
    if dr is None:
        return {}

    feature_categories = dr.feature_categories or []
    if not isinstance(feature_categories, list):
        feature_categories = []
    feature_categories = [
        str(category).strip() for category in feature_categories if str(category).strip()
    ]
    if not feature_categories:
        return {}

    project = dr.project
    lot_size_sqft = project.lot_size_sqft if project is not None else None
    house_sqft = project.house_sqft if project is not None else None

    image_path = Path(render.image_path)
    if not image_path.exists():
        raise HTTPException(status_code=404, detail="Render image file not found on disk")
    render_image_bytes = image_path.read_bytes()

    try:
        defaults = await suggest_dimension_defaults(
            render_image_bytes=render_image_bytes,
            feature_categories=feature_categories,
            lot_size_sqft=lot_size_sqft,
            house_sqft=house_sqft,
        )
    except MissingApiKeyError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    return defaults


@app.post("/api/renders/{render_id}/build-sheet", status_code=201)
async def create_build_sheet(
    render_id: int,
    body: BuildSheetCreate = Body(...),
    db: Session = Depends(get_db),
) -> BuildSheetOut:
    render = db.get(Render, render_id)
    if render is None:
        raise HTTPException(status_code=404, detail="Render not found")

    try:
        llm = MaterialsLLM(body.materials_llm)
    except ValueError:
        raise HTTPException(
            status_code=422,
            detail=f"Unknown materials_llm: {body.materials_llm!r}. "
            f"Valid values: {[m.value for m in MaterialsLLM]}",
        )

    dr = render.design_request
    feature_categories: list[str] = dr.feature_categories

    image_path = Path(render.image_path)
    if not image_path.exists():
        raise HTTPException(status_code=404, detail="Render image file not found on disk")
    render_image_bytes = image_path.read_bytes()

    try:
        grounding = SearchGrounding()
        search_results = await grounding.search(feature_categories)
    except MissingApiKeyError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    try:
        adapter = llm.make_adapter()
        content = await adapter.generate_build_sheet(
            render_image_bytes=render_image_bytes,
            dimensions=body.dimensions,
            quality_tier=dr.quality_tier,
            search_results=search_results,
            feature_categories=feature_categories,
        )
    except MissingApiKeyError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        detail = f"Materials LLM failed: {exc.__class__.__name__}: {exc}"
        status_code = _provider_error_status(exc)
        logger.warning(
            "Materials LLM request failed; returning HTTP %s for render_id=%s provider=%s",
            status_code,
            render_id,
            body.materials_llm,
        )
        raise HTTPException(status_code=status_code, detail=detail)

    content = await validate_build_sheet_material_urls(content)

    # Upsert: delete existing BuildSheet for this render if present, then insert
    existing = db.query(BuildSheet).filter(BuildSheet.render_id == render_id).first()
    if existing is not None:
        db.delete(existing)
        db.flush()

    bs = BuildSheet(
        render_id=render_id,
        materials_llm=body.materials_llm,
        content_json=json.dumps(content),
    )
    db.add(bs)
    db.commit()
    db.refresh(bs)

    return _build_sheet_out(bs)


@app.get("/api/renders/{render_id}/build-sheet", status_code=200)
def get_build_sheet(
    render_id: int,
    db: Session = Depends(get_db),
) -> BuildSheetOut:
    render = db.get(Render, render_id)
    if render is None:
        raise HTTPException(status_code=404, detail="Render not found")

    bs = db.query(BuildSheet).filter(BuildSheet.render_id == render_id).first()
    if bs is None:
        raise HTTPException(status_code=404, detail="Build Sheet not found for this Render")

    return _build_sheet_out(bs)
