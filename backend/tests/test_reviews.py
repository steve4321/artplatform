import io
import uuid

import pytest


async def _create_asset_with_version(client, auth_headers):
    create = await client.post(
        "/api/v1/assets",
        json={
            "name": "Review Test Asset",
            "description": "For review tests",
            "asset_type": "model_3d",
        },
        headers=auth_headers,
    )
    asset_id = create.json()["id"]

    await client.post(
        f"/api/v1/assets/{asset_id}/versions",
        files={"file": ("model.glb", io.BytesIO(b"fake"), "model/gltf-binary")},
        headers=auth_headers,
    )
    return asset_id


@pytest.mark.asyncio
async def test_submit_review(client, auth_headers):
    asset_id = await _create_asset_with_version(client, auth_headers)

    resp = await client.post(
        "/api/v1/reviews",
        json={
            "asset_id": asset_id,
            "version": 2,
            "decision": "approved",
            "notes": "Looks good",
        },
        headers=auth_headers,
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["decision"] == "approved"
    assert data["notes"] == "Looks good"
    assert data["version"] == 2


@pytest.mark.asyncio
async def test_list_reviews_for_asset(client, auth_headers):
    asset_id = await _create_asset_with_version(client, auth_headers)

    await client.post(
        "/api/v1/reviews",
        json={
            "asset_id": asset_id,
            "version": 2,
            "decision": "approved",
            "notes": "First review",
        },
        headers=auth_headers,
    )

    resp = await client.get(
        f"/api/v1/assets/{asset_id}/reviews",
        headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 1
    assert len(data["items"]) >= 1


@pytest.mark.asyncio
async def test_submit_review_invalid_version(client, auth_headers):
    asset_id = await _create_asset_with_version(client, auth_headers)

    resp = await client.post(
        "/api/v1/reviews",
        json={
            "asset_id": asset_id,
            "version": 999,
            "decision": "approved",
        },
        headers=auth_headers,
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_submit_review_asset_not_found(client, auth_headers):
    fake_id = str(uuid.uuid4())
    resp = await client.post(
        "/api/v1/reviews",
        json={
            "asset_id": fake_id,
            "version": 1,
            "decision": "approved",
        },
        headers=auth_headers,
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_list_reviews_asset_not_found(client, auth_headers):
    fake_id = str(uuid.uuid4())
    resp = await client.get(
        f"/api/v1/assets/{fake_id}/reviews",
        headers=auth_headers,
    )
    assert resp.status_code == 404
