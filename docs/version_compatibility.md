# Version Compatibility Guide

## Overview

This document defines the version requirements and compatibility matrix for the RCM Schema. The schema specifies minimum requirements that must be met by any PostgreSQL deployment, while infrastructure (e.g., rcm-cdk) is responsible for provisioning databases that meet these requirements.

## Current Requirements

### PostgreSQL Version
- **Minimum Version**: 16.0
- **Recommended**: Latest 16.x release
- **Why 16+**: Required for advanced pgvector features and performance optimizations

### Required Extensions
| Extension | Minimum Version | Purpose |
|-----------|----------------|---------|
| pgvector | 0.5.0+ | Vector similarity search for embeddings |
| pgcrypto | (bundled) | UUID generation and encryption |
| uuid-ossp | (bundled) | Additional UUID functions |

### Recommended Extensions
| Extension | Purpose |
|-----------|---------|
| pg_stat_statements | Query performance monitoring and optimization |

## Version Compatibility Matrix

| rcm-schema Version | PostgreSQL | pgvector | SQLAlchemy | Pydantic |
|-------------------|------------|----------|------------|----------|
| 0.1.x | 16.0+ | 0.5.0+ | 2.0+ | 2.0+ |
| 0.2.x (planned) | 16.0+ | 0.6.0+ | 2.0+ | 2.0+ |

## Infrastructure Responsibilities

### What Infrastructure (rcm-cdk) Manages:
- Actual PostgreSQL version selection (e.g., 16.1, 16.2, 16.3)
- RDS engine parameters and configuration
- Security patches and minor version upgrades
- Instance sizing and performance tuning
- Backup schedules and maintenance windows
- Network configuration and access control

### What Schema (rcm-schema) Defines:
- Minimum PostgreSQL version requirement
- Required extensions and their minimum versions
- Database objects (tables, indexes, constraints)
- Validation logic to ensure requirements are met

## Version Validation

The schema includes automatic validation that runs on:
- Database connection initialization
- Before running migrations
- During database setup

If validation fails, you'll see an error like:
```
RuntimeError: PostgreSQL 16.0+ required, but found 15.4. Please upgrade your PostgreSQL installation.
```

## Upgrade Path

### PostgreSQL Version Upgrade
1. Infrastructure team updates RDS engine version
2. No schema changes required
3. Validation automatically confirms compatibility

### Extension Version Upgrade
1. Infrastructure updates extension version
2. Schema validation confirms minimum version met
3. Optional: Update schema to use new features

## Development vs Production

### Local Development
- Use PostgreSQL 16+ via Docker or local installation
- Install required extensions manually
- Schema validation ensures compatibility

### Production (AWS RDS)
- CDK provisions appropriate PostgreSQL version
- Extensions pre-installed or automatically added
- Same validation logic applies

## Configuration Recommendations

For optimal performance with RCM Schema:

```yaml
# PostgreSQL Configuration
shared_buffers: 25% of RAM
effective_cache_size: 75% of RAM
maintenance_work_mem: 256MB
work_mem: 16MB
max_connections: 200

# pgvector Specific
ivfflat.probes: 10  # Number of lists to search
```

## Troubleshooting

### Common Issues

1. **Version Too Old**
   - Error: `PostgreSQL 16.0+ required, but found 15.x`
   - Solution: Upgrade PostgreSQL to version 16 or higher

2. **Missing Extension**
   - Error: `Required PostgreSQL extensions not installed: pgvector`
   - Solution: `CREATE EXTENSION IF NOT EXISTS pgvector;`

3. **Extension Version**
   - Error: `pgvector version 0.5.0+ required`
   - Solution: Update pgvector extension to latest version

## Future Considerations

- PostgreSQL 17 support planned for rcm-schema 0.3.x
- pgvector 0.7.0 features under evaluation
- Potential new extensions: pg_cron for scheduled tasks