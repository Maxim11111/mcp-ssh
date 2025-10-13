"""MCP Protocol Handler - converts MCP protocol to tool calls."""

from typing import Dict, Any, List, Optional
import logging

from src.config import TokenConfig
from src.mcp_tools import get_mcp_tools

logger = logging.getLogger(__name__)


class MCPProtocolHandler:
    """Handles MCP protocol requests."""
    
    def __init__(self):
        self.tools = get_mcp_tools()
        self.server_info = {
            'name': 'mcp-ssh-server',
            'version': '0.1.0',
            'protocol_version': '1.0.0',
            'capabilities': {
                'tools': True,
                'resources': False,
                'prompts': False
            }
        }
    
    def get_server_info(self) -> Dict[str, Any]:
        """Get server information for initialization."""
        return self.server_info
    
    def get_tools_list(self) -> List[Dict[str, Any]]:
        """Get list of available tools."""
        return [
            {
                'name': 'execute_command',
                'description': 'Execute a shell command on a remote server. Use for system monitoring, file operations, service management, and general system administration tasks.',
                'inputSchema': {
                    'type': 'object',
                    'properties': {
                        'server': {
                            'type': 'string',
                            'description': 'Server name to execute command on (e.g., "node2", "prod-web-01")'
                        },
                        'command': {
                            'type': 'string',
                            'description': 'Shell command to execute. Examples: "df -h", "systemctl status nginx", "ps aux", "uptime", "free -h"'
                        },
                        'timeout': {
                            'type': 'integer',
                            'description': 'Timeout in seconds (default: 300)',
                            'default': 300
                        }
                    },
                    'required': ['server', 'command']
                }
            },
            {
                'name': 'execute_on_multiple',
                'description': 'Execute a command on multiple servers in parallel. Ideal for bulk operations, monitoring across infrastructure, and coordinated deployments.',
                'inputSchema': {
                    'type': 'object',
                    'properties': {
                        'servers': {
                            'type': 'array',
                            'items': {'type': 'string'},
                            'description': 'List of server names or wildcard patterns. Examples: ["node2", "prod-web-*", "test-*"]'
                        },
                        'command': {
                            'type': 'string',
                            'description': 'Shell command to execute on all servers. Examples: "uptime", "systemctl status nginx", "df -h"'
                        },
                        'timeout': {
                            'type': 'integer',
                            'description': 'Timeout in seconds (default: 300)',
                            'default': 300
                        }
                    },
                    'required': ['servers', 'command']
                }
            },
            {
                'name': 'read_file',
                'description': 'Read contents of a file from a server. Use for viewing configuration files, logs, scripts, and any text-based files.',
                'inputSchema': {
                    'type': 'object',
                    'properties': {
                        'server': {
                            'type': 'string',
                            'description': 'Server name (e.g., "node2", "prod-web-01")'
                        },
                        'file_path': {
                            'type': 'string',
                            'description': 'Absolute path to file. Examples: "/etc/nginx/nginx.conf", "/var/log/syslog", "/home/ubuntu/.bashrc"'
                        }
                    },
                    'required': ['server', 'file_path']
                }
            },
            {
                'name': 'write_file',
                'description': 'Write contents to a file on a server. Use for creating configuration files, scripts, documentation, and updating existing files.',
                'inputSchema': {
                    'type': 'object',
                    'properties': {
                        'server': {
                            'type': 'string',
                            'description': 'Server name (e.g., "node2", "prod-web-01")'
                        },
                        'file_path': {
                            'type': 'string',
                            'description': 'Absolute path to file. Examples: "/etc/nginx/sites-available/mysite", "/home/ubuntu/script.sh"'
                        },
                        'contents': {
                            'type': 'string',
                            'description': 'File contents to write. Can include newlines, special characters, and multi-line content.'
                        },
                        'mode': {
                            'type': 'string',
                            'enum': ['overwrite', 'append'],
                            'description': 'Write mode: "overwrite" replaces file, "append" adds to end (default: overwrite)',
                            'default': 'overwrite'
                        }
                    },
                    'required': ['server', 'file_path', 'contents']
                }
            },
            {
                'name': 'list_directory',
                'description': 'List contents of a directory. Use for exploring file systems, checking directory structures, and finding files.',
                'inputSchema': {
                    'type': 'object',
                    'properties': {
                        'server': {
                            'type': 'string',
                            'description': 'Server name (e.g., "node2", "prod-web-01")'
                        },
                        'path': {
                            'type': 'string',
                            'description': 'Directory path. Examples: "/var/log", "/etc", "/home/ubuntu", "." (current directory)',
                            'default': '.'
                        },
                        'detailed': {
                            'type': 'boolean',
                            'description': 'Show detailed listing with permissions, sizes, dates (default: false)',
                            'default': False
                        }
                    },
                    'required': ['server']
                }
            },
            {
                'name': 'check_service_status',
                'description': 'Check status of a systemd service. Use for monitoring web servers, databases, and other system services.',
                'inputSchema': {
                    'type': 'object',
                    'properties': {
                        'server': {
                            'type': 'string',
                            'description': 'Server name (e.g., "node2", "prod-web-01")'
                        },
                        'service_name': {
                            'type': 'string',
                            'description': 'Service name. Examples: "nginx", "apache2", "postgresql", "docker", "ssh", "mysql"'
                        }
                    },
                    'required': ['server', 'service_name']
                }
            },
            {
                'name': 'install_package',
                'description': 'Install a package using system package manager. Use for installing software, tools, and dependencies on servers.',
                'inputSchema': {
                    'type': 'object',
                    'properties': {
                        'server': {
                            'type': 'string',
                            'description': 'Server name (e.g., "node2", "prod-web-01")'
                        },
                        'package_name': {
                            'type': 'string',
                            'description': 'Package name to install. Examples: "nginx", "htop", "git", "curl", "vim", "docker.io"'
                        },
                        'package_manager': {
                            'type': 'string',
                            'enum': ['auto', 'apt', 'yum', 'dnf'],
                            'description': 'Package manager: "auto" detects automatically, "apt" for Ubuntu/Debian, "yum"/"dnf" for RHEL/CentOS (default: auto)',
                            'default': 'auto'
                        }
                    },
                    'required': ['server', 'package_name']
                }
            },
            {
                'name': 'list_servers',
                'description': 'List available servers accessible by the current token. Use to discover infrastructure and plan operations.',
                'inputSchema': {
                    'type': 'object',
                    'properties': {
                        'tag': {
                            'type': 'string',
                            'description': 'Optional tag to filter servers by. Examples: "production", "staging", "web", "database"'
                        }
                    }
                }
            },
            {
                'name': 'get_system_info',
                'description': 'Get comprehensive system information from a server. Returns hostname, uptime, OS details, CPU, memory, and disk usage.',
                'inputSchema': {
                    'type': 'object',
                    'properties': {
                        'server': {
                            'type': 'string',
                            'description': 'Server name (e.g., "node2", "prod-web-01")'
                        }
                    },
                    'required': ['server']
                }
            }
        ]
    
    async def call_tool(
        self,
        token_config: TokenConfig,
        tool_name: str,
        arguments: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Call a tool with given arguments.
        
        Args:
            token_config: Token configuration
            tool_name: Name of tool to call
            arguments: Tool arguments
        
        Returns:
            Tool execution result
        """
        logger.info(f"Tool call: {tool_name} by {token_config.name}")
        
        try:
            if tool_name == 'execute_command':
                result = await self.tools.execute_command_tool(
                    token_config=token_config,
                    server=arguments['server'],
                    command=arguments['command'],
                    timeout=arguments.get('timeout', 300)
                )
            
            elif tool_name == 'execute_on_multiple':
                result = await self.tools.execute_on_multiple_tool(
                    token_config=token_config,
                    servers=arguments['servers'],
                    command=arguments['command'],
                    timeout=arguments.get('timeout', 300)
                )
            
            elif tool_name == 'read_file':
                result = await self.tools.read_file_tool(
                    token_config=token_config,
                    server=arguments['server'],
                    file_path=arguments['file_path']
                )
            
            elif tool_name == 'write_file':
                result = await self.tools.write_file_tool(
                    token_config=token_config,
                    server=arguments['server'],
                    file_path=arguments['file_path'],
                    contents=arguments['contents'],
                    mode=arguments.get('mode', 'overwrite')
                )
            
            elif tool_name == 'list_directory':
                result = await self.tools.list_directory_tool(
                    token_config=token_config,
                    server=arguments['server'],
                    path=arguments.get('path', '.'),
                    detailed=arguments.get('detailed', False)
                )
            
            elif tool_name == 'check_service_status':
                result = await self.tools.check_service_status_tool(
                    token_config=token_config,
                    server=arguments['server'],
                    service_name=arguments['service_name']
                )
            
            elif tool_name == 'install_package':
                result = await self.tools.install_package_tool(
                    token_config=token_config,
                    server=arguments['server'],
                    package_name=arguments['package_name'],
                    package_manager=arguments.get('package_manager', 'auto')
                )
            
            elif tool_name == 'list_servers':
                result = await self.tools.list_servers_tool(
                    token_config=token_config,
                    tag=arguments.get('tag')
                )
            
            elif tool_name == 'get_system_info':
                result = await self.tools.get_system_info_tool(
                    token_config=token_config,
                    server=arguments['server']
                )
            
            else:
                result = {
                    'success': False,
                    'error': f'Unknown tool: {tool_name}'
                }
            
            logger.info(
                f"Tool call completed: {tool_name} - "
                f"Success: {result.get('success', False)}"
            )
            
            return result
            
        except Exception as e:
            logger.error(f"Tool call error: {tool_name} - {e}")
            return {
                'success': False,
                'error': str(e)
            }


# Global handler instance
_mcp_handler: Optional[MCPProtocolHandler] = None


def get_mcp_handler() -> MCPProtocolHandler:
    """Get global MCP handler instance."""
    global _mcp_handler
    if _mcp_handler is None:
        _mcp_handler = MCPProtocolHandler()
    return _mcp_handler




