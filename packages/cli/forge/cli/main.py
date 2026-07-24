from __future__ import annotations

import asyncio
from pathlib import Path

import typer
from forge.cli import auth as auth_mod  # type: ignore[import-untyped]
from forge.cli import build as build_mod
from forge.cli import deploy as deploy_mod
from forge.cli import orchestrate as orchestrate_mod
from forge.cli import stack as stack_mod
from forge.core.config import settings
from forge.core.config_loader import ConfigLoadError, load_agent_config
from forge.core.logging import configure_logging
from forge.runtime.agent import AgentRuntime
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.table import Table

app = typer.Typer(
    name="forge",
    help="Forge: self-hosted multi-agent AI platform",
    no_args_is_help=True,
)
console = Console()


@app.callback()
def main_callback(
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable verbose output"),
) -> None:
    if verbose:
        settings.log_level = "DEBUG"
    configure_logging()


@app.command()
def version() -> None:
    """Show the Forge version."""
    console.print("[bold cyan]Forge v0.1.0[/bold cyan]")


@app.command()
def status() -> None:
    """Show the status of the Forge stack."""
    table = Table(title="Forge Stack Status")
    table.add_column("Service", style="cyan")
    table.add_column("Status", style="green")
    table.add_column("Endpoint", style="blue")

    table.add_row("API", "ready", f"http://localhost:{settings.api_port}")
    table.add_row("Ollama", "unknown", settings.ollama_base_url)
    table.add_row("PostgreSQL", "unknown", "localhost:5432")
    table.add_row("Qdrant", "unknown", "localhost:6333")
    table.add_row("Redis", "unknown", "localhost:6379")
    table.add_row("MinIO", "unknown", "localhost:9000")

    console.print(table)


@app.command()
def validate(
    config_path: str = typer.Argument(..., help="Path to agent YAML/JSON config"),
) -> None:
    """Validate an agent configuration file."""
    path = Path(config_path)
    if not path.exists():
        console.print(f"[red]Error:[/red] File not found: {config_path}")
        raise typer.Exit(1)

    try:
        config = load_agent_config(path)
        console.print(f"[bold green]Config is valid:[/bold green] {config.name}")
        console.print(f"  Role: {config.role}")
        console.print(f"  Model: {config.model.name}")
        console.print(f"  Tools: {[t.name for t in config.tools] or '(none)'}")
        console.print(f"  Memory: {config.memory.type}")
    except ConfigLoadError as e:
        console.print(f"[red]Config validation failed:[/red] {e}")
        raise typer.Exit(1) from e


@app.command()
def run(
    config_path: str = typer.Argument(..., help="Path to agent YAML/JSON config"),
    task: str = typer.Option("", "--task", "-t", help="Task to run (use --stdin to pipe input)"),
    stdin: bool = typer.Option(False, "--stdin", help="Read task from stdin"),
) -> None:
    """Run an agent with the given task."""
    path = Path(config_path)
    if not path.exists():
        console.print(f"[red]Error:[/red] File not found: {config_path}")
        raise typer.Exit(1)

    try:
        config = load_agent_config(path)
    except ConfigLoadError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1) from e

    if stdin:
        import sys

        task_text = sys.stdin.read().strip()
    elif task:
        task_text = task
    else:
        console.print("[red]Error:[/red] Either --task or --stdin is required")
        raise typer.Exit(1)

    if not task_text:
        console.print("[red]Error:[/red] Task cannot be empty")
        raise typer.Exit(1)

    async def _run() -> None:
        runtime = AgentRuntime(config=config)
        try:
            await runtime.initialize()
            with console.status("[bold cyan]Agent thinking...[/bold cyan]"):
                result = await runtime.run(task_text)

            console.print()
            console.print(Panel(
                Markdown(result.output),
                title=f"[bold]{config.name}[/bold]",
                border_style="cyan",
            ))

            console.print()
            stats = Table.grid(padding=(0, 2))
            stats.add_row("[dim]Iterations:[/dim]", str(result.iterations))
            stats.add_row("[dim]Tokens:[/dim]", str(result.tokens_used))
            stats.add_row("[dim]Duration:[/dim]", f"{result.duration_ms}ms")
            if result.error:
                stats.add_row("[dim]Error:[/dim]", f"[red]{result.error}[/red]")
            console.print(stats)
        finally:
            await runtime.close()

    asyncio.run(_run())


