#!/usr/bin/env python3
"""
Manual integration test script for the registration flow.

Usage (server must be running on http://localhost:8000):
  APP_ENV=dev .venv/bin/python scripts/test_register_flow.py

Steps exercised:
  1. Register a new user with password "admin123"
  2. Verify the account using the simulated 6-digit code
  3. Login and receive a JWT token
  4. Call /me to confirm identity
"""

import sys
import json
import time
import urllib.request
import urllib.error

BASE_URL = "http://localhost:8000/api/v1"

# ── Test credentials ──────────────────────────────────────────────────────────
# Use a unique email per run so the script can be re-run without cleanup
_RUN_ID = int(time.time())
EMAIL = f"testuser+{_RUN_ID}@example.com"
PASSWORD = "admin123"
FIRST_NAME = "Test"
LAST_NAME = "User"


def _post(path: str, body: dict) -> dict:
    url = f"{BASE_URL}{path}"
    data = json.dumps(body).encode()
    req = urllib.request.Request(
        url, data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req) as resp:
            result = json.loads(resp.read())
            print(f"  ✓ POST {path} → {resp.status}")
            return result
    except urllib.error.HTTPError as exc:
        body_text = exc.read().decode()
        print(f"  ✗ POST {path} → {exc.code}: {body_text}")
        sys.exit(1)


def _get(path: str, token: str) -> dict:
    url = f"{BASE_URL}{path}"
    req = urllib.request.Request(
        url,
        headers={"Authorization": f"Bearer {token}"},
        method="GET",
    )
    try:
        with urllib.request.urlopen(req) as resp:
            result = json.loads(resp.read())
            print(f"  ✓ GET  {path} → {resp.status}")
            return result
    except urllib.error.HTTPError as exc:
        body_text = exc.read().decode()
        print(f"  ✗ GET  {path} → {exc.code}: {body_text}")
        sys.exit(1)


def main() -> None:
    print("\n=== Registration Flow Test ===\n")

    # ── Step 1: Register ──────────────────────────────────────────────────────
    print("Step 1 – Register")
    reg = _post("/auth/register", {
        "email": EMAIL,
        "password": PASSWORD,
        "first_name": FIRST_NAME,
        "last_name": LAST_NAME,
    })
    print(f"         message      : {reg.get('message')}")
    code = reg.get("simulated_code")
    print(f"         simulated_code: {code}")
    assert code and len(code) == 6, "Expected a 6-digit code"

    # ── Step 2: Verify email ──────────────────────────────────────────────────
    print("\nStep 2 – Verify email code")
    verify = _post("/auth/verify", {"email": EMAIL, "code": code})
    token = verify.get("access_token")
    print(f"         token_type   : {verify.get('token_type')}")
    print(f"         access_token : {token[:30]}…")
    assert token, "Expected an access_token"

    # ── Step 3: Login ─────────────────────────────────────────────────────────
    print("\nStep 3 – Login")
    login = _post("/auth/login", {"email": EMAIL, "password": PASSWORD})
    login_token = login.get("access_token")
    print(f"         access_token : {login_token[:30]}…")
    assert login_token, "Expected an access_token"

    # ── Step 4: /me ───────────────────────────────────────────────────────────
    print("\nStep 4 – GET /me")
    me = _get("/auth/me", login_token)
    user_data = me.get("user", {})
    tenant_data = me.get("tenant", {})
    print(f"         email        : {user_data.get('email')}")
    print(f"         full name    : {user_data.get('first_name')} {user_data.get('last_name')}")
    print(f"         is_active    : {user_data.get('is_active')}")
    print(f"         role         : {user_data.get('role')}")
    print(f"         tenant_id    : {user_data.get('tenant_id')}")
    print(f"         tenant name  : {tenant_data.get('name')}")
    print(f"         tenant plan  : {tenant_data.get('plan')}")
    assert user_data.get("email") == EMAIL
    assert user_data.get("is_active") is True
    assert user_data.get("email_verified") is True

    print("\n=== All steps passed ✓ ===\n")


if __name__ == "__main__":
    main()
