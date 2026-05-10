import hashlib
import hmac
import secrets
import smtplib
import ssl
from datetime import datetime, timedelta
from email.message import EmailMessage

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from config.database import get_db
from config.settings import settings
from models.user import User
from utils.auth import create_access_token, get_password_hash, verify_password

router = APIRouter(prefix="/api/auth", tags=["Authentication"])

_PENDING_CHALLENGES: dict[str, dict] = {}


class SignupRequest(BaseModel):
    email: EmailStr
    username: str
    password: str
    full_name: str = ""


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class OtpVerifyRequest(BaseModel):
    email: EmailStr
    otp: str
    challenge_token: str


class OtpResendRequest(BaseModel):
    email: EmailStr
    challenge_token: str


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    email: EmailStr
    otp: str
    challenge_token: str
    new_password: str


def _utcnow() -> datetime:
    return datetime.utcnow()


def _hash_secret(value: str) -> str:
    payload = f"{settings.SECRET_KEY}:{value}".encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _verify_secret(value: str, expected_hash: str) -> bool:
    return hmac.compare_digest(_hash_secret(value), expected_hash or "")


def _generate_otp() -> str:
    digits = "0123456789"
    return "".join(secrets.choice(digits) for _ in range(settings.AUTH_OTP_LENGTH))


def _mask_email(email: str) -> str:
    local_part, _, domain = (email or "").partition("@")
    if not local_part or not domain:
        return email
    return f"{local_part[:1]}{'*' * max(len(local_part) - 1, 3)}@{domain}"


def _serialize_user(user: User) -> dict:
    return {
        "id": user.id,
        "email": user.email,
        "username": user.username,
        "full_name": user.full_name,
    }


def _token_response(user: User) -> dict:
    return {
        "requires_otp": False,
        "access_token": create_access_token(data={"sub": user.id}),
        "token_type": "bearer",
        "user": _serialize_user(user),
    }


def _configured_from_address() -> str:
    return (settings.EMAIL_FROM or "").strip() or (settings.EMAIL_FROM_ADDRESS or "").strip()


def _configured_smtp_username() -> str:
    return (settings.SMTP_USER or "").strip() or (settings.SMTP_USERNAME or "").strip()


def _configured_smtp_password() -> str:
    return (settings.SMTP_PASS or "").strip() or (settings.SMTP_PASSWORD or "").strip()


def _send_otp_email(*, recipient_email: str, otp_code: str, subject: str, intro: str) -> None:
    host = (settings.SMTP_HOST or "").strip()
    from_address = _configured_from_address()
    smtp_username = _configured_smtp_username()
    smtp_password = _configured_smtp_password()

    if not host or not from_address or not smtp_username or not smtp_password:
        raise RuntimeError("Email delivery is not configured.")

    if host.lower() == "smtp.gmail.com":
        normalized_password = smtp_password.replace(" ", "")
        if len(normalized_password) == 16:
            smtp_password = normalized_password

    from_name = (settings.EMAIL_FROM_NAME or "NOVA AI").strip()
    from_header = f"{from_name} <{from_address}>"
    expiry = settings.AUTH_OTP_EXPIRE_MINUTES
    text_body = (
        f"Hi,\n\n{intro}\n\n"
        f"Verification code: {otp_code}\n\n"
        f"This code expires in {expiry} minutes.\n\n"
        "If you did not request this, you can ignore this email."
    )
    html_body = f"""
<html>
  <body style="font-family:Arial,sans-serif;background:#f1f5f9;margin:0;padding:24px;color:#0f172a;">
    <div style="max-width:560px;margin:0 auto;background:#ffffff;border:1px solid #cbd5e1;border-radius:16px;overflow:hidden;">
      <div style="background:#0f172a;color:#ffffff;padding:22px 26px;">
        <div style="font-size:13px;letter-spacing:0.16em;text-transform:uppercase;color:#bfdbfe;font-weight:700;">NOVA AI</div>
        <h1 style="margin:10px 0 0;font-size:26px;line-height:1.2;">Your verification code</h1>
      </div>
      <div style="padding:26px;">
        <p style="font-size:15px;line-height:1.7;margin:0 0 18px;">{intro}</p>
        <div style="text-align:center;background:#1d4ed8;color:#ffffff;border-radius:14px;padding:22px;margin:0 0 18px;">
          <div style="font-size:36px;font-weight:800;letter-spacing:10px;">{otp_code}</div>
        </div>
        <p style="font-size:14px;line-height:1.6;margin:0;color:#475569;">This code expires in {expiry} minutes.</p>
      </div>
    </div>
  </body>
</html>
""".strip()

    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = from_header
    message["To"] = recipient_email
    reply_to = (settings.EMAIL_REPLY_TO or "").strip()
    if reply_to:
        message["Reply-To"] = reply_to
    message.set_content(text_body)
    message.add_alternative(html_body, subtype="html")

    smtp_factory = smtplib.SMTP_SSL if settings.SMTP_USE_SSL else smtplib.SMTP
    context = ssl.create_default_context()
    with smtp_factory(host, settings.SMTP_PORT, timeout=settings.SMTP_TIMEOUT_SECONDS) as client:
        if not settings.SMTP_USE_SSL and settings.SMTP_USE_TLS:
            client.starttls(context=context)
        client.login(smtp_username, smtp_password)
        client.send_message(message, from_addr=from_address, to_addrs=[recipient_email])


