# Deployment Guide

Complete guide for deploying MCP SSH Server in production.

## Table of Contents

- [Prerequisites](#prerequisites)
- [Docker Deployment](#docker-deployment)
- [Manual Deployment](#manual-deployment)
- [nginx-proxy-manager Setup](#nginx-proxy-manager-setup)
- [Server Configuration](#server-configuration)
- [Troubleshooting](#troubleshooting)

## Prerequisites

### System Requirements

- Linux server (Ubuntu 22.04 / Debian 11+ recommended)
- Docker & Docker Compose (for containerized deployment)
- 1GB RAM minimum (2GB+ recommended)
- 10GB disk space
- Open port 8000 (or your chosen port)

### SSH Requirements

- SSH access to target servers
- ED25519 or RSA 4096 SSH keys
- User accounts on target servers with appropriate sudo rights

## Docker Deployment (Recommended)

### 1. Clone Repository

```bash
git clone https://github.com/yourusername/mcp-ssh.git
cd mcp-ssh
```

### 2. Prepare Configuration

```bash
# Create config directory
mkdir -p config keys logs

# Copy example configs
cp config/servers.json.example config/servers.json
cp config/tokens.json.example config/tokens.json

# Copy environment configuration
cp .env.example .env

# Edit .env file for production settings
nano .env

# Set proper permissions
chmod 700 keys
chmod 600 config/servers.json config/tokens.json .env
```

### 3. Add Your Servers

Use the CLI tool to automatically setup SSH keys:

```bash
# Add first server
docker-compose run --rm mcp-ssh-server python -m src.cli server add

# Follow prompts:
# - Server name: prod-web-01
# - Hostname: 192.168.1.10
# - Port: 22
# - User: deploy
# - Password: (enter once for SSH key installation)
```

The CLI will:
1. Generate ED25519 SSH key
2. Connect with password (one time)
3. Install public key on remote server
4. Test passwordless connection
5. Save configuration

### 4. Create API Token

```bash
docker-compose run --rm mcp-ssh-server python -m src.cli token create

# Follow prompts:
# - Name: cursor-admin
# - Description: Cursor AI full access
# - Permissions: execute, read, write, install
# - Servers: *
```

**Save the generated token!** You'll need it for agent configuration.

### 5. Start Server

```bash
docker-compose up -d
```

### 6. Verify Deployment

```bash
# Check logs
docker-compose logs -f mcp-ssh-server

# Test health endpoint
curl http://localhost:8000/health

# Check server status
docker-compose exec mcp-ssh-server python -m src.cli status
```

### 7. Test Server Connection

```bash
docker-compose exec mcp-ssh-server python -m src.cli server test prod-web-01
```

## Reverse Proxy Setup

For production deployments, use a reverse proxy for HTTPS and load balancing:

### Option 1: nginx-proxy-manager (Recommended)

For production, use nginx-proxy-manager to add HTTPS:

### 1. Install nginx-proxy-manager

Follow the [official guide](https://nginxproxymanager.com/guide/#quick-setup).

### 2. Configure MCP SSH for Reverse Proxy

```bash
# Use proxy compose file (recommended)
docker-compose -f docker-compose.yml -f docker-compose.proxy.yml up -d
```

### 3. Add Proxy Host

In nginx-proxy-manager admin panel:

1. **Add Proxy Host**
2. **Domain**: mcp.yourdomain.com
3. **Scheme**: http
4. **Forward Hostname/IP**: mcp-ssh-server
5. **Forward Port**: 8000
6. **Enable**: Websockets Support ✓
7. **SSL Tab**:
   - Request SSL Certificate
   - Force SSL ✓
   - HTTP/2 Support ✓

### 4. Update Agent Configuration

Use HTTPS URL in agent configs:

```json
{
  "mcpServers": {
    "ssh-devops": {
      "url": "https://mcp.yourdomain.com/mcp/v1",
      "transport": "sse",
      "headers": {
        "Authorization": "Bearer tok_your_token_here"
      }
    }
  }
}
```

### Option 2: Traefik

For Traefik reverse proxy, use the proxy compose file:

```bash
# Use proxy compose file
docker-compose -f docker-compose.yml -f docker-compose.proxy.yml up -d

# Add labels to docker-compose.yml for Traefik:
labels:
  - "traefik.enable=true"
  - "traefik.http.routers.mcp-ssh.rule=Host(`mcp.yourdomain.com`)"
  - "traefik.http.routers.mcp-ssh.tls=true"
  - "traefik.http.routers.mcp-ssh.tls.certresolver=letsencrypt"
  - "traefik.http.services.mcp-ssh.loadbalancer.server.port=8000"
```

### Option 3: Custom Networks

For custom Docker networks:

```bash
# Create custom networks
docker network create proxy-network
docker network create monitoring-network

# Use proxy compose file with custom networks
docker-compose -f docker-compose.yml -f docker-compose.proxy.yml up -d
```

## Manual Deployment (Without Docker)

### 1. Install Python 3.10+

```bash
# Ubuntu/Debian
sudo apt update
sudo apt install -y python3.10 python3-pip python3-venv

# Create virtual environment
python3 -m venv /opt/mcp-ssh/venv
source /opt/mcp-ssh/venv/bin/activate
```

### 2. Install Dependencies

```bash
cd /opt/mcp-ssh
pip install -r requirements.txt
```

### 3. Create Systemd Service

Create `/etc/systemd/system/mcp-ssh.service`:

```ini
[Unit]
Description=MCP SSH Server
After=network.target

[Service]
Type=simple
User=mcpuser
WorkingDirectory=/opt/mcp-ssh
Environment="PATH=/opt/mcp-ssh/venv/bin"
Environment="CONFIG_DIR=/opt/mcp-ssh/config"
Environment="KEYS_DIR=/opt/mcp-ssh/keys"
Environment="LOGS_DIR=/opt/mcp-ssh/logs"
ExecStart=/opt/mcp-ssh/venv/bin/uvicorn src.server:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

### 4. Enable and Start

```bash
# Create user
sudo useradd -r -s /bin/false mcpuser
sudo chown -R mcpuser:mcpuser /opt/mcp-ssh

# Enable service
sudo systemctl daemon-reload
sudo systemctl enable mcp-ssh
sudo systemctl start mcp-ssh

# Check status
sudo systemctl status mcp-ssh
```

## Environment Configuration (.env)

For production deployment, configure the `.env` file with appropriate settings:

### Production .env Example

```bash
# Server Configuration
HOST=0.0.0.0
PORT=8000
EXTERNAL_PORT=8000
LOG_LEVEL=INFO

# Security (CHANGE THESE!)
TOKEN_EXPIRY_HOURS=8760

# Rate Limiting
RATE_LIMIT_ENABLED=true
RATE_LIMIT_PER_MINUTE=60
RATE_LIMIT_PER_HOUR=500

# SSH Settings
SSH_CONNECTION_TIMEOUT=30
SSH_COMMAND_TIMEOUT=300

# Production Settings
DEBUG=false
RELOAD=false

```

### Security Considerations

1. **Adjust Rate Limits**: Set appropriate limits for your environment
2. **Configure Timeouts**: Adjust SSH timeouts based on network conditions
3. **Use HTTPS**: Always use HTTPS in production (via nginx-proxy-manager)

### Port Configuration

To change the external port:

```bash
# In .env file
EXTERNAL_PORT=9000

# Then update agent configurations to use new port
# "url": "https://mcp.yourdomain.com:9000/mcp/v1"
```

## Server Configuration

### Adding Multiple Servers

#### Method 1: CLI (Interactive)

```bash
python -m src.cli server add
```

#### Method 2: Manual Configuration

Edit `config/servers.json`:

```json
{
  "servers": {
    "prod-web-01": {
      "host": "192.168.1.10",
      "port": 22,
      "user": "deploy",
      "ssh_key_path": "/app/keys/prod_web_ed25519",
      "tags": ["production", "web"],
      "enabled": true
    },
    "prod-db-01": {
      "host": "192.168.1.20",
      "port": 22,
      "user": "deploy",
      "ssh_key_path": "/app/keys/prod_db_ed25519",
      "tags": ["production", "database"],
      "enabled": true
    }
  }
}
```

Then manually setup SSH keys:

```bash
# Generate key
ssh-keygen -t ed25519 -f keys/prod_db_ed25519 -C "mcp-server"

# Install on target server
ssh-copy-id -i keys/prod_db_ed25519.pub deploy@192.168.1.20

# Test
ssh -i keys/prod_db_ed25519 deploy@192.168.1.20
```

### Security Configuration

Edit `config/servers.json` security section:

```json
{
  "security": {
    "allowed_commands_patterns": [
      "^apt ",
      "^apt-get ",
      "^systemctl ",
      "^service ",
      "^docker ",
      "^nginx ",
      "^ls ",
      "^cat ",
      "^grep ",
      "^ps ",
      "^df ",
      "^free "
    ],
    "forbidden_commands": [
      "rm -rf /",
      "mkfs",
      "dd if=/dev/zero",
      "> /dev/sda",
      ":(){ :|:& };:"
    ],
    "require_confirmation": [
      "reboot",
      "shutdown",
      "rm -rf"
    ],
    "rate_limit": {
      "requests_per_minute": 60,
      "commands_per_hour": 500
    }
  }
}
```

### Token Configuration

Edit `config/tokens.json`:

```json
{
  "tokens": {
    "tok_abc123...": {
      "name": "cursor-admin",
      "description": "Cursor AI with full access",
      "permissions": ["execute", "read", "write", "install", "manage"],
      "allowed_servers": ["*"],
      "rate_limit_multiplier": 1.0,
      "enabled": true
    },
    "tok_xyz789...": {
      "name": "claude-readonly",
      "description": "Claude with readonly access to test servers",
      "permissions": ["execute", "read"],
      "allowed_servers": ["test-*"],
      "rate_limit_multiplier": 0.5,
      "enabled": true
    }
  }
}
```

## Monitoring

### Health Checks

```bash
# Simple health check
curl http://localhost:8000/health

# Expected response:
{
  "status": "healthy",
  "version": "0.1.0",
  "ssh_connections": {
    "total_connections": 0,
    "alive_connections": 0,
    "connections_by_server": {}
  }
}
```

### Logs

```bash
# Docker
docker-compose logs -f mcp-ssh-server

# Systemd
sudo journalctl -u mcp-ssh -f

# Application logs
tail -f logs/mcp-ssh.log
tail -f logs/audit.log
```

### Metrics

Monitor these files:

- `logs/mcp-ssh.log` - Application logs
- `logs/audit.log` - Audit trail (all commands)

Audit log format (JSON):

```json
{
  "timestamp": "2025-01-15T10:30:00Z",
  "event_type": "command_execution",
  "token_name": "cursor-admin",
  "server_name": "prod-web-01",
  "command": "systemctl status nginx",
  "result": "success",
  "exit_code": 0,
  "duration_ms": 145
}
```

## Backup

### What to Backup

```bash
# Configuration files
config/servers.json
config/tokens.json

# SSH keys
keys/*_ed25519
keys/*_rsa

# Audit logs
logs/audit.log*
```

### Backup Script

```bash
#!/bin/bash
BACKUP_DIR=/backup/mcp-ssh-$(date +%Y%m%d)
mkdir -p $BACKUP_DIR

# Backup configs
cp config/servers.json $BACKUP_DIR/
cp config/tokens.json $BACKUP_DIR/

# Backup keys
cp -r keys $BACKUP_DIR/

# Backup logs
cp logs/audit.log* $BACKUP_DIR/

# Create archive
tar -czf $BACKUP_DIR.tar.gz $BACKUP_DIR
rm -rf $BACKUP_DIR

echo "Backup created: $BACKUP_DIR.tar.gz"
```

## Troubleshooting

### Server Won't Start

```bash
# Check logs
docker-compose logs mcp-ssh-server

# Common issues:
# 1. Port 8000 already in use
netstat -tulpn | grep 8000

# 2. Config files missing
ls -la config/

# 3. Permission issues
chmod 600 config/*.json
chmod 700 keys
```

### SSH Connection Fails

```bash
# Test SSH manually
ssh -i keys/server_key user@host

# Check key permissions
chmod 600 keys/*_ed25519
chmod 644 keys/*_ed25519.pub

# Check server SSH config
# On target server:
cat /etc/ssh/sshd_config | grep PubkeyAuthentication
# Should be: PubkeyAuthentication yes
```

### Agent Can't Connect

```bash
# Test endpoint
curl -H "Authorization: Bearer tok_your_token" \
  http://localhost:8000/mcp/v1/initialize \
  -d '{"protocolVersion":"1.0.0","capabilities":{},"clientInfo":{"name":"test"}}'

# Check token
docker-compose exec mcp-ssh-server python -m src.cli token list

# Check firewall
sudo ufw status
sudo ufw allow 8000/tcp
```

### Rate Limiting Issues

Increase limits in `config/servers.json`:

```json
{
  "security": {
    "rate_limit": {
      "requests_per_minute": 120,
      "commands_per_hour": 1000
    }
  }
}
```

Or adjust token rate limit multiplier in `config/tokens.json`:

```json
{
  "tokens": {
    "tok_abc123": {
      "rate_limit_multiplier": 2.0
    }
  }
}
```

## Updating

### Docker Deployment

```bash
# Pull latest changes
git pull

# Rebuild image
docker-compose build

# Restart
docker-compose up -d
```

### Manual Deployment

```bash
# Pull latest changes
git pull

# Activate venv
source /opt/mcp-ssh/venv/bin/activate

# Update dependencies
pip install -r requirements.txt

# Restart service
sudo systemctl restart mcp-ssh
```

## Security Hardening

### Firewall Rules

```bash
# Allow only from specific IPs
sudo ufw allow from 192.168.1.0/24 to any port 8000

# Or use nginx-proxy-manager with SSL
```

### SSH Key Rotation

```bash
# Generate new key
ssh-keygen -t ed25519 -f keys/prod_web_ed25519_new

# Install on server
ssh-copy-id -i keys/prod_web_ed25519_new.pub deploy@prod-web-01

# Update config
# Edit config/servers.json to use new key

# Test
python -m src.cli server test prod-web-01

# Remove old key from server
# On target server:
nano ~/.ssh/authorized_keys
# Remove old key line
```

### Regular Maintenance

```bash
# Weekly: Check logs for suspicious activity
grep "denied" logs/audit.log

# Monthly: Rotate logs
find logs/ -name "*.log" -mtime +30 -delete

# Quarterly: Review and update allowed commands
nano config/servers.json
```

---

For more information, see [SECURITY.md](SECURITY.md).




