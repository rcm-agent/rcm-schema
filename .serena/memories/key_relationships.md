# RCM Schema Key Relationships

## Multi-Tenancy Root
```
organization (org_id)
    ├── app_user (org_id)
    ├── endpoint (org_id)
    ├── batch_job (org_id)
    └── workflow_trace (org_id)
```

## Channel/Endpoint Hierarchy
```
channel_type (channel_type_id)
    └── endpoint (channel_type_id, org_id)
        └── portal_credential (endpoint_id)
```

## Graph Workflow System
```
workflow_node (node_id)
    ├── workflow_transition (from_node, to_node)
    └── micro_state (node_id)
        └── user_workflow (workflow_id)
```

## Task Type System
```
task_type (task_type_id)
    ├── field_requirement (task_type_id) [deprecated]
    ├── payer_requirement (task_type_id)
    ├── org_requirement_policy (task_type_id)
    └── task_signature (domain, action)
```

## Batch Processing Chain
```
batch_job (batch_job_id)
    └── batch_job_item (batch_job_id)
        └── workflow_trace (batch_job_item_id)
            └── workflow_trace_endpoint (trace_id, endpoint_id)
```

## Key Foreign Key Rules
- **CASCADE DELETE**: Most child tables cascade delete with parent
- **RESTRICT**: User references prevent deletion if data exists
- **SET NULL**: Optional relationships nullify on parent deletion

## Important Unique Constraints
- organization(name)
- app_user(email)
- channel_type(code)
- endpoint(org_id, channel_type_id)
- endpoint(org_id, name)
- task_type(domain, action)
- workflow_transition(from_node, to_node, action_label)