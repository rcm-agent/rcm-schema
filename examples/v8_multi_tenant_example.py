"""
Example implementation of V8 multi-tenant features
Demonstrates best practices for the new schema
"""
import asyncio
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Optional, List
from uuid import UUID, uuid4

from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import selectinload
import jwt
import numpy as np

# Import V8 models and schemas
from models_v8 import (
    Base, Organization, AppUser, Endpoint, ChannelType,
    TaskType, BatchJob, BatchJobItem, WorkflowTrace,
    MicroState, UserWorkflow, WorkflowNode
)
from schemas_v8 import (
    OrganizationCreate, AppUserCreate, BatchJobCreate,
    WorkflowTraceCreate, MicroStateCreate
)


# ============================================================================
# Database Setup
# ============================================================================

DATABASE_URL = "postgresql+asyncpg://postgres:password@localhost/rcm_v8"
JWT_SECRET = "your-secret-key"
JWT_ALGORITHM = "HS256"

# Create async engine
engine = create_async_engine(DATABASE_URL, echo=True)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)


async def get_db():
    """Dependency to get database session"""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


# ============================================================================
# Authentication & Multi-tenancy
# ============================================================================

security = HTTPBearer()


class TokenData:
    """JWT token payload"""
    def __init__(self, user_id: UUID, org_id: UUID, email: str, role: str):
        self.user_id = user_id
        self.org_id = org_id
        self.email = email
        self.role = role


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db)
) -> TokenData:
    """Extract and validate user from JWT token"""
    try:
        payload = jwt.decode(
            credentials.credentials,
            JWT_SECRET,
            algorithms=[JWT_ALGORITHM]
        )
        token_data = TokenData(
            user_id=UUID(payload["user_id"]),
            org_id=UUID(payload["org_id"]),
            email=payload["email"],
            role=payload["role"]
        )
        
        # Verify user still exists and is active
        user = await db.get(AppUser, token_data.user_id)
        if not user or not user.is_active:
            raise HTTPException(status_code=401, detail="User not found or inactive")
        
        return token_data
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid authentication")


class OrgContext:
    """Request context for organization scoping"""
    def __init__(self, org_id: UUID, user: TokenData):
        self.org_id = org_id
        self.user = user
    
    def check_access(self, resource_org_id: UUID):
        """Check if user can access resource in given org"""
        if self.user.role == "sys_admin":
            return True
        if resource_org_id != self.org_id:
            raise HTTPException(status_code=403, detail="Access denied")
        return True


async def get_org_context(
    current_user: TokenData = Depends(get_current_user)
) -> OrgContext:
    """Get organization context for request"""
    return OrgContext(current_user.org_id, current_user)


# ============================================================================
# Repository Pattern for Data Access
# ============================================================================

class BaseRepository:
    """Base repository with org filtering"""
    def __init__(self, db: AsyncSession, org_context: OrgContext):
        self.db = db
        self.org_context = org_context
    
    async def _filter_by_org(self, query, model):
        """Add org filtering to query if model has org_id"""
        if hasattr(model, 'org_id'):
            return query.where(model.org_id == self.org_context.org_id)
        return query


class BatchJobRepository(BaseRepository):
    """Repository for batch job operations"""
    
    async def create(self, job_data: BatchJobCreate) -> BatchJob:
        """Create new batch job"""
        # Verify user belongs to org
        user = await self.db.get(AppUser, job_data.user_id)
        self.org_context.check_access(user.org_id)
        
        # Create job
        job = BatchJob(**job_data.dict())
        self.db.add(job)
        await self.db.flush()
        return job
    
    async def get_by_id(self, job_id: UUID) -> Optional[BatchJob]:
        """Get batch job by ID with org filtering"""
        query = select(BatchJob).where(BatchJob.batch_job_id == job_id)
        query = query.join(AppUser).where(AppUser.org_id == self.org_context.org_id)
        
        result = await self.db.execute(query)
        return result.scalar_one_or_none()
    
    async def list_for_org(self, limit: int = 100) -> List[BatchJob]:
        """List batch jobs for organization"""
        query = (
            select(BatchJob)
            .join(AppUser)
            .where(AppUser.org_id == self.org_context.org_id)
            .order_by(BatchJob.created_at.desc())
            .limit(limit)
        )
        
        result = await self.db.execute(query)
        return result.scalars().all()


