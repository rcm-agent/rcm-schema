"""Unit tests for RequirementResolver service."""

import pytest
from datetime import date
from uuid import uuid4
from unittest.mock import AsyncMock, MagicMock, patch

from requirement_resolver import (
    RequirementResolver, RequirementSet, ValidationResult, PolicyType
)
from models import (
    PayerRequirement, OrgRequirementPolicy, IntegrationEndpoint
)


class TestRequirementSet:
    """Test RequirementSet data class and validation."""
    
    def test_validate_fields_all_valid(self):
        """Test validation with all required fields present."""
        req_set = RequirementSet(
            portal_id=1,
            task_type_id=uuid4(),
            org_id=uuid4(),
            portal_type_id=1,
            required_fields=["member_id", "dob", "ssn"],
            optional_fields=["phone", "email"],
            field_rules={}
        )
        
        submitted = {
            "member_id": "12345",
            "dob": "1990-01-01",
            "ssn": "123-45-6789",
            "phone": "555-1234"
        }
        
        result = req_set.validate_fields(submitted)
        assert result.is_valid
        assert not result.missing_required
        assert not result.extra_fields
        assert not result.validation_errors
    
    def test_validate_fields_missing_required(self):
        """Test validation with missing required fields."""
        req_set = RequirementSet(
            portal_id=1,
            task_type_id=uuid4(),
            org_id=uuid4(),
            portal_type_id=1,
            required_fields=["member_id", "dob", "ssn"],
            optional_fields=[],
            field_rules={}
        )
        
        submitted = {
            "member_id": "12345",
            "dob": "1990-01-01"
            # Missing ssn
        }
        
        result = req_set.validate_fields(submitted)
        assert not result.is_valid
        assert result.missing_required == ["ssn"]
        assert not result.validation_errors
    
    def test_validate_fields_extra_fields(self):
        """Test validation with extra fields not in schema."""
        req_set = RequirementSet(
            portal_id=1,
            task_type_id=uuid4(),
            org_id=uuid4(),
            portal_type_id=1,
            required_fields=["member_id"],
            optional_fields=["phone"],
            field_rules={}
        )
        
        submitted = {
            "member_id": "12345",
            "phone": "555-1234",
            "extra_field": "not allowed"
        }
        
        result = req_set.validate_fields(submitted)
        assert result.is_valid  # Extra fields don't invalidate
        assert result.extra_fields == ["extra_field"]
    
    def test_validate_field_rules_pattern(self):
        """Test field validation with regex pattern."""
        req_set = RequirementSet(
            portal_id=1,
            task_type_id=uuid4(),
            org_id=uuid4(),
            portal_type_id=1,
            required_fields=["member_id"],
            optional_fields=[],
            field_rules={
                "member_id": {
                    "pattern": r"^[A-Z]{2}\d{6}$"
                }
            }
        )
        
        # Valid pattern
        result = req_set.validate_fields({"member_id": "AB123456"})
        assert result.is_valid
        
        # Invalid pattern
        result = req_set.validate_fields({"member_id": "12345"})
        assert not result.is_valid
        assert "Does not match required pattern" in result.validation_errors[0]
    
    def test_validate_field_rules_length(self):
        """Test field validation with length constraints."""
        req_set = RequirementSet(
            portal_id=1,
            task_type_id=uuid4(),
            org_id=uuid4(),
            portal_type_id=1,
            required_fields=["code"],
            optional_fields=[],
            field_rules={
                "code": {
                    "min_length": 3,
                    "max_length": 10
                }
            }
        )
        
        # Too short
        result = req_set.validate_fields({"code": "AB"})
        assert not result.is_valid
        assert "Must be at least 3 characters" in result.validation_errors[0]
        
        # Too long
        result = req_set.validate_fields({"code": "ABCDEFGHIJK"})
        assert not result.is_valid
        assert "Must be at most 10 characters" in result.validation_errors[0]
        
        # Just right
        result = req_set.validate_fields({"code": "ABC123"})
        assert result.is_valid
    
    def test_validate_field_rules_enum(self):
        """Test field validation with enum constraint."""
        req_set = RequirementSet(
            portal_id=1,
            task_type_id=uuid4(),
            org_id=uuid4(),
            portal_type_id=1,
            required_fields=["status"],
            optional_fields=[],
            field_rules={
                "status": {
                    "enum": ["active", "pending", "inactive"]
                }
            }
        )
        
        # Valid enum value
        result = req_set.validate_fields({"status": "active"})
        assert result.is_valid
        
        # Invalid enum value
        result = req_set.validate_fields({"status": "expired"})
        assert not result.is_valid
        assert "Must be one of" in result.validation_errors[0]


