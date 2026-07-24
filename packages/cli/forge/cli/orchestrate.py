from __future__ import annotations

import asyncio
from pathlib import Path

import typer
from forge.core.agent_config import AgentConfig
from forge.core.config import settings
from forge.core.config_loader import load_agent_config
from forge.llm.client import OllamaClient
from forge.orchestrator.coordinator import OrchestratorCoordinator
from forge.orchestrator.models import (
    OrchestrationConfig,
    OrchestrationResult,
    OrchestrationStrategy,
    SubTaskStatus,
)
from forge.orchestrator.planner import TaskPlanner
from forge.orchestrator.registry import get_registry
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.table import Table

console = Console()


def run_orchestrate(
    task: str = typer.Argument(..., help="Task to orchestrate"),
    configs: list[str] = typer.Option(  # noqa: B008
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
    validated_strategies = {"sequential", "parallel", "supervisor", "auto"}
    if strategy not in validated_strategies:
        console.print(f"[red]Error:[/red] Invalid strategy '{strategy}'. "
                       f"Choose from: {', '.join(sorted(validated_strategies))}")
        raise typer.Exit(1)

    configs = configs or []
    if not configs:
        console.print("[red]Error:[/red] At least one --agent/-a config is required")
        raise typer.Exit(1)

    agents: dict[str, AgentConfig] = {}
    for cfg_path in configs:
        path = Path(cfg_path)
        if not path.exists():
            console.print(f"[red]Error:[/red] Config not found: {cfg_path}")
            raise typer.Exit(1)
        config = load_agent_config(path)
        agents[config.name] = config

    # Register agents
    registry = get_registry()
    for name, cfg in agents.items():
        registry.register(name=name, role=cfg.role, goal=cfg.goal)

    llm = OllamaClient(base_url=settings.ollama_base_url)
    planner = TaskPlanner(llm_client=llm, registry=registry)

    coord = OrchestratorCoordinator(
        llm_client=llm,
        registry=registry,
        planner=planner,
        agents=agents,
    )

    orch_config = OrchestrationConfig(
        strategy=OrchestrationStrategy(strategy),
        max_concurrency=max_concurrency,
        timeout_seconds=timeout,
    )

    async def _run() -> OrchestrationResult:
        return await coord.orchestrate(task, orch_config)

    console.print(f"[bold cyan]Orchestrating:[/bold cyan] {task}")
    console.print(f"  Strategy: {strategy}")
    console.print(f"  Agents: {', '.join(agents.keys())}")

    with console.status("[bold cyan]Orchestrating...[/bold cyan]"):
        result = asyncio.run(_run())

    console.print()
    status_style = "green" if result.status == SubTaskStatus.COMPLETED else "red"
    console.print(Panel(
        Markdown(result.final_output or result.error or "(no output)"),
        title=f"[bold]{result.status.value.title()}[/bold]",
        border_style=status_style,
    ))

    console.print()
    stats = Table.grid(padding=(0, 2))
    stats.add_row("[dim]Strategy:[/dim]", result.strategy.value)
    stats.add_row("[dim]Status:[/dim]", f"[{status_style}]{result.status.value}[/{status_style}]")
    stats.add_row("[dim]Sub-tasks:[/dim]", str(len(result.sub_results)))
    stats.add_row("[dim]Total Iterations:[/dim]", str(result.total_iterations))
    stats.add_row("[dim]Total Tokens:[/dim]", str(result.total_tokens))
    stats.add_row("[dim]Duration:[/dim]", f"{result.total_duration_ms}ms")
    if result.error:
        stats.add_row("[dim]Error:[/dim]", f"[red]{result.error}[/red]")
    console.print(stats)

    if verbose and result.sub_results:
        console.print()
        console.print("[bold]Sub-task Results:[/bold]")
        for sr in result.sub_results:
            sr_style = "green" if sr.status == SubTaskStatus.COMPLETED else "red"
            console.print(Panel(
                Markdown(sr.output or sr.error or "(no output)"),
                title=f"[bold]{sr.description}[/bold] — [{sr_style}]{sr.status.value}[/{sr_style}]",
                border_style=sr_style,
                width=80,
            ))
