-- Complete RCM Schema with AWS SSM Integration
-- Version: 3.0
-- Description: Full schema including credential storage via AWS Systems Manager

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- ============================================================================
-- ENUM TYPES
-- ============================================================================

-- Task domains (healthcare business areas)
CREATE TYPE task_domain AS ENUM (
    'eligibility',
    'prior_auth',
    'claim',
    'payment',
    'patient',
    'provider',
    'billing',
    'reporting',
    'document'
);

-- Task actions (operations within domains)
CREATE TYPE task_action AS ENUM (
    -- Eligibility actions
    'check',
    'verify',
    'update',
    
    -- Prior auth actions
    'submit',
    'check_status',
    'appeal',
    'extend',
    
    -- Claim actions
    'submit_claim',
    'status_check',
    'resubmit',
    'void',
    'correct',
    
    -- Payment actions
    'post',
    'reconcile',
    'adjust',
    'refund',
    
    -- Patient actions
    'search',
    'register',
    'update_demographics',
    'verify_insurance',
    
    -- Provider actions
    'credential',
    'enroll',
    'update_info',
    
    -- Billing actions
    'generate_statement',
    'send_invoice',
    'apply_payment',
    
    -- Reporting actions
    'generate_report',
    'export_data',
    'analyze',
    
    -- Document actions
    'upload',
    'download',
    'parse',
    'validate',
    
    -- Legacy actions
    'check_legacy',
    'status_check_legacy'
);

-- Task signature sources
CREATE TYPE task_signature_source AS ENUM (
    'human',
    'ai_generated',
    'system_learned'
);

-- Job statuses
CREATE TYPE job_status AS ENUM (
    'pending',
    'processing', 
    'completed',
    'failed',
    'partially_completed'
);

-- User roles
CREATE TYPE user_role AS ENUM (
    'admin',
    'operator',
    'viewer',
    'api_user'
);

-- Requirement types
CREATE TYPE requirement_type AS ENUM (
    'required',
    'conditional',
    'optional',
    'output'
);

-- ============================================================================
-- TABLES
-- ============================================================================

-- Portal credentials with AWS SSM integration
CREATE TABLE portal_credential (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    portal_id VARCHAR(100) NOT NULL,
    account_id VARCHAR(200) NOT NULL,
    
    -- AWS SSM Integration
    -- Password stored in SSM Parameter Store
    password_ssm_parameter_name VARCHAR(512),  -- e.g., /rcm/prod/portal/anthem/user123/password
    password_ssm_key_id VARCHAR(256),          -- KMS key ID used for encryption
    
    -- Alternatively, store entire credential set in Secrets Manager
    secret_arn VARCHAR(512),                   -- Full ARN of AWS Secrets Manager secret
    secret_version_id VARCHAR(64),             -- Specific version of the secret
    
    -- Local encrypted storage (fallback/cache)
    encrypted_password BYTEA,                  -- Encrypted with pgcrypto if SSM unavailable
    encryption_key_id VARCHAR(256),            -- Reference to encryption key
    
    -- Session tokens
    session_token TEXT,
    token_expires_at TIMESTAMPTZ,
    
    -- OAuth tokens (if applicable)
    access_token_ssm_parameter_name VARCHAR(512),
    refresh_token_ssm_parameter_name VARCHAR(512),
    oauth_expires_at TIMESTAMPTZ,
    
    -- Metadata
    is_active BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_used_at TIMESTAMPTZ,
    expires_at TIMESTAMPTZ,
    
    -- Tracking
    created_by UUID,
    updated_by UUID,
    
    -- Constraints
    CONSTRAINT unique_portal_account UNIQUE (portal_id, account_id),
    CONSTRAINT check_storage_method CHECK (
        -- Must use either SSM Parameter Store, Secrets Manager, or local encryption
        (password_ssm_parameter_name IS NOT NULL) OR 
        (secret_arn IS NOT NULL) OR 
        (encrypted_password IS NOT NULL)
    )
);

-- User management
CREATE TABLE rcm_user (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255) NOT NULL UNIQUE,
    full_name VARCHAR(255) NOT NULL,
    role user_role NOT NULL DEFAULT 'operator',
    is_active BOOLEAN NOT NULL DEFAULT true,
    
    -- SSM integration for user API keys
    api_key_ssm_parameter_name VARCHAR(512),  -- Store API keys in SSM
    
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_login_at TIMESTAMPTZ
);

