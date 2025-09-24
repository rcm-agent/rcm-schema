# Consolidated Workflow Tables Documentation

## Migration 018: Table Consolidation

### Overview
This migration consolidates 8+ workflow execution tables into just 2 main tables for simplicity and performance.

## Before vs After

### Before (8+ tables):
- `workflow_trace` - Main execution record
- `workflow_steps` - Individual steps
- `workflow_events` - Event log
- `workflow_trace_screenshot` - Screenshots
- `workflow_trace_context` - Key-value context
- `workflow_trace_endpoint` - Endpoints used
- `workflow_configs` - Configurations
- `micro_state` - Cache states

### After (2 main tables + 2 renamed):
- `user_workflow_run` - Main execution record (includes context, endpoints)
- `user_workflow_run_step` - Steps (includes events, screenshots)
- `user_workflow_config` - Renamed from workflow_configs
- `user_workflow_cache_state` - Renamed from micro_state

## New Table Structures

### 1. user_workflow_run
The main execution record - one per workflow run.

```sql
CREATE TABLE user_workflow_run (
    run_id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workflow_id     UUID NOT NULL,
    org_id          UUID NOT NULL,
    
    -- Execution info
    status          TEXT NOT NULL DEFAULT 'pending',
    channel         TEXT NOT NULL,  -- 'web', 'voice', 'efax'
    external_id     VARCHAR(255),
    
    -- Timing
    started_at      TIMESTAMPTZ,
    ended_at        TIMESTAMPTZ,
    duration_ms     INTEGER,
    
    -- Consolidated data (replaced separate tables)
    context         JSONB DEFAULT '{}',     -- Was workflow_trace_context
    endpoints_used  JSONB DEFAULT '[]',     -- Was workflow_trace_endpoint
    config_snapshot JSONB,                  -- Active configs at execution
    
    -- Error handling
    error_message   TEXT,
    error_details   JSONB,
    
    -- LLM tracking
    llm_prompt      TEXT,
    llm_response    TEXT,
    llm_model       VARCHAR(100),
    llm_tokens_used INTEGER,
    
    -- Tier system
    tier            SMALLINT,
    tier_reason     TEXT,
    
    -- Metadata
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_by      UUID NOT NULL,
    updated_at      TIMESTAMPTZ
);
```

#### Key Features:
- **context**: JSONB field replaces entire `workflow_trace_context` table
- **endpoints_used**: JSONB array replaces `workflow_trace_endpoint` table
- **config_snapshot**: Captures all active configurations at runtime

### 2. user_workflow_run_step
Steps within a workflow execution.

```sql
CREATE TABLE user_workflow_run_step (
    step_id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id          UUID NOT NULL REFERENCES user_workflow_run(run_id),
    node_id         UUID NOT NULL,
    
    -- Step execution
    step_number     INTEGER NOT NULL,
    status          TEXT DEFAULT 'pending',
    retry_count     INTEGER DEFAULT 0,
    
    -- Timing
    started_at      TIMESTAMPTZ,
    ended_at        TIMESTAMPTZ,
    duration_ms     INTEGER,
    
    -- Data flow
    input_data      JSONB,
    output_data     JSONB,
    
    -- Consolidated arrays (replaced separate tables)
    screenshots     JSONB DEFAULT '[]',     -- Was workflow_trace_screenshot
    events          JSONB DEFAULT '[]',     -- Was workflow_events
    
    -- Error handling
    error_message   TEXT,
    error_details   JSONB,
    
    -- Additional metadata
    metadata        JSONB DEFAULT '{}',
    
    UNIQUE(run_id, step_number)
);
```

#### Key Features:
- **screenshots**: JSONB array replaces entire `workflow_trace_screenshot` table
- **events**: JSONB array replaces entire `workflow_events` table
- All related data stays with its step

## JSONB Structure Examples

### Context (in user_workflow_run)
```json
{
    "user_session": "abc123",
    "correlation_id": "xyz789",
    "retry_attempt": 0,
    "custom_param": "value"
}
```

### Screenshots (in user_workflow_run_step)
```json
[
    {
        "url": "s3://bucket/screenshot1.png",
        "thumbnail_url": "s3://bucket/thumb1.png",
        "timestamp": "2025-01-14T10:30:00Z",
        "action": "click_submit",
        "selector": "#submit-button",
        "element_found": true,
        "confidence": 0.95
    }
]
```

