-- =====================================================
-- SQL Views and Helper Functions for Workflow Execution
-- =====================================================

-- 1. View: Active Workflow Configurations
CREATE OR REPLACE VIEW v_active_workflow_configs AS
SELECT 
    wc.config_id,
    wc.org_id,
    wc.workflow_id,
    wc.name,
    wc.config_type,
    wc.config_data,
    wc.created_at,
    wc.created_by,
    cs.activated_at,
    cs.activated_by,
    uw.name as workflow_name,
    o.name as org_name
FROM workflow_configs wc
LEFT JOIN config_status cs ON cs.active_config_id = wc.config_id
JOIN organization o ON o.org_id = wc.org_id
LEFT JOIN user_workflow uw ON uw.workflow_id = wc.workflow_id
WHERE wc.is_active = true;

-- 2. View: Workflow Execution Summary
CREATE OR REPLACE VIEW v_workflow_execution_summary AS
SELECT 
    wt.trace_id,
    wt.workflow_id,
    wt.channel,
    wt.status,
    wt.start_time,
    wt.end_time,
    wt.duration_ms,
    wt.error_message,
    wt.created_by,
    uw.name as workflow_name,
    COUNT(DISTINCT ws.step_id) as total_steps,
    COUNT(DISTINCT CASE WHEN ws.status = 'completed' THEN ws.step_id END) as completed_steps,
    COUNT(DISTINCT CASE WHEN ws.status = 'failed' THEN ws.step_id END) as failed_steps,
    AVG(ws.duration_ms) as avg_step_duration_ms
FROM workflow_trace wt
JOIN user_workflow uw ON uw.workflow_id = wt.workflow_id
LEFT JOIN workflow_steps ws ON ws.trace_id = wt.trace_id
GROUP BY 
    wt.trace_id, wt.workflow_id, wt.channel, wt.status,
    wt.start_time, wt.end_time, wt.duration_ms, wt.error_message,
    wt.created_by, uw.name;

-- 3. View: Workflow Channel Performance
CREATE OR REPLACE VIEW v_workflow_channel_performance AS
SELECT 
    wt.workflow_id,
    wt.channel,
    COUNT(*) as execution_count,
    COUNT(CASE WHEN wt.status = 'completed' THEN 1 END) as success_count,
    COUNT(CASE WHEN wt.status = 'failed' THEN 1 END) as failure_count,
    AVG(wt.duration_ms) as avg_duration_ms,
    MIN(wt.duration_ms) as min_duration_ms,
    MAX(wt.duration_ms) as max_duration_ms,
    PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY wt.duration_ms) as median_duration_ms,
    PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY wt.duration_ms) as p95_duration_ms
FROM workflow_trace wt
WHERE wt.start_time >= NOW() - INTERVAL '30 days'
GROUP BY wt.workflow_id, wt.channel;

-- 4. View: Node Execution Statistics
CREATE OR REPLACE VIEW v_node_execution_stats AS
SELECT 
    ws.node_id,
    wn.code as node_code,
    wn.description as node_description,
    COUNT(*) as execution_count,
    COUNT(CASE WHEN ws.status = 'completed' THEN 1 END) as success_count,
    COUNT(CASE WHEN ws.status = 'failed' THEN 1 END) as failure_count,
    COUNT(CASE WHEN ws.status = 'skipped' THEN 1 END) as skip_count,
    AVG(ws.duration_ms) as avg_duration_ms,
    AVG(ws.retry_count) as avg_retry_count,
    MAX(ws.retry_count) as max_retry_count
FROM workflow_steps ws
JOIN workflow_node wn ON wn.node_id = ws.node_id
WHERE ws.start_time >= NOW() - INTERVAL '30 days'
GROUP BY ws.node_id, wn.code, wn.description;

