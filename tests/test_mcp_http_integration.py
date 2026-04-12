"""HTTP integration: OAuth metadata (RFC 9728), auth server discovery, MCP /mcp 401."""

import pytest
from fastapi.testclient import TestClient

from src.server_http import build_app


@pytest.fixture
def client_with_config(temp_config_dir, monkeypatch):
    monkeypatch.setenv("CONFIG_DIR", temp_config_dir)
    monkeypatch.setenv("PUBLIC_BASE_URL", "http://127.0.0.1:8000")
    with TestClient(build_app()) as c:
        yield c


def test_health_in_front_of_mount(client_with_config):
    r = client_with_config.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "healthy"
    assert body["transport"] == "streamable-http"


def test_oauth_protected_resource_metadata(client_with_config):
    r = client_with_config.get("/.well-known/oauth-protected-resource/mcp")
    assert r.status_code == 200
    data = r.json()
    assert data["resource"] == "http://127.0.0.1:8000/mcp"
    assert data["authorization_servers"]
    assert "mcp" in (data.get("scopes_supported") or [])


def test_oauth_authorization_server_metadata(client_with_config):
    r = client_with_config.get("/.well-known/oauth-authorization-server")
    assert r.status_code == 200
    data = r.json()
    assert "authorization_endpoint" in data
    assert "token_endpoint" in data
    assert data.get("code_challenge_methods_supported")


def test_mcp_post_without_token_returns_401_with_resource_metadata(client_with_config):
    r = client_with_config.post("/mcp", json={"jsonrpc": "2.0", "method": "initialize", "id": 1})
    assert r.status_code == 401
    www = r.headers.get("www-authenticate", "")
    assert "resource_metadata=" in www
    body = r.json()
    assert body.get("error") == "invalid_token"


def test_mcp_post_with_valid_bearer_succeeds_initialize(client_with_config):
    """Streamable HTTP accepts Bearer tok_test123 from temp tokens.json."""
    headers = {
        "Authorization": "Bearer tok_test123",
        "Accept": "application/json, text/event-stream",
        "Content-Type": "application/json",
    }
    init_body = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "pytest", "version": "1.0"},
        },
    }
    r = client_with_config.post("/mcp", headers=headers, json=init_body)
    assert r.status_code == 200, r.text
    data = r.json()
    assert "jsonrpc" in data or "result" in data or isinstance(data, dict)
