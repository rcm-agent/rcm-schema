"""Pydantic schemas for all RCM database models.

These schemas provide serialization/deserialization and validation for API requests/responses.
"""

from typing import Optional, List, Dict, Any, Union
from datetime import datetime
from decimal import Decimal
from uuid import UUID
from pydantic import BaseModel, Field, ConfigDict, field_validator, model_validator
from enum import Enum


# Re-export PostgreSQL enums as Python enums for API use
class OrgType(str, Enum):
    HOSPITAL = "hospital"
    BILLING_FIRM = "billing_firm"
    CREDENTIALER = "credentialer"


class EndpointKind(str, Enum):
    PAYER = "payer"
    PROVIDER = "provider"


class TaskDomain(str, Enum):
    # Core BPO domains
    ELIGIBILITY = "eligibility"          # Insurance verification
    CLAIM = "claim"                      # Claims processing
    PRIOR_AUTH = "prior_auth"            # Prior authorization
    
    # Extended BPO domains (future implementation)
    CREDENTIALING = "credentialing"      # Provider enrollment
    CODING = "coding"                    # Medical coding
    CHARGE_CAPTURE = "charge_capture"    # Charge entry
    DENIAL_MGMT = "denial_mgmt"          # Denial management
    PAYMENT_POSTING = "payment_posting"  # Payment processing
    AR_FOLLOWUP = "ar_followup"          # Accounts receivable
    PATIENT_ACCESS = "patient_access"    # Registration/demographics


class TaskAction(str, Enum):
    # Eligibility Actions (270/271)
    VERIFY = "verify"                         # Real-time eligibility verification
    BATCH_VERIFY = "batch_verify"             # Batch eligibility processing
    BENEFITS_BREAKDOWN = "benefits_breakdown" # Detailed benefits analysis
    COVERAGE_DISCOVERY = "coverage_discovery" # Find unknown coverage
    
    # Prior Authorization Actions (278)
    REQUEST = "request"                       # Initial auth request
    SUBMIT = "submit"                         # Submit with clinical documentation
    INQUIRE = "inquire"                       # Check auth status (generic)
    APPEAL = "appeal"                         # Appeal denied authorization
    EXTEND = "extend"                         # Request extension
    EXPEDITE = "expedite"                     # Expedited/urgent auth
    
    # Claim Actions (837/276/277)
    CLAIM_SUBMIT = "claim_submit"             # Submit new claim (837)
    CLAIM_INQUIRE = "claim_inquire"           # Check claim status (276/277)
    CLAIM_CORRECT = "claim_correct"           # Correct and resubmit
    CLAIM_APPEAL = "claim_appeal"             # Appeal claim denial
    CLAIM_VOID = "claim_void"                 # Void submitted claim
    
    # Credentialing Actions
    PROVIDER_ENROLL = "provider_enroll"       # Initial provider enrollment
    CREDENTIAL_VERIFY = "credential_verify"   # Verify provider credentials
    PRIVILEGE_UPDATE = "privilege_update"     # Update hospital privileges
    REVALIDATE = "revalidate"                 # Periodic revalidation
    CAQH_UPDATE = "caqh_update"               # Update CAQH profile
    
    # Coding Actions
    ASSIGN_CODES = "assign_codes"             # Assign ICD-10/CPT codes
    AUDIT_CODES = "audit_codes"               # Audit coding accuracy
    QUERY_PHYSICIAN = "query_physician"       # Query for clarification
    CODE_REVIEW = "code_review"               # Peer review coding
    
    # Charge Capture Actions
    CHARGE_ENTRY = "charge_entry"             # Enter charges
    CHARGE_AUDIT = "charge_audit"             # Audit charges
    CHARGE_RECONCILE = "charge_reconcile"     # Reconcile with clinical
    
    # Denial Management Actions
    DENIAL_REVIEW = "denial_review"           # Review denial reason
    DENIAL_APPEAL = "denial_appeal"           # Submit appeal
    DENIAL_FOLLOWUP = "denial_followup"       # Follow up on appeal
    DENIAL_PREVENT = "denial_prevent"         # Preventive analysis
    
    # Payment Posting Actions
    POST_ERA = "post_era"                     # Post electronic remittance (835)
    POST_MANUAL = "post_manual"               # Manual payment posting
    RECONCILE_PAYMENT = "reconcile_payment"   # Reconcile payments
    IDENTIFY_VARIANCE = "identify_variance"   # Identify payment variances
    
    # AR Follow-up Actions
    AR_REVIEW = "ar_review"                   # Review aging accounts
    AR_FOLLOWUP = "ar_followup"               # Follow up on unpaid claims
    AR_APPEAL = "ar_appeal"                   # Appeal for AR resolution
    AR_WRITEOFF = "ar_writeoff"               # Recommend write-offs
    
    # Patient Access Actions
    REGISTER_PATIENT = "register_patient"     # Patient registration
    VERIFY_DEMOGRAPHICS = "verify_demographics" # Verify patient information
    INSURANCE_DISCOVERY = "insurance_discovery" # Discover insurance coverage
    ESTIMATE_COPAY = "estimate_copay"         # Estimate patient responsibility
    
    # Deprecated - kept for backward compatibility
    STATUS_CHECK = "status_check"             # DEPRECATED: Use VERIFY or appropriate action
    DENIAL_FOLLOW_UP = "denial_follow_up"     # DEPRECATED: Use DENIAL_FOLLOWUP


