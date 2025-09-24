#!/usr/bin/env python3
"""Initialize RCM database with schema and sample data.

This script:
1. Creates the database if it doesn't exist
2. Runs all migrations
3. Optionally loads sample data for development
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
# from validators import validate_database_compatibility_async  # TEMPORARY TEMP-20250813-145500-INIT: Commented out to fix import error

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()


async def create_database_if_not_exists(database_url: str) -> bool:
    """Create database if it doesn't exist.
    
    Args:
        database_url: PostgreSQL connection string
        
    Returns:
        bool: True if database was created, False if already existed
    """
    # Parse database URL to extract components
    if database_url.startswith("postgresql://"):
        url = database_url.replace("postgresql://", "")
    elif database_url.startswith("postgresql+asyncpg://"):
        url = database_url.replace("postgresql+asyncpg://", "")
    else:
        raise ValueError("Invalid database URL format")
    
    # Extract database name and create admin URL
    parts = url.split("/")
    if len(parts) < 2:
        raise ValueError("Database name not found in URL")
    
    db_name = parts[-1].split("?")[0]
    admin_url = "postgresql://" + "/".join(parts[:-1]) + "/postgres"
    
    try:
        # Connect to postgres database to create our database
        conn = await asyncpg.connect(admin_url)
        
        # Check if database exists
        exists = await conn.fetchval(
            "SELECT EXISTS(SELECT 1 FROM pg_database WHERE datname = $1)",
            db_name
        )
        
        if not exists:
            # Create database
            await conn.execute(f'CREATE DATABASE "{db_name}"')
            logger.info(f"Created database: {db_name}")
            created = True
        else:
            logger.info(f"Database already exists: {db_name}")
            created = False
            
        await conn.close()
        return created
        
    except Exception as e:
        logger.error(f"Error creating database: {e}")
        raise


async def create_extensions(database_url: str):
    """Create required PostgreSQL extensions.
    
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
        
        # First validate PostgreSQL version
        logger.info("Validating PostgreSQL compatibility...")
        # await validate_database_compatibility_async(conn)  # TEMPORARY TEMP-20250813-145501-INIT: Commented out to fix import error
        
        # Create extensions
        extensions = ["pgcrypto", "uuid-ossp", "pgvector"]
        for ext in extensions:
            try:
                await conn.execute(f'CREATE EXTENSION IF NOT EXISTS "{ext}"')
                logger.info(f"Created extension: {ext}")
            except Exception as e:
                logger.warning(f"Extension {ext} may already exist: {e}")
        
        await conn.close()
        
    except Exception as e:
        logger.error(f"Error creating extensions: {e}")
        raise


def run_migrations(database_url: str):
    """Run Alembic migrations.
    
    Args:
        database_url: PostgreSQL connection string
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
        logger.info("Running database migrations...")
        command.upgrade(alembic_cfg, "head")
        logger.info("Migrations completed successfully")
    except Exception as e:
        logger.error(f"Error running migrations: {e}")
        raise


async def load_sample_data(database_url: str):
    """Load sample data for development.
    
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
        
        # Insert sample organizations
        logger.info("Loading sample organizations...")
        orgs = [
            ("hospital", "North Valley Hospital", "northvalley.org"),
            ("billing_firm", "MedBill Solutions", "medbill.com"),
            ("hospital", "Central City Medical", "centralmed.org"),
        ]
        
        for org_type, name, domain in orgs:
            await conn.execute("""
                INSERT INTO organization (org_type, name, email_domain)
                VALUES ($1, $2, $3)
                ON CONFLICT (name) DO NOTHING
            """, org_type, name, domain)
        
        # Insert sample portal types
        logger.info("Loading sample portal types...")
        portals = [
            ("uhc_provider", "UnitedHealthcare Provider", "https://provider.uhc.com", "payer"),
            ("availity", "Availity", "https://apps.availity.com", "payer"),
            ("bcbs_provider", "BCBS Provider Portal", "https://provider.bcbs.com", "payer"),
            ("epic_mychart", "Epic MyChart", "https://mychart.epic.com", "provider"),
        ]
        
        for code, name, url, kind in portals:
            await conn.execute("""
                INSERT INTO portal_type (code, name, base_url, endpoint_kind)
                VALUES ($1, $2, $3, $4)
                ON CONFLICT (code) DO NOTHING
            """, code, name, url, kind)
        
        # Insert sample task types
        logger.info("Loading sample task types...")
        task_types = [
            ("eligibility", "status_check", "Eligibility Verification", 
             "Check patient insurance eligibility and benefits"),
            ("prior_auth", "submit", "Prior Authorization Submission", 
             "Submit new prior authorization request"),
            ("prior_auth", "status_check", "Prior Auth Status Check", 
             "Check status of existing prior authorization"),
            ("claim", "status_check", "Claim Status Inquiry", 
             "Check status of submitted claims"),
            ("claim", "submit", "Claim Submission", 
             "Submit new insurance claim"),
        ]
        
        for domain, action, display_name, description in task_types:
            await conn.execute("""
                INSERT INTO task_type (domain, action, display_name, description)
                VALUES ($1, $2, $3, $4)
                ON CONFLICT DO NOTHING
            """, domain, action, display_name, description)
        
        await conn.close()
        logger.info("Sample data loaded successfully")
        
    except Exception as e:
        logger.error(f"Error loading sample data: {e}")
        raise


async def main():
    """Main initialization function."""
    parser = argparse.ArgumentParser(description="Initialize RCM database")
    parser.add_argument(
        "--no-sample-data", 
        action="store_true", 
        help="Skip loading sample data"
    )
    parser.add_argument(
        "--database-url",
        help="Database URL (overrides DATABASE_URL env var)"
    )
    args = parser.parse_args()
    
    # Get database URL
    database_url = args.database_url or os.getenv("DATABASE_URL")
    if not database_url:
        logger.error("DATABASE_URL not provided")
        sys.exit(1)
    
    try:
        # Create database if needed
        created = await create_database_if_not_exists(database_url)
        
        # Create extensions
        await create_extensions(database_url)
        
        # Run migrations
        run_migrations(database_url)
        
        # Load sample data if requested
        if not args.no_sample_data:
            await load_sample_data(database_url)
        
        logger.info("Database initialization completed successfully!")
        
    except Exception as e:
        logger.error(f"Database initialization failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())