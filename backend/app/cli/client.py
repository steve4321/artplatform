"""Shared httpx client factory with automatic auth header injection."""

from __future__ import annotations

import httpx
from rich.console import Console

from app.cli.auth import get_token

console = Console()


def get_client() -> httpx.Client:
    creds = get_token()
    if creds is None:
        console.print("[red]Not logged in.[/red] Run [bold]artplatform login[/bold] first.")
        raise SystemExit(1)

    api_url = creds["api_url"]
    token = creds["token"]
    return httpx.Client(
        base_url=f"{api_url}/api/v1",
        headers={"Authorization": f"Bearer {token}"},
        timeout=30,
    )


def handle_error(resp: httpx.Response) -> None:
    if resp.status_code >= 400:
        try:
            detail = resp.json().get("detail", resp.text)
        except Exception:
            detail = resp.text
        console.print(f"[red]Error {resp.status_code}:[/red] {detail}")
        raise SystemExit(1)
