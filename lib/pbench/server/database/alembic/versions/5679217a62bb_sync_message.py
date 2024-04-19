"""Remove size limit on Sync messages

Revision ID: 5679217a62bb
Revises: 80c8c690f09b
Create Date: 2023-04-18 20:03:26.080554

"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "5679217a62bb"
down_revision = "80c8c690f09b"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "dataset_operations",
        "message",
        existing_type=sa.VARCHAR(length=255),
        type_=sa.Text(),
        existing_nullable=True,
    )
    # ### end Alembic commands ###


def downgrade() -> None:
    op.alter_column(
        "dataset_operations",
        "message",
        existing_type=sa.Text(),
        type_=sa.VARCHAR(length=255),
        existing_nullable=True,
    )
    # ### end Alembic commands ###
