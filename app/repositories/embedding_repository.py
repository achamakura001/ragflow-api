"""Repository for embedding providers and tenant configurations."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.embedding import EmbeddingProvider, TenantEmbeddingConfig
from app.models.vectordb import VectorDbEnv


class EmbeddingRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    # ── Provider catalogue ────────────────────────────────────────────────────

    async def list_providers(self) -> list[EmbeddingProvider]:
        result = await self._session.execute(
            select(EmbeddingProvider).order_by(EmbeddingProvider.id)
        )
        return list(result.scalars().all())

    async def get_provider_by_id(self, provider_id: int) -> EmbeddingProvider | None:
        result = await self._session.execute(
            select(EmbeddingProvider).where(EmbeddingProvider.id == provider_id)
        )
        return result.scalar_one_or_none()

    async def get_provider_by_slug(self, slug: str) -> EmbeddingProvider | None:
        result = await self._session.execute(
            select(EmbeddingProvider).where(EmbeddingProvider.slug == slug.lower())
        )
        return result.scalar_one_or_none()

    # ── Tenant configs ────────────────────────────────────────────────────────

    async def list_configs(
        self,
        tenant_id: str,
        environment: VectorDbEnv | None = None,
        provider_id: int | None = None,
    ) -> list[TenantEmbeddingConfig]:
        stmt = (
            select(TenantEmbeddingConfig)
            .where(TenantEmbeddingConfig.tenant_id == tenant_id)
            .options(selectinload(TenantEmbeddingConfig.provider))
            .order_by(TenantEmbeddingConfig.created_at.desc())
        )
        if environment is not None:
            stmt = stmt.where(TenantEmbeddingConfig.environment == environment)
        if provider_id is not None:
            stmt = stmt.where(TenantEmbeddingConfig.provider_id == provider_id)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def get_config(
        self, config_id: str, tenant_id: str
    ) -> TenantEmbeddingConfig | None:
        result = await self._session.execute(
            select(TenantEmbeddingConfig)
            .where(
                TenantEmbeddingConfig.id == config_id,
                TenantEmbeddingConfig.tenant_id == tenant_id,
            )
            .options(selectinload(TenantEmbeddingConfig.provider))
        )
        return result.scalar_one_or_none()

    async def create_config(
        self,
        tenant_id: str,
        created_by_user_id: int | None,
        provider_id: int,
        name: str,
        environment: VectorDbEnv,
        properties: dict,
    ) -> TenantEmbeddingConfig:
        cfg = TenantEmbeddingConfig(
            tenant_id=tenant_id,
            created_by_user_id=created_by_user_id,
            provider_id=provider_id,
            name=name,
            environment=environment,
            properties=properties,
        )
        self._session.add(cfg)
        await self._session.flush()
        # Re-fetch with provider eagerly loaded so server-default columns
        # (created_at/updated_at) are populated without implicit lazy I/O.
        result = await self._session.execute(
            select(TenantEmbeddingConfig)
            .where(TenantEmbeddingConfig.id == cfg.id)
            .options(selectinload(TenantEmbeddingConfig.provider))
        )
        return result.scalar_one()

    async def update_config(
        self,
        cfg: TenantEmbeddingConfig,
        name: str | None = None,
        environment: VectorDbEnv | None = None,
        properties: dict | None = None,
    ) -> TenantEmbeddingConfig:
        if name is not None:
            cfg.name = name
        if environment is not None:
            cfg.environment = environment
        if properties is not None:
            cfg.properties = properties
        await self._session.flush()
        # Re-fetch so server-updated columns (updated_at) are populated
        # without triggering implicit lazy I/O (MissingGreenlet).
        result = await self._session.execute(
            select(TenantEmbeddingConfig)
            .where(TenantEmbeddingConfig.id == cfg.id)
            .options(selectinload(TenantEmbeddingConfig.provider))
        )
        return result.scalar_one()

    async def delete_config(self, cfg: TenantEmbeddingConfig) -> None:
        await self._session.delete(cfg)
        await self._session.flush()
