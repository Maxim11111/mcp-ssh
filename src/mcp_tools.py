"""MCP tools for LLM agents."""

import asyncio
import base64
from typing import Dict, Any, List, Optional
import logging

from src.config import get_config, TokenConfig
from src.command_executor import execute_command, execute_command_on_multiple, CommandResult
from src.ssh_manager import (
    create_ssh_connection,
    close_ssh_connection,
    get_pool_stats,
    SSHConnectionError,
)
from src.auth import check_permission, require_permission, check_server_access, require_server_access
from src.audit import get_audit_logger
from src.security import SecurityContext, validate_command, validate_file_path

logger = logging.getLogger(__name__)


class MCPTools:
    """Collection of MCP tools for LLM agents."""
    
    def __init__(self):
        self.audit = get_audit_logger()
    
    async def execute_command_tool(
        self,
        token_config: TokenConfig,
        server: str,
        command: str,
        timeout: int = 300
    ) -> Dict[str, Any]:
        """
        Execute a shell command on a server.
        
        Args:
            token_config: Token configuration
            server: Server name
            command: Command to execute
            timeout: Timeout in seconds
        
        Returns:
            Dict with execution results
        """
        # Check permissions
        require_permission(token_config, 'execute')
        require_server_access(token_config, server)
        
        # Validate command for security
        is_valid, reason = validate_command(command)
        if not is_valid:
            self.audit.log_command_execution(
                token_config.name,
                server,
                command,
                'blocked',
                reason
            )
            return {
                'success': False,
                'server': server,
                'command': command,
                'error': f'Security validation failed: {reason}',
                'blocked': True
            }
        
        try:
            result, session_id = await execute_command(
                server_name=server,
                token_name=token_config.name,
                permissions=token_config.permissions,
                command=command,
                timeout=timeout,
                auto_close=True
            )
            
            return {
                'success': result.success,
                'server': server,
                'command': command,
                'exit_code': result.exit_code,
                'stdout': result.stdout,
                'stderr': result.stderr,
                'duration_ms': result.duration_ms
            }
            
        except Exception as e:
            logger.error(f"Command execution failed: {e}")
            return {
                'success': False,
                'server': server,
                'command': command,
                'error': str(e)
            }
    
    async def execute_on_multiple_tool(
        self,
        token_config: TokenConfig,
        servers: List[str],
        command: str,
        timeout: int = 300
    ) -> Dict[str, Any]:
        """
        Execute a command on multiple servers in parallel.
        
        Args:
            token_config: Token configuration
            servers: List of server names (or patterns)
            command: Command to execute
            timeout: Timeout in seconds
        
        Returns:
            Dict with results for each server
        """
        # Check permissions
        require_permission(token_config, 'execute')
        
        # Resolve server patterns and filter by access
        config = get_config()
        resolved_servers = []
        
        for server_pattern in servers:
            if '*' in server_pattern:
                # Wildcard pattern - find matching servers
                prefix = server_pattern.replace('*', '')
                for server_name in config.get_enabled_servers().keys():
                    if server_name.startswith(prefix):
                        if check_server_access(token_config, server_name):
                            resolved_servers.append(server_name)
            else:
                # Exact server name
                if check_server_access(token_config, server_pattern):
                    resolved_servers.append(server_pattern)
        
        if not resolved_servers:
            return {
                'success': False,
                'error': 'No accessible servers found'
            }
        
        # Execute on all servers
        results = await execute_command_on_multiple(
            server_names=resolved_servers,
            token_name=token_config.name,
            permissions=token_config.permissions,
            command=command,
            timeout=timeout
        )
        
        # Format results
        formatted_results = {}
        for server, result in results.items():
            formatted_results[server] = {
                'success': result.success,
                'exit_code': result.exit_code,
                'stdout': result.stdout,
                'stderr': result.stderr,
                'duration_ms': result.duration_ms
            }
        
        return {
            'success': True,
            'command': command,
            'results': formatted_results,
            'summary': {
                'total': len(formatted_results),
                'succeeded': sum(1 for r in formatted_results.values() if r['success']),
                'failed': sum(1 for r in formatted_results.values() if not r['success'])
            }
        }
    
    async def read_file_tool(
        self,
        token_config: TokenConfig,
        server: str,
        file_path: str
    ) -> Dict[str, Any]:
        """
        Read a file from a server.
        
        Args:
            token_config: Token configuration
            server: Server name
            file_path: Path to file
        
        Returns:
            Dict with file contents
        """
        require_permission(token_config, 'read')
        require_server_access(token_config, server)
        
        # Validate file path for security
        is_valid, reason = validate_file_path(file_path)
        if not is_valid:
            self.audit.log_file_operation(
                token_config.name,
                server,
                'read',
                file_path,
                'blocked',
                reason
            )
            return {
                'success': False,
                'server': server,
                'file_path': file_path,
                'error': f'Security validation failed: {reason}',
                'blocked': True
            }
        
        command = f'cat "{file_path}"'
        
        try:
            result, _ = await execute_command(
                server_name=server,
                token_name=token_config.name,
                permissions=token_config.permissions,
                command=command,
                timeout=60,
                auto_close=True
            )
            
            if result.success:
                self.audit.log_file_operation(
                    token_config.name,
                    server,
                    'read',
                    file_path,
                    'success'
                )
                
                return {
                    'success': True,
                    'server': server,
                    'file_path': file_path,
                    'contents': result.stdout,
                    'size_bytes': len(result.stdout)
                }
            else:
                self.audit.log_file_operation(
                    token_config.name,
                    server,
                    'read',
                    file_path,
                    'failed',
                    result.stderr
                )
                
                return {
                    'success': False,
                    'server': server,
                    'file_path': file_path,
                    'error': result.stderr
                }
                
        except Exception as e:
            self.audit.log_file_operation(
                token_config.name,
                server,
                'read',
                file_path,
                'failed',
                str(e)
            )
            
            return {
                'success': False,
                'server': server,
                'file_path': file_path,
                'error': str(e)
            }
    
    async def write_file_tool(
        self,
        token_config: TokenConfig,
        server: str,
        file_path: str,
        contents: str,
        mode: str = 'overwrite'
    ) -> Dict[str, Any]:
        """
        Write a file to a server.
        
        Args:
            token_config: Token configuration
            server: Server name
            file_path: Path to file
            contents: File contents
            mode: 'overwrite' or 'append'
        
        Returns:
            Dict with operation results
        """
        require_permission(token_config, 'write')
        require_server_access(token_config, server)
        
        # Validate file path for security
        is_valid, reason = validate_file_path(file_path)
        if not is_valid:
            self.audit.log_file_operation(
                token_config.name,
                server,
                f'write_{mode}',
                file_path,
                'blocked',
                reason
            )
            return {
                'success': False,
                'server': server,
                'file_path': file_path,
                'error': f'Security validation failed: {reason}',
                'blocked': True
            }
        
        # Escape contents for shell
        contents_b64 = base64.b64encode(contents.encode('utf-8')).decode('ascii')
        
        if mode == 'append':
            command = f'echo "{contents_b64}" | base64 -d >> "{file_path}"'
        else:
            command = f'echo "{contents_b64}" | base64 -d > "{file_path}"'
        
        try:
            result, _ = await execute_command(
                server_name=server,
                token_name=token_config.name,
                permissions=token_config.permissions,
                command=command,
                timeout=60,
                auto_close=True
            )
            
            if result.success:
                self.audit.log_file_operation(
                    token_config.name,
                    server,
                    f'write_{mode}',
                    file_path,
                    'success'
                )
                
                return {
                    'success': True,
                    'server': server,
                    'file_path': file_path,
                    'mode': mode,
                    'bytes_written': len(contents)
                }
            else:
                self.audit.log_file_operation(
                    token_config.name,
                    server,
                    f'write_{mode}',
                    file_path,
                    'failed',
                    result.stderr
                )
                
                return {
                    'success': False,
                    'server': server,
                    'file_path': file_path,
                    'error': result.stderr
                }
                
        except Exception as e:
            self.audit.log_file_operation(
                token_config.name,
                server,
                f'write_{mode}',
                file_path,
                'failed',
                str(e)
            )
            
            return {
                'success': False,
                'server': server,
                'file_path': file_path,
                'error': str(e)
            }
    
    async def list_directory_tool(
        self,
        token_config: TokenConfig,
        server: str,
        path: str = '.',
        detailed: bool = False
    ) -> Dict[str, Any]:
        """
        List directory contents.
        
        Args:
            token_config: Token configuration
            server: Server name
            path: Directory path
            detailed: If True, use 'ls -la', otherwise 'ls'
        
        Returns:
            Dict with directory listing
        """
        require_permission(token_config, 'read')
        require_server_access(token_config, server)
        
        command = f'ls -la "{path}"' if detailed else f'ls "{path}"'
        
        try:
            result, _ = await execute_command(
                server_name=server,
                token_name=token_config.name,
                permissions=token_config.permissions,
                command=command,
                timeout=30,
                auto_close=True
            )
            
            return {
                'success': result.success,
                'server': server,
                'path': path,
                'listing': result.stdout if result.success else result.stderr
            }
            
        except Exception as e:
            return {
                'success': False,
                'server': server,
                'path': path,
                'error': str(e)
            }
    
    async def check_service_status_tool(
        self,
        token_config: TokenConfig,
        server: str,
        service_name: str
    ) -> Dict[str, Any]:
        """
        Check systemd service status.
        
        Args:
            token_config: Token configuration
            server: Server name
            service_name: Service name (e.g., 'nginx')
        
        Returns:
            Dict with service status
        """
        require_permission(token_config, 'execute')
        require_server_access(token_config, server)
        
        command = f'systemctl status {service_name}'
        
        try:
            result, _ = await execute_command(
                server_name=server,
                token_name=token_config.name,
                permissions=token_config.permissions,
                command=command,
                timeout=30,
                auto_close=True
            )
            
            # Parse status
            is_active = 'active (running)' in result.stdout
            is_enabled = 'enabled' in result.stdout
            
            return {
                'success': True,
                'server': server,
                'service': service_name,
                'is_active': is_active,
                'is_enabled': is_enabled,
                'status_output': result.stdout
            }
            
        except Exception as e:
            return {
                'success': False,
                'server': server,
                'service': service_name,
                'error': str(e)
            }
    
    async def install_package_tool(
        self,
        token_config: TokenConfig,
        server: str,
        package_name: str,
        package_manager: str = 'auto'
    ) -> Dict[str, Any]:
        """
        Install a package using system package manager.
        
        Args:
            token_config: Token configuration
            server: Server name
            package_name: Package to install
            package_manager: 'apt', 'yum', 'dnf', or 'auto'
        
        Returns:
            Dict with installation results
        """
        require_permission(token_config, 'install')
        require_server_access(token_config, server)

        # Detect package manager if auto
        if package_manager == 'auto':
            try:
                detect_cmd = 'which apt-get yum dnf 2>/dev/null | head -1'
                result, _ = await execute_command(
                    server_name=server,
                    token_name=token_config.name,
                    permissions=token_config.permissions,
                    command=detect_cmd,
                    timeout=10,
                    auto_close=True
                )
                pm_path = result.stdout.strip()
            except SSHConnectionError as e:
                return {
                    'success': False,
                    'server': server,
                    'package': package_name,
                    'error': str(e)
                }
            if 'apt' in pm_path:
                package_manager = 'apt'
            elif 'yum' in pm_path:
                package_manager = 'yum'
            elif 'dnf' in pm_path:
                package_manager = 'dnf'
            else:
                return {
                    'success': False,
                    'server': server,
                    'package': package_name,
                    'error': 'Could not detect package manager'
                }
        
        # Build install command
        if package_manager == 'apt':
            command = f'apt-get update && apt-get install -y {package_name}'
        elif package_manager == 'yum':
            command = f'yum install -y {package_name}'
        elif package_manager == 'dnf':
            command = f'dnf install -y {package_name}'
        else:
            return {
                'success': False,
                'error': f'Unsupported package manager: {package_manager}'
            }
        
        try:
            result, _ = await execute_command(
                server_name=server,
                token_name=token_config.name,
                permissions=token_config.permissions,
                command=command,
                timeout=300,
                auto_close=True
            )
            
            return {
                'success': result.success,
                'server': server,
                'package': package_name,
                'package_manager': package_manager,
                'exit_code': result.exit_code,
                'output': result.stdout,
                'errors': result.stderr
            }
            
        except Exception as e:
            return {
                'success': False,
                'server': server,
                'package': package_name,
                'error': str(e)
            }
    
    async def list_servers_tool(
        self,
        token_config: TokenConfig,
        tag: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        List available servers.
        
        Args:
            token_config: Token configuration
            tag: Optional tag to filter by
        
        Returns:
            Dict with server list
        """
        config = get_config()
        
        if tag:
            servers = config.get_servers_by_tag(tag)
        else:
            servers = config.get_enabled_servers()
        
        # Filter by token access
        accessible_servers = {}
        for name, server_config in servers.items():
            if check_server_access(token_config, name):
                accessible_servers[name] = {
                    'host': server_config.host,
                    'port': server_config.port,
                    'user': server_config.user,
                    'tags': server_config.tags,
                    'description': server_config.description
                }
        
        return {
            'success': True,
            'servers': accessible_servers,
            'count': len(accessible_servers)
        }
    
    async def get_system_info_tool(
        self,
        token_config: TokenConfig,
        server: str
    ) -> Dict[str, Any]:
        """
        Get system information.
        
        Args:
            token_config: Token configuration
            server: Server name
        
        Returns:
            Dict with system information
        """
        require_permission(token_config, 'read')
        require_server_access(token_config, server)
        
        commands = {
            'hostname': 'hostname',
            'uptime': 'uptime',
            'os_release': 'cat /etc/os-release 2>/dev/null || cat /etc/redhat-release 2>/dev/null',
            'kernel': 'uname -r',
            'cpu_info': 'lscpu | grep "Model name" | cut -d: -f2 | xargs',
            'memory': 'free -h | grep Mem | awk \'{print "Total: " $2 ", Used: " $3 ", Free: " $4}\'',
            'disk': 'df -h / | tail -1 | awk \'{print "Size: " $2 ", Used: " $3 ", Avail: " $4 ", Use%: " $5}\''
        }
        
        info = {}
        connection_error = None

        for key, command in commands.items():
            try:
                result, _ = await execute_command(
                    server_name=server,
                    token_name=token_config.name,
                    permissions=token_config.permissions,
                    command=command,
                    timeout=30,
                    auto_close=True
                )
                info[key] = result.stdout.strip() if result.success else 'N/A'
            except SSHConnectionError as e:
                connection_error = str(e)
                logger.warning(f"Connection to {server} failed: {e}")
                break
            except Exception as e:
                info[key] = 'N/A'

        if connection_error:
            return {
                'success': False,
                'server': server,
                'error': connection_error,
                'system_info': info
            }

        return {
            'success': True,
            'server': server,
            'system_info': info
        }


# Global tools instance
_mcp_tools: Optional[MCPTools] = None


def get_mcp_tools() -> MCPTools:
    """Get global MCP tools instance."""
    global _mcp_tools
    if _mcp_tools is None:
        _mcp_tools = MCPTools()
    return _mcp_tools




