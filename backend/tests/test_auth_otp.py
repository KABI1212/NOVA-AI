from __future__ import annotations

import asyncio
from datetime import timedelta

import pytest
from fastapi import HTTPException

import routes.auth as auth_module
from models.user import User


def _matches_filter(document: dict, payload: dict) -> bool:
    if not document:
        return True

    if "$and" in document:
        return all(_matches_filter(item, payload) for item in document["$and"])

    if "$or" in document:
        return any(_matches_filter(item, payload) for item in document["$or"])

    for key, value in document.items():
        candidate = payload.get(key)
        if isinstance(value, dict):
            if "$ne" in value and candidate == value["$ne"]:
                return False
        elif candidate != value:
            return False

    return True


class _FakeQuery:
    def __init__(self, session: "_FakeSession", model) -> None:
        self.session = session
        self.model = model
        self.conditions = []

    def filter(self, *conditions):
        self.conditions.extend(condition for condition in conditions if condition is not None)
        return self

    def _records(self):
        if self.model is not User:
            return []
        return self.session.users

    def _filtered_records(self):
        if not self.conditions:
            return list(self._records())

        filter_doc = {"$and": [condition.to_mongo() for condition in self.conditions]}
        matched = []
        for obj in self._records():
            payload = {
                field_name: getattr(obj, field_name, None)
                for field_name in type(obj).__fields__
            }
            if _matches_filter(filter_doc, payload):
                matched.append(obj)
        return matched

    def first(self):
        records = self._filtered_records()
        return records[0] if records else None

    def all(self):
        return self._filtered_records()


class _FakeSession:
    def __init__(self, users: list[User] | None = None) -> None:
        self.users = users or []

    def query(self, model):
        return _FakeQuery(self, model)

    def add(self, obj) -> None:
        if isinstance(obj, User) and obj not in self.users:
            self.users.append(obj)

    def commit(self) -> None:
        return None

    def refresh(self, obj) -> None:
        return None

    def rollback(self) -> None:
        return None


def _make_user() -> User:
    return User(
        id=1,
        email="otp.user@example.com",
        username="otp-user",
        hashed_password=auth_module.get_password_hash("Sup3rSecret!"),
        full_name="OTP User",
        is_active=True,
    )


