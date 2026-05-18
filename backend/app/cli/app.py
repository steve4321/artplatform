"""ArtPlatform CLI — main application with subcommand groups."""

from __future__ import annotations

import typer
from rich.console import Console

from app.cli.auth import login as auth_login
from app.cli.auth import whoami as auth_whoami
from app.cli.assets import app as assets_app
from app.cli.pipelines import app as pipelines_app
from app.cli.reviews import app as reviews_app
from app.cli.teams import app as teams_app

console = Console()
cli = typer.Typer(
    name="artplatform",
    help="ArtPlatform CLI — manage assets, pipelines, reviews and teams.",
    no_args_is_help=True,
    rich_markup_mode="rich",
)


@cli.command()
def login(
    email: str = typer.Option(..., "--email", "-e", prompt=True, help="Login email"),
    password: str = typer.Option(
        ..., "--password", "-p", prompt=True, hide_input=True, help="Login password"
    ),
    api_url: str = typer.Option("http://localhost:8000", "--api-url", help="API base URL"),
) -> None:
    auth_login(email=email, password=password, api_url=api_url)


@cli.command()
def whoami() -> None:
    auth_whoami()


cli.add_typer(assets_app, name="assets")
cli.add_typer(pipelines_app, name="pipeline")
cli.add_typer(reviews_app, name="reviews")
cli.add_typer(teams_app, name="teams")
