import io
import uuid

import pytest
import pytest_asyncio


def _make_asset_payload(name="Test Asset"):
    return {
        "name": name,
        "description": "A test asset",
        "asset_type": "model_3d",
        "source": "manual_upload",
        "tags": ["test"],
        "metadata": {"foo": "bar"},
    }


@pytest.mark.asyncio
async def test_create_asset(client, auth_headers):
    resp = await client.post(
        "/api/v1/assets",
        json=_make_asset_payload("Create Test"),
        headers=auth_headers,
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "Create Test"
    assert data["state"] == "draft"
    assert data["asset_type"] == "model_3d"


@pytest.mark.asyncio
async def test_create_asset_no_auth(client):
    resp = await client.post(
        "/api/v1/assets",
        json=_make_asset_payload(),
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_list_assets(client, auth_headers):
    resp = await client.get("/api/v1/assets", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data
    assert "total" in data
    assert "page" in data
    assert data["page"] == 1


@pytest.mark.asyncio
async def test_get_asset_by_id(client, auth_headers):
    create = await client.post(
        "/api/v1/assets",
        json=_make_asset_payload("Get By ID"),
        headers=auth_headers,
    )
    assert create.status_code == 201
    asset_id = create.json()["id"]

    resp = await client.get(f"/api/v1/assets/{asset_id}", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == asset_id
    assert data["name"] == "Get By ID"
    assert isinstance(data["versions"], list)


@pytest.mark.asyncio
async def test_get_asset_not_found(client, auth_headers):
    fake_id = str(uuid.uuid4())
    resp = await client.get(f"/api/v1/assets/{fake_id}", headers=auth_headers)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_update_asset_name(client, auth_headers):
    create = await client.post(
        "/api/v1/assets",
        json=_make_asset_payload("Original Name"),
        headers=auth_headers,
    )
    asset_id = create.json()["id"]

    resp = await client.patch(
        f"/api/v1/assets/{asset_id}",
        json={"name": "Updated Name"},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["name"] == "Updated Name"


@pytest.mark.asyncio
async def test_upload_file_version(client, auth_headers):
    create = await client.post(
        "/api/v1/assets",
        json=_make_asset_payload("Upload Version"),
        headers=auth_headers,
    )
    asset_id = create.json()["id"]

    file_content = b"fake glb binary data for testing"
    resp = await client.post(
        f"/api/v1/assets/{asset_id}/versions",
        files={"file": ("model.glb", io.BytesIO(file_content), "model/gltf-binary")},
        headers=auth_headers,
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["version"] == 2
    assert data["file_format"] == "glb"
    assert data["file_size_bytes"] == len(file_content)
    assert data["checksum_sha256"] is not None


@pytest.mark.asyncio
async def test_download_version_url(client, auth_headers):
    create = await client.post(
        "/api/v1/assets",
        json=_make_asset_payload("Download Test"),
        headers=auth_headers,
    )
    asset_id = create.json()["id"]

    file_content = b"test binary data"
    upload = await client.post(
        f"/api/v1/assets/{asset_id}/versions",
        files={"file": ("data.bin", io.BytesIO(file_content), "application/octet-stream")},
        headers=auth_headers,
    )
    version = upload.json()["version"]

    resp = await client.get(
        f"/api/v1/assets/{asset_id}/versions/{version}/download",
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert "url" in resp.json()


@pytest.mark.asyncio
async def test_state_transition_draft_to_review(client, auth_headers):
    create = await client.post(
        "/api/v1/assets",
        json=_make_asset_payload("State Transition"),
        headers=auth_headers,
    )
    asset_id = create.json()["id"]

    resp = await client.patch(
        f"/api/v1/assets/{asset_id}/state",
        json={"state": "review"},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["state"] == "review"


@pytest.mark.asyncio
async def test_invalid_state_transition(client, auth_headers):
    create = await client.post(
        "/api/v1/assets",
        json=_make_asset_payload("Bad Transition"),
        headers=auth_headers,
    )
    asset_id = create.json()["id"]

    resp = await client.patch(
        f"/api/v1/assets/{asset_id}/state",
        json={"state": "published"},
        headers=auth_headers,
    )
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_deprecate_asset_admin_only(client, auth_headers):
    create = await client.post(
        "/api/v1/assets",
        json=_make_asset_payload("Deprecate Me"),
        headers=auth_headers,
    )
    asset_id = create.json()["id"]

    resp = await client.delete(
        f"/api/v1/assets/{asset_id}",
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["deleted"] == asset_id


@pytest_asyncio.fixture
async def artist_headers(client, auth_headers):
    """Create an artist user on the default team and return auth headers."""
    tag = uuid.uuid4().hex[:8]
    resp = await client.post(
        "/api/v1/auth/register",
        json={
            "email": f"artist_{tag}@test.local",
            "password": "testpass123",
            "display_name": "Test Artist",
            "role": "artist",
        },
        headers=auth_headers,
    )
    assert resp.status_code == 201, f"Register failed: {resp.text}"

    login = await client.post(
        "/api/v1/auth/login",
        json={"email": f"artist_{tag}@test.local", "password": "testpass123"},
    )
    assert login.status_code == 200
    token = login.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_update_asset_by_non_owner(client, auth_headers, artist_headers):
    """Non-owner (artist) should get 403 when patching someone else's asset."""
    create = await client.post(
        "/api/v1/assets",
        json=_make_asset_payload("Owner's Asset"),
        headers=auth_headers,
    )
    assert create.status_code == 201
    asset_id = create.json()["id"]

    resp = await client.patch(
        f"/api/v1/assets/{asset_id}",
        json={"name": "Hacked Name"},
        headers=artist_headers,
    )
    assert resp.status_code == 403
    assert "permission" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_list_assets_team_isolation(client, auth_headers):
    """Non-admin users only see assets from their own team."""
    # Create an asset as admin (on default team)
    create = await client.post(
        "/api/v1/assets",
        json=_make_asset_payload("Admin Team Asset"),
        headers=auth_headers,
    )
    assert create.status_code == 201

    # Create a second team
    team_resp = await client.post(
        "/api/v1/teams",
        json={"name": "Isolation Team"},
        headers=auth_headers,
    )
    assert team_resp.status_code == 201
    other_team_id = team_resp.json()["id"]

    # Register an artist in the second team
    tag = uuid.uuid4().hex[:8]
    reg = await client.post(
        "/api/v1/auth/register",
        json={
            "email": f"iso_artist_{tag}@test.local",
            "password": "testpass123",
            "display_name": "Isolation Artist",
            "role": "artist",
            "team_id": other_team_id,
        },
        headers=auth_headers,
    )
    assert reg.status_code == 201

    # Login as the second-team artist
    login = await client.post(
        "/api/v1/auth/login",
        json={"email": f"iso_artist_{tag}@test.local", "password": "testpass123"},
    )
    assert login.status_code == 200
    other_token = {"Authorization": f"Bearer {login.json()['access_token']}"}

    # The asset created by admin has team_id = admin's team = default team
    # The second-team artist should see zero assets
    resp = await client.get("/api/v1/assets", headers=other_token)
    assert resp.status_code == 200
    data = resp.json()
    # All assets in the response should belong to the other team
    for item in data["items"]:
        assert item["team_id"] == other_team_id, (
            f"Expected team_id={other_team_id}, got {item['team_id']}"
        )
