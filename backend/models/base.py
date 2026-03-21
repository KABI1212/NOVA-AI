from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, ClassVar


_MISSING = object()


def _merge_filters(operator: str, parts: list[dict]) -> dict:
    flattened: list[dict] = []
    for part in parts:
        if not part:
            continue
        if set(part.keys()) == {operator} and isinstance(part[operator], list):
            flattened.extend(part[operator])
        else:
            flattened.append(part)

    if not flattened:
        return {}
    if len(flattened) == 1:
        return flattened[0]
    return {operator: flattened}


class Expression:
    def __and__(self, other: "Expression") -> "CombinedExpression":
        return CombinedExpression("$and", [self, other])

    def __or__(self, other: "Expression") -> "CombinedExpression":
        return CombinedExpression("$or", [self, other])

    def to_mongo(self) -> dict:
        raise NotImplementedError


@dataclass(frozen=True)
class Comparison(Expression):
    field_name: str
    operator: str
    value: Any

    def to_mongo(self) -> dict:
        if self.operator == "eq":
            return {self.field_name: self.value}
        if self.operator == "ne":
            return {self.field_name: {"$ne": self.value}}
        raise ValueError(f"Unsupported comparison operator: {self.operator}")


class CombinedExpression(Expression):
    def __init__(self, operator: str, parts: list[Expression]) -> None:
        self.operator = operator
        self.parts = parts

    def __and__(self, other: Expression) -> "CombinedExpression":
        if self.operator == "$and":
            return CombinedExpression("$and", [*self.parts, other])
        return super().__and__(other)

    def __or__(self, other: Expression) -> "CombinedExpression":
        if self.operator == "$or":
            return CombinedExpression("$or", [*self.parts, other])
        return super().__or__(other)

    def to_mongo(self) -> dict:
        return _merge_filters(self.operator, [part.to_mongo() for part in self.parts])


@dataclass(frozen=True)
class SortSpec:
    field_name: str
    direction: int


class QueryField:
    def __init__(self, name: str, mongo_name: str | None = None) -> None:
        self.name = name
        self.mongo_name = mongo_name or name

    def __get__(self, instance: Any, owner: type | None = None) -> Any:
        if instance is None:
            return self
        return instance.__dict__.get(self.name)

    def __set__(self, instance: Any, value: Any) -> None:
        instance.__dict__[self.name] = value

    def __eq__(self, other: Any) -> Comparison:  # type: ignore[override]
        return Comparison(self.mongo_name, "eq", other)

    def __ne__(self, other: Any) -> Comparison:  # type: ignore[override]
        return Comparison(self.mongo_name, "ne", other)

    def asc(self) -> SortSpec:
        return SortSpec(self.mongo_name, 1)

    def desc(self) -> SortSpec:
        return SortSpec(self.mongo_name, -1)


class Field:
    def __init__(
        self,
        *,
        default: Any = _MISSING,
        default_factory: Callable[[], Any] | None = None,
        mongo_name: str | None = None,
    ) -> None:
        self.default = default
        self.default_factory = default_factory
        self.mongo_name = mongo_name

    def get_default(self) -> Any:
        if self.default_factory is not None:
            return self.default_factory()
        if self.default is _MISSING:
            return None
        return self.default


class MongoModelMeta(type):
    def __new__(mcls, name: str, bases: tuple[type, ...], namespace: dict[str, Any]):
        fields: dict[str, Field] = {}
        for base in bases:
            fields.update(getattr(base, "__fields__", {}))

        for attr_name, attr_value in list(namespace.items()):
            if isinstance(attr_value, Field):
                fields[attr_name] = attr_value
                namespace[attr_name] = QueryField(attr_name, attr_value.mongo_name)

        namespace["__fields__"] = fields
        return super().__new__(mcls, name, bases, namespace)


class MongoModel(metaclass=MongoModelMeta):
    __collection__: ClassVar[str]
    __primary_field__: ClassVar[str] = "id"
    __auto_id__: ClassVar[str | None] = None
    __fields__: ClassVar[dict[str, Field]]

    def __init__(self, **values: Any) -> None:
        for field_name, spec in self.__fields__.items():
            if field_name in values:
                value = values[field_name]
            else:
                value = spec.get_default()
            setattr(self, field_name, value)

        for key, value in values.items():
            if key not in self.__fields__:
                setattr(self, key, value)

        self._db_session = None

    @classmethod
    def from_mongo(cls, payload: dict[str, Any], db_session: Any = None) -> "MongoModel":
        values = {
            field_name: payload.get(spec.mongo_name or field_name)
            for field_name, spec in cls.__fields__.items()
        }
        instance = cls(**values)
        instance._db_session = db_session
        return instance

    def to_mongo(self, *, include_none: bool = True) -> dict[str, Any]:
        payload: dict[str, Any] = {}
        for field_name, spec in self.__fields__.items():
            mongo_name = spec.mongo_name or field_name
            value = getattr(self, field_name)
            if value is None and not include_none:
                continue
            payload[mongo_name] = value
        return payload

    @classmethod
    def primary_field(cls) -> str:
        return cls.__primary_field__

    def primary_value(self) -> Any:
        return getattr(self, self.__primary_field__)
