"""MCP tool implementations for the ArtPlatform.

All nine tools exposed to AI assistants via the MCP protocol. Each tool
delegates to the ArtPlatform REST API through the client helpers.
"""

from __future__ import annotations

import json as _json
from typing import Any

from app.mcp.client import api_get, api_patch, api_post, api_post_file
from app.mcp.server import mcp


def _json_str(data: Any) -> str:
    """Normalize API response to a JSON string for MCP tool return."""
    if isinstance(data, str):
        return data
    return _json.dumps(data, indent=2, ensure_ascii=False)


@mcp.tool()
async def generate_3d_asset(
    prompt: str,
    style: str | None = None,
    reference_image_url: str | None = None,
    pipeline_type: str = "3d_character",
) -> str:
    """Generate a 3D art asset from a text prompt.

    Triggers the full AI pipeline: text-to-image -> 3D model -> cleanup ->
    UV/materials. Returns immediately with a pipeline_id for tracking progress.

    Args:
        prompt: Text description of the desired asset (e.g., "a low-poly fantasy sword")
        style: Optional style modifier (e.g., "low-poly", "realistic", "cartoon")
        reference_image_url: Optional URL to a reference image
        pipeline_type: Pipeline type — "3d_character" (default, includes rigging)
            or "3d_scene" (no rigging)

    Returns:
        JSON with pipeline_id and asset_id for tracking
    """
    body: dict[str, Any] = {"prompt": prompt}
    if style:
        body["style"] = style
    if reference_image_url:
        body["reference_image_url"] = reference_image_url
    body["pipeline_type"] = pipeline_type
    data = await api_post("/api/v1/pipelines", json=body)
    return _json_str(data)


@mcp.tool()
async def list_assets(
    state: str | None = None,
    asset_type: str | None = None,
    search: str | None = None,
    limit: int = 20,
) -> str:
    """List art assets in the platform.

    Args:
        state: Filter by state (draft, processing, review, approved, published, deprecated)
        asset_type: Filter by type (model_3d, texture_2d, material, animation_clip, etc.)
        search: Search assets by name
        limit: Max number of results (default 20, max 100)

    Returns:
        JSON array of assets with id, name, type, state, versions
    """
    params: dict[str, Any] = {"limit": min(limit, 100)}
    if state:
        params["state"] = state
    if asset_type:
        params["asset_type"] = asset_type
    if search:
        params["search"] = search
    data = await api_get("/api/v1/assets", params=params)
    return _json_str(data)


@mcp.tool()
async def get_asset(asset_id: str) -> str:
    """Get detailed information about a specific asset.

    Includes all versions, dependencies, and metadata.

    Args:
        asset_id: UUID of the asset

    Returns:
        Full asset detail as JSON
    """
    data = await api_get(f"/api/v1/assets/{asset_id}")
    return _json_str(data)


@mcp.tool()
async def update_asset(
    asset_id: str,
    name: str | None = None,
    tags: list[str] | None = None,
    state: str | None = None,
) -> str:
    """Update an asset's metadata or transition its state.

    Args:
        asset_id: UUID of the asset
        name: New name for the asset
        tags: New tag list
        state: Transition to a new state (must follow state machine rules)

    Returns:
        Updated asset as JSON
    """
    body: dict[str, Any] = {}
    if name is not None:
        body["name"] = name
    if tags is not None:
        body["tags"] = tags
    if state is not None:
        body["state"] = state
    data = await api_patch(f"/api/v1/assets/{asset_id}", json=body)
    return _json_str(data)


@mcp.tool()
async def upload_asset_version(
    asset_id: str,
    file_path: str,
) -> str:
    """Upload a file as a new version of an asset.

    Args:
        asset_id: UUID of the asset
        file_path: Local path to the file to upload

    Returns:
        New version details as JSON
    """
    data = await api_post_file(f"/api/v1/assets/{asset_id}/versions", file_path)
    return _json_str(data)


@mcp.tool()
async def export_asset(
    asset_id: str,
    format: str = "glb",  # noqa: A002
    version: int | None = None,
) -> str:
    """Export an asset in the specified format.

    Args:
        asset_id: UUID of the asset
        format: Export format (unity, glb, fbx)
        version: Specific version number (defaults to latest)

    Returns:
        Download URL for the exported file
    """
    params: dict[str, Any] = {"format": format}
    if version is not None:
        params["version"] = version
    data = await api_post(f"/api/v1/assets/{asset_id}/export", json=params)
    return _json_str(data)


@mcp.tool()
async def submit_review(
    asset_id: str,
    version: int,
    decision: str,
    notes: str | None = None,
) -> str:
    """Submit a review for an asset version.

    Args:
        asset_id: UUID of the asset
        version: Version number being reviewed
        decision: One of: approved, rejected, changes_requested
        notes: Optional review notes

    Returns:
        Review record as JSON
    """
    body: dict[str, Any] = {"version": version, "decision": decision}
    if notes:
        body["notes"] = notes
    data = await api_post(f"/api/v1/assets/{asset_id}/reviews", json=body)
    return _json_str(data)


@mcp.tool()
async def run_pipeline(
    prompt: str,
    reference_image_key: str | None = None,
) -> str:
    """Start a new AI generation pipeline.

    Args:
        prompt: Text description for generation
        reference_image_key: Optional reference image storage key

    Returns:
        Pipeline run details with all steps as JSON
    """
    body: dict[str, Any] = {"prompt": prompt}
    if reference_image_key:
        body["reference_image_key"] = reference_image_key
    data = await api_post("/api/v1/pipelines", json=body)
    return _json_str(data)


@mcp.tool()
async def get_pipeline_status(pipeline_id: str) -> str:
    """Check the status of a running pipeline.

    Shows all stages with their individual status, duration, and any errors.

    Args:
        pipeline_id: UUID of the pipeline run

    Returns:
        Pipeline status with step-by-step progress as JSON
    """
    data = await api_get(f"/api/v1/pipelines/{pipeline_id}")
    return _json_str(data)
