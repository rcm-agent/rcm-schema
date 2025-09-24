# Hybrid RCM Platform – Database Reference (v3 • 2025‑07‑29)
_Exact column lists **plus concrete example rows** for every table._

> **⚠️ DEPRECATED**: This is the V3 schema documentation. For the current V8 schema with multi-tenancy and graph workflows, see [hybrid_rcm_db_guide_v8.md](hybrid_rcm_db_guide_v8.md)

---

## ENUM Types
| name | values | used by |
|------|--------|---------|
| `task_domain` | `eligibility`, `claim`, `prior_auth` | `task_type`, `task_signature` |
| `task_action` | `status_check`, `submit`, `denial_follow_up` | same |
| `task_signature_source` | `human`, `ai` | `task_signature.source` |

---

## organization
| column | type | purpose |
|--------|------|---------|
| org_id | UUID PK | Tenant key |
| org_type | TEXT | `hospital` / `billing_firm` / `credentialer` |
| name | TEXT UNIQUE | Tenant name |
| email_domain | TEXT UNIQUE | SSO domain |
| created_at | TIMESTAMPTZ | Stamp |

**Example**  
`('7b1d‑1111‑…', 'hospital', 'North Clinic', 'north‑clinic.org', 2025‑07‑28 18:02Z)`

---

## portal_type
| column | type | purpose |
|--------|------|---------|
| portal_type_id | SERIAL PK | Brand key |
| code | TEXT UNIQUE | `availity_uhc` |
| name | TEXT | `Availity – UHC` |
| base_url | TEXT | `https://provider.uhc.com` |
| endpoint_kind | TEXT | `payer` |

**Example**  
`(2, 'availity_uhc', 'Availity – UHC', 'https://provider.uhc.com', 'payer')`

---

## integration_endpoint
| column | type | purpose |
|--------|------|---------|
| portal_id | SERIAL PK | Endpoint key |
| org_id | UUID FK | Tenant |
| name | TEXT | `UHC Prod` |
| portal_type_id | INT FK | Brand |
| base_url | TEXT | Override host |
| config | JSONB | Encrypted creds |
| created_at | TIMESTAMP | Stamp |

**Example**  
`(17, '7b1d‑1111‑…', 'UHC Prod', 2, 'https://provider.uhc.com', {"user":"abc"}, 2025‑07‑28)`

---

## task_type
| column | type | purpose |
|---------|------|---------|
| **task_type_id** | `UUID PRIMARY KEY` | Stable key |
| **domain** | `task_domain` | Business domain |
| **action** | `task_action` | Operation |
| **display_name** | `TEXT` | UI label |
| **description** | `TEXT` | Help text |
| **created_at** | `TIMESTAMPTZ` | Timestamp |

**Examples**  
`('c101‑…', 'eligibility', 'status_check', 'Payer Portal Eligibility Check', 'Check patient eligibility status on payer portal', '2025‑07‑29')`  
`('c102‑…', 'prior_auth', 'status_check', 'Prior Auth Status Check', 'Check status of prior authorization request', '2025‑07‑29')`  
`('c103‑…', 'prior_auth', 'submit', 'Prior Auth Submission', 'Submit new prior authorization request', '2025‑07‑29')`  
`('c104‑…', 'claim', 'status_check', 'Claim Status Check', 'Check status of submitted claim', '2025‑07‑29')`

## field_requirement _(Deprecated - see Hierarchical Requirements below)_
| column | type | purpose |
|--------|------|---------|
| requirement_id | UUID PK | Key |
| task_type_id | UUID FK | Workflow |
| portal_id | INT FK (nullable) | Scope override |
| required_fields | JSONB | `["patient_first_name","dob"]` |
| optional_fields | JSONB | `["middle_initial"]` |
| field_metadata | JSONB | Regex masks etc. |
| version | INT | Schema version |
| active | BOOLEAN | TRUE → in force |
| created_at / updated_at | TIMESTAMPTZ | Timestamps |

**Example** (global to template)  
`('req‑001', 'c101‑…', NULL, '["ssn","dob"]', '[]', '{}', 1, true, 2025‑07‑29, 2025‑07‑29)`

