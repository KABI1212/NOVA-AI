from typing import Any, Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from config.database import MongoSession, get_db, get_db_optional
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


def _find_user_by_id(db: MongoSession, user_id: int) -> User | None:
    """Find a user by id using the MongoSession query interface."""
    collection = db.collection_for(User)
    payload = collection.find_one({"id": user_id})
    if payload is None:
        return None
    return User.from_mongo(payload, db)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: MongoSession = Depends(get_db),
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

    user = _find_user_by_id(db, user_id)
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
    db: Optional[MongoSession] = Depends(get_db_optional),
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

    user = _find_user_by_id(db, user_id)
    if user is None:
        raise _unauthorized("User not found")

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Inactive user",
        )

    return user
