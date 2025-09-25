#!/usr/bin/env python3
"""Fix the migration chain in rcm-schema"""

import os
import re
from pathlib import Path

BASE_DIR = Path(__file__).parent
migrations_dir = BASE_DIR / "alembic" / "versions"

# Expected migration chain
expected_chain = [
    ("001_initial_schema", None),
    ("002_refactor_workflow_type_to_task_type_fk", "001_initial_schema"),
    ("003_add_hierarchical_requirements_system", "002_refactor_workflow_type_to_task_type_fk"),
    ("004_update_task_action_enum_industry_standards", "003_add_hierarchical_requirements_system"),
    ("005_add_comprehensive_bpo_task_enums", "004_update_task_action_enum_industry_standards"),
    ("006_add_credential_storage_fields", "005_add_comprehensive_bpo_task_enums"),
    ("007_migrate_to_v8_schema", "006_add_credential_storage_fields"),
    ("008_add_workflow_revisions", "007_migrate_to_v8_schema"),
    ("009_add_user_organization_table", "008_add_workflow_revisions"),
    ("010_workflow_runs_enhancement", "009_add_user_organization_table"),
    ("011_add_data_sources_tables", "010_workflow_runs_enhancement"),
    ("012_add_billing_tables", "011_add_data_sources_tables"),
    ("013_add_user_invitations_table", "012_add_billing_tables"),
    ("014_add_workflow_execution_tables", "013_add_user_invitations_table"),
    ("015_update_workflow_node_types", "014_add_workflow_execution_tables"),
    ("016_add_workflow_versioning", "015_update_workflow_node_types"),
    ("017_refactor_workflow_nodes_to_user_owned", "016_add_workflow_versioning"),
    ("018_fix_workflow_execution_node_references", "017_refactor_workflow_nodes_to_user_owned"),
    ("019_create_s3_screenshots_table", "018_fix_workflow_execution_node_references"),
]

# Files to remove (broken migrations)
files_to_remove = [
    "20250813_add_workflow_multi_tenancy.py",
    "8a997b2d4049_add_s3_screenshot_storage_columns.py"
]

print("Fixing migration chain...")
print("=" * 60)

# Remove broken migrations
for filename in files_to_remove:
    filepath = migrations_dir / filename
    if filepath.exists():
        print(f"Removing broken migration: {filename}")
        filepath.unlink()

# Fix migration chain
for revision, down_revision in expected_chain:
    # Find the migration file
    pattern = f"{revision}*.py"
    files = list(migrations_dir.glob(pattern))
    
    if not files:
        print(f"WARNING: Migration {revision} not found!")
        continue
    
    if len(files) > 1:
        print(f"WARNING: Multiple files for {revision}: {files}")
        continue
        
    filepath = files[0]
    print(f"Checking {filepath.name}...")
    
    # Read the file
    content = filepath.read_text()
    
    # Fix revision identifier
    content = re.sub(
        r"revision[:\s]*=\s*['\"].*?['\"]",
        f"revision = '{revision}'",
        content
    )
    
    # Fix down_revision
    if down_revision:
        content = re.sub(
            r"down_revision[:\s]*(?:Union\[str,\s*None\]\s*=|=)\s*['\"].*?['\"]",
            f"down_revision = '{down_revision}'",
            content
        )
    else:
        content = re.sub(
            r"down_revision[:\s]*(?:Union\[str,\s*None\]\s*=|=)\s*.*?(?=\n)",
            f"down_revision = None",
            content
        )
    
    # Write back
    filepath.write_text(content)
    print(f"  ✓ Fixed: revision={revision}, down_revision={down_revision}")

print("\n" + "=" * 60)
print("Migration chain fixed!")
print("\nYou can now run: alembic upgrade head")
