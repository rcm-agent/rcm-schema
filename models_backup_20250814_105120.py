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
    Identity, Computed, text, func, Index, Enum
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from pgvector.sqlalchemy import Vector
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


class WorkflowChannelLu(Base):
    __tablename__ = 'workflow_channel_lu'
    channel = Column(Text, primary_key=True)


class ConfigTypeLu(Base):
    __tablename__ = 'config_type_lu'
    config_type = Column(Text, primary_key=True)


class WorkflowIoDirectionLu(Base):
    __tablename__ = 'workflow_io_direction_lu'
    direction = Column(Text, primary_key=True)


class StepStatusLu(Base):
    __tablename__ = 'step_status_lu'
    status = Column(Text, primary_key=True)


class TraceStatusLu(Base):
    __tablename__ = 'trace_status_lu'
    status = Column(Text, primary_key=True)


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
    node_metadata = Column(JSONB, server_default=text("'{}'::jsonb"))
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
    data_sources = relationship('DataSource', secondary='workflow_data_sources', back_populates='workflows')


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
    text_emb = Column(Vector(768), nullable=False)
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
# Workflow Execution Tracking (Updated by V10 - see new tables below)
# ============================================================================


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
    screenshot_metadata = Column(JSONB, default=dict)
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
# Data Source Tables
# ============================================================================

class DataSource(Base, TimestampMixin, OrgMixin):
    """Data sources for workflows (Excel files, CSV, etc.)"""
    __tablename__ = 'data_sources'
    
    data_source_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id = OrgMixin.org_id()
    name = Column(Text, nullable=False)
    description = Column(Text)
    file_name = Column(Text, nullable=False)
    file_type = Column(Text, nullable=False)
    file_size = Column(BigInteger, nullable=False)
    s3_bucket = Column(Text, nullable=False)
    s3_key = Column(Text, nullable=False)
    row_count = Column(Integer)
    column_count = Column(Integer)
    status = Column(Text, nullable=False, default='processing')
    error_message = Column(Text)
    uploaded_by = Column(UUID(as_uuid=True), ForeignKey('app_user.user_id', ondelete='CASCADE'), nullable=False)
    
    # Relationships
    columns = relationship('DataSourceColumn', back_populates='data_source', cascade='all, delete-orphan')
    workbook = relationship('DataSourceWorkbook', back_populates='data_source', uselist=False, cascade='all, delete-orphan')
    workflows = relationship('UserWorkflow', secondary='workflow_data_sources', back_populates='data_sources')
    uploader = relationship('AppUser', foreign_keys=[uploaded_by])
    
    __table_args__ = (
        CheckConstraint("file_type IN ('excel', 'csv')", name='ck_data_source_file_type'),
        CheckConstraint("status IN ('processing', 'active', 'failed', 'archived')", name='ck_data_source_status'),
        Index('idx_data_sources_org_id', 'org_id'),
        Index('idx_data_sources_status', 'status'),
    )


class DataSourceColumn(Base, TimestampMixin):
    """Column mappings for data sources"""
    __tablename__ = 'data_source_columns'
    
    column_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    data_source_id = Column(UUID(as_uuid=True), ForeignKey('data_sources.data_source_id', ondelete='CASCADE'), nullable=False)
    source_column_name = Column(Text, nullable=False)
    source_column_index = Column(Integer, nullable=False)
    target_field = Column(Text)
    transform = Column(Text, nullable=False, default='none')
    data_type = Column(Text)
    sample_values = Column(JSONB)
    
    # Relationships
    data_source = relationship('DataSource', back_populates='columns')
    
    __table_args__ = (
        CheckConstraint("transform IN ('none', 'uppercase', 'lowercase', 'trim', 'date')", name='ck_column_transform'),
        UniqueConstraint('data_source_id', 'source_column_name', name='uq_data_source_column_name'),
        Index('idx_data_source_columns_data_source_id', 'data_source_id'),
    )


class DataSourceWorkbook(Base, TimestampMixin):
    """Cached workbook data for Excel files"""
    __tablename__ = 'data_source_workbook'
    
    workbook_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    data_source_id = Column(UUID(as_uuid=True), ForeignKey('data_sources.data_source_id', ondelete='CASCADE'), nullable=False, unique=True)
    sheet_name = Column(Text, nullable=False)
    data = Column(JSONB, nullable=False)
    row_count = Column(Integer, nullable=False)
    
    # Relationships
    data_source = relationship('DataSource', back_populates='workbook')
    
    __table_args__ = (
        Index('idx_data_source_workbook_data_source_id', 'data_source_id'),
    )


