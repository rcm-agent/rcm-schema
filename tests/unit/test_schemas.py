"""Unit tests for Pydantic schemas."""
import pytest
from uuid import uuid4
from datetime import datetime
from pydantic import ValidationError

from schemas import (
    # Organization schemas
    OrganizationCreate, OrganizationUpdate, Organization,
    # Portal Type schemas
    PortalTypeCreate, PortalTypeUpdate, PortalType,
    # Task Type schemas
    TaskTypeCreate, TaskTypeUpdate, TaskType,
    # Field Requirement schemas
    FieldRequirementCreate, FieldRequirementUpdate, FieldRequirement,
    # Batch Job schemas
    BatchJobCreate, BatchJobUpdate, BatchJob,
    # Task Signature schemas
    TaskSignatureCreate, TaskSignatureUpdate, TaskSignature,
    # RCM Trace schemas
    RcmTraceCreate, RcmTraceUpdate, RcmTrace,
    # Enums
    OrgType, EndpointKind, TaskDomain, TaskAction,
    TaskSignatureSource, JobStatus,
    # Utility
    Vector
)


class TestOrganizationSchemas:
    """Test Organization Pydantic schemas."""
    
    def test_organization_create_valid(self):
        """Test creating valid organization."""
        org = OrganizationCreate(
            org_type=OrgType.HOSPITAL,
            name="Test Hospital",
            email_domain="test.com"
        )
        assert org.org_type == OrgType.HOSPITAL
        assert org.name == "Test Hospital"
        assert org.email_domain == "test.com"
    
    def test_organization_create_missing_required(self):
        """Test organization creation fails without required fields."""
        with pytest.raises(ValidationError) as exc_info:
            OrganizationCreate(name="Test")  # Missing org_type
        
        errors = exc_info.value.errors()
        assert any(e['loc'] == ('org_type',) for e in errors)
    
    def test_organization_update_partial(self):
        """Test organization update with partial data."""
        update = OrganizationUpdate(name="New Name")
        assert update.name == "New Name"
        assert update.email_domain is None  # Optional field
    
    def test_organization_from_orm(self):
        """Test Organization schema can be created from ORM model."""
        org = Organization(
            org_id=uuid4(),
            org_type=OrgType.BILLING_FIRM,
            name="Test Firm",
            email_domain="firm.com",
            created_at=datetime.now()
        )
        assert org.org_id is not None
        assert org.created_at is not None


class TestTaskTypeSchemas:
    """Test TaskType Pydantic schemas."""
    
    def test_task_type_create_valid(self):
        """Test creating valid task type."""
        task = TaskTypeCreate(
            domain=TaskDomain.ELIGIBILITY,
            action=TaskAction.STATUS_CHECK,
            display_name="Eligibility Check",
            description="Check patient eligibility"
        )
        assert task.domain == TaskDomain.ELIGIBILITY
        assert task.action == TaskAction.STATUS_CHECK
    
    def test_task_type_create_invalid_combination(self):
        """Test task type with invalid domain/action combination."""
        # This should still create (validation happens at DB level)
        task = TaskTypeCreate(
            domain=TaskDomain.CLAIM,
            action=TaskAction.STATUS_CHECK,
            display_name="Claim Status"
        )
        assert task.domain == TaskDomain.CLAIM
        assert task.action == TaskAction.STATUS_CHECK


class TestBatchJobSchemas:
    """Test BatchJob Pydantic schemas."""
    
    def test_batch_job_create_valid(self):
        """Test creating valid batch job."""
        job = BatchJobCreate(
            portal_id=1,
            task_type_id=uuid4(),
            org_id=uuid4()
        )
        assert job.portal_id == 1
        assert job.task_type_id is not None
        assert job.status == JobStatus.QUEUED  # Default
    
    def test_batch_job_create_without_org_id(self):
        """Test batch job creation without org_id (set from context)."""
        job = BatchJobCreate(
            portal_id=1,
            task_type_id=uuid4()
        )
        assert job.org_id is None  # Will be set from auth context
    
    def test_batch_job_update_status(self):
        """Test updating batch job status."""
        update = BatchJobUpdate(
            status=JobStatus.SUCCESS,
            completed_at=datetime.now()
        )
        assert update.status == JobStatus.SUCCESS
        assert update.completed_at is not None


class TestVectorSchema:
    """Test Vector validation schema."""
    
    def test_vector_valid_dimensions(self):
        """Test vector with valid dimensions."""
        # 768D text embedding
        text_vec = Vector(root=[0.1] * 768)
        assert len(text_vec.root) == 768
        
        # 512D image embedding  
        img_vec = Vector(root=[0.2] * 512)
        assert len(img_vec.root) == 512
    
    def test_vector_invalid_dimensions(self):
        """Test vector with invalid dimensions."""
        with pytest.raises(ValidationError) as exc_info:
            Vector(root=[0.1] * 100)  # Wrong dimension
        
        error = exc_info.value.errors()[0]
        assert "must be either 512 or 768" in error['msg']
    
    def test_vector_empty(self):
        """Test empty vector is invalid."""
        with pytest.raises(ValidationError):
            Vector(root=[])


