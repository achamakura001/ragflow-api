"""Auth router – register, verify, login, me."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.jwt import get_current_user
from app.config import get_settings
from app.database import get_db
from app.models.user import User
from app.repositories.auth_repository import AuthRepository
from app.schemas.auth import (
    LoginRequest,
    MeResponse,
    RegisterRequest,
    RegisterResponse,
    TenantRead,
    TokenResponse,
    UserRead,
    VerifyRequest,
)
from app.schemas.tenant import AddAdminRequest
from app.services.auth_service import AuthService

router = APIRouter()
settings = get_settings()


def get_auth_service(db: AsyncSession = Depends(get_db)) -> AuthService:
    return AuthService(AuthRepository(db))


AuthServiceDep = Annotated[AuthService, Depends(get_auth_service)]
CurrentUserDep = Annotated[User, Depends(get_current_user)]


@router.post("/register", response_model=RegisterResponse, status_code=status.HTTP_201_CREATED)
async def register(payload: RegisterRequest, service: AuthServiceDep):
    """Register a new user.

    - **First user** from an email domain → creates a new tenant and becomes **admin**.
    - **Subsequent users** from the same domain → auto-join the tenant as **editor**.

    A 6-digit verification code is sent to the email (simulated: returned in response for dev).
    Call `POST /auth/verify` before logging in.
    """
    user, role, simulated_code = await service.register(payload)
    return RegisterResponse(
        message=f"Verification code sent to {user.email}. You joined as {role.value}.",
        simulated_code=simulated_code,
    )


@router.post("/verify", response_model=TokenResponse)
async def verify(payload: VerifyRequest, service: AuthServiceDep):
    """Verify the 6-digit code sent to email. Returns a JWT on success."""
    user, access_token = await service.verify(payload)
    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


@router.post("/login", response_model=TokenResponse)
async def login(payload: LoginRequest, service: AuthServiceDep):
    """Login with verified email and password. Returns a JWT access token."""
    user, access_token = await service.login(payload)
    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


@router.get("/me", response_model=MeResponse)
async def me(current_user: CurrentUserDep, service: AuthServiceDep):
    """Get current authenticated user profile and tenant.

    Requires `Authorization: Bearer <token>` header.
    """
    user, tenant, role = await service.get_me(current_user)
    return MeResponse(
        user=UserRead(
            id=user.id,
            email=user.email,
            first_name=user.first_name,
            last_name=user.last_name,
            phone=user.phone,
            tenant_id=user.tenant_id,
            email_verified=user.email_verified,
            is_active=user.is_active,
            created_at=user.created_at,
            role=role,
        ),
        tenant=TenantRead.model_validate(tenant),
    )


@router.post("/tenants/admins", status_code=status.HTTP_204_NO_CONTENT)
async def promote_to_admin(
    payload: AddAdminRequest,
    current_user: CurrentUserDep,
    service: AuthServiceDep,
):
    """Promote a tenant member to admin. Caller must be a tenant admin."""
    if not await service._repo.is_tenant_admin(current_user.id, current_user.tenant_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only tenant admins can promote members",
        )
    await service.promote_to_admin(current_user, payload.email)

