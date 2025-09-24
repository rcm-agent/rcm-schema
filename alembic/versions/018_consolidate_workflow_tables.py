"""Consolidate workflow execution tables to simplified structure

Revision ID: 018_consolidate_workflow_tables
Revises: 017_refactor_workflow_nodes_to_user_owned
Create Date: 2025-01-14

This migration consolidates 8+ workflow execution tables into 2 main tables:
- user_workflow_run (replaces workflow_trace + context + endpoints)
- user_workflow_run_step (replaces workflow_steps + events + screenshots)
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
import uuid

# revision identifiers, used by Alembic.
revision = '018_consolidate_workflow_tables'
down_revision = '017_refactor_workflow_nodes_to_user_owned'
branch_labels = None
depends_on = None


def upgrade():
    # ============================================================
    # 1. Create new consolidated tables
    # ============================================================
    
    # Create user_workflow_run table (main execution record)
    op.create_table(
        'user_workflow_run',
        sa.Column('run_id', postgresql.UUID(as_uuid=True), primary_key=True, 
                  default=uuid.uuid4, server_default=sa.text('gen_random_uuid()')),
        sa.Column('workflow_id', postgresql.UUID(as_uuid=True), 
                  sa.ForeignKey('user_workflow.workflow_id', ondelete='CASCADE'), nullable=False),
        sa.Column('org_id', postgresql.UUID(as_uuid=True), 
                  sa.ForeignKey('organization.org_id', ondelete='CASCADE'), nullable=False),
        
        # Execution info
        sa.Column('status', sa.Text, nullable=False, server_default='pending'),
        sa.Column('channel', sa.Text, nullable=False),
        sa.Column('external_id', sa.String(255)),
        
        # Timing
        sa.Column('started_at', sa.DateTime(timezone=True)),
        sa.Column('ended_at', sa.DateTime(timezone=True)),
        sa.Column('duration_ms', sa.Integer),
        
        # Context (replaces workflow_trace_context)
        sa.Column('context', postgresql.JSONB(astext_type=sa.Text()), 
                  nullable=False, server_default='{}'),
        
        # Configuration snapshot
        sa.Column('config_snapshot', postgresql.JSONB(astext_type=sa.Text())),
        
        # Endpoints (replaces workflow_trace_endpoint)
        sa.Column('endpoints_used', postgresql.JSONB(astext_type=sa.Text()), 
                  nullable=False, server_default='[]'),
        
        # Error handling
        sa.Column('error_message', sa.Text),
        sa.Column('error_details', postgresql.JSONB(astext_type=sa.Text())),
        
        # LLM tracking (from old workflow_trace)
        sa.Column('llm_prompt', sa.Text),
        sa.Column('llm_response', sa.Text),
        sa.Column('llm_model', sa.String(100)),
        sa.Column('llm_tokens_used', sa.Integer),
        
        # Tier system
        sa.Column('tier', sa.SmallInteger),
        sa.Column('tier_reason', sa.Text),
        
        # Metadata
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, 
                  server_default=sa.func.now()),
        sa.Column('created_by', postgresql.UUID(as_uuid=True), 
                  sa.ForeignKey('app_user.user_id', ondelete='RESTRICT'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True)),
        
        # Legacy reference for migration
        sa.Column('legacy_trace_id', sa.BigInteger, unique=True)  # Temporary for migration
    )
    
    # Create user_workflow_run_step table (steps within execution)
    op.create_table(
        'user_workflow_run_step',
        sa.Column('step_id', postgresql.UUID(as_uuid=True), primary_key=True,
                  default=uuid.uuid4, server_default=sa.text('gen_random_uuid()')),
        sa.Column('run_id', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('user_workflow_run.run_id', ondelete='CASCADE'), nullable=False),
        sa.Column('node_id', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('user_workflow_node.node_id', ondelete='RESTRICT'), nullable=False),
        
        # Step execution
        sa.Column('step_number', sa.Integer, nullable=False),
        sa.Column('status', sa.Text, nullable=False, server_default='pending'),
        sa.Column('retry_count', sa.Integer, nullable=False, server_default='0'),
        
        # Timing
        sa.Column('started_at', sa.DateTime(timezone=True)),
        sa.Column('ended_at', sa.DateTime(timezone=True)),
        sa.Column('duration_ms', sa.Integer),
        
        # Data flow
        sa.Column('input_data', postgresql.JSONB(astext_type=sa.Text())),
        sa.Column('output_data', postgresql.JSONB(astext_type=sa.Text())),
        
        # Screenshots (replaces workflow_trace_screenshot)
        sa.Column('screenshots', postgresql.JSONB(astext_type=sa.Text()),
                  nullable=False, server_default='[]'),
        
        # Events (replaces workflow_events)
        sa.Column('events', postgresql.JSONB(astext_type=sa.Text()),
                  nullable=False, server_default='[]'),
        
        # Error handling
        sa.Column('error_message', sa.Text),
        sa.Column('error_details', postgresql.JSONB(astext_type=sa.Text())),
        
        # Additional metadata
        sa.Column('metadata', postgresql.JSONB(astext_type=sa.Text()),
                  nullable=False, server_default='{}'),
        
        # Timestamps
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True)),
        
        # Legacy reference for migration
        sa.Column('legacy_step_id', sa.BigInteger, unique=True)  # Temporary for migration
    )
    
    # ============================================================
    # 2. Add constraints
    # ============================================================
    
    # user_workflow_run constraints
    op.create_check_constraint(
        'ck_run_status',
        'user_workflow_run',
        "status IN ('pending', 'running', 'completed', 'failed', 'cancelled', 'timeout')"
    )
    
    op.create_check_constraint(
        'ck_run_channel',
        'user_workflow_run',
        "channel IN ('web', 'voice', 'efax')"
    )
    
    op.create_unique_constraint(
        'uq_run_external_id',
        'user_workflow_run',
        ['org_id', 'external_id']
    )
    
    # user_workflow_run_step constraints
    op.create_check_constraint(
        'ck_step_status',
        'user_workflow_run_step',
        "status IN ('pending', 'running', 'completed', 'failed', 'skipped')"
    )
    
    op.create_unique_constraint(
        'uq_run_step_number',
        'user_workflow_run_step',
        ['run_id', 'step_number']
    )
    
    # ============================================================
    # 3. Create indexes
    # ============================================================
    
    # user_workflow_run indexes
    op.create_index('idx_run_workflow', 'user_workflow_run', ['workflow_id'])
    op.create_index('idx_run_org', 'user_workflow_run', ['org_id'])
    op.create_index('idx_run_status', 'user_workflow_run', ['status'])
    op.create_index('idx_run_channel', 'user_workflow_run', ['channel'])
    op.create_index('idx_run_created_at', 'user_workflow_run', ['created_at'])
    op.create_index('idx_run_external_id', 'user_workflow_run', ['external_id'])
    op.create_index('idx_run_workflow_status', 'user_workflow_run', ['workflow_id', 'status'])
    op.create_index('idx_run_org_status', 'user_workflow_run', ['org_id', 'status'])
    
    # JSONB indexes for user_workflow_run
    op.execute("""
        CREATE INDEX idx_run_context_gin ON user_workflow_run 
        USING gin(context jsonb_path_ops)
    """)
    
    op.execute("""
        CREATE INDEX idx_run_endpoints_gin ON user_workflow_run 
        USING gin(endpoints_used jsonb_path_ops)
    """)
    
    # user_workflow_run_step indexes
    op.create_index('idx_step_run', 'user_workflow_run_step', ['run_id'])
    op.create_index('idx_step_node', 'user_workflow_run_step', ['node_id'])
    op.create_index('idx_step_status', 'user_workflow_run_step', ['status'])
    op.create_index('idx_step_run_status', 'user_workflow_run_step', ['run_id', 'status'])
    op.create_index('idx_step_run_number', 'user_workflow_run_step', ['run_id', 'step_number'])
    
    # JSONB indexes for user_workflow_run_step
    op.execute("""
        CREATE INDEX idx_step_events_gin ON user_workflow_run_step 
        USING gin(events jsonb_path_ops)
    """)
    
    op.execute("""
        CREATE INDEX idx_step_screenshots_gin ON user_workflow_run_step 
        USING gin(screenshots jsonb_path_ops)
    """)
    
    # ============================================================
    # 4. Rename other tables for consistency
    # ============================================================
    
    # Rename workflow_configs to user_workflow_config (singular)
    op.rename_table('workflow_configs', 'user_workflow_config')
    
    # Rename micro_state to user_workflow_cache_state
    op.rename_table('micro_state', 'user_workflow_cache_state')
    
    # ============================================================
    # 5. Migrate data from old tables to new tables
    # ============================================================
    
    # Migrate workflow_trace to user_workflow_run
    op.execute("""
        INSERT INTO user_workflow_run (
            workflow_id,
            org_id,
            status,
            channel,
            external_id,
            started_at,
            ended_at,
            duration_ms,
            context,
            config_snapshot,
            endpoints_used,
            error_message,
            llm_prompt,
            llm_response,
            llm_model,
            llm_tokens_used,
            tier,
            tier_reason,
            created_at,
            created_by,
            legacy_trace_id
        )
        SELECT 
            wt.workflow_id,
            COALESCE(wt.org_id, uw.org_id),  -- Get org_id from workflow if not in trace
            COALESCE(wt.status, 'pending'),
            COALESCE(wt.channel, 'web'),
            wt.external_id,
            wt.start_time,
            wt.end_time,
            wt.duration_ms,
            COALESCE(
                (SELECT jsonb_object_agg(key, value) 
                 FROM workflow_trace_context 
                 WHERE trace_id = wt.trace_id),
                '{}'::jsonb
            ) as context,
            wt.config_snapshot,
            COALESCE(
                (SELECT jsonb_agg(endpoint_id) 
                 FROM workflow_trace_endpoint 
                 WHERE trace_id = wt.trace_id),
                '[]'::jsonb
            ) as endpoints_used,
            wt.error_message,
            wt.llm_prompt,
            wt.llm_response,
            wt.llm_model,
            wt.llm_tokens_used,
            wt.tier,
            wt.tier_reason,
            wt.created_at,
            COALESCE(wt.created_by, wt.user_id),  -- Handle different column names
            wt.trace_id
        FROM workflow_trace wt
        LEFT JOIN user_workflow uw ON uw.workflow_id = wt.workflow_id
    """)
    
    # Migrate workflow_steps to user_workflow_run_step
    op.execute("""
        INSERT INTO user_workflow_run_step (
            run_id,
            node_id,
            step_number,
            status,
            retry_count,
            started_at,
            ended_at,
            duration_ms,
            input_data,
            output_data,
            screenshots,
            events,
            error_message,
            metadata,
            created_at,
            legacy_step_id
        )
        SELECT 
            uwr.run_id,
            ws.node_id::uuid,  -- Convert BIGINT to UUID if needed
            ws.step_number,
            COALESCE(ws.status, 'pending'),
            ws.retry_count,
            ws.start_time,
            ws.end_time,
            ws.duration_ms,
            ws.input_data,
            ws.output_data,
            COALESCE(
                (SELECT jsonb_agg(
                    jsonb_build_object(
                        'url', screenshot_url,
                        'thumbnail_url', thumbnail_url,
                        'timestamp', created_at,
                        'action', action_description,
                        'selector', element_selector,
                        'element_found', element_found,
                        'confidence', confidence_score
                    )
                ) 
                FROM workflow_trace_screenshot 
                WHERE trace_id = ws.trace_id 
                AND node_id = ws.node_id),
                '[]'::jsonb
            ) as screenshots,
            COALESCE(
                (SELECT jsonb_agg(
                    jsonb_build_object(
                        'type', event_type,
                        'timestamp', timestamp,
                        'data', event_data
                    )
                ) 
                FROM workflow_events 
                WHERE step_id = ws.step_id),
                '[]'::jsonb
            ) as events,
            ws.error_message,
            COALESCE(ws.metadata, '{}'::jsonb),
            COALESCE(ws.start_time, NOW()),
            ws.step_id
        FROM workflow_steps ws
        JOIN user_workflow_run uwr ON uwr.legacy_trace_id = ws.trace_id
    """)
    
    # ============================================================
    # 6. Create compatibility views for old table names
    # ============================================================
    
    # Create view for workflow_trace compatibility
    op.execute("""
        CREATE OR REPLACE VIEW workflow_trace AS
        SELECT 
            legacy_trace_id as trace_id,
            workflow_id,
            org_id,
            channel,
            external_id,
            status,
            config_snapshot,
            started_at as start_time,
            ended_at as end_time,
            duration_ms,
            error_message,
            created_at,
            created_by
        FROM user_workflow_run
        WHERE legacy_trace_id IS NOT NULL
    """)
    
    # Create view for workflow_steps compatibility
    op.execute("""
        CREATE OR REPLACE VIEW workflow_steps AS
        SELECT 
            legacy_step_id as step_id,
            r.legacy_trace_id as trace_id,
            s.node_id,
            s.step_number,
            s.status,
            s.input_data,
            s.output_data,
            s.error_message,
            s.started_at as start_time,
            s.ended_at as end_time,
            s.duration_ms,
            s.retry_count,
            s.metadata
        FROM user_workflow_run_step s
        JOIN user_workflow_run r ON r.run_id = s.run_id
        WHERE s.legacy_step_id IS NOT NULL
    """)
    
    # ============================================================
    # 7. Enable Row Level Security on new tables
    # ============================================================
    
    op.execute("ALTER TABLE user_workflow_run ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE user_workflow_run_step ENABLE ROW LEVEL SECURITY")
    
    # Create RLS policies
    op.execute("""
        CREATE POLICY user_workflow_run_org_isolation ON user_workflow_run
        FOR ALL
        USING (org_id = current_setting('app.current_org_id')::uuid)
    """)
    
    op.execute("""
        CREATE POLICY user_workflow_run_step_org_isolation ON user_workflow_run_step
        FOR ALL
        USING (run_id IN (
            SELECT run_id FROM user_workflow_run 
            WHERE org_id = current_setting('app.current_org_id')::uuid
        ))
    """)
    
    # ============================================================
    # 8. Add update triggers
    # ============================================================
    
    op.execute("""
        CREATE TRIGGER update_user_workflow_run_updated_at 
        BEFORE UPDATE ON user_workflow_run 
        FOR EACH ROW EXECUTE FUNCTION update_timestamp()
    """)
    
    op.execute("""
        CREATE TRIGGER update_user_workflow_run_step_updated_at 
        BEFORE UPDATE ON user_workflow_run_step 
        FOR EACH ROW EXECUTE FUNCTION update_timestamp()
    """)


def downgrade():
    # Drop new tables and restore old structure
    
    # Drop RLS policies
    op.execute("DROP POLICY IF EXISTS user_workflow_run_org_isolation ON user_workflow_run")
    op.execute("DROP POLICY IF EXISTS user_workflow_run_step_org_isolation ON user_workflow_run_step")
    
    # Drop compatibility views
    op.execute("DROP VIEW IF EXISTS workflow_trace")
    op.execute("DROP VIEW IF EXISTS workflow_steps")
    
    # Drop triggers
    op.execute("DROP TRIGGER IF EXISTS update_user_workflow_run_updated_at ON user_workflow_run")
    op.execute("DROP TRIGGER IF EXISTS update_user_workflow_run_step_updated_at ON user_workflow_run_step")
    
    # Drop indexes
    op.drop_index('idx_run_workflow', 'user_workflow_run')
    op.drop_index('idx_run_org', 'user_workflow_run')
    op.drop_index('idx_run_status', 'user_workflow_run')
    op.drop_index('idx_run_channel', 'user_workflow_run')
    op.drop_index('idx_run_created_at', 'user_workflow_run')
    op.drop_index('idx_run_external_id', 'user_workflow_run')
    op.drop_index('idx_run_workflow_status', 'user_workflow_run')
    op.drop_index('idx_run_org_status', 'user_workflow_run')
    op.drop_index('idx_run_context_gin', 'user_workflow_run')
    op.drop_index('idx_run_endpoints_gin', 'user_workflow_run')
    
    op.drop_index('idx_step_run', 'user_workflow_run_step')
    op.drop_index('idx_step_node', 'user_workflow_run_step')
    op.drop_index('idx_step_status', 'user_workflow_run_step')
    op.drop_index('idx_step_run_status', 'user_workflow_run_step')
    op.drop_index('idx_step_run_number', 'user_workflow_run_step')
    op.drop_index('idx_step_events_gin', 'user_workflow_run_step')
    op.drop_index('idx_step_screenshots_gin', 'user_workflow_run_step')
    
    # Drop constraints
    op.drop_constraint('ck_run_status', 'user_workflow_run')
    op.drop_constraint('ck_run_channel', 'user_workflow_run')
    op.drop_constraint('uq_run_external_id', 'user_workflow_run')
    op.drop_constraint('ck_step_status', 'user_workflow_run_step')
    op.drop_constraint('uq_run_step_number', 'user_workflow_run_step')
    
    # Drop new tables
    op.drop_table('user_workflow_run_step')
    op.drop_table('user_workflow_run')
    
    # Rename tables back
    op.rename_table('user_workflow_config', 'workflow_configs')
    op.rename_table('user_workflow_cache_state', 'micro_state')