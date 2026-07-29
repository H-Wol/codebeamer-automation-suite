from __future__ import annotations

from .settings_store import GuiSettingsStore
from .styles import build_gui_stylesheet


def run_gui() -> int:
    """PySide6 애플리케이션을 만들고 메인 윈도우를 띄운다."""
    try:
        from PySide6.QtWidgets import QApplication
    except ImportError as exc:
        raise RuntimeError(
            "GUI 실행에는 PySide6 패키지가 필요합니다. requirements.txt 를 설치한 뒤 다시 실행해야 합니다."
        ) from exc

    from .main_window import MainWindow

    store = GuiSettingsStore()
    app = QApplication.instance() or QApplication([])
    app.setStyleSheet(build_gui_stylesheet(store.load().theme_name))
    window = MainWindow(store)
    window.show()
    return app.exec()
