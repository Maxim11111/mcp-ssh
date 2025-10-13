"""Audit logging module for tracking all operations."""

import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any
from logging.handlers import RotatingFileHandler

logger = logging.getLogger(__name__)


class AuditLogger:
    """Audit logger for tracking commands and operations."""
    
    def __init__(self, logs_dir: Optional[str] = None):
        self.logs_dir = Path(logs_dir or os.getenv('LOGS_DIR', './logs'))
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        
        # Setup audit log file handler
        audit_file = self.logs_dir / 'audit.log'
        self.audit_handler = RotatingFileHandler(
            audit_file,
            maxBytes=10 * 1024 * 1024,  # 10 MB
            backupCount=10,
            encoding='utf-8'
        )
        self.audit_handler.setLevel(logging.INFO)
        
        # JSON formatter for structured logging
        formatter = logging.Formatter(
            '%(message)s'
        )
        self.audit_handler.setFormatter(formatter)
        
        # Setup audit logger
        self.audit_logger = logging.getLogger('mcp_ssh.audit')
        self.audit_logger.setLevel(logging.INFO)
        self.audit_logger.addHandler(self.audit_handler)
        self.audit_logger.propagate = False
    
    def _create_audit_entry(
        self,
        event_type: str,
        token_name: str,
        server_name: Optional[str] = None,
        command: Optional[str] = None,
        result: Optional[str] = None,
        exit_code: Optional[int] = None,
        duration_ms: Optional[int] = None,
        error: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Create audit entry dictionary."""
        entry = {
            'timestamp': datetime.utcnow().isoformat() + 'Z',
            'event_type': event_type,
            'token_name': token_name,
        }
        
        if server_name:
            entry['server_name'] = server_name
        if command:
            entry['command'] = command
        if result:
            entry['result'] = result
        if exit_code is not None:
            entry['exit_code'] = exit_code
        if duration_ms is not None:
            entry['duration_ms'] = duration_ms
        if error:
            entry['error'] = error
        if metadata:
            entry['metadata'] = metadata
        
        return entry
    
    def log_command_execution(
        self,
        token_name: str,
        server_name: str,
        command: str,
        exit_code: int,
        duration_ms: int,
        stdout: Optional[str] = None,
        stderr: Optional[str] = None
    ):
        """Log command execution."""
        entry = self._create_audit_entry(
            event_type='command_execution',
            token_name=token_name,
            server_name=server_name,
            command=command,
            result='success' if exit_code == 0 else 'failed',
            exit_code=exit_code,
            duration_ms=duration_ms,
            metadata={
                'stdout_length': len(stdout) if stdout else 0,
                'stderr_length': len(stderr) if stderr else 0,
            }
        )
        
        self.audit_logger.info(json.dumps(entry))
        
        logger.info(
            f"Command executed - Token: {token_name}, "
            f"Server: {server_name}, Exit: {exit_code}"
        )
    
    def log_command_denied(
        self,
        token_name: str,
        server_name: str,
        command: str,
        reason: str
    ):
        """Log denied command attempt."""
        entry = self._create_audit_entry(
            event_type='command_denied',
            token_name=token_name,
            server_name=server_name,
            command=command,
            result='denied',
            error=reason
        )
        
        self.audit_logger.warning(json.dumps(entry))
        
        logger.warning(
            f"Command denied - Token: {token_name}, "
            f"Server: {server_name}, Reason: {reason}"
        )
    
    def log_file_operation(
        self,
        token_name: str,
        server_name: str,
        operation: str,
        file_path: str,
        result: str,
        error: Optional[str] = None
    ):
        """Log file operation (read/write/upload/download)."""
        entry = self._create_audit_entry(
            event_type='file_operation',
            token_name=token_name,
            server_name=server_name,
            result=result,
            error=error,
            metadata={
                'operation': operation,
                'file_path': file_path
            }
        )
        
        self.audit_logger.info(json.dumps(entry))
        
        logger.info(
            f"File operation - Token: {token_name}, "
            f"Server: {server_name}, Op: {operation}, Result: {result}"
        )
    
    def log_ssh_connection(
        self,
        token_name: str,
        server_name: str,
        result: str,
        error: Optional[str] = None
    ):
        """Log SSH connection attempt."""
        entry = self._create_audit_entry(
            event_type='ssh_connection',
            token_name=token_name,
            server_name=server_name,
            result=result,
            error=error
        )
        
        self.audit_logger.info(json.dumps(entry))
        
        logger.info(
            f"SSH connection - Token: {token_name}, "
            f"Server: {server_name}, Result: {result}"
        )
    
    def log_authentication(
        self,
        token_name: str,
        result: str,
        reason: Optional[str] = None
    ):
        """Log authentication attempt."""
        entry = self._create_audit_entry(
            event_type='authentication',
            token_name=token_name,
            result=result,
            error=reason
        )
        
        self.audit_logger.info(json.dumps(entry))
        
        logger.info(f"Authentication - Token: {token_name}, Result: {result}")
    
    def log_rate_limit(
        self,
        token_name: str,
        limit_type: str,
        current_count: int,
        limit: int
    ):
        """Log rate limit event."""
        entry = self._create_audit_entry(
            event_type='rate_limit_exceeded',
            token_name=token_name,
            result='blocked',
            metadata={
                'limit_type': limit_type,
                'current_count': current_count,
                'limit': limit
            }
        )
        
        self.audit_logger.warning(json.dumps(entry))
        
        logger.warning(
            f"Rate limit exceeded - Token: {token_name}, "
            f"Type: {limit_type}, Count: {current_count}/{limit}"
        )
    
    def log_server_added(
        self,
        admin_token: str,
        server_name: str
    ):
        """Log server addition."""
        entry = self._create_audit_entry(
            event_type='server_added',
            token_name=admin_token,
            server_name=server_name,
            result='success'
        )
        
        self.audit_logger.info(json.dumps(entry))
        
        logger.info(f"Server added - {server_name} by {admin_token}")
    
    def log_server_removed(
        self,
        admin_token: str,
        server_name: str
    ):
        """Log server removal."""
        entry = self._create_audit_entry(
            event_type='server_removed',
            token_name=admin_token,
            server_name=server_name,
            result='success'
        )
        
        self.audit_logger.info(json.dumps(entry))
        
        logger.info(f"Server removed - {server_name} by {admin_token}")
    
    def log_token_created(
        self,
        admin_token: str,
        new_token_name: str
    ):
        """Log token creation."""
        entry = self._create_audit_entry(
            event_type='token_created',
            token_name=admin_token,
            result='success',
            metadata={'new_token_name': new_token_name}
        )
        
        self.audit_logger.info(json.dumps(entry))
        
        logger.info(f"Token created - {new_token_name} by {admin_token}")
    
    def log_token_revoked(
        self,
        admin_token: str,
        revoked_token_name: str
    ):
        """Log token revocation."""
        entry = self._create_audit_entry(
            event_type='token_revoked',
            token_name=admin_token,
            result='success',
            metadata={'revoked_token_name': revoked_token_name}
        )
        
        self.audit_logger.info(json.dumps(entry))
        
        logger.info(f"Token revoked - {revoked_token_name} by {admin_token}")


# Global audit logger instance
_audit_logger: Optional[AuditLogger] = None


def get_audit_logger() -> AuditLogger:
    """Get global audit logger instance."""
    global _audit_logger
    if _audit_logger is None:
        _audit_logger = AuditLogger()
    return _audit_logger


def setup_logging(log_level: str = 'INFO'):
    """Setup application logging."""
    # Configure root logger
    logging.basicConfig(
        level=getattr(logging, log_level.upper()),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(),
            RotatingFileHandler(
                Path(os.getenv('LOGS_DIR', './logs')) / 'mcp-ssh.log',
                maxBytes=10 * 1024 * 1024,
                backupCount=5
            )
        ]
    )
    
    # Initialize audit logger
    get_audit_logger()
    
    logger.info(f"Logging initialized at {log_level} level")




