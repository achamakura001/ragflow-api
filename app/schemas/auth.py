"""Pydantic schemas for auth, user, and tenant."""

import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.models.tenant import TenantMemberRole, TenantPlan


class RegisterRequest(BaseModel):
    """Schema for POST /auth/register."""

    email: EmailStr
    password: str = Field(..., min_length=8, max_length=20)
    first_name: str = Field(..., min_length=1, max_length=100)
    last_name: str = Field(..., min_length=1, max_length=100)
    phone: str | None = Field(None, max_length=30, examples=["+1-555-000-1234"])


class VerifyRequest(BaseModel):
    """Schema for POST /auth/verify – verify 6-digit email code."""

    email: EmailStr
    code: str = Field(..., min_length=6, max_length=6, pattern=r"^\d{6}$")


class LoginRequest(BaseModel):
    """Schema for POST /auth/login."""

    email: EmailStr
    password: str = Field(..., min_length=8, max_length=20)


class TokenResponse(BaseModel):
    """Schema for token response (login, refresh)."""

    access_token: str
    token_type: str = "bearer"
    expires_in: int  # seconds


class TenantRead(BaseModel):
    """Tenant info returned to the client."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    slug: str
    name: str
    domain: str
    primary_admin_email: str
    plan: TenantPlan
    created_at: datetime.datetime


class UserRead(BaseModel):
    """User info returned to the client (no password)."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    first_name: str
    last_name: str
    phone: str | None
    tenant_id: str
    email_verified: bool
    is_active: bool
    created_at: datetime.datetime
    role: TenantMemberRole | None = None  # populated from membership


class RegisterResponse(BaseModel):
    """Schema for POST /auth/register – verification code sent (simulated)."""

    message: str = "Verification code sent to your email"
    simulated_code: str | None = None  # Only in dev/simulation mode


class MeResponse(BaseModel):
    """Schema for GET /auth/me – current user with tenant."""

    user: UserRead
    tenant: TenantRead
