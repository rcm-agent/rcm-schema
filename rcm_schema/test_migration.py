#!/usr/bin/env python3
"""Test the workflow node migration locally"""

import os
from dotenv import load_dotenv
import psycopg2
from psycopg2 import sql

# Load environment variables
load_dotenv()

# Get database URL
database_url = os.getenv("DATABASE_URL", "postgresql://rcm_user:rcm_password@localhost:5432/rcm_orchestrator")

# Parse the URL
if database_url.startswith("postgresql://"):
    # Parse the URL manually
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
else:
    raise ValueError("Invalid database URL format")

print(f"Connecting to database: {db_config['database']} at {db_config['host']}:{db_config['port']}")

try:
    # Connect to database
    conn = psycopg2.connect(**db_config)
    conn.autocommit = False
    cur = conn.cursor()
    
    print("Connected successfully!")
    
    # Check if user_workflow table exists
    cur.execute("""
        SELECT EXISTS (
            SELECT FROM information_schema.tables 
            WHERE table_name = 'user_workflow'
        );
    """)
    has_workflow_table = cur.fetchone()[0]
    print(f"user_workflow table exists: {has_workflow_table}")
    
    # Check if old tables exist
    cur.execute("""
        SELECT EXISTS (
            SELECT FROM information_schema.tables 
            WHERE table_name = 'workflow_node'
        );
    """)
    has_old_node_table = cur.fetchone()[0]
    print(f"workflow_node table exists: {has_old_node_table}")
    
    # Check if new tables exist
    cur.execute("""
        SELECT EXISTS (
            SELECT FROM information_schema.tables 
            WHERE table_name = 'user_workflow_node'
        );
    """)
    has_new_node_table = cur.fetchone()[0]
    print(f"user_workflow_node table exists: {has_new_node_table}")
    
    if has_new_node_table:
        # Check structure of new table
        cur.execute("""
            SELECT column_name, data_type 
            FROM information_schema.columns 
            WHERE table_name = 'user_workflow_node'
            ORDER BY ordinal_position;
        """)
        columns = cur.fetchall()
        print("\nuser_workflow_node columns:")
        for col_name, col_type in columns:
            print(f"  - {col_name}: {col_type}")
    
    # Test creating the new table structure (in a transaction that we'll rollback)
    print("\n--- Testing Migration SQL ---")
    
    try:
        # Create user_workflow_node table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS user_workflow_node (
                node_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                workflow_id UUID NOT NULL,
                label TEXT NOT NULL,
                description TEXT,
                metadata JSONB DEFAULT '{}'::jsonb,
                label_conf NUMERIC(3, 2),
                last_label_at TIMESTAMPTZ
            );
        """)
        print("✓ user_workflow_node table created successfully")
        
        # Create user_workflow_transition table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS user_workflow_transition (
                workflow_id UUID NOT NULL,
                from_node UUID NOT NULL,
                to_node UUID NOT NULL,
                action_label TEXT NOT NULL,
                freq INTEGER NOT NULL DEFAULT 1,
                PRIMARY KEY (workflow_id, from_node, to_node, action_label)
            );
        """)
        print("✓ user_workflow_transition table created successfully")
        
        # Check if we can add foreign keys (depends on user_workflow existing)
        if has_workflow_table:
            cur.execute("""
                ALTER TABLE user_workflow_node 
                ADD CONSTRAINT fk_workflow_node_workflow
                    FOREIGN KEY (workflow_id) 
                    REFERENCES user_workflow(workflow_id)
                    ON DELETE CASCADE;
            """)
            print("✓ Foreign key constraints added successfully")
        else:
            print("⚠ Skipping foreign key constraints (user_workflow table doesn't exist)")
        
        # Test inserting sample data
        if has_workflow_table:
            # Get a workflow ID
            cur.execute("SELECT workflow_id FROM user_workflow LIMIT 1;")
            result = cur.fetchone()
            if result:
                workflow_id = result[0]
                cur.execute("""
                    INSERT INTO user_workflow_node (workflow_id, label, description)
                    VALUES (%s, %s, %s)
                    RETURNING node_id;
                """, (workflow_id, "Test Node", "Test Description"))
                node_id = cur.fetchone()[0]
                print(f"✓ Test node inserted with UUID: {node_id}")
            else:
                print("⚠ No workflows found to test insertion")
        
        print("\n✅ Migration SQL is valid and executable!")
        
    except Exception as e:
        print(f"\n❌ Migration error: {e}")
    
    # Always rollback since this is just a test
    conn.rollback()
    print("\nRolled back test transaction.")
    
except Exception as e:
    print(f"Connection error: {e}")
finally:
    if 'conn' in locals():
        conn.close()
        print("Connection closed.")