-- Task types (workflow templates)
CREATE TABLE task_type (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    domain task_domain NOT NULL,
    action task_action NOT NULL,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    is_active BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    version INTEGER NOT NULL DEFAULT 1,
    
    -- Constraints
    CONSTRAINT unique_domain_action UNIQUE (domain, action),
    CONSTRAINT unique_task_name UNIQUE (name)
);

-- Field requirements with hierarchical structure
CREATE TABLE field_requirement (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    task_type_id UUID NOT NULL REFERENCES task_type(id) ON DELETE CASCADE,
    parent_id UUID REFERENCES field_requirement(id) ON DELETE CASCADE,
    
    -- Field definition
    field_name VARCHAR(255) NOT NULL,
    field_type VARCHAR(50) NOT NULL,
    requirement_type requirement_type NOT NULL DEFAULT 'required',
    
    -- Hierarchical path (materialized for fast queries)
    path TEXT NOT NULL, -- e.g., "patient.insurance.primary"
    depth INTEGER NOT NULL DEFAULT 0,
    
    -- Business rules
    business_logic JSONB DEFAULT '{}',
    validation_rules JSONB DEFAULT '{}',
    
    -- Conditional logic
    condition_expr TEXT, -- e.g., "parent.field_name == 'Medicare'"
    required_when JSONB, -- Complex conditional rules
    
    -- UI hints
    ui_config JSONB DEFAULT '{}',
    
    -- Metadata
    portal_specific BOOLEAN NOT NULL DEFAULT false,
    source task_signature_source NOT NULL DEFAULT 'human',
    confidence_score DECIMAL(3,2),
    
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    -- Constraints
    CONSTRAINT unique_field_per_task_path UNIQUE (task_type_id, path),
    CONSTRAINT check_confidence_range CHECK (confidence_score >= 0 AND confidence_score <= 1)
);

