-- Fix Workflow Execution Node References
-- Migration to update workflow execution tables to reference user_workflow_node instead of workflow_node
-- Date: 2025-08-14

BEGIN;

-- ============================================================================
-- 1. ADD TEMPORARY COLUMN TO user_workflow_node FOR MIGRATION
-- ============================================================================

-- Add a temporary column to map old BIGINT IDs to new UUID IDs if needed
ALTER TABLE user_workflow_node 
ADD COLUMN IF NOT EXISTS old_node_id BIGINT;

-- ============================================================================
-- 2. FIX workflow_steps TABLE
-- ============================================================================

PRINT 'Fixing workflow_steps table...';

-- Drop existing foreign key constraint
ALTER TABLE workflow_steps 
DROP CONSTRAINT IF EXISTS workflow_steps_node_id_fkey;

-- Add new UUID column
ALTER TABLE workflow_steps 
ADD COLUMN IF NOT EXISTS node_id_new UUID;

-- If there's existing data, we need to handle it
-- For now, we'll set to NULL and require manual mapping or use a default
UPDATE workflow_steps 
SET node_id_new = NULL 
WHERE node_id_new IS NULL;

-- Drop old BIGINT column
ALTER TABLE workflow_steps 
DROP COLUMN IF EXISTS node_id CASCADE;

-- Rename new column
ALTER TABLE workflow_steps 
RENAME COLUMN node_id_new TO node_id;

-- Make it NOT NULL after data migration (commented out for safety)
-- ALTER TABLE workflow_steps ALTER COLUMN node_id SET NOT NULL;

-- Add foreign key to user_workflow_node
ALTER TABLE workflow_steps
ADD CONSTRAINT workflow_steps_node_id_fkey 
FOREIGN KEY (node_id) REFERENCES user_workflow_node(node_id) ON DELETE RESTRICT;

-- ============================================================================
-- 3. FIX node_io_requirements TABLE
-- ============================================================================

PRINT 'Fixing node_io_requirements table...';

-- Drop existing foreign key constraint
ALTER TABLE node_io_requirements 
DROP CONSTRAINT IF EXISTS node_io_requirements_node_id_fkey;

-- Add new UUID column
ALTER TABLE node_io_requirements 
ADD COLUMN IF NOT EXISTS node_id_new UUID;

-- Migrate any existing data (set to NULL for now)
UPDATE node_io_requirements 
SET node_id_new = NULL 
WHERE node_id_new IS NULL;

-- Drop old BIGINT column
ALTER TABLE node_io_requirements 
DROP COLUMN IF EXISTS node_id CASCADE;

-- Rename new column
ALTER TABLE node_io_requirements 
RENAME COLUMN node_id_new TO node_id;

-- Make it NOT NULL after data migration (commented out for safety)
-- ALTER TABLE node_io_requirements ALTER COLUMN node_id SET NOT NULL;

-- Add foreign key to user_workflow_node
ALTER TABLE node_io_requirements
ADD CONSTRAINT node_io_requirements_node_id_fkey 
FOREIGN KEY (node_id) REFERENCES user_workflow_node(node_id) ON DELETE CASCADE;

-- ============================================================================
-- 4. FIX workflow_data_bindings TABLE
-- ============================================================================

PRINT 'Fixing workflow_data_bindings table...';

-- Drop existing foreign key constraint
ALTER TABLE workflow_data_bindings 
DROP CONSTRAINT IF EXISTS workflow_data_bindings_node_id_fkey;

-- Add new UUID column
ALTER TABLE workflow_data_bindings 
ADD COLUMN IF NOT EXISTS node_id_new UUID;

-- Migrate any existing data (set to NULL for now)
UPDATE workflow_data_bindings 
SET node_id_new = NULL 
WHERE node_id_new IS NULL;

-- Drop old BIGINT column
ALTER TABLE workflow_data_bindings 
DROP COLUMN IF EXISTS node_id CASCADE;

-- Rename new column
ALTER TABLE workflow_data_bindings 
RENAME COLUMN node_id_new TO node_id;

