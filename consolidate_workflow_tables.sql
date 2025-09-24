-- =====================================================
-- Workflow Table Consolidation Migration
-- Run this with: psql -U postgres -d rcm_db -f consolidate_workflow_tables.sql
-- =====================================================

-- Start transaction for atomicity
BEGIN;

-- ============================================================
-- 1. Create new consolidated tables
-- ============================================================

-- Create user_workflow_run table (main execution record)
CREATE TABLE IF NOT EXISTS user_workflow_run (
    run_id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workflow_id     UUID NOT NULL REFERENCES user_workflow(workflow_id) ON DELETE CASCADE,
    org_id          UUID NOT NULL REFERENCES organization(org_id) ON DELETE CASCADE,
    
    -- Execution info
    status          TEXT NOT NULL DEFAULT 'pending',
    channel         TEXT NOT NULL,
    external_id     VARCHAR(255),
    
    -- Timing
    started_at      TIMESTAMPTZ,
    ended_at        TIMESTAMPTZ,
    duration_ms     INTEGER,
    
    -- Context (replaces workflow_trace_context table)
    context         JSONB NOT NULL DEFAULT '{}'::jsonb,
    
    -- Configuration snapshot
    config_snapshot JSONB,
    
    -- Endpoints (replaces workflow_trace_endpoint table)
    endpoints_used  JSONB NOT NULL DEFAULT '[]'::jsonb,
    
    -- Error handling
    error_message   TEXT,
    error_details   JSONB,
    
    -- LLM tracking (from old workflow_trace)
    llm_prompt      TEXT,
    llm_response    TEXT,
    llm_model       VARCHAR(100),
    llm_tokens_used INTEGER,
    
    -- Tier system
    tier            SMALLINT,
    tier_reason     TEXT,
    
    -- Metadata
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_by      UUID NOT NULL REFERENCES app_user(user_id) ON DELETE RESTRICT,
    updated_at      TIMESTAMPTZ,
    
    -- Legacy reference for migration (temporary)
    legacy_trace_id BIGINT UNIQUE,
    
    -- Constraints
    CONSTRAINT ck_run_status CHECK (status IN ('pending', 'running', 'completed', 'failed', 'cancelled', 'timeout')),
    CONSTRAINT ck_run_channel CHECK (channel IN ('web', 'voice', 'efax')),
    CONSTRAINT uq_run_external_id UNIQUE (org_id, external_id)
);

-- Create user_workflow_run_step table (steps within execution)
CREATE TABLE IF NOT EXISTS user_workflow_run_step (
    step_id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id          UUID NOT NULL REFERENCES user_workflow_run(run_id) ON DELETE CASCADE,
    node_id         UUID NOT NULL REFERENCES user_workflow_node(node_id) ON DELETE RESTRICT,
    
    -- Step execution
    step_number     INTEGER NOT NULL,
    status          TEXT NOT NULL DEFAULT 'pending',
    retry_count     INTEGER NOT NULL DEFAULT 0,
    
    -- Timing
    started_at      TIMESTAMPTZ,
    ended_at        TIMESTAMPTZ,
    duration_ms     INTEGER,
    
    -- Data flow
    input_data      JSONB,
    output_data     JSONB,
    
    -- Screenshots (replaces workflow_trace_screenshot table)
    screenshots     JSONB NOT NULL DEFAULT '[]'::jsonb,
    
    -- Events (replaces workflow_events table)
    events          JSONB NOT NULL DEFAULT '[]'::jsonb,
    
    -- Error handling
    error_message   TEXT,
    error_details   JSONB,
    
    -- Additional metadata
    metadata        JSONB NOT NULL DEFAULT '{}'::jsonb,
    
    -- Timestamps
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ,
    
    -- Legacy reference for migration (temporary)
    legacy_step_id  BIGINT UNIQUE,
    
    -- Constraints
    CONSTRAINT ck_step_status CHECK (status IN ('pending', 'running', 'completed', 'failed', 'skipped')),
    CONSTRAINT uq_run_step_number UNIQUE (run_id, step_number)
);

