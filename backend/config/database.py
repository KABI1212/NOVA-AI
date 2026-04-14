from __future__ import annotations

import logging
import time
from datetime import datetime
from typing import Any
from urllib.parse import urlparse

from fastapi import HTTPException, status
try:
    from sqlalchemy.exc import IntegrityError
except ImportError:
    class IntegrityError(Exception):
        """Fallback when SQLAlchemy is not installed."""

from config.settings import settings
from models.base import Expression, MongoModel, QueryField, SortSpec

try:
    from pymongo import MongoClient, ReturnDocument
    from pymongo.collection import Collection
    from pymongo.database import Database
    from pymongo.errors import DuplicateKeyError, PyMongoError, ServerSelectionTimeoutError
except ImportError as exc:
    raise RuntimeError(
        "MongoDB support requires pymongo. Install the backend dependencies again."
    ) from exc


logger = logging.getLogger(__name__)


class _MongoMetadata:
    def create_all(self, bind: Any = None) -> None:
        return None


class Base:
    metadata = _MongoMetadata()


_DB_STATUS: dict[str, Any] = {
    "available": False,
    "last_error": None,
    "last_checked_at": None,
    "database_name": None,
}


def _resolve_database_name() -> str:
    configured_name = (settings.MONGODB_DB_NAME or "").strip()
    if configured_name:
        return configured_name

    parsed = urlparse(settings.DATABASE_URL)
    database_name = parsed.path.lstrip("/")
    return database_name or "nova_ai"


def _create_client() -> MongoClient:
    return MongoClient(
        settings.DATABASE_URL,
        serverSelectionTimeoutMS=settings.MONGODB_SERVER_SELECTION_TIMEOUT_MS,
        connectTimeoutMS=settings.MONGODB_CONNECT_TIMEOUT_MS,
        socketTimeoutMS=settings.MONGODB_SOCKET_TIMEOUT_MS,
    )


_CLIENT = _create_client()
_DATABASE_NAME = _resolve_database_name()


def _set_db_status(available: bool, error: str | None = None) -> None:
    _DB_STATUS["available"] = available
    _DB_STATUS["last_error"] = error
    _DB_STATUS["last_checked_at"] = datetime.utcnow().isoformat()
    _DB_STATUS["database_name"] = _DATABASE_NAME


def get_database_status() -> dict[str, Any]:
    return dict(_DB_STATUS)


def _get_database() -> Database:
    return _CLIENT[_DATABASE_NAME]


def _and_filters(parts: list[dict]) -> dict:
    flattened: list[dict] = []
    for part in parts:
        if not part:
            continue
        if set(part.keys()) == {"$and"} and isinstance(part["$and"], list):
            flattened.extend(part["$and"])
        else:
            flattened.append(part)

    if not flattened:
        return {}
    if len(flattened) == 1:
        return flattened[0]
    return {"$and": flattened}


def _ping_database() -> None:
    _get_database().command("ping")


def _ensure_indexes(database: Database) -> None:
    database["users"].create_index("id", unique=True)
    database["users"].create_index("email", unique=True)
    database["users"].create_index("username", unique=True)

    database["conversations"].create_index("id", unique=True)
    database["conversations"].create_index([("user_id", 1), ("updated_at", -1)])
    database["conversations"].create_index("share_id", unique=True, sparse=True)

    database["messages"].create_index("id", unique=True)
    database["messages"].create_index([("conversation_id", 1), ("created_at", 1)])

    database["documents"].create_index("id", unique=True)
    database["documents"].create_index([("user_id", 1), ("created_at", -1)])

    database["files"].create_index("id", unique=True)
    database["files"].create_index([("user_id", 1), ("created_at", -1)])
    database["files"].create_index([("session_id", 1), ("created_at", -1)])
    database["files"].create_index([("conversation_id", 1), ("created_at", -1)])
    database["files"].create_index([("user_id", 1), ("status", 1), ("created_at", -1)])

    database["file_chunks"].create_index("id", unique=True)
    database["file_chunks"].create_index([("file_id", 1), ("chunk_index", 1)])
    database["file_chunks"].create_index([("user_id", 1), ("file_id", 1)])

    database["chat_sessions"].create_index("id", unique=True)
    database["chat_sessions"].create_index([("user_id", 1), ("updated_at", -1)])

    database["learning_progress"].create_index("id", unique=True)
    database["learning_progress"].create_index([("user_id", 1), ("updated_at", -1)])


def _database_unavailable_message(error: str | None = None) -> str:
    message = (
        f"MongoDB is unavailable at {settings.DATABASE_URL}. "
        "Check whether mongod is installed, running, and listening on the expected host/port."
    )
    if error:
        message = f"{message} Details: {error}"
    return message


