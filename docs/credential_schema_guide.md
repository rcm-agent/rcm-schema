# RCM Credential Storage — Database Schema Guide

> 📖 **Part of the RCM Credential Storage System**
> - Design Spec: [credential_storage_design.md](./credential_storage_design.md)
> - Schema Guide: **You are here**
> - Infrastructure: [rcm-cdk/docs/credential_infrastructure.md](../../rcm-cdk/docs/credential_infrastructure.md)
> - Integration: [rcm-web-agent/docs/credential_integration.md](../../rcm-web-agent/docs/credential_integration.md)

**Status:** 🟡 In Development | **Last Updated:** 2025-07-30

## Overview

This guide details the database schema changes required to implement secure credential storage using AWS Systems Manager Parameter Store.

## Schema Changes

### 1. Add Credential Storage Fields

```sql
-- Add secret ARN column to integration_endpoint table
ALTER TABLE integration_endpoint
  ADD COLUMN secret_arn TEXT,
  ADD COLUMN last_rotated_at TIMESTAMPTZ,
  ADD COLUMN rotation_status TEXT DEFAULT 'pending',
  ADD CONSTRAINT check_secret_arn_format 
    CHECK (secret_arn IS NULL OR 
           secret_arn LIKE 'arn:aws:ssm:%:parameter/%' OR 
           secret_arn LIKE 'arn:aws:secretsmanager:%:secret:%'),
  ADD CONSTRAINT check_rotation_status 
    CHECK (rotation_status IN ('active', 'failed', 'pending', 'rotating'));

-- Create index for monitoring queries
CREATE INDEX idx_integration_endpoint_rotation 
  ON integration_endpoint(last_rotated_at, rotation_status) 
  WHERE secret_arn IS NOT NULL;

-- Add comment for documentation
COMMENT ON COLUMN integration_endpoint.secret_arn IS 
  'ARN of the AWS SSM Parameter or Secrets Manager secret containing portal credentials';
COMMENT ON COLUMN integration_endpoint.last_rotated_at IS 
  'Timestamp of last successful credential rotation';
COMMENT ON COLUMN integration_endpoint.rotation_status IS 
  'Current rotation status: active (success), failed, pending (not rotated), rotating (in progress)';
```

### 2. Create Audit Table

```sql
-- Audit table for credential access and rotation history
CREATE TABLE credential_audit_log (
  audit_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  portal_id INTEGER NOT NULL REFERENCES integration_endpoint(portal_id) ON DELETE CASCADE,
  action TEXT NOT NULL CHECK (action IN ('access', 'rotate', 'update', 'delete')),
  performed_by TEXT NOT NULL, -- Service name or user ID
  performed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  details JSONB,
  success BOOLEAN NOT NULL,
  error_message TEXT
);

-- Indexes for efficient querying
CREATE INDEX idx_credential_audit_portal_time 
  ON credential_audit_log(portal_id, performed_at DESC);
CREATE INDEX idx_credential_audit_action 
  ON credential_audit_log(action, performed_at DESC);

-- Retention policy (optional)
COMMENT ON TABLE credential_audit_log IS 
  'Audit log for credential operations. Retain for 90 days per compliance requirements.';
```

### 3. Update Models (SQLAlchemy)

```python
# In models.py, update IntegrationEndpoint class

class IntegrationEndpoint(Base, OrgContextMixin):
    """Integration endpoints (tenant-specific portal configurations)."""
    __tablename__ = 'integration_endpoint'
    
    # Existing columns...
    
    # New credential storage columns
    secret_arn = Column(
        Text, 
        nullable=True,
        comment='ARN of AWS SSM Parameter or Secrets Manager secret'
    )
    last_rotated_at = Column(
        DateTime(timezone=True), 
        nullable=True,
        comment='Last successful credential rotation timestamp'
    )
    rotation_status = Column(
        SQLEnum('active', 'failed', 'pending', 'rotating', name='rotation_status'),
        nullable=False,
        default='pending',
        comment='Current credential rotation status'
    )
    
    # Add validation
    @validates('secret_arn')
    def validate_secret_arn(self, key, value):
        if value and not (
            value.startswith('arn:aws:ssm:') or 
            value.startswith('arn:aws:secretsmanager:')
        ):
            raise ValueError('Invalid secret ARN format')
        return value

# New audit log model
class CredentialAuditLog(Base):
    """Audit log for credential operations."""
    __tablename__ = 'credential_audit_log'
    
    audit_id = Column(PostgreUUID(as_uuid=True), primary_key=True, default=uuid4)
    portal_id = Column(
        Integer, 
        ForeignKey('integration_endpoint.portal_id', ondelete='CASCADE'),
        nullable=False
    )
    action = Column(
        SQLEnum('access', 'rotate', 'update', 'delete', name='credential_action'),
        nullable=False
    )
    performed_by = Column(Text, nullable=False)
    performed_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    details = Column(JSONB, nullable=True)
    success = Column(Boolean, nullable=False)
    error_message = Column(Text, nullable=True)
    
    # Relationships
    portal = relationship('IntegrationEndpoint', backref='credential_audits')
```

