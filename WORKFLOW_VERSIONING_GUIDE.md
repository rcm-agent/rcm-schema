# Workflow Versioning Implementation Guide

## Overview

This guide describes the workflow versioning system that enables optimistic locking for autosave functionality, preventing data loss from concurrent edits.

## Features

✅ **Optimistic Locking**: Prevents concurrent edit conflicts  
✅ **Version Tracking**: Each save increments the version number  
✅ **Conflict Detection**: Returns HTTP 409 when versions mismatch  
✅ **Draft Autosave**: Separate draft state with version control  
✅ **Backward Compatible**: Works with existing APIs without breaking changes  

## Architecture

### Database Schema Changes

The migration adds three columns to `user_workflow` table:

1. **`version`** (INTEGER, DEFAULT 1)
   - Tracks the current version number
   - Increments with each successful save
   - Used for optimistic locking

2. **`draft_state`** (JSONB)
   - Stores autosaved draft data
   - Cleared when workflow is published
   - Separate from main workflow_state

3. **`draft_updated_at`** (TIMESTAMPTZ)
   - Timestamp of last draft save
   - Used for autosave tracking

### Stored Procedures

1. **`update_workflow_with_version_check()`**
   - Updates workflow with version validation
   - Returns success/conflict status
   - Atomically increments version

2. **`update_draft_with_version_check()`**
   - Updates draft state with version validation
   - Used for autosave functionality
   - Maintains version consistency

3. **`clear_workflow_draft()`**
   - Clears draft when publishing
   - Helper function for workflow management

## Installation

### Step 1: Navigate to rcm-schema directory
```bash
cd ~/rcm-schema
```

### Step 2: Run the migration
```bash
# Using the script (recommended)
./apply_workflow_versioning.sh

# Or manually with psql
psql -U your_user -d your_database -f add_workflow_versioning.sql
```

### Step 3: Verify installation
```sql
-- Check columns
SELECT column_name, data_type, column_default
FROM information_schema.columns
WHERE table_name = 'user_workflow'
AND column_name IN ('version', 'draft_state', 'draft_updated_at');

-- Check functions
SELECT proname FROM pg_proc
WHERE proname LIKE '%version_check%';
```

## API Usage

### Frontend Implementation

The frontend already has full support through:

#### 1. `useWorkflowVersion` Hook
```typescript
const {
  version,
  versionConflict,
  saveDraftWithVersion,
  resolveConflict
} = useWorkflowVersion();

// Save with version
const result = await saveDraftWithVersion(workflowId, {
  nodes,
  transitions,
  spreadsheetConnections
});

if (!result.success && versionConflict) {
  // Handle conflict
}
```

#### 2. `useAutoSave` Hook
```typescript
const {
  saveStatus,
  lastSavedAt,
  saveNow
} = useAutoSave(
  workflowData,
  saveFunction,
  {
    debounceMs: 10000,  // 10 seconds
    enabled: true
  }
);
```

### API Endpoints

#### Save Draft with Version
```http
POST /api/workflow/draft
Content-Type: application/json

{
  "workflowId": "uuid",
  "nodes": [...],
  "transitions": [...],
  "version": 1  // Optional - enables versioning
}
```

**Responses:**

Success (200):
```json
{
  "success": true,
  "message": "Draft saved",
  "version": 2,
  "savedAt": "2025-01-09T..."
}
```

Conflict (409):
```json
{
  "success": false,
  "message": "Version conflict detected",
  "conflict": true,
  "currentVersion": 3
}
```

#### Get Workflow with Version
```http
GET /api/workflow/draft?workflowId=uuid&includeVersion=true
```

Response:
```json
{
  "success": true,
  "hasDraft": true,
  "draft": {...},
  "version": 2
}
```

## Conflict Resolution

When a version conflict occurs:

1. **Keep Local Changes**
   - Force save with server version
   - Overwrites server data

2. **Keep Server Changes**
   - Discard local changes
   - Reload from server

3. **Merge Changes**
   - Combine both versions
   - Custom merge logic

Example implementation:
```typescript
// In VersionConflictModal component
const handleResolve = async (resolution: 'keepLocal' | 'keepServer' | 'merge') => {
  await resolveConflict(resolution, mergedData);
};
```

## Testing

### Run the test script
```bash
cd ~/rcm-frontend
node test_workflow_versioning.js
```

### Manual testing

1. Open workflow editor in two browser tabs
2. Make changes in both tabs
3. Save in first tab (succeeds)
4. Save in second tab (conflict detected)
5. Choose resolution strategy

## Monitoring

### Check for conflicts in logs
```bash
# Frontend logs
grep "Version conflict" ~/.pm2/logs/rcm-frontend-*.log

# Database queries
psql -U rcm_user -d rcm -c "
  SELECT workflow_id, version, updated_at 
  FROM user_workflow 
  ORDER BY updated_at DESC 
  LIMIT 10;
"
```

### Version statistics
```sql
-- Workflows with high version numbers (lots of edits)
SELECT 
  workflow_id,
  name,
  version,
  updated_at
FROM user_workflow
ORDER BY version DESC
LIMIT 10;

-- Recent draft saves
SELECT 
  workflow_id,
  version,
  draft_updated_at
FROM user_workflow
WHERE draft_state IS NOT NULL
ORDER BY draft_updated_at DESC
LIMIT 10;
```

## Troubleshooting

### Issue: Version conflicts happening too frequently

**Solution**: Increase autosave debounce time
```typescript
useAutoSave(data, save, {
  debounceMs: 30000  // 30 seconds instead of 10
});
```

### Issue: Functions not found error

**Solution**: Ensure migration was applied
```bash
psql -U rcm_user -d rcm -c "\df *version_check*"
```

### Issue: Version not incrementing

**Solution**: Check if version column exists
```sql
\d user_workflow
```

## Performance Considerations

1. **Indexes**: Migration creates indexes on version columns
2. **Lock duration**: Row locks are held briefly during updates
3. **Conflict rate**: Monitor and adjust autosave frequency if needed

## Security

- Version checks prevent race conditions
- Row-level locking ensures data consistency
- No sensitive data in version metadata

## Future Enhancements

Potential improvements:

1. **Version History**: Store all versions for undo/redo
2. **Conflict Analytics**: Track conflict patterns
3. **Smart Merge**: AI-assisted conflict resolution
4. **Real-time Collaboration**: WebSocket-based live editing

## Summary

The versioning system provides:

- ✅ Data integrity through optimistic locking
- ✅ Seamless autosave with conflict detection
- ✅ Zero-downtime migration
- ✅ Backward compatibility
- ✅ Production-ready implementation

No API changes required - just run the migration and versioning activates automatically!