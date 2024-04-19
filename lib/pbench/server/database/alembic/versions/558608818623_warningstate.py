"""Add WARNING operation status

Allow "partial success" audit status.

Revision ID: 558608818623
Revises: ffcc6daffedb
Create Date: 2024-04-03 12:07:47.018612

"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "558608818623"
down_revision = "ffcc6daffedb"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TYPE operationstate ADD VALUE 'WARNING'")


def downgrade() -> None:
    # Downgrade is problematic, and won't be attempted. Having unused ENUM
    # values defined shouldn't represent a problem.
    pass
    # ### end Alembic commands ###
