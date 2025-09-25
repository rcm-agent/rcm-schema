"""add comprehensive BPO task domain and action enums

Revision ID: 005
Revises: 004
Create Date: 2025-01-29

This migration adds comprehensive BPO-focused task domains and actions that are
commonly outsourced by hospitals to overseas teams (credentialing, billing firms, etc.)
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '005_add_comprehensive_bpo_task_enums'
down_revision = '004_update_task_action_enum_industry_standards'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add comprehensive BPO task domains and actions."""
    
    # Step 1: Create new task_domain enum with BPO-focused domains
    op.execute("""
        CREATE TYPE task_domain_new AS ENUM (
            -- Existing domains
            'eligibility',      -- Insurance eligibility verification
            'claim',            -- Claims processing and management
            'prior_auth',       -- Prior authorization
            
            -- New BPO-focused domains
            'credentialing',    -- Provider credentialing and enrollment
            'coding',           -- Medical coding (ICD-10, CPT, HCPCS)
            'charge_capture',   -- Charge entry and capture
            'denial_mgmt',      -- Denial management and appeals
            'payment_posting',  -- Payment posting and reconciliation
            'ar_followup',      -- Accounts receivable follow-up
            'patient_access'    -- Patient registration and demographics
        )
    """)
    
    # Step 2: Update task domain column
    op.execute("""
        ALTER TABLE task_type 
        ALTER COLUMN domain TYPE TEXT
    """)
    
    op.execute("""
        ALTER TABLE task_type 
        ALTER COLUMN domain TYPE task_domain_new
        USING domain::task_domain_new
    """)
    
    # Handle task_signature table if it exists
    op.execute("""
        DO $$ 
        BEGIN
            IF EXISTS (
                SELECT 1 FROM information_schema.columns 
                WHERE table_name = 'task_signature' 
                AND column_name = 'domain'
            ) THEN
                ALTER TABLE task_signature 
                ALTER COLUMN domain TYPE TEXT;
                
                ALTER TABLE task_signature 
                ALTER COLUMN domain TYPE task_domain_new
                USING domain::task_domain_new;
            END IF;
        END $$;
    """)
    
    # Step 3: Drop old enum and rename new one
    op.execute("DROP TYPE task_domain")
    op.execute("ALTER TYPE task_domain_new RENAME TO task_domain")
    
    # Step 4: Create comprehensive task_action enum for BPO processes
    op.execute("""
        CREATE TYPE task_action_bpo AS ENUM (
            -- Eligibility Actions (270/271)
            'verify',                   -- Real-time eligibility verification
            'batch_verify',             -- Batch eligibility processing
            'benefits_breakdown',       -- Detailed benefits analysis
            'coverage_discovery',       -- Find unknown coverage
            
            -- Prior Authorization Actions (278)
            'request',                  -- Initial auth request
            'submit',                   -- Submit with clinical documentation
            'inquire',                  -- Check auth status
            'appeal',                   -- Appeal denied authorization
            'extend',                   -- Request extension
            'expedite',                 -- Expedited/urgent auth
            
            -- Claim Actions (837/276/277)
            'claim_submit',             -- Submit new claim (837)
            'claim_inquire',            -- Check claim status (276/277)
            'claim_correct',            -- Correct and resubmit
            'claim_appeal',             -- Appeal claim denial
            'claim_void',               -- Void submitted claim
            
            -- Credentialing Actions
            'provider_enroll',          -- Initial provider enrollment
            'credential_verify',        -- Verify provider credentials
            'privilege_update',         -- Update hospital privileges
            'revalidate',              -- Periodic revalidation
            'caqh_update',             -- Update CAQH profile
            
            -- Coding Actions
            'assign_codes',             -- Assign ICD-10/CPT codes
            'audit_codes',              -- Audit coding accuracy
            'query_physician',          -- Query for clarification
            'code_review',              -- Peer review coding
            
            -- Charge Capture Actions
            'charge_entry',             -- Enter charges
            'charge_audit',             -- Audit charges
            'charge_reconcile',         -- Reconcile with clinical documentation
            
            -- Denial Management Actions
            'denial_review',            -- Review denial reason
            'denial_appeal',            -- Submit appeal
            'denial_followup',          -- Follow up on appeal
            'denial_prevent',           -- Preventive analysis
            
            -- Payment Posting Actions
            'post_era',                 -- Post electronic remittance (835)
            'post_manual',              -- Manual payment posting
            'reconcile_payment',        -- Reconcile payments
            'identify_variance',        -- Identify payment variances
            
            -- AR Follow-up Actions
            'ar_review',                -- Review aging accounts
            'ar_followup',              -- Follow up on unpaid claims
            'ar_appeal',                -- Appeal for AR resolution
            'ar_writeoff',              -- Recommend write-offs
            
            -- Patient Access Actions
            'register_patient',         -- Patient registration
            'verify_demographics',      -- Verify patient information
            'insurance_discovery',      -- Discover insurance coverage
            'estimate_copay',           -- Estimate patient responsibility
            
            -- Legacy actions (backward compatibility)
            'status_check',             -- DEPRECATED
            'denial_follow_up'          -- DEPRECATED: Use denial_followup
        )
    """)
    
    # Step 5: Migrate existing task_action to new comprehensive enum
    op.execute("""
        ALTER TABLE task_type 
        ALTER COLUMN action TYPE TEXT
    """)
    
    # Map old actions to new BPO-focused actions
    op.execute("""
        UPDATE task_type
        SET action = CASE
            WHEN domain = 'eligibility' AND action = 'verify' THEN 'verify'
            WHEN domain = 'eligibility' AND action = 'status_check' THEN 'verify'
            WHEN domain = 'claim' AND action = 'inquire' THEN 'claim_inquire'
            WHEN domain = 'claim' AND action = 'status_check' THEN 'claim_inquire'
            WHEN domain = 'claim' AND action = 'submit' THEN 'claim_submit'
            WHEN domain = 'prior_auth' AND action = 'submit' THEN 'submit'
            WHEN domain = 'prior_auth' AND action = 'request' THEN 'request'
            WHEN action = 'denial_follow_up' THEN 'denial_followup'
            ELSE action
        END
    """)
    
    op.execute("""
        ALTER TABLE task_type 
        ALTER COLUMN action TYPE task_action_bpo
        USING action::task_action_bpo
    """)
    
    # Handle task_signature table
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
                    WHEN domain = 'eligibility' AND action = 'verify' THEN 'verify'
                    WHEN domain = 'eligibility' AND action = 'status_check' THEN 'verify'
                    WHEN domain = 'claim' AND action = 'inquire' THEN 'claim_inquire'
                    WHEN domain = 'claim' AND action = 'status_check' THEN 'claim_inquire'
                    WHEN domain = 'claim' AND action = 'submit' THEN 'claim_submit'
                    WHEN domain = 'prior_auth' AND action = 'submit' THEN 'submit'
                    WHEN domain = 'prior_auth' AND action = 'request' THEN 'request'
                    WHEN action = 'denial_follow_up' THEN 'denial_followup'
                    ELSE action
                END;
                
                ALTER TABLE task_signature 
                ALTER COLUMN action TYPE task_action_bpo
                USING action::task_action_bpo;
            END IF;
        END $$;
    """)
    
    # Step 6: Drop old task_action enum and rename new one
    op.execute("DROP TYPE task_action")
    op.execute("ALTER TYPE task_action_bpo RENAME TO task_action")
    
    # Step 7: Create BPO process mapping table
    op.create_table('bpo_process_mapping',
        sa.Column('process_id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('domain', sa.Text(), nullable=False),
        sa.Column('action', sa.Text(), nullable=False),
        sa.Column('process_name', sa.Text(), nullable=False),
        sa.Column('hipaa_transaction', sa.Text(), nullable=True),
        sa.Column('typical_sla_hours', sa.Integer(), nullable=True),
        sa.Column('complexity_level', sa.Text(), nullable=True),
        sa.Column('required_skills', postgresql.JSONB(), nullable=True),
        sa.Column('common_systems', postgresql.JSONB(), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint('process_id'),
        sa.UniqueConstraint('domain', 'action')
    )
    
    # Insert BPO process mappings
    op.execute("""
        INSERT INTO bpo_process_mapping (domain, action, process_name, hipaa_transaction, typical_sla_hours, complexity_level, description) VALUES
        -- Eligibility processes
        ('eligibility', 'verify', 'Insurance Verification', '270/271', 24, 'low', 'Verify patient insurance coverage and benefits'),
        ('eligibility', 'batch_verify', 'Batch Eligibility Processing', '270/271', 48, 'medium', 'Process bulk eligibility verifications'),
        ('eligibility', 'benefits_breakdown', 'Benefits Analysis', NULL, 24, 'medium', 'Detailed breakdown of coverage limits and patient responsibility'),
        
        -- Prior Authorization processes
        ('prior_auth', 'request', 'Authorization Request', '278', 48, 'high', 'Initial prior authorization request with clinical documentation'),
        ('prior_auth', 'inquire', 'Auth Status Check', '278', 24, 'low', 'Check status of submitted authorizations'),
        ('prior_auth', 'appeal', 'Authorization Appeal', NULL, 72, 'high', 'Appeal denied authorizations with additional documentation'),
        
        -- Claims processes
        ('claim', 'claim_submit', 'Claim Submission', '837', 48, 'medium', 'Submit claims to payers'),
        ('claim', 'claim_inquire', 'Claim Status Inquiry', '276/277', 24, 'low', 'Check claim processing status'),
        ('claim', 'claim_correct', 'Claim Correction', NULL, 48, 'medium', 'Correct and resubmit rejected claims'),
        
        -- Credentialing processes
        ('credentialing', 'provider_enroll', 'Provider Enrollment', NULL, 720, 'high', 'Complete provider enrollment with payers'),
        ('credentialing', 'credential_verify', 'Credential Verification', NULL, 168, 'high', 'Verify provider licenses, education, and certifications'),
        
        -- Coding processes
        ('coding', 'assign_codes', 'Medical Coding', NULL, 24, 'high', 'Assign ICD-10, CPT, and HCPCS codes'),
        ('coding', 'audit_codes', 'Coding Audit', NULL, 48, 'high', 'Quality audit of assigned codes'),
        
        -- Denial Management
        ('denial_mgmt', 'denial_review', 'Denial Analysis', NULL, 24, 'medium', 'Analyze denial reasons and determine appeal strategy'),
        ('denial_mgmt', 'denial_appeal', 'Denial Appeal', NULL, 72, 'high', 'Prepare and submit denial appeals'),
        
        -- Payment Posting
        ('payment_posting', 'post_era', 'ERA Posting', '835', 24, 'medium', 'Post electronic remittance advice'),
        ('payment_posting', 'reconcile_payment', 'Payment Reconciliation', NULL, 48, 'medium', 'Reconcile payments with claims'),
        
        -- AR Follow-up
        ('ar_followup', 'ar_review', 'AR Analysis', NULL, 24, 'medium', 'Review aging accounts receivable'),
        ('ar_followup', 'ar_followup', 'AR Follow-up', NULL, 48, 'medium', 'Follow up on unpaid claims with payers')
    """)


def downgrade() -> None:
    """Revert to original limited enums."""
    
    # Drop BPO mapping table
    op.drop_table('bpo_process_mapping')
    
    # Revert task_action enum
    op.execute("""
        CREATE TYPE task_action_old AS ENUM (
            'verify', 'inquire', 'submit', 'request', 
            'denial_follow_up', 'status_check'
        )
    """)
    
    op.execute("ALTER TABLE task_type ALTER COLUMN action TYPE TEXT")
    
    # Reverse mappings
    op.execute("""
        UPDATE task_type
        SET action = CASE
            WHEN action = 'claim_submit' THEN 'submit'
            WHEN action = 'claim_inquire' THEN 'inquire'
            WHEN action = 'denial_followup' THEN 'denial_follow_up'
            WHEN action IN ('verify', 'inquire', 'submit', 'request', 'denial_follow_up', 'status_check') THEN action
            ELSE 'status_check'
        END
    """)
    
    op.execute("ALTER TABLE task_type ALTER COLUMN action TYPE task_action_old USING action::task_action_old")
    op.execute("DROP TYPE task_action")
    op.execute("ALTER TYPE task_action_old RENAME TO task_action")
    
    # Revert task_domain enum
    op.execute("CREATE TYPE task_domain_old AS ENUM ('eligibility', 'claim', 'prior_auth')")
    op.execute("ALTER TABLE task_type ALTER COLUMN domain TYPE TEXT")
    
    # Remove new domains
    op.execute("""
        DELETE FROM task_type 
        WHERE domain NOT IN ('eligibility', 'claim', 'prior_auth')
    """)
    
    op.execute("ALTER TABLE task_type ALTER COLUMN domain TYPE task_domain_old USING domain::task_domain_old")
    op.execute("DROP TYPE task_domain")
    op.execute("ALTER TYPE task_domain_old RENAME TO task_domain")