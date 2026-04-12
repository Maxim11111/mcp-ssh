"""Legacy FastAPI app (REST /mcp/v1/* and SSE streaming).

Deprecated: use :mod:`src.server_http` with the official MCP SDK (Streamable HTTP + OAuth).
This module is kept for reference and optional streaming experiments; Docker and docs
target ``src.server_http:create_app`` with ``uvicorn --factory``.
"""

import asyncio
import json
import os
import uuid
from contextlib import asynccontextmanager
from typing import Dict, Any, Optional
import logging

from fastapi import FastAPI, Request, HTTPException, Depends
from fastapi.responses import StreamingResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from src.config import get_config, set_config, Config
from src.auth import verify_token, TokenConfig, check_command_rate_limit
from src.mcp_handler import get_mcp_handler, TOOL_RESPONSE_SUFFIX
from src.ssh_manager import get_connection_pool, close_all_ssh_connections
from src.audit import setup_logging, get_audit_logger
from src.command_executor import execute_command

logger = logging.getLogger(__name__)


# Request/Response models
class MCPInitializeRequest(BaseModel):
    """MCP initialize request."""
    protocolVersion: str
    capabilities: Dict[str, Any]
    clientInfo: Dict[str, str]


class MCPToolCallRequest(BaseModel):
    """MCP tool call request."""
    name: str
    arguments: Dict[str, Any]


class MCPCommandStreamRequest(BaseModel):
    """Request to execute command with SSE streaming."""
    server: str
    command: str
    timeout: int = 300


# SSE streaming sessions
streaming_sessions: Dict[str, Dict[str, Any]] = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    # Startup
    logger.info("Starting MCP SSH Server...")
    
    # Setup logging
    log_level = os.getenv('LOG_LEVEL', 'INFO')
    setup_logging(log_level)
    
    # Initialize configuration
    config_dir = os.getenv('CONFIG_DIR', './config')
    config = Config(config_dir)
    set_config(config)
    
    # Start SSH connection pool cleanup task
    pool = get_connection_pool()
    await pool.start_cleanup_task()
    
    logger.info("MCP SSH Server started successfully")
    
    yield
    
    # Shutdown
    logger.info("Shutting down MCP SSH Server...")
    
    # Stop cleanup task
    pool.stop_cleanup_task()
    
    # Close all SSH connections
    close_all_ssh_connections()
    
    logger.info("MCP SSH Server shutdown complete")


