"""add hierarchical requirements system

Revision ID: 003
Revises: 002
Create Date: 2025-07-29

This migration adds a comprehensive hierarchical requirements system:
- payer_requirement: Base requirements from insurance companies
- org_requirement_policy: Organization-specific policies and overrides  
- requirement_changelog: Audit trail for all requirement changes
- effective_requirements: Materialized view for fast requirement resolution
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '003_add_hierarchical_requirements_system'
down_revision = '002_refactor_workflow_type_to_task_type_fk'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create hierarchical requirements system tables."""
    
    # 1. Create payer_requirement table
    op.create_table('payer_requirement',
        sa.Column('requirement_id', postgresql.UUID(as_uuid=True), 
                  server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('portal_type_id', sa.Integer(), nullable=False),
        sa.Column('task_type_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('version', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('required_fields', postgresql.JSONB(astext_type=sa.Text()), 
                  nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column('optional_fields', postgresql.JSONB(astext_type=sa.Text()), 
                  nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column('field_rules', postgresql.JSONB(astext_type=sa.Text()), 
                  nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column('compliance_ref', sa.Text(), nullable=True),
        sa.Column('effective_date', sa.Date(), nullable=False),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), 
                  server_default=sa.text('now()'), nullable=True),
        sa.Column('created_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.PrimaryKeyConstraint('requirement_id'),
        sa.ForeignKeyConstraint(['portal_type_id'], ['portal_type.portal_type_id'], ),
        sa.ForeignKeyConstraint(['task_type_id'], ['task_type.task_type_id'], ),
        sa.ForeignKeyConstraint(['created_by'], ['app_user.user_id'], ),
        sa.UniqueConstraint('portal_type_id', 'task_type_id', 'version', 
                           name='uq_payer_requirement_portal_task_version')
    )
    op.create_index('idx_payer_requirement_portal_task', 'payer_requirement', 
                    ['portal_type_id', 'task_type_id'], unique=False)
    op.create_index('idx_payer_requirement_effective_date', 'payer_requirement', 
                    ['effective_date'], unique=False)

    # 2. Create org_requirement_policy table
    op.create_table('org_requirement_policy',
        sa.Column('policy_id', postgresql.UUID(as_uuid=True), 
                  server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('org_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('task_type_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('portal_type_id', sa.Integer(), nullable=True),
        sa.Column('policy_type', sa.Text(), nullable=False),
        sa.Column('field_changes', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('reason', sa.Text(), nullable=True),
        sa.Column('version', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), 
                  server_default=sa.text('now()'), nullable=True),
        sa.Column('created_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('approved_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('approved_at', sa.TIMESTAMP(timezone=True), nullable=True),
        sa.CheckConstraint("policy_type IN ('add', 'remove', 'override')", 
                          name='chk_policy_type'),
        sa.PrimaryKeyConstraint('policy_id'),
        sa.ForeignKeyConstraint(['org_id'], ['organization.org_id'], ),
        sa.ForeignKeyConstraint(['task_type_id'], ['task_type.task_type_id'], ),
        sa.ForeignKeyConstraint(['portal_type_id'], ['portal_type.portal_type_id'], ),
        sa.ForeignKeyConstraint(['created_by'], ['app_user.user_id'], ),
        sa.ForeignKeyConstraint(['approved_by'], ['app_user.user_id'], )
    )
    op.create_index('idx_org_policy_org_task', 'org_requirement_policy', 
                    ['org_id', 'task_type_id'], unique=False)
    op.create_index('idx_org_policy_active', 'org_requirement_policy', 
                    ['active'], unique=False)

    # 3. Create requirement_changelog table
    op.create_table('requirement_changelog',
        sa.Column('log_id', postgresql.UUID(as_uuid=True), 
                  server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('source_table', sa.Text(), nullable=False),
        sa.Column('source_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('change_type', sa.Text(), nullable=False),
        sa.Column('previous_value', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('new_value', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('changed_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('changed_at', sa.TIMESTAMP(timezone=True), 
                  server_default=sa.text('now()'), nullable=True),
        sa.Column('ip_address', postgresql.INET(), nullable=True),
        sa.Column('user_agent', sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint('log_id'),
        sa.ForeignKeyConstraint(['changed_by'], ['app_user.user_id'], )
    )
    op.create_index('idx_changelog_source', 'requirement_changelog', 
                    ['source_table', 'source_id'], unique=False)
    op.create_index('idx_changelog_changed_at', 'requirement_changelog', 
                    ['changed_at'], unique=False)

    # 4. Create helper function for merging requirements
    op.execute("""
        CREATE OR REPLACE FUNCTION jsonb_merge_requirements(
            base_fields JSONB,
            policy_type TEXT,
            policy_fields JSONB
        ) RETURNS JSONB AS $$
        BEGIN
            CASE policy_type
                WHEN 'add' THEN
                    -- Add new fields to the array
                    RETURN base_fields || policy_fields;
                WHEN 'remove' THEN
                    -- Remove fields from the array
                    RETURN (
                        SELECT jsonb_agg(elem)
                        FROM jsonb_array_elements(base_fields) elem
                        WHERE elem NOT IN (SELECT jsonb_array_elements(policy_fields))
                    );
                WHEN 'override' THEN
                    -- Complete replacement
                    RETURN policy_fields;
                ELSE
                    RETURN base_fields;
            END CASE;
        END;
        $$ LANGUAGE plpgsql IMMUTABLE;
    """)

    # 5. Create effective_requirements materialized view
    op.execute("""
        CREATE MATERIALIZED VIEW effective_requirements AS
        WITH latest_payer_requirements AS (
            -- Get the latest version of each payer requirement
            SELECT DISTINCT ON (pr.portal_type_id, pr.task_type_id)
                pr.portal_type_id,
                pr.task_type_id,
                pr.required_fields,
                pr.optional_fields,
                pr.field_rules,
                pr.compliance_ref,
                pr.version
            FROM payer_requirement pr
            WHERE pr.effective_date <= CURRENT_DATE
            ORDER BY pr.portal_type_id, pr.task_type_id, pr.version DESC
        ),
        org_policies AS (
            -- Get active org policies
            SELECT 
                op.org_id,
                op.task_type_id,
                op.portal_type_id,
                op.policy_type,
                op.field_changes,
                op.version
            FROM org_requirement_policy op
            WHERE op.active = TRUE
        )
        SELECT 
            ie.portal_id,
            ie.org_id,
            ie.portal_type_id,
            tt.task_type_id,
            -- Merge payer requirements with org policies
            COALESCE(
                (SELECT jsonb_merge_requirements(
                    lpr.required_fields,
                    op.policy_type,
                    op.field_changes->'required_fields'
                )
                FROM org_policies op
                WHERE op.org_id = ie.org_id 
                AND op.task_type_id = tt.task_type_id
                AND (op.portal_type_id IS NULL OR op.portal_type_id = ie.portal_type_id)
                ORDER BY op.version DESC
                LIMIT 1),
                lpr.required_fields,
                '[]'::jsonb
            ) as required_fields,
            COALESCE(
                (SELECT jsonb_merge_requirements(
                    lpr.optional_fields,
                    op.policy_type,
                    op.field_changes->'optional_fields'
                )
                FROM org_policies op
                WHERE op.org_id = ie.org_id 
                AND op.task_type_id = tt.task_type_id
                AND (op.portal_type_id IS NULL OR op.portal_type_id = ie.portal_type_id)
                ORDER BY op.version DESC
                LIMIT 1),
                lpr.optional_fields,
                '[]'::jsonb
            ) as optional_fields,
            COALESCE(
                (SELECT jsonb_merge_requirements(
                    lpr.field_rules,
                    op.policy_type,
                    op.field_changes->'field_rules'
                )
                FROM org_policies op
                WHERE op.org_id = ie.org_id 
                AND op.task_type_id = tt.task_type_id
                AND (op.portal_type_id IS NULL OR op.portal_type_id = ie.portal_type_id)
                ORDER BY op.version DESC
                LIMIT 1),
                lpr.field_rules,
                '{}'::jsonb
            ) as field_rules,
            lpr.compliance_ref,
            now() as last_updated
        FROM integration_endpoint ie
        CROSS JOIN task_type tt
        LEFT JOIN latest_payer_requirements lpr 
            ON lpr.portal_type_id = ie.portal_type_id 
            AND lpr.task_type_id = tt.task_type_id
    """)

    # Create indexes on the materialized view
    op.execute("""
        CREATE UNIQUE INDEX idx_effective_requirements_portal_task 
        ON effective_requirements (portal_id, task_type_id);
        
        CREATE INDEX idx_effective_requirements_org 
        ON effective_requirements (org_id);
    """)

    # 6. Create trigger to refresh materialized view
    op.execute("""
        CREATE OR REPLACE FUNCTION refresh_effective_requirements()
        RETURNS TRIGGER AS $$
        BEGIN
            -- Use CONCURRENTLY in production for non-blocking refresh
            -- For now, using regular refresh
            REFRESH MATERIALIZED VIEW effective_requirements;
            RETURN NULL;
        END;
        $$ LANGUAGE plpgsql;
    """)

    # Create triggers on source tables
    op.execute("""
        CREATE TRIGGER refresh_requirements_on_payer_change
        AFTER INSERT OR UPDATE OR DELETE ON payer_requirement
        FOR EACH STATEMENT EXECUTE FUNCTION refresh_effective_requirements();
        
        CREATE TRIGGER refresh_requirements_on_policy_change
        AFTER INSERT OR UPDATE OR DELETE ON org_requirement_policy
        FOR EACH STATEMENT EXECUTE FUNCTION refresh_effective_requirements();
        
        CREATE TRIGGER refresh_requirements_on_endpoint_change
        AFTER INSERT OR UPDATE OR DELETE ON integration_endpoint
        FOR EACH STATEMENT EXECUTE FUNCTION refresh_effective_requirements();
    """)

    # 7. Create changelog triggers
    op.execute("""
        CREATE OR REPLACE FUNCTION log_requirement_change()
        RETURNS TRIGGER AS $$
        BEGIN
            IF TG_OP = 'INSERT' THEN
                INSERT INTO requirement_changelog (
                    source_table, source_id, change_type, new_value, changed_by
                ) VALUES (
                    TG_TABLE_NAME, NEW.requirement_id, 'INSERT', 
                    to_jsonb(NEW), 
                    COALESCE(NEW.created_by, current_setting('app.current_user_id', true)::uuid)
                );
            ELSIF TG_OP = 'UPDATE' THEN
                INSERT INTO requirement_changelog (
                    source_table, source_id, change_type, previous_value, new_value, changed_by
                ) VALUES (
                    TG_TABLE_NAME, NEW.requirement_id, 'UPDATE', 
                    to_jsonb(OLD), to_jsonb(NEW),
                    current_setting('app.current_user_id', true)::uuid
                );
            ELSIF TG_OP = 'DELETE' THEN
                INSERT INTO requirement_changelog (
                    source_table, source_id, change_type, previous_value, changed_by
                ) VALUES (
                    TG_TABLE_NAME, OLD.requirement_id, 'DELETE', 
                    to_jsonb(OLD),
                    current_setting('app.current_user_id', true)::uuid
                );
            END IF;
            RETURN NULL;
        END;
        $$ LANGUAGE plpgsql;
    """)

    # Apply changelog triggers to requirement tables
    op.execute("""
        CREATE TRIGGER log_payer_requirement_changes
        AFTER INSERT OR UPDATE OR DELETE ON payer_requirement
        FOR EACH ROW EXECUTE FUNCTION log_requirement_change();
        
        CREATE TRIGGER log_org_policy_changes
        AFTER INSERT OR UPDATE OR DELETE ON org_requirement_policy
        FOR EACH ROW EXECUTE FUNCTION log_requirement_change();
    """)


def downgrade() -> None:
    """Remove hierarchical requirements system."""
    
    # Drop triggers first
    op.execute("DROP TRIGGER IF EXISTS log_org_policy_changes ON org_requirement_policy")
    op.execute("DROP TRIGGER IF EXISTS log_payer_requirement_changes ON payer_requirement")
    op.execute("DROP TRIGGER IF EXISTS refresh_requirements_on_endpoint_change ON integration_endpoint")
    op.execute("DROP TRIGGER IF EXISTS refresh_requirements_on_policy_change ON org_requirement_policy")
    op.execute("DROP TRIGGER IF EXISTS refresh_requirements_on_payer_change ON payer_requirement")
    
    # Drop functions
    op.execute("DROP FUNCTION IF EXISTS log_requirement_change()")
    op.execute("DROP FUNCTION IF EXISTS refresh_effective_requirements()")
    op.execute("DROP FUNCTION IF EXISTS jsonb_merge_requirements(JSONB, TEXT, JSONB)")
    
    # Drop materialized view
    op.execute("DROP MATERIALIZED VIEW IF EXISTS effective_requirements")
    
    # Drop tables in reverse order
    op.drop_table('requirement_changelog')
    op.drop_table('org_requirement_policy')
    op.drop_table('payer_requirement')