"""Pydantic schemas for vector DB types and connections."""

from __future__ import annotations

import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.models.vectordb import VectorDbEnv


# ── Property definition (returned from GET /vector-dbs/supported) ─────────────

class PropertyDefinition(BaseModel):
    """Describes a single configurable field for a vector DB engine."""

    name: str
    label: str
    type: str = Field(..., description="string | integer | boolean | password")
    required: bool
    secret: bool = False
    placeholder: str | None = None
    description: str | None = None
    default: Any = None


class VectorDbTypeRead(BaseModel):
    """Public representation of a supported vector DB engine."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    slug: str
    display_name: str
    description: str | None
    property_schema: list[PropertyDefinition]


class VectorDbTypeList(BaseModel):
    items: list[VectorDbTypeRead]
    total: int


# ── Connection schemas ────────────────────────────────────────────────────────

class CreateConnectionRequest(BaseModel):
    """Body for POST /vector-dbs/connections."""

    type_slug: str = Field(..., description="Slug of the vector DB type, e.g. 'qdrant'")
    name: str = Field(..., min_length=1, max_length=128, description="Friendly name for this connection")
    environment: VectorDbEnv = VectorDbEnv.DEV
    # Keys must match the property_schema `name` fields of the chosen type
    properties: dict[str, Any] = Field(..., description="Configuration key/value pairs")


class UpdateConnectionRequest(BaseModel):
    """Body for PATCH /vector-dbs/connections/{id}."""

    name: str | None = Field(None, min_length=1, max_length=128)
    environment: VectorDbEnv | None = None
    properties: dict[str, Any] | None = None


class VectorDbConnectionRead(BaseModel):
    """Connection record returned to the client. Secret property values are masked."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    tenant_id: str
    type_id: int
    type_slug: str             # denormalised from db_type for convenience
    type_display_name: str
    name: str
    environment: VectorDbEnv
    # Properties with secrets replaced by "***"
    properties: dict[str, Any]
    created_by_user_id: int | None
    created_at: datetime.datetime
    updated_at: datetime.datetime


class VectorDbConnectionList(BaseModel):
    items: list[VectorDbConnectionRead]
    total: int


# ── Test connection result ────────────────────────────────────────────────────

class ConnectionTestResult(BaseModel):
    """Result of a connection test."""

    success: bool
    message: str
    detail: str | None = None
    latency_ms: float | None = None
