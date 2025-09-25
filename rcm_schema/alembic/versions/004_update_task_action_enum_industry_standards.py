"""update task_action enum to industry standards

Revision ID: 004
Revises: 003
Create Date: 2025-01-29

This migration updates the task_action enum to use industry-standard RCM terminology:
- Changes 'status_check' to 'verify' for eligibility domain
- Adds 'inquire' for claim status checks
- Keeps backward compatibility with mapping
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '004_update_task_action_enum_industry_standards'
down_revision = '003_add_hierarchical_requirements_system'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Update task_action enum to use industry-standard terminology."""
    
    # Step 1: Create new enum type with industry-standard values
    op.execute("""
        CREATE TYPE task_action_new AS ENUM (
            'verify',           -- Industry standard for eligibility verification
            'inquire',          -- Industry standard for claim status inquiry
            'submit',           -- Submit prior auth or claim
            'request',          -- Request prior authorization
            'denial_follow_up', -- Follow up on denials
            'status_check'      -- Keep for backward compatibility (deprecated)
        )
    """)
    
    # Step 2: Update task_type table to use new enum
    # First, alter column to text temporarily
    op.execute("""
        ALTER TABLE task_type 
        ALTER COLUMN action TYPE TEXT
    """)
    
    # Step 3: Update existing values to industry standards
    op.execute("""
        UPDATE task_type
        SET action = CASE
            -- Eligibility domain should use 'verify'
            WHEN domain = 'eligibility' AND action = 'status_check' THEN 'verify'
            -- Claim domain should use 'inquire' for status checks
            WHEN domain = 'claim' AND action = 'status_check' THEN 'inquire'
            -- Keep other values as is
            ELSE action
        END
    """)
    
    # Step 4: Convert column to new enum type
    op.execute("""
        ALTER TABLE task_type 
        ALTER COLUMN action TYPE task_action_new
        USING action::task_action_new
    """)
    
    # Step 5: Drop old enum and rename new one
    op.execute("DROP TYPE task_action")
    op.execute("ALTER TYPE task_action_new RENAME TO task_action")
    
    # Step 6: Update task_signature table (if it has task_action column)
    op.execute("""
        DO $$ 
        BEGIN
            IF EXISTS (
                SELECT 1 FROM information_schema.columns 
                WHERE table_name = 'task_signature' 
                AND column_name = 'action'
            ) THEN
                -- Update task_signature table
                ALTER TABLE task_signature 
                ALTER COLUMN action TYPE TEXT;
                
                UPDATE task_signature
                SET action = CASE
                    WHEN domain = 'eligibility' AND action = 'status_check' THEN 'verify'
                    WHEN domain = 'claim' AND action = 'status_check' THEN 'inquire'
                    ELSE action
                END;
                
                ALTER TABLE task_signature 
                ALTER COLUMN action TYPE task_action
                USING action::task_action;
            END IF;
        END $$;
    """)
    
    # Step 7: Create mapping table for backward compatibility
    op.create_table('task_action_mapping',
        sa.Column('legacy_action', sa.Text(), nullable=False),
        sa.Column('standard_action', sa.Text(), nullable=False),
        sa.Column('domain', sa.Text(), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint('legacy_action', 'domain')
    )
    
    # Insert mapping data
    op.execute("""
        INSERT INTO task_action_mapping (legacy_action, standard_action, domain, description) VALUES
        ('status_check', 'verify', 'eligibility', 'HIPAA X12 270/271 Eligibility Verification'),
        ('status_check', 'inquire', 'claim', 'HIPAA X12 276/277 Claim Status Inquiry'),
        ('check', 'verify', 'eligibility', 'Legacy term for eligibility verification'),
        ('check_status', 'inquire', 'claim', 'Legacy term for claim status inquiry')
    """)


def downgrade() -> None:
    """Revert to original task_action enum values."""
    
    # Step 1: Drop mapping table
    op.drop_table('task_action_mapping')
    
    # Step 2: Create old enum type
    op.execute("""
        CREATE TYPE task_action_old AS ENUM (
            'status_check',
            'submit',
            'denial_follow_up'
        )
    """)
    
    # Step 3: Update task_type table
    op.execute("""
        ALTER TABLE task_type 
        ALTER COLUMN action TYPE TEXT
    """)
    
    # Step 4: Revert values to original
    op.execute("""
        UPDATE task_type
        SET action = CASE
            WHEN domain = 'eligibility' AND action = 'verify' THEN 'status_check'
            WHEN domain = 'claim' AND action = 'inquire' THEN 'status_check'
            WHEN action = 'request' THEN 'submit'  -- Revert request to submit
            ELSE action
        END
    """)
    
    # Step 5: Convert column to old enum type
    op.execute("""
        ALTER TABLE task_type 
        ALTER COLUMN action TYPE task_action_old
        USING action::task_action_old
    """)
    
    # Step 6: Handle task_signature table
    op.execute("""
        DO $$ 
        BEGIN
            IF EXISTS (
                SELECT 1 FROM information_schema.columns 
                WHERE table_name = 'task_signature' 
                AND column_name = 'action'
            ) THEN
                ALTER TABLE task_signature 
                ALTER COLUMN action TYPE TEXT;
                
                UPDATE task_signature
                SET action = CASE
                    WHEN domain = 'eligibility' AND action = 'verify' THEN 'status_check'
                    WHEN domain = 'claim' AND action = 'inquire' THEN 'status_check'
                    WHEN action = 'request' THEN 'submit'
                    ELSE action
                END;
                
                ALTER TABLE task_signature 
                ALTER COLUMN action TYPE task_action_old
                USING action::task_action_old;
            END IF;
        END $$;
    """)
    
    # Step 7: Drop new enum and rename old one
    op.execute("DROP TYPE task_action")
    op.execute("ALTER TYPE task_action_old RENAME TO task_action")