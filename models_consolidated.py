"""
SQLAlchemy models for consolidated workflow tables
This file contains the new simplified table structure after migration 018
"""

from sqlalchemy import (
    Column, String, Text, Integer, BigInteger, SmallInteger, Boolean, 
    DateTime, ForeignKey, UniqueConstraint, CheckConstraint, Index,
    Identity, func
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.ext.declarative import declarative_base
import uuid

Base = declarative_base()

# ============================================================================
# Consolidated Workflow Execution Tables
# ============================================================================

class UserWorkflowRun(Base):
    """Main workflow execution record - one per workflow run"""
    __tablename__ = 'user_workflow_run'
    
    # Primary key
    run_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Foreign keys
    workflow_id = Column(UUID(as_uuid=True), 
                        ForeignKey('user_workflow.workflow_id', ondelete='CASCADE'), 
                        nullable=False)
    org_id = Column(UUID(as_uuid=True), 
                   ForeignKey('organization.org_id', ondelete='CASCADE'), 
                   nullable=False)
    created_by = Column(UUID(as_uuid=True), 
                       ForeignKey('app_user.user_id', ondelete='RESTRICT'), 
                       nullable=False)
    
    # Execution info
    status = Column(Text, nullable=False, default='pending')
    channel = Column(Text, nullable=False)  # web, voice, efax
    external_id = Column(String(255))  # External reference ID
    
    # Timing
    started_at = Column(DateTime(timezone=True))
    ended_at = Column(DateTime(timezone=True))
    duration_ms = Column(Integer)
    
    # Context (replaces workflow_trace_context table)
    context = Column(JSONB, nullable=False, server_default='{}')
    
    # Configuration snapshot
    config_snapshot = Column(JSONB)
    
    # Endpoints (replaces workflow_trace_endpoint table)
    endpoints_used = Column(JSONB, nullable=False, server_default='[]')
    
    # Error handling
    error_message = Column(Text)
    error_details = Column(JSONB)
    
    # LLM tracking (from old workflow_trace)
    llm_prompt = Column(Text)
    llm_response = Column(Text)
    llm_model = Column(String(100))
    llm_tokens_used = Column(Integer)
    
    # Tier system
    tier = Column(SmallInteger)
    tier_reason = Column(Text)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Legacy reference for migration (temporary)
    legacy_trace_id = Column(BigInteger, unique=True)
    
    # Relationships
    workflow = relationship('UserWorkflow', backref='runs')
    organization = relationship('Organization', backref='workflow_runs')
    creator = relationship('AppUser', foreign_keys=[created_by], backref='created_runs')
    steps = relationship('UserWorkflowRunStep', back_populates='run', 
                        cascade='all, delete-orphan', 
                        order_by='UserWorkflowRunStep.step_number')
    
    # Constraints and indexes
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'running', 'completed', 'failed', 'cancelled', 'timeout')", 
            name='ck_run_status'
        ),
        CheckConstraint(
            "channel IN ('web', 'voice', 'efax')", 
            name='ck_run_channel'
        ),
        UniqueConstraint('org_id', 'external_id', name='uq_run_external_id'),
        
        # Indexes
        Index('idx_run_workflow', 'workflow_id'),
        Index('idx_run_org', 'org_id'),
        Index('idx_run_status', 'status'),
        Index('idx_run_channel', 'channel'),
        Index('idx_run_created_at', 'created_at'),
        Index('idx_run_external_id', 'external_id'),
        Index('idx_run_workflow_status', 'workflow_id', 'status'),
        Index('idx_run_org_status', 'org_id', 'status'),
    )
    
    def add_context(self, key, value):
        """Add or update a context value"""
        if self.context is None:
            self.context = {}
        self.context[key] = value
    
    def get_context(self, key, default=None):
        """Get a context value"""
        if self.context is None:
            return default
        return self.context.get(key, default)
    
    def add_endpoint(self, endpoint_id):
        """Add an endpoint to the used list"""
        if self.endpoints_used is None:
            self.endpoints_used = []
        if endpoint_id not in self.endpoints_used:
            self.endpoints_used.append(endpoint_id)
    
    @property
    def is_completed(self):
        """Check if run is in a terminal state"""
        return self.status in ('completed', 'failed', 'cancelled', 'timeout')
    
    @property
    def is_successful(self):
        """Check if run completed successfully"""
        return self.status == 'completed'