class WorkflowTraceRepository(BaseRepository):
    """Repository for workflow traces"""
    
    async def create(self, trace_data: WorkflowTraceCreate) -> WorkflowTrace:
        """Create workflow trace with multi-endpoint support"""
        # Verify org access
        self.org_context.check_access(trace_data.org_id)
        
        # Extract endpoint IDs
        endpoint_ids = trace_data.endpoint_ids
        trace_dict = trace_data.dict()
        del trace_dict['endpoint_ids']
        
        # Create trace
        trace = WorkflowTrace(**trace_dict)
        self.db.add(trace)
        await self.db.flush()
        
        # Add endpoint associations
        for endpoint_id in endpoint_ids:
            await self.db.execute(
                text("""
                    INSERT INTO workflow_trace_endpoint (trace_id, endpoint_id)
                    VALUES (:trace_id, :endpoint_id)
                """),
                {"trace_id": trace.trace_id, "endpoint_id": endpoint_id}
            )
        
        return trace
    
    async def search_by_timerange(
        self,
        start_time: datetime,
        end_time: datetime,
        endpoint_id: Optional[int] = None
    ) -> List[WorkflowTrace]:
        """Search traces by time range with optional endpoint filter"""
        query = (
            select(WorkflowTrace)
            .where(
                and_(
                    WorkflowTrace.org_id == self.org_context.org_id,
                    WorkflowTrace.created_at >= start_time,
                    WorkflowTrace.created_at <= end_time
                )
            )
        )
        
        if endpoint_id:
            query = query.join(WorkflowTraceEndpoint).where(
                WorkflowTraceEndpoint.endpoint_id == endpoint_id
            )
        
        query = query.order_by(WorkflowTrace.created_at.desc())
        result = await self.db.execute(query)
        return result.scalars().all()


class MicroStateRepository(BaseRepository):
    """Repository for micro state operations with vector search"""
    
    async def create(self, state_data: MicroStateCreate) -> MicroState:
        """Create micro state with embedding"""
        # Verify workflow belongs to org (through complex join)
        # In practice, you'd add org_id to user_workflow for simpler queries
        
        state = MicroState(**state_data.dict())
        self.db.add(state)
        await self.db.flush()
        return state
    
    async def find_similar(
        self,
        embedding: List[float],
        workflow_id: UUID,
        threshold: float = 0.8,
        limit: int = 10
    ) -> List[MicroState]:
        """Find similar micro states using vector similarity"""
        # Use raw SQL for vector operations
        query = text("""
            SELECT ms.*
            FROM micro_state ms
            WHERE ms.workflow_id = :workflow_id
              AND ms.is_retired = false
              AND 1 - (ms.text_emb <=> :embedding::vector) > :threshold
            ORDER BY ms.text_emb <=> :embedding::vector
            LIMIT :limit
        """)
        
        result = await self.db.execute(
            query,
            {
                "workflow_id": workflow_id,
                "embedding": embedding,
                "threshold": threshold,
                "limit": limit
            }
        )
        
        return [MicroState(**row) for row in result.mappings()]


# ============================================================================
# Service Layer
# ============================================================================

class WorkflowExecutionService:
    """Service for executing graph-based workflows"""
    
    def __init__(
        self,
        db: AsyncSession,
        org_context: OrgContext,
        trace_repo: WorkflowTraceRepository
    ):
        self.db = db
        self.org_context = org_context
        self.trace_repo = trace_repo
    
    async def execute_workflow(
        self,
        workflow_id: UUID,
        input_data: dict,
        endpoint_ids: List[int]
    ) -> dict:
        """Execute a graph-based workflow"""
        start_time = datetime.utcnow()
        
        try:
            # Load workflow definition
            workflow = await self.db.get(UserWorkflow, workflow_id)
            if not workflow:
                raise ValueError("Workflow not found")
            
            # Load workflow nodes
            nodes_query = (
                select(WorkflowNode)
                .join(MicroState)
                .where(MicroState.workflow_id == workflow_id)
                .distinct()
            )
            nodes = await self.db.execute(nodes_query)
            workflow_nodes = {n.node_id: n for n in nodes.scalars()}
            
            # Execute workflow (simplified)
            result = await self._execute_graph(
                workflow_nodes,
                input_data,
                workflow.required_data
            )
            
            # Record trace
            duration_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)
            
            trace = await self.trace_repo.create(
                WorkflowTraceCreate(
                    org_id=self.org_context.org_id,
                    workflow_id=workflow_id,
                    action_type="workflow_execution",
                    action_detail={
                        "input": input_data,
                        "output": result,
                        "nodes_executed": len(workflow_nodes)
                    },
                    success=True,
                    duration_ms=duration_ms,
                    endpoint_ids=endpoint_ids,
                    user_id=self.org_context.user.user_id
                )
            )
            
            return {
                "trace_id": trace.trace_id,
                "result": result,
                "duration_ms": duration_ms
            }
            
        except Exception as e:
            # Record failure trace
            trace = await self.trace_repo.create(
                WorkflowTraceCreate(
                    org_id=self.org_context.org_id,
                    workflow_id=workflow_id,
                    action_type="workflow_execution",
                    action_detail={"input": input_data},
                    success=False,
                    error_detail={"error": str(e)},
                    endpoint_ids=endpoint_ids,
                    user_id=self.org_context.user.user_id
                )
            )
            raise
    
    async def _execute_graph(
        self,
        nodes: dict,
        input_data: dict,
        required_data: list
    ) -> dict:
        """Execute workflow graph (simplified implementation)"""
        # This would implement actual graph traversal logic
        # For now, return mock result
        return {
            "status": "completed",
            "processed_nodes": len(nodes),
            "output": {"mock": "result"}
        }


# ============================================================================
# API Application
# ============================================================================