-- ============================================================
-- 2. Create indexes for performance
-- ============================================================

-- user_workflow_run indexes
CREATE INDEX idx_run_workflow ON user_workflow_run(workflow_id);
CREATE INDEX idx_run_org ON user_workflow_run(org_id);
CREATE INDEX idx_run_status ON user_workflow_run(status);
CREATE INDEX idx_run_channel ON user_workflow_run(channel);
CREATE INDEX idx_run_created_at ON user_workflow_run(created_at DESC);
CREATE INDEX idx_run_external_id ON user_workflow_run(external_id);
CREATE INDEX idx_run_workflow_status ON user_workflow_run(workflow_id, status);
CREATE INDEX idx_run_org_status ON user_workflow_run(org_id, status);

-- JSONB indexes for user_workflow_run
CREATE INDEX idx_run_context_gin ON user_workflow_run 
USING gin(context jsonb_path_ops);

CREATE INDEX idx_run_endpoints_gin ON user_workflow_run 
USING gin(endpoints_used jsonb_path_ops);

-- user_workflow_run_step indexes
CREATE INDEX idx_step_run ON user_workflow_run_step(run_id);
CREATE INDEX idx_step_node ON user_workflow_run_step(node_id);
CREATE INDEX idx_step_status ON user_workflow_run_step(status);
CREATE INDEX idx_step_run_status ON user_workflow_run_step(run_id, status);
CREATE INDEX idx_step_run_number ON user_workflow_run_step(run_id, step_number);

-- JSONB indexes for user_workflow_run_step
CREATE INDEX idx_step_events_gin ON user_workflow_run_step 
USING gin(events jsonb_path_ops);

CREATE INDEX idx_step_screenshots_gin ON user_workflow_run_step 
USING gin(screenshots jsonb_path_ops);

-- ============================================================
-- 3. Rename other tables for consistency
-- ============================================================

-- Check if tables exist before renaming
DO $$
BEGIN
    -- Rename workflow_configs to user_workflow_config
    IF EXISTS (SELECT 1 FROM information_schema.tables 
               WHERE table_name = 'workflow_configs') THEN
        ALTER TABLE workflow_configs RENAME TO user_workflow_config;
    END IF;
    
    -- Rename micro_state to user_workflow_cache_state
    IF EXISTS (SELECT 1 FROM information_schema.tables 
               WHERE table_name = 'micro_state') THEN
        ALTER TABLE micro_state RENAME TO user_workflow_cache_state;
        -- Also rename the primary key column for consistency
        ALTER TABLE user_workflow_cache_state 
        RENAME COLUMN micro_state_id TO cache_state_id;
    END IF;
END $$;

-- ============================================================
-- 4. Migrate data from old tables to new tables
-- ============================================================