class TaskSignatureSource(str, Enum):
    HUMAN = "human"
    AI = "ai"


class WorkflowType(str, Enum):
    ELIGIBILITY = "eligibility"
    CLAIM_STATUS = "claim_status"
    PRIOR_AUTH = "prior_auth"


class JobStatus(str, Enum):
    QUEUED = "queued"
    PROCESSING = "processing"
    SUCCESS = "success"
    ERROR = "error"


class UserRole(str, Enum):
    ORG_ADMIN = "org_admin"
    FIRM_USER = "firm_user"
    HOSPITAL_USER = "hospital_user"
    SYS_ADMIN = "sys_admin"


# Custom field types
class Vector(BaseModel):
    """Custom type for pgvector arrays."""
    values: List[float]
    dimensions: int
    
    @field_validator('values')
    @classmethod
    def validate_dimensions(cls, v, info):
        if 'dimensions' in info.data and len(v) != info.data['dimensions']:
            raise ValueError(f"Expected {info.data['dimensions']} dimensions, got {len(v)}")
        return v


# Base schemas with common fields
class TimestampMixin(BaseModel):
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


# Organization schemas
class OrganizationBase(BaseModel):
    org_type: OrgType
    name: str
    email_domain: Optional[str] = None


class OrganizationCreate(OrganizationBase):
    pass


class OrganizationUpdate(BaseModel):
    name: Optional[str] = None
    email_domain: Optional[str] = None


class Organization(OrganizationBase):
    org_id: UUID
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)


# Portal Type schemas
class PortalTypeBase(BaseModel):
    code: Optional[str] = None
    name: str
    base_url: str
    endpoint_kind: EndpointKind


class PortalTypeCreate(PortalTypeBase):
    pass


class PortalTypeUpdate(BaseModel):
    name: Optional[str] = None
    base_url: Optional[str] = None


class PortalType(PortalTypeBase):
    portal_type_id: int
    
    model_config = ConfigDict(from_attributes=True)


# Integration Endpoint schemas
class IntegrationEndpointBase(BaseModel):
    name: str
    portal_type_id: int
    base_url: Optional[str] = None
    config: Optional[Dict[str, Any]] = Field(default_factory=dict)


class IntegrationEndpointCreate(IntegrationEndpointBase):
    org_id: Optional[UUID] = None  # Will be set from auth context


class IntegrationEndpointUpdate(BaseModel):
    name: Optional[str] = None
    base_url: Optional[str] = None
    config: Optional[Dict[str, Any]] = None


class IntegrationEndpoint(IntegrationEndpointBase):
    portal_id: int
    org_id: UUID
    created_at: datetime
    portal_type: Optional[PortalType] = None  # For joined queries
    
    model_config = ConfigDict(from_attributes=True)


# Task Type schemas
class TaskTypeBase(BaseModel):
    domain: TaskDomain
    action: TaskAction
    display_name: str
    description: Optional[str] = None


class TaskTypeCreate(TaskTypeBase):
    pass


class TaskTypeUpdate(BaseModel):
    display_name: Optional[str] = None
    description: Optional[str] = None


class TaskType(TaskTypeBase):
    task_type_id: UUID
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)


# Field Requirement schemas
class FieldRequirementBase(BaseModel):
    task_type_id: UUID
    portal_id: Optional[int] = None
    required_fields: List[str] = Field(default_factory=list)
    optional_fields: List[str] = Field(default_factory=list)
    field_metadata: Dict[str, Any] = Field(default_factory=dict)
    version: int = 1
    active: bool = True


class FieldRequirementCreate(FieldRequirementBase):
    pass


class FieldRequirementUpdate(BaseModel):
    required_fields: Optional[List[str]] = None
    optional_fields: Optional[List[str]] = None
    field_metadata: Optional[Dict[str, Any]] = None
    version: Optional[int] = None
    active: Optional[bool] = None


