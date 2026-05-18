"""Review commands: submit, list."""

from __future__ import annotations

from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from app.cli.client import get_client, handle_error

console = Console()
app = typer.Typer(help="Manage asset reviews.")


@app.command("submit")
def submit_review(
    asset_id: str = typer.Option(..., "--asset-id", "-a", help="Asset UUID"),
    version: int = typer.Option(..., "--version", "-v", help="Asset version"),
    decision: str = typer.Option(..., "--decision", "-d", help="approved, rejected, or changes_requested"),
    notes: Optional[str] = typer.Option(None, "--notes", "-n", help="Review notes"),
) -> None:
    payload: dict = {
        "asset_id": asset_id,
        "version": version,
        "decision": decision,
    }
    if notes:
        payload["notes"] = notes

    with get_client() as client:
        resp = client.post("/reviews", json=payload)
        handle_error(resp)
        data = resp.json()

    console.print(f"[green]Review submitted[/green] {data.get('id')}")
    console.print(f"  Asset:    {data.get('asset_id')}")
    console.print(f"  Version:  v{data.get('version')}")
    console.print(f"  Decision: {data.get('decision')}")


@app.command("list")
def list_reviews(
    asset_id: str = typer.Argument(..., help="Asset UUID"),
    page: int = typer.Option(1, "--page", "-p", help="Page number"),
    page_size: int = typer.Option(20, "--page-size", "-n", help="Items per page"),
    output_json: bool = typer.Option(False, "--output", "-o", help="Output as JSON"),
) -> None:
    with get_client() as client:
        resp = client.get(
            f"/assets/{asset_id}/reviews",
            params={"page": page, "page_size": page_size},
        )
        handle_error(resp)
        data = resp.json()

    if output_json:
        import json
        console.print_json(json.dumps(data))
        return

    table = Table(title="Reviews", show_lines=True)
    table.add_column("ID", style="dim", max_width=36)
    table.add_column("Version", justify="right")
    table.add_column("Decision")
    table.add_column("Reviewer", style="cyan")
    table.add_column("Notes", max_width=40)
    table.add_column("Reviewed At", style="dim")

    for item in data.get("items", []):
        decision_val = item.get("decision", "")
        decision_style = {
            "approved": "[green]approved[/green]",
            "rejected": "[red]rejected[/red]",
            "changes_requested": "[yellow]changes_requested[/yellow]",
        }.get(decision_val, decision_val)

        reviewer = item.get("reviewer", {})
        reviewer_name = reviewer.get("display_name", str(item.get("reviewer_id", ""))) if reviewer else str(item.get("reviewer_id", ""))

        table.add_row(
            str(item.get("id", "")),
            str(item.get("version", "")),
            decision_style,
            reviewer_name,
            (item.get("notes") or "-")[:40],
            item.get("reviewed_at", "")[:19],
        )

    console.print(table)
    console.print(f"[dim]{data.get('total', 0)} total reviews[/dim]")
