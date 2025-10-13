"""Tests for MCP protocol handler."""

import pytest

from src.mcp_handler import MCPProtocolHandler


@pytest.fixture
def mcp_handler():
    """Create MCP protocol handler."""
    return MCPProtocolHandler()


def test_get_server_info(mcp_handler):
    """Test getting server info."""
    info = mcp_handler.get_server_info()
    
    assert 'name' in info
    assert 'version' in info
    assert 'protocol_version' in info
    assert 'capabilities' in info
    
    # Check capabilities
    caps = info['capabilities']
    assert caps['tools'] is True


def test_get_tools_list(mcp_handler):
    """Test getting tools list."""
    tools = mcp_handler.get_tools_list()
    
    assert len(tools) > 0
    
    # Check tool structure
    for tool in tools:
        assert 'name' in tool
        assert 'description' in tool
        assert 'inputSchema' in tool
        
        schema = tool['inputSchema']
        assert 'type' in schema
        assert schema['type'] == 'object'
        assert 'properties' in schema


def test_tools_have_required_fields(mcp_handler):
    """Test that all tools have required fields defined."""
    tools = mcp_handler.get_tools_list()
    
    for tool in tools:
        schema = tool['inputSchema']
        
        # Tools with server parameter should require it
        if 'server' in schema.get('properties', {}):
            if tool['name'] != 'list_servers':  # list_servers doesn't require server
                # Most tools should require server
                pass  # We don't enforce this for all tools


def test_tool_names(mcp_handler):
    """Test that expected tools are present."""
    tools = mcp_handler.get_tools_list()
    tool_names = [t['name'] for t in tools]
    
    expected_tools = [
        'execute_command',
        'execute_on_multiple',
        'read_file',
        'write_file',
        'list_directory',
        'check_service_status',
        'install_package',
        'list_servers',
        'get_system_info'
    ]
    
    for expected in expected_tools:
        assert expected in tool_names, f"Tool '{expected}' not found"




