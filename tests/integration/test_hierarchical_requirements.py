"""Integration tests for hierarchical requirements system."""

import pytest
from datetime import date
from uuid import uuid4

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from models import (
    Organization, PortalType, IntegrationEndpoint, TaskType,
    PayerRequirement, OrgRequirementPolicy, RequirementChangelog,
    AppUser
)
from requirement_resolver import RequirementResolver, PolicyType


@pytest.mark.asyncio
class TestHierarchicalRequirements:
    """Integration tests for the new requirements system."""
    
    async def test_payer_requirement_creation(self, async_session: AsyncSession):
        """Test creating payer requirements."""
        # Create test data
        portal_type = PortalType(
            code="test_payer",
            name="Test Payer",
            base_url="https://testpayer.com",
            endpoint_kind="payer"
        )
        async_session.add(portal_type)
        await async_session.flush()
        
        task_type = TaskType(
            domain="eligibility",
            action="status_check",
            display_name="Eligibility Check"
        )
        async_session.add(task_type)
        await async_session.flush()
        
        # Create payer requirement
        payer_req = PayerRequirement(
            portal_type_id=portal_type.portal_type_id,
            task_type_id=task_type.task_type_id,
            required_fields=["member_id", "dob", "ssn"],
            optional_fields=["phone", "email"],
            field_rules={
                "member_id": {"pattern": r"^[A-Z]\d{8}$"},
                "ssn": {"pattern": r"^\d{3}-\d{2}-\d{4}$"}
            },
            compliance_ref="HIPAA 837P",
            effective_date=date.today(),
            version=1
        )
        async_session.add(payer_req)
        await async_session.commit()
        
        # Verify
        result = await async_session.execute(
            select(PayerRequirement).where(
                PayerRequirement.portal_type_id == portal_type.portal_type_id
            )
        )
        saved_req = result.scalar_one()
        
        assert saved_req.required_fields == ["member_id", "dob", "ssn"]
        assert saved_req.compliance_ref == "HIPAA 837P"
        assert "pattern" in saved_req.field_rules["member_id"]
    
    async def test_org_policy_override(self, async_session: AsyncSession):
        """Test organization policy overriding payer requirements."""
        # Create base data
        org = Organization(
            name="Test Hospital",
            org_type="hospital"
        )
        async_session.add(org)
        
        portal_type = PortalType(
            code="uhc",
            name="UnitedHealthcare",
            base_url="https://uhc.com",
            endpoint_kind="payer"
        )
        async_session.add(portal_type)
        
        task_type = TaskType(
            domain="prior_auth",
            action="submit",
            display_name="Prior Auth Submit"
        )
        async_session.add(task_type)
        await async_session.flush()
        
        # Create payer requirement
        payer_req = PayerRequirement(
            portal_type_id=portal_type.portal_type_id,
            task_type_id=task_type.task_type_id,
            required_fields=["member_id", "diagnosis_code", "procedure_code"],
            optional_fields=["notes"],
            field_rules={},
            compliance_ref="UHC PA Guidelines",
            effective_date=date.today()
        )
        async_session.add(payer_req)
        
        # Create org policy to add internal tracking
        org_policy = OrgRequirementPolicy(
            org_id=org.org_id,
            task_type_id=task_type.task_type_id,
            portal_type_id=portal_type.portal_type_id,
            policy_type=PolicyType.ADD,
            field_changes={
                "required_fields": ["internal_case_id", "department_code"]
            },
            reason="Hospital requires internal tracking fields",
            active=True
        )
        async_session.add(org_policy)
        
        # Create integration endpoint
        endpoint = IntegrationEndpoint(
            org_id=org.org_id,
            name="UHC Portal",
            portal_type_id=portal_type.portal_type_id,
            config={}
        )
        async_session.add(endpoint)
        await async_session.commit()
        
        # Test resolver
        resolver = RequirementResolver(async_session)
        requirements = await resolver._compute_requirements(
            endpoint.portal_id,
            task_type.task_type_id
        )
        
        # Verify merged requirements
        assert "member_id" in requirements.required_fields  # From payer
        assert "internal_case_id" in requirements.required_fields  # From org policy
        assert "department_code" in requirements.required_fields  # From org policy
        assert len(requirements.required_fields) == 5  # 3 payer + 2 org
    
    async def test_materialized_view_refresh(self, async_session: AsyncSession):
        """Test materialized view updates after requirement changes."""
        # Create test data
        org = Organization(name="Test Org", org_type="hospital")
        portal_type = PortalType(
            code="anthem",
            name="Anthem",
            base_url="https://anthem.com",
            endpoint_kind="payer"
        )
        task_type = TaskType(
            domain="eligibility",
            action="status_check",
            display_name="Eligibility Check"
        )
        
        async_session.add_all([org, portal_type, task_type])
        await async_session.flush()
        
        endpoint = IntegrationEndpoint(
            org_id=org.org_id,
            name="Anthem Portal",
            portal_type_id=portal_type.portal_type_id,
            config={}
        )
        async_session.add(endpoint)
        
        payer_req = PayerRequirement(
            portal_type_id=portal_type.portal_type_id,
            task_type_id=task_type.task_type_id,
            required_fields=["member_id", "dob"],
            optional_fields=[],
            field_rules={},
            effective_date=date.today()
        )
        async_session.add(payer_req)
        await async_session.commit()
        
        # Refresh materialized view
        await async_session.execute(
            text("REFRESH MATERIALIZED VIEW effective_requirements")
        )
        await async_session.commit()
        
        # Query materialized view
        result = await async_session.execute(
            text("""
                SELECT * FROM effective_requirements 
                WHERE portal_id = :portal_id 
                AND task_type_id = :task_type_id
            """),
            {
                "portal_id": endpoint.portal_id,
                "task_type_id": str(task_type.task_type_id)
            }
        )
        row = result.one()
        
        assert row.required_fields == ["member_id", "dob"]
        assert row.portal_type_id == portal_type.portal_type_id
    
    async def test_requirement_changelog(self, async_session: AsyncSession):
        """Test requirement change logging."""
        # Create user for audit
        user = AppUser(
            username="test_user",
            email="test@example.com"
        )
        async_session.add(user)
        
        portal_type = PortalType(
            code="bcbs",
            name="Blue Cross Blue Shield",
            base_url="https://bcbs.com",
            endpoint_kind="payer"
        )
        task_type = TaskType(
            domain="claim",
            action="submit",
            display_name="Claim Submit"
        )
        
        async_session.add_all([portal_type, task_type])
        await async_session.flush()
        
        # Set current user for audit
        await async_session.execute(
            text("SET LOCAL app.current_user_id = :user_id"),
            {"user_id": str(user.user_id)}
        )
        
        # Create payer requirement (should trigger changelog)
        payer_req = PayerRequirement(
            portal_type_id=portal_type.portal_type_id,
            task_type_id=task_type.task_type_id,
            required_fields=["claim_number", "service_date"],
            optional_fields=["notes"],
            field_rules={},
            effective_date=date.today(),
            created_by=user.user_id
        )
        async_session.add(payer_req)
        await async_session.commit()
        
        # Check changelog
        result = await async_session.execute(
            select(RequirementChangelog).where(
                RequirementChangelog.source_table == "payer_requirement"
            )
        )
        log_entry = result.scalar_one()
        
        assert log_entry.change_type == "INSERT"
        assert log_entry.new_value["required_fields"] == ["claim_number", "service_date"]
        assert log_entry.changed_by == user.user_id
    
    async def test_complex_hierarchy_resolution(self, async_session: AsyncSession):
        """Test complex requirement resolution with multiple policies."""
        # Create comprehensive test scenario
        org = Organization(name="Complex Hospital", org_type="hospital")
        portal_type = PortalType(
            code="aetna",
            name="Aetna",
            base_url="https://aetna.com",
            endpoint_kind="payer"
        )
        task_type = TaskType(
            domain="prior_auth",
            action="submit",
            display_name="PA Submit"
        )
        
        async_session.add_all([org, portal_type, task_type])
        await async_session.flush()
        
        # Payer requirement (base)
        payer_req = PayerRequirement(
            portal_type_id=portal_type.portal_type_id,
            task_type_id=task_type.task_type_id,
            required_fields=["member_id", "diagnosis", "procedure"],
            optional_fields=["physician_notes"],
            field_rules={
                "member_id": {"pattern": r"^W\d{9}$"}
            },
            effective_date=date.today()
        )
        async_session.add(payer_req)
        
        # Org policy 1: Add fields
        policy1 = OrgRequirementPolicy(
            org_id=org.org_id,
            task_type_id=task_type.task_type_id,
            portal_type_id=portal_type.portal_type_id,
            policy_type=PolicyType.ADD,
            field_changes={
                "required_fields": ["auth_number", "department"],
                "field_rules": {
                    "auth_number": {"pattern": r"^AUTH-\d{6}$"}
                }
            },
            reason="Internal tracking",
            active=True,
            version=1
        )
        async_session.add(policy1)
        
        # Org policy 2: Remove optional field
        policy2 = OrgRequirementPolicy(
            org_id=org.org_id,
            task_type_id=task_type.task_type_id,
            portal_type_id=portal_type.portal_type_id,
            policy_type=PolicyType.REMOVE,
            field_changes={
                "optional_fields": ["physician_notes"]
            },
            reason="Not needed for this portal",
            active=True,
            version=2
        )
        async_session.add(policy2)
        
        endpoint = IntegrationEndpoint(
            org_id=org.org_id,
            name="Aetna Portal",
            portal_type_id=portal_type.portal_type_id,
            config={}
        )
        async_session.add(endpoint)
        await async_session.commit()
        
        # Test resolution
        resolver = RequirementResolver(async_session)
        requirements = await resolver._compute_requirements(
            endpoint.portal_id,
            task_type.task_type_id
        )
        
        # Verify complex merge
        assert set(requirements.required_fields) == {
            "member_id", "diagnosis", "procedure",  # From payer
            "auth_number", "department"  # From policy1
        }
        assert "physician_notes" not in requirements.optional_fields  # Removed by policy2
        assert requirements.field_rules["member_id"]["pattern"] == r"^W\d{9}$"  # From payer
        assert requirements.field_rules["auth_number"]["pattern"] == r"^AUTH-\d{6}$"  # From policy1
    
    async def test_validation_with_resolver(self, async_session: AsyncSession):
        """Test field validation through resolver."""
        # Setup test data
        org = Organization(name="Validation Test Org", org_type="hospital")
        portal_type = PortalType(
            code="cigna",
            name="Cigna",
            base_url="https://cigna.com",
            endpoint_kind="payer"
        )
        task_type = TaskType(
            domain="eligibility",
            action="status_check",
            display_name="Eligibility Check"
        )
        
        async_session.add_all([org, portal_type, task_type])
        await async_session.flush()
        
        payer_req = PayerRequirement(
            portal_type_id=portal_type.portal_type_id,
            task_type_id=task_type.task_type_id,
            required_fields=["member_id", "dob"],
            optional_fields=["group_number"],
            field_rules={
                "member_id": {
                    "pattern": r"^[A-Z]{3}\d{7}$",
                    "min_length": 10
                },
                "dob": {
                    "pattern": r"^\d{4}-\d{2}-\d{2}$"
                }
            },
            effective_date=date.today()
        )
        async_session.add(payer_req)
        
        endpoint = IntegrationEndpoint(
            org_id=org.org_id,
            name="Cigna Portal",
            portal_type_id=portal_type.portal_type_id,
            config={}
        )
        async_session.add(endpoint)
        await async_session.commit()
        
        # Refresh materialized view
        await async_session.execute(
            text("REFRESH MATERIALIZED VIEW effective_requirements")
        )
        await async_session.commit()
        
        # Test validation
        resolver = RequirementResolver(async_session)
        
        # Valid submission
        valid_result = await resolver.validate_fields(
            endpoint.portal_id,
            task_type.task_type_id,
            {
                "member_id": "ABC1234567",
                "dob": "1990-01-15",
                "group_number": "GRP123"
            }
        )
        assert valid_result.is_valid
        
        # Invalid submission
        invalid_result = await resolver.validate_fields(
            endpoint.portal_id,
            task_type.task_type_id,
            {
                "member_id": "123",  # Wrong format
                "dob": "01/15/1990"  # Wrong date format
            }
        )
        assert not invalid_result.is_valid
        assert len(invalid_result.validation_errors) >= 2