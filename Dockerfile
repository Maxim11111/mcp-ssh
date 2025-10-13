# Multi-stage Dockerfile for MCP SSH Server

# Stage 1: Builder
FROM python:3.11-slim as builder

WORKDIR /build

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libssl-dev \
    libffi-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir --user -r requirements.txt

# Stage 2: Runtime
FROM python:3.11-slim

LABEL maintainer="maxim@maxber.ru"
LABEL description="MCP SSH Server for remote Linux server management"

# Create non-root user
RUN useradd -m -u 1000 -s /bin/bash mcpuser

# Install runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    openssh-client \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy Python dependencies from builder
COPY --from=builder /root/.local /home/mcpuser/.local

# Copy application code
COPY --chown=mcpuser:mcpuser src/ /app/src/
COPY --chown=mcpuser:mcpuser setup.py /app/

# Create directories
RUN mkdir -p /app/config /app/keys /app/logs && \
    chown -R mcpuser:mcpuser /app

# Set environment variables
ENV PATH=/home/mcpuser/.local/bin:$PATH \
    PYTHONUNBUFFERED=1 \
    HOST=0.0.0.0 \
    PORT=8000 \
    CONFIG_DIR=/app/config \
    KEYS_DIR=/app/keys \
    LOGS_DIR=/app/logs \
    LOG_LEVEL=INFO

# Switch to non-root user
USER mcpuser

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"

# Copy entrypoint script
COPY --chown=mcpuser:mcpuser docker/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Set entrypoint
ENTRYPOINT ["/entrypoint.sh"]

# Default command
CMD ["uvicorn", "src.server_http:app", "--host", "0.0.0.0", "--port", "8000"]

