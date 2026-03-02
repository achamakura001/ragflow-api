"""
Embedding providers router.

Prefix  : /api/v1/embeddings
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
from app.repositories.embedding_repository import EmbeddingRepository
from app.routers.tenant import require_admin
from app.schemas.embedding import (
    ConfigTestResult,
    CreateEmbeddingConfigRequest,
    EmbeddingProviderList,
    EmbeddingProviderRead,
    FetchModelsResult,
    TenantEmbeddingConfigList,
    TenantEmbeddingConfigRead,
    UpdateEmbeddingConfigRequest,
)
from app.services.auth_service import AuthService
from app.services.embedding_service import EmbeddingService

router = APIRouter()


# ── Dependencies ──────────────────────────────────────────────────────────────

def get_embedding_service(db: AsyncSession = Depends(get_db)) -> EmbeddingService:
    return EmbeddingService(EmbeddingRepository(db))


def get_auth_service(db: AsyncSession = Depends(get_db)) -> AuthService:
    return AuthService(AuthRepository(db))


EmbeddingServiceDep = Annotated[EmbeddingService, Depends(get_embedding_service)]
AuthServiceDep = Annotated[AuthService, Depends(get_auth_service)]
CurrentUserDep = Annotated[User, Depends(get_current_user)]


# ── Provider catalogue (read-only, any authenticated user) ────────────────────

@router.get(
    "/providers",
    response_model=EmbeddingProviderList,
    summary="List all supported embedding providers and their configuration schemas",
)
async def list_providers(service: EmbeddingServiceDep, _: CurrentUserDep):
    """
    Returns all supported embedding providers together with the property schema
    the UI needs to build dynamic configuration forms.  No admin role required.
    """
    items = await service.list_providers()
    return EmbeddingProviderList(items=items, total=len(items))


@router.get(
    "/providers/{provider_id}",
    response_model=EmbeddingProviderRead,
    summary="Get a specific embedding provider by ID",
)
async def get_provider(
    provider_id: int, service: EmbeddingServiceDep, _: CurrentUserDep
):
    return await service.get_provider(provider_id)


# ── Tenant configurations (CRUD + test + fetch-models) ───────────────────────

@router.get(
    "/configs",
    response_model=TenantEmbeddingConfigList,
    summary="List all embedding configurations for the current tenant",
)
async def list_configs(
    service: EmbeddingServiceDep,
    current_user: CurrentUserDep,
    environment: VectorDbEnv | None = Query(None, description="Filter by environment"),
    provider_slug: str | None = Query(None, description="Filter by provider slug"),
):
    """Admins and editors can list configurations. Secret property values are masked."""
    items = await service.list_configs(current_user.tenant_id, environment, provider_slug)
    return TenantEmbeddingConfigList(items=items, total=len(items))


@router.get(
    "/configs/{config_id}",
    response_model=TenantEmbeddingConfigRead,
    summary="Get a specific embedding configuration",
)
async def get_config(
    config_id: str, service: EmbeddingServiceDep, current_user: CurrentUserDep
):
    return await service.get_config(config_id, current_user.tenant_id)


@router.post(
    "/configs",
    response_model=TenantEmbeddingConfigRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create an embedding provider configuration (admin only)",
)
async def create_config(
    payload: CreateEmbeddingConfigRequest,
    service: EmbeddingServiceDep,
    auth_service: AuthServiceDep,
    current_user: CurrentUserDep,
):
    """
    Creates a named, environment-specific embedding provider configuration under
    the current tenant.

    - ``provider_slug`` must match one of the slugs from ``GET /providers``.
    - ``properties`` must include all fields marked ``required`` in the schema.
    - Caller must be a tenant **admin**.
    """
    await require_admin(current_user, auth_service)
    return await service.create_config(payload, current_user)


@router.patch(
    "/configs/{config_id}",
    response_model=TenantEmbeddingConfigRead,
    summary="Update an embedding configuration (admin only)",
)
async def update_config(
    config_id: str,
    payload: UpdateEmbeddingConfigRequest,
    service: EmbeddingServiceDep,
    auth_service: AuthServiceDep,
    current_user: CurrentUserDep,
):
    await require_admin(current_user, auth_service)
    return await service.update_config(config_id, payload, current_user.tenant_id)


@router.delete(
    "/configs/{config_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete an embedding configuration (admin only)",
)
async def delete_config(
    config_id: str,
    service: EmbeddingServiceDep,
    auth_service: AuthServiceDep,
    current_user: CurrentUserDep,
):
    await require_admin(current_user, auth_service)
    await service.delete_config(config_id, current_user.tenant_id)


@router.post(
    "/configs/{config_id}/test",
    response_model=ConfigTestResult,
    summary="Test an embedding provider configuration",
)
async def test_config(
    config_id: str,
    service: EmbeddingServiceDep,
    current_user: CurrentUserDep,
):
    """
    Verifies that the stored credentials can authenticate with the provider.
    Any authenticated tenant member can call this.
    """
    return await service.test_config(config_id, current_user.tenant_id)


@router.post(
    "/configs/{config_id}/models",
    response_model=FetchModelsResult,
    summary="Fetch the list of embedding models from the provider",
)
async def fetch_models(
    config_id: str,
    service: EmbeddingServiceDep,
    current_user: CurrentUserDep,
):
    """
    Calls the provider's API using the stored configuration and returns all
    available embedding models. Any authenticated tenant member can call this.
    """
    return await service.fetch_models(config_id, current_user.tenant_id)
