"""Data migration script for moving from old field_requirement to new hierarchical system.

This script analyzes existing field requirements and intelligently separates them into:
1. Payer-level requirements (common across organizations)
2. Organization-specific policies (deviations from payer standards)
"""

import asyncio
import argparse
import logging
from datetime import date
from collections import defaultdict
from typing import Dict, List, Set, Tuple
import json

from sqlalchemy import select, and_, func, text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from models import (
    FieldRequirement, PayerRequirement, OrgRequirementPolicy,
    IntegrationEndpoint, PortalType, TaskType, Organization
)
from database import get_database_url


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class RequirementsMigrator:
    """Handles migration from old to new requirements system."""
    
    def __init__(self, session: AsyncSession, dry_run: bool = True):
        self.session = session
        self.dry_run = dry_run
        self.stats = {
            "total_requirements": 0,
            "payer_requirements_created": 0,
            "org_policies_created": 0,
            "conflicts_found": 0,
            "duplicates_removed": 0
        }
    
    async def migrate(self):
        """Main migration process."""
        logger.info("Starting requirements migration...")
        
        # Step 1: Analyze existing requirements
        requirements_by_portal_type = await self._analyze_requirements()
        
        # Step 2: Identify common payer requirements
        payer_requirements = await self._identify_payer_requirements(requirements_by_portal_type)
        
        # Step 3: Create payer requirements
        if not self.dry_run:
            await self._create_payer_requirements(payer_requirements)
        
        # Step 4: Create org-specific policies for deviations
        await self._create_org_policies(requirements_by_portal_type, payer_requirements)
        
        # Step 5: Verify migration
        await self._verify_migration()
        
        # Report statistics
        self._report_stats()
    
    async def _analyze_requirements(self) -> Dict:
        """Analyze existing requirements grouped by portal type and task type."""
        # Get all field requirements with portal info
        query = select(
            FieldRequirement,
            IntegrationEndpoint,
            PortalType
        ).join(
            IntegrationEndpoint, 
            FieldRequirement.portal_id == IntegrationEndpoint.portal_id
        ).join(
            PortalType,
            IntegrationEndpoint.portal_type_id == PortalType.portal_type_id
        ).where(
            FieldRequirement.active == True
        )
        
        result = await self.session.execute(query)
        
        # Group by portal_type and task_type
        requirements_map = defaultdict(lambda: defaultdict(list))
        
        for req, endpoint, portal_type in result:
            self.stats["total_requirements"] += 1
            key = (portal_type.portal_type_id, req.task_type_id)
            requirements_map[key].append({
                "requirement": req,
                "endpoint": endpoint,
                "portal_type": portal_type
            })
        
        logger.info(f"Found {self.stats['total_requirements']} active requirements")
        return requirements_map
    
    async def _identify_payer_requirements(self, requirements_map: Dict) -> Dict:
        """Identify common requirements across organizations for each payer/task combo."""
        payer_requirements = {}
        
        for (portal_type_id, task_type_id), req_list in requirements_map.items():
            if len(req_list) < 2:
                # Only one org uses this portal/task combo - could be org-specific
                continue
            
            # Analyze field patterns
            field_patterns = defaultdict(int)
            total_orgs = len(req_list)
            
            for req_data in req_list:
                req = req_data["requirement"]
                # Create a hashable representation of fields
                fields_key = json.dumps({
                    "required": sorted(req.required_fields or []),
                    "optional": sorted(req.optional_fields or [])
                }, sort_keys=True)
                field_patterns[fields_key] += 1
            
            # Find the most common pattern (likely the payer standard)
            if field_patterns:
                most_common_pattern = max(field_patterns.items(), key=lambda x: x[1])
                pattern_data = json.loads(most_common_pattern[0])
                frequency = most_common_pattern[1]
                
                # If >60% of orgs use the same pattern, consider it payer standard
                if frequency / total_orgs > 0.6:
                    # Get a sample requirement with this pattern for metadata
                    sample_req = next(
                        r for r in req_list 
                        if sorted(r["requirement"].required_fields or []) == pattern_data["required"]
                    )
                    
                    payer_requirements[(portal_type_id, task_type_id)] = {
                        "required_fields": pattern_data["required"],
                        "optional_fields": pattern_data["optional"],
                        "field_metadata": sample_req["requirement"].field_metadata or {},
                        "portal_type": sample_req["portal_type"],
                        "frequency": frequency,
                        "total_orgs": total_orgs
                    }
                    
                    logger.info(
                        f"Identified payer requirement for {sample_req['portal_type'].name} "
                        f"task {task_type_id}: {frequency}/{total_orgs} orgs use same pattern"
                    )
        
        return payer_requirements
    
    async def _create_payer_requirements(self, payer_requirements: Dict):
        """Create payer requirement records."""
        for (portal_type_id, task_type_id), req_data in payer_requirements.items():
            payer_req = PayerRequirement(
                portal_type_id=portal_type_id,
                task_type_id=task_type_id,
                required_fields=req_data["required_fields"],
                optional_fields=req_data["optional_fields"],
                field_rules=req_data["field_metadata"],
                compliance_ref=f"Migrated from legacy system",
                effective_date=date.today(),
                version=1
            )
            
            self.session.add(payer_req)
            self.stats["payer_requirements_created"] += 1
            
            logger.info(
                f"Created payer requirement for {req_data['portal_type'].name} "
                f"with {len(req_data['required_fields'])} required fields"
            )
        
        if not self.dry_run:
            await self.session.commit()
    
    async def _create_org_policies(self, requirements_map: Dict, payer_requirements: Dict):
        """Create org policies for deviations from payer standards."""
        for (portal_type_id, task_type_id), req_list in requirements_map.items():
            payer_standard = payer_requirements.get((portal_type_id, task_type_id))
            
            for req_data in req_list:
                req = req_data["requirement"]
                endpoint = req_data["endpoint"]
                
                # Compare with payer standard
                if payer_standard:
                    deviations = self._find_deviations(req, payer_standard)
                    
                    if deviations:
                        # Create org policy for deviation
                        policy = OrgRequirementPolicy(
                            org_id=endpoint.org_id,
                            task_type_id=task_type_id,
                            portal_type_id=portal_type_id,
                            policy_type=deviations["type"],
                            field_changes=deviations["changes"],
                            reason=f"Migrated from legacy requirement {req.requirement_id}",
                            active=True,
                            version=1
                        )
                        
                        if not self.dry_run:
                            self.session.add(policy)
                        
                        self.stats["org_policies_created"] += 1
                        
                        logger.info(
                            f"Created {deviations['type']} policy for org {endpoint.org_id} "
                            f"on {req_data['portal_type'].name}"
                        )
                else:
                    # No payer standard - create as org-specific override
                    policy = OrgRequirementPolicy(
                        org_id=endpoint.org_id,
                        task_type_id=task_type_id,
                        portal_type_id=portal_type_id,
                        policy_type="override",
                        field_changes={
                            "required_fields": req.required_fields or [],
                            "optional_fields": req.optional_fields or [],
                            "field_rules": req.field_metadata or {}
                        },
                        reason=f"Migrated org-specific requirement {req.requirement_id}",
                        active=True,
                        version=1
                    )
                    
                    if not self.dry_run:
                        self.session.add(policy)
                    
                    self.stats["org_policies_created"] += 1
        
        if not self.dry_run:
            await self.session.commit()
    
    def _find_deviations(self, requirement: FieldRequirement, payer_standard: Dict) -> Dict:
        """Find deviations between org requirement and payer standard."""
        org_required = set(requirement.required_fields or [])
        org_optional = set(requirement.optional_fields or [])
        payer_required = set(payer_standard["required_fields"])
        payer_optional = set(payer_standard["optional_fields"])
        
        # Check what's different
        added_required = org_required - payer_required
        removed_required = payer_required - org_required
        added_optional = org_optional - payer_optional
        removed_optional = payer_optional - org_optional
        
        if not any([added_required, removed_required, added_optional, removed_optional]):
            return None
        
        # Determine policy type and changes
        if removed_required or removed_optional:
            # If removing fields, likely need override
            return {
                "type": "override",
                "changes": {
                    "required_fields": list(org_required),
                    "optional_fields": list(org_optional),
                    "field_rules": requirement.field_metadata or {}
                }
            }
        else:
            # Just adding fields
            changes = {}
            if added_required:
                changes["required_fields"] = list(added_required)
            if added_optional:
                changes["optional_fields"] = list(added_optional)
            
            return {
                "type": "add",
                "changes": changes
            }
    
    async def _verify_migration(self):
        """Verify the migration maintained data integrity."""
        if self.dry_run:
            logger.info("Dry run - skipping verification")
            return
        
        # Count new records
        payer_count = await self.session.scalar(
            select(func.count()).select_from(PayerRequirement)
        )
        policy_count = await self.session.scalar(
            select(func.count()).select_from(OrgRequirementPolicy)
        )
        
        logger.info(f"Created {payer_count} payer requirements")
        logger.info(f"Created {policy_count} org policies")
        
        # Refresh materialized view
        await self.session.execute(text("REFRESH MATERIALIZED VIEW effective_requirements"))
        await self.session.commit()
        
        logger.info("Refreshed effective_requirements materialized view")
    
    def _report_stats(self):
        """Report migration statistics."""
        logger.info("\n" + "="*50)
        logger.info("Migration Statistics:")
        logger.info(f"Total requirements analyzed: {self.stats['total_requirements']}")
        logger.info(f"Payer requirements created: {self.stats['payer_requirements_created']}")
        logger.info(f"Org policies created: {self.stats['org_policies_created']}")
        logger.info(f"Dry run: {self.dry_run}")
        logger.info("="*50 + "\n")


async def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Migrate requirements to new hierarchical system")
    parser.add_argument(
        "--execute", 
        action="store_true", 
        help="Execute the migration (default is dry run)"
    )
    parser.add_argument(
        "--database-url",
        help="Override database URL from environment"
    )
    
    args = parser.parse_args()
    
    # Get database URL
    database_url = args.database_url or get_database_url()
    if not database_url:
        logger.error("No database URL provided")
        return
    
    # Create async engine
    engine = create_async_engine(database_url, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    async with async_session() as session:
        migrator = RequirementsMigrator(session, dry_run=not args.execute)
        await migrator.migrate()
    
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())