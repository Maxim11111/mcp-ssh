# Security Guide

Comprehensive security guide for MCP SSH Server deployment and usage.

## Table of Contents

- [Security Architecture](#security-architecture)
- [Authentication & Authorization](#authentication--authorization)
- [SSH Key Management](#ssh-key-management)
- [Command Validation](#command-validation)
- [Rate Limiting](#rate-limiting)
- [Audit Logging](#audit-logging)
- [Network Security](#network-security)
- [Best Practices](#best-practices)
- [Incident Response](#incident-response)

## Security Architecture

### Multi-Layer Defense

```
┌─────────────────────────────────────┐
│   Layer 1: Network (HTTPS/SSL)      │
├─────────────────────────────────────┤
│   Layer 2: Bearer Token Auth        │
├─────────────────────────────────────┤
│   Layer 3: Permission System        │
├─────────────────────────────────────┤
│   Layer 4: Command Validation       │
├─────────────────────────────────────┤
│   Layer 5: SSH Key Auth             │
├─────────────────────────────────────┤
│   Layer 6: Audit Logging            │
└─────────────────────────────────────┘
```

## Authentication & Authorization

### Bearer Token Security

#### Token Generation

Tokens are generated using secure random UUIDs:

```python
tok_abc123def456...  # 32+ character random hex string
```

**Best Practices:**

- ✅ Generate unique tokens for each agent/user
- ✅ Use descriptive names to track token usage
- ✅ Set appropriate permissions (principle of least privilege)
- ✅ Configure server access patterns
- ✅ Set reasonable rate limit multipliers

❌ **Never:**
- Share tokens between users/agents
- Commit tokens to git repositories
- Send tokens over unencrypted channels
- Use the same token for production and testing

#### Token Storage

**On MCP Server:**

```json
{
  "tokens": {
    "tok_abc123": {
      "name": "cursor-admin",
      "permissions": ["execute", "read", "write"],
      "allowed_servers": ["prod-*"],
      "enabled": true
    }
  }
}
```

File permissions:
```bash
chmod 600 config/tokens.json
chown mcpuser:mcpuser config/tokens.json
```

**In Agent Configuration:**

```json
{
  "headers": {
    "Authorization": "Bearer tok_abc123..."
  }
}
```

Never log or display tokens in plaintext!

#### Permission System

Available permissions:

| Permission | Description | Risk Level |
|------------|-------------|------------|
| `execute` | Execute read-only commands | Low |
| `read` | Read files | Low |
| `write` | Write/modify files | Medium |
| `install` | Install packages | High |
| `manage` | Server management (add/remove) | Critical |

**Example Configurations:**

**Readonly Monitoring:**
```json
{
  "permissions": ["execute", "read"],
  "allowed_servers": ["*"]
}
```

**DevOps Engineer:**
```json
{
  "permissions": ["execute", "read", "write", "install"],
  "allowed_servers": ["test-*", "staging-*"]
}
```

**Production Admin:**
```json
{
  "permissions": ["execute", "read", "write", "install"],
  "allowed_servers": ["prod-*"],
  "rate_limit_multiplier": 0.5
}
```

### Server Access Patterns

**Wildcard Access:**
```json
"allowed_servers": ["*"]  // All servers
```

**Pattern Matching:**
```json
"allowed_servers": ["prod-*", "test-web-*"]
```

**Explicit List:**
```json
"allowed_servers": ["prod-web-01", "prod-web-02", "prod-db-01"]
```

## SSH Key Management

### Key Generation

**Recommended: ED25519**

```bash
ssh-keygen -t ed25519 -f keys/server_ed25519 -C "mcp-server@host"
```

**Alternative: RSA 4096**

```bash
ssh-keygen -t rsa -b 4096 -f keys/server_rsa -C "mcp-server@host"
```

**With Passphrase:**

```bash
ssh-keygen -t ed25519 -f keys/server_ed25519 -N "strong-passphrase"
```

Store passphrase in environment variable:
```bash
export SERVER_SSH_PASSPHRASE="strong-passphrase"
```

### Key Storage

**On MCP Server:**

```bash
keys/
├── prod_web_ed25519      (600) - Private key
├── prod_web_ed25519.pub  (644) - Public key
├── prod_db_ed25519       (600)
└── prod_db_ed25519.pub   (644)
```

**Critical:**
- ✅ Private keys: `chmod 600`
- ✅ Public keys: `chmod 644`
- ✅ Keys directory: `chmod 700`
- ✅ Owner: MCP server user only
- ✅ Never commit private keys to git

### Key Installation

**Automatic (via CLI):**

```bash
python -m src.cli server add
# CLI handles key generation and installation
```

**Manual:**

```bash
# Install public key on target server
ssh-copy-id -i keys/server_ed25519.pub user@target-server

# Or manually
cat keys/server_ed25519.pub | ssh user@target-server 'cat >> ~/.ssh/authorized_keys'
```

### Key Rotation

**Recommended Frequency:** Every 90 days

**Process:**

```bash
# 1. Generate new key
ssh-keygen -t ed25519 -f keys/server_ed25519_new

# 2. Install new key on target servers
ssh-copy-id -i keys/server_ed25519_new.pub user@server

# 3. Test new key
ssh -i keys/server_ed25519_new user@server

# 4. Update config
# Edit config/servers.json to use new key

# 5. Restart MCP server
docker-compose restart

# 6. Verify all servers work
python -m src.cli server test server-name

# 7. Remove old key from target servers
ssh user@server 'sed -i "/old-key-comment/d" ~/.ssh/authorized_keys'

# 8. Archive old key
mv keys/server_ed25519 keys/archive/server_ed25519_$(date +%Y%m%d)
```

## Command Validation

### Whitelist Patterns

Define allowed command patterns in `config/servers.json`:

```json
{
  "security": {
    "allowed_commands_patterns": [
      "^apt ",
      "^apt-get ",
      "^systemctl ",
      "^service ",
      "^docker ",
      "^docker-compose ",
      "^nginx ",
      "^ls ",
      "^cat ",
      "^grep ",
      "^tail ",
      "^head ",
      "^ps ",
      "^top ",
      "^df ",
      "^du ",
      "^free ",
      "^uptime ",
      "^whoami ",
      "^id ",
      "^pwd "
    ]
  }
}
```

### Blacklist Commands

Explicitly forbidden commands:

```json
{
  "forbidden_commands": [
    "rm -rf /",
    "mkfs",
    "dd if=/dev/zero",
    "> /dev/sda",
    ":(){ :|:& };:",  // Fork bomb
    "chmod 777 /",
    "chown root:root /"
  ]
}
```

### Dangerous Patterns

Automatically detected patterns:

- Destructive filesystem operations
- Kernel module loading
- Hardware access
- Fork bombs
- Privilege escalation attempts

### Confirmation Required

Commands that require manual confirmation:

```json
{
  "require_confirmation": [
    "reboot",
    "shutdown",
    "systemctl restart",
    "rm -rf",
    "mkfs"
  ]
}
```

## Rate Limiting

### Configuration

```json
{
  "security": {
    "rate_limit": {
      "requests_per_minute": 60,
      "commands_per_hour": 500
    }
  }
}
```

### Per-Token Multipliers

```json
{
  "tokens": {
    "tok_abc123": {
      "rate_limit_multiplier": 2.0  // Double the limits
    },
    "tok_xyz789": {
      "rate_limit_multiplier": 0.5  // Half the limits
    }
  }
}
```

### Effective Limits

For token with multiplier 2.0:
- Requests per minute: 60 × 2.0 = 120
- Commands per hour: 500 × 2.0 = 1000

## Audit Logging

### What is Logged

Every operation is logged in `logs/audit.log`:

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

### Event Types

- `command_execution` - Command executed
- `command_denied` - Command blocked
- `file_operation` - File read/write
- `ssh_connection` - SSH connection attempt
- `authentication` - Token validation
- `rate_limit_exceeded` - Rate limit hit
- `server_added` - Server configuration added
- `server_removed` - Server removed
- `token_created` - New token created
- `token_revoked` - Token revoked

### Monitoring Audit Logs

**Real-time monitoring:**

```bash
tail -f logs/audit.log | jq '.'
```

**Find denied commands:**

```bash
grep "command_denied" logs/audit.log | jq '.'
```

**Track specific token:**

```bash
grep "cursor-admin" logs/audit.log | jq '.'
```

**Failed SSH connections:**

```bash
grep "ssh_connection.*failed" logs/audit.log | jq '.'
```

### Log Retention

**Configuration:**

- Maximum file size: 10 MB
- Backup count: 10 files
- Retention: Keep last 100 MB (10 × 10 MB)

**Manual cleanup:**

```bash
# Archive old logs
tar -czf logs/archive/audit-$(date +%Y%m).tar.gz logs/audit.log.*

# Remove archived logs
rm logs/audit.log.*
```

## Network Security

### HTTPS/TLS

**Always use HTTPS in production!**

Use nginx-proxy-manager or similar:

```nginx
server {
    listen 443 ssl http2;
    server_name mcp.yourcompany.com;
    
    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;
    
    location / {
        proxy_pass http://mcp-ssh-server:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

### Firewall Rules

**Allow only necessary access:**

```bash
# UFW example
sudo ufw default deny incoming
sudo ufw default allow outgoing

# Allow from specific networks
sudo ufw allow from 192.168.1.0/24 to any port 8000

# Or use nginx with public HTTPS
sudo ufw allow 443/tcp
```

### IP Whitelisting

At application level (future enhancement):

```json
{
  "tokens": {
    "tok_abc123": {
      "allowed_ips": ["192.168.1.0/24", "10.0.0.5"]
    }
  }
}
```

### VPN Access

Recommended for additional security:

```
[Agent] → [VPN] → [MCP Server] → [Target Servers]
```

## Best Practices

### 1. Principle of Least Privilege

- Grant only necessary permissions
- Use server access patterns
- Set appropriate rate limits
- Regular permission audits

### 2. Defense in Depth

- Multiple security layers
- No single point of failure
- Redundant controls

### 3. Regular Security Audits

**Weekly:**
- Review audit logs
- Check for failed authentication attempts
- Monitor rate limit hits

**Monthly:**
- Review token permissions
- Check for unused tokens
- Update allowed command patterns

**Quarterly:**
- Rotate SSH keys
- Review server access
- Update security policies
- Penetration testing

### 4. Incident Response Plan

**Detection:**
- Monitor audit logs
- Alert on suspicious patterns
- Regular security reviews

**Response:**
- Disable compromised tokens immediately
- Rotate affected SSH keys
- Review all actions by compromised token
- Update security measures

**Recovery:**
- Restore from known good state
- Apply security patches
- Document lessons learned
- Update procedures

### 5. Secure Configuration

**Environment Variables:**

```bash
# Use environment variables for sensitive data
export PROD_SSH_PASSPHRASE="secure-passphrase"
export DATABASE_URL="postgres://..."

# Never commit .env files
echo ".env" >> .gitignore
```

**Docker Secrets:**

```yaml
services:
  mcp-ssh-server:
    secrets:
      - ssh_passphrase

secrets:
  ssh_passphrase:
    file: ./secrets/ssh_passphrase.txt
```

### 6. Regular Updates

```bash
# Update dependencies monthly
pip install --upgrade -r requirements.txt

# Monitor for security advisories
# - GitHub Security Advisories
# - CVE databases
# - Dependency security scanners
```

## Compliance

### GDPR Considerations

If operating in EU:
- Log retention policies
- Data access controls
- User consent for logging
- Right to erasure

### SOC 2 Requirements

If applicable:
- Access controls
- Audit logging
- Change management
- Incident response

## Threat Model

### Threats

1. **Compromised Token**
   - Mitigation: Rate limiting, audit logging, token rotation

2. **SSH Key Theft**
   - Mitigation: Key passphrases, key rotation, file permissions

3. **Command Injection**
   - Mitigation: Command validation, input sanitization

4. **Privilege Escalation**
   - Mitigation: Least privilege, command whitelist

5. **Denial of Service**
   - Mitigation: Rate limiting, resource limits

6. **Man-in-the-Middle**
   - Mitigation: HTTPS/TLS, certificate pinning

## Security Checklist

### Deployment

- [ ] HTTPS/TLS enabled
- [ ] Firewall configured
- [ ] SSH keys generated (ED25519)
- [ ] Private keys have correct permissions (600)
- [ ] Tokens generated with least privilege
- [ ] Command whitelist configured
- [ ] Rate limiting enabled
- [ ] Audit logging enabled
- [ ] Log rotation configured
- [ ] Backup strategy in place

### Ongoing

- [ ] Review audit logs weekly
- [ ] Rotate SSH keys quarterly
- [ ] Review token permissions monthly
- [ ] Update dependencies monthly
- [ ] Test disaster recovery quarterly
- [ ] Security training for users
- [ ] Incident response plan documented
- [ ] Emergency contact list updated

---

**Security is a process, not a product. Stay vigilant!** 🔒




