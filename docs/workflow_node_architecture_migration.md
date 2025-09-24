# Workflow Node Architecture Migration (v017)

## Overview

This document describes the architectural transformation of workflow nodes from a shared, graph-based design to a workflow-owned node structure, implemented in migration 017.

## Background

### Original Design (Pre-v017)
The original schema followed a pure graph database pattern where:
- **workflow_node** table contained globally shared nodes
- Nodes could be reused across multiple workflows (like Lego blocks)
- **workflow_transition** table defined edges between nodes
- Nodes were identified by BIGINT IDs
- Field was named `code` (misleading as it contained human-readable labels)

### Problem Statement
The elegant shared-node design created a mismatch with pragmatic code expectations:
- Frontend and backend code assumed workflow-owned nodes
- Complex queries were needed to filter nodes per workflow
- Node reusability was theoretical but not used in practice
- The `code` field name was confusing (contained labels, not codes)

## Migration Details

### Schema Changes

#### Table Renames
- `workflow_node` → `user_workflow_node`
- `workflow_transition` → `user_workflow_transition`

#### Structural Changes
1. **Node Ownership**
   - Added `workflow_id` column to `user_workflow_node`
   - Foreign key constraint to `user_workflow` table
   - Each node now belongs to exactly one workflow

2. **UUID Migration**
   - Changed `node_id` from BIGINT to UUID
   - Frontend already used UUID strings for node IDs
   - Maintains compatibility with existing frontend code

3. **Field Rename**
   - `code` → `label` (more accurate naming)
   - Reflects actual content: human-readable text

4. **Transition Updates**
   - Added `workflow_id` to transitions table
   - Updated foreign keys to use UUID node_ids
   - Maintained action_label for transition identification

### Migration Strategy

The migration uses a mapping table approach to preserve data relationships:

```sql
-- Step 1: Create mapping table for UUID conversion
CREATE TEMP TABLE node_id_mapping (
    old_id BIGINT,
    new_id UUID DEFAULT gen_random_uuid(),
    workflow_id UUID
);

-- Step 2: Populate mapping from existing nodes
INSERT INTO node_id_mapping (old_id, workflow_id)
SELECT DISTINCT wn.node_id, uw.workflow_id
FROM workflow_node wn
CROSS JOIN user_workflow uw;

-- Step 3: Create new tables with UUID relationships
CREATE TABLE user_workflow_node (
    node_id UUID PRIMARY KEY,
    workflow_id UUID NOT NULL REFERENCES user_workflow(workflow_id),
    label TEXT NOT NULL,
    -- other fields...
);

-- Step 4: Migrate data using mappings
INSERT INTO user_workflow_node
SELECT new_id, workflow_id, code as label, ...
FROM workflow_node
JOIN node_id_mapping ON old_id = node_id;
```

## Technical Debt Acknowledged

### Trade-offs Made
1. **Lost Node Reusability**
   - Nodes can no longer be shared across workflows
   - Each workflow must define its own nodes
   - Accepted as nodes weren't being reused in practice

2. **Data Duplication**
   - Common patterns must be duplicated per workflow
   - Increases storage requirements
   - Simplifies queries and management

3. **Migration Complexity**
   - One-time UUID conversion adds migration risk
   - Requires careful data mapping
   - Frontend compatibility maintained

### Benefits Gained
1. **Simpler Mental Model**
   - Clear ownership: workflow owns its nodes
   - Easier to understand and maintain
   - Matches actual usage patterns

2. **Better Performance**
   - No complex joins to filter nodes per workflow
   - Direct foreign key relationships
   - Simpler queries

3. **Frontend Compatibility**
   - UUID node_ids match frontend expectations
   - No frontend changes required
   - Consistent type system

## Rollback Plan

If rollback is needed:

```sql
-- Restore original tables from backup
ALTER TABLE user_workflow_node RENAME TO user_workflow_node_backup;
ALTER TABLE user_workflow_transition RENAME TO user_workflow_transition_backup;

-- Recreate original tables
CREATE TABLE workflow_node AS SELECT * FROM workflow_node_backup;
CREATE TABLE workflow_transition AS SELECT * FROM workflow_transition_backup;
```

## Validation

Post-migration validation steps:

1. **Data Integrity**
   - All nodes have valid workflow_id
   - All transitions reference existing nodes
   - No orphaned nodes or transitions

2. **Frontend Compatibility**
   - Node IDs are valid UUIDs
   - API responses match expected format
   - Workflow editor functions correctly

3. **Performance**
   - Query performance improved or maintained
   - No degradation in workflow operations
   - Index usage optimized

## Future Considerations

### Potential Improvements
1. **Template System**
   - Workflow templates for common patterns
   - Copy-on-write for node creation
   - Reduces duplication while maintaining ownership

2. **Soft References**
   - Track node similarity across workflows
   - Enable pattern analysis
   - Support future optimization

3. **Migration Tools**
   - Automated workflow copying
   - Bulk node operations
   - Pattern extraction utilities

## Conclusion

This migration represents a pragmatic choice to align the database schema with actual usage patterns. While it sacrifices theoretical elegance for practical simplicity, it results in a more maintainable and performant system that better matches developer expectations and frontend requirements.