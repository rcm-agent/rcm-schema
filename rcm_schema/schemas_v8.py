"""
Pydantic schemas for V8 RCM Schema
API validation and serialization models
"""
from datetime import datetime
from typing import Optional, List, Dict, Any
from uuid import UUID
from enum import Enum
from pydantic import BaseModel, Field, validator, constr, confloat
import numpy as np


# ============================================================================
# Enums (for backward compatibility and validation)
# ============================================================================

class OrgType(str, Enum):
    HOSPITAL = "hospital"
    BILLING_FIRM = "billing_firm"
    CREDENTIALER = "credentialer"


class EndpointKind(str, Enum):
    PAYER = "payer"
    PROVIDER = "provider"
    CLEARINGHOUSE = "clearinghouse"


class AccessMedium(str, Enum):
    WEB = "web"
    PHONE = "phone"
    FAX = "fax"
    EFAX = "efax"
    EDI = "edi"


class TaskDomain(str, Enum):
    ELIGIBILITY = "eligibility"
    PRIOR_AUTH = "prior_auth"
    CLAIM = "claim"
    PAYMENT = "payment"
    PATIENT = "patient"
    PROVIDER = "provider"
    BILLING = "billing"
    REPORTING = "reporting"
    DOCUMENT = "document"


class TaskAction(str, Enum):
    # General actions
    CHECK = "check"
    VERIFY = "verify"
    UPDATE = "update"
    
    # Prior auth actions
    SUBMIT = "submit"
    CHECK_STATUS = "check_status"
    APPEAL = "appeal"
    EXTEND = "extend"
    
    # Claim actions
    SUBMIT_CLAIM = "submit_claim"
    STATUS_CHECK = "status_check"
    RESUBMIT = "resubmit"
    VOID = "void"
    CORRECT = "correct"
    
    # Payment actions
    POST = "post"
    RECONCILE = "reconcile"
    ADJUST = "adjust"
    REFUND = "refund"
    
    # Patient actions
    SEARCH = "search"
    REGISTER = "register"
    UPDATE_DEMOGRAPHICS = "update_demographics"
    VERIFY_INSURANCE = "verify_insurance"
    
    # Provider actions
    CREDENTIAL = "credential"
    ENROLL = "enroll"
    UPDATE_INFO = "update_info"
    
    # Billing actions
    GENERATE_STATEMENT = "generate_statement"
    SEND_INVOICE = "send_invoice"
    APPLY_PAYMENT = "apply_payment"
    
    # Reporting actions
    GENERATE_REPORT = "generate_report"
    EXPORT_DATA = "export_data"
    ANALYZE = "analyze"
    
    # Document actions
    UPLOAD = "upload"
    DOWNLOAD = "download"
    PARSE = "parse"
    VALIDATE = "validate"
    
    # Legacy actions
    CHECK_LEGACY = "check_legacy"
    STATUS_CHECK_LEGACY = "status_check_legacy"


class TaskSignatureSource(str, Enum):
    HUMAN = "human"
    AI_GENERATED = "ai_generated"
    SYSTEM_LEARNED = "system_learned"


class JobStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    PARTIALLY_COMPLETED = "partially_completed"


class RequirementType(str, Enum):
    REQUIRED = "required"
    CONDITIONAL = "conditional"
    OPTIONAL = "optional"
    OUTPUT = "output"


class UserRole(str, Enum):
    ADMIN = "admin"
    OPERATOR = "operator"
    VIEWER = "viewer"
    API_USER = "api_user"
    ORG_ADMIN = "org_admin"
    FIRM_USER = "firm_user"
    HOSPITAL_USER = "hospital_user"
    SYS_ADMIN = "sys_admin"


# ============================================================================
# Base Schemas
# ============================================================================

class BaseSchema(BaseModel):
    """Base schema with common configuration"""
    class Config:
        orm_mode = True
        use_enum_values = True
        json_encoders = {
            datetime: lambda v: v.isoformat() if v else None,
            UUID: lambda v: str(v) if v else None,
            np.ndarray: lambda v: v.tolist() if v is not None else None
        }


# ============================================================================
# Organization Schemas
# ============================================================================

