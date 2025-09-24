-- Migration: Add secret_arn column to integration_endpoint table
-- Purpose: Support secure credential storage in AWS Parameter Store/Secrets Manager
-- Date: 2025-01-30

-- Add secret_arn column to integration_endpoint table
ALTER TABLE integration_endpoint
ADD COLUMN IF NOT EXISTS secret_arn VARCHAR(255);

-- Add index for faster lookups by secret_arn
CREATE INDEX IF NOT EXISTS idx_integration_endpoint_secret_arn 
ON integration_endpoint(secret_arn);

-- Add comment to document the column
COMMENT ON COLUMN integration_endpoint.secret_arn IS 
'AWS Secrets Manager ARN or Parameter Store path for secure credential storage. Format: arn:aws:secretsmanager:region:account:secret:name or /rcm/credentials/portal_id';

-- Create credential audit log table
CREATE TABLE IF NOT EXISTS credential_access_log (
    id SERIAL PRIMARY KEY,
    access_timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    portal_id VARCHAR(255) NOT NULL,
    secret_arn VARCHAR(255),
    access_type VARCHAR(50) NOT NULL, -- 'retrieve', 'store', 'rotate', 'delete'
    access_by VARCHAR(255), -- User or service that accessed
    ip_address INET,
    user_agent TEXT,
    success BOOLEAN NOT NULL DEFAULT true,
    error_message TEXT,
    metadata JSONB -- Additional context
);

-- Add indexes for audit log queries
CREATE INDEX IF NOT EXISTS idx_credential_access_log_portal_id 
ON credential_access_log(portal_id);

CREATE INDEX IF NOT EXISTS idx_credential_access_log_timestamp 
ON credential_access_log(access_timestamp);

CREATE INDEX IF NOT EXISTS idx_credential_access_log_access_type 
ON credential_access_log(access_type);

-- Add comment to document the table
COMMENT ON TABLE credential_access_log IS 
'Audit log for credential access operations. Tracks all credential retrievals, updates, and rotations for compliance and security monitoring.';

-- Create credential rotation schedule table
CREATE TABLE IF NOT EXISTS credential_rotation_schedule (
    id SERIAL PRIMARY KEY,
    portal_id VARCHAR(255) NOT NULL UNIQUE,
    secret_arn VARCHAR(255),
    last_rotation TIMESTAMP WITH TIME ZONE,
    next_rotation TIMESTAMP WITH TIME ZONE,
    rotation_interval_days INTEGER DEFAULT 90,
    auto_rotate BOOLEAN DEFAULT false,
    notification_email VARCHAR(255),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Add foreign key constraint
ALTER TABLE credential_rotation_schedule
ADD CONSTRAINT fk_rotation_portal_id
FOREIGN KEY (portal_id) 
REFERENCES integration_endpoint(portal_id)
ON DELETE CASCADE;

-- Add comment to document the table
COMMENT ON TABLE credential_rotation_schedule IS 
'Manages credential rotation schedules for each portal. Supports automated rotation and notification policies.';

-- Create a view for easier credential management
CREATE OR REPLACE VIEW v_portal_credentials AS
SELECT 
    ie.portal_id,
    ie.portal_name,
    ie.portal_type,
    ie.base_url,
    ie.secret_arn,
    ie.is_active,
    crs.last_rotation,
    crs.next_rotation,
    crs.auto_rotate,
    CASE 
        WHEN crs.next_rotation < CURRENT_TIMESTAMP THEN 'overdue'
        WHEN crs.next_rotation < CURRENT_TIMESTAMP + INTERVAL '7 days' THEN 'due_soon'
        ELSE 'current'
    END AS rotation_status
FROM integration_endpoint ie
LEFT JOIN credential_rotation_schedule crs ON ie.portal_id = crs.portal_id
WHERE ie.is_active = true;

-- Add comment to document the view
COMMENT ON VIEW v_portal_credentials IS 
'Consolidated view of portal credentials with rotation status. Use for monitoring and management dashboards.';

-- Migration rollback script (save separately)
/*
-- Rollback: Remove secret_arn column and related objects
DROP VIEW IF EXISTS v_portal_credentials;
DROP TABLE IF EXISTS credential_rotation_schedule;
DROP TABLE IF EXISTS credential_access_log;
DROP INDEX IF EXISTS idx_integration_endpoint_secret_arn;
ALTER TABLE integration_endpoint DROP COLUMN IF EXISTS secret_arn;
*/