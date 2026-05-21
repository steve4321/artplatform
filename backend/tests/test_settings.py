import pytest


@pytest.mark.asyncio
async def test_list_provider_settings(client, auth_headers):
    """GET /settings/providers returns all 7 stages with defaults."""
    resp = await client.get("/api/v1/settings/providers", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "settings" in data
    assert "stage_definitions" in data
    assert len(data["stage_definitions"]) == 7
    assert len(data["settings"]) == 7
    # All default to mock mode
    for s in data["settings"]:
        assert s["mode"] == "mock"


@pytest.mark.asyncio
async def test_list_settings_no_auth(client):
    """Unauthenticated request returns 401."""
    resp = await client.get("/api/v1/settings/providers")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_update_setting_to_local(client, auth_headers):
    """PUT a stage to local mode."""
    resp = await client.put(
        "/api/v1/settings/providers/mesh_cleanup",
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


@pytest.mark.asyncio
async def test_update_setting_to_cloud(client, auth_headers):
    """PUT a stage to cloud mode with provider + api_key."""
    resp = await client.put(
        "/api/v1/settings/providers/text_to_image",
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
    # API key should be masked
    assert data["api_key"] == "sk-t***5678"
    assert data["base_url"] == "https://api.stability.ai"


@pytest.mark.asyncio
async def test_update_cloud_without_provider_fails(client, auth_headers):
    """Cloud mode requires cloud_provider."""
    resp = await client.put(
        "/api/v1/settings/providers/text_to_image",
        json={"mode": "cloud"},
        headers=auth_headers,
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_update_cloud_invalid_provider_fails(client, auth_headers):
    """Invalid cloud_provider for the stage is rejected."""
    resp = await client.put(
        "/api/v1/settings/providers/text_to_image",
        json={"mode": "cloud", "cloud_provider": "meshy_ai"},
        headers=auth_headers,
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_update_invalid_mode_fails(client, auth_headers):
    """Invalid mode for a stage that doesn't support it is rejected."""
    resp = await client.put(
        "/api/v1/settings/providers/mesh_cleanup",
        json={"mode": "cloud"},
        headers=auth_headers,
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_update_unknown_stage_fails(client, auth_headers):
    """Unknown stage returns 404."""
    resp = await client.put(
        "/api/v1/settings/providers/nonexistent_stage",
        json={"mode": "mock"},
        headers=auth_headers,
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_update_setting_back_to_mock(client, auth_headers):
    """Can switch back from cloud to mock."""
    # First set to cloud
    await client.put(
        "/api/v1/settings/providers/image_to_3d",
        json={"mode": "cloud", "cloud_provider": "tripo_cloud", "api_key": "test-key"},
        headers=auth_headers,
    )
    # Then switch back to mock
    resp = await client.put(
        "/api/v1/settings/providers/image_to_3d",
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
    # Set to local
    await client.put(
        "/api/v1/settings/providers/uv_material",
        json={"mode": "local"},
        headers=auth_headers,
    )
    # Read back
    resp = await client.get("/api/v1/settings/providers", headers=auth_headers)
    data = resp.json()
    uv_setting = next(s for s in data["settings"] if s["stage"] == "uv_material")
    assert uv_setting["mode"] == "local"
    assert uv_setting["processor_name"] == "xatlas_bpy"