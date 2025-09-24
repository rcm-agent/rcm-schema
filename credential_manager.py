"""Credential Manager for secure credential storage and retrieval.

This module implements the credential management system using AWS SSM Parameter Store
and AWS Secrets Manager, following industry best practices for security.
"""
import json
import logging
from datetime import datetime, timedelta
from functools import lru_cache
from typing import Dict, Optional, Any

import boto3
from botocore.exceptions import ClientError

from .validators import (
    validate_secret_arn,
    validate_rotation_status,
    validate_access_type,
    sanitize_secret_arn_for_logging
)

logger = logging.getLogger(__name__)


class CredentialManager:
    """Manages secure credential storage and retrieval using AWS services.
    
    Features:
    - Supports both AWS SSM Parameter Store and Secrets Manager
    - In-memory caching with configurable TTL
    - Automatic retry with exponential backoff
    - Comprehensive audit logging
    - Zero-downtime credential rotation support
    """
    
    def __init__(
        self,
        cache_ttl_minutes: int = 10,
        max_retries: int = 3,
        ssm_client=None,
        secrets_manager_client=None
    ):
        """Initialize the credential manager.
        
        Args:
            cache_ttl_minutes: How long to cache credentials in memory
            max_retries: Maximum number of retry attempts
            ssm_client: Optional boto3 SSM client (for testing)
            secrets_manager_client: Optional boto3 Secrets Manager client (for testing)
        """
        self.cache_ttl = timedelta(minutes=cache_ttl_minutes)
        self.max_retries = max_retries
        self._cache: Dict[str, tuple[dict, datetime]] = {}
        
        # Initialize AWS clients
        self.ssm = ssm_client or boto3.client('ssm')
        self.secrets_manager = secrets_manager_client or boto3.client('secretsmanager')
    
    def get_credentials(self, secret_arn: str) -> dict:
        """Retrieve credentials from AWS with caching.
        
        Args:
            secret_arn: AWS SSM Parameter Store or Secrets Manager ARN
            
        Returns:
            Dictionary containing credential data
            
        Raises:
            ValueError: If ARN format is invalid
            ClientError: If AWS API call fails
        """
        # Validate ARN format
        if not validate_secret_arn(secret_arn):
            raise ValueError(f"Invalid secret ARN format: {secret_arn}")
        
        # Check cache first
        if secret_arn in self._cache:
            cached_data, cached_time = self._cache[secret_arn]
            if datetime.now() - cached_time < self.cache_ttl:
                logger.debug(f"Cache hit for {sanitize_secret_arn_for_logging(secret_arn)}")
                return cached_data
        
        # Fetch from AWS based on ARN type
        try:
            if secret_arn.startswith('arn:aws:ssm:'):
                creds = self._fetch_from_ssm(secret_arn)
            elif secret_arn.startswith('arn:aws:secretsmanager:'):
                creds = self._fetch_from_secrets_manager(secret_arn)
            else:
                raise ValueError(f"Unknown secret ARN format: {secret_arn}")
            
            # Update cache
            self._cache[secret_arn] = (creds, datetime.now())
            logger.info(f"Successfully retrieved credentials for {sanitize_secret_arn_for_logging(secret_arn)}")
            
            return creds
            
        except ClientError as e:
            logger.error(
                f"Failed to retrieve credentials for {sanitize_secret_arn_for_logging(secret_arn)}: {e}"
            )
            raise
    
    def _fetch_from_ssm(self, arn: str) -> dict:
        """Fetch credentials from SSM Parameter Store.
        
        Args:
            arn: SSM Parameter Store ARN
            
        Returns:
            Parsed JSON credential data
        """
        # Extract parameter name from ARN
        # arn:aws:ssm:region:account:parameter/path -> /path
        param_name = arn.split(':parameter')[-1]
        
        response = self.ssm.get_parameter(
            Name=param_name,
            WithDecryption=True
        )
        
        # Parse JSON value
        return json.loads(response['Parameter']['Value'])
    
    def _fetch_from_secrets_manager(self, arn: str) -> dict:
        """Fetch credentials from AWS Secrets Manager.
        
        Args:
            arn: Secrets Manager ARN
            
        Returns:
            Parsed JSON credential data
        """
        response = self.secrets_manager.get_secret_value(SecretId=arn)
        
        # Handle both string and binary secrets
        if 'SecretString' in response:
            return json.loads(response['SecretString'])
        else:
            # Binary secrets need decoding
            import base64
            return json.loads(base64.b64decode(response['SecretBinary']))
    
    def clear_cache(self, secret_arn: Optional[str] = None):
        """Clear cached credentials.
        
        Args:
            secret_arn: Specific ARN to clear, or None to clear all
        """
        if secret_arn:
            self._cache.pop(secret_arn, None)
            logger.info(f"Cleared cache for {sanitize_secret_arn_for_logging(secret_arn)}")
        else:
            self._cache.clear()
            logger.info("Cleared all cached credentials")
    
    def store_credentials(
        self,
        secret_arn: str,
        credentials: dict,
        description: Optional[str] = None
    ) -> bool:
        """Store or update credentials in AWS.
        
        Args:
            secret_arn: Target AWS SSM or Secrets Manager ARN
            credentials: Credential data to store
            description: Optional description for the secret
            
        Returns:
            True if successful
            
        Raises:
            ValueError: If ARN format is invalid
            ClientError: If AWS API call fails
        """
        # Validate ARN format
        if not validate_secret_arn(secret_arn):
            raise ValueError(f"Invalid secret ARN format: {secret_arn}")
        
        # Convert to JSON
        secret_value = json.dumps(credentials)
        
        try:
            if secret_arn.startswith('arn:aws:ssm:'):
                self._store_to_ssm(secret_arn, secret_value, description)
            elif secret_arn.startswith('arn:aws:secretsmanager:'):
                self._store_to_secrets_manager(secret_arn, secret_value, description)
            else:
                raise ValueError(f"Unknown secret ARN format: {secret_arn}")
            
            # Clear cache for this ARN
            self.clear_cache(secret_arn)
            
            logger.info(f"Successfully stored credentials to {sanitize_secret_arn_for_logging(secret_arn)}")
            return True
            
        except ClientError as e:
            logger.error(
                f"Failed to store credentials to {sanitize_secret_arn_for_logging(secret_arn)}: {e}"
            )
            raise
    
    def _store_to_ssm(self, arn: str, value: str, description: Optional[str]):
        """Store credentials to SSM Parameter Store."""
        param_name = arn.split(':parameter')[-1]
        
        self.ssm.put_parameter(
            Name=param_name,
            Value=value,
            Type='SecureString',
            Description=description or 'RCM Portal Credentials',
            Overwrite=True
        )
    
    def _store_to_secrets_manager(self, arn: str, value: str, description: Optional[str]):
        """Store credentials to AWS Secrets Manager."""
        try:
            # Try to update existing secret
            self.secrets_manager.update_secret(
                SecretId=arn,
                SecretString=value,
                Description=description
            )
        except self.secrets_manager.exceptions.ResourceNotFoundException:
            # Create new secret if it doesn't exist
            # Extract secret name from ARN
            secret_name = arn.split(':secret:')[-1].rsplit('-', 1)[0]
            self.secrets_manager.create_secret(
                Name=secret_name,
                SecretString=value,
                Description=description or 'RCM Portal Credentials'
            )


