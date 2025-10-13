"""Tests for authentication module."""

import pytest
import time

from src.auth import (
    RateLimiter,
    generate_token,
    create_token_config,
    check_permission,
    check_server_access
)


def test_generate_token():
    """Test token generation."""
    token = generate_token()
    assert token.startswith('tok_')
    assert len(token) > 10
    
    # Tokens should be unique
    token2 = generate_token()
    assert token != token2


def test_create_token_config():
    """Test token config creation."""
    token, config = create_token_config(
        name='test-token',
        description='Test token',
        permissions=['execute', 'read'],
        allowed_servers=['test-*']
    )
    
    assert token.startswith('tok_')
    assert config.name == 'test-token'
    assert 'execute' in config.permissions
    assert 'test-*' in config.allowed_servers


def test_check_permission(test_token_config):
    """Test permission checking."""
    assert check_permission(test_token_config, 'execute')
    assert check_permission(test_token_config, 'read')
    assert not check_permission(test_token_config, 'manage')


def test_check_server_access(test_config, test_token_config):
    """Test server access checking."""
    # Wildcard access
    test_token_config.allowed_servers = ['*']
    assert check_server_access(test_token_config, 'any-server')
    
    # Pattern matching
    test_token_config.allowed_servers = ['test-*', 'prod-web-*']
    assert check_server_access(test_token_config, 'test-server-01')
    assert check_server_access(test_token_config, 'prod-web-01')
    assert not check_server_access(test_token_config, 'prod-db-01')


def test_rate_limiter():
    """Test rate limiter."""
    limiter = RateLimiter()
    
    token_config = create_token_config(
        name='test',
        permissions=['execute'],
        rate_limit_multiplier=1.0
    )[1]
    
    # First request should pass
    assert limiter.check_rate_limit('tok_test', token_config)
    
    # Get stats
    stats = limiter.get_stats('tok_test')
    assert stats['requests_last_minute'] == 1
    assert stats['commands_last_hour'] == 0


def test_rate_limiter_command():
    """Test rate limiter for commands."""
    limiter = RateLimiter()
    
    token_config = create_token_config(
        name='test',
        permissions=['execute'],
        rate_limit_multiplier=1.0
    )[1]
    
    # Command execution
    assert limiter.check_rate_limit('tok_test', token_config, is_command=True)
    
    stats = limiter.get_stats('tok_test')
    assert stats['commands_last_hour'] == 1




