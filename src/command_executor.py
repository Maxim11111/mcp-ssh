"""Command executor with real-time stdout/stderr streaming."""

import asyncio
import time
import select
from typing import Optional, Callable, Dict, Any
import logging

from src.ssh_manager import SSHConnection, create_ssh_connection, close_ssh_connection
from src.security import SecurityContext
from src.audit import get_audit_logger

logger = logging.getLogger(__name__)


class CommandResult:
    """Result of command execution."""
    
    def __init__(
        self,
        exit_code: int,
        stdout: str,
        stderr: str,
        duration_ms: int
    ):
        self.exit_code = exit_code
        self.stdout = stdout
        self.stderr = stderr
        self.duration_ms = duration_ms
        self.success = exit_code == 0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'exit_code': self.exit_code,
            'stdout': self.stdout,
            'stderr': self.stderr,
            'duration_ms': self.duration_ms,
            'success': self.success
        }


class CommandExecutor:
    """Executes commands on remote servers via SSH."""
    
    def __init__(
        self,
        connection: SSHConnection,
        security_context: SecurityContext
    ):
        self.connection = connection
        self.security_context = security_context
        self.audit = get_audit_logger()
    
    async def execute(
        self,
        command: str,
        timeout: int = 300,
        on_stdout: Optional[Callable[[str], None]] = None,
        on_stderr: Optional[Callable[[str], None]] = None
    ) -> CommandResult:
        """
        Execute command with optional streaming callbacks.
        
        Args:
            command: Command to execute
            timeout: Timeout in seconds
            on_stdout: Callback for stdout lines (async)
            on_stderr: Callback for stderr lines (async)
        
        Returns:
            CommandResult
        
        Raises:
            Exception: If command execution fails
        """
        start_time = time.time()
        
        # Validate and sanitize command
        is_valid, sanitized_cmd, error = self.security_context.validate_and_sanitize(command)
        
        if not is_valid:
            self.audit.log_command_denied(
                self.security_context.token_name,
                self.security_context.server_name,
                command,
                error or "Unknown error"
            )
            raise ValueError(f"Command validation failed: {error}")
        
        try:
            # Execute command in thread pool (paramiko is blocking)
            result = await asyncio.get_event_loop().run_in_executor(
                None,
                self._execute_blocking,
                sanitized_cmd,
                timeout,
                on_stdout,
                on_stderr
            )
            
            duration_ms = int((time.time() - start_time) * 1000)
            result.duration_ms = duration_ms
            
            # Audit log
            self.audit.log_command_execution(
                self.security_context.token_name,
                self.security_context.server_name,
                sanitized_cmd,
                result.exit_code,
                duration_ms,
                result.stdout,
                result.stderr
            )
            
            return result
            
        except Exception as e:
            duration_ms = int((time.time() - start_time) * 1000)
            logger.error(f"Command execution failed: {e}")
            
            self.audit.log_command_denied(
                self.security_context.token_name,
                self.security_context.server_name,
                command,
                str(e)
            )
            
            raise
    
    def _execute_blocking(
        self,
        command: str,
        timeout: int,
        on_stdout: Optional[Callable],
        on_stderr: Optional[Callable]
    ) -> CommandResult:
        """
        Execute command in blocking mode (runs in thread pool).
        
        This is the actual SSH command execution with real-time streaming.
        """
        logger.info(
            f"Executing command on {self.connection.server_name}: {command}"
        )
        
        # Get transport and open session
        transport = self.connection.client.get_transport()
        if not transport or not transport.is_active():
            raise RuntimeError("SSH connection is not active")
        
        channel = transport.open_session()
        channel.settimeout(timeout)
        
        try:
            # Execute command
            channel.exec_command(command)
            
            # Buffers for output
            stdout_buffer = []
            stderr_buffer = []
            
            # Read output in real-time
            while True:
                # Check if channel has data
                if channel.recv_ready():
                    data = channel.recv(4096).decode('utf-8', errors='replace')
                    stdout_buffer.append(data)
                    
                    if on_stdout:
                        # Call streaming callback
                        for line in data.splitlines():
                            if line:
                                on_stdout(line)
                
                if channel.recv_stderr_ready():
                    data = channel.recv_stderr(4096).decode('utf-8', errors='replace')
                    stderr_buffer.append(data)
                    
                    if on_stderr:
                        for line in data.splitlines():
                            if line:
                                on_stderr(line)
                
                # Check if command finished
                if channel.exit_status_ready():
                    break
                
                # Small sleep to prevent busy waiting
                time.sleep(0.01)
            
            # Get final output
            while channel.recv_ready():
                data = channel.recv(4096).decode('utf-8', errors='replace')
                stdout_buffer.append(data)
                if on_stdout:
                    for line in data.splitlines():
                        if line:
                            on_stdout(line)
            
            while channel.recv_stderr_ready():
                data = channel.recv_stderr(4096).decode('utf-8', errors='replace')
                stderr_buffer.append(data)
                if on_stderr:
                    for line in data.splitlines():
                        if line:
                            on_stderr(line)
            
            # Get exit code
            exit_code = channel.recv_exit_status()
            
            stdout = ''.join(stdout_buffer)
            stderr = ''.join(stderr_buffer)
            
            logger.info(
                f"Command completed on {self.connection.server_name}: "
                f"exit_code={exit_code}"
            )
            
            return CommandResult(
                exit_code=exit_code,
                stdout=stdout,
                stderr=stderr,
                duration_ms=0  # Will be set by caller
            )
            
        finally:
            channel.close()