-- Batch job management
CREATE TABLE batch_job (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES rcm_user(id),
    task_type_id UUID NOT NULL REFERENCES task_type(id),
    
    -- File storage (can reference S3 via SSM parameters)
    file_path VARCHAR(500) NOT NULL,
    file_s3_bucket_param VARCHAR(512),  -- SSM parameter containing S3 bucket name
    file_s3_key VARCHAR(1024),          -- S3 object key
    
    status job_status NOT NULL DEFAULT 'pending',
    total_items INTEGER NOT NULL DEFAULT 0,
    processed_items INTEGER NOT NULL DEFAULT 0,
    failed_items INTEGER NOT NULL DEFAULT 0,
    
    -- Processing metadata
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    error_summary JSONB,
    
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Batch job items
CREATE TABLE batch_job_item (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    batch_job_id UUID NOT NULL REFERENCES batch_job(id) ON DELETE CASCADE,
    item_index INTEGER NOT NULL,
    
    -- Item data
    input_data JSONB NOT NULL,
    output_data JSONB,
    
    -- Status tracking
    status job_status NOT NULL DEFAULT 'pending',
    error_message TEXT,
    attempts INTEGER NOT NULL DEFAULT 0,
    
    -- Timing
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    -- Constraints
    CONSTRAINT unique_item_index UNIQUE (batch_job_id, item_index)
);

-- Task signatures (workflow execution patterns)
CREATE TABLE task_signature (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    task_type_id UUID NOT NULL REFERENCES task_type(id),
    portal_id VARCHAR(100) NOT NULL,
    
    -- Signature data
    signature_hash VARCHAR(64) NOT NULL,
    signature_data JSONB NOT NULL,
    
    -- Classification
    source task_signature_source NOT NULL DEFAULT 'human',
    confidence_score DECIMAL(3,2) NOT NULL DEFAULT 1.0,
    
    -- Usage tracking
    use_count INTEGER NOT NULL DEFAULT 0,
    last_used_at TIMESTAMPTZ,
    success_rate DECIMAL(5,2),
    avg_duration_ms INTEGER,
    
    -- Metadata
    is_active BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_by UUID REFERENCES rcm_user(id),
    
    -- Constraints
    CONSTRAINT unique_signature_per_portal UNIQUE (task_type_id, portal_id, signature_hash),
    CONSTRAINT check_confidence_range CHECK (confidence_score >= 0 AND confidence_score <= 1),
    CONSTRAINT check_success_rate CHECK (success_rate >= 0 AND success_rate <= 100)
);

-- RCM trace/audit log
CREATE TABLE rcm_trace (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    batch_job_item_id UUID REFERENCES batch_job_item(id),
    portal_id VARCHAR(100) NOT NULL,
    
    -- Action tracking
    action_type VARCHAR(100) NOT NULL,
    action_detail JSONB,
    
    -- Results
    success BOOLEAN NOT NULL DEFAULT false,
    duration_ms INTEGER,
    error_detail JSONB,
    
    -- LLM interaction tracking (if applicable)
    llm_prompt TEXT,
    llm_response TEXT,
    llm_model VARCHAR(100),
    llm_tokens_used INTEGER,
    
    -- Metadata
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    user_id UUID REFERENCES rcm_user(id),
    session_id UUID
);

-- ============================================================================
-- INDEXES
-- ============================================================================

-- Portal credentials
CREATE INDEX idx_portal_cred_portal_account ON portal_credential(portal_id, account_id);
CREATE INDEX idx_portal_cred_active ON portal_credential(is_active) WHERE is_active = true;
CREATE INDEX idx_portal_cred_expires ON portal_credential(expires_at) WHERE expires_at IS NOT NULL;

-- Field requirements
CREATE INDEX idx_field_req_task_type ON field_requirement(task_type_id);
CREATE INDEX idx_field_req_parent ON field_requirement(parent_id) WHERE parent_id IS NOT NULL;
CREATE INDEX idx_field_req_path ON field_requirement(task_type_id, path);
CREATE INDEX idx_field_req_depth ON field_requirement(depth);

-- Batch jobs
CREATE INDEX idx_batch_job_user ON batch_job(user_id);
CREATE INDEX idx_batch_job_status ON batch_job(status);
CREATE INDEX idx_batch_job_created ON batch_job(created_at DESC);

-- Batch job items
CREATE INDEX idx_batch_item_job ON batch_job_item(batch_job_id);
CREATE INDEX idx_batch_item_status ON batch_job_item(batch_job_id, status);

-- Task signatures
CREATE INDEX idx_task_sig_type_portal ON task_signature(task_type_id, portal_id);
CREATE INDEX idx_task_sig_active ON task_signature(is_active) WHERE is_active = true;
CREATE INDEX idx_task_sig_usage ON task_signature(use_count DESC);

-- RCM trace
CREATE INDEX idx_trace_batch_item ON rcm_trace(batch_job_item_id);
CREATE INDEX idx_trace_portal ON rcm_trace(portal_id);
CREATE INDEX idx_trace_created ON rcm_trace(created_at DESC);
CREATE INDEX idx_trace_portal_created ON rcm_trace(portal_id, created_at DESC);

-- ============================================================================
-- FUNCTIONS AND TRIGGERS
-- ============================================================================

-- Update timestamp trigger function
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Apply update trigger to all tables with updated_at
CREATE TRIGGER update_portal_credential_updated_at BEFORE UPDATE ON portal_credential
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_rcm_user_updated_at BEFORE UPDATE ON rcm_user
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_task_type_updated_at BEFORE UPDATE ON task_type
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_field_requirement_updated_at BEFORE UPDATE ON field_requirement
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_batch_job_updated_at BEFORE UPDATE ON batch_job
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_batch_job_item_updated_at BEFORE UPDATE ON batch_job_item
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_task_signature_updated_at BEFORE UPDATE ON task_signature
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Function to maintain hierarchical path consistency
CREATE OR REPLACE FUNCTION maintain_field_path()
RETURNS TRIGGER AS $$
DECLARE
    parent_path TEXT;
    parent_depth INTEGER;
BEGIN
    IF NEW.parent_id IS NULL THEN
        NEW.path = NEW.field_name;
        NEW.depth = 0;
    ELSE
        SELECT path, depth INTO parent_path, parent_depth
        FROM field_requirement
        WHERE id = NEW.parent_id;
        
        NEW.path = parent_path || '.' || NEW.field_name;
        NEW.depth = parent_depth + 1;
    END IF;
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER maintain_field_requirement_path
    BEFORE INSERT OR UPDATE OF parent_id, field_name ON field_requirement
    FOR EACH ROW EXECUTE FUNCTION maintain_field_path();

-- ============================================================================
-- SECURITY POLICIES (Row Level Security)
-- ============================================================================

-- Enable RLS on sensitive tables
ALTER TABLE portal_credential ENABLE ROW LEVEL SECURITY;
ALTER TABLE rcm_user ENABLE ROW LEVEL SECURITY;

-- Portal credential policies
CREATE POLICY portal_cred_admin_all ON portal_credential
    FOR ALL TO rcm_admin
    USING (true);

CREATE POLICY portal_cred_user_view ON portal_credential
    FOR SELECT TO rcm_operator
    USING (true);

-- User policies
CREATE POLICY user_admin_all ON rcm_user
    FOR ALL TO rcm_admin
    USING (true);

CREATE POLICY user_self_view ON rcm_user
    FOR SELECT TO rcm_operator
    USING (email = current_user);

-- ============================================================================
-- HELPER VIEWS
-- ============================================================================

-- View for active portal credentials (hides sensitive data)
CREATE VIEW v_active_portal_credentials AS
SELECT 
    id,
    portal_id,
    account_id,
    CASE 
        WHEN password_ssm_parameter_name IS NOT NULL THEN 'SSM Parameter Store'
        WHEN secret_arn IS NOT NULL THEN 'AWS Secrets Manager'
        WHEN encrypted_password IS NOT NULL THEN 'Local Encrypted'
        ELSE 'Unknown'
    END as storage_method,
    is_active,
    created_at,
    updated_at,
    last_used_at,
    expires_at
FROM portal_credential
WHERE is_active = true;

-- View for task execution metrics
CREATE VIEW v_task_execution_metrics AS
SELECT 
    ts.task_type_id,
    tt.domain,
    tt.action,
    tt.name as task_name,
    ts.portal_id,
    COUNT(*) as signature_count,
    SUM(ts.use_count) as total_uses,
    AVG(ts.success_rate) as avg_success_rate,
    AVG(ts.avg_duration_ms) as avg_duration_ms
FROM task_signature ts
JOIN task_type tt ON ts.task_type_id = tt.id
WHERE ts.is_active = true
GROUP BY ts.task_type_id, tt.domain, tt.action, tt.name, ts.portal_id;

-- ============================================================================
-- SAMPLE DATA / COMMENTS
-- ============================================================================

COMMENT ON TABLE portal_credential IS 'Stores portal login credentials with AWS SSM integration for secure password/secret management';
COMMENT ON COLUMN portal_credential.password_ssm_parameter_name IS 'AWS SSM Parameter Store path for password, e.g., /rcm/prod/portal/anthem/user123/password';
COMMENT ON COLUMN portal_credential.secret_arn IS 'AWS Secrets Manager ARN for storing complete credential sets including username, password, and other secrets';
COMMENT ON COLUMN portal_credential.password_ssm_key_id IS 'KMS key ID used to encrypt the SSM parameter';

COMMENT ON TABLE task_type IS 'Defines available workflow templates combining domain and action';
COMMENT ON TABLE field_requirement IS 'Hierarchical field requirements for each task type with conditional logic';
COMMENT ON TABLE batch_job IS 'Tracks batch processing jobs with optional S3 integration via SSM parameters';
COMMENT ON TABLE task_signature IS 'Stores successful execution patterns for workflow automation';
COMMENT ON TABLE rcm_trace IS 'Comprehensive audit trail for all RCM operations';

-- ============================================================================
-- PERMISSIONS
-- ============================================================================

-- Create roles if they don't exist
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'rcm_admin') THEN
        CREATE ROLE rcm_admin;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'rcm_operator') THEN
        CREATE ROLE rcm_operator;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'rcm_viewer') THEN
        CREATE ROLE rcm_viewer;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'rcm_api') THEN
        CREATE ROLE rcm_api;
    END IF;
END
$$;

-- Grant permissions
GRANT ALL ON ALL TABLES IN SCHEMA public TO rcm_admin;
GRANT ALL ON ALL SEQUENCES IN SCHEMA public TO rcm_admin;

GRANT SELECT, INSERT, UPDATE ON ALL TABLES IN SCHEMA public TO rcm_operator;
GRANT USAGE ON ALL SEQUENCES IN SCHEMA public TO rcm_operator;

GRANT SELECT ON ALL TABLES IN SCHEMA public TO rcm_viewer;

GRANT SELECT, INSERT, UPDATE ON batch_job, batch_job_item, rcm_trace TO rcm_api;
GRANT SELECT ON task_type, field_requirement, task_signature TO rcm_api;
GRANT USAGE ON ALL SEQUENCES IN SCHEMA public TO rcm_api;