-- 5. Function: Start Workflow Execution
CREATE OR REPLACE FUNCTION start_workflow_execution(
    p_workflow_id UUID,
    p_channel workflow_channel,
    p_external_id VARCHAR(255),
    p_config_snapshot JSONB,
    p_created_by UUID
) RETURNS BIGINT AS $$
DECLARE
    v_trace_id BIGINT;
BEGIN
    INSERT INTO workflow_trace (
        workflow_id,
        channel,
        external_id,
        status,
        config_snapshot,
        start_time,
        created_by
    ) VALUES (
        p_workflow_id,
        p_channel,
        p_external_id,
        'active',
        p_config_snapshot,
        NOW(),
        p_created_by
    ) RETURNING trace_id INTO v_trace_id;
    
    -- Log start event
    INSERT INTO workflow_events (
        trace_id,
        event_type,
        event_data
    ) VALUES (
        v_trace_id,
        'workflow_started',
        jsonb_build_object(
            'workflow_id', p_workflow_id,
            'channel', p_channel,
            'external_id', p_external_id
        )
    );
    
    RETURN v_trace_id;
END;
$$ LANGUAGE plpgsql;

-- 6. Function: Complete Workflow Execution
CREATE OR REPLACE FUNCTION complete_workflow_execution(
    p_trace_id BIGINT,
    p_status trace_status,
    p_error_message TEXT DEFAULT NULL
) RETURNS VOID AS $$
DECLARE
    v_start_time TIMESTAMP WITH TIME ZONE;
    v_duration_ms INTEGER;
BEGIN
    -- Get start time
    SELECT start_time INTO v_start_time
    FROM workflow_trace
    WHERE trace_id = p_trace_id;
    
    -- Calculate duration
    v_duration_ms := EXTRACT(EPOCH FROM (NOW() - v_start_time)) * 1000;
    
    -- Update trace
    UPDATE workflow_trace
    SET 
        status = p_status,
        end_time = NOW(),
        duration_ms = v_duration_ms,
        error_message = p_error_message
    WHERE trace_id = p_trace_id;
    
    -- Log completion event
    INSERT INTO workflow_events (
        trace_id,
        event_type,
        event_data
    ) VALUES (
        p_trace_id,
        'workflow_completed',
        jsonb_build_object(
            'status', p_status,
            'duration_ms', v_duration_ms,
            'error_message', p_error_message
        )
    );
END;
$$ LANGUAGE plpgsql;

-- 7. Function: Start Workflow Step
CREATE OR REPLACE FUNCTION start_workflow_step(
    p_trace_id BIGINT,
    p_node_id BIGINT,
    p_step_number INTEGER,
    p_input_data JSONB DEFAULT NULL
) RETURNS BIGINT AS $$
DECLARE
    v_step_id BIGINT;
BEGIN
    INSERT INTO workflow_steps (
        trace_id,
        node_id,
        step_number,
        status,
        input_data,
        start_time
    ) VALUES (
        p_trace_id,
        p_node_id,
        p_step_number,
        'running',
        p_input_data,
        NOW()
    ) RETURNING step_id INTO v_step_id;
    
    -- Log step start event
    INSERT INTO workflow_events (
        trace_id,
        step_id,
        event_type,
        event_data
    ) VALUES (
        p_trace_id,
        v_step_id,
        'step_started',
        jsonb_build_object(
            'node_id', p_node_id,
            'step_number', p_step_number
        )
    );
    
    RETURN v_step_id;
END;
$$ LANGUAGE plpgsql;

-- 8. Function: Complete Workflow Step
CREATE OR REPLACE FUNCTION complete_workflow_step(
    p_step_id BIGINT,
    p_status step_status,
    p_output_data JSONB DEFAULT NULL,
    p_error_message TEXT DEFAULT NULL
) RETURNS VOID AS $$
DECLARE
    v_start_time TIMESTAMP WITH TIME ZONE;
    v_duration_ms INTEGER;
    v_trace_id BIGINT;
