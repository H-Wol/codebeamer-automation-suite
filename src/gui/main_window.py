from __future__ import annotations

from src.upload_policy import normalize_upload_mode as normalize_gui_upload_mode

from .services import GuiCodebeamerService
from .services import GuiExcelService
from .services import GuiUploadPipelineService
from .settings_store import GuiSettings
from .settings_store import GuiSettingsStore
from .settings_store import GuiWorkflowPreset
from .window_shell import WindowShellMixin
from .window_support import GuiSessionState
from .window_support import UploadProgressState
from .window_support import _estimate_upload_remaining_seconds
from .window_support import _format_clock_text
from .window_support import _format_duration_text
from .window_support import _format_upload_eta_text
from .window_support import _format_upload_progress_text
from .window_support import _merge_root_item_page_configs
from .window_support import _merge_window_preferences
from .window_support import _require_qt
from .window_support import _window_size_from_settings
from .window_upload import WindowUploadMixin
from .window_workflow import WindowWorkflowMixin


_QT = _require_qt()
QMainWindow = _QT["QMainWindow"]


class MainWindow(WindowShellMixin, WindowWorkflowMixin, WindowUploadMixin, QMainWindow):
    """GUI workflow와 업로드 실행을 조합하는 정적 Qt 메인 윈도우."""

    def __init__(self, settings_store: GuiSettingsStore) -> None:
        super().__init__()
        self.qt = _QT
        self.settings_store = settings_store
        initial_settings = settings_store.load()
        self.session_state = GuiSessionState(
            settings=initial_settings,
            file_state={},
            projects=[],
            trackers=[],
            workflow_preset=settings_store.load_workflow_preset(),
            mapping_context=None,
            validation_context=None,
            upload_result=None,
        )
        self.codebeamer_service = GuiCodebeamerService()
        self.excel_service = GuiExcelService()
        self.pipeline_service = GuiUploadPipelineService()
        self.upload_worker = None
        self.background_task = None
        self.upload_progress = UploadProgressState()
        self._build_shell()
        self._build_pages()

        self.setWindowTitle("Codebeamer Upload Studio")
        self.resize(*_window_size_from_settings(initial_settings))
        normalized_theme = self._apply_theme(initial_settings.theme_name)
        self.session_state.settings = GuiSettings(
            **{
                **initial_settings.__dict__,
                "theme_name": normalized_theme,
            }
        )
        self.statusBar().showMessage("설정 페이지를 확인하세요.")
        self._show_page(self.settings_page)

        if bool(getattr(initial_settings, "window_is_fullscreen", False)):
            self.showFullScreen()
        elif bool(getattr(initial_settings, "window_is_maximized", False)):
            self.showMaximized()
        if self.session_state.workflow_preset is not None:
            self._apply_workflow_preset(self.session_state.workflow_preset, startup=True)


__all__ = [
    "MainWindow",
    "_estimate_upload_remaining_seconds",
    "_format_clock_text",
    "_format_duration_text",
    "_format_upload_eta_text",
    "_format_upload_progress_text",
    "_merge_root_item_page_configs",
    "_merge_window_preferences",
    "_window_size_from_settings",
]
