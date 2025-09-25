#!/usr/bin/env python3
"""Run special migrations that Alembic can't handle automatically.

This includes:
- PostgreSQL extensions (requires superuser)
- Row Level Security policies
- Trigger functions
"""

import os
import sys
import asyncio
import logging
from pathlib import Path
from typing import List, Optional
import asyncpg
from asyncpg import Connection

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from rcm_schema.database import get_db_manager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class SpecialMigrationRunner:
    """Runs SQL scripts that require special handling."""
    
    def __init__(self, database_url: Optional[str] = None):
        self.database_url = database_url or os.getenv("DATABASE_URL")
        if not self.database_url:
            raise ValueError("DATABASE_URL not provided")
        
        # Convert to asyncpg URL
        if self.database_url.startswith("postgresql://"):
            self.database_url = self.database_url
        elif self.database_url.startswith("postgresql+asyncpg://"):
            self.database_url = self.database_url.replace("postgresql+asyncpg://", "postgresql://")
    
    async def run_script(self, script_path: Path, conn: Connection) -> None:
        """Run a single SQL script.
        
        Args:
            script_path: Path to SQL script
            conn: Database connection
        """
        logger.info(f"Running script: {script_path.name}")
        
        try:
            # Read script
            sql = script_path.read_text()
            
            # Execute script
            await conn.execute(sql)
            
            logger.info(f"✓ Script {script_path.name} completed successfully")
            
        except Exception as e:
            logger.error(f"✗ Script {script_path.name} failed: {e}")
            raise
    
    async def check_superuser(self, conn: Connection) -> bool:
        """Check if current user is superuser.
        
        Args:
            conn: Database connection
            
        Returns:
            bool: True if superuser
        """
        result = await conn.fetchval(
            "SELECT rolsuper FROM pg_roles WHERE rolname = current_user"
        )
        return bool(result)
    
    async def run_all_scripts(self, scripts_dir: Path) -> None:
        """Run all scripts in order.
        
        Args:
            scripts_dir: Directory containing SQL scripts
        """
        # Get all SQL scripts sorted by name
        scripts = sorted(scripts_dir.glob("*.sql"))
        
        if not scripts:
            logger.warning(f"No SQL scripts found in {scripts_dir}")
            return
        
        # Connect to database
        logger.info(f"Connecting to database...")
        conn = await asyncpg.connect(self.database_url)
        
        try:
            # Check permissions for extensions
            is_superuser = await self.check_superuser(conn)
            
            # Run each script
            for script_path in scripts:
                # Skip extension script if not superuser
                if "extensions" in script_path.name and not is_superuser:
                    logger.warning(
                        f"⚠️  Skipping {script_path.name} - requires superuser. "
                        "Please run this script manually with appropriate privileges."
                    )
                    continue
                
                await self.run_script(script_path, conn)
            
            logger.info("✅ All scripts completed successfully")
            
        finally:
            await conn.close()
    
    async def verify_extensions(self) -> List[str]:
        """Verify required extensions are installed.
        
        Returns:
            List of missing extensions
        """
        required_extensions = ['pgcrypto', 'uuid-ossp', 'pgvector']
        missing = []
        
        conn = await asyncpg.connect(self.database_url)
        try:
            for ext in required_extensions:
                result = await conn.fetchval(
                    "SELECT 1 FROM pg_extension WHERE extname = $1",
                    ext
                )
                if not result:
                    missing.append(ext)
            
            return missing
            
        finally:
            await conn.close()


async def main():
    """Run special migrations."""
    runner = SpecialMigrationRunner()
    
    # Scripts directory
    scripts_dir = Path(__file__).parent / "scripts"
    
    # Run all scripts
    await runner.run_all_scripts(scripts_dir)
    
    # Verify extensions
    missing_extensions = await runner.verify_extensions()
    if missing_extensions:
        logger.warning(
            f"⚠️  Missing extensions: {', '.join(missing_extensions)}. "
            "Please install these extensions manually."
        )


if __name__ == "__main__":
    asyncio.run(main())