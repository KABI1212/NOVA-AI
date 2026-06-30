import logging
import re
from datetime import datetime, timedelta
from typing import Any, Literal

from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response, status
from pydantic import BaseModel, EmailStr, field_validator
from starlette.concurrency import run_in_threadpool
try:
    from sqlalchemy.exc import IntegrityError
    from sqlalchemy import func
except ImportError:
    class IntegrityError(Exception):
        """Fallback when SQLAlchemy is not installed."""
    func = None

try:
    from sqlalchemy.orm import Session
except ImportError:
    Session = Any

from config.database import get_db
from config.settings import settings
from models.conversation import Conversation
from models.auth_session import AuthSession
from models.chat_session import ChatSession
from models.document import Document
from models.file_record import FileRecord
from models.learning import LearningProgress
from models.user import User
from services.document_service import document_service
from services.email_service import EmailDeliveryError, email_service
from services.retriever import retriever_service
from services.storage import storage_service
from utils.auth import (
    access_token_expires_at,
    create_access_token,
    generate_csrf_token,
    generate_login_challenge_token,
    generate_numeric_otp,
    generate_refresh_token,
    get_password_hash,
    hash_secret_value,
    utcnow_naive,
    verify_password,
    verify_secret_value,
)
from utils.dependencies import get_current_user
from services.rate_limit_service import rate_limit_service

router = APIRouter(prefix="/api/auth", tags=["Authentication"])
logger = logging.getLogger(__name__)
EMAIL_DELIVERY_FAILURE_MESSAGE = (
    "We couldn't send the verification email right now. Please try again shortly."
)
PASSWORD_RESET_DELIVERY_FAILURE_MESSAGE = (
    "We couldn't send the password reset code right now. Please try again shortly."
)
PASSWORD_RESET_REQUEST_GENERIC_MESSAGE = (
    "If an account exists for that email, a password reset code has been sent."
)
EMAIL_TEST_DELIVERY_FAILURE_MESSAGE = (
    "We couldn't send the test email right now. Please try again shortly."
)
INVALID_LOGIN_MESSAGE = "Invalid email or password. Please try again."
OTP_LOCKED_MESSAGE = (
    "Too many failed attempts. Your account has been temporarily locked for "
    f"security. Please try again after {settings.AUTH_OTP_LOCK_MINUTES} minutes."
)
RESEND_LIMIT_MESSAGE = (
    "Too many resend attempts. Please sign in again to request a new code."
)


class SignupRequest(BaseModel):
    email: EmailStr
    username: str
    password: str
    full_name: str = ""

    @field_validator("username")
    @classmethod
    def validate_username(cls, value: str) -> str:
        username = (value or "").strip()
        if len(username) < 3:
            raise ValueError("Username must be at least 3 characters.")
        if len(username) > 32:
            raise ValueError("Username must be 32 characters or fewer.")
        if not re.fullmatch(r"[A-Za-z0-9._-]+", username):
            raise ValueError("Username can only contain letters, numbers, dots, underscores, and hyphens.")
        return username

    @field_validator("password")
    @classmethod
    def validate_password(cls, value: str) -> str:
        if len(value or "") < 8:
            raise ValueError("Password must be at least 8 characters.")
        return value

    @field_validator("full_name")
    @classmethod
    def normalize_full_name(cls, value: str) -> str:
        return (value or "").strip()


class LoginRequest(BaseModel):
    email: str
    password: str

    @field_validator("email")
    @classmethod
    def validate_identifier(cls, value: str) -> str:
        identifier = (value or "").strip()
        if not identifier:
            raise ValueError("Email or username is required.")
        return identifier


class LoginOtpVerifyRequest(BaseModel):
    email: EmailStr
    otp: str
    challenge_token: str


class LoginOtpResendRequest(BaseModel):
    email: EmailStr
    challenge_token: str


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    email: EmailStr
    otp: str
    challenge_token: str
    new_password: str

    @field_validator("new_password")
    @classmethod
    def validate_new_password(cls, value: str) -> str:
        if len(value or "") < 8:
            raise ValueError("Password must be at least 8 characters.")
        return value


class TokenResponse(BaseModel):
    requires_otp: Literal[False] = False
    access_token: str
    token_type: str
    expires_at: datetime
    user: dict


class LoginChallengeResponse(BaseModel):
    requires_otp: Literal[True] = True
    challenge_token: str
    email: EmailStr
    masked_email: str
    otp_expires_at: datetime
    resend_available_at: datetime
    delivery_mode: Literal["email"]
    resend_attempts_remaining: int
    otp_attempts_remaining: int
    message: str
    dev_otp_code: str | None = None


class PasswordResetChallengeResponse(BaseModel):
    challenge_token: str | None = None
    email: EmailStr | None = None
    otp_expires_at: datetime | None = None
    delivery_mode: Literal["email"] | None = None
    message: str
    dev_otp_code: str | None = None


class PasswordResetResponse(BaseModel):
    message: str


class UpdateAccountRequest(BaseModel):
    email: EmailStr | None = None
    username: str | None = None
    full_name: str | None = None

    @field_validator("username")
    @classmethod
    def validate_username(cls, value: str | None) -> str | None:
        if value is None:
            return value
        username = value.strip()
        if len(username) < 3:
            raise ValueError("Username must be at least 3 characters.")
        if len(username) > 32:
            raise ValueError("Username must be 32 characters or fewer.")
        if not re.fullmatch(r"[A-Za-z0-9._-]+", username):
            raise ValueError("Username can only contain letters, numbers, dots, underscores, and hyphens.")
        return username

    @field_validator("full_name")
    @classmethod
    def normalize_full_name(cls, value: str | None) -> str | None:
        if value is None:
            return value
        return value.strip()


