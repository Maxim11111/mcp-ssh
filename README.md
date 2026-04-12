# MCP SSH Server

**Remote SSH Management Server for LLM Agents**

A centralized MCP (Model Context Protocol) server that enables LLM agents (Cursor AI, Claude Desktop, Codex, etc.) to securely execute commands and manage Linux servers via SSH.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)

## Features

- 🔐 **Secure SSH Access** - Key-based authentication with automatic setup
- 🌐 **Official MCP SDK** - Streamable HTTP ([modelcontextprotocol/python-sdk](https://github.com/modelcontextprotocol/python-sdk))
- 🔏 **MCP OAuth (RFC 9728)** - Protected resource metadata + browser login for Claude Code; same API tokens as Bearer
- 🔄 **Real-time Streaming** - Live stdout/stderr streaming via SSE
- 🔑 **Token-based Auth** - Bearer tokens with granular permissions
- 🛡️ **Security First** - Command validation, rate limiting, audit logging
- 📊 **Multi-server Support** - Manage hundreds of servers from one endpoint
- 🚀 **Production Ready** - Docker support, health checks, graceful shutdown
- 🛠️ **CLI Management** - Easy server/token management via CLI tool

## Quick Start

### Using Docker (Recommended)

```bash
# Clone repository
git clone https://github.com/Maxim11111/mcp-ssh.git
cd mcp-ssh

# Copy example configs
cp config/servers.json.example config/servers.json
cp config/tokens.json.example config/tokens.json

# Copy environment configuration
cp env.example .env

# Edit .env file to customize settings (optional)
# nano .env

# Start with Docker Compose
docker-compose up -d

# Quick view servers list
docker exec -it mcp-ssh-server python -m src.cli server list

# Add your first server
docker exec -it mcp-ssh-server python -m src.cli server add

# Check status
docker-compose logs -f mcp-ssh-server
```

### Local Installation

```bash
# Install dependencies
pip install -r requirements.txt

# Setup configuration
mkdir -p config keys logs
cp config/servers.json.example config/servers.json
cp config/tokens.json.example config/tokens.json

# Add server
python -m src.cli server add

# Start server (factory loads env each process)
uvicorn src.server_http:create_app --factory --host 0.0.0.0 --port 8000
```

## Architecture

```
[Cursor / Claude Code / Codex / …]
         ↓
  HTTPS → Streamable HTTP POST /mcp (Bearer or OAuth access token)
         ↓
  [MCP SSH Server] → SSH Keys → [Your Linux Servers]
         ↓
  Audit Logs + Security Validation
```

Set **`PUBLIC_BASE_URL`** in `.env` to the URL clients use (e.g. `https://mcp.example.com` behind TLS). The SDK publishes OAuth discovery at `/.well-known/oauth-protected-resource/mcp` and authorization server metadata at `/.well-known/oauth-authorization-server`. Browser login for MCP OAuth is at `/login` (paste the same API token you would put in `Authorization: Bearer`).

## Client configuration (quick reference)

| Client | Config | Notes |
|--------|--------|--------|
| **Cursor** | `~/.cursor/mcp.json` | `url` + `headers.Authorization: Bearer tok_…` |
| **Claude Code** | `claude mcp add …` or project config | Use HTTP transport URL ending in `/mcp`; complete **Authenticate** with token from `cli token create`, or pre-supply Bearer if the client supports it |
| **OpenAI Codex** | `~/.codex/config.toml` or `.codex/config.toml` | `[mcp_servers.name]` with `url = "https://host/mcp"` and `bearer_token_env_var = "MCP_SSH_TOKEN"` (or `http_headers`) — see [Codex MCP](https://developers.openai.com/codex/mcp) |
| **Stdio** | process env | `MCP_TOKEN=tok_…` and `python -m src.server_stdio` |

## Usage Examples

### With Cursor AI

Add to `~/.cursor/mcp.json`:

```json
{
  "mcpServers": {
    "ssh-devops": {
      "url": "http://your-server:8000/mcp",
      "headers": {
        "Authorization": "Bearer tok_your_token_here"
      }
    }
  }
}
```

Then in Cursor chat:

```
You: Install nginx on prod-web-01
AI: Executing command on prod-web-01...
✓ nginx installed successfully
```

### With Claude Desktop

Add to `~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "ssh-devops": {
      "url": "http://your-server:8000/mcp",
      "headers": {
        "Authorization": "Bearer tok_your_token_here"
      }
    }
  }
}
```

### With Claude Code (CLI)

After the server is reachable at `PUBLIC_BASE_URL` (HTTPS in production):

```bash
claude mcp add --transport http ssh-devops https://your-server.example.com/mcp
```

Use **Authenticate** in `/mcp` when prompted: open `/login`, paste the API token from `python -m src.cli token create`. The issued access token is the same string as your Bearer token.

### With OpenAI Codex (`config.toml`)

```toml
[mcp_servers.ssh_devops]
url = "https://your-server.example.com/mcp"
bearer_token_env_var = "MCP_SSH_TOKEN"
```

Then `export MCP_SSH_TOKEN=tok_...` before running Codex.

### Stdio (local)

```bash
export MCP_TOKEN=tok_your_token_here
export CONFIG_DIR=./config
python -m src.server_stdio
```

## Available Tools

MCP SSH Server provides these tools to agents:

- **execute_command** - Execute shell command on a server
- **execute_on_multiple** - Execute command on multiple servers in parallel
- **read_file** - Read file contents
- **write_file** - Write/update files
- **list_directory** - List directory contents
- **check_service_status** - Check systemd service status
- **install_package** - Install packages (apt/yum/dnf)
- **list_servers** - Get available servers
- **get_system_info** - Get system information

## CLI Management

### Server Management

```bash
# Add server with automatic SSH key setup
python -m src.cli server add

# List all servers
python -m src.cli server list

# Test connection
python -m src.cli server test prod-web-01

# Remove server
python -m src.cli server remove prod-web-01
```

### Token Management

```bash
# Create new API token
python -m src.cli token create

# List tokens
python -m src.cli token list

# Revoke token
python -m src.cli token revoke tok_abc123
```

## Configuration

### Environment Variables (.env)

The server can be configured using environment variables. Copy `env.example` to `.env` and customize:

```bash
# Copy example configuration
cp env.example .env

# Edit configuration
nano .env
```

Key configuration options:

```bash
# Server Configuration
HOST=0.0.0.0                    # Server bind address
PORT=8000                       # Internal container port
EXTERNAL_PORT=8000              # External Docker host port

# Security
TOKEN_EXPIRY_HOURS=8760        # Token validity period

# Rate Limiting
RATE_LIMIT_PER_MINUTE=60       # Requests per minute
RATE_LIMIT_PER_HOUR=500        # Commands per hour

# SSH Settings
SSH_CONNECTION_TIMEOUT=30       # SSH connection timeout
SSH_COMMAND_TIMEOUT=300        # Command execution timeout
```

### Reverse Proxy Setup

For production deployments with reverse proxy (nginx-proxy-manager, traefik, etc.):

```bash
# Use proxy compose file (recommended)
docker-compose -f docker-compose.yml -f docker-compose.proxy.yml up -d
```

### servers.json

```json
{
  "servers": {
    "prod-web-01": {
      "host": "192.168.1.10",
      "port": 22,
      "user": "deploy",
      "ssh_key_path": "/app/keys/prod_web_ed25519",
      "tags": ["production", "web"],
      "enabled": true,
      "description": "Production web server"
    }
  },
  "security": {
    "allowed_commands_patterns": ["^apt ", "^systemctl ", "^docker "],
    "forbidden_commands": ["rm -rf /", "mkfs"],
    "rate_limit": {
      "requests_per_minute": 60,
      "commands_per_hour": 500
    }
  }
}
```

### tokens.json

```json
{
  "tokens": {
    "tok_abc123...": {
      "name": "cursor-admin",
      "permissions": ["execute", "read", "write", "install"],
      "allowed_servers": ["*"],
      "rate_limit_multiplier": 1.0,
      "enabled": true
    }
  }
}
```

## Security

### Multi-layer Security

1. **Bearer Tokens** - API access control
2. **SSH Keys** - Server authentication (keys never leave server)
3. **Command Validation** - Whitelist/blacklist patterns
4. **Rate Limiting** - Per-token request limits
5. **Audit Logging** - All operations logged
6. **Permission System** - Granular access control

### Best Practices

- Use ED25519 SSH keys
- Rotate tokens regularly
- Configure allowed command patterns
- Monitor audit logs
- Use HTTPS in production (via nginx-proxy-manager)
- Limit token permissions to minimum required

## Testing

```bash
# Install dev dependencies
pip install -r requirements-dev.txt

# Run tests
pytest

# Run with coverage
pytest --cov=src --cov-report=html

# View coverage report
open htmlcov/index.html
```

See [TESTING.md](TESTING.md) for detailed testing instructions.

## Deployment

See [DEPLOYMENT.md](DEPLOYMENT.md) for production deployment guide.

## Documentation

- [QUICKSTART.md](QUICKSTART.md) - Quick start (RU/EN)
- [DEPLOYMENT.md](DEPLOYMENT.md) - Production deployment guide
- [CURSOR_INTEGRATION.md](CURSOR_INTEGRATION.md) - Cursor AI integration
- [DEVELOPMENT.md](DEVELOPMENT.md) - Development and debugging
- [MCP_PROTOCOL.md](MCP_PROTOCOL.md) - MCP protocol and tools
- [SECURITY.md](SECURITY.md) - Security best practices
- [TESTING.md](TESTING.md) - Testing guide

## API Endpoints

The server runs HTTP JSON-RPC on a single endpoint (see [MCP_PROTOCOL.md](MCP_PROTOCOL.md)):

### MCP Protocol

- `GET /mcp` - Server info and available transports
- `POST /mcp` - JSON-RPC (methods: `initialize`, `tools/list`, `tools/call`)
- `GET /sse` - SSE transport (legacy)

### Utility

- `GET /health` - Health check

## Environment Variables

All configuration can be managed via `.env` file. See `env.example` for all available options:

```bash
# Server Configuration
HOST=0.0.0.0              # Listen host
PORT=8000                 # Internal container port
EXTERNAL_PORT=8000        # External Docker host port
LOG_LEVEL=INFO            # Logging level

# Directory Configuration
CONFIG_DIR=/app/config    # Configuration directory
KEYS_DIR=/app/keys        # SSH keys directory
LOGS_DIR=/app/logs        # Logs directory

# Security Settings
TOKEN_EXPIRY_HOURS=8760   # Token validity period

# Rate Limiting
RATE_LIMIT_ENABLED=true   # Enable rate limiting
RATE_LIMIT_PER_MINUTE=60  # Requests per minute
RATE_LIMIT_PER_HOUR=500   # Commands per hour

# SSH Settings
SSH_CONNECTION_TIMEOUT=30  # SSH connection timeout
SSH_COMMAND_TIMEOUT=300   # Command execution timeout

# Development Settings
DEBUG=false               # Debug mode
RELOAD=false              # Auto-reload on changes
```

## Requirements

- Python 3.10+
- Docker & Docker Compose (for containerized deployment)
- SSH access to target servers
- OpenSSH client

## Contributing

Contributions welcome! Please:

1. Fork the repository
2. Create a feature branch
3. Add tests for new features
4. Ensure all tests pass
5. Submit a pull request

## License

MIT License - see [LICENSE](LICENSE) file for details.

## Support

- GitHub Issues: [Report bugs](https://github.com/Maxim11111/mcp-ssh/issues)
- Documentation: See *.md files in the repository root
- Email: your.email@example.com

## Acknowledgments

- Built with [FastAPI](https://fastapi.tiangolo.com/)
- MCP Protocol specification by [Anthropic](https://www.anthropic.com/)
- SSH via [Paramiko](https://www.paramiko.org/)
- SSE streaming via [sse-starlette](https://github.com/sysid/sse-starlette)

---

**Made with ❤️ for the LLM DevOps community**

