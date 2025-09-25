-- Database Triggers for RCM Schema

-- Create or replace the updated_at timestamp function
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Drop existing triggers if they exist (for idempotency)
DROP TRIGGER IF EXISTS update_batch_row_updated_at ON batch_row;
DROP TRIGGER IF EXISTS update_task_signature_updated_at ON task_signature;

-- Create trigger for batch_row table
CREATE TRIGGER update_batch_row_updated_at 
    BEFORE UPDATE ON batch_row 
    FOR EACH ROW 
    EXECUTE FUNCTION update_updated_at_column();

-- Create trigger for task_signature table
CREATE TRIGGER update_task_signature_updated_at 
    BEFORE UPDATE ON task_signature 
    FOR EACH ROW 
    EXECUTE FUNCTION update_updated_at_column();

-- Audit trigger for tracking data changes (optional but recommended)
CREATE OR REPLACE FUNCTION audit_trigger_function()
RETURNS TRIGGER AS $$
DECLARE
    audit_user_id text;
    audit_org_id text;
BEGIN
    -- Get user and org from session
    audit_user_id := current_setting('app.current_user_id', true);
    audit_org_id := current_setting('app.current_org_id', true);
    
    -- Log the change (would write to audit table if it exists)
    -- For now, just use RAISE NOTICE for debugging
    IF TG_OP = 'INSERT' THEN
        RAISE DEBUG 'INSERT on % by user % in org %', TG_TABLE_NAME, audit_user_id, audit_org_id;
    ELSIF TG_OP = 'UPDATE' THEN
        RAISE DEBUG 'UPDATE on % by user % in org %', TG_TABLE_NAME, audit_user_id, audit_org_id;
    ELSIF TG_OP = 'DELETE' THEN
        RAISE DEBUG 'DELETE on % by user % in org %', TG_TABLE_NAME, audit_user_id, audit_org_id;
    END IF;
    
    IF TG_OP = 'DELETE' THEN
        RETURN OLD;
    ELSE
        RETURN NEW;
    END IF;
END;
$$ LANGUAGE plpgsql;

-- Optional: Add audit triggers to critical tables
-- Uncomment these lines if you want audit logging
-- CREATE TRIGGER audit_organization AFTER INSERT OR UPDATE OR DELETE ON organization
--     FOR EACH ROW EXECUTE FUNCTION audit_trigger_function();
-- 
-- CREATE TRIGGER audit_integration_endpoint AFTER INSERT OR UPDATE OR DELETE ON integration_endpoint
--     FOR EACH ROW EXECUTE FUNCTION audit_trigger_function();
-- 
-- CREATE TRIGGER audit_task_signature AFTER INSERT OR UPDATE OR DELETE ON task_signature
--     FOR EACH ROW EXECUTE FUNCTION audit_trigger_function();