## Migration Guide

### 1. Create Alembic Migration

```bash
# Generate migration
alembic revision -m "Add credential storage fields"
```

```python
# In the generated migration file
"""Add credential storage fields

Revision ID: 006_add_credential_storage
Revises: 005_add_comprehensive_bpo_task_enums
Create Date: 2025-07-30

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

def upgrade():
    # Add columns to integration_endpoint
    op.add_column('integration_endpoint', 
        sa.Column('secret_arn', sa.Text(), nullable=True))
    op.add_column('integration_endpoint', 
        sa.Column('last_rotated_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('integration_endpoint', 
        sa.Column('rotation_status', sa.Text(), nullable=False, server_default='pending'))
    
    # Add constraints
    op.create_check_constraint(
        'check_secret_arn_format',
        'integration_endpoint',
        "secret_arn IS NULL OR secret_arn LIKE 'arn:aws:ssm:%:parameter/%' OR secret_arn LIKE 'arn:aws:secretsmanager:%:secret:%'"
    )
    op.create_check_constraint(
        'check_rotation_status',
        'integration_endpoint',
        "rotation_status IN ('active', 'failed', 'pending', 'rotating')"
    )
    
    # Create index
    op.create_index(
        'idx_integration_endpoint_rotation',
        'integration_endpoint',
        ['last_rotated_at', 'rotation_status'],
        postgresql_where=sa.text('secret_arn IS NOT NULL')
    )
    
    # Create audit table
    op.create_table('credential_audit_log',
        sa.Column('audit_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('portal_id', sa.Integer(), nullable=False),
        sa.Column('action', sa.Text(), nullable=False),
        sa.Column('performed_by', sa.Text(), nullable=False),
        sa.Column('performed_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('details', postgresql.JSONB(), nullable=True),
        sa.Column('success', sa.Boolean(), nullable=False),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['portal_id'], ['integration_endpoint.portal_id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('audit_id')
    )
    
    # Create indexes on audit table
    op.create_index('idx_credential_audit_portal_time', 'credential_audit_log', 
                    ['portal_id', sa.text('performed_at DESC')])
    op.create_index('idx_credential_audit_action', 'credential_audit_log', 
                    ['action', sa.text('performed_at DESC')])

def downgrade():
    # Drop audit table
    op.drop_index('idx_credential_audit_action', 'credential_audit_log')
    op.drop_index('idx_credential_audit_portal_time', 'credential_audit_log')
    op.drop_table('credential_audit_log')
    
    # Drop constraints and columns
    op.drop_index('idx_integration_endpoint_rotation', 'integration_endpoint')
    op.drop_constraint('check_rotation_status', 'integration_endpoint')
    op.drop_constraint('check_secret_arn_format', 'integration_endpoint')
    op.drop_column('integration_endpoint', 'rotation_status')
    op.drop_column('integration_endpoint', 'last_rotated_at')
    op.drop_column('integration_endpoint', 'secret_arn')
```

### 2. Data Migration Strategy

#### Phase 1: Add New Schema (No Data Changes)
```bash
# Apply migration to all environments
alembic upgrade head
```

#### Phase 2: Migrate Credentials (Gradual)

