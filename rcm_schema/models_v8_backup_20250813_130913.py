"""
SQLAlchemy models for V8 RCM Schema
Supports multi-tenancy, graph workflows, and vector embeddings
"""
from datetime import datetime
from typing import Optional, List
import uuid
from uuid import uuid4
from sqlalchemy import (
    Column, String, DateTime, Boolean, Integer, BigInteger, SmallInteger,
    ForeignKey, Text, Numeric, CheckConstraint, UniqueConstraint, 
    Identity, Computed, text, func, Index
)
from sqlalchemy.dialects.postgresql import UUID, JSONB, VECTOR
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, backref
from sqlalchemy.ext.hybrid import hybrid_property

Base = declarative_base()


# ============================================================================
# Mixins
# ============================================================================

class TimestampMixin:
    """Mixin for created_at and updated_at timestamps"""
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())


class OrgMixin:
    """Mixin for multi-tenant organization support"""
    @classmethod
    def org_id(cls):
        return Column(UUID(as_uuid=True), ForeignKey('organization.org_id', ondelete='CASCADE'), nullable=False, index=True)


# ============================================================================
# Lookup Tables (replacing ENUMs)
# ============================================================================

class TaskDomainLu(Base):
    __tablename__ = 'task_domain_lu'
    domain = Column(Text, primary_key=True)


class TaskActionLu(Base):
    __tablename__ = 'task_action_lu'
    action = Column(Text, primary_key=True)


class TaskSignatureSourceLu(Base):
    __tablename__ = 'task_signature_source_lu'
    source = Column(Text, primary_key=True)


class JobStatusLu(Base):
    __tablename__ = 'job_status_lu'
    status = Column(Text, primary_key=True)


class RequirementTypeLu(Base):
    __tablename__ = 'requirement_type_lu'
    rtype = Column(Text, primary_key=True)


class UserRoleLu(Base):
    __tablename__ = 'user_role_lu'
    role = Column(Text, primary_key=True)


# ============================================================================
# Core Tables
# ============================================================================

