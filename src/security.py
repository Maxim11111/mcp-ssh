"""Security module for command validation."""

import re
import logging
from typing import List, Tuple, Optional

from src.config import get_config, SecurityConfig

logger = logging.getLogger(__name__)


class CommandValidator:
    """Validates commands before execution."""
    
    def __init__(self, security_config: Optional[SecurityConfig] = None):
        if security_config is None:
            config = get_config()
            security_config = config.security
        
        self.security_config = security_config
        
        # Compile regex patterns for allowed commands
        self.allowed_patterns = [
            re.compile(pattern) 
            for pattern in security_config.allowed_commands_patterns
        ]
    
    def is_command_allowed(self, command: str) -> Tuple[bool, Optional[str]]:
        """
        Check if command is allowed.
        
        Args:
            command: Command to validate
        
        Returns:
            Tuple of (is_allowed, reason_if_denied)
        """
        command = command.strip()
        
        if not command:
            return False, "Empty command"
        
        # Check forbidden commands first
        for forbidden in self.security_config.forbidden_commands:
            if forbidden.lower() in command.lower():
                logger.warning(f"Forbidden command detected: {command}")
                return False, f"Forbidden command: contains '{forbidden}'"
        
        # Check dangerous patterns
        if self._is_dangerous_pattern(command):
            logger.warning(f"Dangerous pattern detected: {command}")
            return False, "Dangerous command pattern detected"
        
        # Check against allowed patterns
        if not self.allowed_patterns:
            # If no patterns configured, allow all (not recommended for production)
            logger.warning("No allowed patterns configured - allowing all commands")
            return True, None
        
        for pattern in self.allowed_patterns:
            if pattern.match(command):
                return True, None
        
        logger.warning(f"Command not in allowed patterns: {command}")
        return False, "Command not in allowed patterns"
    
    def _is_dangerous_pattern(self, command: str) -> bool:
        """Check for dangerous command patterns."""
        dangerous_patterns = [
            # File system destruction
            r'rm\s+-rf\s+/',  # rm -rf /
            r'rm\s+-rf\s+/[^/]',  # rm -rf /anything
            r'>\s*/dev/sd[a-z]',  # > /dev/sda
            r'dd\s+if=/dev/zero',  # dd if=/dev/zero
            r'mkfs\.',  # mkfs.*
            r'format\s+',  # format commands
            
            # System destruction
            r':\(\)\{.*:\|:&\s*\};:',  # Fork bomb
            r'chmod\s+777\s+/',  # chmod 777 /
            r'chown.*root:root\s+/',  # chown root:root /
            r'mount\s+-o\s+remount.*ro\s+/',  # remount root read-only
            
            # Database destruction
            r'drop\s+database\s+',  # DROP DATABASE
            r'drop\s+table\s+',  # DROP TABLE
            r'truncate\s+table\s+',  # TRUNCATE TABLE
            r'delete\s+from\s+.*\s+where\s+1=1',  # DELETE FROM table WHERE 1=1
            
            # Service destruction
            r'systemctl\s+stop\s+ssh',  # Stop SSH service
            r'systemctl\s+disable\s+ssh',  # Disable SSH service
            r'service\s+ssh\s+stop',  # Stop SSH service (legacy)
            
            # Network destruction
            r'iptables\s+-F',  # Flush iptables
            r'iptables\s+-P\s+INPUT\s+DROP',  # Drop all input
            r'ufw\s+--force\s+reset',  # Reset UFW firewall
            
            # User/group destruction
            r'userdel\s+-r\s+',  # Delete user with home directory
            r'groupdel\s+',  # Delete group
            r'passwd\s+-l\s+root',  # Lock root account
            
            # Process destruction
            r'killall\s+-9\s+',  # Kill all processes
            r'pkill\s+-9\s+',  # Kill processes by pattern
            r'kill\s+-9\s+1',  # Kill init process
            
            # Backup destruction
            r'rm\s+-rf\s+.*\.bak',  # Remove backup files
            r'rm\s+-rf\s+.*backup',  # Remove backup directories
            
            # Log destruction
            r'>\s+/var/log/',  # Clear log files
            r'rm\s+-rf\s+/var/log/',  # Remove log directory
            
            # Configuration destruction
            r'rm\s+-rf\s+/etc/',  # Remove etc directory
            r'>\s+/etc/passwd',  # Clear passwd file
            r'>\s+/etc/shadow',  # Clear shadow file
            
            # Docker destruction
            r'docker\s+rm\s+-f\s+',  # Force remove containers
            r'docker\s+rmi\s+-f\s+',  # Force remove images
            r'docker\s+system\s+prune\s+-a\s+--force',  # Prune all Docker data
            
            # Package destruction
            r'apt-get\s+remove\s+--purge\s+',  # Purge packages
            r'yum\s+remove\s+-y\s+',  # Remove packages
            r'dnf\s+remove\s+-y\s+',  # Remove packages
            
            # Cron destruction
            r'crontab\s+-r',  # Remove crontab
            r'rm\s+-rf\s+/var/spool/cron/',  # Remove cron jobs
            
            # System files destruction
            r'rm\s+-rf\s+/boot/',  # Remove boot directory
            r'rm\s+-rf\s+/lib/',  # Remove lib directory
            r'rm\s+-rf\s+/usr/',  # Remove usr directory
            r'rm\s+-rf\s+/bin/',  # Remove bin directory
            r'rm\s+-rf\s+/sbin/',  # Remove sbin directory
            
            # Script execution with dangerous content
            r'curl\s+.*\s+\|\s+sh',  # curl | sh
            r'wget\s+.*\s+\|\s+sh',  # wget | sh
            r'echo\s+.*\s+\|\s+sh',  # echo | sh
        ]
        
        for pattern in dangerous_patterns:
            if re.search(pattern, command, re.IGNORECASE):
                return True
        
        return False
    
    def requires_confirmation(self, command: str) -> bool:
        """Check if command requires user confirmation."""
        command_lower = command.lower()
        
        for confirmation_cmd in self.security_config.require_confirmation:
            if confirmation_cmd.lower() in command_lower:
                return True
        
        return False
    
    def sanitize_command(self, command: str) -> str:
        """
        Sanitize command (basic cleanup).
        
        Args:
            command: Command to sanitize
        
        Returns:
            Sanitized command
        """
        # Remove multiple spaces
        command = ' '.join(command.split())
        
        # Strip leading/trailing whitespace
        command = command.strip()
        
        return command


