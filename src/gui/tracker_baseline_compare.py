from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import json
from typing import Any

from .tracker_query_models import TrackerItemSummary
from .tracker_query_models import mask_sensitive_payload


class BaselineComparisonKind(str, Enum):
    ADDED = "added"
    REMOVED = "removed"
    CHANGED = "changed"
    UNCHANGED = "unchanged"


@dataclass(frozen=True)
class TrackerBaseline:
    baseline_id: int
    name: str
    created_at: str = ""

    @classmethod
    def from_raw(cls, value: dict[str, Any]) -> "TrackerBaseline":
        baseline_id = int(value.get("id") or 0)
        if baseline_id <= 0:
            raise ValueError("Baseline ID가 올바르지 않습니다.")
        return cls(
            baseline_id=baseline_id,
            name=str(value.get("name") or value.get("label") or baseline_id),
            created_at=str(value.get("createdAt") or ""),
        )


@dataclass(frozen=True)
class BaselineComparisonSource:
    baseline_id: int | None = None

    @property
    def is_head(self) -> bool:
        return self.baseline_id is None

    @property
    def label(self) -> str:
        return "현재 상태" if self.is_head else f"Baseline #{self.baseline_id}"


@dataclass(frozen=True)
class TrackerFieldDifference:
    field_key: str
    label: str
    before: Any
    after: Any
    is_changed: bool

    def before_text(self) -> str:
        return _display_value(self.before)

    def after_text(self) -> str:
        return _display_value(self.after)


@dataclass(frozen=True)
class TrackerItemComparison:
    item_id: int
    kind: BaselineComparisonKind
    before: TrackerItemSummary | None
    after: TrackerItemSummary | None
    fields: tuple[TrackerFieldDifference, ...] = ()

    @property
    def name(self) -> str:
        item = self.after or self.before
        return item.name if item is not None else str(self.item_id)


@dataclass(frozen=True)
class BaselineComparisonResult:
    before_source: BaselineComparisonSource
    after_source: BaselineComparisonSource
    items: tuple[TrackerItemComparison, ...]

    def count(self, kind: BaselineComparisonKind) -> int:
        return sum(item.kind == kind for item in self.items)


def compare_tracker_items(
    before_items: tuple[TrackerItemSummary, ...],
    after_items: tuple[TrackerItemSummary, ...],
    *,
    before_source: BaselineComparisonSource,
    after_source: BaselineComparisonSource,
) -> BaselineComparisonResult:
    if before_source == after_source:
        raise ValueError("서로 다른 두 비교 기준을 선택하세요.")
    before_by_id = {item.item_id: item for item in before_items}
    after_by_id = {item.item_id: item for item in after_items}
    comparisons: list[TrackerItemComparison] = []
    for item_id in sorted(before_by_id.keys() | after_by_id.keys()):
        before = before_by_id.get(item_id)
        after = after_by_id.get(item_id)
        if before is None:
            fields = _field_comparisons({}, after.raw_reference if after is not None else {})
            comparisons.append(
                TrackerItemComparison(
                    item_id,
                    BaselineComparisonKind.ADDED,
                    None,
                    after,
                    fields,
                )
            )
            continue
        if after is None:
            fields = _field_comparisons(before.raw_reference, {})
            comparisons.append(
                TrackerItemComparison(
                    item_id,
                    BaselineComparisonKind.REMOVED,
                    before,
                    None,
                    fields,
                )
            )
            continue
        fields = _field_comparisons(before.raw_reference, after.raw_reference)
        kind = (
            BaselineComparisonKind.CHANGED
            if any(field.is_changed for field in fields)
            else BaselineComparisonKind.UNCHANGED
        )
        comparisons.append(TrackerItemComparison(item_id, kind, before, after, fields))
    return BaselineComparisonResult(before_source, after_source, tuple(comparisons))


