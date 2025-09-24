#!/bin/bash
# RCM V8 Database Migration Script
# This script performs the database migration to V8 schema

set -e  # Exit on error

echo "========================================="
echo "RCM Database Migration to V8 Schema"
echo "========================================="

# Configuration
DB_HOST="${DB_HOST:-localhost}"
DB_PORT="${DB_PORT:-5432}"
DB_NAME="${DB_NAME:-rcm_db}"
DB_USER="${DB_USER:-postgres}"
BACKUP_DIR="${BACKUP_DIR:-./backups}"

# Create backup directory
mkdir -p "$BACKUP_DIR"

# Step 1: Create backup
echo "Step 1: Creating database backup..."
BACKUP_FILE="$BACKUP_DIR/rcm_backup_$(date +%Y%m%d_%H%M%S).sql"
pg_dump -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" > "$BACKUP_FILE"
echo "✓ Backup created: $BACKUP_FILE"

# Step 2: Enable pgvector extension
echo "Step 2: Enabling pgvector extension..."
psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" <<EOF
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";
CREATE EXTENSION IF NOT EXISTS "vector";
EOF
echo "✓ Extensions enabled"

# Step 3: Check current migration status
echo "Step 3: Checking current migration status..."
CURRENT_VERSION=$(psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -t -c "SELECT version_num FROM alembic_version;" 2>/dev/null || echo "none")
echo "Current version: $CURRENT_VERSION"

# Step 4: Run Alembic migration
echo "Step 4: Running Alembic migration to V8..."
cd "$(dirname "$0")"
alembic upgrade 007_migrate_v8

# Step 5: Verify migration
echo "Step 5: Verifying migration..."
echo "Checking new tables..."
psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" <<EOF
-- Check if new tables exist
SELECT EXISTS (
    SELECT 1 FROM information_schema.tables 
    WHERE table_name = 'organization'
) as organization_exists,
EXISTS (
    SELECT 1 FROM information_schema.tables 
    WHERE table_name = 'channel_type'
) as channel_type_exists,
EXISTS (
    SELECT 1 FROM information_schema.tables 
    WHERE table_name = 'workflow_node'
) as workflow_node_exists,
EXISTS (
    SELECT 1 FROM information_schema.tables 
    WHERE table_name = 'micro_state'
) as micro_state_exists;

-- Check if backward compatibility views exist
SELECT EXISTS (
    SELECT 1 FROM information_schema.views 
    WHERE table_name = 'rcm_user'
) as rcm_user_view_exists,
EXISTS (
    SELECT 1 FROM information_schema.views 
    WHERE table_name = 'rcm_trace'
) as rcm_trace_view_exists;

-- Check default organization
SELECT org_id, name, org_type FROM organization WHERE name = 'Default Organization';

-- Check lookup tables
SELECT 'task_domain_lu' as table_name, COUNT(*) as row_count FROM task_domain_lu
UNION ALL
SELECT 'task_action_lu', COUNT(*) FROM task_action_lu
UNION ALL
SELECT 'job_status_lu', COUNT(*) FROM job_status_lu
UNION ALL
SELECT 'user_role_lu', COUNT(*) FROM user_role_lu;
EOF

echo "✓ Migration completed successfully!"
echo ""
echo "Next steps:"
echo "1. Test backward compatibility by running: psql -c 'SELECT * FROM rcm_user LIMIT 1;'"
echo "2. Verify your application still works with the compatibility views"
echo "3. Begin updating services to use new table names"
echo ""
echo "To rollback if needed:"
echo "psql -h $DB_HOST -p $DB_PORT -U $DB_USER -d $DB_NAME < $BACKUP_FILE"