"""Rename column api_key to key

Revision ID: 8e43d4c470a7
Revises: 1a91bc68d6de
Create Date: 2023-05-03 18:55:50.094026

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "8e43d4c470a7"
down_revision = "1a91bc68d6de"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column("api_keys", sa.Column("key", sa.String(length=500), nullable=False))
    op.drop_constraint("api_keys_api_key_key", "api_keys", type_="unique")
    op.create_unique_constraint(None, "api_keys", ["key"])
    op.drop_column("api_keys", "api_key")
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column(
        "api_keys",
        sa.Column(
            "api_key", sa.VARCHAR(length=500), autoincrement=False, nullable=False
        ),
    )
    op.drop_constraint(None, "api_keys", type_="unique")
    op.create_unique_constraint("api_keys_api_key_key", "api_keys", ["api_key"])
    op.drop_column("api_keys", "key")
    # ### end Alembic commands ###