> **Note**: This table is deprecated. Use the hierarchical requirements system (payer_requirement + org_requirement_policy) for new implementations.

---

## Hierarchical Requirements System

The following tables implement a three-tier requirements hierarchy: Global → Payer → Organization

### payer_requirement
| column | type | purpose |
|--------|------|---------|
| requirement_id | UUID PK | Requirement key |
| portal_type_id | INT FK | Payer portal type |
| task_type_id | UUID FK | Task template |
| version | INT | Version number |
| required_fields | JSONB | `["member_id","dob","ssn"]` |
| optional_fields | JSONB | `["group_number"]` |
| field_rules | JSONB | Validation patterns |
| compliance_ref | TEXT | `HIPAA 837P v5010` |
| effective_date | DATE | When active |
| created_at | TIMESTAMPTZ | Stamp |
| created_by | UUID FK | Creator |

**Example** (Anthem eligibility requirements)  
`('pr‑001', 2, 'c101‑…', 1, '["member_id","dob","ssn"]', '["group_number"]', '{"member_id":{"pattern":"^W\d{9}$"}}', 'Anthem Guide 2025', 2025‑01‑01, 2025‑07‑29 10:00Z, 'user‑123')`

### org_requirement_policy
| column | type | purpose |
|--------|------|---------|
| policy_id | UUID PK | Policy key |
| org_id | UUID FK | Organization |
| task_type_id | UUID FK | Task affected |
| portal_type_id | INT FK (nullable) | Portal scope |
| policy_type | TEXT | `add`/`remove`/`override` |
| field_changes | JSONB | Changes to apply |
| reason | TEXT | Business justification |
| version | INT | Policy version |
| active | BOOLEAN | Is active? |
| created_at | TIMESTAMPTZ | Stamp |
| created_by | UUID FK | Creator |
| approved_by | UUID FK | Approver |
| approved_at | TIMESTAMPTZ | Approval time |

**Example** (Hospital adds internal tracking)  
`('pol‑001', '7b1d‑1111‑…', 'c101‑…', 2, 'add', '{"required_fields":["internal_case_id"]}', 'Hospital tracking policy', 1, true, 2025‑07‑29 11:00Z, 'user‑456', 'user‑789', 2025‑07‑29 11:30Z)`

### requirement_changelog
| column | type | purpose |
|--------|------|---------|
| log_id | UUID PK | Log entry key |
| source_table | TEXT | Table changed |
| source_id | UUID | Record changed |
| change_type | TEXT | INSERT/UPDATE/DELETE |
| previous_value | JSONB | Before state |
| new_value | JSONB | After state |
| changed_by | UUID FK | User |
| changed_at | TIMESTAMPTZ | When |
| ip_address | TEXT | Client IP |
| user_agent | TEXT | Client info |

**Example** (Payer requirement update logged)  
`('log‑001', 'payer_requirement', 'pr‑001', 'UPDATE', '{"version":1,"required_fields":["member_id","dob"]}', '{"version":2,"required_fields":["member_id","dob","ssn"]}', 'user‑123', 2025‑07‑29 12:00Z, '10.0.0.1', 'RCM-Admin/1.0')`

### effective_requirements (Materialized View)
| column | type | purpose |
|--------|------|---------|
| portal_id | INT | Integration endpoint |
| org_id | UUID | Organization |
| portal_type_id | INT | Portal type |
| task_type_id | UUID | Task type |
| required_fields | JSONB | Merged requirements |
| optional_fields | JSONB | Merged optional |
| field_rules | JSONB | Merged rules |
| compliance_ref | TEXT | From payer |
| last_updated | TIMESTAMPTZ | View refresh |

**Example** (Computed requirements for North Clinic Anthem)  
`(17, '7b1d‑1111‑…', 2, 'c101‑…', '["member_id","dob","ssn","internal_case_id"]', '["group_number"]', '{"member_id":{"pattern":"^W\d{9}$"}}', 'Anthem Guide 2025', 2025‑07‑29 13:00Z)`

---

## batch_job
| column | type | purpose |
|--------|------|---------|
| batch_id | UUID PK | Job key |
| org_id | UUID FK | Tenant |
| portal_id | INT FK | Endpoint |
| workflow_type | TEXT | `eligibility` |
| status | TEXT | `processing` |
| created_at / completed_at | TIMESTAMP | Timing |
| result_url | TEXT | Output file |

