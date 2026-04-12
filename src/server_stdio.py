"""Stdio MCP server using official FastMCP (token from MCP_TOKEN env)."""

import os

from dotenv import load_dotenv

from src.audit import setup_logging
from src.config import Config, set_config
from src.fastmcp_ssh_server import create_ssh_fastmcp_stdio

load_dotenv()

setup_logging(os.getenv("LOG_LEVEL", "INFO"))

_config_dir = os.getenv("CONFIG_DIR", "./config")
set_config(Config(_config_dir))

_stdio_mcp = create_ssh_fastmcp_stdio()


def main() -> None:
    _stdio_mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
