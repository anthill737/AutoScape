"""Record which vendor model produced each Design Request and Build Sheet

Revision ID: 0003
Revises: 0002
Create Date: 2026-09-30

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Nullable: rows created before this migration used the vendor default of the time.
    op.add_column("design_request", sa.Column("image_model", sa.String(), nullable=True))
    op.add_column("build_sheet", sa.Column("materials_model", sa.String(), nullable=True))
    op.add_column("build_sheet", sa.Column("grounding_model", sa.String(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("build_sheet") as batch_op:
        batch_op.drop_column("grounding_model")
        batch_op.drop_column("materials_model")
    with op.batch_alter_table("design_request") as batch_op:
        batch_op.drop_column("image_model")