# Association table for workflow data sources
workflow_data_sources = Base.metadata.tables.get('workflow_data_sources')
if not workflow_data_sources:
    from sqlalchemy import Table
    workflow_data_sources = Table('workflow_data_sources', Base.metadata,
        Column('workflow_id', UUID(as_uuid=True), ForeignKey('user_workflow.workflow_id', ondelete='CASCADE'), primary_key=True),
        Column('data_source_id', UUID(as_uuid=True), ForeignKey('data_sources.data_source_id', ondelete='CASCADE'), primary_key=True),
        Column('created_at', DateTime(timezone=True), nullable=False, server_default=func.now())
    )


# ============================================================================
# Billing and Subscription Models
# ============================================================================

class OrganizationBilling(Base, TimestampMixin):
    """Billing information for organizations"""
    __tablename__ = 'organizations_billing'
    
    org_billing_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id = Column(UUID(as_uuid=True), ForeignKey('organizations.org_id'), nullable=False, unique=True)
    stripe_customer_id = Column(String(255), unique=True)
    stripe_subscription_id = Column(String(255))
    stripe_payment_method_id = Column(String(255))
    
    # Relationships
    organization = relationship('Organization', back_populates='billing')
    subscriptions = relationship('OrganizationSubscription', back_populates='billing', cascade='all, delete-orphan')
    
    __table_args__ = (
        Index('idx_organizations_billing_org_id', 'org_id'),
        Index('idx_organizations_billing_stripe_customer_id', 'stripe_customer_id'),
    )


class SubscriptionPlan(Base, TimestampMixin):
    """Available subscription plans"""
    __tablename__ = 'subscription_plans'
    
    plan_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(100), nullable=False, unique=True)
    display_name = Column(String(100), nullable=False)
    stripe_product_id = Column(String(255), unique=True)
    stripe_price_id_monthly = Column(String(255))
    stripe_price_id_yearly = Column(String(255))
    price_monthly = Column(Numeric(10, 2), nullable=False)
    price_yearly = Column(Numeric(10, 2), nullable=False)
    features = Column(JSONB, nullable=False, default=dict)
    limits = Column(JSONB, nullable=False, default=dict)
    is_active = Column(Boolean, nullable=False, default=True)
    sort_order = Column(Integer, nullable=False, default=0)
    
    # Relationships
    subscriptions = relationship('OrganizationSubscription', back_populates='plan')


class OrganizationSubscription(Base, TimestampMixin):
    """Organization subscription records"""
    __tablename__ = 'organization_subscriptions'
    
    subscription_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id = Column(UUID(as_uuid=True), ForeignKey('organizations.org_id'), nullable=False)
    plan_id = Column(UUID(as_uuid=True), ForeignKey('subscription_plans.plan_id'), nullable=False)
    stripe_subscription_id = Column(String(255), unique=True)
    status = Column(Enum('active', 'canceled', 'past_due', 'trialing', 'incomplete', 'incomplete_expired', name='subscription_status'), nullable=False)
    billing_interval = Column(Enum('monthly', 'yearly', name='billing_interval'), nullable=False)
    current_period_start = Column(DateTime(timezone=True))
    current_period_end = Column(DateTime(timezone=True))
    cancel_at_period_end = Column(Boolean, nullable=False, default=False)
    canceled_at = Column(DateTime(timezone=True))
    trial_start = Column(DateTime(timezone=True))
    trial_end = Column(DateTime(timezone=True))
    
    # Relationships
    organization = relationship('Organization', backref='subscriptions')
    billing = relationship('OrganizationBilling', back_populates='subscriptions')
    plan = relationship('SubscriptionPlan', back_populates='subscriptions')
    usage = relationship('BillingUsage', back_populates='subscription', cascade='all, delete-orphan')
    invoices = relationship('Invoice', back_populates='subscription', cascade='all, delete-orphan')
    
    __table_args__ = (
        Index('idx_organization_subscriptions_org_id', 'org_id'),
        Index('idx_organization_subscriptions_status', 'status'),
    )


