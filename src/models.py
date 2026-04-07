from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional
from enum import Enum
import pandas as pd
import re

# =========================================================
# Enums
# =========================================================


class DescriptionFormat(str, Enum):
    PlainText = "PlainText"
    Html = "Html"
    Wiki = "Wiki"

# =========================================================
# Base utility
# =========================================================


class DomainModel:
    def to_dict(self) -> dict[str, Any]:
        raise NotImplementedError


def _drop_none(data: dict[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for k, v in data.items():
        if v is None:
            continue
        if isinstance(v, list):
            if not v:
                continue
            result[k] = [
                item.to_dict() if isinstance(item, DomainModel) else item
                for item in v
            ]
            continue
        if isinstance(v, DomainModel):
            result[k] = v.to_dict()
            continue
        result[k] = v
    return result


def _camel_to_snake(name: str) -> str:
    if not name:
        return name
    s1 = re.sub(r"(.)([A-Z][a-z]+)", r"\1_\2", name)
    return re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", s1).lower()


# =========================================================
# Reference models
# =========================================================


@dataclass
class BaseReference(DomainModel):
    id: int
    name: Optional[str] = None
    type: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        return _drop_none({
            "id": self.id,
            "name": self.name,
            "type": self.type,
        })


@dataclass
class AbstractReference(BaseReference):
    type: str = "AbstractReference"


@dataclass
class ChoiceOptionReference(BaseReference):
    type: str = "ChoiceOptionReference"


@dataclass
class CommentReference(BaseReference):
    type: str = "CommentReference"


@dataclass
class UserReference(BaseReference):
    type: str = "UserReference"
    email: Optional[str] = None


@dataclass
class TrackerItemReference(BaseReference):
    type: str = "TrackerItemReference"


@dataclass
class TrackerReference(BaseReference):
    type: str = "TrackerReference"


@dataclass
class Label(DomainModel):
    id: int
    name: Optional[str] = None
    createdAt: Optional[str] = None
    createdBy: Optional[UserReference] = None
    hidden: Optional[bool] = None
    privateLabel: Optional[bool] = None

    def to_dict(self) -> dict[str, Any]:
        return _drop_none({
            "id": self.id,
            "name": self.name,
            "createdAt": self.createdAt,
            "createdBy": self.createdBy,
            "hidden": self.hidden,
            "privateLabel": self.privateLabel,
        })


@dataclass
class AbstractFieldValue(DomainModel):
    field_id: int
    type: str
    field_name: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        return _drop_none({
            "fieldId": self.field_id,
            "name": self.field_name,
            "type": self.type,
        })


@dataclass
class ChoiceFieldValue(AbstractFieldValue):
    values: list[BaseReference] = field(default_factory=list)
    type: str = "ChoiceFieldValue"

    def to_dict(self) -> dict[str, Any]:
        base = super().to_dict()
        if self.values:
            processed_values = []
            for v in self.values:
                if isinstance(v, DomainModel):
                    processed_values.append(v.to_dict())
                elif isinstance(v, dict):
                    processed_values.append(v)
                else:
                    processed_values.append(v)
            base["values"] = processed_values
        return base


@dataclass
class TextFieldValue(AbstractFieldValue):
    value: Optional[str] = None
    type: str = "TextFieldValue"

    def to_dict(self) -> dict[str, Any]:
        base = super().to_dict()
        if self.value is not None:
            base["value"] = self.value
        return base


@dataclass
class TableFieldValue(AbstractFieldValue):
    values: list[list[Any]] = field(default_factory=list)
    type: str = "TableFieldValue"

    def to_dict(self) -> dict[str, Any]:
        base = super().to_dict()
        if self.values:
            processed_rows = []
            for row in self.values:
                processed_row = []
                for item in row:
                    if isinstance(item, DomainModel):
                        processed_row.append(item.to_dict())
                    else:
                        processed_row.append(item)
                processed_rows.append(processed_row)
            base["values"] = processed_rows
        return base


@dataclass
class ScalarFieldValue(AbstractFieldValue):
    value: Any = None
    type: str = "TextFieldValue"

    def to_dict(self) -> dict[str, Any]:
        base = super().to_dict()
        if self.value is not None:
            base["value"] = self.value
        return base


@dataclass
class TrackerItemBase(DomainModel):
    id: Optional[int] = None
    tracker: Optional[TrackerReference] = None

    name: Optional[str] = None
    description: Optional[str] = None
    description_format: Optional[str] = None

    status: Optional[AbstractReference] = None
    priority: Optional[AbstractReference] = None
    categories: Optional[AbstractReference] = None

    subjects: list[TrackerItemReference] = field(default_factory=list)
    children: list[TrackerItemReference] = field(default_factory=list)

    ordinal: Optional[int] = None
    version: Optional[int] = None
    versions: Optional[list[AbstractReference]] = None
    type_name: Optional[str] = None

    custom_fields: list[AbstractFieldValue] = field(default_factory=list)

    modified_at: Optional[str] = None
    modified_by: Optional[UserReference] = None

    owners: Optional[AbstractReference] = None

    parent: Optional[TrackerItemReference] = field(default_factory=list)

    # ReadOnly
    angular_icon: Optional[str] = None
    assigned_at: list[str] = None
    comments: list[CommentReference] = field(default_factory=list)
    created_at: Optional[str] = None
    created_by: Optional[UserReference] = None
    icon_color: Optional[str] = None
    icon_url: Optional[str] = None
    tags: list[Label] = field(default_factory=list)

    # 미확정
    accrued_millis: Optional[int] = None
    areas: Optional[list[AbstractReference]] = None
    assigned_to: Optional[list[UserReference]] = None
    closed_at: Optional[str] = None
    end_date: Optional[str] = None
    estimated_millis: Optional[int] = None
    formality: Optional[AbstractReference] = None
    platforms: Optional[list[AbstractReference]] = None
    release_method: Optional[AbstractReference] = None
    resolutions: Optional[list[AbstractReference]] = None
    severities: Optional[list[AbstractReference]] = None
    spent_millis: Optional[int] = None
    start_date: Optional[str] = None
    story_points: Optional[int] = None
    teams: Optional[list[AbstractReference]] = None

    def add_field_value(self, field_value: AbstractFieldValue) -> None:
        self.custom_fields.append(field_value)

    @staticmethod
    def _normalize_tracker_field_name(field_name: str) -> str:
        if not field_name:
            return field_name
        if hasattr(TrackerItemBase, field_name):
            return field_name
        normalized = _camel_to_snake(field_name)
        return normalized if hasattr(TrackerItemBase, normalized) else field_name

    def _to_reference(self, raw_value: Any, reference_type: Optional[str] = None) -> Any:
        if isinstance(raw_value, DomainModel):
            return raw_value
        if not isinstance(raw_value, dict):
            return raw_value

        ref_type = raw_value.get("type") or reference_type
        ref_id = raw_value.get("id")
        ref_name = raw_value.get("name")

        if ref_type == "UserReference":
            return UserReference(id=ref_id, name=ref_name, email=raw_value.get("email"))
        if ref_type == "TrackerItemReference":
            return TrackerItemReference(id=ref_id, name=ref_name)
        if ref_type == "TrackerReference":
            return TrackerReference(id=ref_id, name=ref_name)
        if ref_type == "ChoiceOptionReference":
            return ChoiceOptionReference(id=ref_id, name=ref_name)
        if ref_type == "CommentReference":
            return CommentReference(id=ref_id, name=ref_name)
        if ref_type == "AbstractReference" or ref_type is None:
            return AbstractReference(id=ref_id, name=ref_name)
        return BaseReference(id=ref_id, name=ref_name, type=ref_type)

    def set_field_value(self, tracker_field: str, value, field_info: dict = None) -> None:
        """tracker_field에 따라 TrackerItemBase의 속성이나 custom_fields에 값 설정"""
        tracker_field = self._normalize_tracker_field_name(tracker_field)

        if hasattr(self, tracker_field):
            if tracker_field == "description" and value is not None:
                self.description = str(value)
            elif tracker_field in {"status", "priority"} and value:
                self.__dict__[tracker_field] = self._to_reference(
                    value, field_info.get("reference_type") if field_info else None)
            elif tracker_field == "assigned_to" and value:
                values = value if isinstance(value, list) else [value]
                self.assigned_to = [self._to_reference(v, field_info.get(
                    "reference_type") if field_info else None) for v in values]
            elif tracker_field in {"subjects", "children", "versions", "teams", "platforms", "areas", "resolutions", "severities"} and value:
                values = value if isinstance(value, list) else [value]
                self.__dict__[tracker_field] = [self._to_reference(v, field_info.get(
                    "reference_type") if field_info else None) for v in values]
            elif tracker_field in {"created_by", "modified_by", "parent"} and value:
                self.__dict__[tracker_field] = self._to_reference(
                    value, field_info.get("reference_type") if field_info else None)
            elif tracker_field == "story_points" and value is not None:
                self.story_points = float(value)
            elif tracker_field == "ordinal" and value is not None:
                self.ordinal = int(value)
            elif tracker_field == "version" and value is not None:
                self.version = int(value)
            elif tracker_field == "type_name" and value:
                self.type_name = str(value)
            elif tracker_field == "description_format" and value:
                self.description_format = str(value)
            elif tracker_field in {"assigned_at", "closed_at", "created_at", "modified_at", "start_date", "end_date"} and value is not None:
                setattr(self, tracker_field, str(value))
            else:
                setattr(self, tracker_field, value)
            return

        if field_info:
            field_value_obj = self._create_field_value(field_info, value)
            if field_value_obj:
                self.add_field_value(field_value_obj)

    def _create_field_value(self, field_info: dict, value) -> AbstractFieldValue | None:
        """FieldValue 객체 생성 헬퍼"""
        field_type = field_info.get('field_type')
        value_model = field_info.get(
            'value_model') or field_type or 'TextFieldValue'
        field_id = field_info['field_id']
        field_name = field_info.get('field_name')

        if isinstance(value_model, str) and 'ChoiceFieldValue' in value_model:
            if isinstance(value, list):
                values = value
            else:
                values = [value] if value else []
            return ChoiceFieldValue(
                field_id=field_id,
                field_name=field_name,
                values=[self._to_reference(v, field_info.get(
                    'reference_type')) for v in values]
            )

        if field_type == 'TableField' or (isinstance(value_model, str) and value_model == 'TableFieldValue'):
            if isinstance(value, TableFieldValue):
                return value
            if isinstance(value, list):
                return TableFieldValue(
                    field_id=field_id,
                    field_name=field_name,
                    values=value,
                )
            return TableFieldValue(
                field_id=field_id,
                field_name=field_name,
                values=[[value]],
            )

        if isinstance(value_model, str) and value_model.endswith('FieldValue'):
            return ScalarFieldValue(
                field_id=field_id,
                field_name=field_name,
                value=value,
                type=value_model
            )

        return TextFieldValue(
            field_id=field_id,
            field_name=field_name,
            value=str(value) if value is not None else None
        )

    def to_dict(self) -> dict[str, Any]:
        return _drop_none({
            "accruedMillis": self.accrued_millis,
            "angularIcon": self.angular_icon,
            "areas": self.areas,
            "assignedAt": self.assigned_at,
            "assignedTo": self.assigned_to,
            "categories": self.categories,
            "children": self.children,
            "closedAt": self.closed_at,
            "comments": self.comments,
            "createdAt": self.created_at,
            "createdBy": self.created_by,
            "customFields": self.custom_fields,
            "description": self.description,
            "descriptionFormat": self.description_format,
            "endDate": self.end_date,
            "estimatedMillis": self.estimated_millis,
            "formality": self.formality,
            "iconColor": self.icon_color,
            "iconUrl": self.icon_url,
            "id": self.id,
            "modifiedAt": self.modified_at,
            "modifiedBy": self.modified_by,
            "name": self.name,
            "ordinal": self.ordinal,
            "owners": self.owners,
            "parent": self.parent,
            "platforms": self.platforms,
            "priority": self.priority,
            "releaseMethod": self.release_method,
            "resolutions": self.resolutions,
            "severities": self.severities,
            "spentMillis": self.spent_millis,
            "startDate": self.start_date,
            "status": self.status,
            "storyPoints": self.story_points,
            "subjects": self.subjects,
            "tags": self.tags,
            "teams": self.teams,
            "tracker": self.tracker,
            "typeName": self.type_name,
            "version": self.version,
            "versions": self.versions
        })

    def create_new_item_payload(self) -> dict[str, Any]:
        payload = self.to_dict()

        # 신규 생성시 불필요한 필드들 제거
        payload.pop("id", None)
        payload.pop("createdAt", None)
        payload.pop("modifiedAt", None)
        payload.pop("createdBy", None)
        payload.pop("modifiedBy", None)
        payload.pop("version", None)

        return payload


@dataclass
class WizardState:
    project_id: int | None = None
    tracker_id: int | None = None

    raw_df: pd.DataFrame | None = None
    merged_df: pd.DataFrame | None = None
    hierarchy_df: pd.DataFrame | None = None
    upload_df: pd.DataFrame | None = None
    converted_upload_df: pd.DataFrame | None = None

    schema: dict | None = None
    schema_df: pd.DataFrame | None = None
    comparison_df: pd.DataFrame | None = None
    option_candidates_df: pd.DataFrame | None = None
    option_maps: dict[str, Any] | None = None
    option_check_df: pd.DataFrame | None = None

    selected_mapping: dict[str, str] = field(default_factory=dict)
    selected_option_mapping: dict[str, str] = field(default_factory=dict)
    # {excel_col: {table_field_name, column_name}}
    table_field_mapping: dict[str, dict] = field(default_factory=dict)

    upload_result: dict[str, Any] | None = None
