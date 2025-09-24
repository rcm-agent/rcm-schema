-- Row Level Security Policies for Multi-tenant Isolation
-- This script must be run after all tables are created

-- Enable RLS on all tenant-scoped tables
ALTER TABLE organization ENABLE ROW LEVEL SECURITY;
ALTER TABLE integration_endpoint ENABLE ROW LEVEL SECURITY;
ALTER TABLE batch_job ENABLE ROW LEVEL SECURITY;
ALTER TABLE batch_row ENABLE ROW LEVEL SECURITY;
ALTER TABLE rcm_state ENABLE ROW LEVEL SECURITY;
ALTER TABLE macro_state ENABLE ROW LEVEL SECURITY;
ALTER TABLE rcm_trace ENABLE ROW LEVEL SECURITY;
ALTER TABLE rcm_transition ENABLE ROW LEVEL SECURITY;
ALTER TABLE app_user ENABLE ROW LEVEL SECURITY;

-- Drop existing policies if they exist (for idempotency)
DROP POLICY IF EXISTS org_isolation_policy ON organization;
DROP POLICY IF EXISTS endpoint_isolation_policy ON integration_endpoint;
DROP POLICY IF EXISTS batch_job_isolation_policy ON batch_job;
DROP POLICY IF EXISTS batch_row_isolation_policy ON batch_row;
DROP POLICY IF EXISTS rcm_state_isolation_policy ON rcm_state;
DROP POLICY IF EXISTS macro_state_isolation_policy ON macro_state;
DROP POLICY IF EXISTS trace_isolation_policy ON rcm_trace;
DROP POLICY IF EXISTS rcm_transition_isolation_policy ON rcm_transition;
DROP POLICY IF EXISTS user_isolation_policy ON app_user;

-- Organization: users can only see their own organization
CREATE POLICY org_isolation_policy ON organization
    FOR ALL 
    USING (org_id = current_setting('app.current_org_id')::uuid);

-- Integration Endpoint: filtered by organization
CREATE POLICY endpoint_isolation_policy ON integration_endpoint
    FOR ALL 
    USING (org_id = current_setting('app.current_org_id')::uuid);

-- Batch Job: filtered by organization
CREATE POLICY batch_job_isolation_policy ON batch_job
    FOR ALL 
    USING (org_id = current_setting('app.current_org_id')::uuid);

-- Batch Row: filtered through batch job's organization
CREATE POLICY batch_row_isolation_policy ON batch_row
    FOR ALL 
    USING (
        EXISTS (
            SELECT 1 FROM batch_job 
            WHERE batch_job.batch_id = batch_row.batch_id 
            AND batch_job.org_id = current_setting('app.current_org_id')::uuid
        )
    );

-- RCM State: filtered through portal's organization
CREATE POLICY rcm_state_isolation_policy ON rcm_state
    FOR ALL 
    USING (
        EXISTS (
            SELECT 1 FROM integration_endpoint 
            WHERE integration_endpoint.portal_id = rcm_state.portal_id 
            AND integration_endpoint.org_id = current_setting('app.current_org_id')::uuid
        )
    );

-- Macro State: filtered through portal's organization (if portal_id is set)
CREATE POLICY macro_state_isolation_policy ON macro_state
    FOR ALL 
    USING (
        portal_id IS NULL OR
        EXISTS (
            SELECT 1 FROM integration_endpoint 
            WHERE integration_endpoint.portal_id = macro_state.portal_id 
            AND integration_endpoint.org_id = current_setting('app.current_org_id')::uuid
        )
    );

-- RCM Trace: filtered by organization
CREATE POLICY trace_isolation_policy ON rcm_trace
    FOR ALL 
    USING (org_id = current_setting('app.current_org_id')::uuid);

-- RCM Transition: both states must be accessible to the organization
CREATE POLICY rcm_transition_isolation_policy ON rcm_transition
    FOR ALL 
    USING (
        EXISTS (
            SELECT 1 FROM rcm_state s 
            JOIN integration_endpoint ie ON s.portal_id = ie.portal_id
            WHERE s.state_id = from_state 
            AND ie.org_id = current_setting('app.current_org_id')::uuid
        )
        AND 
        EXISTS (
            SELECT 1 FROM rcm_state s 
            JOIN integration_endpoint ie ON s.portal_id = ie.portal_id
            WHERE s.state_id = to_state 
            AND ie.org_id = current_setting('app.current_org_id')::uuid
        )
    );

-- App User: filtered by organization
CREATE POLICY user_isolation_policy ON app_user
    FOR ALL 
    USING (org_id = current_setting('app.current_org_id')::uuid);

-- Create function to bypass RLS for system operations
CREATE OR REPLACE FUNCTION bypass_rls(query text) 
RETURNS SETOF record AS $$
BEGIN
    -- Only superuser can bypass RLS
    IF NOT EXISTS (
        SELECT 1 FROM pg_roles 
        WHERE rolname = current_user AND rolsuper = true
    ) THEN
        RAISE EXCEPTION 'Only superuser can bypass RLS';
    END IF;
    
    -- Execute query without RLS
    RETURN QUERY EXECUTE query;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Grant execute on bypass function only to migration role
REVOKE ALL ON FUNCTION bypass_rls(text) FROM PUBLIC;
-- GRANT EXECUTE ON FUNCTION bypass_rls(text) TO rcm_migration_role;