class UserWorkflowRunStep(Base):
    """Steps within a workflow execution"""
    __tablename__ = 'user_workflow_run_step'
    
    # Primary key
    step_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Foreign keys
    run_id = Column(UUID(as_uuid=True), 
                   ForeignKey('user_workflow_run.run_id', ondelete='CASCADE'), 
                   nullable=False)
    node_id = Column(UUID(as_uuid=True), 
                    ForeignKey('user_workflow_node.node_id', ondelete='RESTRICT'), 
                    nullable=False)
    
    # Step execution
    step_number = Column(Integer, nullable=False)
    status = Column(Text, nullable=False, default='pending')
    retry_count = Column(Integer, nullable=False, default=0)
    
    # Timing
    started_at = Column(DateTime(timezone=True))
    ended_at = Column(DateTime(timezone=True))
    duration_ms = Column(Integer)
    
    # Data flow
    input_data = Column(JSONB)
    output_data = Column(JSONB)
    
    # Screenshots (replaces workflow_trace_screenshot table)
    screenshots = Column(JSONB, nullable=False, server_default='[]')
    """
    Screenshot structure:
    [
        {
            "url": "s3://bucket/screenshot1.png",
            "thumbnail_url": "s3://bucket/thumb1.png",
            "timestamp": "2025-01-14T10:30:00Z",
            "action": "click_submit",
            "selector": "#submit-button",
            "element_found": true,
            "confidence": 0.95
        }
    ]
    """
    
    # Events (replaces workflow_events table)
    events = Column(JSONB, nullable=False, server_default='[]')
    """
    Event structure:
    [
        {
            "type": "element_clicked",
            "timestamp": "2025-01-14T10:30:00Z",
            "data": {"selector": "#submit", "success": true}
        }
    ]
    """
    
    # Error handling
    error_message = Column(Text)
    error_details = Column(JSONB)
    
    # Additional metadata
    metadata = Column(JSONB, nullable=False, server_default='{}')
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Legacy reference for migration (temporary)
    legacy_step_id = Column(BigInteger, unique=True)
    
    # Relationships
    run = relationship('UserWorkflowRun', back_populates='steps')
    node = relationship('UserWorkflowNode', backref='run_steps')
    
    # Constraints and indexes
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'running', 'completed', 'failed', 'skipped')", 
            name='ck_step_status'
        ),
        UniqueConstraint('run_id', 'step_number', name='uq_run_step_number'),
        
        # Indexes
        Index('idx_step_run', 'run_id'),
        Index('idx_step_node', 'node_id'),
        Index('idx_step_status', 'status'),
        Index('idx_step_run_status', 'run_id', 'status'),
        Index('idx_step_run_number', 'run_id', 'step_number'),
    )
    
    def add_screenshot(self, url, action=None, selector=None, confidence=None, **kwargs):
        """Add a screenshot to this step"""
        if self.screenshots is None:
            self.screenshots = []
        
        screenshot = {
            'url': url,
            'timestamp': datetime.utcnow().isoformat() + 'Z',
            'action': action,
            'selector': selector,
            'confidence': confidence
        }
        screenshot.update(kwargs)  # Add any additional fields
        
        self.screenshots.append(screenshot)
    
    def add_event(self, event_type, data=None):
        """Add an event to this step"""
        if self.events is None:
            self.events = []
        
        event = {
            'type': event_type,
            'timestamp': datetime.utcnow().isoformat() + 'Z',
            'data': data or {}
        }
        
        self.events.append(event)
    
    @property
    def is_completed(self):
        """Check if step is in a terminal state"""
        return self.status in ('completed', 'failed', 'skipped')
    
    @property
    def is_successful(self):
        """Check if step completed successfully"""
        return self.status == 'completed'
    
    @property
    def screenshot_count(self):
        """Get number of screenshots for this step"""
        return len(self.screenshots) if self.screenshots else 0
    
    @property
    def event_count(self):
        """Get number of events for this step"""
        return len(self.events) if self.events else 0


# ============================================================================
# Renamed Tables for Consistency
# ============================================================================

