# Cursor AI Integration Guide

Complete guide for integrating MCP SSH Server with Cursor AI.

## Table of Contents

- [Prerequisites](#prerequisites)
- [Configuration](#configuration)
- [Usage Examples](#usage-examples)
- [Advanced Features](#advanced-features)
- [Troubleshooting](#troubleshooting)

## Prerequisites

### Server Setup

1. MCP SSH Server deployed and running
2. Bearer token generated with appropriate permissions
3. Network connectivity from your machine to MCP server

### Cursor AI

- Cursor IDE installed (latest version recommended)
- Understanding of Cursor AI chat interface

## Configuration

### Step 1: Get Your Bearer Token

Ask your MCP SSH Server administrator for a token, or generate one:

```bash
# On MCP server
python -m src.cli token create

# Save the generated token (starts with tok_)
```

### Step 2: Configure Cursor

Create or edit `~/.cursor/mcp.json`:

**For HTTP/SSE Transport (Recommended):**

Cursor supports HTTP/SSE transport for remote MCP servers. Use this configuration:

```json
{
  "mcpServers": {
    "ssh-devops": {
      "url": "http://localhost:8000/mcp",
      "headers": {
        "Authorization": "Bearer tok_your_actual_token_here"
      }
    }
  }
}
```

**For Production (with HTTPS via nginx-proxy-manager):**

```json
{
  "mcpServers": {
    "ssh-devops": {
      "url": "https://mcp.yourcompany.com/mcp",
      "headers": {
        "Authorization": "Bearer tok_your_actual_token_here"
      }
    }
  }
}
```

**For Legacy SSE Transport (deprecated but supported):**

```json
{
  "mcpServers": {
    "ssh-devops": {
      "url": "http://localhost:8000/sse",
      "transport": "sse",
      "headers": {
        "Authorization": "Bearer tok_your_actual_token_here"
      }
    }
  }
}
```

**Alternative: Using Docker Exec (for local stdio):**

If you prefer stdio transport (local process communication):

```json
{
  "mcpServers": {
    "ssh-devops": {
      "command": "docker",
      "args": [
        "exec", 
        "-i", 
        "mcp-ssh-server", 
        "python", 
        "-m", 
        "src.server_stdio"
      ],
      "env": {
        "MCP_TOKEN": "tok_your_actual_token_here"
      }
    }
  }
}
```

**Multiple Environments:**

```json
{
  "mcpServers": {
    "ssh-prod": {
      "url": "https://mcp-prod.yourcompany.com/mcp",
      "headers": {
        "Authorization": "Bearer tok_prod_token"
      }
    },
    "ssh-test": {
      "url": "https://mcp-test.yourcompany.com/mcp",
      "headers": {
        "Authorization": "Bearer tok_test_token"
      }
    }
  }
}
```

### Step 3: Restart Cursor

1. Close Cursor completely
2. Reopen Cursor
3. Check connection in Cursor's developer console (Cmd/Ctrl + Shift + I)

### Step 4: Verify Connection

In Cursor AI chat, try:

```
Show me the available servers
```

Expected response:
```
Here are the available servers:
- prod-web-01 (192.168.1.10) - Production web server
- prod-db-01 (192.168.1.20) - Production database server
- test-web-01 (192.168.2.10) - Test web server
```

## Usage Examples

### Basic Commands

#### Check System Information

```
Get system information for prod-web-01
```

Response:
```
System information for prod-web-01:
- Hostname: web01.yourcompany.com
- Uptime: 45 days
- OS: Ubuntu 22.04.3 LTS
- Kernel: 5.15.0-91-generic
- CPU: Intel Xeon E5-2680 v4
- Memory: Total: 32G, Used: 8.5G, Free: 23G
- Disk: Size: 500G, Used: 120G, Avail: 350G
```

#### Execute Command

```
Check if nginx is running on prod-web-01
```

```
Show disk space on all production servers
```

#### File Operations

```
Read the nginx configuration file from prod-web-01 at /etc/nginx/nginx.conf
```

```
Update the nginx config on prod-web-01: add a new server block for api.example.com
```

### Package Management

```
Install docker on test-web-01
```

```
Check if postgresql is installed on prod-db-01
```

### Service Management

```
Check status of nginx service on prod-web-01
```

```
Restart nginx on all web servers
```

### Multi-Server Operations

```
Execute 'uptime' on all production servers
```

```
Check nginx version on all servers tagged 'web'
```

### Complex Workflows

#### Deploy Application

```
I need to deploy a new version of my app to prod-web-01:
1. Stop the application service
2. Backup the current version
3. Update the files in /var/www/myapp
4. Start the service
5. Verify it's running
```

#### Setup New Server

```
Help me setup a new web server test-web-02:
1. Install nginx and certbot
2. Configure nginx for myapp.test.com
3. Enable and start nginx
4. Check if it's accessible
```

#### Troubleshooting

```
The website on prod-web-01 is slow. Help me diagnose:
1. Check CPU and memory usage
2. Check nginx error logs
3. Check disk space
4. Check active connections
```

## Advanced Features

### Working with Multiple Servers

Use patterns to target multiple servers:

```
Get disk space on all servers starting with 'prod-'
```

```
Check nginx status on all web servers
```

### File Editing

Cursor can read, modify, and write files:

```
Read /etc/nginx/sites-available/default from prod-web-01
```

```
Add this location block to the nginx config:
location /api {
    proxy_pass http://localhost:3000;
}
```

### Conditional Operations

```
Check if docker is installed on test-web-01, if not, install it
```

```
If nginx is not running on prod-web-01, start it and check the logs
```

### Iterative Debugging

```
1. Check if the app is running on prod-web-01
2. If not, check the logs in /var/log/myapp/error.log
3. Based on the error, suggest and apply a fix
```

## Best Practices

### 1. Be Specific

❌ Bad: `Check the server`

✅ Good: `Check disk space and memory usage on prod-web-01`

### 2. Use Server Names

❌ Bad: `Install nginx on the production server`

✅ Good: `Install nginx on prod-web-01`

### 3. Confirm Critical Operations

❌ Bad: `Reboot all servers`

✅ Good: `I need to restart nginx on prod-web-01 for config changes. Please confirm before executing.`

### 4. Reference Tags

✅ Good: `Check nginx status on all servers tagged 'web'`

### 5. Iterative Approach

```
1. First, check the current state of prod-web-01
2. Then based on findings, we'll decide next steps
```

## Limitations

### Command Restrictions

Some commands may be blocked by security policies:

- Destructive commands (e.g., `rm -rf /`)
- Kernel operations
- Direct hardware access
- Certain privileged operations

If a command is blocked, you'll see:

```
Error: Command validation failed: Forbidden command: contains 'rm -rf /'
```

### Rate Limits

Your token has rate limits:

- Requests per minute: 60 (default)
- Commands per hour: 500 (default)

If exceeded:

```
Error: Rate limit exceeded. Please try again in a few minutes.
```

### Permissions

Your token has specific permissions:

- `execute` - Run commands
- `read` - Read files
- `write` - Write files
- `install` - Install packages
- `manage` - Server management

Missing permissions will result in:

```
Error: Permission denied: 'install' required
```

## Troubleshooting

### Connection Issues

**Problem**: "Failed to connect to MCP server"

**Solutions**:

1. Check MCP server is running:
   ```bash
   curl http://your-server:8000/health
   ```

2. Verify token is correct in `mcp.json`

3. Check network connectivity:
   ```bash
   ping your-server
   telnet your-server 8000
   ```

4. Check Cursor logs:
   - Open DevTools (Cmd/Ctrl + Shift + I)
   - Look for MCP-related errors

### Authentication Errors

**Problem**: "Invalid or disabled token"

**Solutions**:

1. Verify token in `mcp.json` is correct

2. Check token status on server:
   ```bash
   python -m src.cli token list
   ```

3. Generate new token if needed:
   ```bash
   python -m src.cli token create
   ```

### Command Failures

**Problem**: Commands not executing

**Solutions**:

1. Check server is accessible:
   ```bash
   python -m src.cli server test server-name
   ```

2. Check SSH keys are valid

3. Review audit logs on MCP server:
   ```bash
   tail -f logs/audit.log
   ```

### Slow Responses

**Problem**: Commands take too long

**Possible Causes**:

1. Network latency
2. Server is overloaded
3. Command is computationally expensive

**Solutions**:

1. Use more specific commands
2. Check server resources
3. Consider breaking into smaller operations

## Tips & Tricks

### 1. Ask for Explanations

```
Explain what this command will do before executing:
apt-get update && apt-get upgrade
```

### 2. Dry Run

```
Show me what changes would be made to the nginx config without actually making them
```

### 3. Incremental Changes

```
Let's update the nginx config in steps:
1. First, show me the current config
2. Then I'll tell you what to change
3. Finally, apply the changes
```

### 4. Validation

```
After restarting nginx, please:
1. Check if it started successfully
2. Test the configuration
3. Show me any errors
```

### 5. Documentation

```
Document the changes you're making to prod-web-01 so I can review them later
```

## Security Considerations

### DO

- ✅ Use specific server names
- ✅ Review commands before critical operations
- ✅ Use test servers for experimentation
- ✅ Keep tokens secure
- ✅ Use minimal required permissions

### DON'T

- ❌ Share your Bearer token
- ❌ Execute untested commands on production
- ❌ Grant unnecessary permissions
- ❌ Bypass security confirmations
- ❌ Run commands you don't understand

## Getting Help

### In Cursor

```
Help me understand what MCP tools are available
```

```
Show me examples of using the ssh-devops MCP server
```

### On MCP Server

```bash
# List available servers
python -m src.cli server list

# Check your token permissions
python -m src.cli token list

# View audit logs
tail -f logs/audit.log | grep your-token-name
```

### Support

- MCP Server Admin: admin@yourcompany.com
- Documentation: https://docs.yourcompany.com/mcp-ssh
- Internal Slack: #mcp-ssh-support

---

Happy DevOps with Cursor AI! 🚀