class TestTaskSignatureSchemas:
    """Test TaskSignature Pydantic schemas."""
    
    def test_task_signature_create_human_source(self):
        """Test creating human-sourced task signature."""
        sig = TaskSignatureCreate(
            domain=TaskDomain.PRIOR_AUTH,
            action=TaskAction.SUBMIT,
            source=TaskSignatureSource.HUMAN,
            display_name="Submit Prior Auth"
        )
        assert sig.source == TaskSignatureSource.HUMAN
        assert sig.portal_id is None  # Optional
    
    def test_task_signature_create_ai_source(self):
        """Test creating AI-sourced task signature."""
        sig = TaskSignatureCreate(
            domain=TaskDomain.CLAIM,
            action=TaskAction.DENIAL_FOLLOW_UP,
            source=TaskSignatureSource.AI,
            portal_type_id=1
        )
        assert sig.source == TaskSignatureSource.AI
        assert sig.portal_type_id == 1
    
    def test_task_signature_with_embeddings(self):
        """Test task signature with vector embeddings."""
        sig = TaskSignatureCreate(
            domain=TaskDomain.ELIGIBILITY,
            action=TaskAction.STATUS_CHECK,
            source=TaskSignatureSource.AI,
            text_emb=[0.1] * 768,
            image_emb=[0.2] * 512
        )
        assert len(sig.text_emb) == 768
        assert len(sig.image_emb) == 512


class TestRcmTraceSchemas:
    """Test RcmTrace Pydantic schemas."""
    
    def test_rcm_trace_create_valid(self):
        """Test creating valid RCM trace."""
        trace = RcmTraceCreate(
            portal_id=1,
            trace={"steps": ["login", "search", "submit"]},
            org_id=uuid4()
        )
        assert trace.portal_id == 1
        assert len(trace.trace["steps"]) == 3
    
    def test_rcm_trace_create_with_metadata(self):
        """Test RCM trace with metadata."""
        trace = RcmTraceCreate(
            portal_id=1,
            trace={"steps": []},
            task_signature=uuid4(),
            prompt_version="v1.2.3",
            used_fallback=True,
            fallback_model="gpt-4"
        )
        assert trace.prompt_version == "v1.2.3"
        assert trace.used_fallback is True
        assert trace.fallback_model == "gpt-4"
    
    def test_rcm_trace_update_partial(self):
        """Test partial RCM trace update."""
        update = RcmTraceUpdate(
            duration_ms=1500,
            success=True
        )
        assert update.duration_ms == 1500
        assert update.success is True
        assert update.task_signature is None  # Not updated


class TestFieldRequirementSchemas:
    """Test FieldRequirement Pydantic schemas."""
    
    def test_field_requirement_create(self):
        """Test creating field requirement."""
        req = FieldRequirementCreate(
            task_type_id=uuid4(),
            required_fields=["patient_id", "dob"],
            optional_fields=["phone"],
            field_metadata={
                "patient_id": {"type": "string", "pattern": "^[A-Z0-9]+$"},
                "dob": {"type": "date", "format": "MM/DD/YYYY"}
            }
        )
        assert len(req.required_fields) == 2
        assert len(req.optional_fields) == 1
        assert "patient_id" in req.field_metadata
    
    def test_field_requirement_version_increment(self):
        """Test field requirement version in update."""
        update = FieldRequirementUpdate(
            required_fields=["patient_id", "dob", "insurance_id"],
            version=2
        )
        assert update.version == 2
        assert len(update.required_fields) == 3


class TestEnumValidation:
    """Test enum validation in schemas."""
    
    def test_valid_org_type(self):
        """Test valid organization types."""
        assert OrgType.HOSPITAL == "hospital"
        assert OrgType.BILLING_FIRM == "billing_firm"
        assert OrgType.CREDENTIALER == "credentialer"
    
    def test_valid_job_status(self):
        """Test valid job statuses."""
        assert JobStatus.QUEUED == "queued"
        assert JobStatus.PROCESSING == "processing"
        assert JobStatus.SUCCESS == "success"
        assert JobStatus.ERROR == "error"
    
    def test_task_signature_source(self):
        """Test task signature sources."""
        assert TaskSignatureSource.HUMAN == "human"
        assert TaskSignatureSource.AI == "ai"
    
    def test_invalid_enum_value(self):
        """Test invalid enum value raises error."""
        with pytest.raises(ValidationError):
            OrganizationCreate(
                org_type="invalid_type",  # Not a valid OrgType
                name="Test"
            )