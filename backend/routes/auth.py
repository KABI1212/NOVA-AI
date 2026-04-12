import logging
from datetime import datetime, timedelta
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr
try:
    from sqlalchemy.exc import IntegrityError
except ImportError:
    class IntegrityError(Exception):
        """Fallback when SQLAlchemy is not installed."""

try:
    from sqlalchemy.orm import Session
except ImportError:
    Session = Any

from config.database import get_db
from config.settings import settings
from models.conversation import Conversation
from models.document import Document
from models.learning import LearningProgress
from models.user import User
from services.document_service import document_service
from services.email_service import EmailDeliveryError, email_service
from utils.auth import (
    create_access_token,
    generate_login_challenge_token,
    generate_numeric_otp,
    get_password_hash,
    hash_secret_value,
    utcnow_naive,
    verify_password,
    verify_secret_value,
)
from utils.dependencies import get_current_user

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
OTP_EXPIRED_MESSAGE = "Your code has expired. Click 'Resend Code' to get a new one."
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


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


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


class TokenResponse(BaseModel):
    requires_otp: Literal[False] = False
    access_token: str
    token_type: str
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


class EmailTestResponse(BaseModel):
    email: EmailStr
    delivery_mode: Literal["email"]
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


def _build_token_response(user: User) -> dict:
    access_token = create_access_token(data={"sub": user.id})
    return {
        "requires_otp": False,
        "access_token": access_token,
        "token_type": "bearer",
        "user": _serialize_user(user),
    }


def _password_only_fallback_enabled() -> bool:
    return bool(settings.AUTH_ALLOW_PASSWORD_ONLY_FALLBACK)


def _should_require_email_verification() -> bool:
    return not _password_only_fallback_enabled() or email_service.can_send_real_email()


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


def _restore_login_otp_state(user: User, snapshot: dict[str, Any]) -> None:
    for field_name, value in snapshot.items():
        setattr(user, field_name, value)


def _build_password_only_auth_response(
    user: User,
    db: Session,
    *,
    mark_verified: bool,
) -> dict:
    requires_persist = False

    if mark_verified and not user.is_verified:
        user.is_verified = True
        requires_persist = True

    if _has_login_otp_state(user):
        _clear_login_otp_state(user)
        requires_persist = True

    if requires_persist:
        _persist_user(db, user)

    return _build_token_response(user)


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


def _issue_login_otp(user: User, db: Session, *, is_resend: bool = False) -> dict:
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
        delivery_mode = email_service.send_login_otp(
            recipient_email=user.email,
            otp_code=otp_code,
            recipient_name=user.full_name or user.username,
        )
    except EmailDeliveryError as exc:
        logger.error(
            "login_otp_email_delivery_failed user_id=%s email=%s error=%s",
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


def _issue_password_reset_otp(user: User, db: Session) -> dict:
    otp_code = generate_numeric_otp()
    challenge_token = generate_login_challenge_token()
    expires_at = utcnow_naive() + timedelta(minutes=settings.AUTH_OTP_EXPIRE_MINUTES)

    user.password_reset_otp_code_hash = hash_secret_value(otp_code)
    user.password_reset_otp_challenge_hash = hash_secret_value(challenge_token)
    user.password_reset_otp_expires_at = expires_at
    user.password_reset_otp_sent_at = utcnow_naive()

    _persist_user(db, user)

    try:
        delivery_mode = email_service.send_password_reset_otp(
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
        _clear_password_reset_state(user)
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
    return db.query(User).filter(User.email == email).first()


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
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=OTP_EXPIRED_MESSAGE,
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
async def signup(request: SignupRequest, db: Session = Depends(get_db)):
    """Register a new user and require OTP verification before sign-in."""

    email = request.email.strip().lower()
    username = request.username.strip()
    full_name = request.full_name.strip() if request.full_name else ""
    requires_email_verification = _should_require_email_verification()

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
        is_verified=not requires_email_verification,
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

    if not requires_email_verification:
        logger.info(
            "signup_password_only_fallback_enabled user_id=%s email=%s",
            new_user.id,
            new_user.email,
        )
        return _build_token_response(new_user)

    try:
        return _issue_login_otp(new_user, db)
    except HTTPException as exc:
        if exc.status_code == status.HTTP_503_SERVICE_UNAVAILABLE:
            if _password_only_fallback_enabled():
                logger.warning(
                    "signup_otp_delivery_failed_password_only_fallback user_id=%s email=%s",
                    new_user.id,
                    new_user.email,
                )
                return _build_password_only_auth_response(
                    new_user,
                    db,
                    mark_verified=True,
                )
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
async def login(request: LoginRequest, db: Session = Depends(get_db)):
    """Validate credentials and require OTP until the account has been verified."""

    email = request.email.strip().lower()
    user = _load_user_by_email(email, db)

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

    if not user.is_verified:
        if not _should_require_email_verification():
            logger.info(
                "login_password_only_fallback_enabled user_id=%s email=%s",
                user.id,
                user.email,
            )
            return _build_password_only_auth_response(
                user,
                db,
                mark_verified=True,
            )

        try:
            return _issue_login_otp(user, db)
        except HTTPException as exc:
            if (
                exc.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
                and _password_only_fallback_enabled()
            ):
                logger.warning(
                    "login_otp_delivery_failed_password_only_fallback user_id=%s email=%s",
                    user.id,
                    user.email,
                )
                return _build_password_only_auth_response(
                    user,
                    db,
                    mark_verified=True,
                )
            raise

    return _build_password_only_auth_response(
        user,
        db,
        mark_verified=False,
    )


@router.post("/login/otp/verify", response_model=TokenResponse)
async def verify_login_otp(
    request: LoginOtpVerifyRequest,
    db: Session = Depends(get_db),
):
    """Verify a pending login OTP and return the authenticated session token."""

    email = request.email.strip().lower()
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

    _clear_login_otp_state(user)
    user.is_verified = True
    _persist_user(db, user)

    return _build_token_response(user)


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

    return _issue_login_otp(user, db, is_resend=True)


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

    return _issue_password_reset_otp(user, db)


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
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid verification code.",
        )

    user.hashed_password = get_password_hash(new_password)
    _clear_password_reset_state(user)
    _clear_login_otp_state(user)
    _persist_user(db, user)

    return {"message": "Password reset successful. Please sign in with your new password."}


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
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Delete the current authenticated account and owned data."""

    conversations = db.query(Conversation).filter(
        Conversation.user_id == current_user.id
    ).all()
    documents = db.query(Document).filter(Document.user_id == current_user.id).all()
    learning_progress = db.query(LearningProgress).filter(
        LearningProgress.user_id == current_user.id
    ).all()

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

    for conversation in conversations:
        db.delete(conversation)

    for item in learning_progress:
        db.delete(item)

    db.delete(current_user)
    db.commit()

    return {
        "message": "Account deleted successfully",
        "deleted": {
            "conversations": len(conversations),
            "documents": len(documents),
            "learning_items": len(learning_progress),
        },
    }
