"""Integration tests for database operations."""
import pytest
from uuid import uuid4
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload

from rcm_schema import (
    Organization,
    PortalType,
    IntegrationEndpoint,
    TaskType,
    FieldRequirement,
    BatchJob,
    AppUser,
    RcmState,
)
from rcm_schema.schemas import (
    OrganizationCreate,
    TaskTypeCreate,
    BatchJobCreate,
)
from rcm_schema.database import DatabaseManager


@pytest.mark.integration
@pytest.mark.asyncio
class TestDatabaseConnection:
    """Test database connection and basic operations."""
    
    async def test_database_connection(self, db_manager):
        """Test database manager can connect."""
        assert await db_manager.health_check() is True
    
    async def test_database_session(self, db_manager):
        """Test getting database session."""
        async with db_manager.get_session() as session:
            result = await session.execute(text("SELECT 1"))
            assert result.scalar() == 1
    
    async def test_transaction_rollback(self, db_manager):
        """Test transaction rollback on error."""
        async with db_manager.get_session() as session:
            # Create an org
            org = Organization(
                org_type="hospital",
                name="Test Hospital"
            )
            session.add(org)
            await session.flush()
            
            # Verify it exists in this transaction
            result = await session.execute(
                select(Organization).where(Organization.name == "Test Hospital")
            )
            assert result.scalar_one_or_none() is not None
        
        # After rollback, it shouldn't exist
        async with db_manager.get_session() as session:
            result = await session.execute(
                select(Organization).where(Organization.name == "Test Hospital")
            )
            assert result.scalar_one_or_none() is None


@pytest.mark.integration
@pytest.mark.asyncio
class TestOrganizationCRUD:
    """Test Organization CRUD operations."""
    
    async def test_create_organization(self, async_session):
        """Test creating an organization."""
        org = Organization(
            org_type="hospital",
            name="Integration Test Hospital",
            email_domain="test-hospital.com"
        )
        async_session.add(org)
        await async_session.commit()
        
        # Verify created
        result = await async_session.execute(
            select(Organization).where(Organization.name == "Integration Test Hospital")
        )
        created_org = result.scalar_one()
        assert created_org.org_id is not None
        assert created_org.email_domain == "test-hospital.com"
    
    async def test_unique_constraint(self, async_session):
        """Test unique constraint on organization name."""
        # Create first org
        org1 = Organization(
            org_type="hospital",
            name="Unique Hospital"
        )
        async_session.add(org1)
        await async_session.commit()
        
        # Try to create duplicate
        org2 = Organization(
            org_type="billing_firm",
            name="Unique Hospital"  # Duplicate name
        )
        async_session.add(org2)
        
        with pytest.raises(IntegrityError):
            await async_session.commit()
    
    async def test_cascade_delete(self, async_session):
        """Test cascade delete of organization."""
        # Create org with user
        org = Organization(
            org_type="hospital",
            name="Delete Test Hospital"
        )
        async_session.add(org)
        await async_session.flush()
        
        user = AppUser(
            user_id=uuid4(),
            org_id=org.org_id,
            email="test@delete-hospital.com",
            role="org_admin"
        )
        async_session.add(user)
        await async_session.commit()
        
        # Delete org
        await async_session.delete(org)
        await async_session.commit()
        
        # Verify user was cascade deleted
        result = await async_session.execute(
            select(AppUser).where(AppUser.email == "test@delete-hospital.com")
        )
        assert result.scalar_one_or_none() is None


@pytest.mark.integration
@pytest.mark.asyncio
class TestTaskTypeWorkflow:
    """Test task type and field requirement workflow."""
    
    async def test_create_task_type_with_requirements(self, async_session):
        """Test creating task type with field requirements."""
        # Create task type
        task_type = TaskType(
            domain="eligibility",
            action="status_check",
            display_name="Eligibility Status Check",
            description="Check patient eligibility status"
        )
        async_session.add(task_type)
        await async_session.flush()
        
        # Add field requirements
        field_req = FieldRequirement(
            task_type_id=task_type.task_type_id,
            required_fields=["patient_id", "insurance_id", "dob"],
            optional_fields=["group_number"],
            field_metadata={
                "patient_id": {"type": "string", "max_length": 20},
                "dob": {"type": "date", "format": "YYYY-MM-DD"}
            }
        )
        async_session.add(field_req)
        await async_session.commit()
        
        # Verify relationship
        result = await async_session.execute(
            select(TaskType)
            .where(TaskType.task_type_id == task_type.task_type_id)
            .options(selectinload(TaskType.field_requirements))
        )
        loaded_task = result.scalar_one()
        assert len(loaded_task.field_requirements) == 1
        assert "patient_id" in loaded_task.field_requirements[0].required_fields


