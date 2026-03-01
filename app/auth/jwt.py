"""JWT utilities for token creation and validation."""

from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import Depends, HTTPException, Query, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import get_db
from app.models.user import User

settings = get_settings()

ALGORITHM = "HS256"

# Bearer token from Authorization header
_http_bearer = HTTPBearer(auto_error=False)


def get_token(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_http_bearer)],
    token_query: Annotated[str | None, Query(alias="token")] = None,
) -> str:
    """Extract JWT from Authorization: Bearer header or from ?token= query param."""
    if credentials is not None:
        return credentials.credentials
    if token_query:
        return token_query
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Not authenticated",
        headers={"WWW-Authenticate": "Bearer"},
    )


def create_access_token(
    subject: str | int,
    *,
    expires_delta: timedelta | None = None,
) -> str:
    """Create a JWT access token for the given subject (user id)."""
    if expires_delta is None:
        expires_delta = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    expire = datetime.now(UTC) + expires_delta
    to_encode = {"sub": str(subject), "exp": expire, "iat": datetime.now(UTC)}
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=ALGORITHM)


async def get_current_user(
    db: Annotated[AsyncSession, Depends(get_db)],
    token: Annotated[str, Depends(get_token)],
) -> User:
    """Validate JWT and return the current User."""
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])
        user_id_str: str | None = payload.get("sub")
        if user_id_str is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token payload",
            )
        user_id = int(user_id_str)
    except (JWTError, ValueError) as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        ) from e

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )
    return user
