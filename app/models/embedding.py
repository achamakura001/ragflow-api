"""
SQLAlchemy ORM models – EmbeddingProvider and TenantEmbeddingConfig.

EmbeddingProvider    : lookup catalogue describing each supported embedding
                       service (OpenAI, Ollama, Gemini …) together with the
                       property schema the UI needs to render the config form.

TenantEmbeddingConfig: tenant-scoped, environment-specific configuration record
                       that stores the actual credentials in a JSON properties
                       blob.  Secret values are masked on read via the service
                       layer.
"""

from __future__ import annotations

import datetime
import uuid

from sqlalchemy import (
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
# Reuse the same env enum – same four environments (dev/qa/perf/prod)
from app.models.vectordb import VectorDbEnv


class EmbeddingProvider(Base):
    """
    Catalogue of supported embedding service providers.

    ``property_schema`` is a JSON array where each element follows the shape:

        {
            "name":        "api_key",
            "label":       "API Key",
            "type":        "string | integer | boolean | password",
            "required":    true,
            "secret":      true,
            "placeholder": "sk-…",
            "description": "OpenAI API key",
            "default":     null
        }

    ``models_url`` is the provider endpoint that returns a list of models.
    The provider implementation uses this URL together with properties to
    perform the real HTTP call.
    """

    __tablename__ = "embedding_providers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, index=True)
    slug: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    # REST endpoint (may contain {api_key} placeholder for query-param auth)
    models_url: Mapped[str] = mapped_column(String(512), nullable=False)
    # JSON array of PropertyDefinition objects
    property_schema: Mapped[list] = mapped_column(JSON, nullable=False, default=list)

    configs: Mapped[list["TenantEmbeddingConfig"]] = relationship(
        "TenantEmbeddingConfig",
        back_populates="provider",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<EmbeddingProvider slug={self.slug!r}>"


class TenantEmbeddingConfig(Base):
    """
    A tenant-scoped, environment-specific embedding provider configuration.

    ``properties`` is a JSON dict whose keys match the ``name`` fields in the
    parent EmbeddingProvider's ``property_schema``.
    """

    __tablename__ = "tenant_embedding_configs"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    tenant_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    created_by_user_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    provider_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("embedding_providers.id", ondelete="RESTRICT"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    environment: Mapped[VectorDbEnv] = mapped_column(
        Enum(VectorDbEnv, values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        default=VectorDbEnv.DEV,
    )
    # Actual credential/config values keyed by property name
    properties: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    provider: Mapped["EmbeddingProvider"] = relationship(
        "EmbeddingProvider", back_populates="configs"
    )
    tenant: Mapped["Tenant"] = relationship("Tenant")  # type: ignore[name-defined]
    created_by: Mapped["User"] = relationship("User")  # type: ignore[name-defined]

    def __repr__(self) -> str:
        return (
            f"<TenantEmbeddingConfig id={self.id!r} name={self.name!r} "
            f"env={self.environment.value} provider_id={self.provider_id}>"
        )
