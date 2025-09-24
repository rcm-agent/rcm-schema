# V8 Multi-Tenancy Guide

## Overview

The V8 schema introduces comprehensive multi-tenant support to the RCM platform, enabling secure data isolation between organizations while maintaining efficient resource sharing.

## Key Concepts

### 1. Organization Root

Every tenant in the system belongs to an `organization`:

```sql
CREATE TABLE organization (
    org_id       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_type     TEXT NOT NULL CHECK (org_type IN ('hospital','billing_firm','credentialer')),
    name         TEXT NOT NULL UNIQUE,
    email_domain TEXT UNIQUE,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

### 2. Data Isolation Pattern

All tenant-specific tables include `org_id`:

```sql
-- Users belong to organizations
CREATE TABLE app_user (
    user_id UUID PRIMARY KEY,
    org_id  UUID NOT NULL REFERENCES organization(org_id),
    ...
);

-- Batch jobs are org-scoped
CREATE TABLE batch_job (
    batch_job_id BIGINT PRIMARY KEY,
    org_id       UUID NOT NULL REFERENCES organization(org_id),
    ...
);
```

### 3. Row Level Security (RLS)

Enable automatic filtering based on organization:

```sql
-- Enable RLS
ALTER TABLE batch_job ENABLE ROW LEVEL SECURITY;

-- Create policy
CREATE POLICY "org_isolation" ON batch_job
    FOR ALL 
    USING (org_id = current_setting('app.current_org_id')::uuid);
```

## Implementation Patterns

### API Layer

Every API request must include organization context:

```python
# FastAPI dependency
async def get_org_context(
    authorization: str = Header(...),
    x_organization_id: str = Header(...)
) -> OrgContext:
    # Validate JWT
    user = decode_jwt(authorization)
    
    # Verify user belongs to org
    if not user_belongs_to_org(user.id, x_organization_id):
        raise HTTPException(403, "Access denied")
    
    return OrgContext(org_id=x_organization_id, user=user)
```

### Database Session

Set organization context for RLS:

```python
async def get_db_session(org_context: OrgContext):
    async with get_session() as session:
        # Set org context for RLS
        await session.execute(
            text("SET app.current_org_id = :org_id"),
            {"org_id": str(org_context.org_id)}
        )
        yield session
```

### Query Patterns

Always include org_id in queries:

```python
# ✅ Good - Explicit org filtering
workflows = await session.execute(
    select(UserWorkflow)
    .join(WorkflowTrace)
    .where(WorkflowTrace.org_id == org_context.org_id)
)

# ❌ Bad - No org filtering
workflows = await session.execute(
    select(UserWorkflow)
)
```

## Channel & Endpoint Abstraction

Organizations configure their own endpoints:

```sql
-- Channel types are global catalog
INSERT INTO channel_type (code, name, endpoint_kind, access_medium) 
VALUES ('anthem_portal', 'Anthem Provider Portal', 'payer', 'web');

-- Each org configures their instance
INSERT INTO endpoint (org_id, name, channel_type_id, config)
VALUES (
    '7b1d-1111-...', 
    'Anthem Production',
    1,
    '{"region": "midwest", "api_version": "2.0"}'
);
```

## Credential Management

Credentials are scoped to organization endpoints:

```
/rcm/{environment}/{org_id}/endpoints/{endpoint_id}/{account_id}

Example:
/rcm/prod/7b1d-1111.../endpoints/123/provider-456
```

## Migration Considerations

### Default Organization

For existing single-tenant data:

```sql
-- Create default org
INSERT INTO organization (org_type, name, email_domain)
VALUES ('billing_firm', 'Default Organization', 'default.com');

-- Migrate existing data
UPDATE batch_job 
SET org_id = (SELECT org_id FROM organization WHERE name = 'Default Organization')
WHERE org_id IS NULL;
```

### Backward Compatibility

Views maintain legacy interfaces:

```sql
-- Legacy apps can still query rcm_user
CREATE VIEW rcm_user AS
SELECT 
    user_id as id,
    email,
    full_name,
    -- org_id hidden from legacy view
    ...
FROM app_user;
```

## Best Practices

1. **Always validate org membership** before granting access
2. **Use RLS policies** as defense in depth
3. **Include org_id in all indexes** for query performance
4. **Audit cross-org access** attempts
5. **Test isolation** with multiple test organizations

## Security Considerations

- Organization IDs should be UUIDs (not sequential)
- Validate org membership on every API call
- Log all cross-organization access attempts
- Use separate encryption keys per organization
- Implement org-level audit trails

## Performance Optimization

```sql
-- Composite indexes for org-scoped queries
CREATE INDEX idx_workflow_trace_org_created 
ON workflow_trace(org_id, created_at DESC);

-- Partition large tables by org_id
CREATE TABLE workflow_trace_2025 PARTITION OF workflow_trace
FOR VALUES FROM ('2025-01-01') TO ('2026-01-01')
PARTITION BY HASH (org_id);
```