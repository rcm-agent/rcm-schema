# Changelog

## [0.4.0] - 2025-01-30

### Added
- Secure credential storage system following AWS best practices
  - `secret_arn` field in `integration_endpoint` table for AWS SSM/Secrets Manager ARNs
  - `last_rotated_at` and `rotation_status` fields for rotation tracking
  - `credential_access_log` table for audit trail and compliance
  - `credential_rotation_schedule` table for automated rotation management
- CredentialManager implementation with:
  - Support for both AWS SSM Parameter Store and Secrets Manager
  - In-memory caching with configurable TTL
  - Automatic retry with exponential backoff
  - Comprehensive audit logging
- Validation functions for credential fields:
  - ARN format validation for SSM and Secrets Manager
  - Rotation status validation
  - Access type validation
  - ARN sanitization for secure logging
- Migration `006_add_credential_storage_fields.py`
- Comprehensive indexes for performance optimization

### Security
- Credentials are never stored in database, only ARN references
- Tenant isolation via IAM policies with Principal Tags
- Encryption at rest using AWS KMS
- Audit logging for all credential operations
- Support for zero-downtime credential rotation

## [0.3.0] - 2025-01-29

### Added
- Comprehensive BPO process taxonomy for healthcare outsourcing
- New task domains: `credentialing`, `coding`, `charge_capture`, `denial_mgmt`, `payment_posting`, `ar_followup`, `patient_access`
- 40+ new task actions covering all major BPO processes
- Migration `005_add_comprehensive_bpo_task_enums.py`
- `bpo_process_mapping` table with process metadata, SLAs, and complexity levels
- Documentation: `docs/bpo_process_taxonomy.md` with detailed BPO process guide

### Changed
- Expanded TaskDomain enum from 3 to 10 domains
- Expanded TaskAction enum from 6 to 50+ actions
- Updated models.py and schemas.py with comprehensive enums

## [0.2.0] - 2025-01-29

### Changed
- Updated `task_action` enum to use industry-standard RCM terminology
  - `status_check` → `verify` for eligibility (HIPAA X12 270/271)
  - `status_check` → `inquire` for claims (HIPAA X12 276/277)
  - Added `request` for prior authorization requests
  - Kept `status_check` for backward compatibility (deprecated)
- Added migration `004_update_task_action_enum_industry_standards.py`
- Created `task_action_mapping` table for legacy term support
- Updated schemas.py and models.py with new enum values

### Added
- Documentation for industry-standard terminology (`docs/industry_standard_terminology.md`)
- Mapping table for backward compatibility with legacy action names

## [0.1.0] - 2025-07-29

### Added
- Complete SQLAlchemy models for v3 schema
  - All 14 tables with proper relationships
  - pgvector support for embeddings (768D text, 512D image)
  - Custom ENUM types including `task_signature_source`
  - Complex constraints (XOR, partial unique indexes)
  
- Pydantic schemas for all models
  - Request/response validation
  - Vector dimension validation
  - New schemas for `TaskType` and `FieldRequirement`
  
- Alembic migration setup
  - Initial migration with complete v3 schema
  - Support for async SQLAlchemy
  - Proper dependency ordering
  
- Database utilities
  - Async database manager with connection pooling
  - `init_db.py` for database initialization
  - `run_migrations.py` for migration management
  - Sample data loading for development
  
- Documentation
  - Comprehensive README with usage examples
  - Database reference guide with example data
  - SQL schema definition
  - Architecture documentation in `/docs`
  
### Key Design Decisions
- Used `task_signature` (not `workflow_recipe`) throughout
- Added `task_signature_source` enum with values `human` and `ai`
- Implemented template inheritance pattern for workflows
- Multi-tenant isolation with org_id foreign keys
- Dynamic field requirements per task type