"""Pipeline commands: run, status."""

from __future__ import annotations

from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from app.cli.client import get_client, handle_error

console = Console()
app = typer.Typer(help="Manage AI generation pipelines.")


@app.command("run")
def run_pipeline(
    prompt: str = typer.Option(..., "--prompt", "-p", help="Text prompt for generation"),
    asset_id: Optional[str] = typer.Option(None, "--asset-id", "-a", help="Attach to existing asset"),
    reference: Optional[str] = typer.Option(None, "--reference", "-r", help="Reference image storage key"),
) -> None:
    payload: dict = {"prompt": prompt}
    if asset_id:
        payload["asset_id"] = asset_id
    if reference:
        payload["reference_image_key"] = reference

    with get_client() as client:
        resp = client.post("/pipelines", json=payload)
        handle_error(resp)
        data = resp.json()

    console.print(f"[green]Pipeline created[/green] {data['id']}")
    console.print(f"  Asset:   {data.get('asset_id')}")
    console.print(f"  Status:  {data.get('status')}")
    console.print(f"  Stages:  {data.get('total_stages')}")
    _print_steps_table(data.get("steps", []))


@app.command("status")
def pipeline_status(
    pipeline_id: str = typer.Argument(..., help="Pipeline run UUID"),
) -> None:
    with get_client() as client:
        resp = client.get(f"/pipelines/{pipeline_id}")
        handle_error(resp)
        data = resp.json()

    lines = [
        f"[bold]ID:[/bold]          {data.get('id')}",
        f"[bold]Asset:[/bold]      {data.get('asset_id')}",
        f"[bold]Status:[/bold]     {_status_style(data.get('status', ''))}",
        f"[bold]Prompt:[/bold]     {data.get('prompt', '')[:100]}",
        f"[bold]Progress:[/bold]   {data.get('completed_stages', 0)}/{data.get('total_stages', '?')}",
        f"[bold]Created:[/bold]    {data.get('created_at', '')[:19]}",
    ]

    console.print(Panel("\n".join(lines), title="Pipeline Run", border_style="cyan"))
    _print_steps_table(data.get("steps", []))


def _print_steps_table(steps: list[dict]) -> None:
    if not steps:
        return

    table = Table(title="Pipeline Steps", show_lines=True)
    table.add_column("#", justify="right", style="dim")
    table.add_column("Stage", style="bold")
    table.add_column("Processor", style="cyan")
    table.add_column("Status")
    table.add_column("Duration", justify="right")
    table.add_column("Error", style="red")

    for step in sorted(steps, key=lambda s: s.get("stage_order", 0)):
        status_val = step.get("status", "")
        table.add_row(
            str(step.get("stage_order", "")),
            step.get("stage", ""),
            step.get("processor_name", ""),
            _status_style(status_val),
            _fmt_duration(step.get("duration_ms")),
            (step.get("error_message") or "")[:60],
        )

    console.print(table)


def _status_style(status: str) -> str:
    colors = {
        "pending": "[dim]pending[/dim]",
        "running": "[yellow]running[/yellow]",
        "completed": "[green]completed[/green]",
        "failed": "[red]failed[/red]",
        "skipped": "[dim]skipped[/dim]",
        "partial": "[yellow]partial[/yellow]",
    }
    return colors.get(status, status)


def _fmt_duration(ms: int | None) -> str:
    if ms is None:
        return "-"
    if ms < 1000:
        return f"{ms}ms"
    return f"{ms / 1000:.1f}s"
