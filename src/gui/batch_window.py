from __future__ import annotations

from collections.abc import Callable

from .services import GuiCodebeamerService
from .services import GuiExcelService
from .services import GuiUploadPipelineService
from .settings_store import GuiSettings
from .settings_store import GuiSettingsStore
from .window_shell import WindowShellMixin
from .window_support import GuiSessionState
from .window_support import UploadProgressState
from .window_support import _require_qt
from .window_support import _window_size_from_settings
from .window_upload import WindowUploadMixin
from .window_workflow import WindowWorkflowMixin


_QT = _require_qt()
QMainWindow = _QT["QMainWindow"]


class BatchUploadWindow(WindowShellMixin, WindowWorkflowMixin, WindowUploadMixin, QMainWindow):
    """기존 9단계 create/update/upsert 마법사를 제공한다."""

    def __init__(
        self,
        settings_store: GuiSettingsStore,
        *,
        parent=None,
        embedded: bool = False,
        settings_changed_callback: Callable[[GuiSettings], None] | None = None,
        global_settings_requested_callback: Callable[[], None] | None = None,
    ) -> None:
        super().__init__(parent)
        self.qt = _QT
        self.settings_store = settings_store
        self._embedded = bool(embedded)
        self._persist_window_preferences_on_close = not self._embedded
        self._settings_changed_callback = settings_changed_callback
        self._global_settings_requested_callback = global_settings_requested_callback
        if self._embedded:
            self.setWindowFlags(self.qt["Qt"].WindowType.Widget)

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
        if not self._embedded:
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

        if not self._embedded:
            if bool(getattr(initial_settings, "window_is_fullscreen", False)):
                self.showFullScreen()
            elif bool(getattr(initial_settings, "window_is_maximized", False)):
                self.showMaximized()
        if self.session_state.workflow_preset is not None:
            self._apply_workflow_preset(self.session_state.workflow_preset, startup=True)

    def _on_settings_changed(self, settings: GuiSettings | None) -> GuiSettings:
        updated_settings = WindowWorkflowMixin._on_settings_changed(self, settings)
        if self._settings_changed_callback is not None:
            self._settings_changed_callback(updated_settings)
        return updated_settings

    def apply_global_settings(self, settings: GuiSettings) -> GuiSettings:
        """전용 설정 센터에서 적용한 전역 설정을 현재 배치 세션에 반영한다."""

        current = self.session_state.settings
        merged = GuiSettings(
            **{
                **settings.__dict__,
                "upload_mode": current.upload_mode,
                "excel_header_row": current.excel_header_row,
                "summary_column": current.summary_column,
                "excel_sheet_name": current.excel_sheet_name,
                "last_file_path": current.last_file_path,
            }
        )
        updated = self._on_settings_changed(merged)
        set_settings = getattr(self.settings_page, "set_settings", None)
        if callable(set_settings):
            set_settings(updated)
        return updated

__all__ = ["BatchUploadWindow"]