class Organization(Base):
    """Multi-tenant organization"""
    __tablename__ = 'organization'
    
    org_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_type = Column(Text, nullable=False)
    name = Column(Text, nullable=False, unique=True)
    email_domain = Column(Text, unique=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    
    # Relationships
    users = relationship('AppUser', back_populates='organization', cascade='all, delete-orphan')
    endpoints = relationship('Endpoint', back_populates='organization', cascade='all, delete-orphan')
    
    __table_args__ = (
        CheckConstraint("org_type IN ('hospital','billing_firm','credentialer')", name='ck_org_type'),
    )


class ChannelType(Base):
    """Communication channel types (web, phone, fax, etc.)"""
    __tablename__ = 'channel_type'
    
    channel_type_id = Column(BigInteger, Identity(always=False), primary_key=True)
    code = Column(Text, unique=True)
    name = Column(Text, nullable=False)
    base_url = Column(Text)
    endpoint_kind = Column(Text, nullable=False)
    access_medium = Column(Text, nullable=False)
    
    # Relationships
    endpoints = relationship('Endpoint', back_populates='channel_type')
    
    __table_args__ = (
        CheckConstraint("endpoint_kind IN ('payer','provider','clearinghouse')", name='ck_endpoint_kind'),
        CheckConstraint("access_medium IN ('web','phone','fax','efax','edi')", name='ck_access_medium'),
    )


class Endpoint(Base):
    """Organization-specific endpoints"""
    __tablename__ = 'endpoint'
    
    endpoint_id = Column(BigInteger, Identity(always=False), primary_key=True)
    org_id = Column(UUID(as_uuid=True), ForeignKey('organization.org_id', ondelete='CASCADE'), nullable=False, index=True)
    name = Column(Text, nullable=False)
    channel_type_id = Column(BigInteger, ForeignKey('channel_type.channel_type_id'), nullable=False)
    base_url = Column(Text)
    config = Column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    
    # Relationships
    organization = relationship('Organization', back_populates='endpoints')
    channel_type = relationship('ChannelType', back_populates='endpoints')
    credentials = relationship('PortalCredential', back_populates='endpoint', cascade='all, delete-orphan')
    
    __table_args__ = (
        UniqueConstraint('org_id', 'name'),
        UniqueConstraint('org_id', 'channel_type_id'),
    )


class PortalCredential(Base, TimestampMixin):
    """Credentials for accessing portals/endpoints"""
    __tablename__ = 'portal_credential'
    
    credential_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    endpoint_id = Column(BigInteger, ForeignKey('endpoint.endpoint_id', ondelete='CASCADE'), nullable=False)
    account_id = Column(Text, nullable=False)
    
    # AWS SSM Integration
    password_ssm_parameter_name = Column(String(512))
    password_ssm_key_id = Column(String(256))
    secret_arn = Column(String(512))
    secret_version_id = Column(String(64))
    
    # Local encrypted storage
    encrypted_password = Column(Text)  # BYTEA in PostgreSQL
    encryption_key_id = Column(String(256))
    
    # Session management
    session_token = Column(Text)
    token_expires_at = Column(DateTime(timezone=True))
    
    # OAuth tokens
    access_token_ssm_parameter_name = Column(String(512))
    refresh_token_ssm_parameter_name = Column(String(512))
    oauth_expires_at = Column(DateTime(timezone=True))
    
    # Status
    is_active = Column(Boolean, nullable=False, default=True)
    last_used_at = Column(DateTime(timezone=True))
    expires_at = Column(DateTime(timezone=True))
    
    # Audit
    created_by = Column(UUID(as_uuid=True))
    updated_by = Column(UUID(as_uuid=True))
    
    # Relationships
    endpoint = relationship('Endpoint', back_populates='credentials')
    
    __table_args__ = (
        UniqueConstraint('endpoint_id', 'account_id', name='unique_endpoint_account'),
        CheckConstraint(
            'password_ssm_parameter_name IS NOT NULL OR secret_arn IS NOT NULL OR encrypted_password IS NOT NULL',
            name='ck_cred_storage'
        ),
    )


class AppUser(Base, TimestampMixin):
    """Application users (renamed from rcm_user)"""
    __tablename__ = 'app_user'
    
    user_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id = Column(UUID(as_uuid=True), ForeignKey('organization.org_id', ondelete='CASCADE'), index=True)
    email = Column(Text, nullable=False, unique=True)
    full_name = Column(Text)
    role = Column(Text, ForeignKey('user_role_lu.role'), nullable=False)
    is_active = Column(Boolean, nullable=False, default=True)
    api_key_ssm_parameter_name = Column(String(512))
    last_login_at = Column(DateTime(timezone=True))
    
    # Relationships
    organization = relationship('Organization', back_populates='users')
    batch_jobs = relationship('BatchJob', back_populates='user')
    
    def has_role(self, role: str) -> bool:
        """Check if user has a specific role"""
        return self.role == role
    
    def can_access_org(self, org_id: uuid.UUID) -> bool:
        """Check if user can access an organization"""
        return self.org_id == org_id or self.role in ['sys_admin']


class TaskType(Base, TimestampMixin):
    """Task type catalog"""
    __tablename__ = 'task_type'
    
    task_type_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    domain = Column(Text, ForeignKey('task_domain_lu.domain'), nullable=False)
    action = Column(Text, ForeignKey('task_action_lu.action'), nullable=False)
    name = Column(Text, nullable=False, unique=True)
    description = Column(Text)
    version = Column(Integer, nullable=False, default=1)
    is_active = Column(Boolean, nullable=False, default=True)
    
    # Relationships
    field_requirements = relationship('FieldRequirement', back_populates='task_type', cascade='all, delete-orphan')
    batch_jobs = relationship('BatchJob', back_populates='task_type')
    
    __table_args__ = (
        UniqueConstraint('domain', 'action'),
    )


class FieldRequirement(Base, TimestampMixin):
    """Hierarchical field requirements"""
    __tablename__ = 'field_requirement'
    
    field_req_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    task_type_id = Column(UUID(as_uuid=True), ForeignKey('task_type.task_type_id', ondelete='CASCADE'), nullable=False)
    parent_id = Column(UUID(as_uuid=True), ForeignKey('field_requirement.field_req_id', ondelete='CASCADE'))
    
    # Field definition
    field_name = Column(Text, nullable=False)
    field_type = Column(Text, nullable=False)
    requirement_type = Column(Text, ForeignKey('requirement_type_lu.rtype'), nullable=False)
    
    # Hierarchical path
    path = Column(Text, nullable=False)
    depth = Column(Integer, nullable=False, default=0)
    
    # Business rules
    business_logic = Column(JSONB, server_default=text("'{}'::jsonb"))
    validation_rules = Column(JSONB, server_default=text("'{}'::jsonb"))
    condition_expr = Column(Text)
    required_when = Column(JSONB)
    
    # UI configuration
    ui_config = Column(JSONB, server_default=text("'{}'::jsonb"))
    
    # Source tracking
    source = Column(Text, ForeignKey('task_signature_source_lu.source'), nullable=False)
    confidence_score = Column(Numeric(3, 2))
    portal_specific = Column(Boolean, nullable=False, default=False)
    
    # Relationships
    task_type = relationship('TaskType', back_populates='field_requirements')
    parent = relationship('FieldRequirement', remote_side=[field_req_id], backref='children')
    
    __table_args__ = (
        UniqueConstraint('task_type_id', 'path'),
        CheckConstraint('confidence_score IS NULL OR confidence_score BETWEEN 0 AND 1'),
    )


class WorkflowNode(Base):
    """Nodes in the workflow graph"""
    __tablename__ = 'workflow_node'
    
    node_id = Column(BigInteger, Identity(always=False), primary_key=True)
    code = Column(Text, unique=True)
    description = Column(Text)
    metadata = Column(JSONB, server_default=text("'{}'::jsonb"))
    label_conf = Column(Numeric(3, 2))
    last_label_at = Column(DateTime(timezone=True))
    
    # Relationships
    micro_states = relationship('MicroState', back_populates='node')
    
    # Graph relationships via association table
    successors = relationship(
        'WorkflowNode',
        secondary='workflow_transition',
        primaryjoin='WorkflowNode.node_id==WorkflowTransition.from_node',
        secondaryjoin='WorkflowNode.node_id==WorkflowTransition.to_node',
        backref=backref('predecessors', lazy='dynamic'),
        lazy='dynamic'
    )


class WorkflowTransition(Base):
    """Edges in the workflow graph"""
    __tablename__ = 'workflow_transition'
    
    from_node = Column(BigInteger, ForeignKey('workflow_node.node_id', ondelete='CASCADE'), primary_key=True)
    to_node = Column(BigInteger, ForeignKey('workflow_node.node_id', ondelete='CASCADE'), primary_key=True)
    action_label = Column(Text, primary_key=True, nullable=False)
    freq = Column(Integer, nullable=False, default=1)
    
    __table_args__ = (
        CheckConstraint('freq >= 1', name='ck_freq_positive'),
    )


class UserWorkflow(Base, TimestampMixin):
    """User-defined workflows"""
    __tablename__ = 'user_workflow'
    
    workflow_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(Text, nullable=False)
    description = Column(Text)
    required_data = Column(JSONB, server_default=text("'[]'::jsonb"))
    
    # Relationships
    micro_states = relationship('MicroState', back_populates='workflow', cascade='all, delete-orphan')
    channel_types = relationship('ChannelType', secondary='user_workflow_channel_type')
    task_types = relationship('TaskType', secondary='user_workflow_task_type')
    revisions = relationship('WorkflowRevision', back_populates='workflow', cascade='all, delete-orphan', order_by='WorkflowRevision.revision_num.desc()')


class WorkflowRevision(Base):
    """Versioned snapshots of workflow configurations"""
    __tablename__ = 'workflow_revision'
    
    revision_id = Column(BigInteger, Identity(always=False), primary_key=True)
    workflow_id = Column(UUID(as_uuid=True), ForeignKey('user_workflow.workflow_id', ondelete='CASCADE'), nullable=False)
    revision_num = Column(Integer, nullable=False)
    comment = Column(Text)
    created_by = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    snapshot = Column(JSONB, nullable=False)
    
    # Relationships
    workflow = relationship('UserWorkflow', back_populates='revisions')
    
    __table_args__ = (
        UniqueConstraint('workflow_id', 'revision_num', name='uq_workflow_revision'),
    )


class MicroState(Base):
    """UI state snapshots with vector embeddings"""
    __tablename__ = 'micro_state'
    
    micro_state_id = Column(BigInteger, Identity(always=False), primary_key=True)
    workflow_id = Column(UUID(as_uuid=True), ForeignKey('user_workflow.workflow_id', ondelete='CASCADE'), nullable=False)
    node_id = Column(BigInteger, ForeignKey('workflow_node.node_id'), nullable=False)
    
    # State data
    dom_snapshot = Column(Text, nullable=False)
    action_json = Column(JSONB, nullable=False)
    semantic_spec = Column(JSONB)
    label = Column(Text)
    category = Column(Text)
    required = Column(Boolean, default=False)
    
    # Dynamic state detection
    is_dynamic = Column(
        Boolean,
        Computed("((semantic_spec -> 'dynamic_meta') IS NOT NULL)", persisted=True)
    )
    
    # Vector embedding for similarity search
    text_emb = Column(VECTOR(768), nullable=False)
    mini_score = Column(Numeric(4, 3))
    
    # State management
    is_retired = Column(Boolean, nullable=False, default=False)
    aliased_to = Column(BigInteger, ForeignKey('micro_state.micro_state_id'))
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    
    # Relationships
    workflow = relationship('UserWorkflow', back_populates='micro_states')
    node = relationship('WorkflowNode', back_populates='micro_states')
    alias_target = relationship('MicroState', remote_side=[micro_state_id])


# ============================================================================
# Bridge Tables
# ============================================================================

class UserWorkflowChannelType(Base):
    """Many-to-many: workflows to channel types"""
    __tablename__ = 'user_workflow_channel_type'
    
    workflow_id = Column(UUID(as_uuid=True), ForeignKey('user_workflow.workflow_id', ondelete='CASCADE'), primary_key=True)
    channel_type_id = Column(BigInteger, ForeignKey('channel_type.channel_type_id', ondelete='CASCADE'), primary_key=True)
    timeout_ms = Column(Integer)
    priority = Column(SmallInteger)


class UserWorkflowTaskType(Base):
    """Many-to-many: workflows to task types"""
    __tablename__ = 'user_workflow_task_type'
    
    workflow_id = Column(UUID(as_uuid=True), ForeignKey('user_workflow.workflow_id', ondelete='CASCADE'), primary_key=True)
    task_type_id = Column(UUID(as_uuid=True), ForeignKey('task_type.task_type_id', ondelete='CASCADE'), primary_key=True)
    preferred = Column(Boolean, default=False)


# ============================================================================
# Batch Processing
# ============================================================================

class BatchJob(Base, TimestampMixin):
    """Batch job management"""
    __tablename__ = 'batch_job'
    
    batch_job_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey('app_user.user_id'), nullable=False)
    task_type_id = Column(UUID(as_uuid=True), ForeignKey('task_type.task_type_id'), nullable=False)
    
    # File storage
    file_path = Column(String(500), nullable=False)
    file_s3_bucket_param = Column(String(512))
    file_s3_key = Column(String(1024))
    
    # Status tracking
    status = Column(Text, ForeignKey('job_status_lu.status'), nullable=False, default='pending')
    total_items = Column(Integer, nullable=False, default=0)
    processed_items = Column(Integer, nullable=False, default=0)
    failed_items = Column(Integer, nullable=False, default=0)
    
    # Timing
    started_at = Column(DateTime(timezone=True))
    completed_at = Column(DateTime(timezone=True))
    error_summary = Column(JSONB)
    
    # Relationships
    user = relationship('AppUser', back_populates='batch_jobs')
    task_type = relationship('TaskType', back_populates='batch_jobs')
    items = relationship('BatchJobItem', back_populates='batch_job', cascade='all, delete-orphan')
    
    @hybrid_property
    def progress_percentage(self):
        """Calculate job progress percentage"""
        if self.total_items == 0:
            return 0
        return int((self.processed_items / self.total_items) * 100)
    
    @hybrid_property
    def is_complete(self):
        """Check if job is complete"""
        return self.status in ['completed', 'failed']