-- Only migrate if old tables exist
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.tables 
               WHERE table_name = 'workflow_trace') THEN
        
        -- Migrate workflow_trace to user_workflow_run
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
            error_details,
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
            COALESCE(
                wt.org_id,
                (SELECT org_id FROM user_workflow WHERE workflow_id = wt.workflow_id LIMIT 1),
                (SELECT org_id FROM organization LIMIT 1)  -- Fallback to any org
            ),
            COALESCE(wt.status, 'pending'),
            COALESCE(wt.channel, 'web'),
            wt.external_id,
            wt.start_time,
            wt.end_time,
            wt.duration_ms,
            -- Merge context from workflow_trace_context
            COALESCE(
                (SELECT jsonb_object_agg(key, value) 
                 FROM workflow_trace_context 
                 WHERE trace_id = wt.trace_id),
                '{}'::jsonb
            ),
            wt.config_snapshot,
            -- Merge endpoints from workflow_trace_endpoint
            COALESCE(
                (SELECT jsonb_agg(endpoint_id) 
                 FROM workflow_trace_endpoint 
                 WHERE trace_id = wt.trace_id),
                '[]'::jsonb
            ),
            wt.error_message,
            CASE 
                WHEN wt.error_detail IS NOT NULL THEN wt.error_detail
                ELSE NULL
            END,
            wt.llm_prompt,
            wt.llm_response,
            wt.llm_model,
            wt.llm_tokens_used,
            wt.tier,
            wt.tier_reason,
            wt.created_at,
            COALESCE(wt.created_by, wt.user_id),
            wt.trace_id
        FROM workflow_trace wt
        ON CONFLICT (legacy_trace_id) DO NOTHING;  -- Skip if already migrated
        
        -- Migrate workflow_steps to user_workflow_run_step
        IF EXISTS (SELECT 1 FROM information_schema.tables 
                   WHERE table_name = 'workflow_steps') THEN
            
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
                -- Handle node_id conversion (BIGINT to UUID if needed)
                CASE 
                    WHEN ws.node_id IS NOT NULL THEN
                        COALESCE(
                            (SELECT node_id FROM user_workflow_node WHERE node_id::text = ws.node_id::text LIMIT 1),
                            gen_random_uuid()  -- Generate new UUID if not found
                        )
                    ELSE gen_random_uuid()
                END,
                ws.step_number,
                COALESCE(ws.status, 'pending'),
                COALESCE(ws.retry_count, 0),
                ws.start_time,
                ws.end_time,
                ws.duration_ms,
                ws.input_data,
                ws.output_data,
                -- Merge screenshots from workflow_trace_screenshot
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
                    AND (node_id IS NULL OR node_id::text = ws.node_id::text)),
                    '[]'::jsonb
                ),
                -- Merge events from workflow_events
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
                ),
                ws.error_message,
                COALESCE(ws.metadata, '{}'::jsonb),
                COALESCE(ws.start_time, NOW()),
                ws.step_id
            FROM workflow_steps ws
            JOIN user_workflow_run uwr ON uwr.legacy_trace_id = ws.trace_id
            ON CONFLICT (legacy_step_id) DO NOTHING;  -- Skip if already migrated
        END IF;
    END IF;
END $$;

-- ============================================================
-- 5. Create compatibility views for backward compatibility
-- ============================================================

-- Drop existing views if they exist
DROP VIEW IF EXISTS workflow_trace CASCADE;
DROP VIEW IF EXISTS workflow_steps CASCADE;

-- Create view for workflow_trace compatibility
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
    created_by,
    created_by as user_id,  -- For backward compatibility
    llm_prompt,
    llm_response,
    llm_model,
    llm_tokens_used,
    tier,
    tier_reason
FROM user_workflow_run
WHERE legacy_trace_id IS NOT NULL;

-- Create view for workflow_steps compatibility
CREATE OR REPLACE VIEW workflow_steps AS
SELECT 
    s.legacy_step_id as step_id,
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
WHERE s.legacy_step_id IS NOT NULL;

-- ============================================================
-- 6. Enable Row Level Security on new tables
-- ============================================================

ALTER TABLE user_workflow_run ENABLE ROW LEVEL SECURITY;
ALTER TABLE user_workflow_run_step ENABLE ROW LEVEL SECURITY;

-- Create RLS policies (drop if exists first)
DROP POLICY IF EXISTS user_workflow_run_org_isolation ON user_workflow_run;
CREATE POLICY user_workflow_run_org_isolation ON user_workflow_run
FOR ALL
USING (org_id = current_setting('app.current_org_id', true)::uuid);

DROP POLICY IF EXISTS user_workflow_run_step_org_isolation ON user_workflow_run_step;
CREATE POLICY user_workflow_run_step_org_isolation ON user_workflow_run_step
FOR ALL
USING (run_id IN (
    SELECT run_id FROM user_workflow_run 
    WHERE org_id = current_setting('app.current_org_id', true)::uuid
));

-- ============================================================
-- 7. Add update triggers
-- ============================================================

-- Create or replace update timestamp function
CREATE OR REPLACE FUNCTION update_timestamp() RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Drop existing triggers if they exist
DROP TRIGGER IF EXISTS update_user_workflow_run_updated_at ON user_workflow_run;
DROP TRIGGER IF EXISTS update_user_workflow_run_step_updated_at ON user_workflow_run_step;

