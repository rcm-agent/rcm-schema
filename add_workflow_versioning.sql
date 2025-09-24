-- ============================================================================
-- Add Workflow Versioning Support
-- ============================================================================
-- Description: Adds optimistic locking and versioning support for workflow autosave
-- Author: Claude
-- Date: 2025-01-09
-- ============================================================================

-- Start transaction
BEGIN;

-- ============================================================================
-- Step 1: Add version column to user_workflow table
-- ============================================================================
DO $$ 
BEGIN
    IF NOT EXISTS (
        SELECT 1 
        FROM information_schema.columns 
        WHERE table_name = 'user_workflow' 
        AND column_name = 'version'
    ) THEN
        ALTER TABLE user_workflow 
        ADD COLUMN version INTEGER NOT NULL DEFAULT 1;
        
        COMMENT ON COLUMN user_workflow.version IS 
        'Version number for optimistic locking to prevent concurrent edit conflicts';
        
        RAISE NOTICE 'Added version column to user_workflow table';
    ELSE
        RAISE NOTICE 'Version column already exists in user_workflow table';
    END IF;
END $$;

-- ============================================================================
-- Step 2: Add draft_updated_at column for tracking draft saves
-- ============================================================================
DO $$ 
BEGIN
    IF NOT EXISTS (
        SELECT 1 
        FROM information_schema.columns 
        WHERE table_name = 'user_workflow' 
        AND column_name = 'draft_updated_at'
    ) THEN
        ALTER TABLE user_workflow 
        ADD COLUMN draft_updated_at TIMESTAMPTZ;
        
        COMMENT ON COLUMN user_workflow.draft_updated_at IS 
        'Timestamp of last draft save for autosave tracking';
        
        RAISE NOTICE 'Added draft_updated_at column to user_workflow table';
    ELSE
        RAISE NOTICE 'draft_updated_at column already exists in user_workflow table';
    END IF;
END $$;

-- ============================================================================
-- Step 3: Add draft_state column for storing autosave drafts
-- ============================================================================
DO $$ 
BEGIN
    IF NOT EXISTS (
        SELECT 1 
        FROM information_schema.columns 
        WHERE table_name = 'user_workflow' 
        AND column_name = 'draft_state'
    ) THEN
        ALTER TABLE user_workflow 
        ADD COLUMN draft_state JSONB;
        
        COMMENT ON COLUMN user_workflow.draft_state IS 
        'Draft state for autosave functionality, cleared when workflow is published';
        
        RAISE NOTICE 'Added draft_state column to user_workflow table';
    ELSE
        RAISE NOTICE 'draft_state column already exists in user_workflow table';
    END IF;
END $$;

-- ============================================================================
-- Step 4: Create function for updating workflow with version check
-- ============================================================================
CREATE OR REPLACE FUNCTION update_workflow_with_version_check(
    p_workflow_id UUID,
    p_org_id UUID,
    p_workflow_state JSONB,
    p_current_version INTEGER
)
RETURNS TABLE(success BOOLEAN, new_version INTEGER, conflict BOOLEAN)
LANGUAGE plpgsql
AS $$
DECLARE
    v_actual_version INTEGER;
    v_new_version INTEGER;
BEGIN
    -- Get current version with row lock
    SELECT version INTO v_actual_version
    FROM user_workflow
    WHERE workflow_id = p_workflow_id 
    AND org_id = p_org_id
    FOR UPDATE;
    
    -- Check if workflow exists
    IF NOT FOUND THEN
        RETURN QUERY SELECT FALSE, 0, FALSE;
        RETURN;
    END IF;
    
    -- Check for version conflict
    IF v_actual_version != p_current_version THEN
        -- Return conflict with current version
        RETURN QUERY SELECT FALSE, v_actual_version, TRUE;
        RETURN;
    END IF;
    
    -- Update workflow and increment version
    v_new_version := v_actual_version + 1;
    
    UPDATE user_workflow
    SET workflow_state = p_workflow_state,
        version = v_new_version,
        updated_at = NOW()
    WHERE workflow_id = p_workflow_id 
    AND org_id = p_org_id
    AND version = p_current_version;  -- Double-check version hasn't changed
    
    -- Verify update succeeded
    IF NOT FOUND THEN
        -- Version changed during update, return conflict
        SELECT version INTO v_actual_version
        FROM user_workflow
        WHERE workflow_id = p_workflow_id 
        AND org_id = p_org_id;
        
        RETURN QUERY SELECT FALSE, v_actual_version, TRUE;
        RETURN;
    END IF;
    
    RETURN QUERY SELECT TRUE, v_new_version, FALSE;
END;
$$;

COMMENT ON FUNCTION update_workflow_with_version_check IS 
'Updates workflow with optimistic locking using version check to prevent concurrent edits';

