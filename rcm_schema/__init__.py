"""RCM Schema package - Shared database models and utilities for RCM services."""

from .constants import (
    DATABASE_REQUIREMENTS,
    VERSION_COMPATIBILITY,
    EXTENSION_VERSIONS,
)

from .validators import (
    validate_postgresql_version_async,
    validate_postgresql_version_sync,
    validate_extensions_async,
    validate_extensions_sync,
    validate_database_compatibility_async,
    validate_database_compatibility_sync,
)

from .schemas import (
    # Enums
    OrgType,
    EndpointKind,
    TaskDomain,
    TaskAction,
    TaskSignatureSource,
    JobStatus,
    UserRole,
)

from .models import (
    # Base
    Base,
    
    # Models
    Organization,
    PortalType,
    IntegrationEndpoint,
    TaskType,
    FieldRequirement,
    BatchJob,
    BatchRow,
    RcmState,
    MacroState,
    TaskSignature,
    RcmTrace,
    RcmTransition,
    AppUser,
    
    # Workflow Models (V8)
    UserWorkflow,
    UserWorkflowNode,
    UserWorkflowTransition,
    WorkflowRevision,
    MicroState,
)

from .schemas import (
    # Enums (re-exported for API use)
    OrgType as OrgTypeSchema,
    EndpointKind as EndpointKindSchema,
    TaskDomain as TaskDomainSchema,
    TaskAction as TaskActionSchema,
    TaskSignatureSource as TaskSignatureSourceSchema,
    JobStatus as JobStatusSchema,
    UserRole as UserRoleSchema,
    
    # Organization schemas
    OrganizationBase,
    OrganizationCreate,
    OrganizationUpdate,
    Organization as OrganizationSchema,
    
    # Portal Type schemas
    PortalTypeBase,
    PortalTypeCreate,
    PortalTypeUpdate,
    PortalType as PortalTypeSchema,
    
    # Integration Endpoint schemas
    IntegrationEndpointBase,
    IntegrationEndpointCreate,
    IntegrationEndpointUpdate,
    IntegrationEndpoint as IntegrationEndpointSchema,
    
    # Task Type schemas
    TaskTypeBase,
    TaskTypeCreate,
    TaskTypeUpdate,
    TaskType as TaskTypeSchema,
    
    # Field Requirement schemas
    FieldRequirementBase,
    FieldRequirementCreate,
    FieldRequirementUpdate,
    FieldRequirement as FieldRequirementSchema,
    
    # Batch Job schemas
    BatchJobBase,
    BatchJobCreate,
    BatchJobUpdate,
    BatchJob as BatchJobSchema,
    
    # Batch Row schemas
    BatchRowBase,
    BatchRowCreate,
    BatchRowUpdate,
    BatchRow as BatchRowSchema,
    
    # RCM State schemas
    RcmStateBase,
    RcmStateCreate,
    RcmStateUpdate,
    RcmState as RcmStateSchema,
    
    # Macro State schemas
    MacroStateBase,
    MacroStateCreate,
    MacroStateUpdate,
    MacroState as MacroStateSchema,
    
    # Task Signature schemas
    TaskSignatureBase,
    TaskSignatureCreate,
    TaskSignatureUpdate,
    TaskSignature as TaskSignatureSchema,
    
    # RCM Trace schemas
    RcmTraceBase,
    RcmTraceCreate,
    RcmTraceUpdate,
    RcmTrace as RcmTraceSchema,
    
    # RCM Transition schemas
    RcmTransitionBase,
    RcmTransitionCreate,
    RcmTransitionUpdate,
    RcmTransition as RcmTransitionSchema,
    
    # App User schemas
    AppUserBase,
    AppUserCreate,
    AppUserUpdate,
    AppUser as AppUserSchema,
    
    # Utility schemas
    PaginationParams,
    PaginatedResponse,
    Vector,
)

from .database import (
    DatabaseManager,
    get_db_manager,
    get_session,
)

from .security import (
    SecurityContext,
    require_org_context,
    OrgFilterMixin,
    AuditMixin,
    check_org_access,
    validate_uuid,
    sanitize_org_id,
    extract_org_from_jwt,
)

