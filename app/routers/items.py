"""
Items router.
Dependencies are injected – repository and service are swappable in tests.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.repositories.item_repository import ItemRepository
from app.schemas.item import ItemCreate, ItemList, ItemRead, ItemUpdate
from app.services.item_service import ItemService

router = APIRouter()


# ── Dependency helpers ────────────────────────────────────────────────────────

def get_item_service(db: AsyncSession = Depends(get_db)) -> ItemService:
    return ItemService(ItemRepository(db))


ServiceDep = Annotated[ItemService, Depends(get_item_service)]


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("", response_model=ItemList)
async def list_items(
    service: ServiceDep,
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    active_only: bool = Query(False),
) -> ItemList:
    return await service.list_items(skip=skip, limit=limit, active_only=active_only)


@router.post("", response_model=ItemRead, status_code=status.HTTP_201_CREATED)
async def create_item(payload: ItemCreate, service: ServiceDep) -> ItemRead:
    return await service.create_item(payload)


@router.get("/{item_id}", response_model=ItemRead)
async def get_item(item_id: int, service: ServiceDep) -> ItemRead:
    return await service.get_item(item_id)


@router.patch("/{item_id}", response_model=ItemRead)
async def update_item(
    item_id: int, payload: ItemUpdate, service: ServiceDep
) -> ItemRead:
    return await service.update_item(item_id, payload)


@router.delete("/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_item(item_id: int, service: ServiceDep) -> None:
    await service.delete_item(item_id)
