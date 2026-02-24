"""SSH connection manager with connection pooling."""

import asyncio
import threading
import time
import uuid
from typing import Dict, Optional, Tuple
from pathlib import Path
import logging

import paramiko
from paramiko import SSHClient, AutoAddPolicy, RSAKey, Ed25519Key
from paramiko.ssh_exception import SSHException

from src.config import get_config, ServerConfig
from src.audit import get_audit_logger

logger = logging.getLogger(__name__)


class SSHConnectionError(Exception):
    """Raised when SSH connection to a server fails (timeout, unreachable, etc)."""

    def __init__(self, server_name: str, message: str):
        self.server_name = server_name
        self.message = message
        super().__init__(f"Failed to connect to {server_name}: {message}")


class SSHConnection:
    """Represents a single SSH connection."""
    
    def __init__(
        self,
        session_id: str,
        client: SSHClient,
        server_name: str,
        token_name: str
    ):
        self.session_id = session_id
        self.client = client
        self.server_name = server_name
        self.token_name = token_name
        self.created_at = time.time()
        self.last_used = time.time()
        self.is_active = True
    
    def touch(self):
        """Update last used timestamp."""
        self.last_used = time.time()
    
    def close(self):
        """Close SSH connection."""
        if self.is_active:
            try:
                self.client.close()
                self.is_active = False
                logger.debug(
                    f"Closed SSH connection: {self.session_id} "
                    f"to {self.server_name}"
                )
            except Exception as e:
                logger.error(f"Error closing SSH connection: {e}")
    
    def is_alive(self) -> bool:
        """Check if connection is still alive."""
        try:
            transport = self.client.get_transport()
            return transport is not None and transport.is_active()
        except:
            return False