__version__ = "0.1.0"

__all__ = [
    # Base
    "Base",
    
    # Database enums
    "OrgType",
    "EndpointKind", 
    "TaskDomain",
    "TaskAction",
    "TaskSignatureSource",
    "JobStatus",
    "UserRole",
    
    # Models
    "Organization",
    "PortalType",
    "IntegrationEndpoint",
    "TaskType",
    "FieldRequirement",
    "BatchJob",
    "BatchRow",
    "RcmState",
    "MacroState",
    "TaskSignature",
    "RcmTrace",
    "RcmTransition",
    "AppUser",
    
    # Workflow Models (V8)
    "UserWorkflow",
    "UserWorkflowNode",
    "UserWorkflowTransition",
    "WorkflowRevision",
    "MicroState",
    
    # Schema enums
    "OrgTypeSchema",
    "EndpointKindSchema",
    "TaskDomainSchema",
    "TaskActionSchema",
    "TaskSignatureSourceSchema",
    "JobStatusSchema",
    "UserRoleSchema",
    
    # Organization schemas
    "OrganizationBase",
    "OrganizationCreate",
    "OrganizationUpdate",
    "OrganizationSchema",
    
    # Portal Type schemas
    "PortalTypeBase",
    "PortalTypeCreate",
    "PortalTypeUpdate",
    "PortalTypeSchema",
    
    # Integration Endpoint schemas
    "IntegrationEndpointBase",
    "IntegrationEndpointCreate",
    "IntegrationEndpointUpdate",
    "IntegrationEndpointSchema",
    
    # Task Type schemas
    "TaskTypeBase",
    "TaskTypeCreate",
    "TaskTypeUpdate",
    "TaskTypeSchema",
    
    # Field Requirement schemas
    "FieldRequirementBase",
    "FieldRequirementCreate",
    "FieldRequirementUpdate",
    "FieldRequirementSchema",
    
    # Batch Job schemas
    "BatchJobBase",
    "BatchJobCreate",
    "BatchJobUpdate",
    "BatchJobSchema",
    
    # Batch Row schemas
    "BatchRowBase",
    "BatchRowCreate",
    "BatchRowUpdate",
    "BatchRowSchema",
    
    # RCM State schemas
    "RcmStateBase",
    "RcmStateCreate",
    "RcmStateUpdate",
    "RcmStateSchema",
    
    # Macro State schemas
    "MacroStateBase",
    "MacroStateCreate",
    "MacroStateUpdate",
    "MacroStateSchema",
    
    # Task Signature schemas
    "TaskSignatureBase",
    "TaskSignatureCreate",
    "TaskSignatureUpdate",
    "TaskSignatureSchema",
    
    # RCM Trace schemas
    "RcmTraceBase",
    "RcmTraceCreate",
    "RcmTraceUpdate",
    "RcmTraceSchema",
    
    # RCM Transition schemas
    "RcmTransitionBase",
    "RcmTransitionCreate",
    "RcmTransitionUpdate",
    "RcmTransitionSchema",
    
    # App User schemas
    "AppUserBase",
    "AppUserCreate",
    "AppUserUpdate",
    "AppUserSchema",
    
    # Utility schemas
    "PaginationParams",
    "PaginatedResponse",
    "Vector",
    
    # Database utilities
    "DatabaseManager",
    "get_db_manager",
    "get_session",
    
    # Security utilities
    "SecurityContext",
    "require_org_context",
    "OrgFilterMixin",
    "AuditMixin",
    "check_org_access",
    "validate_uuid",
    "sanitize_org_id",
    "extract_org_from_jwt",
    
    # Version requirements
    "DATABASE_REQUIREMENTS",
    "VERSION_COMPATIBILITY",
    "EXTENSION_VERSIONS",
    
    # Validation utilities
    "validate_postgresql_version_async",
    "validate_postgresql_version_sync",
    "validate_extensions_async",
    "validate_extensions_sync",
    "validate_database_compatibility_async",
    "validate_database_compatibility_sync",
]

__version__ = "0.1.0"