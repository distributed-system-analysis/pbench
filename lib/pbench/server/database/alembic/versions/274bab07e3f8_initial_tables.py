"""Initial tables

Revision ID: 274bab07e3f8
Revises: 62eddcec4817
Create Date: 2023-01-16 05:54:33.496244

Since we are adding Alembic migrations after we have already been using our
database in various contexts, this "Initial tables" migration describes how to
bring an empty database up to the state of the database as of commit 6a764f154.
That commit was the latest working version of the Pbench Server deployed in Red
Hat's staging environment.
"""
from alembic import op
import sqlalchemy as sa

from pbench.server.database.models import TZDateTime

# revision identifiers, used by Alembic.
revision = "274bab07e3f8"
down_revision = "62eddcec4817"
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table(
        "audit",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("root_id", sa.Integer(), nullable=True),
        sa.Column("name", sa.String(length=128), nullable=True),
        sa.Column(
            "operation",
            sa.Enum("CREATE", "READ", "UPDATE", "DELETE", name="operationcode"),
            nullable=False,
        ),
        sa.Column(
            "object_type",
            sa.Enum("DATASET", "CONFIG", "NONE", "TEMPLATE", "TOKEN", name="audittype"),
            nullable=True,
        ),
        sa.Column("object_id", sa.String(length=128), nullable=True),
        sa.Column("object_name", sa.String(length=256), nullable=True),
        sa.Column("user_id", sa.String(length=128), nullable=True),
        sa.Column("user_name", sa.String(length=256), nullable=True),
        sa.Column(
            "status",
            sa.Enum("BEGIN", "SUCCESS", "FAILURE", "WARNING", name="auditstatus"),
            nullable=False,
        ),
        sa.Column(
            "reason",
            sa.Enum("PERMISSION", "INTERNAL", "CONSISTENCY", name="auditreason"),
            nullable=True,
        ),
        sa.Column("attributes", sa.JSON(), nullable=True),
        sa.Column("timestamp", TZDateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "datasets",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("owner_id", sa.String(length=255), nullable=False),
        sa.Column("access", sa.String(length=255), nullable=False),
        sa.Column("resource_id", sa.String(length=255), nullable=False),
        sa.Column("uploaded", TZDateTime(), nullable=False),
        sa.Column("created", TZDateTime(), nullable=True),
        sa.Column(
            "state",
            sa.Enum(
                "UPLOADING",
                "UPLOADED",
                "INDEXING",
                "INDEXED",
                "DELETING",
                "DELETED",
                name="states",
            ),
            nullable=False,
        ),
        sa.Column("transition", TZDateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("resource_id"),
    )
    op.create_table(
        "serverconfig",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("key", sa.String(length=255), nullable=False),
        sa.Column("value", sa.JSON(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_serverconfig_key"), "serverconfig", ["key"], unique=True)
    op.create_table(
        "templates",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("idxname", sa.String(length=255), nullable=False),
        sa.Column("template_name", sa.String(length=255), nullable=False),
        sa.Column("file", sa.String(length=255), nullable=False),
        sa.Column("mtime", sa.DateTime(), nullable=False),
        sa.Column("template_pattern", sa.String(length=255), nullable=False),
        sa.Column("index_template", sa.String(length=225), nullable=False),
        sa.Column("settings", sa.JSON(), nullable=False),
        sa.Column("mappings", sa.JSON(), nullable=False),
        sa.Column("version", sa.String(length=255), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("idxname"),
        sa.UniqueConstraint("name"),
        sa.UniqueConstraint("template_name"),
    )
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("username", sa.String(length=255), nullable=False),
        sa.Column("first_name", sa.String(length=255), nullable=False),
        sa.Column("last_name", sa.String(length=255), nullable=False),
        sa.Column("password", sa.LargeBinary(length=128), nullable=False),
        sa.Column("registered_on", sa.DateTime(), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("role", sa.Enum("ADMIN", name="roles"), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email"),
        sa.UniqueConstraint("username"),
    )
    op.create_table(
        "active_tokens",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("token", sa.String(length=500), nullable=False),
        sa.Column("created", sa.DateTime(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_active_tokens_token"), "active_tokens", ["token"], unique=True
    )
    op.create_table(
        "dataset_metadata",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("key", sa.String(length=255), nullable=False),
        sa.Column("value", sa.JSON(), nullable=True),
        sa.Column("dataset_ref", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.String(length=255), nullable=True),
        sa.ForeignKeyConstraint(
            ["dataset_ref"],
            ["datasets.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_dataset_metadata_key"), "dataset_metadata", ["key"], unique=False
    )
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_index(op.f("ix_dataset_metadata_key"), table_name="dataset_metadata")
    op.drop_table("dataset_metadata")
    op.drop_index(op.f("ix_active_tokens_token"), table_name="active_tokens")
    op.drop_table("active_tokens")
    op.drop_table("users")
    op.drop_table("templates")
    op.drop_index(op.f("ix_serverconfig_key"), table_name="serverconfig")
    op.drop_table("serverconfig")
    op.drop_table("datasets")
    op.drop_table("audit")
    # ### end Alembic commands ###