# ── Orchestrate commands ────────────────────────────────────────────────

@app.command("orchestrate")
def orchestrate_command(
    task: str = typer.Argument(..., help="Task to orchestrate"),
    agent: list[str] = typer.Option(  # noqa: B008
        None, "--agent", "-a", help="Agent config file (can be repeated)"
    ),
    strategy: str = typer.Option(
        "auto", "--strategy", "-s",
        help="Orchestration strategy (sequential, parallel, supervisor, auto)"
    ),
    max_concurrency: int = typer.Option(
        3, "--max-concurrency", "-c", help="Maximum parallel agents"
    ),
    timeout: int = typer.Option(
        600, "--timeout", "-t", help="Timeout in seconds"
    ),
    verbose: bool = typer.Option(
        False, "--verbose", "-v", help="Show detailed sub-task results"
    ),
) -> None:
    """Run a multi-agent orchestration."""
    orchestrate_mod.run_orchestrate(
        task=task,
        configs=agent or [],
        strategy=strategy,
        max_concurrency=max_concurrency,
        timeout=timeout,
        verbose=verbose,
    )


# ── Auth commands ───────────────────────────────────────────────────────

app.add_typer(auth_mod.auth_app, name="auth", help="Authentication commands")


# ── Build commands ──────────────────────────────────────────────────────

@app.command()
def build(
    config_path: str = typer.Argument(..., help="Path to agent YAML/JSON config"),
    tag: str = typer.Option("", "--tag", "-t", help="Image tag (default: auto)"),
    push: bool = typer.Option(False, "--push", "-p", help="Push image to registry after build"),
    registry: str = typer.Option("", "--registry", "-r", help="Registry to push to"),
) -> None:
    """Build a Docker image for an agent."""
    build_mod.agent(config_path=config_path, tag=tag, push=push, registry=registry)


# ── Deploy commands ────────────────────────────────────────────────────

@app.command()
def deploy(
    config_path: str = typer.Argument(..., help="Path to agent YAML/JSON config"),
    namespace: str = typer.Option("forge", "--namespace", "-n", help="Kubernetes namespace"),
    image: str = typer.Option("", "--image", "-i", help="Container image"),
    kubeconfig: str = typer.Option("", "--kubeconfig", "-k", help="Path to kubeconfig"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Print manifests without applying"),
) -> None:
    """Deploy an agent to Kubernetes."""
    deploy_mod.agent(
        config_path=config_path,
        namespace=namespace,
        image=image,
        kubeconfig=kubeconfig,
        dry_run=dry_run,
    )


# ── Stack commands ─────────────────────────────────────────────────────

@app.command()
def up(
    detach: bool = typer.Option(True, "--detach", "-d", help="Run containers in background"),
    build: bool = typer.Option(False, "--build", "-b", help="Rebuild images before starting"),
    env_file: str = typer.Option("", "--env-file", "-e", help="Path to .env file"),
) -> None:
    """Start the local Forge stack (Docker Compose)."""
    stack_mod.up(detach=detach, build=build, env_file=env_file)


@app.command()
def down(
    volumes: bool = typer.Option(False, "--volumes", "-v", help="Remove named volumes"),
) -> None:
    """Stop the local Forge stack."""
    stack_mod.down(volumes=volumes)


@app.command()
def logs(
    follow: bool = typer.Option(False, "--follow", "-f", help="Follow log output"),
    tail: int = typer.Option(100, "--tail", "-n", help="Number of lines to show"),
) -> None:
    """Show logs from the local Forge stack."""
    stack_mod.logs(follow=follow, tail=tail)


@app.command()
def ps() -> None:
    """List running containers in the Forge stack."""
    stack_mod.ps()
