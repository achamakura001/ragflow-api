"""Repository for vector DB types and connections."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.vectordb import VectorDbConnection, VectorDbEnv, VectorDbType


class VectorDbRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    # ── Vector DB Types (catalogue) ───────────────────────────────────────────

    async def list_types(self) -> list[VectorDbType]:
        result = await self._session.execute(select(VectorDbType).order_by(VectorDbType.id))
        return list(result.scalars().all())

    async def get_type_by_id(self, type_id: int) -> VectorDbType | None:
        result = await self._session.execute(
            select(VectorDbType).where(VectorDbType.id == type_id)
        )
        return result.scalar_one_or_none()

    async def get_type_by_slug(self, slug: str) -> VectorDbType | None:
        result = await self._session.execute(
            select(VectorDbType).where(VectorDbType.slug == slug.lower())
        )
        return result.scalar_one_or_none()

    # ── Connections ───────────────────────────────────────────────────────────

    async def list_connections(
        self,
        tenant_id: str,
        environment: VectorDbEnv | None = None,
        type_id: int | None = None,
    ) -> list[VectorDbConnection]:
        stmt = (
            select(VectorDbConnection)
            .where(VectorDbConnection.tenant_id == tenant_id)
            .options(selectinload(VectorDbConnection.db_type))
            .order_by(VectorDbConnection.created_at.desc())
        )
        if environment:
            stmt = stmt.where(VectorDbConnection.environment == environment)
        if type_id:
            stmt = stmt.where(VectorDbConnection.type_id == type_id)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def get_connection(
        self, connection_id: str, tenant_id: str
    ) -> VectorDbConnection | None:
        result = await self._session.execute(
            select(VectorDbConnection)
            .where(
                VectorDbConnection.id == connection_id,
                VectorDbConnection.tenant_id == tenant_id,
            )
            .options(selectinload(VectorDbConnection.db_type))
        )
        return result.scalar_one_or_none()

    async def create_connection(
        self,
        tenant_id: str,
        created_by_user_id: int,
        type_id: int,
        name: str,
        environment: VectorDbEnv,
        properties: dict,
    ) -> VectorDbConnection:
        conn = VectorDbConnection(
            tenant_id=tenant_id,
            created_by_user_id=created_by_user_id,
            type_id=type_id,
            name=name,
            environment=environment,
            properties=properties,
        )
        self._session.add(conn)
        await self._session.flush()
        # Re-fetch so server-default columns (created_at/updated_at) are populated
        # and db_type is eagerly loaded — avoids async-incompatible lazy loading.
        result = await self._session.execute(
            select(VectorDbConnection)
            .where(VectorDbConnection.id == conn.id)
            .options(selectinload(VectorDbConnection.db_type))
        )
        return result.scalar_one()

    async def update_connection(
        self,
        conn: VectorDbConnection,
        name: str | None = None,
        environment: VectorDbEnv | None = None,
        properties: dict | None = None,
    ) -> VectorDbConnection:
        if name is not None:
            conn.name = name
        if environment is not None:
            conn.environment = environment
        if properties is not None:
            conn.properties = properties
        await self._session.flush()
        # Re-fetch so server-updated columns (updated_at) are populated
        # without triggering implicit lazy I/O (MissingGreenlet).
        result = await self._session.execute(
            select(VectorDbConnection)
            .where(VectorDbConnection.id == conn.id)
            .options(selectinload(VectorDbConnection.provider))
        )
        return result.scalar_one()

    async def delete_connection(self, conn: VectorDbConnection) -> None:
        await self._session.delete(conn)
        await self._session.flush()
