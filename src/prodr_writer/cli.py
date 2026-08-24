"""CLI entry points.

Commands: generate (default), config, info.
`python -m prodr_writer` and the `prodr-writer` script both land here.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from rich.table import Table

from . import __version__
from .config import AppConfig, test_connection
from .profiles import list_profiles
from .schemas import ProjectInput

app = typer.Typer(add_completion=False, no_args_is_help=False,
                  context_settings={"help_option_names": ["-h", "--help"]})
console = Console()

INDUSTRIES = ["general", "insurance", "banking", "healthcare", "government",
              "telecom", "manufacturing", "retail", "energy"]

# Generic API-key shape found inside litellm/provider error strings.
_API_KEY_RE = re.compile(r"sk-[A-Za-z0-9]{8,}")


def redact_secrets(text: str, api_key: str = "") -> str:
    """Strip API keys out of provider error strings before display/logging."""
    if api_key:
        text = text.replace(api_key, "***")
    return _API_KEY_RE.sub("sk-***", text)


def _interactive_inputs(project: Optional[str], provided: Optional[dict] = None) -> ProjectInput:
    """Interactive prompts; answers already given on the command line are skipped."""
    provided = provided or {}

    def ask(key: str, prompt_text: str, **kwargs):
        value = provided.get(key)
        return value if value is not None else Prompt.ask(prompt_text, **kwargs)

    project = provided.get("project_name") or project or Prompt.ask("Project name")
    client = ask("client_name", "Client name", default="")
    vendor = ask("vendor_name", "Vendor name (your company)", default="")
    industry = ask("industry", f"Industry {INDUSTRIES}", default="general")
    while industry not in INDUSTRIES:
        industry = Prompt.ask("Please choose from the listed industries", default="general")
    rto = ask("overall_rto", "Overall RTO target (e.g. '< 4 hours')", default="< 4 hours")
    rpo = ask("overall_rpo", "Overall RPO target (e.g. '< 1 hour')", default="< 1 hour")
    budget = ask("budget", "Budget range (e.g. 'USD 200k-300k')", default="")
    return ProjectInput(project_name=project, client_name=client, vendor_name=vendor,
                        industry=industry, overall_rto=rto, overall_rpo=rpo, budget=budget)


def _generate(inputs: ProjectInput, cfg: AppConfig, output_dir: Optional[Path],
              fresh: bool = False) -> dict:
    missing = cfg.missing()
    if missing:
        console.print(Panel.fit(
            "[yellow]LLM configuration is incomplete.[/yellow]\n"
            f"Missing: [bold]{', '.join(missing)}[/bold]\n"
            "Run [bold]prodr-writer config[/bold] to set base_url / api_key / model,\n"
            "or export PRODR_BASE_URL / PRODR_API_KEY / PRODR_MODEL.",
            title="Configuration required"))
        raise typer.Exit(code=2)
    cfg.language = inputs.language
    if output_dir:
        cfg.output_dir = str(output_dir)

    from .pipeline import Pipeline  # deferred: heavy crewai import

    _, summary = Pipeline(cfg, fresh=fresh).run(inputs)
    return summary


@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    project: Optional[str] = typer.Option(None, "--project", "-p", help="Project name"),
    interactive: bool = typer.Option(False, "--interactive", "-i",
                                     help="Prompt for all project parameters interactively"),
    language: Optional[str] = typer.Option(None, "--language", "-L", help="Output language: en|zh"),
    profile: Optional[str] = typer.Option(None, "--profile", help="Compliance profile name"),
):
    """Generate a DR proposal document (default action when no command given)."""
    if ctx.invoked_subcommand is not None:
        return  # a real subcommand (config/info) was invoked — do NOT generate
    cfg = AppConfig.load({"language": language, "profile": profile})
    inputs_kwargs = {"language": cfg.language, "profile": cfg.profile}
    if interactive or not project:
        base = _interactive_inputs(project)
        inputs = base.model_copy(update={k: v for k, v in {
            "language": language or base.language,
            "profile": profile or base.profile}.items()})
    else:
        inputs = ProjectInput(project_name=project, **inputs_kwargs)
    try:
        summary = _generate(inputs, cfg, None)
    except typer.Exit:
        raise
    except Exception as exc:  # noqa: BLE001 — single loud failure point
        console.print(f"[red]Generation failed:[/red] "
                      f"{type(exc).__name__}: {redact_secrets(str(exc), cfg.llm.api_key)}")
        raise typer.Exit(code=1)
    console.print(f"[green]Done.[/green] Document: {summary['docx']} "
                  f"(review rounds: {summary['review_rounds']}, final score: {summary['score']}, "
                  f"fatal findings: {summary['fatal_findings']}, warnings: {summary['warnings']})")
    if summary["fatal_findings"]:
        raise typer.Exit(code=3)


@app.command()
def generate(
    project: Optional[str] = typer.Option(None, "--project", "-p"),
    client: Optional[str] = typer.Option(None, "--client", help="Client / bidder entity"),
    vendor: Optional[str] = typer.Option(None, "--vendor", help="Your company name"),
    industry: Optional[str] = typer.Option(None, "--industry"),
    rto: Optional[str] = typer.Option(None, "--rto", help="Overall RTO target"),
    rpo: Optional[str] = typer.Option(None, "--rpo", help="Overall RPO target"),
    budget: Optional[str] = typer.Option(None, "--budget"),
    language: Optional[str] = typer.Option(None, "--language", "-L", help="en|zh"),
    profile: Optional[str] = typer.Option(None, "--profile"),
    output_dir: Optional[Path] = typer.Option(None, "--output-dir", "-o"),
    fresh: bool = typer.Option(False, "--fresh", help="Ignore persisted stage artifacts and start over"),
    interactive: bool = typer.Option(False, "--interactive", "-i"),
):
    """Generate a DR proposal document."""
    cfg = AppConfig.load({"language": language, "profile": profile})
    if interactive or not project:
        # Flags given on the command line pre-fill (skip) the matching prompts.
        provided = {k: v for k, v in {
            "project_name": project, "client_name": client, "vendor_name": vendor,
            "industry": industry, "overall_rto": rto, "overall_rpo": rpo,
            "budget": budget,
        }.items() if v}
        base = _interactive_inputs(project, provided)
        inputs = base.model_copy(update={"language": language or base.language,
                                         "profile": profile or base.profile})
    else:
        inputs = ProjectInput(
            project_name=project,
            client_name=client or "",
            vendor_name=vendor or "",
            industry=industry or "general",
            overall_rto=rto or "",
            overall_rpo=rpo or "",
            budget=budget or "",
            language=language or cfg.language,
            profile=profile or cfg.profile,
        )
    try:
        summary = _generate(inputs, cfg, output_dir, fresh=fresh)
    except typer.Exit:
        raise
    except Exception as exc:  # noqa: BLE001 — single loud failure point
        console.print(f"[red]Generation failed:[/red] "
                      f"{type(exc).__name__}: {redact_secrets(str(exc), cfg.llm.api_key)}")
        raise typer.Exit(code=1)
    console.print(f"[green]Done.[/green] Document: {summary['docx']} "
                  f"(review rounds: {summary['review_rounds']}, final score: {summary['score']}, "
                  f"fatal findings: {summary['fatal_findings']}, warnings: {summary['warnings']})")
    if summary["fatal_findings"]:
        raise typer.Exit(code=3)


@app.command()
def config(
    test_only: bool = typer.Option(False, "--test", help="Only test the saved configuration"),
):
    """Configure the LLM endpoint (base_url / api_key / model) interactively."""
    cfg = AppConfig.load()
    if test_only:
        ok, message = test_connection(cfg)
        console.print(("[green]✔ Connection OK:[/green] " if ok else "[red]✘ Connection failed:[/red] ")
                      + redact_secrets(message, cfg.llm.api_key))
        raise typer.Exit(code=0 if ok else 1)

    console.print(Panel.fit("ProDR_Writer configuration\nSaved to ~/.prodr/config.yaml"))
    cfg.llm.base_url = Prompt.ask("Base URL (OpenAI-compatible)",
                                  default=cfg.llm.base_url or "https://api.minimax.chat/v1")
    cfg.llm.api_key = Prompt.ask("API key", password=True, default=cfg.llm.api_key)
    cfg.llm.model = Prompt.ask("Model name", default=cfg.llm.model or "MiniMax-M2.5")
    while True:
        raw_temp = Prompt.ask("Temperature", default=str(cfg.llm.temperature))
        try:
            cfg.llm.temperature = float(raw_temp)
            break
        except ValueError:
            console.print("[red]Please enter a number, e.g. 0.3[/red]")
    cfg.language = Prompt.ask("Default document language (en/zh)", default=cfg.language)
    profiles = ", ".join(list_profiles())
    cfg.profile = Prompt.ask(f"Default compliance profile ({profiles})", default=cfg.profile)

    path = cfg.save()
    console.print(f"[green]Saved to[/green] {path}")
    ok, message = test_connection(cfg)
    console.print(("[green]✔ Connection OK:[/green] " if ok else "[yellow]⚠ Connection check failed:[/yellow] ")
                  + redact_secrets(message, cfg.llm.api_key))


@app.command()
def web(
    host: str = typer.Option("127.0.0.1", "--host", help="Bind address"),
    port: int = typer.Option(8000, "--port", help="Port"),
):
    """Start the Web UI (generate documents and manage config in the browser)."""
    import uvicorn

    from .web.server import create_app

    console.print(Panel.fit(
        f"[bold]ProDR_Writer Web UI[/bold]\nhttp://{host}:{port}\n\n"
        "Press Ctrl+C to stop.",
        border_style="blue"))
    uvicorn.run(create_app(), host=host, port=port, log_level="info")


@app.command()
def info():
    """Show current version and configuration summary."""
    table = Table(title=f"ProDR_Writer v{__version__}")
    table.add_column("Setting")
    table.add_column("Value")
    cfg = AppConfig.load()
    table.add_row("base_url", cfg.llm.base_url or "(not set)")
    table.add_row("api_key", ("***" + cfg.llm.api_key[-4:]) if len(cfg.llm.api_key) > 4 else "(not set)")
    table.add_row("model", cfg.llm.model or "(not set)")
    table.add_row("language", cfg.language)
    table.add_row("profile", cfg.profile)
    table.add_row("output_dir", cfg.output_dir)
    table.add_row("profiles available", ", ".join(list_profiles()))
    console.print(table)


if __name__ == "__main__":
    app()
