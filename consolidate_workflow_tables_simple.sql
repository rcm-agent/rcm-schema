-- =====================================================
-- Workflow Table Consolidation Migration (SIMPLIFIED)
-- Run this with: docker exec -i rcm-orchestrator-postgres-1 psql -U rcm_user -d rcm_orchestrator < consolidate_workflow_tables_simple.sql
-- =====================================================

-- Start transaction for atomicity
BEGIN;

-- ============================================================
-- 1. Create new consolidated tables
-- ============================================================

-- Drop tables if they exist (for re-running)
DROP TABLE IF EXISTS user_workflow_run_step CASCADE;
DROP TABLE IF EXISTS user_workflow_run CASCADE;

-- Create user_workflow_run table (main execution record)
CREATE TABLE user_workflow_run (
    run_id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workflow_id     UUID NOT NULL REFERENCES user_workflow(workflow_id) ON DELETE CASCADE,
    org_id          UUID REFERENCES organization(org_id) ON DELETE CASCADE,
    
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
    
    -- Metadata
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_by      UUID REFERENCES app_user(user_id) ON DELETE RESTRICT,
    updated_at      TIMESTAMPTZ,
    
    -- Legacy reference for migration (temporary)
    legacy_trace_id BIGINT UNIQUE,
    
    -- Constraints
    CONSTRAINT ck_run_status CHECK (status IN ('pending', 'running', 'completed', 'failed', 'cancelled', 'timeout')),
    CONSTRAINT ck_run_channel CHECK (channel IN ('web', 'voice', 'efax'))
);

-- Create user_workflow_run_step table (steps within execution)
CREATE TABLE user_workflow_run_step (
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

CREATE INDEX idx_run_workflow ON user_workflow_run(workflow_id);
CREATE INDEX idx_run_org ON user_workflow_run(org_id);
CREATE INDEX idx_run_status ON user_workflow_run(status);
CREATE INDEX idx_run_channel ON user_workflow_run(channel);
CREATE INDEX idx_run_created_at ON user_workflow_run(created_at DESC);

CREATE INDEX idx_step_run ON user_workflow_run_step(run_id);
CREATE INDEX idx_step_node ON user_workflow_run_step(node_id);
CREATE INDEX idx_step_status ON user_workflow_run_step(status);

-- ============================================================
-- 3. Migrate data from old tables to new tables
-- ============================================================

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
    error_message,
    created_at,
    created_by,
    legacy_trace_id
)
SELECT 
    wt.workflow_id,
    uw.org_id,  -- Get org_id from user_workflow
    CASE 
        WHEN wt.status::text = 'active' THEN 'running'
        WHEN wt.status::text IN ('pending', 'completed', 'failed', 'cancelled', 'timeout') THEN wt.status::text
        ELSE 'pending'
    END,
    wt.channel::text,
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
    wt.error_message,
    wt.created_at,
    wt.created_by,
    wt.trace_id
FROM workflow_trace wt
LEFT JOIN user_workflow uw ON uw.workflow_id = wt.workflow_id
WHERE uw.workflow_id IS NOT NULL  -- Only migrate traces with valid workflows
ON CONFLICT (legacy_trace_id) DO NOTHING;  -- Skip if already migrated

-- Migrate workflow_steps to user_workflow_run_step
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
    ws.node_id,
    ws.step_number,
    CASE 
        WHEN ws.status::text IN ('pending', 'running', 'completed', 'failed', 'skipped') THEN ws.status::text
        ELSE 'pending'
    END,
    COALESCE(ws.retry_count, 0),
    ws.start_time,
    ws.end_time,
    ws.duration_ms,
    ws.input_data,
    ws.output_data,
    -- Merge screenshots from workflow_trace_screenshot (if exists)
    COALESCE(
        (SELECT jsonb_agg(
            jsonb_build_object(
                'screenshot_id', screenshot_id,
                'path', screenshot_path,
                's3_key', screenshot_s3_key,
                'url', screenshot_url,
                'node_id', node_id,
                'node_name', node_name,
                'timestamp', created_at,
                'metadata', metadata
            )
        ) 
        FROM workflow_trace_screenshot 
        WHERE trace_id = ws.trace_id),
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

-- ============================================================
-- 4. Rename other tables for consistency (if they exist)
-- ============================================================

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
        IF EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name = 'user_workflow_cache_state' 
                   AND column_name = 'micro_state_id') THEN
            ALTER TABLE user_workflow_cache_state 
            RENAME COLUMN micro_state_id TO cache_state_id;
        END IF;
    END IF;
