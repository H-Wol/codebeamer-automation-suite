from __future__ import annotations


def run_gui() -> int:
    """GUI 실행 엔트리 포인트를 필요할 때만 로드한다."""
    from .app import run_gui as _run_gui

    return _run_gui()


__all__ = ["run_gui"]