def _log_db_event(level: int, event: str, **fields: Any) -> None:
    payload = " ".join(f"{key}={value!r}" for key, value in fields.items())
    logger.log(level, "mongodb_event=%s %s", event, payload)


def check_database_connection(*, log_errors: bool = True) -> bool:
    try:
        _ping_database()
        _set_db_status(True, None)
        if log_errors:
            _log_db_event(
                logging.INFO,
                "connection_ok",
                uri=settings.DATABASE_URL,
                database=_DATABASE_NAME,
            )
        return True
    except ServerSelectionTimeoutError as exc:
        _set_db_status(False, str(exc))
        if log_errors:
            _log_db_event(
                logging.ERROR,
                "connection_refused",
                uri=settings.DATABASE_URL,
                database=_DATABASE_NAME,
                error=str(exc),
            )
        return False
    except PyMongoError as exc:
        _set_db_status(False, str(exc))
        if log_errors:
            _log_db_event(
                logging.ERROR,
                "connection_error",
                uri=settings.DATABASE_URL,
                database=_DATABASE_NAME,
                error=str(exc),
            )
        return False


class MongoQuery:
    def __init__(self, session: "MongoSession", model: type[MongoModel]) -> None:
        self.session = session
        self.model = model
        self._conditions: list[Expression] = []
        self._sorts: list[SortSpec] = []

    def filter(self, *conditions: Expression) -> "MongoQuery":
        self._conditions.extend(condition for condition in conditions if condition is not None)
        return self

    def order_by(self, *sorts: SortSpec | QueryField) -> "MongoQuery":
        normalized_sorts: list[SortSpec] = []
        for sort in sorts:
            if isinstance(sort, SortSpec):
                normalized_sorts.append(sort)
            elif isinstance(sort, QueryField):
                normalized_sorts.append(sort.asc())
            else:
                raise TypeError(f"Unsupported sort type: {type(sort)!r}")
        self._sorts = normalized_sorts
        return self

    def _collection(self) -> Collection:
        return self.session.collection_for(self.model)

    def _mongo_filter(self) -> dict:
        return _and_filters([condition.to_mongo() for condition in self._conditions])

    def all(self) -> list[MongoModel]:
        cursor = self._collection().find(self._mongo_filter())
        if self._sorts:
            cursor = cursor.sort([(sort.field_name, sort.direction) for sort in self._sorts])
        return [self.session.attach(self.model.from_mongo(payload, self.session)) for payload in cursor]

    def first(self) -> MongoModel | None:
        cursor = self._collection().find(self._mongo_filter())
        if self._sorts:
            cursor = cursor.sort([(sort.field_name, sort.direction) for sort in self._sorts])
        payload = next(cursor.limit(1), None)
        if payload is None:
            return None
        return self.session.attach(self.model.from_mongo(payload, self.session))


class MongoSession:
    def __init__(self) -> None:
        self.database = _get_database()
        self._tracked: dict[int, MongoModel] = {}
        self._deleted: dict[int, MongoModel] = {}

    def collection_for(self, model: type[MongoModel]) -> Collection:
        return self.database[model.__collection__]

    def attach(self, obj: MongoModel) -> MongoModel:
        obj._db_session = self
        self._tracked[id(obj)] = obj
        return obj

    def query(self, model: type[MongoModel]) -> MongoQuery:
        return MongoQuery(self, model)

    def add(self, obj: MongoModel) -> None:
        self.attach(obj)
        self._deleted.pop(id(obj), None)

    def delete(self, obj: MongoModel) -> None:
        self._deleted[id(obj)] = obj
        self._tracked.pop(id(obj), None)

    def _next_sequence(self, name: str) -> int:
        counter = self.database["counters"].find_one_and_update(
            {"_id": name},
            {"$inc": {"value": 1}},
            upsert=True,
            return_document=ReturnDocument.AFTER,
        )
        return int(counter["value"])

    def _delete_object(self, obj: MongoModel) -> None:
        collection = self.collection_for(type(obj))
        primary_field = type(obj).primary_field()
        primary_value = obj.primary_value()
        if primary_value is None:
            return

        collection.delete_one({primary_field: primary_value})

        from models.chat import ChatMessage
        from models.conversation import Conversation

        if isinstance(obj, Conversation):
            self.collection_for(ChatMessage).delete_many({"conversation_id": obj.id})

    def _save_object(self, obj: MongoModel) -> None:
        model = type(obj)
        primary_field = model.primary_field()
        primary_value = obj.primary_value()

        if primary_value is None and model.__auto_id__ == "counter":
            setattr(obj, primary_field, self._next_sequence(model.__collection__))
            primary_value = obj.primary_value()

        if hasattr(obj, "created_at") and getattr(obj, "created_at") is None:
            setattr(obj, "created_at", datetime.utcnow())
        if hasattr(obj, "updated_at"):
            setattr(obj, "updated_at", datetime.utcnow())

        payload = obj.to_mongo(include_none=False)
        unset_fields = {
            spec.mongo_name or field_name: ""
            for field_name, spec in model.__fields__.items()
            if getattr(obj, field_name) is None
        }

        update_doc: dict[str, Any] = {}
        if payload:
            update_doc["$set"] = payload
        if unset_fields:
            update_doc["$unset"] = unset_fields

        self.collection_for(model).update_one(
            {primary_field: primary_value},
            update_doc or {"$set": {primary_field: primary_value}},
            upsert=True,
        )

    def commit(self) -> None:
        try:
            for obj in list(self._deleted.values()):
                self._delete_object(obj)

            for obj in list(self._tracked.values()):
                self._save_object(obj)
        except DuplicateKeyError as exc:
            raise IntegrityError(None, None, exc) from exc
        finally:
            self._deleted.clear()

    def refresh(self, obj: MongoModel) -> None:
        primary_field = type(obj).primary_field()
        primary_value = obj.primary_value()
        if primary_value is None:
            return

        payload = self.collection_for(type(obj)).find_one({primary_field: primary_value})
        if payload is None:
            return

        fresh_obj = type(obj).from_mongo(payload, self)
        for field_name in type(obj).__fields__:
            setattr(obj, field_name, getattr(fresh_obj, field_name))
        self.attach(obj)

    def rollback(self) -> None:
        self._deleted.clear()
        self._tracked.clear()

    def close(self) -> None:
        self._deleted.clear()
        self._tracked.clear()


