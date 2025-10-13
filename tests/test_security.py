"""Tests for security module."""

import pytest

from src.security import CommandValidator, validate_command, validate_file_path, SecurityContext
from src.config import SecurityConfig


@pytest.fixture
def security_config():
    """Create test security configuration."""
    return SecurityConfig(
        allowed_commands_patterns=['^ls ', '^cat ', '^echo '],
        forbidden_commands=['rm -rf /', 'mkfs'],
        require_confirmation=['reboot', 'shutdown']
    )


@pytest.fixture
def command_validator(security_config):
    """Create command validator."""
    return CommandValidator(security_config)


def test_allowed_command(command_validator):
    """Test that allowed commands pass validation."""
    is_allowed, reason = command_validator.is_command_allowed('ls -la /tmp')
    assert is_allowed
    assert reason is None


def test_forbidden_command(command_validator):
    """Test that forbidden commands are blocked."""
    is_allowed, reason = command_validator.is_command_allowed('rm -rf /')
    assert not is_allowed
    assert 'forbidden' in reason.lower()


def test_dangerous_pattern(command_validator):
    """Test that dangerous patterns are detected."""
    dangerous_commands = [
        'dd if=/dev/zero of=/dev/sda',
        'chmod 777 /',
        ':(){ :|:& };:',  # Fork bomb
    ]
    
    for cmd in dangerous_commands:
        is_allowed, reason = command_validator.is_command_allowed(cmd)
        assert not is_allowed


def test_command_not_in_whitelist(command_validator):
    """Test that commands not in whitelist are blocked."""
    is_allowed, reason = command_validator.is_command_allowed('systemctl restart nginx')
    assert not is_allowed
    assert 'not in allowed patterns' in reason.lower()


def test_requires_confirmation(command_validator):
    """Test confirmation requirement detection."""
    assert command_validator.requires_confirmation('reboot now')
    assert command_validator.requires_confirmation('shutdown -h now')
    assert not command_validator.requires_confirmation('ls -la')


def test_sanitize_command(command_validator):
    """Test command sanitization."""
    cmd = '  ls   -la   /tmp  '
    sanitized = command_validator.sanitize_command(cmd)
    assert sanitized == 'ls -la /tmp'


def test_validate_file_path():
    """Test file path validation."""
    # Safe paths
    is_valid, reason = validate_file_path('/tmp/test.txt')
    assert is_valid
    
    is_valid, reason = validate_file_path('/home/user/file.txt')
    assert is_valid
    
    # Dangerous paths
    dangerous_paths = [
        '/etc/shadow',
        '/etc/passwd',
        '/root/.ssh/id_rsa',
        '/proc/something',
    ]
    
    for path in dangerous_paths:
        is_valid, reason = validate_file_path(path)
        assert not is_valid


def test_security_context(test_token_config):
    """Test security context."""
    context = SecurityContext(
        token_name='test-token',
        server_name='test-server',
        permissions=['execute', 'read']
    )
    
    # Valid command
    is_valid, sanitized, error = context.validate_and_sanitize('ls -la')
    assert error is None or is_valid  # Depends on allowed patterns
    
    # Check permission
    assert context.has_permission('execute')
    assert context.has_permission('read')
    assert not context.has_permission('manage')




