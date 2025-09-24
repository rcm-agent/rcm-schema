#!/usr/bin/env python3
"""
V8 Test Data Seeding Script
Creates sample data for testing the V8 schema
"""
import os
import sys
import asyncio
import random
from datetime import datetime, timedelta
from uuid import uuid4
import asyncpg
import numpy as np
from faker import Faker

# Configuration
DATABASE_URL = os.getenv('DATABASE_URL', 'postgresql://postgres:postgres@localhost:5432/rcm_db')
fake = Faker()

# Sample data templates
CHANNEL_TYPES = [
    {
        'channel_name': 'web',
        'auth_type': 'none',
        'config_template': {
            'browser': 'chrome',
            'viewport': {'width': 1920, 'height': 1080}
        }
    },
    {
        'channel_name': 'api',
        'auth_type': 'bearer',
        'config_template': {
            'timeout': 30,
            'retry_count': 3,
            'rate_limit': 100
        }
    },
    {
        'channel_name': 'mobile',
        'auth_type': 'oauth2',
        'config_template': {
            'platform': ['ios', 'android'],
            'min_version': '1.0.0'
        }
    }
]

WORKFLOW_TEMPLATES = [
    {
        'name': 'Customer Onboarding',
        'description': 'Automated customer registration and verification',
        'nodes': [
            {'code': 'start', 'name': 'Start', 'order': 1},
            {'code': 'collect_info', 'name': 'Collect Information', 'order': 2},
            {'code': 'verify_email', 'name': 'Verify Email', 'order': 3},
            {'code': 'kyc_check', 'name': 'KYC Verification', 'order': 3},
            {'code': 'create_account', 'name': 'Create Account', 'order': 4},
            {'code': 'send_welcome', 'name': 'Send Welcome Email', 'order': 5},
            {'code': 'end', 'name': 'Complete', 'order': 6}
        ]
    },
    {
        'name': 'Order Processing',
        'description': 'E-commerce order fulfillment workflow',
        'nodes': [
            {'code': 'receive_order', 'name': 'Receive Order', 'order': 1},
            {'code': 'check_inventory', 'name': 'Check Inventory', 'order': 2},
            {'code': 'process_payment', 'name': 'Process Payment', 'order': 3},
            {'code': 'allocate_stock', 'name': 'Allocate Stock', 'order': 4},
            {'code': 'ship_order', 'name': 'Ship Order', 'order': 5},
            {'code': 'notify_customer', 'name': 'Notify Customer', 'order': 6}
        ]
    },
    {
        'name': 'Content Moderation',
        'description': 'AI-powered content review and approval',
        'nodes': [
            {'code': 'receive_content', 'name': 'Receive Content', 'order': 1},
            {'code': 'ai_review', 'name': 'AI Review', 'order': 2},
            {'code': 'human_review', 'name': 'Human Review', 'order': 3},
            {'code': 'publish', 'name': 'Publish Content', 'order': 4}
        ]
    }
]

MICRO_STATE_TEMPLATES = [
    {
        'category': 'form_interaction',
        'labels': ['login_form', 'registration_form', 'checkout_form', 'search_form'],
        'dom_patterns': [
            '<form><input type="email" /><input type="password" /></form>',
            '<form><input type="text" name="username" /><input type="email" /></form>',
            '<div class="checkout"><input type="text" name="card" /></div>',
            '<form><input type="search" placeholder="Search..." /></form>'
        ]
    },
    {
        'category': 'navigation',
        'labels': ['menu_click', 'tab_switch', 'page_navigation', 'breadcrumb'],
        'dom_patterns': [
            '<nav><ul><li><a href="/home">Home</a></li></ul></nav>',
            '<div class="tabs"><button class="active">Tab 1</button></div>',
            '<div class="pagination"><a href="?page=2">Next</a></div>',
            '<ol class="breadcrumb"><li>Home</li><li>Products</li></ol>'
        ]
    },
    {
        'category': 'data_display',
        'labels': ['table_view', 'card_grid', 'list_view', 'detail_view'],
        'dom_patterns': [
            '<table><thead><tr><th>Name</th><th>Value</th></tr></thead></table>',
            '<div class="grid"><div class="card">Item 1</div></div>',
            '<ul class="list"><li>Item 1</li><li>Item 2</li></ul>',
            '<div class="detail"><h1>Title</h1><p>Description</p></div>'
        ]
    }
]


