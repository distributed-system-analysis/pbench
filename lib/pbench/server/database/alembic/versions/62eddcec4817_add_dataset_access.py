"""Add Dataset.access

Revision ID: 62eddcec4817
Revises: base
Create Date: 2021-05-27 16:22:13.714761

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "62eddcec4817"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    """
    Upgrade the "base" revision with changes necessary to support publishing
    datasets.

    1. Add the "access" column, and set all existing rows to "private". This
       can't be done in a single step, apparently. Instead, we add the column,
       set the value in all existing rows, and then mark it non-nullable.
    2. The document map can be extremely large, so change the dataset metadata
       "value" column from 2048 character String to unbounded Text.
    """
    op.add_column("datasets", sa.Column("access", sa.String(255), default="private"))
    op.execute("UPDATE datasets SET access = 'private'")
    op.alter_column("datasets", "access", nullable=False)
    op.alter_column(
        "dataset_metadata", "value", type_=sa.Text, existing_type=sa.String(2048)
    )


def downgrade():
    """
    Reverse the upgrade if we're downgrading to "base" revision
    """
    op.drop_column("datasets", "access")
    op.alter_column(
        "dataset_metadata", "value", type_=sa.String(2048), existing_type=sa.Text
    )
