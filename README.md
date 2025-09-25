# RCM Schema

Centralized database schema management for the Hybrid RCM platform. This repository provides the complete database schema, ORM models, and utilities that power the RCM automation system across all services.

> **🚀 V8 Migration Update**: The schema has been upgraded to V8 with multi-tenancy, graph-based workflows, and ML capabilities. See [V8 Migration Guide](V8_DEPLOYMENT_GUIDE.md) for details.
> 
> **📊 Workflow Architecture Update**: Migration 017 transforms workflow nodes from shared graph components to workflow-owned nodes, simplifying the architecture by trading node reusability for clearer ownership and easier management.

## Purpose

This repository serves as the single source of truth for the RCM database schema, ensuring consistency across all services (rcm-frontend, rcm-memory, rcm-web-agent, etc.) that share the same database.

## Key Features

### V8 Features (New)
- **Multi-Tenancy**: Complete organization-based data isolation
- **Graph Workflows**: DAG-based workflow execution with nodes and transitions
- **ML Integration**: 768D vector embeddings for semantic search and similarity
- **Flexible Schema**: Lookup tables replacing ENUMs for runtime flexibility
- **Backward Compatibility**: Views maintaining legacy table names

### Core Features
- **Centralized Schema Management**: All database tables, relationships, and constraints defined in one place
- **SQLAlchemy Models**: Complete ORM models for all database tables with SQLAlchemy 2.0+
- **Pydantic Schemas**: Request/response validation schemas for all models
- **Async Database Utilities**: Connection pooling, session management, and RLS support
- **Security Utilities**: Row Level Security helpers for multi-tenant isolation
- **Version Controlled Migrations**: Alembic-based migration system for safe schema evolution
- **Special Migrations**: Scripts for PostgreSQL extensions, RLS policies, and triggers
- **Vector Embeddings**: Support for pgvector with 768D text embeddings
- **Dynamic Workflows**: Task types and field requirements for configurable workflows
- **Hierarchical Requirements**: Three-tier system (Global → Payer → Organization) for field requirements without duplication
- **Industry Standards**: Task actions aligned with HIPAA X12 transaction standards (see [Industry Standard Terminology](docs/industry_standard_terminology.md))

## Prerequisites

- PostgreSQL 16+ with the following extensions:
  - pgcrypto
  - uuid-ossp
  - pgvector (0.5.0+)
- Python 3.9+

> **Note**: Infrastructure (e.g., rcm-cdk) manages the actual PostgreSQL version, while this schema only specifies minimum requirements. See [Version Compatibility Guide](docs/version_compatibility.md) for details.

## Installation

1. Clone the repository:
```bash
git clone <repository-url>
cd rcm-schema
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Set up environment variables:
```bash
cp .env.example .env
# Edit .env with your database connection details
```

## Database Setup

### V8 Migration

To migrate to the V8 schema:

```bash
# Option 1: Full deployment with Docker
cd ../rcm-orchestrator
./deploy_v8.sh

# Option 2: Direct migration
python run_v8_migration.py

# Validate migration
python scripts/validate_v8_migration.py
```

See [V8 Migration Guide](V8_DEPLOYMENT_GUIDE.md) for detailed instructions.

### Quick Start

Initialize the database with schema and sample data:
```bash
python init_db.py
```

This will:
- Create the database if it doesn't exist
- Install required extensions
- Run all migrations
- Load sample data for development

### Production Setup

For production, skip sample data:
```bash
python init_db.py --no-sample-data
```

### Running Migrations Only

To run migrations on an existing database:
```bash
python -m rcm_schema.run_migrations
```

To verify the schema without running migrations:
```bash
python -m rcm_schema.run_migrations --verify-only
```

## Schema Overview

### Core Tables

1. **organization** - Multi-tenant organizations
2. **portal_type** - Portal catalog/templates
3. **integration_endpoint** - Tenant-specific portal configurations

### Workflow Tables (V8 - Migration 017)

4. **user_workflow** - User-defined workflows with DAG structure
5. **user_workflow_node** - Workflow-owned nodes with UUID identifiers (replaced workflow_node)
6. **user_workflow_transition** - Workflow-specific transitions between nodes (replaced workflow_transition)
7. **workflow_revision** - Versioned snapshots of workflow configurations
8. **micro_state** - UI state snapshots with vector embeddings, references user_workflow_node
9. **task_type** - Workflow templates (e.g., eligibility check)
10. **field_requirement** - Dynamic field requirements per task (deprecated - see Hierarchical Requirements)
11. **task_signature** - Workflow execution patterns

### Hierarchical Requirements Tables

12. **payer_requirement** - Payer-level field requirements (e.g., Anthem's standards)
13. **org_requirement_policy** - Organization-specific overrides and additions
14. **requirement_changelog** - Audit trail for all requirement changes
15. **effective_requirements** - Materialized view merging payer + org requirements

### Execution Tables

16. **batch_job** - Batch processing jobs
17. **batch_row** - Individual batch items
18. **workflow_trace** - Execution traces with workflow run tracking

### State Memory Tables

19. **macro_state** - State clustering
20. **rcm_transition** - State transition graph
(Note: micro_state is listed under Workflow Tables as it now references user_workflow_node)

### User Management

21. **app_user** - Application users

## Usage in Services

### Import Models and Schemas

```python
from rcm_schema import (
    # Models
    Organization, TaskType, TaskSignature,
    # Schemas
    OrganizationCreate, TaskTypeSchema,
    # Database utilities
    get_db_manager, get_session
)
```

### Database Session Management

```python
from rcm_schema import get_db_manager