# Create FastAPI app
app = FastAPI(
    title="MCP SSH Server",
    description="MCP Server for remote SSH management of Linux servers",
    version="0.1.0",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    pool = get_connection_pool()
    stats = pool.get_stats()
    
    return {
        "status": "healthy",
        "version": "0.1.0",
        "ssh_connections": stats
    }


@app.post("/mcp/v1/initialize")
async def mcp_initialize(
    request: MCPInitializeRequest,
    auth: tuple = Depends(verify_token)
):
    """MCP protocol initialize endpoint."""
    token, token_config = auth
    
    handler = get_mcp_handler()
    server_info = handler.get_server_info()
    
    logger.info(f"MCP initialization from {token_config.name}")
    
    return {
        "protocolVersion": server_info['protocol_version'],
        "capabilities": server_info['capabilities'],
        "serverInfo": {
            "name": server_info['name'],
            "version": server_info['version']
        }
    }


@app.post("/mcp/v1/tools/list")
async def mcp_tools_list(auth: tuple = Depends(verify_token)):
    """List available MCP tools."""
    token, token_config = auth
    
    handler = get_mcp_handler()
    tools = handler.get_tools_list()
    
    return {
        "tools": tools
    }


@app.post("/mcp/v1/tools/call")
async def mcp_tool_call(
    request: MCPToolCallRequest,
    auth: tuple = Depends(verify_token)
):
    """Call an MCP tool."""
    token, token_config = auth
    
    # Check command rate limit for command execution tools
    if request.name in ['execute_command', 'execute_on_multiple', 'install_package']:
        await check_command_rate_limit(token, token_config)
    
    handler = get_mcp_handler()
    
    try:
        result = await handler.call_tool(
            token_config=token_config,
            tool_name=request.name,
            arguments=request.arguments
        )
        
        # Format as MCP response
        if result.get('success', False):
            return {
                "content": [
                    {
                        "type": "text",
                        "text": json.dumps(result, indent=2) + TOOL_RESPONSE_SUFFIX
                    }
                ],
                "isError": False
            }
        else:
            return {
                "content": [
                    {
                        "type": "text",
                        "text": json.dumps(result, indent=2) + TOOL_RESPONSE_SUFFIX
                    }
                ],
                "isError": True
            }
    
    except Exception as e:
        logger.error(f"Tool call error: {e}")
        return {
            "content": [
                {
                    "type": "text",
                    "text": f"Error: {str(e)}{TOOL_RESPONSE_SUFFIX}"
                }
            ],
            "isError": True
        }


@app.post("/mcp/v1/command/stream")
async def create_command_stream(
    request: MCPCommandStreamRequest,
    auth: tuple = Depends(verify_token)
):
    """
    Create a command execution session with streaming.
    Returns session_id for SSE endpoint.
    """
    token, token_config = auth
    
    # Check permissions and rate limits
    await check_command_rate_limit(token, token_config)
    
    # Create session
    session_id = f"cmd_{uuid.uuid4().hex[:16]}"
    
    streaming_sessions[session_id] = {
        'server': request.server,
        'command': request.command,
        'timeout': request.timeout,
        'token_config': token_config,
        'status': 'pending',
        'stdout_queue': asyncio.Queue(),
        'stderr_queue': asyncio.Queue(),
        'result': None
    }
    
    logger.info(f"Created streaming session: {session_id}")
    
    return {
        'session_id': session_id,
        'sse_url': f'/mcp/v1/sse/{session_id}'
    }


@app.get("/mcp/v1/sse/{session_id}")
async def command_stream_sse(session_id: str):
    """
    SSE endpoint for real-time command output streaming.
    """
    if session_id not in streaming_sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    session = streaming_sessions[session_id]
    
    async def event_generator():
        """Generate SSE events."""
        try:
            # Send start event
            yield f"event: start\ndata: {json.dumps({'session_id': session_id})}\n\n"
            
            # Start command execution in background
            async def execute_with_streaming():
                def on_stdout(line: str):
                    session['stdout_queue'].put_nowait(line)
                
                def on_stderr(line: str):
                    session['stderr_queue'].put_nowait(line)
                
                try:
                    session['status'] = 'running'
                    result, _ = await execute_command(
                        server_name=session['server'],
                        token_name=session['token_config'].name,
                        permissions=session['token_config'].permissions,
                        command=session['command'],
                        timeout=session['timeout'],
                        on_stdout=on_stdout,
                        on_stderr=on_stderr,
                        auto_close=True
                    )
                    session['result'] = result
                    session['status'] = 'completed'
                except Exception as e:
                    session['error'] = str(e)
                    session['status'] = 'error'
            
            # Start execution
            exec_task = asyncio.create_task(execute_with_streaming())
            
            # Stream output
            while True:
                # Check for stdout
                try:
                    line = session['stdout_queue'].get_nowait()
                    yield f"event: stdout\ndata: {json.dumps({'line': line})}\n\n"
                except asyncio.QueueEmpty:
                    pass
                
                # Check for stderr
                try:
                    line = session['stderr_queue'].get_nowait()
                    yield f"event: stderr\ndata: {json.dumps({'line': line})}\n\n"
                except asyncio.QueueEmpty:
                    pass
                
                # Check if completed
                if session['status'] == 'completed':
                    result = session['result']
                    yield f"event: complete\ndata: {json.dumps({'exit_code': result.exit_code, 'duration_ms': result.duration_ms})}\n\n"
                    break
                elif session['status'] == 'error':
                    yield f"event: error\ndata: {json.dumps({'error': session.get('error', 'Unknown error')})}\n\n"
                    break
                
                await asyncio.sleep(0.1)
            
            # Wait for execution to finish
            await exec_task
            
        except Exception as e:
            logger.error(f"SSE stream error: {e}")
            yield f"event: error\ndata: {json.dumps({'error': str(e)})}\n\n"
        
        finally:
            # Cleanup session
            if session_id in streaming_sessions:
                del streaming_sessions[session_id]
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        }
    )


@app.get("/api/servers")
async def list_servers(auth: tuple = Depends(verify_token)):
    """List available servers (non-MCP endpoint for debugging)."""
    token, token_config = auth
    
    config = get_config()
    servers = config.get_enabled_servers()
    
    # Filter by access
    accessible = {}
    for name, server in servers.items():
        if config.server_allowed_for_token(name, token_config):
            accessible[name] = {
                'host': server.host,
                'port': server.port,
                'user': server.user,
                'tags': server.tags,
                'description': server.description
            }
    
    return {
        'servers': accessible,
        'count': len(accessible)
    }


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Custom HTTP exception handler."""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": exc.detail,
            "status_code": exc.status_code
        }
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """General exception handler."""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "detail": str(exc)
        }
    )


if __name__ == "__main__":
    import uvicorn
    
    host = os.getenv('HOST', '0.0.0.0')
    port = int(os.getenv('PORT', 8000))
    
    uvicorn.run(
        "src.server:app",
        host=host,
        port=port,
        reload=False,
        log_level="info"
    )




