"""Business logic for embedding provider configuration."""

from __future__ import annotations

import asyncio
from typing import Any

from fastapi import HTTPException, status

from app.models.embedding import EmbeddingProvider, TenantEmbeddingConfig
from app.models.user import User
from app.models.vectordb import VectorDbEnv
from app.providers.factory import EmbeddingProviderFactory
from app.repositories.embedding_repository import EmbeddingRepository
from app.schemas.embedding import (
    ConfigTestResult,
    CreateEmbeddingConfigRequest,
    EmbeddingProviderRead,
    FetchModelsResult,
    TenantEmbeddingConfigRead,
    UpdateEmbeddingConfigRequest,
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


def _config_to_read(cfg: TenantEmbeddingConfig) -> TenantEmbeddingConfigRead:
    schema: list[dict] = cfg.provider.property_schema if cfg.provider else []
    masked = _mask_secrets(cfg.properties or {}, schema)
    return TenantEmbeddingConfigRead(
        id=cfg.id,
        tenant_id=cfg.tenant_id,
        provider_id=cfg.provider_id,
        provider_slug=cfg.provider.slug if cfg.provider else "",
        provider_display_name=cfg.provider.display_name if cfg.provider else "",
        name=cfg.name,
        environment=cfg.environment,
        properties=masked,
        created_by_user_id=cfg.created_by_user_id,
        created_at=cfg.created_at,
        updated_at=cfg.updated_at,
    )


class EmbeddingService:
    def __init__(self, repo: EmbeddingRepository) -> None:
        self._repo = repo

    # ── Provider catalogue ────────────────────────────────────────────────────

    async def list_providers(self) -> list[EmbeddingProviderRead]:
        providers = await self._repo.list_providers()
        return [EmbeddingProviderRead.model_validate(p) for p in providers]

    async def get_provider(self, provider_id: int) -> EmbeddingProviderRead:
        p = await self._repo.get_provider_by_id(provider_id)
        if not p:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Embedding provider not found")
        return EmbeddingProviderRead.model_validate(p)

    # ── Tenant configs ────────────────────────────────────────────────────────

    async def list_configs(
        self,
        tenant_id: str,
        environment: VectorDbEnv | None = None,
        provider_slug: str | None = None,
    ) -> list[TenantEmbeddingConfigRead]:
        provider_id: int | None = None
        if provider_slug:
            p = await self._repo.get_provider_by_slug(provider_slug)
            if not p:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Unknown embedding provider '{provider_slug}'",
                )
            provider_id = p.id
        configs = await self._repo.list_configs(tenant_id, environment, provider_id)
        return [_config_to_read(c) for c in configs]

    async def get_config(self, config_id: str, tenant_id: str) -> TenantEmbeddingConfigRead:
        cfg = await self._repo.get_config(config_id, tenant_id)
        if not cfg:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Configuration not found")
        return _config_to_read(cfg)

    async def create_config(
        self, payload: CreateEmbeddingConfigRequest, current_user: User
    ) -> TenantEmbeddingConfigRead:
        provider = await self._repo.get_provider_by_slug(payload.provider_slug)
        if not provider:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported embedding provider '{payload.provider_slug}'. "
                       f"Call GET /api/v1/embeddings/providers to see available providers.",
            )
        self._validate_properties(payload.properties, provider)
        cfg = await self._repo.create_config(
            tenant_id=current_user.tenant_id,
            created_by_user_id=current_user.id,
            provider_id=provider.id,
            name=payload.name,
            environment=payload.environment,
            properties=payload.properties,
        )
        return _config_to_read(cfg)

    async def update_config(
        self, config_id: str, payload: UpdateEmbeddingConfigRequest, tenant_id: str
    ) -> TenantEmbeddingConfigRead:
        cfg = await self._repo.get_config(config_id, tenant_id)
        if not cfg:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Configuration not found")
        if payload.properties is not None:
            self._validate_properties(payload.properties, cfg.provider)
        cfg = await self._repo.update_config(
            cfg,
            name=payload.name,
            environment=payload.environment,
            properties=payload.properties,
        )
        return _config_to_read(cfg)

    async def delete_config(self, config_id: str, tenant_id: str) -> None:
        cfg = await self._repo.get_config(config_id, tenant_id)
        if not cfg:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Configuration not found")
        await self._repo.delete_config(cfg)

    async def test_config(self, config_id: str, tenant_id: str) -> ConfigTestResult:
        cfg = await self._repo.get_config(config_id, tenant_id)
        if not cfg:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Configuration not found")
        try:
            provider_impl = EmbeddingProviderFactory.get(cfg.provider.slug, cfg.properties or {})
        except ValueError as exc:
            return ConfigTestResult(success=False, message=str(exc))
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, provider_impl.test_connection)

    async def fetch_models(self, config_id: str, tenant_id: str) -> FetchModelsResult:
        cfg = await self._repo.get_config(config_id, tenant_id)
        if not cfg:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Configuration not found")
        try:
            provider_impl = EmbeddingProviderFactory.get(cfg.provider.slug, cfg.properties or {})
        except ValueError as exc:
            return FetchModelsResult(
                success=False,
                provider_slug=cfg.provider.slug if cfg.provider else "",
                message=str(exc),
            )
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, provider_impl.fetch_models)

    # ── Internal ──────────────────────────────────────────────────────────────

    @staticmethod
    def _validate_properties(
        provided: dict[str, Any], provider: EmbeddingProvider
    ) -> None:
        """Raise 422 if any required property is missing or None."""
        schema: list[dict] = provider.property_schema or []
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
                detail=f"Missing required properties for {provider.display_name}: {missing}",
            )