class EmailTestResponse(BaseModel):
    email: EmailStr
    delivery_mode: Literal["email"]
    message: str


class LogoutResponse(BaseModel):
    message: str


class LogoutRequest(BaseModel):
    all_devices: bool = False


class AuthSessionSummary(BaseModel):
    id: int
    user_id: int
    user_agent: str
    ip_address: str
    created_at: datetime
    updated_at: datetime
    last_used_at: datetime | None
    expires_at: datetime | None
    revoked_at: datetime | None
    revoked_reason: str
    rotated_from_session_id: int | None
    status: Literal["active", "expired", "revoked"]
    is_current: bool = False


class AuthSessionListResponse(BaseModel):
    sessions: list[AuthSessionSummary]


class RevokeSessionResponse(BaseModel):
    message: str


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _mask_email(email: str) -> str:
    local_part, separator, domain = (email or "").partition("@")
    if not local_part or not separator or not domain:
        return email

    return f"{local_part[:1]}{'*' * max(len(local_part) - 1, 3)}@{domain}"


def _remaining_login_otp_attempts(user: User) -> int:
    return max(
        settings.AUTH_OTP_MAX_ATTEMPTS - _safe_int(user.login_otp_failed_attempts),
        0,
    )


def _remaining_login_otp_resends(user: User) -> int:
    return max(
        settings.AUTH_OTP_MAX_RESEND_ATTEMPTS - _safe_int(user.login_otp_resend_count),
        0,
    )


def _login_resend_available_at(user: User) -> datetime:
    sent_at = user.login_otp_sent_at or utcnow_naive()
    return sent_at + timedelta(seconds=settings.AUTH_OTP_RESEND_COOLDOWN_SECONDS)


def _serialize_user(user: User) -> dict:
    return {
        "id": user.id,
        "email": user.email,
        "username": user.username,
        "full_name": user.full_name,
    }


def _client_ip(request: Request) -> str:
    forwarded_for = request.headers.get("x-forwarded-for", "")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    real_ip = request.headers.get("x-real-ip", "").strip()
    if real_ip:
        return real_ip
    return request.client.host if request.client else "unknown"


def _cookie_secure() -> bool:
    if settings.AUTH_COOKIE_SECURE is not None:
        return bool(settings.AUTH_COOKIE_SECURE)
    return not settings.DEBUG


def _cookie_samesite() -> str:
    value = str(settings.AUTH_COOKIE_SAMESITE or "lax").lower()
    return value if value in {"lax", "strict", "none"} else "lax"


def _set_session_cookies(response: Response, refresh_token: str, csrf_token: str, expires_at: datetime) -> None:
    max_age = max(1, int((expires_at - utcnow_naive()).total_seconds()))
    response.set_cookie(
        settings.REFRESH_TOKEN_COOKIE_NAME,
        refresh_token,
        max_age=max_age,
        expires=max_age,
        httponly=True,
        secure=_cookie_secure(),
        samesite=_cookie_samesite(),
        path="/api/auth",
    )
    response.set_cookie(
        settings.CSRF_COOKIE_NAME,
        csrf_token,
        max_age=max_age,
        expires=max_age,
        httponly=False,
        secure=_cookie_secure(),
        samesite=_cookie_samesite(),
        path="/",
    )


def _clear_session_cookies(response: Response) -> None:
    response.delete_cookie(settings.REFRESH_TOKEN_COOKIE_NAME, path="/api/auth")
    response.delete_cookie(settings.CSRF_COOKIE_NAME, path="/")


def _audit_auth_event(event: str, *, user: User | None = None, session: AuthSession | None = None, request: Request | None = None, reason: str = "") -> None:
    logger.info(
        "auth_audit event=%s user_id=%s session_id=%s ip=%s reason=%s",
        event,
        getattr(user, "id", None),
        getattr(session, "id", None),
        _client_ip(request) if request else "",
        reason,
    )


async def _enforce_auth_rate_limit(scope: str, request: Request, *, limit: int) -> None:
    if not settings.RATE_LIMIT_ENABLED:
        return
    identifier = _client_ip(request)
    result = await rate_limit_service.check_limit(
        scope,
        f"ip:{identifier}",
        limit=limit,
        window_seconds=settings.AUTH_RATE_LIMIT_WINDOW_SECONDS,
    )
    if result.current <= result.limit:
        return
    raise HTTPException(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        detail=f"Too many authentication requests. Try again in {result.retry_after} seconds.",
        headers={"Retry-After": str(result.retry_after)},
    )


def _create_auth_session(user: User, db: Session, request: Request, response: Response) -> AuthSession:
    refresh_token = generate_refresh_token()
    csrf_token = generate_csrf_token()
    now = utcnow_naive()
    expires_at = now + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    auth_session = AuthSession(
        user_id=user.id,
        refresh_token_hash=hash_secret_value(refresh_token),
        csrf_token_hash=hash_secret_value(csrf_token),
        user_agent=request.headers.get("user-agent", "")[:512],
        ip_address=_client_ip(request),
        created_at=now,
        updated_at=now,
        last_used_at=now,
        expires_at=expires_at,
    )
    db.add(auth_session)
    db.commit()
    db.refresh(auth_session)
    _set_session_cookies(response, refresh_token, csrf_token, expires_at)
    _audit_auth_event("session_created", user=user, session=auth_session, request=request)
    return auth_session


def _load_refresh_session(refresh_token: str | None, db: Session) -> AuthSession | None:
    if not refresh_token:
        return None
    return db.query(AuthSession).filter(
        AuthSession.refresh_token_hash == hash_secret_value(refresh_token)
    ).first()


