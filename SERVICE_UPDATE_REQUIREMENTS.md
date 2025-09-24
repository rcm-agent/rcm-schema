# Service Update Requirements for Workflow Node Architecture Migration

## Current Status

The workflow node architecture has been migrated in rcm-schema (migration 017), but **NOT ALL SERVICES ARE USING THE CORRECT MAPPINGS**.

## Issues Found

### 1. **rcm-frontend** ❌
- Still using `code` field instead of `label`
- TypeScript interfaces need updating:
  - `WorkflowNode.code` → `WorkflowNode.label`
  - All API request interfaces need field rename

### 2. **rcm-memory** ❌
- Importing non-existent `WorkflowNode` from local models
- Files affected:
  - `/src/services/vector_search.py` - imports WorkflowNode
  - `/src/api/v2/micro_states.py` - imports and uses WorkflowNode
- Should use `UserWorkflowNode` from rcm-schema models_v8

### 3. **rcm-web-agent** ❌
- Using old table names in SQL queries
- Files affected:
  - `/src/api/workflow_sync_api.py` - queries `workflow_node` table
  - `/src/automation/workflows/workflow_engine.py` - queries `workflow_node` table
  - `/src/services/workflow_mapping_engine.py` - INSERT/DELETE on `workflow_node` table
- Should query `user_workflow_node` and `user_workflow_transition` tables

### 4. **rcm-orchestrator** ❌
- Importing from non-existent `models.v8`
- Files affected:
  - `/tests/test_v8_integration.py` - imports from models.v8
  - `/api/v2/workflows.py` - imports WorkflowNode from local models
- Models not aligned with rcm-schema v8

## Required Updates

### Step 1: Update rcm-schema imports
All services should import from rcm-schema models_v8:
```python
from rcm_schema.models_v8 import (
    UserWorkflowNode,  # Not WorkflowNode
    UserWorkflowTransition,  # Not WorkflowTransition
    UserWorkflow,
    MicroState
)
```

### Step 2: Update SQL queries
Replace all direct SQL queries:
```sql
-- OLD
SELECT * FROM workflow_node WHERE ...
SELECT * FROM workflow_transition WHERE ...

-- NEW
SELECT * FROM user_workflow_node WHERE ...
SELECT * FROM user_workflow_transition WHERE ...
```

### Step 3: Update field names
```python
# OLD
node.code = "some_label"

# NEW
node.label = "some_label"
```

### Step 4: Update TypeScript interfaces
```typescript
// OLD
interface WorkflowNode {
  node_id: string;
  code: string;
  // ...
}

// NEW
interface UserWorkflowNode {
  node_id: string;
  workflow_id: string;  // Added
  label: string;        // Renamed from code
  // ...
}
```

## Migration Path

1. **First**: Update all imports to use rcm-schema models_v8
2. **Second**: Update all SQL queries to use new table names
3. **Third**: Update all field references from `code` to `label`
4. **Fourth**: Add `workflow_id` to all node operations
5. **Finally**: Test all services together

## Testing Checklist

- [ ] rcm-frontend can create/edit workflows
- [ ] rcm-memory can store/retrieve micro states
- [ ] rcm-web-agent can execute workflows
- [ ] rcm-orchestrator can coordinate workflow runs
- [ ] All services use consistent table/field names

## Notes

- The migration preserves data through UUID mapping
- Old tables (`workflow_node`, `workflow_transition`) should be dropped after migration
- Each workflow now owns its nodes (no sharing between workflows)
- This is a breaking change requiring coordinated deployment