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

    def delete(self, obj) -> None:
        if isinstance(obj, User) and obj in self.users:
            self.users.remove(obj)

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
        assert response["masked_email"] == auth_module._mask_email("new.user@example.com")
        assert response["delivery_mode"] == "email"
        assert response["resend_attempts_remaining"] == auth_module.settings.AUTH_OTP_MAX_RESEND_ATTEMPTS
        assert response["otp_attempts_remaining"] == auth_module.settings.AUTH_OTP_MAX_ATTEMPTS
        assert "dev_otp_code" not in response
        assert sent_email["recipient_email"] == "new.user@example.com"
        assert auth_module.verify_secret_value(
            sent_email["otp_code"],
            db.users[0].login_otp_code_hash,
        )
        assert len(db.users) == 1
        assert db.users[0].is_verified is False

    monkeypatch.setattr(auth_module.email_service, "send_login_otp", fake_send_login_otp)
    asyncio.run(scenario())


@pytest.mark.parametrize(
    ("username", "password"),
    [
        ("  ", "Sup3rSecret!"),
        ("ab", "Sup3rSecret!"),
        ("bad username", "Sup3rSecret!"),
        ("new-user", "short"),
    ],
)
def test_signup_request_rejects_invalid_credentials(username: str, password: str) -> None:
    with pytest.raises(ValueError):
        auth_module.SignupRequest(
            email="new.user@example.com",
            username=username,
            password=password,
            full_name="New User",
        )


def test_signup_can_include_debug_otp_when_explicitly_enabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db = _FakeSession()
    sent_email: dict = {}

    def fake_send_login_otp(*, recipient_email: str, otp_code: str, recipient_name: str = "") -> str:
        sent_email["otp_code"] = otp_code
        return "email"

    async def scenario() -> None:
        response = await auth_module.signup(
            auth_module.SignupRequest(
                email="debug.user@example.com",
                username="debug-user",
                password="Sup3rSecret!",
                full_name="Debug User",
            ),
            db=db,
        )

        assert response["requires_otp"] is True
        assert response["dev_otp_code"] == sent_email["otp_code"]

    monkeypatch.setattr(auth_module.settings, "DEBUG", True)
    monkeypatch.setattr(auth_module.settings, "AUTH_EXPOSE_DEBUG_OTP", True)
    monkeypatch.setattr(auth_module.email_service, "send_login_otp", fake_send_login_otp)
    asyncio.run(scenario())


def test_signup_cleans_up_user_when_otp_delivery_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db = _FakeSession()

    def fake_send_login_otp(*, recipient_email: str, otp_code: str, recipient_name: str = "") -> str:
        raise auth_module.EmailDeliveryError("SMTP could not deliver the verification email.")

    async def scenario() -> None:
        with pytest.raises(HTTPException) as exc_info:
            await auth_module.signup(
                auth_module.SignupRequest(
                    email="New.User@Example.com",
                    username="new-user",
                    password="Sup3rSecret!",
                    full_name="New User",
                ),
                db=db,
            )

        assert exc_info.value.status_code == 503
        assert exc_info.value.detail == auth_module.EMAIL_DELIVERY_FAILURE_MESSAGE
        assert db.users == []

    monkeypatch.setattr(auth_module.email_service, "send_login_otp", fake_send_login_otp)
    asyncio.run(scenario())


