"""MCP server with proper JSON-RPC 2.0 protocol over HTTP/SSE."""

import asyncio
import json
import os
import uuid
from contextlib import asynccontextmanager
from typing import Dict, Any, Optional, AsyncIterator
import logging

from fastapi import FastAPI, Request, HTTPException, Header, Depends
from fastapi.responses import StreamingResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from src.config import get_config, set_config, Config
from src.auth import verify_token, TokenConfig
from src.mcp_handler import get_mcp_handler
from src.ssh_manager import get_connection_pool, close_all_ssh_connections
from src.audit import setup_logging, get_audit_logger
from src.command_executor import execute_command

logger = logging.getLogger(__name__)


# JSON-RPC 2.0 Models
class JSONRPCMessage(BaseModel):
    """JSON-RPC 2.0 message (request or notification)."""
    jsonrpc: str = "2.0"
    id: Optional[int | str] = None  # None for notifications
    method: str
    params: Optional[Dict[str, Any]] = None


class JSONRPCResponse(BaseModel):
    """JSON-RPC 2.0 response."""
    jsonrpc: str = "2.0"
    id: Optional[int | str] = None
    result: Optional[Dict[str, Any]] = None
    error: Optional[Dict[str, Any]] = None


# SSE sessions for streaming
sse_sessions: Dict[str, asyncio.Queue] = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    # Startup
    logger.info("Starting MCP SSH Server...")
    
    log_level = os.getenv('LOG_LEVEL', 'INFO')
    setup_logging(log_level)
    
    config_dir = os.getenv('CONFIG_DIR', './config')
    config = Config(config_dir)
    set_config(config)
    
    logger.info("MCP SSH Server started successfully")
    
    yield
    
    # Shutdown
    logger.info("Shutting down MCP SSH Server...")
    await close_all_ssh_connections()
    logger.info("MCP SSH Server stopped")


