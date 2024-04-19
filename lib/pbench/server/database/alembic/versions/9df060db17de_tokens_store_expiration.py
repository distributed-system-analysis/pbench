"""Tokens store expiration instead of creation.

Revision ID: 9df060db17de
Revises: e6b44fb7c065
Create Date: 2023-02-05 15:58:25.408754

"""

from alembic import op

# Revision identifiers, used by Alembic.
revision = "9df060db17de"
down_revision = "e6b44fb7c065"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "auth_tokens", "auth_token", nullable=False, new_column_name="token"
    )
    op.execute("ALTER INDEX ix_auth_tokens_auth_token RENAME TO ix_auth_tokens_token")
    op.alter_column(
        "auth_tokens", "created", nullable=False, new_column_name="expiration"
    )
    op.create_index(
        op.f("ix_auth_tokens_expiration"),
        "auth_tokens",
        ["expiration"],
        unique=False,
    )


def downgrade() -> None:
    op.alter_column(
        "auth_tokens", "expiration", nullable=False, new_column_name="created"
    )
    op.drop_index(op.f("ix_auth_tokens_expiration"), table_name="auth_tokens")
    op.alter_column(
        "auth_tokens", "token", nullable=False, new_column_name="auth_token"
    )
    op.execute("ALTER INDEX ix_auth_tokens_token RENAME TO ix_auth_tokens_auth_token")