class BatchJobItem(Base, TimestampMixin):
    """Individual items in a batch job"""
    __tablename__ = 'batch_job_item'
    
    batch_job_item_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    batch_job_id = Column(UUID(as_uuid=True), ForeignKey('batch_job.batch_job_id', ondelete='CASCADE'), nullable=False)
    item_index = Column(Integer, nullable=False)
    
    # Data
    input_data = Column(JSONB, nullable=False)
    output_data = Column(JSONB)
    
    # Status
    status = Column(Text, ForeignKey('job_status_lu.status'), nullable=False, default='pending')
    error_message = Column(Text)
    attempts = Column(Integer, nullable=False, default=0)
    
    # Timing
    started_at = Column(DateTime(timezone=True))
    completed_at = Column(DateTime(timezone=True))
    
    # Relationships
    batch_job = relationship('BatchJob', back_populates='items')
    traces = relationship('WorkflowTrace', back_populates='batch_job_item')
    
    __table_args__ = (
        UniqueConstraint('batch_job_id', 'item_index'),
    )


# ============================================================================
# Workflow Execution Tracking
# ============================================================================

class WorkflowTrace(Base):
    """Execution trace/audit log (renamed from rcm_trace) - Enhanced for workflow runs"""
    __tablename__ = 'workflow_trace'
    
    trace_id = Column(BigInteger, Identity(always=False), primary_key=True)
    batch_job_item_id = Column(UUID(as_uuid=True), ForeignKey('batch_job_item.batch_job_item_id'))
    org_id = Column(UUID(as_uuid=True), ForeignKey('organization.org_id'), nullable=False, index=True)
    workflow_id = Column(UUID(as_uuid=True), ForeignKey('user_workflow.workflow_id'))
    
    # Action tracking
    action_type = Column(Text)
    action_detail = Column(JSONB)
    success = Column(Boolean, default=False)
    duration_ms = Column(Integer)
    error_detail = Column(JSONB)
    
    # LLM tracking
    llm_prompt = Column(Text)
    llm_response = Column(Text)
    llm_model = Column(String(100))
    llm_tokens_used = Column(Integer)
    
    # V9 Enhancement: Workflow run tracking fields
    status = Column(String(50), nullable=False, default='pending')  # pending, running, completed, failed, cancelled
    started_by = Column(UUID(as_uuid=True), ForeignKey('app_user.user_id'))
    completed_at = Column(DateTime(timezone=True))
    node_count = Column(Integer, default=0)
    completed_node_count = Column(Integer, default=0)
    execution_time_ms = Column(BigInteger)
    error_message = Column(Text)
    metadata = Column(JSONB, default=dict)
    
    # Relationships
    started_by_user = relationship('AppUser', foreign_keys=[started_by])
    screenshots = relationship('WorkflowTraceScreenshot', back_populates='trace', cascade='all, delete-orphan')
    
    # Tiering
    tier = Column(SmallInteger)
    tier_reason = Column(Text)
    
    # Metadata
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    user_id = Column(UUID(as_uuid=True), ForeignKey('app_user.user_id'))
    session_id = Column(UUID(as_uuid=True))
    
    # Relationships
    batch_job_item = relationship('BatchJobItem', back_populates='traces')
    endpoints = relationship('Endpoint', secondary='workflow_trace_endpoint')


