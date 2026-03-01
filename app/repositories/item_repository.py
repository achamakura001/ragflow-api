"""
Repository layer – all direct DB access lives here.
Swap the underlying engine/driver by changing Settings; nothing else changes.
"""

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.item import Item
from app.schemas.item import ItemCreate, ItemUpdate


class ItemRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, item_id: int) -> Item | None:
        result = await self._session.execute(
            select(Item).where(Item.id == item_id)
        )
        return result.scalar_one_or_none()

    async def list_items(
        self, *, skip: int = 0, limit: int = 20, active_only: bool = False
    ) -> tuple[int, list[Item]]:
        query = select(Item)
        if active_only:
            query = query.where(Item.is_active.is_(True))

        count_result = await self._session.execute(
            select(func.count()).select_from(query.subquery())
        )
        total: int = count_result.scalar_one()

        result = await self._session.execute(query.offset(skip).limit(limit))
        return total, list(result.scalars().all())

    async def create(self, payload: ItemCreate) -> Item:
        item = Item(**payload.model_dump())
        self._session.add(item)
        await self._session.flush()          # get auto-generated id
        await self._session.refresh(item)
        return item

    async def update(self, item: Item, payload: ItemUpdate) -> Item:
        for field, value in payload.model_dump(exclude_unset=True).items():
            setattr(item, field, value)
        await self._session.flush()
        await self._session.refresh(item)
        return item

    async def delete(self, item: Item) -> None:
        await self._session.delete(item)
        await self._session.flush()
