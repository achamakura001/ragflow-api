"""Auth service – register, verify, login, get current user."""

from fastapi import HTTPException, status

from app.auth.jwt import create_access_token
from app.auth.password import get_password_hash, verify_password
from app.auth.verification import store_code, verify_code as verify_code_store
from app.config import get_settings
from app.models.tenant import TenantMemberRole, TenantPlan
from app.repositories.auth_repository import AuthRepository

settings = get_settings()


def _domain_from_email(email: str) -> str:
    return email.split("@", 1)[1].lower()


class AuthService:
    def __init__(self, repo: AuthRepository) -> None:
        self._repo = repo

    async def register(self, payload) -> tuple:
        """Register a new user.

        - If no tenant exists for the email domain → create tenant + assign role ADMIN.
        - If tenant already exists for the domain → auto-join as EDITOR.
        Returns (user, role, simulated_code).  User must verify email before login.
        """
        email = payload.email.lower()
        domain = _domain_from_email(email)

        existing_user = await self._repo.get_user_by_email(email)
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="A user with this email already exists",
            )

        existing_tenant = await self._repo.get_tenant_by_domain(domain)

        if existing_tenant is None:
            # First user from this domain – create a new tenant and become admin
            tenant = await self._repo.create_tenant(
                domain=domain,
                name=domain,
                primary_admin_email=email,
                plan=TenantPlan.STARTER,
            )
            role = TenantMemberRole.ADMIN
        else:
            # Same-domain user – auto-join the existing tenant as editor
            tenant = existing_tenant
            role = TenantMemberRole.EDITOR

        user = await self._repo.create_user(
            email=email,
            first_name=payload.first_name,
            last_name=payload.last_name,
            phone=getattr(payload, "phone", None),
            password_hash=get_password_hash(payload.password),
            tenant_id=tenant.id,
        )

        await self._repo.add_member(tenant_id=tenant.id, user_id=user.id, role=role)

        code = store_code(email)
        return user, role, code

    async def verify(self, payload) -> tuple:
        """Verify 6-digit code. On success mark user verified and return (user, access_token)."""
        email = payload.email.lower()
        user = await self._repo.get_user_by_email(email)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found. Please register first.",
            )
        if user.email_verified:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already verified. You can log in.",
            )
        if not verify_code_store(email, payload.code):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid or expired verification code",
            )
        await self._repo.set_user_email_verified(user)
        access_token = create_access_token(subject=user.id)
        return user, access_token

    async def login(self, payload) -> tuple:
        """Authenticate user and return (user, access_token). Requires email verification."""
        user = await self._repo.get_user_by_email(payload.email)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password",
            )
        if not user.email_verified:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Email not verified. Please verify your email with the code sent to you.",
            )
        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Account is deactivated. Contact your tenant admin.",
            )
        if not verify_password(payload.password, user.password_hash):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password",
            )
        access_token = create_access_token(subject=user.id)
        return user, access_token

    async def get_me(self, user) -> tuple:
        """Get user with tenant and membership role for /me response."""
        tenant = await self._repo.get_tenant_by_id(user.tenant_id)
        if not tenant:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Tenant not found",
            )
        membership = await self._repo.get_membership(user.id, user.tenant_id)
        role = membership.role if membership else None
        return user, tenant, role

    async def promote_to_admin(self, current_user, target_email: str) -> None:
        """Promote a tenant member to admin. Caller must be admin."""
        target_email = target_email.lower()
        if target_email == current_user.email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="You are already an admin",
            )

        target_user = await self._repo.get_user_by_email(target_email)
        if not target_user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found",
            )
        if target_user.tenant_id != current_user.tenant_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Can only manage users from the same tenant",
            )

        membership = await self._repo.get_membership(target_user.id, current_user.tenant_id)
        if not membership:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User is not a member of this tenant",
            )
        if membership.role == TenantMemberRole.ADMIN:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User is already an admin",
            )

        await self._repo.set_member_role(membership, TenantMemberRole.ADMIN)

    async def change_member_role(
        self, current_user, target_user_id: int, role: TenantMemberRole
    ) -> None:
        """Change any member's role. Caller must be admin."""
        target_user = await self._repo.get_user_by_id(target_user_id)
        if not target_user or target_user.tenant_id != current_user.tenant_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Member not found in your tenant",
            )

        membership = await self._repo.get_membership(target_user.id, current_user.tenant_id)
        if not membership:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Membership record not found",
            )
        await self._repo.set_member_role(membership, role)
