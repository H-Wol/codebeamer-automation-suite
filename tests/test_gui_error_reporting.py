from __future__ import annotations

import os
import sys
import threading
import unittest


os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication
from PySide6.QtWidgets import QPushButton

from src.gui.error_reporting import install_global_exception_handler
from src.gui.error_reporting import safe_exception_message


class GuiErrorReportingTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        existing = getattr(self._app, "_codebeamer_gui_exception_reporter", None)
        if existing is not None:
            existing.restore()
        self.alerts: list[tuple[str, str]] = []
        self.logged: list[tuple[str, str, str]] = []
        self.reporter = install_global_exception_handler(
            self._app,
            alert_handler=lambda title, message: self.alerts.append((title, message)),
            exception_logger=lambda exc_type, exc_value, _traceback, thread_name: (
                self.logged.append((exc_type.__name__, str(exc_value), thread_name))
            ),
        )

    def tearDown(self) -> None:
        self.reporter.restore()

    def test_unhandled_qt_slot_exception_is_logged_and_alerted(self) -> None:
        button = QPushButton("실행")

        def fail() -> None:
            raise AttributeError("status_label이 없습니다")

        button.clicked.connect(fail)
        button.click()
        self._app.processEvents()

        self.assertEqual(
            self.logged[0][:2],
            ("AttributeError", "status_label이 없습니다"),
        )
        self.assertEqual(self.alerts[0][0], "예상하지 못한 오류")
        self.assertIn("AttributeError", self.alerts[0][1])
        self.assertIn("status_label", self.alerts[0][1])

    def test_unhandled_python_thread_exception_is_forwarded_to_gui(self) -> None:
        def fail() -> None:
            raise RuntimeError("worker failed")

        thread = threading.Thread(target=fail, name="sample-worker")
        thread.start()
        thread.join()
        self._app.processEvents()

        self.assertEqual(
            self.logged[0],
            ("RuntimeError", "worker failed", "sample-worker"),
        )
        self.assertEqual(self.alerts[0][0], "예상하지 못한 오류")
        self.assertIn("worker failed", self.alerts[0][1])

    def test_install_is_idempotent_and_restore_recovers_hooks(self) -> None:
        sys_hook = self.reporter._previous_sys_hook
        thread_hook = self.reporter._previous_thread_hook

        same = install_global_exception_handler(self._app)

        self.assertIs(same, self.reporter)
        self.reporter.restore()
        self.assertIs(sys.excepthook, sys_hook)
        self.assertIs(threading.excepthook, thread_hook)

    def test_safe_message_redacts_credentials_and_limits_length(self) -> None:
        message = safe_exception_message(
            RuntimeError("token=secret password:guess " + ("x" * 2000))
        )

        self.assertNotIn("secret", message)
        self.assertNotIn("guess", message)
        self.assertLessEqual(len(message), 1200)


if __name__ == "__main__":
    unittest.main()
