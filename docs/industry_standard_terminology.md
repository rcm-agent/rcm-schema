# RCM Industry Standard Terminology

## Overview

This document explains the industry-standard terminology used in our RCM schema and the rationale behind our naming choices.

## Task Actions

### Industry Standards

Our task actions align with healthcare industry standards and HIPAA X12 transaction sets:

| Domain | Action | Industry Standard | HIPAA Transaction |
|--------|--------|------------------|-------------------|
| eligibility | **verify** | Eligibility Verification | X12 270/271 |
| claim | **inquire** | Claim Status Inquiry | X12 276/277 |
| prior_auth | **request** | Prior Authorization Request | X12 278 |
| prior_auth | **submit** | Submit Prior Auth | X12 278 |
| any | **denial_follow_up** | Denial Follow-up | N/A |

### Migration from Generic Terms

We've migrated from generic technical terms to industry-specific terminology:

- `status_check` → `verify` (for eligibility)
- `status_check` → `inquire` (for claims)
- `check` → `verify`
- `check_status` → `inquire`

### Benefits

1. **Clarity**: Healthcare professionals immediately understand the intent
2. **Standards Compliance**: Aligns with HIPAA X12 transaction standards
3. **Integration**: Better compatibility with existing RCM systems
4. **Reduced Confusion**: Distinct actions for different operations

## Implementation

### Database Migration

Run migration `004_update_task_action_enum_industry_standards.py` to:
- Update the task_action enum with new values
- Migrate existing data to use industry terms
- Create backward compatibility mapping

### Code Updates

Update your code to use the new action values:

```python
# Old way (deprecated)
structured_data = {
    "domain": "eligibility",
    "action": "status_check"  # Generic term
}

# New way (industry standard)
structured_data = {
    "domain": "eligibility", 
    "action": "verify"  # HIPAA X12 270/271 standard
}
```

### Backward Compatibility

The `task_action_mapping` table provides backward compatibility:
- Maps legacy terms to industry standards
- Allows gradual migration of existing systems
- Documents the translation for reference

## References

- [HIPAA X12 270/271](https://www.cms.gov/medicare/billing/electronicbillingeditrans/downloads/5010a1ca270271.pdf) - Eligibility, Coverage or Benefit Inquiry and Response
- [HIPAA X12 276/277](https://www.cms.gov/medicare/billing/electronicbillingeditrans/downloads/5010a1ca276277.pdf) - Health Care Claim Status Request and Response
- [HIPAA X12 278](https://www.cms.gov/medicare/billing/electronicbillingeditrans/downloads/5010a1ca278.pdf) - Health Care Services Review