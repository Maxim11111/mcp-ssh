#!/bin/bash
set -e

echo "==================================="
echo "MCP SSH Server"
echo "==================================="
echo ""

# Check if config files exist
if [ ! -f "/app/config/servers.json" ]; then
    echo "⚠ Warning: /app/config/servers.json not found"
    
    if [ -f "/app/config/servers.json.example" ]; then
        echo "Creating from example file..."
        if cp /app/config/servers.json.example /app/config/servers.json 2>/dev/null; then
            echo "✓ Created servers.json from example"
        else
            echo "✗ Error: Cannot write to /app/config (read-only filesystem?)"
            echo ""
            echo "Please ensure config directory is writable:"
            echo "  - Remove :ro flag from docker-compose.yml"
            echo "  - Or create servers.json manually before starting"
            exit 1
        fi
    else
        echo "✗ Error: servers.json.example not found"
        echo ""
        echo "Please mount a valid configuration:"
        echo "  docker run -v ./config:/app/config mcp-ssh-server"
        exit 1
    fi
fi

if [ ! -f "/app/config/tokens.json" ]; then
    echo "⚠ Warning: /app/config/tokens.json not found"
    
    if [ -f "/app/config/tokens.json.example" ]; then
        echo "Creating from example file..."
        if cp /app/config/tokens.json.example /app/config/tokens.json 2>/dev/null; then
            echo "✓ Created tokens.json from example"
        else
            echo "✗ Error: Cannot write to /app/config (read-only filesystem?)"
            echo ""
            echo "Please ensure config directory is writable"
            exit 1
        fi
    else
        echo "⚠ Warning: tokens.json.example not found"
        echo "You'll need to create tokens manually"
    fi
fi

# Check keys directory
if [ ! -d "/app/keys" ] || [ -z "$(ls -A /app/keys 2>/dev/null | grep -v README)" ]; then
    echo "⚠ Warning: No SSH keys found in /app/keys"
    echo ""
    echo "Use the CLI tool to add servers and generate keys:"
    echo "  docker exec -it mcp-ssh-server python -m src.cli server add"
    echo ""
fi

# Display configuration
echo "Configuration:"
echo "  Config dir: ${CONFIG_DIR:-/app/config}"
echo "  Keys dir: ${KEYS_DIR:-/app/keys}"
echo "  Logs dir: ${LOGS_DIR:-/app/logs}"
echo "  Log level: ${LOG_LEVEL:-INFO}"
echo "  Listen: ${HOST:-0.0.0.0}:${PORT:-8000}"
echo ""

# Set proper permissions
chmod 700 /app/keys 2>/dev/null || true
chmod 600 /app/keys/*_ed25519 2>/dev/null || true
chmod 600 /app/keys/*_rsa 2>/dev/null || true
chmod 644 /app/keys/*.pub 2>/dev/null || true

echo "Starting MCP SSH Server..."
echo "==================================="
echo ""

# Execute the main command
exec "$@"

