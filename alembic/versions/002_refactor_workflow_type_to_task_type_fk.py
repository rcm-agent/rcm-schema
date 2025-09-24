"""refactor workflow_type to task_type_fk

Revision ID: 002
Revises: 001
Create Date: 2025-07-29

This migration replaces the workflow_type enum column with a foreign key
to the task_type table for better consistency and flexibility.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '002_refactor_workflow_type_to_task_type_fk'
down_revision = '001_initial_schema'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Replace workflow_type with task_type_id foreign key."""
    
    # Step 1: Add task_type_id column to batch_job (nullable initially)
    op.add_column('batch_job', 
        sa.Column('task_type_id', postgresql.UUID(as_uuid=True), nullable=True)
    )
    
    # Step 2: Create temporary legacy task types for migration
    # This ensures we have task_type records to link to
    op.execute("""
        INSERT INTO task_type (task_type_id, domain, action, display_name, description)
        VALUES 
            (gen_random_uuid(), 'eligibility', 'status_check', 'Legacy Eligibility Check', 'Migrated from workflow_type=eligibility'),
            (gen_random_uuid(), 'claim', 'status_check', 'Legacy Claim Status', 'Migrated from workflow_type=claim_status'),
            (gen_random_uuid(), 'prior_auth', 'submit', 'Legacy Prior Auth', 'Migrated from workflow_type=prior_auth')
        ON CONFLICT DO NOTHING;
    """)
    
    # Step 3: Update existing batch_job records to use the new task_type_id
    op.execute("""
        UPDATE batch_job b
        SET task_type_id = (
            SELECT task_type_id 
            FROM task_type t
            WHERE 
                CASE 
                    WHEN b.workflow_type = 'eligibility' THEN t.domain = 'eligibility' AND t.action = 'status_check'
                    WHEN b.workflow_type = 'claim_status' THEN t.domain = 'claim' AND t.action = 'status_check'
                    WHEN b.workflow_type = 'prior_auth' THEN t.domain = 'prior_auth' AND t.action = 'submit'
                END
            LIMIT 1
        )
        WHERE b.task_type_id IS NULL;
    """)
    
    # Step 4: Make task_type_id NOT NULL and add foreign key constraint
    op.alter_column('batch_job', 'task_type_id', nullable=False)
    op.create_foreign_key(
        'fk_batch_job_task_type', 
        'batch_job', 
        'task_type', 
        ['task_type_id'], 
        ['task_type_id']
    )
    
    # Step 5: Drop the workflow_type column from batch_job
    op.drop_column('batch_job', 'workflow_type')
    
    # Step 6: Remove workflow_type from rcm_trace
    op.drop_column('rcm_trace', 'workflow_type')
    
    # Step 7: Drop the old index and create new one for rcm_trace
    op.drop_index('idx_rcm_trace_portal_workflow', 'rcm_trace')
    op.create_index('idx_rcm_trace_portal_created', 'rcm_trace', 
                    ['portal_id', sa.text('created_at DESC')])
    
    # Step 8: Drop the workflow_type enum
    op.execute("DROP TYPE IF EXISTS workflow_type")


def downgrade() -> None:
    """Revert to workflow_type enum columns."""
    
    # Step 1: Recreate workflow_type enum
    op.execute("CREATE TYPE workflow_type AS ENUM ('eligibility', 'claim_status', 'prior_auth')")
    
    # Step 2: Add workflow_type column back to batch_job
    op.add_column('batch_job',
        sa.Column('workflow_type', postgresql.ENUM('eligibility', 'claim_status', 'prior_auth', 
                                                    name='workflow_type', create_type=False), 
                  nullable=True)
    )
    
    # Step 3: Populate workflow_type based on task_type
    op.execute("""
        UPDATE batch_job b
        SET workflow_type = 
            CASE 
                WHEN t.domain = 'eligibility' THEN 'eligibility'::workflow_type
                WHEN t.domain = 'claim' THEN 'claim_status'::workflow_type
                WHEN t.domain = 'prior_auth' THEN 'prior_auth'::workflow_type
            END
        FROM task_type t
        WHERE b.task_type_id = t.task_type_id;
    """)
    
    # Step 4: Make workflow_type NOT NULL
    op.alter_column('batch_job', 'workflow_type', nullable=False)
    
    # Step 5: Drop the foreign key and task_type_id column
    op.drop_constraint('fk_batch_job_task_type', 'batch_job', type_='foreignkey')
    op.drop_column('batch_job', 'task_type_id')
    
    # Step 6: Add workflow_type back to rcm_trace
    op.add_column('rcm_trace',
        sa.Column('workflow_type', sa.Text(), nullable=True)
    )
    
    # Update rcm_trace workflow_type from related batch_job (best effort)
    op.execute("""
        UPDATE rcm_trace rt
        SET workflow_type = 'eligibility'
        WHERE workflow_type IS NULL;
    """)
    
    op.alter_column('rcm_trace', 'workflow_type', nullable=False)
    
    # Step 7: Recreate the old index
    op.drop_index('idx_rcm_trace_portal_created', 'rcm_trace')
    op.create_index('idx_rcm_trace_portal_workflow', 'rcm_trace', 
                    ['portal_id', 'workflow_type', sa.text('created_at DESC')])
    
    # Step 8: Remove legacy task_type records (optional)
    op.execute("""
        DELETE FROM task_type 
        WHERE action IN ('check_legacy', 'status_check_legacy');
    """)