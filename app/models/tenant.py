"""
SQLAlchemy ORM models – Tenant, TenantPlan, TenantMember.
Multi-tenant entity with plan-based access control and role-aware membership.
MySQL-compatible (CHAR(36) for UUID, VARCHAR for enums).
"""

from __future__ import annotations

import datetime
import enum
import uuid

from sqlalchemy import DateTime, Enum, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class TenantPlan(str, enum.Enum):
    """Tenant subscription plan."""

    STARTER = "starter"
    PROFESSIONAL = "professional"
    ENTERPRISE = "enterprise"


class TenantMemberRole(str, enum.Enum):
    """Role a user holds within a tenant."""

    ADMIN = "admin"
    EDITOR = "editor"


class Tenant(Base):
    __tablename__ = "tenants"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    slug: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    domain: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    primary_admin_email: Mapped[str] = mapped_column(String(255), nullable=False)
    plan: Mapped[TenantPlan] = mapped_column(
        Enum(TenantPlan),
        nullable=False,
        default=TenantPlan.STARTER,
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    users: Mapped[list["User"]] = relationship("User", back_populates="tenant")
    members: Mapped[list["TenantMember"]] = relationship(
        "TenantMember", back_populates="tenant", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Tenant id={self.id} domain={self.domain!r} name={self.name!r}>"


class TenantMember(Base):
    """Role-aware membership: every user in a tenant has exactly one role (admin | editor)."""

    __tablename__ = "tenant_members"

    tenant_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        primary_key=True,
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    role: Mapped[TenantMemberRole] = mapped_column(
        Enum(TenantMemberRole),
        nullable=False,
        default=TenantMemberRole.EDITOR,
    )
    joined_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    tenant: Mapped["Tenant"] = relationship("Tenant", back_populates="members")
    user: Mapped["User"] = relationship("User", back_populates="memberships")

    def __repr__(self) -> str:
        return f"<TenantMember tenant={self.tenant_id} user={self.user_id} role={self.role}>"