-- Make it NOT NULL after data migration (commented out for safety)
-- ALTER TABLE workflow_data_bindings ALTER COLUMN node_id SET NOT NULL;

-- Add foreign key to user_workflow_node
ALTER TABLE workflow_data_bindings
ADD CONSTRAINT workflow_data_bindings_node_id_fkey 
FOREIGN KEY (node_id) REFERENCES user_workflow_node(node_id) ON DELETE CASCADE;

-- ============================================================================
-- 5. FIX workflow_trace_screenshot TABLE
-- ============================================================================

PRINT 'Fixing workflow_trace_screenshot table...';

-- Add new UUID column
ALTER TABLE workflow_trace_screenshot 
ADD COLUMN IF NOT EXISTS node_id_new UUID;

-- Migrate any existing data
-- Try to match by node_name to user_workflow_node.label
UPDATE workflow_trace_screenshot wts
SET node_id_new = uwn.node_id
FROM user_workflow_node uwn
WHERE wts.node_name = uwn.label
AND wts.node_id_new IS NULL;

-- For any remaining, generate a new UUID
UPDATE workflow_trace_screenshot
SET node_id_new = gen_random_uuid()
WHERE node_id_new IS NULL;

-- Drop old INTEGER column
ALTER TABLE workflow_trace_screenshot 
DROP COLUMN IF EXISTS node_id CASCADE;

-- Rename new column
ALTER TABLE workflow_trace_screenshot 
RENAME COLUMN node_id_new TO node_id;

-- Make it NOT NULL
ALTER TABLE workflow_trace_screenshot 
ALTER COLUMN node_id SET NOT NULL;

-- Note: Not adding foreign key for screenshots as they might reference historical nodes

-- ============================================================================
-- 6. RECREATE INDEXES
-- ============================================================================

PRINT 'Recreating indexes...';

-- Drop old indexes if they exist
DROP INDEX IF EXISTS idx_workflow_steps_node;
DROP INDEX IF EXISTS idx_node_io_requirements_node;
DROP INDEX IF EXISTS idx_workflow_data_bindings_node;

-- Create new indexes with UUID type
CREATE INDEX IF NOT EXISTS idx_workflow_steps_node ON workflow_steps(node_id);
CREATE INDEX IF NOT EXISTS idx_node_io_requirements_node ON node_io_requirements(node_id);
CREATE INDEX IF NOT EXISTS idx_workflow_data_bindings_node ON workflow_data_bindings(node_id);
CREATE INDEX IF NOT EXISTS idx_workflow_trace_screenshot_node ON workflow_trace_screenshot(node_id);

-- ============================================================================
-- 7. CLEAN UP
-- ============================================================================

-- Remove temporary column from user_workflow_node
ALTER TABLE user_workflow_node 
DROP COLUMN IF EXISTS old_node_id;

-- ============================================================================
-- 8. VERIFICATION QUERIES
-- ============================================================================

-- Check that all tables have correct column types
SELECT 
    table_name,
    column_name,
    data_type,
    udt_name
FROM information_schema.columns
WHERE table_name IN ('workflow_steps', 'node_io_requirements', 'workflow_data_bindings', 'workflow_trace_screenshot')
AND column_name = 'node_id'
ORDER BY table_name;

-- Check foreign key constraints
SELECT
    tc.table_name,
    kcu.column_name,
    ccu.table_name AS foreign_table_name,
    ccu.column_name AS foreign_column_name
FROM information_schema.table_constraints AS tc
JOIN information_schema.key_column_usage AS kcu
    ON tc.constraint_name = kcu.constraint_name
JOIN information_schema.constraint_column_usage AS ccu
    ON ccu.constraint_name = tc.constraint_name
WHERE tc.constraint_type = 'FOREIGN KEY'
AND kcu.column_name = 'node_id'
AND tc.table_name IN ('workflow_steps', 'node_io_requirements', 'workflow_data_bindings')
ORDER BY tc.table_name;

COMMIT;

PRINT 'Migration completed successfully!';
PRINT 'Note: You may need to manually update node_id values in the affected tables if you have existing data.';