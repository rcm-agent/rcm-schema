-- Initialize Workflow Execution Tables for RCM Schema
-- This script creates the workflow execution tables needed for the workflow automation

BEGIN;

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- Create basic organization table if it doesn't exist
CREATE TABLE IF NOT EXISTS organization (
    org_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create basic user table if it doesn't exist  
CREATE TABLE IF NOT EXISTS app_user (
    user_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255) NOT NULL,
    org_id UUID REFERENCES organization(org_id),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create user_workflow table if it doesn't exist
CREATE TABLE IF NOT EXISTS user_workflow (
    workflow_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id UUID REFERENCES organization(org_id),
    name VARCHAR(255) NOT NULL,
    description TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE
);

-- Create user_workflow_node table (UUID-based)
CREATE TABLE IF NOT EXISTS user_workflow_node (
    node_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workflow_id UUID NOT NULL REFERENCES user_workflow(workflow_id) ON DELETE CASCADE,
    label TEXT NOT NULL,
    description TEXT,
    metadata JSONB DEFAULT '{}'::jsonb,
    label_conf NUMERIC(3, 2),
    last_label_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create user_workflow_transition table
CREATE TABLE IF NOT EXISTS user_workflow_transition (
    workflow_id UUID NOT NULL REFERENCES user_workflow(workflow_id) ON DELETE CASCADE,
    from_node UUID NOT NULL REFERENCES user_workflow_node(node_id) ON DELETE CASCADE,
    to_node UUID NOT NULL REFERENCES user_workflow_node(node_id) ON DELETE CASCADE,
    action_label TEXT NOT NULL,
    freq INTEGER NOT NULL DEFAULT 1,
    PRIMARY KEY (workflow_id, from_node, to_node, action_label)
);

-- Create workflow execution tracking tables

-- Enum types for workflow execution
DO $$ BEGIN
    CREATE TYPE workflow_channel AS ENUM ('web', 'voice', 'efax');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

DO $$ BEGIN
    CREATE TYPE trace_status AS ENUM ('pending', 'active', 'completed', 'failed', 'cancelled', 'timeout');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

DO $$ BEGIN
    CREATE TYPE step_status AS ENUM ('pending', 'running', 'completed', 'failed', 'skipped');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

DO $$ BEGIN
    CREATE TYPE workflow_io_direction AS ENUM ('input', 'output');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

-- Create workflow_trace table
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
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    created_by UUID NOT NULL REFERENCES app_user(user_id) ON DELETE RESTRICT
);

-- Create workflow_steps table (with UUID node_id)
CREATE TABLE IF NOT EXISTS workflow_steps (
    step_id BIGSERIAL PRIMARY KEY,
    trace_id BIGINT NOT NULL REFERENCES workflow_trace(trace_id) ON DELETE CASCADE,
    node_id UUID NOT NULL REFERENCES user_workflow_node(node_id) ON DELETE RESTRICT,
    step_number INTEGER NOT NULL,
    status step_status NOT NULL DEFAULT 'pending',
    input_data JSONB,
    output_data JSONB,
    error_message TEXT,
    start_time TIMESTAMP WITH TIME ZONE,
    end_time TIMESTAMP WITH TIME ZONE,
    duration_ms INTEGER,
    retry_count INTEGER DEFAULT 0,
    metadata JSONB,
    UNIQUE(trace_id, step_number)
);

-- Create node_io_requirements table (with UUID node_id)
CREATE TABLE IF NOT EXISTS node_io_requirements (
    node_io_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    node_id UUID NOT NULL REFERENCES user_workflow_node(node_id) ON DELETE CASCADE,
    io_name VARCHAR(255) NOT NULL,
    io_direction workflow_io_direction NOT NULL,
    data_type VARCHAR(50) NOT NULL,
    is_required BOOLEAN DEFAULT TRUE,
    default_value JSONB,
    validation_rules JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(node_id, io_name, io_direction)
);

-- Create workflow_data_bindings table (with UUID node_id)
CREATE TABLE IF NOT EXISTS workflow_data_bindings (
    binding_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workflow_id UUID NOT NULL REFERENCES user_workflow(workflow_id) ON DELETE CASCADE,
    node_id UUID NOT NULL REFERENCES user_workflow_node(node_id) ON DELETE CASCADE,
    io_name VARCHAR(255) NOT NULL,
    binding_type VARCHAR(50) NOT NULL,
    binding_config JSONB NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE,
    UNIQUE(workflow_id, node_id, io_name)
);

-- Create workflow_trace_screenshot table (with UUID node_id)
CREATE TABLE IF NOT EXISTS workflow_trace_screenshot (
    screenshot_id BIGSERIAL PRIMARY KEY,
    trace_id BIGINT NOT NULL REFERENCES workflow_trace(trace_id) ON DELETE CASCADE,
    step_id BIGINT REFERENCES workflow_steps(step_id) ON DELETE CASCADE,
    node_id UUID NOT NULL,  -- No foreign key as nodes might be deleted
    node_name VARCHAR(255),
    screenshot_path TEXT NOT NULL,
    screenshot_s3_key TEXT,
    screenshot_url TEXT,
    metadata JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create workflow_trace_context table
CREATE TABLE IF NOT EXISTS workflow_trace_context (
    context_id BIGSERIAL PRIMARY KEY,
    trace_id BIGINT NOT NULL REFERENCES workflow_trace(trace_id) ON DELETE CASCADE,
    key VARCHAR(255) NOT NULL,
    value JSONB NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE,
    UNIQUE(trace_id, key)
);

-- Create workflow_events table
CREATE TABLE IF NOT EXISTS workflow_events (
    event_id BIGSERIAL PRIMARY KEY,
    trace_id BIGINT NOT NULL REFERENCES workflow_trace(trace_id) ON DELETE CASCADE,
    step_id BIGINT REFERENCES workflow_steps(step_id) ON DELETE CASCADE,
    event_type VARCHAR(100) NOT NULL,
    event_data JSONB NOT NULL,
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create indexes for performance
CREATE INDEX IF NOT EXISTS idx_workflow_trace_workflow ON workflow_trace(workflow_id);
CREATE INDEX IF NOT EXISTS idx_workflow_trace_status ON workflow_trace(status);
CREATE INDEX IF NOT EXISTS idx_workflow_trace_created_at ON workflow_trace(created_at);

CREATE INDEX IF NOT EXISTS idx_workflow_steps_trace ON workflow_steps(trace_id);
CREATE INDEX IF NOT EXISTS idx_workflow_steps_node ON workflow_steps(node_id);
CREATE INDEX IF NOT EXISTS idx_workflow_steps_status ON workflow_steps(status);

CREATE INDEX IF NOT EXISTS idx_node_io_requirements_node ON node_io_requirements(node_id);
CREATE INDEX IF NOT EXISTS idx_workflow_data_bindings_workflow ON workflow_data_bindings(workflow_id);
CREATE INDEX IF NOT EXISTS idx_workflow_data_bindings_node ON workflow_data_bindings(node_id);

CREATE INDEX IF NOT EXISTS idx_workflow_trace_screenshot_trace ON workflow_trace_screenshot(trace_id);
CREATE INDEX IF NOT EXISTS idx_workflow_trace_screenshot_node ON workflow_trace_screenshot(node_id);

CREATE INDEX IF NOT EXISTS idx_workflow_events_trace ON workflow_events(trace_id);
CREATE INDEX IF NOT EXISTS idx_workflow_events_timestamp ON workflow_events(timestamp);

-- Insert sample data for testing
INSERT INTO organization (org_id, name) 
VALUES ('00000000-0000-0000-0000-000000000001', 'Test Organization')
ON CONFLICT DO NOTHING;

INSERT INTO app_user (user_id, email, org_id)
VALUES ('00000000-0000-0000-0000-000000000001', 'test@example.com', '00000000-0000-0000-0000-000000000001')
ON CONFLICT DO NOTHING;

COMMIT;

-- Verify tables were created
SELECT 
    'Tables created:' as status,
    COUNT(*) as count
FROM information_schema.tables 
WHERE table_schema = 'public'
AND table_name IN (
    'user_workflow',
    'user_workflow_node', 
    'user_workflow_transition',
    'workflow_trace',
    'workflow_steps',
    'node_io_requirements',
    'workflow_data_bindings',
    'workflow_trace_screenshot',
    'workflow_trace_context',
    'workflow_events'
);