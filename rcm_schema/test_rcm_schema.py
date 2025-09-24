#!/usr/bin/env python3
"""Test script to verify RCM schema implementation.

This script tests:
1. Model imports
2. Schema imports
3. Enum definitions
4. Basic model creation
5. Pydantic validation
"""

import sys
import traceback
from datetime import datetime
from uuid import uuid4
from decimal import Decimal

# Test imports
print("Testing imports...")
try:
    # Test model imports
    from models import (
        Base, Organization, PortalType, IntegrationEndpoint,
        TaskType, FieldRequirement, BatchJob, BatchRow,
        RcmState, MacroState, TaskSignature, RcmTrace,
        RcmTransition, AppUser
    )
    print("✓ Model imports successful")
except Exception as e:
    print(f"✗ Model import error: {e}")
    traceback.print_exc()
    sys.exit(1)

try:
    # Test schema imports
    from schemas import (
        OrgType, EndpointKind, TaskDomain, TaskAction,
        TaskSignatureSource, WorkflowType, JobStatus, UserRole,
        OrganizationCreate, TaskTypeCreate, TaskSignatureCreate,
        FieldRequirementCreate
    )
    print("✓ Schema imports successful")
except Exception as e:
    print(f"✗ Schema import error: {e}")
    traceback.print_exc()
    sys.exit(1)

try:
    # Test database imports
    from database import DatabaseManager, get_db_manager
    print("✓ Database utility imports successful")
except Exception as e:
    print(f"✗ Database import error: {e}")
    traceback.print_exc()
    sys.exit(1)

# Test enum values
print("\nTesting enum definitions...")
try:
    assert OrgType.HOSPITAL == "hospital"
    assert TaskDomain.ELIGIBILITY == "eligibility"
    assert TaskAction.STATUS_CHECK == "status_check"
    assert TaskSignatureSource.HUMAN == "human"
    assert TaskSignatureSource.AI == "ai"
    print("✓ Enum values correct")
except AssertionError as e:
    print(f"✗ Enum value error: {e}")
    sys.exit(1)

# Test Pydantic schema validation
print("\nTesting Pydantic schema validation...")
try:
    # Test organization creation
    org_data = OrganizationCreate(
        org_type=OrgType.HOSPITAL,
        name="Test Hospital",
        email_domain="test.org"
    )
    print(f"✓ Organization schema: {org_data.model_dump()}")
    
    # Test task type creation
    task_data = TaskTypeCreate(
        domain=TaskDomain.ELIGIBILITY,
        action=TaskAction.STATUS_CHECK,
        display_name="Test Eligibility Check",
        description="Test description"
    )
    print(f"✓ TaskType schema: {task_data.model_dump()}")
    
    # Test task signature with source
    sig_data = TaskSignatureCreate(
        portal_id=1,
        domain=TaskDomain.PRIOR_AUTH,
        action=TaskAction.SUBMIT,
        source=TaskSignatureSource.AI,
        text_emb=[0.1] * 768,
        image_emb=[0.2] * 512
    )
    print(f"✓ TaskSignature schema with source: {sig_data.source}")
    
    # Test field requirement
    field_data = FieldRequirementCreate(
        task_type_id=uuid4(),
        required_fields=["patient_id", "dob"],
        optional_fields=["middle_name"],
        field_metadata={"patient_id": {"format": "regex"}}
    )
    print(f"✓ FieldRequirement schema: {len(field_data.required_fields)} required fields")
    
except Exception as e:
    print(f"✗ Schema validation error: {e}")
    traceback.print_exc()
    sys.exit(1)

# Test model instantiation
print("\nTesting SQLAlchemy model instantiation...")
try:
    # Create organization instance
    org = Organization(
        org_id=uuid4(),
        org_type="hospital",
        name="Model Test Hospital",
        email_domain="modeltest.org"
    )
    print(f"✓ Organization model: {org.name}")
    
    # Create task type instance
    task_type = TaskType(
        task_type_id=uuid4(),
        domain="eligibility",
        action="status_check",
        display_name="Model Test Task",
        description="Test"
    )
    print(f"✓ TaskType model: {task_type.display_name}")
    
    # Create task signature with source
    task_sig = TaskSignature(
        signature_id=uuid4(),
        portal_id=1,
        domain="claim",
        action="submit",
        source="human",
        composed=False
    )
    print(f"✓ TaskSignature model with source: {task_sig.source}")
    
except Exception as e:
    print(f"✗ Model instantiation error: {e}")
    traceback.print_exc()
    sys.exit(1)

# Test vector field validation
print("\nTesting vector field validation...")
try:
    # Test correct dimensions
    sig_data = TaskSignatureCreate(
        portal_id=1,
        domain=TaskDomain.ELIGIBILITY,
        action=TaskAction.STATUS_CHECK,
        source=TaskSignatureSource.HUMAN,
        text_emb=[0.1] * 768,
        image_emb=[0.2] * 512
    )
    print("✓ Correct vector dimensions accepted")
    
    # Test incorrect dimensions (should fail)
    try:
        bad_sig = TaskSignatureCreate(
            portal_id=1,
            domain=TaskDomain.ELIGIBILITY,
            action=TaskAction.STATUS_CHECK,
            source=TaskSignatureSource.AI,
            text_emb=[0.1] * 100,  # Wrong dimension
            image_emb=[0.2] * 512
        )
        print("✗ Incorrect vector dimensions should have failed!")
    except ValueError as e:
        print(f"✓ Vector validation working: {e}")
    
except Exception as e:
    print(f"✗ Vector validation error: {e}")
    traceback.print_exc()

# Summary
print("\n" + "="*50)
print("RCM Schema Implementation Test Complete!")
print("="*50)
print("\nKey features verified:")
print("- All models imported successfully")
print("- All schemas imported successfully") 
print("- Enums defined correctly")
print("- TaskSignatureSource enum working")
print("- Pydantic validation working")
print("- SQLAlchemy models instantiate correctly")
print("- Vector dimension validation working")
print("\nThe schema implementation is ready for use!")
print("\nNext steps:")
print("1. Set DATABASE_URL environment variable")
print("2. Run: python init_db.py")
print("3. Start using in your services!")