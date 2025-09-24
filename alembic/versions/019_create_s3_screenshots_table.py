"""Create S3 screenshots table

Revision ID: 017_create_s3_screenshots_table
Revises: 013_add_user_invitations
Create Date: 2025-08-13 14:57:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB


# revision identifiers, used by Alembic.
revision: str = '019_create_s3_screenshots_table'
down_revision = '018_consolidate_workflow_tables'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # TEMPORARY TEMP-20250813-146000-TABLE: Create new table for S3 screenshot storage
    op.create_table('s3_screenshots',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('workflow_run_id', UUID(as_uuid=True), nullable=True, index=True),
        sa.Column('step_number', sa.Integer(), nullable=True),
        sa.Column('screenshot_s3_key', sa.Text(), nullable=False, comment='S3 object key for screenshot storage'),
        sa.Column('screenshot_url', sa.Text(), nullable=True, comment='S3 or CloudFront URL for screenshot access'),
        sa.Column('content_sha256', sa.String(64), nullable=True, comment='SHA256 hash of screenshot for integrity verification'),
        sa.Column('s3_etag', sa.String(255), nullable=True, comment='S3 ETag for version tracking'),
        sa.Column('size_bytes', sa.BigInteger(), nullable=True, comment='Size of screenshot file in bytes'),
        sa.Column('content_type', sa.String(100), nullable=False, server_default='image/png', comment='MIME type of screenshot'),
        sa.Column('thumbnail_s3_key', sa.Text(), nullable=True, comment='S3 object key for thumbnail (optional)'),
        sa.Column('metadata', JSONB, nullable=True, server_default=sa.text("'{}'::jsonb"), comment='Additional metadata'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.Column('migrated_at', sa.DateTime(timezone=True), nullable=True, comment='Timestamp when screenshot was migrated to S3'),
        sa.Column('legacy_base64', sa.Text(), nullable=True, comment='Original base64 data for migration rollback')
    )
    
    # Create indexes for performance
    op.create_index('idx_s3_screenshots_s3_key', 's3_screenshots', ['screenshot_s3_key'])
    op.create_index('idx_s3_screenshots_workflow_run', 's3_screenshots', ['workflow_run_id', 'step_number'])
    op.create_index('idx_s3_screenshots_created', 's3_screenshots', ['created_at'])


def downgrade() -> None:
    # Drop indexes
    op.drop_index('idx_s3_screenshots_created', 's3_screenshots')
    op.drop_index('idx_s3_screenshots_workflow_run', 's3_screenshots')
    op.drop_index('idx_s3_screenshots_s3_key', 's3_screenshots')
    
    # Drop table
    op.drop_table('s3_screenshots')