app = FastAPI(title="RCM V8 Multi-Tenant API")


@app.on_event("startup")
async def startup():
    """Initialize database"""
    async with engine.begin() as conn:
        # Create tables if needed
        await conn.run_sync(Base.metadata.create_all)
        
        # Ensure pgvector extension
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))


@app.post("/api/v1/organizations", response_model=Organization)
async def create_organization(
    org_data: OrganizationCreate,
    db: AsyncSession = Depends(get_db),
    current_user: TokenData = Depends(get_current_user)
):
    """Create new organization (sys_admin only)"""
    if current_user.role != "sys_admin":
        raise HTTPException(status_code=403, detail="Only sys_admin can create organizations")
    
    org = Organization(**org_data.dict())
    db.add(org)
    await db.commit()
    await db.refresh(org)
    return org


@app.post("/api/v1/batch-jobs", response_model=BatchJob)
async def create_batch_job(
    job_data: BatchJobCreate,
    db: AsyncSession = Depends(get_db),
    org_context: OrgContext = Depends(get_org_context)
):
    """Create new batch job"""
    repo = BatchJobRepository(db, org_context)
    job = await repo.create(job_data)
    await db.commit()
    return job


@app.get("/api/v1/batch-jobs", response_model=List[BatchJob])
async def list_batch_jobs(
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
    org_context: OrgContext = Depends(get_org_context)
):
    """List batch jobs for organization"""
    repo = BatchJobRepository(db, org_context)
    return await repo.list_for_org(limit)


@app.post("/api/v1/workflows/{workflow_id}/execute")
async def execute_workflow(
    workflow_id: UUID,
    input_data: dict,
    endpoint_ids: List[int],
    db: AsyncSession = Depends(get_db),
    org_context: OrgContext = Depends(get_org_context)
):
    """Execute a workflow"""
    trace_repo = WorkflowTraceRepository(db, org_context)
    service = WorkflowExecutionService(db, org_context, trace_repo)
    
    result = await service.execute_workflow(
        workflow_id,
        input_data,
        endpoint_ids
    )
    
    await db.commit()
    return result


@app.get("/api/v1/traces/search", response_model=List[WorkflowTrace])
async def search_traces(
    start_time: datetime,
    end_time: datetime,
    endpoint_id: Optional[int] = None,
    db: AsyncSession = Depends(get_db),
    org_context: OrgContext = Depends(get_org_context)
):
    """Search workflow traces"""
    repo = WorkflowTraceRepository(db, org_context)
    return await repo.search_by_timerange(start_time, end_time, endpoint_id)


# ============================================================================
# Example Usage
# ============================================================================

async def example_usage():
    """Example of using the multi-tenant system"""
    async with AsyncSessionLocal() as db:
        # Create organizations
        hospital = Organization(
            name="City General Hospital",
            org_type="hospital",
            email_domain="citygeneral.com"
        )
        billing_firm = Organization(
            name="MedBill Solutions",
            org_type="billing_firm",
            email_domain="medbill.com"
        )
        
        db.add_all([hospital, billing_firm])
        await db.commit()
        
        # Create users in different orgs
        hospital_admin = AppUser(
            org_id=hospital.org_id,
            email="admin@citygeneral.com",
            full_name="Hospital Admin",
            role="org_admin"
        )
        
        billing_user = AppUser(
            org_id=billing_firm.org_id,
            email="user@medbill.com",
            full_name="Billing User",
            role="operator"
        )
        
        db.add_all([hospital_admin, billing_user])
        await db.commit()
        
        # Create channel types and endpoints
        web_channel = ChannelType(
            code="anthem-web",
            name="Anthem Web Portal",
            endpoint_kind="payer",
            access_medium="web"
        )
        
        db.add(web_channel)
        await db.commit()
        
        # Each org has their own endpoints
        hospital_endpoint = Endpoint(
            org_id=hospital.org_id,
            name="Hospital Anthem Access",
            channel_type_id=web_channel.channel_type_id,
            config={"timeout": 30, "retry": 3}
        )
        
        billing_endpoint = Endpoint(
            org_id=billing_firm.org_id,
            name="Billing Anthem Access",
            channel_type_id=web_channel.channel_type_id,
            config={"timeout": 60, "retry": 5}
        )
        
        db.add_all([hospital_endpoint, billing_endpoint])
        await db.commit()
        
        print(f"Created {hospital.name} with endpoint {hospital_endpoint.name}")
        print(f"Created {billing_firm.name} with endpoint {billing_endpoint.name}")
        
        # Demonstrate org isolation
        # Users can only see their org's data
        hospital_context = OrgContext(hospital.org_id, 
            TokenData(hospital_admin.user_id, hospital.org_id, 
                     hospital_admin.email, hospital_admin.role))
        
        repo = BatchJobRepository(db, hospital_context)
        jobs = await repo.list_for_org()
        print(f"Hospital sees {len(jobs)} batch jobs")


if __name__ == "__main__":
    # Run example
    asyncio.run(example_usage())
    
    # Start API server
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)