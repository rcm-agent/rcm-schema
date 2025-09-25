"""Add user_organization table for many-to-many relationship

Revision ID: 009_add_user_org
Revises: 008_add_revisions
Create Date: 2025-08-02

This migration:
1. Removes org_id foreign key from app_user table
2. Creates user_organization association table
3. Migrates existing user-org relationships
4. Adds indexes and constraints
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers
revision = '009_add_user_organization_table'
down_revision = '008_add_workflow_revisions'
branch_labels = None
depends_on = None


def upgrade():
    # Create user_organization table
    op.create_table('user_organization',
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('org_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('is_primary', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('joined_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['org_id'], ['organization.org_id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['app_user.user_id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('user_id', 'org_id')
    )
    
    # Create indexes
    op.create_index('idx_user_organization_user_id', 'user_organization', ['user_id'])
    op.create_index('idx_user_organization_org_id', 'user_organization', ['org_id'])
    op.create_index('idx_user_organization_active', 'user_organization', ['is_active'])
    
    # Create unique constraint for one primary org per user
    op.create_index(
        'uq_one_primary_org_per_user',
        'user_organization',
        ['user_id', 'is_primary'],
        unique=True,
        postgresql_where=sa.text('is_primary = true')
    )
    
    # Migrate existing data from app_user to user_organization
    # Only if app_user has org_id column (check if it exists first)
    connection = op.get_bind()
    
    # Check if org_id column exists in app_user
    result = connection.execute(sa.text("""
        SELECT column_name 
        FROM information_schema.columns 
        WHERE table_name = 'app_user' AND column_name = 'org_id'
    """))
    
    if result.fetchone():
        # Migrate existing relationships
        op.execute("""
            INSERT INTO user_organization (user_id, org_id, is_active, is_primary, joined_at)
            SELECT user_id, org_id, true, true, created_at
            FROM app_user
            WHERE org_id IS NOT NULL
        """)
        
        # Drop the foreign key constraint
        op.drop_constraint('app_user_org_id_fkey', 'app_user', type_='foreignkey')
        
        # Drop the org_id column
        op.drop_column('app_user', 'org_id')


def downgrade():
    # Add org_id column back to app_user
    op.add_column('app_user', 
        sa.Column('org_id', postgresql.UUID(as_uuid=True), nullable=True)
    )
    
    # Restore data from user_organization (taking primary org)
    op.execute("""
        UPDATE app_user au
        SET org_id = uo.org_id
        FROM user_organization uo
        WHERE au.user_id = uo.user_id
        AND uo.is_primary = true
    """)
    
    # Recreate foreign key constraint
    op.create_foreign_key(
        'app_user_org_id_fkey', 
        'app_user', 
        'organization', 
        ['org_id'], 
        ['org_id'],
        ondelete='CASCADE'
    )
    
    # Drop indexes
    op.drop_index('uq_one_primary_org_per_user', 'user_organization')
    op.drop_index('idx_user_organization_active', 'user_organization')
    op.drop_index('idx_user_organization_org_id', 'user_organization')
    op.drop_index('idx_user_organization_user_id', 'user_organization')
    
    # Drop user_organization table
    op.drop_table('user_organization')