class OrganizationBase(BaseSchema):
    org_type: OrgType
    name: constr(min_length=1, max_length=255)
    email_domain: Optional[str] = None


class OrganizationCreate(OrganizationBase):
    pass


class OrganizationUpdate(BaseSchema):
    org_type: Optional[OrgType] = None
    name: Optional[constr(min_length=1, max_length=255)] = None
    email_domain: Optional[str] = None


class Organization(OrganizationBase):
    org_id: UUID
    created_at: datetime
    
    # Computed fields
    user_count: Optional[int] = 0
    endpoint_count: Optional[int] = 0


# ============================================================================
# Channel Type and Endpoint Schemas
# ============================================================================

class ChannelTypeBase(BaseSchema):
    code: Optional[str] = None
    name: constr(min_length=1, max_length=255)
    base_url: Optional[str] = None
    endpoint_kind: EndpointKind
    access_medium: AccessMedium


class ChannelTypeCreate(ChannelTypeBase):
    pass


class ChannelType(ChannelTypeBase):
    channel_type_id: int


class EndpointBase(BaseSchema):
    name: constr(min_length=1, max_length=255)
    channel_type_id: int
    base_url: Optional[str] = None
    config: Dict[str, Any] = Field(default_factory=dict)


class EndpointCreate(EndpointBase):
    org_id: UUID


class EndpointUpdate(BaseSchema):
    name: Optional[constr(min_length=1, max_length=255)] = None
    base_url: Optional[str] = None
    config: Optional[Dict[str, Any]] = None


class Endpoint(EndpointBase):
    endpoint_id: int
    org_id: UUID
    created_at: datetime
    channel_type: Optional[ChannelType] = None


# ============================================================================
# User Schemas
# ============================================================================

class AppUserBase(BaseSchema):
    email: constr(min_length=1, max_length=255)
    full_name: Optional[str] = None
    role: UserRole
    is_active: bool = True


class AppUserCreate(AppUserBase):
    org_id: UUID
    password: constr(min_length=8)  # For initial user creation


class AppUserUpdate(BaseSchema):
    email: Optional[constr(min_length=1, max_length=255)] = None
    full_name: Optional[str] = None
    role: Optional[UserRole] = None
    is_active: Optional[bool] = None


class AppUser(AppUserBase):
    user_id: UUID
    org_id: UUID
    created_at: datetime
    updated_at: datetime
    last_login_at: Optional[datetime] = None
    organization: Optional[Organization] = None


# ============================================================================
# Task Type Schemas
# ============================================================================

class TaskTypeBase(BaseSchema):
    domain: TaskDomain
    action: TaskAction
    name: constr(min_length=1, max_length=255)
    description: Optional[str] = None
    is_active: bool = True


class TaskTypeCreate(TaskTypeBase):
    pass


class TaskTypeUpdate(BaseSchema):
    name: Optional[constr(min_length=1, max_length=255)] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None


class TaskType(TaskTypeBase):
    task_type_id: UUID
    version: int
    created_at: datetime
    updated_at: datetime


# ============================================================================
# Field Requirement Schemas
# ============================================================================

class FieldRequirementBase(BaseSchema):
    field_name: constr(min_length=1, max_length=255)
    field_type: str
    requirement_type: RequirementType = RequirementType.REQUIRED
    business_logic: Dict[str, Any] = Field(default_factory=dict)
    validation_rules: Dict[str, Any] = Field(default_factory=dict)
    condition_expr: Optional[str] = None
    required_when: Optional[Dict[str, Any]] = None
    ui_config: Dict[str, Any] = Field(default_factory=dict)
    source: TaskSignatureSource = TaskSignatureSource.HUMAN
    confidence_score: Optional[confloat(ge=0, le=1)] = None
    portal_specific: bool = False


class FieldRequirementCreate(FieldRequirementBase):
    task_type_id: UUID
    parent_id: Optional[UUID] = None


class FieldRequirementUpdate(BaseSchema):
    field_name: Optional[constr(min_length=1, max_length=255)] = None
    field_type: Optional[str] = None
    requirement_type: Optional[RequirementType] = None
    business_logic: Optional[Dict[str, Any]] = None
    validation_rules: Optional[Dict[str, Any]] = None
    condition_expr: Optional[str] = None
    required_when: Optional[Dict[str, Any]] = None
    ui_config: Optional[Dict[str, Any]] = None
    confidence_score: Optional[confloat(ge=0, le=1)] = None


