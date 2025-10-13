"""Tests for configuration module."""

import pytest

from src.config import Config, ServerConfig, TokenConfig


def test_config_loads_servers(test_config):
    """Test that configuration loads servers correctly."""
    assert len(test_config.servers) > 0
    assert 'test-server-01' in test_config.servers


def test_config_loads_tokens(test_config):
    """Test that configuration loads tokens correctly."""
    assert len(test_config.tokens) > 0
    assert 'tok_test123' in test_config.tokens


def test_server_config_validation():
    """Test server configuration validation."""
    # Valid config
    config = ServerConfig(
        host='192.168.1.10',
        port=22,
        user='testuser',
        ssh_key_path='/tmp/key'
    )
    assert config.host == '192.168.1.10'
    
    # Invalid port
    with pytest.raises(ValueError):
        ServerConfig(
            host='192.168.1.10',
            port=99999,  # Invalid port
            user='testuser',
            ssh_key_path='/tmp/key'
        )


def test_token_config_validation():
    """Test token configuration validation."""
    # Valid config
    config = TokenConfig(
        name='test',
        permissions=['execute', 'read']
    )
    assert 'execute' in config.permissions
    
    # Invalid permission
    with pytest.raises(ValueError):
        TokenConfig(
            name='test',
            permissions=['invalid_permission']
        )


def test_get_enabled_servers(test_config):
    """Test getting enabled servers."""
    enabled = test_config.get_enabled_servers()
    assert len(enabled) > 0
    assert all(s.enabled for s in enabled.values())


def test_get_servers_by_tag(test_config):
    """Test getting servers by tag."""
    test_servers = test_config.get_servers_by_tag('test')
    assert len(test_servers) > 0


def test_server_allowed_for_token(test_config):
    """Test server access validation for tokens."""
    token_config = test_config.tokens['tok_test123']
    
    # Wildcard should allow all servers
    assert test_config.server_allowed_for_token('test-server-01', token_config)
    assert test_config.server_allowed_for_token('any-server', token_config)
    
    # Specific server pattern
    token_config.allowed_servers = ['test-*']
    assert test_config.server_allowed_for_token('test-server-01', token_config)
    assert not test_config.server_allowed_for_token('prod-server-01', token_config)


def test_add_and_remove_server(test_config):
    """Test adding and removing servers."""
    new_server = ServerConfig(
        host='192.168.1.20',
        port=22,
        user='newuser',
        ssh_key_path='/tmp/new_key'
    )
    
    # Add server
    test_config.add_server('new-server', new_server)
    assert 'new-server' in test_config.servers
    
    # Remove server
    test_config.remove_server('new-server')
    assert 'new-server' not in test_config.servers


def test_validate_token(test_config):
    """Test token validation."""
    # Valid token
    config = test_config.validate_token('tok_test123')
    assert config is not None
    assert config.name == 'test-token'
    
    # Invalid token
    config = test_config.validate_token('invalid_token')
    assert config is None