BEGIN
    -- Get start time and trace_id
    SELECT start_time, trace_id INTO v_start_time, v_trace_id
    FROM workflow_steps
    WHERE step_id = p_step_id;
    
    -- Calculate duration
    v_duration_ms := EXTRACT(EPOCH FROM (NOW() - v_start_time)) * 1000;
    
    -- Update step
    UPDATE workflow_steps
    SET 
        status = p_status,
        output_data = p_output_data,
        error_message = p_error_message,
        end_time = NOW(),
        duration_ms = v_duration_ms
    WHERE step_id = p_step_id;
    
    -- Log step completion event
    INSERT INTO workflow_events (
        trace_id,
        step_id,
        event_type,
        event_data
    ) VALUES (
        v_trace_id,
        p_step_id,
        'step_completed',
        jsonb_build_object(
            'status', p_status,
            'duration_ms', v_duration_ms,
            'error_message', p_error_message
        )
    );
END;
$$ LANGUAGE plpgsql;

-- 9. Function: Set Workflow Context
CREATE OR REPLACE FUNCTION set_workflow_context(
    p_trace_id BIGINT,
    p_key VARCHAR(255),
    p_value JSONB
) RETURNS VOID AS $$
BEGIN
    INSERT INTO workflow_trace_context (trace_id, key, value)
    VALUES (p_trace_id, p_key, p_value)
    ON CONFLICT (trace_id, key) 
    DO UPDATE SET value = p_value, updated_at = NOW();
END;
$$ LANGUAGE plpgsql;

