"""
SQLAlchemy ORM models – VectorDbType and VectorDbConnection.

VectorDbType  : lookup table listing supported vector DB engines with their
                required/optional property schemas (stored as JSON).
VectorDbConnection : tenant-scoped connections per environment; properties
                     (actual config values) stored as JSON.
"""

from __future__ import annotations

import datetime
import enum
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


class VectorDbEnv(str, enum.Enum):
    """Deployment environment a connection belongs to."""

    DEV = "dev"
    QA = "qa"
    PERF = "perf"
    PROD = "prod"


class VectorDbType(Base):
    """
    Catalogue of supported vector database engines.

    The `property_schema` column is a JSON array describing every configurable
    field the engine accepts.  Each element follows this shape:

        {
            "name":        "api_key",           # internal key used in properties dict
            "label":       "API Key",           # human-readable label for UI forms
            "type":        "password",          # string | integer | boolean | password
            "required":    true,
            "secret":      true,                # mask value on read
            "placeholder": "sk-…",
            "description": "Pinecone API key",
            "default":     null                 # optional default value
        }

    This structure lets the frontend render configuration forms dynamically
    without hard-coding field knowledge.
    """

    __tablename__ = "vector_db_types"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    slug: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=True)
    # JSON array of property definitions (see docstring above)
    property_schema: Mapped[list] = mapped_column(JSON, nullable=False, default=list)

    connections: Mapped[list["VectorDbConnection"]] = relationship(
        "VectorDbConnection", back_populates="db_type", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<VectorDbType slug={self.slug!r}>"


class VectorDbConnection(Base):
    """
    A tenant-scoped, environment-specific vector DB connection record.

    `properties` is a JSON dict whose keys match the `name` fields in the
    parent VectorDbType's `property_schema`.  Secret values are stored as-is
    (plain-text for now; encrypt at rest in production via a KMS-backed column
    type or an application-level encryption wrapper before GA).
    """

    __tablename__ = "vector_db_connections"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    tenant_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    created_by_user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    type_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("vector_db_types.id", ondelete="RESTRICT"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    environment: Mapped[VectorDbEnv] = mapped_column(
        Enum(VectorDbEnv, values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        default=VectorDbEnv.DEV,
    )
    # Actual config values keyed by property name
    properties: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    db_type: Mapped["VectorDbType"] = relationship("VectorDbType", back_populates="connections")
    tenant: Mapped["Tenant"] = relationship("Tenant")  # type: ignore[name-defined]
    created_by: Mapped["User"] = relationship("User")  # type: ignore[name-defined]

    def __repr__(self) -> str:
        return (
            f"<VectorDbConnection id={self.id!r} name={self.name!r} "
            f"env={self.environment.value} type_id={self.type_id}>"
        )
