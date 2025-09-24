# Hybrid RCM Platform — Credential Storage & Rotation Design

> 📖 **Part of the RCM Credential Storage System**
> - Design Spec: **You are here**
> - Schema Guide: [credential_schema_guide.md](./credential_schema_guide.md)
> - Infrastructure: [rcm-cdk/docs/credential_infrastructure.md](../../rcm-cdk/docs/credential_infrastructure.md)
> - Integration: [rcm-web-agent/docs/credential_integration.md](../../rcm-web-agent/docs/credential_integration.md)

> **🚀 V8 Update**: This design has been updated for V8 multi-tenancy. Credentials are now scoped to organizations and endpoints.

**Status:** 🟡 In Development | **Last Updated:** 2025-08-01

## Executive Summary

This document outlines the design for secure credential storage in the RCM platform, migrating from database-stored credentials to AWS Systems Manager Parameter Store with KMS encryption.

**Key Benefits:**
- ✅ Eliminates plaintext credentials from database
- ✅ Provides tenant isolation via IAM
- ✅ Enables audit trail through CloudTrail
- ✅ Supports zero-downtime rotation
- ✅ Cost-effective (<$1/month for 2k credentials)

## 1. Goals & Non-Goals

| # | Goal |
|---|------|
| G-1 | **Keep plaintext secrets _out_ of Postgres** to minimize blast radius & simplify HIPAA/SOC-2 audits |
| G-2 | Support **multi-tenant hierarchy**: firm → hospital → portal with strict isolation |
| G-3 | Zero downtime **rotation**: web-agent transparently reloads new credentials |
| G-4 | **Cost-efficient** (< $50/mo at 2k credentials) with upgrade path to Secrets Manager |
| G-5 | Local-dev & CI flows that do **not require AWS** |

**Non-goals:**
- End-user (staff) password storage — handled by Auth0/Cognito
- On-premise only deployments — see Appendix B for Vault alternative

## 2. High-Level Architecture

### V8 Multi-Tenant Architecture

```text
Organization (org_id) ──┐
                       ▼
                  Endpoint (endpoint_id) ──┐
                                          ▼
                     ┌────────────────────┐
  CDK/Terraform ---> │  SSM Parameter     │
 (creates SecureStr) │  Store (std tier)  │
                     └────────┬───────────┘
                              │ get_parameter
          secret_arn (FK)     │
Postgres ←────────────┐   ┌───▼────┐
  portal_credential   │   │ Web-   │  caches creds in-mem
  .ssm_parameter_name └──►│ Agent  │───▶ Browser / Portal
                          └──▲──────┘
                     update  │ rotation Lambda (opt.)
                     secret  │
```

### V8 Credential Path Structure

```
/rcm/{environment}/{org_id}/endpoints/{endpoint_id}/{account_id}
```

Example:
```
/rcm/prod/7b1d-1111-cafe/endpoints/endpoint-123/provider-456
```

## 3. Data Model Changes

### 3.1 Database Schema Update

```sql
ALTER TABLE integration_endpoint
  ADD COLUMN secret_arn TEXT 
      CHECK (secret_arn LIKE 'arn:aws:ssm:%' OR secret_arn LIKE 'arn:aws:secretsmanager:%');

-- Audit fields
ALTER TABLE integration_endpoint
  ADD COLUMN last_rotated_at TIMESTAMPTZ,
  ADD COLUMN rotation_status TEXT CHECK (rotation_status IN ('active', 'failed', 'pending'));
```

**Note:** Using `secret_arn` instead of `secret_path` for future compatibility with AWS Secrets Manager.

### 3.2 Secret ARN Format

- **SSM:** `arn:aws:ssm:us-east-1:123456789012:parameter/rcm/{env}/{tenant_id}/{portal_code}`
- **Secrets Manager:** `arn:aws:secretsmanager:us-east-1:123456789012:secret:rcm/{env}/{tenant_id}/{portal_code}-AbCdEf`

