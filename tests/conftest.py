"""Pytest configuration and fixtures."""

import pytest
import tempfile
import json
from pathlib import Path

from src.config import Config, ServerConfig, TokenConfig


@pytest.fixture
def temp_config_dir():
    """Create temporary configuration directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config_dir = Path(tmpdir) / 'config'
        config_dir.mkdir()
        
        # Create example servers.json
        servers_data = {
            'servers': {
                'test-server-01': {
                    'host': '192.168.1.10',
                    'port': 22,
                    'user': 'testuser',
                    'ssh_key_path': '/tmp/test_key',
                    'tags': ['test'],
                    'enabled': True
                }
            },
            'security': {
                'allowed_commands_patterns': ['^ls ', '^cat '],
                'forbidden_commands': ['rm -rf /'],
                'rate_limit': {
                    'requests_per_minute': 60,
                    'commands_per_hour': 100
                }
            }
        }
        
        with open(config_dir / 'servers.json', 'w') as f:
            json.dump(servers_data, f)
        
        # Create example tokens.json
        tokens_data = {
            'tokens': {
                'tok_test123': {
                    'name': 'test-token',
                    'permissions': ['execute', 'read'],
                    'allowed_servers': ['*'],
                    'enabled': True
                }
            }
        }
        
        with open(config_dir / 'tokens.json', 'w') as f:
            json.dump(tokens_data, f)
        
        yield str(config_dir)


@pytest.fixture
def test_config(temp_config_dir):
    """Create test configuration instance."""
    return Config(temp_config_dir)


@pytest.fixture
def test_server_config():
    """Create test server configuration."""
    return ServerConfig(
        host='192.168.1.10',
        port=22,
        user='testuser',
        ssh_key_path='/tmp/test_key',
        tags=['test'],
        enabled=True
    )


@pytest.fixture
def test_token_config():
    """Create test token configuration."""
    return TokenConfig(
        name='test-token',
        permissions=['execute', 'read', 'write'],
        allowed_servers=['*'],
        enabled=True
    )




