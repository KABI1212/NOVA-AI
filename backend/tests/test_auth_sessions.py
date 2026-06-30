from __future__ import annotations

import asyncio
from datetime import timedelta
from types import SimpleNamespace

from fastapi import Response

import routes.auth as auth_module
from models.auth_session import AuthSession
from models.user import User


def _matches_filter(document: dict, payload: dict) -> bool:
    if not document:
        return True
    if "$and" in document:
        return all(_matches_filter(item, payload) for item in document["$and"])
    if "$or" in document:
        return any(_matches_filter(item, payload) for item in document["$or"])
    for key, value in document.items():
        if payload.get(key) != value:
            return False
    return True


class _FakeQuery:
    def __init__(self, records: list) -> None:
        self.records = records
        self.conditions = []

    def filter(self, *conditions):
        self.conditions.extend(condition for condition in conditions if condition is not None)
        return self

    def _filtered_records(self):
        if not self.conditions:
            return list(self.records)
        filter_doc = {"$and": [condition.to_mongo() for condition in self.conditions]}
        matched = []
        for obj in self.records:
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
    def __init__(self, users: list[User] | None = None, sessions: list[AuthSession] | None = None) -> None:
        self.users = users or []
        self.sessions = sessions or []
        self.next_session_id = 100

    def query(self, model):
        if model is User:
            return _FakeQuery(self.users)
        if model is AuthSession:
            return _FakeQuery(self.sessions)
        return _FakeQuery([])

    def add(self, obj) -> None:
        if isinstance(obj, User) and obj not in self.users:
            self.users.append(obj)
        if isinstance(obj, AuthSession):
            if obj.id is None:
                obj.id = self.next_session_id
                self.next_session_id += 1
            if obj not in self.sessions:
                self.sessions.append(obj)

    def commit(self) -> None:
        return None

    def refresh(self, obj) -> None:
        return None


def _make_request(refresh_token: str, csrf_token: str):
    return SimpleNamespace(
        headers={"user-agent": "pytest", "x-csrf-token": csrf_token},
        cookies={
            auth_module.settings.REFRESH_TOKEN_COOKIE_NAME: refresh_token,
            auth_module.settings.CSRF_COOKIE_NAME: csrf_token,
        },
        client=SimpleNamespace(host="127.0.0.1"),
    )


def test_refresh_session_rotates_refresh_token_and_revokes_old_session() -> None:
    user = User(
        id=1,
        email="session.user@example.com",
        username="session-user",
        hashed_password=auth_module.get_password_hash("Sup3rSecret!"),
        is_active=True,
        is_verified=True,
    )
    refresh_token = "refresh-token"
    csrf_token = "csrf-token"
    old_session = AuthSession(
        id=1,
        user_id=user.id,
        refresh_token_hash=auth_module.hash_secret_value(refresh_token),
        csrf_token_hash=auth_module.hash_secret_value(csrf_token),
        expires_at=auth_module.utcnow_naive() + timedelta(days=1),
    )
    db = _FakeSession([user], [old_session])

    async def scenario() -> None:
        response = Response()
        payload = await auth_module.refresh_session(
            request=_make_request(refresh_token, csrf_token),
            response=response,
            x_csrf_token=csrf_token,
            db=db,
        )

        assert payload["access_token"]
        assert payload["user"]["email"] == user.email
        assert old_session.revoked_reason == "rotated"
        assert old_session.revoked_at is not None
        assert len(db.sessions) == 2
        assert db.sessions[-1].rotated_from_session_id == old_session.id
        set_cookie_headers = [
            value for name, value in response.raw_headers if name.lower() == b"set-cookie"
        ]
        assert any(
            auth_module.settings.REFRESH_TOKEN_COOKIE_NAME.encode() in header
            for header in set_cookie_headers
        )

    asyncio.run(scenario())