async def execute_command(
    server_name: str,
    token_name: str,
    permissions: list,
    command: str,
    timeout: int = 300,
    on_stdout: Optional[Callable[[str], None]] = None,
    on_stderr: Optional[Callable[[str], None]] = None,
    auto_close: bool = True
) -> tuple[CommandResult, str]:
    """
    Execute command on server with optional streaming.
    
    Args:
        server_name: Server to execute on
        token_name: Token name for audit
        permissions: Token permissions
        command: Command to execute
        timeout: Timeout in seconds
        on_stdout: Callback for stdout streaming
        on_stderr: Callback for stderr streaming
        auto_close: Auto-close connection after execution
    
    Returns:
        Tuple of (CommandResult, session_id)
    """
    # Create SSH connection
    session_id, connection = create_ssh_connection(server_name, token_name)
    
    try:
        # Create security context
        security_context = SecurityContext(
            token_name=token_name,
            server_name=server_name,
            permissions=permissions
        )
        
        # Create executor
        executor = CommandExecutor(connection, security_context)
        
        # Execute command
        result = await executor.execute(
            command=command,
            timeout=timeout,
            on_stdout=on_stdout,
            on_stderr=on_stderr
        )
        
        return result, session_id
        
    finally:
        if auto_close:
            close_ssh_connection(session_id)


async def execute_command_on_multiple(
    server_names: list,
    token_name: str,
    permissions: list,
    command: str,
    timeout: int = 300
) -> Dict[str, CommandResult]:
    """
    Execute command on multiple servers in parallel.
    
    Args:
        server_names: List of servers to execute on
        token_name: Token name for audit
        permissions: Token permissions
        command: Command to execute
        timeout: Timeout in seconds
    
    Returns:
        Dictionary mapping server_name to CommandResult
    """
    tasks = []
    
    for server_name in server_names:
        task = execute_command(
            server_name=server_name,
            token_name=token_name,
            permissions=permissions,
            command=command,
            timeout=timeout,
            auto_close=True
        )
        tasks.append((server_name, task))
    
    results = {}
    
    for server_name, task in tasks:
        try:
            result, _ = await task
            results[server_name] = result
        except Exception as e:
            logger.error(f"Failed to execute on {server_name}: {e}")
            results[server_name] = CommandResult(
                exit_code=-1,
                stdout="",
                stderr=str(e),
                duration_ms=0
            )
    
    return results