### Events (in user_workflow_run_step)
```json
[
    {
        "type": "page_loaded",
        "timestamp": "2025-01-14T10:30:00Z",
        "data": {
            "url": "https://example.com/login",
            "load_time_ms": 1234
        }
    },
    {
        "type": "element_clicked",
        "timestamp": "2025-01-14T10:30:05Z",
        "data": {
            "selector": "#submit",
            "success": true
        }
    }
]
```

## Benefits of Consolidation

### 1. Simpler Queries
**Before (5+ JOINs):**
```sql
SELECT * FROM workflow_trace t
LEFT JOIN workflow_steps s ON t.trace_id = s.trace_id
LEFT JOIN workflow_events e ON s.step_id = e.step_id
LEFT JOIN workflow_trace_screenshot sc ON t.trace_id = sc.trace_id
LEFT JOIN workflow_trace_context c ON t.trace_id = c.trace_id
WHERE t.trace_id = 123;
```

**After (1 JOIN):**
```sql
SELECT * FROM user_workflow_run r
LEFT JOIN user_workflow_run_step s ON r.run_id = s.run_id
WHERE r.run_id = ?;
```

### 2. Atomic Operations
- Insert/update all step data in one operation
- No risk of orphaned records in separate tables
- Better transaction consistency

### 3. Performance
- Fewer tables to query
- Data locality - related data stored together
- Reduced index overhead
- Better cache utilization

### 4. Maintenance
- Simpler schema to understand
- Fewer foreign key relationships
- Easier backup and restore
- Simpler application code

## Migration Path

### Step 1: Run Migration
```bash
# Using Alembic
alembic upgrade 018_consolidate_workflow_tables

# Or using SQL directly
psql -U postgres -d rcm_db -f consolidate_workflow_tables.sql
```

### Step 2: Verify Migration
```sql
-- Check migrated data
SELECT COUNT(*) FROM user_workflow_run;
SELECT COUNT(*) FROM user_workflow_run_step;

-- Test compatibility views
SELECT * FROM workflow_trace LIMIT 1;
SELECT * FROM workflow_steps LIMIT 1;
```

### Step 3: Update Application Code
- Update imports to use new models
- Update queries to use new table names
- Update insert/update logic for JSONB fields

### Step 4: Drop Old Tables (After Verification)
```sql
-- Only after confirming everything works!
DROP TABLE IF EXISTS workflow_events CASCADE;
DROP TABLE IF EXISTS workflow_trace_screenshot CASCADE;
DROP TABLE IF EXISTS workflow_trace_context CASCADE;
DROP TABLE IF EXISTS workflow_trace_endpoint CASCADE;
DROP TABLE IF EXISTS workflow_steps CASCADE;
DROP TABLE IF EXISTS workflow_trace CASCADE;
```

## Backward Compatibility

Compatibility views are created for old table names:
- `workflow_trace` view → maps to `user_workflow_run`
- `workflow_steps` view → maps to `user_workflow_run_step`

This allows existing code to continue working during transition.

## JSONB Indexing

PostgreSQL GIN indexes are created for efficient JSONB queries:

```sql
-- Search within context
CREATE INDEX idx_run_context_gin ON user_workflow_run 
USING gin(context jsonb_path_ops);

-- Search within events
CREATE INDEX idx_step_events_gin ON user_workflow_run_step 
USING gin(events jsonb_path_ops);

-- Example queries using indexes
SELECT * FROM user_workflow_run 
WHERE context @> '{"correlation_id": "xyz789"}';

SELECT * FROM user_workflow_run_step 
WHERE events @> '[{"type": "error"}]';
```

## Row Level Security

RLS is enabled on new tables for multi-tenancy:

```sql
-- Only see runs from your organization
CREATE POLICY user_workflow_run_org_isolation ON user_workflow_run
FOR ALL
USING (org_id = current_setting('app.current_org_id')::uuid);
```

## Helper Functions in Models

The new SQLAlchemy models include helper methods:

```python
# UserWorkflowRun
run.add_context('key', 'value')
run.get_context('key')
run.add_endpoint('endpoint_id')

# UserWorkflowRunStep
step.add_screenshot(url='...', action='click')
step.add_event('navigation', {'from': '/login', 'to': '/dashboard'})
```

## Summary

This consolidation reduces complexity while maintaining all functionality:
- **From 8+ tables to 2 main tables**
- **JSONB arrays replace separate tables**
- **Better performance through data locality**
- **Simpler queries and maintenance**
- **Backward compatibility through views**

The trade-off of slightly less normalized data is worth the significant simplification and performance benefits.