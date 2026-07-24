from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import httpx
import typer
from rich.console import Console
from rich.table import Table

console = Console()
auth_app = typer.Typer(help="Authentication commands")

TOKEN_FILE = Path.home() / ".forge" / "credentials.json"


def _get_api_url() -> str:
    return os.environ.get("FORGE_API_URL", "http://localhost:8000")


def _load_credentials() -> dict[str, Any]:
    if TOKEN_FILE.exists():
        return json.loads(TOKEN_FILE.read_text())
    return {}


def _save_credentials(data: dict[str, Any]) -> None:
    TOKEN_FILE.parent.mkdir(parents=True, exist_ok=True)
    TOKEN_FILE.write_text(json.dumps(data, indent=2))
    TOKEN_FILE.chmod(0o600)


def _clear_credentials() -> None:
    if TOKEN_FILE.exists():
        TOKEN_FILE.unlink()


def _get_headers() -> dict[str, str]:
    creds = _load_credentials()
    token = creds.get("access_token") or creds.get("api_key", "")
    if token:
        if creds.get("auth_method") == "api_key":
            return {"X-API-Key": token}
        return {"Authorization": f"Bearer {token}"}
    return {}


@auth_app.command()
def register(
    username: str = typer.Argument(..., help="Desired username"),
    email: str = typer.Argument(..., help="Email address"),
    password: str = typer.Option(
        ..., "--password", "-p", prompt=True, hide_input=True,
        confirmation_prompt=True, help="Password",
    ),
):
    """Register a new user account."""
    url = f"{_get_api_url()}/api/v1/auth/register"
    try:
        with httpx.Client() as client:
            resp = client.post(
                url,
                json={"username": username, "email": email, "password": password},
            )
            if resp.status_code == 201:
                data = resp.json()
                console.print(f"[bold green]User '{data['username']}' registered successfully[/bold green]")
                console.print(f"  ID: {data['id']}")
                console.print(f"  Email: {data['email']}")
            else:
                detail = resp.json().get("detail", "Unknown error")
                console.print(f"[bold red]Registration failed: {detail}[/bold red]")
                raise typer.Exit(1)
    except httpx.ConnectError:
        console.print(f"[bold red]Cannot connect to Forge API at {url}[/bold red]")
        raise typer.Exit(1) from None


@auth_app.command()
def login(
    username: str = typer.Argument(..., help="Username"),
    password: str = typer.Option(
        ..., "--password", "-p", prompt=True, hide_input=True, help="Password",
    ),
):
    """Login and save credentials."""
    url = f"{_get_api_url()}/api/v1/auth/login"
    try:
        with httpx.Client() as client:
            resp = client.post(
                url,
                json={"username": username, "password": password},
            )
            if resp.status_code == 200:
                data = resp.json()
                _save_credentials({
                    "access_token": data["access_token"],
                    "refresh_token": data["refresh_token"],
                    "auth_method": "jwt",
                    "api_url": _get_api_url(),
                })
                console.print("[bold green]Login successful[/bold green]")
                console.print(f"  Token expires in: {data.get('expires_in', 1440)} minutes")
            else:
                detail = resp.json().get("detail", "Invalid credentials")
                console.print(f"[bold red]Login failed: {detail}[/bold red]")
                raise typer.Exit(1)
    except httpx.ConnectError:
        console.print(f"[bold red]Cannot connect to Forge API at {url}[/bold red]")
        raise typer.Exit(1) from None


@auth_app.command()
def logout():
    """Clear saved credentials."""
    _clear_credentials()
    console.print("[bold green]Logged out successfully[/bold green]")


