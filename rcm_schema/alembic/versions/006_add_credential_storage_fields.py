"""add credential storage fields following AWS best practices

Revision ID: 006
Revises: 005
Create Date: 2025-01-30

This migration adds secure credential storage capabilities using AWS SSM Parameter Store
and Secrets Manager ARNs, along with audit logging and rotation scheduling.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '006_add_credential_storage_fields'
down_revision = '005_add_comprehensive_bpo_task_enums'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add credential storage fields to integration_endpoint and create related tables."""
    
    # Add credential storage fields to integration_endpoint
    op.add_column('integration_endpoint', 
        sa.Column('secret_arn', sa.Text(), nullable=True,
                  comment='AWS Secrets Manager ARN or Parameter Store path for secure credential storage'))
    
    op.add_column('integration_endpoint',
        sa.Column('last_rotated_at', sa.DateTime(timezone=True), nullable=True,
                  comment='Timestamp of last credential rotation'))
    
    op.add_column('integration_endpoint',
        sa.Column('rotation_status', sa.Text(), nullable=True,
                  comment='Current rotation status: active, failed, or pending'))
    
    # Add check constraints
    op.create_check_constraint(
        'check_secret_arn_format',
        'integration_endpoint',
        "secret_arn IS NULL OR (secret_arn LIKE 'arn:aws:ssm:%' OR secret_arn LIKE 'arn:aws:secretsmanager:%')"
    )
    
    op.create_check_constraint(
        'check_rotation_status',
        'integration_endpoint',
        "rotation_status IS NULL OR rotation_status IN ('active', 'failed', 'pending')"
    )
    
    # Add indexes for performance
    op.create_index(
        'idx_integration_endpoint_secret_arn',
        'integration_endpoint',
        ['secret_arn'],
        postgresql_where=sa.text('secret_arn IS NOT NULL')
    )
    
    op.create_index(
        'idx_integration_endpoint_rotation_status',
        'integration_endpoint',
        ['rotation_status'],
        postgresql_where=sa.text('rotation_status IS NOT NULL')
    )
    
    # Create credential access log table for audit trail
    op.create_table('credential_access_log',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('access_timestamp', sa.DateTime(timezone=True), 
                  server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('portal_id', sa.Text(), nullable=False),
        sa.Column('secret_arn', sa.Text(), nullable=True),
        sa.Column('access_type', sa.Text(), nullable=False, 
                  comment='retrieve, store, rotate, delete'),
        sa.Column('access_by', sa.Text(), nullable=True,
                  comment='User or service that accessed'),
        sa.Column('ip_address', sa.Text(), nullable=True),
        sa.Column('user_agent', sa.Text(), nullable=True),
        sa.Column('success', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=True,
                  comment='Additional context'),
        sa.PrimaryKeyConstraint('id'),
        sa.CheckConstraint(
            "access_type IN ('retrieve', 'store', 'rotate', 'delete')",
            name='check_access_type'
        )
    )
    
    # Add indexes for audit log queries
    op.create_index('idx_credential_access_log_portal_id', 
                   'credential_access_log', ['portal_id'])
    op.create_index('idx_credential_access_log_timestamp', 
                   'credential_access_log', ['access_timestamp'])
    op.create_index('idx_credential_access_log_access_type', 
                   'credential_access_log', ['access_type'])
    
    # Create credential rotation schedule table
    op.create_table('credential_rotation_schedule',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('portal_id', sa.Text(), nullable=False),
        sa.Column('secret_arn', sa.Text(), nullable=True),
        sa.Column('last_rotation', sa.DateTime(timezone=True), nullable=True),
        sa.Column('next_rotation', sa.DateTime(timezone=True), nullable=True),
        sa.Column('rotation_interval_days', sa.Integer(), nullable=False, server_default='90'),
        sa.Column('auto_rotate', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('notification_email', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), 
                  server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('portal_id', name='uq_rotation_schedule_portal_id'),
        sa.CheckConstraint(
            'rotation_interval_days > 0',
            name='check_rotation_interval_positive'
        )
    )
    
    # Add indexes for rotation schedule
    op.create_index('idx_rotation_schedule_portal_id', 
                   'credential_rotation_schedule', ['portal_id'])
    op.create_index('idx_rotation_schedule_next_rotation', 
                   'credential_rotation_schedule', ['next_rotation'])
    
    # Add comments to document the tables
    op.execute("""
        COMMENT ON TABLE credential_access_log IS 
        'Audit log for credential access operations. Tracks all credential retrievals, updates, and rotations for compliance and security monitoring.';
        
        COMMENT ON TABLE credential_rotation_schedule IS 
        'Manages credential rotation schedules for each portal. Supports automated rotation and notification policies.';
        
        COMMENT ON COLUMN integration_endpoint.secret_arn IS 
        'AWS Secrets Manager ARN or Parameter Store path for secure credential storage. Format: arn:aws:secretsmanager:region:account:secret:name or arn:aws:ssm:region:account:parameter/path';
    """)


def downgrade() -> None:
    """Remove credential storage fields and tables."""
    
    # Drop tables
    op.drop_table('credential_rotation_schedule')
    op.drop_table('credential_access_log')
    
    # Drop indexes from integration_endpoint
    op.drop_index('idx_integration_endpoint_rotation_status', table_name='integration_endpoint')
    op.drop_index('idx_integration_endpoint_secret_arn', table_name='integration_endpoint')
    
    # Drop check constraints
    op.drop_constraint('check_rotation_status', 'integration_endpoint', type_='check')
    op.drop_constraint('check_secret_arn_format', 'integration_endpoint', type_='check')
    
    # Drop columns from integration_endpoint
    op.drop_column('integration_endpoint', 'rotation_status')
    op.drop_column('integration_endpoint', 'last_rotated_at')
    op.drop_column('integration_endpoint', 'secret_arn')