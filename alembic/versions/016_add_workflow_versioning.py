"""Add workflow versioning support

Revision ID: 016_add_workflow_versioning
Revises: 015_update_workflow_node_types
Create Date: 2025-01-09

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '016_add_workflow_versioning'
down_revision = '015_update_workflow_node_types'
branch_labels = None
depends_on = None


def upgrade():
    """Add version column and optimistic locking support to user_workflow table"""
    
    # Add version column to user_workflow table if it doesn't exist
    op.execute("""
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
            END IF;
        END $$;
    """)
    
    # Add draft_updated_at column to track when draft was last saved
    op.execute("""
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
            END IF;
        END $$;
    """)
    
    # Add draft_state column if it doesn't exist (for storing autosave drafts)
    op.execute("""
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
            END IF;
        END $$;
    """)
    
    # Create function for updating workflow with version check
    op.execute("""
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
            AND org_id = p_org_id;
            
            RETURN QUERY SELECT TRUE, v_new_version, FALSE;
        END;
        $$;
    """)
    
    # Create function for updating draft with version check
    op.execute("""
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
            AND org_id = p_org_id;
            
            RETURN QUERY SELECT TRUE, v_new_version, FALSE;
        END;
        $$;
    """)
    
    # Create index on version column for better performance
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_user_workflow_version 
        ON user_workflow(workflow_id, version);
    """)
    
    # Add comment on functions
    op.execute("""
        COMMENT ON FUNCTION update_workflow_with_version_check IS 
        'Updates workflow with optimistic locking using version check to prevent concurrent edits';
        
        COMMENT ON FUNCTION update_draft_with_version_check IS 
        'Updates draft state with optimistic locking using version check for autosave functionality';
    """)


def downgrade():
    """Remove workflow versioning support"""
    
    # Drop functions
    op.execute("DROP FUNCTION IF EXISTS update_workflow_with_version_check CASCADE;")
    op.execute("DROP FUNCTION IF EXISTS update_draft_with_version_check CASCADE;")
    
    # Drop index
    op.execute("DROP INDEX IF EXISTS idx_user_workflow_version;")
    
    # Remove columns
    op.execute("""
        ALTER TABLE user_workflow 
        DROP COLUMN IF EXISTS version,
        DROP COLUMN IF EXISTS draft_updated_at,
        DROP COLUMN IF EXISTS draft_state;
    """)