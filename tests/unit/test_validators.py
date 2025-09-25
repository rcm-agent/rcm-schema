"""Unit tests for database validators."""
import pytest
from unittest.mock import AsyncMock, MagicMock
import asyncpg

from rcm_schema.validators import (
    parse_postgresql_version,
    validate_postgresql_version_async,
    validate_postgresql_version_sync,
    validate_extensions_async,
    validate_extensions_sync,
    validate_database_compatibility_async,
    validate_database_compatibility_sync,
)


class TestParsePostgreSQLVersion:
    """Test PostgreSQL version parsing."""
    
    def test_parse_standard_version(self):
        """Test parsing standard PostgreSQL version string."""
        version_string = "PostgreSQL 16.1 on x86_64-pc-linux-gnu, compiled by gcc"
        version = parse_postgresql_version(version_string)
        assert version == 16.1
    
    def test_parse_major_version_only(self):
        """Test parsing major version only."""
        version_string = "PostgreSQL 16 on x86_64-pc-linux-gnu"
        version = parse_postgresql_version(version_string)
        assert version == 16.0
    
    def test_parse_with_extra_info(self):
        """Test parsing version with extra build info."""
        version_string = "PostgreSQL 16.2 (Ubuntu 16.2-1.pgdg22.04+1) on x86_64-pc-linux-gnu"
        version = parse_postgresql_version(version_string)
        assert version == 16.2
    
    def test_parse_invalid_format(self):
        """Test parsing invalid version format."""
        version_string = "Not a PostgreSQL version string"
        version = parse_postgresql_version(version_string)
        assert version is None


class TestValidatePostgreSQLVersionAsync:
    """Test async PostgreSQL version validation."""
    
    @pytest.mark.asyncio
    async def test_valid_version(self, mock_asyncpg_connection):
        """Test validation passes with valid version."""
        mock_asyncpg_connection.fetchval.return_value = "PostgreSQL 16.1 on x86_64-pc-linux-gnu"
        
        # Should not raise
        await validate_postgresql_version_async(mock_asyncpg_connection)
        
        # Verify version was fetched
        mock_asyncpg_connection.fetchval.assert_called_with("SELECT version()")
    
    @pytest.mark.asyncio
    async def test_version_too_old(self, mock_asyncpg_connection):
        """Test validation fails with old version."""
        mock_asyncpg_connection.fetchval.return_value = "PostgreSQL 15.4 on x86_64-pc-linux-gnu"
        
        with pytest.raises(RuntimeError) as exc_info:
            await validate_postgresql_version_async(mock_asyncpg_connection)
        
        assert "PostgreSQL 16.0+ required" in str(exc_info.value)
        assert "found 15.4" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_unparseable_version(self, mock_asyncpg_connection):
        """Test validation fails with unparseable version."""
        mock_asyncpg_connection.fetchval.return_value = "Unknown database version"
        
        with pytest.raises(RuntimeError) as exc_info:
            await validate_postgresql_version_async(mock_asyncpg_connection)
        
        assert "Unable to determine PostgreSQL version" in str(exc_info.value)


class TestValidatePostgreSQLVersionSync:
    """Test sync PostgreSQL version validation."""
    
    def test_valid_version(self, mock_psycopg2_connection):
        """Test validation passes with valid version."""
        cursor = mock_psycopg2_connection.cursor()
        cursor.fetchone.return_value = ("PostgreSQL 16.1 on x86_64-pc-linux-gnu",)
        
        # Should not raise
        validate_postgresql_version_sync(mock_psycopg2_connection)
        
        # Verify version was fetched
        cursor.execute.assert_called_with("SELECT version()")
    
    def test_version_too_old(self, mock_psycopg2_connection):
        """Test validation fails with old version."""
        cursor = mock_psycopg2_connection.cursor()
        cursor.fetchone.return_value = ("PostgreSQL 14.0 on x86_64-pc-linux-gnu",)
        
        with pytest.raises(RuntimeError) as exc_info:
            validate_postgresql_version_sync(mock_psycopg2_connection)
        
        assert "PostgreSQL 16.0+ required" in str(exc_info.value)


