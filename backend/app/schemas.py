from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel


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
    feature_categories: list[str]
    style: str
    quality_tier: str
    composed_prompt: str
    created_at: datetime
    renders: list[RenderOut] = []

    model_config = {"from_attributes": True}


class DesignRequestCreate(BaseModel):
    image_provider: str
    feature_categories: list[str]
    style: str
    quality_tier: str
    composed_prompt: str
    parent_render_id: Optional[int] = None


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
    dimensions: dict[str, Any]


class BuildSheetOut(BaseModel):
    id: int
    render_id: int
    materials_llm: str
    material_items: list[dict]
    tool_list: list[Any]
    build_steps: list[dict]
    total_cost_range: str
    skill_level: str
    assumptions: list[Any]
    warning: Optional[str] = None
    created_at: datetime
