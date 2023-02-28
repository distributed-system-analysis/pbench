"""Update User table to only keep username, oidc_id, roles of the user

Revision ID: f628657bed56
Revises: fa12f45a2a5a
Create Date: 2023-02-26 23:24:16.650879

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "f628657bed56"
down_revision = "fa12f45a2a5a"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("_roles", sa.String(length=255), nullable=True))
    op.execute("ALTER TABLE users DROP CONSTRAINT users_pkey CASCADE")
    op.alter_column(
        "users",
        "id",
        existing_type=sa.INTEGER(),
        type_=sa.String(length=255),
        existing_nullable=False,
    )
    op.alter_column(
        "users", "username", existing_type=sa.VARCHAR(length=255), nullable=False
    )
    op.create_primary_key("user_primary", "users", ["id"])
    op.drop_constraint("users_email_key", "users", type_="unique")
    op.drop_column("users", "role")
    op.drop_column("users", "password")
    op.drop_column("users", "first_name")
    op.drop_column("users", "last_name")
    op.drop_column("users", "email")
    op.drop_column("users", "registered_on")
    op.drop_column("active_tokens", "user_id")
    op.add_column("dataset_metadata", sa.Column("user_ref", sa.String(), nullable=True))
    op.create_foreign_key(None, "dataset_metadata", "users", ["user_ref"], ["id"])
    op.drop_column("dataset_metadata", "user_id")
    op.create_foreign_key(None, "datasets", "users", ["owner_id"], ["id"])
    # ### end Alembic commands ###


def downgrade() -> None:
    op.execute("ALTER TABLE users DROP CONSTRAINT user_primary CASCADE")
    op.add_column(
        "users",
        sa.Column(
            "registered_on", postgresql.TIMESTAMP(), autoincrement=False, nullable=False
        ),
    )
    op.add_column(
        "users",
        sa.Column("email", sa.VARCHAR(length=255), autoincrement=False, nullable=False),
    )
    op.add_column(
        "users",
        sa.Column(
            "last_name", sa.VARCHAR(length=255), autoincrement=False, nullable=False
        ),
    )
    op.add_column(
        "users",
        sa.Column(
            "first_name", sa.VARCHAR(length=255), autoincrement=False, nullable=False
        ),
    )
    op.add_column(
        "users",
        sa.Column("password", postgresql.BYTEA(), autoincrement=False, nullable=False),
    )
    op.add_column(
        "users",
        sa.Column(
            "role",
            postgresql.ENUM("ADMIN", name="roles"),
            autoincrement=False,
            nullable=True,
        ),
    )
    op.create_unique_constraint("users_email_key", "users", ["email"])
    op.alter_column(
        "users", "username", existing_type=sa.VARCHAR(length=255), nullable=False
    )
    op.alter_column(
        "users",
        "id",
        existing_type=sa.String(length=255),
        type_=sa.INTEGER(),
        existing_nullable=False,
    )
    op.create_primary_key("user_primary", "users", ["id"])
    op.drop_column("users", "_roles")
    op.add_column(
        "dataset_metadata",
        sa.Column(
            "user_id", sa.VARCHAR(length=255), autoincrement=False, nullable=True
        ),
    )
    op.drop_column("dataset_metadata", "user_ref")
    op.add_column(
        "active_tokens",
        sa.Column("user_id", sa.INTEGER(), autoincrement=False, nullable=False),
    )
    op.create_foreign_key(
        "active_tokens_user_id_fkey",
        "active_tokens",
        "users",
        ["user_id"],
        ["id"],
        ondelete="CASCADE",
    )
    # ### end Alembic commands ###