-- ============================================================================
-- Step 5: Create function for updating draft with version check
-- ============================================================================
CREATE OR REPLACE FUNCTION update_draft_with_version_check(
    p_workflow_id UUID,
    p_org_id UUID,
    p_draft_state JSONB,
    p_current_version INTEGER
)
RETURNS TABLE(success BOOLEAN, new_version INTEGER, conflict BOOLEAN)
LANGUAGE plpgsql
AS $$
DECLARE
    v_actual_version INTEGER;
    v_new_version INTEGER;
BEGIN
    -- Get current version with row lock
    SELECT version INTO v_actual_version
    FROM user_workflow
    WHERE workflow_id = p_workflow_id 
    AND org_id = p_org_id
    FOR UPDATE;
    
    -- Check if workflow exists
    IF NOT FOUND THEN
        RETURN QUERY SELECT FALSE, 0, FALSE;
        RETURN;
    END IF;
    
    -- Check for version conflict
    IF v_actual_version != p_current_version THEN
        -- Return conflict with current version
        RETURN QUERY SELECT FALSE, v_actual_version, TRUE;
        RETURN;
    END IF;
    
    -- Update draft and increment version
    v_new_version := v_actual_version + 1;
    
    UPDATE user_workflow
    SET draft_state = p_draft_state,
        draft_updated_at = NOW(),
        version = v_new_version,
        updated_at = NOW()
    WHERE workflow_id = p_workflow_id 
    AND org_id = p_org_id
    AND version = p_current_version;  -- Double-check version hasn't changed
    
    -- Verify update succeeded
    IF NOT FOUND THEN
        -- Version changed during update, return conflict
        SELECT version INTO v_actual_version
        FROM user_workflow
        WHERE workflow_id = p_workflow_id 
        AND org_id = p_org_id;
        
        RETURN QUERY SELECT FALSE, v_actual_version, TRUE;
        RETURN;
    END IF;
    
    RETURN QUERY SELECT TRUE, v_new_version, FALSE;
END;
$$;

COMMENT ON FUNCTION update_draft_with_version_check IS 
'Updates draft state with optimistic locking using version check for autosave functionality';

-- ============================================================================
-- Step 6: Create helper function to clear draft (used when publishing)
-- ============================================================================
CREATE OR REPLACE FUNCTION clear_workflow_draft(
    p_workflow_id UUID,
    p_org_id UUID
)
RETURNS BOOLEAN
LANGUAGE plpgsql
AS $$
BEGIN
    UPDATE user_workflow
    SET draft_state = NULL,
        draft_updated_at = NULL,
        updated_at = NOW()
    WHERE workflow_id = p_workflow_id 
    AND org_id = p_org_id;
    
    RETURN FOUND;
END;
$$;

COMMENT ON FUNCTION clear_workflow_draft IS 
'Clears draft state when workflow is published or draft is discarded';

-- ============================================================================
-- Step 7: Create indexes for better performance
-- ============================================================================
CREATE INDEX IF NOT EXISTS idx_user_workflow_version 
ON user_workflow(workflow_id, version);

CREATE INDEX IF NOT EXISTS idx_user_workflow_draft_updated 
ON user_workflow(workflow_id, draft_updated_at) 
WHERE draft_state IS NOT NULL;

-- ============================================================================
-- Step 8: Update alembic version table
-- ============================================================================
INSERT INTO alembic_version (version_num) 
VALUES ('016_add_workflow_versioning')
ON CONFLICT (version_num) DO NOTHING;

-- ============================================================================
-- Verification queries (commented out, run manually to verify)
-- ============================================================================
/*
-- Check if columns were added
SELECT column_name, data_type, is_nullable, column_default
FROM information_schema.columns
WHERE table_name = 'user_workflow'
AND column_name IN ('version', 'draft_state', 'draft_updated_at');

-- Check if functions were created
SELECT proname, prosrc
FROM pg_proc
WHERE proname IN ('update_workflow_with_version_check', 'update_draft_with_version_check', 'clear_workflow_draft');

-- Check indexes
SELECT indexname, indexdef
FROM pg_indexes
WHERE tablename = 'user_workflow'
AND indexname LIKE '%version%' OR indexname LIKE '%draft%';
*/

-- Commit transaction
COMMIT;

-- Success message
DO $$
BEGIN
    RAISE NOTICE '✅ Workflow versioning support has been successfully added!';
    RAISE NOTICE '';
    RAISE NOTICE 'Features enabled:';
    RAISE NOTICE '  • Optimistic locking with version tracking';
    RAISE NOTICE '  • Draft state storage for autosave';
    RAISE NOTICE '  • Concurrent edit conflict detection';
    RAISE NOTICE '  • Version-aware stored procedures';
    RAISE NOTICE '';
    RAISE NOTICE 'Next steps:';
    RAISE NOTICE '  1. Test the versioning with your frontend';
    RAISE NOTICE '  2. Monitor for version conflicts in logs';
    RAISE NOTICE '  3. Consider adding UI for conflict resolution';
END $$;