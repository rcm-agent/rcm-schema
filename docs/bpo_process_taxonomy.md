# BPO Process Taxonomy for RCM

## Overview

This document defines the comprehensive taxonomy of Business Process Outsourcing (BPO) tasks commonly handled by overseas teams for hospitals and healthcare organizations. These processes represent the core revenue cycle operations that are frequently outsourced to reduce costs while maintaining quality.

## Target Users

- **Hospitals**: Outsourcing non-clinical RCM functions
- **Billing Companies**: Managing RCM for multiple providers  
- **Credentialing Firms**: Specialized provider enrollment services
- **Offshore BPO Centers**: Teams in India, Philippines, etc.

## Domain Categories

### 1. ELIGIBILITY - Insurance Verification
The foundation of RCM - ensuring patients have valid coverage before services.

| Action | Description | SLA | Complexity |
|--------|-------------|-----|------------|
| `verify` | Real-time eligibility check | 24h | Low |
| `batch_verify` | Bulk eligibility processing | 48h | Medium |
| `benefits_breakdown` | Detailed benefits analysis | 24h | Medium |
| `coverage_discovery` | Find unknown insurance | 48h | High |

**Common Systems**: Availity, NaviNet, Optum, Payer portals

### 2. PRIOR_AUTH - Prior Authorization
Critical for high-cost procedures and specialty medications.

| Action | Description | SLA | Complexity |
|--------|-------------|-----|------------|
| `request` | Initial auth request | 48h | High |
| `submit` | Submit with clinical docs | 48h | High |
| `inquire` | Check auth status | 24h | Low |
| `appeal` | Appeal denial | 72h | High |
| `extend` | Request extension | 48h | Medium |
| `expedite` | Urgent authorization | 24h | High |

**Common Systems**: Payer portals, CoverMyMeds, Prior Auth tools

### 3. CLAIM - Claims Management
Core billing operations from submission to payment.

| Action | Description | SLA | Complexity |
|--------|-------------|-----|------------|
| `claim_submit` | Submit new claim (837) | 48h | Medium |
| `claim_inquire` | Check status (276/277) | 24h | Low |
| `claim_correct` | Fix and resubmit | 48h | Medium |
| `claim_appeal` | Appeal denial | 72h | High |
| `claim_void` | Void submitted claim | 24h | Low |

**Common Systems**: Clearinghouses (Availity, Change Healthcare), Practice Management Systems

### 4. CREDENTIALING - Provider Enrollment
Long-cycle, high-complexity process for provider onboarding.

| Action | Description | SLA | Complexity |
|--------|-------------|-----|------------|
| `provider_enroll` | New provider enrollment | 30d | High |
| `credential_verify` | Verify credentials | 7d | High |
| `privilege_update` | Update hospital privileges | 14d | Medium |
| `revalidate` | Periodic revalidation | 14d | Medium |
| `caqh_update` | Update CAQH profile | 3d | Low |

**Common Systems**: CAQH, PECOS, Payer enrollment portals

### 5. CODING - Medical Coding
Requires certified coders (CPC, CCS) with clinical knowledge.

| Action | Description | SLA | Complexity |
|--------|-------------|-----|------------|
| `assign_codes` | ICD-10/CPT coding | 24h | High |
| `audit_codes` | Quality audit | 48h | High |
| `query_physician` | Provider queries | 48h | Medium |
| `code_review` | Peer review | 48h | High |

**Common Systems**: 3M, Optum encoders, EHR systems

### 6. CHARGE_CAPTURE - Charge Entry
Converting clinical services to billable charges.

| Action | Description | SLA | Complexity |
|--------|-------------|-----|------------|
| `charge_entry` | Enter charges | 24h | Medium |
| `charge_audit` | Audit accuracy | 48h | Medium |
| `charge_reconcile` | Reconcile with clinical | 48h | High |

### 7. DENIAL_MGMT - Denial Management
Critical for revenue recovery and process improvement.

| Action | Description | SLA | Complexity |
|--------|-------------|-----|------------|
| `denial_review` | Analyze denial reasons | 24h | Medium |
| `denial_appeal` | Submit appeals | 72h | High |
| `denial_followup` | Appeal follow-up | 48h | Medium |
| `denial_prevent` | Root cause analysis | 96h | High |

### 8. PAYMENT_POSTING - Payment Processing
Accurate posting ensures proper revenue recognition.

| Action | Description | SLA | Complexity |
|--------|-------------|-----|------------|
| `post_era` | Post 835 ERA | 24h | Medium |
| `post_manual` | Manual posting | 24h | Low |
| `reconcile_payment` | Payment reconciliation | 48h | Medium |
| `identify_variance` | Find discrepancies | 48h | High |

### 9. AR_FOLLOWUP - Accounts Receivable
Managing outstanding balances to optimize cash flow.

| Action | Description | SLA | Complexity |
|--------|-------------|-----|------------|
| `ar_review` | Review aging buckets | 24h | Medium |
| `ar_followup` | Payer follow-up | 48h | Medium |
| `ar_appeal` | Appeal for payment | 72h | High |
| `ar_writeoff` | Recommend write-offs | 48h | Medium |

### 10. PATIENT_ACCESS - Patient Registration
Front-end processes ensuring clean claims downstream.

| Action | Description | SLA | Complexity |
|--------|-------------|-----|------------|
| `register_patient` | New registration | 24h | Low |
| `verify_demographics` | Verify patient info | 24h | Low |
| `insurance_discovery` | Find coverage | 48h | Medium |
| `estimate_copay` | Calculate patient responsibility | 24h | Medium |

## Implementation Priorities

### Phase 1 - Core BPO Functions (Current Focus)
1. **Eligibility Verification** - Foundation of clean claims
2. **Prior Authorization** - High impact on revenue
3. **Claim Status Inquiry** - Essential follow-up

### Phase 2 - Extended BPO Functions
1. **Denial Management** - Revenue recovery
2. **Payment Posting** - Cash application
3. **AR Follow-up** - Collections support

### Phase 3 - Specialized Functions
1. **Medical Coding** - Requires certified staff
2. **Credentialing** - Long-cycle processes
3. **Charge Capture** - Clinical integration

## Skill Requirements by Domain

### Basic Skills (Eligibility, Claim Inquiry)
- Basic medical terminology
- Payer portal navigation
- Data entry accuracy
- English proficiency

### Intermediate Skills (Prior Auth, Denials)
- Clinical knowledge
- Medical necessity understanding
- Appeal letter writing
- Payer policy knowledge

### Advanced Skills (Coding, Credentialing)
- Professional certification (CPC, CCS)
- Regulatory compliance
- Clinical documentation interpretation
- Complex problem solving

## Compliance Considerations

- **HIPAA**: All processes handle PHI
- **Timely Filing**: Critical for claims/appeals
- **Payer Policies**: Constantly changing rules
- **State Regulations**: Vary by location
- **International**: Data privacy for offshore teams

## Success Metrics

### Efficiency Metrics
- Tasks per hour
- First-pass resolution rate
- Average handling time
- SLA compliance

### Quality Metrics
- Error rates
- Denial rates
- Days in AR
- Clean claim rate

### Financial Metrics
- Cost per transaction
- Revenue impact
- Collection rate
- Write-off percentage

## Future Considerations

1. **AI/ML Integration**: Automate routine tasks
2. **Real-time APIs**: Move from portal scraping to API calls
3. **Predictive Analytics**: Prevent denials before submission
4. **Global Workforce**: 24/7 follow-the-sun model
5. **Specialization**: Domain-specific expert teams