END $$;

-- ============================================================
-- 5. Create update timestamp function and triggers
-- ============================================================

-- Create or replace update timestamp function
CREATE OR REPLACE FUNCTION update_timestamp() RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Create triggers
CREATE TRIGGER update_user_workflow_run_updated_at 
BEFORE UPDATE ON user_workflow_run 
FOR EACH ROW EXECUTE FUNCTION update_timestamp();

CREATE TRIGGER update_user_workflow_run_step_updated_at 
BEFORE UPDATE ON user_workflow_run_step 
FOR EACH ROW EXECUTE FUNCTION update_timestamp();

-- ============================================================
-- 6. Summary of changes
-- ============================================================

DO $$
DECLARE
    v_run_count INTEGER;
    v_step_count INTEGER;
    v_event_count INTEGER;
    v_screenshot_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO v_run_count FROM user_workflow_run;
    SELECT COUNT(*) INTO v_step_count FROM user_workflow_run_step;
    SELECT COUNT(*) INTO v_event_count FROM workflow_events;
    SELECT COUNT(*) INTO v_screenshot_count FROM workflow_trace_screenshot;
    
    RAISE NOTICE '';
    RAISE NOTICE '===================================================';
    RAISE NOTICE 'Workflow Table Consolidation Complete!';
    RAISE NOTICE '===================================================';
    RAISE NOTICE 'Migrated % workflow runs', v_run_count;
    RAISE NOTICE 'Migrated % workflow steps', v_step_count;
    RAISE NOTICE 'Consolidated % events into step.events', v_event_count;
    RAISE NOTICE 'Consolidated % screenshots into step.screenshots', v_screenshot_count;
    RAISE NOTICE '';
    RAISE NOTICE 'New consolidated tables created:';
    RAISE NOTICE '  ✓ user_workflow_run (replaces workflow_trace)';
    RAISE NOTICE '  ✓ user_workflow_run_step (replaces workflow_steps)';
    RAISE NOTICE '';
    RAISE NOTICE 'Data consolidated into JSONB fields:';
    RAISE NOTICE '  ✓ run.context (from workflow_trace_context)';
    RAISE NOTICE '  ✓ run.endpoints_used (from workflow_trace_endpoint)';
    RAISE NOTICE '  ✓ step.events (from workflow_events)';
    RAISE NOTICE '  ✓ step.screenshots (from workflow_trace_screenshot)';
    RAISE NOTICE '';
    RAISE NOTICE 'Tables renamed for consistency:';
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'user_workflow_config') THEN
        RAISE NOTICE '  ✓ workflow_configs → user_workflow_config';
    END IF;
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'user_workflow_cache_state') THEN
        RAISE NOTICE '  ✓ micro_state → user_workflow_cache_state';
    END IF;
    RAISE NOTICE '===================================================';
    RAISE NOTICE '';
END $$;

COMMIT;

-- ============================================================
-- Verification queries (run these to check the migration)
-- ============================================================

-- Check new tables
SELECT 'user_workflow_run' as table_name, COUNT(*) as row_count FROM user_workflow_run
UNION ALL
SELECT 'user_workflow_run_step', COUNT(*) FROM user_workflow_run_step;

-- Check a sample run with steps
SELECT 
    r.run_id,
    r.workflow_id,
    r.status,
    r.channel,
    COUNT(s.step_id) as step_count
FROM user_workflow_run r
LEFT JOIN user_workflow_run_step s ON r.run_id = s.run_id
GROUP BY r.run_id, r.workflow_id, r.status, r.channel
LIMIT 5;