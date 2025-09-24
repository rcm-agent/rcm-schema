# RCM Schema V8 Migration Guide

## Overview

This guide provides a comprehensive roadmap for migrating the RCM system from the current schema to V8, which introduces multi-tenancy, graph-based workflows, and vector embeddings for ML capabilities.

## Major Changes

### 1. Multi-Tenant Architecture
- Added `organization` table with org_id propagated throughout
- All data is now scoped to organizations
- Default organization created for existing data

### 2. Lookup Tables Replace ENUMs
- All PostgreSQL ENUMs converted to lookup tables
- More flexible, allows runtime additions
- Foreign key relationships ensure data integrity

### 3. Graph-Based Workflows
- New `workflow_node` and `workflow_transition` tables
- Replaces linear workflow model
- Supports complex, branching workflows

### 4. Vector Embeddings
- `micro_state` table with 768-dimensional text embeddings
- Enables similarity search for UI states
- Requires pgvector extension

### 5. Table Renames
- `rcm_user` → `app_user`
- `rcm_trace` → `workflow_trace`
- `integration_endpoint` → `endpoint` + `channel_type`

### 6. Bridge Tables
- `workflow_trace_endpoint` for multi-endpoint traces
- `user_workflow_channel_type` for workflow-channel mapping
- `user_workflow_task_type` for workflow-task mapping

## Migration Strategy

### Phase 1: Database Migration

```bash
# 1. Backup existing database
pg_dump -h localhost -U postgres -d rcm_db > rcm_backup_$(date +%Y%m%d).sql

# 2. Enable required extensions
psql -U postgres -d rcm_db -c "CREATE EXTENSION IF NOT EXISTS pgvector;"

# 3. Run migration
cd rcm-schema
alembic upgrade 007_migrate_v8

# 4. Verify migration
psql -U postgres -d rcm_db -c "SELECT * FROM alembic_version;"
```

### Phase 2: Update rcm-schema Package

```bash
# Update models
cp models_v8.py models.py
cp schemas_v8.py schemas.py

# Update dependencies
echo "pgvector==0.2.5" >> requirements.txt
pip install -r requirements.txt

# Run tests
pytest tests/
```

### Phase 3: Service Updates

## Service-Specific Migration Instructions

### rcm-orchestrator

1. **Update Models**
```python
# rcm-orchestrator/models/rcm_models.py
# Replace with new V8 models or import from rcm-schema
from rcm_schema.models_v8 import *
```

2. **Add Organization Context**
```python
# rcm-orchestrator/core/context.py
from typing import Optional
from uuid import UUID

class RequestContext:
    """Request context for multi-tenancy"""
    def __init__(self, org_id: UUID, user_id: Optional[UUID] = None):
        self.org_id = org_id
        self.user_id = user_id

# Middleware to extract org_id from JWT
from fastapi import Request, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

async def get_current_org(request: Request) -> UUID:
    """Extract org_id from JWT token"""
    # Implementation depends on your auth system
    auth = HTTPBearer()
    credentials = await auth(request)
    # Decode JWT and extract org_id
    return org_id
```

3. **Update Database Queries**
```python
# Before
batch_jobs = await session.execute(
    select(BatchJob).where(BatchJob.user_id == user_id)
)

# After - with org filtering
batch_jobs = await session.execute(
    select(BatchJob)
    .join(AppUser)
    .where(
        BatchJob.user_id == user_id,
        AppUser.org_id == request_context.org_id
    )
)
```

4. **Update API Endpoints**
```python
# rcm-orchestrator/api/v1/batch_jobs.py
from fastapi import Depends

@router.post("/batch-jobs")
async def create_batch_job(
    job: BatchJobCreate,
    org_id: UUID = Depends(get_current_org),
    db: AsyncSession = Depends(get_db)
):
    # Ensure user belongs to org
    user = await db.get(AppUser, job.user_id)
    if user.org_id != org_id:
        raise HTTPException(403, "Access denied")
    
    # Create job
    db_job = BatchJob(**job.dict())
    db.add(db_job)
    await db.commit()
    return db_job
```

