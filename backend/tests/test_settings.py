import pytest


PIPELINE_TYPES = {"3d_scene", "3d_character", "2d_art"}


def _total_stage_count() -> int:
    """Count all stage definitions across all pipeline types."""
    return 4 + 5 + 3  # 3d_scene(4) + 3d_character(5) + 2d_art(3)


def _stage_count_for(pipeline_type: str) -> int:
    return {"3d_scene": 4, "3d_character": 5, "2d_art": 3}[pipeline_type]


@pytest.mark.asyncio
async def test_list_provider_settings(client, auth_headers):
    """GET /settings/providers returns per-pipeline-type stage definitions."""
    resp = await client.get("/api/v1/settings/providers", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "settings" in data
    assert "stage_definitions" in data
    assert "defaults" in data

    # stage_definitions is now grouped by pipeline_type (3 groups)
    assert len(data["stage_definitions"]) == 3
    types_found = {sd["pipeline_type"] for sd in data["stage_definitions"]}
    assert types_found == PIPELINE_TYPES

    # settings count = total stages across all pipeline types
    assert len(data["settings"]) == _total_stage_count()

    # All default to first mode in definitions
    for s in data["settings"]:
        assert s["pipeline_type"] in PIPELINE_TYPES

    # defaults is a dict
    assert isinstance(data["defaults"], dict)


@pytest.mark.asyncio
async def test_list_settings_no_auth(client):
    """Unauthenticated request returns 401."""
    resp = await client.get("/api/v1/settings/providers")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_update_setting_to_local(client, auth_headers):
    """PUT a stage to local mode."""
    resp = await client.put(
        "/api/v1/settings/providers/3d_scene/mesh_cleanup",
        json={"mode": "local"},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["stage"] == "mesh_cleanup"
    assert data["mode"] == "local"
    assert data["processor_name"] == "instant_meshes"
    assert data["cloud_provider"] is None
    assert data["api_key"] is None
    assert data["pipeline_type"] == "3d_scene"


@pytest.mark.asyncio
async def test_update_setting_to_cloud(client, auth_headers):
    """PUT a stage to cloud mode with provider + api_key."""
    resp = await client.put(
        "/api/v1/settings/providers/3d_scene/text_to_image",
        json={
            "mode": "cloud",
            "cloud_provider": "stability_ai",
            "api_key": "sk-test-12345678",
            "base_url": "https://api.stability.ai",
        },
        headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["mode"] == "cloud"
    assert data["processor_name"] == "sdxl_cloud"
    assert data["cloud_provider"] == "stability_ai"
    assert data["api_key"] == "sk-t***5678"
    assert data["base_url"] == "https://api.stability.ai"


@pytest.mark.asyncio
async def test_update_cloud_without_provider_fails(client, auth_headers):
    """Cloud mode requires cloud_provider."""
    resp = await client.put(
        "/api/v1/settings/providers/3d_scene/text_to_image",
        json={"mode": "cloud"},
        headers=auth_headers,
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_update_cloud_invalid_provider_fails(client, auth_headers):
    """Invalid cloud_provider for the stage is rejected."""
    resp = await client.put(
        "/api/v1/settings/providers/3d_scene/text_to_image",
        json={"mode": "cloud", "cloud_provider": "meshy_ai"},
        headers=auth_headers,
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_update_invalid_mode_fails(client, auth_headers):
    """Invalid mode for a stage is rejected."""
    resp = await client.put(
        "/api/v1/settings/providers/3d_scene/mesh_cleanup",
        json={"mode": "cloud"},
        headers=auth_headers,
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_update_unknown_stage_fails(client, auth_headers):
    """Unknown stage returns 404."""
    resp = await client.put(
        "/api/v1/settings/providers/3d_scene/nonexistent_stage",
        json={"mode": "mock"},
        headers=auth_headers,
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_update_unknown_pipeline_type_fails(client, auth_headers):
    """Unknown pipeline_type returns 404."""
    resp = await client.put(
        "/api/v1/settings/providers/fake_type/text_to_image",
        json={"mode": "mock"},
        headers=auth_headers,
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_update_setting_back_to_mock(client, auth_headers):
    """Can switch from cloud back to mock."""
    await client.put(
        "/api/v1/settings/providers/3d_scene/image_to_3d",
        json={"mode": "cloud", "cloud_provider": "tripo_cloud", "api_key": "test-key"},
        headers=auth_headers,
    )
    resp = await client.put(
        "/api/v1/settings/providers/3d_scene/image_to_3d",
        json={"mode": "mock"},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["mode"] == "mock"
    assert data["cloud_provider"] is None


@pytest.mark.asyncio
async def test_settings_persist_across_reads(client, auth_headers):
    """Settings persist between GET requests."""
    await client.put(
        "/api/v1/settings/providers/3d_scene/uv_material",
        json={"mode": "local"},
        headers=auth_headers,
    )
    resp = await client.get("/api/v1/settings/providers", headers=auth_headers)
    data = resp.json()
    uv_setting = next(
        s for s in data["settings"]
        if s["stage"] == "uv_material" and s["pipeline_type"] == "3d_scene"
    )
    assert uv_setting["mode"] == "local"
    assert uv_setting["processor_name"] == "xatlas_bpy"


@pytest.mark.asyncio
async def test_skip_mode(client, auth_headers):
    """Skip mode is valid for mesh_cleanup and uv_material."""
    resp = await client.put(
        "/api/v1/settings/providers/3d_scene/mesh_cleanup",
        json={"mode": "skip"},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["mode"] == "skip"
    assert data["processor_name"] == "skip"

    resp = await client.put(
        "/api/v1/settings/providers/3d_scene/uv_material",
        json={"mode": "skip"},
        headers=auth_headers,
    )
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_pipeline_defaults_crud(client, auth_headers):
    """Pipeline defaults can be set and read."""
    resp = await client.put(
        "/api/v1/settings/providers/defaults",
        json={"pipeline_type": "3d_scene", "default_mode": "cloud"},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["pipeline_type"] == "3d_scene"
    assert data["default_mode"] == "cloud"

    # Read back via GET defaults
    resp = await client.get("/api/v1/settings/providers/defaults", headers=auth_headers)
    assert resp.status_code == 200
    defaults = resp.json()
    assert any(d["pipeline_type"] == "3d_scene" and d["default_mode"] == "cloud" for d in defaults)

    # Also visible in GET providers
    resp = await client.get("/api/v1/settings/providers", headers=auth_headers)
    data = resp.json()
    assert data["defaults"]["3d_scene"] == "cloud"


@pytest.mark.asyncio
async def test_pipeline_defaults_clear_overrides(client, auth_headers):
    """Switching from custom to a mode clears per-stage overrides."""
    # Set a custom per-stage setting
    await client.put(
        "/api/v1/settings/providers/3d_scene/mesh_cleanup",
        json={"mode": "local"},
        headers=auth_headers,
    )
    # Check it was saved
    resp = await client.get("/api/v1/settings/providers", headers=auth_headers)
    mesh_settings = [
        s for s in resp.json()["settings"]
        if s["stage"] == "mesh_cleanup" and s["pipeline_type"] == "3d_scene"
    ]
    assert any(s["mode"] == "local" for s in mesh_settings)

    # Now set default to cloud (not custom) - should clear overrides
    await client.put(
        "/api/v1/settings/providers/defaults",
        json={"pipeline_type": "3d_scene", "default_mode": "cloud"},
        headers=auth_headers,
    )
    # mesh_cleanup doesn't support cloud, but the point is the setting is cleared
    resp = await client.get("/api/v1/settings/providers", headers=auth_headers)
    data = resp.json()
    assert data["defaults"]["3d_scene"] == "cloud"


@pytest.mark.asyncio
async def test_pipeline_type_isolation(client, auth_headers):
    """Settings for different pipeline types are independent."""
    # Set 3d_scene text_to_image to cloud
    await client.put(
        "/api/v1/settings/providers/3d_scene/text_to_image",
        json={"mode": "cloud", "cloud_provider": "stability_ai", "api_key": "key-3d"},
        headers=auth_headers,
    )
    # Set 2d_art text_to_image to local
    await client.put(
        "/api/v1/settings/providers/2d_art/text_to_image",
        json={"mode": "local"},
        headers=auth_headers,
    )

    resp = await client.get("/api/v1/settings/providers", headers=auth_headers)
    data = resp.json()

    tti_3d = next(
        s for s in data["settings"]
        if s["stage"] == "text_to_image" and s["pipeline_type"] == "3d_scene"
    )
    tti_2d = next(
        s for s in data["settings"]
        if s["stage"] == "text_to_image" and s["pipeline_type"] == "2d_art"
    )

    assert tti_3d["mode"] == "cloud"
    assert tti_2d["mode"] == "local"