**Example**  
`('b9e9‑…', '7b1d‑1111‑…', 17, 'eligibility', 'queued', 2025‑07‑29 09:00Z, NULL, NULL)`

---

## batch_row
| column | type | purpose |
|--------|------|---------|
| row_id | UUID PK | Key |
| batch_id | UUID FK | Parent batch |
| row_idx | INT | Position |
| task_signature | UUID (SHA or FK) |
| trace_id | UUID | After exec |
| status | TEXT | `queued` |
| error_code / error_msg | TEXT | Failure reason |
| created_at / updated_at | TIMESTAMP | |

**Example**  
`('row‑aaa', 'b9e9‑…', 3, NULL, NULL, 'queued', NULL, NULL, 2025‑07‑29)`

---

## rcm_state
| column | type | purpose |
|--------|------|---------|
| state_id | UUID PK | |
| portal_id | INT FK | Endpoint |
| text_emb | VECTOR(768) | Text embed |
| image_emb | VECTOR(512) | Vision embed |
| semantic_spec | JSONB | State spec |
| action | JSONB | Selector |
| success_ema | FLOAT | EMA success |
| page_caption | TEXT | UI label |
| action_caption | TEXT | Action label |
| caption_conf | NUMERIC(3,2) | Confidence |
| macro_state_id | UUID | Cluster |
| is_retired | BOOLEAN | Flag |
| alias_state_id | UUID | Dedup pointer |

**Example**  
`('s‑login', 17, [0.01…], [0.02…], {...}, {"click":"#login"}, 0.93, 'Login', 'Click login', 0.91, NULL, false, NULL)`

---

## macro_state
| column | type | purpose |
|--------|------|---------|
| macro_state_id | UUID PK | |
| portal_id | INT FK | Endpoint |
| canonical_caption | TEXT | Cluster title |
| description | TEXT | Details |
| sample_state_id | UUID | Representative |

**Example**  
`('m‑auth', 17, 'Auth screen cluster', 'Any step in login accordion', 's‑login')`

---

## task_signature
| column | type | purpose |
|--------|------|---------|
| signature_id | UUID PK | Key |
| portal_id | INT FK (nullable) | Tenant copy |
| portal_type_id | INT FK (nullable) | Template copy |
| domain | task_domain | |
| action | task_action | |
| source | task_signature_source | `human` or `ai` |
| text_emb | VECTOR(768) | Text embed |
| image_emb | VECTOR(512) | Vision embed |
| sample_trace_id | UUID | Blob pointer |
| alias_of | UUID | Inherit pointer |
| composed | BOOLEAN | TRUE → stitched |
| updated_at | TIMESTAMPTZ | Stamp |

**Template example**  
`('tmpl‑elig‑uhc', NULL, 2, 'eligibility', 'status_check', 'ai', [vec], [vec], 'trace‑tmpl‑001', NULL, false, 2025‑07‑29)`

**Tenant alias example**  
`('sig‑north‑uhc', 17, NULL, 'eligibility', 'status_check', 'human', NULL, NULL, NULL, 'tmpl‑elig‑uhc', false, 2025‑07‑29)`

---

## rcm_trace
| column | type | purpose |
|--------|------|---------|
| trace_id | UUID PK | |
| portal_id | INT FK | Endpoint |
| org_id | UUID FK | Tenant |
| workflow_type | TEXT | `eligibility:status_check` |
| task_signature | UUID FK | Signature executed |
| prompt_version | VARCHAR(20) | LLM prompt tag |
| used_fallback | BOOLEAN | LLM fallback flag |
| fallback_model | TEXT | Model name |
| trace | JSONB | Ordered steps |
| duration_ms | INT | Runtime |
| success | BOOLEAN | Outcome |
| created_at | TIMESTAMP | |

**Example**  
`('tr‑123', 17, '7b1d‑1111‑…', 'eligibility:status_check', 'sig‑north‑uhc', 'v2', false, NULL, {...}, 9123, true, 2025‑07‑29 09:05Z)`