def _validate_refresh_session(
    *,
    auth_session: AuthSession | None,
    csrf_token: str | None,
    csrf_header: str | None,
    db: Session,
) -> AuthSession:
    if auth_session is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token.")
    if auth_session.revoked_at is not None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token has been revoked.")
    if auth_session.expires_at is None or auth_session.expires_at <= utcnow_naive():
        auth_session.revoked_at = utcnow_naive()
        auth_session.revoked_reason = "expired"
        db.add(auth_session)
        db.commit()
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token has expired.")
    if not csrf_header or not csrf_token or csrf_header != csrf_token:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid CSRF token.")
    if not verify_secret_value(csrf_header, auth_session.csrf_token_hash):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid CSRF token.")
    return auth_session


def _revoke_active_user_sessions(
    *,
    db: Session,
    user_id: Any,
    reason: str,
) -> int:
    now = utcnow_naive()
    sessions = db.query(AuthSession).filter(AuthSession.user_id == user_id).all()
    revoked_count = 0
    for session in sessions:
        if session.revoked_at is not None:
            continue
        session.revoked_at = now
        session.revoked_reason = reason
        db.add(session)
        revoked_count += 1
    if revoked_count:
        db.commit()
    return revoked_count


def _cleanup_expired_auth_sessions(*, db: Session, user_id: int) -> int:
    now = utcnow_naive()
    sessions = db.query(AuthSession).filter(AuthSession.user_id == user_id).all()
    expired_count = 0
    for session in sessions:
        if session.revoked_at is not None:
            continue
        if session.expires_at is None or session.expires_at > now:
            continue
        session.revoked_at = now
        session.revoked_reason = "expired"
        db.add(session)
        expired_count += 1
    if expired_count:
        db.commit()
    return expired_count


def _serialize_auth_session(
    session: AuthSession,
    *,
    current_session_id: int | None = None,
) -> dict[str, Any]:
    now = utcnow_naive()
    if session.revoked_reason == "expired":
        status_label: Literal["active", "expired", "revoked"] = "expired"
    elif session.revoked_at is not None:
        status_label = "revoked"
    elif session.expires_at is not None and session.expires_at <= now:
        status_label = "expired"
    else:
        status_label = "active"

    return {
        "id": session.id,
        "user_id": session.user_id,
        "user_agent": session.user_agent,
        "ip_address": session.ip_address,
        "created_at": session.created_at,
        "updated_at": session.updated_at,
        "last_used_at": session.last_used_at,
        "expires_at": session.expires_at,
        "revoked_at": session.revoked_at,
        "revoked_reason": session.revoked_reason,
        "rotated_from_session_id": session.rotated_from_session_id,
        "status": status_label,
        "is_current": bool(current_session_id is not None and session.id == current_session_id),
    }


def _handle_refresh_token_reuse(
    *,
    auth_session: AuthSession,
    db: Session,
    request: Request,
    response: Response,
) -> None:
    user = db.query(User).filter(User.id == auth_session.user_id).first()
    revoked_count = _revoke_active_user_sessions(
        db=db,
        user_id=auth_session.user_id,
        reason="refresh_token_reuse",
    )
    _clear_session_cookies(response)
    _audit_auth_event(
        "refresh_token_reuse_detected",
        user=user,
        session=auth_session,
        request=request,
        reason=f"revoked_active_sessions={revoked_count}",
    )
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Refresh token reuse detected. Please sign in again.",
    )


def _revoke_single_session(
    *,
    db: Session,
    user_id: int,
    session_id: int,
    reason: str,
) -> AuthSession:
    session = db.query(AuthSession).filter(
        AuthSession.user_id == user_id,
        AuthSession.id == session_id,
    ).first()
    if session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found.")

    if session.revoked_at is None:
        session.revoked_at = utcnow_naive()
        session.revoked_reason = reason
        db.add(session)
        db.commit()

    return session


def _rotate_refresh_session(
    *,
    auth_session: AuthSession,
    user: User,
    db: Session,
    request: Request,
    response: Response,
) -> AuthSession:
    now = utcnow_naive()
    auth_session.revoked_at = now
    auth_session.revoked_reason = "rotated"
    db.add(auth_session)
    new_session = _create_auth_session(user, db, request, response)
    new_session.rotated_from_session_id = auth_session.id
    db.add(new_session)
    db.commit()
    db.refresh(new_session)
    _audit_auth_event("session_rotated", user=user, session=new_session, request=request)
    return new_session


def _build_token_response(user: User) -> dict:
    expires_at = access_token_expires_at()
    access_token = create_access_token(
        data={"sub": user.id, "username": user.username, "email": user.email}  # FIX: dynamic username JWT claims
    )
    return {
        "requires_otp": False,
        "access_token": access_token,
        "token_type": "bearer",
        "expires_at": expires_at,
        "user": _serialize_user(user),
    }


def _clear_login_otp_challenge(user: User) -> None:
    user.login_otp_code_hash = None
    user.login_otp_expires_at = None
    user.login_otp_sent_at = None
    user.login_otp_challenge_hash = None


def _reset_login_otp_security_state(user: User) -> None:
    user.login_otp_failed_attempts = 0
    user.login_otp_resend_count = 0
    user.login_otp_locked_until = None


def _clear_login_otp_state(user: User) -> None:
    _clear_login_otp_challenge(user)
    _reset_login_otp_security_state(user)


def _has_login_otp_state(user: User) -> bool:
    return bool(
        user.login_otp_code_hash
        or user.login_otp_challenge_hash
        or user.login_otp_expires_at is not None
        or user.login_otp_sent_at is not None
        or _safe_int(user.login_otp_failed_attempts) > 0
        or _safe_int(user.login_otp_resend_count) > 0
        or user.login_otp_locked_until is not None
    )


