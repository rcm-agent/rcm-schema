"""SQLAlchemy ORM models for RCM database schema v3.

This module defines all database tables, relationships, and constraints for the 
Hybrid RCM platform's shared database.
"""

from typing import Optional
from datetime import datetime
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import (
    Column, String, Integer, Float, Boolean, Text, DateTime, Date,
    ForeignKey, UniqueConstraint, CheckConstraint, Index,
    DECIMAL, UUID, JSON, Enum as SQLEnum, text, func
)
from sqlalchemy.orm import declarative_base, relationship, declared_attr
from sqlalchemy.dialects.postgresql import UUID as PostgreUUID, JSONB
from pgvector.sqlalchemy import Vector

# Create base class for all models
Base = declarative_base()

# Custom ENUM types
class OrgType(str, SQLEnum):
    """Organization types."""
    def __init__(self):
        super().__init__('hospital', 'billing_firm', 'credentialer', name='org_type')

class EndpointKind(str, SQLEnum):
    """Endpoint types."""
    def __init__(self):
        super().__init__('payer', 'provider', name='endpoint_kind')

class TaskDomain(str, SQLEnum):
    """Task domains for BPO processes."""
    def __init__(self):
        super().__init__(
            # Core BPO domains
            'eligibility',       # Insurance verification
            'claim',            # Claims processing
            'prior_auth',       # Prior authorization
            # Extended BPO domains
            'credentialing',    # Provider enrollment
            'coding',           # Medical coding
            'charge_capture',   # Charge entry
            'denial_mgmt',      # Denial management
            'payment_posting',  # Payment processing
            'ar_followup',      # Accounts receivable
            'patient_access',   # Registration/demographics
            name='task_domain'
        )

class TaskAction(str, SQLEnum):
    """Task actions - Industry-standard RCM terminology."""
    def __init__(self):
        super().__init__(
            'verify',           # HIPAA X12 270/271 - Eligibility verification
            'inquire',          # HIPAA X12 276/277 - Claim status inquiry  
            'submit',           # Submit prior auth or claim
            'request',          # Request prior authorization
            'denial_follow_up', # Follow up on denials
            'status_check',     # DEPRECATED - kept for backward compatibility
            name='task_action'
        )

class TaskSignatureSource(str, SQLEnum):
    """Task signature sources."""
    def __init__(self):
        super().__init__('human', 'ai', name='task_signature_source')

class JobStatus(str, SQLEnum):
    """Job/row status."""
    def __init__(self):
        super().__init__('queued', 'processing', 'success', 'error', name='job_status')

class UserRole(str, SQLEnum):
    """User roles."""
    def __init__(self):
        super().__init__('org_admin', 'firm_user', 'hospital_user', 'sys_admin', name='user_role')

# Mixins for common patterns
class TimestampMixin:
    """Mixin for created_at and updated_at timestamps."""
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

class OrgContextMixin:
    """Mixin for org_id foreign key."""
    @declared_attr
    def org_id(cls):
        return Column(PostgreUUID(as_uuid=True), ForeignKey('organization.org_id', ondelete='CASCADE'), nullable=False)