def test_signup_creates_user_and_requires_verification(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db = _FakeSession()
    sent_email: dict = {}

    def fake_send_login_otp(*, recipient_email: str, otp_code: str, recipient_name: str = "") -> str:
        sent_email.update(
            {
                "recipient_email": recipient_email,
                "otp_code": otp_code,
                "recipient_name": recipient_name,
            }
        )
        return "email"

    async def scenario() -> None:
        response = await auth_module.signup(
            auth_module.SignupRequest(
                email="New.User@Example.com",
                username="new-user",
                password="Sup3rSecret!",
                full_name="New User",
            ),
            db=db,
        )

        assert response["requires_otp"] is True
        assert response["email"] == "new.user@example.com"
        assert response["delivery_mode"] == "email"
        assert sent_email["recipient_email"] == "new.user@example.com"
        assert auth_module.verify_secret_value(
            sent_email["otp_code"],
            db.users[0].login_otp_code_hash,
        )
        assert len(db.users) == 1
        assert db.users[0].is_verified is False

    monkeypatch.setattr(auth_module.email_service, "send_login_otp", fake_send_login_otp)
    asyncio.run(scenario())


def test_signup_verification_completes_account_activation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db = _FakeSession()

    async def scenario() -> None:
        signup_response, sent_email = await _issue_signup_challenge(monkeypatch, db)

        verify_response = await auth_module.verify_login_otp(
            auth_module.LoginOtpVerifyRequest(
                email=signup_response["email"],
                otp=sent_email["otp_code"],
                challenge_token=signup_response["challenge_token"],
            ),
            db=db,
        )

        assert verify_response["requires_otp"] is False
        assert verify_response["access_token"]
        assert verify_response["user"]["email"] == "new.user@example.com"
        assert db.users[0].is_verified is True

    asyncio.run(scenario())


async def _issue_login_challenge(
    monkeypatch: pytest.MonkeyPatch,
    db: _FakeSession,
    user: User,
    *,
    delivery_mode: str = "email",
) -> tuple[dict, dict]:
    sent_email: dict = {}

    def fake_send_login_otp(*, recipient_email: str, otp_code: str, recipient_name: str = "") -> str:
        sent_email.update(
            {
                "recipient_email": recipient_email,
                "otp_code": otp_code,
                "recipient_name": recipient_name,
            }
        )
        return delivery_mode

    monkeypatch.setattr(auth_module.email_service, "send_login_otp", fake_send_login_otp)

    response = auth_module._issue_login_otp(user, db)

    return response, sent_email


async def _issue_signup_challenge(
    monkeypatch: pytest.MonkeyPatch,
    db: _FakeSession,
    *,
    delivery_mode: str = "email",
) -> tuple[dict, dict]:
    sent_email: dict = {}

    def fake_send_login_otp(*, recipient_email: str, otp_code: str, recipient_name: str = "") -> str:
        sent_email.update(
            {
                "recipient_email": recipient_email,
                "otp_code": otp_code,
                "recipient_name": recipient_name,
            }
        )
        return delivery_mode

    monkeypatch.setattr(auth_module.email_service, "send_login_otp", fake_send_login_otp)

    response = await auth_module.signup(
        auth_module.SignupRequest(
            email="New.User@Example.com",
            username="new-user",
            password="Sup3rSecret!",
            full_name="New User",
        ),
        db=db,
    )

    return response, sent_email


def test_issue_login_otp_returns_challenge_and_persists_pending_state(monkeypatch: pytest.MonkeyPatch) -> None:
    user = _make_user()
    db = _FakeSession([user])

    async def scenario() -> None:
        response, sent_email = await _issue_login_challenge(monkeypatch, db, user)

        assert response["requires_otp"] is True
        assert response["email"] == user.email
        assert response["delivery_mode"] == "email"
        assert response["dev_otp_code"] is None
        assert len(sent_email["otp_code"]) == auth_module.settings.AUTH_OTP_LENGTH
        assert sent_email["recipient_email"] == user.email
        assert auth_module.verify_secret_value(
            sent_email["otp_code"],
            user.login_otp_code_hash,
        )
        assert auth_module.verify_secret_value(
            response["challenge_token"],
            user.login_otp_challenge_hash,
        )
        assert user.login_otp_expires_at > auth_module.utcnow_naive()

    asyncio.run(scenario())


def test_issue_login_otp_returns_debug_otp_when_delivery_falls_back_to_log_mode(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user = _make_user()
    db = _FakeSession([user])
    monkeypatch.setattr(auth_module.settings, "DEBUG", True)

    async def scenario() -> None:
        response, sent_email = await _issue_login_challenge(
            monkeypatch,
            db,
            user,
            delivery_mode="log",
        )

        assert response["delivery_mode"] == "log"
        assert response["dev_otp_code"] == sent_email["otp_code"]
        assert "logged by the backend" in response["message"].lower()

    asyncio.run(scenario())


def test_login_returns_token_without_requiring_otp_for_verified_user() -> None:
    user = _make_user()
    user.is_verified = True
    db = _FakeSession([user])

    async def scenario() -> None:
        response = await auth_module.login(
            auth_module.LoginRequest(email=user.email, password="Sup3rSecret!"),
            db=db,
        )

        assert response["requires_otp"] is False
        assert response["access_token"]
        assert response["user"]["email"] == user.email

    asyncio.run(scenario())


def test_login_requires_otp_for_unverified_user(monkeypatch: pytest.MonkeyPatch) -> None:
    user = _make_user()
    user.is_verified = False
    db = _FakeSession([user])
    sent_email: dict = {}

    def fake_send_login_otp(*, recipient_email: str, otp_code: str, recipient_name: str = "") -> str:
        sent_email.update(
            {
                "recipient_email": recipient_email,
                "otp_code": otp_code,
                "recipient_name": recipient_name,
            }
        )
        return "email"

    async def scenario() -> None:
        response = await auth_module.login(
            auth_module.LoginRequest(email=user.email, password="Sup3rSecret!"),
            db=db,
        )

        assert response["requires_otp"] is True
        assert response["email"] == user.email
        assert response["delivery_mode"] == "email"
        assert sent_email["recipient_email"] == user.email
        assert auth_module.verify_secret_value(
            sent_email["otp_code"],
            user.login_otp_code_hash,
        )
        assert auth_module.verify_secret_value(
            response["challenge_token"],
            user.login_otp_challenge_hash,
        )
        assert user.is_verified is False

    monkeypatch.setattr(auth_module.email_service, "send_login_otp", fake_send_login_otp)
    asyncio.run(scenario())


def test_verify_login_otp_returns_token_and_clears_pending_state(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user = _make_user()
    db = _FakeSession([user])

    async def scenario() -> None:
        response, sent_email = await _issue_login_challenge(monkeypatch, db, user)

        verify_response = await auth_module.verify_login_otp(
            auth_module.LoginOtpVerifyRequest(
                email=user.email,
                otp=sent_email["otp_code"],
                challenge_token=response["challenge_token"],
            ),
            db=db,
        )

        assert verify_response["requires_otp"] is False
        assert verify_response["access_token"]
        assert verify_response["user"]["email"] == user.email
        assert user.is_verified is True
        assert user.login_otp_code_hash is None
        assert user.login_otp_challenge_hash is None
        assert user.login_otp_expires_at is None

    asyncio.run(scenario())


def test_verify_login_otp_rejects_invalid_code(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user = _make_user()
    db = _FakeSession([user])

    async def scenario() -> None:
        response, _sent_email = await _issue_login_challenge(monkeypatch, db, user)

        with pytest.raises(HTTPException) as exc_info:
            await auth_module.verify_login_otp(
                auth_module.LoginOtpVerifyRequest(
                    email=user.email,
                    otp="000000",
                    challenge_token=response["challenge_token"],
                ),
                db=db,
            )

        assert exc_info.value.status_code == 401
        assert exc_info.value.detail == "Invalid verification code."
        assert user.login_otp_code_hash is not None
        assert user.login_otp_challenge_hash is not None

    asyncio.run(scenario())


def test_verify_login_otp_rejects_expired_code_and_clears_pending_state(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user = _make_user()
    db = _FakeSession([user])

    async def scenario() -> None:
        response, sent_email = await _issue_login_challenge(monkeypatch, db, user)
        user.login_otp_expires_at = auth_module.utcnow_naive() - timedelta(seconds=1)

        with pytest.raises(HTTPException) as exc_info:
            await auth_module.verify_login_otp(
                auth_module.LoginOtpVerifyRequest(
                    email=user.email,
                    otp=sent_email["otp_code"],
                    challenge_token=response["challenge_token"],
                ),
                db=db,
            )

        assert exc_info.value.status_code == 401
        assert exc_info.value.detail == "Verification code expired. Please sign in again."
        assert user.login_otp_code_hash is None
        assert user.login_otp_challenge_hash is None
        assert user.login_otp_expires_at is None

    asyncio.run(scenario())


def test_send_email_test_uses_current_user_email(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user = _make_user()
    sent_email: dict = {}

    def fake_send_test_email(*, recipient_email: str, recipient_name: str = "") -> str:
        sent_email["recipient_email"] = recipient_email
        sent_email["recipient_name"] = recipient_name
        return "email"

    monkeypatch.setattr(auth_module.email_service, "send_test_email", fake_send_test_email)

    async def scenario() -> None:
        response = await auth_module.send_email_test(current_user=user)

        assert response["email"] == user.email
        assert response["delivery_mode"] == "email"
        assert sent_email["recipient_email"] == user.email
        assert sent_email["recipient_name"] == user.full_name

    asyncio.run(scenario())
