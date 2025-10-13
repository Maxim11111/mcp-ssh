"""CLI manager for MCP SSH Server administration."""

import os
import sys
import json
import getpass
from pathlib import Path
from typing import Optional
import logging

import typer
from rich.console import Console
from rich.table import Table
from rich import print as rprint
import paramiko
import questionary
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ed25519
from cryptography.hazmat.backends import default_backend
import base64

from src.config import Config, ServerConfig, TokenConfig
from src.auth import generate_token, create_token_config

# Setup logging
logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)

app = typer.Typer(help="MCP SSH Server Management CLI")
console = Console()

# Subcommands
server_app = typer.Typer(help="Server management commands")
token_app = typer.Typer(help="Token management commands")
key_app = typer.Typer(help="SSH key management commands")

app.add_typer(server_app, name="server")
app.add_typer(token_app, name="token")
app.add_typer(key_app, name="key")


def get_config() -> Config:
    """Load configuration."""
    config_dir = typer.prompt("Config directory", default="./config")
    return Config(config_dir)


@server_app.command("add")
def server_add(
    config_dir: str = typer.Option("./config", help="Configuration directory")
):
    """
    Add a new server with automatic SSH key setup.
    
    This command will:
    1. Prompt for server details
    2. Generate SSH key if needed
    3. Connect with password (one time)
    4. Install public key on remote server
    5. Test passwordless connection
    6. Save configuration
    """
    console.print("\n[bold cyan]Add New Server[/bold cyan]\n")
    
    config = Config(config_dir)
    
    # Interactive prompts
    try:
        server_name = questionary.text(
            "Server name (e.g., 'prod-web-01'):",
            validate=lambda x: len(x) > 0
        ).ask()
        
        if not server_name:
            console.print("[red]Cancelled[/red]")
            return
        
        if server_name in config.servers:
            if not questionary.confirm(f"Server '{server_name}' already exists. Overwrite?").ask():
                return
        
        host = questionary.text(
            "Hostname or IP:",
            validate=lambda x: len(x) > 0
        ).ask()
        
        port = questionary.text(
            "SSH Port:",
            default="22"
        ).ask()
        
        user = questionary.text(
            "SSH Username:",
            default="root"
        ).ask()
        
        description = questionary.text(
            "Description (optional):"
        ).ask()
        
        tags_input = questionary.text(
            "Tags (comma-separated, optional):",
            default=""
        ).ask()
        tags = [t.strip() for t in tags_input.split(',') if t.strip()]
        
        # SSH key setup
        keys_dir = Path(os.getenv('KEYS_DIR', './keys'))
        keys_dir.mkdir(parents=True, exist_ok=True)
        
        key_name = f"{server_name}_ed25519"
        private_key_path = keys_dir / key_name
        public_key_path = keys_dir / f"{key_name}.pub"
        
        # Generate key if doesn't exist
        if not private_key_path.exists():
            console.print(f"\n[yellow]Generating SSH key: {private_key_path}[/yellow]")
            
            # Generate ED25519 key using cryptography
            private_key = ed25519.Ed25519PrivateKey.generate()
            
            # Serialize private key to OpenSSH format
            private_bytes = private_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.OpenSSH,
                encryption_algorithm=serialization.NoEncryption()
            )
            
            # Write private key
            with open(private_key_path, 'wb') as f:
                f.write(private_bytes)
            
            # Get public key
            public_key_obj = private_key.public_key()
            public_bytes = public_key_obj.public_bytes(
                encoding=serialization.Encoding.OpenSSH,
                format=serialization.PublicFormat.OpenSSH
            )
            
            # Write public key with comment
            public_key_str = public_bytes.decode('utf-8') + f" mcp-server@{server_name}\n"
            with open(public_key_path, 'w') as f:
                f.write(public_key_str)
            
            # Set permissions
            private_key_path.chmod(0o600)
            public_key_path.chmod(0o644)
            
            console.print("[green]✓[/green] SSH key generated")
        else:
            console.print(f"\n[yellow]Using existing SSH key: {private_key_path}[/yellow]")
        
        # Read public key
        with open(public_key_path, 'r') as f:
            public_key_content = f.read().strip()
        
        # Connect with password and install key
        console.print(f"\n[bold]Connecting to {host}:{port} as {user}[/bold]")
        console.print("[yellow]Please enter password for initial connection:[/yellow]")
        
        password = getpass.getpass("Password: ")
        
        try:
            # Create SSH client
            client = paramiko.SSHClient()
            client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            
            console.print("[yellow]Connecting...[/yellow]")
            client.connect(
                hostname=host,
                port=int(port),
                username=user,
                password=password,
                timeout=30
            )
            
            console.print("[green]✓[/green] Connected successfully")
            
            # Install public key
            console.print("[yellow]Installing SSH public key...[/yellow]")
            
            commands = [
                'mkdir -p ~/.ssh',
                'chmod 700 ~/.ssh',
                f'echo "{public_key_content}" >> ~/.ssh/authorized_keys',
                'chmod 600 ~/.ssh/authorized_keys',
                'echo "Key installed successfully"'
            ]
            
            for cmd in commands:
                stdin, stdout, stderr = client.exec_command(cmd)
                exit_code = stdout.channel.recv_exit_status()
                if exit_code != 0:
                    error = stderr.read().decode()
                    raise Exception(f"Command failed: {cmd}\\n{error}")
            
            console.print("[green]✓[/green] SSH key installed")
            
            client.close()
            
            # Test passwordless connection
            console.print("[yellow]Testing passwordless connection...[/yellow]")
            
            client2 = paramiko.SSHClient()
            client2.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            
            pkey = paramiko.Ed25519Key.from_private_key_file(str(private_key_path))
            
            client2.connect(
                hostname=host,
                port=int(port),
                username=user,
                pkey=pkey,
                timeout=30,
                look_for_keys=False,
                allow_agent=False
            )
            
            stdin, stdout, stderr = client2.exec_command('echo "Connection test successful"')
            output = stdout.read().decode()
            
            console.print("[green]✓[/green] Passwordless connection works!")
            
            client2.close()
            
        except Exception as e:
            console.print(f"\n[red]Error: {e}[/red]")
            console.print("\n[yellow]Note: You can manually install the public key using:[/yellow]")
            console.print(f"  ssh-copy-id -i {public_key_path} {user}@{host}")
            
            if not questionary.confirm("Continue saving server configuration anyway?").ask():
                return
        
        # Save server configuration
        server_config = ServerConfig(
            host=host,
            port=int(port),
            user=user,
            ssh_key_path=str(private_key_path),
            ssh_key_passphrase_env=None,
            tags=tags,
            enabled=True,
            description=description
        )
        
        config.add_server(server_name, server_config)
        
        console.print(f"\n[bold green]✓ Server '{server_name}' added successfully![/bold green]\n")
        
    except KeyboardInterrupt:
        console.print("\n[red]Cancelled[/red]")
        sys.exit(1)
    except Exception as e:
        console.print(f"\n[red]Error: {e}[/red]")
        sys.exit(1)


