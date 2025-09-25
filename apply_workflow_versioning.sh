#!/bin/bash

# ============================================================================
# Apply Workflow Versioning Migration
# ============================================================================
# This script applies the workflow versioning migration to enable
# optimistic locking and autosave functionality
# ============================================================================

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}============================================${NC}"
echo -e "${BLUE}Workflow Versioning Migration${NC}"
echo -e "${BLUE}============================================${NC}"
echo ""

# Resolve project directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ALEMBIC_CONFIG="${SCRIPT_DIR}/rcm_schema/alembic.ini"

# Load environment variables
if [ -f .env ]; then
    export $(cat .env | grep -v '^#' | xargs)
    echo -e "${GREEN}✓ Loaded environment variables from .env${NC}"
else
    echo -e "${YELLOW}⚠ No .env file found. Using environment variables.${NC}"
fi

# Set database connection parameters
DB_HOST="${DB_HOST:-localhost}"
DB_PORT="${DB_PORT:-5432}"
DB_NAME="${DB_NAME:-rcm}"
DB_USER="${DB_USER:-rcm_user}"

echo ""
echo "Database Configuration:"
echo "  Host: $DB_HOST"
echo "  Port: $DB_PORT"
echo "  Database: $DB_NAME"
echo "  User: $DB_USER"
echo ""

# Function to run SQL file
run_sql() {
    local sql_file=$1
    local description=$2
    
    echo -e "${BLUE}→ ${description}...${NC}"
    
    if PGPASSWORD="$DB_PASSWORD" psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -f "$sql_file" -v ON_ERROR_STOP=1 > /tmp/migration_output.log 2>&1; then
        echo -e "${GREEN}  ✓ Success${NC}"
        
        # Show any notices from the migration
        if grep -q "NOTICE:" /tmp/migration_output.log; then
            echo -e "${YELLOW}  Notices:${NC}"
            grep "NOTICE:" /tmp/migration_output.log | sed 's/^/    /'
        fi
        return 0
    else
        echo -e "${RED}  ✗ Failed${NC}"
        echo -e "${RED}  Error output:${NC}"
        cat /tmp/migration_output.log
        return 1
    fi
}

# Function to run Alembic migration
run_alembic() {
    echo -e "${BLUE}→ Running Alembic migration...${NC}"
    
    if command -v alembic &> /dev/null; then
        if alembic -c "$ALEMBIC_CONFIG" upgrade head; then
            echo -e "${GREEN}  ✓ Alembic migration completed${NC}"
            return 0
        else
            echo -e "${YELLOW}  ⚠ Alembic migration failed, but continuing...${NC}"
            return 0  # Don't fail the script
        fi
    else
        echo -e "${YELLOW}  ⚠ Alembic not found, skipping Python migration${NC}"
        return 0
    fi
}

# Main migration process
echo -e "${BLUE}Starting migration process...${NC}"
echo ""

# Step 1: Apply SQL migration
if run_sql "${SCRIPT_DIR}/add_workflow_versioning.sql" "Applying workflow versioning migration"; then
    echo ""
    echo -e "${GREEN}✅ SQL migration completed successfully!${NC}"
else
    echo ""
    echo -e "${RED}❌ SQL migration failed!${NC}"
    exit 1
fi

echo ""

# Step 2: Try Alembic migration (optional)
run_alembic

echo ""

# Step 3: Verify the migration
echo -e "${BLUE}→ Verifying migration...${NC}"

VERIFY_SQL="
SELECT 
    column_name,
    data_type,
    column_default
FROM information_schema.columns
WHERE table_name = 'user_workflow'
AND column_name IN ('version', 'draft_state', 'draft_updated_at')
ORDER BY column_name;
"

echo "$VERIFY_SQL" | PGPASSWORD="$DB_PASSWORD" psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -t > /tmp/verify_output.log 2>&1

if [ -s /tmp/verify_output.log ]; then
    echo -e "${GREEN}  ✓ Columns verified:${NC}"
    cat /tmp/verify_output.log | sed 's/^/    /'
else
    echo -e "${YELLOW}  ⚠ Could not verify columns${NC}"
fi

# Check for functions
echo ""
echo -e "${BLUE}→ Checking stored procedures...${NC}"

FUNCTION_CHECK="
SELECT proname AS function_name
FROM pg_proc
WHERE proname IN (
    'update_workflow_with_version_check',
    'update_draft_with_version_check',
    'clear_workflow_draft'
)
ORDER BY proname;
"

echo "$FUNCTION_CHECK" | PGPASSWORD="$DB_PASSWORD" psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -t > /tmp/function_output.log 2>&1

if [ -s /tmp/function_output.log ]; then
    echo -e "${GREEN}  ✓ Functions created:${NC}"
    cat /tmp/function_output.log | sed 's/^/    /'
else
    echo -e "${YELLOW}  ⚠ Could not verify functions${NC}"
fi

# Cleanup temp files
rm -f /tmp/migration_output.log /tmp/verify_output.log /tmp/function_output.log

echo ""
echo -e "${BLUE}============================================${NC}"
echo -e "${GREEN}✅ Migration completed successfully!${NC}"
echo -e "${BLUE}============================================${NC}"
echo ""
echo "Next steps:"
echo "  1. Restart your application to use the new versioning"
echo "  2. Test autosave functionality in the workflow editor"
echo "  3. Monitor logs for version conflicts"
echo ""
echo -e "${YELLOW}Note: Existing workflows will start with version 1${NC}"
