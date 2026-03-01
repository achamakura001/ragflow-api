"""
Tenant management router.
All endpoints require authentication; most require the caller to be a tenant admin.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.jwt import get_current_user
from app.database import get_db
from app.models.user import User
from app.repositories.auth_repository import AuthRepository
from app.schemas.tenant import (
    ChangeMemberRoleRequest,
    TenantMemberList,
    TenantMemberRead,
    UpdateTenantNameRequest,
    UpdateTenantPlanRequest,
)
from app.services.auth_service import AuthService

router = APIRouter()


# ── Shared dependencies ───────────────────────────────────────────────────────

def get_auth_service(db: AsyncSession = Depends(get_db)) -> AuthService:
    return AuthService(AuthRepository(db))


AuthServiceDep = Annotated[AuthService, Depends(get_auth_service)]
CurrentUserDep = Annotated[User, Depends(get_current_user)]


async def require_admin(current_user: User, service: AuthService) -> None:
    """Raise 403 if the current user is not a tenant admin."""
    is_admin = await service._repo.is_tenant_admin(current_user.id, current_user.tenant_id)
    if not is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only tenant admins can perform this action",
        )


# ── Tenant info & plan ────────────────────────────────────────────────────────

@router.patch("/plan", status_code=status.HTTP_204_NO_CONTENT)
async def update_plan(
    payload: UpdateTenantPlanRequest,
    current_user: CurrentUserDep,
    service: AuthServiceDep,
):
    """Update the tenant's subscription plan. Requires admin role.

    Plans: starter | professional | enterprise
    """
    await require_admin(current_user, service)
    tenant = await service._repo.get_tenant_by_id(current_user.tenant_id)
    if not tenant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found")
    await service._repo.update_tenant_plan(tenant, payload.plan)


@router.patch("/name", status_code=status.HTTP_204_NO_CONTENT)
async def update_name(
    payload: UpdateTenantNameRequest,
    current_user: CurrentUserDep,
    service: AuthServiceDep,
):
    """Update the tenant's display name. Requires admin role."""
    await require_admin(current_user, service)
    tenant = await service._repo.get_tenant_by_id(current_user.tenant_id)
    if not tenant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found")
    await service._repo.update_tenant_name(tenant, payload.name)


# ── Members ───────────────────────────────────────────────────────────────────

@router.get("/members", response_model=TenantMemberList)
async def list_members(
    current_user: CurrentUserDep,
    service: AuthServiceDep,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
):
    """List all members in your tenant with their roles. Any authenticated user can view."""
    total, rows = await service._repo.list_members(
        current_user.tenant_id, skip=skip, limit=limit
    )
    members = [
        TenantMemberRead(
            user_id=user.id,
            email=user.email,
            first_name=user.first_name,
            last_name=user.last_name,
            phone=user.phone,
            role=member.role,
            joined_at=member.joined_at,
        )
        for member, user in rows
    ]
    return TenantMemberList(total=total, members=members)


@router.patch("/members/{user_id}/role", status_code=status.HTTP_204_NO_CONTENT)
async def change_member_role(
    user_id: int,
    payload: ChangeMemberRoleRequest,
    current_user: CurrentUserDep,
    service: AuthServiceDep,
):
    """Change a member's role (admin ↔ editor). Requires admin role."""
    await require_admin(current_user, service)
    await service.change_member_role(current_user, user_id, payload.role)