def _clear_password_reset_state(user: User) -> None:
    user.password_reset_otp_code_hash = None
    user.password_reset_otp_expires_at = None
    user.password_reset_otp_sent_at = None
    user.password_reset_otp_challenge_hash = None


def _reset_password_reset_security_state(user: User) -> None:
    user.password_reset_otp_failed_attempts = 0
    user.password_reset_otp_resend_count = 0
    user.password_reset_otp_locked_until = None


def _clear_all_password_reset_state(user: User) -> None:
    _clear_password_reset_state(user)
    _reset_password_reset_security_state(user)


def _persist_user(db: Session, user: User) -> None:
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise
    db.refresh(user)


def _delete_user(db: Session, user: User) -> None:
    db.delete(user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise


def _snapshot_login_otp_state(user: User) -> dict[str, Any]:
    return {
        "login_otp_code_hash": user.login_otp_code_hash,
        "login_otp_expires_at": user.login_otp_expires_at,
        "login_otp_sent_at": user.login_otp_sent_at,
        "login_otp_challenge_hash": user.login_otp_challenge_hash,
        "login_otp_failed_attempts": _safe_int(user.login_otp_failed_attempts),
        "login_otp_resend_count": _safe_int(user.login_otp_resend_count),
        "login_otp_locked_until": user.login_otp_locked_until,
    }


def _snapshot_password_reset_state(user: User) -> dict[str, Any]:
    return {
        "password_reset_otp_code_hash": user.password_reset_otp_code_hash,
        "password_reset_otp_expires_at": user.password_reset_otp_expires_at,
        "password_reset_otp_sent_at": user.password_reset_otp_sent_at,
        "password_reset_otp_challenge_hash": user.password_reset_otp_challenge_hash,
        "password_reset_otp_failed_attempts": _safe_int(user.password_reset_otp_failed_attempts),
        "password_reset_otp_resend_count": _safe_int(user.password_reset_otp_resend_count),
        "password_reset_otp_locked_until": user.password_reset_otp_locked_until,
    }


def _restore_login_otp_state(user: User, snapshot: dict[str, Any]) -> None:
    for field_name, value in snapshot.items():
        setattr(user, field_name, value)


def _restore_password_reset_state(user: User, snapshot: dict[str, Any]) -> None:
    for field_name, value in snapshot.items():
        setattr(user, field_name, value)


def _build_login_challenge_response(
    user: User,
    *,
    challenge_token: str,
    expires_at: datetime,
    delivery_mode: str,
    otp_code: str | None = None,
) -> dict:
    masked_email = _mask_email(user.email)
    response = {
        "requires_otp": True,
        "challenge_token": challenge_token,
        "email": user.email,
        "masked_email": masked_email,
        "otp_expires_at": expires_at,
        "resend_available_at": _login_resend_available_at(user),
        "delivery_mode": delivery_mode,
        "resend_attempts_remaining": _remaining_login_otp_resends(user),
        "otp_attempts_remaining": _remaining_login_otp_attempts(user),
        "message": (
            "A 6-digit verification code has been sent to your registered "
            f"email address {masked_email}. Please enter the code below. The "
            f"code will expire in {settings.AUTH_OTP_EXPIRE_MINUTES} minutes."
        ),
    }
    if settings.DEBUG and settings.AUTH_EXPOSE_DEBUG_OTP and otp_code:
        response["dev_otp_code"] = otp_code
    return response


def _ensure_login_not_locked(user: User, db: Session) -> None:
    locked_until = user.login_otp_locked_until
    if locked_until is None:
        return

    now = utcnow_naive()
    if locked_until <= now:
        _reset_login_otp_security_state(user)
        _persist_user(db, user)
        return

    raise HTTPException(
        status_code=status.HTTP_423_LOCKED,
        detail=OTP_LOCKED_MESSAGE,
    )


def _ensure_password_reset_not_locked(user: User, db: Session) -> None:
    locked_until = user.password_reset_otp_locked_until
    if locked_until is None:
        return

    now = utcnow_naive()
    if locked_until <= now:
        _reset_password_reset_security_state(user)
        _persist_user(db, user)
        return

    raise HTTPException(
        status_code=status.HTTP_423_LOCKED,
        detail=OTP_LOCKED_MESSAGE,
    )


async def _issue_login_otp(
    user: User,
    db: Session,
    *,
    is_resend: bool = False,
    is_registration: bool = False,
) -> dict:
    _ensure_login_not_locked(user, db)

    now = utcnow_naive()
    snapshot = _snapshot_login_otp_state(user)

    if is_resend:
        resend_available_at = _login_resend_available_at(user)
        if user.login_otp_sent_at and resend_available_at > now:
            seconds_remaining = max(
                int((resend_available_at - now).total_seconds() + 0.999),
                1,
            )
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Please wait {seconds_remaining} seconds before requesting a new code.",
            )

        resend_count = _safe_int(user.login_otp_resend_count)
        if resend_count >= settings.AUTH_OTP_MAX_RESEND_ATTEMPTS:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=RESEND_LIMIT_MESSAGE,
            )
        user.login_otp_resend_count = resend_count + 1
    else:
        _reset_login_otp_security_state(user)

    otp_code = generate_numeric_otp()
    challenge_token = generate_login_challenge_token()
    expires_at = now + timedelta(minutes=settings.AUTH_OTP_EXPIRE_MINUTES)

    user.login_otp_code_hash = hash_secret_value(otp_code)
    user.login_otp_challenge_hash = hash_secret_value(challenge_token)
    user.login_otp_expires_at = expires_at
    user.login_otp_sent_at = now

    _persist_user(db, user)

    try:
        send_otp = (
            email_service.send_registration_otp
            if is_registration
            else email_service.send_login_otp
        )
        delivery_mode = await run_in_threadpool(
            send_otp,
            recipient_email=user.email,
            otp_code=otp_code,
            recipient_name=user.full_name or user.username,
        )
    except EmailDeliveryError as exc:
        logger.error(
            "login_otp_email_delivery_failed purpose=%s user_id=%s email=%s error=%s",
            "registration" if is_registration else "login",
            user.id,
            user.email,
            exc,
        )
        _restore_login_otp_state(user, snapshot)
        _persist_user(db, user)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=EMAIL_DELIVERY_FAILURE_MESSAGE,
        ) from exc

    return _build_login_challenge_response(
        user,
        challenge_token=challenge_token,
        expires_at=expires_at,
        delivery_mode=delivery_mode,
        otp_code=otp_code,
    )


