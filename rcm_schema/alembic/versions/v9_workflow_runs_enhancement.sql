-- V9 Schema Migration: Workflow Runs Enhancement
-- This migration adds support for comprehensive workflow run tracking and multiple screenshots
-- Date: 2025-08-03
-- Purpose: Support workflow management UI with detailed run tracking

-- 1. Enhance workflow_trace table with additional tracking fields
ALTER TABLE workflow_trace 
ADD COLUMN IF NOT EXISTS started_by UUID REFERENCES app_user(user_id),
ADD COLUMN IF NOT EXISTS completed_at TIMESTAMP WITH TIME ZONE,
ADD COLUMN IF NOT EXISTS node_count INTEGER DEFAULT 0,
ADD COLUMN IF NOT EXISTS completed_node_count INTEGER DEFAULT 0,
ADD COLUMN IF NOT EXISTS execution_time_ms BIGINT,
ADD COLUMN IF NOT EXISTS error_message TEXT,
ADD COLUMN IF NOT EXISTS metadata JSONB DEFAULT '{}'::jsonb;

-- Add index for faster queries by user
CREATE INDEX IF NOT EXISTS idx_workflow_trace_started_by ON workflow_trace(started_by);
CREATE INDEX IF NOT EXISTS idx_workflow_trace_status_org ON workflow_trace(org_id, status);

-- 2. Create workflow_trace_screenshot table for multiple screenshots per run
CREATE TABLE IF NOT EXISTS workflow_trace_screenshot (
    screenshot_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    trace_id UUID NOT NULL REFERENCES workflow_trace(trace_id) ON DELETE CASCADE,
    org_id UUID NOT NULL REFERENCES organization(org_id) ON DELETE CASCADE,
    node_id INTEGER NOT NULL,
    node_name VARCHAR(255) NOT NULL,
    step_index INTEGER NOT NULL,
    screenshot_url TEXT NOT NULL,
    thumbnail_url TEXT,
    action_description TEXT NOT NULL,
    element_selector TEXT,
    metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    
    -- Ensure screenshot belongs to same org as trace
    CONSTRAINT fk_screenshot_trace_org 
        FOREIGN KEY (trace_id, org_id) 
        REFERENCES workflow_trace(trace_id, org_id)
);

-- Add indexes for performance
CREATE INDEX idx_trace_screenshots ON workflow_trace_screenshot(trace_id, step_index);
CREATE INDEX idx_screenshot_org ON workflow_trace_screenshot(org_id);
CREATE INDEX idx_screenshot_created ON workflow_trace_screenshot(created_at DESC);

-- 3. Add unique constraint to workflow_trace for multi-tenant safety
ALTER TABLE workflow_trace 
ADD CONSTRAINT uk_workflow_trace_org UNIQUE (trace_id, org_id);

-- 4. Update status check constraint to include more statuses
ALTER TABLE workflow_trace 
DROP CONSTRAINT IF EXISTS workflow_trace_status_check;

ALTER TABLE workflow_trace 
ADD CONSTRAINT workflow_trace_status_check 
CHECK (status IN ('pending', 'running', 'completed', 'failed', 'cancelled', 'timeout'));

-- 5. Add trigger to update execution_time_ms when completed_at is set
CREATE OR REPLACE FUNCTION update_execution_time()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.completed_at IS NOT NULL AND NEW.created_at IS NOT NULL THEN
        NEW.execution_time_ms = EXTRACT(EPOCH FROM (NEW.completed_at - NEW.created_at)) * 1000;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trigger_update_execution_time ON workflow_trace;
CREATE TRIGGER trigger_update_execution_time
BEFORE UPDATE ON workflow_trace
FOR EACH ROW
WHEN (OLD.completed_at IS DISTINCT FROM NEW.completed_at)
EXECUTE FUNCTION update_execution_time();

-- 6. Create view for workflow run summary (backward compatible)
CREATE OR REPLACE VIEW workflow_run_summary AS
SELECT 
    wt.trace_id as run_id,
    wt.org_id,
    wt.workflow_id,
    w.name as workflow_name,
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
    wt.metadata
FROM workflow_trace wt
LEFT JOIN workflow w ON wt.workflow_id = w.workflow_id
LEFT JOIN app_user au ON wt.started_by = au.user_id
LEFT JOIN workflow_trace_screenshot wts ON wt.trace_id = wts.trace_id
GROUP BY 
    wt.trace_id, wt.org_id, wt.workflow_id, w.name, wt.status,
    wt.created_at, wt.completed_at, wt.execution_time_ms,
    wt.started_by, au.email, wt.node_count, wt.completed_node_count,
    wt.error_message, wt.metadata;

-- 7. Add comments for documentation
COMMENT ON TABLE workflow_trace_screenshot IS 'Stores multiple screenshots captured during workflow execution';
COMMENT ON COLUMN workflow_trace.started_by IS 'User who initiated the workflow run';
COMMENT ON COLUMN workflow_trace.completed_at IS 'Timestamp when workflow execution completed';
COMMENT ON COLUMN workflow_trace.node_count IS 'Total number of nodes in the workflow';
COMMENT ON COLUMN workflow_trace.completed_node_count IS 'Number of nodes successfully executed';
COMMENT ON COLUMN workflow_trace.execution_time_ms IS 'Total execution time in milliseconds';
COMMENT ON COLUMN workflow_trace.error_message IS 'Error message if workflow failed';
COMMENT ON COLUMN workflow_trace.metadata IS 'Additional metadata about the run (trigger source, environment, etc)';

-- 8. Sample data for development (remove in production)
-- INSERT INTO workflow_trace_screenshot (trace_id, org_id, node_id, node_name, step_index, screenshot_url, action_description)
-- SELECT 
--     trace_id,
--     org_id,
--     1,
--     'Login',
--     1,
--     'https://example.com/screenshot1.png',
--     'Entering username'
-- FROM workflow_trace
-- WHERE status = 'completed'
-- LIMIT 1;