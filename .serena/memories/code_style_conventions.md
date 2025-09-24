# RCM Schema Code Style and Conventions

## Python Code Style
- **Python 3.9+** with type hints
- **Async/await** patterns for database operations
- **SQLAlchemy 2.0+** declarative style with mapped_column
- **Pydantic 2.0+** for schema validation

## Naming Conventions

### Database Tables
- Snake_case table names: `workflow_node`, `batch_job`
- Lookup tables end with `_lu`: `task_domain_lu`, `user_role_lu`
- Junction tables use both table names: `workflow_trace_endpoint`

### Columns
- Primary keys: `{table_name}_id` or just `id` for UUID keys
- Foreign keys: Reference the full column name from parent table
- Timestamps: `created_at`, `updated_at`, `completed_at`
- Boolean flags: `is_active`, `is_retired`, `has_*`

### SQLAlchemy Models
- PascalCase class names matching table names: `WorkflowNode`, `BatchJob`
- Mixins for common patterns: `TimestampMixin`, `OrgContextMixin`

### Pydantic Schemas
- Suffix with purpose: `TaskTypeCreate`, `OrganizationResponse`
- Use `ConfigDict` for model configuration
- Always validate data at API boundaries

## Code Organization
```
rcm-schema/
├── models.py          # Current SQLAlchemy models
├── models_v8.py       # V8 migration models
├── schemas.py         # Pydantic schemas
├── database.py        # Database connection utilities
├── validators.py      # Custom validators
├── constants.py       # Shared constants
└── migrations/        # Alembic migrations
```

## Best Practices
1. **Always use migrations** - Never modify schema directly in production
2. **Test migrations** - Run up and down migrations in development
3. **Document changes** - Update CHANGELOG.md for schema changes
4. **Maintain backward compatibility** - Use views for legacy interfaces
5. **Use transactions** - Wrap related changes in database transactions

## Type Hints Example
```python
from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID

async def get_organization(
    session: AsyncSession,
    org_id: UUID
) -> Optional[Organization]:
    result = await session.get(Organization, org_id)
    return result
```