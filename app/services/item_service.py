"""
Service layer – business logic lives here.
Services receive repository instances (easy to mock in tests).
"""

from fastapi import HTTPException, status

from app.models.item import Item
from app.repositories.item_repository import ItemRepository
from app.schemas.item import ItemCreate, ItemList, ItemRead, ItemUpdate


class ItemService:
    def __init__(self, repo: ItemRepository) -> None:
        self._repo = repo

    async def get_item(self, item_id: int) -> ItemRead:
        item = await self._repo.get_by_id(item_id)
        if item is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Item {item_id} not found",
            )
        return ItemRead.model_validate(item)

    async def list_items(
        self, *, skip: int = 0, limit: int = 20, active_only: bool = False
    ) -> ItemList:
        total, items = await self._repo.list_items(
            skip=skip, limit=limit, active_only=active_only
        )
        return ItemList(
            total=total,
            items=[ItemRead.model_validate(i) for i in items],
        )

    async def create_item(self, payload: ItemCreate) -> ItemRead:
        item = await self._repo.create(payload)
        return ItemRead.model_validate(item)

    async def update_item(self, item_id: int, payload: ItemUpdate) -> ItemRead:
        item = await self._repo.get_by_id(item_id)
        if item is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Item {item_id} not found",
            )
        updated = await self._repo.update(item, payload)
        return ItemRead.model_validate(updated)

    async def delete_item(self, item_id: int) -> None:
        item = await self._repo.get_by_id(item_id)
        if item is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Item {item_id} not found",
            )
        await self._repo.delete(item)
