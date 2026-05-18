"""Entry point for running the ArtPlatform MCP server.

Usage:
    python -m app.mcp
"""

from app.mcp.server import mcp


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
