from __future__ import annotations

from dataclasses import dataclass
from dataclasses import field
from typing import Any
from typing import ClassVar

from .common import DomainModel
from .common import FieldValueType
from .common import FieldInfo
from .common import SchemaFieldType
from .common import _as_list
from .common import _coerce_bool
from .common import _drop_none
from .common import _serialize_value
from .references import _build_reference


@dataclass
class AbstractFieldValue(DomainModel):
    _REGISTRY: ClassVar[list[type["AbstractFieldValue"]]] = []
    VALUE_MODEL_ALIASES: ClassVar[tuple[str, ...]] = ()
    FIELD_TYPE_ALIASES: ClassVar[tuple[str, ...]] = ()

    field_id: int
    type: str
    field_name: str | None = None

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        if cls is not AbstractFieldValue:
            AbstractFieldValue._REGISTRY.append(cls)

    def to_dict(self) -> dict[str, Any]:
        return _drop_none({
            "fieldId": int(self.field_id),
            "name": self.field_name,
            "type": self.type,
        })

    @classmethod
    def _base_kwargs(cls, field_info: FieldInfo) -> dict[str, Any]:
        return {
            "field_id": field_info["field_id"],
            "field_name": field_info.get("field_name"),
        }

    @classmethod
    def matches(cls, field_info: FieldInfo) -> bool:
        value_model = field_info.get("value_model")
        field_type = field_info.get("field_type")
        return (
            value_model in cls.VALUE_MODEL_ALIASES
            or field_type in cls.FIELD_TYPE_ALIASES
        )

    @classmethod
    def from_value(cls, field_info: FieldInfo, value: Any) -> "AbstractFieldValue":
        return cls(**cls._base_kwargs(field_info), type=cls.__name__)

    @classmethod
    def resolve_class(cls, field_info: FieldInfo) -> type["AbstractFieldValue"]:
        for candidate in cls._REGISTRY:
            if candidate.matches(field_info):
                return candidate

        value_model = field_info.get("value_model")
        if isinstance(value_model, str) and value_model.endswith("FieldValue"):
            return ScalarFieldValue
        return TextFieldValue


@dataclass
class ChoiceFieldValue(AbstractFieldValue):
    values: list[Any] = field(default_factory=list)
    type: str = FieldValueType.CHOICE.value

    def to_dict(self) -> dict[str, Any]:
        data = super().to_dict()
        if self.values:
            data["values"] = _serialize_value(self.values)
        return data

    @classmethod
    def matches(cls, field_info: FieldInfo) -> bool:
        value_model = field_info.get("value_model")
        return isinstance(value_model, str) and FieldValueType.CHOICE.value in value_model

    @classmethod
    def from_value(cls, field_info: FieldInfo, value: Any) -> "ChoiceFieldValue":
        reference_type = field_info.get("reference_type")
        values = [] if value is None else _as_list(value)
        return cls(
            **cls._base_kwargs(field_info),
            values=[_build_reference(item, reference_type) for item in values],
        )


@dataclass
class TextFieldValue(AbstractFieldValue):
    VALUE_MODEL_ALIASES: ClassVar[tuple[str, ...]] = (FieldValueType.TEXT.value,)

    value: str | None = None
    type: str = FieldValueType.TEXT.value

    def to_dict(self) -> dict[str, Any]:
        data = super().to_dict()
        if self.value is not None:
            data["value"] = self.value
        return data

    @classmethod
    def from_value(cls, field_info: FieldInfo, value: Any) -> "TextFieldValue":
        return cls(
            **cls._base_kwargs(field_info),
            value=str(value) if value is not None else None,
        )


@dataclass
class TableFieldValue(AbstractFieldValue):
    VALUE_MODEL_ALIASES: ClassVar[tuple[str, ...]] = (FieldValueType.TABLE.value,)
    FIELD_TYPE_ALIASES: ClassVar[tuple[str, ...]] = (SchemaFieldType.TABLE.value,)

    values: list[list[Any]] = field(default_factory=list)
    type: str = FieldValueType.TABLE.value

    def to_dict(self) -> dict[str, Any]:
        data = super().to_dict()
        if self.values:
            data["values"] = _serialize_value(self.values)
        return data

    @classmethod
    def from_value(cls, field_info: FieldInfo, value: Any) -> "TableFieldValue":
        if isinstance(value, TableFieldValue):
            return value

        if isinstance(value, list):
            table_values = value
        else:
            table_values = [[value]]

        return cls(
            **cls._base_kwargs(field_info),
            values=table_values,
        )


@dataclass
class BoolFieldValue(AbstractFieldValue):
    VALUE_MODEL_ALIASES: ClassVar[tuple[str, ...]] = (FieldValueType.BOOL.value,)
    FIELD_TYPE_ALIASES: ClassVar[tuple[str, ...]] = (SchemaFieldType.BOOL.value,)

    value: bool = False
    type: str = FieldValueType.BOOL.value

    def to_dict(self) -> dict[str, Any]:
        data = super().to_dict()
        data["value"] = self.value
        return data

    @classmethod
    def from_value(cls, field_info: FieldInfo, value: Any) -> "BoolFieldValue":
        return cls(
            **cls._base_kwargs(field_info),
            value=_coerce_bool(value),
        )


@dataclass
class ScalarFieldValue(AbstractFieldValue):
    value: Any = None
    type: str = FieldValueType.TEXT.value

    def to_dict(self) -> dict[str, Any]:
        data = super().to_dict()
        if self.value is not None:
            data["value"] = self.value
        return data

    @classmethod
    def from_value(cls, field_info: FieldInfo, value: Any) -> "ScalarFieldValue":
        value_model = field_info.get("value_model") or FieldValueType.TEXT.value
        return cls(
            **cls._base_kwargs(field_info),
            value=value,
            type=value_model,
        )


def _build_field_value(field_info: FieldInfo, value: Any) -> AbstractFieldValue | None:
    field_value_cls = AbstractFieldValue.resolve_class(field_info)
    return field_value_cls.from_value(field_info, value)
