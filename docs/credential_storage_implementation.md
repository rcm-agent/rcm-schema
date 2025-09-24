# Credential Storage Implementation Guide

This guide explains how to use the credential storage system implemented in RCM Schema v0.4.0.

## Overview

The credential storage system follows AWS best practices for secure credential management:
- Credentials are stored in AWS SSM Parameter Store or Secrets Manager
- Only ARN references are stored in the database
- Full audit logging and rotation scheduling support
- Tenant isolation via IAM policies

## Key Components

### 1. Database Schema Updates

The `integration_endpoint` table now includes:
- `secret_arn`: AWS SSM Parameter Store or Secrets Manager ARN
- `last_rotated_at`: Timestamp of last credential rotation
- `rotation_status`: Current status ('active', 'failed', 'pending')

### 2. Audit Logging

The `credential_access_log` table tracks:
- All credential access operations
- Access types: 'retrieve', 'store', 'rotate', 'delete'
- Success/failure status with error messages
- IP address and user agent for security monitoring

### 3. Rotation Scheduling

The `credential_rotation_schedule` table manages:
- Rotation intervals (default 90 days)
- Automatic rotation flags
- Notification email addresses
- Next rotation timestamps

## Usage Examples

### Storing Credentials

```python
from rcm_schema.credential_manager import CredentialManager

# Initialize manager
manager = CredentialManager()

# Store credentials in AWS SSM
secret_arn = "arn:aws:ssm:us-east-1:123456789012:parameter/rcm/prod/org-123/portal-456"
credentials = {
    "username": "portal_user",
    "password": "secure_password",
    "mfa_seed": "JBSWY3DPEHPK3PXP",
    "metadata": {
        "portal_type": "insurance",
        "portal_name": "BlueCross BlueShield"
    }
}

manager.store_credentials(secret_arn, credentials)

# Update database with ARN reference
portal.secret_arn = secret_arn
portal.last_rotated_at = datetime.utcnow()
portal.rotation_status = 'active'
db.commit()
```

### Retrieving Credentials

```python
# Get credentials with automatic caching
credentials = manager.get_credentials(portal.secret_arn)

# Access credential fields
username = credentials['username']
password = credentials['password']
```

### Dual-Read Migration Pattern

During migration from database-stored to AWS-stored credentials:

```python
def get_portal_credentials(portal_id: int) -> dict:
    portal = db.query(IntegrationEndpoint).filter_by(portal_id=portal_id).first()
    
    # Try new credential system first
    if portal.secret_arn:
        try:
            return credential_manager.get_credentials(portal.secret_arn)
        except Exception as e:
            logger.error(f"Failed to fetch from {portal.secret_arn}: {e}")
            # Continue to fallback
    
    # Fallback to legacy credentials in config JSONB
    if portal.config and 'credentials' in portal.config:
        logger.warning(f"Using legacy credentials for portal {portal_id}")
        return portal.config['credentials']
    
    raise ValueError(f"No credentials found for portal {portal_id}")
```

### Credential Rotation

```python
from rcm_schema.credential_manager import CredentialRotationManager

rotation_manager = CredentialRotationManager(credential_manager)

# Perform rotation
new_credentials = {
    "username": "portal_user",
    "password": generate_secure_password(),
    # ... other fields
}

result = rotation_manager.rotate_credentials(
    portal_id="portal-123",
    secret_arn=portal.secret_arn,
    new_credentials=new_credentials
)

# Update database
if result['success']:
    portal.last_rotated_at = datetime.utcnow()
    portal.rotation_status = 'active'
else:
    portal.rotation_status = 'failed'
    # Send notification
```

## Security Best Practices

1. **IAM Policies**: Ensure ECS tasks have minimal required permissions:
   ```json
   {
     "Effect": "Allow",
     "Action": ["ssm:GetParameter"],
     "Resource": "arn:aws:ssm:*:*:parameter/rcm/${Environment}/${TenantId}/*"
   }
   ```

2. **Audit Logging**: Always log credential access:
   ```python
   # Log credential access
   access_log = CredentialAccessLog(
       portal_id=portal_id,
       secret_arn=secret_arn,
       access_type='retrieve',
       access_by=current_user,
       ip_address=request.remote_addr,
       success=True
   )
   db.add(access_log)
   ```

3. **Cache Management**: Clear cache after rotation:
   ```python
   credential_manager.clear_cache(secret_arn)
   ```

4. **Error Handling**: Never expose ARNs in error messages:
   ```python
   from rcm_schema.validators import sanitize_secret_arn_for_logging
   
   logger.error(f"Failed to access {sanitize_secret_arn_for_logging(arn)}")
   ```

## Migration Steps

1. **Create AWS resources** (SSM parameters or Secrets Manager secrets)
2. **Run database migration**: `alembic upgrade 006`
3. **Migrate credentials** using the provided migration script
4. **Update application code** to use CredentialManager
5. **Monitor access logs** for any issues
6. **Remove legacy credentials** from database after validation

## Monitoring

Key metrics to monitor:
- Credential fetch failures
- Cache hit/miss ratio
- Rotation success rate
- Unusual access patterns

Set up CloudWatch alarms for:
- Failed credential retrieval > 5 in 5 minutes
- Rotation failure for any portal
- Access from unexpected IP ranges