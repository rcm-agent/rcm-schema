# Hybrid RCM Platform – Database Reference (v8 • 2025-08-01)
_Complete V8 schema with multi-tenancy, graph workflows, and ML capabilities._

> **Migration Note**: This is the V8 schema. For V3 documentation, see [hybrid_rcm_db_guide.md](hybrid_rcm_db_guide.md)

---

## Lookup Tables (Replacing ENUMs)

V8 replaces PostgreSQL ENUMs with lookup tables for runtime flexibility:

### task_domain_lu
| domain | description |
|--------|-------------|
| `eligibility` | Eligibility verification |
| `prior_auth` | Prior authorization |
| `claim` | Claims processing |
| `payment` | Payment posting |
| `patient` | Patient management |
| `provider` | Provider management |
| `billing` | Billing operations |
| `reporting` | Report generation |
| `document` | Document management |

### task_action_lu
| action | description |
|--------|-------------|
| `check` | Check status |
| `verify` | Verify information |
| `update` | Update data |
| `submit` | Submit request |
| `check_status` | Check processing status |
| `appeal` | File appeal |
| `extend` | Extend deadline |
| `submit_claim` | Submit claim |
| `status_check` | Status inquiry |
| `resubmit` | Resubmit request |
| `void` | Void/cancel |
| `correct` | Make correction |
| `post` | Post payment |
| `reconcile` | Reconcile accounts |
| `adjust` | Make adjustment |
| `refund` | Process refund |
| ... | (20+ more actions) |

### job_status_lu
| status | description |
|--------|-------------|
| `pending` | Awaiting processing |
| `processing` | Currently running |
| `completed` | Successfully finished |
| `failed` | Error occurred |
| `partially_completed` | Some items succeeded |

### user_role_lu
| role | description |
|------|-------------|
| `admin` | Full access |
| `operator` | Execute workflows |
| `viewer` | Read-only access |
| `api_user` | API access only |
| `org_admin` | Organization admin |
| `firm_user` | Billing firm user |
| `hospital_user` | Hospital user |
| `sys_admin` | System administrator |

---

## Core Multi-Tenant Tables

### organization
| column | type | constraints | purpose |
|--------|------|-------------|---------|
| org_id | UUID | PRIMARY KEY | Organization identifier |
| org_type | TEXT | CHECK IN ('hospital','billing_firm','credentialer') | Organization type |
| name | TEXT | UNIQUE NOT NULL | Organization name |
| email_domain | TEXT | UNIQUE | SSO domain |
| created_at | TIMESTAMPTZ | NOT NULL DEFAULT now() | Creation timestamp |

**Example**  
```sql
('7b1d-1111-...', 'hospital', 'North Medical Center', 'northmed.org', '2025-08-01 10:00:00Z')
('8c2e-2222-...', 'billing_firm', 'Revenue Partners LLC', 'revpartners.com', '2025-08-01 11:00:00Z')
```

### app_user (renamed from rcm_user)
| column | type | constraints | purpose |
|--------|------|-------------|---------|
| user_id | UUID | PRIMARY KEY | User identifier |
| org_id | UUID | FK → organization | Organization association |
| email | TEXT | UNIQUE NOT NULL | User email |
| full_name | TEXT | NOT NULL | Display name |
| role | TEXT | FK → user_role_lu | User role |
| is_active | BOOLEAN | DEFAULT true | Active status |
| api_key_ssm_parameter_name | TEXT | | AWS SSM parameter |
| created_at | TIMESTAMPTZ | NOT NULL | Creation time |
| updated_at | TIMESTAMPTZ | NOT NULL | Last update |
| last_login_at | TIMESTAMPTZ | | Last login time |

**Example**  
```sql
('user-123', '7b1d-1111-...', 'john@northmed.org', 'John Doe', 'operator', true, '/rcm/keys/john', '2025-08-01 12:00:00Z', '2025-08-01 12:00:00Z', '2025-08-01 14:00:00Z')
```

---

## Channel & Endpoint Abstraction

### channel_type (replaces portal_type)
| column | type | constraints | purpose |
|--------|------|-------------|---------|
| channel_type_id | BIGINT | PRIMARY KEY IDENTITY | Channel type ID |
| code | TEXT | UNIQUE | Internal code |
| name | TEXT | NOT NULL | Display name |
| base_url | TEXT | | Default URL |
| endpoint_kind | TEXT | CHECK IN ('payer','provider','clearinghouse') | Endpoint type |
| access_medium | TEXT | CHECK IN ('web','phone','fax','efax','edi') | Access method |

**Example**  
```sql
(1, 'anthem_availity', 'Anthem via Availity', 'https://availity.com', 'payer', 'web')
(2, 'uhc_portal', 'UnitedHealthcare Portal', 'https://provider.uhc.com', 'payer', 'web')
(3, 'medicaid_phone', 'State Medicaid Phone', NULL, 'payer', 'phone')
```

