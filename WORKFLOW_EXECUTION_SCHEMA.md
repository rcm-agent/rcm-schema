# Workflow Execution Schema Documentation

## Overview

This document describes the new workflow execution tables added to the RCM schema (migration 014). These tables provide comprehensive support for multi-channel workflow execution, configuration management, and execution tracking.

## Tables

### 1. **workflow_configs**
Stores versioned workflow configurations with support for different configuration types.

**Key Features:**
- Multi-tenant support via `org_id`
- Configuration versioning with `is_active` flag
- Supports workflow-specific, channel-specific, and global configs
- Audit trail with `created_by` and timestamps

### 2. **channel_configs**
Channel-specific configurations for web, voice, and efax channels.

**Key Features:**
- Organization-scoped channel settings
- Flexible JSON configuration storage
- Active/inactive state management

### 3. **workflow_channel_configs**
Associates workflows with channels and provides channel-specific settings.

**Key Features:**
- Enable/disable channels per workflow
- Priority-based channel selection
- Optional webhook URLs for external integrations

### 4. **node_io_requirements**
Defines input/output requirements for workflow nodes.

**Key Features:**
- Strong typing for node inputs/outputs
- Default values and validation rules
- Required/optional field support

### 5. **workflow_trace**
Main execution tracking table for workflow runs.

**Key Features:**
- Multi-channel execution support (web, voice, efax)
- Status tracking (pending, active, completed, failed, cancelled, timeout)
- Configuration snapshot for execution reproducibility
- Performance metrics (duration_ms)

### 6. **workflow_steps**
Tracks individual step execution within a workflow.

**Key Features:**
- Step-by-step execution tracking
- Input/output data capture
- Retry support with count tracking
- Performance metrics per step

### 7. **workflow_trace_context**
Key-value storage for workflow execution context.

**Key Features:**
- Dynamic context storage during execution
- Supports workflow state persistence
- Updateable key-value pairs

### 8. **workflow_events**
Event log for detailed execution tracking.

**Key Features:**
- Comprehensive event logging
- Links to specific traces and steps
- Timestamped event stream

### 9. **workflow_data_bindings**
Defines data flow between workflow nodes.

**Key Features:**
- Node-to-node data mapping
- Flexible binding configurations
- Support for different binding types

### 10. **config_status**
Tracks which configurations are currently active.

**Key Features:**
- Active configuration tracking
- Configuration activation audit trail
- Multi-entity support

## Key SQL Views

### v_active_workflow_configs
Shows all active workflow configurations with organization and workflow details.

### v_workflow_execution_summary
Provides execution summary with step counts and performance metrics.

### v_workflow_channel_performance
Channel-specific performance metrics including success rates and duration statistics.

### v_node_execution_stats
Node-level execution statistics for identifying bottlenecks.

### v_workflow_execution_timeline
Complete event timeline for workflow executions.

### v_failed_steps_analysis
Analysis view for debugging failed workflow steps.

## Helper Functions

### Execution Management
- `start_workflow_execution()` - Initiates a new workflow execution
- `complete_workflow_execution()` - Marks workflow as complete
- `start_workflow_step()` - Begins execution of a workflow step
- `complete_workflow_step()` - Completes a workflow step
- `retry_workflow_step()` - Retries a failed step

### Context Management
- `set_workflow_context()` - Sets/updates execution context
- `get_workflow_context()` - Retrieves execution context

### Configuration
- `get_active_workflow_config()` - Gets the active configuration for a workflow

### Maintenance
- `cleanup_old_execution_data()` - Removes old execution data based on retention policy

## Usage Examples

### Starting a Workflow Execution
```sql
-- Start a new workflow execution
SELECT start_workflow_execution(
    '123e4567-e89b-12d3-a456-426614174000'::uuid, -- workflow_id
    'web'::workflow_channel,                        -- channel
    'EXT-12345',                                   -- external_id
    '{"config": "data"}'::jsonb,                   -- config_snapshot
    '123e4567-e89b-12d3-a456-426614174001'::uuid  -- created_by user_id
);
```

### Executing Workflow Steps
```sql
-- Start a step
SELECT start_workflow_step(
    1001,                               -- trace_id
    5,                                  -- node_id
    1,                                  -- step_number
    '{"input": "data"}'::jsonb         -- input_data
);

-- Complete a step
SELECT complete_workflow_step(
    2001,                               -- step_id
    'completed'::step_status,           -- status
    '{"output": "data"}'::jsonb,        -- output_data
    NULL                                -- error_message
);
```

### Managing Workflow Context
```sql
-- Set context value
SELECT set_workflow_context(
    1001,                               -- trace_id
    'user_session',                     -- key
    '{"session_id": "abc123"}'::jsonb  -- value
);

-- Get all context for a trace
SELECT * FROM get_workflow_context(1001);

-- Get specific context value
SELECT * FROM get_workflow_context(1001, 'user_session');
```

### Monitoring and Analysis
```sql
-- View execution summary
SELECT * FROM v_workflow_execution_summary 
WHERE workflow_id = '123e4567-e89b-12d3-a456-426614174000'::uuid
ORDER BY start_time DESC
LIMIT 10;

-- Analyze channel performance
SELECT * FROM v_workflow_channel_performance
WHERE workflow_id = '123e4567-e89b-12d3-a456-426614174000'::uuid;

-- Debug failed steps
SELECT * FROM v_failed_steps_analysis
WHERE workflow_id = '123e4567-e89b-12d3-a456-426614174000'::uuid;
```

## Security Considerations

1. **Row Level Security (RLS)** is enabled on sensitive tables:
   - workflow_configs
   - channel_configs
   - workflow_trace
   - workflow_trace_context

2. **Multi-tenant isolation** is enforced through:
   - org_id foreign keys
   - RLS policies based on `app.current_org_id` setting

3. **Audit trail** maintained through:
   - created_by/activated_by user tracking
   - Timestamp tracking on all modifications

## Performance Considerations

1. **Indexes** are created on:
   - Foreign key columns
   - Frequently queried columns (status, channel, timestamps)
   - Composite indexes for common query patterns

2. **Partitioning** considerations:
   - workflow_trace and workflow_events tables may benefit from time-based partitioning
   - Consider partitioning by created_at for large deployments

3. **Data retention**:
   - Use `cleanup_old_execution_data()` function regularly
   - Consider archiving old execution data to cold storage

## Migration Notes

To apply this schema:

1. Run the Alembic migration:
   ```bash
   alembic upgrade 014_add_workflow_execution_tables
   ```

2. Or apply the SQL script directly:
   ```bash
   psql -U your_user -d your_database -f add_workflow_execution_tables.sql
   ```

3. Create views and functions:
   ```bash
   psql -U your_user -d your_database -f workflow_execution_views.sql
   ```

## Future Enhancements

1. **Workflow Templates** - Pre-defined workflow configurations
2. **Execution Replay** - Ability to replay workflow executions
3. **Advanced Analytics** - ML-based performance optimization
4. **Real-time Monitoring** - WebSocket-based execution updates
5. **Workflow Versioning** - Track workflow definition changes over time