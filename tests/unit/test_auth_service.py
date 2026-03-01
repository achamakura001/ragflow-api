"""
Unit tests for AuthService with all new features:
  - register first user (new tenant, admin role)
  - register second user same domain (auto-join as editor)
  - verify email code
  - login
  - promote to admin
  - change member role
"""

import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from app.models.tenant import TenantMember, TenantMemberRole, TenantPlan
from app.models.user import User
from app.services.auth_service import AuthService


# ── Helpers ───────────────────────────────────────────────────────────────────

def _now() -> datetime.datetime:
    return datetime.datetime(2026, 1, 1, tzinfo=datetime.timezone.utc)


def _make_user(**kw) -> MagicMock:
    defaults = dict(
        id=1, email="alice@acme.com", first_name="Alice", last_name="Smith",
        phone=None, password_hash="hashed", email_verified=True, is_active=True,
        tenant_id="tenant-uuid", created_at=_now(), updated_at=_now(),
    )
    defaults.update(kw)
    u = MagicMock(spec=User)
    for k, v in defaults.items():
        setattr(u, k, v)
    return u


def _make_membership(role: TenantMemberRole = TenantMemberRole.ADMIN) -> MagicMock:
    m = MagicMock(spec=TenantMember)
    m.role = role
    m.joined_at = _now()
    return m


def _make_tenant(**kw) -> MagicMock:
    from app.models.tenant import Tenant
    defaults = dict(
        id="tenant-uuid", slug="acme-com", name="acme.com", domain="acme.com",
        primary_admin_email="alice@acme.com", plan=TenantPlan.STARTER, created_at=_now(),
    )
    defaults.update(kw)
    t = MagicMock(spec=Tenant)
    for k, v in defaults.items():
        setattr(t, k, v)
    return t


@pytest.fixture()
def repo() -> AsyncMock:
    return AsyncMock()


@pytest.fixture()
def service(repo: AsyncMock) -> AuthService:
    return AuthService(repo)


# ── Register – first user (new domain) ───────────────────────────────────────

@pytest.mark.asyncio
async def test_register_first_user_creates_tenant_as_admin(service, repo):
    from app.schemas.auth import RegisterRequest

    payload = RegisterRequest(
        email="alice@acme.com", password="password123",
        first_name="Alice", last_name="Smith", phone="+1-555-0001",
    )
    repo.get_user_by_email.return_value = None
    repo.get_tenant_by_domain.return_value = None  # no existing tenant
    repo.create_tenant.return_value = _make_tenant()
    repo.create_user.return_value = _make_user()
    repo.add_member.return_value = _make_membership(TenantMemberRole.ADMIN)

    with patch("app.services.auth_service.store_code", return_value="123456"), \
         patch("app.services.auth_service.get_password_hash", return_value="hashed_pw"):
        user, role, code = await service.register(payload)

    assert role == TenantMemberRole.ADMIN
    assert code == "123456"
    repo.create_tenant.assert_awaited_once()
    repo.add_member.assert_awaited_once_with(
        tenant_id="tenant-uuid", user_id=1, role=TenantMemberRole.ADMIN
    )


@pytest.mark.asyncio
async def test_register_second_user_same_domain_joins_as_editor(service, repo):
    from app.schemas.auth import RegisterRequest

    payload = RegisterRequest(
        email="bob@acme.com", password="password456",
        first_name="Bob", last_name="Jones",
    )
    repo.get_user_by_email.return_value = None
    repo.get_tenant_by_domain.return_value = _make_tenant()  # tenant already exists
    repo.create_user.return_value = _make_user(id=2, email="bob@acme.com")
    repo.add_member.return_value = _make_membership(TenantMemberRole.EDITOR)

    with patch("app.services.auth_service.store_code", return_value="654321"), \
         patch("app.services.auth_service.get_password_hash", return_value="hashed_pw"):
        user, role, code = await service.register(payload)

    assert role == TenantMemberRole.EDITOR
    # tenant should NOT be created for the second user
    repo.create_tenant.assert_not_awaited()
    repo.add_member.assert_awaited_once_with(
        tenant_id="tenant-uuid", user_id=2, role=TenantMemberRole.EDITOR
    )


@pytest.mark.asyncio
async def test_register_duplicate_email_raises_400(service, repo):
    from app.schemas.auth import RegisterRequest

    repo.get_user_by_email.return_value = _make_user()
    payload = RegisterRequest(
        email="alice@acme.com", password="password123",
        first_name="Alice", last_name="Smith",
    )
    with pytest.raises(HTTPException) as exc_info:
        await service.register(payload)
    assert exc_info.value.status_code == 400


