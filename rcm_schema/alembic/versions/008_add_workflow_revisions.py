"""Add workflow revisions table

Revision ID: 008_add_revisions
Revises: 007_migrate_v8
Create Date: 2025-01-25

This migration adds a workflow_revision table to track workflow changes over time.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers
revision = '008_add_workflow_revisions'
down_revision = '007_migrate_to_v8_schema'
branch_labels = None
depends_on = None


def upgrade():
    """Add workflow_revision table"""
    
    # Create workflow_revision table
    op.create_table('workflow_revision',
        sa.Column('revision_id', sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column('workflow_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('revision_num', sa.Integer(), nullable=False),
        sa.Column('comment', sa.Text(), nullable=True),
        sa.Column('created_by', sa.Text(), nullable=False),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('snapshot', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.ForeignKeyConstraint(['workflow_id'], ['user_workflow.workflow_id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('revision_id'),
        sa.UniqueConstraint('workflow_id', 'revision_num', name='uq_workflow_revision')
    )
    
    # Create indexes
    op.create_index('idx_workflow_revision_workflow', 'workflow_revision', ['workflow_id'])
    op.create_index('idx_workflow_revision_created', 'workflow_revision', ['created_at'])
    
    # Add comment
    op.execute("COMMENT ON TABLE workflow_revision IS 'Stores versioned snapshots of workflow configurations'")
    op.execute("COMMENT ON COLUMN workflow_revision.snapshot IS 'Complete workflow state including nodes and transitions'")


def downgrade():
    """Remove workflow_revision table"""
    op.drop_index('idx_workflow_revision_created', table_name='workflow_revision')
    op.drop_index('idx_workflow_revision_workflow', table_name='workflow_revision')
    op.drop_table('workflow_revision')