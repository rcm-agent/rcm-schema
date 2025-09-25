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

# Import ORM modules explicitly so we can reconcile legacy and V8 schemas.
try:  # New V8 schema (graph workflows, vector embeddings)
    from . import models as _models_v8
except ImportError:  # pragma: no cover - defensive guard if module renamed
    _models_v8 = None

try:  # Legacy schema still referenced by downstream services
    from . import models_backup as _models_legacy
except ImportError:  # pragma: no cover - should never happen in published package
    _models_legacy = None


def _get_model(name: str, *, prefer: str = "legacy"):
    """Locate a model class by name, preferring the requested schema set."""

    sources = []
    if prefer == "v8":
        sources = [_models_v8, _models_legacy]
    else:
        sources = [_models_legacy, _models_v8]

    for module in sources:
        if module is None:
            continue
        if hasattr(module, name):
            return getattr(module, name)

    raise AttributeError(f"rcm_schema: model '{name}' not found in legacy or V8 modules")


# Expose declarative base classes so consumers can select the appropriate one.
LegacyBase = _get_model("Base", prefer="legacy") if _models_legacy else None
V8Base = _get_model("Base", prefer="v8") if _models_v8 else None

# Default Base remains the legacy version for compatibility with existing
# services that still operate on portal/state tables.
Base = LegacyBase or V8Base

# Core legacy models (portal + automation state)
Organization = _get_model("Organization", prefer="legacy")
PortalType = _get_model("PortalType", prefer="legacy")
IntegrationEndpoint = _get_model("IntegrationEndpoint", prefer="legacy")
TaskType = _get_model("TaskType", prefer="legacy")
FieldRequirement = _get_model("FieldRequirement", prefer="legacy")
BatchJob = _get_model("BatchJob", prefer="legacy")
BatchRow = _get_model("BatchRow", prefer="legacy")
TaskSignature = _get_model("TaskSignature", prefer="legacy")
RcmState = _get_model("RcmState", prefer="legacy")
MacroState = _get_model("MacroState", prefer="legacy")
RcmTrace = _get_model("RcmTrace", prefer="legacy")
RcmTransition = _get_model("RcmTransition", prefer="legacy")
AppUser = _get_model("AppUser", prefer="legacy")
RequirementChangelog = _get_model("RequirementChangelog", prefer="legacy")
OrgRequirementPolicy = _get_model("OrgRequirementPolicy", prefer="legacy")
PayerRequirement = _get_model("PayerRequirement", prefer="legacy")

# V8 workflow models (graph-based workflows, microstates)
UserWorkflow = _get_model("UserWorkflow", prefer="v8")
UserWorkflowNode = _get_model("UserWorkflowNode", prefer="v8")
UserWorkflowTransition = _get_model("UserWorkflowTransition", prefer="v8")
WorkflowRevision = _get_model("WorkflowRevision", prefer="v8")
MicroState = _get_model("MicroState", prefer="v8")

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
    "LegacyBase",
    "V8Base",
    
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
    "RequirementChangelog",
    "OrgRequirementPolicy",
    "PayerRequirement",
    
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
