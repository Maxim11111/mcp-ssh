"""Stdio MCP server for Cursor integration."""

import sys
import json
import asyncio
import os
from typing import Dict, Any

from src.config import get_config, Config, set_config
from src.mcp_handler import get_mcp_handler, TOOL_RESPONSE_SUFFIX
from src.audit import setup_logging

# Setup logging to file (not stdout to avoid interfering with stdio)
setup_logging(os.getenv('LOG_LEVEL', 'INFO'))


async def handle_request(request: Dict[str, Any]) -> Dict[str, Any]:
    """Handle a single MCP request."""
    method = request.get("method")
    params = request.get("params", {})
    
    handler = get_mcp_handler()
    
    # Get token from environment
    token = os.getenv("MCP_TOKEN")
    if not token:
        return {
            "error": {
                "code": -32000,
                "message": "MCP_TOKEN environment variable not set"
            }
        }
    
    # Validate token
    config = get_config()
    token_config = config.validate_token(token)
    
    if not token_config:
        return {
            "error": {
                "code": -32001,
                "message": "Invalid or disabled token"
            }
        }
    
    try:
        if method == "initialize":
            return {
                "result": {
                    "protocolVersion": "1.0.0",
                    "capabilities": {
                        "tools": True
                    },
                    "serverInfo": handler.get_server_info()
                }
            }
        
        elif method == "tools/list":
            tools = handler.get_tools_list()
            return {
                "result": {
                    "tools": tools
                }
            }
        
        elif method == "tools/call":
            tool_name = params.get("name")
            arguments = params.get("arguments", {})
            
            result = await handler.call_tool(
                token_config=token_config,
                tool_name=tool_name,
                arguments=arguments
            )
            
            return {
                "result": {
                    "content": [
                        {
                            "type": "text",
                            "text": json.dumps(result, indent=2) + TOOL_RESPONSE_SUFFIX
                        }
                    ],
                    "isError": not result.get("success", False)
                }
            }
        
        else:
            return {
                "error": {
                    "code": -32601,
                    "message": f"Unknown method: {method}"
                }
            }
    
    except Exception as e:
        return {
            "error": {
                "code": -32000,
                "message": str(e)
            }
        }


async def main():
    """Main stdio loop."""
    # Initialize config
    config_dir = os.getenv('CONFIG_DIR', './config')
    config = Config(config_dir)
    set_config(config)
    
    # Read from stdin, write to stdout
    while True:
        try:
            # Read line from stdin
            line = sys.stdin.readline()
            if not line:
                break
            
            # Parse JSON-RPC request
            request = json.loads(line)
            
            # Handle request
            response = await handle_request(request)
            
            # Add JSON-RPC fields
            response["jsonrpc"] = "2.0"
            response["id"] = request.get("id")
            
            # Write response to stdout
            sys.stdout.write(json.dumps(response) + "\n")
            sys.stdout.flush()
            
        except json.JSONDecodeError as e:
            error_response = {
                "jsonrpc": "2.0",
                "id": None,
                "error": {
                    "code": -32700,
                    "message": f"Parse error: {str(e)}"
                }
            }
            sys.stdout.write(json.dumps(error_response) + "\n")
            sys.stdout.flush()
        
        except Exception as e:
            error_response = {
                "jsonrpc": "2.0",
                "id": None,
                "error": {
                    "code": -32603,
                    "message": f"Internal error: {str(e)}"
                }
            }
            sys.stdout.write(json.dumps(error_response) + "\n")
            sys.stdout.flush()


if __name__ == "__main__":
    asyncio.run(main())