## 4. Secret Structure

### 4.1 JSON Payload (<= 4KB)

```json
{
  "username": "portal_user_123",
  "password": "•••••",
  "mfa_seed": "JBSWY3DPEHPK3PXP",
  "oauth_client_id": "client-123",
  "oauth_client_secret": "•••••",
  "custom_fields": {
    "api_key": "•••••",
    "account_number": "12345"
  },
  "metadata": {
    "portal_type": "insurance",
    "portal_name": "BlueCross BlueShield",
    "last_rotated": "2025-07-30T00:00:00Z",
    "rotation_method": "manual|automatic"
  }
}
```

## 5. Security Model

### 5.1 Tenant Isolation via IAM

```json
{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Allow",
    "Action": ["ssm:GetParameter"],
    "Resource": "arn:aws:ssm:${AWS::Region}:${AWS::AccountId}:parameter/rcm/${aws:PrincipalTag/env}/${aws:PrincipalTag/tenant_id}/*",
    "Condition": {
      "StringEquals": {
        "aws:ResourceTag/TenantId": "${aws:PrincipalTag/tenant_id}",
        "aws:ResourceTag/Environment": "${aws:PrincipalTag/env}"
      }
    }
  }]
}
```

### 5.2 Access Control Matrix

| Principal | SSM Permissions | Scope |
|-----------|-----------------|-------|
| Web-Agent ECS Task | `GetParameter` | Own tenant only via Principal Tags |
| Rotation Lambda | `GetParameter`, `PutParameter` | Assigned portals only |
| DevOps Admin | `*` on `/rcm/dev/*` | Dev environment only |
| Break-glass Role | `GetParameter` | All, with CloudTrail alerts |

## 6. Implementation Strategy

### 6.1 Runtime Retrieval with Caching

```python
import boto3
import json
from functools import lru_cache
from datetime import datetime, timedelta

class CredentialManager:
    def __init__(self, cache_ttl_minutes=10):
        self.ssm = boto3.client('ssm')
        self.secrets_manager = boto3.client('secretsmanager')
        self.cache_ttl = timedelta(minutes=cache_ttl_minutes)
        self._cache = {}
    
    def get_credentials(self, secret_arn: str) -> dict:
        # Check cache first
        if secret_arn in self._cache:
            cached_data, cached_time = self._cache[secret_arn]
            if datetime.now() - cached_time < self.cache_ttl:
                return cached_data
        
        # Fetch based on ARN type
        if secret_arn.startswith('arn:aws:ssm:'):
            creds = self._fetch_from_ssm(secret_arn)
        elif secret_arn.startswith('arn:aws:secretsmanager:'):
            creds = self._fetch_from_secrets_manager(secret_arn)
        else:
            raise ValueError(f"Unknown secret ARN format: {secret_arn}")
        
        # Update cache
        self._cache[secret_arn] = (creds, datetime.now())
        return creds
    
    def _fetch_from_ssm(self, arn: str) -> dict:
        # Extract parameter name from ARN
        param_name = arn.split(':parameter')[-1]
        response = self.ssm.get_parameter(Name=param_name, WithDecryption=True)
        return json.loads(response['Parameter']['Value'])
    
    def _fetch_from_secrets_manager(self, arn: str) -> dict:
        response = self.secrets_manager.get_secret_value(SecretId=arn)
        return json.loads(response['SecretString'])
```

### 6.2 Zero-Downtime Migration

**Phase 1: Dual-Read Implementation**
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

