from __future__ import annotations

import re
from enum import Enum
from typing import Any


FieldInfo = dict[str, Any]


class DescriptionFormat(str, Enum):
    PlainText = "PlainText"
    Html = "Html"
    Wiki = "Wiki"


class DomainModel:
    def to_dict(self) -> dict[str, Any]:
        raise NotImplementedError


def _serialize_value(value: Any) -> Any:
    if isinstance(value, DomainModel):
        return value.to_dict()
    if isinstance(value, list):
        return [_serialize_value(item) for item in value]
    if isinstance(value, dict):
        return {key: _serialize_value(item) for key, item in value.items()}
    return value


def _drop_none(data: dict[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in data.items():
        if value is None:
            continue
        if isinstance(value, list) and not value:
            continue
        result[key] = _serialize_value(value)
    return result


def _camel_to_snake(name: str) -> str:
    if not name:
        return name
    s1 = re.sub(r"(.)([A-Z][a-z]+)", r"\1_\2", name)
    return re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", s1).lower()


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    return value if isinstance(value, list) else [value]


def _coerce_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "1", "yes", "y"}:
            return True
        if normalized in {"false", "0", "no", "n"}:
            return False
    raise ValueError(f"Cannot convert value to bool: {value}")
