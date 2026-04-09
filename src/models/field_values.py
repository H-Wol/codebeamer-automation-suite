from __future__ import annotations

from dataclasses import dataclass
from dataclasses import field
from typing import Any

from .common import DomainModel
from .common import FieldInfo
from .common import _as_list
from .common import _coerce_bool
from .common import _drop_none
from .common import _serialize_value
from .references import _build_reference


@dataclass
class AbstractFieldValue(DomainModel):
    field_id: int
    type: str
    field_name: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return _drop_none({
            "fieldId": int(self.field_id),
            "name": self.field_name,
            "type": self.type,
        })


@dataclass
class ChoiceFieldValue(AbstractFieldValue):
    values: list[Any] = field(default_factory=list)
    type: str = "ChoiceFieldValue"

    def to_dict(self) -> dict[str, Any]:
        data = super().to_dict()
        if self.values:
            data["values"] = _serialize_value(self.values)
        return data


@dataclass
class TextFieldValue(AbstractFieldValue):
    value: str | None = None
    type: str = "TextFieldValue"

    def to_dict(self) -> dict[str, Any]:
        data = super().to_dict()
        if self.value is not None:
            data["value"] = self.value
        return data


@dataclass
class TableFieldValue(AbstractFieldValue):
    values: list[list[Any]] = field(default_factory=list)
    type: str = "TableFieldValue"

    def to_dict(self) -> dict[str, Any]:
        data = super().to_dict()
        if self.values:
            data["values"] = _serialize_value(self.values)
        return data


@dataclass
class BoolFieldValue(AbstractFieldValue):
    value: bool = False
    type: str = "BoolFieldValue"

    def to_dict(self) -> dict[str, Any]:
        data = super().to_dict()
        data["value"] = self.value
        return data


@dataclass
class ScalarFieldValue(AbstractFieldValue):
    value: Any = None
    type: str = "TextFieldValue"

    def to_dict(self) -> dict[str, Any]:
        data = super().to_dict()
        if self.value is not None:
            data["value"] = self.value
        return data


def _build_field_value(field_info: FieldInfo, value: Any) -> AbstractFieldValue | None:
    field_type = field_info.get("field_type")
    value_model = field_info.get("value_model") or field_type or "TextFieldValue"
    field_id = field_info["field_id"]
    field_name = field_info.get("field_name")
    reference_type = field_info.get("reference_type")

    if isinstance(value_model, str) and "ChoiceFieldValue" in value_model:
        values = [] if value is None else _as_list(value)
        return ChoiceFieldValue(
            field_id=field_id,
            field_name=field_name,
            values=[_build_reference(item, reference_type) for item in values],
        )

    if field_type == "TableField" or value_model == "TableFieldValue":
        if isinstance(value, TableFieldValue):
            return value
        if isinstance(value, list):
            table_values = value
        else:
            table_values = [[value]]
        return TableFieldValue(
            field_id=field_id,
            field_name=field_name,
            values=table_values,
        )

    if field_type == "BoolField" or value_model == "BoolFieldValue":
        return BoolFieldValue(
            field_id=field_id,
            field_name=field_name,
            value=_coerce_bool(value),
        )

    if isinstance(value_model, str) and value_model.endswith("FieldValue"):
        return ScalarFieldValue(
            field_id=field_id,
            field_name=field_name,
            value=value,
            type=value_model,
        )

    return TextFieldValue(
        field_id=field_id,
        field_name=field_name,
        value=str(value) if value is not None else None,
    )
