from __future__ import annotations

import importlib
import unittest


class GuiImportCompatibilityTest(unittest.TestCase):
    def test_gui_modules_import_without_runtime_initialization(self) -> None:
        app_module = importlib.import_module("src.gui.app")
        main_window_module = importlib.import_module("src.gui.main_window")
        pages_module = importlib.import_module("src.gui.pages")
        qt_module = importlib.import_module("src.gui.qt")
        worker_module = importlib.import_module("src.gui.worker")

        self.assertTrue(hasattr(app_module, "run_gui"))
        self.assertTrue(hasattr(main_window_module, "MainWindow"))
        self.assertTrue(hasattr(pages_module, "create_settings_page"))
        self.assertTrue(hasattr(qt_module, "QApplication"))
        self.assertTrue(hasattr(qt_module, "QMainWindowBase"))
        self.assertTrue(hasattr(worker_module, "UploadWorker"))