class V8DataSeeder:
    """Seeds test data for V8 schema"""
    
    def __init__(self, db_url: str):
        self.db_url = db_url
        self.conn = None
        self.org_ids = []
        self.user_ids = []
        self.channel_type_ids = {}
        self.endpoint_ids = []
        self.workflow_ids = []
        
    async def connect(self):
        """Connect to database"""
        self.conn = await asyncpg.connect(self.db_url)
        
    async def disconnect(self):
        """Disconnect from database"""
        if self.conn:
            await self.conn.close()
    
    async def seed_all(self):
        """Run all seeding operations"""
        print("Starting V8 test data seeding...")
        
        # Seed in order of dependencies
        await self.seed_organizations()
        await self.seed_users()
        await self.seed_channel_types()
        await self.seed_endpoints()
        await self.seed_workflows()
        await self.seed_workflow_nodes()
        await self.seed_micro_states()
        await self.seed_batch_jobs()
        await self.seed_workflow_traces()
        
        print("\n✅ Test data seeding complete!")
        await self.print_summary()
    
    async def seed_organizations(self):
        """Create test organizations"""
        print("\n[1/9] Seeding organizations...")
        
        orgs = [
            ('Acme Corporation', 'enterprise', {'industry': 'technology', 'size': 'large'}),
            ('StartupXYZ', 'standard', {'industry': 'fintech', 'size': 'small'}),
            ('Global Retail Inc', 'enterprise', {'industry': 'retail', 'size': 'large'}),
            ('Local Services LLC', 'standard', {'industry': 'services', 'size': 'medium'}),
            ('Partner Solutions', 'partner', {'industry': 'consulting', 'size': 'medium'})
        ]
        
        for name, org_type, metadata in orgs:
            org_id = uuid4()
            await self.conn.execute("""
                INSERT INTO organization (org_id, org_type, name, metadata)
                VALUES ($1, $2, $3, $4)
                ON CONFLICT (name) DO NOTHING
            """, org_id, org_type, name, metadata)
            self.org_ids.append(org_id)
        
        print(f"  Created {len(self.org_ids)} organizations")
    
    async def seed_users(self):
        """Create test users"""
        print("\n[2/9] Seeding users...")
        
        for org_id in self.org_ids:
            # Create 5-10 users per org
            num_users = random.randint(5, 10)
            
            for i in range(num_users):
                user_id = uuid4()
                is_admin = i == 0  # First user is admin
                
                await self.conn.execute("""
                    INSERT INTO app_user (
                        user_id, org_id, email, username, 
                        first_name, last_name, is_active, is_admin
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                """, 
                    user_id, org_id,
                    fake.email(), fake.user_name(),
                    fake.first_name(), fake.last_name(),
                    True, is_admin
                )
                self.user_ids.append(user_id)
        
        print(f"  Created {len(self.user_ids)} users")
    
    async def seed_channel_types(self):
        """Create channel types"""
        print("\n[3/9] Seeding channel types...")
        
        for channel in CHANNEL_TYPES:
            result = await self.conn.fetchrow("""
                INSERT INTO channel_type (channel_name, auth_type, config_template)
                VALUES ($1, $2, $3)
                ON CONFLICT (channel_name) DO UPDATE
                SET config_template = EXCLUDED.config_template
                RETURNING channel_type_id
            """, channel['channel_name'], channel['auth_type'], channel['config_template'])
            
            self.channel_type_ids[channel['channel_name']] = result['channel_type_id']
        
        print(f"  Created {len(self.channel_type_ids)} channel types")
    
    async def seed_endpoints(self):
        """Create endpoints for each organization"""
        print("\n[4/9] Seeding endpoints...")
        
        endpoint_templates = [
            ('Production API', 'https://api.production.com', 'api'),
            ('Staging API', 'https://api.staging.com', 'api'),
            ('Company Website', 'https://www.company.com', 'web'),
            ('Mobile Backend', 'https://mobile.company.com', 'mobile'),
            ('Partner Portal', 'https://partners.company.com', 'web')
        ]
        
        for org_id in self.org_ids[:3]:  # Only first 3 orgs get endpoints
            for name, base_url, channel_name in endpoint_templates[:random.randint(2, 5)]:
                endpoint_id = await self.conn.fetchval("""
                    INSERT INTO endpoint (
                        org_id, channel_type_id, name, base_url,
                        auth_config, is_active
                    ) VALUES ($1, $2, $3, $4, $5, $6)
                    RETURNING endpoint_id
                """,
                    org_id,
                    self.channel_type_ids[channel_name],
                    f"{name} ({org_id.hex[:8]})",
                    base_url,
                    {'api_key': f'key_{uuid4().hex[:16]}'},
                    True
                )
                self.endpoint_ids.append(endpoint_id)
        
        print(f"  Created {len(self.endpoint_ids)} endpoints")
    
    async def seed_workflows(self):
        """Create workflows"""
        print("\n[5/9] Seeding workflows...")
        
        # Each org gets 2-3 workflows
        for org_id in self.org_ids:
            org_users = await self.conn.fetch("""
                SELECT user_id FROM app_user WHERE org_id = $1
            """, org_id)
            
            if not org_users:
                continue
            
            templates = random.sample(WORKFLOW_TEMPLATES, k=min(len(WORKFLOW_TEMPLATES), random.randint(2, 3)))
            
            for template in templates:
                workflow_id = uuid4()
                creator = random.choice(org_users)['user_id']
                
                await self.conn.execute("""
                    INSERT INTO user_workflow (
                        workflow_id, workflow_name, description,
                        status, created_by
                    ) VALUES ($1, $2, $3, $4, $5)
                """,
                    workflow_id,
                    f"{template['name']} ({org_id.hex[:8]})",
                    template['description'],
                    random.choice(['active', 'draft', 'paused']),
                    creator
                )
                
                self.workflow_ids.append({
                    'workflow_id': workflow_id,
                    'template': template,
                    'org_id': org_id
                })
        
        print(f"  Created {len(self.workflow_ids)} workflows")
    
    async def seed_workflow_nodes(self):
        """Create workflow nodes and transitions"""
        print("\n[6/9] Seeding workflow nodes and transitions...")
        
        total_nodes = 0
        total_transitions = 0
        
        for workflow_data in self.workflow_ids:
            workflow_id = workflow_data['workflow_id']
            template = workflow_data['template']
            
            node_ids = {}
            
            # Create nodes
            for node in template['nodes']:
                node_id = await self.conn.fetchval("""
                    INSERT INTO workflow_node (
                        workflow_id, code, name, parent_relation,
                        processing_order, config
                    ) VALUES ($1, $2, $3, $4, $5, $6)
                    RETURNING node_id
                """,
                    workflow_id,
                    node['code'],
                    node['name'],
                    'root' if node['order'] == 1 else 'child',
                    node['order'],
                    {'timeout': random.randint(30, 300)}
                )
                
                node_ids[node['code']] = node_id
                total_nodes += 1
            
            # Create transitions (linear flow with some parallel branches)
            nodes_by_order = sorted(template['nodes'], key=lambda x: x['order'])
            
            for i in range(len(nodes_by_order) - 1):
                current = nodes_by_order[i]
                
                # Find all nodes at next order level
                next_order = current['order'] + 1
                next_nodes = [n for n in nodes_by_order if n['order'] == next_order]
                
                for next_node in next_nodes:
                    await self.conn.execute("""
                        INSERT INTO workflow_transition (
                            workflow_id, from_node_id, to_node_id,
                            condition_type, condition_config, transition_order
                        ) VALUES ($1, $2, $3, $4, $5, $6)
                    """,
                        workflow_id,
                        node_ids[current['code']],
                        node_ids[next_node['code']],
                        'always',
                        {},
                        1
                    )
                    total_transitions += 1
        
        print(f"  Created {total_nodes} nodes and {total_transitions} transitions")
    
    async def seed_micro_states(self):
        """Create micro states with embeddings"""
        print("\n[7/9] Seeding micro states...")
        
        total_states = 0
        
        # Only create micro states for workflows with nodes
        for workflow_data in self.workflow_ids[:10]:  # Limit to first 10 workflows
            workflow_id = workflow_data['workflow_id']
            
            # Get nodes for this workflow
            nodes = await self.conn.fetch("""
                SELECT node_id, code FROM workflow_node 
                WHERE workflow_id = $1
            """, workflow_id)
            
            if not nodes:
                continue
            
            # Create 5-15 micro states per workflow
            num_states = random.randint(5, 15)
            
            for _ in range(num_states):
                node = random.choice(nodes)
                template = random.choice(MICRO_STATE_TEMPLATES)
                
                # Generate random 768-dimensional embedding
                embedding = np.random.randn(768).astype(np.float32)
                embedding = embedding / np.linalg.norm(embedding)  # Normalize
                
                label = random.choice(template['labels'])
                dom = random.choice(template['dom_patterns'])
                
                await self.conn.execute("""
                    INSERT INTO micro_state (
                        workflow_id, node_id, dom_snapshot, action_json,
                        semantic_spec, label, category, required,
                        is_dynamic, text_emb
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
                """,
                    workflow_id,
                    node['node_id'],
                    dom,
                    {
                        'action': random.choice(['click', 'type', 'select', 'wait']),
                        'target': f'element_{random.randint(1, 100)}'
                    },
                    {'confidence': random.random()},
                    label,
                    template['category'],
                    random.choice([True, False]),
                    random.choice([True, False]),
                    embedding.tolist()
                )
                total_states += 1
        
        print(f"  Created {total_states} micro states")
    
    async def seed_batch_jobs(self):
        """Create batch jobs"""
        print("\n[8/9] Seeding batch jobs...")
        
        task_types = ['data_import', 'report_generation', 'bulk_update', 'email_campaign', 'data_export']
        
        total_jobs = 0
        
        for org_id in self.org_ids:
            # Each org gets 2-5 batch jobs
            num_jobs = random.randint(2, 5)
            
            org_users = await self.conn.fetch("""
                SELECT user_id FROM app_user WHERE org_id = $1
            """, org_id)
            
            if not org_users:
                continue
            
            for _ in range(num_jobs):
                user_id = random.choice(org_users)['user_id']
                task_type = random.choice(task_types)
                
                # Generate items
                num_items = random.randint(10, 100)
                items = [
                    {'id': i, 'data': f'item_{i}', 'status': 'pending'}
                    for i in range(num_items)
                ]
                
                # Simulate job progress
                status = random.choice(['queued', 'processing', 'completed', 'failed'])
                completed = 0
                failed = 0
                
                if status in ['processing', 'completed', 'failed']:
                    completed = random.randint(0, num_items)
                    if status == 'failed':
                        failed = random.randint(1, max(1, num_items - completed))
                
                await self.conn.execute("""
                    INSERT INTO batch_job (
                        batch_job_id, org_id, user_id, task_type,
                        total_items, completed_items, failed_items,
                        status, input_data, metadata
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
                """,
                    uuid4(), org_id, user_id, task_type,
                    num_items, completed, failed, status,
                    {'items': items},
                    {'priority': random.choice(['low', 'normal', 'high'])}
                )
                total_jobs += 1
        
        print(f"  Created {total_jobs} batch jobs")
    
    async def seed_workflow_traces(self):
        """Create workflow execution traces"""
        print("\n[9/9] Seeding workflow traces...")
        
        total_traces = 0
        
        for workflow_data in self.workflow_ids:
            workflow_id = workflow_data['workflow_id']
            org_id = workflow_data['org_id']
            
            # Get users from this org
            org_users = await self.conn.fetch("""
                SELECT user_id FROM app_user WHERE org_id = $1
            """, org_id)
            
            if not org_users:
                continue
            
            # Create 10-30 traces per workflow
            num_traces = random.randint(10, 30)
            
            for i in range(num_traces):
                user_id = random.choice(org_users)['user_id']
                
                # Simulate execution over past 30 days
                created_at = datetime.utcnow() - timedelta(
                    days=random.randint(0, 30),
                    hours=random.randint(0, 23),
                    minutes=random.randint(0, 59)
                )
                
                success = random.random() > 0.1  # 90% success rate
                duration_ms = random.randint(100, 30000) if success else random.randint(50, 5000)
                
                await self.conn.execute("""
                    INSERT INTO workflow_trace (
                        trace_id, org_id, workflow_id, user_id,
                        endpoint_ids, action_type, action_detail,
                        success, duration_ms, error_detail,
                        created_at
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
                """,
                    i + 1,  # Use sequential IDs for traces
                    org_id, workflow_id, user_id,
                    random.sample(self.endpoint_ids, k=min(len(self.endpoint_ids), random.randint(1, 3))),
                    random.choice(['manual', 'scheduled', 'triggered', 'api']),
                    {'trigger': 'test', 'run': i},
                    success,
                    duration_ms,
                    None if success else {'error': 'Simulated error', 'code': random.choice(['TIMEOUT', 'AUTH_FAILED', 'NETWORK_ERROR'])},
                    created_at
                )
                total_traces += 1
        
        print(f"  Created {total_traces} workflow traces")
    
    async def print_summary(self):
        """Print summary of seeded data"""
        print("\n" + "=" * 60)
        print("SEEDING SUMMARY")
        print("=" * 60)
        
        counts = await self.conn.fetchrow("""
            SELECT 
                (SELECT COUNT(*) FROM organization) as orgs,
                (SELECT COUNT(*) FROM app_user) as users,
                (SELECT COUNT(*) FROM channel_type) as channels,
                (SELECT COUNT(*) FROM endpoint) as endpoints,
                (SELECT COUNT(*) FROM user_workflow) as workflows,
                (SELECT COUNT(*) FROM workflow_node) as nodes,
                (SELECT COUNT(*) FROM workflow_transition) as transitions,
                (SELECT COUNT(*) FROM micro_state) as micro_states,
                (SELECT COUNT(*) FROM batch_job) as batch_jobs,
                (SELECT COUNT(*) FROM workflow_trace) as traces
        """)
        
        for key, value in counts.items():
            print(f"  {key:15s}: {value:,}")
        
        print("=" * 60)


async def main():
    """Main entry point"""
    seeder = V8DataSeeder(DATABASE_URL)
    
    try:
        await seeder.connect()
        
        # Check if data already exists
        existing = await seeder.conn.fetchval("SELECT COUNT(*) FROM organization")
        if existing > 0:
            print("⚠️  Warning: Database already contains data!")
            response = input("Do you want to continue? (y/N): ")
            if response.lower() != 'y':
                print("Aborted.")
                return
        
        await seeder.seed_all()
        
    except Exception as e:
        print(f"\n❌ Error: {str(e)}")
        raise
    finally:
        await seeder.disconnect()


if __name__ == "__main__":
    asyncio.run(main())