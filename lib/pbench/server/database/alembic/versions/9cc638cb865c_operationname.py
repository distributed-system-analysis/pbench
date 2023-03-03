"""Correct operationname ENUM

Alembic does not check or autogenerate ENUM value changes, so this will
upgrade the original operationname revision to add UPDATE.

Revision ID: 9cc638cb865c
Revises: 9df060db17de
Create Date: 2023-03-03 14:32:16.955897

"""
from alembic import op

# revision identifiers, used by Alembic.
revision = "9cc638cb865c"
down_revision = "9df060db17de"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # NOTE: the 'BACKUP' and 'UNPACK' operationname ENUM values are now
    # obsolete. We don't attempt to remove them because dataset_operations
    # rows with these values record the previous operation of the server.
    # Instead we simply add the new 'UPDATE' value. Having the obsolete
    # values defined in the ENUM isn't a problem, and removing them isn't
    # worth the complication.
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE operationname ADD VALUE 'UPDATE' BEFORE 'UPLOAD'")
    # ### end Alembic commands ###


def downgrade() -> None:
    # Downgrade is problematic, and won't be attempted. Having unused ENUM
    # values defined shouldn't represent a problem.
    pass
    # ### end Alembic commands ###
