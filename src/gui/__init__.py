from __future__ import annotations


def run_gui() -> int:
    """PySide6 의존성을 실제 GUI 실행 시점까지 늦춘다."""
    from .app import run_gui as _run_gui

    return _run_gui()

__all__ = ["run_gui"]
