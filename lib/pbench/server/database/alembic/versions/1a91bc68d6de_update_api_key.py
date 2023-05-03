"""Update api_key table with "id" as primary_key


Revision ID: 1a91bc68d6de
Revises: 5679217a62bb
Create Date: 2023-05-03 09:50:29.609672

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "1a91bc68d6de"
down_revision = "5679217a62bb"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint("api_keys_pkey", "api_keys", type_="primary")
    op.add_column(
        "api_keys", sa.Column("id", sa.Integer(), autoincrement=True, nullable=False)
    )
    op.add_column("api_keys", sa.Column("name", sa.String(length=128), nullable=True))
    op.create_unique_constraint("api_keys_api_key_key", "api_keys", ["api_key"])
    op.create_primary_key("api_keys_pkey", "api_keys", ["id"])


def downgrade() -> None:
    op.drop_constraint("api_keys_pkey", "api_keys", type_="primary")
    op.drop_column("api_keys", "name")
    op.drop_column("api_keys", "id")
    op.create_primary_key("api_keys_pkey", "api_keys", ["api_key"])
