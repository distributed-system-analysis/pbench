"""Update api_key table with "id" as primary_key

Revision ID: e695e86f722a
Revises: 5679217a62bb
Create Date: 2023-04-27 18:59:31.914683

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "e695e86f722a"
down_revision = "5679217a62bb"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "api_keys", sa.Column("id", sa.Integer(), autoincrement=True, nullable=False)
    )
    op.add_column("api_keys", sa.Column("name", sa.String(length=128), nullable=False))
    op.create_unique_constraint(None, "api_keys", ["api_key"])


def downgrade() -> None:
    op.drop_constraint(None, "api_keys", type_="unique")
    op.drop_column("api_keys", "name")
    op.drop_column("api_keys", "id")