class BillingUsage(Base, TimestampMixin):
    """Usage tracking for billing purposes"""
    __tablename__ = 'billing_usage'
    
    usage_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id = Column(UUID(as_uuid=True), ForeignKey('organizations.org_id'), nullable=False)
    subscription_id = Column(UUID(as_uuid=True), ForeignKey('organization_subscriptions.subscription_id'))
    metric_name = Column(String(100), nullable=False)
    quantity = Column(Integer, nullable=False)
    unit_amount = Column(Numeric(10, 4))
    total_amount = Column(Numeric(10, 2))
    period_start = Column(DateTime(timezone=True), nullable=False)
    period_end = Column(DateTime(timezone=True), nullable=False)
    usage_metadata = Column(JSONB)
    reported_to_stripe = Column(Boolean, nullable=False, default=False)
    stripe_usage_record_id = Column(String(255))
    
    # Relationships
    organization = relationship('Organization', backref='billing_usage')
    subscription = relationship('OrganizationSubscription', back_populates='usage')
    
    __table_args__ = (
        Index('idx_billing_usage_org_id', 'org_id'),
        Index('idx_billing_usage_period', 'period_start', 'period_end'),
        Index('idx_billing_usage_metric', 'metric_name'),
    )


class Invoice(Base, TimestampMixin):
    """Invoice records"""
    __tablename__ = 'invoices'
    
    invoice_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id = Column(UUID(as_uuid=True), ForeignKey('organizations.org_id'), nullable=False)
    subscription_id = Column(UUID(as_uuid=True), ForeignKey('organization_subscriptions.subscription_id'))
    stripe_invoice_id = Column(String(255), unique=True)
    invoice_number = Column(String(100), unique=True)
    status = Column(Enum('pending', 'succeeded', 'failed', 'refunded', name='payment_status'), nullable=False)
    amount_due = Column(Numeric(10, 2), nullable=False)
    amount_paid = Column(Numeric(10, 2), nullable=False, default=0)
    currency = Column(String(3), nullable=False, default='USD')
    period_start = Column(DateTime(timezone=True), nullable=False)
    period_end = Column(DateTime(timezone=True), nullable=False)
    due_date = Column(DateTime(timezone=True))
    paid_at = Column(DateTime(timezone=True))
    invoice_pdf_url = Column(Text)
    hosted_invoice_url = Column(Text)
    line_items = Column(JSONB)
    
    # Relationships
    organization = relationship('Organization', backref='invoices')
    subscription = relationship('OrganizationSubscription', back_populates='invoices')
    
    __table_args__ = (
        Index('idx_invoices_org_id', 'org_id'),
        Index('idx_invoices_status', 'status'),
        Index('idx_invoices_period', 'period_start', 'period_end'),
    )


# Update Organization model to include billing relationship
Organization.billing = relationship('OrganizationBilling', back_populates='organization', uselist=False, cascade='all, delete-orphan')


# ============================================================================
# User Management
# ============================================================================

class UserInvitation(Base, TimestampMixin):
    """Tracks user invitations sent to join organizations"""
    __tablename__ = 'user_invitations'
    
    invite_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id = Column(UUID(as_uuid=True), ForeignKey('organization.org_id', ondelete='CASCADE'), nullable=False)
    email = Column(Text, nullable=False)
    role = Column(Text, nullable=False)
    invite_token = Column(String(255), nullable=False, unique=True)
    invited_by = Column(UUID(as_uuid=True), ForeignKey('app_user.user_id', ondelete='CASCADE'), nullable=False)
    message = Column(Text)
    accepted = Column(Boolean, nullable=False, default=False)
    accepted_at = Column(DateTime(timezone=True))
    accepted_by_user_id = Column(UUID(as_uuid=True), ForeignKey('app_user.user_id', ondelete='SET NULL'))
    expires_at = Column(DateTime(timezone=True), nullable=False)
    
    # Relationships
    organization = relationship('Organization', backref='invitations')
    inviter = relationship('AppUser', foreign_keys=[invited_by], backref='sent_invitations')
    accepter = relationship('AppUser', foreign_keys=[accepted_by_user_id], backref='accepted_invitations')
    
    # Indexes
    __table_args__ = (
        Index('idx_user_invitations_token', 'invite_token', unique=True),
        Index('idx_user_invitations_org_id', 'org_id'),
        Index('idx_user_invitations_email', 'email'),
        Index('idx_user_invitations_expires_at', 'expires_at'),
        Index('idx_user_invitations_accepted', 'accepted'),
        Index('idx_user_invitations_pending', 'org_id', 'accepted', 'expires_at'),
    )


