from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .common import DomainModel
from .common import _drop_none


@dataclass
class BaseReference(DomainModel):
    id: int
    name: str | None = None
    type: str | None = None

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
    email: str | None = None


@dataclass
class TrackerItemReference(BaseReference):
    type: str = "TrackerItemReference"


@dataclass
class TrackerReference(BaseReference):
    type: str = "TrackerReference"


@dataclass
class Label(DomainModel):
    id: int
    name: str | None = None
    createdAt: str | None = None
    createdBy: UserReference | None = None
    hidden: bool | None = None
    privateLabel: bool | None = None

    def to_dict(self) -> dict[str, Any]:
        return _drop_none({
            "id": self.id,
            "name": self.name,
            "createdAt": self.createdAt,
            "createdBy": self.createdBy,
            "hidden": self.hidden,
            "privateLabel": self.privateLabel,
        })


def _build_reference(raw_value: Any, reference_type: str | None = None) -> Any:
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
    if ref_type in {None, "AbstractReference"}:
        return AbstractReference(id=ref_id, name=ref_name)
    return BaseReference(id=ref_id, name=ref_name, type=ref_type)
