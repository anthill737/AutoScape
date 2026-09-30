"""Add interior/exterior space type, room type and size details to Project

Revision ID: 0004
Revises: 0003
Create Date: 2026-09-30

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Every project created before this migration was a landscape (exterior) project.
    op.add_column(
        "project",
        sa.Column("space_type", sa.String(), nullable=False, server_default="exterior"),
    )
    # Interior only: which room the photo shows (e.g. "Kitchen").
    op.add_column("project", sa.Column("room_type", sa.String(), nullable=True))
    # Size inputs keyed by the space's size_fields (lot/house sqft or room dimensions).
    op.add_column("project", sa.Column("space_details", sa.JSON(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("project") as batch_op:
        batch_op.drop_column("space_details")
        batch_op.drop_column("room_type")
        batch_op.drop_column("space_type")
