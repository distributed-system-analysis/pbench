"""Separate index map from metadata

Revision ID: 313cfbf6e74b
Revises: 1a91bc68d6de
Create Date: 2023-08-10 20:31:22.937542

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "313cfbf6e74b"
down_revision = "1a91bc68d6de"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "indexmaps",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("dataset_ref", sa.Integer(), nullable=False),
        sa.Column("root", sa.String(length=255), nullable=False),
        sa.Column("index", sa.String(length=255), nullable=False),
        sa.Column("documents", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(
            ["dataset_ref"],
            ["datasets.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_indexmaps_index"), "indexmaps", ["index"], unique=False)
    op.create_index(op.f("ix_indexmaps_root"), "indexmaps", ["root"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_indexmaps_root"), table_name="indexmaps")
    op.drop_index(op.f("ix_indexmaps_index"), table_name="indexmaps")
    op.drop_table("indexmaps")
