from __future__ import annotations

import asyncio
import json
from datetime import timedelta
from types import SimpleNamespace

import pytest
from fastapi import HTTPException, Response

import routes.auth as auth_module
from models.auth_audit import AuthAuditEvent
from models.auth_session import AuthSession
from models.chat import ChatMessage
from models.chat_session import ChatSession
from models.conversation import Conversation
from models.document import Document
from models.file_record import FileRecord
from models.learning import LearningProgress
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

    def order_by(self, *args, **kwargs):
        return self


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
        if model is AuthAuditEvent:
            return _FakeQuery(getattr(self, "audit_events", []))
        if model is Conversation:
            return _FakeQuery(getattr(self, "conversations", []))
        if model is ChatSession:
            return _FakeQuery(getattr(self, "chat_sessions", []))
        if model is Document:
            return _FakeQuery(getattr(self, "documents", []))
        if model is FileRecord:
            return _FakeQuery(getattr(self, "files", []))
        if model is LearningProgress:
            return _FakeQuery(getattr(self, "learning_progress", []))
        if model is ChatMessage:
            return _FakeQuery(getattr(self, "messages", []))
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
        if isinstance(obj, AuthAuditEvent):
            audit_events = getattr(self, "audit_events", [])
            if obj not in audit_events:
                audit_events.append(obj)
            self.audit_events = audit_events
        if isinstance(obj, Conversation):
            conversations = getattr(self, "conversations", [])
            if obj not in conversations:
                conversations.append(obj)
            self.conversations = conversations
        if isinstance(obj, ChatSession):
            chat_sessions = getattr(self, "chat_sessions", [])
            if obj not in chat_sessions:
                chat_sessions.append(obj)
            self.chat_sessions = chat_sessions
        if isinstance(obj, Document):
            documents = getattr(self, "documents", [])
            if obj not in documents:
                documents.append(obj)
            self.documents = documents
        if isinstance(obj, FileRecord):
            files = getattr(self, "files", [])
            if obj not in files:
                files.append(obj)
            self.files = files
        if isinstance(obj, LearningProgress):
            learning_progress = getattr(self, "learning_progress", [])
            if obj not in learning_progress:
                learning_progress.append(obj)
            self.learning_progress = learning_progress
        if isinstance(obj, ChatMessage):
            messages = getattr(self, "messages", [])
            if obj not in messages:
                messages.append(obj)
            self.messages = messages

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


def test_refresh_session_reuse_detection_revokes_active_user_sessions() -> None:
    user = User(
        id=1,
        email="session.user@example.com",
        username="session-user",
        hashed_password=auth_module.get_password_hash("Sup3rSecret!"),
        is_active=True,
        is_verified=True,
    )
    other_user = User(
        id=2,
        email="other.user@example.com",
        username="other-user",
        hashed_password=auth_module.get_password_hash("Sup3rSecret!"),
        is_active=True,
        is_verified=True,
    )
    refresh_token = "old-refresh-token"
    csrf_token = "csrf-token"
    reused_session = AuthSession(
        id=1,
        user_id=user.id,
        refresh_token_hash=auth_module.hash_secret_value(refresh_token),
        csrf_token_hash=auth_module.hash_secret_value(csrf_token),
        expires_at=auth_module.utcnow_naive() + timedelta(days=1),
        revoked_at=auth_module.utcnow_naive(),
        revoked_reason="rotated",
    )
    active_session = AuthSession(
        id=2,
        user_id=user.id,
        refresh_token_hash=auth_module.hash_secret_value("new-refresh-token"),
        csrf_token_hash=auth_module.hash_secret_value("new-csrf-token"),
        expires_at=auth_module.utcnow_naive() + timedelta(days=1),
    )
    other_user_session = AuthSession(
        id=3,
        user_id=other_user.id,
        refresh_token_hash=auth_module.hash_secret_value("other-refresh-token"),
        csrf_token_hash=auth_module.hash_secret_value("other-csrf-token"),
        expires_at=auth_module.utcnow_naive() + timedelta(days=1),
    )
    db = _FakeSession([user, other_user], [reused_session, active_session, other_user_session])

    async def scenario() -> None:
        response = Response()
        with pytest.raises(HTTPException) as exc_info:
            await auth_module.refresh_session(
                request=_make_request(refresh_token, csrf_token),
                response=response,
                x_csrf_token=csrf_token,
                db=db,
            )

        assert exc_info.value.status_code == 401
        assert active_session.revoked_at is not None
        assert active_session.revoked_reason == "refresh_token_reuse"
        assert reused_session.revoked_reason == "rotated"
        assert other_user_session.revoked_at is None
        set_cookie_headers = [
            value for name, value in response.raw_headers if name.lower() == b"set-cookie"
        ]
        assert any(
            auth_module.settings.REFRESH_TOKEN_COOKIE_NAME.encode() in header
            and b"Max-Age=0" in header
            for header in set_cookie_headers
        )

    asyncio.run(scenario())


