# Testing Guide

Complete guide for testing MCP SSH Server.

## Table of Contents

- [Test Setup](#test-setup)
- [Running Tests](#running-tests)
- [Test Coverage](#test-coverage)
- [Writing Tests](#writing-tests)
- [Integration Testing](#integration-testing)
- [Manual Testing](#manual-testing)
- [Performance Testing](#performance-testing)
- [CI/CD Integration](#cicd-integration)

## Test Setup

### Install Test Dependencies

```bash
# Install development dependencies
pip install -r requirements-dev.txt
```

This includes:
- `pytest` - Test framework
- `pytest-asyncio` - Async test support
- `pytest-cov` - Coverage reporting
- `pytest-mock` - Mocking support
- `httpx` - HTTP client for API testing

### Test Configuration

Tests use temporary directories and mock SSH connections to avoid requiring actual servers.

## Running Tests

### Run All Tests

```bash
pytest
```

### Run Specific Test File

```bash
pytest tests/test_config.py
```

### Run Specific Test

```bash
pytest tests/test_config.py::test_config_loads_servers
```

### Run with Verbose Output

```bash
pytest -v
```

### Run with Output

```bash
pytest -s
```

### Run Tests Matching Pattern

```bash
pytest -k "security"  # Runs all tests with "security" in name
```

## Test Coverage

### Generate Coverage Report

```bash
pytest --cov=src --cov-report=html
```

### View Coverage Report

```bash
open htmlcov/index.html  # macOS
xdg-open htmlcov/index.html  # Linux
```

### Coverage Goals

- Overall coverage: >80%
- Critical modules (auth, security, ssh_manager): >90%

### Check Coverage

```bash
pytest --cov=src --cov-report=term-missing
```

Example output:
```
Name                        Stmts   Miss  Cover   Missing
---------------------------------------------------------
src/__init__.py                 1      0   100%
src/auth.py                   156     12    92%   45-47, 89
src/config.py                 189      8    96%   234-237
src/security.py               124      6    95%   178-181
src/ssh_manager.py            203     25    88%   156-163, 245-251
---------------------------------------------------------
TOTAL                        1234    98    92%
```

## Writing Tests

### Test Structure

```python
"""Tests for module_name."""

import pytest

from src.module_name import function_to_test


@pytest.fixture
def test_fixture():
    """Create test data."""
    # Setup
    data = create_test_data()
    yield data
    # Teardown (if needed)
    cleanup(data)


def test_function_behavior():
    """Test that function behaves correctly."""
    # Arrange
    input_data = "test"
    
    # Act
    result = function_to_test(input_data)
    
    # Assert
    assert result == expected_output
```

### Unit Test Example

```python
# tests/test_auth.py

import pytest
from src.auth import generate_token, check_permission


def test_generate_token():
    """Test token generation."""
    token = generate_token()
    
    # Verify format
    assert token.startswith('tok_')
    assert len(token) > 10
    
    # Verify uniqueness
    token2 = generate_token()
    assert token != token2


def test_check_permission(test_token_config):
    """Test permission checking."""
    # Should have execute permission
    assert check_permission(test_token_config, 'execute')
    
    # Should not have manage permission
    assert not check_permission(test_token_config, 'manage')
```

### Async Test Example

```python
# tests/test_command_executor.py

import pytest


@pytest.mark.asyncio
async def test_execute_command():
    """Test command execution."""
    result = await execute_command(
        server_name='test-server',
        token_name='test-token',
        permissions=['execute'],
        command='echo "Hello"'
    )
    
    assert result.exit_code == 0
    assert 'Hello' in result.stdout
```

### Mock Example

```python
# tests/test_ssh_manager.py

from unittest.mock import Mock, patch


def test_create_connection():
    """Test SSH connection creation."""
    with patch('paramiko.SSHClient') as mock_client:
        # Setup mock
        mock_client.return_value.connect.return_value = None
        
        # Test
        session_id, connection = create_ssh_connection(
            'test-server',
            'test-token'
        )
        
        # Verify
        assert session_id.startswith('ssh_')
        mock_client.return_value.connect.assert_called_once()
```

## Integration Testing

### API Integration Tests

```python
# tests/test_api_integration.py

import pytest
from fastapi.testclient import TestClient
from src.server import app


@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app)


def test_health_endpoint(client):
    """Test health check endpoint."""
    response = client.get("/health")
    
    assert response.status_code == 200
    data = response.json()
    assert data['status'] == 'healthy'


def test_mcp_initialize(client):
    """Test MCP initialize endpoint."""
    headers = {"Authorization": "Bearer tok_test123"}
    payload = {
        "protocolVersion": "1.0.0",
        "capabilities": {},
        "clientInfo": {"name": "test"}
    }
    
    response = client.post(
        "/mcp/v1/initialize",
        json=payload,
        headers=headers
    )
    
    assert response.status_code == 200
    data = response.json()
    assert 'protocolVersion' in data
```

### Docker Integration Tests

```bash
# tests/docker_integration_test.sh

#!/bin/bash
set -e

echo "Building Docker image..."
docker-compose build

echo "Starting services..."
docker-compose up -d

echo "Waiting for service to be ready..."
sleep 5

echo "Testing health endpoint..."
curl -f http://localhost:8000/health || exit 1

echo "Testing MCP endpoints..."
# Add more tests here

echo "Cleaning up..."
docker-compose down

echo "✓ All integration tests passed!"
```

Run with:
```bash
chmod +x tests/docker_integration_test.sh
./tests/docker_integration_test.sh
```

## Manual Testing

### Test Server Addition

```bash
# Start server
docker-compose up -d

# Add test server
docker-compose exec mcp-ssh-server python -m src.cli server add

# Verify
docker-compose exec mcp-ssh-server python -m src.cli server list
docker-compose exec mcp-ssh-server python -m src.cli server test test-server-01
```

### Test API Endpoints

```bash
# Health check
curl http://localhost:8000/health

# Initialize MCP
curl -X POST http://localhost:8000/mcp/v1/initialize \
  -H "Authorization: Bearer tok_test123" \
  -H "Content-Type: application/json" \
  -d '{
    "protocolVersion": "1.0.0",
    "capabilities": {},
    "clientInfo": {"name": "test"}
  }'

# List tools
curl -X POST http://localhost:8000/mcp/v1/tools/list \
  -H "Authorization: Bearer tok_test123"

# Call tool
curl -X POST http://localhost:8000/mcp/v1/tools/call \
  -H "Authorization: Bearer tok_test123" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "list_servers",
    "arguments": {}
  }'
```

### Test with Cursor AI

1. Configure Cursor (see [CURSOR_INTEGRATION.md](CURSOR_INTEGRATION.md))

2. Test basic command:
   ```
   List available servers
   ```

3. Test command execution:
   ```
   Execute 'uptime' on test-server-01
   ```

4. Test file operations:
   ```
   Read /etc/hostname from test-server-01
   ```

### Test Security

```bash
# Test forbidden command
curl -X POST http://localhost:8000/mcp/v1/tools/call \
  -H "Authorization: Bearer tok_test123" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "execute_command",
    "arguments": {
      "server": "test-server-01",
      "command": "rm -rf /"
    }
  }'

# Should return error: "Forbidden command"

# Test rate limiting
for i in {1..100}; do
  curl http://localhost:8000/health &
done
wait

# Check logs for rate limit messages
docker-compose logs | grep "rate limit"
```

## Performance Testing

### Load Testing with Apache Bench

```bash
# Install ab
sudo apt-get install apache2-utils

# Test health endpoint
ab -n 1000 -c 10 http://localhost:8000/health

# Test with authentication
ab -n 100 -c 5 \
  -H "Authorization: Bearer tok_test123" \
  -p request.json \
  -T "application/json" \
  http://localhost:8000/mcp/v1/tools/list
```

### Load Testing with Locust

Create `tests/locustfile.py`:

```python
from locust import HttpUser, task, between


class MCPUser(HttpUser):
    wait_time = between(1, 3)
    
    def on_start(self):
        """Setup headers."""
        self.headers = {
            "Authorization": "Bearer tok_test123"
        }
    
    @task(3)
    def health_check(self):
        """Test health endpoint."""
        self.client.get("/health")
    
    @task(1)
    def list_tools(self):
        """Test list tools."""
        self.client.post(
            "/mcp/v1/tools/list",
            headers=self.headers
        )
```

Run:
```bash
pip install locust
locust -f tests/locustfile.py
# Open http://localhost:8089
```

### Stress Testing

```bash
# Test concurrent connections
seq 1 100 | xargs -P 10 -I {} curl -s http://localhost:8000/health > /dev/null

# Monitor resource usage
docker stats mcp-ssh-server

# Check for errors
docker-compose logs | grep -i error
```

## CI/CD Integration

### GitHub Actions

Create `.github/workflows/test.yml`:

```yaml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    
    steps:
    - uses: actions/checkout@v2
    
    - name: Set up Python
      uses: actions/setup-python@v2
      with:
        python-version: '3.10'
    
    - name: Install dependencies
      run: |
        pip install -r requirements.txt
        pip install -r requirements-dev.txt
    
    - name: Run tests
      run: pytest --cov=src --cov-report=xml
    
    - name: Upload coverage
      uses: codecov/codecov-action@v2
      with:
        files: ./coverage.xml
```

### GitLab CI

Create `.gitlab-ci.yml`:

```yaml
image: python:3.10

stages:
  - test
  - build

test:
  stage: test
  script:
    - pip install -r requirements.txt
    - pip install -r requirements-dev.txt
    - pytest --cov=src --cov-report=term
  coverage: '/TOTAL.*\s+(\d+%)$/'

build:
  stage: build
  image: docker:latest
  services:
    - docker:dind
  script:
    - docker build -t mcp-ssh-server:$CI_COMMIT_SHA .
  only:
    - main
```

### Pre-commit Hooks

Create `.pre-commit-config.yaml`:

```yaml
repos:
  - repo: local
    hooks:
      - id: pytest
        name: pytest
        entry: pytest
        language: system
        pass_filenames: false
        always_run: true
```

Install:
```bash
pip install pre-commit
pre-commit install
```

## Test Fixtures

### Common Fixtures

Located in `tests/conftest.py`:

```python
@pytest.fixture
def temp_config_dir():
    """Create temporary config directory."""
    # Returns path to temp config dir
    
@pytest.fixture
def test_config(temp_config_dir):
    """Create test Config instance."""
    # Returns Config with test data
    
@pytest.fixture
def test_server_config():
    """Create test ServerConfig."""
    # Returns ServerConfig instance
    
@pytest.fixture
def test_token_config():
    """Create test TokenConfig."""
    # Returns TokenConfig instance
```

Use in tests:
```python
def test_something(test_config):
    """Test using test config."""
    assert len(test_config.servers) > 0
```

## Debugging Tests

### Run with PDB

```bash
pytest --pdb  # Drop into debugger on failure
```

### Print Output

```bash
pytest -s  # Don't capture output
```

### Verbose Mode

```bash
pytest -vv  # Extra verbose
```

### Show Locals on Failure

```bash
pytest -l  # Show local variables
```

### Run Last Failed

```bash
pytest --lf  # Run only tests that failed last time
```

## Best Practices

### 1. Test Isolation

- Each test should be independent
- Use fixtures for setup/teardown
- Don't rely on test execution order

### 2. Test Naming

```python
# Good
def test_config_loads_servers_correctly()
def test_invalid_token_raises_exception()

# Bad
def test1()
def test_stuff()
```

### 3. Assertions

```python
# Good - Clear failure messages
assert result.exit_code == 0, f"Command failed: {result.stderr}"

# Better - Multiple specific assertions
assert result.success
assert result.exit_code == 0
assert "nginx" in result.stdout
```

### 4. Test Coverage

- Aim for >80% overall coverage
- Critical modules: >90%
- Don't chase 100% - focus on meaningful tests

### 5. Mock Appropriately

```python
# Mock external dependencies
@patch('paramiko.SSHClient')
def test_ssh_connection(mock_ssh):
    # Test logic without real SSH

# Don't mock internals you want to test
def test_command_validator():
    # Test real CommandValidator, don't mock it
    validator = CommandValidator()
    result = validator.is_command_allowed('ls')
```

## Continuous Improvement

### Regular Testing

- Run tests before committing
- Run full test suite before merging
- Regular integration testing
- Periodic load testing

### Test Maintenance

- Update tests when changing functionality
- Remove obsolete tests
- Refactor test code
- Keep test dependencies updated

### Monitoring

- Track test execution time
- Monitor flaky tests
- Review coverage trends
- Analyze failure patterns

---

**Good tests make good code!** ✅




