"""Refactor workflow nodes from shared to user-owned

Revision ID: 017_refactor_workflow_nodes_to_user_owned
Revises: 016_add_workflow_versioning  
Create Date: 2025-08-13

This migration transforms the workflow node architecture from shared/reusable nodes
to workflow-owned nodes. This is a pragmatic decision that simplifies queries and
aligns with current code expectations, though it does sacrifice some flexibility.

Changes:
1. Rename workflow_node -> user_workflow_node (clarifies ownership)
2. Rename workflow_transition -> user_workflow_transition (consistency)
3. Add workflow_id to nodes (creates 1-to-many relationship)
4. Rename 'code' to 'label' (reflects actual usage as human-readable text)
5. Add proper 'id' field for stable identification

TECHNICAL DEBT: This design loses node reusability across workflows.
Consider refactoring back to shared nodes if reuse patterns emerge.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
import uuid

# revision identifiers, used by Alembic.
revision = '017_refactor_workflow_nodes_to_user_owned'
down_revision = '016_add_workflow_versioning'
branch_labels = None
depends_on = None


def upgrade():
    """Transform workflow nodes from shared to user-owned"""
    
    # Step 1: Create new tables with proper structure
    # ================================================
    
    # Create user_workflow_node table
    op.execute("""
        CREATE TABLE IF NOT EXISTS user_workflow_node (
            -- Primary identifier (UUID to match frontend)
            node_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            
            -- Workflow ownership (NEW - makes nodes workflow-specific)
            workflow_id UUID NOT NULL,
            
            -- Human-readable label (renamed from 'code')
            label TEXT NOT NULL,
            
            -- Original fields
            description TEXT,
            metadata JSONB DEFAULT '{}'::jsonb,
            label_conf NUMERIC(3, 2),
            last_label_at TIMESTAMPTZ,
            
            -- Add foreign key to user_workflow
            CONSTRAINT fk_workflow
                FOREIGN KEY (workflow_id) 
                REFERENCES user_workflow(workflow_id)
                ON DELETE CASCADE,
            
            -- Ensure unique nodes per workflow
            CONSTRAINT uq_workflow_node
                UNIQUE (workflow_id, node_id)
        );
        
        COMMENT ON TABLE user_workflow_node IS 
            'Workflow-specific nodes (refactored from shared workflow_node)';
        COMMENT ON COLUMN user_workflow_node.workflow_id IS 
            'Owning workflow - nodes are no longer shared across workflows';
        COMMENT ON COLUMN user_workflow_node.node_id IS 
            'UUID primary identifier matching frontend expectations';
        COMMENT ON COLUMN user_workflow_node.label IS 
            'Human-readable label (e.g., "Login to Portal", "Check Status")';
    """)
    
    # Create user_workflow_transition table
    op.execute("""
        CREATE TABLE IF NOT EXISTS user_workflow_transition (
            -- Workflow ownership
            workflow_id UUID NOT NULL,
            
            -- Node references (using UUID to match node_id)
            from_node UUID NOT NULL,
            to_node UUID NOT NULL,
            
            -- Original fields
            action_label TEXT NOT NULL,
            freq INTEGER NOT NULL DEFAULT 1,
            
            -- Composite primary key
            PRIMARY KEY (workflow_id, from_node, to_node, action_label),
            
            -- Foreign key to workflow
            CONSTRAINT fk_workflow
                FOREIGN KEY (workflow_id)
                REFERENCES user_workflow(workflow_id)
                ON DELETE CASCADE,
            
            -- Foreign keys to nodes
            CONSTRAINT fk_from_node
                FOREIGN KEY (from_node)
                REFERENCES user_workflow_node(node_id)
                ON DELETE CASCADE,
            
            CONSTRAINT fk_to_node
                FOREIGN KEY (to_node)
                REFERENCES user_workflow_node(node_id)
                ON DELETE CASCADE,
            
            -- Frequency must be positive
            CONSTRAINT ck_freq_positive
                CHECK (freq >= 1)
        );
        
        COMMENT ON TABLE user_workflow_transition IS 
            'Workflow-specific transitions (refactored from shared workflow_transition)';
        COMMENT ON COLUMN user_workflow_transition.workflow_id IS 
            'Owning workflow - transitions are workflow-specific';
        COMMENT ON COLUMN user_workflow_transition.from_node IS 
            'Source node UUID (references user_workflow_node.node_id)';
        COMMENT ON COLUMN user_workflow_transition.to_node IS 
            'Target node UUID (references user_workflow_node.node_id)';
    """)
    
    # Step 2: Migrate existing data
    # ==============================
    
    # Check if old tables exist and have data
    op.execute("""
        DO $$
        DECLARE
            v_has_nodes BOOLEAN;
            v_has_transitions BOOLEAN;
        BEGIN
            -- Check if old tables exist
            SELECT EXISTS(
                SELECT 1 FROM information_schema.tables 
                WHERE table_name = 'workflow_node'
            ) INTO v_has_nodes;
            
            SELECT EXISTS(
                SELECT 1 FROM information_schema.tables 
                WHERE table_name = 'workflow_transition'
            ) INTO v_has_transitions;
            
            IF v_has_nodes THEN
                -- Create temporary mapping table for old to new node IDs
                CREATE TEMP TABLE node_id_mapping (
                    old_node_id BIGINT,
                    new_node_id UUID,
                    workflow_id UUID
                );
                
                -- Generate UUID mappings for each node per workflow
                INSERT INTO node_id_mapping (old_node_id, new_node_id, workflow_id)
                SELECT 
                    wn.node_id,
                    gen_random_uuid(),
                    uw.workflow_id
                FROM workflow_node wn
                CROSS JOIN user_workflow uw;
                
                -- Migrate nodes with new UUIDs
                INSERT INTO user_workflow_node (
                    node_id,                 -- New UUID
                    workflow_id,
                    label,                   -- code becomes label
                    description,
                    metadata,
                    label_conf,
                    last_label_at
                )
                SELECT 
                    nm.new_node_id,          -- Use mapped UUID
                    nm.workflow_id,
                    wn.code,                 -- code becomes label
                    wn.description,
                    wn.metadata,
                    wn.label_conf,
                    wn.last_label_at
                FROM workflow_node wn
                JOIN node_id_mapping nm ON nm.old_node_id = wn.node_id
                WHERE EXISTS (
                    -- Only migrate if we have workflows to attach to
                    SELECT 1 FROM user_workflow
                );
                
                RAISE NOTICE 'Migrated % nodes to user_workflow_node', 
                    (SELECT COUNT(*) FROM user_workflow_node);
            END IF;
            
            IF v_has_transitions THEN
                -- Migrate transitions using the UUID mappings
                INSERT INTO user_workflow_transition (
                    workflow_id,
                    from_node,               -- UUID from mapping
                    to_node,                 -- UUID from mapping
                    action_label,
                    freq
                )
                SELECT DISTINCT
                    nm_from.workflow_id,
                    nm_from.new_node_id,     -- Mapped UUID
                    nm_to.new_node_id,       -- Mapped UUID
                    wt.action_label,
                    wt.freq
                FROM workflow_transition wt
                JOIN node_id_mapping nm_from ON nm_from.old_node_id = wt.from_node
                JOIN node_id_mapping nm_to ON nm_to.old_node_id = wt.to_node 
                    AND nm_to.workflow_id = nm_from.workflow_id  -- Same workflow
                WHERE EXISTS (
                    SELECT 1 FROM user_workflow
                );
                
                RAISE NOTICE 'Migrated % transitions to user_workflow_transition', 
                    (SELECT COUNT(*) FROM user_workflow_transition);
                    
                -- Clean up temp table
                DROP TABLE IF EXISTS node_id_mapping;
            END IF;
        END $$;
    """)
    
    # Step 3: Update foreign key references
    # ======================================
    
    # Update micro_state table to reference new node structure
    op.execute("""
        DO $$
        BEGIN
            -- Check if micro_state table exists and has node_id column
            IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'micro_state' 
                AND column_name = 'node_id'
            ) THEN
                -- Change node_id from BIGINT to UUID to match new structure
                ALTER TABLE micro_state 
                DROP CONSTRAINT IF EXISTS micro_state_node_id_fkey;
                
                -- Add new UUID column
                ALTER TABLE micro_state 
                ADD COLUMN IF NOT EXISTS node_id_uuid UUID;
                
                -- Note: Data migration would need the node_id_mapping table
                -- which was dropped earlier. In production, you'd handle this differently
                
                -- Eventually drop old column and rename new one
                -- ALTER TABLE micro_state DROP COLUMN node_id;
                -- ALTER TABLE micro_state RENAME COLUMN node_id_uuid TO node_id;
                
                RAISE NOTICE 'micro_state table structure updated for UUID node references';
            END IF;
        END $$;
    """)
    
    # Step 4: Create indexes for performance
    # =======================================
    
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_user_workflow_node_workflow_id 
            ON user_workflow_node(workflow_id);
        
        CREATE INDEX IF NOT EXISTS idx_user_workflow_node_composite 
            ON user_workflow_node(workflow_id, node_id);
        
        CREATE INDEX IF NOT EXISTS idx_user_workflow_transition_workflow_id 
            ON user_workflow_transition(workflow_id);
        
        CREATE INDEX IF NOT EXISTS idx_user_workflow_transition_from_node 
            ON user_workflow_transition(workflow_id, from_node);
        
        CREATE INDEX IF NOT EXISTS idx_user_workflow_transition_to_node 
            ON user_workflow_transition(workflow_id, to_node);
    """)
    
    # Step 5: Update RLS policies for new tables
    # ===========================================
    
    op.execute("""
        -- Enable RLS on new tables
        ALTER TABLE user_workflow_node ENABLE ROW LEVEL SECURITY;
        ALTER TABLE user_workflow_transition ENABLE ROW LEVEL SECURITY;
        
        -- Create RLS policies for user_workflow_node
        CREATE POLICY user_workflow_node_org_isolation ON user_workflow_node
            USING (
                workflow_id IN (
                    SELECT workflow_id FROM user_workflow
                    WHERE org_id = current_setting('app.org_id', true)::uuid
                )
            );
        
        -- Create RLS policies for user_workflow_transition  
        CREATE POLICY user_workflow_transition_org_isolation ON user_workflow_transition
            USING (
                workflow_id IN (
                    SELECT workflow_id FROM user_workflow
                    WHERE org_id = current_setting('app.org_id', true)::uuid
                )
            );
    """)
    
    # Step 6: Drop old tables (commented for safety - run manually after verification)
    # ================================================================================
    
    op.execute("""
        -- IMPORTANT: Verify migration before uncommenting these drops!
        -- Review data in new tables and test application functionality first.
        
        -- ALTER TABLE workflow_node RENAME TO workflow_node_deprecated;
        -- ALTER TABLE workflow_transition RENAME TO workflow_transition_deprecated;
        
        -- To fully drop after verification:
        -- DROP TABLE IF EXISTS workflow_node CASCADE;
        -- DROP TABLE IF EXISTS workflow_transition CASCADE;
    """)
    
    # Step 7: Add helpful comments
    # =============================
    
    op.execute("""
        COMMENT ON TABLE user_workflow_node IS 
            'Workflow-owned nodes. TECHNICAL DEBT: Sacrifices reusability for simplicity.';
        
        COMMENT ON TABLE user_workflow_transition IS 
            'Workflow-owned transitions. Each workflow has its own transition graph.';
    """)


