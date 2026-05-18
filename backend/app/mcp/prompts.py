"""MCP prompt templates for the ArtPlatform."""

from __future__ import annotations

from app.mcp.server import mcp


@mcp.prompt()
def generate_asset_prompt(
    subject: str,
    style: str = "game-ready",
    details: str = "",
) -> str:
    """Generate an effective prompt for the art asset pipeline.

    Constructs a well-structured prompt optimized for the SDXL -> TripoSR
    pipeline, including style keywords, composition hints, and technical
    constraints.

    Args:
        subject: The main subject to create (e.g., "a medieval knight helmet")
        style: Visual style (e.g., "low-poly", "realistic", "cartoon")
        details: Additional details or constraints
    """
    return (
        f"Create a 3D art asset with these specifications:\n\n"
        f"Subject: {subject}\n"
        f"Style: {style}\n"
        f"Additional details: {details}\n\n"
        f"Technical requirements:\n"
        f"- PBR metallic-roughness workflow\n"
        f"- Clean topology suitable for real-time rendering\n"
        f"- UV-unwrapped with proper texture density\n"
        f"- Game-ready polygon count (target: under 10k triangles)\n\n"
        f'Prompt for generation pipeline:\n'
        f'"{subject}, {style} style, {details}, clean background, '
        f'studio lighting, front-facing view"'
    )