### rcm-memory

1. **Update Models with Vector Support**
```python
# rcm-memory/src/models/database.py
from pgvector.sqlalchemy import Vector
from rcm_schema.models_v8 import *

# Ensure vector operations are registered
from sqlalchemy import create_engine
engine = create_engine("postgresql://...", echo=True)

# Register vector extension
with engine.connect() as conn:
    conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
    conn.commit()
```

2. **Add Vector Search Capabilities**
```python
# rcm-memory/src/services/micro_state_service.py
from sqlalchemy import select
from pgvector.sqlalchemy import Vector

class MicroStateService:
    async def find_similar_states(
        self, 
        embedding: List[float], 
        org_id: UUID,
        threshold: float = 0.8,
        limit: int = 10
    ):
        """Find similar micro states using vector similarity"""
        # Convert to numpy array
        query_vector = np.array(embedding)
        
        # Use pgvector's <-> operator for cosine distance
        results = await self.db.execute(
            select(MicroState)
            .join(UserWorkflow)
            .join(WorkflowNode)
            .where(
                MicroState.is_retired == False,
                # Add org filtering through relationships
            )
            .order_by(
                MicroState.text_emb.cosine_distance(query_vector)
            )
            .limit(limit)
        )
        
        return results.scalars().all()
```

3. **Update Memory Storage**
```python
# rcm-memory/src/services/memory_service.py
class MemoryService:
    def __init__(self, embedding_service: EmbeddingService):
        self.embedding_service = embedding_service
    
    async def store_micro_state(
        self,
        workflow_id: UUID,
        node_id: int,
        dom_snapshot: str,
        action_json: dict,
        org_id: UUID
    ):
        # Generate embedding
        text_content = f"{dom_snapshot} {json.dumps(action_json)}"
        embedding = await self.embedding_service.embed_text(text_content)
        
        # Create micro state
        micro_state = MicroState(
            workflow_id=workflow_id,
            node_id=node_id,
            dom_snapshot=dom_snapshot,
            action_json=action_json,
            text_emb=embedding
        )
        
        self.db.add(micro_state)
        await self.db.commit()
        return micro_state
```

### rcm-web-agent

1. **Update Domain Models**
```python
# rcm-web-agent/src/models/rcm.py
from rcm_schema.schemas_v8 import (
    TaskDomain, TaskAction, JobStatus,
    BatchJob, BatchJobItem, WorkflowTrace
)
```

2. **Update Memory Client**
```python
# rcm-web-agent/src/clients/memory_client.py
class MemoryClient:
    def __init__(self, base_url: str, org_id: UUID):
        self.base_url = base_url
        self.org_id = org_id
        self.session = httpx.AsyncClient()
    
    async def store_trace(self, trace_data: dict):
        """Store workflow trace with org context"""
        trace_data['org_id'] = str(self.org_id)
        
        response = await self.session.post(
            f"{self.base_url}/api/v1/traces",
            json=trace_data,
            headers={"X-Org-ID": str(self.org_id)}
        )
        response.raise_for_status()
        return response.json()
```

3. **Update Workflow Execution**
```python
# rcm-web-agent/src/services/workflow_service.py
class WorkflowService:
    async def execute_workflow(
        self,
        workflow_id: UUID,
        input_data: dict,
        org_id: UUID
    ):
        # Fetch workflow definition
        workflow = await self.memory_client.get_workflow(
            workflow_id, org_id
        )
        
        # Execute graph-based workflow
        executor = GraphWorkflowExecutor(workflow)
        result = await executor.execute(input_data)
        
        # Store execution trace
        trace = WorkflowTraceCreate(
            org_id=org_id,
            workflow_id=workflow_id,
            action_type="workflow_execution",
            action_detail={"input": input_data, "output": result},
            success=True,
            duration_ms=executor.duration_ms
        )
        
        await self.memory_client.store_trace(trace.dict())
        return result
```

## Testing Strategy

