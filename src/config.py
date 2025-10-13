"""Configuration module for MCP SSH Server."""

import json
import os
from pathlib import Path
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field, validator
import logging

logger = logging.getLogger(__name__)


class ServerConfig(BaseModel):
    """Configuration for a single SSH server."""
    
    host: str
    port: int = 22
    user: str
    ssh_key_path: str
    ssh_key_passphrase_env: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
    enabled: bool = True
    description: Optional[str] = None
    
    @validator('port')
    def validate_port(cls, v):
        if not 1 <= v <= 65535:
            raise ValueError('Port must be between 1 and 65535')
        return v
    
    def get_passphrase(self) -> Optional[str]:
        """Get SSH key passphrase from environment variable."""
        if self.ssh_key_passphrase_env:
            return os.getenv(self.ssh_key_passphrase_env)
        return None


class TokenConfig(BaseModel):
    """Configuration for an API token."""
    
    name: str
    description: Optional[str] = None
    permissions: List[str] = Field(default_factory=list)
    allowed_servers: List[str] = Field(default_factory=lambda: ["*"])
    rate_limit_multiplier: float = 1.0
    enabled: bool = True
    created_at: Optional[str] = None
    
    @validator('permissions')
    def validate_permissions(cls, v):
        valid_perms = {'execute', 'read', 'write', 'install', 'manage'}
        for perm in v:
            if perm not in valid_perms:
                raise ValueError(f'Invalid permission: {perm}. Must be one of {valid_perms}')
        return v


class SecurityConfig(BaseModel):
    """Security configuration."""
    
    allowed_commands_patterns: List[str] = Field(default_factory=list)
    forbidden_commands: List[str] = Field(default_factory=list)
    require_confirmation: List[str] = Field(default_factory=list)
    rate_limit: Dict[str, int] = Field(default_factory=dict)


