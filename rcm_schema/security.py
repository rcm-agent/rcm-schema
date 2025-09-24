"""Security utilities for Row Level Security and multi-tenant access control."""

from typing import Optional, Dict, Any, TypeVar, Type
from functools import wraps
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Query
from uuid import UUID
import logging

from .models import Base

logger = logging.getLogger(__name__)

T = TypeVar('T', bound=Base)


class SecurityContext:
    """Security context for RLS operations."""
    
    def __init__(self, org_id: str, user_id: Optional[str] = None):
        """Initialize security context.
        
        Args:
            org_id: Organization ID for RLS filtering
            user_id: Optional user ID for audit trails
        """
        self.org_id = org_id
        self.user_id = user_id
        self._original_settings: Dict[str, Any] = {}
    
    async def apply_to_session(self, session: AsyncSession):
        """Apply security context to a database session.
        
        Args:
            session: Database session to apply context to
        """
        # Store original settings if needed
        result = await session.execute(
            text("SELECT current_setting('app.current_org_id', true)")
        )
        self._original_settings['org_id'] = result.scalar()
        
        # Set new context
        await session.execute(
            text("SET LOCAL app.current_org_id = :org_id"),
            {"org_id": self.org_id}
        )
        
        if self.user_id:
            await session.execute(
                text("SET LOCAL app.current_user_id = :user_id"),
                {"user_id": self.user_id}
            )
    
    async def restore_session(self, session: AsyncSession):
        """Restore original session settings.
        
        Args:
            session: Database session to restore
        """
        if self._original_settings.get('org_id'):
            await session.execute(
                text("SET LOCAL app.current_org_id = :org_id"),
                {"org_id": self._original_settings['org_id']}
            )
        else:
            await session.execute(text("RESET app.current_org_id"))


def require_org_context(func):
    """Decorator that ensures org context is set for database operations.
    
    The decorated function must have 'session' and 'org_id' parameters.
    
    Example:
        @require_org_context
        async def get_portals(session: AsyncSession, org_id: str):
            result = await session.execute(select(IntegrationEndpoint))
            return result.scalars().all()
    """
    @wraps(func)
    async def wrapper(*args, **kwargs):
        # Extract session and org_id from arguments
        session = kwargs.get('session')
        org_id = kwargs.get('org_id')
        
        if not session:
            # Try positional args
            session = args[0] if args else None
            
        if not org_id:
            # Try positional args
            org_id = args[1] if len(args) > 1 else None
        
        if not session or not org_id:
            raise ValueError("Function must have 'session' and 'org_id' parameters")
        
        # Apply security context
        context = SecurityContext(org_id)
        await context.apply_to_session(session)
        
        try:
            # Execute function
            return await func(*args, **kwargs)
        finally:
            # Restore context
            await context.restore_session(session)
    
    return wrapper


class OrgFilterMixin:
    """Mixin for query builders that need org filtering."""
    
    @staticmethod
    def filter_by_org(query: Query, org_id: str, model: Type[T]) -> Query:
        """Add org filtering to a query.
        
        Args:
            query: SQLAlchemy query
            org_id: Organization ID to filter by
            model: Model class being queried
            
        Returns:
            Query with org filter applied
        """
        if hasattr(model, 'org_id'):
            # Direct org_id column
            return query.filter(model.org_id == org_id)
        elif hasattr(model, 'portal_id'):
            # Filter through portal relationship
            from .models import IntegrationEndpoint
            return query.join(IntegrationEndpoint).filter(
                IntegrationEndpoint.org_id == org_id
            )
        else:
            # Model doesn't support org filtering
            logger.warning(f"Model {model.__name__} doesn't support org filtering")
            return query


class AuditMixin:
    """Mixin for adding audit trail functionality."""
    
    @staticmethod
    async def log_access(
        session: AsyncSession,
        user_id: str,
        resource_type: str,
        resource_id: str,
        action: str,
        details: Optional[Dict[str, Any]] = None
    ):
        """Log an access event for audit trails.
        
        Args:
            session: Database session
            user_id: User performing the action
            resource_type: Type of resource accessed
            resource_id: ID of the resource
            action: Action performed (read, write, delete)
            details: Optional additional details
        """
        # This would log to an audit table if implemented
        logger.info(
            f"Audit: User {user_id} performed {action} on "
            f"{resource_type}:{resource_id}",
            extra={"details": details}
        )


async def check_org_access(
    session: AsyncSession,
    org_id: str,
    resource_model: Type[T],
    resource_id: Any
) -> bool:
    """Check if an organization has access to a resource.
    
    Args:
        session: Database session
        org_id: Organization ID to check
        resource_model: Model class of the resource
        resource_id: ID of the resource
        
    Returns:
        bool: True if organization has access
    """
    # Set org context
    await session.execute(
        text("SET LOCAL app.current_org_id = :org_id"),
        {"org_id": org_id}
    )
    
    # Try to fetch resource (RLS will filter)
    result = await session.execute(
        select(resource_model).where(
            resource_model.id == resource_id
        )
    )
    
    return result.scalar() is not None


def validate_uuid(value: str) -> UUID:
    """Validate and convert a string to UUID.
    
    Args:
        value: String value to validate
        
    Returns:
        UUID: Validated UUID
        
    Raises:
        ValueError: If value is not a valid UUID
    """
    try:
        return UUID(value)
    except (ValueError, TypeError):
        raise ValueError(f"Invalid UUID: {value}")


def sanitize_org_id(org_id: Any) -> str:
    """Sanitize and validate organization ID.
    
    Args:
        org_id: Organization ID to sanitize
        
    Returns:
        str: Sanitized organization ID
        
    Raises:
        ValueError: If org_id is invalid
    """
    if not org_id:
        raise ValueError("Organization ID is required")
    
    # Validate UUID format
    return str(validate_uuid(str(org_id)))


def extract_org_from_jwt(jwt_payload: Dict[str, Any]) -> str:
    """Extract organization ID from JWT payload.
    
    Args:
        jwt_payload: Decoded JWT payload
        
    Returns:
        str: Organization ID
        
    Raises:
        ValueError: If org_id not found in JWT
    """
    # Try multiple possible locations
    org_id = (
        jwt_payload.get('custom:org_id') or
        jwt_payload.get('org_id') or
        jwt_payload.get('organization_id')
    )
    
    if not org_id:
        raise ValueError("Organization ID not found in JWT")
    
    return sanitize_org_id(org_id)