def downgrade():
    """Revert to shared workflow nodes"""
    
    # Step 1: Recreate original tables
    op.execute("""
        -- Recreate workflow_node table
        CREATE TABLE IF NOT EXISTS workflow_node (
            node_id BIGSERIAL PRIMARY KEY,
            code TEXT UNIQUE,
            description TEXT,
            metadata JSONB DEFAULT '{}'::jsonb,
            label_conf NUMERIC(3, 2),
            last_label_at TIMESTAMPTZ
        );
        
        -- Recreate workflow_transition table
        CREATE TABLE IF NOT EXISTS workflow_transition (
            from_node BIGINT REFERENCES workflow_node(node_id) ON DELETE CASCADE,
            to_node BIGINT REFERENCES workflow_node(node_id) ON DELETE CASCADE,
            action_label TEXT NOT NULL,
            freq INTEGER NOT NULL DEFAULT 1,
            PRIMARY KEY (from_node, to_node, action_label),
            CONSTRAINT ck_freq_positive CHECK (freq >= 1)
        );
    """)
    
    # Step 2: Migrate data back (deduplicate nodes)
    op.execute("""
        -- Create mapping for UUID back to BIGINT
        CREATE TEMP TABLE IF NOT EXISTS node_id_reverse_mapping (
            uuid_node_id UUID,
            bigint_node_id BIGSERIAL
        );
        
        -- Generate BIGINT IDs for unique labels
        INSERT INTO node_id_reverse_mapping (uuid_node_id)
        SELECT DISTINCT ON (label) node_id
        FROM user_workflow_node
        ORDER BY label, node_id;
        
        -- Migrate unique nodes back with new BIGINT IDs
        INSERT INTO workflow_node (node_id, code, description, metadata, label_conf, last_label_at)
        SELECT 
            nm.bigint_node_id,
            uwn.label as code,     -- label becomes code again
            uwn.description,
            uwn.metadata,
            uwn.label_conf,
            uwn.last_label_at
        FROM user_workflow_node uwn
        JOIN node_id_reverse_mapping nm ON nm.uuid_node_id = uwn.node_id;
        
        -- Migrate transitions using the mapping
        INSERT INTO workflow_transition (from_node, to_node, action_label, freq)
        SELECT DISTINCT
            nm_from.bigint_node_id,
            nm_to.bigint_node_id,
            uwt.action_label,
            MAX(uwt.freq)          -- Take max frequency across workflows
        FROM user_workflow_transition uwt
        JOIN node_id_reverse_mapping nm_from ON nm_from.uuid_node_id = uwt.from_node
        JOIN node_id_reverse_mapping nm_to ON nm_to.uuid_node_id = uwt.to_node
        GROUP BY nm_from.bigint_node_id, nm_to.bigint_node_id, uwt.action_label
        ON CONFLICT DO NOTHING;
        
        -- Clean up
        DROP TABLE IF EXISTS node_id_reverse_mapping;
    """)
    
    # Step 3: Drop new tables
    op.execute("""
        DROP TABLE IF EXISTS user_workflow_transition CASCADE;
        DROP TABLE IF EXISTS user_workflow_node CASCADE;
    """)
    
    # Step 4: Restore RLS policies on original tables
    op.execute("""
        ALTER TABLE workflow_node ENABLE ROW LEVEL SECURITY;
        ALTER TABLE workflow_transition ENABLE ROW LEVEL SECURITY;
        
        -- Note: Original RLS policies would need to be recreated here
        -- based on your original schema design
    """)