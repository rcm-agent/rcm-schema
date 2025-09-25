-- Migration: Add user_organization table for many-to-many relationship
-- Date: 2025-08-02
-- Description: Converts direct user-org relationship to many-to-many

BEGIN;

-- Create user_organization association table
CREATE TABLE IF NOT EXISTS user_organization (
    user_id UUID NOT NULL REFERENCES app_user(user_id) ON DELETE CASCADE,
    org_id UUID NOT NULL REFERENCES organization(org_id) ON DELETE CASCADE,
    is_active BOOLEAN NOT NULL DEFAULT true,
    is_primary BOOLEAN NOT NULL DEFAULT false,
    joined_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ,
    PRIMARY KEY (user_id, org_id)
);

-- Create indexes for performance
CREATE INDEX idx_user_organization_user_id ON user_organization(user_id);
CREATE INDEX idx_user_organization_org_id ON user_organization(org_id);
CREATE INDEX idx_user_organization_active ON user_organization(is_active);

-- Ensure only one primary organization per user
CREATE UNIQUE INDEX uq_one_primary_org_per_user 
ON user_organization(user_id, is_primary) 
WHERE is_primary = true;

-- Check if org_id exists in app_user before migration
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 
        FROM information_schema.columns 
        WHERE table_name = 'app_user' 
        AND column_name = 'org_id'
    ) THEN
        -- Migrate existing user-org relationships
        INSERT INTO user_organization (user_id, org_id, is_active, is_primary, joined_at)
        SELECT user_id, org_id, true, true, created_at
        FROM app_user
        WHERE org_id IS NOT NULL
        ON CONFLICT (user_id, org_id) DO NOTHING;
        
        -- Drop foreign key constraint if it exists
        ALTER TABLE app_user DROP CONSTRAINT IF EXISTS app_user_org_id_fkey;
        
        -- Drop org_id column
        ALTER TABLE app_user DROP COLUMN IF EXISTS org_id;
    END IF;
END $$;

-- Add comment to table
COMMENT ON TABLE user_organization IS 'Association table for many-to-many relationship between users and organizations';
COMMENT ON COLUMN user_organization.is_active IS 'Whether the user is currently active in this organization';
COMMENT ON COLUMN user_organization.is_primary IS 'Whether this is the user''s primary organization';
COMMENT ON COLUMN user_organization.joined_at IS 'When the user joined this organization';

COMMIT;

-- Rollback script (save separately)
-- BEGIN;
-- ALTER TABLE app_user ADD COLUMN org_id UUID;
-- UPDATE app_user au
-- SET org_id = uo.org_id
-- FROM user_organization uo
-- WHERE au.user_id = uo.user_id AND uo.is_primary = true;
-- ALTER TABLE app_user ADD CONSTRAINT app_user_org_id_fkey 
--   FOREIGN KEY (org_id) REFERENCES organization(org_id) ON DELETE CASCADE;
-- DROP TABLE user_organization;
-- COMMIT;