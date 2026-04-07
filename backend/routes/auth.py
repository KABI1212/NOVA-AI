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


class TokenResponse(BaseModel):
    requires_otp: Literal[False] = False
    access_token: str
    token_type: str
    user: dict


class LoginChallengeResponse(BaseModel):
    requires_otp: Literal[True] = True
    challenge_token: str
    email: EmailStr
    otp_expires_at: datetime
    delivery_mode: Literal["email", "log"]
    dev_otp_code: str | None = None
    message: str


class UpdateAccountRequest(BaseModel):
    email: EmailStr | None = None
    username: str | None = None
    full_name: str | None = None


class EmailTestResponse(BaseModel):
    email: EmailStr
    delivery_mode: Literal["email", "log"]
    message: str


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


def _clear_login_otp_state(user: User) -> None:
    user.login_otp_code_hash = None
    user.login_otp_expires_at = None
    user.login_otp_sent_at = None
    user.login_otp_challenge_hash = None


def _persist_user(db: Session, user: User) -> None:
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise
    db.refresh(user)


def _issue_login_otp(user: User, db: Session) -> dict:
    otp_code = generate_numeric_otp()
    challenge_token = generate_login_challenge_token()
    expires_at = utcnow_naive() + timedelta(minutes=settings.AUTH_OTP_EXPIRE_MINUTES)

    user.login_otp_code_hash = hash_secret_value(otp_code)
    user.login_otp_challenge_hash = hash_secret_value(challenge_token)
    user.login_otp_expires_at = expires_at
    user.login_otp_sent_at = utcnow_naive()

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
        _clear_login_otp_state(user)
        _persist_user(db, user)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc

    return {
        "requires_otp": True,
        "challenge_token": challenge_token,
        "email": user.email,
        "otp_expires_at": expires_at,
        "delivery_mode": delivery_mode,
        "dev_otp_code": otp_code if delivery_mode == "log" and settings.DEBUG else None,
        "message": (
            "A verification code has been sent to your email address."
            if delivery_mode == "email"
            else "Email delivery is not configured. The verification code was logged by the backend for local development."
        ),
    }


def _load_user_by_email(email: str, db: Session) -> User | None:
    return db.query(User).filter(User.email == email).first()


def _validate_pending_login(
    *,
    user: User | None,
    challenge_token: str,
    db: Session,
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

    if user.login_otp_expires_at < utcnow_naive():
        _clear_login_otp_state(user)
        _persist_user(db, user)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Verification code expired. Please sign in again.",
        )

    return user


@router.post(
    "/signup",
    response_model=LoginChallengeResponse,
    status_code=status.HTTP_201_CREATED,
)
async def signup(request: SignupRequest, db: Session = Depends(get_db)):
    """Register a new user and require OTP verification before sign-in."""

    email = request.email.strip().lower()
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

    return _issue_login_otp(new_user, db)


@router.post("/login", response_model=TokenResponse | LoginChallengeResponse)
async def login(request: LoginRequest, db: Session = Depends(get_db)):
    """Validate credentials and require OTP until the account has been verified."""

    email = request.email.strip().lower()
    user = _load_user_by_email(email, db)

    if not user or not verify_password(request.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive",
        )

    if not user.is_verified:
        return _issue_login_otp(user, db)

    requires_persist = False
    if (
        user.login_otp_code_hash
        or user.login_otp_challenge_hash
        or user.login_otp_expires_at is not None
        or user.login_otp_sent_at is not None
    ):
        _clear_login_otp_state(user)
        requires_persist = True

    if requires_persist:
        _persist_user(db, user)

    return _build_token_response(user)


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
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid verification code.",
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
    )

    return _issue_login_otp(user, db)


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
            detail=str(exc),
        ) from exc

    return {
        "email": current_user.email,
        "delivery_mode": delivery_mode,
        "message": (
            "Test email sent successfully."
            if delivery_mode == "email"
            else "Email delivery is not configured. The test email was logged by the backend for local development."
        ),
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
