"""
Integration tests for /api/v1/items endpoints.
Uses the in-memory SQLite DB wired in conftest.py – no real MySQL needed.
"""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_health_check(client: AsyncClient):
    resp = await client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"


@pytest.mark.asyncio
async def test_create_item(client: AsyncClient):
    payload = {"title": "Integration Item", "description": "test", "is_active": True}
    resp = await client.post("/api/v1/items", json=payload)
    assert resp.status_code == 201
    data = resp.json()
    assert data["title"] == "Integration Item"
    assert data["id"] is not None


@pytest.mark.asyncio
async def test_get_item(client: AsyncClient):
    # create first
    create_resp = await client.post(
        "/api/v1/items", json={"title": "Fetchable Item", "is_active": True}
    )
    item_id = create_resp.json()["id"]

    resp = await client.get(f"/api/v1/items/{item_id}")
    assert resp.status_code == 200
    assert resp.json()["id"] == item_id


@pytest.mark.asyncio
async def test_get_item_not_found(client: AsyncClient):
    resp = await client.get("/api/v1/items/99999")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_list_items(client: AsyncClient):
    for i in range(3):
        await client.post("/api/v1/items", json={"title": f"List Item {i}"})

    resp = await client.get("/api/v1/items?limit=50")
    assert resp.status_code == 200
    data = resp.json()
    assert "total" in data
    assert isinstance(data["items"], list)


@pytest.mark.asyncio
async def test_update_item(client: AsyncClient):
    create_resp = await client.post(
        "/api/v1/items", json={"title": "Before Update"}
    )
    item_id = create_resp.json()["id"]

    resp = await client.patch(
        f"/api/v1/items/{item_id}", json={"title": "After Update"}
    )
    assert resp.status_code == 200
    assert resp.json()["title"] == "After Update"


@pytest.mark.asyncio
async def test_delete_item(client: AsyncClient):
    create_resp = await client.post(
        "/api/v1/items", json={"title": "To Delete"}
    )
    item_id = create_resp.json()["id"]

    del_resp = await client.delete(f"/api/v1/items/{item_id}")
    assert del_resp.status_code == 204

    get_resp = await client.get(f"/api/v1/items/{item_id}")
    assert get_resp.status_code == 404
