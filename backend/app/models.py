from datetime import datetime, timezone

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    pass


class Project(Base):
    __tablename__ = "project"

    id = Column(Integer, primary_key=True)
    address = Column(String, nullable=False)
    lot_size_sqft = Column(Float, nullable=True)
    house_sqft = Column(Float, nullable=True)
    site_photo_path = Column(String, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    design_requests = relationship("DesignRequest", back_populates="project")


class DesignRequest(Base):
    __tablename__ = "design_request"

    id = Column(Integer, primary_key=True)
    project_id = Column(Integer, ForeignKey("project.id"), nullable=False)
    # use_alter=True + post_update=True handle the circular FK with Render
    parent_render_id = Column(
        Integer,
        ForeignKey("render.id", use_alter=True, name="fk_design_request_parent_render"),
        nullable=True,
    )
    image_provider = Column(String, nullable=False)
    feature_categories = Column(JSON, nullable=False)
    style = Column(String, nullable=False)
    quality_tier = Column(String, nullable=False)
    composed_prompt = Column(Text, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    project = relationship("Project", back_populates="design_requests")
    renders = relationship(
        "Render",
        back_populates="design_request",
        foreign_keys="[Render.design_request_id]",
    )
    parent_render = relationship(
        "Render",
        foreign_keys=[parent_render_id],
        post_update=True,
    )


class Render(Base):
    __tablename__ = "render"

    id = Column(Integer, primary_key=True)
    design_request_id = Column(Integer, ForeignKey("design_request.id"), nullable=False)
    image_path = Column(String, nullable=False)
    is_chosen = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    design_request = relationship(
        "DesignRequest",
        back_populates="renders",
        foreign_keys=[design_request_id],
    )
    build_sheet = relationship("BuildSheet", back_populates="render", uselist=False)
    project_dimensions = relationship("ProjectDimensions", back_populates="render", uselist=False)


class BuildSheet(Base):
    __tablename__ = "build_sheet"
    __table_args__ = (UniqueConstraint("render_id", name="uq_build_sheet_render_id"),)

    id = Column(Integer, primary_key=True)
    render_id = Column(Integer, ForeignKey("render.id"), nullable=False)
    materials_llm = Column(String, nullable=False)
    content_json = Column(Text, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    render = relationship("Render", back_populates="build_sheet")


class ProjectDimensions(Base):
    __tablename__ = "project_dimensions"

    id = Column(Integer, primary_key=True)
    render_id = Column(Integer, ForeignKey("render.id"), nullable=False)
    dimensions_json = Column(Text, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    render = relationship("Render", back_populates="project_dimensions")
