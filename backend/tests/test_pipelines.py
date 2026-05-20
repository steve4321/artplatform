import pytest


@pytest.mark.asyncio
async def test_create_pipeline(client, auth_headers):
    resp = await client.post(
        "/api/v1/pipelines",
        json={"prompt": "A low-poly knight character with sword"},
        headers=auth_headers,
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["prompt"] == "A low-poly knight character with sword"
    assert data["status"] == "pending"
    assert data["total_stages"] == 5
    assert len(data["steps"]) == 5

    stages = [s["stage"] for s in data["steps"]]
    assert stages == [
        "text_to_image",
        "image_to_3d",
        "cleanup",
        "uv_material",
        "rig",
    ]


@pytest.mark.asyncio
async def test_create_pipeline_no_auth(client):
    resp = await client.post(
        "/api/v1/pipelines",
        json={"prompt": "should fail"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_list_pipelines(client, auth_headers):
    resp = await client.get("/api/v1/pipelines", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data
    assert "total" in data
    assert "page" in data


@pytest.mark.asyncio
async def test_get_pipeline_by_id(client, auth_headers):
    create = await client.post(
        "/api/v1/pipelines",
        json={"prompt": "Get pipeline by ID test"},
        headers=auth_headers,
    )
    pipeline_id = create.json()["id"]

    resp = await client.get(f"/api/v1/pipelines/{pipeline_id}", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == pipeline_id
    assert len(data["steps"]) == 5


@pytest.mark.asyncio
async def test_get_pipeline_not_found(client, auth_headers):
    import uuid

    resp = await client.get(f"/api/v1/pipelines/{uuid.uuid4()}", headers=auth_headers)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_retry_pipeline_stage(client, auth_headers):
    create = await client.post(
        "/api/v1/pipelines",
        json={"prompt": "Retry test pipeline"},
        headers=auth_headers,
    )
    pipeline_id = create.json()["id"]

    resp = await client.post(
        f"/api/v1/pipelines/{pipeline_id}/retry/3",
        headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "running"
    for step in data["steps"]:
        if step["stage_order"] >= 3:
            assert step["status"] == "pending"