# Initialize database
db_manager = get_db_manager()
await db_manager.initialize()

# Use in async context
async with db_manager.get_session() as session:
    # Your database operations here
    result = await session.execute(...)
```

### Creating Records

```python
from rcm_schema import TaskTypeCreate, TaskType

# Using Pydantic schema for validation
task_data = TaskTypeCreate(
    domain="eligibility",
    action="status_check",
    display_name="Eligibility Verification",
    description="Check patient eligibility"
)

# Create ORM instance
task = TaskType(**task_data.model_dump())
session.add(task)
await session.commit()
```

## Key Design Patterns

### 1. Workflow-Owned Nodes Architecture

- **Pre-v017**: Shared nodes across workflows (like Lego blocks)
- **Post-v017**: Each workflow owns its nodes (simpler but less reusable)
- **Key Changes**:
  - `workflow_node` → `user_workflow_node` with `workflow_id` foreign key
  - `workflow_transition` → `user_workflow_transition` with workflow ownership
  - Field rename: `code` → `label` (human-readable text, not identifiers)
  - UUID-based `node_id` for frontend compatibility
- **Trade-off**: Sacrificed node reusability for clearer ownership and simpler management

### 2. Vector Embeddings

- Text embeddings: 768 dimensions (BGE model)
- Image embeddings: 512 dimensions (SigLIP model)
- Indexed with IVFFlat for fast similarity search

### 3. Task Signature Inheritance

- Portal-type level templates
- Portal-specific overrides via `alias_of`
- Source tracking (human vs AI generated)

### 4. Multi-tenancy

- All tenant data includes `org_id`
- Row Level Security (RLS) policies
- Shared reference data (portal_type)

### 5. Dynamic Field Requirements

- Task types define workflow templates
- ~~Field requirements can be global or portal-specific~~ (deprecated)
- **NEW**: Hierarchical requirements system with three tiers:
  - Global defaults for any task type
  - Payer-specific requirements (e.g., Anthem's standards)
  - Organization-specific overrides and additions
- Full audit trail and versioning support
- See [Hierarchical Requirements Guide](docs/hierarchical_requirements_guide.md) for details

## Development

### Adding New Tables

1. Add model to `models.py`
2. Add Pydantic schemas to `schemas.py`
3. Update imports in `__init__.py`
4. Create migration:
   ```bash
   alembic revision -m "Add new table"
   ```
5. Run migration:
   ```bash
   python -m rcm_schema.run_migrations
   ```

### Testing

Run the test script to verify installation:
```bash
python test_rcm_schema.py
```

## Migrations

### Creating a New Migration

```bash
alembic revision -m "Description of changes"
```

### Running Migrations

```bash
alembic upgrade head
```

### Rollback

```bash
alembic downgrade -1
```

### Hierarchical Requirements Migration

To migrate from the old field_requirement system to the new hierarchical requirements:

```bash
# Run schema migration first
alembic upgrade head

# Then run data migration (dry run)
python migrate_requirements_data.py

# Execute migration
python migrate_requirements_data.py --execute
```

See [Migration Guide](docs/hierarchical_requirements_guide.md#migration-guide) for detailed steps.

## Security Considerations

1. **Multi-tenant Isolation**: Use RLS policies for data isolation
2. **PHI Protection**: Never store unencrypted PHI
3. **Credential Storage**: Use encrypted JSONB for credentials
4. **Audit Trail**: All tables include timestamps

## Documentation

For detailed technical documentation, see the `/docs` folder:

- **[Database Reference Guide](docs/hybrid_rcm_db_guide.md)** - Complete table reference with examples
- **[SQL Schema](docs/hybrid_rcm_schema_v3.sql)** - Full PostgreSQL schema definition
- **[Industry Standard Terminology](docs/industry_standard_terminology.md)** - HIPAA X12 aligned task actions
- **[BPO Process Taxonomy](docs/bpo_process_taxonomy.md)** - Comprehensive BPO process definitions for healthcare outsourcing
- **[LLM Trace Design](docs/llm_trace_design.md)** - Web agent architecture and trace system
- **[Agent Design Spec](docs/Hybrid_RCM_Agent_Design_Spec.md)** - High-level system design

## Architecture Overview

The RCM platform consists of several interconnected services:

### Services
- **rcm-frontend** - User interface for managing workflows
- **rcm-web-agent** - Browser automation with AI-powered state memory
- **rcm-memory** - Semantic memory and embedding management
- **rcm-orchestrator** - Workflow coordination and batch processing

### Key Technologies
- **PostgreSQL 16+** with pgvector for semantic search
- **SQLAlchemy 2.0+** for async ORM
- **Pydantic 2.0+** for data validation
- **Alembic** for database migrations
- **Vector Embeddings** - 768D text (BGE) and 512D image (SigLIP)

## License

[Your License Here]