# ── Verify ────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_verify_success(service, repo):
    from app.schemas.auth import VerifyRequest

    user = _make_user(email_verified=False)
    repo.get_user_by_email.return_value = user

    with patch("app.services.auth_service.verify_code_store", return_value=True), \
         patch("app.services.auth_service.create_access_token", return_value="jwt-token"):
        returned_user, token = await service.verify(
            VerifyRequest(email="alice@acme.com", code="123456")
        )

    assert token == "jwt-token"
    repo.set_user_email_verified.assert_awaited_once_with(user)


@pytest.mark.asyncio
async def test_verify_wrong_code_raises_400(service, repo):
    from app.schemas.auth import VerifyRequest

    repo.get_user_by_email.return_value = _make_user(email_verified=False)
    with patch("app.services.auth_service.verify_code_store", return_value=False):
        with pytest.raises(HTTPException) as exc_info:
            await service.verify(VerifyRequest(email="alice@acme.com", code="000000"))
    assert exc_info.value.status_code == 400


@pytest.mark.asyncio
async def test_verify_already_verified_raises_400(service, repo):
    from app.schemas.auth import VerifyRequest

    repo.get_user_by_email.return_value = _make_user(email_verified=True)
    with pytest.raises(HTTPException) as exc_info:
        await service.verify(VerifyRequest(email="alice@acme.com", code="123456"))
    assert exc_info.value.status_code == 400


# ── Login ─────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_login_success(service, repo):
    from app.schemas.auth import LoginRequest

    repo.get_user_by_email.return_value = _make_user()
    with patch("app.services.auth_service.verify_password", return_value=True), \
         patch("app.services.auth_service.create_access_token", return_value="jwt"):
        user, token = await service.login(LoginRequest(email="alice@acme.com", password="Password1"))
    assert token == "jwt"


@pytest.mark.asyncio
async def test_login_wrong_password_raises_401(service, repo):
    from app.schemas.auth import LoginRequest

    repo.get_user_by_email.return_value = _make_user()
    with patch("app.services.auth_service.verify_password", return_value=False):
        with pytest.raises(HTTPException) as exc_info:
            await service.login(LoginRequest(email="alice@acme.com", password="wrongpw1"))
    assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_login_unverified_raises_403(service, repo):
    from app.schemas.auth import LoginRequest

    repo.get_user_by_email.return_value = _make_user(email_verified=False)
    with pytest.raises(HTTPException) as exc_info:
        await service.login(LoginRequest(email="alice@acme.com", password="Password1"))
    assert exc_info.value.status_code == 403


@pytest.mark.asyncio
async def test_login_inactive_user_raises_403(service, repo):
    from app.schemas.auth import LoginRequest

    repo.get_user_by_email.return_value = _make_user(is_active=False)
    with pytest.raises(HTTPException) as exc_info:
        await service.login(LoginRequest(email="alice@acme.com", password="Password1"))
    assert exc_info.value.status_code == 403


# ── Promote to admin ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_promote_to_admin_success(service, repo):
    caller = _make_user(id=1, email="alice@acme.com", tenant_id="t1")
    target = _make_user(id=2, email="bob@acme.com", tenant_id="t1")
    membership = _make_membership(TenantMemberRole.EDITOR)

    repo.get_user_by_email.return_value = target
    repo.get_membership.return_value = membership

    await service.promote_to_admin(caller, "bob@acme.com")
    repo.set_member_role.assert_awaited_once_with(membership, TenantMemberRole.ADMIN)


@pytest.mark.asyncio
async def test_promote_self_raises_400(service, repo):
    caller = _make_user(id=1, email="alice@acme.com")
    with pytest.raises(HTTPException) as exc_info:
        await service.promote_to_admin(caller, "alice@acme.com")
    assert exc_info.value.status_code == 400


@pytest.mark.asyncio
async def test_promote_cross_tenant_raises_403(service, repo):
    caller = _make_user(id=1, email="alice@acme.com", tenant_id="t1")
    target = _make_user(id=2, email="bob@other.com", tenant_id="t2")  # different tenant
    repo.get_user_by_email.return_value = target
    with pytest.raises(HTTPException) as exc_info:
        await service.promote_to_admin(caller, "bob@other.com")
    assert exc_info.value.status_code == 403


# ── Change member role ────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_change_member_role(service, repo):
    caller = _make_user(id=1, tenant_id="t1")
    target = _make_user(id=2, tenant_id="t1")
    membership = _make_membership(TenantMemberRole.EDITOR)

    repo.get_user_by_id.return_value = target
    repo.get_membership.return_value = membership

    await service.change_member_role(caller, 2, TenantMemberRole.ADMIN)
    repo.set_member_role.assert_awaited_once_with(membership, TenantMemberRole.ADMIN)


@pytest.mark.asyncio
async def test_change_role_user_not_found_raises_404(service, repo):
    caller = _make_user(id=1, tenant_id="t1")
    repo.get_user_by_id.return_value = None
    with pytest.raises(HTTPException) as exc_info:
        await service.change_member_role(caller, 999, TenantMemberRole.ADMIN)
    assert exc_info.value.status_code == 404