@server_app.command("list")
def server_list(
    config_dir: str = typer.Option("./config", help="Configuration directory")
):
    """List all configured servers."""
    config = Config(config_dir)
    
    if not config.servers:
        console.print("[yellow]No servers configured[/yellow]")
        return
    
    table = Table(title="Configured Servers")
    table.add_column("Name", style="cyan")
    table.add_column("Host", style="green")
    table.add_column("User", style="blue")
    table.add_column("Tags", style="magenta")
    table.add_column("Status", style="yellow")
    
    for name, server in config.servers.items():
        status = "✓ Enabled" if server.enabled else "✗ Disabled"
        tags_str = ", ".join(server.tags) if server.tags else "-"
        
        table.add_row(
            name,
            f"{server.host}:{server.port}",
            server.user,
            tags_str,
            status
        )
    
    console.print(table)


@server_app.command("remove")
def server_remove(
    name: str = typer.Argument(..., help="Server name to remove"),
    config_dir: str = typer.Option("./config", help="Configuration directory"),
    remove_key: bool = typer.Option(False, "--remove-key", help="Also remove SSH key")
):
    """Remove a server configuration."""
    config = Config(config_dir)
    
    if name not in config.servers:
        console.print(f"[red]Server '{name}' not found[/red]")
        return
    
    server = config.servers[name]
    
    console.print(f"\n[yellow]Server: {name}[/yellow]")
    console.print(f"Host: {server.host}:{server.port}")
    console.print(f"User: {server.user}\n")
    
    if not questionary.confirm("Are you sure you want to remove this server?").ask():
        console.print("[yellow]Cancelled[/yellow]")
        return
    
    # Remove key if requested
    if remove_key:
        key_path = Path(server.ssh_key_path)
        pub_key_path = Path(str(key_path) + '.pub')
        
        if key_path.exists():
            key_path.unlink()
            console.print(f"[green]✓[/green] Removed key: {key_path}")
        
        if pub_key_path.exists():
            pub_key_path.unlink()
            console.print(f"[green]✓[/green] Removed key: {pub_key_path}")
    
    # Remove from config
    config.remove_server(name)
    
    console.print(f"\n[bold green]✓ Server '{name}' removed[/bold green]")


