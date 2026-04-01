from __future__ import annotations

from typing import Sequence


def choose_one(prompt: str, items: Sequence[str], default_index: int | None = None) -> int:
    if not items:
        raise ValueError("선택 가능한 항목이 없습니다.")

    while True:
        print(f"\n{prompt}")
        for idx, item in enumerate(items, start=1):
            default_mark = " [default]" if default_index == idx - 1 else ""
            print(f"  {idx}. {item}{default_mark}")

        raw = input("> 번호 선택" + (" (Enter=default)" if default_index is not None else "") + ": ").strip()
        if raw == "" and default_index is not None:
            return default_index
        if raw.isdigit():
            selected = int(raw) - 1
            if 0 <= selected < len(items):
                return selected
        print("잘못된 입력입니다. 다시 선택해 주세요.")


def choose_many(prompt: str, items: Sequence[str], default_indices: Sequence[int] | None = None) -> list[int]:
    default_indices = list(default_indices or [])

    while True:
        print(f"\n{prompt}")
        for idx, item in enumerate(items, start=1):
            default_mark = " [default]" if idx - 1 in default_indices else ""
            print(f"  {idx}. {item}{default_mark}")

        raw = input("> 여러 개 선택 (예: 1,3,5 / Enter=default 또는 none): ").strip()
        if raw == "":
            return default_indices
        if raw.lower() == "none":
            return []

        parts = [p.strip() for p in raw.split(",") if p.strip()]
        if all(p.isdigit() for p in parts):
            values = sorted({int(p) - 1 for p in parts})
            if values and min(values) >= 0 and max(values) < len(items):
                return values
        print("잘못된 입력입니다. 다시 선택해 주세요.")


def confirm(prompt: str, default: bool = True) -> bool:
    suffix = "[Y/n]" if default else "[y/N]"
    raw = input(f"{prompt} {suffix}: ").strip().lower()
    if raw == "":
        return default
    return raw in {"y", "yes"}
