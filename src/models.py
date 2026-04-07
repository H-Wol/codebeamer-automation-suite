from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional
from enum import Enum
import pandas as pd

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
            base["values"] = [v.to_dict() for v in self.values]
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

    def set_field_value(self, tracker_field: str, value, field_info: dict = None) -> None:
        """tracker_field에 따라 TrackerItemBase의 속성이나 custom_fields에 값 설정"""
        if hasattr(self, tracker_field):
            # built-in 필드: TrackerItemBase 속성으로 설정
            if tracker_field == "description" and value:
                self.description = str(value)
            elif tracker_field == "status" and value:
                self.status = AbstractReference(id=value["id"], name=value["name"])
            elif tracker_field == "priority" and value:
                self.priority = AbstractReference(id=value["id"], name=value["name"])
            elif tracker_field == "assigned_to" and value:
                if isinstance(value, list):
                    self.assigned_to = [UserReference(id=v["id"], name=v["name"]) for v in value]
                else:
                    self.assigned_to = [UserReference(id=value["id"], name=value["name"])]
            elif tracker_field == "subjects" and value:
                if isinstance(value, list):
                    self.subjects = [TrackerItemReference(id=v["id"], name=v["name"]) for v in value]
                else:
                    self.subjects = [TrackerItemReference(id=value["id"], name=value["name"])]
            elif tracker_field == "children" and value:
                if isinstance(value, list):
                    self.children = [TrackerItemReference(id=v["id"], name=v["name"]) for v in value]
                else:
                    self.children = [TrackerItemReference(id=value["id"], name=value["name"])]
            elif tracker_field == "story_points" and value is not None:
                self.story_points = float(value)
            elif tracker_field == "ordinal" and value is not None:
                self.ordinal = int(value)
            elif tracker_field == "version" and value is not None:
                self.version = int(value)
            elif tracker_field == "type_name" and value:
                self.type_name = str(value)
            # name과 description은 이미 preview_payload에서 직접 설정됨
        else:
            # custom 필드: FieldValue 객체 생성 후 custom_fields에 추가
            if field_info:
                field_value_obj = self._create_field_value(field_info, value)
                if field_value_obj:
                    self.add_field_value(field_value_obj)

    def _create_field_value(self, field_info: dict, value) -> AbstractFieldValue | None:
        """FieldValue 객체 생성 헬퍼"""
        field_type = field_info.get('field_type', 'TextField')
        field_id = field_info['field_id']
        field_name = field_info.get('field_name')

        if field_type == 'ChoiceField':
            if isinstance(value, list):
                values = value
            else:
                values = [value] if value else []
            return ChoiceFieldValue(
                field_id=field_id,
                field_name=field_name,
                values=values
            )
        elif field_type == 'TextField':
            return TextFieldValue(
                field_id=field_id,
                field_name=field_name,
                value=str(value) if value is not None else None
            )
        else:
            # 기타 필드 타입은 TextField로 처리
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
            "assignedAt": self.assigned_to,
            "assignedTo": self.assigned_at,
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
        payload.pop("version",None)

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
    table_field_mapping: dict[str, dict] = field(default_factory=dict)  # {excel_col: {table_field_name, column_name}}

    upload_result: dict[str, Any] | None = None
