"""ArtPlatform MCP server definition.

Creates the FastMCP instance and imports all tool / prompt / resource
registrations from sibling modules.
"""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

mcp = FastMCP(
    "artplatform",
    instructions=(
        "ArtPlatform MCP server — enables AI assistants to create, manage, "
        "and export 3D art assets through the ArtPlatform pipeline. "
        "Use generate_3d_asset or run_pipeline to start generation, "
        "then track progress with get_pipeline_status."
    ),
)

# Import modules so their @mcp.tool / @mcp.prompt decorators execute at import time.
import app.mcp.tools as _tools  # noqa: F401, E402
import app.mcp.prompts as _prompts  # noqa: F401, E402
