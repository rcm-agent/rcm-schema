# Workflow Table Consolidation Migration Summary

## Migration 018: Consolidate Workflow Tables
**Date**: December 2024
**Status**: ✅ Successfully Applied

## Overview
Successfully consolidated 8+ workflow execution tables into 2 main tables with JSONB fields for better performance and simpler architecture.

## Changes Applied

### New Tables Created
1. **`user_workflow_run`** (replaces `workflow_trace`)
   - Main execution record for each workflow run
   - Contains consolidated context and endpoints in JSONB fields
   - Migrated 2 existing workflow runs

2. **`user_workflow_run_step`** (replaces `workflow_steps`)  
   - Individual steps within a workflow execution
   - Contains consolidated screenshots and events in JSONB fields
   - Migrated 10 existing workflow steps

### Data Consolidation
- **`run.context`**: Merged data from `workflow_trace_context` table
- **`run.endpoints_used`**: Would merge from `workflow_trace_endpoint` (table didn't exist)
- **`step.screenshots`**: Merged data from `workflow_trace_screenshot` table
- **`step.events`**: Merged data from `workflow_events` table

### Tables Preserved (Can be dropped after verification)
- `workflow_trace` (2 records)
- `workflow_steps` (10 records)
- `workflow_events` (0 records)
- `workflow_trace_screenshot` (0 records)
- `workflow_trace_context` (0 records)
- `workflow_data_bindings`

## Migration Statistics
- **Workflow Runs Migrated**: 2
- **Workflow Steps Migrated**: 10
- **Events Consolidated**: 0 (no events in old tables)
- **Screenshots Consolidated**: 0 (no screenshots in old tables)

## New Table Structure

### user_workflow_run
```sql
run_id          UUID PRIMARY KEY
workflow_id     UUID (FK to user_workflow)
org_id          UUID (FK to organization)
status          TEXT (pending/running/completed/failed/cancelled/timeout)
channel         TEXT (web/voice/efax)
external_id     VARCHAR(255)
started_at      TIMESTAMPTZ
ended_at        TIMESTAMPTZ
duration_ms     INTEGER
context         JSONB (key-value pairs)
config_snapshot JSONB
endpoints_used  JSONB (array of endpoints)
error_message   TEXT
error_details   JSONB
created_at      TIMESTAMPTZ
created_by      UUID
updated_at      TIMESTAMPTZ
legacy_trace_id BIGINT (temporary for migration)
```

### user_workflow_run_step
```sql
step_id         UUID PRIMARY KEY
run_id          UUID (FK to user_workflow_run)
node_id         UUID (FK to user_workflow_node)
step_number     INTEGER
status          TEXT (pending/running/completed/failed/skipped)
retry_count     INTEGER
started_at      TIMESTAMPTZ
ended_at        TIMESTAMPTZ
duration_ms     INTEGER
input_data      JSONB
output_data     JSONB
screenshots     JSONB (array of screenshot objects)
events          JSONB (array of event objects)
error_message   TEXT
error_details   JSONB
metadata        JSONB
created_at      TIMESTAMPTZ
updated_at      TIMESTAMPTZ
legacy_step_id  BIGINT (temporary for migration)
```

## Benefits Achieved

1. **Simplified Architecture**: Reduced from 8+ tables to 2 main tables
2. **Better Performance**: 
   - Fewer JOINs required
   - GIN indexes on JSONB fields for fast searches
   - Single query can retrieve all execution data

3. **Consistent Naming**: All workflow tables now use `user_workflow_` prefix
4. **Flexible Storage**: JSONB fields allow schema evolution without migrations
5. **Backward Compatibility**: Legacy ID columns preserve relationships during transition

## Next Steps

### Recommended Actions
1. ✅ Verify data migration completeness
2. ⏳ Update application code to use new tables
3. ⏳ Monitor performance for 1-2 weeks
4. ⏳ Drop old tables after verification period

### Optional Cleanup (After Verification)
```sql
-- Drop old tables
DROP TABLE IF EXISTS workflow_events CASCADE;
DROP TABLE IF EXISTS workflow_trace_screenshot CASCADE;
DROP TABLE IF EXISTS workflow_trace_context CASCADE;
DROP TABLE IF EXISTS workflow_trace_endpoint CASCADE;
DROP TABLE IF EXISTS workflow_steps CASCADE;
DROP TABLE IF EXISTS workflow_trace CASCADE;
DROP TABLE IF EXISTS workflow_data_bindings CASCADE;

-- Remove legacy columns
ALTER TABLE user_workflow_run DROP COLUMN legacy_trace_id;
ALTER TABLE user_workflow_run_step DROP COLUMN legacy_step_id;
```

## Files Created
- `/Users/seunghwanlee/rcm-schema/consolidate_workflow_tables_simple.sql` - Applied migration
- `/Users/seunghwanlee/rcm-schema/alembic/versions/018_consolidate_workflow_tables.py` - Alembic version
- `/Users/seunghwanlee/rcm-schema/models_consolidated.py` - New SQLAlchemy models
- `/Users/seunghwanlee/rcm-schema/CONSOLIDATED_WORKFLOW_TABLES.md` - Technical documentation
- `/Users/seunghwanlee/rcm-schema/rollback_consolidation.sql` - Rollback script

## Rollback Plan
If issues arise, use: `/Users/seunghwanlee/rcm-schema/rollback_consolidation.sql`

## Configuration Storage Note
The investigation also revealed that workflow configurations (agent types, etc.) are stored in:
- `user_workflow_node.metadata` JSONB field (contains agent_type, agent_config)
- Not in dedicated columns as originally expected
- This was updated in migrations 015 and 017