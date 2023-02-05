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
        "active_tokens", "created", nullable=False, new_column_name="expiration"
    )
    op.create_index(
        op.f("ix_active_tokens_expiration"),
        "active_tokens",
        ["expiration"],
        unique=False,
    )


def downgrade() -> None:
    op.alter_column(
        "active_tokens", "expiration", nullable=False, new_column_name="created"
    )
    op.drop_index(op.f("ix_active_tokens_expiration"), table_name="active_tokens")
