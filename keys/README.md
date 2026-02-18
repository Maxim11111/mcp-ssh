# SSH Keys Directory

This directory stores SSH private keys used to connect to target servers.

## Security Warning

⚠️ **NEVER commit SSH private keys to version control!**

All files in this directory (except this README) are ignored by git.

## Key Format

Use ED25519 keys (recommended) or RSA 4096 keys:

```bash
# Generate ED25519 key
ssh-keygen -t ed25519 -f prod_web_ed25519 -C "mcp-server"

# Or RSA 4096 key
ssh-keygen -t rsa -b 4096 -f prod_web_rsa -C "mcp-server"
```

## Key Management with CLI

The MCP SSH CLI tool can automatically generate and install keys:

```bash
# Add server with automatic key generation (from project root)
python -m src.cli server add

# Or via Docker:
# docker exec -it mcp-ssh-server python -m src.cli server add

# This will:
# 1. Prompt for server details
# 2. Generate SSH key if it doesn't exist
# 3. Connect with password (one time)
# 4. Install public key on remote server
# 5. Test passwordless connection
# 6. Save configuration
```

## Manual Key Installation

If you prefer manual setup:

```bash
# 1. Generate key
ssh-keygen -t ed25519 -f ./keys/myserver_ed25519

# 2. Copy public key to server
ssh-copy-id -i ./keys/myserver_ed25519.pub user@server

# 3. Test connection
ssh -i ./keys/myserver_ed25519 user@server

# 4. Add server to config/servers.json
```

## Key Permissions

Ensure proper permissions:

```bash
chmod 600 keys/*_ed25519
chmod 644 keys/*_ed25519.pub
```

## Docker Volume

When running in Docker, mount this directory as a volume (read-write so the CLI can create keys):

```yaml
volumes:
  - ./keys:/app/keys
```




