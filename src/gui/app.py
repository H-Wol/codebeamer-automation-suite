from __future__ import annotations

from .main_window import MainWindow
from .qt import QApplication
from .settings_store import GuiSettingsStore
from .styles import GUI_STYLESHEET


def run_gui() -> int:
    app = QApplication.instance() or QApplication([])
    app.setStyleSheet(GUI_STYLESHEET)
    window = MainWindow(GuiSettingsStore())
    window.show()
    return app.exec()