-- Create triggers
CREATE TRIGGER update_user_workflow_run_updated_at 
BEFORE UPDATE ON user_workflow_run 
FOR EACH ROW EXECUTE FUNCTION update_timestamp();

CREATE TRIGGER update_user_workflow_run_step_updated_at 
BEFORE UPDATE ON user_workflow_run_step 
FOR EACH ROW EXECUTE FUNCTION update_timestamp();

-- ============================================================
-- 8. Add comments for documentation
-- ============================================================

COMMENT ON TABLE user_workflow_run IS 'Main workflow execution record - one per workflow run';
COMMENT ON TABLE user_workflow_run_step IS 'Steps within a workflow execution';
COMMENT ON TABLE user_workflow_config IS 'Workflow configurations with versioning support';
COMMENT ON TABLE user_workflow_cache_state IS 'Cached states for Tier 1 system (formerly micro_state)';

COMMENT ON COLUMN user_workflow_run.context IS 'Key-value context storage (replaces workflow_trace_context table)';
COMMENT ON COLUMN user_workflow_run.endpoints_used IS 'Array of endpoint IDs used (replaces workflow_trace_endpoint table)';
COMMENT ON COLUMN user_workflow_run_step.screenshots IS 'Array of screenshot data (replaces workflow_trace_screenshot table)';
COMMENT ON COLUMN user_workflow_run_step.events IS 'Array of events (replaces workflow_events table)';

-- ============================================================
-- 9. Update alembic version table
-- ============================================================

INSERT INTO alembic_version (version_num) 
VALUES ('018_consolidate_workflow_tables')
ON CONFLICT (version_num) DO NOTHING;

-- ============================================================
-- 10. Summary of changes
-- ============================================================

DO $$
DECLARE
    v_run_count INTEGER;
    v_step_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO v_run_count FROM user_workflow_run;
    SELECT COUNT(*) INTO v_step_count FROM user_workflow_run_step;
    
    RAISE NOTICE '===================================================';
    RAISE NOTICE 'Workflow Table Consolidation Complete!';
    RAISE NOTICE '===================================================';
    RAISE NOTICE 'Migrated % workflow runs', v_run_count;
    RAISE NOTICE 'Migrated % workflow steps', v_step_count;
    RAISE NOTICE '';
    RAISE NOTICE 'Old tables preserved but can be dropped later:';
    RAISE NOTICE '  - workflow_trace (view created for compatibility)';
    RAISE NOTICE '  - workflow_steps (view created for compatibility)';
    RAISE NOTICE '  - workflow_events (data merged into steps.events)';
    RAISE NOTICE '  - workflow_trace_screenshot (data merged into steps.screenshots)';
    RAISE NOTICE '  - workflow_trace_context (data merged into run.context)';
    RAISE NOTICE '  - workflow_trace_endpoint (data merged into run.endpoints_used)';
    RAISE NOTICE '';
    RAISE NOTICE 'Tables renamed:';
    RAISE NOTICE '  - workflow_configs → user_workflow_config';
    RAISE NOTICE '  - micro_state → user_workflow_cache_state';
    RAISE NOTICE '===================================================';
END $$;

COMMIT;

-- ============================================================
-- Optional: Drop old tables (run separately after verification)
-- ============================================================
-- WARNING: Only run this after verifying migration success!
/*
BEGIN;

-- Drop old tables
DROP TABLE IF EXISTS workflow_events CASCADE;
DROP TABLE IF EXISTS workflow_trace_screenshot CASCADE;
DROP TABLE IF EXISTS workflow_trace_context CASCADE;
DROP TABLE IF EXISTS workflow_trace_endpoint CASCADE;
DROP TABLE IF EXISTS workflow_steps CASCADE;
DROP TABLE IF EXISTS workflow_trace CASCADE;

-- Drop legacy columns (after confirming migration)
ALTER TABLE user_workflow_run DROP COLUMN IF EXISTS legacy_trace_id;
ALTER TABLE user_workflow_run_step DROP COLUMN IF EXISTS legacy_step_id;

COMMIT;
*/