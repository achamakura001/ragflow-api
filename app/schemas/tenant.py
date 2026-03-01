"""Pydantic schemas for tenant and membership operations."""

import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.models.tenant import TenantMemberRole, TenantPlan


class AddAdminRequest(BaseModel):
    """Schema for POST /tenants/admins – promote a member to admin."""

    email: EmailStr


class UpdateTenantPlanRequest(BaseModel):
    """Schema for PATCH /tenants/plan – update subscription plan."""

    plan: TenantPlan


class UpdateTenantNameRequest(BaseModel):
    """Schema for PATCH /tenants/name – update tenant display name."""

    name: str = Field(..., min_length=1, max_length=255)


class TenantMemberRead(BaseModel):
    """Schema for a user+role entry in the tenant member list."""

    model_config = ConfigDict(from_attributes=True)

    user_id: int
    email: str
    first_name: str
    last_name: str
    phone: str | None
    role: TenantMemberRole
    joined_at: datetime.datetime


class TenantMemberList(BaseModel):
    """Paginated list of tenant members."""

    total: int
    members: list[TenantMemberRead]


class ChangeMemberRoleRequest(BaseModel):
    """Schema for PATCH /tenants/members/{user_id}/role – change a member's role."""

    role: TenantMemberRole
