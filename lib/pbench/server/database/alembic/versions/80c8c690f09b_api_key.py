""" Update table for storing api_key and removing auth_token


Revision ID: 80c8c690f09b
Revises: f628657bed56
Create Date: 2023-04-11 19:20:36.892126

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from pbench.server.database.models import TZDateTime

# revision identifiers, used by Alembic.
revision = "80c8c690f09b"
down_revision = "f628657bed56"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "api_keys",
        sa.Column("api_key", sa.String(length=500), nullable=False),
        sa.Column("created", TZDateTime(), nullable=False),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
        ),
        sa.PrimaryKeyConstraint("api_key"),
    )
    op.execute("ALTER TYPE audittype ADD VALUE 'API_KEY'")
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
    op.drop_table("api_keys")
