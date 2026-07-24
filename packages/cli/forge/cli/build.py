from __future__ import annotations

import re
import subprocess
import tempfile
from pathlib import Path

import typer
from forge.core.config_loader import load_agent_config
from rich.console import Console

console = Console()

DOCKERFILE_DIR = (
    Path(__file__).resolve().parent.parent.parent.parent.parent
    / "packages" / "deploy" / "docker"
)
MONOREPO_ROOT = DOCKERFILE_DIR.parent.parent.parent

VALID_TAG_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_\.\-]{0,127}$")


def _check_docker() -> None:
    try:
        subprocess.run(["docker", "version"], capture_output=True, check=True)
    except (FileNotFoundError, subprocess.CalledProcessError):
        console.print("[red]Error:[/red] Docker is not installed or not running.")
        raise typer.Exit(1) from None


def _validate_tag(tag: str) -> str:
    parts = tag.split("/")
    for part in parts:
        subparts = part.split(":")
        label = subparts[0]
        if not VALID_TAG_RE.match(label):
            console.print(f"[red]Error:[/red] Invalid tag: {tag}")
            raise typer.Exit(1)
    return tag


def agent(
    config_path: str = typer.Argument(..., help="Path to agent YAML/JSON config"),
    tag: str = typer.Option("", "--tag", "-t", help="Image tag (default: auto)"),
    push: bool = typer.Option(False, "--push", "-p", help="Push image to registry after build"),
    registry: str = typer.Option("", "--registry", "-r", help="Registry to push to"),
) -> None:
    _check_docker()

    path = Path(config_path)
    if not path.exists():
        console.print(f"[red]Error:[/red] File not found: {config_path}")
        raise typer.Exit(1)

    config = load_agent_config(path)
    safe_name = re.sub(r"[^a-zA-Z0-9_\-]", "-", config.name)

    if not tag:
        tag = f"forge/agent-{safe_name}:latest"
    tag = _validate_tag(tag)

    registry_tag = f"{registry}/agent-{safe_name}:latest" if registry else ""

    dockerfile = DOCKERFILE_DIR / "agent.Dockerfile"
    if not dockerfile.exists():
        console.print(f"[red]Error:[/red] Dockerfile not found: {dockerfile}")
        raise typer.Exit(1)

    # Resolve config path relative to monorepo root for Docker build context
    abs_config = path.resolve()
    try:
        rel_config = abs_config.relative_to(MONOREPO_ROOT)
    except ValueError:
        # Config is outside the repo; copy to a temp dir inside the context
        with tempfile.TemporaryDirectory() as tmp:
            tmp_config = Path(tmp) / "agent-config.yaml"
            tmp_config.write_text(abs_config.read_text())
            rel_config = Path(tmp_config.name)

    console.print(f"[bold cyan]Building agent image:[/bold cyan] {tag}")
    console.print(f"  Config: {config_path}")
    console.print(f"  Dockerfile: {dockerfile}")

    build_args = [
        "docker", "build",
        "-f", str(dockerfile),
        "-t", tag,
        "--build-arg", f"AGENT_CONFIG={rel_config}",
        str(MONOREPO_ROOT),
    ]

    result = subprocess.run(build_args, capture_output=True, text=True)
    if result.returncode != 0:
        console.print(f"[red]Build failed:[/red]\n{result.stderr}")
        raise typer.Exit(1)

    console.print(f"[bold green]Build succeeded:[/bold green] {tag}")

    if push:
        if not registry_tag:
            console.print("[yellow]Warning:[/yellow] No registry specified")
            push_tag = tag
        else:
            push_tag = registry_tag
            subprocess.run(["docker", "tag", tag, push_tag], check=True)

        console.print(f"Pushing {push_tag} ...")
        result = subprocess.run(["docker", "push", push_tag], capture_output=True, text=True)
        if result.returncode != 0:
            console.print(f"[red]Push failed:[/red]\n{result.stderr}")
            raise typer.Exit(1)
        console.print(f"[bold green]Push succeeded:[/bold green] {push_tag}")


def api(
    tag: str = typer.Option("forge/api:latest", "--tag", "-t", help="Image tag"),
    push: bool = typer.Option(False, "--push", "-p", help="Push image after build"),
    registry: str = typer.Option("", "--registry", "-r", help="Registry to push to"),
) -> None:
    _check_docker()

    tag = _validate_tag(tag)
    dockerfile = DOCKERFILE_DIR / "api.Dockerfile"
    if not dockerfile.exists():
        console.print(f"[red]Error:[/red] Dockerfile not found: {dockerfile}")
        raise typer.Exit(1)

    console.print(f"[bold cyan]Building API image:[/bold cyan] {tag}")
    build_args = [
        "docker", "build",
        "-f", str(dockerfile),
        "-t", tag,
        str(MONOREPO_ROOT),
    ]

    result = subprocess.run(build_args, capture_output=True, text=True)
    if result.returncode != 0:
        console.print(f"[red]Build failed:[/red]\n{result.stderr}")
        raise typer.Exit(1)

    console.print(f"[bold green]Build succeeded:[/bold green] {tag}")

    if push:
        push_tag = f"{registry}/{tag}" if registry else tag
        if registry:
            subprocess.run(["docker", "tag", tag, push_tag], check=True)
        console.print(f"Pushing {push_tag} ...")
        result = subprocess.run(["docker", "push", push_tag], capture_output=True, text=True)
        if result.returncode != 0:
            console.print(f"[red]Push failed:[/red]\n{result.stderr}")
            raise typer.Exit(1)
        console.print(f"[bold green]Push succeeded:[/bold green] {push_tag}")
