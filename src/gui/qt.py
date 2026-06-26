from __future__ import annotations


MISSING_QT_MESSAGE = "GUI 실행에는 PySide6 패키지가 필요합니다."
QT_IMPORT_ERROR: ImportError | None = None


class _QtFallbackBase:
    """PySide6 미설치 환경에서도 모듈 import 는 허용하고, 실제 사용 시에만 실패시킨다."""

    def __init__(self, *args, **kwargs) -> None:
        del args, kwargs
        raise RuntimeError(MISSING_QT_MESSAGE) from QT_IMPORT_ERROR

    @classmethod
    def instance(cls):
        return None


class _QtFallbackNamespace:
    def __getattr__(self, _name: str):
        raise RuntimeError(MISSING_QT_MESSAGE) from QT_IMPORT_ERROR


class _QtFallbackSignal:
    def connect(self, *args, **kwargs) -> None:
        del args, kwargs
        raise RuntimeError(MISSING_QT_MESSAGE) from QT_IMPORT_ERROR

    def emit(self, *args, **kwargs) -> None:
        del args, kwargs
        raise RuntimeError(MISSING_QT_MESSAGE) from QT_IMPORT_ERROR


def _fallback_signal(*args, **kwargs) -> _QtFallbackSignal:
    del args, kwargs
    return _QtFallbackSignal()


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
    QT_IMPORT_ERROR = exc
    QApplication = _QtFallbackBase
    QCheckBox = _QtFallbackBase
    QComboBox = _QtFallbackBase
    QDoubleSpinBox = _QtFallbackBase
    QEventLoop = _QtFallbackBase
    QFileDialog = _QtFallbackBase
    QFrame = _QtFallbackBase
    QHBoxLayout = _QtFallbackBase
    QLabel = _QtFallbackBase
    QLineEdit = _QtFallbackBase
    QMainWindow = _QtFallbackBase
    QMessageBox = _QtFallbackBase
    QPlainTextEdit = _QtFallbackBase
    QProgressBar = _QtFallbackBase
    QPushButton = _QtFallbackBase
    QSize = _QtFallbackBase
    QSpinBox = _QtFallbackBase
    QStackedWidget = _QtFallbackBase
    QStatusBar = _QtFallbackBase
    QTabWidget = _QtFallbackBase
    QTableWidget = _QtFallbackBase
    QTableWidgetItem = _QtFallbackBase
    QToolButton = _QtFallbackBase
    QVBoxLayout = _QtFallbackBase
    QWidget = _QtFallbackBase
    Qt = _QtFallbackNamespace()
    QFormLayout = _QtFallbackNamespace()
    QHeaderView = _QtFallbackNamespace()
    QSizePolicy = _QtFallbackNamespace()
    QThread = _QtFallbackBase
    Signal = _fallback_signal


QMainWindowBase = QMainWindow
QThreadBase = QThread


__all__ = [
    "MISSING_QT_MESSAGE",
    "QT_IMPORT_ERROR",
    "QApplication",
    "QCheckBox",
    "QComboBox",
    "QDoubleSpinBox",
    "QEventLoop",
    "QFileDialog",
    "QFormLayout",
    "QFrame",
    "QHBoxLayout",
    "QHeaderView",
    "QLabel",
    "QLineEdit",
    "QMainWindow",
    "QMainWindowBase",
    "QMessageBox",
    "QPlainTextEdit",
    "QProgressBar",
    "QPushButton",
    "QSize",
    "QSizePolicy",
    "QSpinBox",
    "QStackedWidget",
    "QStatusBar",
    "QTabWidget",
    "QTableWidget",
    "QTableWidgetItem",
    "QThread",
    "QThreadBase",
    "QToolButton",
    "QVBoxLayout",
    "QWidget",
    "Qt",
    "Signal",
]