# Core reference tables
class Organization(Base):
    """Organizations (tenants) table."""
    __tablename__ = 'organization'
    
    org_id = Column(PostgreUUID(as_uuid=True), primary_key=True, default=uuid4)
    org_type = Column(SQLEnum('hospital', 'billing_firm', 'credentialer', name='org_type'), nullable=False)
    name = Column(Text, nullable=False, unique=True)
    email_domain = Column(Text, unique=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    endpoints = relationship('IntegrationEndpoint', back_populates='organization', cascade='all, delete-orphan')
    batch_jobs = relationship('BatchJob', back_populates='organization', cascade='all, delete-orphan')
    user_associations = relationship('UserOrganization', back_populates='organization', cascade='all, delete-orphan')
    traces = relationship('RcmTrace', back_populates='organization', cascade='all, delete-orphan')

class PortalType(Base):
    """Portal type catalog table."""
    __tablename__ = 'portal_type'
    
    portal_type_id = Column(Integer, primary_key=True, autoincrement=True)
    code = Column(Text, unique=True)
    name = Column(Text, nullable=False)
    base_url = Column(Text, nullable=False)
    endpoint_kind = Column(SQLEnum('payer', 'provider', name='endpoint_kind'), nullable=False)
    
    # Relationships
    endpoints = relationship('IntegrationEndpoint', back_populates='portal_type')
    task_signatures = relationship('TaskSignature', back_populates='portal_type')

class IntegrationEndpoint(Base, OrgContextMixin):
    """Integration endpoints (tenant-specific portal configurations)."""
    __tablename__ = 'integration_endpoint'
    
    portal_id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(Text, nullable=False)
    portal_type_id = Column(Integer, ForeignKey('portal_type.portal_type_id'), nullable=False)
    base_url = Column(Text)
    config = Column(JSONB, default=dict, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Credential storage fields - following AWS best practices
    secret_arn = Column(Text, nullable=True)  # AWS SSM Parameter Store or Secrets Manager ARN
    last_rotated_at = Column(DateTime(timezone=True), nullable=True)
    rotation_status = Column(Text, nullable=True)  # 'active', 'failed', 'pending'
    
    # Relationships
    organization = relationship('Organization', back_populates='endpoints')
    portal_type = relationship('PortalType', back_populates='endpoints')
    batch_jobs = relationship('BatchJob', back_populates='portal')
    states = relationship('RcmState', back_populates='portal', cascade='all, delete-orphan')
    macro_states = relationship('MacroState', back_populates='portal', cascade='all, delete-orphan')
    task_signatures = relationship('TaskSignature', back_populates='portal')
    traces = relationship('RcmTrace', back_populates='portal', cascade='all, delete-orphan')
    field_requirements = relationship('FieldRequirement', back_populates='portal')
    
    __table_args__ = (
        UniqueConstraint('org_id', 'name'),
        UniqueConstraint('org_id', 'portal_type_id'),
        CheckConstraint(
            "secret_arn IS NULL OR (secret_arn LIKE 'arn:aws:ssm:%' OR secret_arn LIKE 'arn:aws:secretsmanager:%')",
            name='check_secret_arn_format'
        ),
        CheckConstraint(
            "rotation_status IS NULL OR rotation_status IN ('active', 'failed', 'pending')",
            name='check_rotation_status'
        ),
        Index('idx_integration_endpoint_secret_arn', 'secret_arn', postgresql_where=text('secret_arn IS NOT NULL')),
        Index('idx_integration_endpoint_rotation_status', 'rotation_status', postgresql_where=text('rotation_status IS NOT NULL')),
    )

# Task definition tables
class TaskType(Base):
    """Task type definitions (workflow templates)."""
    __tablename__ = 'task_type'
    
    task_type_id = Column(PostgreUUID(as_uuid=True), primary_key=True, default=uuid4)
    domain = Column(SQLEnum('eligibility', 'claim', 'prior_auth', name='task_domain'), nullable=False)
    action = Column(SQLEnum('status_check', 'submit', 'denial_follow_up', name='task_action'), nullable=False)
    display_name = Column(Text, nullable=False)
    description = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    field_requirements = relationship('FieldRequirement', back_populates='task_type')

class FieldRequirement(Base, TimestampMixin):
    """Dynamic field requirements for task types."""
    __tablename__ = 'field_requirement'
    
    requirement_id = Column(PostgreUUID(as_uuid=True), primary_key=True, default=uuid4)
    task_type_id = Column(PostgreUUID(as_uuid=True), ForeignKey('task_type.task_type_id'), nullable=False)
    portal_id = Column(Integer, ForeignKey('integration_endpoint.portal_id'))  # NULL = global
    required_fields = Column(JSONB, nullable=False, default=list)
    optional_fields = Column(JSONB, nullable=False, default=list)
    field_metadata = Column(JSONB, nullable=False, default=dict)
    version = Column(Integer, nullable=False, default=1)
    active = Column(Boolean, nullable=False, default=True)
    
    # Relationships
    task_type = relationship('TaskType', back_populates='field_requirements')
    portal = relationship('IntegrationEndpoint', back_populates='field_requirements')

# Batch processing tables
class BatchJob(Base, OrgContextMixin):
    """Batch job tracking."""
    __tablename__ = 'batch_job'
    
    batch_id = Column(PostgreUUID(as_uuid=True), primary_key=True, default=uuid4)
    portal_id = Column(Integer, ForeignKey('integration_endpoint.portal_id', ondelete='CASCADE'), nullable=False)
    task_type_id = Column(PostgreUUID(as_uuid=True), ForeignKey('task_type.task_type_id'), nullable=False)
    status = Column(SQLEnum('queued', 'processing', 'success', 'error', name='job_status'), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    completed_at = Column(DateTime(timezone=True))
    result_url = Column(Text)
    
    # Relationships
    organization = relationship('Organization', back_populates='batch_jobs')
    portal = relationship('IntegrationEndpoint', back_populates='batch_jobs')
    rows = relationship('BatchRow', back_populates='batch', cascade='all, delete-orphan')
    task_type = relationship('TaskType')
    
    __table_args__ = (
        Index('idx_batch_status', 'status'),
    )

class BatchRow(Base, TimestampMixin):
    """Individual rows in a batch job."""
    __tablename__ = 'batch_row'
    
    row_id = Column(PostgreUUID(as_uuid=True), primary_key=True, default=uuid4)
    batch_id = Column(PostgreUUID(as_uuid=True), ForeignKey('batch_job.batch_id', ondelete='CASCADE'), nullable=False)
    row_idx = Column(Integer, nullable=False)
    task_signature = Column(PostgreUUID(as_uuid=True))  # Can be SHA or FK
    trace_id = Column(PostgreUUID(as_uuid=True), ForeignKey('rcm_trace.trace_id'))
    status = Column(SQLEnum('queued', 'processing', 'success', 'error', name='job_status'), nullable=False)
    error_code = Column(Text)
    error_msg = Column(Text)
    
    # Relationships
    batch = relationship('BatchJob', back_populates='rows')
    trace = relationship('RcmTrace')
    
    __table_args__ = (
        Index('idx_batch_row_batch', 'batch_id'),
        Index('idx_batch_row_status', 'status'),
    )

# Web-agent state memory tables
class RcmState(Base):
    """Page state memory with embeddings."""
    __tablename__ = 'rcm_state'
    
    state_id = Column(PostgreUUID(as_uuid=True), primary_key=True, default=uuid4)
    portal_id = Column(Integer, ForeignKey('integration_endpoint.portal_id', ondelete='CASCADE'), nullable=False)
    text_emb = Column(Vector(768), nullable=False)  # BGE text embedding
    image_emb = Column(Vector(512), nullable=False)  # SigLIP image embedding
    semantic_spec = Column(JSONB, nullable=False)
    action = Column(JSONB, nullable=False)
    success_ema = Column(Float, nullable=False, default=1.0)
    page_caption = Column(Text)
    action_caption = Column(Text)
    caption_conf = Column(DECIMAL(3, 2))
    macro_state_id = Column(PostgreUUID(as_uuid=True), ForeignKey('macro_state.macro_state_id'))
    is_retired = Column(Boolean, nullable=False, default=False)
    alias_state_id = Column(PostgreUUID(as_uuid=True), ForeignKey('rcm_state.state_id'))
    
    # Relationships
    portal = relationship('IntegrationEndpoint', back_populates='states')
    macro_state = relationship('MacroState', back_populates='states')
    alias_state = relationship('RcmState', remote_side=[state_id])
    from_transitions = relationship('RcmTransition', foreign_keys='RcmTransition.from_state', back_populates='from_state_obj', cascade='all, delete-orphan')
    to_transitions = relationship('RcmTransition', foreign_keys='RcmTransition.to_state', back_populates='to_state_obj', cascade='all, delete-orphan')

class MacroState(Base):
    """State clustering/grouping."""
    __tablename__ = 'macro_state'
    
    macro_state_id = Column(PostgreUUID(as_uuid=True), primary_key=True, default=uuid4)
    portal_id = Column(Integer, ForeignKey('integration_endpoint.portal_id', ondelete='CASCADE'))
    canonical_caption = Column(Text)
    description = Column(Text)
    sample_state_id = Column(PostgreUUID(as_uuid=True), ForeignKey('rcm_state.state_id'))
    
    # Relationships
    portal = relationship('IntegrationEndpoint', back_populates='macro_states')
    sample_state = relationship('RcmState', foreign_keys=[sample_state_id], post_update=True)
    states = relationship('RcmState', foreign_keys='RcmState.macro_state_id', back_populates='macro_state')

# Task execution tables
class TaskSignature(Base, TimestampMixin):
    """Task signatures (workflow execution patterns)."""
    __tablename__ = 'task_signature'
    
    signature_id = Column(PostgreUUID(as_uuid=True), primary_key=True, default=uuid4)
    portal_id = Column(Integer, ForeignKey('integration_endpoint.portal_id'))
    portal_type_id = Column(Integer, ForeignKey('portal_type.portal_type_id'))
    domain = Column(SQLEnum('eligibility', 'claim', 'prior_auth', name='task_domain'), nullable=False)
    action = Column(SQLEnum('status_check', 'submit', 'denial_follow_up', name='task_action'), nullable=False)
    source = Column(SQLEnum('human', 'ai', name='task_signature_source'), nullable=False)
    text_emb = Column(Vector(768))
    image_emb = Column(Vector(512))
    sample_trace_id = Column(PostgreUUID(as_uuid=True))
    alias_of = Column(PostgreUUID(as_uuid=True), ForeignKey('task_signature.signature_id'))
    composed = Column(Boolean, default=False)
    
    # Relationships
    portal = relationship('IntegrationEndpoint', back_populates='task_signatures')
    portal_type = relationship('PortalType', back_populates='task_signatures')
    alias_signature = relationship('TaskSignature', remote_side=[signature_id])
    traces = relationship('RcmTrace', back_populates='signature')
    
    __table_args__ = (
        CheckConstraint(
            "(portal_id IS NOT NULL)::int + (portal_type_id IS NOT NULL)::int = 1",
            name="task_signature_xor_check"
        ),
        UniqueConstraint('portal_id', 'domain', 'action', 
                         postgresql_where=text('portal_id IS NOT NULL')),
        UniqueConstraint('portal_type_id', 'domain', 'action',
                         postgresql_where=text('portal_type_id IS NOT NULL')),
    )

class RcmTrace(Base, OrgContextMixin):
    """Execution trace logs."""
    __tablename__ = 'rcm_trace'
    
    trace_id = Column(PostgreUUID(as_uuid=True), primary_key=True, default=uuid4)
    portal_id = Column(Integer, ForeignKey('integration_endpoint.portal_id', ondelete='CASCADE'), nullable=False)
    # workflow_type removed - access via batch_job.task_type relationship
    task_signature = Column(PostgreUUID(as_uuid=True), ForeignKey('task_signature.signature_id'))
    prompt_version = Column(String(20))
    used_fallback = Column(Boolean, default=False)
    fallback_model = Column(Text)
    trace = Column(JSONB, nullable=False)
    duration_ms = Column(Integer)
    success = Column(Boolean)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    organization = relationship('Organization', back_populates='traces')
    portal = relationship('IntegrationEndpoint', back_populates='traces')
    signature = relationship('TaskSignature', back_populates='traces')
    batch_rows = relationship('BatchRow', back_populates='trace')

class RcmTransition(Base):
    """State transition graph."""
    __tablename__ = 'rcm_transition'
    
    from_state = Column(PostgreUUID(as_uuid=True), ForeignKey('rcm_state.state_id', ondelete='CASCADE'), primary_key=True)
    to_state = Column(PostgreUUID(as_uuid=True), ForeignKey('rcm_state.state_id', ondelete='CASCADE'), primary_key=True)
    action_caption = Column(Text, primary_key=True)
    freq = Column(Integer, nullable=False, default=1)
    
    # Relationships
    from_state_obj = relationship('RcmState', foreign_keys=[from_state], back_populates='from_transitions')
    to_state_obj = relationship('RcmState', foreign_keys=[to_state], back_populates='to_transitions')
    
    __table_args__ = (
        CheckConstraint('freq >= 1', name='rcm_transition_freq_check'),
    )

# User management
class AppUser(Base, TimestampMixin):
    """Application users."""
    __tablename__ = 'app_user'
    
    user_id = Column(PostgreUUID(as_uuid=True), primary_key=True)  # From Cognito
    email = Column(Text, nullable=False, unique=True)
    full_name = Column(Text)
    role = Column(SQLEnum('org_admin', 'firm_user', 'hospital_user', 'sys_admin', name='user_role'), nullable=False)
    
    # Relationships
    organizations = relationship('UserOrganization', back_populates='user', cascade='all, delete-orphan')

class UserOrganization(Base, TimestampMixin):
    """Association table for many-to-many relationship between users and organizations."""
    __tablename__ = 'user_organization'
    
    user_id = Column(PostgreUUID(as_uuid=True), ForeignKey('app_user.user_id', ondelete='CASCADE'), primary_key=True)
    org_id = Column(PostgreUUID(as_uuid=True), ForeignKey('organization.org_id', ondelete='CASCADE'), primary_key=True)
    is_active = Column(Boolean, nullable=False, default=True)
    is_primary = Column(Boolean, nullable=False, default=False)
    joined_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    
    # Relationships
    user = relationship('AppUser', back_populates='organizations')
    organization = relationship('Organization', back_populates='user_associations')
    
    __table_args__ = (
        Index('idx_user_organization_user_id', 'user_id'),
        Index('idx_user_organization_org_id', 'org_id'),
        Index('idx_user_organization_active', 'is_active'),
        UniqueConstraint('user_id', 'is_primary', postgresql_where=text('is_primary = true'), 
                        name='uq_one_primary_org_per_user'),
    )

# Create indexes for vector similarity search
Index('idx_rcm_state_text_emb', RcmState.text_emb, postgresql_using='ivfflat', postgresql_ops={'text_emb': 'vector_l2_ops'})
Index('idx_rcm_state_image_emb', RcmState.image_emb, postgresql_using='ivfflat', postgresql_ops={'image_emb': 'vector_l2_ops'})
Index('idx_task_signature_text_emb', TaskSignature.text_emb, postgresql_using='ivfflat', postgresql_ops={'text_emb': 'vector_l2_ops'})
Index('idx_task_signature_image_emb', TaskSignature.image_emb, postgresql_using='ivfflat', postgresql_ops={'image_emb': 'vector_l2_ops'})

# Additional indexes for performance
Index('idx_rcm_trace_portal_created', RcmTrace.portal_id, RcmTrace.created_at.desc())
Index('idx_rcm_state_portal_active', RcmState.portal_id, RcmState.is_retired)

# Hierarchical Requirements System Models

class PayerRequirement(Base, TimestampMixin):
    """Payer-level requirements for task types."""
    __tablename__ = 'payer_requirement'
    
    requirement_id = Column(PostgreUUID(as_uuid=True), primary_key=True, default=uuid4)
    portal_type_id = Column(Integer, ForeignKey('portal_type.portal_type_id'), nullable=False)
    task_type_id = Column(PostgreUUID(as_uuid=True), ForeignKey('task_type.task_type_id'), nullable=False)
    version = Column(Integer, nullable=False, default=1)
    required_fields = Column(JSONB, nullable=False, default=list)
    optional_fields = Column(JSONB, nullable=False, default=list)
    field_rules = Column(JSONB, nullable=False, default=dict)
    compliance_ref = Column(Text)
    effective_date = Column(Date, nullable=False)
    created_by = Column(PostgreUUID(as_uuid=True), ForeignKey('app_user.user_id'))
    
    # Relationships
    portal_type = relationship('PortalType')
    task_type = relationship('TaskType')
    created_by_user = relationship('AppUser', foreign_keys=[created_by])
    
    __table_args__ = (
        UniqueConstraint('portal_type_id', 'task_type_id', 'version', 
                        name='uq_payer_requirement_portal_task_version'),
        Index('idx_payer_requirement_portal_task', 'portal_type_id', 'task_type_id'),
        Index('idx_payer_requirement_effective_date', 'effective_date'),
    )

class OrgRequirementPolicy(Base, TimestampMixin):
    """Organization-specific requirement policies."""
    __tablename__ = 'org_requirement_policy'
    
    policy_id = Column(PostgreUUID(as_uuid=True), primary_key=True, default=uuid4)
    org_id = Column(PostgreUUID(as_uuid=True), ForeignKey('organization.org_id'), nullable=False)
    task_type_id = Column(PostgreUUID(as_uuid=True), ForeignKey('task_type.task_type_id'), nullable=False)
    portal_type_id = Column(Integer, ForeignKey('portal_type.portal_type_id'))
    policy_type = Column(Text, nullable=False)  # 'add', 'remove', 'override'
    field_changes = Column(JSONB, nullable=False)
    reason = Column(Text)
    version = Column(Integer, nullable=False, default=1)
    active = Column(Boolean, nullable=False, default=True)
    created_by = Column(PostgreUUID(as_uuid=True), ForeignKey('app_user.user_id'))
    approved_by = Column(PostgreUUID(as_uuid=True), ForeignKey('app_user.user_id'))
    approved_at = Column(DateTime(timezone=True))
    
    # Relationships
    organization = relationship('Organization')
    task_type = relationship('TaskType')
    portal_type = relationship('PortalType')
    created_by_user = relationship('AppUser', foreign_keys=[created_by])
    approved_by_user = relationship('AppUser', foreign_keys=[approved_by])
    
    __table_args__ = (
        CheckConstraint("policy_type IN ('add', 'remove', 'override')", 
                       name='chk_policy_type'),
        Index('idx_org_policy_org_task', 'org_id', 'task_type_id'),
        Index('idx_org_policy_active', 'active'),
    )

class RequirementChangelog(Base):
    """Audit trail for requirement changes."""
    __tablename__ = 'requirement_changelog'
    
    log_id = Column(PostgreUUID(as_uuid=True), primary_key=True, default=uuid4)
    source_table = Column(Text, nullable=False)
    source_id = Column(PostgreUUID(as_uuid=True), nullable=False)
    change_type = Column(Text, nullable=False)
    previous_value = Column(JSONB)
    new_value = Column(JSONB)
    changed_by = Column(PostgreUUID(as_uuid=True), ForeignKey('app_user.user_id'))
    changed_at = Column(DateTime(timezone=True), server_default=func.now())
    ip_address = Column(Text)
    user_agent = Column(Text)
    
    # Relationships
    changed_by_user = relationship('AppUser')
    
    __table_args__ = (
        Index('idx_changelog_source', 'source_table', 'source_id'),
        Index('idx_changelog_changed_at', 'changed_at'),
    )

# Credential Management Tables

class CredentialAccessLog(Base):
    """Audit log for credential access operations.
    
    Tracks all credential retrievals, updates, and rotations for compliance 
    and security monitoring. Part of the credential storage security system.
    """
    __tablename__ = 'credential_access_log'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    access_timestamp = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    portal_id = Column(Text, nullable=False)  # Using Text to match SQL migration
    secret_arn = Column(Text, nullable=True)
    access_type = Column(Text, nullable=False)  # 'retrieve', 'store', 'rotate', 'delete'
    access_by = Column(Text, nullable=True)  # User or service that accessed
    ip_address = Column(Text, nullable=True)  # Using Text for INET compatibility
    user_agent = Column(Text, nullable=True)
    success = Column(Boolean, nullable=False, default=True)
    error_message = Column(Text, nullable=True)
    metadata = Column(JSONB, nullable=True)  # Additional context
    
    __table_args__ = (
        CheckConstraint(
            "access_type IN ('retrieve', 'store', 'rotate', 'delete')",
            name='check_access_type'
        ),
        Index('idx_credential_access_log_portal_id', 'portal_id'),
        Index('idx_credential_access_log_timestamp', 'access_timestamp'),
        Index('idx_credential_access_log_access_type', 'access_type'),
    )

class CredentialRotationSchedule(Base, TimestampMixin):
    """Manages credential rotation schedules for each portal.
    
    Supports automated rotation and notification policies. Ensures credentials
    are rotated regularly for security compliance.
    """
    __tablename__ = 'credential_rotation_schedule'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    portal_id = Column(Text, nullable=False, unique=True)  # Using Text to match SQL
    secret_arn = Column(Text, nullable=True)
    last_rotation = Column(DateTime(timezone=True), nullable=True)
    next_rotation = Column(DateTime(timezone=True), nullable=True)
    rotation_interval_days = Column(Integer, nullable=False, default=90)
    auto_rotate = Column(Boolean, nullable=False, default=False)
    notification_email = Column(Text, nullable=True)
    
    # Note: created_at and updated_at are provided by TimestampMixin
    
    __table_args__ = (
        Index('idx_rotation_schedule_portal_id', 'portal_id'),
        Index('idx_rotation_schedule_next_rotation', 'next_rotation'),
        CheckConstraint(
            'rotation_interval_days > 0',
            name='check_rotation_interval_positive'
        ),
    )