```python
# Migration script to move credentials from config JSONB to SSM
import asyncio
from sqlalchemy import select
from rcm_schema.models import IntegrationEndpoint

async def migrate_portal_credentials(session, portal_id: int):
    """Migrate a single portal's credentials to SSM."""
    portal = await session.get(IntegrationEndpoint, portal_id)
    
    if portal.secret_arn:
        print(f"Portal {portal_id} already migrated")
        return
    
    # Extract credentials from config
    if not portal.config or 'credentials' not in portal.config:
        print(f"No credentials found for portal {portal_id}")
        return
    
    creds = portal.config['credentials']
    
    # Create SSM parameter (handled by CDK/external script)
    secret_arn = await create_ssm_parameter(
        portal_id=portal_id,
        org_id=portal.org_id,
        portal_type=portal.portal_type.code,
        credentials=creds
    )
    
    # Update database
    portal.secret_arn = secret_arn
    portal.last_rotated_at = datetime.utcnow()
    portal.rotation_status = 'active'
    
    # Log audit entry
    audit = CredentialAuditLog(
        portal_id=portal_id,
        action='update',
        performed_by='migration_script',
        details={'migration': 'config_to_ssm'},
        success=True
    )
    session.add(audit)
    
    await session.commit()
    print(f"Migrated portal {portal_id} -> {secret_arn}")

# Run migration
async def run_migration():
    async with get_session() as session:
        # Get all portals
        result = await session.execute(
            select(IntegrationEndpoint).where(
                IntegrationEndpoint.secret_arn.is_(None)
            )
        )
        portals = result.scalars().all()
        
        # Migrate in batches
        for portal in portals:
            try:
                await migrate_portal_credentials(session, portal.portal_id)
                await asyncio.sleep(0.1)  # Rate limiting
            except Exception as e:
                print(f"Failed to migrate portal {portal.portal_id}: {e}")
```

#### Phase 3: Cleanup Legacy Data

```sql
-- After all portals are migrated and verified

-- Remove credentials from config JSONB
UPDATE integration_endpoint
SET config = config - 'credentials'
WHERE secret_arn IS NOT NULL;

-- Add NOT NULL constraint (optional, after full migration)
ALTER TABLE integration_endpoint
  ALTER COLUMN secret_arn SET NOT NULL;
```

## Querying Patterns

### 1. Find Portals Needing Rotation

```sql
-- Portals not rotated in 60+ days
SELECT 
  ie.portal_id,
  ie.name,
  pt.name as portal_type,
  ie.last_rotated_at,
  EXTRACT(DAY FROM NOW() - ie.last_rotated_at) as days_since_rotation
FROM integration_endpoint ie
JOIN portal_type pt ON ie.portal_type_id = pt.portal_type_id
WHERE ie.secret_arn IS NOT NULL
  AND (ie.last_rotated_at IS NULL 
       OR ie.last_rotated_at < NOW() - INTERVAL '60 days')
ORDER BY ie.last_rotated_at ASC NULLS FIRST;
```

### 2. Audit Trail Query

```sql
-- Recent credential access for a specific org
SELECT 
  cal.performed_at,
  cal.action,
  cal.performed_by,
  ie.name as portal_name,
  cal.success,
  cal.error_message
FROM credential_audit_log cal
JOIN integration_endpoint ie ON cal.portal_id = ie.portal_id
WHERE ie.org_id = :org_id
  AND cal.performed_at > NOW() - INTERVAL '7 days'
ORDER BY cal.performed_at DESC
LIMIT 100;
```

### 3. Migration Progress

```sql
-- Check migration status
SELECT 
  COUNT(*) as total_portals,
  COUNT(secret_arn) as migrated_portals,
  COUNT(*) - COUNT(secret_arn) as pending_migration,
  ROUND(COUNT(secret_arn)::numeric / COUNT(*)::numeric * 100, 2) as percent_complete
FROM integration_endpoint
WHERE config->>'credentials' IS NOT NULL;
```

## Best Practices

1. **Always use transactions** when updating credential references
2. **Log all credential operations** to the audit table
3. **Never log actual credential values** in audit logs
4. **Use row-level security** if implementing multi-tenant access
5. **Regular backups** of the secret_arn mappings
6. **Monitor for orphaned secrets** (ARNs in DB but not in AWS)

## Rollback Plan

If issues arise during migration:

1. **Stop migration script** immediately
2. **Keep dual-read code** active (reads from both sources)
3. **Investigate and fix** issues
4. **Resume migration** after fixes
5. **If critical failure**, null out secret_arn to force config reads

```sql
-- Emergency rollback
UPDATE integration_endpoint
SET secret_arn = NULL
WHERE portal_id IN (/* affected portal IDs */);
```

---

**Next Steps:** Configure AWS infrastructure ([rcm-cdk/docs/credential_infrastructure.md](../../rcm-cdk/docs/credential_infrastructure.md))