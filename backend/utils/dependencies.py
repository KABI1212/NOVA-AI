from typing import Any, Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
try:
    from sqlalchemy.orm import Session
except ImportError:
    Session = Any

from config.database import get_db, get_db_optional
from models.user import User
from .auth import decode_access_token

security = HTTPBearer()
optional_security = HTTPBearer(auto_error=False)


def _unauthorized(detail: str = "Invalid authentication credentials") -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
) -> User:
    """Get the current authenticated user."""
    payload = decode_access_token(credentials.credentials)
    if payload is None:
        raise _unauthorized()

    raw_sub = payload.get("sub")
    if raw_sub is None:
        raise _unauthorized()

    try:
        user_id = int(raw_sub)
    except (TypeError, ValueError) as exc:
        raise _unauthorized() from exc

    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise _unauthorized("User not found")

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Inactive user",
        )

    return user


async def get_current_user_optional(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(optional_security),
    db: Optional[Session] = Depends(get_db_optional),
) -> Optional[User]:
    """Get the current authenticated user if provided, otherwise return None."""
    if credentials is None:
        return None

    if db is None:
        return None

    payload = decode_access_token(credentials.credentials)
    if payload is None:
        raise _unauthorized()

    raw_sub = payload.get("sub")
    if raw_sub is None:
        raise _unauthorized()

    try:
        user_id = int(raw_sub)
    except (TypeError, ValueError) as exc:
        raise _unauthorized() from exc

    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise _unauthorized("User not found")

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Inactive user",
        )

    return user