# ============================================================================
# Workflow Execution Tables (V10)
# ============================================================================

class WorkflowConfig(Base, TimestampMixin):
    """Configuration for workflows with versioning support"""
    __tablename__ = 'workflow_configs'
    
    config_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id = Column(UUID(as_uuid=True), ForeignKey('organization.org_id', ondelete='CASCADE'), nullable=False)
    workflow_id = Column(UUID(as_uuid=True), ForeignKey('user_workflow.workflow_id', ondelete='CASCADE'))
    name = Column(String(255), nullable=False)
    config_type = Column(Text, nullable=False)  # workflow, channel, global
    config_data = Column(JSONB, nullable=False)
    is_active = Column(Boolean, nullable=False, default=True)
    created_by = Column(UUID(as_uuid=True), ForeignKey('app_user.user_id', ondelete='RESTRICT'), nullable=False)
    
    # Relationships
    organization = relationship('Organization', backref='workflow_configs')
    workflow = relationship('UserWorkflow', backref='configs')
    creator = relationship('AppUser', foreign_keys=[created_by])
    
    __table_args__ = (
        UniqueConstraint('org_id', 'workflow_id', 'name', 'config_type', name='uq_workflow_config_unique'),
        CheckConstraint("config_type IN ('workflow', 'channel', 'global')", name='ck_config_type'),
        Index('idx_workflow_configs_org_id', 'org_id'),
        Index('idx_workflow_configs_workflow_id', 'workflow_id'),
        Index('idx_workflow_configs_type', 'config_type'),
        Index('idx_workflow_configs_active', 'is_active'),
    )


class ChannelConfig(Base, TimestampMixin):
    """Channel-specific configurations"""
    __tablename__ = 'channel_configs'
    
    channel_config_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id = Column(UUID(as_uuid=True), ForeignKey('organization.org_id', ondelete='CASCADE'), nullable=False)
    channel = Column(Text, nullable=False)  # web, voice, efax
    name = Column(String(255), nullable=False)
    config_data = Column(JSONB, nullable=False)
    is_active = Column(Boolean, nullable=False, default=True)
    created_by = Column(UUID(as_uuid=True), ForeignKey('app_user.user_id', ondelete='RESTRICT'), nullable=False)
    
    # Relationships
    organization = relationship('Organization', backref='channel_configs')
    creator = relationship('AppUser', foreign_keys=[created_by])
    workflow_channels = relationship('WorkflowChannelConfig', back_populates='channel_config')
    
    __table_args__ = (
        UniqueConstraint('org_id', 'channel', 'name', name='uq_channel_config_unique'),
        CheckConstraint("channel IN ('web', 'voice', 'efax')", name='ck_workflow_channel'),
        Index('idx_channel_configs_org_id', 'org_id'),
        Index('idx_channel_configs_channel', 'channel'),
        Index('idx_channel_configs_active', 'is_active'),
    )


class WorkflowChannelConfig(Base, TimestampMixin):
    """Workflow-channel associations with channel-specific settings"""
    __tablename__ = 'workflow_channel_configs'
    
    workflow_channel_config_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workflow_id = Column(UUID(as_uuid=True), ForeignKey('user_workflow.workflow_id', ondelete='CASCADE'), nullable=False)
    channel = Column(Text, nullable=False)  # web, voice, efax
    channel_config_id = Column(UUID(as_uuid=True), ForeignKey('channel_configs.channel_config_id', ondelete='SET NULL'))
    webhook_url = Column(Text)
    is_enabled = Column(Boolean, nullable=False, default=True)
    priority = Column(Integer, nullable=False, default=1)
    
    # Relationships
    workflow = relationship('UserWorkflow', backref='channel_configs')
    channel_config = relationship('ChannelConfig', back_populates='workflow_channels')
    
    __table_args__ = (
        UniqueConstraint('workflow_id', 'channel', name='uq_workflow_channel_unique'),
        CheckConstraint("channel IN ('web', 'voice', 'efax')", name='ck_workflow_channel_config'),
        Index('idx_workflow_channel_configs_workflow', 'workflow_id'),
        Index('idx_workflow_channel_configs_channel', 'channel'),
        Index('idx_workflow_channel_configs_enabled', 'is_enabled'),
    )


