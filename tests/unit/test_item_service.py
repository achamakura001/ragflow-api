"""
Unit tests for ItemService.
The repository is mocked – no DB required.
"""

import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException

from app.models.item import Item
from app.schemas.item import ItemCreate, ItemUpdate
from app.services.item_service import ItemService

_NOW = datetime.datetime(2026, 1, 1, 12, 0, 0, tzinfo=datetime.timezone.utc)


def _make_item(**kwargs) -> Item:
    defaults = dict(
        id=1,
        title="Test Item",
        description="A description",
        is_active=True,
        created_at=_NOW,
        updated_at=_NOW,
    )
    defaults.update(kwargs)
    item = MagicMock(spec=Item)
    for k, v in defaults.items():
        setattr(item, k, v)
    return item


@pytest.fixture()
def mock_repo() -> AsyncMock:
    return AsyncMock()


@pytest.fixture()
def service(mock_repo: AsyncMock) -> ItemService:
    return ItemService(mock_repo)


# ── get_item ──────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_item_returns_item(service: ItemService, mock_repo: AsyncMock):
    mock_repo.get_by_id.return_value = _make_item()
    result = await service.get_item(1)
    assert result.id == 1
    assert result.title == "Test Item"
    mock_repo.get_by_id.assert_awaited_once_with(1)


@pytest.mark.asyncio
async def test_get_item_raises_404_when_not_found(service: ItemService, mock_repo: AsyncMock):
    mock_repo.get_by_id.return_value = None
    with pytest.raises(HTTPException) as exc_info:
        await service.get_item(999)
    assert exc_info.value.status_code == 404


# ── create_item ───────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_item(service: ItemService, mock_repo: AsyncMock):
    payload = ItemCreate(title="New Item", description="desc")
    mock_repo.create.return_value = _make_item(title="New Item", description="desc")
    result = await service.create_item(payload)
    assert result.title == "New Item"
    mock_repo.create.assert_awaited_once_with(payload)


# ── update_item ───────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_update_item(service: ItemService, mock_repo: AsyncMock):
    existing = _make_item()
    mock_repo.get_by_id.return_value = existing
    mock_repo.update.return_value = _make_item(title="Updated")
    payload = ItemUpdate(title="Updated")
    result = await service.update_item(1, payload)
    assert result.title == "Updated"


@pytest.mark.asyncio
async def test_update_item_not_found(service: ItemService, mock_repo: AsyncMock):
    mock_repo.get_by_id.return_value = None
    with pytest.raises(HTTPException) as exc_info:
        await service.update_item(999, ItemUpdate(title="X"))
    assert exc_info.value.status_code == 404


# ── delete_item ───────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_delete_item(service: ItemService, mock_repo: AsyncMock):
    mock_repo.get_by_id.return_value = _make_item()
    await service.delete_item(1)
    mock_repo.delete.assert_awaited_once()


@pytest.mark.asyncio
async def test_delete_item_not_found(service: ItemService, mock_repo: AsyncMock):
    mock_repo.get_by_id.return_value = None
    with pytest.raises(HTTPException) as exc_info:
        await service.delete_item(999)
    assert exc_info.value.status_code == 404
