# User-Organization Many-to-Many Migration

## Overview

This migration converts the direct foreign key relationship between users and organizations to a many-to-many relationship using an association table. This allows users to belong to multiple organizations while maintaining a primary organization designation.

## Changes Made

### 1. Database Schema Changes

#### Removed from `app_user` table:
- `org_id` column (foreign key to organization)
- OrgContextMixin dependency

#### Added `user_organization` table:
```sql
CREATE TABLE user_organization (
    user_id UUID NOT NULL,
    org_id UUID NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT true,
    is_primary BOOLEAN NOT NULL DEFAULT false,
    joined_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ,
    PRIMARY KEY (user_id, org_id)
);
```

### 2. Model Changes

#### AppUser model:
```python
# Before:
class AppUser(Base, OrgContextMixin, TimestampMixin):
    # Direct org_id from OrgContextMixin
    organization = relationship('Organization', back_populates='users')

# After:
class AppUser(Base, TimestampMixin):
    # No more OrgContextMixin
    organizations = relationship('UserOrganization', back_populates='user')
```

#### Organization model:
```python
# Before:
users = relationship('AppUser', back_populates='organization')

# After:
user_associations = relationship('UserOrganization', back_populates='organization')
```

#### New UserOrganization model:
```python
class UserOrganization(Base, TimestampMixin):
    """Association table for many-to-many relationship between users and organizations."""
    user_id = Column(PostgreUUID(as_uuid=True), ForeignKey(...), primary_key=True)
    org_id = Column(PostgreUUID(as_uuid=True), ForeignKey(...), primary_key=True)
    is_active = Column(Boolean, nullable=False, default=True)
    is_primary = Column(Boolean, nullable=False, default=False)
    joined_at = Column(DateTime(timezone=True), server_default=func.now())
```

### 3. Key Features

1. **Multiple Organizations**: Users can now belong to multiple organizations
2. **Primary Organization**: Each user can have one primary organization (enforced by unique constraint)
3. **Active Status**: Track whether a user is currently active in an organization
4. **Join History**: Track when users joined each organization
5. **Cascade Deletes**: Deleting a user or organization automatically removes the associations

### 4. Migration Process

1. Creates the new `user_organization` table
2. Migrates existing user-org relationships (marking them as primary)
3. Removes the `org_id` column from `app_user`
4. Creates necessary indexes for performance

### 5. Usage Examples

#### Adding a user to an organization:
```python
# Create association
user_org = UserOrganization(
    user_id=user.user_id,
    org_id=org.org_id,
    is_primary=True  # First org is primary
)
session.add(user_org)
```

#### Finding a user's organizations:
```python
# Get all organizations for a user
user_orgs = session.query(UserOrganization).filter_by(
    user_id=user_id,
    is_active=True
).all()

# Get primary organization
primary_org = session.query(UserOrganization).filter_by(
    user_id=user_id,
    is_primary=True
).first()
```

#### Finding users in an organization:
```python
# Get all active users in an organization
org_users = session.query(UserOrganization).filter_by(
    org_id=org_id,
    is_active=True
).all()
```

### 6. Backward Compatibility Considerations

Applications that expect a direct `user.org_id` will need to be updated to use the association table. Consider adding helper properties to the AppUser model:

```python
@property
def primary_org_id(self):
    primary = next((uo for uo in self.organizations if uo.is_primary), None)
    return primary.org_id if primary else None
```

### 7. Migration Files

- **Alembic Migration**: `alembic/versions/009_add_user_organization_table.py`
- **Direct SQL**: `migrations/add_user_organization_table.sql`
- **Models**: Updated in `models.py`

### 8. Running the Migration

```bash
# Using Alembic
alembic upgrade head

# Using direct SQL
psql -U username -d database_name -f migrations/add_user_organization_table.sql
```

### 9. Rollback

The migration includes rollback support to restore the previous schema if needed. The rollback will:
1. Add `org_id` column back to `app_user`
2. Restore primary organization relationships
3. Drop the `user_organization` table