-- 10. Function: Get Workflow Context
CREATE OR REPLACE FUNCTION get_workflow_context(
    p_trace_id BIGINT,
    p_key VARCHAR(255) DEFAULT NULL
) RETURNS TABLE (
    key VARCHAR(255),
    value JSONB,
    created_at TIMESTAMP WITH TIME ZONE,
    updated_at TIMESTAMP WITH TIME ZONE
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        wtc.key,
        wtc.value,
        wtc.created_at,
        wtc.updated_at
    FROM workflow_trace_context wtc
    WHERE wtc.trace_id = p_trace_id
    AND (p_key IS NULL OR wtc.key = p_key);
END;
$$ LANGUAGE plpgsql;

-- 11. Function: Get Active Workflow Config
CREATE OR REPLACE FUNCTION get_active_workflow_config(
    p_org_id UUID,
    p_workflow_id UUID,
    p_config_type config_type
) RETURNS JSONB AS $$
DECLARE
    v_config_data JSONB;
BEGIN
    SELECT wc.config_data INTO v_config_data
    FROM workflow_configs wc
    JOIN config_status cs ON cs.active_config_id = wc.config_id
    WHERE cs.org_id = p_org_id
    AND cs.entity_id = p_workflow_id
    AND cs.config_type = p_config_type
    AND wc.is_active = true
    LIMIT 1;
    
    RETURN v_config_data;
END;
$$ LANGUAGE plpgsql;

-- 12. View: Workflow Execution Timeline
CREATE OR REPLACE VIEW v_workflow_execution_timeline AS
SELECT 
    we.event_id,
    we.trace_id,
    we.step_id,
    we.event_type,
    we.event_data,
    we.timestamp,
    wt.workflow_id,
    wt.channel,
    ws.node_id,
    wn.code as node_code,
    wn.description as node_description
FROM workflow_events we
JOIN workflow_trace wt ON wt.trace_id = we.trace_id
LEFT JOIN workflow_steps ws ON ws.step_id = we.step_id
LEFT JOIN workflow_node wn ON wn.node_id = ws.node_id
ORDER BY we.trace_id, we.timestamp;

-- 13. Function: Retry Workflow Step
CREATE OR REPLACE FUNCTION retry_workflow_step(
    p_step_id BIGINT,
    p_input_data JSONB DEFAULT NULL
) RETURNS VOID AS $$
DECLARE
    v_trace_id BIGINT;
    v_retry_count INTEGER;
    v_node_id BIGINT;
BEGIN
    -- Get current step info
    SELECT trace_id, retry_count + 1, node_id 
    INTO v_trace_id, v_retry_count, v_node_id
    FROM workflow_steps
    WHERE step_id = p_step_id;
    
    -- Update step for retry
    UPDATE workflow_steps
    SET 
        status = 'running',
        retry_count = v_retry_count,
        start_time = NOW(),
        input_data = COALESCE(p_input_data, input_data),
        error_message = NULL,
        output_data = NULL,
        end_time = NULL,
        duration_ms = NULL
    WHERE step_id = p_step_id;
    
    -- Log retry event
    INSERT INTO workflow_events (
        trace_id,
        step_id,
        event_type,
        event_data
    ) VALUES (
        v_trace_id,
        p_step_id,
        'step_retried',
        jsonb_build_object(
            'retry_count', v_retry_count,
            'node_id', v_node_id
        )
    );
END;
$$ LANGUAGE plpgsql;

-- 14. View: Failed Steps Analysis
CREATE OR REPLACE VIEW v_failed_steps_analysis AS
SELECT 
    ws.step_id,
    ws.trace_id,
    ws.node_id,
    ws.status,
    ws.error_message,
    ws.retry_count,
    ws.duration_ms,
    wn.code as node_code,
    wn.description as node_description,
    wt.workflow_id,
    wt.channel,
    uw.name as workflow_name
FROM workflow_steps ws
JOIN workflow_node wn ON wn.node_id = ws.node_id
JOIN workflow_trace wt ON wt.trace_id = ws.trace_id
JOIN user_workflow uw ON uw.workflow_id = wt.workflow_id
WHERE ws.status = 'failed'
AND ws.start_time >= NOW() - INTERVAL '7 days'
ORDER BY ws.start_time DESC;

-- 15. Function: Cleanup Old Execution Data
CREATE OR REPLACE FUNCTION cleanup_old_execution_data(
    p_retention_days INTEGER DEFAULT 90
) RETURNS TABLE (
    deleted_traces BIGINT,
    deleted_steps BIGINT,
    deleted_events BIGINT,
    deleted_context BIGINT
) AS $$
DECLARE
    v_cutoff_date TIMESTAMP WITH TIME ZONE;
    v_deleted_traces BIGINT;
    v_deleted_steps BIGINT;
    v_deleted_events BIGINT;
    v_deleted_context BIGINT;
BEGIN
    v_cutoff_date := NOW() - (p_retention_days || ' days')::INTERVAL;
    
    -- Delete old traces and cascade will handle related records
    WITH deleted AS (
        DELETE FROM workflow_trace
        WHERE created_at < v_cutoff_date
        AND status IN ('completed', 'failed', 'cancelled')
        RETURNING trace_id
    )
    SELECT COUNT(*) INTO v_deleted_traces FROM deleted;
    
    -- Count cascaded deletions (approximate)
    SELECT 
        v_deleted_traces,
        v_deleted_traces * 10, -- Estimated steps per trace
        v_deleted_traces * 20, -- Estimated events per trace
        v_deleted_traces * 5   -- Estimated context entries per trace
    INTO 
        deleted_traces,
        deleted_steps,
        deleted_events,
        deleted_context;
    
    RETURN NEXT;
END;
$$ LANGUAGE plpgsql;

-- 16. Indexes for performance
CREATE INDEX IF NOT EXISTS idx_workflow_events_event_type_timestamp 
ON workflow_events(event_type, timestamp);

CREATE INDEX IF NOT EXISTS idx_workflow_trace_created_by 
ON workflow_trace(created_by);

CREATE INDEX IF NOT EXISTS idx_workflow_configs_org_workflow 
ON workflow_configs(org_id, workflow_id);

-- Grant appropriate permissions (adjust as needed)
-- GRANT SELECT ON ALL TABLES IN SCHEMA public TO readonly_role;
-- GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA public TO app_role;