@pytest.mark.integration  
@pytest.mark.asyncio
class TestBatchJobWorkflow:
    """Test batch job creation and workflow."""
    
    async def test_create_batch_job_with_task_type(self, async_session):
        """Test creating batch job linked to task type."""
        # Setup: Create org, portal type, portal, and task type
        org = Organization(
            org_type="hospital",
            name="Batch Test Hospital"
        )
        async_session.add(org)
        await async_session.flush()
        
        portal_type = PortalType(
            code="TEST_PORTAL",
            name="Test Portal",
            kind="payer",
            base_url="https://test.com"
        )
        async_session.add(portal_type)
        await async_session.flush()
        
        portal = IntegrationEndpoint(
            org_id=org.org_id,
            portal_type_id=portal_type.portal_type_id,
            name="Test Endpoint"
        )
        async_session.add(portal)
        await async_session.flush()
        
        task_type = TaskType(
            domain="eligibility",
            action="status_check",
            display_name="Test Task"
        )
        async_session.add(task_type)
        await async_session.flush()
        
        # Create batch job
        batch_job = BatchJob(
            org_id=org.org_id,
            portal_id=portal.portal_id,
            task_type_id=task_type.task_type_id,
            status="queued"
        )
        async_session.add(batch_job)
        await async_session.commit()
        
        # Verify relationships
        result = await async_session.execute(
            select(BatchJob)
            .where(BatchJob.batch_id == batch_job.batch_id)
            .options(
                selectinload(BatchJob.task_type),
                selectinload(BatchJob.portal)
            )
        )
        loaded_job = result.scalar_one()
        assert loaded_job.task_type.domain == "eligibility"
        assert loaded_job.task_type.action == "status_check"
        assert loaded_job.portal.name == "Test Endpoint"


@pytest.mark.integration
@pytest.mark.asyncio 
class TestVectorOperations:
    """Test pgvector operations."""
    
    async def test_create_rcm_state_with_vectors(self, async_session):
        """Test creating RCM state with vector embeddings."""
        import numpy as np
        
        # Setup portal
        org = Organization(org_type="hospital", name="Vector Test Org")
        async_session.add(org)
        await async_session.flush()
        
        portal_type = PortalType(
            code="VECTOR_TEST",
            name="Vector Test Portal",
            kind="payer"
        )
        async_session.add(portal_type)
        await async_session.flush()
        
        portal = IntegrationEndpoint(
            org_id=org.org_id,
            portal_type_id=portal_type.portal_type_id,
            name="Vector Test Endpoint"
        )
        async_session.add(portal)
        await async_session.flush()
        
        # Create state with vectors
        text_emb = np.random.rand(768).tolist()
        image_emb = np.random.rand(512).tolist()
        
        state = RcmState(
            portal_id=portal.portal_id,
            text_emb=text_emb,
            image_emb=image_emb,
            semantic_spec={"page": "login"},
            action={"type": "click", "selector": "#submit"},
            page_caption="Login page"
        )
        async_session.add(state)
        await async_session.commit()
        
        # Verify vectors stored correctly
        result = await async_session.execute(
            select(RcmState).where(RcmState.state_id == state.state_id)
        )
        loaded_state = result.scalar_one()
        assert len(loaded_state.text_emb) == 768
        assert len(loaded_state.image_emb) == 512


@pytest.mark.integration
@pytest.mark.asyncio
class TestRowLevelSecurity:
    """Test row level security helpers."""
    
    async def test_set_org_context(self, async_session):
        """Test setting organization context."""
        from database import set_org_context
        
        org_id = str(uuid4())
        await set_org_context(async_session, org_id)
        
        # Verify context is set
        result = await async_session.execute(
            text("SELECT current_setting('app.current_org_id', true)")
        )
        assert result.scalar() == org_id