class NodeIoRequirement(Base, TimestampMixin):
    """Input/output requirements for workflow nodes"""
    __tablename__ = 'node_io_requirements'
    
    node_io_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    node_id = Column(BigInteger, ForeignKey('workflow_node.node_id', ondelete='CASCADE'), nullable=False)
    io_name = Column(String(255), nullable=False)
    io_direction = Column(Text, nullable=False)  # input, output
    data_type = Column(String(50), nullable=False)
    is_required = Column(Boolean, nullable=False, default=True)
    default_value = Column(JSONB)
    validation_rules = Column(JSONB)
    
    # Relationships
    node = relationship('WorkflowNode', backref='io_requirements')
    
    __table_args__ = (
        UniqueConstraint('node_id', 'io_name', 'io_direction', name='uq_node_io_unique'),
        CheckConstraint("io_direction IN ('input', 'output')", name='ck_io_direction'),
        CheckConstraint("data_type IN ('string', 'number', 'boolean', 'object', 'array', 'date', 'file')", name='ck_io_data_type'),
        Index('idx_node_io_requirements_node', 'node_id'),
        Index('idx_node_io_requirements_direction', 'io_direction'),
    )


class WorkflowTrace(Base):
    """Enhanced workflow execution traces with multi-channel support"""
    __tablename__ = 'workflow_trace'
    
    trace_id = Column(BigInteger, Identity(always=False), primary_key=True)
    workflow_id = Column(UUID(as_uuid=True), ForeignKey('user_workflow.workflow_id', ondelete='RESTRICT'), nullable=False)
    channel = Column(Text, nullable=False)  # web, voice, efax
    external_id = Column(String(255))
    status = Column(Text, nullable=False, default='pending')  # pending, active, completed, failed, cancelled, timeout
    config_snapshot = Column(JSONB)
    start_time = Column(DateTime(timezone=True))
    end_time = Column(DateTime(timezone=True))
    duration_ms = Column(Integer)
    error_message = Column(Text)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    created_by = Column(UUID(as_uuid=True), ForeignKey('app_user.user_id', ondelete='RESTRICT'), nullable=False)
    
    # Relationships
    workflow = relationship('UserWorkflow', backref='traces')
    creator = relationship('AppUser', foreign_keys=[created_by])
    steps = relationship('WorkflowStep', back_populates='trace', cascade='all, delete-orphan')
    context = relationship('WorkflowTraceContext', back_populates='trace', cascade='all, delete-orphan')
    events = relationship('WorkflowEvent', back_populates='trace', cascade='all, delete-orphan')
    
    __table_args__ = (
        CheckConstraint("channel IN ('web', 'voice', 'efax')", name='ck_trace_channel'),
        CheckConstraint("status IN ('pending', 'active', 'completed', 'failed', 'cancelled', 'timeout')", name='ck_trace_status'),
        Index('idx_workflow_trace_workflow', 'workflow_id'),
        Index('idx_workflow_trace_channel', 'channel'),
        Index('idx_workflow_trace_status', 'status'),
        Index('idx_workflow_trace_created_at', 'created_at'),
        Index('idx_workflow_trace_external_id', 'external_id'),
        Index('idx_workflow_trace_workflow_status', 'workflow_id', 'status'),
    )


class WorkflowStep(Base):
    """Individual steps in workflow execution"""
    __tablename__ = 'workflow_steps'
    
    step_id = Column(BigInteger, Identity(always=False), primary_key=True)
    trace_id = Column(BigInteger, ForeignKey('workflow_trace.trace_id', ondelete='CASCADE'), nullable=False)
    node_id = Column(BigInteger, ForeignKey('workflow_node.node_id', ondelete='RESTRICT'), nullable=False)
    step_number = Column(Integer, nullable=False)
    status = Column(Text, nullable=False, default='pending')  # pending, running, completed, failed, skipped
    input_data = Column(JSONB)
    output_data = Column(JSONB)
    error_message = Column(Text)
    start_time = Column(DateTime(timezone=True))
    end_time = Column(DateTime(timezone=True))
    duration_ms = Column(Integer)
    retry_count = Column(Integer, nullable=False, default=0)
    step_metadata = Column('metadata', JSONB)  # TEMPORARY TEMP-20250813-144500-METADATA: Renamed to avoid SQLAlchemy reserved word
    
    # Relationships
    trace = relationship('WorkflowTrace', back_populates='steps')
    node = relationship('WorkflowNode', backref='execution_steps')
    events = relationship('WorkflowEvent', back_populates='step')
    
    __table_args__ = (
        UniqueConstraint('trace_id', 'step_number', name='uq_workflow_step_number'),
        CheckConstraint("status IN ('pending', 'running', 'completed', 'failed', 'skipped')", name='ck_step_status'),
        Index('idx_workflow_steps_trace', 'trace_id'),
        Index('idx_workflow_steps_node', 'node_id'),
        Index('idx_workflow_steps_status', 'status'),
        Index('idx_workflow_steps_trace_status', 'trace_id', 'status'),
    )


