from __future__ import annotations

from dataclasses import dataclass
from dataclasses import fields
from typing import Any
from typing import ClassVar

from .common import DomainModel
from .common import _drop_none


@dataclass
class BaseReference(DomainModel):
    TYPE_NAME: ClassVar[str | None] = None
    _TYPE_REGISTRY: ClassVar[dict[str, type["BaseReference"]]] = {}

    id: int
    name: str | None = None
    type: str | None = None

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        if cls.TYPE_NAME:
            BaseReference._TYPE_REGISTRY[cls.TYPE_NAME] = cls

    def to_dict(self) -> dict[str, Any]:
        return _drop_none({
            "id": self.id,
            "name": self.name,
            "type": self.type,
        })

    @classmethod
    def from_raw(
        cls,
        raw_value: dict[str, Any],
        reference_type: str | None = None,
    ) -> "BaseReference":
        resolved_type = raw_value.get("type") or reference_type or cls.TYPE_NAME
        init_kwargs: dict[str, Any] = {}

        for field_info in fields(cls):
            if not field_info.init:
                continue
            if field_info.name == "type":
                init_kwargs["type"] = resolved_type
                continue
            if field_info.name in raw_value:
                init_kwargs[field_info.name] = raw_value[field_info.name]

        return cls(**init_kwargs)

    @classmethod
    def resolve_type(cls, reference_type: str | None) -> type["BaseReference"]:
        if reference_type in {None, "AbstractReference"}:
            return AbstractReference
        return cls._TYPE_REGISTRY.get(reference_type, BaseReference)


@dataclass
class AbstractReference(BaseReference):
    TYPE_NAME: ClassVar[str] = "AbstractReference"
    type: str = "AbstractReference"


@dataclass
class ChoiceOptionReference(BaseReference):
    TYPE_NAME: ClassVar[str] = "ChoiceOptionReference"
    type: str = "ChoiceOptionReference"


@dataclass
class CommentReference(BaseReference):
    TYPE_NAME: ClassVar[str] = "CommentReference"
    type: str = "CommentReference"


@dataclass
class ProjectReference(BaseReference):
    TYPE_NAME: ClassVar[str] = "ProjectReference"
    type: str = "ProjectReference"


@dataclass
class RepositoryReference(BaseReference):
    TYPE_NAME: ClassVar[str] = "RepositoryReference"
    type: str = "RepositoryReference"


@dataclass
class RoleReference(BaseReference):
    TYPE_NAME: ClassVar[str] = "RoleReference"
    type: str = "RoleReference"


@dataclass
class TrackerPermissionReference(BaseReference):
    TYPE_NAME: ClassVar[str] = "TrackerPermissionReference"
    type: str = "TrackerPermissionReference"


@dataclass
class UserReference(BaseReference):
    TYPE_NAME: ClassVar[str] = "UserReference"
    type: str = "UserReference"
    email: str | None = None


@dataclass
class TrackerItemReference(BaseReference):
    TYPE_NAME: ClassVar[str] = "TrackerItemReference"
    type: str = "TrackerItemReference"


@dataclass
class TrackerReference(BaseReference):
    TYPE_NAME: ClassVar[str] = "TrackerReference"
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

    resolved_type = raw_value.get("type") or reference_type
    reference_cls = BaseReference.resolve_type(resolved_type)
    return reference_cls.from_raw(raw_value, reference_type=resolved_type)