class FieldRequirement(FieldRequirementBase):
    field_req_id: UUID
    task_type_id: UUID
    parent_id: Optional[UUID] = None
    path: str
    depth: int
    created_at: datetime
    updated_at: datetime
    children: Optional[List['FieldRequirement']] = []


# ============================================================================
# Workflow Schemas
# ============================================================================

# New workflow node schemas (workflow-owned nodes)
class UserWorkflowNodeBase(BaseSchema):
    label: str  # Renamed from 'code'
    description: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    label_conf: Optional[confloat(ge=0, le=1)] = None


class UserWorkflowNodeCreate(UserWorkflowNodeBase):
    workflow_id: UUID


class UserWorkflowNode(UserWorkflowNodeBase):
    node_id: UUID
    workflow_id: UUID
    last_label_at: Optional[datetime] = None


class UserWorkflowTransitionBase(BaseSchema):
    from_node: UUID
    to_node: UUID
    action_label: str
    freq: int = 1


class UserWorkflowTransitionCreate(UserWorkflowTransitionBase):
    workflow_id: UUID


class UserWorkflowTransition(UserWorkflowTransitionBase):
    workflow_id: UUID


class UserWorkflowBase(BaseSchema):
    name: constr(min_length=1, max_length=255)
    description: Optional[str] = None
    required_data: List[Dict[str, Any]] = Field(default_factory=list)


class UserWorkflowCreate(UserWorkflowBase):
    pass


class UserWorkflowUpdate(BaseSchema):
    name: Optional[constr(min_length=1, max_length=255)] = None
    description: Optional[str] = None
    required_data: Optional[List[Dict[str, Any]]] = None


class UserWorkflow(UserWorkflowBase):
    workflow_id: UUID
    created_at: datetime
    updated_at: datetime


# ============================================================================
# Workflow Revision Schemas
# ============================================================================

class WorkflowRevisionBase(BaseSchema):
    comment: Optional[str] = None


class WorkflowRevisionCreate(WorkflowRevisionBase):
    workflow_id: UUID
    snapshot: Dict[str, Any]  # Contains nodes and transitions


class WorkflowRevisionResponse(WorkflowRevisionBase):
    revision_id: int
    workflow_id: UUID
    revision_num: int
    created_by: str
    created_at: datetime
    snapshot: Dict[str, Any]


# ============================================================================
# Micro State Schemas
# ============================================================================

class MicroStateBase(BaseSchema):
    workflow_id: UUID
    node_id: UUID  # Changed from int to UUID
    dom_snapshot: str
    action_json: Dict[str, Any]
    semantic_spec: Optional[Dict[str, Any]] = None
    label: Optional[str] = None
    category: Optional[str] = None
    required: bool = False
    text_emb: List[float]  # 768-dimensional vector
    mini_score: Optional[confloat(ge=0, le=1)] = None


class MicroStateCreate(MicroStateBase):
    pass
    
    @validator('text_emb')
    def validate_embedding_dimension(cls, v):
        if len(v) != 768:
            raise ValueError('text_emb must be 768-dimensional')
        return v


class MicroState(MicroStateBase):
    micro_state_id: int
    is_dynamic: bool
    is_retired: bool
    aliased_to: Optional[int] = None
    created_at: datetime


# ============================================================================
# Batch Processing Schemas
# ============================================================================

class BatchJobBase(BaseSchema):
    task_type_id: UUID
    file_path: constr(max_length=500)
    file_s3_bucket_param: Optional[constr(max_length=512)] = None
    file_s3_key: Optional[constr(max_length=1024)] = None


class BatchJobCreate(BatchJobBase):
    user_id: UUID


class BatchJobUpdate(BaseSchema):
    status: Optional[JobStatus] = None
    error_summary: Optional[Dict[str, Any]] = None


