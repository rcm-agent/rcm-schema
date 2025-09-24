# RCM Schema Documentation

This directory contains the technical documentation for the Hybrid RCM platform database schema.

> **🚀 V8 Schema Update**: The schema has been upgraded to V8 with multi-tenancy, graph-based workflows, and ML capabilities. See [V8 Migration Guide](../V8_MIGRATION_GUIDE.md) for details.

## Documents

### Core Schema Documentation
- **[hybrid_rcm_db_guide.md](hybrid_rcm_db_guide.md)** - Database reference with all tables, columns, and example data (V8)
- **[hybrid_rcm_schema_v8.sql](hybrid_rcm_schema_v8.sql)** - Complete PostgreSQL V8 schema definition
- **[hybrid_rcm_schema_v3.sql](hybrid_rcm_schema_v3.sql)** - Legacy V3 schema (deprecated)
- **[hierarchical_requirements_schema_additions.sql](hierarchical_requirements_schema_additions.sql)** - Schema additions for hierarchical requirements (migration 003)
- **[hierarchical_requirements_guide.md](hierarchical_requirements_guide.md)** - Comprehensive guide to the hierarchical requirements system

### V8 Feature Documentation
- **[v8_multi_tenancy_guide.md](v8_multi_tenancy_guide.md)** - Multi-tenant architecture patterns
- **[v8_graph_workflows_guide.md](v8_graph_workflows_guide.md)** - DAG-based workflow system
- **[v8_lookup_tables_guide.md](v8_lookup_tables_guide.md)** - Dynamic lookup table management
- **[v8_micro_states_guide.md](v8_micro_states_guide.md)** - ML-powered state management

### Architecture & Design
- **[llm_trace_design.md](llm_trace_design.md)** - Web agent technical design with trace system (updated for V8)
- **[Hybrid_RCM_Agent_Design_Spec.md](Hybrid_RCM_Agent_Design_Spec.md)** - High-level system architecture

### Operations & Deployment
- **[version_compatibility.md](version_compatibility.md)** - PostgreSQL version requirements and compatibility matrix
- **[v8_migration_cookbook.md](v8_migration_cookbook.md)** - Step-by-step V8 migration examples

## Schema Overview

The RCM V8 schema uses PostgreSQL 16+ with pgvector extension for semantic search and multi-tenant isolation.

### V8 Table Categories

1. **Organization & Multi-Tenancy**
   - `organization` - Multi-tenant organizations with types (hospital, billing_firm, credentialer)
   - `app_user` - Application users with org association (renamed from rcm_user)
   - Row-level security across all tenant tables

2. **Channel & Endpoint Abstraction**
   - `channel_type` - Portal catalog/templates (replaces portal_type)
   - `endpoint` - Organization-specific portal configurations
   - `portal_credential` - Encrypted credentials per endpoint

3. **Graph-Based Workflows**
   - `workflow_node` - DAG nodes for workflow steps
   - `workflow_transition` - Edges defining workflow paths
   - `user_workflow` - Workflow instances with metadata
   - `workflow_trace` - Execution traces (renamed from rcm_trace)
   - `workflow_trace_endpoint` - Multi-endpoint support

4. **Task & Requirements**
   - `task_type` - Workflow templates with lookup-based domains/actions
   - `field_requirement` - Dynamic field requirements (being phased out)
   - `task_signature` - Execution patterns with source tracking
   - Hierarchical requirements system (payer → org overrides)

5. **ML-Powered State Management**
   - `micro_state` - UI states with 768D vector embeddings
   - `macro_state` - State clustering for patterns
   - `rcm_state` - Legacy state table (compatibility)
   - `rcm_transition` - State transition graph

6. **Execution & Processing**
   - `batch_job` - Multi-tenant batch processing
   - `batch_job_item` - Individual batch items (renamed from batch_row)
   - Status tracking via lookup tables

7. **Lookup Tables** (Replacing ENUMs)
   - `task_domain_lu` - Task domains (eligibility, prior_auth, etc.)
   - `task_action_lu` - Task actions (check, submit, appeal, etc.)
   - `job_status_lu` - Job statuses
   - `user_role_lu` - User roles with org context
   - `org_type_lu` - Organization types
   - Additional lookup tables for flexibility

### V8 Key Features

- **Multi-Tenancy**: Complete organization-based isolation with RLS
- **Graph Workflows**: DAG-based execution with parallel processing
- **Vector Embeddings**: 768D for micro-states, 1024D for memory (BGE-M3)
- **Dynamic Schema**: Lookup tables allow runtime extension without migrations
- **Backward Compatibility**: Views maintain legacy table names (rcm_user, rcm_trace)
- **Channel Abstraction**: Flexible portal configuration without code changes
- **ML Integration**: pgvector with HNSW indexing for fast similarity search
- **Audit Trail**: Comprehensive tracking with organization context