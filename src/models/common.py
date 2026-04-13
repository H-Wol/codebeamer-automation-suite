from __future__ import annotations

import re
from enum import Enum
from typing import Any


FieldInfo = dict[str, Any]


class DescriptionFormat(str, Enum):
    PlainText = "PlainText"
    Html = "Html"
    Wiki = "Wiki"


class ReferenceType(str, Enum):
    ABSTRACT = "AbstractReference"
    CHOICE_OPTION = "ChoiceOptionReference"
    COMMENT = "CommentReference"
    PROJECT = "ProjectReference"
    REPOSITORY = "RepositoryReference"
    ROLE = "RoleReference"
    TRACKER = "TrackerReference"
    TRACKER_ITEM = "TrackerItemReference"
    TRACKER_PERMISSION = "TrackerPermissionReference"
    USER = "UserReference"


class FieldValueType(str, Enum):
    BOOL = "BoolFieldValue"
    CHOICE = "ChoiceFieldValue"
    TABLE = "TableFieldValue"
    TEXT = "TextFieldValue"


class SchemaFieldType(str, Enum):
    BOOL = "BoolField"
    OPTION_CHOICE = "OptionChoiceField"
    REFERENCE = "ReferenceField"
    TABLE = "TableField"


class ResolvedFieldKind(str, Enum):
    SCALAR_TEXT = "scalar_text"
    SCALAR_BOOL = "scalar_bool"
    STATIC_OPTION = "static_option"
    USER_REFERENCE = "user_reference"
    GENERIC_REFERENCE = "generic_reference"
    TABLE = "table"
    UNSUPPORTED = "unsupported"


class ResolutionStrategy(str, Enum):
    BUILTIN_SCALAR = "builtin_scalar"
    CUSTOM_SCALAR = "custom_scalar"
    TYPE_BOOL = "type_bool"
    TYPE_TABLE = "type_table"
    TYPE_OPTION_WITH_OPTIONS = "type_option_with_options"
    TYPE_OPTION_WITH_USER_REFERENCE = "type_option_with_user_reference"
    TYPE_OPTION_WITH_REFERENCE_TYPE = "type_option_with_reference_type"
    TYPE_OPTION_AMBIGUOUS = "type_option_ambiguous"
    TYPE_REFERENCE_WITH_USER_REFERENCE = "type_reference_with_user_reference"
    TYPE_REFERENCE_WITH_REFERENCE_TYPE = "type_reference_with_reference_type"
    TYPE_REFERENCE_WITHOUT_REFERENCE_TYPE = "type_reference_without_reference_type"
    UNKNOWN_TYPE = "unknown_type"


class LookupTargetKind(str, Enum):
    NONE = "none"
    USER = "user"
    REFERENCE = "reference"


class PreconstructionKind(str, Enum):
    NONE = "none"
    BUILTIN_DIRECT = "builtin_direct"
    FIELD_VALUE = "field_value"
    REFERENCE = "reference"
    REFERENCE_LIST = "reference_list"
    TABLE_FIELD_VALUE = "table_field_value"


class PayloadTargetKind(str, Enum):
    BUILTIN_FIELD = "builtin_field"
    CUSTOM_FIELD = "custom_field"
    UNSUPPORTED = "unsupported"


class OptionSourceKind(str, Enum):
    SCHEMA_OPTIONS = "schema_options"
    REFERENCE_LOOKUP = "reference_lookup"
    UNSUPPORTED = "unsupported"


class OptionMapKind(str, Enum):
    STATIC_OPTIONS = "static_options"
    USER_LOOKUP = "user_lookup"
    REFERENCE_LOOKUP = "reference_lookup"
    UNSUPPORTED = "unsupported"


class OptionSourceStatus(str, Enum):
    READY = "READY"
    LOOKUP_REQUIRED = "LOOKUP_REQUIRED"
    UNSUPPORTED = "UNSUPPORTED"


class MappingStatus(str, Enum):
    OK = "OK"
    SCHEMA_FIELD_MISSING = "SCHEMA_FIELD_MISSING"
    UNMAPPED = "UNMAPPED"


class OptionCheckStatus(str, Enum):
    DF_COLUMN_MISSING = "DF_COLUMN_MISSING"
    FIELD_UNSUPPORTED = "FIELD_UNSUPPORTED"
    LOOKUP_REQUIRED = "LOOKUP_REQUIRED"
    OPTION_MAP_MISSING = "OPTION_MAP_MISSING"
    OPTION_NOT_FOUND = "OPTION_NOT_FOUND"
    OPTION_SOURCE_UNAVAILABLE = "OPTION_SOURCE_UNAVAILABLE"
    PRECONSTRUCTION_REQUIRED = "PRECONSTRUCTION_REQUIRED"


class UserLookupStatus(str, Enum):
    RESOLVED = "RESOLVED"
    USER_LOOKUP_AMBIGUOUS = "USER_LOOKUP_AMBIGUOUS"
    USER_LOOKUP_FAILED = "USER_LOOKUP_FAILED"
    USER_LOOKUP_NOT_RUN = "USER_LOOKUP_NOT_RUN"
    USER_NOT_FOUND = "USER_NOT_FOUND"


class UploadStatus(str, Enum):
    FAILED = "FAILED"
    SUCCESS = "SUCCESS"


class TrackerItemField(str, Enum):
    STATUS = "status"


class TrackerSchemaName(str, Enum):
    STATUS = "Status"


OPTION_CONTAINER_KEYS: tuple[str, ...] = ("items", "options", "references", "values")
USER_SEARCH_RESULT_KEYS: tuple[str, ...] = ("users", "userRefs", "items", "references", "content")


class DomainModel:
    def to_dict(self) -> dict[str, Any]:
        """각 모델이 스스로를 dict로 바꾸도록 강제하는 공통 규약이다."""
        raise NotImplementedError


def _serialize_value(value: Any) -> Any:
    """중첩된 모델 객체를 재귀적으로 일반 dict/list 값으로 바꾼다."""
    if isinstance(value, DomainModel):
        return value.to_dict()
    if isinstance(value, list):
        return [_serialize_value(item) for item in value]
    if isinstance(value, dict):
        return {key: _serialize_value(item) for key, item in value.items()}
    return value


def _drop_none(data: dict[str, Any]) -> dict[str, Any]:
    """값이 비어 있는 항목을 빼서 API payload를 간단하게 만든다."""
    result: dict[str, Any] = {}
    for key, value in data.items():
        if value is None:
            continue
        if isinstance(value, list) and not value:
            continue
        result[key] = _serialize_value(value)
    return result


def _camel_to_snake(name: str) -> str:
    """카멜 표기 이름을 파이썬에서 쓰기 쉬운 스네이크 표기로 바꾼다."""
    if not name:
        return name
    s1 = re.sub(r"(.)([A-Z][a-z]+)", r"\1_\2", name)
    return re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", s1).lower()


def _as_list(value: Any) -> list[Any]:
    """단일 값도 항상 목록처럼 다룰 수 있게 감싼다."""
    if value is None:
        return []
    return value if isinstance(value, list) else [value]


def _coerce_bool(value: Any) -> bool:
    """문자열이나 불린 값을 실제 True/False로 통일한다."""
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "1", "yes", "y"}:
            return True
        if normalized in {"false", "0", "no", "n"}:
            return False
    raise ValueError(f"Cannot convert value to bool: {value}")