def _password_reset_resend_available_at(user: User) -> datetime:
    sent_at = user.password_reset_otp_sent_at or utcnow_naive()
    return sent_at + timedelta(seconds=settings.AUTH_OTP_RESEND_COOLDOWN_SECONDS)


async def _issue_password_reset_otp(user: User, db: Session) -> dict:
    _ensure_password_reset_not_locked(user, db)

    now = utcnow_naive()
    snapshot = _snapshot_password_reset_state(user)

    if user.password_reset_otp_sent_at:
        resend_available_at = _password_reset_resend_available_at(user)
        if resend_available_at > now:
            seconds_remaining = max(
                int((resend_available_at - now).total_seconds() + 0.999),
                1,
            )
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Please wait {seconds_remaining} seconds before requesting a new reset code.",
            )

        resend_count = _safe_int(user.password_reset_otp_resend_count)
        if resend_count >= settings.AUTH_OTP_MAX_RESEND_ATTEMPTS:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many password reset code requests. Please try again later.",
            )
        user.password_reset_otp_resend_count = resend_count + 1
    else:
        _reset_password_reset_security_state(user)

    otp_code = generate_numeric_otp()
    challenge_token = generate_login_challenge_token()
    expires_at = now + timedelta(minutes=settings.AUTH_OTP_EXPIRE_MINUTES)

    user.password_reset_otp_code_hash = hash_secret_value(otp_code)
    user.password_reset_otp_challenge_hash = hash_secret_value(challenge_token)
    user.password_reset_otp_expires_at = expires_at
    user.password_reset_otp_sent_at = now

    _persist_user(db, user)

    try:
        delivery_mode = await run_in_threadpool(
            email_service.send_password_reset_otp,
            recipient_email=user.email,
            otp_code=otp_code,
            recipient_name=user.full_name or user.username,
        )
    except EmailDeliveryError as exc:
        logger.error(
            "password_reset_otp_email_delivery_failed user_id=%s email=%s error=%s",
            user.id,
            user.email,
            exc,
        )
        _restore_password_reset_state(user, snapshot)
        _persist_user(db, user)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=PASSWORD_RESET_DELIVERY_FAILURE_MESSAGE,
        ) from exc

    response = {
        "challenge_token": challenge_token,
        "email": user.email,
        "otp_expires_at": expires_at,
        "delivery_mode": delivery_mode,
        "message": "A password reset code has been sent to your email address.",
    }
    if settings.DEBUG and settings.AUTH_EXPOSE_DEBUG_OTP:
        response["dev_otp_code"] = otp_code
    return response


def _load_user_by_email(email: str, db: Session) -> User | None:
    normalized_email = (email or "").strip().lower()
    if func is None:
        return db.query(User).filter(User.email == normalized_email).first()
    return db.query(User).filter(func.lower(User.email) == normalized_email).first()  # FIX: case-sensitive login bug


def _load_user_by_login_identifier(
    raw_identifier: str,
    normalized_identifier: str,
    db: Session,
) -> User | None:
    raw_identifier = (raw_identifier or "").strip()
    normalized = (normalized_identifier or "").strip().lower()
    if not raw_identifier:
        return None
    email_filter = func.lower(User.email) == normalized if func is not None else User.email == normalized  # FIX: case-sensitive login bug
    return db.query(User).filter(
        email_filter
        | (User.username == raw_identifier)
    ).first()


def _validate_pending_login(
    *,
    user: User | None,
    challenge_token: str,
    db: Session,
    allow_expired: bool = False,
) -> User:
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Verification request is invalid. Please sign in again.",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive",
        )

    _ensure_login_not_locked(user, db)

    if (
        not user.login_otp_code_hash
        or not user.login_otp_challenge_hash
        or user.login_otp_expires_at is None
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No active verification request. Please sign in again.",
        )

    if not verify_secret_value(challenge_token, user.login_otp_challenge_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Verification request is invalid. Please sign in again.",
        )

    if user.login_otp_expires_at < utcnow_naive() and not allow_expired:
        _clear_login_otp_challenge(user)  # FIX: OTP logic issue
        _persist_user(db, user)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="OTP expired. Please request a new one.",  # FIX: OTP logic issue
        )

    return user


def _validate_pending_password_reset(
    *,
    user: User | None,
    challenge_token: str,
    db: Session,
) -> User:
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No account found with this email address.",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive",
        )

    if (
        not user.password_reset_otp_code_hash
        or not user.password_reset_otp_challenge_hash
        or user.password_reset_otp_expires_at is None
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No active password reset request. Please request a new code.",
        )

    if not verify_secret_value(challenge_token, user.password_reset_otp_challenge_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Password reset request is invalid. Please request a new code.",
        )

    if user.password_reset_otp_expires_at < utcnow_naive():
        _clear_password_reset_state(user)
        _persist_user(db, user)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Verification code expired. Please request a new code.",
        )

    return user


