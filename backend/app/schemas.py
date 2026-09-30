from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, field_validator


def _clean_model_id(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    cleaned = value.strip()
    return cleaned or None


class RenderOut(BaseModel):
    id: int
    design_request_id: int
    image_path: str
    image_url: Optional[str] = None
    is_chosen: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class DesignRequestOut(BaseModel):
    id: int
    project_id: int
    parent_render_id: Optional[int] = None
    image_provider: str
    image_model: Optional[str] = None
    feature_categories: list[str]
    style: str
    quality_tier: str
    composed_prompt: str
    created_at: datetime
    renders: list[RenderOut] = []

    model_config = {"from_attributes": True}


class DesignRequestCreate(BaseModel):
    image_provider: str
    # Vendor model id from GET /api/models; None uses the provider's default.
    image_model: Optional[str] = None
    feature_categories: list[str]
    style: str
    quality_tier: str
    composed_prompt: str
    parent_render_id: Optional[int] = None

    _clean_image_model = field_validator("image_model")(_clean_model_id)


class ProjectListItem(BaseModel):
    id: int
    address: str
    site_photo_url: Optional[str] = None
    site_photo_thumb_url: Optional[str] = None
    created_at: datetime
    latest_design_request_at: Optional[datetime] = None
    design_request_count: int = 0
    render_count: int = 0
    iteration_count: int = 0
    has_chosen_render: bool = False
    has_build_sheet: bool = False
    latest_quality_tier: Optional[str] = None


class ProjectDetail(BaseModel):
    id: int
    address: str
    lot_size_sqft: Optional[float] = None
    house_sqft: Optional[float] = None
    site_photo_url: Optional[str] = None
    created_at: datetime
    design_requests: list[DesignRequestOut] = []


class BuildSheetCreate(BaseModel):
    materials_llm: str
    # Vendor model ids from GET /api/models; None uses each provider's default.
    materials_model: Optional[str] = None
    grounding_model: Optional[str] = None
    dimensions: dict[str, Any]

    _clean_materials_model = field_validator("materials_model")(_clean_model_id)
    _clean_grounding_model = field_validator("grounding_model")(_clean_model_id)


class BuildSheetOut(BaseModel):
    id: int
    render_id: int
    materials_llm: str
    materials_model: Optional[str] = None
    grounding_model: Optional[str] = None
    material_items: list[dict]
    tool_list: list[Any]
    build_steps: list[dict]
    total_cost_range: str
    skill_level: str
    assumptions: list[Any]
    warning: Optional[str] = None
    created_at: datetime


class ModelInfoOut(BaseModel):
    id: str
    display_name: str
    # Curated comparison data (see app/providers/model_metadata.py)
    tier: str = "unknown"
    quality: Optional[int] = None
    cost: Optional[str] = None
    cost_rank: Optional[int] = None
    recommended: bool = False
    note: Optional[str] = None
    current: bool = True


class ProviderModelsOut(BaseModel):
    slug: str
    role: str
    vendor: str
    label: str
    key_env: str
    key_set: bool
    default_model: str
    models: list[ModelInfoOut]
    source: str
    error: Optional[str] = None


class ModelCatalogOut(BaseModel):
    image: list[ProviderModelsOut]
    materials: list[ProviderModelsOut]
    grounding: list[ProviderModelsOut]
