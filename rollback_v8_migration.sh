#!/bin/bash
# RCM V8 Migration Rollback Script
# Use this if you need to rollback the migration

set -e

echo "========================================="
echo "RCM V8 Migration Rollback"
echo "========================================="

# Configuration
DB_HOST="${DB_HOST:-localhost}"
DB_PORT="${DB_PORT:-5432}"
DB_NAME="${DB_NAME:-rcm_db}"
DB_USER="${DB_USER:-postgres}"

echo "WARNING: This will rollback all V8 changes!"
echo "Make sure you have a recent backup before proceeding."
echo ""
read -p "Are you sure you want to rollback? (yes/no): " confirm

if [ "$confirm" != "yes" ]; then
    echo "Rollback cancelled."
    exit 0
fi

echo "Step 1: Running Alembic downgrade..."
cd "$(dirname "$0")"
alembic downgrade 006_add_credential_storage_fields

echo "Step 2: Cleaning up any remaining V8 artifacts..."
psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" <<EOF
-- Drop views if they still exist
DROP VIEW IF EXISTS rcm_user CASCADE;
DROP VIEW IF EXISTS rcm_trace CASCADE;

-- Drop V8 tables if they still exist
DROP TABLE IF EXISTS workflow_trace_endpoint CASCADE;
DROP TABLE IF EXISTS micro_state CASCADE;
DROP TABLE IF EXISTS user_workflow_task_type CASCADE;
DROP TABLE IF EXISTS user_workflow_channel_type CASCADE;
DROP TABLE IF EXISTS user_workflow CASCADE;
DROP TABLE IF EXISTS workflow_transition CASCADE;
DROP TABLE IF EXISTS workflow_node CASCADE;
DROP TABLE IF EXISTS portal_credential CASCADE;
DROP TABLE IF EXISTS endpoint CASCADE;
DROP TABLE IF EXISTS channel_type CASCADE;
DROP TABLE IF EXISTS app_user CASCADE;
DROP TABLE IF EXISTS workflow_trace CASCADE;
DROP TABLE IF EXISTS organization CASCADE;

-- Drop lookup tables
DROP TABLE IF EXISTS user_role_lu CASCADE;
DROP TABLE IF EXISTS requirement_type_lu CASCADE;
DROP TABLE IF EXISTS job_status_lu CASCADE;
DROP TABLE IF EXISTS task_signature_source_lu CASCADE;
DROP TABLE IF EXISTS task_action_lu CASCADE;
DROP TABLE IF EXISTS task_domain_lu CASCADE;

-- Recreate original ENUMs if needed
DO \$\$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'task_domain') THEN
        CREATE TYPE task_domain AS ENUM (
            'eligibility', 'prior_auth', 'claim', 'payment', 'patient',
            'provider', 'billing', 'reporting', 'document'
        );
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'task_action') THEN
        CREATE TYPE task_action AS ENUM (
            'check', 'verify', 'update', 'submit', 'check_status', 'appeal', 'extend',
            'submit_claim', 'status_check', 'resubmit', 'void', 'correct',
            'post', 'reconcile', 'adjust', 'refund',
            'search', 'register', 'update_demographics', 'verify_insurance',
            'credential', 'enroll', 'update_info',
            'generate_statement', 'send_invoice', 'apply_payment',
            'generate_report', 'export_data', 'analyze',
            'upload', 'download', 'parse', 'validate',
            'check_legacy', 'status_check_legacy'
        );
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'job_status') THEN
        CREATE TYPE job_status AS ENUM (
            'pending', 'processing', 'completed', 'failed', 'partially_completed'
        );
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'user_role') THEN
        CREATE TYPE user_role AS ENUM (
            'admin', 'operator', 'viewer', 'api_user'
        );
    END IF;
END\$\$;
EOF

echo "✓ Rollback completed!"
echo ""
echo "Next steps:"
echo "1. Verify your application is working with the previous schema"
echo "2. Check that all data is intact"
echo "3. If you have a backup to restore from a specific point:"
echo "   psql -h $DB_HOST -p $DB_PORT -U $DB_USER -d $DB_NAME < your_backup.sql"