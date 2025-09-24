-- =====================================================
-- Add Workflow Execution Tables for Web Agent
-- =====================================================

-- Create enums (if they don't exist)
DO $$ BEGIN
    CREATE TYPE workflow_channel AS ENUM ('web', 'voice', 'efax');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

DO $$ BEGIN
    CREATE TYPE config_type AS ENUM ('workflow', 'channel', 'global');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

DO $$ BEGIN
    CREATE TYPE workflow_io_direction AS ENUM ('input', 'output');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

DO $$ BEGIN
    CREATE TYPE step_status AS ENUM ('pending', 'running', 'completed', 'failed', 'skipped');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

DO $$ BEGIN
    CREATE TYPE trace_status AS ENUM ('pending', 'active', 'completed', 'failed', 'cancelled', 'timeout');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

-- 1. Create workflow_configs table
CREATE TABLE IF NOT EXISTS workflow_configs (
    config_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id UUID NOT NULL REFERENCES organization(org_id) ON DELETE CASCADE,
    workflow_id UUID REFERENCES user_workflow(workflow_id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    config_type config_type NOT NULL,
    config_data JSONB NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE,
    created_by UUID NOT NULL REFERENCES app_user(user_id) ON DELETE RESTRICT,
    
    CONSTRAINT uq_workflow_config_unique UNIQUE(org_id, workflow_id, name, config_type)
);

-- 2. Create channel_configs table
CREATE TABLE IF NOT EXISTS channel_configs (
    channel_config_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id UUID NOT NULL REFERENCES organization(org_id) ON DELETE CASCADE,
    channel workflow_channel NOT NULL,
    name VARCHAR(255) NOT NULL,
    config_data JSONB NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE,
    created_by UUID NOT NULL REFERENCES app_user(user_id) ON DELETE RESTRICT,
    
    CONSTRAINT uq_channel_config_unique UNIQUE(org_id, channel, name)
);

-- 3. Create workflow_channel_configs table
CREATE TABLE IF NOT EXISTS workflow_channel_configs (
    workflow_channel_config_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workflow_id UUID NOT NULL REFERENCES user_workflow(workflow_id) ON DELETE CASCADE,
    channel workflow_channel NOT NULL,
    channel_config_id UUID REFERENCES channel_configs(channel_config_id) ON DELETE SET NULL,
    webhook_url TEXT,
    is_enabled BOOLEAN NOT NULL DEFAULT true,
    priority INTEGER NOT NULL DEFAULT 1,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE,
    
    CONSTRAINT uq_workflow_channel_unique UNIQUE(workflow_id, channel)
);

-- 4. Create node_io_requirements table
CREATE TABLE IF NOT EXISTS node_io_requirements (
    node_io_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    node_id BIGINT NOT NULL REFERENCES workflow_node(node_id) ON DELETE CASCADE,
    io_name VARCHAR(255) NOT NULL,
    io_direction workflow_io_direction NOT NULL,
    data_type VARCHAR(50) NOT NULL,
    is_required BOOLEAN NOT NULL DEFAULT true,
    default_value JSONB,
    validation_rules JSONB,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    
    CONSTRAINT uq_node_io_unique UNIQUE(node_id, io_name, io_direction)
);

-- 5. Create workflow_trace table
CREATE TABLE IF NOT EXISTS workflow_trace (
    trace_id BIGSERIAL PRIMARY KEY,
    workflow_id UUID NOT NULL REFERENCES user_workflow(workflow_id) ON DELETE RESTRICT,
    channel workflow_channel NOT NULL,
    external_id VARCHAR(255),
    status trace_status NOT NULL DEFAULT 'pending',
    config_snapshot JSONB,
    start_time TIMESTAMP WITH TIME ZONE,
    end_time TIMESTAMP WITH TIME ZONE,
    duration_ms INTEGER,
    error_message TEXT,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    created_by UUID NOT NULL REFERENCES app_user(user_id) ON DELETE RESTRICT
);

-- 6. Create workflow_steps table
CREATE TABLE IF NOT EXISTS workflow_steps (
    step_id BIGSERIAL PRIMARY KEY,
    trace_id BIGINT NOT NULL REFERENCES workflow_trace(trace_id) ON DELETE CASCADE,
    node_id BIGINT NOT NULL REFERENCES workflow_node(node_id) ON DELETE RESTRICT,
    step_number INTEGER NOT NULL,
    status step_status NOT NULL DEFAULT 'pending',
    input_data JSONB,
    output_data JSONB,
    error_message TEXT,
    start_time TIMESTAMP WITH TIME ZONE,
    end_time TIMESTAMP WITH TIME ZONE,
    duration_ms INTEGER,
    retry_count INTEGER NOT NULL DEFAULT 0,
    metadata JSONB,
    
    CONSTRAINT uq_workflow_step_number UNIQUE(trace_id, step_number)
);

-- 7. Create workflow_trace_context table
CREATE TABLE IF NOT EXISTS workflow_trace_context (
    context_id BIGSERIAL PRIMARY KEY,
    trace_id BIGINT NOT NULL REFERENCES workflow_trace(trace_id) ON DELETE CASCADE,
    key VARCHAR(255) NOT NULL,
    value JSONB NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE,
    
    CONSTRAINT uq_trace_context_key UNIQUE(trace_id, key)
);

-- 8. Create workflow_events table
CREATE TABLE IF NOT EXISTS workflow_events (
    event_id BIGSERIAL PRIMARY KEY,
    trace_id BIGINT NOT NULL REFERENCES workflow_trace(trace_id) ON DELETE CASCADE,
    step_id BIGINT REFERENCES workflow_steps(step_id) ON DELETE CASCADE,
    event_type VARCHAR(100) NOT NULL,
    event_data JSONB NOT NULL,
    timestamp TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

-- 9. Create workflow_data_bindings table
CREATE TABLE IF NOT EXISTS workflow_data_bindings (
    binding_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workflow_id UUID NOT NULL REFERENCES user_workflow(workflow_id) ON DELETE CASCADE,
    node_id BIGINT NOT NULL REFERENCES workflow_node(node_id) ON DELETE CASCADE,
    io_name VARCHAR(255) NOT NULL,
    binding_type VARCHAR(50) NOT NULL,
    binding_config JSONB NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE,
    
    CONSTRAINT uq_workflow_data_binding UNIQUE(workflow_id, node_id, io_name)
);

-- 10. Create config_status table (for tracking active configs)
CREATE TABLE IF NOT EXISTS config_status (
    status_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id UUID NOT NULL REFERENCES organization(org_id) ON DELETE CASCADE,
    config_type config_type NOT NULL,
    entity_id UUID,
    active_config_id UUID,
    activated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    activated_by UUID NOT NULL REFERENCES app_user(user_id) ON DELETE RESTRICT,
    
    CONSTRAINT uq_config_status_unique UNIQUE(org_id, config_type, entity_id)
);

-- Create indexes for performance
CREATE INDEX IF NOT EXISTS idx_workflow_configs_org_id ON workflow_configs(org_id);
CREATE INDEX IF NOT EXISTS idx_workflow_configs_workflow_id ON workflow_configs(workflow_id);
CREATE INDEX IF NOT EXISTS idx_workflow_configs_type ON workflow_configs(config_type);
CREATE INDEX IF NOT EXISTS idx_workflow_configs_active ON workflow_configs(is_active);

CREATE INDEX IF NOT EXISTS idx_channel_configs_org_id ON channel_configs(org_id);
CREATE INDEX IF NOT EXISTS idx_channel_configs_channel ON channel_configs(channel);
CREATE INDEX IF NOT EXISTS idx_channel_configs_active ON channel_configs(is_active);

CREATE INDEX IF NOT EXISTS idx_workflow_channel_configs_workflow ON workflow_channel_configs(workflow_id);
CREATE INDEX IF NOT EXISTS idx_workflow_channel_configs_channel ON workflow_channel_configs(channel);
CREATE INDEX IF NOT EXISTS idx_workflow_channel_configs_enabled ON workflow_channel_configs(is_enabled);

CREATE INDEX IF NOT EXISTS idx_node_io_requirements_node ON node_io_requirements(node_id);
CREATE INDEX IF NOT EXISTS idx_node_io_requirements_direction ON node_io_requirements(io_direction);

CREATE INDEX IF NOT EXISTS idx_workflow_trace_workflow ON workflow_trace(workflow_id);
CREATE INDEX IF NOT EXISTS idx_workflow_trace_channel ON workflow_trace(channel);
CREATE INDEX IF NOT EXISTS idx_workflow_trace_status ON workflow_trace(status);
CREATE INDEX IF NOT EXISTS idx_workflow_trace_created_at ON workflow_trace(created_at);
CREATE INDEX IF NOT EXISTS idx_workflow_trace_external_id ON workflow_trace(external_id);

CREATE INDEX IF NOT EXISTS idx_workflow_steps_trace ON workflow_steps(trace_id);
CREATE INDEX IF NOT EXISTS idx_workflow_steps_node ON workflow_steps(node_id);
CREATE INDEX IF NOT EXISTS idx_workflow_steps_status ON workflow_steps(status);

CREATE INDEX IF NOT EXISTS idx_workflow_trace_context_trace ON workflow_trace_context(trace_id);
CREATE INDEX IF NOT EXISTS idx_workflow_trace_context_key ON workflow_trace_context(key);

CREATE INDEX IF NOT EXISTS idx_workflow_events_trace ON workflow_events(trace_id);
CREATE INDEX IF NOT EXISTS idx_workflow_events_step ON workflow_events(step_id);
CREATE INDEX IF NOT EXISTS idx_workflow_events_type ON workflow_events(event_type);
CREATE INDEX IF NOT EXISTS idx_workflow_events_timestamp ON workflow_events(timestamp);

CREATE INDEX IF NOT EXISTS idx_workflow_data_bindings_workflow ON workflow_data_bindings(workflow_id);
CREATE INDEX IF NOT EXISTS idx_workflow_data_bindings_node ON workflow_data_bindings(node_id);

CREATE INDEX IF NOT EXISTS idx_config_status_org ON config_status(org_id);
CREATE INDEX IF NOT EXISTS idx_config_status_type ON config_status(config_type);
CREATE INDEX IF NOT EXISTS idx_config_status_entity ON config_status(entity_id);

-- Create composite indexes for common queries
CREATE INDEX IF NOT EXISTS idx_workflow_trace_workflow_status ON workflow_trace(workflow_id, status);
CREATE INDEX IF NOT EXISTS idx_workflow_steps_trace_status ON workflow_steps(trace_id, status);
CREATE INDEX IF NOT EXISTS idx_workflow_configs_org_type_active ON workflow_configs(org_id, config_type, is_active);

-- Enable Row Level Security on sensitive tables
ALTER TABLE workflow_configs ENABLE ROW LEVEL SECURITY;
ALTER TABLE channel_configs ENABLE ROW LEVEL SECURITY;
ALTER TABLE workflow_trace ENABLE ROW LEVEL SECURITY;
ALTER TABLE workflow_trace_context ENABLE ROW LEVEL SECURITY;

-- Create RLS policies (if they don't exist)
DO $$ BEGIN
    CREATE POLICY workflow_configs_org_isolation ON workflow_configs
        FOR ALL
        USING (org_id = current_setting('app.current_org_id')::uuid);
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

DO $$ BEGIN
    CREATE POLICY channel_configs_org_isolation ON channel_configs
        FOR ALL
        USING (org_id = current_setting('app.current_org_id')::uuid);
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

DO $$ BEGIN
    CREATE POLICY workflow_trace_org_isolation ON workflow_trace
        FOR ALL
        USING (workflow_id IN (
            SELECT workflow_id FROM user_workflow 
            WHERE org_id = current_setting('app.current_org_id')::uuid
        ));
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

DO $$ BEGIN
    CREATE POLICY workflow_trace_context_org_isolation ON workflow_trace_context
        FOR ALL
        USING (trace_id IN (
            SELECT t.trace_id FROM workflow_trace t
            JOIN user_workflow w ON t.workflow_id = w.workflow_id
            WHERE w.org_id = current_setting('app.current_org_id')::uuid
        ));
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

-- Create a function to validate node IO requirements
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

-- Create trigger to validate node IO requirements
CREATE OR REPLACE FUNCTION trigger_validate_node_io()
RETURNS TRIGGER AS $$
BEGIN
    PERFORM validate_node_io_requirements(NEW.node_id);
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DO $$ BEGIN
    CREATE TRIGGER validate_node_io_before_insert
        BEFORE INSERT OR UPDATE ON node_io_requirements
        FOR EACH ROW
        EXECUTE FUNCTION trigger_validate_node_io();
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

-- Update alembic version table to mark migration as complete
INSERT INTO alembic_version (version_num) 
VALUES ('014_add_workflow_execution_tables')
ON CONFLICT (version_num) DO NOTHING;

-- Success message
DO $$ BEGIN
    RAISE NOTICE 'Workflow execution tables created successfully!';
END $$;