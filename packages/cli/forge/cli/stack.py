from __future__ import annotations

import subprocess
from pathlib import Path

import typer
from rich.console import Console

console = Console()

COMPOSE_FILE = (
    Path(__file__).resolve().parent.parent.parent.parent.parent
    / "packages" / "deploy" / "docker-compose.yml"
)


def _compose_cmd() -> list[str]:
    if not COMPOSE_FILE.exists():
        console.print(f"[red]Error:[/red] docker-compose.yml not found at {COMPOSE_FILE}")
        raise typer.Exit(1)
    return [
        "docker", "compose",
        "-f", str(COMPOSE_FILE),
    ]


def up(
    detach: bool = typer.Option(True, "--detach", "-d", help="Run containers in background"),
    build: bool = typer.Option(False, "--build", "-b", help="Rebuild images before starting"),
    env_file: str = typer.Option("", "--env-file", "-e", help="Path to .env file"),
) -> None:
    cmd = _compose_cmd()
    cmd.append("up")
    if detach:
        cmd.append("-d")
    if build:
        cmd.append("--build")
    if env_file:
        cmd.extend(["--env-file", env_file])

    console.print("[bold cyan]Starting Forge stack...[/bold cyan]")
    result = subprocess.run(cmd)
    if result.returncode != 0:
        raise typer.Exit(result.returncode)


def down(
    volumes: bool = typer.Option(False, "--volumes", "-v", help="Remove named volumes"),
) -> None:
    cmd = _compose_cmd()
    cmd.append("down")
    if volumes:
        cmd.append("-v")

    console.print("[bold yellow]Stopping Forge stack...[/bold yellow]")
    result = subprocess.run(cmd)
    if result.returncode != 0:
        raise typer.Exit(result.returncode)


def ps() -> None:
    cmd = _compose_cmd()
    cmd.append("ps")
    result = subprocess.run(cmd)
    if result.returncode != 0:
        raise typer.Exit(result.returncode)


def logs(
    follow: bool = typer.Option(False, "--follow", "-f", help="Follow log output"),
    tail: int = typer.Option(100, "--tail", "-n", help="Number of lines to show"),
) -> None:
    cmd = _compose_cmd()
    cmd.append("logs")
    if follow:
        cmd.append("-f")
    cmd.extend(["--tail", str(tail)])
    result = subprocess.run(cmd)
    if result.returncode != 0:
        raise typer.Exit(result.returncode)
