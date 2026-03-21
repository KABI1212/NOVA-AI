import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from pydantic import BaseModel, EmailStr

from config.database import get_db
from models.conversation import Conversation
from models.document import Document
from models.learning import LearningProgress
from models.user import User
from services.document_service import document_service
from utils.auth import verify_password, get_password_hash, create_access_token
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


class TokenResponse(BaseModel):
    access_token: str
    token_type: str
    user: dict


class UpdateAccountRequest(BaseModel):
    email: EmailStr | None = None
    username: str | None = None
    full_name: str | None = None


def _serialize_user(user: User) -> dict:
    return {
        "id": user.id,
        "email": user.email,
        "username": user.username,
        "full_name": user.full_name,
    }


@router.post("/signup", response_model=TokenResponse)
async def signup(request: SignupRequest, db: Session = Depends(get_db)):
    """Register a new user"""

    email = request.email.strip().lower()
    username = request.username.strip()
    full_name = request.full_name.strip() if request.full_name else ""

    # Check if user already exists
    existing_user = db.query(User).filter(
        (User.email == email) | (User.username == username)
    ).first()

    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User with this email or username already exists"
        )

    # Create new user
    hashed_password = get_password_hash(request.password)

    new_user = User(
        email=email,
        username=username,
        hashed_password=hashed_password,
        full_name=full_name
    )

    db.add(new_user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User with this email or username already exists"
        )
    db.refresh(new_user)

    # Create access token
    access_token = create_access_token(data={"sub": new_user.id})

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": _serialize_user(new_user),
    }


@router.post("/login", response_model=TokenResponse)
async def login(request: LoginRequest, db: Session = Depends(get_db)):
    """Login user"""

    email = request.email.strip().lower()

    # Find user
    user = db.query(User).filter(User.email == email).first()

    if not user or not verify_password(request.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password"
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive"
        )

    # Create access token
    access_token = create_access_token(data={"sub": user.id})

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": _serialize_user(user),
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
