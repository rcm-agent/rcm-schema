"""Add workflow execution tables for web agent

Revision ID: 014_add_workflow_execution_tables
Revises: 013_add_user_invitations
Create Date: 2025-08-08

This migration adds comprehensive workflow execution tables for web agent functionality,
including multi-channel support (web, voice, efax), configuration management, and
enhanced security with proper constraints and indexes.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
import uuid

# revision identifiers
revision = '014_add_workflow_execution_tables'
down_revision = '013_add_user_invitations_table'
branch_labels = None
depends_on = None


def upgrade():
    # Create enums (with IF NOT EXISTS check)
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE workflow_channel AS ENUM ('web', 'voice', 'efax');
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
    """)
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE config_type AS ENUM ('workflow', 'channel', 'global');
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
    """)
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE workflow_io_direction AS ENUM ('input', 'output');
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
    """)
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE step_status AS ENUM ('pending', 'running', 'completed', 'failed', 'skipped');
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
    """)
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE trace_status AS ENUM ('pending', 'active', 'completed', 'failed', 'cancelled', 'timeout');
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
    """)
    
    # 1. Create workflow_configs table
    op.create_table('workflow_configs',
        sa.Column('config_id', postgresql.UUID(as_uuid=True), nullable=False, 
                  default=uuid.uuid4, server_default=sa.text('gen_random_uuid()')),
        sa.Column('org_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('workflow_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('config_type', postgresql.ENUM('workflow', 'channel', 'global', name='config_type'), nullable=False),
        sa.Column('config_data', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_by', postgresql.UUID(as_uuid=True), nullable=False),
        
        sa.PrimaryKeyConstraint('config_id'),
        sa.ForeignKeyConstraint(['org_id'], ['organization.org_id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['workflow_id'], ['user_workflow.workflow_id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['created_by'], ['app_user.user_id'], ondelete='RESTRICT'),
        sa.UniqueConstraint('org_id', 'workflow_id', 'name', 'config_type', name='uq_workflow_config_unique')
    )
    
    # 2. Create channel_configs table
    op.create_table('channel_configs',
        sa.Column('channel_config_id', postgresql.UUID(as_uuid=True), nullable=False, 
                  default=uuid.uuid4, server_default=sa.text('gen_random_uuid()')),
        sa.Column('org_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('channel', postgresql.ENUM('web', 'voice', 'efax', name='workflow_channel'), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('config_data', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_by', postgresql.UUID(as_uuid=True), nullable=False),
        
        sa.PrimaryKeyConstraint('channel_config_id'),
        sa.ForeignKeyConstraint(['org_id'], ['organization.org_id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['created_by'], ['app_user.user_id'], ondelete='RESTRICT'),
        sa.UniqueConstraint('org_id', 'channel', 'name', name='uq_channel_config_unique')
    )
    
    # 3. Create workflow_channel_configs table
    op.create_table('workflow_channel_configs',
        sa.Column('workflow_channel_config_id', postgresql.UUID(as_uuid=True), nullable=False, 
                  default=uuid.uuid4, server_default=sa.text('gen_random_uuid()')),
        sa.Column('workflow_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('channel', postgresql.ENUM('web', 'voice', 'efax', name='workflow_channel'), nullable=False),
        sa.Column('channel_config_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('webhook_url', sa.Text(), nullable=True),
        sa.Column('is_enabled', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('priority', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        
        sa.PrimaryKeyConstraint('workflow_channel_config_id'),
        sa.ForeignKeyConstraint(['workflow_id'], ['user_workflow.workflow_id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['channel_config_id'], ['channel_configs.channel_config_id'], ondelete='SET NULL'),
        sa.UniqueConstraint('workflow_id', 'channel', name='uq_workflow_channel_unique')
    )
    
    # 4. Create node_io_requirements table
    op.create_table('node_io_requirements',
        sa.Column('node_io_id', postgresql.UUID(as_uuid=True), nullable=False, 
                  default=uuid.uuid4, server_default=sa.text('gen_random_uuid()')),
        sa.Column('node_id', sa.BigInteger(), nullable=False),
        sa.Column('io_name', sa.String(255), nullable=False),
        sa.Column('io_direction', postgresql.ENUM('input', 'output', name='workflow_io_direction'), nullable=False),
        sa.Column('data_type', sa.String(50), nullable=False),
        sa.Column('is_required', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('default_value', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('validation_rules', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        
        sa.PrimaryKeyConstraint('node_io_id'),
        sa.ForeignKeyConstraint(['node_id'], ['workflow_node.node_id'], ondelete='CASCADE'),
        sa.UniqueConstraint('node_id', 'io_name', 'io_direction', name='uq_node_io_unique')
    )
    
    # 5. Create workflow_trace table
    op.create_table('workflow_trace',
        sa.Column('trace_id', sa.BigInteger(), nullable=False, autoincrement=True),
        sa.Column('workflow_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('channel', postgresql.ENUM('web', 'voice', 'efax', name='workflow_channel'), nullable=False),
        sa.Column('external_id', sa.String(255), nullable=True),
        sa.Column('status', postgresql.ENUM('pending', 'active', 'completed', 'failed', 'cancelled', 'timeout', name='trace_status'), nullable=False, server_default='pending'),
        sa.Column('config_snapshot', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('start_time', sa.DateTime(timezone=True), nullable=True),
        sa.Column('end_time', sa.DateTime(timezone=True), nullable=True),
        sa.Column('duration_ms', sa.Integer(), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('created_by', postgresql.UUID(as_uuid=True), nullable=False),
        
        sa.PrimaryKeyConstraint('trace_id'),
        sa.ForeignKeyConstraint(['workflow_id'], ['user_workflow.workflow_id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['created_by'], ['app_user.user_id'], ondelete='RESTRICT')
    )
    
    # 6. Create workflow_steps table
    op.create_table('workflow_steps',
        sa.Column('step_id', sa.BigInteger(), nullable=False, autoincrement=True),
        sa.Column('trace_id', sa.BigInteger(), nullable=False),
        sa.Column('node_id', sa.BigInteger(), nullable=False),
        sa.Column('step_number', sa.Integer(), nullable=False),
        sa.Column('status', postgresql.ENUM('pending', 'running', 'completed', 'failed', 'skipped', name='step_status'), nullable=False, server_default='pending'),
        sa.Column('input_data', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('output_data', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('start_time', sa.DateTime(timezone=True), nullable=True),
        sa.Column('end_time', sa.DateTime(timezone=True), nullable=True),
        sa.Column('duration_ms', sa.Integer(), nullable=True),
        sa.Column('retry_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        
        sa.PrimaryKeyConstraint('step_id'),
        sa.ForeignKeyConstraint(['trace_id'], ['workflow_trace.trace_id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['node_id'], ['workflow_node.node_id'], ondelete='RESTRICT'),
        sa.UniqueConstraint('trace_id', 'step_number', name='uq_workflow_step_number')
    )
    
    # 7. Create workflow_trace_context table
    op.create_table('workflow_trace_context',
        sa.Column('context_id', sa.BigInteger(), nullable=False, autoincrement=True),
        sa.Column('trace_id', sa.BigInteger(), nullable=False),
        sa.Column('key', sa.String(255), nullable=False),
        sa.Column('value', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        
        sa.PrimaryKeyConstraint('context_id'),
        sa.ForeignKeyConstraint(['trace_id'], ['workflow_trace.trace_id'], ondelete='CASCADE'),
        sa.UniqueConstraint('trace_id', 'key', name='uq_trace_context_key')
    )
    
    # 8. Create workflow_events table
    op.create_table('workflow_events',
        sa.Column('event_id', sa.BigInteger(), nullable=False, autoincrement=True),
        sa.Column('trace_id', sa.BigInteger(), nullable=False),
        sa.Column('step_id', sa.BigInteger(), nullable=True),
        sa.Column('event_type', sa.String(100), nullable=False),
        sa.Column('event_data', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('timestamp', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        
        sa.PrimaryKeyConstraint('event_id'),
        sa.ForeignKeyConstraint(['trace_id'], ['workflow_trace.trace_id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['step_id'], ['workflow_steps.step_id'], ondelete='CASCADE')
    )
    
    # 9. Create workflow_data_bindings table
    op.create_table('workflow_data_bindings',
        sa.Column('binding_id', postgresql.UUID(as_uuid=True), nullable=False, 
                  default=uuid.uuid4, server_default=sa.text('gen_random_uuid()')),
        sa.Column('workflow_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('node_id', sa.BigInteger(), nullable=False),
        sa.Column('io_name', sa.String(255), nullable=False),
        sa.Column('binding_type', sa.String(50), nullable=False),
        sa.Column('binding_config', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        
        sa.PrimaryKeyConstraint('binding_id'),
        sa.ForeignKeyConstraint(['workflow_id'], ['user_workflow.workflow_id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['node_id'], ['workflow_node.node_id'], ondelete='CASCADE'),
        sa.UniqueConstraint('workflow_id', 'node_id', 'io_name', name='uq_workflow_data_binding')
    )
    
    # 10. Create config_status table (for tracking active configs)
    op.create_table('config_status',
        sa.Column('status_id', postgresql.UUID(as_uuid=True), nullable=False, 
                  default=uuid.uuid4, server_default=sa.text('gen_random_uuid()')),
        sa.Column('org_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('config_type', postgresql.ENUM('workflow', 'channel', 'global', name='config_type'), nullable=False),
        sa.Column('entity_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('active_config_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('activated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('activated_by', postgresql.UUID(as_uuid=True), nullable=False),
        
        sa.PrimaryKeyConstraint('status_id'),
        sa.ForeignKeyConstraint(['org_id'], ['organization.org_id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['activated_by'], ['app_user.user_id'], ondelete='RESTRICT'),
        sa.UniqueConstraint('org_id', 'config_type', 'entity_id', name='uq_config_status_unique')
    )
    
    # Create indexes for performance
    op.create_index('idx_workflow_configs_org_id', 'workflow_configs', ['org_id'])
    op.create_index('idx_workflow_configs_workflow_id', 'workflow_configs', ['workflow_id'])
    op.create_index('idx_workflow_configs_type', 'workflow_configs', ['config_type'])
    op.create_index('idx_workflow_configs_active', 'workflow_configs', ['is_active'])
    
    op.create_index('idx_channel_configs_org_id', 'channel_configs', ['org_id'])
    op.create_index('idx_channel_configs_channel', 'channel_configs', ['channel'])
    op.create_index('idx_channel_configs_active', 'channel_configs', ['is_active'])
    
    op.create_index('idx_workflow_channel_configs_workflow', 'workflow_channel_configs', ['workflow_id'])
    op.create_index('idx_workflow_channel_configs_channel', 'workflow_channel_configs', ['channel'])
    op.create_index('idx_workflow_channel_configs_enabled', 'workflow_channel_configs', ['is_enabled'])
    
    op.create_index('idx_node_io_requirements_node', 'node_io_requirements', ['node_id'])
    op.create_index('idx_node_io_requirements_direction', 'node_io_requirements', ['io_direction'])
    
    op.create_index('idx_workflow_trace_workflow', 'workflow_trace', ['workflow_id'])
    op.create_index('idx_workflow_trace_channel', 'workflow_trace', ['channel'])
    op.create_index('idx_workflow_trace_status', 'workflow_trace', ['status'])
    op.create_index('idx_workflow_trace_created_at', 'workflow_trace', ['created_at'])
    op.create_index('idx_workflow_trace_external_id', 'workflow_trace', ['external_id'])
    
    op.create_index('idx_workflow_steps_trace', 'workflow_steps', ['trace_id'])
    op.create_index('idx_workflow_steps_node', 'workflow_steps', ['node_id'])
    op.create_index('idx_workflow_steps_status', 'workflow_steps', ['status'])
    
    op.create_index('idx_workflow_trace_context_trace', 'workflow_trace_context', ['trace_id'])
    op.create_index('idx_workflow_trace_context_key', 'workflow_trace_context', ['key'])
    
    op.create_index('idx_workflow_events_trace', 'workflow_events', ['trace_id'])
    op.create_index('idx_workflow_events_step', 'workflow_events', ['step_id'])
    op.create_index('idx_workflow_events_type', 'workflow_events', ['event_type'])
    op.create_index('idx_workflow_events_timestamp', 'workflow_events', ['timestamp'])
    
    op.create_index('idx_workflow_data_bindings_workflow', 'workflow_data_bindings', ['workflow_id'])
    op.create_index('idx_workflow_data_bindings_node', 'workflow_data_bindings', ['node_id'])
    
    op.create_index('idx_config_status_org', 'config_status', ['org_id'])
    op.create_index('idx_config_status_type', 'config_status', ['config_type'])
    op.create_index('idx_config_status_entity', 'config_status', ['entity_id'])
    
    # Create composite indexes for common queries
    op.create_index('idx_workflow_trace_workflow_status', 'workflow_trace', ['workflow_id', 'status'])
    op.create_index('idx_workflow_steps_trace_status', 'workflow_steps', ['trace_id', 'status'])
    op.create_index('idx_workflow_configs_org_type_active', 'workflow_configs', ['org_id', 'config_type', 'is_active'])
    
    # Enable Row Level Security on sensitive tables
    op.execute("ALTER TABLE workflow_configs ENABLE ROW LEVEL SECURITY;")
    op.execute("ALTER TABLE channel_configs ENABLE ROW LEVEL SECURITY;")
    op.execute("ALTER TABLE workflow_trace ENABLE ROW LEVEL SECURITY;")
    op.execute("ALTER TABLE workflow_trace_context ENABLE ROW LEVEL SECURITY;")
    
    # Create RLS policies
    op.execute("""
        CREATE POLICY workflow_configs_org_isolation ON workflow_configs
            FOR ALL
            USING (org_id = current_setting('app.current_org_id')::uuid);
    """)
    
    op.execute("""
        CREATE POLICY channel_configs_org_isolation ON channel_configs
            FOR ALL
            USING (org_id = current_setting('app.current_org_id')::uuid);
    """)
    
    op.execute("""
        CREATE POLICY workflow_trace_org_isolation ON workflow_trace
            FOR ALL
            USING (workflow_id IN (
                SELECT workflow_id FROM user_workflow 
                WHERE org_id = current_setting('app.current_org_id')::uuid
            ));
    """)
    
    op.execute("""
        CREATE POLICY workflow_trace_context_org_isolation ON workflow_trace_context
            FOR ALL
            USING (trace_id IN (
                SELECT t.trace_id FROM workflow_trace t
                JOIN user_workflow w ON t.workflow_id = w.workflow_id
                WHERE w.org_id = current_setting('app.current_org_id')::uuid
            ));
    """)
    
    # Create a function to validate node IO requirements
    op.execute("""
        CREATE OR REPLACE FUNCTION validate_node_io_requirements(p_node_id UUID)
        RETURNS BOOLEAN AS $$
        DECLARE
            v_valid BOOLEAN := TRUE;
            v_error_msg TEXT;
        BEGIN
            -- Check for duplicate input/output names
            IF EXISTS (
                SELECT io_name, io_direction, COUNT(*)
                FROM node_io_requirements
                WHERE node_id = p_node_id
                GROUP BY io_name, io_direction
                HAVING COUNT(*) > 1
            ) THEN
                v_valid := FALSE;
                v_error_msg := 'Duplicate IO names found for node';
            END IF;
            
            -- Check for valid data types
            IF EXISTS (
                SELECT 1
                FROM node_io_requirements
                WHERE node_id = p_node_id
                AND data_type NOT IN ('string', 'number', 'boolean', 'object', 'array', 'date', 'file')
            ) THEN
                v_valid := FALSE;
                v_error_msg := 'Invalid data type specified';
            END IF;
            
            IF NOT v_valid THEN
                RAISE EXCEPTION '%', v_error_msg;
            END IF;
            
            RETURN v_valid;
        END;
        $$ LANGUAGE plpgsql;
    """)
    
    # Create trigger to validate node IO requirements
    op.execute("""
        CREATE OR REPLACE FUNCTION trigger_validate_node_io()
        RETURNS TRIGGER AS $$
        BEGIN
            PERFORM validate_node_io_requirements(NEW.node_id);
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """)
    
    op.execute("""
        CREATE TRIGGER validate_node_io_before_insert
            BEFORE INSERT OR UPDATE ON node_io_requirements
            FOR EACH ROW
            EXECUTE FUNCTION trigger_validate_node_io();
    """)


def downgrade():
    # Drop triggers
    op.execute("DROP TRIGGER IF EXISTS validate_node_io_before_insert ON node_io_requirements;")
    
    # Drop functions
    op.execute("DROP FUNCTION IF EXISTS trigger_validate_node_io();")
    op.execute("DROP FUNCTION IF EXISTS validate_node_io_requirements(UUID);")
    
    # Drop RLS policies
    op.execute("DROP POLICY IF EXISTS workflow_trace_context_org_isolation ON workflow_trace_context;")
    op.execute("DROP POLICY IF EXISTS workflow_trace_org_isolation ON workflow_trace;")
    op.execute("DROP POLICY IF EXISTS channel_configs_org_isolation ON channel_configs;")
    op.execute("DROP POLICY IF EXISTS workflow_configs_org_isolation ON workflow_configs;")
    
    # Disable RLS
    op.execute("ALTER TABLE workflow_trace_context DISABLE ROW LEVEL SECURITY;")
    op.execute("ALTER TABLE workflow_trace DISABLE ROW LEVEL SECURITY;")
    op.execute("ALTER TABLE channel_configs DISABLE ROW LEVEL SECURITY;")
    op.execute("ALTER TABLE workflow_configs DISABLE ROW LEVEL SECURITY;")
    
    # Drop all indexes
    op.drop_index('idx_config_status_entity', 'config_status')
    op.drop_index('idx_config_status_type', 'config_status')
    op.drop_index('idx_config_status_org', 'config_status')
    
    op.drop_index('idx_workflow_data_bindings_node', 'workflow_data_bindings')
    op.drop_index('idx_workflow_data_bindings_workflow', 'workflow_data_bindings')
    
    op.drop_index('idx_workflow_events_timestamp', 'workflow_events')
    op.drop_index('idx_workflow_events_type', 'workflow_events')
    op.drop_index('idx_workflow_events_step', 'workflow_events')
    op.drop_index('idx_workflow_events_trace', 'workflow_events')
    
    op.drop_index('idx_workflow_trace_context_key', 'workflow_trace_context')
    op.drop_index('idx_workflow_trace_context_trace', 'workflow_trace_context')
    
    op.drop_index('idx_workflow_steps_trace_status', 'workflow_steps')
    op.drop_index('idx_workflow_steps_status', 'workflow_steps')
    op.drop_index('idx_workflow_steps_node', 'workflow_steps')
    op.drop_index('idx_workflow_steps_trace', 'workflow_steps')
    
    op.drop_index('idx_workflow_trace_workflow_status', 'workflow_trace')
    op.drop_index('idx_workflow_trace_external_id', 'workflow_trace')
    op.drop_index('idx_workflow_trace_created_at', 'workflow_trace')
    op.drop_index('idx_workflow_trace_status', 'workflow_trace')
    op.drop_index('idx_workflow_trace_channel', 'workflow_trace')
    op.drop_index('idx_workflow_trace_workflow', 'workflow_trace')
    
    op.drop_index('idx_node_io_requirements_direction', 'node_io_requirements')
    op.drop_index('idx_node_io_requirements_node', 'node_io_requirements')
    
    op.drop_index('idx_workflow_channel_configs_enabled', 'workflow_channel_configs')
    op.drop_index('idx_workflow_channel_configs_channel', 'workflow_channel_configs')
    op.drop_index('idx_workflow_channel_configs_workflow', 'workflow_channel_configs')
    
    op.drop_index('idx_channel_configs_active', 'channel_configs')
    op.drop_index('idx_channel_configs_channel', 'channel_configs')
    op.drop_index('idx_channel_configs_org_id', 'channel_configs')
    
    op.drop_index('idx_workflow_configs_org_type_active', 'workflow_configs')
    op.drop_index('idx_workflow_configs_active', 'workflow_configs')
    op.drop_index('idx_workflow_configs_type', 'workflow_configs')
    op.drop_index('idx_workflow_configs_workflow_id', 'workflow_configs')
    op.drop_index('idx_workflow_configs_org_id', 'workflow_configs')
    
    # Drop tables in reverse order
    op.drop_table('config_status')
    op.drop_table('workflow_data_bindings')
    op.drop_table('workflow_events')
    op.drop_table('workflow_trace_context')
    op.drop_table('workflow_steps')
    op.drop_table('workflow_trace')
    op.drop_table('node_io_requirements')
    op.drop_table('workflow_channel_configs')
    op.drop_table('channel_configs')
    op.drop_table('workflow_configs')
    
    # Drop enums
    op.execute("DROP TYPE IF EXISTS trace_status;")
    op.execute("DROP TYPE IF EXISTS step_status;")
    op.execute("DROP TYPE IF EXISTS workflow_io_direction;")
    op.execute("DROP TYPE IF EXISTS config_type;")
    op.execute("DROP TYPE IF EXISTS workflow_channel;")