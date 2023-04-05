""" Update table for storing api_key and removing auth_token

Revision ID: 626a82b8b0a5
Revises: f628657bed56
Create Date: 2023-04-05 12:03:53.025572

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "626a82b8b0a5"
down_revision = "f628657bed56"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "api_key",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("api_key", sa.String(length=500), nullable=False),
        sa.Column("created", sa.DateTime(), nullable=False),
        sa.Column("expiration", sa.DateTime(), nullable=False),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_api_key_api_key"), "api_key", ["api_key"], unique=True)
    op.drop_index("ix_auth_tokens_expiration", table_name="auth_tokens")
    op.drop_index("ix_auth_tokens_token", table_name="auth_tokens")
    op.drop_table("auth_tokens")


def downgrade() -> None:
    op.create_table(
        "auth_tokens",
        sa.Column("id", sa.INTEGER(), autoincrement=True, nullable=False),
        sa.Column("token", sa.VARCHAR(length=500), autoincrement=False, nullable=False),
        sa.Column(
            "expiration", postgresql.TIMESTAMP(), autoincrement=False, nullable=False
        ),
        sa.PrimaryKeyConstraint("id", name="auth_tokens_pkey"),
    )
    op.create_index("ix_auth_tokens_token", "auth_tokens", ["token"], unique=False)
    op.create_index(
        "ix_auth_tokens_expiration", "auth_tokens", ["expiration"], unique=False
    )
    op.drop_index(op.f("ix_api_key_api_key"), table_name="api_key")
    op.drop_table("api_key")
