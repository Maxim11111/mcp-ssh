"""Authentication and authorization module."""

import time
import uuid
from typing import Optional, Dict
from datetime import datetime, timedelta
from collections import defaultdict
import logging

from fastapi import HTTPException, Security, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from src.config import get_config, TokenConfig

logger = logging.getLogger(__name__)

security = HTTPBearer()


class RateLimiter:
    """Token-based rate limiter."""
    
    def __init__(self):
        self.requests: Dict[str, list] = defaultdict(list)
        self.commands: Dict[str, list] = defaultdict(list)
    
    def _clean_old_entries(self, entries: list, window_seconds: int):
        """Remove entries older than window."""
        cutoff = time.time() - window_seconds
        return [ts for ts in entries if ts > cutoff]
    
    def check_rate_limit(
        self, 
        token: str, 
        token_config: TokenConfig,
        is_command: bool = False
    ) -> bool:
        """
        Check if request is within rate limits.
        
        Args:
            token: Bearer token
            token_config: Token configuration
            is_command: If True, count as command execution
        
        Returns:
            True if within limits, False otherwise
        """
        config = get_config()
        base_limits = config.security.rate_limit
        
        if not base_limits:
            return True  # No rate limiting configured
        
        multiplier = token_config.rate_limit_multiplier
        current_time = time.time()
        
        # Check request rate (per minute)
        if 'requests_per_minute' in base_limits:
            limit = int(base_limits['requests_per_minute'] * multiplier)
            self.requests[token] = self._clean_old_entries(
                self.requests[token], 60
            )
            
            if len(self.requests[token]) >= limit:
                logger.warning(
                    f"Rate limit exceeded for token {token_config.name}: "
                    f"{len(self.requests[token])}/{limit} requests per minute"
                )
                return False
            
            self.requests[token].append(current_time)
        
        # Check command rate (per hour)
        if is_command and 'commands_per_hour' in base_limits:
            limit = int(base_limits['commands_per_hour'] * multiplier)
            self.commands[token] = self._clean_old_entries(
                self.commands[token], 3600
            )
            
            if len(self.commands[token]) >= limit:
                logger.warning(
                    f"Command rate limit exceeded for token {token_config.name}: "
                    f"{len(self.commands[token])}/{limit} commands per hour"
                )
                return False
            
            self.commands[token].append(current_time)
        
        return True
    
    def get_stats(self, token: str) -> Dict:
        """Get rate limit statistics for token."""
        self.requests[token] = self._clean_old_entries(self.requests[token], 60)
        self.commands[token] = self._clean_old_entries(self.commands[token], 3600)
        
        return {
            'requests_last_minute': len(self.requests[token]),
            'commands_last_hour': len(self.commands[token])
        }


# Global rate limiter instance
rate_limiter = RateLimiter()


async def verify_token(
    credentials: HTTPAuthorizationCredentials = Security(security)
) -> tuple[str, TokenConfig]:
    """
    Verify Bearer token and return token string and config.
    
    Args:
        credentials: HTTP authorization credentials
    
    Returns:
        Tuple of (token, TokenConfig)
    
    Raises:
        HTTPException: If token is invalid or disabled
    """
    token = credentials.credentials
    config = get_config()
    
    token_config = config.validate_token(token)
    
    if not token_config:
        logger.warning(f"Invalid or disabled token used: {token[:20]}...")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or disabled token"
        )
    
    # Check rate limits
    if not rate_limiter.check_rate_limit(token, token_config):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded"
        )
    
    logger.debug(f"Token verified: {token_config.name}")
    return token, token_config


def check_permission(token_config: TokenConfig, permission: str) -> bool:
    """
    Check if token has specific permission.
    
    Args:
        token_config: Token configuration
        permission: Permission to check (e.g., 'execute', 'read', 'write')
    
    Returns:
        True if permission granted, False otherwise
    """
    return permission in token_config.permissions


def require_permission(token_config: TokenConfig, permission: str):
    """
    Require specific permission or raise exception.
    
    Args:
        token_config: Token configuration
        permission: Required permission
    
    Raises:
        HTTPException: If permission not granted
    """
    if not check_permission(token_config, permission):
        logger.warning(
            f"Permission denied: {token_config.name} lacks '{permission}'"
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Permission denied: '{permission}' required"
        )


def check_server_access(
    token_config: TokenConfig, 
    server_name: str
) -> bool:
    """
    Check if token has access to server.
    
    Args:
        token_config: Token configuration
        server_name: Server name to check
    
    Returns:
        True if access granted, False otherwise
    """
    config = get_config()
    return config.server_allowed_for_token(server_name, token_config)


def require_server_access(token_config: TokenConfig, server_name: str):
    """
    Require server access or raise exception.
    
    Args:
        token_config: Token configuration
        server_name: Server name to check
    
    Raises:
        HTTPException: If access not granted
    """
    if not check_server_access(token_config, server_name):
        logger.warning(
            f"Server access denied: {token_config.name} -> {server_name}"
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Access denied to server: {server_name}"
        )


def generate_token() -> str:
    """
    Generate a new Bearer token.
    
    Returns:
        New token string with 'tok_' prefix
    """
    return f"tok_{uuid.uuid4().hex}"


def create_token_config(
    name: str,
    description: Optional[str] = None,
    permissions: Optional[list] = None,
    allowed_servers: Optional[list] = None,
    rate_limit_multiplier: float = 1.0
) -> tuple[str, TokenConfig]:
    """
    Create a new token and configuration.
    
    Args:
        name: Token name
        description: Token description
        permissions: List of permissions
        allowed_servers: List of allowed servers (patterns)
        rate_limit_multiplier: Rate limit multiplier
    
    Returns:
        Tuple of (token, TokenConfig)
    """
    token = generate_token()
    
    config = TokenConfig(
        name=name,
        description=description,
        permissions=permissions or ['execute', 'read'],
        allowed_servers=allowed_servers or ['*'],
        rate_limit_multiplier=rate_limit_multiplier,
        enabled=True,
        created_at=datetime.utcnow().isoformat() + 'Z'
    )
    
    logger.info(f"Created new token: {name}")
    return token, config


async def check_command_rate_limit(
    token: str,
    token_config: TokenConfig
):
    """
    Check command execution rate limit.
    
    Args:
        token: Bearer token
        token_config: Token configuration
    
    Raises:
        HTTPException: If rate limit exceeded
    """
    if not rate_limiter.check_rate_limit(token, token_config, is_command=True):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Command rate limit exceeded"
        )




