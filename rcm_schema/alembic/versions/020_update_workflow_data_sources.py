"""Enhance workflow_data_sources storage

Revision ID: 020_update_workflow_data_sources
Revises: 019_create_s3_screenshots_table
Create Date: 2025-09-xx

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "020_update_workflow_data_sources"
down_revision = "019_create_s3_screenshots_table"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "workflow_data_sources",
        sa.Column("org_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "workflow_data_sources",
        sa.Column(
            "connected_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.add_column(
        "workflow_data_sources",
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.add_column(
        "workflow_data_sources",
        sa.Column("output_config", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.add_column(
        "workflow_data_sources",
        sa.Column("variables", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.add_column(
        "workflow_data_sources",
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )

    # Populate org_id for existing records
    op.execute(
        """
        UPDATE workflow_data_sources AS wds
        SET org_id = uw.org_id,
            updated_at = NOW()
        FROM user_workflow AS uw
        WHERE uw.workflow_id = wds.workflow_id
        """
    )

    op.alter_column("workflow_data_sources", "org_id", nullable=False)

    op.drop_constraint(
        "workflow_data_sources_pkey", "workflow_data_sources", type_="primary"
    )
    op.create_primary_key(
        "workflow_data_sources_pkey",
        "workflow_data_sources",
        ["workflow_id", "org_id"],
    )

    op.create_index(
        "idx_workflow_data_sources_org",
        "workflow_data_sources",
        ["org_id", "updated_at"],
    )
    op.create_index(
        "idx_workflow_data_sources_data_source",
        "workflow_data_sources",
        ["data_source_id", "updated_at"],
    )

    op.create_foreign_key(
        "fk_workflow_data_sources_org_id",
        "workflow_data_sources",
        "organizations",
        ["org_id"],
        ["org_id"],
        ondelete="CASCADE",
    )


def downgrade():
    op.drop_constraint(
        "fk_workflow_data_sources_org_id", "workflow_data_sources", type_="foreignkey"
    )
    op.drop_index("idx_workflow_data_sources_data_source", table_name="workflow_data_sources")
    op.drop_index("idx_workflow_data_sources_org", table_name="workflow_data_sources")
    op.drop_constraint(
        "workflow_data_sources_pkey", "workflow_data_sources", type_="primary"
    )
    op.create_primary_key(
        "workflow_data_sources_pkey",
        "workflow_data_sources",
        ["workflow_id", "data_source_id"],
    )

    op.drop_column("workflow_data_sources", "metadata")
    op.drop_column("workflow_data_sources", "variables")
    op.drop_column("workflow_data_sources", "output_config")
    op.drop_column("workflow_data_sources", "updated_at")
    op.drop_column("workflow_data_sources", "connected_at")
    op.drop_column("workflow_data_sources", "org_id")