**Phase 2: Migration Script**
```python
async def migrate_portal_credentials(portal_id: int):
    portal = await get_portal(portal_id)
    
    # Skip if already migrated
    if portal.secret_arn:
        return
    
    # Create parameter in SSM
    param_name = f"/rcm/{env}/{portal.org_id}/{portal.portal_type.code}"
    secret_arn = f"arn:aws:ssm:{region}:{account_id}:parameter{param_name}"
    
    ssm.put_parameter(
        Name=param_name,
        Value=json.dumps(portal.config['credentials']),
        Type='SecureString',
        KeyId=kms_key_id,
        Tags=[
            {'Key': 'TenantId', 'Value': str(portal.org_id)},
            {'Key': 'Environment', 'Value': env},
            {'Key': 'PortalType', 'Value': portal.portal_type.code}
        ]
    )
    
    # Update database
    portal.secret_arn = secret_arn
    portal.last_rotated_at = datetime.utcnow()
    await db.commit()
    
    logger.info(f"Migrated credentials for portal {portal_id} to {secret_arn}")
```

## 7. Rotation Strategy

### 7.1 Automatic Rotation Flow

1. **EventBridge Rule**: Triggers every 60 days per portal
2. **Rotation Lambda**: 
   - Fetches current credentials from SSM
   - Uses web-agent to log into portal
   - Navigates to password change page
   - Generates new password: `secrets.token_urlsafe(18)`
   - Updates portal and verifies login
   - Updates SSM parameter
   - Updates `last_rotated_at` in database
3. **Notification**: SNS → Slack on success/failure

### 7.2 Manual Rotation

For portals that don't support automated password changes:
1. DevOps receives Slack notification
2. Manually updates password in portal
3. Updates SSM via AWS Console or CLI
4. System automatically picks up new credentials

## 8. Cost Analysis

| Component | Monthly Cost @ 2k Credentials |
|-----------|------------------------------|
| Parameter Store (Standard) | $0.00 |
| API Calls (with caching) | $0.00 |
| KMS Encryption | ~$1.00 |
| Rotation Lambda | ~$0.50 |
| **Total** | **< $2.00** |

Compare to Secrets Manager: 2,000 × $0.40 = $800/month

## 9. Monitoring & Alerting

### 9.1 CloudWatch Metrics
- Credential fetch failures
- Cache hit/miss ratio
- Rotation success rate
- API throttling events

### 9.2 Alarms
- Failed credential retrieval > 5 in 5 minutes
- Rotation failure for any portal
- Unusual access patterns (potential breach)

## 10. Migration Timeline

| Week | Phase | Activities |
|------|-------|------------|
| 1-2 | Foundation | Schema updates, CDK infrastructure |
| 3-4 | Implementation | Dual-read code, caching layer |
| 5-6 | Migration | Migrate dev/test credentials |
| 7-8 | Production | Migrate prod credentials in batches |
| 9-10 | Cleanup | Remove legacy code, monitoring |

## 11. Future Considerations

### 11.1 Scaling Beyond 10k Secrets
- **Option A**: Migrate high-rotation portals to Secrets Manager
- **Option B**: Upgrade to Parameter Store Advanced tier
- **Option C**: Implement credential pooling for similar portals

### 11.2 Cross-Region Replication
For disaster recovery:
- Use AWS Backup for Parameter Store
- Replicate to secondary region
- Update connection logic to failover

## Appendices

### Appendix A: Local Development

```yaml
# docker-compose.override.yml
services:
  localstack:
    image: localstack/localstack
    environment:
      - SERVICES=ssm,kms
    volumes:
      - ./scripts/init-local-secrets.sh:/docker-entrypoint-initaws.d/init.sh
```

### Appendix B: HashiCorp Vault Alternative

For on-premise deployments:
- 3-node Vault cluster with Raft storage
- Auto-unseal via AWS KMS
- AppRole authentication for services
- Similar secret path structure
- Estimated cost: ~$150/month infrastructure

### Appendix C: Security Checklist

- [ ] Enable CloudTrail for all SSM access
- [ ] Configure AWS Config rules for parameter compliance
- [ ] Set up break-glass procedures
- [ ] Document incident response plan
- [ ] Schedule quarterly access reviews
- [ ] Enable MFA for administrative access

---

**Document Version:** 1.0  
**Next Review:** 2025-Q3  
**Owner:** Platform Security Team