def _issue_challenge(*, user: User, purpose: str) -> dict:
    otp_code = _generate_otp()
    challenge_token = secrets.token_urlsafe(32)
    expires_at = _utcnow() + timedelta(minutes=settings.AUTH_OTP_EXPIRE_MINUTES)
    email = user.email.strip().lower()

    intro = (
        "Use this code to reset your NOVA AI password."
        if purpose == "password_reset"
        else "Use this code to continue signing in to NOVA AI."
    )
    subject = (
        "NOVA AI password reset code"
        if purpose == "password_reset"
        else "NOVA AI verification code"
    )

    _send_otp_email(
        recipient_email=email,
        otp_code=otp_code,
        subject=subject,
        intro=intro,
    )

    _PENDING_CHALLENGES[email] = {
        "otp_hash": _hash_secret(otp_code),
        "challenge_hash": _hash_secret(challenge_token),
        "expires_at": expires_at,
        "purpose": purpose,
    }

    return {
        "requires_otp": True,
        "challenge_token": challenge_token,
        "email": email,
        "masked_email": _mask_email(email),
        "otp_expires_at": expires_at,
        "delivery_mode": "email",
        "message": f"A 6-digit verification code has been sent to {_mask_email(email)}.",
    }


def _validate_challenge(*, email: str, otp: str, challenge_token: str, purpose: str) -> None:
    challenge = _PENDING_CHALLENGES.get(email)
    if not challenge or challenge.get("purpose") != purpose:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No active verification request. Please try again.",
        )
    if challenge["expires_at"] < _utcnow():
        _PENDING_CHALLENGES.pop(email, None)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Verification code expired. Please request a new code.",
        )
    if not _verify_secret(challenge_token, challenge["challenge_hash"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Verification request is invalid. Please try again.",
        )
    if not _verify_secret(otp, challenge["otp_hash"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid verification code.",
        )


@router.post("/signup")
async def signup(request: SignupRequest, db: Session = Depends(get_db)):
    """Create an unverified account and send an email OTP."""

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

    try:
        return _issue_challenge(user=new_user, purpose="login")
    except Exception as exc:
        db.delete(new_user)
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="We couldn't send the verification email right now. Please try again shortly.",
        ) from exc


@router.post("/login")
async def login(request: LoginRequest, db: Session = Depends(get_db)):
    """Validate password and sign in existing registered users."""

    email = request.email.strip().lower()
    user = db.query(User).filter(User.email == email).first()

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
        user.is_verified = True
        db.add(user)
        db.commit()
        db.refresh(user)

    return _token_response(user)


@router.post("/login/otp/verify")
async def verify_login_otp(request: OtpVerifyRequest, db: Session = Depends(get_db)):
    email = request.email.strip().lower()
    otp = "".join(character for character in request.otp if character.isdigit())
    user = db.query(User).filter(User.email == email).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid verification request.")

    _validate_challenge(
        email=email,
        otp=otp,
        challenge_token=request.challenge_token.strip(),
        purpose="login",
    )
    _PENDING_CHALLENGES.pop(email, None)
    user.is_verified = True
    db.add(user)
    db.commit()
    db.refresh(user)
    return _token_response(user)


@router.post("/login/otp/resend")
async def resend_login_otp(request: OtpResendRequest, db: Session = Depends(get_db)):
    email = request.email.strip().lower()
    challenge = _PENDING_CHALLENGES.get(email)
    if not challenge or not _verify_secret(request.challenge_token.strip(), challenge["challenge_hash"]):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid verification request.")
    user = db.query(User).filter(User.email == email).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid verification request.")
    return _issue_challenge(user=user, purpose=challenge["purpose"])


@router.post("/password/forgot")
async def forgot_password(request: ForgotPasswordRequest, db: Session = Depends(get_db)):
    email = request.email.strip().lower()
    user = db.query(User).filter(User.email == email).first()
    if not user:
        return {"message": "If an account exists for that email, a password reset code has been sent."}
    try:
        response = _issue_challenge(user=user, purpose="password_reset")
        response["message"] = "A password reset code has been sent to your email address."
        return response
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="We couldn't send the password reset code right now. Please try again shortly.",
        ) from exc


@router.post("/password/reset")
async def reset_password(request: ResetPasswordRequest, db: Session = Depends(get_db)):
    email = request.email.strip().lower()
    otp = "".join(character for character in request.otp if character.isdigit())
    user = db.query(User).filter(User.email == email).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No account found with this email address.")
    if len(request.new_password or "") < 8:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="New password must be at least 8 characters.")

    _validate_challenge(
        email=email,
        otp=otp,
        challenge_token=request.challenge_token.strip(),
        purpose="password_reset",
    )
    _PENDING_CHALLENGES.pop(email, None)
    user.hashed_password = get_password_hash(request.new_password)
    db.add(user)
    db.commit()
    return {"message": "Password reset successful. Please sign in with your new password."}
