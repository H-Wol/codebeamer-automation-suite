from __future__ import annotations

from functools import lru_cache
from typing import Any


@lru_cache(maxsize=1)
def require_qt() -> dict[str, Any]:
    """GUI 모듈이 공유하는 PySide6 바인딩을 한 번만 로드한다."""
    try:
        from PySide6.QtCore import QEventLoop
        from PySide6.QtCore import QSize
        from PySide6.QtCore import Qt
        from PySide6.QtCore import QThread
        from PySide6.QtCore import Signal
        from PySide6.QtWidgets import QApplication
        from PySide6.QtWidgets import QCheckBox
        from PySide6.QtWidgets import QComboBox
        from PySide6.QtWidgets import QDoubleSpinBox
        from PySide6.QtWidgets import QFileDialog
        from PySide6.QtWidgets import QFormLayout
        from PySide6.QtWidgets import QFrame
        from PySide6.QtWidgets import QHBoxLayout
        from PySide6.QtWidgets import QHeaderView
        from PySide6.QtWidgets import QLabel
        from PySide6.QtWidgets import QLineEdit
        from PySide6.QtWidgets import QMainWindow
        from PySide6.QtWidgets import QMessageBox
        from PySide6.QtWidgets import QPlainTextEdit
        from PySide6.QtWidgets import QProgressBar
        from PySide6.QtWidgets import QPushButton
        from PySide6.QtWidgets import QSizePolicy
        from PySide6.QtWidgets import QSpinBox
        from PySide6.QtWidgets import QStackedWidget
        from PySide6.QtWidgets import QStatusBar
        from PySide6.QtWidgets import QTabWidget
        from PySide6.QtWidgets import QTableWidget
        from PySide6.QtWidgets import QTableWidgetItem
        from PySide6.QtWidgets import QToolButton
        from PySide6.QtWidgets import QVBoxLayout
        from PySide6.QtWidgets import QWidget
    except ImportError as exc:
        raise RuntimeError("GUI 실행에는 PySide6 패키지가 필요합니다.") from exc

    return {
        "QApplication": QApplication,
        "QCheckBox": QCheckBox,
        "QComboBox": QComboBox,
        "QDoubleSpinBox": QDoubleSpinBox,
        "QEventLoop": QEventLoop,
        "QFileDialog": QFileDialog,
        "QFormLayout": QFormLayout,
        "QFrame": QFrame,
        "QHBoxLayout": QHBoxLayout,
        "QHeaderView": QHeaderView,
        "QLabel": QLabel,
        "QLineEdit": QLineEdit,
        "QMainWindow": QMainWindow,
        "QMessageBox": QMessageBox,
        "QPlainTextEdit": QPlainTextEdit,
        "QProgressBar": QProgressBar,
        "QPushButton": QPushButton,
        "QSize": QSize,
        "QSizePolicy": QSizePolicy,
        "QSpinBox": QSpinBox,
        "QStackedWidget": QStackedWidget,
        "QStatusBar": QStatusBar,
        "QTabWidget": QTabWidget,
        "QTableWidget": QTableWidget,
        "QTableWidgetItem": QTableWidgetItem,
        "QThread": QThread,
        "QToolButton": QToolButton,
        "QVBoxLayout": QVBoxLayout,
        "QWidget": QWidget,
        "Qt": Qt,
        "Signal": Signal,
    }
