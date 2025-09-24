-- Hierarchical Requirements System Schema Additions
-- To be appended to hybrid_rcm_schema_v3.sql after running migration 003

-- Note: The full schema should be regenerated from the database after migration:
-- pg_dump -s -t payer_requirement -t org_requirement_policy -t requirement_changelog rcm_db

-- =====================================================
-- HIERARCHICAL REQUIREMENTS TABLES
-- =====================================================

-- Payer-level requirements (base truth)
CREATE TABLE payer_requirement (
    requirement_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    portal_type_id INT NOT NULL REFERENCES portal_type(portal_type_id),
    task_type_id UUID NOT NULL REFERENCES task_type(task_type_id),
    version INT NOT NULL DEFAULT 1,
    required_fields JSONB NOT NULL DEFAULT '[]'::jsonb,
    optional_fields JSONB NOT NULL DEFAULT '[]'::jsonb,
    field_rules JSONB NOT NULL DEFAULT '{}'::jsonb,
    compliance_ref TEXT,
    effective_date DATE NOT NULL,
    created_at TIMESTAMPTZ DEFAULT now(),
    created_by UUID REFERENCES app_user(user_id),
    CONSTRAINT uq_payer_requirement_portal_task_version 
        UNIQUE (portal_type_id, task_type_id, version)
);

CREATE INDEX idx_payer_requirement_portal_task 
    ON payer_requirement (portal_type_id, task_type_id);
CREATE INDEX idx_payer_requirement_effective_date 
    ON payer_requirement (effective_date);

-- Organization-specific requirement policies
CREATE TABLE org_requirement_policy (
    policy_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id UUID NOT NULL REFERENCES organization(org_id),
    task_type_id UUID NOT NULL REFERENCES task_type(task_type_id),
    portal_type_id INT REFERENCES portal_type(portal_type_id),
    policy_type TEXT NOT NULL CHECK (policy_type IN ('add', 'remove', 'override')),
    field_changes JSONB NOT NULL,
    reason TEXT,
    version INT NOT NULL DEFAULT 1,
    active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT now(),
    created_by UUID REFERENCES app_user(user_id),
    approved_by UUID REFERENCES app_user(user_id),
    approved_at TIMESTAMPTZ
);

CREATE INDEX idx_org_policy_org_task 
    ON org_requirement_policy (org_id, task_type_id);
CREATE INDEX idx_org_policy_active 
    ON org_requirement_policy (active);

-- Requirement change audit log
CREATE TABLE requirement_changelog (
    log_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_table TEXT NOT NULL,
    source_id UUID NOT NULL,
    change_type TEXT NOT NULL,
    previous_value JSONB,
    new_value JSONB,
    changed_by UUID REFERENCES app_user(user_id),
    changed_at TIMESTAMPTZ DEFAULT now(),
    ip_address INET,
    user_agent TEXT
);

CREATE INDEX idx_changelog_source 
    ON requirement_changelog (source_table, source_id);
CREATE INDEX idx_changelog_changed_at 
    ON requirement_changelog (changed_at);

-- =====================================================
-- HELPER FUNCTION FOR MERGING REQUIREMENTS
-- =====================================================

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

-- =====================================================
-- EFFECTIVE REQUIREMENTS MATERIALIZED VIEW
-- =====================================================

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
    AND lpr.task_type_id = tt.task_type_id;

-- Indexes on materialized view
CREATE UNIQUE INDEX idx_effective_requirements_portal_task 
    ON effective_requirements (portal_id, task_type_id);
CREATE INDEX idx_effective_requirements_org 
    ON effective_requirements (org_id);

-- =====================================================
-- REFRESH TRIGGERS
-- =====================================================

CREATE OR REPLACE FUNCTION refresh_effective_requirements()
RETURNS TRIGGER AS $$
BEGIN
    -- Use CONCURRENTLY in production for non-blocking refresh
    REFRESH MATERIALIZED VIEW effective_requirements;
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

-- Triggers to refresh materialized view on changes
CREATE TRIGGER refresh_requirements_on_payer_change
AFTER INSERT OR UPDATE OR DELETE ON payer_requirement
FOR EACH STATEMENT EXECUTE FUNCTION refresh_effective_requirements();

CREATE TRIGGER refresh_requirements_on_policy_change
AFTER INSERT OR UPDATE OR DELETE ON org_requirement_policy
FOR EACH STATEMENT EXECUTE FUNCTION refresh_effective_requirements();

CREATE TRIGGER refresh_requirements_on_endpoint_change
AFTER INSERT OR UPDATE OR DELETE ON integration_endpoint
FOR EACH STATEMENT EXECUTE FUNCTION refresh_effective_requirements();

-- =====================================================
-- AUDIT LOG TRIGGERS
-- =====================================================

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

-- Apply audit triggers
CREATE TRIGGER log_payer_requirement_changes
AFTER INSERT OR UPDATE OR DELETE ON payer_requirement
FOR EACH ROW EXECUTE FUNCTION log_requirement_change();

CREATE TRIGGER log_org_policy_changes
AFTER INSERT OR UPDATE OR DELETE ON org_requirement_policy
FOR EACH ROW EXECUTE FUNCTION log_requirement_change();