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
    op.execute("ALTER TABLE api_keys ADD COLUMN id SERIAL PRIMARY KEY")
    op.add_column("api_keys", sa.Column("label", sa.String(length=128), nullable=True))
    op.add_column("api_keys", sa.Column("key", sa.String(length=500), nullable=False))
    op.create_unique_constraint(None, "api_keys", ["key"])
    op.drop_column("api_keys", "api_key")


def downgrade() -> None:
    op.drop_constraint("api_keys_pkey", "api_keys", type_="primary")
    op.drop_column("api_keys", "label")
    op.drop_column("api_keys", "id")
    op.drop_column("api_keys", "key")
    op.create_primary_key("api_keys_pkey", "api_keys", ["api_key"])