### endpoint (replaces integration_endpoint)
| column | type | constraints | purpose |
|--------|------|-------------|---------|
| endpoint_id | BIGINT | PRIMARY KEY IDENTITY | Endpoint ID |
| org_id | UUID | FK → organization | Organization |
| name | TEXT | NOT NULL | Display name |
| channel_type_id | BIGINT | FK → channel_type | Channel type |
| base_url | TEXT | | Override URL |
| config | JSONB | DEFAULT '{}' | Configuration |
| created_at | TIMESTAMPTZ | NOT NULL | Creation time |

**Constraints**: UNIQUE(org_id, channel_type_id), UNIQUE(org_id, name)

**Example**  
```sql
(1, '7b1d-1111-...', 'Anthem Production', 1, NULL, '{"region": "midwest"}', '2025-08-01 12:00:00Z')
(2, '7b1d-1111-...', 'UHC Production', 2, 'https://custom.uhc.com', '{"api_version": "2.0"}', '2025-08-01 12:00:00Z')
```

---

## Graph-Based Workflow Tables

### workflow_node
| column | type | constraints | purpose |
|--------|------|-------------|---------|
| node_id | BIGINT | PRIMARY KEY IDENTITY | Node identifier |
| code | TEXT | UNIQUE | Node code |
| description | TEXT | | Node description |
| metadata | JSONB | | Node metadata |
| label_conf | NUMERIC(3,2) | | Labeling confidence |
| last_label_at | TIMESTAMPTZ | | Last labeled |

**Example**  
```sql
(1, 'login_portal', 'Login to payer portal', '{"portal_type": "payer"}', 0.95, '2025-08-01 10:00:00Z')
(2, 'search_patient', 'Search for patient', '{"search_fields": ["name", "dob", "member_id"]}', 0.90, '2025-08-01 10:00:00Z')
(3, 'verify_eligibility', 'Verify eligibility status', '{"output_fields": ["coverage", "copay"]}', 0.85, '2025-08-01 10:00:00Z')
```

### workflow_transition
| column | type | constraints | purpose |
|--------|------|-------------|---------|
| from_node | BIGINT | FK → workflow_node | Source node |
| to_node | BIGINT | FK → workflow_node | Target node |
| action_label | TEXT | NOT NULL | Transition action |
| freq | INTEGER | DEFAULT 1 CHECK >= 1 | Frequency count |

**Primary Key**: (from_node, to_node, action_label)

**Example**  
```sql
(1, 2, 'login_success', 150)  -- login_portal → search_patient
(2, 3, 'patient_found', 145)  -- search_patient → verify_eligibility
(1, 1, 'login_retry', 5)      -- login_portal → login_portal (retry)
```

### user_workflow
| column | type | constraints | purpose |
|--------|------|-------------|---------|
| workflow_id | UUID | PRIMARY KEY | Workflow instance |
| name | TEXT | NOT NULL | Workflow name |
| description | TEXT | | Description |
| required_data | JSONB | DEFAULT '[]' | Required inputs |
| created_at | TIMESTAMPTZ | NOT NULL | Creation time |
| updated_at | TIMESTAMPTZ | NOT NULL | Last update |

**Example**  
```sql
('wf-123', 'Eligibility Check Workflow', 'Standard eligibility verification process', '["patient_name", "dob", "member_id"]', '2025-08-01 10:00:00Z', '2025-08-01 10:00:00Z')
```

---

## ML-Powered State Management

### micro_state
| column | type | constraints | purpose |
|--------|------|-------------|---------|
| micro_state_id | BIGINT | PRIMARY KEY IDENTITY | State ID |
| workflow_id | UUID | FK → user_workflow | Workflow |
| node_id | BIGINT | FK → workflow_node | Current node |
| dom_snapshot | TEXT | NOT NULL | DOM HTML |
| action_json | JSONB | NOT NULL | Action data |
| semantic_spec | JSONB | | Semantic info |
| label | TEXT | | State label |
| category | TEXT | | State category |
| required | BOOLEAN | DEFAULT FALSE | Required state |
| is_dynamic | BOOLEAN | COMPUTED | Has dynamic content |
| text_emb | vector(768) | NOT NULL | Text embedding |
| mini_score | NUMERIC(4,3) | | Similarity score |
| is_retired | BOOLEAN | DEFAULT false | Retired flag |
| aliased_to | BIGINT | FK → micro_state | Alias target |
| created_at | TIMESTAMPTZ | NOT NULL | Creation time |

**Index**: HNSW index on text_emb for vector similarity search

**Example**  
```sql
(1, 'wf-123', 1, '<html>...</html>', '{"action": "click", "element": "login"}', '{"page_type": "login"}', 'login_page', 'authentication', true, false, '[0.123, -0.456, ...]', 0.95, false, NULL, '2025-08-01 10:00:00Z')
```

---

## Execution & Trace Tables