def test_signup_does_not_bypass_otp_when_fallback_is_enabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db = _FakeSession()

    def fake_send_login_otp(*, recipient_email: str, otp_code: str, recipient_name: str = "") -> str:
        raise auth_module.EmailDeliveryError("SMTP could not deliver the verification email.")

    async def scenario() -> None:
        with pytest.raises(HTTPException) as exc_info:
            await auth_module.signup(
                auth_module.SignupRequest(
                    email="New.User@Example.com",
                    username="new-user",
                    password="Sup3rSecret!",
                    full_name="New User",
                ),
                db=db,
            )

        assert exc_info.value.status_code == 503
        assert exc_info.value.detail == auth_module.EMAIL_DELIVERY_FAILURE_MESSAGE
        assert db.users == []

    monkeypatch.setattr(
        auth_module.settings,
        "AUTH_ALLOW_PASSWORD_ONLY_FALLBACK",
        True,
    )
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
        assert response["masked_email"] == auth_module._mask_email(user.email)
        assert response["delivery_mode"] == "email"
        assert response["resend_attempts_remaining"] == auth_module.settings.AUTH_OTP_MAX_RESEND_ATTEMPTS
        assert response["otp_attempts_remaining"] == auth_module.settings.AUTH_OTP_MAX_ATTEMPTS
        assert "dev_otp_code" not in response
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


