"""Repository for auth, user, and tenant operations."""

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.tenant import Tenant, TenantMember, TenantMemberRole, TenantPlan
from app.models.user import User


def _domain_from_email(email: str) -> str:
    """Extract domain from email (e.g. user@acme.com -> acme.com)."""
    return email.split("@", 1)[1].lower()


def _slug_from_domain(domain: str) -> str:
    """Generate a URL-safe slug from domain (e.g. acme.com -> acme-com)."""
    return domain.replace(".", "-").replace("_", "-").lower()


class AuthRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    # ── User ──────────────────────────────────────────────────────────────────

    async def get_user_by_email(self, email: str) -> User | None:
        result = await self._session.execute(
            select(User).where(User.email == email.lower())
        )
        return result.scalar_one_or_none()

    async def get_user_by_id(self, user_id: int) -> User | None:
        result = await self._session.execute(select(User).where(User.id == user_id))
        return result.scalar_one_or_none()

    async def create_user(
        self,
        *,
        email: str,
        first_name: str,
        last_name: str,
        phone: str | None,
        password_hash: str,
        tenant_id: str,
    ) -> User:
        user = User(
            email=email.lower(),
            first_name=first_name,
            last_name=last_name,
            phone=phone,
            password_hash=password_hash,
            tenant_id=tenant_id,
            email_verified=False,
            is_active=True,
        )
        self._session.add(user)
        await self._session.flush()
        return user

    async def set_user_email_verified(self, user: User, verified: bool = True) -> None:
        """Persist email_verified flag using a direct UPDATE (avoids ORM tracking issues)."""
        await self._session.execute(
            update(User)
            .where(User.id == user.id)
            .values(email_verified=verified)
        )
        await self._session.flush()

    # ── Tenant ────────────────────────────────────────────────────────────────

    async def get_tenant_by_id(self, tenant_id: str) -> Tenant | None:
        result = await self._session.execute(
            select(Tenant).where(Tenant.id == tenant_id)
        )
        return result.scalar_one_or_none()

    async def get_tenant_by_domain(self, domain: str) -> Tenant | None:
        result = await self._session.execute(
            select(Tenant).where(Tenant.domain == domain.lower())
        )
        return result.scalar_one_or_none()

    async def create_tenant(
        self,
        *,
        domain: str,
        name: str,
        primary_admin_email: str,
        plan: TenantPlan,
    ) -> Tenant:
        slug = _slug_from_domain(domain)
        tenant = Tenant(
            slug=slug,
            name=name,
            domain=domain.lower(),
            primary_admin_email=primary_admin_email.lower(),
            plan=plan,
        )
        self._session.add(tenant)
        await self._session.flush()
        return tenant

    async def update_tenant_plan(self, tenant: Tenant, plan: TenantPlan) -> Tenant:
        tenant.plan = plan
        await self._session.flush()
        return tenant

    async def update_tenant_name(self, tenant: Tenant, name: str) -> Tenant:
        tenant.name = name
        await self._session.flush()
        return tenant

    # ── TenantMember ──────────────────────────────────────────────────────────

    async def add_member(
        self,
        tenant_id: str,
        user_id: int,
        role: TenantMemberRole,
    ) -> TenantMember:
        member = TenantMember(tenant_id=tenant_id, user_id=user_id, role=role)
        self._session.add(member)
        await self._session.flush()
        return member

    async def get_membership(self, user_id: int, tenant_id: str) -> TenantMember | None:
        result = await self._session.execute(
            select(TenantMember).where(
                TenantMember.tenant_id == tenant_id,
                TenantMember.user_id == user_id,
            )
        )
        return result.scalar_one_or_none()

    async def is_tenant_admin(self, user_id: int, tenant_id: str) -> bool:
        membership = await self.get_membership(user_id, tenant_id)
        return membership is not None and membership.role == TenantMemberRole.ADMIN

    async def set_member_role(
        self, member: TenantMember, role: TenantMemberRole
    ) -> TenantMember:
        member.role = role
        await self._session.flush()
        return member

    async def list_members(
        self, tenant_id: str, *, skip: int = 0, limit: int = 50
    ) -> tuple[int, list[tuple[TenantMember, User]]]:
        """Return (total, [(membership, user), ...]) for a tenant."""
        from sqlalchemy import func

        count_q = (
            select(func.count())
            .select_from(TenantMember)
            .where(TenantMember.tenant_id == tenant_id)
        )
        total = (await self._session.execute(count_q)).scalar_one()

        rows_q = (
            select(TenantMember, User)
            .join(User, TenantMember.user_id == User.id)
            .where(TenantMember.tenant_id == tenant_id)
            .offset(skip)
            .limit(limit)
        )
        rows = (await self._session.execute(rows_q)).all()
        return total, [(m, u) for m, u in rows]
