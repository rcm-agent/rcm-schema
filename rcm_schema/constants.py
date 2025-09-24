"""Database requirements and constants for RCM Schema.

This module defines the minimum requirements that any PostgreSQL instance
must meet to support the RCM schema. Infrastructure (e.g., rcm-cdk) is
responsible for provisioning a database that meets these requirements.
"""

# Database version requirements
DATABASE_REQUIREMENTS = {
    "min_postgresql_version": "16.0",
    "required_extensions": [
        "pgvector",      # Vector similarity search for embeddings
        "pgcrypto",      # UUID generation and encryption
        "uuid-ossp",     # Additional UUID functions
    ],
    "recommended_extensions": [
        "pg_stat_statements",  # Query performance monitoring
    ]
}

# Version compatibility matrix
VERSION_COMPATIBILITY = {
    "0.1.x": {
        "postgresql": "16.0+",
        "pgvector": "0.5.0+",
        "sqlalchemy": "2.0+",
        "pydantic": "2.0+",
    }
}

# Extension version requirements (if specific versions needed)
EXTENSION_VERSIONS = {
    "pgvector": "0.5.0",  # Minimum version for IVFFlat index support
}

# Database configuration recommendations
DATABASE_CONFIG_RECOMMENDATIONS = {
    "shared_buffers": "25% of RAM",
    "effective_cache_size": "75% of RAM",
    "maintenance_work_mem": "256MB",
    "work_mem": "16MB",
    "max_connections": 200,
    # pgvector specific
    "ivfflat.probes": 10,  # Number of lists to search
}

# Connection pool settings
CONNECTION_POOL_DEFAULTS = {
    "min_size": 10,
    "max_size": 20,
    "max_inactive_connection_lifetime": 300,  # 5 minutes
}