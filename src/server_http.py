"""MCP SSH HTTP server: FastAPI + official MCP SDK (Streamable HTTP) + OAuth (RFC 9728)."""

from __future__ import annotations

import asyncio
import logging
import os
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from src.audit import setup_logging
from src.config import Config, set_config
from src.fastmcp_ssh_server import create_ssh_fastmcp
from src.ssh_manager import close_all_ssh_connections, get_connection_pool

logger = logging.getLogger(__name__)


def build_app() -> FastAPI:
    """
    Build ASGI app (reads CONFIG_DIR, PUBLIC_BASE_URL, LOG_LEVEL from environment).
    Use this in tests after monkeypatching env; production uses ``create_app`` (uvicorn --factory).
    """
    load_dotenv()

    ssh_mcp = create_ssh_fastmcp()
    mcp_asgi = ssh_mcp.streamable_http_app()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        log_level = os.getenv("LOG_LEVEL", "INFO")
        setup_logging(log_level)

        config_dir = os.getenv("CONFIG_DIR", "./config")
        config = Config(config_dir)
        set_config(config)

        logger.info("Starting MCP SSH Server (Streamable HTTP + OAuth)...")
        async with ssh_mcp.session_manager.run():
            yield

        logger.info("Shutting down MCP SSH Server...")
        await asyncio.to_thread(close_all_ssh_connections)
        logger.info("MCP SSH Server stopped")

    application = FastAPI(
        title="MCP SSH Server",
        version="0.2.0",
        lifespan=lifespan,
    )

    application.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["Mcp-Session-Id", "mcp-session-id"],
    )

    @application.middleware("http")
    async def log_requests(request: Request, call_next):
        logger.info("Incoming: %s %s", request.method, request.url.path)
        response = await call_next(request)
        logger.info("Response: %s for %s %s", response.status_code, request.method, request.url.path)
        return response

    @application.get("/health")
    async def health_check():
        pool = get_connection_pool()
        stats = pool.get_stats()
        return {
            "status": "healthy",
            "version": "0.2.0",
            "transport": "streamable-http",
            "mcp_path": "/mcp",
            "ssh_connections": stats,
        }

    application.mount("/", mcp_asgi)
    return application


def create_app() -> FastAPI:
    """Uvicorn factory target: ``uvicorn src.server_http:create_app --factory``."""
    return build_app()