class FieldRequirement(FieldRequirementBase):
    requirement_id: UUID
    created_at: datetime
    updated_at: Optional[datetime] = None
    task_type: Optional[TaskType] = None  # For joined queries
    portal: Optional[IntegrationEndpoint] = None  # For joined queries
    
    model_config = ConfigDict(from_attributes=True)


# Batch Job schemas
class BatchJobBase(BaseModel):
    portal_id: int
    task_type_id: UUID
    status: JobStatus = JobStatus.QUEUED


class BatchJobCreate(BatchJobBase):
    org_id: Optional[UUID] = None  # Will be set from auth context


class BatchJobUpdate(BaseModel):
    status: Optional[JobStatus] = None
    completed_at: Optional[datetime] = None
    result_url: Optional[str] = None


class BatchJob(BatchJobBase):
    batch_id: UUID
    org_id: UUID
    created_at: datetime
    completed_at: Optional[datetime] = None
    result_url: Optional[str] = None
    portal: Optional[IntegrationEndpoint] = None  # For joined queries
    task_type: Optional[TaskType] = None  # For joined queries
    
    model_config = ConfigDict(from_attributes=True)


# Batch Row schemas
class BatchRowBase(BaseModel):
    row_idx: int
    task_signature: Optional[str] = None
    trace_id: Optional[UUID] = None
    status: JobStatus = JobStatus.QUEUED
    error_code: Optional[str] = None
    error_msg: Optional[str] = None


class BatchRowCreate(BatchRowBase):
    batch_id: UUID


class BatchRowUpdate(BaseModel):
    task_signature: Optional[str] = None
    trace_id: Optional[UUID] = None
    status: Optional[JobStatus] = None
    error_code: Optional[str] = None
    error_msg: Optional[str] = None


class BatchRow(BatchRowBase):
    row_id: UUID
    batch_id: UUID
    created_at: datetime
    updated_at: Optional[datetime] = None
    
    model_config = ConfigDict(from_attributes=True)


# RCM State schemas
class RcmStateBase(BaseModel):
    portal_id: int
    text_emb: List[float] = Field(..., description="768D text embedding")
    image_emb: List[float] = Field(..., description="512D image embedding")
    semantic_spec: Dict[str, Any]
    action: Dict[str, Any]
    success_ema: float = Field(default=1.0, ge=0.0, le=1.0)
    page_caption: Optional[str] = None
    action_caption: Optional[str] = None
    caption_conf: Optional[Decimal] = Field(None, ge=0, le=1)
    macro_state_id: Optional[UUID] = None
    is_retired: bool = False
    alias_state_id: Optional[UUID] = None
    
    @field_validator('text_emb')
    @classmethod
    def validate_text_emb(cls, v):
        if len(v) != 768:
            raise ValueError(f"Text embedding must be 768D, got {len(v)}D")
        return v
    
    @field_validator('image_emb')
    @classmethod
    def validate_image_emb(cls, v):
        if len(v) != 512:
            raise ValueError(f"Image embedding must be 512D, got {len(v)}D")
        return v


class RcmStateCreate(RcmStateBase):
    pass


class RcmStateUpdate(BaseModel):
    success_ema: Optional[float] = Field(None, ge=0.0, le=1.0)
    page_caption: Optional[str] = None
    action_caption: Optional[str] = None
    caption_conf: Optional[Decimal] = Field(None, ge=0, le=1)
    macro_state_id: Optional[UUID] = None
    is_retired: Optional[bool] = None
    alias_state_id: Optional[UUID] = None


class RcmState(RcmStateBase):
    state_id: UUID
    portal: Optional[IntegrationEndpoint] = None  # For joined queries
    macro_state: Optional['MacroState'] = None  # For joined queries
    
    model_config = ConfigDict(from_attributes=True)


# Macro State schemas
class MacroStateBase(BaseModel):
    portal_id: Optional[int] = None
    canonical_caption: Optional[str] = None
    description: Optional[str] = None
    sample_state_id: Optional[UUID] = None


class MacroStateCreate(MacroStateBase):
    pass


class MacroStateUpdate(BaseModel):
    canonical_caption: Optional[str] = None
    description: Optional[str] = None
    sample_state_id: Optional[UUID] = None


class MacroState(MacroStateBase):
    macro_state_id: UUID
    portal: Optional[IntegrationEndpoint] = None  # For joined queries
    sample_state: Optional[RcmState] = None  # For joined queries
    
    model_config = ConfigDict(from_attributes=True)