class TestRequirementResolver:
    """Test RequirementResolver service."""
    
    @pytest.fixture
    def mock_session(self):
        """Create mock async session."""
        session = AsyncMock()
        return session
    
    @pytest.fixture
    def resolver(self, mock_session):
        """Create resolver instance."""
        return RequirementResolver(mock_session)
    
    @pytest.mark.asyncio
    async def test_get_from_materialized_view(self, resolver, mock_session):
        """Test getting requirements from materialized view."""
        portal_id = 1
        task_type_id = uuid4()
        org_id = uuid4()
        
        # Mock query result
        mock_row = MagicMock()
        mock_row.portal_id = portal_id
        mock_row.task_type_id = str(task_type_id)
        mock_row.org_id = str(org_id)
        mock_row.portal_type_id = 2
        mock_row.required_fields = ["member_id", "dob"]
        mock_row.optional_fields = ["phone"]
        mock_row.field_rules = {"member_id": {"pattern": r"^\d+$"}}
        mock_row.compliance_ref = "HIPAA"
        
        mock_result = MagicMock()
        mock_result.one_or_none.return_value = mock_row
        mock_session.execute.return_value = mock_result
        
        # Call method
        result = await resolver._get_from_materialized_view(portal_id, task_type_id)
        
        # Verify
        assert isinstance(result, RequirementSet)
        assert result.portal_id == portal_id
        assert result.task_type_id == task_type_id
        assert result.required_fields == ["member_id", "dob"]
        assert result.source == "effective_requirements"
    
    @pytest.mark.asyncio
    async def test_apply_policy_add(self, resolver):
        """Test applying ADD policy type."""
        required_fields = ["field1", "field2"]
        optional_fields = ["opt1"]
        field_rules = {"field1": {"required": True}}
        
        policy = MagicMock()
        policy.policy_type = PolicyType.ADD
        policy.field_changes = {
            "required_fields": ["field3"],
            "optional_fields": ["opt2"],
            "field_rules": {"field3": {"pattern": r"^\d+$"}}
        }
        
        new_req, new_opt, new_rules = resolver._apply_policy(
            required_fields, optional_fields, field_rules, policy
        )
        
        assert "field3" in new_req
        assert "opt2" in new_opt
        assert "field3" in new_rules
        assert new_rules["field3"]["pattern"] == r"^\d+$"
    
    @pytest.mark.asyncio
    async def test_apply_policy_remove(self, resolver):
        """Test applying REMOVE policy type."""
        required_fields = ["field1", "field2", "field3"]
        optional_fields = ["opt1", "opt2"]
        field_rules = {"field1": {"required": True}, "field2": {"pattern": ".*"}}
        
        policy = MagicMock()
        policy.policy_type = PolicyType.REMOVE
        policy.field_changes = {
            "required_fields": ["field2"],
            "optional_fields": ["opt1"],
            "field_rules": ["field2"]
        }
        
        new_req, new_opt, new_rules = resolver._apply_policy(
            required_fields, optional_fields, field_rules, policy
        )
        
        assert "field2" not in new_req
        assert "opt1" not in new_opt
        assert "field2" not in new_rules
        assert "field1" in new_req  # Others remain
    
    @pytest.mark.asyncio
    async def test_apply_policy_override(self, resolver):
        """Test applying OVERRIDE policy type."""
        required_fields = ["field1", "field2"]
        optional_fields = ["opt1"]
        field_rules = {"field1": {"required": True}}
        
        policy = MagicMock()
        policy.policy_type = PolicyType.OVERRIDE
        policy.field_changes = {
            "required_fields": ["new_field1", "new_field2"],
            "optional_fields": ["new_opt1"],
            "field_rules": {"new_field1": {"min_length": 5}}
        }
        
        new_req, new_opt, new_rules = resolver._apply_policy(
            required_fields, optional_fields, field_rules, policy
        )
        
        assert new_req == ["new_field1", "new_field2"]
        assert new_opt == ["new_opt1"]
        assert new_rules == {"new_field1": {"min_length": 5}}
    
    @pytest.mark.asyncio
    async def test_compute_requirements_no_payer_req(self, resolver, mock_session):
        """Test computing requirements when no payer requirement exists."""
        portal_id = 1
        task_type_id = uuid4()
        org_id = uuid4()
        
        # Mock portal
        mock_portal = MagicMock()
        mock_portal.portal_id = portal_id
        mock_portal.org_id = org_id
        mock_portal.portal_type_id = 2
        
        # Mock queries
        portal_result = MagicMock()
        portal_result.scalar_one.return_value = mock_portal
        
        payer_result = MagicMock()
        payer_result.scalar_one_or_none.return_value = None  # No payer req
        
        policy_result = MagicMock()
        policy_result.scalars.return_value.all.return_value = []  # No policies
        
        mock_session.execute.side_effect = [portal_result, payer_result, policy_result]
        
        # Call method
        result = await resolver._compute_requirements(portal_id, task_type_id)
        
        # Verify empty requirements
        assert result.required_fields == []
        assert result.optional_fields == []
        assert result.field_rules == {}
        assert result.source == "computed"
    
    @pytest.mark.asyncio
    async def test_validate_fields(self, resolver, mock_session):
        """Test validate_fields method."""
        portal_id = 1
        task_type_id = uuid4()
        
        # Mock get_requirements to return a RequirementSet
        mock_req_set = RequirementSet(
            portal_id=portal_id,
            task_type_id=task_type_id,
            org_id=uuid4(),
            portal_type_id=1,
            required_fields=["field1"],
            optional_fields=[],
            field_rules={}
        )
        
        with patch.object(resolver, 'get_requirements', return_value=mock_req_set):
            result = await resolver.validate_fields(
                portal_id, 
                task_type_id,
                {"field1": "value1"}
            )
            
            assert isinstance(result, ValidationResult)
            assert result.is_valid