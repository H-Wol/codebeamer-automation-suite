from __future__ import annotations

from dataclasses import dataclass
from dataclasses import field
from typing import Any
from typing import ClassVar

from .common import DomainModel
from .common import FieldInfo
from .common import _as_list
from .common import _camel_to_snake
from .common import _drop_none
from .field_values import AbstractFieldValue
from .field_values import TableFieldValue
from .field_values import _build_field_value
from .references import AbstractReference
from .references import CommentReference
from .references import Label
from .references import TrackerItemReference
from .references import TrackerReference
from .references import UserReference
from .references import _build_reference


@dataclass
class TrackerItemBase(DomainModel):
    NON_CREATABLE_FIELDS: ClassVar[set[str]] = {
        "angular_icon",
        "assigned_at",
        "children",
        "comments",
        "created_at",
        "created_by",
        "icon_color",
        "icon_url",
        "id",
        "modified_at",
        "modified_by",
        "parent",
        "tags",
        "tracker",
        "version",
    }
    CREATE_EXCLUDED_KEYS: ClassVar[set[str]] = {
        "angularIcon",
        "assignedAt",
        "children",
        "comments",
        "createdAt",
        "createdBy",
        "iconColor",
        "iconUrl",
        "id",
        "modifiedAt",
        "modifiedBy",
        "parent",
        "tags",
        "tracker",
        "version",
    }
    REFERENCE_LIST_FIELDS: ClassVar[set[str]] = {
        "areas",
        "assigned_to",
        "categories",
        "platforms",
        "resolutions",
        "severities",
        "subjects",
        "teams",
        "versions",
    }
    REFERENCE_SINGLE_FIELDS: ClassVar[set[str]] = {
        "formality",
        "owners",
        "priority",
        "release_method",
        "status",
    }
    INTEGER_FIELDS: ClassVar[set[str]] = {
        "ordinal",
        "story_points",
        "version",
    }
    STRING_FIELDS: ClassVar[set[str]] = {
        "closed_at",
        "description",
        "description_format",
        "end_date",
        "name",
        "start_date",
        "type_name",
    }
    PAYLOAD_FIELD_MAP: ClassVar[dict[str, str]] = {
        "accrued_millis": "accruedMillis",
        "angular_icon": "angularIcon",
        "areas": "areas",
        "assigned_at": "assignedAt",
        "assigned_to": "assignedTo",
        "categories": "categories",
        "children": "children",
        "closed_at": "closedAt",
        "comments": "comments",
        "created_at": "createdAt",
        "created_by": "createdBy",
        "custom_fields": "customFields",
        "description": "description",
        "description_format": "descriptionFormat",
        "end_date": "endDate",
        "estimated_millis": "estimatedMillis",
        "formality": "formality",
        "icon_color": "iconColor",
        "icon_url": "iconUrl",
        "id": "id",
        "modified_at": "modifiedAt",
        "modified_by": "modifiedBy",
        "name": "name",
        "ordinal": "ordinal",
        "owners": "owners",
        "parent": "parent",
        "platforms": "platforms",
        "priority": "priority",
        "release_method": "releaseMethod",
        "resolutions": "resolutions",
        "severities": "severities",
        "spent_millis": "spentMillis",
        "start_date": "startDate",
        "status": "status",
        "story_points": "storyPoints",
        "subjects": "subjects",
        "tags": "tags",
        "teams": "teams",
        "tracker": "tracker",
        "type_name": "typeName",
        "version": "version",
        "versions": "versions",
    }

    id: int | None = None
    tracker: TrackerReference | None = None

    name: str | None = None
    description: str | None = None
    description_format: str | None = None

    status: AbstractReference | None = None
    priority: AbstractReference | None = None
    categories: list[AbstractReference] | None = None

    subjects: list[TrackerItemReference] = field(default_factory=list)
    children: list[TrackerItemReference] = field(default_factory=list)

    ordinal: int | None = None
    version: int | None = None
    versions: list[AbstractReference] | None = None
    type_name: str | None = None

    custom_fields: list[AbstractFieldValue] = field(default_factory=list)

    modified_at: str | None = None
    modified_by: UserReference | None = None

    owners: AbstractReference | None = None
    parent: TrackerItemReference | None = None

    angular_icon: str | None = None
    assigned_at: list[str] = field(default_factory=list)
    comments: list[CommentReference] = field(default_factory=list)
    created_at: str | None = None
    created_by: UserReference | None = None
    icon_color: str | None = None
    icon_url: str | None = None
    tags: list[Label] = field(default_factory=list)

    accrued_millis: int | None = None
    areas: list[AbstractReference] | None = None
    assigned_to: list[UserReference] | None = None
    closed_at: str | None = None
    end_date: str | None = None
    estimated_millis: int | None = None
    formality: AbstractReference | None = None
    platforms: list[AbstractReference] | None = None
    release_method: AbstractReference | None = None
    resolutions: list[AbstractReference] | None = None
    severities: list[AbstractReference] | None = None
    spent_millis: int | None = None
    start_date: str | None = None
    story_points: int | None = None
    teams: list[AbstractReference] | None = None

    @staticmethod
    def _normalize_tracker_field_name(field_name: str) -> str:
        if not field_name:
            return field_name
        if hasattr(TrackerItemBase, field_name):
            return field_name
        normalized = _camel_to_snake(field_name)
        return normalized if hasattr(TrackerItemBase, normalized) else field_name

    @staticmethod
    def _reference_type(field_info: FieldInfo | None) -> str | None:
        if not field_info:
            return None
        return field_info.get("reference_type")

    def _to_reference(self, raw_value: Any, reference_type: str | None = None) -> Any:
        return _build_reference(raw_value, reference_type)

    def _to_reference_list(self, value: Any, field_info: FieldInfo | None = None) -> list[Any]:
        reference_type = self._reference_type(field_info)
        return [self._to_reference(item, reference_type) for item in _as_list(value)]

    def _create_field_value(self, field_info: FieldInfo, value: Any) -> AbstractFieldValue | None:
        return _build_field_value(field_info, value)

    def add_field_value(self, field_value: AbstractFieldValue) -> None:
        self.custom_fields.append(field_value)

    def _set_builtin_field(self, tracker_field: str, value: Any, field_info: FieldInfo | None = None) -> bool:
        if not hasattr(self, tracker_field):
            return False

        if tracker_field in self.REFERENCE_LIST_FIELDS:
            setattr(self, tracker_field, self._to_reference_list(value, field_info))
            return True

        if tracker_field in self.REFERENCE_SINGLE_FIELDS:
            setattr(self, tracker_field, self._to_reference(value, self._reference_type(field_info)))
            return True

        if tracker_field in self.INTEGER_FIELDS and value is not None:
            setattr(self, tracker_field, int(value))
            return True

        if tracker_field in self.STRING_FIELDS and value is not None:
            setattr(self, tracker_field, str(value))
            return True

        setattr(self, tracker_field, value)
        return True

    def set_field_value(self, tracker_field: str, value: Any, field_info: FieldInfo | None = None) -> None:
        normalized_field = self._normalize_tracker_field_name(tracker_field)
        if normalized_field in self.NON_CREATABLE_FIELDS:
            return

        if self._set_builtin_field(normalized_field, value, field_info):
            return

        if field_info:
            field_value = self._create_field_value(field_info, value)
            if field_value is not None:
                self.add_field_value(field_value)

    def to_dict(self) -> dict[str, Any]:
        return _drop_none({
            payload_key: getattr(self, attr_name)
            for attr_name, payload_key in self.PAYLOAD_FIELD_MAP.items()
        })

    def to_create_payload(self) -> dict[str, Any]:
        payload = self.to_dict()
        for key in self.CREATE_EXCLUDED_KEYS:
            payload.pop(key, None)
        return payload

    def create_new_item_payload(self) -> dict[str, Any]:
        return self.to_create_payload()