class WorkflowTraceScreenshot(Base):
    """Screenshots captured during workflow execution"""
    __tablename__ = 'workflow_trace_screenshot'
    
    screenshot_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    trace_id = Column(BigInteger, ForeignKey('workflow_trace.trace_id', ondelete='CASCADE'), nullable=False)
    org_id = Column(UUID(as_uuid=True), ForeignKey('organization.org_id', ondelete='CASCADE'), nullable=False)
    node_id = Column(Integer, nullable=False)
    node_name = Column(String(255), nullable=False)
    step_index = Column(Integer, nullable=False)
    screenshot_url = Column(Text, nullable=False)
    thumbnail_url = Column(Text)
    action_description = Column(Text, nullable=False)
    element_selector = Column(Text)
    metadata = Column(JSONB, default=dict)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    
    # Relationships
    trace = relationship('WorkflowTrace', back_populates='screenshots')
    
    # Indexes
    __table_args__ = (
        Index('idx_trace_screenshots', 'trace_id', 'step_index'),
        Index('idx_screenshot_org', 'org_id'),
        Index('idx_screenshot_created', 'created_at'),
    )


class WorkflowTraceEndpoint(Base):
    """Bridge table: traces to endpoints (multi-endpoint support)"""
    __tablename__ = 'workflow_trace_endpoint'
    
    trace_id = Column(BigInteger, ForeignKey('workflow_trace.trace_id', ondelete='CASCADE'), primary_key=True)
    endpoint_id = Column(BigInteger, ForeignKey('endpoint.endpoint_id', ondelete='CASCADE'), primary_key=True)


# ============================================================================
# Helper Functions
# ============================================================================

def get_default_org_id():
    """Get default organization ID for single-tenant compatibility"""
    # This would be implemented to fetch from database or config
    return None


def create_all_tables(engine):
    """Create all tables in the database"""
    Base.metadata.create_all(engine)


def drop_all_tables(engine):
    """Drop all tables from the database"""
    Base.metadata.drop_all(engine)