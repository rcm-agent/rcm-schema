# Workflow Schema Fix Summary

## Date: 2025-08-14

## Problem Identified
The workflow execution tables (created in migration 014) were referencing a non-existent `workflow_node` table with BIGINT node IDs, but migration 017 had refactored the schema to use `user_workflow_node` with UUID node IDs.

## Schema Mismatches Fixed

### 1. **workflow_steps** table
- **Before**: `node_id BIGINT` → `workflow_node.node_id`
- **After**: `node_id UUID` → `user_workflow_node.node_id`

### 2. **node_io_requirements** table  
- **Before**: `node_id BIGINT` → `workflow_node.node_id`
- **After**: `node_id UUID` → `user_workflow_node.node_id`

### 3. **workflow_data_bindings** table
- **Before**: `node_id BIGINT` → `workflow_node.node_id`
- **After**: `node_id UUID` → `user_workflow_node.node_id`

### 4. **workflow_trace_screenshot** table
- **Before**: `node_id INTEGER` (no foreign key)
- **After**: `node_id UUID` (no foreign key, for historical data)

## Solution Implemented

### Direct SQL Initialization
Created `init_workflow_tables.sql` that directly creates all workflow execution tables with the correct UUID-based schema, properly referencing `user_workflow_node`.

### SQLAlchemy Models Updated
Modified `/Users/seunghwanlee/rcm-schema/models.py` to reflect the UUID changes:
```python
class WorkflowStep(Base):
    node_id = Column(UUID(as_uuid=True), ForeignKey('user_workflow_node.node_id'))

class NodeIoRequirement(Base):
    node_id = Column(UUID(as_uuid=True), ForeignKey('user_workflow_node.node_id'))

class WorkflowDataBinding(Base):  
    node_id = Column(UUID(as_uuid=True), ForeignKey('user_workflow_node.node_id'))

class WorkflowTraceScreenshot(Base):
    node_id = Column(UUID(as_uuid=True), nullable=False)  # No FK for historical data
```

### Migration Files Created (for future use)
1. **018_fix_workflow_execution_node_references.py** - Alembic migration to fix references
2. **fix_workflow_node_references.sql** - Direct SQL migration script

## Current Database State
✅ All workflow execution tables created with correct UUID schema
✅ Foreign keys properly reference `user_workflow_node`
✅ Indexes created for performance
✅ Test data inserted for validation

## Tables Created
- `user_workflow` - Workflow definitions
- `user_workflow_node` - Workflow-owned nodes (UUID-based)
- `user_workflow_transition` - Node transitions
- `workflow_trace` - Execution traces
- `workflow_steps` - Execution steps (UUID node_id)
- `node_io_requirements` - Node I/O specs (UUID node_id)
- `workflow_data_bindings` - Data bindings (UUID node_id)
- `workflow_trace_screenshot` - Screenshots (UUID node_id)
- `workflow_trace_context` - Trace context
- `workflow_events` - Execution events

## Next Steps for RCM Web Agent
The web agent can now:
1. Track workflow executions using `workflow_trace`
2. Record step execution with proper node references in `workflow_steps`
3. Store screenshots linked to workflow nodes
4. Manage node I/O requirements and data bindings

All tables use UUID-based node references compatible with the frontend expectations.