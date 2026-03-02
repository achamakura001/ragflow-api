"""Business logic for vector DB connections."""

from __future__ import annotations

from typing import Any

from fastapi import HTTPException, status

from app.connectors.factory import ConnectorFactory
from app.models.user import User
from app.models.vectordb import VectorDbConnection, VectorDbEnv, VectorDbType
from app.repositories.vectordb_repository import VectorDbRepository
from app.schemas.vectordb import (
    ConnectionTestResult,
    CreateConnectionRequest,
    UpdateConnectionRequest,
    VectorDbConnectionRead,
    VectorDbTypeRead,
)


_MASK = "***"


def _mask_secrets(
    properties: dict[str, Any],
    property_schema: list[dict],
) -> dict[str, Any]:
    """Return a copy of properties with secret field values replaced by '***'."""
    secret_fields = {p["name"] for p in property_schema if p.get("secret")}
    return {
        k: (_MASK if k in secret_fields and v else v)
        for k, v in properties.items()
    }


def _connection_to_read(conn: VectorDbConnection) -> VectorDbConnectionRead:
    """Convert ORM object to read schema, masking secrets."""
    schema: list[dict] = conn.db_type.property_schema if conn.db_type else []
    masked = _mask_secrets(conn.properties or {}, schema)
    return VectorDbConnectionRead(
        id=conn.id,
        tenant_id=conn.tenant_id,
        type_id=conn.type_id,
        type_slug=conn.db_type.slug if conn.db_type else "",
        type_display_name=conn.db_type.display_name if conn.db_type else "",
        name=conn.name,
        environment=conn.environment,
        properties=masked,
        created_by_user_id=conn.created_by_user_id,
        created_at=conn.created_at,
        updated_at=conn.updated_at,
    )


class VectorDbService:
    def __init__(self, repo: VectorDbRepository) -> None:
        self._repo = repo

    # ── Catalogue ─────────────────────────────────────────────────────────────

    async def list_supported_types(self) -> list[VectorDbTypeRead]:
        types = await self._repo.list_types()
        return [VectorDbTypeRead.model_validate(t) for t in types]

    async def get_type(self, type_id: int) -> VectorDbTypeRead:
        t = await self._repo.get_type_by_id(type_id)
        if not t:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Vector DB type not found")
        return VectorDbTypeRead.model_validate(t)

    # ── Connections ───────────────────────────────────────────────────────────

    async def list_connections(
        self,
        tenant_id: str,
        environment: VectorDbEnv | None = None,
        type_slug: str | None = None,
    ) -> list[VectorDbConnectionRead]:
        type_id: int | None = None
        if type_slug:
            db_type = await self._repo.get_type_by_slug(type_slug)
            if not db_type:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Unknown vector DB type '{type_slug}'",
                )
            type_id = db_type.id

        conns = await self._repo.list_connections(tenant_id, environment, type_id)
        return [_connection_to_read(c) for c in conns]

    async def get_connection(self, connection_id: str, tenant_id: str) -> VectorDbConnectionRead:
        conn = await self._repo.get_connection(connection_id, tenant_id)
        if not conn:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Connection not found")
        return _connection_to_read(conn)

    async def create_connection(
        self,
        payload: CreateConnectionRequest,
        current_user: User,
    ) -> VectorDbConnectionRead:
        db_type = await self._repo.get_type_by_slug(payload.type_slug)
        if not db_type:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported vector DB type '{payload.type_slug}'. "
                       f"Call GET /api/v1/vector-dbs/supported to see available types.",
            )

        self._validate_properties(payload.properties, db_type)

        conn = await self._repo.create_connection(
            tenant_id=current_user.tenant_id,
            created_by_user_id=current_user.id,
            type_id=db_type.id,
            name=payload.name,
            environment=payload.environment,
            properties=payload.properties,
        )
        return _connection_to_read(conn)

    async def update_connection(
        self,
        connection_id: str,
        payload: UpdateConnectionRequest,
        tenant_id: str,
    ) -> VectorDbConnectionRead:
        conn = await self._repo.get_connection(connection_id, tenant_id)
        if not conn:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Connection not found")

        if payload.properties is not None:
            self._validate_properties(payload.properties, conn.db_type)

        conn = await self._repo.update_connection(
            conn,
            name=payload.name,
            environment=payload.environment,
            properties=payload.properties,
        )
        return _connection_to_read(conn)

    async def delete_connection(self, connection_id: str, tenant_id: str) -> None:
        conn = await self._repo.get_connection(connection_id, tenant_id)
        if not conn:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Connection not found")
        await self._repo.delete_connection(conn)

    async def test_connection(
        self, connection_id: str, tenant_id: str
    ) -> ConnectionTestResult:
        conn = await self._repo.get_connection(connection_id, tenant_id)
        if not conn:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Connection not found")

        try:
            connector = ConnectorFactory.get(conn.db_type.slug, conn.properties or {})
        except ValueError as exc:
            return ConnectionTestResult(success=False, message=str(exc))

        # Run sync connector in a thread to avoid blocking the event loop
        import asyncio
        loop = asyncio.get_event_loop()
        result: ConnectionTestResult = await loop.run_in_executor(
            None, connector.test_connection
        )
        return result

    # ── Internal ──────────────────────────────────────────────────────────────

    @staticmethod
    def _validate_properties(
        provided: dict[str, Any], db_type: VectorDbType
    ) -> None:
        """Raise 422 if any required property is missing."""
        schema: list[dict] = db_type.property_schema or []
        missing = [
            p["name"]
            for p in schema
            if p.get("required") and (
                p["name"] not in provided or provided[p["name"]] is None
            )
        ]
        if missing:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=f"Missing required properties for {db_type.display_name}: {missing}",
            )
