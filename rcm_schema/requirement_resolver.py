"""Requirement resolver service for hierarchical field requirements.

This module provides the RequirementResolver class that resolves effective
requirements by merging payer-level requirements with organization-specific
policies.
"""

from typing import Dict, List, Any, Optional, Set
from datetime import date
from uuid import UUID
from dataclasses import dataclass
from enum import Enum

from sqlalchemy import select, and_, or_, func, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from models import (
    PayerRequirement, OrgRequirementPolicy, IntegrationEndpoint,
    TaskType, PortalType, Organization
)


class PolicyType(str, Enum):
    """Policy types for requirement modifications."""
    ADD = "add"
    REMOVE = "remove"
    OVERRIDE = "override"


@dataclass
class RequirementSet:
    """Container for resolved requirements."""
    portal_id: int
    task_type_id: UUID
    org_id: UUID
    portal_type_id: int
    required_fields: List[str]
    optional_fields: List[str]
    field_rules: Dict[str, Any]
    compliance_ref: Optional[str] = None
    source: str = "effective_requirements"  # or "computed"
    
    def validate_fields(self, submitted_fields: Dict[str, Any]) -> 'ValidationResult':
        """Validate submitted fields against requirements."""
        missing_required = []
        extra_fields = []
        validation_errors = []
        
        # Check required fields
        for field in self.required_fields:
            if field not in submitted_fields or submitted_fields[field] is None:
                missing_required.append(field)
        
        # Check for extra fields not in required or optional
        all_allowed_fields = set(self.required_fields) | set(self.optional_fields)
        for field in submitted_fields:
            if field not in all_allowed_fields:
                extra_fields.append(field)
        
        # Apply field rules validation
        for field, rules in self.field_rules.items():
            if field in submitted_fields:
                value = submitted_fields[field]
                errors = self._validate_field_rules(field, value, rules)
                validation_errors.extend(errors)
        
        return ValidationResult(
            is_valid=not (missing_required or validation_errors),
            missing_required=missing_required,
            extra_fields=extra_fields,
            validation_errors=validation_errors
        )
    
    def _validate_field_rules(self, field: str, value: Any, rules: Dict[str, Any]) -> List[str]:
        """Apply validation rules to a field value."""
        errors = []
        
        if "pattern" in rules and isinstance(value, str):
            import re
            if not re.match(rules["pattern"], value):
                errors.append(f"{field}: Does not match required pattern {rules['pattern']}")
        
        if "min_length" in rules and isinstance(value, str):
            if len(value) < rules["min_length"]:
                errors.append(f"{field}: Must be at least {rules['min_length']} characters")
        
        if "max_length" in rules and isinstance(value, str):
            if len(value) > rules["max_length"]:
                errors.append(f"{field}: Must be at most {rules['max_length']} characters")
        
        if "enum" in rules:
            if value not in rules["enum"]:
                errors.append(f"{field}: Must be one of {rules['enum']}")
        
        return errors


@dataclass
class ValidationResult:
    """Result of field validation."""
    is_valid: bool
    missing_required: List[str]
    extra_fields: List[str]
    validation_errors: List[str]