@server_app.command("test")
def server_test(
    name: str = typer.Argument(..., help="Server name to test"),
    config_dir: str = typer.Option("./config", help="Configuration directory")
):
    """Test SSH connection to a server."""
    config = Config(config_dir)
    
    if name not in config.servers:
        console.print(f"[red]Server '{name}' not found[/red]")
        return
    
    server = config.servers[name]
    
    console.print(f"\n[bold]Testing connection to {name}[/bold]")
    console.print(f"Host: {server.host}:{server.port}")
    console.print(f"User: {server.user}\n")
    
    try:
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        
        pkey = paramiko.Ed25519Key.from_private_key_file(server.ssh_key_path)
        
        console.print("[yellow]Connecting...[/yellow]")
        
        client.connect(
            hostname=server.host,
            port=server.port,
            username=server.user,
            pkey=pkey,
            timeout=30,
            look_for_keys=False,
            allow_agent=False
        )
        
        console.print("[green]✓[/green] Connected successfully")
        
        # Run test command
        stdin, stdout, stderr = client.exec_command('uname -a')
        output = stdout.read().decode().strip()
        
        console.print(f"\n[cyan]System info:[/cyan] {output}\n")
        
        client.close()
        
        console.print("[bold green]✓ Connection test passed![/bold green]\n")
        
    except Exception as e:
        console.print(f"\n[red]✗ Connection failed: {e}[/red]\n")
        sys.exit(1)


@token_app.command("create")
def token_create(
    config_dir: str = typer.Option("./config", help="Configuration directory")
):
    """Create a new API token."""
    config = Config(config_dir)
    
    console.print("\n[bold cyan]Create New API Token[/bold cyan]\n")
    
    try:
        name = questionary.text(
            "Token name (e.g., 'cursor-admin'):",
            validate=lambda x: len(x) > 0
        ).ask()
        
        description = questionary.text(
            "Description:"
        ).ask()
        
        permissions = questionary.checkbox(
            "Select permissions:",
            choices=[
                "execute",
                "read",
                "write",
                "install",
                "manage"
            ]
        ).ask()
        
        if not permissions:
            console.print("[red]No permissions selected[/red]")
            return
        
        allowed_servers = questionary.text(
            "Allowed servers (comma-separated, or '*' for all):",
            default="*"
        ).ask()
        
        allowed_list = [s.strip() for s in allowed_servers.split(',')]
        
        # Generate token
        token, token_config = create_token_config(
            name=name,
            description=description,
            permissions=permissions,
            allowed_servers=allowed_list
        )
        
        # Save to config
        config.add_token(token, token_config)
        
        console.print(f"\n[bold green]✓ Token created successfully![/bold green]\n")
        console.print(f"[cyan]Token:[/cyan] {token}")
        console.print("\n[yellow]⚠ Save this token securely. It won't be shown again.[/yellow]\n")
        
    except KeyboardInterrupt:
        console.print("\n[red]Cancelled[/red]")
        sys.exit(1)


@token_app.command("list")
def token_list(
    config_dir: str = typer.Option("./config", help="Configuration directory")
):
    """List all API tokens."""
    config = Config(config_dir)
    
    if not config.tokens:
        console.print("[yellow]No tokens configured[/yellow]")
        return
    
    table = Table(title="API Tokens")
    table.add_column("Name", style="cyan")
    table.add_column("Permissions", style="green")
    table.add_column("Servers", style="blue")
    table.add_column("Status", style="yellow")
    
    for token, token_config in config.tokens.items():
        status = "✓ Enabled" if token_config.enabled else "✗ Disabled"
        perms_str = ", ".join(token_config.permissions)
        servers_str = ", ".join(token_config.allowed_servers)
        
        table.add_row(
            token_config.name,
            perms_str,
            servers_str,
            status
        )
    
    console.print(table)


@token_app.command("revoke")
def token_revoke(
    token: str = typer.Argument(..., help="Token to revoke (or token name)"),
    config_dir: str = typer.Option("./config", help="Configuration directory")
):
    """Revoke an API token."""
    config = Config(config_dir)
    
    # Find token
    found_token = None
    for t, tc in config.tokens.items():
        if t == token or tc.name == token:
            found_token = t
            break
    
    if not found_token:
        console.print(f"[red]Token not found: {token}[/red]")
        return
    
    token_config = config.tokens[found_token]
    
    console.print(f"\n[yellow]Token: {token_config.name}[/yellow]")
    console.print(f"Permissions: {', '.join(token_config.permissions)}\n")
    
    if not questionary.confirm("Are you sure you want to revoke this token?").ask():
        console.print("[yellow]Cancelled[/yellow]")
        return
    
    config.remove_token(found_token)
    
    console.print(f"\n[bold green]✓ Token revoked[/bold green]")


@app.command("status")
def show_status(
    config_dir: str = typer.Option("./config", help="Configuration directory")
):
    """Show system status."""
    config = Config(config_dir)
    
    console.print("\n[bold cyan]MCP SSH Server Status[/bold cyan]\n")
    
    console.print(f"[cyan]Configuration directory:[/cyan] {config.config_dir}")
    console.print(f"[cyan]Servers configured:[/cyan] {len(config.servers)}")
    console.print(f"[cyan]Tokens configured:[/cyan] {len(config.tokens)}")
    console.print()


if __name__ == "__main__":
    app()