engine = None
SessionLocal = MongoSession


def get_db():
    """Database dependency for FastAPI."""
    if not _DB_STATUS["available"] and not check_database_connection(log_errors=False):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database unavailable. Check MongoDB service and DATABASE_URL.",
        )

    db = MongoSession()
    try:
        yield db
    finally:
        db.close()


def get_db_optional():
    """Best-effort database dependency for routes that can degrade without persistence."""
    if not _DB_STATUS["available"] and not check_database_connection(log_errors=False):
        yield None
        return

    db = MongoSession()
    try:
        yield db
    finally:
        db.close()


def init_db() -> bool:
    """Initialize MongoDB collections and indexes."""
    last_error: Exception | None = None

    for attempt in range(1, settings.MONGODB_RETRY_ATTEMPTS + 1):
        try:
            database = _get_database()
            _ping_database()
            _ensure_indexes(database)
            _set_db_status(True, None)
            _log_db_event(
                logging.INFO,
                "init_success",
                uri=settings.DATABASE_URL,
                database=_DATABASE_NAME,
                attempt=attempt,
                attempts=settings.MONGODB_RETRY_ATTEMPTS,
            )
            return True
        except ServerSelectionTimeoutError as exc:
            last_error = exc
            _set_db_status(False, str(exc))
            _log_db_event(
                logging.WARNING,
                "init_retryable_failure",
                uri=settings.DATABASE_URL,
                database=_DATABASE_NAME,
                attempt=attempt,
                attempts=settings.MONGODB_RETRY_ATTEMPTS,
                error=str(exc),
            )
        except PyMongoError as exc:
            last_error = exc
            _set_db_status(False, str(exc))
            _log_db_event(
                logging.ERROR,
                "init_error",
                uri=settings.DATABASE_URL,
                database=_DATABASE_NAME,
                attempt=attempt,
                attempts=settings.MONGODB_RETRY_ATTEMPTS,
                error=str(exc),
            )

        if attempt < settings.MONGODB_RETRY_ATTEMPTS:
            delay = min(
                settings.MONGODB_RETRY_DELAY_SECONDS
                * (settings.MONGODB_RETRY_BACKOFF_MULTIPLIER ** (attempt - 1)),
                settings.MONGODB_RETRY_MAX_DELAY_SECONDS,
            )
            _log_db_event(
                logging.INFO,
                "init_backoff_sleep",
                delay_seconds=delay,
                next_attempt=attempt + 1,
            )
            time.sleep(delay)

    message = _database_unavailable_message(str(last_error) if last_error else None)
    if settings.MONGODB_REQUIRED:
        raise RuntimeError(message) from last_error

    _log_db_event(
        logging.ERROR,
        "init_fallback_without_db",
        uri=settings.DATABASE_URL,
        database=_DATABASE_NAME,
        required=settings.MONGODB_REQUIRED,
        error=message,
    )
    return False
