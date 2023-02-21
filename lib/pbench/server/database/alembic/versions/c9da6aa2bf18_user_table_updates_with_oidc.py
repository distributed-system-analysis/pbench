"""User table updates with OIDC changes

Revision ID: c9da6aa2bf18
Revises: fa12f45a2a5a
Create Date: 2023-02-20 19:58:19.008998

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "c9da6aa2bf18"
down_revision = "fa12f45a2a5a"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_constraint(
        "active_tokens_user_id_fkey", "active_tokens", type_="foreignkey"
    )
    op.drop_column("active_tokens", "user_id")
    op.add_column(
        "dataset_metadata", sa.Column("user_ref", sa.Integer(), nullable=True)
    )
    op.create_foreign_key(None, "dataset_metadata", "users", ["user_ref"], ["id"])
    op.drop_column("dataset_metadata", "user_id")
    op.drop_column("datasets", "owner_id")
    op.add_column("datasets", sa.Column("owner_id", sa.Integer(), nullable=False))
    op.create_foreign_key(None, "datasets", "users", ["owner_id"], ["id"])
    op.add_column("users", sa.Column("oidc_id", sa.String(length=255), nullable=False))
    op.add_column("users", sa.Column("profile", sa.JSON(), nullable=True))
    op.alter_column(
        "users", "username", existing_type=sa.VARCHAR(length=255), nullable=True
    )
    op.drop_constraint("users_email_key", "users", type_="unique")
    op.create_unique_constraint(None, "users", ["oidc_id"])
    op.drop_column("users", "role")
    op.drop_column("users", "last_name")
    op.drop_column("users", "password")
    op.drop_column("users", "email")
    op.drop_column("users", "first_name")
    op.drop_column("users", "registered_on")
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column(
        "users",
        sa.Column(
            "registered_on", postgresql.TIMESTAMP(), autoincrement=False, nullable=False
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
        sa.Column("email", sa.VARCHAR(length=255), autoincrement=False, nullable=False),
    )
    op.add_column(
        "users",
        sa.Column("password", postgresql.BYTEA(), autoincrement=False, nullable=False),
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
            "role",
            postgresql.ENUM("ADMIN", name="roles"),
            autoincrement=False,
            nullable=True,
        ),
    )
    op.drop_constraint(None, "users", type_="unique")
    op.create_unique_constraint("users_email_key", "users", ["email"])
    op.alter_column(
        "users", "username", existing_type=sa.VARCHAR(length=255), nullable=False
    )
    op.drop_column("users", "profile")
    op.drop_column("users", "oidc_id")
    op.drop_constraint(None, "datasets", type_="foreignkey")
    op.add_column(
        "dataset_metadata",
        sa.Column(
            "user_id", sa.VARCHAR(length=255), autoincrement=False, nullable=True
        ),
    )
    op.drop_constraint(None, "dataset_metadata", type_="foreignkey")
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