class RequirementResolver:
    """Resolves effective requirements for a given context."""
    
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def get_requirements(
        self, 
        portal_id: int, 
        task_type_id: UUID,
        as_of_date: Optional[date] = None
    ) -> RequirementSet:
        """
        Returns the effective requirements by:
        1. Checking materialized view first (fast path)
        2. If not found, computing from base tables
        3. Applying inheritance hierarchy
        """
        # Try fast path first - materialized view
        requirements = await self._get_from_materialized_view(portal_id, task_type_id)
        if requirements:
            return requirements
        
        # Fallback to computing from base tables
        return await self._compute_requirements(portal_id, task_type_id, as_of_date)
    
    async def _get_from_materialized_view(
        self, 
        portal_id: int, 
        task_type_id: UUID
    ) -> Optional[RequirementSet]:
        """Get requirements from materialized view (fast path)."""
        query = text("""
            SELECT 
                portal_id,
                org_id,
                portal_type_id,
                task_type_id,
                required_fields,
                optional_fields,
                field_rules,
                compliance_ref
            FROM effective_requirements
            WHERE portal_id = :portal_id 
            AND task_type_id = :task_type_id
        """)
        
        result = await self.session.execute(
            query, 
            {"portal_id": portal_id, "task_type_id": str(task_type_id)}
        )
        row = result.one_or_none()
        
        if row:
            return RequirementSet(
                portal_id=row.portal_id,
                task_type_id=UUID(row.task_type_id),
                org_id=UUID(row.org_id),
                portal_type_id=row.portal_type_id,
                required_fields=row.required_fields or [],
                optional_fields=row.optional_fields or [],
                field_rules=row.field_rules or {},
                compliance_ref=row.compliance_ref,
                source="effective_requirements"
            )
        
        return None
    
    async def _compute_requirements(
        self, 
        portal_id: int, 
        task_type_id: UUID,
        as_of_date: Optional[date] = None
    ) -> RequirementSet:
        """Compute requirements from base tables."""
        effective_date = as_of_date or date.today()
        
        # Get portal info
        portal_query = select(IntegrationEndpoint).where(
            IntegrationEndpoint.portal_id == portal_id
        ).options(selectinload(IntegrationEndpoint.portal_type))
        
        portal_result = await self.session.execute(portal_query)
        portal = portal_result.scalar_one()
        
        # Get base payer requirements
        payer_req_query = select(PayerRequirement).where(
            and_(
                PayerRequirement.portal_type_id == portal.portal_type_id,
                PayerRequirement.task_type_id == task_type_id,
                PayerRequirement.effective_date <= effective_date
            )
        ).order_by(PayerRequirement.version.desc()).limit(1)
        
        payer_result = await self.session.execute(payer_req_query)
        payer_req = payer_result.scalar_one_or_none()
        
        # Start with payer requirements or empty
        if payer_req:
            required_fields = list(payer_req.required_fields)
            optional_fields = list(payer_req.optional_fields)
            field_rules = dict(payer_req.field_rules)
            compliance_ref = payer_req.compliance_ref
        else:
            required_fields = []
            optional_fields = []
            field_rules = {}
            compliance_ref = None
        
        # Apply org policies
        policy_query = select(OrgRequirementPolicy).where(
            and_(
                OrgRequirementPolicy.org_id == portal.org_id,
                OrgRequirementPolicy.task_type_id == task_type_id,
                OrgRequirementPolicy.active == True,
                or_(
                    OrgRequirementPolicy.portal_type_id.is_(None),
                    OrgRequirementPolicy.portal_type_id == portal.portal_type_id
                )
            )
        ).order_by(OrgRequirementPolicy.version)
        
        policy_result = await self.session.execute(policy_query)
        policies = policy_result.scalars().all()
        
        # Apply each policy in order
        for policy in policies:
            required_fields, optional_fields, field_rules = self._apply_policy(
                required_fields, 
                optional_fields,
                field_rules,
                policy
            )
        
        return RequirementSet(
            portal_id=portal_id,
            task_type_id=task_type_id,
            org_id=portal.org_id,
            portal_type_id=portal.portal_type_id,
            required_fields=required_fields,
            optional_fields=optional_fields,
            field_rules=field_rules,
            compliance_ref=compliance_ref,
            source="computed"
        )
    
    def _apply_policy(
        self,
        required_fields: List[str],
        optional_fields: List[str],
        field_rules: Dict[str, Any],
        policy: OrgRequirementPolicy
    ) -> tuple[List[str], List[str], Dict[str, Any]]:
        """Apply a single policy to the requirement sets."""
        changes = policy.field_changes
        
        if policy.policy_type == PolicyType.ADD:
            # Add new fields
            if "required_fields" in changes:
                for field in changes["required_fields"]:
                    if field not in required_fields:
                        required_fields.append(field)
            
            if "optional_fields" in changes:
                for field in changes["optional_fields"]:
                    if field not in optional_fields and field not in required_fields:
                        optional_fields.append(field)
            
            if "field_rules" in changes:
                field_rules.update(changes["field_rules"])
        
        elif policy.policy_type == PolicyType.REMOVE:
            # Remove fields
            if "required_fields" in changes:
                required_fields = [f for f in required_fields if f not in changes["required_fields"]]
            
            if "optional_fields" in changes:
                optional_fields = [f for f in optional_fields if f not in changes["optional_fields"]]
            
            if "field_rules" in changes:
                for field in changes["field_rules"]:
                    field_rules.pop(field, None)
        
        elif policy.policy_type == PolicyType.OVERRIDE:
            # Complete replacement
            if "required_fields" in changes:
                required_fields = list(changes["required_fields"])
            
            if "optional_fields" in changes:
                optional_fields = list(changes["optional_fields"])
            
            if "field_rules" in changes:
                field_rules = dict(changes["field_rules"])
        
        return required_fields, optional_fields, field_rules
    
    async def validate_fields(
        self,
        portal_id: int,
        task_type_id: UUID,
        submitted_fields: Dict[str, Any]
    ) -> ValidationResult:
        """Validates submitted fields against requirements."""
        requirements = await self.get_requirements(portal_id, task_type_id)
        return requirements.validate_fields(submitted_fields)
    
    async def get_all_requirements_for_org(
        self,
        org_id: UUID,
        task_type_id: Optional[UUID] = None
    ) -> List[RequirementSet]:
        """Get all requirements for an organization's portals."""
        # Get all portals for the org
        portal_query = select(IntegrationEndpoint).where(
            IntegrationEndpoint.org_id == org_id
        )
        
        portal_result = await self.session.execute(portal_query)
        portals = portal_result.scalars().all()
        
        requirements = []
        for portal in portals:
            if task_type_id:
                # Single task type
                req = await self.get_requirements(portal.portal_id, task_type_id)
                requirements.append(req)
            else:
                # All task types
                task_query = select(TaskType.task_type_id)
                task_result = await self.session.execute(task_query)
                task_ids = task_result.scalars().all()
                
                for tid in task_ids:
                    req = await self.get_requirements(portal.portal_id, tid)
                    requirements.append(req)
        
        return requirements
    
    async def refresh_materialized_view(self) -> None:
        """Manually refresh the materialized view."""
        await self.session.execute(text("REFRESH MATERIALIZED VIEW effective_requirements"))
        await self.session.commit()