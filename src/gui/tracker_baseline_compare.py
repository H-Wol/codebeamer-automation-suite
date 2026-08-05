from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import json
from typing import Any

from .tracker_query_models import TrackerItemSummary


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
            comparisons.append(TrackerItemComparison(item_id, BaselineComparisonKind.ADDED, None, after))
            continue
        if after is None:
            comparisons.append(TrackerItemComparison(item_id, BaselineComparisonKind.REMOVED, before, None))
            continue
        differences = _field_differences(before.raw_reference, after.raw_reference)
        kind = BaselineComparisonKind.CHANGED if differences else BaselineComparisonKind.UNCHANGED
        comparisons.append(TrackerItemComparison(item_id, kind, before, after, differences))
    return BaselineComparisonResult(before_source, after_source, tuple(comparisons))


def _field_differences(before: dict[str, Any], after: dict[str, Any]) -> tuple[TrackerFieldDifference, ...]:
    before_fields = _comparison_fields(before)
    after_fields = _comparison_fields(after)
    differences: list[TrackerFieldDifference] = []
    for key in sorted(before_fields.keys() | after_fields.keys()):
        before_label, before_compare, before_value = before_fields.get(key, (key, None, None))
        after_label, after_compare, after_value = after_fields.get(key, (key, None, None))
        if before_compare != after_compare:
            differences.append(TrackerFieldDifference(key, after_label or before_label, before_value, after_value))
    return tuple(differences)


def _comparison_fields(raw: dict[str, Any]) -> dict[str, tuple[str, Any, Any]]:
    if not isinstance(raw, dict):
        return {}
    def normalize_field(label: str, value: Any) -> tuple[str, Any, Any]:
        return label, _canonical(value), value

    fields: dict[str, tuple[str, Any, Any]] = {
        "summary": normalize_field("요약", raw.get("name") if raw.get("name") is not None else raw.get("summary")),
        "description": normalize_field("설명", raw.get("description")),
        "descriptionFormat": normalize_field("설명 형식", raw.get("descriptionFormat")),
        "status": normalize_field("상태", raw.get("status")),
        "assignedTo": normalize_field("담당자", raw.get("assignedTo") or []),
        "parent": normalize_field("상위 아이템", raw.get("parent")),
    }
    custom_fields = raw.get("customFields")
    if isinstance(custom_fields, list):
        for index, field in enumerate(custom_fields):
            if not isinstance(field, dict):
                continue
            field_id = field.get("fieldId") if field.get("fieldId") is not None else field.get("id")
            name = str(field.get("name") or field_id or f"custom-{index}")
            key = f"custom:{field_id if field_id is not None else name}"
            value = field.get("values") if "values" in field else field.get("value")
            fields[key] = normalize_field(name, value)
    return fields


def _canonical(value: Any) -> Any:
    if isinstance(value, dict):
        if value.get("id") is not None and value.get("type"):
            return {"id": value.get("id"), "type": value.get("type")}
        return {str(key): _canonical(nested) for key, nested in sorted(value.items()) if key not in {"modifiedAt", "version", "name", "summary"}}
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