# Create FastAPI app
app = FastAPI(
    title="MCP SSH Server",
    version="0.1.0",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Request logging middleware
@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Log all incoming requests."""
    logger.info(f"Incoming: {request.method} {request.url.path} from {request.client.host}")
    logger.debug(f"Headers: {dict(request.headers)}")
    
    response = await call_next(request)
    
    logger.info(f"Response: {response.status_code} for {request.method} {request.url.path}")
    return response


async def get_token_config(authorization: Optional[str] = Header(None)) -> TokenConfig:
    """Extract and verify token from Authorization header."""
    logger.debug(f"Authorization header: {authorization[:50] if authorization else 'None'}...")
    
    if not authorization:
        logger.warning("Missing Authorization header")
        raise HTTPException(status_code=401, detail="Missing Authorization header")
    
    if not authorization.startswith("Bearer "):
        logger.warning(f"Invalid Authorization header format: {authorization[:50]}...")
        raise HTTPException(status_code=401, detail="Invalid Authorization header format")
    
    token = authorization.replace("Bearer ", "")
    config = get_config()
    token_config = config.validate_token(token)
    
    if not token_config:
        logger.warning(f"Invalid or disabled token: {token[:20]}...")
        raise HTTPException(status_code=401, detail="Invalid or disabled token")
    
    logger.info(f"Authenticated as: {token_config.name}")
    return token_config


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


@app.get("/mcp")
async def mcp_info():
    """MCP server info endpoint (for clients that check GET first)."""
    return {
        "name": "mcp-ssh-server",
        "version": "0.1.0",
        "protocol": "json-rpc-2.0",
        "transport": "http",
        "endpoints": {
            "rpc": "/mcp (POST)",
            "sse": "/sse (GET)",
            "messages": "/messages (POST)"
        },
        "authentication": "Bearer token required",
        "documentation": "https://github.com/yourusername/mcp-ssh"
    }


@app.post("/mcp")
async def mcp_endpoint(
    request: Request,
    token_config: TokenConfig = Depends(get_token_config)
):
    """Main MCP JSON-RPC endpoint."""
    try:
        body = await request.json()
        logger.info(f"MCP Request from {request.client.host}: {body}")
        
        message = JSONRPCMessage(**body)
        is_notification = message.id is None
        
        handler = get_mcp_handler()
        method = message.method
        params = message.params or {}
        
        # Handle notifications (no response needed)
        if is_notification:
            logger.info(f"Received notification: {method}")
            
            if method == "notifications/initialized":
                logger.info("Client initialized successfully")
            elif method == "notifications/cancelled":
                logger.info(f"Request cancelled: {params}")
            else:
                logger.warning(f"Unknown notification: {method}")
            
            # Notifications don't get a response, just 200 OK
            return JSONResponse(status_code=200, content={"status": "ok"})
        
        # Handle requests (need response)
        if method == "initialize":
            result = {
                "protocolVersion": "2024-11-05",
                "capabilities": {
                    "tools": {},
                    "resources": {},
                    "prompts": {}
                },
                "serverInfo": handler.get_server_info()
            }
            
        elif method == "tools/list":
            tools = handler.get_tools_list()
            result = {"tools": tools}
            
        elif method == "tools/call":
            tool_name = params.get("name")
            arguments = params.get("arguments", {})
            
            tool_result = await handler.call_tool(
                token_config=token_config,
                tool_name=tool_name,
                arguments=arguments
            )
            
            # Format result according to MCP spec
            result = {
                "content": [
                    {
                        "type": "text",
                        "text": json.dumps(tool_result, indent=2)
                    }
                ],
                "isError": not tool_result.get("success", False)
            }
            
        elif method == "resources/list":
            result = {"resources": []}
            
        elif method == "prompts/list":
            result = {"prompts": []}
            
        else:
            return JSONResponse(
                status_code=400,
                content={
                    "jsonrpc": "2.0",
                    "id": message.id,
                    "error": {
                        "code": -32601,
                        "message": f"Method not found: {method}"
                    }
                }
            )
        
        return {
            "jsonrpc": "2.0",
            "id": message.id,
            "result": result
        }
        
    except Exception as e:
        logger.error(f"Error handling MCP request: {e}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={
                "jsonrpc": "2.0",
                "id": body.get("id") if isinstance(body, dict) else None,
                "error": {
                    "code": -32603,
                    "message": str(e)
                }
            }
        )


@app.get("/sse")
async def sse_endpoint(
    request: Request,
    token_config: TokenConfig = Depends(get_token_config)
):
    """SSE endpoint for streaming (legacy support)."""
    session_id = str(uuid.uuid4())
    queue: asyncio.Queue = asyncio.Queue()
    sse_sessions[session_id] = queue
    
    async def event_generator() -> AsyncIterator[str]:
        try:
            # Send endpoint message
            endpoint_msg = {
                "endpoint": f"/messages?sessionId={session_id}"
            }
            yield f"event: endpoint\ndata: {json.dumps(endpoint_msg)}\n\n"
            
            # Stream events from queue
            while True:
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=30)
                    if event is None:  # Shutdown signal
                        break
                    yield f"data: {json.dumps(event)}\n\n"
                except asyncio.TimeoutError:
                    # Send keepalive
                    yield ": keepalive\n\n"
                    
        except asyncio.CancelledError:
            pass
        finally:
            if session_id in sse_sessions:
                del sse_sessions[session_id]
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        }
    )


@app.post("/messages")
async def messages_endpoint(
    request: Request,
    token_config: TokenConfig = Depends(get_token_config)
):
    """Message endpoint for SSE (legacy support)."""
    session_id = request.query_params.get("sessionId")
    
    if not session_id or session_id not in sse_sessions:
        raise HTTPException(status_code=400, detail="Invalid or expired session")
    
    try:
        body = await request.json()
        message = JSONRPCMessage(**body)
        is_notification = message.id is None
        
        handler = get_mcp_handler()
        method = message.method
        params = message.params or {}
        
        # Handle notifications (no response via SSE)
        if is_notification:
            logger.info(f"SSE notification: {method}")
            return {"status": "ok"}
        
        # Handle different MCP methods (same as /mcp endpoint)
        if method == "initialize":
            result = {
                "protocolVersion": "2024-11-05",
                "capabilities": {
                    "tools": {},
                    "resources": {},
                    "prompts": {}
                },
                "serverInfo": handler.get_server_info()
            }
            
        elif method == "tools/list":
            tools = handler.get_tools_list()
            result = {"tools": tools}
            
        elif method == "tools/call":
            tool_name = params.get("name")
            arguments = params.get("arguments", {})
            
            tool_result = await handler.call_tool(
                token_config=token_config,
                tool_name=tool_name,
                arguments=arguments
            )
            
            result = {
                "content": [
                    {
                        "type": "text",
                        "text": json.dumps(tool_result, indent=2)
                    }
                ],
                "isError": not tool_result.get("success", False)
            }
            
        else:
            result = None
            error = {
                "code": -32601,
                "message": f"Method not found: {method}"
            }
        
        # Send response via SSE
        response = {
            "jsonrpc": "2.0",
            "id": message.id,
        }
        
        if result is not None:
            response["result"] = result
        else:
            response["error"] = error
        
        queue = sse_sessions[session_id]
        await queue.put(response)
        
        return {"status": "ok"}
        
    except Exception as e:
        logger.error(f"Error handling message: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run(
        "src.server_http:app",
        host="0.0.0.0",
        port=port,
        log_level="info",
        access_log=True
    )

