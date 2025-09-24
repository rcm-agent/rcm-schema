# Breaking Changes Analysis - UserWorkflowNode Migration

**Date**: 2025-08-14
**Migration**: 017_refactor_workflow_nodes_to_user_owned

## Summary

Changed rcm-schema models.py to use the new V8 workflow architecture with `UserWorkflowNode` and `UserWorkflowTransition` instead of the old `WorkflowNode` and `WorkflowTransition` tables.

## Changes Made

### 1. rcm-schema Updates
✅ **models.py** - Updated to use new workflow models:
- Replaced `WorkflowNode` → `UserWorkflowNode` (UUID primary keys)
- Replaced `WorkflowTransition` → `UserWorkflowTransition` (workflow ownership)
- Updated `UserWorkflow` relationships to include `nodes` and `transitions`
- Fixed `MicroState` to reference `UserWorkflowNode` with UUID foreign key
- Updated `__init__.py` to export new workflow models

✅ **README.md** - Updated documentation:
- Updated Schema Overview section with new table names
- Added migration 017 notice to workflow tables
- Clarified that `micro_state` now references `user_workflow_node`

## Breaking Changes Found & Fixed

### 1. rcm-frontend
**Found**: `/src/app/api/workflow/create-from-json/route.ts`
- ❌ Was using old table names: `workflow_nodes`, `workflow_transitions`
- ❌ Was inserting `code` field instead of `label`
- ❌ Was inserting extra columns (position, style) that don't exist
- ❌ Was using transition_id which doesn't exist in new schema

**Fixed**:
- ✅ Updated to use `user_workflow_node` and `user_workflow_transition`
- ✅ Changed `code` → `label` in INSERT statement
- ✅ Moved position and style into metadata JSONB field
- ✅ Removed transition_id from INSERT (composite primary key used)
- ✅ Changed freq from float to integer

### 2. rcm-web-agent
**Found**: `/src/repositories/workflow_repository.py`
- ⚠️ Was importing from `models_v8` directly instead of proper package
- ✅ Already using `UserWorkflowNode` and `UserWorkflowTransition` classes

**Fixed**:
- ✅ Updated import to use `from rcm_schema import ...` with fallback

**Verified OK**:
- `/src/automation/workflows/workflow_engine.py` - Already using new table names
- `/src/api/workflow_sync_api.py` - Already using new table names

### 3. rcm-orchestrator
**Verified OK**:
- `/models/v8.py` - Has correct `UserWorkflowNode` and `UserWorkflowTransition` classes
- `/api/v2/workflows.py` - Using new models correctly
- All references already updated to new schema

### 4. rcm-memory
**No Issues**: No references to workflow nodes or transitions found

### 5. Other Services
**No Issues**: 
- rcm-mock-portals - No workflow references
- rcm-state-labeler - No workflow references

## Key Schema Differences

| Aspect | Old Schema | New Schema |
|--------|------------|------------|
| **Node Table** | `workflow_node` | `user_workflow_node` |
| **Transition Table** | `workflow_transition` | `user_workflow_transition` |
| **Node ID Type** | BIGINT | UUID |
| **Node Ownership** | Shared across workflows | Workflow-specific (workflow_id FK) |
| **Node Label Field** | `code` | `label` |
| **Transition ID** | Has transition_id | No transition_id (composite PK) |
| **Freq Type** | Could be float | INTEGER only |

## Impact Assessment

### Low Impact Services
- ✅ rcm-orchestrator - Already updated
- ✅ rcm-web-agent - Already updated (just import fix)
- ✅ rcm-memory - No workflow usage
- ✅ rcm-mock-portals - No workflow usage
- ✅ rcm-state-labeler - No workflow usage

### Medium Impact Services
- ⚠️ rcm-frontend - One API route needed updates (fixed)

## Testing Recommendations

1. **Database Migration**:
   - Run migration 017 if not already applied
   - Verify new tables exist: `user_workflow_node`, `user_workflow_transition`
   - Check old tables can be dropped: `workflow_node`, `workflow_transition`

2. **Frontend Testing**:
   - Test workflow creation from JSON (`/api/workflow/create-from-json`)
   - Verify nodes are created with UUID IDs
   - Check metadata contains position and style

3. **Integration Testing**:
   - Create a workflow through frontend
   - Execute workflow through web-agent
   - Verify workflow traces are created correctly

## Conclusion

The migration to `UserWorkflowNode` and `UserWorkflowTransition` had minimal breaking changes:
- Only one frontend API route required updates (now fixed)
- Most services were already using the new schema or don't use workflows
- The changes follow simple, scalable patterns without over-engineering