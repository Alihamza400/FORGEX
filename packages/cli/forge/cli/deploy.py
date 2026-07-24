from __future__ import annotations

import re
import subprocess
from pathlib import Path

import typer
from forge.core.config_loader import load_agent_config
from rich.console import Console

console = Console()

MONOREPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent.parent
K8S_DIR = MONOREPO_ROOT / "packages" / "deploy" / "k8s"
HELM_DIR = MONOREPO_ROOT / "packages" / "deploy" / "helm" / "forge"


def _check_kubectl() -> None:
    try:
        subprocess.run(["kubectl", "version", "--client"], capture_output=True, check=True)
    except (FileNotFoundError, subprocess.CalledProcessError):
        console.print("[red]Error:[/red] kubectl is not installed.")
        raise typer.Exit(1) from None


def _check_helm() -> None:
    try:
        subprocess.run(["helm", "version", "--short"], capture_output=True, check=True)
    except (FileNotFoundError, subprocess.CalledProcessError):
        console.print("[red]Error:[/red] Helm is not installed.")
        raise typer.Exit(1) from None


def agent(
    config_path: str = typer.Argument(..., help="Path to agent YAML/JSON config"),
    namespace: str = typer.Option("forge", "--namespace", "-n", help="Kubernetes namespace"),
    image: str = typer.Option("", "--image", "-i", help="Container image (default: from config)"),
    kubeconfig: str = typer.Option("", "--kubeconfig", "-k", help="Path to kubeconfig"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Print manifests without applying"),
) -> None:
    _check_kubectl()

    path = Path(config_path)
    if not path.exists():
        console.print(f"[red]Error:[/red] File not found: {config_path}")
        raise typer.Exit(1)

    config = load_agent_config(path)
    safe_name = re.sub(r"[^a-zA-Z0-9_\-]", "-", config.name)

    if not image:
        image = f"forge/agent-{safe_name}:latest"

    template_path = K8S_DIR / "agent" / "deployment.yaml"
    if not template_path.exists():
        console.print(f"[red]Error:[/red] Template not found: {template_path}")
        raise typer.Exit(1)

    template = template_path.read_text()
    config_yaml = path.read_text()

    rendered = (
        template
        .replace("{{AGENT_NAME}}", safe_name)
        .replace("{{AGENT_VERSION}}", "latest")
        .replace("{{AGENT_CONFIG_YAML}}", config_yaml)
    )

    if dry_run:
        console.print(rendered)
        return

    # Apply via kubectl
    cmd = ["kubectl", "apply", "-n", namespace, "-f", "-"]
    if kubeconfig:
        cmd = ["kubectl", "--kubeconfig", kubeconfig, "apply", "-n", namespace, "-f", "-"]

    result = subprocess.run(
        cmd,
        input=rendered,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        console.print(f"[red]Deploy failed:[/red]\n{result.stderr}")
        raise typer.Exit(1)

    console.print(f"[bold green]Deployed agent:[/bold green] {safe_name}")
    console.print(f"  Namespace: {namespace}")
    console.print(f"  Image: {image}")
    if result.stdout:
        console.print(result.stdout.strip())


def stack(
    namespace: str = typer.Option("forge", "--namespace", "-n", help="Kubernetes namespace"),
    kubeconfig: str = typer.Option("", "--kubeconfig", "-k", help="Path to kubeconfig"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Print manifests without applying"),
) -> None:
    _check_kubectl()

    console.print("[bold cyan]Deploying Forge infrastructure stack...[/bold cyan]")

    # Order matters: namespace → secrets → statefulsets → deployments
    manifest_dirs: list[Path] = [
        K8S_DIR / "namespace.yaml",
    ]
    for fname in ["secrets.yaml"]:
        p = K8S_DIR / fname
        if p.exists():
            manifest_dirs.append(p)
    for path in sorted(K8S_DIR.iterdir()):
        if path.is_dir() and path.name != "agent":
            for f in sorted(path.iterdir()):
                if f.suffix in (".yaml", ".yml"):
                    manifest_dirs.append(f)

    for manifest in manifest_dirs:
        if not manifest.exists():
            continue

        content = manifest.read_text()
        if dry_run:
            console.print(f"--- # {manifest.name}")
            console.print(content)
            continue

        cmd = ["kubectl", "apply", "-n", namespace, "-f", "-"]
        if kubeconfig:
            cmd = ["kubectl", "--kubeconfig", kubeconfig, "apply", "-n", namespace, "-f", "-"]

        result = subprocess.run(
            cmd,
            input=content,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            console.print(f"[red]Failed to apply {manifest.name}:[/red]\n{result.stderr}")
            raise typer.Exit(1)
        if result.stdout.strip():
            console.print(f"  {result.stdout.strip()}")

    console.print("[bold green]Forge stack deployed successfully.[/bold green]")


def helm_install(
    name: str = typer.Option("forge", "--name", help="Helm release name"),
    namespace: str = typer.Option("forge", "--namespace", "-n", help="Kubernetes namespace"),
    values: str = typer.Option("", "--values", "-f", help="Additional values files (comma-sep)"),
    set_args: str = typer.Option("", "--set", help="Set values (comma-sep key=val pairs)"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Simulate installation"),
) -> None:
    _check_helm()

    if not HELM_DIR.exists():
        console.print(f"[red]Error:[/red] Helm chart not found: {HELM_DIR}")
        raise typer.Exit(1)

    cmd = [
        "helm", "upgrade", "--install",
        name,
        str(HELM_DIR),
        "--namespace", namespace,
        "--create-namespace",
    ]

    for v in values.split(",") if values else []:
        if v.strip():
            cmd.extend(["--values", v.strip()])
    for s in set_args.split(",") if set_args else []:
        if s.strip():
            cmd.extend(["--set", s.strip()])
    if dry_run:
        cmd.append("--dry-run")

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        console.print(f"[red]Helm install failed:[/red]\n{result.stderr}")
        raise typer.Exit(1)

    console.print(result.stdout.strip())
    if dry_run:
        console.print(result.stderr.strip())


def helm_uninstall(
    name: str = typer.Option("forge", "--name", help="Helm release name"),
    namespace: str = typer.Option("forge", "--namespace", "-n", help="Kubernetes namespace"),
) -> None:
    _check_helm()

    result = subprocess.run(
        ["helm", "uninstall", name, "--namespace", namespace],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        console.print(f"[red]Helm uninstall failed:[/red]\n{result.stderr}")
        raise typer.Exit(1)

    console.print(f"[green]Helm release '{name}' uninstalled.[/green]")