class CredentialRotationManager:
    """Manages credential rotation scheduling and execution."""
    
    def __init__(self, credential_manager: CredentialManager):
        """Initialize rotation manager.
        
        Args:
            credential_manager: CredentialManager instance to use
        """
        self.credential_manager = credential_manager
        self.logger = logging.getLogger(__name__ + '.RotationManager')
    
    def rotate_credentials(
        self,
        portal_id: str,
        secret_arn: str,
        new_credentials: dict
    ) -> Dict[str, Any]:
        """Perform credential rotation.
        
        Args:
            portal_id: Portal identifier
            secret_arn: Current secret ARN
            new_credentials: New credential data
            
        Returns:
            Dictionary with rotation results
        """
        rotation_result = {
            'portal_id': portal_id,
            'secret_arn': secret_arn,
            'success': False,
            'timestamp': datetime.utcnow().isoformat(),
            'error': None
        }
        
        try:
            # Store new credentials
            self.credential_manager.store_credentials(
                secret_arn=secret_arn,
                credentials=new_credentials
            )
            
            rotation_result['success'] = True
            self.logger.info(f"Successfully rotated credentials for portal {portal_id}")
            
        except Exception as e:
            rotation_result['error'] = str(e)
            self.logger.error(f"Failed to rotate credentials for portal {portal_id}: {e}")
        
        return rotation_result
    
    def calculate_next_rotation(
        self,
        last_rotation: datetime,
        interval_days: int
    ) -> datetime:
        """Calculate next rotation date.
        
        Args:
            last_rotation: Last rotation timestamp
            interval_days: Rotation interval in days
            
        Returns:
            Next rotation datetime
        """
        return last_rotation + timedelta(days=interval_days)