# Task Signature schemas
class TaskSignatureBase(BaseModel):
    domain: TaskDomain
    action: TaskAction
    source: TaskSignatureSource
    text_emb: Optional[List[float]] = Field(None, description="768D text embedding")
    image_emb: Optional[List[float]] = Field(None, description="512D image embedding")
    sample_trace_id: Optional[UUID] = None
    alias_of: Optional[UUID] = None
    composed: bool = False
    
    @field_validator('text_emb')
    @classmethod
    def validate_text_emb(cls, v):
        if v is not None and len(v) != 768:
            raise ValueError(f"Text embedding must be 768D, got {len(v)}D")
        return v
    
    @field_validator('image_emb')
    @classmethod
    def validate_image_emb(cls, v):
        if v is not None and len(v) != 512:
            raise ValueError(f"Image embedding must be 512D, got {len(v)}D")
        return v


class TaskSignatureCreate(TaskSignatureBase):
    portal_id: Optional[int] = None
    portal_type_id: Optional[int] = None
    
    @model_validator(mode='after')
    def validate_xor_constraint(self):
        if (self.portal_id is None) == (self.portal_type_id is None):
            raise ValueError("Exactly one of portal_id or portal_type_id must be provided")
        return self


class TaskSignatureUpdate(BaseModel):
    source: Optional[TaskSignatureSource] = None
    text_emb: Optional[List[float]] = Field(None, description="768D text embedding")
    image_emb: Optional[List[float]] = Field(None, description="512D image embedding")
    sample_trace_id: Optional[UUID] = None
    alias_of: Optional[UUID] = None
    composed: Optional[bool] = None
    
    @field_validator('text_emb')
    @classmethod
    def validate_text_emb(cls, v):
        if v is not None and len(v) != 768:
            raise ValueError(f"Text embedding must be 768D, got {len(v)}D")
        return v
    
    @field_validator('image_emb')
    @classmethod
    def validate_image_emb(cls, v):
        if v is not None and len(v) != 512:
            raise ValueError(f"Image embedding must be 512D, got {len(v)}D")
        return v


class TaskSignature(TaskSignatureBase):
    signature_id: UUID
    portal_id: Optional[int] = None
    portal_type_id: Optional[int] = None
    updated_at: datetime
    portal: Optional[IntegrationEndpoint] = None  # For joined queries
    portal_type: Optional[PortalType] = None  # For joined queries
    
    model_config = ConfigDict(from_attributes=True)


# RCM Trace schemas
class RcmTraceBase(BaseModel):
    portal_id: int
    task_signature: Optional[UUID] = None
    prompt_version: Optional[str] = Field(None, max_length=20)
    used_fallback: bool = False
    fallback_model: Optional[str] = None
    trace: Dict[str, Any]
    duration_ms: Optional[int] = None
    success: Optional[bool] = None


class RcmTraceCreate(RcmTraceBase):
    org_id: Optional[UUID] = None  # Will be set from auth context


class RcmTraceUpdate(BaseModel):
    task_signature: Optional[UUID] = None
    duration_ms: Optional[int] = None
    success: Optional[bool] = None


class RcmTrace(RcmTraceBase):
    trace_id: UUID
    org_id: UUID
    created_at: datetime
    portal: Optional[IntegrationEndpoint] = None  # For joined queries
    signature: Optional[TaskSignature] = None  # For joined queries
    
    model_config = ConfigDict(from_attributes=True)


# RCM Transition schemas
class RcmTransitionBase(BaseModel):
    from_state: UUID
    to_state: UUID
    action_caption: str
    freq: int = Field(default=1, ge=1)


class RcmTransitionCreate(RcmTransitionBase):
    pass


class RcmTransitionUpdate(BaseModel):
    freq: Optional[int] = Field(None, ge=1)


class RcmTransition(RcmTransitionBase):
    from_state_obj: Optional[RcmState] = None  # For joined queries
    to_state_obj: Optional[RcmState] = None  # For joined queries
    
    model_config = ConfigDict(from_attributes=True)


# App User schemas
class AppUserBase(BaseModel):
    email: str
    full_name: Optional[str] = None
    role: UserRole


class AppUserCreate(AppUserBase):
    user_id: UUID  # From Cognito
    org_id: Optional[UUID] = None  # Will be set from auth context or admin


class AppUserUpdate(BaseModel):
    full_name: Optional[str] = None
    role: Optional[UserRole] = None


class AppUser(AppUserBase):
    user_id: UUID
    org_id: UUID
    created_at: datetime
    organization: Optional[Organization] = None  # For joined queries
    
    model_config = ConfigDict(from_attributes=True)


# Pagination schemas
class PaginationParams(BaseModel):
    offset: int = Field(default=0, ge=0)
    limit: int = Field(default=10, ge=1, le=100)


class PaginatedResponse(BaseModel):
    items: List[Any]
    total: int
    offset: int
    limit: int
    
    @property
    def has_more(self) -> bool:
        return self.offset + self.limit < self.total


# Update forward references
RcmState.model_rebuild()
MacroState.model_rebuild()