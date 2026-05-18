"""Asset CRUD commands: list, get, create, upload, download, export."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from app.cli.client import get_client, handle_error

console = Console()
app = typer.Typer(help="Manage assets.")


@app.command("list")
def list_assets(
    page: int = typer.Option(1, "--page", "-p", help="Page number"),
    page_size: int = typer.Option(20, "--page-size", "-n", help="Items per page"),
    state: Optional[str] = typer.Option(None, "--state", "-s", help="Filter by state"),
    asset_type: Optional[str] = typer.Option(None, "--type", "-t", help="Filter by asset type"),
    search: Optional[str] = typer.Option(None, "--search", help="Search by name"),
    output_json: bool = typer.Option(False, "--output", "-o", help="Output as JSON"),
) -> None:
    params: dict = {"page": page, "page_size": page_size}
    if state:
        params["state"] = state
    if asset_type:
        params["asset_type"] = asset_type
    if search:
        params["search"] = search

    with get_client() as client:
        resp = client.get("/assets", params=params)
        handle_error(resp)
        data = resp.json()

    if output_json:
        import json
        console.print_json(json.dumps(data))
        return

    table = Table(title="Assets", show_lines=True)
    table.add_column("ID", style="dim", max_width=36)
    table.add_column("Name", style="bold")
    table.add_column("Type", style="cyan")
    table.add_column("State", style="magenta")
    table.add_column("Version", justify="right")
    table.add_column("Created", style="dim")

    for item in data.get("items", []):
        state_val = item.get("state", "")
        state_style = _state_style(state_val)
        table.add_row(
            str(item.get("id", "")),
            item.get("name", ""),
            item.get("asset_type", ""),
            f"[{state_style}]{state_val}[/{state_style}]",
            str(item.get("current_version", 0)),
            item.get("created_at", "")[:19],
        )

    console.print(table)
    console.print(
        f"[dim]Page {data.get('page', '?')} of ~{max(1, -(-data.get('total', 0) // data.get('page_size', 20)))} "
        f"({data.get('total', 0)} total)[/dim]"
    )


@app.command("get")
def get_asset(
    asset_id: str = typer.Argument(..., help="Asset UUID"),
) -> None:
    with get_client() as client:
        resp = client.get(f"/assets/{asset_id}")
        handle_error(resp)
        data = resp.json()

    lines = [
        f"[bold]ID:[/bold]           {data.get('id')}",
        f"[bold]Name:[/bold]         {data.get('name')}",
        f"[bold]Type:[/bold]         {data.get('asset_type')}",
        f"[bold]Source:[/bold]       {data.get('source')}",
        f"[bold]State:[/bold]        {data.get('state')}",
        f"[bold]Version:[/bold]      {data.get('current_version')}",
        f"[bold]Description:[/bold]  {data.get('description', '')}",
        f"[bold]Tags:[/bold]         {', '.join(data.get('tags', [])) or '-'}",
        f"[bold]Created:[/bold]      {data.get('created_at', '')[:19]}",
        f"[bold]Updated:[/bold]      {data.get('updated_at', '')[:19]}",
    ]

    if data.get("versions"):
        lines.append("\n[bold]Versions:[/bold]")
        for v in data["versions"]:
            lines.append(
                f"  v{v['version']}  {v['file_format']}  "
                f"{_fmt_size(v.get('file_size_bytes'))}  {v.get('source_type', '')}  "
                f"{v.get('created_at', '')[:19]}"
            )

    console.print(Panel("\n".join(lines), title=data.get("name", "Asset"), border_style="cyan"))


@app.command("create")
def create_asset(
    name: str = typer.Option(..., "--name", "-n", help="Asset name"),
    asset_type: str = typer.Option("model_3d", "--type", "-t", help="Asset type"),
    source: str = typer.Option("manual_upload", "--source", "-s", help="Source type"),
    description: str = typer.Option("", "--description", "-d", help="Description"),
    tags: Optional[str] = typer.Option(None, "--tags", help="Comma-separated tags"),
) -> None:
    payload: dict = {
        "name": name,
        "asset_type": asset_type,
        "source": source,
        "description": description,
    }
    if tags:
        payload["tags"] = [t.strip() for t in tags.split(",") if t.strip()]

    with get_client() as client:
        resp = client.post("/assets", json=payload)
        handle_error(resp)
        data = resp.json()

    console.print(f"[green]Created asset[/green] {data['id']}")
    console.print(f"  Name:  {data['name']}")
    console.print(f"  State: {data['state']}")


@app.command("upload")
def upload_version(
    asset_id: str = typer.Argument(..., help="Asset UUID"),
    file: Path = typer.Argument(..., help="File to upload", exists=True),
) -> None:
    with get_client() as client:
        with open(file, "rb") as f:
            resp = client.post(
                f"/assets/{asset_id}/versions",
                files={"file": (file.name, f)},
                data={"source_type": "manual_upload"},
            )
        handle_error(resp)
        data = resp.json()

    console.print(f"[green]Uploaded version {data.get('version')}[/green]")
    console.print(f"  Format:    {data.get('file_format')}")
    console.print(f"  Size:      {_fmt_size(data.get('file_size_bytes'))}")
    console.print(f"  Checksum:  {data.get('checksum_sha256', '')[:16]}...")


@app.command("download")
def download_version(
    asset_id: str = typer.Argument(..., help="Asset UUID"),
    version: int = typer.Argument(..., help="Version number"),
    output: Optional[Path] = typer.Option(None, "--output", "-o", help="Output file path"),
) -> None:
    with get_client() as client:
        resp = client.get(f"/assets/{asset_id}/versions/{version}/download")
        handle_error(resp)
        url_data = resp.json()

    download_url = url_data["url"]
    if output is None:
        output = Path(f"{asset_id}_v{version}")

    import httpx as _httpx
    with _httpx.stream("GET", download_url, follow_redirects=True) as dl:
        dl.raise_for_status()
        total = int(dl.headers.get("content-length", 0))
        written = 0
        with open(output, "wb") as f:
            for chunk in dl.iter_bytes(chunk_size=8192):
                f.write(chunk)
                written += len(chunk)

    console.print(f"[green]Downloaded[/green] {output} ({_fmt_size(written)})")


@app.command("export")
def export_asset(
    asset_id: str = typer.Argument(..., help="Asset UUID"),
    version: int = typer.Option(..., "--version", "-v", help="Asset version"),
    fmt: str = typer.Option("unity", "--format", "-f", help="Export format: unity, glb, fbx"),
    output: Optional[Path] = typer.Option(None, "--output", "-o", help="Output file path"),
) -> None:
    fmt_endpoint = {"unity": "unity", "glb": "glb", "fbx": "fbx"}
    ep = fmt_endpoint.get(fmt)
    if ep is None:
        console.print(f"[red]Unknown format:[/red] {fmt}. Use unity, glb, or fbx.")
        raise SystemExit(1)

    with get_client() as client:
        resp = client.get(f"/assets/{asset_id}/export/{ep}", params={"version": version})
        handle_error(resp)
        url_data = resp.json()

    download_url = url_data["url"]
    if output is None:
        ext = {"unity": "zip", "glb": "glb", "fbx": "fbx"}[fmt]
        output = Path(f"{asset_id}_v{version}.{ext}")

    import httpx as _httpx
    with _httpx.stream("GET", download_url, follow_redirects=True) as dl:
        dl.raise_for_status()
        written = 0
        with open(output, "wb") as f:
            for chunk in dl.iter_bytes(chunk_size=8192):
                f.write(chunk)
                written += len(chunk)

    console.print(f"[green]Exported ({fmt})[/green] {output} ({_fmt_size(written)})")


def _state_style(state: str) -> str:
    return {
        "draft": "dim",
        "processing": "yellow",
        "review": "cyan",
        "approved": "green",
        "rejected": "red",
        "published": "bold green",
        "deprecated": "dim strikethrough",
    }.get(state, "white")


def _fmt_size(size: int | None) -> str:
    if size is None:
        return "?"
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024:
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} TB"
