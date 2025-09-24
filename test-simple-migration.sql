-- Test simple migration without vector dependencies
-- This will help us understand what we can migrate

-- Check current tables
SELECT table_name 
FROM information_schema.tables 
WHERE table_schema = 'public' 
ORDER BY table_name;

-- Create organization table if it doesn't exist
CREATE TABLE IF NOT EXISTS organization (
    org_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_type TEXT NOT NULL CHECK (org_type IN ('hospital','billing_firm','credentialer')),
    name TEXT NOT NULL UNIQUE,
    email_domain TEXT UNIQUE,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now()
);

-- Create app_user table if it doesn't exist
CREATE TABLE IF NOT EXISTS app_user (
    user_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id UUID REFERENCES organization(org_id),
    email TEXT NOT NULL UNIQUE,
    full_name TEXT,
    role TEXT NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT true,
    api_key_ssm_parameter_name VARCHAR(512),
    last_login_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now()
);

-- Add columns to user_workflow table if they don't exist
DO $$ 
BEGIN
    -- Add status column if it doesn't exist
    IF NOT EXISTS (SELECT column_name 
                   FROM information_schema.columns 
                   WHERE table_name='user_workflow' 
                   AND column_name='status') THEN
        ALTER TABLE user_workflow ADD COLUMN status VARCHAR(50) DEFAULT 'active';
    END IF;
    
    -- Add org_id column if it doesn't exist
    IF NOT EXISTS (SELECT column_name 
                   FROM information_schema.columns 
                   WHERE table_name='user_workflow' 
                   AND column_name='org_id') THEN
        -- First add the column without constraint
        ALTER TABLE user_workflow ADD COLUMN org_id UUID;
        
        -- Insert a default organization if none exists
        INSERT INTO organization (org_id, org_type, name, email_domain)
        VALUES ('00000000-0000-0000-0000-000000000000', 'hospital', 'Default Organization', 'default.com')
        ON CONFLICT (name) DO NOTHING;
        
        -- Update existing workflows to use default org
        UPDATE user_workflow SET org_id = '00000000-0000-0000-0000-000000000000'
        WHERE org_id IS NULL;
        
        -- Now add the constraint
        ALTER TABLE user_workflow ALTER COLUMN org_id SET NOT NULL;
        ALTER TABLE user_workflow ADD CONSTRAINT fk_user_workflow_org 
            FOREIGN KEY (org_id) REFERENCES organization(org_id);
    END IF;
END $$;

-- Create or update workflow_trace table
CREATE TABLE IF NOT EXISTS workflow_trace (
    trace_id BIGSERIAL PRIMARY KEY,
    batch_job_item_id UUID,
    org_id UUID NOT NULL REFERENCES organization(org_id),
    workflow_id UUID REFERENCES user_workflow(workflow_id),
    action_type TEXT,
    action_detail JSONB,
    success BOOLEAN DEFAULT false,
    duration_ms INTEGER,
    error_detail JSONB,
    llm_prompt TEXT,
    llm_response TEXT,
    llm_model VARCHAR(100),
    llm_tokens_used INTEGER,
    -- V9 Enhancement fields
    status VARCHAR(50) NOT NULL DEFAULT 'pending',
    started_by UUID,
    completed_at TIMESTAMP WITH TIME ZONE,
    node_count INTEGER DEFAULT 0,
    completed_node_count INTEGER DEFAULT 0,
    execution_time_ms BIGINT,
    error_message TEXT,
    run_metadata JSONB DEFAULT '{}',
    tier SMALLINT,
    tier_reason TEXT,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
    user_id UUID,
    session_id UUID,
    CONSTRAINT workflow_trace_status_check CHECK (status IN ('pending', 'running', 'completed', 'failed', 'cancelled', 'timeout'))
);

-- Create workflow_trace_screenshot table
CREATE TABLE IF NOT EXISTS workflow_trace_screenshot (
    screenshot_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    trace_id BIGINT NOT NULL REFERENCES workflow_trace(trace_id) ON DELETE CASCADE,
    org_id UUID NOT NULL REFERENCES organization(org_id) ON DELETE CASCADE,
    node_id INTEGER NOT NULL,
    node_name VARCHAR(255) NOT NULL,
    step_index INTEGER NOT NULL,
    screenshot_url TEXT NOT NULL,
    thumbnail_url TEXT,
    action_description TEXT NOT NULL,
    element_selector TEXT,
    screenshot_metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now()
);

-- Create indexes
CREATE INDEX IF NOT EXISTS idx_workflow_trace_started_by ON workflow_trace(started_by);
CREATE INDEX IF NOT EXISTS idx_workflow_trace_status_org ON workflow_trace(org_id, status);
CREATE INDEX IF NOT EXISTS idx_trace_screenshots ON workflow_trace_screenshot(trace_id, step_index);
CREATE INDEX IF NOT EXISTS idx_screenshot_org ON workflow_trace_screenshot(org_id);
CREATE INDEX IF NOT EXISTS idx_screenshot_created ON workflow_trace_screenshot(created_at);

-- Show results
SELECT 'Migration completed successfully' as status;