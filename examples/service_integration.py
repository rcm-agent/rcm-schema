"""Example of how services should integrate with rcm-schema."""

import asyncio
from typing import List, Optional
from uuid import UUID
from sqlalchemy import select, and_
from sqlalchemy.orm import selectinload

# Import from rcm-schema
from rcm_schema import (
    # Database utilities
    get_session,
    with_org_context,
    set_org_context,
    
    # Models
    IntegrationEndpoint,
    TaskSignature,
    RcmTrace,
    
    # Schemas
    IntegrationEndpointCreate,
    IntegrationEndpointSchema,
    TaskSignatureCreate,
    TaskSignatureSchema,
    
    # Enums
    TaskDomain,
    TaskAction,
    
    # Security
    require_org_context,
    extract_org_from_jwt,
)


class PortalService:
    """Example service class using rcm-schema."""
    
    @staticmethod
    async def create_portal(
        portal_data: IntegrationEndpointCreate,
        org_id: str
    ) -> IntegrationEndpointSchema:
        """Create a new portal for an organization.
        
        Args:
            portal_data: Portal creation data
            org_id: Organization ID from auth context
            
        Returns:
            Created portal
        """
        async with with_org_context(org_id) as session:
            # Create ORM model from Pydantic schema
            portal = IntegrationEndpoint(
                org_id=org_id,
                name=portal_data.name,
                portal_type_id=portal_data.portal_type_id,
                base_url=portal_data.base_url,
                config=portal_data.config or {}
            )
            
            session.add(portal)
            await session.commit()
            await session.refresh(portal)
            
            # Convert to Pydantic schema for response
            return IntegrationEndpointSchema.model_validate(portal)
    
    @staticmethod
    async def get_org_portals(org_id: str) -> List[IntegrationEndpointSchema]:
        """Get all portals for an organization.
        
        Args:
            org_id: Organization ID
            
        Returns:
            List of portals
        """
        async with with_org_context(org_id) as session:
            # Query with eager loading of portal_type
            result = await session.execute(
                select(IntegrationEndpoint)
                .options(selectinload(IntegrationEndpoint.portal_type))
                .order_by(IntegrationEndpoint.created_at.desc())
            )
            
            portals = result.scalars().all()
            
            # Convert to Pydantic schemas
            return [
                IntegrationEndpointSchema.model_validate(portal)
                for portal in portals
            ]


class TaskRecognitionService:
    """Example task recognition service."""
    
    @staticmethod
    @require_org_context
    async def find_task_signature(
        session,  # Injected by decorator
        org_id: str,  # Required by decorator
        portal_id: Optional[int] = None,
        portal_type_id: Optional[int] = None,
        domain: TaskDomain = None,
        action: TaskAction = None
    ) -> Optional[TaskSignatureSchema]:
        """Find a task signature.
        
        Args:
            session: Database session (injected)
            org_id: Organization ID (for decorator)
            portal_id: Specific portal ID
            portal_type_id: Portal type ID
            domain: Task domain
            action: Task action
            
        Returns:
            Task signature if found
        """
        # Build query
        query = select(TaskSignature)
        
        if portal_id:
            query = query.where(TaskSignature.portal_id == portal_id)
        elif portal_type_id:
            query = query.where(TaskSignature.portal_type_id == portal_type_id)
        
        if domain:
            query = query.where(TaskSignature.domain == domain)
        if action:
            query = query.where(TaskSignature.action == action)
        
        # Execute with RLS context already set by decorator
        result = await session.execute(query)
        signature = result.scalar_one_or_none()
        
        if signature:
            return TaskSignatureSchema.model_validate(signature)
        return None
    
    @staticmethod
    async def create_task_signature(
        signature_data: TaskSignatureCreate,
        org_id: str
    ) -> TaskSignatureSchema:
        """Create a new task signature.
        
        Args:
            signature_data: Signature creation data
            org_id: Organization ID for validation
            
        Returns:
            Created signature
        """
        async with get_session() as session:
            # If portal_id is provided, verify org has access
            if signature_data.portal_id:
                await set_org_context(session, org_id)
                
                result = await session.execute(
                    select(IntegrationEndpoint).where(
                        IntegrationEndpoint.portal_id == signature_data.portal_id
                    )
                )
                
                if not result.scalar_one_or_none():
                    raise ValueError("Portal not found or access denied")
            
            # Create signature (no org context needed for task_signature table)
            signature = TaskSignature(**signature_data.model_dump())
            
            session.add(signature)
            await session.commit()
            await session.refresh(signature)
            
            return TaskSignatureSchema.model_validate(signature)


# Example FastAPI integration
from fastapi import FastAPI, Depends, HTTPException
from typing import Dict, Any

app = FastAPI()


def get_current_user() -> Dict[str, Any]:
    """Mock auth dependency - replace with real auth."""
    return {
        "sub": "user-123",
        "custom:org_id": "550e8400-e29b-41d4-a716-446655440000",
        "email": "user@example.com"
    }


@app.post("/portals", response_model=IntegrationEndpointSchema)
async def create_portal(
    portal: IntegrationEndpointCreate,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Create a new portal."""
    try:
        org_id = extract_org_from_jwt(current_user)
        return await PortalService.create_portal(portal, org_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/portals", response_model=List[IntegrationEndpointSchema])
async def list_portals(
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """List organization's portals."""
    try:
        org_id = extract_org_from_jwt(current_user)
        return await PortalService.get_org_portals(org_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/task-signatures/search", response_model=Optional[TaskSignatureSchema])
async def search_task_signature(
    portal_id: Optional[int] = None,
    portal_type_id: Optional[int] = None,
    domain: Optional[TaskDomain] = None,
    action: Optional[TaskAction] = None,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Search for a task signature."""
    try:
        org_id = extract_org_from_jwt(current_user)
        return await TaskRecognitionService.find_task_signature(
            org_id=org_id,
            portal_id=portal_id,
            portal_type_id=portal_type_id,
            domain=domain,
            action=action
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# Example startup/shutdown
from contextlib import asynccontextmanager
from rcm_schema import init_db, close_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    # Startup
    await init_db()
    yield
    # Shutdown
    await close_db()


app = FastAPI(lifespan=lifespan)


if __name__ == "__main__":
    # Example usage
    async def example():
        # Initialize database
        await init_db()
        
        try:
            # Example org ID
            org_id = "550e8400-e29b-41d4-a716-446655440000"
            
            # Create a portal
            portal_data = IntegrationEndpointCreate(
                name="United Healthcare",
                portal_type_id=1,
                base_url="https://united.example.com"
            )
            
            portal = await PortalService.create_portal(portal_data, org_id)
            print(f"Created portal: {portal.portal_id}")
            
            # List portals
            portals = await PortalService.get_org_portals(org_id)
            print(f"Found {len(portals)} portals")
            
            # Search for task signature
            signature = await TaskRecognitionService.find_task_signature(
                org_id=org_id,
                portal_id=portal.portal_id,
                domain=TaskDomain.ELIGIBILITY,
                action=TaskAction.STATUS_CHECK
            )
            
            if signature:
                print(f"Found signature: {signature.signature_id}")
            else:
                print("No signature found")
                
        finally:
            # Cleanup
            await close_db()
    
    # Run example
    asyncio.run(example())