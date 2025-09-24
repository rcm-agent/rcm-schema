#!/usr/bin/env python3
"""Test the complete workflow node migration with prerequisites"""

import os
import uuid
from dotenv import load_dotenv
import psycopg2
from psycopg2 import sql

# Load environment variables
load_dotenv()

# Get database URL
database_url = os.getenv("DATABASE_URL", "postgresql://rcm_user:rcm_password@127.0.0.1:5432/rcm_orchestrator")

# Parse the URL
if database_url.startswith("postgresql://"):
    parts = database_url.replace("postgresql://", "").split("@")
    user_pass = parts[0].split(":")
    host_db = parts[1].split("/")
    host_port = host_db[0].split(":")
    
    db_config = {
        "user": user_pass[0],
        "password": user_pass[1] if len(user_pass) > 1 else "",
        "host": host_port[0],
        "port": host_port[1] if len(host_port) > 1 else "5432",
        "database": host_db[1] if len(host_db) > 1 else "postgres"
    }

print(f"Testing complete migration in database: {db_config['database']}")

try:
    conn = psycopg2.connect(**db_config)
    conn.autocommit = False
    cur = conn.cursor()
    
    print("✓ Connected to database")
    
    # Step 1: Create prerequisite tables if they don't exist
    print("\n1. Creating prerequisite tables...")
    
    # Create organization table
    cur.execute("""
        CREATE TABLE IF NOT EXISTS organization (
            org_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            org_type TEXT NOT NULL,
            name TEXT NOT NULL UNIQUE,
            email_domain TEXT UNIQUE,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
    """)
    print("  ✓ organization table")
    
    # Create user_workflow table  
    cur.execute("""
        CREATE TABLE IF NOT EXISTS user_workflow (
            workflow_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            org_id UUID REFERENCES organization(org_id) ON DELETE CASCADE,
            name TEXT NOT NULL,
            description TEXT,
            required_data JSONB DEFAULT '[]'::jsonb,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
    """)
    print("  ✓ user_workflow table")
    
    # Create old workflow_node table (to simulate existing schema)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS workflow_node (
            node_id BIGSERIAL PRIMARY KEY,
            code TEXT UNIQUE,
            description TEXT,
            metadata JSONB DEFAULT '{}'::jsonb,
            label_conf NUMERIC(3, 2),
            last_label_at TIMESTAMPTZ
        );
    """)
    print("  ✓ workflow_node table (old schema)")
    
    # Create old workflow_transition table
    cur.execute("""
        CREATE TABLE IF NOT EXISTS workflow_transition (
            from_node BIGINT REFERENCES workflow_node(node_id) ON DELETE CASCADE,
            to_node BIGINT REFERENCES workflow_node(node_id) ON DELETE CASCADE,
            action_label TEXT NOT NULL,
            freq INTEGER NOT NULL DEFAULT 1,
            PRIMARY KEY (from_node, to_node, action_label)
        );
    """)
    print("  ✓ workflow_transition table (old schema)")
    
    # Step 2: Insert test data
    print("\n2. Inserting test data...")
    
    # Insert organization
    cur.execute("""
        INSERT INTO organization (org_id, org_type, name)
        VALUES (%s, 'hospital', 'Test Hospital')
        ON CONFLICT (name) DO NOTHING
        RETURNING org_id;
    """, (str(uuid.uuid4()),))
    org_result = cur.fetchone()
    if org_result:
        org_id = org_result[0]
    else:
        cur.execute("SELECT org_id FROM organization WHERE name = 'Test Hospital';")
        org_id = cur.fetchone()[0]
    print(f"  ✓ Organization: {org_id}")
    
    # Insert workflow
    workflow_id = str(uuid.uuid4())
    cur.execute("""
        INSERT INTO user_workflow (workflow_id, org_id, name, description)
        VALUES (%s, %s, 'Test Workflow', 'Testing migration')
        RETURNING workflow_id;
    """, (workflow_id, org_id))
    print(f"  ✓ Workflow: {workflow_id}")
    
    # Insert old-style nodes
    cur.execute("""
        INSERT INTO workflow_node (code, description)
        VALUES 
            ('LOGIN_PORTAL', 'Login to insurance portal'),
            ('CHECK_STATUS', 'Check claim status'),
            ('DOWNLOAD_EOB', 'Download explanation of benefits')
        ON CONFLICT (code) DO NOTHING
        RETURNING node_id, code;
    """)
    nodes = cur.fetchall()
    if nodes:
        print(f"  ✓ Created {len(nodes)} old-style nodes")
        
        # Insert transitions
        if len(nodes) >= 2:
            cur.execute("""
                INSERT INTO workflow_transition (from_node, to_node, action_label, freq)
                VALUES (%s, %s, 'proceed', 1)
                ON CONFLICT DO NOTHING;
            """, (nodes[0][0], nodes[1][0]))
            print("  ✓ Created transitions")
    
    # Step 3: Run the migration
    print("\n3. Running migration...")
    
    # Create new tables
    cur.execute("""
        CREATE TABLE IF NOT EXISTS user_workflow_node (
            node_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            workflow_id UUID NOT NULL,
            label TEXT NOT NULL,
            description TEXT,
            metadata JSONB DEFAULT '{}'::jsonb,
            label_conf NUMERIC(3, 2),
            last_label_at TIMESTAMPTZ,
            CONSTRAINT fk_workflow
                FOREIGN KEY (workflow_id) 
                REFERENCES user_workflow(workflow_id)
                ON DELETE CASCADE,
            CONSTRAINT uq_workflow_node
                UNIQUE (workflow_id, node_id)
        );
    """)
    print("  ✓ Created user_workflow_node table")
    
    cur.execute("""
        CREATE TABLE IF NOT EXISTS user_workflow_transition (
            workflow_id UUID NOT NULL,
            from_node UUID NOT NULL,
            to_node UUID NOT NULL,
            action_label TEXT NOT NULL,
            freq INTEGER NOT NULL DEFAULT 1,
            PRIMARY KEY (workflow_id, from_node, to_node, action_label),
            CONSTRAINT fk_workflow
                FOREIGN KEY (workflow_id)
                REFERENCES user_workflow(workflow_id)
                ON DELETE CASCADE,
            CONSTRAINT fk_from_node
                FOREIGN KEY (from_node)
                REFERENCES user_workflow_node(node_id)
                ON DELETE CASCADE,
            CONSTRAINT fk_to_node
                FOREIGN KEY (to_node)
                REFERENCES user_workflow_node(node_id)
                ON DELETE CASCADE
        );
    """)
    print("  ✓ Created user_workflow_transition table")
    
    # Migrate data if we have old nodes
    cur.execute("SELECT COUNT(*) FROM workflow_node;")
    old_node_count = cur.fetchone()[0]
    
    if old_node_count > 0:
        print(f"\n4. Migrating {old_node_count} nodes...")
        
        # Create mapping table
        cur.execute("""
            CREATE TEMP TABLE node_id_mapping (
                old_node_id BIGINT,
                new_node_id UUID,
                workflow_id UUID
            );
        """)
        
        # Generate mappings
        cur.execute("""
            INSERT INTO node_id_mapping (old_node_id, new_node_id, workflow_id)
            SELECT 
                wn.node_id,
                gen_random_uuid(),
                %s
            FROM workflow_node wn;
        """, (workflow_id,))
        
        # Migrate nodes
        cur.execute("""
            INSERT INTO user_workflow_node (
                node_id, workflow_id, label, description, metadata, label_conf, last_label_at
            )
            SELECT 
                nm.new_node_id,
                nm.workflow_id,
                wn.code,  -- code becomes label
                wn.description,
                wn.metadata,
                wn.label_conf,
                wn.last_label_at
            FROM workflow_node wn
            JOIN node_id_mapping nm ON nm.old_node_id = wn.node_id;
        """)
        
        cur.execute("SELECT COUNT(*) FROM user_workflow_node;")
        new_node_count = cur.fetchone()[0]
        print(f"  ✓ Migrated {new_node_count} nodes to new schema")
        
        # Migrate transitions
        cur.execute("""
            INSERT INTO user_workflow_transition (
                workflow_id, from_node, to_node, action_label, freq
            )
            SELECT DISTINCT
                nm_from.workflow_id,
                nm_from.new_node_id,
                nm_to.new_node_id,
                wt.action_label,
                wt.freq
            FROM workflow_transition wt
            JOIN node_id_mapping nm_from ON nm_from.old_node_id = wt.from_node
            JOIN node_id_mapping nm_to ON nm_to.old_node_id = wt.to_node 
                AND nm_to.workflow_id = nm_from.workflow_id
            ON CONFLICT DO NOTHING;
        """)
        
        cur.execute("SELECT COUNT(*) FROM user_workflow_transition;")
        transition_count = cur.fetchone()[0]
        print(f"  ✓ Migrated {transition_count} transitions")
    
    # Step 5: Verify the migration
    print("\n5. Verifying migration...")
    
    cur.execute("""
        SELECT node_id, workflow_id, label, description
        FROM user_workflow_node
        ORDER BY label;
    """)
    nodes = cur.fetchall()
    
    print(f"\n  New nodes (UUID-based):")
    for node_id, wf_id, label, desc in nodes:
        print(f"    - {node_id}: {label} ({desc})")
    
    print("\n✅ Migration completed successfully!")
    print("\nNote: This was a test transaction. Rolling back...")
    
    conn.rollback()
    print("Rolled back test transaction.")
    
except Exception as e:
    print(f"\n❌ Error: {e}")
    import traceback
    traceback.print_exc()
finally:
    if 'conn' in locals():
        conn.close()
        print("\nConnection closed.")