### workflow_trace (renamed from rcm_trace)
| column | type | constraints | purpose |
|--------|------|-------------|---------|
| trace_id | BIGINT | PRIMARY KEY IDENTITY | Trace ID |
| org_id | UUID | FK → organization | Organization |
| workflow_id | UUID | FK → user_workflow | Workflow |
| batch_job_item_id | BIGINT | FK → batch_job_item | Batch item |
| action_type | TEXT | NOT NULL | Action type |
| action_detail | JSONB | | Action details |
| success | BOOLEAN | DEFAULT false | Success flag |
| duration_ms | INTEGER | | Duration |
| error_detail | TEXT | | Error message |
| llm_prompt | TEXT | | LLM prompt |
| llm_response | TEXT | | LLM response |
| llm_model | TEXT | | Model used |
| llm_tokens_used | INTEGER | | Token count |
| tier | SMALLINT | | Execution tier |
| tier_reason | TEXT | | Tier rationale |
| created_at | TIMESTAMPTZ | NOT NULL | Creation time |
| user_id | UUID | FK → app_user | User |
| session_id | TEXT | | Session ID |

**Example**  
```sql
(1, '7b1d-1111-...', 'wf-123', 1, 'navigate', '{"url": "https://portal.com"}', true, 1500, NULL, 'Navigate to portal', 'Navigated successfully', 'gpt-4', 150, 1, 'standard', '2025-08-01 10:00:00Z', 'user-123', 'sess-456')
```

### workflow_trace_endpoint
| column | type | constraints | purpose |
|--------|------|-------------|---------|
| trace_id | BIGINT | FK → workflow_trace | Trace |
| endpoint_id | BIGINT | FK → endpoint | Endpoint |

**Primary Key**: (trace_id, endpoint_id)

---

## Batch Processing

### batch_job
| column | type | constraints | purpose |
|--------|------|-------------|---------|
| batch_job_id | BIGINT | PRIMARY KEY IDENTITY | Job ID |
| org_id | UUID | FK → organization | Organization |
| prompt | TEXT | NOT NULL | Job description |
| file_name | TEXT | | Input file |
| file_path | TEXT | | File location |
| total_rows | INTEGER | DEFAULT 0 | Row count |
| processed_rows | INTEGER | DEFAULT 0 | Processed count |
| successful_rows | INTEGER | DEFAULT 0 | Success count |
| failed_rows | INTEGER | DEFAULT 0 | Failed count |
| status | TEXT | FK → job_status_lu | Job status |
| created_at | TIMESTAMPTZ | NOT NULL | Creation time |
| updated_at | TIMESTAMPTZ | NOT NULL | Last update |
| completed_at | TIMESTAMPTZ | | Completion time |
| created_by | UUID | FK → app_user | Creator |

### batch_job_item (renamed from batch_row)
| column | type | constraints | purpose |
|--------|------|-------------|---------|
| batch_job_item_id | BIGINT | PRIMARY KEY IDENTITY | Item ID |
| batch_job_id | BIGINT | FK → batch_job | Parent job |
| row_number | INTEGER | NOT NULL | Row index |
| input_data | JSONB | NOT NULL | Input data |
| output_data | JSONB | | Output data |
| status | TEXT | FK → job_status_lu | Item status |
| error_message | TEXT | | Error detail |
| created_at | TIMESTAMPTZ | NOT NULL | Creation time |
| updated_at | TIMESTAMPTZ | NOT NULL | Last update |
| completed_at | TIMESTAMPTZ | | Completion time |

---

## Backward Compatibility Views

### rcm_user (view → app_user)
```sql
CREATE VIEW rcm_user AS
SELECT 
    user_id as id,
    email,
    full_name,
    role,
    is_active,
    api_key_ssm_parameter_name,
    created_at,
    updated_at,
    last_login_at
FROM app_user;
```

### rcm_trace (view → workflow_trace)
```sql
CREATE VIEW rcm_trace AS
SELECT 
    trace_id as id,
    batch_job_item_id,
    (SELECT ct.code FROM workflow_trace_endpoint wte 
     JOIN endpoint e ON wte.endpoint_id = e.endpoint_id
     JOIN channel_type ct ON e.channel_type_id = ct.channel_type_id
     WHERE wte.trace_id = workflow_trace.trace_id
     LIMIT 1) as portal_id,
    action_type,
    action_detail,
    success,
    duration_ms,
    error_detail,
    llm_prompt,
    llm_response,
    llm_model,
    llm_tokens_used,
    created_at,
    user_id,
    session_id
FROM workflow_trace;
```

---

## Key V8 Features

1. **Multi-Tenancy**: All tenant data includes org_id with RLS policies
2. **Graph Workflows**: DAG-based execution with workflow_node and workflow_transition
3. **Vector Search**: 768D embeddings in micro_state with HNSW indexing
4. **Dynamic Schema**: Lookup tables replace ENUMs for runtime flexibility
5. **Channel Abstraction**: Flexible portal configuration without code changes
6. **Backward Compatibility**: Views maintain legacy interfaces
7. **Audit Trail**: Complete tracking with organization context

---

## Migration Notes

- Default organization created for existing data
- Table renames: rcm_user → app_user, rcm_trace → workflow_trace
- ENUMs replaced with lookup tables
- New primary keys: user_id (UUID), trace_id (BIGINT)
- Multi-endpoint support via workflow_trace_endpoint
- Vector dimensions: 768D for micro_state, 1024D for memory service