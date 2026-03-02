"""
Vector DB router.

Prefix  : /api/v1/vector-dbs
Auth    : all endpoints require a Bearer token
Admin   : write endpoints (create / update / delete) require tenant admin role
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.jwt import get_current_user
from app.database import get_db
from app.models.user import User
from app.models.vectordb import VectorDbEnv
from app.repositories.auth_repository import AuthRepository
from app.repositories.vectordb_repository import VectorDbRepository
from app.routers.tenant import require_admin
from app.schemas.vectordb import (
    ConnectionTestResult,
    CreateConnectionRequest,
    UpdateConnectionRequest,
    VectorDbConnectionList,
    VectorDbConnectionRead,
    VectorDbTypeList,
    VectorDbTypeRead,
)
from app.services.auth_service import AuthService
from app.services.vectordb_service import VectorDbService

router = APIRouter()


# ── Dependencies ──────────────────────────────────────────────────────────────

def get_vectordb_service(db: AsyncSession = Depends(get_db)) -> VectorDbService:
    return VectorDbService(VectorDbRepository(db))


def get_auth_service(db: AsyncSession = Depends(get_db)) -> AuthService:
    return AuthService(AuthRepository(db))


VectorDbServiceDep = Annotated[VectorDbService, Depends(get_vectordb_service)]
AuthServiceDep = Annotated[AuthService, Depends(get_auth_service)]
CurrentUserDep = Annotated[User, Depends(get_current_user)]


# ── Supported types catalogue (read-only, any authenticated user) ─────────────

@router.get(
    "/supported",
    response_model=VectorDbTypeList,
    summary="List all supported vector DB engines and their required properties",
)
async def list_supported(service: VectorDbServiceDep, _: CurrentUserDep):
    """
    Returns every vector DB engine the platform supports, together with the
    property schema that the UI should use to build dynamic configuration forms.

    No admin role required – any authenticated user can call this endpoint.
    """
    items = await service.list_supported_types()
    return VectorDbTypeList(items=items, total=len(items))


@router.get(
    "/supported/{type_id}",
    response_model=VectorDbTypeRead,
    summary="Get a specific supported vector DB type by ID",
)
async def get_supported_type(type_id: int, service: VectorDbServiceDep, _: CurrentUserDep):
    return await service.get_type(type_id)


# ── Connections (tenant-scoped) ───────────────────────────────────────────────

@router.get(
    "/connections",
    response_model=VectorDbConnectionList,
    summary="List all vector DB connections for the current tenant",
)
async def list_connections(
    service: VectorDbServiceDep,
    current_user: CurrentUserDep,
    environment: VectorDbEnv | None = Query(None, description="Filter by environment"),
    type_slug: str | None = Query(None, description="Filter by vector DB type slug"),
):
    """Admins and editors can list connections. Secret property values are masked."""
    items = await service.list_connections(current_user.tenant_id, environment, type_slug)
    return VectorDbConnectionList(items=items, total=len(items))


@router.get(
    "/connections/{connection_id}",
    response_model=VectorDbConnectionRead,
    summary="Get a specific connection",
)
async def get_connection(
    connection_id: str,
    service: VectorDbServiceDep,
    current_user: CurrentUserDep,
):
    return await service.get_connection(connection_id, current_user.tenant_id)


@router.post(
    "/connections",
    response_model=VectorDbConnectionRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new vector DB connection (admin only)",
)
async def create_connection(
    payload: CreateConnectionRequest,
    service: VectorDbServiceDep,
    auth_service: AuthServiceDep,
    current_user: CurrentUserDep,
):
    """
    Creates a named, environment-specific connection under the current tenant.

    - `type_slug` must match one of the slugs returned by `GET /supported`.
    - `properties` must include all fields marked `required` in the type's schema.
    - Caller must be a tenant **admin**.
    """
    await require_admin(current_user, auth_service)
    return await service.create_connection(payload, current_user)


@router.patch(
    "/connections/{connection_id}",
    response_model=VectorDbConnectionRead,
    summary="Update a connection (admin only)",
)
async def update_connection(
    connection_id: str,
    payload: UpdateConnectionRequest,
    service: VectorDbServiceDep,
    auth_service: AuthServiceDep,
    current_user: CurrentUserDep,
):
    await require_admin(current_user, auth_service)
    return await service.update_connection(connection_id, payload, current_user.tenant_id)


@router.delete(
    "/connections/{connection_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a connection (admin only)",
)
async def delete_connection(
    connection_id: str,
    service: VectorDbServiceDep,
    auth_service: AuthServiceDep,
    current_user: CurrentUserDep,
):
    await require_admin(current_user, auth_service)
    await service.delete_connection(connection_id, current_user.tenant_id)


@router.post(
    "/connections/{connection_id}/test",
    response_model=ConnectionTestResult,
    summary="Test an existing connection",
)
async def test_connection(
    connection_id: str,
    service: VectorDbServiceDep,
    current_user: CurrentUserDep,
):
    """
    Attempts to establish a live connection using the saved properties.
    Returns success/failure with optional latency and error detail.
    Any authenticated tenant member can trigger a test.
    """
    return await service.test_connection(connection_id, current_user.tenant_id)