### 1. Unit Tests
```python
# tests/test_multi_tenancy.py
import pytest
from uuid import uuid4

@pytest.mark.asyncio
async def test_org_isolation(db_session):
    """Test that data is properly isolated by organization"""
    org1 = Organization(name="Org1", org_type="hospital")
    org2 = Organization(name="Org2", org_type="billing_firm")
    
    db_session.add_all([org1, org2])
    await db_session.commit()
    
    # Create users in different orgs
    user1 = AppUser(org_id=org1.org_id, email="user1@org1.com", role="operator")
    user2 = AppUser(org_id=org2.org_id, email="user2@org2.com", role="operator")
    
    db_session.add_all([user1, user2])
    await db_session.commit()
    
    # Verify isolation
    org1_users = await db_session.execute(
        select(AppUser).where(AppUser.org_id == org1.org_id)
    )
    assert len(org1_users.scalars().all()) == 1
```

### 2. Integration Tests
```python
# tests/test_workflow_execution.py
@pytest.mark.integration
async def test_graph_workflow_execution():
    """Test graph-based workflow execution"""
    # Create workflow nodes
    start_node = WorkflowNode(code="start", description="Start node")
    process_node = WorkflowNode(code="process", description="Process data")
    end_node = WorkflowNode(code="end", description="End node")
    
    # Create transitions
    transitions = [
        WorkflowTransition(
            from_node=start_node.node_id,
            to_node=process_node.node_id,
            action_label="begin"
        ),
        WorkflowTransition(
            from_node=process_node.node_id,
            to_node=end_node.node_id,
            action_label="complete"
        )
    ]
    
    # Execute workflow
    executor = GraphWorkflowExecutor(nodes, transitions)
    result = await executor.execute({"input": "test"})
    
    assert result["status"] == "completed"
```

### 3. Performance Tests
```python
# tests/test_vector_search_performance.py
import time
import numpy as np

@pytest.mark.performance
async def test_vector_search_performance(db_session):
    """Test vector similarity search performance"""
    # Insert 10k micro states with random embeddings
    states = []
    for i in range(10000):
        embedding = np.random.rand(768).tolist()
        state = MicroState(
            workflow_id=uuid4(),
            node_id=1,
            dom_snapshot=f"snapshot_{i}",
            action_json={"action": f"test_{i}"},
            text_emb=embedding
        )
        states.append(state)
    
    db_session.add_all(states)
    await db_session.commit()
    
    # Search for similar states
    query_embedding = np.random.rand(768).tolist()
    
    start_time = time.time()
    results = await db_session.execute(
        select(MicroState)
        .order_by(
            MicroState.text_emb.cosine_distance(query_embedding)
        )
        .limit(10)
    )
    duration = time.time() - start_time
    
    assert duration < 0.1  # Should complete in under 100ms
    assert len(results.scalars().all()) == 10
```

## Rollback Plan

If issues arise during migration:

```bash
# 1. Restore database backup
psql -U postgres -c "DROP DATABASE rcm_db;"
psql -U postgres -c "CREATE DATABASE rcm_db;"
psql -U postgres -d rcm_db < rcm_backup_20250801.sql

# 2. Revert code changes
git checkout main
git pull origin main

# 3. Restart services
docker-compose down
docker-compose up -d
```

## Monitoring

After migration, monitor:

1. **Database Performance**
   - Query execution times
   - Index usage
   - Connection pool metrics

2. **API Response Times**
   - Endpoint latencies
   - Error rates
   - Throughput

3. **Vector Search Performance**
   - Search query times
   - Index build times
   - Memory usage

## Timeline

- **Week 1**: Database migration and testing
- **Week 2**: Update rcm-orchestrator
- **Week 3**: Update rcm-memory
- **Week 4**: Update rcm-web-agent
- **Week 5**: Integration testing
- **Week 6**: Performance tuning and monitoring

## Support

For questions or issues during migration:
- Create tickets in the project issue tracker
- Contact the architecture team
- Refer to the V8 schema documentation