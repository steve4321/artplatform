import uuid

import pytest
import pytest_asyncio

from app.core.seed import DEFAULT_TEAM_ID


@pytest.mark.asyncio
async def test_list_teams(client, auth_headers):
    resp = await client.get("/api/v1/teams", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data
    assert "total" in data
    assert data["total"] >= 1

    names = [t["name"] for t in data["items"]]
    assert "Default Team" in names


@pytest.mark.asyncio
async def test_create_team(client, auth_headers):
    resp = await client.post(
        "/api/v1/teams",
        json={"name": "New Test Team"},
        headers=auth_headers,
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "New Test Team"
    assert data["member_count"] == 0


@pytest.mark.asyncio
async def test_create_team_no_auth(client):
    resp = await client.post(
        "/api/v1/teams",
        json={"name": "Should Fail"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_get_team_by_id(client, auth_headers):
    resp = await client.get(
        f"/api/v1/teams/{DEFAULT_TEAM_ID}",
        headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == str(DEFAULT_TEAM_ID)
    assert data["name"] == "Default Team"
    assert data["member_count"] >= 1


@pytest.mark.asyncio
async def test_get_team_not_found(client, auth_headers):
    import uuid

    resp = await client.get(
        f"/api/v1/teams/{uuid.uuid4()}",
        headers=auth_headers,
    )
    assert resp.status_code == 404


@pytest_asyncio.fixture
async def artist_headers(client, auth_headers):
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
    assert resp.status_code == 201
    login = await client.post(
        "/api/v1/auth/login",
        json={"email": f"artist_{tag}@test.local", "password": "testpass123"},
    )
    token = login.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_create_team_non_admin(client, artist_headers):
    resp = await client.post(
        "/api/v1/teams",
        json={"name": "Rogue Team"},
        headers=artist_headers,
    )
    assert resp.status_code == 403
    assert "permission" in resp.json()["detail"].lower()
