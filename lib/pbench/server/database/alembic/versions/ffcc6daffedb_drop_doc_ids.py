"""Drop the document IDs from IndexMap

Revision ID: ffcc6daffedb
Revises: 313cfbf6e74b
Create Date: 2024-01-30 19:33:14.976874

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "ffcc6daffedb"
down_revision = "313cfbf6e74b"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_column("indexmaps", "documents")


def downgrade() -> None:
    op.add_column(
        "indexmaps",
        sa.Column(
            "documents",
            postgresql.JSON(astext_type=sa.Text()),
            autoincrement=False,
            nullable=False,
        ),
    )
