"""Initial RCM schema v3

Revision ID: 001
Revises: 
Create Date: 2025-07-29

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
# from pgvector.sqlalchemy import Vector  # TODO: Install pgvector extension

# revision identifiers, used by Alembic.
revision: str = '001_initial_schema'
down_revision = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create extensions
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")
    op.execute("CREATE EXTENSION IF NOT EXISTS \"uuid-ossp\"")
    # op.execute("CREATE EXTENSION IF NOT EXISTS pgvector")  # TODO: Install pgvector extension
    
    # Create ENUM types
    op.execute("CREATE TYPE org_type AS ENUM ('hospital', 'billing_firm', 'credentialer')")
    op.execute("CREATE TYPE endpoint_kind AS ENUM ('payer', 'provider')")
    op.execute("CREATE TYPE task_domain AS ENUM ('eligibility', 'claim', 'prior_auth')")
    op.execute("CREATE TYPE task_action AS ENUM ('status_check', 'submit', 'denial_follow_up')")
    op.execute("CREATE TYPE task_signature_source AS ENUM ('human', 'ai')")
    op.execute("CREATE TYPE workflow_type AS ENUM ('eligibility', 'claim_status', 'prior_auth')")
    op.execute("CREATE TYPE job_status AS ENUM ('queued', 'processing', 'success', 'error')")
    op.execute("CREATE TYPE user_role AS ENUM ('org_admin', 'firm_user', 'hospital_user', 'sys_admin')")
    
    # Create organization table
    op.create_table('organization',
        sa.Column('org_id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('org_type', postgresql.ENUM('hospital', 'billing_firm', 'credentialer', name='org_type', create_type=False), nullable=False),
        sa.Column('name', sa.Text(), nullable=False),
        sa.Column('email_domain', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.PrimaryKeyConstraint('org_id'),
        sa.UniqueConstraint('email_domain'),
        sa.UniqueConstraint('name')
    )
    
    # Create portal_type table
    op.create_table('portal_type',
        sa.Column('portal_type_id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('code', sa.Text(), nullable=True),
        sa.Column('name', sa.Text(), nullable=False),
        sa.Column('base_url', sa.Text(), nullable=False),
        sa.Column('endpoint_kind', postgresql.ENUM('payer', 'provider', name='endpoint_kind', create_type=False), nullable=False),
        sa.PrimaryKeyConstraint('portal_type_id'),
        sa.UniqueConstraint('code')
    )
    
    # Create integration_endpoint table
    op.create_table('integration_endpoint',
        sa.Column('portal_id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('org_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('name', sa.Text(), nullable=False),
        sa.Column('portal_type_id', sa.Integer(), nullable=False),
        sa.Column('base_url', sa.Text(), nullable=True),
        sa.Column('config', postgresql.JSONB(astext_type=sa.Text()), server_default='{}', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['org_id'], ['organization.org_id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['portal_type_id'], ['portal_type.portal_type_id'], ),
        sa.PrimaryKeyConstraint('portal_id'),
        sa.UniqueConstraint('org_id', 'name'),
        sa.UniqueConstraint('org_id', 'portal_type_id')
    )
    
    # Create task_type table
    op.create_table('task_type',
        sa.Column('task_type_id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('domain', postgresql.ENUM('eligibility', 'claim', 'prior_auth', name='task_domain', create_type=False), nullable=False),
        sa.Column('action', postgresql.ENUM('status_check', 'submit', 'denial_follow_up', name='task_action', create_type=False), nullable=False),
        sa.Column('display_name', sa.Text(), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.PrimaryKeyConstraint('task_type_id')
    )
    
    # Create app_user table
    op.create_table('app_user',
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('org_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('email', sa.Text(), nullable=False),
        sa.Column('full_name', sa.Text(), nullable=True),
        sa.Column('role', postgresql.ENUM('org_admin', 'firm_user', 'hospital_user', 'sys_admin', name='user_role', create_type=False), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['org_id'], ['organization.org_id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('user_id'),
        sa.UniqueConstraint('email')
    )
    
    # Create field_requirement table
    op.create_table('field_requirement',
        sa.Column('requirement_id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('task_type_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('portal_id', sa.Integer(), nullable=True),
        sa.Column('required_fields', postgresql.JSONB(astext_type=sa.Text()), server_default='[]', nullable=False),
        sa.Column('optional_fields', postgresql.JSONB(astext_type=sa.Text()), server_default='[]', nullable=False),
        sa.Column('field_metadata', postgresql.JSONB(astext_type=sa.Text()), server_default='{}', nullable=False),
        sa.Column('version', sa.Integer(), server_default='1', nullable=False),
        sa.Column('active', sa.Boolean(), server_default='true', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['portal_id'], ['integration_endpoint.portal_id'], ),
        sa.ForeignKeyConstraint(['task_type_id'], ['task_type.task_type_id'], ),
        sa.PrimaryKeyConstraint('requirement_id')
    )
    
    # Create batch_job table
    op.create_table('batch_job',
        sa.Column('batch_id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('org_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('portal_id', sa.Integer(), nullable=False),
        sa.Column('workflow_type', postgresql.ENUM('eligibility', 'claim_status', 'prior_auth', name='workflow_type', create_type=False), nullable=False),
        sa.Column('status', postgresql.ENUM('queued', 'processing', 'success', 'error', name='job_status', create_type=False), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('result_url', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['org_id'], ['organization.org_id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['portal_id'], ['integration_endpoint.portal_id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('batch_id')
    )
    op.create_index('idx_batch_status', 'batch_job', ['status'], unique=False)
    
    # Create macro_state table
    op.create_table('macro_state',
        sa.Column('macro_state_id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('portal_id', sa.Integer(), nullable=True),
        sa.Column('canonical_caption', sa.Text(), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('sample_state_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.ForeignKeyConstraint(['portal_id'], ['integration_endpoint.portal_id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('macro_state_id')
    )
    
    # Create rcm_state table
    op.create_table('rcm_state',
        sa.Column('state_id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('portal_id', sa.Integer(), nullable=False),
        # sa.Column('text_emb', Vector(768), nullable=False),  # TODO: Enable when pgvector is installed
        # sa.Column('image_emb', Vector(512), nullable=False),  # TODO: Enable when pgvector is installed
        sa.Column('text_emb', postgresql.JSONB(astext_type=sa.Text()), nullable=True),  # Temporary: store as JSONB
        sa.Column('image_emb', postgresql.JSONB(astext_type=sa.Text()), nullable=True),  # Temporary: store as JSONB
        sa.Column('semantic_spec', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('action', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('success_ema', sa.Float(), server_default='1.0', nullable=False),
        sa.Column('page_caption', sa.Text(), nullable=True),
        sa.Column('action_caption', sa.Text(), nullable=True),
        sa.Column('caption_conf', sa.DECIMAL(precision=3, scale=2), nullable=True),
        sa.Column('macro_state_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('is_retired', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('alias_state_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.ForeignKeyConstraint(['alias_state_id'], ['rcm_state.state_id'], ),
        sa.ForeignKeyConstraint(['macro_state_id'], ['macro_state.macro_state_id'], ),
        sa.ForeignKeyConstraint(['portal_id'], ['integration_endpoint.portal_id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('state_id')
    )
    
    # Add foreign key constraint for sample_state_id (column already created above)
    op.create_foreign_key(None, 'macro_state', 'rcm_state', ['sample_state_id'], ['state_id'])
    
    # Create task_signature table
    op.create_table('task_signature',
        sa.Column('signature_id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('portal_id', sa.Integer(), nullable=True),
        sa.Column('portal_type_id', sa.Integer(), nullable=True),
        sa.Column('domain', postgresql.ENUM('eligibility', 'claim', 'prior_auth', name='task_domain', create_type=False), nullable=False),
        sa.Column('action', postgresql.ENUM('status_check', 'submit', 'denial_follow_up', name='task_action', create_type=False), nullable=False),
        sa.Column('source', postgresql.ENUM('human', 'ai', name='task_signature_source', create_type=False), nullable=False),
        # sa.Column('text_emb', Vector(768), nullable=True),  # TODO: Enable when pgvector is installed
        # sa.Column('image_emb', Vector(512), nullable=True),  # TODO: Enable when pgvector is installed
        sa.Column('text_emb', postgresql.JSONB(astext_type=sa.Text()), nullable=True),  # Temporary: store as JSONB
        sa.Column('image_emb', postgresql.JSONB(astext_type=sa.Text()), nullable=True),  # Temporary: store as JSONB
        sa.Column('sample_trace_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('alias_of', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('composed', sa.Boolean(), server_default='false', nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint('(portal_id IS NOT NULL)::int + (portal_type_id IS NOT NULL)::int = 1', name='task_signature_xor_check'),
        sa.ForeignKeyConstraint(['alias_of'], ['task_signature.signature_id'], ),
        sa.ForeignKeyConstraint(['portal_id'], ['integration_endpoint.portal_id'], ),
        sa.ForeignKeyConstraint(['portal_type_id'], ['portal_type.portal_type_id'], ),
        sa.PrimaryKeyConstraint('signature_id')
    )
    op.create_index(op.f('ix_task_signature_domain'), 'task_signature', ['domain'], unique=False)
    op.create_index(op.f('ix_task_signature_action'), 'task_signature', ['action'], unique=False)
    
    # Create partial unique constraints for task_signature
    op.execute("""
        CREATE UNIQUE INDEX task_signature_portal_unique 
        ON task_signature (portal_id, domain, action) 
        WHERE portal_id IS NOT NULL
    """)
    op.execute("""
        CREATE UNIQUE INDEX task_signature_portal_type_unique 
        ON task_signature (portal_type_id, domain, action) 
        WHERE portal_type_id IS NOT NULL
    """)
    
    # Create rcm_trace table
    op.create_table('rcm_trace',
        sa.Column('trace_id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('portal_id', sa.Integer(), nullable=False),
        sa.Column('org_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('workflow_type', sa.Text(), nullable=False),
        sa.Column('task_signature', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('prompt_version', sa.String(length=20), nullable=True),
        sa.Column('used_fallback', sa.Boolean(), server_default='false', nullable=True),
        sa.Column('fallback_model', sa.Text(), nullable=True),
        sa.Column('trace', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('duration_ms', sa.Integer(), nullable=True),
        sa.Column('success', sa.Boolean(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['org_id'], ['organization.org_id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['portal_id'], ['integration_endpoint.portal_id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['task_signature'], ['task_signature.signature_id'], ),
        sa.PrimaryKeyConstraint('trace_id')
    )
    op.create_index('idx_rcm_trace_portal_workflow', 'rcm_trace', ['portal_id', 'workflow_type', sa.text('created_at DESC')], unique=False)
    
    # Create batch_row table
    op.create_table('batch_row',
        sa.Column('row_id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('batch_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('row_idx', sa.Integer(), nullable=False),
        sa.Column('task_signature', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('trace_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('status', postgresql.ENUM('queued', 'processing', 'success', 'error', name='job_status', create_type=False), nullable=False),
        sa.Column('error_code', sa.Text(), nullable=True),
        sa.Column('error_msg', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['batch_id'], ['batch_job.batch_id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['trace_id'], ['rcm_trace.trace_id'], ),
        sa.PrimaryKeyConstraint('row_id')
    )
    op.create_index('idx_batch_row_batch', 'batch_row', ['batch_id'], unique=False)
    op.create_index('idx_batch_row_status', 'batch_row', ['status'], unique=False)
    
    # Create rcm_transition table
    op.create_table('rcm_transition',
        sa.Column('from_state', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('to_state', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('action_caption', sa.Text(), nullable=False),
        sa.Column('freq', sa.Integer(), server_default='1', nullable=False),
        sa.CheckConstraint('freq >= 1', name='rcm_transition_freq_check'),
        sa.ForeignKeyConstraint(['from_state'], ['rcm_state.state_id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['to_state'], ['rcm_state.state_id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('from_state', 'to_state', 'action_caption')
    )
    
    # Create vector indexes (disabled until pgvector is installed)
    # op.execute("CREATE INDEX idx_rcm_state_text_emb ON rcm_state USING ivfflat (text_emb vector_l2_ops)")
    # op.execute("CREATE INDEX idx_rcm_state_image_emb ON rcm_state USING ivfflat (image_emb vector_l2_ops)")
    # op.execute("CREATE INDEX idx_task_signature_text_emb ON task_signature USING ivfflat (text_emb vector_l2_ops)")
    # op.execute("CREATE INDEX idx_task_signature_image_emb ON task_signature USING ivfflat (image_emb vector_l2_ops)")
    
    # Additional performance indexes
    op.create_index('idx_rcm_state_portal_active', 'rcm_state', ['portal_id', 'is_retired'], unique=False)


def downgrade() -> None:
    # Drop indexes
    op.drop_index('idx_rcm_state_portal_active', table_name='rcm_state')
    op.drop_index('idx_rcm_trace_portal_workflow', table_name='rcm_trace')
    op.drop_index('idx_batch_row_status', table_name='batch_row')
    op.drop_index('idx_batch_row_batch', table_name='batch_row')
    op.drop_index('idx_batch_status', table_name='batch_job')
    op.drop_index(op.f('ix_task_signature_action'), table_name='task_signature')
    op.drop_index(op.f('ix_task_signature_domain'), table_name='task_signature')
    
    # Drop vector indexes
    op.execute("DROP INDEX IF EXISTS idx_rcm_state_text_emb")
    op.execute("DROP INDEX IF EXISTS idx_rcm_state_image_emb")
    op.execute("DROP INDEX IF EXISTS idx_task_signature_text_emb")
    op.execute("DROP INDEX IF EXISTS idx_task_signature_image_emb")
    
    # Drop partial unique indexes
    op.execute("DROP INDEX IF EXISTS task_signature_portal_unique")
    op.execute("DROP INDEX IF EXISTS task_signature_portal_type_unique")
    
    # Drop tables in reverse dependency order
    op.drop_table('rcm_transition')
    op.drop_table('batch_row')
    op.drop_table('rcm_trace')
    op.drop_table('task_signature')
    op.drop_table('rcm_state')
    op.drop_table('macro_state')
    op.drop_table('batch_job')
    op.drop_table('field_requirement')
    op.drop_table('app_user')
    op.drop_table('task_type')
    op.drop_table('integration_endpoint')
    op.drop_table('portal_type')
    op.drop_table('organization')
    
    # Drop ENUM types
    op.execute("DROP TYPE IF EXISTS user_role")
    op.execute("DROP TYPE IF EXISTS job_status")
    op.execute("DROP TYPE IF EXISTS workflow_type")
    op.execute("DROP TYPE IF EXISTS task_signature_source")
    op.execute("DROP TYPE IF EXISTS task_action")
    op.execute("DROP TYPE IF EXISTS task_domain")
    op.execute("DROP TYPE IF EXISTS endpoint_kind")
    op.execute("DROP TYPE IF EXISTS org_type")