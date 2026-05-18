"""Authentication helpers: login, token persistence, retrieval."""

from __future__ import annotations

import json
from typing import Any

import httpx
from rich.console import Console
from rich.panel import Panel

from app.cli.config import API_PREFIX, API_URL, CREDENTIALS_FILE

console = Console()


def save_token(api_url: str, email: str, token: str) -> None:
    CREDENTIALS_FILE.parent.mkdir(parents=True, exist_ok=True)
    payload: dict[str, str] = {"api_url": api_url, "email": email, "token": token}
    CREDENTIALS_FILE.write_text(json.dumps(payload, indent=2))
    CREDENTIALS_FILE.chmod(0o600)


def get_token() -> dict[str, str] | None:
    if not CREDENTIALS_FILE.exists():
        return None
    try:
        data: dict[str, str] = json.loads(CREDENTIALS_FILE.read_text())
        return data
    except (json.JSONDecodeError, KeyError):
        return None


def login(email: str, password: str, api_url: str = API_URL) -> dict[str, Any]:
    resp = httpx.post(
        f"{api_url}{API_PREFIX}/auth/login",
        json={"email": email, "password": password},
        timeout=15,
    )
    if resp.status_code != 200:
        detail = resp.json().get("detail", resp.text)
        console.print(f"[red]Login failed:[/red] {detail}")
        raise SystemExit(1)
    body = resp.json()
    token = body["access_token"]
    save_token(api_url, email, token)
    console.print(f"[green]Logged in as[/green] {email}")
    return body


def whoami() -> None:
    creds = get_token()
    if creds is None:
        console.print("[red]Not logged in.[/red] Run [bold]artplatform login[/bold] first.")
        raise SystemExit(1)

    api_url = creds["api_url"]
    token = creds["token"]
    resp = httpx.get(
        f"{api_url}{API_PREFIX}/auth/me",
        headers={"Authorization": f"Bearer {token}"},
        timeout=15,
    )
    if resp.status_code != 200:
        detail = resp.json().get("detail", resp.text)
        console.print(f"[red]Failed:[/red] {detail}")
        raise SystemExit(1)

    user = resp.json()
    lines = [
        f"[bold]ID:[/bold]           {user.get('id', '-')}",
        f"[bold]Email:[/bold]        {user.get('email', '-')}",
        f"[bold]Display name:[/bold] {user.get('display_name', '-')}",
        f"[bold]Role:[/bold]         {user.get('role', '-')}",
        f"[bold]Active:[/bold]       {user.get('is_active', '-')}",
    ]
    console.print(Panel("\n".join(lines), title="Current User", border_style="green"))
