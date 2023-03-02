"""empty message

Revision ID: 0645bfc869f4
Revises: f628657bed56
Create Date: 2023-03-23 14:44:33.904942

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "0645bfc869f4"
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
    op.drop_index("ix_active_tokens_token", table_name="active_tokens")
    op.drop_table("active_tokens")


def downgrade() -> None:
    op.create_table(
        "active_tokens",
        sa.Column("id", sa.INTEGER(), autoincrement=True, nullable=False),
        sa.Column("token", sa.VARCHAR(length=500), autoincrement=False, nullable=False),
        sa.Column(
            "created", postgresql.TIMESTAMP(), autoincrement=False, nullable=False
        ),
        sa.PrimaryKeyConstraint("id", name="active_tokens_pkey"),
    )
    op.create_index("ix_active_tokens_token", "active_tokens", ["token"], unique=False)
    op.drop_index(op.f("ix_api_key_api_key"), table_name="api_key")
    op.drop_table("api_key")