def test_list_sessions_marks_current_and_expires_stale_sessions() -> None:
    user = User(
        id=1,
        email="session.user@example.com",
        username="session-user",
        hashed_password=auth_module.get_password_hash("Sup3rSecret!"),
        is_active=True,
        is_verified=True,
    )
    refresh_token = "current-refresh-token"
    csrf_token = "csrf-token"
    current_session = AuthSession(
        id=2,
        user_id=user.id,
        refresh_token_hash=auth_module.hash_secret_value(refresh_token),
        csrf_token_hash=auth_module.hash_secret_value(csrf_token),
        expires_at=auth_module.utcnow_naive() + timedelta(days=1),
        updated_at=auth_module.utcnow_naive(),
    )
    stale_session = AuthSession(
        id=1,
        user_id=user.id,
        refresh_token_hash=auth_module.hash_secret_value("stale-refresh-token"),
        csrf_token_hash=auth_module.hash_secret_value("stale-csrf-token"),
        expires_at=auth_module.utcnow_naive() - timedelta(minutes=1),
        updated_at=auth_module.utcnow_naive(),
    )
    db = _FakeSession([user], [stale_session, current_session])

    async def scenario() -> None:
        payload = await auth_module.list_sessions(
            request=_make_request(refresh_token, csrf_token),
            current_user=user,
            db=db,
        )

        sessions = payload["sessions"]
        assert len(sessions) == 2
        current = next(item for item in sessions if item["id"] == current_session.id)
        stale = next(item for item in sessions if item["id"] == stale_session.id)
        assert current["is_current"] is True
        assert current["status"] == "active"
        assert stale["status"] == "expired"
        assert stale["revoked_reason"] == "expired"

    asyncio.run(scenario())


def test_list_auth_audit_events_returns_recent_activity() -> None:
    user = User(
        id=1,
        email="session.user@example.com",
        username="session-user",
        hashed_password=auth_module.get_password_hash("Sup3rSecret!"),
        is_active=True,
        is_verified=True,
    )
    first_event = AuthAuditEvent(
        id=1,
        user_id=user.id,
        event="logout",
        ip_address="127.0.0.1",
        user_agent="pytest",
        reason="manual",
        created_at=auth_module.utcnow_naive(),
    )
    second_event = AuthAuditEvent(
        id=2,
        user_id=user.id,
        event="session_created",
        ip_address="127.0.0.1",
        user_agent="pytest",
        reason="",
        created_at=auth_module.utcnow_naive(),
    )
    db = _FakeSession([user], [])
    db.audit_events = [first_event, second_event]

    async def scenario() -> None:
        payload = await auth_module.list_auth_audit_events(current_user=user, db=db, limit=1)

        assert len(payload["events"]) == 1
        assert payload["events"][0]["event"] in {"logout", "session_created"}

    asyncio.run(scenario())


