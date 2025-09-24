# RCM Schema Database Structure

## Core Table Categories

### 1. Multi-Tenant Core Tables
- **organization**: Root tenant table (org_id is the tenant key)
- **app_user**: Application users (formerly rcm_user)

### 2. Channel & Endpoint Tables
- **channel_type**: Portal catalog (Anthem, UHC, etc.)
- **endpoint**: Organization-specific portal configurations
- **portal_credential**: Encrypted credentials for endpoints

### 3. Graph Workflow Tables
- **workflow_node**: DAG vertices representing workflow steps
- **workflow_transition**: DAG edges defining valid paths
- **user_workflow**: Workflow instances
- **micro_state**: UI states with 768D embeddings

### 4. Task & Requirements Tables
- **task_type**: Workflow templates (eligibility check, prior auth, etc.)
- **field_requirement**: Dynamic field requirements (being phased out)
- **payer_requirement**: Payer-level requirements (new hierarchical system)
- **org_requirement_policy**: Organization-specific overrides

### 5. Execution & Trace Tables
- **workflow_trace**: Execution logs (formerly rcm_trace)
- **batch_job**: Batch processing jobs
- **batch_job_item**: Individual batch items

### 6. Lookup Tables (replacing ENUMs)
- task_domain_lu, task_action_lu, job_status_lu, user_role_lu, etc.

## Key Design Patterns
- All tenant data includes org_id for multi-tenancy
- Lookup tables instead of ENUMs for flexibility
- Vector embeddings for semantic search
- Backward compatibility views for legacy code