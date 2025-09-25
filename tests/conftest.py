"""Pytest configuration and fixtures for RCM Schema tests."""
import os
import asyncio
from typing import Generator, AsyncGenerator
from unittest.mock import MagicMock, AsyncMock
import pytest
import pytest_asyncio
from sqlalchemy import create_engine, text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import NullPool
import asyncpg

# Add parent directory to path
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT.parent))

from rcm_schema.models import Base
from rcm_schema.database import DatabaseManager


# Test database URL - override with env var if needed
TEST_DATABASE_URL = os.getenv(
    "TEST_DATABASE_URL",
    "postgresql://test:test@localhost:5432/rcm_test"
)


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
def test_database_url():
    """Provide test database URL."""
    return TEST_DATABASE_URL


@pytest.fixture(scope="session")
def sync_engine(test_database_url):
    """Create synchronous engine for test database setup."""
    # Convert async URL to sync if needed
    url = test_database_url.replace("postgresql+asyncpg://", "postgresql://")
    engine = create_engine(url, poolclass=NullPool)
    yield engine
    engine.dispose()


@pytest.fixture(scope="session")
async def async_engine(test_database_url):
    """Create async engine for tests."""
    # Convert sync URL to async if needed
    if test_database_url.startswith("postgresql://"):
        url = test_database_url.replace("postgresql://", "postgresql+asyncpg://")
    else:
        url = test_database_url
    
    engine = create_async_engine(url, poolclass=NullPool)
    yield engine
    await engine.dispose()


@pytest.fixture(scope="function")
async def setup_database(sync_engine):
    """Create all tables before each test and drop after."""
    # Create tables
    Base.metadata.create_all(bind=sync_engine)
    yield
    # Drop tables
    Base.metadata.drop_all(bind=sync_engine)


@pytest.fixture
async def async_session(async_engine, setup_database):
    """Provide async database session for tests."""
    async_session_maker = sessionmaker(
        async_engine,
        class_=AsyncSession,
        expire_on_commit=False
    )
    
    async with async_session_maker() as session:
        yield session
        await session.rollback()


@pytest.fixture
def sync_session(sync_engine, setup_database):
    """Provide sync database session for tests."""
    Session = sessionmaker(bind=sync_engine)
    session = Session()
    yield session
    session.rollback()
    session.close()


@pytest.fixture
async def db_manager(test_database_url, setup_database):
    """Provide initialized DatabaseManager for tests."""
    manager = DatabaseManager(test_database_url)
    await manager.initialize()
    yield manager
    await manager.close()


@pytest.fixture
def mock_asyncpg_connection():
    """Mock asyncpg connection for unit tests."""
    mock_conn = AsyncMock(spec=asyncpg.Connection)
    
    # Mock version check
    mock_conn.fetchval.return_value = "PostgreSQL 16.1 on x86_64-pc-linux-gnu"
    
    # Mock extension check
    async def mock_fetchval(query, *args):
        if "version()" in query:
            return "PostgreSQL 16.1 on x86_64-pc-linux-gnu"
        elif "pg_extension" in query:
            return True  # All extensions exist
        return None
    
    mock_conn.fetchval = AsyncMock(side_effect=mock_fetchval)
    return mock_conn


@pytest.fixture
def mock_psycopg2_connection():
    """Mock psycopg2 connection for unit tests."""
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    
    # Mock cursor
    mock_conn.cursor.return_value = mock_cursor
    
    # Mock version check
    mock_cursor.fetchone.return_value = ("PostgreSQL 16.1 on x86_64-pc-linux-gnu",)
    
    # Mock execute results
    def mock_execute(query, params=None):
        if "version()" in query:
            mock_cursor.fetchone.return_value = ("PostgreSQL 16.1 on x86_64-pc-linux-gnu",)
        elif "pg_extension" in query:
            mock_cursor.fetchone.return_value = (True,)
    
    mock_cursor.execute = MagicMock(side_effect=mock_execute)
    return mock_conn


@pytest.fixture
def sample_org_data():
    """Sample organization data for tests."""
    return {
        "org_type": "hospital",
        "name": "Test Hospital",
        "email_domain": "testhospital.com"
    }


@pytest.fixture
def sample_portal_type_data():
    """Sample portal type data for tests."""
    return {
        "code": "BCBS_MI",
        "name": "Blue Cross Blue Shield Michigan",
        "kind": "payer",
        "base_url": "https://www.bcbsm.com"
    }


@pytest.fixture
def sample_task_type_data():
    """Sample task type data for tests."""
    return {
        "domain": "eligibility",
        "action": "status_check",
        "display_name": "Eligibility Status Check",
        "description": "Check patient eligibility status"
    }


@pytest.fixture
def sample_batch_job_data():
    """Sample batch job data for tests."""
    return {
        "portal_id": 1,
        "task_type_id": "123e4567-e89b-12d3-a456-426614174000",
        "status": "queued"
    }


# Markers for different test types
def pytest_configure(config):
    """Register custom markers."""
    config.addinivalue_line("markers", "unit: Unit tests that don't require database")
    config.addinivalue_line("markers", "integration: Integration tests that require database")
    config.addinivalue_line("markers", "slow: Tests that take more than 5 seconds")
    config.addinivalue_line("markers", "migration: Tests for database migrations")
    config.addinivalue_line("markers", "security: Security-related tests")


# Skip integration tests if database not available
def pytest_collection_modifyitems(config, items):
    """Skip integration tests if TEST_DATABASE_URL not set."""
    if not os.getenv("RUN_INTEGRATION_TESTS"):
        skip_integration = pytest.mark.skip(
            reason="Need RUN_INTEGRATION_TESTS=1 to run integration tests"
        )
        for item in items:
            if "integration" in item.keywords:
                item.add_marker(skip_integration)
