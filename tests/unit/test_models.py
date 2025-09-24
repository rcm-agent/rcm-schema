"""Unit tests for SQLAlchemy models."""
import pytest
from uuid import uuid4
from datetime import datetime
from decimal import Decimal

from models import (
    Organization, PortalType, IntegrationEndpoint,
    TaskType, FieldRequirement, BatchJob, BatchRow,
    RcmState, MacroState, TaskSignature, RcmTrace,
    RcmTransition, AppUser
)


class TestOrganizationModel:
    """Test Organization model."""
    
    def test_organization_creation(self):
        """Test creating an organization instance."""
        org = Organization(
            org_type="hospital",
            name="Test Hospital",
            email_domain="test.com"
        )
        assert org.org_type == "hospital"
        assert org.name == "Test Hospital"
        assert org.email_domain == "test.com"
        assert org.org_id is not None  # Should auto-generate UUID
    
    def test_organization_relationships(self):
        """Test organization relationships are defined."""
        org = Organization()
        assert hasattr(org, 'endpoints')
        assert hasattr(org, 'batch_jobs')
        assert hasattr(org, 'users')
        assert hasattr(org, 'traces')


class TestPortalTypeModel:
    """Test PortalType model."""
    
    def test_portal_type_creation(self):
        """Test creating a portal type instance."""
        portal_type = PortalType(
            code="BCBS_MI",
            name="Blue Cross Blue Shield Michigan",
            kind="payer",
            base_url="https://www.bcbsm.com"
        )
        assert portal_type.code == "BCBS_MI"
        assert portal_type.kind == "payer"
        assert portal_type.base_url == "https://www.bcbsm.com"
    
    def test_portal_type_relationships(self):
        """Test portal type relationships."""
        portal_type = PortalType()
        assert hasattr(portal_type, 'endpoints')
        assert hasattr(portal_type, 'task_signatures')


class TestTaskTypeModel:
    """Test TaskType model."""
    
    def test_task_type_creation(self):
        """Test creating a task type instance."""
        task_type = TaskType(
            domain="eligibility",
            action="status_check",
            display_name="Eligibility Check",
            description="Check patient eligibility"
        )
        assert task_type.domain == "eligibility"
        assert task_type.action == "status_check"
        assert task_type.display_name == "Eligibility Check"
    
    def test_task_type_relationships(self):
        """Test task type relationships."""
        task_type = TaskType()
        assert hasattr(task_type, 'field_requirements')


class TestBatchJobModel:
    """Test BatchJob model."""
    
    def test_batch_job_creation(self):
        """Test creating a batch job instance."""
        org_id = uuid4()
        task_type_id = uuid4()
        batch_job = BatchJob(
            org_id=org_id,
            portal_id=1,
            task_type_id=task_type_id,
            status="queued"
        )
        assert batch_job.org_id == org_id
        assert batch_job.portal_id == 1
        assert batch_job.task_type_id == task_type_id
        assert batch_job.status == "queued"
    
    def test_batch_job_relationships(self):
        """Test batch job relationships."""
        batch_job = BatchJob()
        assert hasattr(batch_job, 'organization')
        assert hasattr(batch_job, 'portal')
        assert hasattr(batch_job, 'rows')
        assert hasattr(batch_job, 'task_type')


class TestRcmStateModel:
    """Test RcmState model."""
    
    def test_rcm_state_creation(self):
        """Test creating an RCM state instance."""
        import numpy as np
        
        state = RcmState(
            portal_id=1,
            text_emb=np.random.rand(768).tolist(),
            image_emb=np.random.rand(512).tolist(),
            semantic_spec={"page": "login"},
            action={"type": "click", "selector": "#submit"},
            success_ema=0.95,
            page_caption="Login page",
            action_caption="Click submit button"
        )
        assert state.portal_id == 1
        assert len(state.text_emb) == 768
        assert len(state.image_emb) == 512
        assert state.success_ema == 0.95
    
    def test_rcm_state_defaults(self):
        """Test RCM state default values."""
        state = RcmState(
            portal_id=1,
            text_emb=[0.0] * 768,
            image_emb=[0.0] * 512,
            semantic_spec={},
            action={}
        )
        assert state.success_ema == 1.0  # Default value
        assert state.is_retired is False  # Default value


class TestTaskSignatureModel:
    """Test TaskSignature model."""
    
    def test_task_signature_creation(self):
        """Test creating a task signature instance."""
        signature = TaskSignature(
            domain="eligibility",
            action="status_check",
            source="human",
            display_name="Check Eligibility",
            description="Manual eligibility check process"
        )
        assert signature.domain == "eligibility"
        assert signature.action == "status_check"
        assert signature.source == "human"
    
    def test_task_signature_vectors(self):
        """Test task signature with vector embeddings."""
        signature = TaskSignature(
            domain="claim",
            action="submit",
            source="ai",
            text_emb=[0.1] * 768,
            image_emb=[0.2] * 512
        )
        assert len(signature.text_emb) == 768
        assert len(signature.image_emb) == 512
        assert signature.source == "ai"


class TestRcmTraceModel:
    """Test RcmTrace model."""
    
    def test_rcm_trace_creation(self):
        """Test creating an RCM trace instance."""
        org_id = uuid4()
        trace = RcmTrace(
            org_id=org_id,
            portal_id=1,
            trace={"steps": ["login", "search", "submit"]},
            duration_ms=1500,
            success=True
        )
        assert trace.org_id == org_id
        assert trace.portal_id == 1
        assert trace.duration_ms == 1500
        assert trace.success is True
    
    def test_rcm_trace_optional_fields(self):
        """Test RCM trace optional fields."""
        trace = RcmTrace(
            org_id=uuid4(),
            portal_id=1,
            trace={},
            prompt_version="v1.2.3",
            used_fallback=True,
            fallback_model="gpt-4"
        )
        assert trace.prompt_version == "v1.2.3"
        assert trace.used_fallback is True
        assert trace.fallback_model == "gpt-4"


class TestAppUserModel:
    """Test AppUser model."""
    
    def test_app_user_creation(self):
        """Test creating an app user instance."""
        user_id = uuid4()
        org_id = uuid4()
        user = AppUser(
            user_id=user_id,
            org_id=org_id,
            email="test@example.com",
            full_name="Test User",
            role="org_admin"
        )
        assert user.user_id == user_id
        assert user.org_id == org_id
        assert user.email == "test@example.com"
        assert user.role == "org_admin"
    
    def test_app_user_timestamps(self):
        """Test app user has timestamp fields."""
        user = AppUser()
        assert hasattr(user, 'created_at')
        assert hasattr(user, 'updated_at')


class TestModelConstraints:
    """Test model constraints and validations."""
    
    def test_field_requirement_version_default(self):
        """Test field requirement version default."""
        field_req = FieldRequirement(
            task_type_id=uuid4(),
            required_fields=[],
            optional_fields=[]
        )
        assert field_req.version == 1  # Default value
    
    def test_rcm_transition_freq_default(self):
        """Test RCM transition frequency default."""
        transition = RcmTransition(
            from_state=uuid4(),
            to_state=uuid4(),
            action_caption="Click next"
        )
        assert transition.freq == 1  # Default value
    
    def test_macro_state_relationships(self):
        """Test macro state relationships."""
        macro_state = MacroState()
        assert hasattr(macro_state, 'states')
        assert hasattr(macro_state, 'sample_state')