class UserWorkflowConfig(Base):
    """Configuration for workflows with versioning support (renamed from workflow_configs)"""
    __tablename__ = 'user_workflow_config'
    
    config_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id = Column(UUID(as_uuid=True), 
                   ForeignKey('organization.org_id', ondelete='CASCADE'), 
                   nullable=False)
    workflow_id = Column(UUID(as_uuid=True), 
                        ForeignKey('user_workflow.workflow_id', ondelete='CASCADE'))
    name = Column(String(255), nullable=False)
    config_type = Column(Text, nullable=False)  # workflow, channel, global
    config_data = Column(JSONB, nullable=False)
    is_active = Column(Boolean, nullable=False, default=True)
    created_by = Column(UUID(as_uuid=True), 
                       ForeignKey('app_user.user_id', ondelete='RESTRICT'), 
                       nullable=False)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    organization = relationship('Organization', backref='workflow_configs')
    workflow = relationship('UserWorkflow', backref='configs')
    creator = relationship('AppUser', foreign_keys=[created_by])
    
    __table_args__ = (
        UniqueConstraint('org_id', 'workflow_id', 'name', 'config_type', 
                        name='uq_workflow_config_unique'),
        CheckConstraint("config_type IN ('workflow', 'channel', 'global')", 
                       name='ck_config_type'),
        Index('idx_workflow_config_org_id', 'org_id'),
        Index('idx_workflow_config_workflow_id', 'workflow_id'),
        Index('idx_workflow_config_type', 'config_type'),
        Index('idx_workflow_config_active', 'is_active'),
    )


class UserWorkflowCacheState(Base):
    """Cached states for Tier 1 system (renamed from micro_state)"""
    __tablename__ = 'user_workflow_cache_state'
    
    cache_state_id = Column(BigInteger, Identity(always=False), primary_key=True)
    workflow_id = Column(UUID(as_uuid=True), 
                        ForeignKey('user_workflow.workflow_id', ondelete='CASCADE'), 
                        nullable=False)
    node_id = Column(UUID(as_uuid=True), 
                    ForeignKey('user_workflow_node.node_id', ondelete='CASCADE'), 
                    nullable=False)
    
    # State data
    dom_snapshot = Column(Text, nullable=False)
    action_json = Column(JSONB, nullable=False)
    semantic_spec = Column(JSONB)
    label = Column(Text)
    category = Column(Text)
    required = Column(Boolean, default=False)
    is_dynamic = Column(Boolean)
    
    # Embeddings for similarity search
    text_emb = Column('text_embedding', JSONB, nullable=False)  # Vector(768) in actual DB
    
    # Cache management
    mini_score = Column(Float)
    is_retired = Column(Boolean, nullable=False, default=False)
    aliased_to = Column(BigInteger, ForeignKey('user_workflow_cache_state.cache_state_id'))
    
    # Success/failure tracking
    success_count = Column(Integer, default=0)
    failure_count = Column(Integer, default=0)
    last_used = Column(DateTime(timezone=True))
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    workflow = relationship('UserWorkflow', backref='cache_states')
    node = relationship('UserWorkflowNode', backref='cache_states')
    alias_target = relationship('UserWorkflowCacheState', remote_side=[cache_state_id])
    
    __table_args__ = (
        Index('idx_cache_state_workflow', 'workflow_id'),
        Index('idx_cache_state_node', 'node_id'),
        Index('idx_cache_state_retired', 'is_retired'),
        Index('idx_cache_state_last_used', 'last_used'),
    )
    
    @property
    def success_rate(self):
        """Calculate success rate for this cached state"""
        total = self.success_count + self.failure_count
        if total == 0:
            return 0.0
        return self.success_count / total


# ============================================================================
# Helper Functions for Migration
# ============================================================================

def migrate_context_to_jsonb(trace_contexts):
    """Convert workflow_trace_context records to JSONB for run.context"""
    context = {}
    for ctx in trace_contexts:
        context[ctx.key] = ctx.value
    return context


def migrate_endpoints_to_jsonb(trace_endpoints):
    """Convert workflow_trace_endpoint records to JSONB array"""
    return [ep.endpoint_id for ep in trace_endpoints]


def migrate_screenshots_to_jsonb(screenshots):
    """Convert workflow_trace_screenshot records to JSONB array"""
    return [
        {
            'url': s.screenshot_url,
            'thumbnail_url': s.thumbnail_url,
            'timestamp': s.created_at.isoformat() + 'Z',
            'action': s.action_description,
            'selector': s.element_selector,
            'element_found': s.element_found,
            'confidence': float(s.confidence_score) if s.confidence_score else None
        }
        for s in screenshots
    ]


def migrate_events_to_jsonb(events):
    """Convert workflow_events records to JSONB array"""
    return [
        {
            'type': e.event_type,
            'timestamp': e.timestamp.isoformat() + 'Z',
            'data': e.event_data
        }
        for e in events
    ]