def validate_command(command: str) -> Tuple[bool, Optional[str]]:
    """
    Validate command using global configuration.
    
    Args:
        command: Command to validate
    
    Returns:
        Tuple of (is_allowed, reason_if_denied)
    """
    validator = CommandValidator()
    return validator.is_command_allowed(command)


def validate_file_path(path: str) -> Tuple[bool, Optional[str]]:
    """
    Validate file path for safety.
    
    Args:
        path: File path to validate
    
    Returns:
        Tuple of (is_valid, reason_if_invalid)
    """
    # Check for null bytes
    if '\x00' in path:
        return False, "Path contains null bytes"
    
    # Check for dangerous paths
    dangerous_paths = [
        '/etc/shadow',
        '/etc/passwd',
        '/root/.ssh/id_',
        '/home/*/.ssh/id_',
        '/var/lib/docker',
        '/proc/',
        '/sys/',
    ]
    
    for dangerous in dangerous_paths:
        if '*' in dangerous:
            # Wildcard pattern
            pattern = dangerous.replace('*', '.*')
            if re.match(pattern, path):
                return False, f"Access to {dangerous} is restricted"
        else:
            if path.startswith(dangerous):
                return False, f"Access to {dangerous} is restricted"
    
    return True, None


class SecurityContext:
    """Security context for command execution."""
    
    def __init__(
        self,
        token_name: str,
        server_name: str,
        permissions: List[str]
    ):
        self.token_name = token_name
        self.server_name = server_name
        self.permissions = permissions
        self.validator = CommandValidator()
    
    def validate_and_sanitize(
        self, 
        command: str
    ) -> Tuple[bool, str, Optional[str]]:
        """
        Validate and sanitize command.
        
        Args:
            command: Command to validate
        
        Returns:
            Tuple of (is_valid, sanitized_command, error_message)
        """
        # Sanitize first
        sanitized = self.validator.sanitize_command(command)
        
        # Validate
        is_allowed, reason = self.validator.is_command_allowed(sanitized)
        
        if not is_allowed:
            return False, sanitized, reason
        
        return True, sanitized, None
    
    def requires_confirmation(self, command: str) -> bool:
        """Check if command requires confirmation."""
        return self.validator.requires_confirmation(command)
    
    def has_permission(self, permission: str) -> bool:
        """Check if context has specific permission."""
        return permission in self.permissions
    
    def log_command(self, command: str, result: str = "pending"):
        """Log command execution attempt."""
        logger.info(
            f"Command execution - "
            f"Token: {self.token_name}, "
            f"Server: {self.server_name}, "
            f"Command: {command}, "
            f"Result: {result}"
        )




