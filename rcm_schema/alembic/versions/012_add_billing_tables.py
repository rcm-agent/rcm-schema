"""add billing tables

Revision ID: 012
Revises: 011
Create Date: 2025-08-04

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
import uuid

# revision identifiers
revision = '012_add_billing_tables'
down_revision = '011_add_data_sources_tables'
branch_labels = None
depends_on = None


def upgrade():
    # Create billing enum types
    op.execute("""
        CREATE TYPE subscription_status AS ENUM (
            'active', 'canceled', 'past_due', 'trialing', 'incomplete', 'incomplete_expired'
        );
        
        CREATE TYPE payment_status AS ENUM (
            'pending', 'succeeded', 'failed', 'refunded'
        );
        
        CREATE TYPE billing_interval AS ENUM (
            'monthly', 'yearly'
        );
    """)
    
    # Organizations billing table - extends organizations with billing info
    op.create_table('organizations_billing',
        sa.Column('org_billing_id', sa.UUID(), nullable=False, default=uuid.uuid4),
        sa.Column('org_id', sa.UUID(), nullable=False),
        sa.Column('stripe_customer_id', sa.String(255), nullable=True),
        sa.Column('stripe_subscription_id', sa.String(255), nullable=True),
        sa.Column('stripe_payment_method_id', sa.String(255), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('org_billing_id'),
        sa.ForeignKeyConstraint(['org_id'], ['organizations.org_id'], ),
        sa.UniqueConstraint('org_id'),
        sa.UniqueConstraint('stripe_customer_id')
    )
    op.create_index('idx_organizations_billing_org_id', 'organizations_billing', ['org_id'])
    op.create_index('idx_organizations_billing_stripe_customer_id', 'organizations_billing', ['stripe_customer_id'])
    
    # Subscription plans table
    op.create_table('subscription_plans',
        sa.Column('plan_id', sa.UUID(), nullable=False, default=uuid.uuid4),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('display_name', sa.String(100), nullable=False),
        sa.Column('stripe_product_id', sa.String(255), nullable=True),
        sa.Column('stripe_price_id_monthly', sa.String(255), nullable=True),
        sa.Column('stripe_price_id_yearly', sa.String(255), nullable=True),
        sa.Column('price_monthly', sa.Numeric(10, 2), nullable=False),
        sa.Column('price_yearly', sa.Numeric(10, 2), nullable=False),
        sa.Column('features', sa.JSON(), nullable=False, default={}),
        sa.Column('limits', sa.JSON(), nullable=False, default={}),
        sa.Column('is_active', sa.Boolean(), nullable=False, default=True),
        sa.Column('sort_order', sa.Integer(), nullable=False, default=0),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('plan_id'),
        sa.UniqueConstraint('name'),
        sa.UniqueConstraint('stripe_product_id')
    )
    
    # Organization subscriptions table
    op.create_table('organization_subscriptions',
        sa.Column('subscription_id', sa.UUID(), nullable=False, default=uuid.uuid4),
        sa.Column('org_id', sa.UUID(), nullable=False),
        sa.Column('plan_id', sa.UUID(), nullable=False),
        sa.Column('stripe_subscription_id', sa.String(255), nullable=True),
        sa.Column('status', postgresql.ENUM('active', 'canceled', 'past_due', 'trialing', 'incomplete', 'incomplete_expired', name='subscription_status'), nullable=False),
        sa.Column('billing_interval', postgresql.ENUM('monthly', 'yearly', name='billing_interval'), nullable=False),
        sa.Column('current_period_start', sa.DateTime(timezone=True), nullable=True),
        sa.Column('current_period_end', sa.DateTime(timezone=True), nullable=True),
        sa.Column('cancel_at_period_end', sa.Boolean(), nullable=False, default=False),
        sa.Column('canceled_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('trial_start', sa.DateTime(timezone=True), nullable=True),
        sa.Column('trial_end', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('subscription_id'),
        sa.ForeignKeyConstraint(['org_id'], ['organizations.org_id'], ),
        sa.ForeignKeyConstraint(['plan_id'], ['subscription_plans.plan_id'], ),
        sa.UniqueConstraint('stripe_subscription_id')
    )
    op.create_index('idx_organization_subscriptions_org_id', 'organization_subscriptions', ['org_id'])
    op.create_index('idx_organization_subscriptions_status', 'organization_subscriptions', ['status'])
    
    # Billing usage table for tracking usage-based billing
    op.create_table('billing_usage',
        sa.Column('usage_id', sa.UUID(), nullable=False, default=uuid.uuid4),
        sa.Column('org_id', sa.UUID(), nullable=False),
        sa.Column('subscription_id', sa.UUID(), nullable=True),
        sa.Column('metric_name', sa.String(100), nullable=False),
        sa.Column('quantity', sa.Integer(), nullable=False),
        sa.Column('unit_amount', sa.Numeric(10, 4), nullable=True),
        sa.Column('total_amount', sa.Numeric(10, 2), nullable=True),
        sa.Column('period_start', sa.DateTime(timezone=True), nullable=False),
        sa.Column('period_end', sa.DateTime(timezone=True), nullable=False),
        sa.Column('metadata', sa.JSON(), nullable=True),
        sa.Column('reported_to_stripe', sa.Boolean(), nullable=False, default=False),
        sa.Column('stripe_usage_record_id', sa.String(255), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('usage_id'),
        sa.ForeignKeyConstraint(['org_id'], ['organizations.org_id'], ),
        sa.ForeignKeyConstraint(['subscription_id'], ['organization_subscriptions.subscription_id'], )
    )
    op.create_index('idx_billing_usage_org_id', 'billing_usage', ['org_id'])
    op.create_index('idx_billing_usage_period', 'billing_usage', ['period_start', 'period_end'])
    op.create_index('idx_billing_usage_metric', 'billing_usage', ['metric_name'])
    
    # Invoices table
    op.create_table('invoices',
        sa.Column('invoice_id', sa.UUID(), nullable=False, default=uuid.uuid4),
        sa.Column('org_id', sa.UUID(), nullable=False),
        sa.Column('subscription_id', sa.UUID(), nullable=True),
        sa.Column('stripe_invoice_id', sa.String(255), nullable=True),
        sa.Column('invoice_number', sa.String(100), nullable=True),
        sa.Column('status', postgresql.ENUM('pending', 'succeeded', 'failed', 'refunded', name='payment_status'), nullable=False),
        sa.Column('amount_due', sa.Numeric(10, 2), nullable=False),
        sa.Column('amount_paid', sa.Numeric(10, 2), nullable=False, default=0),
        sa.Column('currency', sa.String(3), nullable=False, default='USD'),
        sa.Column('period_start', sa.DateTime(timezone=True), nullable=False),
        sa.Column('period_end', sa.DateTime(timezone=True), nullable=False),
        sa.Column('due_date', sa.DateTime(timezone=True), nullable=True),
        sa.Column('paid_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('invoice_pdf_url', sa.Text(), nullable=True),
        sa.Column('hosted_invoice_url', sa.Text(), nullable=True),
        sa.Column('line_items', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('invoice_id'),
        sa.ForeignKeyConstraint(['org_id'], ['organizations.org_id'], ),
        sa.ForeignKeyConstraint(['subscription_id'], ['organization_subscriptions.subscription_id'], ),
        sa.UniqueConstraint('stripe_invoice_id'),
        sa.UniqueConstraint('invoice_number')
    )
    op.create_index('idx_invoices_org_id', 'invoices', ['org_id'])
    op.create_index('idx_invoices_status', 'invoices', ['status'])
    op.create_index('idx_invoices_period', 'invoices', ['period_start', 'period_end'])
    
    # Insert default subscription plans
    op.execute("""
        INSERT INTO subscription_plans (plan_id, name, display_name, price_monthly, price_yearly, features, limits, sort_order)
        VALUES 
        (gen_random_uuid(), 'basic', 'Basic', 49.00, 490.00, 
         '{"workflows": 10, "users": 5, "data_sources": 10, "workflow_runs": 1000, "support": "email"}',
         '{"max_workflows": 10, "max_users": 5, "max_data_sources": 10, "max_workflow_runs_per_month": 1000}',
         1),
        (gen_random_uuid(), 'professional', 'Professional', 199.00, 1990.00,
         '{"workflows": 50, "users": 20, "data_sources": 50, "workflow_runs": 10000, "support": "priority", "api_access": true}',
         '{"max_workflows": 50, "max_users": 20, "max_data_sources": 50, "max_workflow_runs_per_month": 10000}',
         2),
        (gen_random_uuid(), 'enterprise', 'Enterprise', 999.00, 9990.00,
         '{"workflows": -1, "users": -1, "data_sources": -1, "workflow_runs": -1, "support": "dedicated", "api_access": true, "sso": true, "custom_integrations": true}',
         '{"max_workflows": -1, "max_users": -1, "max_data_sources": -1, "max_workflow_runs_per_month": -1}',
         3);
    """)


def downgrade():
    # Drop tables in reverse order
    op.drop_table('invoices')
    op.drop_table('billing_usage')
    op.drop_table('organization_subscriptions')
    op.drop_table('subscription_plans')
    op.drop_table('organizations_billing')
    
    # Drop enum types
    op.execute('DROP TYPE IF EXISTS payment_status;')
    op.execute('DROP TYPE IF EXISTS billing_interval;')
    op.execute('DROP TYPE IF EXISTS subscription_status;')