"""Password hashing utilities using bcrypt directly.

bcrypt >= 4.0 enforces a strict 72-byte limit per the algorithm spec.
We truncate to 72 bytes before hashing so the limit is always respected.
"""

import bcrypt

# bcrypt hard limit (algorithm spec)
_BCRYPT_MAX_BYTES = 72
_ROUNDS = 12


def _encode(password: str) -> bytes:
    """UTF-8 encode and truncate to 72 bytes (bcrypt maximum)."""
    raw = password.encode("utf-8")
    return raw[:_BCRYPT_MAX_BYTES]


def get_password_hash(password: str) -> str:
    """Return a bcrypt hash of the password."""
    hashed = bcrypt.hashpw(_encode(password), bcrypt.gensalt(rounds=_ROUNDS))
    return hashed.decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Return True if plain_password matches the stored bcrypt hash."""
    return bcrypt.checkpw(_encode(plain_password), hashed_password.encode("utf-8"))

