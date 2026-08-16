from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DetailLocation:
    item_id: int
    version: int | None = None


class TrackerItemDetailSession:
    """상세 창의 독립 이동 기록과 stale 응답 세대를 관리한다."""

    def __init__(self, item_id: int, version: int | None = None, *, max_entries: int = 50) -> None:
        self.max_entries = max(1, int(max_entries))
        self._entries = [DetailLocation(int(item_id), version)]
        self._index = 0
        self._generation = 0

    @property
    def current(self) -> DetailLocation:
        return self._entries[self._index]

    @property
    def can_go_back(self) -> bool:
        return self._index > 0

    @property
    def can_go_forward(self) -> bool:
        return self._index + 1 < len(self._entries)

    @property
    def generation(self) -> int:
        return self._generation

    def navigate(self, item_id: int, version: int | None = None) -> DetailLocation:
        target = DetailLocation(int(item_id), version)
        if target.item_id == self.current.item_id:
            return self.current
        del self._entries[self._index + 1:]
        self._entries.append(target)
        if len(self._entries) > self.max_entries:
            del self._entries[:len(self._entries) - self.max_entries]
        self._index = len(self._entries) - 1
        self._generation += 1
        return self.current

    def back(self) -> DetailLocation | None:
        if not self.can_go_back:
            return None
        self._index -= 1
        self._generation += 1
        return self.current

    def forward(self) -> DetailLocation | None:
        if not self.can_go_forward:
            return None
        self._index += 1
        self._generation += 1
        return self.current

    def invalidate(self) -> int:
        self._generation += 1
        return self._generation


__all__ = ["DetailLocation", "TrackerItemDetailSession"]