@router.post(
    "/signup",
    response_model=TokenResponse | LoginChallengeResponse,
    status_code=status.HTTP_201_CREATED,
)
async def signup(
    request: SignupRequest,
    response: Response = None,
    http_request: Request = None,
    db: Session = Depends(get_db),
):
    """Register a new user and require OTP verification before sign-in."""

    email = request.email.strip().lower()  # FIX: case-sensitive login bug
    username = request.username.strip()
    full_name = request.full_name.strip() if request.full_name else ""

    existing_user = db.query(User).filter(
        (User.email == email) | (User.username == username)
    ).first()

    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User with this email or username already exists",
        )

    new_user = User(
        email=email,
        username=username,
        hashed_password=get_password_hash(request.password),
        full_name=full_name,
        is_verified=False,
    )

    db.add(new_user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User with this email or username already exists",
        )
    db.refresh(new_user)

    try:
        return await _issue_login_otp(new_user, db, is_registration=True)
    except HTTPException as exc:
        if exc.status_code == status.HTTP_503_SERVICE_UNAVAILABLE:
            logger.warning(
                "signup_otp_delivery_failed_cleanup user_id=%s email=%s",
                new_user.id,
                new_user.email,
            )
            try:
                _delete_user(db, new_user)
            except Exception:
                db.rollback()
                logger.exception(
                    "signup_otp_delivery_failed_cleanup_error user_id=%s email=%s",
                    new_user.id,
                    new_user.email,
                )
        raise


@router.post("/login", response_model=TokenResponse | LoginChallengeResponse)
async def login(
    request: LoginRequest,
    response: Response = None,
    http_request: Request = None,
    db: Session = Depends(get_db),
):
    """Validate credentials and issue a session for verified accounts."""

    if http_request is not None:
        await _enforce_auth_rate_limit("auth:login", http_request, limit=settings.AUTH_LOGIN_RATE_LIMIT_REQUESTS)

    raw_identifier = request.email.strip()
    normalized_identifier = raw_identifier.lower()  # FIX: case-sensitive login bug
    user = _load_user_by_login_identifier(raw_identifier, normalized_identifier, db)

    if not user or not verify_password(request.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=INVALID_LOGIN_MESSAGE,
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive",
        )

    if not user.is_verified and settings.AUTH_ALLOW_PASSWORD_ONLY_FALLBACK:
        user.is_verified = True
        _persist_user(db, user)
    elif not user.is_verified:
        return await _issue_login_otp(user, db, is_registration=True)

    if _has_login_otp_state(user):
        _clear_login_otp_state(user)
        _persist_user(db, user)

    if http_request is not None and response is not None:
        _create_auth_session(user, db, http_request, response)
    return _build_token_response(user)


@router.post("/signup/otp/verify", response_model=TokenResponse)
@router.post("/login/otp/verify", response_model=TokenResponse)
async def verify_login_otp(
    request: LoginOtpVerifyRequest,
    response: Response = None,
    http_request: Request = None,
    db: Session = Depends(get_db),
):
    """Verify a pending signup OTP and activate the account."""

    email = request.email.strip().lower()  # FIX: case-sensitive login bug
    otp = "".join(character for character in request.otp if character.isdigit())

    if len(otp) != settings.AUTH_OTP_LENGTH:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Verification code must be {settings.AUTH_OTP_LENGTH} digits.",
        )

    user = _validate_pending_login(
        user=_load_user_by_email(email, db),
        challenge_token=request.challenge_token.strip(),
        db=db,
    )

    if not verify_secret_value(otp, user.login_otp_code_hash):
        user.login_otp_failed_attempts = _safe_int(user.login_otp_failed_attempts) + 1
        attempts_remaining = _remaining_login_otp_attempts(user)
        if attempts_remaining <= 0:
            _clear_login_otp_challenge(user)
            user.login_otp_resend_count = 0
            user.login_otp_locked_until = utcnow_naive() + timedelta(
                minutes=settings.AUTH_OTP_LOCK_MINUTES
            )
            _persist_user(db, user)
            raise HTTPException(
                status_code=status.HTTP_423_LOCKED,
                detail=OTP_LOCKED_MESSAGE,
            )

        _persist_user(db, user)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=(
                "Incorrect code. Please try again. "
                f"You have {attempts_remaining} attempts remaining."
            ),
        )

    _clear_login_otp_state(user)  # FIX: OTP logic issue
    user.is_verified = True
    _persist_user(db, user)
    if http_request is not None and response is not None:
        _create_auth_session(user, db, http_request, response)

    return _build_token_response(user)