class TestValidateExtensionsAsync:
    """Test async extension validation."""
    
    @pytest.mark.asyncio
    async def test_all_extensions_present(self):
        """Test validation passes when all extensions present."""
        mock_conn = AsyncMock()
        mock_conn.fetchval.return_value = True  # All extensions exist
        
        results = await validate_extensions_async(mock_conn)
        
        assert results["pgvector"] is True
        assert results["pgcrypto"] is True
        assert results["uuid-ossp"] is True
        
        # Should check each extension
        assert mock_conn.fetchval.call_count >= 3
    
    @pytest.mark.asyncio
    async def test_missing_extension(self):
        """Test validation fails with missing extension."""
        mock_conn = AsyncMock()
        
        # Mock pgvector missing, others present
        async def mock_fetchval(query, ext_name):
            if ext_name == "pgvector":
                return False
            return True
        
        mock_conn.fetchval = AsyncMock(side_effect=mock_fetchval)
        
        with pytest.raises(RuntimeError) as exc_info:
            await validate_extensions_async(mock_conn)
        
        assert "Required PostgreSQL extensions not installed: pgvector" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_multiple_missing_extensions(self):
        """Test validation with multiple missing extensions."""
        mock_conn = AsyncMock()
        
        # Mock multiple extensions missing
        async def mock_fetchval(query, ext_name):
            return ext_name not in ["pgvector", "pgcrypto"]
        
        mock_conn.fetchval = AsyncMock(side_effect=mock_fetchval)
        
        with pytest.raises(RuntimeError) as exc_info:
            await validate_extensions_async(mock_conn)
        
        error_msg = str(exc_info.value)
        assert "pgvector" in error_msg
        assert "pgcrypto" in error_msg


class TestValidateExtensionsSync:
    """Test sync extension validation."""
    
    def test_all_extensions_present(self):
        """Test validation passes when all extensions present."""
        mock_conn = MagicMock()
        cursor = mock_conn.cursor()
        cursor.fetchone.return_value = (True,)  # All extensions exist
        
        results = validate_extensions_sync(mock_conn)
        
        assert results["pgvector"] is True
        assert results["pgcrypto"] is True
        assert results["uuid-ossp"] is True
    
    def test_missing_extension(self):
        """Test validation fails with missing extension."""
        mock_conn = MagicMock()
        cursor = mock_conn.cursor()
        
        # Mock uuid-ossp missing
        def mock_execute(query, params):
            if params and params[0] == "uuid-ossp":
                cursor.fetchone.return_value = (False,)
            else:
                cursor.fetchone.return_value = (True,)
        
        cursor.execute = MagicMock(side_effect=mock_execute)
        
        with pytest.raises(RuntimeError) as exc_info:
            validate_extensions_sync(mock_conn)
        
        assert "uuid-ossp" in str(exc_info.value)


class TestValidateDatabaseCompatibility:
    """Test full database compatibility validation."""
    
    @pytest.mark.asyncio
    async def test_full_validation_passes(self):
        """Test full async validation passes."""
        mock_conn = AsyncMock()
        
        # Mock valid version
        async def mock_fetchval(query, *args):
            if "version()" in query:
                return "PostgreSQL 16.1 on x86_64-pc-linux-gnu"
            else:
                return True  # Extensions exist
        
        mock_conn.fetchval = AsyncMock(side_effect=mock_fetchval)
        
        # Should not raise
        await validate_database_compatibility_async(mock_conn)
    
    @pytest.mark.asyncio
    async def test_full_validation_fails_version(self):
        """Test full validation fails on version check."""
        mock_conn = AsyncMock()
        mock_conn.fetchval.return_value = "PostgreSQL 15.0 on x86_64-pc-linux-gnu"
        
        with pytest.raises(RuntimeError) as exc_info:
            await validate_database_compatibility_async(mock_conn)
        
        assert "PostgreSQL 16.0+ required" in str(exc_info.value)
    
    def test_sync_full_validation_passes(self):
        """Test full sync validation passes."""
        mock_conn = MagicMock()
        cursor = mock_conn.cursor()
        
        # Mock valid responses
        def mock_execute(query, params=None):
            if "version()" in query:
                cursor.fetchone.return_value = ("PostgreSQL 16.3 on x86_64-pc-linux-gnu",)
            else:
                cursor.fetchone.return_value = (True,)  # Extensions exist
        
        cursor.execute = MagicMock(side_effect=mock_execute)
        
        # Should not raise
        validate_database_compatibility_sync(mock_conn)