class SSHConnectionPool:
    """Thread-safe SSH connection pool manager."""
    
    def __init__(self):
        self.connections: Dict[str, SSHConnection] = {}
        self.lock = threading.RLock()
        self.cleanup_interval = 300  # 5 minutes
        self.max_idle_time = 600  # 10 minutes
        self._cleanup_task: Optional[asyncio.Task] = None
    
    def _generate_session_id(self) -> str:
        """Generate unique session ID."""
        return f"ssh_{uuid.uuid4().hex[:16]}"
    
    def _load_ssh_key(self, key_path: str, passphrase: Optional[str] = None):
        """Load SSH private key."""
        key_path = Path(key_path)
        
        if not key_path.exists():
            raise FileNotFoundError(f"SSH key not found: {key_path}")
        
        # Try different key types
        for key_class in [Ed25519Key, RSAKey]:
            try:
                if passphrase:
                    return key_class.from_private_key_file(
                        str(key_path), 
                        password=passphrase
                    )
                else:
                    return key_class.from_private_key_file(str(key_path))
            except Exception:
                continue
        
        raise ValueError(f"Could not load SSH key: {key_path}")
    
    def create_connection(
        self,
        server_name: str,
        token_name: str
    ) -> Tuple[str, SSHConnection]:
        """
        Create new SSH connection.
        
        Args:
            server_name: Name of server to connect to
            token_name: Name of token making the connection
        
        Returns:
            Tuple of (session_id, SSHConnection)
        
        Raises:
            Exception: If connection fails
        """
        config = get_config()
        audit = get_audit_logger()
        
        server_config = config.get_server(server_name)
        if not server_config:
            raise ValueError(f"Server not found: {server_name}")
        
        if not server_config.enabled:
            raise ValueError(f"Server is disabled: {server_name}")
        
        session_id = self._generate_session_id()
        client = None

        try:
            # Create SSH client
            client = SSHClient()
            client.set_missing_host_key_policy(AutoAddPolicy())

            # Load SSH key
            passphrase = server_config.get_passphrase()
            pkey = self._load_ssh_key(
                server_config.ssh_key_path,
                passphrase
            )

            # Connect
            logger.info(
                f"Connecting to {server_name} ({server_config.host}:{server_config.port}) "
                f"as {server_config.user} - Session: {session_id}"
            )

            client.connect(
                hostname=server_config.host,
                port=server_config.port,
                username=server_config.user,
                pkey=pkey,
                timeout=30,
                banner_timeout=30,
                auth_timeout=30,
                look_for_keys=False,
                allow_agent=False
            )

            # Create connection object
            connection = SSHConnection(
                session_id=session_id,
                client=client,
                server_name=server_name,
                token_name=token_name
            )

            # Store in pool
            with self.lock:
                self.connections[session_id] = connection

            audit.log_ssh_connection(token_name, server_name, 'success')

            logger.info(
                f"SSH connection established: {session_id} to {server_name}"
            )

            return session_id, connection

        except (SSHException, TimeoutError, OSError) as e:
            error_msg = str(e)
            audit.log_ssh_connection(token_name, server_name, 'failed', error_msg)
            logger.error(f"Failed to connect to {server_name}: {error_msg}")
            if client:
                try:
                    client.close()
                except Exception:
                    pass
            raise SSHConnectionError(server_name, error_msg)
        except Exception as e:
            error_msg = str(e)
            audit.log_ssh_connection(token_name, server_name, 'failed', error_msg)
            logger.error(f"Failed to connect to {server_name}: {error_msg}")
            if client:
                try:
                    client.close()
                except Exception:
                    pass
            raise SSHConnectionError(server_name, error_msg)
    
    def get_connection(self, session_id: str) -> Optional[SSHConnection]:
        """Get connection by session ID."""
        with self.lock:
            connection = self.connections.get(session_id)
            
            if connection:
                # Check if connection is still alive
                if not connection.is_alive():
                    logger.warning(
                        f"Connection {session_id} is dead, removing"
                    )
                    self.close_connection(session_id)
                    return None
                
                connection.touch()
            
            return connection
    
    def close_connection(self, session_id: str):
        """Close and remove connection."""
        with self.lock:
            connection = self.connections.pop(session_id, None)
            if connection:
                connection.close()
                logger.info(f"Connection closed: {session_id}")
    
    def close_all_connections(self):
        """Close all connections."""
        with self.lock:
            session_ids = list(self.connections.keys())
            for session_id in session_ids:
                self.close_connection(session_id)
            
            logger.info("All SSH connections closed")
    
    def cleanup_idle_connections(self):
        """Remove idle connections."""
        current_time = time.time()
        
        with self.lock:
            to_remove = []
            
            for session_id, connection in self.connections.items():
                idle_time = current_time - connection.last_used
                
                if idle_time > self.max_idle_time:
                    logger.info(
                        f"Closing idle connection: {session_id} "
                        f"(idle: {int(idle_time)}s)"
                    )
                    to_remove.append(session_id)
                elif not connection.is_alive():
                    logger.warning(
                        f"Removing dead connection: {session_id}"
                    )
                    to_remove.append(session_id)
            
            for session_id in to_remove:
                self.close_connection(session_id)
            
            if to_remove:
                logger.info(f"Cleaned up {len(to_remove)} connections")
    
    def get_stats(self) -> Dict:
        """Get connection pool statistics."""
        with self.lock:
            total = len(self.connections)
            alive = sum(1 for c in self.connections.values() if c.is_alive())
            
            by_server = {}
            for conn in self.connections.values():
                by_server[conn.server_name] = by_server.get(conn.server_name, 0) + 1
            
            return {
                'total_connections': total,
                'alive_connections': alive,
                'connections_by_server': by_server
            }
    
    async def start_cleanup_task(self):
        """Start background cleanup task."""
        async def cleanup_loop():
            while True:
                await asyncio.sleep(self.cleanup_interval)
                self.cleanup_idle_connections()
        
        self._cleanup_task = asyncio.create_task(cleanup_loop())
        logger.info("Started SSH connection cleanup task")
    
    def stop_cleanup_task(self):
        """Stop background cleanup task."""
        if self._cleanup_task:
            self._cleanup_task.cancel()
            logger.info("Stopped SSH connection cleanup task")


# Global connection pool
_connection_pool: Optional[SSHConnectionPool] = None


def get_connection_pool() -> SSHConnectionPool:
    """Get global connection pool instance."""
    global _connection_pool
    if _connection_pool is None:
        _connection_pool = SSHConnectionPool()
    return _connection_pool


def create_ssh_connection(
    server_name: str,
    token_name: str
) -> Tuple[str, SSHConnection]:
    """
    Create new SSH connection using global pool.
    
    Args:
        server_name: Server to connect to
        token_name: Token making the connection
    
    Returns:
        Tuple of (session_id, SSHConnection)
    """
    pool = get_connection_pool()
    return pool.create_connection(server_name, token_name)


def get_ssh_connection(session_id: str) -> Optional[SSHConnection]:
    """Get SSH connection by session ID."""
    pool = get_connection_pool()
    return pool.get_connection(session_id)


def close_ssh_connection(session_id: str):
    """Close SSH connection."""
    pool = get_connection_pool()
    pool.close_connection(session_id)


def close_all_ssh_connections():
    """Close all SSH connections."""
    pool = get_connection_pool()
    pool.close_all_connections()


def get_pool_stats() -> Dict:
    """Get connection pool statistics."""
    pool = get_connection_pool()
    return pool.get_stats()




