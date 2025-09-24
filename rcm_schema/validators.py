"""Database validation utilities for RCM Schema.

This module provides functions to validate that the PostgreSQL database
meets the minimum requirements specified in constants.py.
"""
import re
import logging
from typing import Optional, Dict, Any

import asyncpg
import psycopg2

from .constants import DATABASE_REQUIREMENTS, EXTENSION_VERSIONS

logger = logging.getLogger(__name__)


def parse_postgresql_version(version_string: str) -> Optional[float]:
    """Parse PostgreSQL version from version() output.
    
    Args:
        version_string: Output from SELECT version()
        
    Returns:
        Float version number (e.g., 16.1 -> 16.1) or None if parsing fails
    """
    # Example: "PostgreSQL 16.1 on x86_64-pc-linux-gnu, compiled by..."
    match = re.search(r'PostgreSQL (\d+(?:\.\d+)?)', version_string)
    if match:
        return float(match.group(1))
    return None


async def validate_postgresql_version_async(connection: asyncpg.Connection) -> None:
    """Validate PostgreSQL version meets minimum requirements (async).
    
    Args:
        connection: AsyncPG database connection
        
    Raises:
        RuntimeError: If version is below minimum requirement
    """
    version_string = await connection.fetchval("SELECT version()")
    version = parse_postgresql_version(version_string)
    
    if version is None:
        logger.warning(f"Could not parse PostgreSQL version from: {version_string}")
        raise RuntimeError(f"Unable to determine PostgreSQL version")
    
    min_version = float(DATABASE_REQUIREMENTS["min_postgresql_version"])
    if version < min_version:
        raise RuntimeError(
            f"PostgreSQL {min_version}+ required, but found {version}. "
            f"Please upgrade your PostgreSQL installation."
        )
    
    logger.info(f"PostgreSQL version {version} meets requirement (>= {min_version})")


def validate_postgresql_version_sync(connection) -> None:
    """Validate PostgreSQL version meets minimum requirements (sync).
    
    Args:
        connection: Psycopg2 database connection
        
    Raises:
        RuntimeError: If version is below minimum requirement
    """
    cursor = connection.cursor()
    cursor.execute("SELECT version()")
    version_string = cursor.fetchone()[0]
    cursor.close()
    
    version = parse_postgresql_version(version_string)
    
    if version is None:
        logger.warning(f"Could not parse PostgreSQL version from: {version_string}")
        raise RuntimeError(f"Unable to determine PostgreSQL version")
    
    min_version = float(DATABASE_REQUIREMENTS["min_postgresql_version"])
    if version < min_version:
        raise RuntimeError(
            f"PostgreSQL {min_version}+ required, but found {version}. "
            f"Please upgrade your PostgreSQL installation."
        )
    
    logger.info(f"PostgreSQL version {version} meets requirement (>= {min_version})")


async def validate_extensions_async(connection: asyncpg.Connection) -> Dict[str, bool]:
    """Validate required PostgreSQL extensions are installed (async).
    
    Args:
        connection: AsyncPG database connection
        
    Returns:
        Dict mapping extension name to installation status
        
    Raises:
        RuntimeError: If any required extension is missing
    """
    results = {}
    missing_extensions = []
    
    for ext_name in DATABASE_REQUIREMENTS["required_extensions"]:
        exists = await connection.fetchval(
            "SELECT EXISTS(SELECT 1 FROM pg_extension WHERE extname = $1)",
            ext_name
        )
        results[ext_name] = exists
        if not exists:
            missing_extensions.append(ext_name)
    
    if missing_extensions:
        raise RuntimeError(
            f"Required PostgreSQL extensions not installed: {', '.join(missing_extensions)}. "
            f"Please install them with: CREATE EXTENSION IF NOT EXISTS <extension_name>;"
        )
    
    # Check extension versions if specified
    for ext_name, min_version in EXTENSION_VERSIONS.items():
        if ext_name in results and results[ext_name]:
            version = await connection.fetchval(
                "SELECT extversion FROM pg_extension WHERE extname = $1",
                ext_name
            )
            logger.info(f"Extension {ext_name} version: {version} (minimum: {min_version})")
    
    return results


