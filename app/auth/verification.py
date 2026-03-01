"""Simulated 6-digit verification code storage for email verification.

In production, replace with Redis or a DB-backed store.
Codes expire after CODE_EXPIRE_MINUTES.
"""

import random
import time
from threading import Lock

CODE_EXPIRE_MINUTES = 10
_PENDING: dict[str, tuple[str, float]] = {}
_lock = Lock()


def generate_code() -> str:
    """Generate a 6-digit numeric code."""
    return "".join(str(random.randint(0, 9)) for _ in range(6))


def store_code(email: str) -> str:
    """Store a new code for the email. Returns the code (for simulation)."""
    code = generate_code()
    with _lock:
        _pending_cleanup()
        _PENDING[email.lower()] = (code, time.monotonic())
    return code


def verify_code(email: str, code: str) -> bool:
    """Verify the code for the email. Removes code on success."""
    email = email.lower()
    with _lock:
        _pending_cleanup()
        entry = _PENDING.get(email)
        if not entry:
            return False
        stored_code, _ = entry
        if stored_code == code:
            del _PENDING[email]
            return True
        return False


def _pending_cleanup() -> None:
    """Remove expired codes."""
    expire_sec = CODE_EXPIRE_MINUTES * 60
    now = time.monotonic()
    expired = [e for e, (_, ts) in _PENDING.items() if now - ts > expire_sec]
    for e in expired:
        del _PENDING[e]
