"""Entry point for ``python -m app.cli``."""

from app.cli.app import cli


def main() -> None:
    cli()


if __name__ == "__main__":
    main()
