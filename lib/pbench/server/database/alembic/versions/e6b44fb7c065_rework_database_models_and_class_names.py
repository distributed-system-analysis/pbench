"""Rework database modules and class names

Revision ID: e6b44fb7c065
Revises: fa12f45a2a5a
Create Date: 2023-01-23 20:44:32.238138
"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "e6b44fb7c065"
down_revision = "fa12f45a2a5a"
branch_labels = None
depends_on = None


def rename_table(old: str, new: str):
    """Rename a table from the given old name to the new name.

    It also renames the primary key index and the associated sequence for the ID
    field.

    Args:
        old : exiting table name
        new : new table name
    """
    # Rename table "serverconfig" to "server_settings", updating the primary key
    # index and the sequence for IDs.
    op.rename_table(old, new)
    op.execute(f"ALTER INDEX {old}_pkey RENAME TO {new}_pkey")
    op.execute(f"ALTER SEQUENCE {old}_id_seq RENAME TO {new}_id_seq")


def rename_index(column: str, old: str, new: str):
    """Rename an index from an existing table to a new table where the column
    name does not change.

    Args:
        column : column name of associated index to rename
        old : existing table name
        new : new table name
    """
    op.execute(f"ALTER INDEX ix_{old}_{column} RENAME TO ix_{new}_{column}")


def rename_fkey(column: str, old: str, new: str):
    """Rename a foreign key constraint for an existing table to a new table
    where the column name does not change.

    Args:
        column : column name of associated foreign key constraint to rename
        old : existing table name
        new : new table name
    """
    op.execute(
        f'ALTER TABLE {new} RENAME CONSTRAINT "{old}_{column}_fkey" TO "{new}_{column}_fkey"'
    )


def rename_column(old_table: str, new_table: str, old_column: str, new_column: str):
    """Rename a column in a new table and update the existing index to the new
    table and column name.

    This MUST following a `rename_table()` operation.

    Args:
        old_table : existing table name
        new_table : new table name where the column lives
        old_column : existing column name
        new_column : new column name
    """
    op.execute(
        f'ALTER TABLE {new_table} RENAME COLUMN "{old_column}" TO "{new_column}"'
    )
    op.execute(
        f"ALTER INDEX ix_{old_table}_{old_column} RENAME TO ix_{new_table}_{new_column}"
    )


def upgrade() -> None:
    # Rename table "serverconfig" to "server_settings", updating the index names
    # and sequence for IDs.
    rename_table("serverconfig", "server_settings")
    rename_index("key", "serverconfig", "server_settings")

    rename_table("active_tokens", "auth_tokens")
    rename_fkey("user_id", "active_tokens", "auth_tokens")
    rename_column("active_tokens", "auth_tokens", "token", "auth_token")


def downgrade() -> None:
    rename_table("server_settings", "serverconfig")
    rename_index("key", "server_settings", "serverconfig")

    rename_table("auth_tokens", "active_tokens")
    rename_fkey("user_id", "auth_tokens", "active_tokens")
    rename_column("auth_tokens", "active_tokens", "auth_token", "token")
