# Docker Compose Proxy Configuration

This file provides an override configuration for running MCP SSH Server behind a reverse proxy.

## Usage

```bash
# Start with reverse proxy configuration
docker-compose -f docker-compose.yml -f docker-compose.proxy.yml up -d
```

## What it does

1. **Removes port mapping** - No external port exposure needed
2. **Adds proxy network** - Connects to nginx-proxy-manager network
3. **Exposes internal port** - Makes port 8000 available to reverse proxy
4. **Maintains health checks** - For reverse proxy monitoring

## Prerequisites

- nginx-proxy-manager running with network named `nginx-proxy-manager`
- Or modify the network name in this file to match your setup

## Customization

To use with different reverse proxy:

1. Change network name in `networks` section
2. Adjust `expose` port if needed
3. Modify health check if required

## Alternative: Environment Variables

Instead of using this file, you can configure via `.env`:

```bash
DISABLE_PORT_MAPPING=true
CUSTOM_NETWORKS=nginx-proxy-manager
```

Then use regular docker-compose:

```bash
docker-compose up -d
```