def test_issue_login_otp_never_returns_raw_otp(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user = _make_user()
    db = _FakeSession([user])

    async def scenario() -> None:
        response, _sent_email = await _issue_login_challenge(monkeypatch, db, user)

        assert response["delivery_mode"] == "email"
        assert "dev_otp_code" not in response

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


def test_login_marks_existing_unverified_user_verified_without_otp() -> None:
    user = _make_user()
    user.is_verified = False
    db = _FakeSession([user])

    async def scenario() -> None:
        response = await auth_module.login(
            auth_module.LoginRequest(email=user.email, password="Sup3rSecret!"),
            db=db,
        )

        assert response["requires_otp"] is False
        assert response["access_token"]
        assert response["user"]["email"] == user.email
        assert user.is_verified is True
        assert user.login_otp_code_hash is None
        assert user.login_otp_challenge_hash is None

    asyncio.run(scenario())


def test_login_does_not_send_email_when_fallback_is_enabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user = _make_user()
    user.is_verified = False
    db = _FakeSession([user])

    def fake_send_login_otp(*, recipient_email: str, otp_code: str, recipient_name: str = "") -> str:
        raise auth_module.EmailDeliveryError("SMTP could not deliver the verification email.")

    async def scenario() -> None:
        response = await auth_module.login(
            auth_module.LoginRequest(email=user.email, password="Sup3rSecret!"),
            db=db,
        )

        assert response["requires_otp"] is False
        assert response["access_token"]
        assert user.is_verified is True
        assert user.login_otp_code_hash is None
        assert user.login_otp_challenge_hash is None

    monkeypatch.setattr(
        auth_module.settings,
        "AUTH_ALLOW_PASSWORD_ONLY_FALLBACK",
        True,
    )
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
        assert exc_info.value.detail == "Incorrect code. Please try again. You have 2 attempts remaining."
        assert user.login_otp_failed_attempts == 1
        assert user.login_otp_code_hash is not None
        assert user.login_otp_challenge_hash is not None

    asyncio.run(scenario())


def test_verify_login_otp_rejects_expired_code_without_clearing_pending_state(
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
        assert exc_info.value.detail == auth_module.OTP_EXPIRED_MESSAGE
        assert user.login_otp_code_hash is not None
        assert user.login_otp_challenge_hash is not None
        assert user.login_otp_expires_at is not None

    asyncio.run(scenario())


def test_verify_login_otp_locks_after_three_failed_attempts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user = _make_user()
    db = _FakeSession([user])

    async def scenario() -> None:
        response, _sent_email = await _issue_login_challenge(monkeypatch, db, user)

        for expected_remaining in [2, 1]:
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
            assert f"{expected_remaining} attempts remaining" in exc_info.value.detail

        with pytest.raises(HTTPException) as exc_info:
            await auth_module.verify_login_otp(
                auth_module.LoginOtpVerifyRequest(
                    email=user.email,
                    otp="000000",
                    challenge_token=response["challenge_token"],
                ),
                db=db,
            )

        assert exc_info.value.status_code == 423
        assert exc_info.value.detail == auth_module.OTP_LOCKED_MESSAGE
        assert user.login_otp_locked_until is not None
        assert user.login_otp_code_hash is None
        assert user.login_otp_challenge_hash is None

        login_response = await auth_module.login(
            auth_module.LoginRequest(email=user.email, password="Sup3rSecret!"),
            db=db,
        )

        assert login_response["requires_otp"] is False
        assert login_response["access_token"]

    asyncio.run(scenario())


def test_resend_login_otp_enforces_cooldown_and_limit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user = _make_user()
    db = _FakeSession([user])
    current_time = [auth_module.utcnow_naive()]

    monkeypatch.setattr(auth_module, "utcnow_naive", lambda: current_time[0])

    async def scenario() -> None:
        response, _sent_email = await _issue_login_challenge(monkeypatch, db, user)

        with pytest.raises(HTTPException) as exc_info:
            await auth_module.resend_login_otp(
                auth_module.LoginOtpResendRequest(
                    email=user.email,
                    challenge_token=response["challenge_token"],
                ),
                db=db,
            )

        assert exc_info.value.status_code == 429
        assert "Please wait" in exc_info.value.detail

        latest_response = response
        for expected_remaining in [2, 1, 0]:
            current_time[0] = current_time[0] + timedelta(
                seconds=auth_module.settings.AUTH_OTP_RESEND_COOLDOWN_SECONDS + 1
            )
            latest_response = await auth_module.resend_login_otp(
                auth_module.LoginOtpResendRequest(
                    email=user.email,
                    challenge_token=latest_response["challenge_token"],
                ),
                db=db,
            )
            assert latest_response["resend_attempts_remaining"] == expected_remaining

        current_time[0] = current_time[0] + timedelta(
            seconds=auth_module.settings.AUTH_OTP_RESEND_COOLDOWN_SECONDS + 1
        )
        with pytest.raises(HTTPException) as exc_info:
            await auth_module.resend_login_otp(
                auth_module.LoginOtpResendRequest(
                    email=user.email,
                    challenge_token=latest_response["challenge_token"],
                ),
                db=db,
            )

        assert exc_info.value.status_code == 429
        assert exc_info.value.detail == auth_module.RESEND_LIMIT_MESSAGE

    asyncio.run(scenario())


def test_resend_login_otp_allows_expired_code_with_valid_challenge(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user = _make_user()
    db = _FakeSession([user])
    current_time = [auth_module.utcnow_naive()]

    monkeypatch.setattr(auth_module, "utcnow_naive", lambda: current_time[0])

    async def scenario() -> None:
        response, _sent_email = await _issue_login_challenge(monkeypatch, db, user)
        current_time[0] = current_time[0] + timedelta(
            minutes=auth_module.settings.AUTH_OTP_EXPIRE_MINUTES,
            seconds=1,
        )

        resend_response = await auth_module.resend_login_otp(
            auth_module.LoginOtpResendRequest(
                email=user.email,
                challenge_token=response["challenge_token"],
            ),
            db=db,
        )

        assert resend_response["challenge_token"] != response["challenge_token"]
        assert resend_response["resend_attempts_remaining"] == (
            auth_module.settings.AUTH_OTP_MAX_RESEND_ATTEMPTS - 1
        )

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


async def _issue_password_reset_challenge(
    monkeypatch: pytest.MonkeyPatch,
    db: _FakeSession,
    user: User,
    *,
    delivery_mode: str = "email",
) -> tuple[dict, dict]:
    sent_email: dict = {}

    def fake_send_password_reset_otp(
        *,
        recipient_email: str,
        otp_code: str,
        recipient_name: str = "",
    ) -> str:
        sent_email.update(
            {
                "recipient_email": recipient_email,
                "otp_code": otp_code,
                "recipient_name": recipient_name,
            }
        )
        return delivery_mode

    monkeypatch.setattr(auth_module.email_service, "send_password_reset_otp", fake_send_password_reset_otp)

    response = await auth_module.forgot_password(
        auth_module.ForgotPasswordRequest(email=user.email),
        db=db,
    )

    return response, sent_email


def test_forgot_password_issues_reset_challenge(monkeypatch: pytest.MonkeyPatch) -> None:
    user = _make_user()
    db = _FakeSession([user])

    async def scenario() -> None:
        response, sent_email = await _issue_password_reset_challenge(monkeypatch, db, user)

        assert response["email"] == user.email
        assert response["delivery_mode"] == "email"
        assert "dev_otp_code" not in response
        assert sent_email["recipient_email"] == user.email
        assert auth_module.verify_secret_value(
            sent_email["otp_code"],
            user.password_reset_otp_code_hash,
        )
        assert auth_module.verify_secret_value(
            response["challenge_token"],
            user.password_reset_otp_challenge_hash,
        )
        assert user.password_reset_otp_expires_at > auth_module.utcnow_naive()

    asyncio.run(scenario())


def test_forgot_password_can_include_debug_otp_when_explicitly_enabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user = _make_user()
    db = _FakeSession([user])
    sent_email: dict = {}

    def fake_send_password_reset_otp(
        *,
        recipient_email: str,
        otp_code: str,
        recipient_name: str = "",
    ) -> str:
        sent_email["otp_code"] = otp_code
        return "email"

    async def scenario() -> None:
        response = await auth_module.forgot_password(
            auth_module.ForgotPasswordRequest(email=user.email),
            db=db,
        )

        assert response["dev_otp_code"] == sent_email["otp_code"]

    monkeypatch.setattr(auth_module.settings, "DEBUG", True)
    monkeypatch.setattr(auth_module.settings, "AUTH_EXPOSE_DEBUG_OTP", True)
    monkeypatch.setattr(
        auth_module.email_service,
        "send_password_reset_otp",
        fake_send_password_reset_otp,
    )
    asyncio.run(scenario())


def test_forgot_password_returns_generic_message_when_account_is_missing() -> None:
    db = _FakeSession()

    async def scenario() -> None:
        response = await auth_module.forgot_password(
            auth_module.ForgotPasswordRequest(email="missing@example.com"),
            db=db,
        )

        assert response == {
            "message": auth_module.PASSWORD_RESET_REQUEST_GENERIC_MESSAGE,
        }

    asyncio.run(scenario())


def test_reset_password_updates_hash_and_clears_challenge(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user = _make_user()
    db = _FakeSession([user])

    async def scenario() -> None:
        response, sent_email = await _issue_password_reset_challenge(monkeypatch, db, user)

        reset_response = await auth_module.reset_password(
            auth_module.ResetPasswordRequest(
                email=user.email,
                otp=sent_email["otp_code"],
                challenge_token=response["challenge_token"],
                new_password="NewSecret123!",
            ),
            db=db,
        )

        assert "successful" in reset_response["message"].lower()
        assert auth_module.verify_password("NewSecret123!", user.hashed_password)
        assert user.password_reset_otp_code_hash is None
        assert user.password_reset_otp_challenge_hash is None
        assert user.password_reset_otp_expires_at is None

    asyncio.run(scenario())


def test_reset_password_rejects_invalid_reset_otp(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user = _make_user()
    db = _FakeSession([user])

    async def scenario() -> None:
        response, _sent_email = await _issue_password_reset_challenge(monkeypatch, db, user)

        with pytest.raises(HTTPException) as exc_info:
            await auth_module.reset_password(
                auth_module.ResetPasswordRequest(
                    email=user.email,
                    otp="000000",
                    challenge_token=response["challenge_token"],
                    new_password="NewSecret123!",
                ),
                db=db,
            )

        assert exc_info.value.status_code == 401
        assert exc_info.value.detail == "Invalid verification code."

    asyncio.run(scenario())
