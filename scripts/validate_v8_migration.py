#!/usr/bin/env python3
"""
V8 Migration Validation Script
Validates that the migration was successful and data integrity is maintained
"""
import os
import sys
import json
import asyncio
from datetime import datetime
from uuid import UUID
import asyncpg
from typing import Dict, List, Tuple, Optional

# Database configuration
DATABASE_URL = os.getenv('DATABASE_URL', 'postgresql://postgres:postgres@localhost:5432/rcm_db')


class MigrationValidator:
    """Validates V8 schema migration"""
    
    def __init__(self, db_url: str):
        self.db_url = db_url
        self.conn: Optional[asyncpg.Connection] = None
        self.errors: List[str] = []
        self.warnings: List[str] = []
        self.info: List[str] = []
    
    async def connect(self):
        """Connect to database"""
        self.conn = await asyncpg.connect(self.db_url)
    
    async def disconnect(self):
        """Disconnect from database"""
        if self.conn:
            await self.conn.close()
    
    async def validate_all(self) -> bool:
        """Run all validation checks"""
        print("=" * 60)
        print("RCM V8 Schema Migration Validator")
        print("=" * 60)
        print(f"Database: {self.db_url}")
        print(f"Started: {datetime.now()}")
        print("=" * 60)
        
        checks = [
            ("Schema Structure", self.check_schema_structure),
            ("Data Integrity", self.check_data_integrity),
            ("Foreign Key Constraints", self.check_foreign_keys),
            ("Indexes", self.check_indexes),
            ("Views", self.check_views),
            ("Extensions", self.check_extensions),
            ("Default Organization", self.check_default_org),
            ("Data Migration", self.check_data_migration),
            ("Lookup Tables", self.check_lookup_tables),
            ("Vector Columns", self.check_vector_columns)
        ]
        
        all_passed = True
        
        for check_name, check_func in checks:
            print(f"\n[CHECK] {check_name}...")
            try:
                passed = await check_func()
                status = "✓ PASSED" if passed else "✗ FAILED"
                print(f"  {status}")
                all_passed = all_passed and passed
            except Exception as e:
                print(f"  ✗ ERROR: {str(e)}")
                self.errors.append(f"{check_name}: {str(e)}")
                all_passed = False
        
        # Print summary
        print("\n" + "=" * 60)
        print("VALIDATION SUMMARY")
        print("=" * 60)
        
        if self.errors:
            print(f"\n❌ ERRORS ({len(self.errors)}):")
            for error in self.errors:
                print(f"  - {error}")
        
        if self.warnings:
            print(f"\n⚠️  WARNINGS ({len(self.warnings)}):")
            for warning in self.warnings:
                print(f"  - {warning}")
        
        if self.info:
            print(f"\nℹ️  INFO ({len(self.info)}):")
            for info in self.info:
                print(f"  - {info}")
        
        print("\n" + "=" * 60)
        if all_passed:
            print("✅ MIGRATION VALIDATION PASSED!")
        else:
            print("❌ MIGRATION VALIDATION FAILED!")
        print("=" * 60)
        
        return all_passed
    
    async def check_schema_structure(self) -> bool:
        """Check that all V8 tables exist with correct structure"""
        required_tables = {
            # Lookup tables
            'lookup_org_type': ['org_type', 'description'],
            'lookup_channel_auth_type': ['auth_type', 'description'],
            'lookup_workflow_status': ['status', 'description'],
            'lookup_batch_job_status': ['status', 'description'],
            
            # Core tables
            'organization': ['org_id', 'org_type', 'name', 'metadata', 'created_at', 'updated_at'],
            'app_user': ['user_id', 'org_id', 'email', 'username', 'first_name', 'last_name'],
            'channel_type': ['channel_type_id', 'channel_name', 'auth_type', 'config_template'],
            'endpoint': ['endpoint_id', 'org_id', 'channel_type_id', 'name', 'base_url'],
            'user_workflow': ['workflow_id', 'workflow_name', 'description', 'created_by'],
            'workflow_node': ['node_id', 'workflow_id', 'code', 'name', 'parent_relation'],
            'workflow_transition': ['transition_id', 'workflow_id', 'from_node_id', 'to_node_id'],
            'micro_state': ['micro_state_id', 'workflow_id', 'node_id', 'text_emb'],
            'workflow_trace': ['trace_id', 'org_id', 'workflow_id', 'user_id'],
            'batch_job': ['batch_job_id', 'org_id', 'user_id', 'task_type']
        }
        
        passed = True
        
        for table, required_columns in required_tables.items():
            # Check table exists
            exists = await self.conn.fetchval(
                """
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_schema = 'public' 
                    AND table_name = $1
                )
                """,
                table
            )
            
            if not exists:
                self.errors.append(f"Table '{table}' does not exist")
                passed = False
                continue
            
            # Check columns
            columns = await self.conn.fetch(
                """
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_schema = 'public' 
                AND table_name = $1
                """,
                table
            )
            
            column_names = {row['column_name'] for row in columns}
            
            for required_col in required_columns:
                if required_col not in column_names:
                    self.errors.append(f"Column '{required_col}' missing from table '{table}'")
                    passed = False
            
            self.info.append(f"Table '{table}' has {len(columns)} columns")
        
        return passed
    
    async def check_data_integrity(self) -> bool:
        """Check data integrity after migration"""
        passed = True
        
        # Check for orphaned records
        orphan_checks = [
            ("app_user without organization", 
             "SELECT COUNT(*) FROM app_user u LEFT JOIN organization o ON u.org_id = o.org_id WHERE o.org_id IS NULL"),
            
            ("endpoint without organization",
             "SELECT COUNT(*) FROM endpoint e LEFT JOIN organization o ON e.org_id = o.org_id WHERE o.org_id IS NULL"),
            
            ("workflow_node without workflow",
             "SELECT COUNT(*) FROM workflow_node n LEFT JOIN user_workflow w ON n.workflow_id = w.workflow_id WHERE w.workflow_id IS NULL"),
            
            ("micro_state without workflow",
             "SELECT COUNT(*) FROM micro_state m LEFT JOIN user_workflow w ON m.workflow_id = w.workflow_id WHERE w.workflow_id IS NULL")
        ]
        
        for check_name, query in orphan_checks:
            count = await self.conn.fetchval(query)
            if count > 0:
                self.warnings.append(f"{check_name}: {count} orphaned records found")
                passed = False
        
        return passed
    
    async def check_foreign_keys(self) -> bool:
        """Check that all foreign key constraints are in place"""
        fk_query = """
        SELECT
            tc.table_name,
            kcu.column_name,
            ccu.table_name AS foreign_table_name,
            ccu.column_name AS foreign_column_name
        FROM information_schema.table_constraints AS tc
        JOIN information_schema.key_column_usage AS kcu
            ON tc.constraint_name = kcu.constraint_name
            AND tc.table_schema = kcu.table_schema
        JOIN information_schema.constraint_column_usage AS ccu
            ON ccu.constraint_name = tc.constraint_name
            AND ccu.table_schema = tc.table_schema
        WHERE tc.constraint_type = 'FOREIGN KEY'
        AND tc.table_schema = 'public'
        ORDER BY tc.table_name
        """
        
        fks = await self.conn.fetch(fk_query)
        
        # Expected foreign keys
        expected_fks = [
            ('app_user', 'org_id', 'organization'),
            ('endpoint', 'org_id', 'organization'),
            ('endpoint', 'channel_type_id', 'channel_type'),
            ('workflow_node', 'workflow_id', 'user_workflow'),
            ('workflow_transition', 'workflow_id', 'user_workflow'),
            ('workflow_transition', 'from_node_id', 'workflow_node'),
            ('workflow_transition', 'to_node_id', 'workflow_node'),
            ('micro_state', 'workflow_id', 'user_workflow'),
            ('micro_state', 'node_id', 'workflow_node'),
            ('workflow_trace', 'org_id', 'organization'),
            ('workflow_trace', 'workflow_id', 'user_workflow'),
            ('workflow_trace', 'user_id', 'app_user'),
            ('batch_job', 'org_id', 'organization'),
            ('batch_job', 'user_id', 'app_user')
        ]
        
        found_fks = {(fk['table_name'], fk['column_name'], fk['foreign_table_name']) 
                     for fk in fks}
        
        passed = True
        for expected in expected_fks:
            if expected not in found_fks:
                self.errors.append(f"Missing FK: {expected[0]}.{expected[1]} -> {expected[2]}")
                passed = False
        
        self.info.append(f"Found {len(fks)} foreign key constraints")
        return passed
    
    async def check_indexes(self) -> bool:
        """Check that performance indexes are created"""
        index_query = """
        SELECT
            schemaname,
            tablename,
            indexname,
            indexdef
        FROM pg_indexes
        WHERE schemaname = 'public'
        AND indexname NOT LIKE '%_pkey'
        ORDER BY tablename, indexname
        """
        
        indexes = await self.conn.fetch(index_query)
        
        # Check for important indexes
        important_indexes = [
            ('app_user', 'org_id'),
            ('app_user', 'email'),
            ('workflow_trace', 'org_id'),
            ('workflow_trace', 'workflow_id'),
            ('micro_state', 'workflow_id'),
            ('batch_job', 'org_id')
        ]
        
        indexed_columns = {}
        for idx in indexes:
            table = idx['tablename']
            if table not in indexed_columns:
                indexed_columns[table] = []
            # Extract column from index definition
            indexdef = idx['indexdef']
            indexed_columns[table].append(indexdef)
        
        passed = True
        for table, column in important_indexes:
            if table not in indexed_columns:
                self.warnings.append(f"No indexes found for table '{table}'")
            else:
                # Check if column is indexed (simple check)
                column_indexed = any(column in idx for idx in indexed_columns[table])
                if not column_indexed:
                    self.warnings.append(f"Column '{table}.{column}' should be indexed for performance")
        
        self.info.append(f"Found {len(indexes)} indexes (excluding primary keys)")
        return passed
    
    async def check_views(self) -> bool:
        """Check backward compatibility views"""
        views_query = """
        SELECT table_name 
        FROM information_schema.views 
        WHERE table_schema = 'public'
        """
        
        views = await self.conn.fetch(views_query)
        view_names = {v['table_name'] for v in views}
        
        required_views = ['rcm_user', 'rcm_trace']
        passed = True
        
        for view in required_views:
            if view in view_names:
                # Test view is functional
                try:
                    await self.conn.fetchval(f"SELECT COUNT(*) FROM {view}")
                    self.info.append(f"Backward compatibility view '{view}' is functional")
                except Exception as e:
                    self.errors.append(f"View '{view}' exists but is not functional: {str(e)}")
                    passed = False
            else:
                self.errors.append(f"Backward compatibility view '{view}' is missing")
                passed = False
        
        return passed
    
    async def check_extensions(self) -> bool:
        """Check required PostgreSQL extensions"""
        extensions = await self.conn.fetch(
            "SELECT extname, extversion FROM pg_extension"
        )
        
        ext_dict = {ext['extname']: ext['extversion'] for ext in extensions}
        
        if 'vector' not in ext_dict:
            self.errors.append("pgvector extension is not installed")
            return False
        
        self.info.append(f"pgvector version {ext_dict['vector']} is installed")
        
        # Check vector functionality
        try:
            await self.conn.fetchval(
                "SELECT '[1,2,3]'::vector <-> '[3,2,1]'::vector as distance"
            )
            self.info.append("pgvector is functional")
        except Exception as e:
            self.errors.append(f"pgvector is not functional: {str(e)}")
            return False
        
        return True
    
    async def check_default_org(self) -> bool:
        """Check default organization exists"""
        default_org = await self.conn.fetchrow(
            """
            SELECT org_id, name, org_type 
            FROM organization 
            WHERE org_id = '00000000-0000-0000-0000-000000000000'
            """
        )
        
        if not default_org:
            self.warnings.append("Default organization not found - existing data may not be migrated")
            return False
        
        self.info.append(f"Default organization: {default_org['name']} (type: {default_org['org_type']})")
        return True
    
    async def check_data_migration(self) -> bool:
        """Check that data was migrated from old tables"""
        # Check user count
        old_user_count = await self.conn.fetchval(
            "SELECT COUNT(*) FROM rcm_user"
        )
        new_user_count = await self.conn.fetchval(
            "SELECT COUNT(*) FROM app_user"
        )
        
        if old_user_count != new_user_count:
            self.errors.append(f"User count mismatch: {old_user_count} in rcm_user vs {new_user_count} in app_user")
            return False
        
        # Check trace count
        old_trace_count = await self.conn.fetchval(
            "SELECT COUNT(*) FROM rcm_trace"
        )
        new_trace_count = await self.conn.fetchval(
            "SELECT COUNT(*) FROM workflow_trace"
        )
        
        if old_trace_count != new_trace_count:
            self.errors.append(f"Trace count mismatch: {old_trace_count} in rcm_trace vs {new_trace_count} in workflow_trace")
            return False
        
        self.info.append(f"Migrated {new_user_count} users and {new_trace_count} traces")
        return True
    
    async def check_lookup_tables(self) -> bool:
        """Check lookup tables are populated"""
        lookup_checks = [
            ('lookup_org_type', ['standard', 'enterprise', 'partner']),
            ('lookup_channel_auth_type', ['none', 'basic', 'bearer', 'oauth2']),
            ('lookup_workflow_status', ['draft', 'active', 'paused', 'archived']),
            ('lookup_batch_job_status', ['queued', 'processing', 'completed', 'failed', 'cancelled'])
        ]
        
        passed = True
        for table, expected_values in lookup_checks:
            values = await self.conn.fetch(f"SELECT * FROM {table}")
            value_dict = {v[list(v.keys())[0]]: v['description'] for v in values}
            
            for expected in expected_values:
                if expected not in value_dict:
                    self.errors.append(f"Lookup value '{expected}' missing from {table}")
                    passed = False
            
            self.info.append(f"Lookup table {table} has {len(values)} entries")
        
        return passed
    
    async def check_vector_columns(self) -> bool:
        """Check vector columns are properly configured"""
        # Check micro_state.text_emb
        column_info = await self.conn.fetchrow(
            """
            SELECT 
                data_type,
                character_maximum_length,
                udt_name
            FROM information_schema.columns
            WHERE table_name = 'micro_state'
            AND column_name = 'text_emb'
            """
        )
        
        if not column_info:
            self.errors.append("Column micro_state.text_emb not found")
            return False
        
        if column_info['udt_name'] != 'vector':
            self.errors.append(f"Column micro_state.text_emb has wrong type: {column_info['udt_name']} (expected: vector)")
            return False
        
        # Check if any micro states have embeddings
        has_embeddings = await self.conn.fetchval(
            "SELECT EXISTS(SELECT 1 FROM micro_state WHERE text_emb IS NOT NULL)"
        )
        
        if has_embeddings:
            # Check embedding dimension
            dimension = await self.conn.fetchval(
                "SELECT vector_dims(text_emb) FROM micro_state WHERE text_emb IS NOT NULL LIMIT 1"
            )
            if dimension != 768:
                self.warnings.append(f"Unexpected embedding dimension: {dimension} (expected: 768)")
            else:
                self.info.append(f"Embeddings have correct dimension: {dimension}")
        else:
            self.info.append("No embeddings found in micro_state table yet")
        
        return True


async def main():
    """Main entry point"""
    validator = MigrationValidator(DATABASE_URL)
    
    try:
        await validator.connect()
        success = await validator.validate_all()
        await validator.disconnect()
        
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n❌ FATAL ERROR: {str(e)}")
        sys.exit(2)


if __name__ == "__main__":
    asyncio.run(main())