"""Add user invitations table

Revision ID: 013_add_user_invitations
Revises: 012_add_billing_tables
Create Date: 2025-08-04

This migration adds a table to track user invitations sent to join organizations.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
import uuid

# revision identifiers
revision = '013_add_user_invitations_table'
down_revision = '012_add_billing_tables'
branch_labels = None
depends_on = None


def upgrade():
    # Create user_invitations table
    op.create_table('user_invitations',
        sa.Column('invite_id', postgresql.UUID(as_uuid=True), nullable=False, 
                  default=uuid.uuid4, server_default=sa.text('gen_random_uuid()')),
        sa.Column('org_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('email', sa.Text(), nullable=False),
        sa.Column('role', sa.Text(), nullable=False),
        sa.Column('invite_token', sa.String(255), nullable=False),
        sa.Column('invited_by', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('message', sa.Text(), nullable=True),
        sa.Column('accepted', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('accepted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('accepted_by_user_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        
        sa.PrimaryKeyConstraint('invite_id'),
        sa.ForeignKeyConstraint(['org_id'], ['organization.org_id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['invited_by'], ['app_user.user_id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['accepted_by_user_id'], ['app_user.user_id'], ondelete='SET NULL'),
    )
    
    # Create indexes for efficient queries
    op.create_index('idx_user_invitations_token', 'user_invitations', ['invite_token'], unique=True)
    op.create_index('idx_user_invitations_org_id', 'user_invitations', ['org_id'])
    op.create_index('idx_user_invitations_email', 'user_invitations', ['email'])
    op.create_index('idx_user_invitations_expires_at', 'user_invitations', ['expires_at'])
    op.create_index('idx_user_invitations_accepted', 'user_invitations', ['accepted'])
    
    # Create a composite index for finding pending invitations
    op.create_index('idx_user_invitations_pending', 'user_invitations', 
                    ['org_id', 'accepted', 'expires_at'])


def downgrade():
    # Drop indexes
    op.drop_index('idx_user_invitations_pending', 'user_invitations')
    op.drop_index('idx_user_invitations_accepted', 'user_invitations')
    op.drop_index('idx_user_invitations_expires_at', 'user_invitations')
    op.drop_index('idx_user_invitations_email', 'user_invitations')
    op.drop_index('idx_user_invitations_org_id', 'user_invitations')
    op.drop_index('idx_user_invitations_token', 'user_invitations')
    
    # Drop table
    op.drop_table('user_invitations')