@auth_app.command()
def status():
    """Check authentication status."""
    creds = _load_credentials()
    if not creds:
        console.print("[yellow]Not authenticated. Run 'forge auth login' to authenticate.[/yellow]")
        return

    method = creds.get("auth_method", "unknown")
    console.print("[bold green]Authenticated[/bold green]")
    console.print(f"  Method: {method}")
    console.print(f"  API URL: {creds.get('api_url', 'unknown')}")

    if method == "jwt":
        token = creds.get("access_token", "")
        if token:
            import base64
            try:
                payload = token.split(".")[1]
                padded = payload + "=" * (4 - len(payload) % 4)
                data = json.loads(base64.urlsafe_b64decode(padded))
                console.print(f"  Subject: {data.get('sub', 'unknown')}")
                console.print(f"  Roles: {', '.join(data.get('roles', []))}")
            except Exception:
                pass


@auth_app.command()
def api_key(
    name: str = typer.Argument(..., help="Name for the API key"),
    expires_days: int = typer.Option(
        365, "--expires-days", "-d", help="Days until key expires",
    ),
):
    """Create a new API key."""
    url = f"{_get_api_url()}/api/v1/auth/api-keys"
    try:
        with httpx.Client() as client:
            resp = client.post(
                url,
                json={"name": name, "expires_in_days": expires_days},
                headers=_get_headers(),
            )
            if resp.status_code == 201:
                data = resp.json()
                table = Table(title="API Key Created")
                table.add_column("Field", style="cyan")
                table.add_column("Value", style="green")
                table.add_row("Name", data["name"])
                table.add_row("Prefix", data["prefix"])
                table.add_row("Key", f"[bold yellow]{data['key']}[/bold yellow]")
                table.add_row("Expires", str(data.get("expires_at", "Never")))
                console.print(table)
                console.print("\n[yellow]⚠ Store this key securely — it will not be shown again![/yellow]")
            else:
                detail = resp.json().get("detail", "Unknown error")
                console.print(f"[bold red]Failed: {detail}[/bold red]")
                raise typer.Exit(1)
    except httpx.ConnectError:
        console.print("[bold red]Cannot connect to Forge API[/bold red]")
        raise typer.Exit(1) from None


@auth_app.command(name="list-keys")
def list_api_keys():
    """List all API keys for the current user."""
    url = f"{_get_api_url()}/api/v1/auth/api-keys"
    try:
        with httpx.Client() as client:
            resp = client.get(url, headers=_get_headers())
            if resp.status_code == 200:
                keys = resp.json()
                if not keys:
                    console.print("[yellow]No API keys found[/yellow]")
                    return
                table = Table(title="API Keys")
                table.add_column("ID", style="cyan")
                table.add_column("Name", style="green")
                table.add_column("Prefix", style="yellow")
                table.add_column("Active", style="bold")
                table.add_column("Last Used")
                table.add_column("Expires")
                for key in keys:
                    table.add_row(
                        str(key["id"]),
                        key["name"],
                        key["prefix"],
                        "[green]Yes[/green]" if key["is_active"] else "[red]No[/red]",
                        key.get("last_used_at", "Never"),
                        str(key.get("expires_at", "Never")),
                    )
                console.print(table)
            else:
                detail = resp.json().get("detail", "Unknown error")
                console.print(f"[bold red]Failed: {detail}[/bold red]")
                raise typer.Exit(1)
    except httpx.ConnectError:
        console.print("[bold red]Cannot connect to Forge API[/bold red]")
        raise typer.Exit(1) from None


@auth_app.command(name="revoke-key")
def revoke_api_key(
    key_id: int = typer.Argument(..., help="API key ID to revoke"),
):
    """Revoke an API key."""
    url = f"{_get_api_url()}/api/v1/auth/api-keys/{key_id}"
    try:
        with httpx.Client() as client:
            resp = client.delete(url, headers=_get_headers())
            if resp.status_code == 200:
                console.print("[bold green]API key revoked successfully[/bold green]")
            else:
                detail = resp.json().get("detail", "Unknown error")
                console.print(f"[bold red]Failed: {detail}[/bold red]")
                raise typer.Exit(1)
    except httpx.ConnectError:
        console.print("[bold red]Cannot connect to Forge API[/bold red]")
        raise typer.Exit(1) from None