def test_revoke_session_clears_current_cookies() -> None:
    user = User(
        id=1,
        email="session.user@example.com",
        username="session-user",
        hashed_password=auth_module.get_password_hash("Sup3rSecret!"),
        is_active=True,
        is_verified=True,
    )
    refresh_token = "current-refresh-token"
    csrf_token = "csrf-token"
    current_session = AuthSession(
        id=2,
        user_id=user.id,
        refresh_token_hash=auth_module.hash_secret_value(refresh_token),
        csrf_token_hash=auth_module.hash_secret_value(csrf_token),
        expires_at=auth_module.utcnow_naive() + timedelta(days=1),
    )
    db = _FakeSession([user], [current_session])

    async def scenario() -> None:
        response = Response()
        payload = await auth_module.revoke_session(
            session_id=current_session.id,
            request=_make_request(refresh_token, csrf_token),
            response=response,
            current_user=user,
            db=db,
        )

        assert payload["message"] == "Session revoked successfully."
        assert current_session.revoked_reason == "revoked_by_user"
        assert current_session.revoked_at is not None
        set_cookie_headers = [
            value for name, value in response.raw_headers if name.lower() == b"set-cookie"
        ]
        assert any(
            auth_module.settings.REFRESH_TOKEN_COOKIE_NAME.encode() in header
            and b"Max-Age=0" in header
            for header in set_cookie_headers
        )

    asyncio.run(scenario())


def test_export_account_data_returns_downloadable_json() -> None:
    user = User(
        id=1,
        email="session.user@example.com",
        username="session-user",
        hashed_password=auth_module.get_password_hash("Sup3rSecret!"),
        is_active=True,
        is_verified=True,
    )
    conversation = Conversation(
        id="conv-1",
        user_id=user.id,
        title="Exported chat",
        model="gpt-4o",
    )
    document = Document(
        id=1,
        user_id=user.id,
        filename="notes.pdf",
        file_type="pdf",
        file_size=2048,
        text_content="Hello export",
        summary="Summary text",
        is_processed=True,
    )
    file_record = FileRecord(
        id="file-1",
        user_id=user.id,
        filename="upload.txt",
        original_name="upload.txt",
        mime_type="text/plain",
        extension=".txt",
        size=123,
        storage_path="/private/storage/upload.txt",
        extracted_text="File text",
        metadata={"source": "upload"},
        chunk_count=1,
        status="ready",
        preview_text="Preview",
    )
    learning = LearningProgress(
        id=1,
        user_id=user.id,
        topic="AI",
        roadmap={"steps": ["one"]},
        completed_items=["one"],
        current_level="intermediate",
        notes="Keep learning",
    )
    chat_session = ChatSession(
        id="session-1",
        user_id=user.id,
        conversation_id=conversation.id,
        file_ids=["file-1"],
    )
    auth_session = AuthSession(
        id=1,
        user_id=user.id,
        refresh_token_hash=auth_module.hash_secret_value("refresh-token"),
        csrf_token_hash=auth_module.hash_secret_value("csrf-token"),
        expires_at=auth_module.utcnow_naive() + timedelta(days=1),
    )
    db = _FakeSession([user], [auth_session])
    db.conversations = [conversation]
    db.documents = [document]
    db.files = [file_record]
    db.learning_progress = [learning]
    db.chat_sessions = [chat_session]
    db.messages = []

    async def scenario() -> None:
        response = await auth_module.export_account_data(current_user=user, db=db)

        assert response.status_code == 200
        assert "attachment" in response.headers["content-disposition"].lower()
        payload = json.loads(response.body.decode("utf-8"))
        assert payload["user"]["email"] == user.email
        assert payload["counts"]["conversations"] == 1
        assert payload["counts"]["documents"] == 1
        assert payload["counts"]["files"] == 1
        assert payload["conversations"][0]["messages"] == []
        assert "storage_path" not in payload["files"][0]

    asyncio.run(scenario())


def test_refresh_session_updates_last_used_timestamp() -> None:
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
    session = AuthSession(
        id=1,
        user_id=user.id,
        refresh_token_hash=auth_module.hash_secret_value(refresh_token),
        csrf_token_hash=auth_module.hash_secret_value(csrf_token),
        expires_at=auth_module.utcnow_naive() + timedelta(days=1),
    )
    db = _FakeSession([user], [session])

    async def scenario() -> None:
        response = Response()
        await auth_module.refresh_session(
            request=_make_request(refresh_token, csrf_token),
            response=response,
            x_csrf_token=csrf_token,
            db=db,
        )

        assert session.last_used_at is not None
        assert session.updated_at is not None

    asyncio.run(scenario())