class Config:
    """Main configuration manager for MCP SSH Server."""
    
    def __init__(self, config_dir: Optional[str] = None):
        self.config_dir = Path(config_dir or os.getenv('CONFIG_DIR', './config'))
        self.servers: Dict[str, ServerConfig] = {}
        self.tokens: Dict[str, TokenConfig] = {}
        self.security: SecurityConfig = SecurityConfig()
        
        self._load_servers()
        self._load_tokens()
    
    def _load_servers(self):
        """Load servers configuration from JSON file."""
        servers_file = self.config_dir / 'servers.json'
        
        if not servers_file.exists():
            logger.warning(f"Servers config file not found: {servers_file}")
            # Try example file
            example_file = self.config_dir / 'servers.json.example'
            if example_file.exists():
                logger.info(f"Using example file: {example_file}")
                servers_file = example_file
            else:
                logger.warning("No servers configuration found")
                return
        
        try:
            with open(servers_file, 'r') as f:
                data = json.load(f)
            
            # Load servers
            servers_data = data.get('servers', {})
            for name, config in servers_data.items():
                try:
                    self.servers[name] = ServerConfig(**config)
                    logger.debug(f"Loaded server config: {name}")
                except Exception as e:
                    logger.error(f"Error loading server config '{name}': {e}")
            
            # Load security config
            security_data = data.get('security', {})
            self.security = SecurityConfig(**security_data)
            
            logger.info(f"Loaded {len(self.servers)} server configurations")
            
        except Exception as e:
            logger.error(f"Error loading servers config: {e}")
    
    def _load_tokens(self):
        """Load tokens configuration from JSON file."""
        tokens_file = self.config_dir / 'tokens.json'
        
        if not tokens_file.exists():
            logger.warning(f"Tokens config file not found: {tokens_file}")
            # Try example file
            example_file = self.config_dir / 'tokens.json.example'
            if example_file.exists():
                logger.info(f"Using example tokens file: {example_file}")
                tokens_file = example_file
            else:
                logger.warning("No tokens configuration found")
                return
        
        try:
            with open(tokens_file, 'r') as f:
                data = json.load(f)
            
            tokens_data = data.get('tokens', {})
            for token, config in tokens_data.items():
                try:
                    self.tokens[token] = TokenConfig(**config)
                    logger.debug(f"Loaded token: {config.get('name', token)}")
                except Exception as e:
                    logger.error(f"Error loading token config: {e}")
            
            logger.info(f"Loaded {len(self.tokens)} token configurations")
            
        except Exception as e:
            logger.error(f"Error loading tokens config: {e}")
    
    def save_servers(self):
        """Save servers configuration to JSON file."""
        servers_file = self.config_dir / 'servers.json'
        
        try:
            # Prepare data
            data = {
                'servers': {
                    name: server.dict()
                    for name, server in self.servers.items()
                },
                'security': self.security.dict()
            }
            
            # Write to file
            with open(servers_file, 'w') as f:
                json.dump(data, f, indent=2)
            
            logger.info(f"Saved servers configuration to {servers_file}")
            
        except Exception as e:
            logger.error(f"Error saving servers config: {e}")
            raise
    
    def save_tokens(self):
        """Save tokens configuration to JSON file."""
        tokens_file = self.config_dir / 'tokens.json'
        
        try:
            data = {
                'tokens': {
                    token: config.dict()
                    for token, config in self.tokens.items()
                }
            }
            
            with open(tokens_file, 'w') as f:
                json.dump(data, f, indent=2)
            
            logger.info(f"Saved tokens configuration to {tokens_file}")
            
        except Exception as e:
            logger.error(f"Error saving tokens config: {e}")
            raise
    
    def get_server(self, name: str) -> Optional[ServerConfig]:
        """Get server configuration by name."""
        return self.servers.get(name)
    
    def get_enabled_servers(self) -> Dict[str, ServerConfig]:
        """Get all enabled servers."""
        return {
            name: server
            for name, server in self.servers.items()
            if server.enabled
        }
    
    def get_servers_by_tag(self, tag: str) -> Dict[str, ServerConfig]:
        """Get servers by tag."""
        return {
            name: server
            for name, server in self.servers.items()
            if tag in server.tags and server.enabled
        }
    
    def add_server(self, name: str, server: ServerConfig):
        """Add a new server configuration."""
        self.servers[name] = server
        self.save_servers()
        logger.info(f"Added server: {name}")
    
    def remove_server(self, name: str):
        """Remove a server configuration."""
        if name in self.servers:
            del self.servers[name]
            self.save_servers()
            logger.info(f"Removed server: {name}")
        else:
            raise KeyError(f"Server not found: {name}")
    
    def update_server(self, name: str, **kwargs):
        """Update server configuration."""
        if name not in self.servers:
            raise KeyError(f"Server not found: {name}")
        
        server = self.servers[name]
        for key, value in kwargs.items():
            if hasattr(server, key):
                setattr(server, key, value)
        
        self.save_servers()
        logger.info(f"Updated server: {name}")
    
    def validate_token(self, token: str) -> Optional[TokenConfig]:
        """Validate token and return config if valid."""
        config = self.tokens.get(token)
        if config and config.enabled:
            return config
        return None
    
    def add_token(self, token: str, config: TokenConfig):
        """Add a new token."""
        self.tokens[token] = config
        self.save_tokens()
        logger.info(f"Added token: {config.name}")
    
    def remove_token(self, token: str):
        """Remove a token."""
        if token in self.tokens:
            del self.tokens[token]
            self.save_tokens()
            logger.info(f"Removed token: {token}")
        else:
            raise KeyError(f"Token not found: {token}")
    
    def server_allowed_for_token(self, server_name: str, token_config: TokenConfig) -> bool:
        """Check if server is allowed for token."""
        if "*" in token_config.allowed_servers:
            return True
        
        # Check exact match
        if server_name in token_config.allowed_servers:
            return True
        
        # Check wildcard patterns (e.g., "prod-*")
        for pattern in token_config.allowed_servers:
            if "*" in pattern:
                prefix = pattern.replace("*", "")
                if server_name.startswith(prefix):
                    return True
        
        return False


# Global config instance
_config: Optional[Config] = None


def get_config() -> Config:
    """Get global config instance."""
    global _config
    if _config is None:
        _config = Config()
    return _config


def set_config(config: Config):
    """Set global config instance."""
    global _config
    _config = config




