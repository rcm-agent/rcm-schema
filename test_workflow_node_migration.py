#!/usr/bin/env python3
"""
Test the workflow node reference migration
"""
import os
import sys
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Database connection
DATABASE_URL = os.getenv('DATABASE_URL')
if not DATABASE_URL:
    print("ERROR: DATABASE_URL not set in .env file")
    sys.exit(1)

def test_migration():
    """Test the workflow node reference migration"""
    
    engine = create_engine(DATABASE_URL)
    
    with engine.connect() as conn:
        print("=" * 60)
        print("Testing Workflow Node Reference Migration")
        print("=" * 60)
        
        # Check if tables exist
        print("\n1. Checking table existence...")
        tables = ['workflow_steps', 'node_io_requirements', 'workflow_data_bindings', 'workflow_trace_screenshot']
        
        for table in tables:
            result = conn.execute(text(f"""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_name = '{table}'
                );
            """)).scalar()
            print(f"   {table}: {'✓ EXISTS' if result else '✗ MISSING'}")
        
        # Check column types before migration
        print("\n2. Checking node_id column types BEFORE migration...")
        
        query = text("""
            SELECT 
                table_name,
                column_name,
                data_type,
                udt_name
            FROM information_schema.columns
            WHERE table_name IN ('workflow_steps', 'node_io_requirements', 'workflow_data_bindings', 'workflow_trace_screenshot')
            AND column_name = 'node_id'
            ORDER BY table_name;
        """)
        
        results = conn.execute(query).fetchall()
        
        if results:
            print("\n   Current node_id column types:")
            for row in results:
                print(f"   {row.table_name}.node_id: {row.data_type} ({row.udt_name})")
        else:
            print("   No node_id columns found in these tables")
        
        # Check foreign key constraints
        print("\n3. Checking foreign key constraints...")
        
        fk_query = text("""
            SELECT
                tc.table_name,
                kcu.column_name,
                ccu.table_name AS foreign_table_name,
                ccu.column_name AS foreign_column_name
            FROM information_schema.table_constraints AS tc
            JOIN information_schema.key_column_usage AS kcu
                ON tc.constraint_name = kcu.constraint_name
            JOIN information_schema.constraint_column_usage AS ccu
                ON ccu.constraint_name = tc.constraint_name
            WHERE tc.constraint_type = 'FOREIGN KEY'
            AND kcu.column_name = 'node_id'
            AND tc.table_name IN ('workflow_steps', 'node_io_requirements', 'workflow_data_bindings')
            ORDER BY tc.table_name;
        """)
        
        fk_results = conn.execute(fk_query).fetchall()
        
        if fk_results:
            print("\n   Current foreign key references:")
            for row in fk_results:
                print(f"   {row.table_name}.{row.column_name} -> {row.foreign_table_name}.{row.foreign_column_name}")
        else:
            print("   No foreign key constraints found for node_id columns")
        
        # Check if user_workflow_node table exists
        print("\n4. Checking user_workflow_node table...")
        
        user_node_exists = conn.execute(text("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_name = 'user_workflow_node'
            );
        """)).scalar()
        
        if user_node_exists:
            print("   ✓ user_workflow_node table exists")
            
            # Check its structure
            node_structure = conn.execute(text("""
                SELECT column_name, data_type, udt_name
                FROM information_schema.columns
                WHERE table_name = 'user_workflow_node'
                AND column_name IN ('node_id', 'workflow_id', 'label')
                ORDER BY column_name;
            """)).fetchall()
            
            print("\n   user_workflow_node structure:")
            for col in node_structure:
                print(f"   - {col.column_name}: {col.data_type} ({col.udt_name})")
        else:
            print("   ✗ user_workflow_node table NOT FOUND")
        
        # Check if old workflow_node table exists
        print("\n5. Checking for old workflow_node table...")
        
        old_node_exists = conn.execute(text("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_name = 'workflow_node'
            );
        """)).scalar()
        
        if old_node_exists:
            print("   ⚠ WARNING: Old workflow_node table still exists")
        else:
            print("   ✓ Old workflow_node table does not exist (expected)")
        
        print("\n" + "=" * 60)
        print("Migration Status Summary:")
        print("=" * 60)
        
        # Determine if migration is needed
        needs_migration = False
        for row in results:
            if row.udt_name in ['int8', 'int4', 'bigint', 'integer']:
                needs_migration = True
                break
        
        if needs_migration:
            print("\n⚠ MIGRATION NEEDED: Tables have BIGINT/INTEGER node_id columns")
            print("  Run: psql -f fix_workflow_node_references.sql")
            print("  Or: alembic upgrade 018_fix_workflow_node_refs")
        else:
            print("\n✓ Tables appear to be using UUID node_id columns")
            print("  Migration may have already been applied")


if __name__ == "__main__":
    test_migration()