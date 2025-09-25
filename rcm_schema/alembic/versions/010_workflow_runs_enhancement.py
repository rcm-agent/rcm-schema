"""V9 workflow runs enhancement

Revision ID: 010_workflow_runs_enhancement
Revises: 009_add_user_org
Create Date: 2025-08-03

This migration:
1. Adds workflow run tracking fields to workflow_trace table
2. Creates workflow_trace_screenshot table for multiple screenshots per run
3. Adds proper indexes for performance
4. Maintains backward compatibility
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
import uuid

# revision identifiers, used by Alembic.
revision = '010_workflow_runs_enhancement'
down_revision = '009_add_user_organization_table'
branch_labels = None
depends_on = None


def upgrade():
    # Add new columns to workflow_trace table
    op.add_column('workflow_trace', sa.Column('status', sa.String(50), nullable=False, server_default='pending'))
    op.add_column('workflow_trace', sa.Column('started_by', postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column('workflow_trace', sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('workflow_trace', sa.Column('node_count', sa.Integer(), nullable=True, server_default='0'))
    op.add_column('workflow_trace', sa.Column('completed_node_count', sa.Integer(), nullable=True, server_default='0'))
    op.add_column('workflow_trace', sa.Column('execution_time_ms', sa.BigInteger(), nullable=True))
    op.add_column('workflow_trace', sa.Column('error_message', sa.Text(), nullable=True))
    op.add_column('workflow_trace', sa.Column('run_metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=True, server_default='{}'))
    
    # Add foreign key for started_by
    op.create_foreign_key('fk_workflow_trace_started_by', 'workflow_trace', 'app_user', ['started_by'], ['user_id'])
    
    # Create indexes
    op.create_index('idx_workflow_trace_started_by', 'workflow_trace', ['started_by'])
    op.create_index('idx_workflow_trace_status_org', 'workflow_trace', ['org_id', 'status'])
    
    # Add check constraint for status
    op.create_check_constraint(
        'workflow_trace_status_check',
        'workflow_trace',
        "status IN ('pending', 'running', 'completed', 'failed', 'cancelled', 'timeout')"
    )
    
    # Create workflow_trace_screenshot table
    op.create_table('workflow_trace_screenshot',
        sa.Column('screenshot_id', postgresql.UUID(as_uuid=True), nullable=False, default=uuid.uuid4),
        sa.Column('trace_id', sa.BigInteger(), nullable=False),
        sa.Column('org_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('node_id', sa.Integer(), nullable=False),
        sa.Column('node_name', sa.String(255), nullable=False),
        sa.Column('step_index', sa.Integer(), nullable=False),
        sa.Column('screenshot_url', sa.Text(), nullable=False),
        sa.Column('thumbnail_url', sa.Text(), nullable=True),
        sa.Column('action_description', sa.Text(), nullable=False),
        sa.Column('element_selector', sa.Text(), nullable=True),
        sa.Column('screenshot_metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=True, server_default='{}'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['org_id'], ['organization.org_id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['trace_id'], ['workflow_trace.trace_id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('screenshot_id')
    )
    
    # Create indexes for workflow_trace_screenshot
    op.create_index('idx_trace_screenshots', 'workflow_trace_screenshot', ['trace_id', 'step_index'])
    op.create_index('idx_screenshot_org', 'workflow_trace_screenshot', ['org_id'])
    op.create_index('idx_screenshot_created', 'workflow_trace_screenshot', ['created_at'])
    
    # Create the execution time update function
    op.execute('''
        CREATE OR REPLACE FUNCTION update_execution_time()
        RETURNS TRIGGER AS $$
        BEGIN
            IF NEW.completed_at IS NOT NULL AND NEW.created_at IS NOT NULL THEN
                NEW.execution_time_ms = EXTRACT(EPOCH FROM (NEW.completed_at - NEW.created_at)) * 1000;
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    ''')
    
    # Create trigger for execution time
    op.execute('''
        CREATE TRIGGER trigger_update_execution_time
        BEFORE UPDATE ON workflow_trace
        FOR EACH ROW
        WHEN (OLD.completed_at IS DISTINCT FROM NEW.completed_at)
        EXECUTE FUNCTION update_execution_time();
    ''')
    
    # Create workflow run summary view
    op.execute('''
        CREATE OR REPLACE VIEW workflow_run_summary AS
        SELECT 
            wt.trace_id as run_id,
            wt.org_id,
            wt.workflow_id,
            uw.name as workflow_name,
            wt.status,
            wt.created_at as started_at,
            wt.completed_at,
            wt.execution_time_ms,
            wt.started_by,
            au.email as started_by_email,
            wt.node_count,
            wt.completed_node_count,
            COALESCE(wt.completed_node_count::float / NULLIF(wt.node_count, 0) * 100, 0) as progress_percentage,
            COUNT(DISTINCT wts.screenshot_id) as screenshot_count,
            wt.error_message,
            wt.run_metadata
        FROM workflow_trace wt
        LEFT JOIN user_workflow uw ON wt.workflow_id = uw.workflow_id
        LEFT JOIN app_user au ON wt.started_by = au.user_id
        LEFT JOIN workflow_trace_screenshot wts ON wt.trace_id = wts.trace_id
        GROUP BY 
            wt.trace_id, wt.org_id, wt.workflow_id, uw.name, wt.status,
            wt.created_at, wt.completed_at, wt.execution_time_ms,
            wt.started_by, au.email, wt.node_count, wt.completed_node_count,
            wt.error_message, wt.run_metadata;
    ''')


def downgrade():
    # Drop view
    op.execute('DROP VIEW IF EXISTS workflow_run_summary')
    
    # Drop trigger and function
    op.execute('DROP TRIGGER IF EXISTS trigger_update_execution_time ON workflow_trace')
    op.execute('DROP FUNCTION IF EXISTS update_execution_time()')
    
    # Drop workflow_trace_screenshot table
    op.drop_table('workflow_trace_screenshot')
    
    # Drop constraints and indexes
    op.drop_constraint('workflow_trace_status_check', 'workflow_trace', type_='check')
    op.drop_index('idx_workflow_trace_status_org', table_name='workflow_trace')
    op.drop_index('idx_workflow_trace_started_by', table_name='workflow_trace')
    op.drop_constraint('fk_workflow_trace_started_by', 'workflow_trace', type_='foreignkey')
    
    # Drop columns from workflow_trace
    op.drop_column('workflow_trace', 'run_metadata')
    op.drop_column('workflow_trace', 'error_message')
    op.drop_column('workflow_trace', 'execution_time_ms')
    op.drop_column('workflow_trace', 'completed_node_count')
    op.drop_column('workflow_trace', 'node_count')
    op.drop_column('workflow_trace', 'completed_at')
    op.drop_column('workflow_trace', 'started_by')
    op.drop_column('workflow_trace', 'status')