# Workflow Type Migration Preview

## Summary
This migration replaces the `workflow_type` enum with a proper foreign key relationship to the `task_type` table.

## Changes Made

### 1. Model Changes
- **BatchJob**: Replaced `workflow_type` enum column with `task_type_id` foreign key
- **RcmTrace**: Removed `workflow_type` column entirely
- **Removed**: `WorkflowType` enum class

### 2. Schema Changes
- **BatchJobBase**: Changed `workflow_type: WorkflowType` to `task_type_id: UUID`
- **BatchJob**: Added `task_type: Optional[TaskType]` for joined queries
- **RcmTraceBase**: Removed `workflow_type: str` field

### 3. Migration Strategy

#### Data Migration Logic
The migration creates "legacy" task_type records to map existing workflow_type values:

| Old workflow_type | New task_type |
|-------------------|---------------|
| 'eligibility' | domain='eligibility', action='check_legacy' |
| 'claim_status' | domain='claim', action='status_check_legacy' |
| 'prior_auth' | domain='prior_auth', action='check_legacy' |

#### Migration Steps
1. Add nullable `task_type_id` column to batch_job
2. Create legacy task_type records for migration
3. Update all batch_job records to reference appropriate task_type
4. Make task_type_id NOT NULL and add foreign key
5. Drop workflow_type columns from both tables
6. Drop workflow_type enum

## Benefits

1. **Consistency**: Follows established "task" naming pattern
2. **Flexibility**: Batch jobs can reference specific task types with both domain AND action
3. **Better Analytics**: Can track batch jobs by specific workflows, not just domains
4. **Cleaner Schema**: Eliminates redundant enum that duplicated task_domain

## Example Usage After Migration

```python
# Before: Only knew the domain
batch_job.workflow_type = 'claim_status'  # Just a string

# After: Full task type information
batch_job.task_type.domain = 'claim'
batch_job.task_type.action = 'status_check'
batch_job.task_type.display_name = 'Claim Status Verification'
batch_job.task_type.description = 'Check the current status of a submitted claim'

# Can query specific workflows
session.query(BatchJob)\
    .join(TaskType)\
    .filter(TaskType.domain == 'claim', TaskType.action == 'appeal')
```

## Rollback Plan
The migration includes a full downgrade path that:
1. Recreates the workflow_type enum
2. Maps task_type references back to workflow_type values
3. Restores original column structure
Note: Some data loss is possible (multiple task_types → one workflow_type)