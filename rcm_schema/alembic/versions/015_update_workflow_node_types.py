"""Update workflow node types to entry, outcome, decision, general

Revision ID: 015_update_workflow_node_types
Revises: 014_add_workflow_execution_tables
Create Date: 2025-01-08

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '015_update_workflow_node_types'
down_revision = '014_add_workflow_execution_tables'
branch_labels = None
depends_on = None


def upgrade():
    # Add a check constraint for valid node types
    op.execute("""
        ALTER TABLE workflow_node 
        ADD CONSTRAINT ck_node_type_valid 
        CHECK (
            metadata->>'type' IS NULL OR
            metadata->>'type' IN ('entry', 'outcome', 'decision', 'general')
        )
    """)
    
    # Update existing node types in workflow_node metadata
    op.execute("""
        UPDATE workflow_node
        SET metadata = jsonb_set(
            metadata,
            '{type}',
            CASE 
                WHEN metadata->>'type' = 'start' THEN '"entry"'::jsonb
                WHEN metadata->>'type' = 'end' THEN '"outcome"'::jsonb
                WHEN metadata->>'type' = 'action' THEN '"general"'::jsonb
                WHEN metadata->>'type' = 'agent' THEN '"general"'::jsonb
                WHEN metadata->>'type' = 'error' THEN '"outcome"'::jsonb
                WHEN metadata->>'type' = 'decision' THEN '"decision"'::jsonb
                ELSE metadata->'type'
            END
        )
        WHERE metadata ? 'type'
    """)
    
    # Update node types in workflow_revision snapshots
    op.execute("""
        UPDATE workflow_revision
        SET snapshot = jsonb_set(
            snapshot,
            '{nodes}',
            (
                SELECT jsonb_agg(
                    CASE 
                        WHEN elem->'metadata'->>'type' = 'start' THEN 
                            jsonb_set(elem, '{metadata,type}', '"entry"')
                        WHEN elem->'metadata'->>'type' = 'end' THEN 
                            jsonb_set(elem, '{metadata,type}', '"outcome"')
                        WHEN elem->'metadata'->>'type' = 'action' THEN 
                            jsonb_set(elem, '{metadata,type}', '"general"')
                        WHEN elem->'metadata'->>'type' = 'agent' THEN 
                            jsonb_set(elem, '{metadata,type}', '"general"')
                        WHEN elem->'metadata'->>'type' = 'error' THEN 
                            jsonb_set(elem, '{metadata,type}', '"outcome"')
                        WHEN elem->'metadata'->>'type' = 'decision' THEN 
                            jsonb_set(elem, '{metadata,type}', '"decision"')
                        ELSE elem
                    END
                )
                FROM jsonb_array_elements(snapshot->'nodes') elem
            )
        )
        WHERE snapshot->'nodes' IS NOT NULL
    """)
    
    # Add agent metadata preservation for nodes that were previously 'agent' type
    op.execute("""
        UPDATE workflow_node
        SET metadata = jsonb_set(
            metadata,
            '{agentType}',
            '"web"'::jsonb
        )
        WHERE metadata->>'type' = 'general' 
        AND metadata->>'prevType' = 'agent'
    """)
    
    # Update any draft states in user_workflow
    op.execute("""
        UPDATE user_workflow
        SET draft_state = jsonb_set(
            draft_state,
            '{nodes}',
            (
                SELECT jsonb_agg(
                    CASE 
                        WHEN elem->>'nodeType' = 'start' THEN 
                            jsonb_set(elem, '{nodeType}', '"entry"')
                        WHEN elem->>'nodeType' = 'end' THEN 
                            jsonb_set(elem, '{nodeType}', '"outcome"')
                        WHEN elem->>'nodeType' = 'action' THEN 
                            jsonb_set(elem, '{nodeType}', '"general"')
                        WHEN elem->>'nodeType' = 'agent' THEN 
                            jsonb_set(elem, '{nodeType}', '"general"')
                        WHEN elem->>'nodeType' = 'error' THEN 
                            jsonb_set(elem, '{nodeType}', '"outcome"')
                        WHEN elem->>'nodeType' = 'decision' THEN 
                            jsonb_set(elem, '{nodeType}', '"decision"')
                        ELSE elem
                    END
                )
                FROM jsonb_array_elements(draft_state->'nodes') elem
            )
        )
        WHERE draft_state->'nodes' IS NOT NULL
    """)


def downgrade():
    # Remove the constraint
    op.execute("ALTER TABLE workflow_node DROP CONSTRAINT IF EXISTS ck_node_type_valid")
    
    # Revert node types in workflow_node metadata
    op.execute("""
        UPDATE workflow_node
        SET metadata = jsonb_set(
            metadata,
            '{type}',
            CASE 
                WHEN metadata->>'type' = 'entry' THEN '"start"'::jsonb
                WHEN metadata->>'type' = 'outcome' THEN '"end"'::jsonb
                WHEN metadata->>'type' = 'general' AND metadata->>'agentType' IS NOT NULL THEN '"agent"'::jsonb
                WHEN metadata->>'type' = 'general' THEN '"action"'::jsonb
                WHEN metadata->>'type' = 'decision' THEN '"decision"'::jsonb
                ELSE metadata->'type'
            END
        )
        WHERE metadata ? 'type'
    """)
    
    # Revert node types in workflow_revision snapshots
    op.execute("""
        UPDATE workflow_revision
        SET snapshot = jsonb_set(
            snapshot,
            '{nodes}',
            (
                SELECT jsonb_agg(
                    CASE 
                        WHEN elem->'metadata'->>'type' = 'entry' THEN 
                            jsonb_set(elem, '{metadata,type}', '"start"')
                        WHEN elem->'metadata'->>'type' = 'outcome' THEN 
                            jsonb_set(elem, '{metadata,type}', '"end"')
                        WHEN elem->'metadata'->>'type' = 'general' AND elem->'metadata'->>'agentType' IS NOT NULL THEN 
                            jsonb_set(elem, '{metadata,type}', '"agent"')
                        WHEN elem->'metadata'->>'type' = 'general' THEN 
                            jsonb_set(elem, '{metadata,type}', '"action"')
                        WHEN elem->'metadata'->>'type' = 'decision' THEN 
                            jsonb_set(elem, '{metadata,type}', '"decision"')
                        ELSE elem
                    END
                )
                FROM jsonb_array_elements(snapshot->'nodes') elem
            )
        )
        WHERE snapshot->'nodes' IS NOT NULL
    """)
    
    # Revert draft states
    op.execute("""
        UPDATE user_workflow
        SET draft_state = jsonb_set(
            draft_state,
            '{nodes}',
            (
                SELECT jsonb_agg(
                    CASE 
                        WHEN elem->>'nodeType' = 'entry' THEN 
                            jsonb_set(elem, '{nodeType}', '"start"')
                        WHEN elem->>'nodeType' = 'outcome' THEN 
                            jsonb_set(elem, '{nodeType}', '"end"')
                        WHEN elem->>'nodeType' = 'general' AND elem->'data'->>'agentType' IS NOT NULL THEN 
                            jsonb_set(elem, '{nodeType}', '"agent"')
                        WHEN elem->>'nodeType' = 'general' THEN 
                            jsonb_set(elem, '{nodeType}', '"action"')
                        WHEN elem->>'nodeType' = 'decision' THEN 
                            jsonb_set(elem, '{nodeType}', '"decision"')
                        ELSE elem
                    END
                )
                FROM jsonb_array_elements(draft_state->'nodes') elem
            )
        )
        WHERE draft_state->'nodes' IS NOT NULL
    """)