class BatchJob(BatchJobBase):
    batch_job_id: UUID
    user_id: UUID
    status: JobStatus
    total_items: int
    processed_items: int
    failed_items: int
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error_summary: Optional[Dict[str, Any]] = None
    created_at: datetime
    updated_at: datetime
    
    # Computed fields
    progress_percentage: Optional[int] = None
    is_complete: Optional[bool] = None


class BatchJobItemBase(BaseSchema):
    item_index: int
    input_data: Dict[str, Any]


class BatchJobItemCreate(BatchJobItemBase):
    batch_job_id: UUID


class BatchJobItemUpdate(BaseSchema):
    output_data: Optional[Dict[str, Any]] = None
    status: Optional[JobStatus] = None
    error_message: Optional[str] = None


class BatchJobItem(BatchJobItemBase):
    batch_job_item_id: UUID
    batch_job_id: UUID
    output_data: Optional[Dict[str, Any]] = None
    status: JobStatus
    error_message: Optional[str] = None
    attempts: int
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime


# ============================================================================
# Workflow Trace Schemas
# ============================================================================

class WorkflowTraceBase(BaseSchema):
    org_id: UUID
    workflow_id: Optional[UUID] = None
    action_type: Optional[str] = None
    action_detail: Optional[Dict[str, Any]] = None
    success: bool = False
    duration_ms: Optional[int] = None
    error_detail: Optional[Dict[str, Any]] = None
    llm_prompt: Optional[str] = None
    llm_response: Optional[str] = None
    llm_model: Optional[str] = None
    llm_tokens_used: Optional[int] = None
    tier: Optional[int] = None
    tier_reason: Optional[str] = None


class WorkflowTraceCreate(WorkflowTraceBase):
    batch_job_item_id: Optional[UUID] = None
    user_id: Optional[UUID] = None
    session_id: Optional[UUID] = None
    endpoint_ids: List[int] = []  # List of endpoints involved


class WorkflowTrace(WorkflowTraceBase):
    trace_id: int
    batch_job_item_id: Optional[UUID] = None
    created_at: datetime
    user_id: Optional[UUID] = None
    session_id: Optional[UUID] = None
    endpoints: Optional[List[Endpoint]] = []


# ============================================================================
# Credential Schemas
# ============================================================================

class PortalCredentialBase(BaseSchema):
    endpoint_id: int
    account_id: str
    is_active: bool = True


class PortalCredentialCreate(PortalCredentialBase):
    # One of these must be provided
    password_ssm_parameter_name: Optional[constr(max_length=512)] = None
    secret_arn: Optional[constr(max_length=512)] = None
    encrypted_password: Optional[str] = None
    
    # Optional fields
    password_ssm_key_id: Optional[constr(max_length=256)] = None
    secret_version_id: Optional[constr(max_length=64)] = None
    encryption_key_id: Optional[constr(max_length=256)] = None
    
    @validator('secret_arn')
    def validate_storage_method(cls, v, values):
        if not v and not values.get('password_ssm_parameter_name') and not values.get('encrypted_password'):
            raise ValueError('Must provide either password_ssm_parameter_name, secret_arn, or encrypted_password')
        return v


class PortalCredentialUpdate(BaseSchema):
    is_active: Optional[bool] = None
    session_token: Optional[str] = None
    token_expires_at: Optional[datetime] = None
    last_used_at: Optional[datetime] = None


class PortalCredential(PortalCredentialBase):
    credential_id: UUID
    has_password: bool = Field(description="Indicates if password is stored")
    storage_method: str = Field(description="SSM Parameter Store, AWS Secrets Manager, or Local Encrypted")
    created_at: datetime
    updated_at: datetime
    last_used_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    endpoint: Optional[Endpoint] = None


# ============================================================================
# Response Models
# ============================================================================

class PaginationParams(BaseModel):
    page: int = Field(1, ge=1)
    page_size: int = Field(50, ge=1, le=1000)


class PaginatedResponse(BaseModel):
    items: List[Any]
    total: int
    page: int
    page_size: int
    pages: int


class HealthCheckResponse(BaseModel):
    status: str = "healthy"
    timestamp: datetime
    version: str
    database: bool = True


class ErrorResponse(BaseModel):
    error: str
    detail: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)


# Forward reference resolution
FieldRequirement.update_forward_refs()