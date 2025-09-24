"""Async database connection and session management utilities."""

import os
from typing import AsyncGenerator, Optional
from contextlib import asynccontextmanager
from sqlalchemy.ext.asyncio import (
    AsyncSession, 
    AsyncEngine,
    create_async_engine,
    async_sessionmaker
)
from sqlalchemy.pool import NullPool, QueuePool
from sqlalchemy import text
import logging
import asyncpg

from .validators import validate_database_compatibility_async

logger = logging.getLogger(__name__)


class DatabaseManager:
    """Manages async database connections with connection pooling."""
    
    def __init__(self, database_url: Optional[str] = None):
        """Initialize database manager.
        
        Args:
            database_url: PostgreSQL connection string. If not provided,
                         will use DATABASE_URL environment variable.
        """
        self.database_url = database_url or os.getenv("DATABASE_URL")
        if not self.database_url:
            raise ValueError("DATABASE_URL not provided or set in environment")
        
        # Convert to async URL if needed
        if self.database_url.startswith("postgresql://"):
            self.database_url = self.database_url.replace(
                "postgresql://", "postgresql+asyncpg://"
            )
        elif not self.database_url.startswith("postgresql+asyncpg://"):
            raise ValueError("Database URL must be PostgreSQL")
        
        self._engine: Optional[AsyncEngine] = None
        self._sessionmaker: Optional[async_sessionmaker] = None
    
    async def initialize(self, **engine_kwargs):
        """Initialize the database engine and session factory.
        
        Args:
            **engine_kwargs: Additional arguments for create_async_engine
        """
        if self._engine is not None:
            return
        
        # Default engine configuration
        default_config = {
            "echo": os.getenv("SQL_ECHO", "false").lower() == "true",
            "pool_size": int(os.getenv("DB_POOL_SIZE", "5")),
            "max_overflow": int(os.getenv("DB_MAX_OVERFLOW", "10")),
            "pool_timeout": int(os.getenv("DB_POOL_TIMEOUT", "30")),
            "pool_recycle": int(os.getenv("DB_POOL_RECYCLE", "3600")),
            "pool_pre_ping": True,  # Verify connections before use
        }
        
        # Use NullPool for serverless environments
        if os.getenv("SERVERLESS", "false").lower() == "true":
            default_config["poolclass"] = NullPool
            default_config.pop("pool_size", None)
            default_config.pop("max_overflow", None)
        
        # Merge with provided kwargs
        config = {**default_config, **engine_kwargs}
        
        # Create engine
        self._engine = create_async_engine(self.database_url, **config)
        
        # Create session factory
        self._sessionmaker = async_sessionmaker(
            self._engine,
            class_=AsyncSession,
            expire_on_commit=False,
            autoflush=False,
            autocommit=False
        )
        
        # Test connection and validate compatibility
        try:
            async with self._engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
                logger.info("Database connection established")
                
                # Validate PostgreSQL version and extensions
                raw_conn = await conn.get_raw_connection()
                asyncpg_conn = raw_conn.connection  # Get asyncpg connection
                await validate_database_compatibility_async(asyncpg_conn)
                
        except Exception as e:
            logger.error(f"Failed to connect to database: {e}")
            await self.close()
            raise
    
    async def close(self):
        """Close the database engine."""
        if self._engine:
            await self._engine.dispose()
            self._engine = None
            self._sessionmaker = None
            logger.info("Database connection closed")
    
    @asynccontextmanager
    async def get_session(self) -> AsyncGenerator[AsyncSession, None]:
        """Get an async database session.
        
        Yields:
            AsyncSession: Database session for executing queries
            
        Example:
            async with db_manager.get_session() as session:
                result = await session.execute(select(User))
                users = result.scalars().all()
        """
        if self._sessionmaker is None:
            await self.initialize()
        
        async with self._sessionmaker() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise
            finally:
                await session.close()
    
    @asynccontextmanager
    async def transaction(self):
        """Get a session with explicit transaction control.
        
        Example:
            async with db_manager.transaction() as session:
                # All operations in transaction
                await session.execute(...)
                # Commits on exit, rolls back on exception
        """
        async with self.get_session() as session:
            async with session.begin():
                yield session
    
    async def execute_with_rls(
        self, 
        session: AsyncSession, 
        org_id: str,
        query
    ):
        """Execute a query with Row Level Security context.
        
        Args:
            session: Database session
            org_id: Organization ID for RLS context
            query: SQLAlchemy query to execute
            
        Returns:
            Query result
        """
        # Set RLS context
        await session.execute(
            text("SET LOCAL app.current_org_id = :org_id"),
            {"org_id": org_id}
        )
        
        # Execute query
        return await session.execute(query)
    
    async def health_check(self) -> bool:
        """Check if database is accessible.
        
        Returns:
            bool: True if database is healthy
        """
        try:
            async with self.get_session() as session:
                result = await session.execute(text("SELECT 1"))
                return result.scalar() == 1
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return False


# Global database manager instance
_db_manager: Optional[DatabaseManager] = None


def get_db_manager() -> DatabaseManager:
    """Get the global database manager instance.
    
    Returns:
        DatabaseManager: Global database manager
    """
    global _db_manager
    if _db_manager is None:
        _db_manager = DatabaseManager()
    return _db_manager


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """Get a database session from the global manager.
    
    Yields:
        AsyncSession: Database session
        
    Example:
        async with get_session() as session:
            result = await session.execute(select(User))
    """
    db_manager = get_db_manager()
    async with db_manager.get_session() as session:
        yield session


async def set_org_context(session: AsyncSession, org_id: str):
    """Set organization context for Row Level Security.
    
    Args:
        session: Database session
        org_id: Organization ID to set as context
        
    Example:
        async with get_session() as session:
            await set_org_context(session, user.org_id)
            # All queries now filtered by org_id
            result = await session.execute(select(Portal))
    """
    await session.execute(
        text("SET LOCAL app.current_org_id = :org_id"),
        {"org_id": org_id}
    )


@asynccontextmanager
async def with_org_context(org_id: str):
    """Context manager that sets org context for the session.
    
    Args:
        org_id: Organization ID to set as context
        
    Yields:
        AsyncSession: Database session with org context set
        
    Example:
        async with with_org_context(user.org_id) as session:
            # All queries automatically filtered by org_id
            result = await session.execute(select(Portal))
    """
    async with get_session() as session:
        await set_org_context(session, org_id)
        yield session


async def init_db():
    """Initialize the global database manager.
    
    Should be called during application startup.
    """
    db_manager = get_db_manager()
    await db_manager.initialize()


async def close_db():
    """Close the global database manager.
    
    Should be called during application shutdown.
    """
    global _db_manager
    if _db_manager:
        await _db_manager.close()
        _db_manager = None