"""Pydantic schemas for embedding providers and tenant configurations."""

from __future__ import annotations

import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.models.vectordb import VectorDbEnv


# ── Provider catalogue ────────────────────────────────────────────────────────

class PropertyDefinition(BaseModel):
    """Describes a single configurable field for an embedding provider."""

    name: str
    label: str
    type: str = Field(..., description="string | integer | boolean | password")
    required: bool
    secret: bool = False
    placeholder: str | None = None
    description: str | None = None
    default: Any = None


class EmbeddingProviderRead(BaseModel):
    """Public representation of a supported embedding provider."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    slug: str
    display_name: str
    description: str | None
    models_url: str
    property_schema: list[PropertyDefinition]


class EmbeddingProviderList(BaseModel):
    items: list[EmbeddingProviderRead]
    total: int


# ── Tenant config schemas ─────────────────────────────────────────────────────

class CreateEmbeddingConfigRequest(BaseModel):
    """Body for POST /embeddings/configs."""

    provider_slug: str = Field(
        ..., description="Slug of the embedding provider, e.g. 'openai'"
    )
    name: str = Field(..., min_length=1, max_length=128)
    environment: VectorDbEnv = VectorDbEnv.DEV
    properties: dict[str, Any] = Field(
        ..., description="Credential / config key-value pairs"
    )


class UpdateEmbeddingConfigRequest(BaseModel):
    """Body for PATCH /embeddings/configs/{id}."""

    name: str | None = Field(None, min_length=1, max_length=128)
    environment: VectorDbEnv | None = None
    properties: dict[str, Any] | None = None


class TenantEmbeddingConfigRead(BaseModel):
    """Config record returned to the client. Secret values are masked."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    tenant_id: str
    provider_id: int
    provider_slug: str
    provider_display_name: str
    name: str
    environment: VectorDbEnv
    properties: dict[str, Any]   # secrets replaced with "***"
    created_by_user_id: int | None
    created_at: datetime.datetime
    updated_at: datetime.datetime


class TenantEmbeddingConfigList(BaseModel):
    items: list[TenantEmbeddingConfigRead]
    total: int


# ── Models-fetch result ───────────────────────────────────────────────────────

class EmbeddingModel(BaseModel):
    """A single embedding model returned by a provider."""

    id: str
    display_name: str | None = None
    description: str | None = None


class FetchModelsResult(BaseModel):
    """Result of calling the provider endpoint to list available models."""

    success: bool
    provider_slug: str
    models: list[EmbeddingModel] = []
    message: str = ""
    detail: str | None = None


# ── Config test result ────────────────────────────────────────────────────────

class ConfigTestResult(BaseModel):
    """Result of testing an embedding provider configuration."""

    success: bool
    message: str
    detail: str | None = None
    latency_ms: float | None = None