class WorkflowTraceContext(Base, TimestampMixin):
    """Key-value context storage for workflow execution"""
    __tablename__ = 'workflow_trace_context'
    
    context_id = Column(BigInteger, Identity(always=False), primary_key=True)
    trace_id = Column(BigInteger, ForeignKey('workflow_trace.trace_id', ondelete='CASCADE'), nullable=False)
    key = Column(String(255), nullable=False)
    value = Column(JSONB, nullable=False)
    
    # Relationships
    trace = relationship('WorkflowTrace', back_populates='context')
    
    __table_args__ = (
        UniqueConstraint('trace_id', 'key', name='uq_trace_context_key'),
        Index('idx_workflow_trace_context_trace', 'trace_id'),
        Index('idx_workflow_trace_context_key', 'key'),
    )


class WorkflowEvent(Base):
    """Event log for workflow execution"""
    __tablename__ = 'workflow_events'
    
    event_id = Column(BigInteger, Identity(always=False), primary_key=True)
    trace_id = Column(BigInteger, ForeignKey('workflow_trace.trace_id', ondelete='CASCADE'), nullable=False)
    step_id = Column(BigInteger, ForeignKey('workflow_steps.step_id', ondelete='CASCADE'))
    event_type = Column(String(100), nullable=False)
    event_data = Column(JSONB, nullable=False)
    timestamp = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    
    # Relationships
    trace = relationship('WorkflowTrace', back_populates='events')
    step = relationship('WorkflowStep', back_populates='events')
    
    __table_args__ = (
        Index('idx_workflow_events_trace', 'trace_id'),
        Index('idx_workflow_events_step', 'step_id'),
        Index('idx_workflow_events_type', 'event_type'),
        Index('idx_workflow_events_timestamp', 'timestamp'),
    )


class WorkflowDataBinding(Base, TimestampMixin):
    """Data bindings between workflow nodes"""
    __tablename__ = 'workflow_data_bindings'
    
    binding_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workflow_id = Column(UUID(as_uuid=True), ForeignKey('user_workflow.workflow_id', ondelete='CASCADE'), nullable=False)
    node_id = Column(BigInteger, ForeignKey('workflow_node.node_id', ondelete='CASCADE'), nullable=False)
    io_name = Column(String(255), nullable=False)
    binding_type = Column(String(50), nullable=False)
    binding_config = Column(JSONB, nullable=False)
    
    # Relationships
    workflow = relationship('UserWorkflow', backref='data_bindings')
    node = relationship('WorkflowNode', backref='data_bindings')
    
    __table_args__ = (
        UniqueConstraint('workflow_id', 'node_id', 'io_name', name='uq_workflow_data_binding'),
        Index('idx_workflow_data_bindings_workflow', 'workflow_id'),
        Index('idx_workflow_data_bindings_node', 'node_id'),
    )


class ConfigStatus(Base, TimestampMixin):
    """Tracks active configurations for different entities"""
    __tablename__ = 'config_status'
    
    status_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id = Column(UUID(as_uuid=True), ForeignKey('organization.org_id', ondelete='CASCADE'), nullable=False)
    config_type = Column(Text, nullable=False)  # workflow, channel, global
    entity_id = Column(UUID(as_uuid=True))
    active_config_id = Column(UUID(as_uuid=True))
    activated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    activated_by = Column(UUID(as_uuid=True), ForeignKey('app_user.user_id', ondelete='RESTRICT'), nullable=False)
    
    # Relationships
    organization = relationship('Organization', backref='config_statuses')
    activator = relationship('AppUser', foreign_keys=[activated_by])
    
    __table_args__ = (
        UniqueConstraint('org_id', 'config_type', 'entity_id', name='uq_config_status_unique'),
        CheckConstraint("config_type IN ('workflow', 'channel', 'global')", name='ck_config_status_type'),
        Index('idx_config_status_org', 'org_id'),
        Index('idx_config_status_type', 'config_type'),
        Index('idx_config_status_entity', 'entity_id'),
    )


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