from __future__ import annotations

from dataclasses import dataclass
from dataclasses import fields
from typing import Any

from .common import DomainModel
from .common import _drop_none
from .references import UserReference


@dataclass
class UserInfo(DomainModel):
    id: int
    name: str | None = None
    firstName: str | None = None
    lastName: str | None = None
    email: str | None = None
    title: str | None = None
    company: str | None = None
    address: str | None = None
    zip: str | None = None
    city: str | None = None
    state: str | None = None
    country: str | None = None
    dateFormat: str | None = None
    timeZone: str | None = None
    language: str | None = None
    phone: str | None = None
    skills: Any = None
    registryDate: str | None = None
    lastLoginDate: str | None = None
    status: str | None = None
    mobile: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return _drop_none({
            "id": self.id,
            "name": self.name,
            "firstName": self.firstName,
            "lastName": self.lastName,
            "email": self.email,
            "title": self.title,
            "company": self.company,
            "address": self.address,
            "zip": self.zip,
            "city": self.city,
            "state": self.state,
            "country": self.country,
            "dateFormat": self.dateFormat,
            "timeZone": self.timeZone,
            "language": self.language,
            "phone": self.phone,
            "skills": self.skills,
            "registryDate": self.registryDate,
            "lastLoginDate": self.lastLoginDate,
            "status": self.status,
            "mobile": self.mobile,
        })

    @classmethod
    def from_raw(cls, raw_value: dict[str, Any]) -> "UserInfo":
        init_kwargs: dict[str, Any] = {}
        for field_info in fields(cls):
            if field_info.name in raw_value:
                init_kwargs[field_info.name] = raw_value[field_info.name]
        return cls(**init_kwargs)

    def to_reference(self) -> UserReference:
        return UserReference(
            id=self.id,
            name=self.name,
            email=self.email,
        )
