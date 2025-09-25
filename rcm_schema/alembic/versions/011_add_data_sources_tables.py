"""Add data sources tables

Revision ID: 011_add_data_sources
Revises: 010_workflow_runs_enhancement
Create Date: 2025-08-04

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '011_add_data_sources_tables'
down_revision = '010_workflow_runs_enhancement'
branch_labels = None
depends_on = None


def upgrade():
    # Create data_sources table
    op.create_table('data_sources',
        sa.Column('data_source_id', postgresql.UUID(as_uuid=True), nullable=False, 
                  server_default=sa.text('gen_random_uuid()')),
        sa.Column('org_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('name', sa.Text(), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('file_name', sa.Text(), nullable=False),
        sa.Column('file_type', sa.Text(), nullable=False),
        sa.Column('file_size', sa.BigInteger(), nullable=False),
        sa.Column('s3_bucket', sa.Text(), nullable=False),
        sa.Column('s3_key', sa.Text(), nullable=False),
        sa.Column('row_count', sa.Integer(), nullable=True),
        sa.Column('column_count', sa.Integer(), nullable=True),
        sa.Column('status', sa.Text(), nullable=False, server_default='processing'),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('uploaded_by', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, 
                  server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, 
                  server_default=sa.text('now()')),
        sa.PrimaryKeyConstraint('data_source_id'),
        sa.ForeignKeyConstraint(['org_id'], ['organization.org_id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['uploaded_by'], ['app_user.user_id'], ondelete='CASCADE'),
        sa.CheckConstraint("file_type IN ('excel', 'csv')", name='ck_data_source_file_type'),
        sa.CheckConstraint("status IN ('processing', 'active', 'failed', 'archived')", 
                          name='ck_data_source_status')
    )
    op.create_index('idx_data_sources_org_id', 'data_sources', ['org_id'])
    op.create_index('idx_data_sources_status', 'data_sources', ['status'])

    # Create data_source_columns table
    op.create_table('data_source_columns',
        sa.Column('column_id', postgresql.UUID(as_uuid=True), nullable=False,
                  server_default=sa.text('gen_random_uuid()')),
        sa.Column('data_source_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('source_column_name', sa.Text(), nullable=False),
        sa.Column('source_column_index', sa.Integer(), nullable=False),
        sa.Column('target_field', sa.Text(), nullable=True),
        sa.Column('transform', sa.Text(), nullable=False, server_default='none'),
        sa.Column('data_type', sa.Text(), nullable=True),
        sa.Column('sample_values', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text('now()')),
        sa.PrimaryKeyConstraint('column_id'),
        sa.ForeignKeyConstraint(['data_source_id'], ['data_sources.data_source_id'], 
                               ondelete='CASCADE'),
        sa.CheckConstraint("transform IN ('none', 'uppercase', 'lowercase', 'trim', 'date')",
                          name='ck_column_transform'),
        sa.UniqueConstraint('data_source_id', 'source_column_name', 
                           name='uq_data_source_column_name')
    )
    op.create_index('idx_data_source_columns_data_source_id', 'data_source_columns', 
                    ['data_source_id'])

    # Create data_source_workbook table for Excel workbook data (cached)
    op.create_table('data_source_workbook',
        sa.Column('workbook_id', postgresql.UUID(as_uuid=True), nullable=False,
                  server_default=sa.text('gen_random_uuid()')),
        sa.Column('data_source_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('sheet_name', sa.Text(), nullable=False),
        sa.Column('data', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('row_count', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text('now()')),
        sa.PrimaryKeyConstraint('workbook_id'),
        sa.ForeignKeyConstraint(['data_source_id'], ['data_sources.data_source_id'],
                               ondelete='CASCADE'),
        sa.UniqueConstraint('data_source_id', name='uq_data_source_workbook')
    )
    op.create_index('idx_data_source_workbook_data_source_id', 'data_source_workbook',
                    ['data_source_id'])

    # Create workflow_data_sources table (many-to-many relationship)
    op.create_table('workflow_data_sources',
        sa.Column('workflow_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('data_source_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text('now()')),
        sa.PrimaryKeyConstraint('workflow_id', 'data_source_id'),
        sa.ForeignKeyConstraint(['workflow_id'], ['user_workflow.workflow_id'],
                               ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['data_source_id'], ['data_sources.data_source_id'],
                               ondelete='CASCADE')
    )

    # Add triggers for updated_at
    op.execute("""
        CREATE TRIGGER update_data_sources_updated_at 
        BEFORE UPDATE ON data_sources 
        FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
    """)
    
    op.execute("""
        CREATE TRIGGER update_data_source_columns_updated_at 
        BEFORE UPDATE ON data_source_columns 
        FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
    """)
    
    op.execute("""
        CREATE TRIGGER update_data_source_workbook_updated_at 
        BEFORE UPDATE ON data_source_workbook 
        FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
    """)


def downgrade():
    # Drop triggers
    op.execute('DROP TRIGGER IF EXISTS update_data_sources_updated_at ON data_sources')
    op.execute('DROP TRIGGER IF EXISTS update_data_source_columns_updated_at ON data_source_columns')
    op.execute('DROP TRIGGER IF EXISTS update_data_source_workbook_updated_at ON data_source_workbook')
    
    # Drop tables
    op.drop_table('workflow_data_sources')
    op.drop_table('data_source_workbook')
    op.drop_table('data_source_columns')
    op.drop_table('data_sources')