@router.post(
    "/signup/otp/resend",
    response_model=LoginChallengeResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def resend_signup_otp(
    request: LoginOtpResendRequest,
    db: Session = Depends(get_db),
):
    """Reissue a signup verification OTP for an active verification challenge."""

    email = request.email.strip().lower()
    user = _validate_pending_login(
        user=_load_user_by_email(email, db),
        challenge_token=request.challenge_token.strip(),
        db=db,
        allow_expired=True,
    )

    return await _issue_login_otp(user, db, is_resend=True, is_registration=True)


@router.post(
    "/login/otp/resend",
    response_model=LoginChallengeResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def resend_login_otp(
    request: LoginOtpResendRequest,
    db: Session = Depends(get_db),
):
    """Reissue a login OTP for an active verification challenge."""

    email = request.email.strip().lower()
    user = _validate_pending_login(
        user=_load_user_by_email(email, db),
        challenge_token=request.challenge_token.strip(),
        db=db,
        allow_expired=True,
    )

    return await _issue_login_otp(user, db, is_resend=True, is_registration=False)


@router.post(
    "/password/forgot",
    response_model=PasswordResetChallengeResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def forgot_password(
    request: ForgotPasswordRequest,
    db: Session = Depends(get_db),
):
    """Send a password-reset OTP when an active account exists."""

    email = request.email.strip().lower()
    user = _load_user_by_email(email, db)

    if user is None:
        return {"message": PASSWORD_RESET_REQUEST_GENERIC_MESSAGE}

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive",
        )

    if not email_service.can_send_real_email():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=PASSWORD_RESET_DELIVERY_FAILURE_MESSAGE,
        )

    return await _issue_password_reset_otp(user, db)


@router.post("/password/reset", response_model=PasswordResetResponse)
async def reset_password(
    request: ResetPasswordRequest,
    db: Session = Depends(get_db),
):
    """Reset an account password using a valid OTP challenge."""

    email = request.email.strip().lower()
    otp = "".join(character for character in request.otp if character.isdigit())
    new_password = request.new_password or ""

    if len(otp) != settings.AUTH_OTP_LENGTH:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Verification code must be {settings.AUTH_OTP_LENGTH} digits.",
        )

    if len(new_password) < 8:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="New password must be at least 8 characters.",
        )

    user = _validate_pending_password_reset(
        user=_load_user_by_email(email, db),
        challenge_token=request.challenge_token.strip(),
        db=db,
    )

    if not verify_secret_value(otp, user.password_reset_otp_code_hash):
        user.password_reset_otp_failed_attempts = _safe_int(user.password_reset_otp_failed_attempts) + 1
        attempts_remaining = max(
            settings.AUTH_OTP_MAX_ATTEMPTS - _safe_int(user.password_reset_otp_failed_attempts),
            0,
        )
        if attempts_remaining <= 0:
            _clear_password_reset_state(user)
            user.password_reset_otp_resend_count = 0
            user.password_reset_otp_locked_until = utcnow_naive() + timedelta(
                minutes=settings.AUTH_OTP_LOCK_MINUTES
            )
            _persist_user(db, user)
            raise HTTPException(
                status_code=status.HTTP_423_LOCKED,
                detail=OTP_LOCKED_MESSAGE,
            )

        _persist_user(db, user)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=(
                "Invalid verification code. "
                f"You have {attempts_remaining} attempts remaining."
            ),
        )

    user.hashed_password = get_password_hash(new_password)
    _clear_all_password_reset_state(user)
    _clear_login_otp_state(user)
    _persist_user(db, user)

    return {"message": "Password reset successful. Please sign in with your new password."}


@router.post("/refresh", response_model=TokenResponse)
async def refresh_session(
    request: Request,
    response: Response,
    x_csrf_token: str | None = Header(default=None, alias="X-CSRF-Token"),
    db: Session = Depends(get_db),
):
    """Rotate a valid refresh token and issue a new short-lived access token."""

    await _enforce_auth_rate_limit(
        "auth:refresh",
        request,
        limit=settings.AUTH_REFRESH_RATE_LIMIT_REQUESTS,
    )
    refresh_token = request.cookies.get(settings.REFRESH_TOKEN_COOKIE_NAME)
    csrf_token = request.cookies.get(settings.CSRF_COOKIE_NAME)
    loaded_session = _load_refresh_session(refresh_token, db)
    if (
        loaded_session is not None
        and loaded_session.revoked_at is not None
        and loaded_session.revoked_reason == "rotated"
    ):
        _handle_refresh_token_reuse(
            auth_session=loaded_session,
            db=db,
            request=request,
            response=response,
        )

    auth_session = _validate_refresh_session(
        auth_session=loaded_session,
        csrf_token=csrf_token,
        csrf_header=x_csrf_token,
        db=db,
    )
    user = db.query(User).filter(User.id == auth_session.user_id).first()
    if user is None or not user.is_active:
        auth_session.revoked_at = utcnow_naive()
        auth_session.revoked_reason = "user_unavailable"
        db.add(auth_session)
        db.commit()
        _clear_session_cookies(response)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session user is unavailable.")

    _rotate_refresh_session(
        auth_session=auth_session,
        user=user,
        db=db,
        request=request,
        response=response,
    )
    return _build_token_response(user)


@router.post("/logout", response_model=LogoutResponse)
async def logout_session(
    request: Request,
    response: Response,
    payload: LogoutRequest | None = None,
    x_csrf_token: str | None = Header(default=None, alias="X-CSRF-Token"),
    db: Session = Depends(get_db),
):
    """Revoke the current device refresh token and clear auth cookies."""

    refresh_token = request.cookies.get(settings.REFRESH_TOKEN_COOKIE_NAME)
    csrf_token = request.cookies.get(settings.CSRF_COOKIE_NAME)
    auth_session = _load_refresh_session(refresh_token, db)
    if auth_session is None:
        _clear_session_cookies(response)
        return {"message": "Logged out successfully."}
    if auth_session.revoked_at is not None:
        _clear_session_cookies(response)
        return {"message": "Logged out successfully."}

    _validate_refresh_session(
        auth_session=auth_session,
        csrf_token=csrf_token,
        csrf_header=x_csrf_token,
        db=db,
    )
    user = db.query(User).filter(User.id == auth_session.user_id).first()

    now = utcnow_naive()
    if payload and payload.all_devices:
        sessions = db.query(AuthSession).filter(AuthSession.user_id == auth_session.user_id).all()
        for session in sessions:
            if session.revoked_at is None:
                session.revoked_at = now
                session.revoked_reason = "logout_all_devices"
                db.add(session)
        db.commit()
        _audit_auth_event("logout_all_devices", user=user, session=auth_session, request=request)
    elif auth_session.revoked_at is None:
        auth_session.revoked_at = now
        auth_session.revoked_reason = "logout"
        db.add(auth_session)
        db.commit()
        _audit_auth_event("logout", user=user, session=auth_session, request=request)

    _clear_session_cookies(response)
    return {"message": "Logged out successfully."}


