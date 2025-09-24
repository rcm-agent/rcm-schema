#!/usr/bin/env python3
"""Run database migrations including special scripts.

This script:
1. Runs Alembic migrations
2. Applies RLS policies
3. Creates database triggers
4. Sets up any additional database objects
"""

import asyncio
import os
import sys
from pathlib import Path
import argparse
import logging
from dotenv import load_dotenv
import asyncpg
from alembic.config import Config
from alembic import command

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))
from validators import validate_database_compatibility_async

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()


def run_alembic_migrations(database_url: str, revision: str = "head"):
    """Run Alembic migrations.
    
    Args:
        database_url: PostgreSQL connection string
        revision: Target revision (default: head)
    """
    # Convert to async URL for Alembic
    if database_url.startswith("postgresql://"):
        alembic_url = database_url.replace("postgresql://", "postgresql+asyncpg://")
    else:
        alembic_url = database_url
    
    # Get the directory containing this script
    script_dir = Path(__file__).parent
    alembic_ini = script_dir / "alembic.ini"
    
    # Create Alembic configuration
    alembic_cfg = Config(str(alembic_ini))
    alembic_cfg.set_main_option("sqlalchemy.url", alembic_url)
    
    try:
        # Run migrations
        logger.info(f"Running migrations to revision: {revision}")
        command.upgrade(alembic_cfg, revision)
        logger.info("Alembic migrations completed successfully")
    except Exception as e:
        logger.error(f"Error running Alembic migrations: {e}")
        raise


async def run_special_migrations(database_url: str):
    """Run special migration scripts (RLS, triggers, etc.).
    
    Args:
        database_url: PostgreSQL connection string
    """
    # Convert to asyncpg URL if needed
    if database_url.startswith("postgresql://"):
        db_url = database_url
    else:
        db_url = database_url.replace("postgresql+asyncpg://", "postgresql://")
    
    # Get migrations directory
    script_dir = Path(__file__).parent
    migrations_dir = script_dir / "migrations" / "scripts"
    
    if not migrations_dir.exists():
        logger.warning(f"Migrations directory not found: {migrations_dir}")
        return
    
    try:
        conn = await asyncpg.connect(db_url)
        
        # Get all SQL files in order
        sql_files = sorted(migrations_dir.glob("*.sql"))
        
        for sql_file in sql_files:
            logger.info(f"Running migration script: {sql_file.name}")
            
            # Read and execute SQL file
            with open(sql_file, 'r') as f:
                sql_content = f.read()
            
            try:
                await conn.execute(sql_content)
                logger.info(f"Successfully executed: {sql_file.name}")
            except Exception as e:
                logger.error(f"Error executing {sql_file.name}: {e}")
                # Continue with other scripts even if one fails
                continue
        
        await conn.close()
        logger.info("Special migrations completed")
        
    except Exception as e:
        logger.error(f"Error running special migrations: {e}")
        raise


async def verify_schema(database_url: str):
    """Verify that all expected tables and objects exist.
    
    Args:
        database_url: PostgreSQL connection string
    """
    # Convert to asyncpg URL if needed
    if database_url.startswith("postgresql://"):
        db_url = database_url
    else:
        db_url = database_url.replace("postgresql+asyncpg://", "postgresql://")
    
    try:
        conn = await asyncpg.connect(db_url)
        
        # First validate PostgreSQL compatibility
        await validate_database_compatibility_async(conn)
        
        # Check for expected tables
        expected_tables = [
            'organization', 'portal_type', 'integration_endpoint',
            'task_type', 'field_requirement', 'batch_job', 'batch_row',
            'rcm_state', 'macro_state', 'task_signature', 'rcm_trace',
            'rcm_transition', 'app_user'
        ]
        
        logger.info("Verifying database schema...")
        
        for table in expected_tables:
            exists = await conn.fetchval("""
                SELECT EXISTS (
                    SELECT 1 FROM information_schema.tables 
                    WHERE table_schema = 'public' 
                    AND table_name = $1
                )
            """, table)
            
            if exists:
                logger.info(f"✓ Table exists: {table}")
            else:
                logger.error(f"✗ Table missing: {table}")
        
        # Check for extensions
        extensions = ['pgcrypto', 'uuid-ossp', 'pgvector']
        for ext in extensions:
            exists = await conn.fetchval("""
                SELECT EXISTS (
                    SELECT 1 FROM pg_extension 
                    WHERE extname = $1
                )
            """, ext)
            
            if exists:
                logger.info(f"✓ Extension exists: {ext}")
            else:
                logger.error(f"✗ Extension missing: {ext}")
        
        # Check for custom types
        custom_types = [
            'org_type', 'endpoint_kind', 'task_domain', 'task_action',
            'task_signature_source', 'workflow_type', 'job_status', 'user_role'
        ]
        
        for type_name in custom_types:
            exists = await conn.fetchval("""
                SELECT EXISTS (
                    SELECT 1 FROM pg_type 
                    WHERE typname = $1
                )
            """, type_name)
            
            if exists:
                logger.info(f"✓ Type exists: {type_name}")
            else:
                logger.error(f"✗ Type missing: {type_name}")
        
        await conn.close()
        logger.info("Schema verification completed")
        
    except Exception as e:
        logger.error(f"Error verifying schema: {e}")
        raise


async def main():
    """Main migration runner."""
    parser = argparse.ArgumentParser(description="Run RCM database migrations")
    parser.add_argument(
        "--database-url",
        help="Database URL (overrides DATABASE_URL env var)"
    )
    parser.add_argument(
        "--revision",
        default="head",
        help="Target revision for Alembic (default: head)"
    )
    parser.add_argument(
        "--skip-special",
        action="store_true",
        help="Skip special migration scripts"
    )
    parser.add_argument(
        "--verify-only",
        action="store_true",
        help="Only verify schema, don't run migrations"
    )
    args = parser.parse_args()
    
    # Get database URL
    database_url = args.database_url or os.getenv("DATABASE_URL")
    if not database_url:
        logger.error("DATABASE_URL not provided")
        sys.exit(1)
    
    try:
        if args.verify_only:
            # Just verify schema
            await verify_schema(database_url)
        else:
            # Run migrations
            run_alembic_migrations(database_url, args.revision)
            
            # Run special migrations unless skipped
            if not args.skip_special:
                await run_special_migrations(database_url)
            
            # Verify schema after migrations
            await verify_schema(database_url)
        
        logger.info("Migration process completed successfully!")
        
    except Exception as e:
        logger.error(f"Migration process failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())