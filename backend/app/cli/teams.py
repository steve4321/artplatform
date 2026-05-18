"""Team commands: list, create."""

from __future__ import annotations

import typer
from rich.console import Console
from rich.table import Table

from app.cli.client import get_client, handle_error

console = Console()
app = typer.Typer(help="Manage teams.")


@app.command("list")
def list_teams(
    page: int = typer.Option(1, "--page", "-p", help="Page number"),
    page_size: int = typer.Option(20, "--page-size", "-n", help="Items per page"),
    output_json: bool = typer.Option(False, "--output", "-o", help="Output as JSON"),
) -> None:
    with get_client() as client:
        resp = client.get("/teams", params={"page": page, "page_size": page_size})
        handle_error(resp)
        data = resp.json()

    if output_json:
        import json
        console.print_json(json.dumps(data))
        return

    table = Table(title="Teams", show_lines=True)
    table.add_column("ID", style="dim", max_width=36)
    table.add_column("Name", style="bold")
    table.add_column("Members", justify="right")
    table.add_column("Created", style="dim")

    for item in data.get("items", []):
        table.add_row(
            str(item.get("id", "")),
            item.get("name", ""),
            str(item.get("member_count", 0)),
            item.get("created_at", "")[:19] if item.get("created_at") else "-",
        )

    console.print(table)
    console.print(f"[dim]{data.get('total', 0)} total teams[/dim]")


@app.command("create")
def create_team(
    name: str = typer.Option(..., "--name", "-n", help="Team name"),
) -> None:
    with get_client() as client:
        resp = client.post("/teams", json={"name": name})
        handle_error(resp)
        data = resp.json()

    console.print(f"[green]Created team[/green] {data.get('id')}")
    console.print(f"  Name:    {data.get('name')}")
    console.print(f"  Members: {data.get('member_count', 0)}")
