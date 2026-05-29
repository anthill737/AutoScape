"""Initial schema: project, design_request, render

Revision ID: 0001
Revises:
Create Date: 2026-05-24

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "project",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("address", sa.String(), nullable=False),
        sa.Column("lot_size_sqft", sa.Float(), nullable=True),
        sa.Column("house_sqft", sa.Float(), nullable=True),
        sa.Column("site_photo_path", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )

    # design_request references render via parent_render_id, but render doesn't
    # exist yet. We omit the FK constraint here and rely on ORM-level metadata
    # (use_alter=True in the model). SQLite doesn't enforce FK constraints by
    # default, so application integrity is maintained by the ORM.
    op.create_table(
        "design_request",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("parent_render_id", sa.Integer(), nullable=True),
        sa.Column("image_provider", sa.String(), nullable=False),
        sa.Column("feature_categories", sa.JSON(), nullable=False),
        sa.Column("style", sa.String(), nullable=False),
        sa.Column("quality_tier", sa.String(), nullable=False),
        sa.Column("composed_prompt", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["project_id"], ["project.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "render",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("design_request_id", sa.Integer(), nullable=False),
        sa.Column("image_path", sa.String(), nullable=False),
        sa.Column("is_chosen", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["design_request_id"], ["design_request.id"]),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("render")
    op.drop_table("design_request")
    op.drop_table("project")