@router.get("/sessions", response_model=AuthSessionListResponse)
async def list_sessions(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List the current user's sessions for device management."""

    _cleanup_expired_auth_sessions(db=db, user_id=current_user.id)
    current_session = _load_refresh_session(request.cookies.get(settings.REFRESH_TOKEN_COOKIE_NAME), db)
    sessions = (
        db.query(AuthSession)
        .filter(AuthSession.user_id == current_user.id)
        .order_by(AuthSession.updated_at.desc())
        .all()
    )
    return {
        "sessions": [
            _serialize_auth_session(session, current_session_id=getattr(current_session, "id", None))
            for session in sessions
        ]
    }


@router.delete("/sessions/{session_id}", response_model=RevokeSessionResponse)
async def revoke_session(
    session_id: int,
    request: Request,
    response: Response,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Revoke a single session belonging to the authenticated user."""

    current_refresh_session = _load_refresh_session(request.cookies.get(settings.REFRESH_TOKEN_COOKIE_NAME), db)
    session = _revoke_single_session(
        db=db,
        user_id=current_user.id,
        session_id=session_id,
        reason="revoked_by_user",
    )

    if current_refresh_session is not None and current_refresh_session.id == session.id:
        _clear_session_cookies(response)

    _audit_auth_event("session_revoked", user=current_user, session=session, request=request, reason="user_requested")
    return {"message": "Session revoked successfully."}


@router.post("/email-test", response_model=EmailTestResponse)
async def send_email_test(current_user: User = Depends(get_current_user)):
    """Send a test email to the current user's registered email address."""

    try:
        delivery_mode = email_service.send_test_email(
            recipient_email=current_user.email,
            recipient_name=current_user.full_name or current_user.username,
        )
    except EmailDeliveryError as exc:
        logger.error(
            "email_test_delivery_failed user_id=%s email=%s error=%s",
            current_user.id,
            current_user.email,
            exc,
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=EMAIL_TEST_DELIVERY_FAILURE_MESSAGE,
        ) from exc

    return {
        "email": current_user.email,
        "delivery_mode": delivery_mode,
        "message": "Test email sent successfully.",
    }


@router.get("/me")
async def get_current_account(current_user: User = Depends(get_current_user)):
    """Get the current authenticated account."""
    return {"user": _serialize_user(current_user)}


@router.put("/me")
async def update_current_account(
    request: UpdateAccountRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Update the current authenticated account."""

    updates: dict[str, str] = {}

    if request.email is not None:
        email = request.email.strip().lower()
        if not email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email cannot be empty",
            )
        updates["email"] = email

    if request.username is not None:
        username = request.username.strip()
        if not username:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Username cannot be empty",
            )
        updates["username"] = username

    if request.full_name is not None:
        updates["full_name"] = request.full_name.strip()

    if not updates:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No account changes were provided",
        )

    duplicate_checks: list = []
    if "email" in updates:
        duplicate_checks.append(User.email == updates["email"])
    if "username" in updates:
        duplicate_checks.append(User.username == updates["username"])

    if duplicate_checks:
        duplicate_filter = duplicate_checks[0]
        for expression in duplicate_checks[1:]:
            duplicate_filter = duplicate_filter | expression

        existing_user = db.query(User).filter(
            duplicate_filter,
            User.id != current_user.id,
        ).first()

        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User with this email or username already exists",
            )

    for field_name, value in updates.items():
        setattr(current_user, field_name, value)

    db.add(current_user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User with this email or username already exists",
        )
    db.refresh(current_user)

    return {
        "message": "Account updated successfully",
        "user": _serialize_user(current_user),
    }


@router.delete("/me")
async def delete_current_account(
    response: Response,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Delete the current authenticated account and owned data."""

    conversations = db.query(Conversation).filter(
        Conversation.user_id == current_user.id
    ).all()
    documents = db.query(Document).filter(Document.user_id == current_user.id).all()
    file_records = db.query(FileRecord).filter(FileRecord.user_id == current_user.id).all()
    chat_sessions = db.query(ChatSession).filter(ChatSession.user_id == current_user.id).all()
    learning_progress = db.query(LearningProgress).filter(
        LearningProgress.user_id == current_user.id
    ).all()
    auth_sessions = db.query(AuthSession).filter(AuthSession.user_id == current_user.id).all()

    for document in documents:
        try:
            document_service.delete_file(document.file_path)
        except RuntimeError as exc:
            logger.warning(
                "account_delete_file_cleanup_failed user_id=%s document_id=%s error=%s",
                current_user.id,
                document.id,
                exc,
            )
        db.delete(document)

    for file_record in file_records:
        try:
            storage_service.delete_file(file_record.storage_path)
        except RuntimeError as exc:
            logger.warning(
                "account_delete_uploaded_file_cleanup_failed user_id=%s file_id=%s error=%s",
                current_user.id,
                file_record.id,
                exc,
            )
        retriever_service.delete_file_chunks(db, file_record.id)
        db.delete(file_record)

    for chat_session in chat_sessions:
        db.delete(chat_session)

    for conversation in conversations:
        db.delete(conversation)

    for item in learning_progress:
        db.delete(item)

    for auth_session in auth_sessions:
        auth_session.revoked_at = utcnow_naive()
        auth_session.revoked_reason = "account_deleted"
        db.add(auth_session)

    db.delete(current_user)
    db.commit()
    _clear_session_cookies(response)

    return {
        "message": "Account deleted successfully",
        "deleted": {
            "conversations": len(conversations),
            "documents": len(documents),
            "files": len(file_records),
            "learning_items": len(learning_progress),
        },
    }