def validate_extensions_sync(connection) -> Dict[str, bool]:
    """Validate required PostgreSQL extensions are installed (sync).
    
    Args:
        connection: Psycopg2 database connection
        
    Returns:
        Dict mapping extension name to installation status
        
    Raises:
        RuntimeError: If any required extension is missing
    """
    results = {}
    missing_extensions = []
    cursor = connection.cursor()
    
    for ext_name in DATABASE_REQUIREMENTS["required_extensions"]:
        cursor.execute(
            "SELECT EXISTS(SELECT 1 FROM pg_extension WHERE extname = %s)",
            (ext_name,)
        )
        exists = cursor.fetchone()[0]
        results[ext_name] = exists
        if not exists:
            missing_extensions.append(ext_name)
    
    if missing_extensions:
        cursor.close()
        raise RuntimeError(
            f"Required PostgreSQL extensions not installed: {', '.join(missing_extensions)}. "
            f"Please install them with: CREATE EXTENSION IF NOT EXISTS <extension_name>;"
        )
    
    # Check extension versions if specified
    for ext_name, min_version in EXTENSION_VERSIONS.items():
        if ext_name in results and results[ext_name]:
            cursor.execute(
                "SELECT extversion FROM pg_extension WHERE extname = %s",
                (ext_name,)
            )
            version = cursor.fetchone()[0]
            logger.info(f"Extension {ext_name} version: {version} (minimum: {min_version})")
    
    cursor.close()
    return results


async def validate_database_compatibility_async(connection: asyncpg.Connection) -> None:
    """Perform full database compatibility validation (async).
    
    Args:
        connection: AsyncPG database connection
        
    Raises:
        RuntimeError: If any requirement is not met
    """
    logger.info("Validating database compatibility...")
    
    # Check PostgreSQL version
    await validate_postgresql_version_async(connection)
    
    # Check extensions
    await validate_extensions_async(connection)
    
    logger.info("Database compatibility validation passed ✓")


def validate_database_compatibility_sync(connection) -> None:
    """Perform full database compatibility validation (sync).
    
    Args:
        connection: Psycopg2 database connection
        
    Raises:
        RuntimeError: If any requirement is not met
    """
    logger.info("Validating database compatibility...")
    
    # Check PostgreSQL version
    validate_postgresql_version_sync(connection)
    
    # Check extensions
    validate_extensions_sync(connection)
    
    logger.info("Database compatibility validation passed ✓")


# Credential Storage Validation Functions

def validate_secret_arn(arn: Optional[str]) -> bool:
    """Validate AWS secret ARN format.
    
    Args:
        arn: AWS SSM Parameter Store or Secrets Manager ARN
        
    Returns:
        True if valid ARN format or None, False otherwise
    """
    if arn is None:
        return True
    
    # AWS SSM Parameter Store ARN pattern
    # arn:aws:ssm:region:account-id:parameter/path
    ssm_pattern = re.compile(
        r'^arn:aws:ssm:[a-z0-9-]+:\d{12}:parameter/[\w/\-._]+$'
    )
    
    # AWS Secrets Manager ARN pattern
    # arn:aws:secretsmanager:region:account-id:secret:name-abcdef
    secrets_pattern = re.compile(
        r'^arn:aws:secretsmanager:[a-z0-9-]+:\d{12}:secret:[\w/\-._]+-[A-Za-z0-9]+$'
    )
    
    return bool(ssm_pattern.match(arn) or secrets_pattern.match(arn))


def validate_rotation_status(status: Optional[str]) -> bool:
    """Validate credential rotation status.
    
    Args:
        status: Rotation status value
        
    Returns:
        True if valid status or None, False otherwise
    """
    if status is None:
        return True
    
    valid_statuses = {'active', 'failed', 'pending'}
    return status in valid_statuses


def validate_access_type(access_type: str) -> bool:
    """Validate credential access type.
    
    Args:
        access_type: Type of credential access
        
    Returns:
        True if valid access type, False otherwise
    """
    valid_types = {'retrieve', 'store', 'rotate', 'delete'}
    return access_type in valid_types


def validate_rotation_interval(days: int) -> bool:
    """Validate credential rotation interval.
    
    Args:
        days: Number of days between rotations
        
    Returns:
        True if valid interval, False otherwise
    """
    # Minimum 1 day, maximum 365 days (1 year)
    return 1 <= days <= 365


def sanitize_secret_arn_for_logging(arn: Optional[str]) -> Optional[str]:
    """Sanitize secret ARN for safe logging.
    
    Removes account ID from ARN to prevent information disclosure.
    
    Args:
        arn: AWS secret ARN
        
    Returns:
        Sanitized ARN safe for logging
    """
    if not arn:
        return arn
    
    # Replace account ID with asterisks
    sanitized = re.sub(r':\d{12}:', ':****:', arn)
    return sanitized