def _field_comparisons(
    before: dict[str, Any],
    after: dict[str, Any],
) -> tuple[TrackerFieldDifference, ...]:
    before_fields = _comparison_fields(before)
    after_fields = _comparison_fields(after)
    comparisons: list[TrackerFieldDifference] = []
    missing = object()
    for key in dict.fromkeys((*after_fields, *before_fields)):
        before_entry = before_fields.get(key)
        after_entry = after_fields.get(key)
        before_label, before_compare, before_value = (
            before_entry if before_entry is not None else (key, missing, None)
        )
        after_label, after_compare, after_value = (
            after_entry if after_entry is not None else (key, missing, None)
        )
        comparisons.append(
            TrackerFieldDifference(
                key,
                after_label or before_label,
                before_value,
                after_value,
                before_compare != after_compare,
            )
        )
    return tuple(comparisons)


_FIELD_LABELS = {
    "id": "ID",
    "name": "요약",
    "summary": "요약 (summary)",
    "description": "설명",
    "descriptionFormat": "설명 형식",
    "type": "유형",
    "tracker": "트래커",
    "project": "프로젝트",
    "status": "상태",
    "assignedTo": "담당자",
    "assignees": "담당자 (assignees)",
    "parent": "상위 아이템",
    "children": "하위 아이템",
    "childCount": "하위 아이템 수",
    "hasChildren": "하위 아이템 여부",
    "createdAt": "생성 시각",
    "createdBy": "생성자",
    "modifiedAt": "수정 시각",
    "modifiedBy": "수정자",
    "version": "버전",
}

_FIELD_ORDER = tuple(_FIELD_LABELS)


def _comparison_fields(raw: dict[str, Any]) -> dict[str, tuple[str, Any, Any]]:
    if not isinstance(raw, dict):
        return {}

    def normalize_field(label: str, value: Any) -> tuple[str, Any, Any]:
        return label, _canonical(value), value

    safe_raw = mask_sensitive_payload(raw)
    fields: dict[str, tuple[str, Any, Any]] = {}
    ordered_keys = (
        *(key for key in _FIELD_ORDER if key in safe_raw),
        *(key for key in safe_raw if key not in _FIELD_LABELS and key != "customFields"),
    )
    for key in ordered_keys:
        fields[key] = normalize_field(_FIELD_LABELS.get(key, key), safe_raw[key])

    custom_fields = safe_raw.get("customFields")
    if isinstance(custom_fields, list):
        for index, field in enumerate(custom_fields):
            if not isinstance(field, dict):
                continue
            field_id = field.get("fieldId") if field.get("fieldId") is not None else field.get("id")
            name = str(field.get("name") or field_id or f"custom-{index}")
            key = f"custom:{field_id if field_id is not None else name}"
            value = field.get("values") if "values" in field else field.get("value")
            type_name = str(field.get("type") or field.get("valueModel") or "").strip()
            label = f"{name} ({type_name})" if type_name else name
            fields[key] = normalize_field(label, value)
    elif "customFields" in safe_raw:
        fields["customFields"] = normalize_field("사용자 정의 필드", custom_fields)
    return fields


def _canonical(value: Any) -> Any:
    if isinstance(value, dict):
        reference_keys = {"id", "name", "summary", "type"}
        if value.get("id") is not None and (
            value.get("type") or set(value).issubset(reference_keys)
        ):
            identity = {"id": value.get("id")}
            if value.get("type"):
                identity["type"] = value.get("type")
            return identity
        return {
            str(key): _canonical(nested)
            for key, nested in sorted(value.items())
        }
    if isinstance(value, (list, tuple)):
        return [_canonical(item) for item in value]
    return value


def _display_value(value: Any) -> str:
    if value in (None, "", []):
        return "-"
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True)
    return str(value)


__all__ = [
    "BaselineComparisonKind",
    "BaselineComparisonResult",
    "BaselineComparisonSource",
    "TrackerBaseline",
    "TrackerFieldDifference",
    "TrackerItemComparison",
    "compare_tracker_items",
]
