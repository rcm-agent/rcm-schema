# RCM Schema Development Commands

## Database Setup
```bash
# Initialize database with schema and sample data
python init_db.py

# Initialize without sample data (production)
python init_db.py --no-sample-data

# Run migrations on existing database
python run_migrations.py

# Verify schema without running migrations
python run_migrations.py --verify-only
```

## V8 Migration
```bash
# Run V8 migration
python run_v8_migration.py

# Validate V8 migration
python scripts/validate_v8_migration.py

# Rollback V8 migration (if needed)
./rollback_v8_migration.sh
```

## Alembic Migrations
```bash
# Create new migration
alembic revision -m "Description of changes"

# Run migrations
alembic upgrade head

# Rollback one migration
alembic downgrade -1

# Show current migration status
alembic current

# Show migration history
alembic history
```

## Testing
```bash
# Run basic schema test
python test_rcm_schema.py

# Run full test suite
pytest

# Run specific test file
pytest test_basic.py
```

## Environment Setup
```bash
# Copy environment template
cp .env.example .env

# Install Python dependencies
pip install -r requirements.txt

# Install development dependencies
pip install -r requirements-dev.txt
```

## Special Migrations
```bash
# Run special PostgreSQL migrations (extensions, RLS, triggers)
python migrations/run_special_migrations.py
```

## Data Migration
```bash
# Migrate from old field_requirement to hierarchical requirements
python migrate_requirements_data.py --dry-run
python migrate_requirements_data.py --execute
```

## Common Development Tasks
```bash
# Check if connected to correct database
echo $DATABASE_URL

# Access PostgreSQL directly
psql $DATABASE_URL

# List all tables
psql $DATABASE_URL -c "\dt"

# Describe a table
psql $DATABASE_URL -c "\d organization"
```