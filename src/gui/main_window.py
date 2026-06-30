from __future__ import annotations

from dataclasses import dataclass
from dataclasses import replace
from datetime import datetime
from pathlib import Path
import time

from .pages import create_file_selection_page
from .pages import create_mapping_page
from .pages import create_project_selection_page
from .pages import create_root_item_page
from .pages import create_settings_page
from .pages import create_validation_page
from .pages import create_upload_page
from .pages import create_result_page
from .services import GuiCodebeamerService
from .services import GuiExcelService
from .services import GuiUploadPipelineService
from .settings_store import GuiSettings
from .settings_store import GuiSettingsStore
from .settings_store import GuiWorkflowPreset
from .worker import BackgroundTask
from .worker import UploadWorker


def _require_qt():
    try:
        from PySide6.QtCore import QEventLoop
        from PySide6.QtCore import QSize
        from PySide6.QtCore import Qt
        from PySide6.QtWidgets import QApplication
        from PySide6.QtWidgets import QFrame
        from PySide6.QtWidgets import QHBoxLayout
        from PySide6.QtWidgets import QLabel
        from PySide6.QtWidgets import QMainWindow
        from PySide6.QtWidgets import QMessageBox
        from PySide6.QtWidgets import QProgressBar
        from PySide6.QtWidgets import QPushButton
        from PySide6.QtWidgets import QStackedWidget
        from PySide6.QtWidgets import QStatusBar
        from PySide6.QtWidgets import QVBoxLayout
        from PySide6.QtWidgets import QWidget
    except ImportError as exc:
        raise RuntimeError("GUI 실행에는 PySide6 패키지가 필요합니다.") from exc

    return {
        "QApplication": QApplication,
        "QEventLoop": QEventLoop,
        "QFrame": QFrame,
        "QHBoxLayout": QHBoxLayout,
        "QLabel": QLabel,
        "QMainWindow": QMainWindow,
        "QMessageBox": QMessageBox,
        "QProgressBar": QProgressBar,
        "QPushButton": QPushButton,
        "QSize": QSize,
        "QStackedWidget": QStackedWidget,
        "QStatusBar": QStatusBar,
        "Qt": Qt,
        "QVBoxLayout": QVBoxLayout,
        "QWidget": QWidget,
    }


@dataclass
class GuiSessionState:
    settings: GuiSettings
    file_state: dict[str, object]
    projects: list[dict[str, object]]
    trackers: list[dict[str, object]]
    workflow_preset: GuiWorkflowPreset | None
    mapping_context: object | None
    validation_context: object | None
    upload_result: dict[str, object] | None


class MainWindow:
    """단계형 GUI 스켈레톤을 제공한다."""

    def __new__(cls, settings_store: GuiSettingsStore):
        qt = _require_qt()
        base_cls = qt["QMainWindow"]

        class _MainWindow(base_cls):
            def __init__(self, store: GuiSettingsStore) -> None:
                super().__init__()
                self.qt = qt
                self.settings_store = store
                self.session_state = GuiSessionState(
                    settings=store.load(),
                    file_state={},
                    projects=[],
                    trackers=[],
                    workflow_preset=store.load_workflow_preset(),
                    mapping_context=None,
                    validation_context=None,
                    upload_result=None,
                )
                self.codebeamer_service = GuiCodebeamerService()
                self.excel_service = GuiExcelService()
                self.pipeline_service = GuiUploadPipelineService()
                self.upload_worker = None
                self.busy_task = None
                self.upload_success_count = 0
                self.upload_failed_count = 0
                self.upload_retry_count = 0
                self.upload_total_count = 0
                self._upload_event_started_at = {}
                self._upload_batch_started_at = None
                self.setWindowTitle("Codebeamer Upload GUI")
                self.resize(qt["QSize"](920, 500))
                self.setMinimumSize(qt["QSize"](760, 400))
                self._build_shell()
                self.setStatusBar(qt["QStatusBar"]())
                self._build_pages()

            def _build_shell(self) -> None:
                QWidget = self.qt["QWidget"]
                QVBoxLayout = self.qt["QVBoxLayout"]
                QHBoxLayout = self.qt["QHBoxLayout"]
                QLabel = self.qt["QLabel"]
                QProgressBar = self.qt["QProgressBar"]
                Qt = self.qt["Qt"]
                QFrame = self.qt["QFrame"]
                QPushButton = self.qt["QPushButton"]

                root = QWidget()
                root.setObjectName("app_root")
                self.root_widget = root
                root_layout = QVBoxLayout(root)
                root_layout.setContentsMargins(14, 12, 14, 12)
                root_layout.setSpacing(10)

                header_card = QFrame()
                header_card.setObjectName("header_card")
                header_layout = QVBoxLayout(header_card)
                header_layout.setContentsMargins(14, 12, 14, 12)
                header_layout.setSpacing(6)

                title = QLabel("Codebeamer Upload Studio")
                title.setObjectName("app_title")
                subtitle = QLabel("현대케피코용 업로드 작업을 단계별로 확인하고 실행하는 도구")
                subtitle.setObjectName("app_subtitle")

                title_row = QHBoxLayout()
                title_row.setSpacing(8)
                title_row.addWidget(title)
                title_row.addStretch(1)

                self.load_workflow_button = QPushButton("전체 설정 불러오기")
                self.save_workflow_button = QPushButton("전체 설정 저장")
                title_row.addWidget(self.load_workflow_button)
                title_row.addWidget(self.save_workflow_button)

                header_layout.addLayout(title_row)
                header_layout.addWidget(subtitle)

                steps_row = QHBoxLayout()
                steps_row.setSpacing(8)
                self.step_labels = []
                for step_name in ("설정", "프로젝트", "파일", "상단 데이터", "매핑", "검증", "업로드", "결과"):
                    label = QLabel(step_name)
                    label.setObjectName("step_badge")
                    steps_row.addWidget(label)
                    self.step_labels.append(label)
                steps_row.addStretch(1)
                header_layout.addLayout(steps_row)

                self.page_title_label = QLabel("")
                self.page_title_label.setObjectName("page_title")
                self.page_subtitle_label = QLabel("")
                self.page_subtitle_label.setObjectName("app_subtitle")
                header_layout.addWidget(self.page_title_label)
                header_layout.addWidget(self.page_subtitle_label)

                self.stack_card = QFrame()
                self.stack_card.setObjectName("page_card")
                stack_layout = QVBoxLayout(self.stack_card)
                stack_layout.setContentsMargins(8, 8, 8, 8)
                stack_layout.setSpacing(0)
                self.stack = self.qt["QStackedWidget"]()
                stack_layout.addWidget(self.stack)

                root_layout.addWidget(header_card)
                root_layout.addWidget(self.stack_card, 1)

                self.busy_overlay = QWidget(root)
                self.busy_overlay.setObjectName("busy_overlay")
                self.busy_overlay.hide()
                overlay_layout = QVBoxLayout(self.busy_overlay)
                overlay_layout.setContentsMargins(0, 0, 0, 0)
                overlay_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

                busy_card = QFrame(self.busy_overlay)
                busy_card.setObjectName("busy_card")
                busy_card_layout = QVBoxLayout(busy_card)
                busy_card_layout.setContentsMargins(22, 20, 22, 18)
                busy_card_layout.setSpacing(10)

                busy_title = QLabel("작업 중")
                busy_title.setObjectName("busy_title")
                self.busy_message_label = QLabel("잠시만 기다려 주세요.")
                self.busy_message_label.setObjectName("busy_message")
                self.busy_message_label.setWordWrap(True)
                self.busy_progress = QProgressBar()
                self.busy_progress.setObjectName("busy_progress")
                self.busy_progress.setRange(0, 0)
                self.busy_progress.setTextVisible(False)

                busy_card_layout.addWidget(busy_title)
                busy_card_layout.addWidget(self.busy_message_label)
                busy_card_layout.addWidget(self.busy_progress)
                overlay_layout.addWidget(busy_card)

                self.setCentralWidget(root)
                self._update_busy_overlay_geometry()

            def _content_height_for_page(self, page) -> int:
                if page is None:
                    return self.height()

                root_layout = self.root_widget.layout()
                stack_layout = self.stack_card.layout()
                header_item = root_layout.itemAt(0)
                header_widget = None if header_item is None else header_item.widget()
                header_height = 0 if header_widget is None else header_widget.sizeHint().height()

                page_layout = page.layout()
                if page_layout is not None:
                    page_layout.invalidate()
                    page_layout.activate()
                page.adjustSize()

                root_margins = root_layout.contentsMargins()
                stack_margins = stack_layout.contentsMargins()
                status_height = 0 if self.statusBar() is None else self.statusBar().sizeHint().height()
                stack_frame_height = self.stack_card.frameWidth() * 2

                return (
                    root_margins.top()
                    + header_height
                    + root_layout.spacing()
                    + stack_frame_height
                    + stack_margins.top()
                    + page.sizeHint().height()
                    + stack_margins.bottom()
                    + root_margins.bottom()
                    + status_height
                )

            def _fit_window_to_current_page(self, *, allow_grow: bool) -> None:
                page = self.stack.currentWidget() if hasattr(self, "stack") else None
                if page is None:
                    return

                target_height = max(self.minimumHeight(), self._content_height_for_page(page))
                if not allow_grow and target_height >= self.height():
                    return

                self.resize(self.width(), target_height)
                self.updateGeometry()

            def _update_busy_overlay_geometry(self) -> None:
                if hasattr(self, "busy_overlay") and hasattr(self, "root_widget"):
                    self.busy_overlay.setGeometry(self.root_widget.rect())
                    self.busy_overlay.raise_()

            def resizeEvent(self, event) -> None:
                super().resizeEvent(event)
                self._update_busy_overlay_geometry()

            def _set_busy(self, busy: bool, message: str = "") -> None:
                QApplication = self.qt["QApplication"]
                Qt = self.qt["Qt"]

                if busy:
                    self.busy_message_label.setText(message or "잠시만 기다려 주세요.")
                    self._update_busy_overlay_geometry()
                    self.busy_overlay.show()
                    self.busy_overlay.raise_()
                    QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
                    QApplication.processEvents()
                    return

                self.busy_overlay.hide()
                QApplication.restoreOverrideCursor()
                QApplication.processEvents()

            def _run_with_busy(self, message: str, func, *args, **kwargs):
                QEventLoop = self.qt["QEventLoop"]
                loop = QEventLoop(self)
                task = BackgroundTask(func, *args, **kwargs)
                result_box: dict[str, object] = {}

                def _on_completed(result: object) -> None:
                    result_box["result"] = result
                    loop.quit()

                def _on_failed(error: object) -> None:
                    result_box["error"] = error
                    loop.quit()

                task.completed.connect(_on_completed)
                task.failed.connect(_on_failed)
                self.busy_task = task
                self._set_busy(True, message)
                task.start()

                try:
                    loop.exec()
                finally:
                    task.wait()
                    task.deleteLater()
                    self.busy_task = None
                    self._set_busy(False)

                if "error" in result_box:
                    error = result_box["error"]
                    if isinstance(error, Exception):
                        raise error
                    raise RuntimeError(str(error))

                return result_box.get("result")

            def _build_pages(self) -> None:
                self.settings_page = create_settings_page(
                    self.settings_store,
                    self.session_state.settings,
                    self._on_settings_changed,
                )
                self.project_page = create_project_selection_page(
                    self.session_state.settings,
                    self._on_settings_changed,
                    self._test_connection,
                    self._load_trackers,
                    self._show_error_dialog,
                )
                self.file_page = create_file_selection_page(
                    self.session_state.settings,
                    self._on_file_state_changed,
                    self._load_file_preview,
                    self._show_error_dialog,
                )
                self.root_item_page = create_root_item_page(self._preview_root_item_config)
                self.mapping_page = create_mapping_page(
                    self._validate_mapping,
                    self._show_error_dialog,
                )
                self.validation_page = create_validation_page()
                self.upload_page = create_upload_page(
                    self._start_upload,
                    self._pause_upload,
                    self._resume_upload,
                    self._cancel_upload,
                )
                self.result_page = create_result_page()

                self.load_workflow_button.clicked.connect(self._load_workflow_preset)
                self.save_workflow_button.clicked.connect(self._save_workflow_preset)

                self._attach_navigation(self.settings_page, next_page=self.project_page)
                self._attach_navigation(
                    self.project_page,
                    previous_page=self.settings_page,
                    next_page=self.file_page,
                )
                self._attach_navigation(
                    self.file_page,
                    previous_page=self.project_page,
                    next_handler=self._on_prepare_root_item_context,
                )
                self._attach_navigation(
                    self.root_item_page,
                    previous_page=self.file_page,
                    next_handler=self._on_confirm_root_item_config,
                )
                self._attach_navigation(
                    self.mapping_page,
                    previous_page=self.root_item_page,
                    next_page=self.validation_page,
                    next_handler=self._enter_validation_page,
                )
                self._attach_navigation(
                    self.validation_page,
                    previous_page=self.mapping_page,
                    next_page=self.upload_page,
                    next_handler=self._enter_upload_page,
                )
                self._attach_navigation(
                    self.upload_page,
                    previous_page=self.validation_page,
                    next_page=self.result_page,
                    next_handler=self._enter_result_page,
                )
                self._attach_navigation(
                    self.result_page,
                    previous_page=self.upload_page,
                    restart_handler=self._restart_upload_flow,
                )

                for page in (
                    self.settings_page,
                    self.project_page,
                    self.file_page,
                    self.root_item_page,
                    self.mapping_page,
                    self.validation_page,
                    self.upload_page,
                    self.result_page,
                ):
                    self.stack.addWidget(page)

                self.page_meta = {
                    self.settings_page: ("설정", "연결 정보와 기본 실행 옵션을 입력합니다.", 0),
                    self.project_page: ("프로젝트 선택", "업로드 대상 프로젝트와 트래커를 선택합니다.", 1),
                    self.file_page: ("파일 선택", "Excel 파일과 시트, 헤더 정보를 확인합니다.", 2),
                    self.root_item_page: ("상단 데이터", "파일명 기반 부모 데이터의 필드와 정규식 파싱 규칙을 설정합니다.", 3),
                    self.mapping_page: ("컬럼 매핑", "업로드할 컬럼만 선택하고 Codebeamer 필드와 연결합니다.", 4),
                    self.validation_page: ("검증", "문제가 있는 항목만 먼저 확인하고 수정 여부를 판단합니다.", 5),
                    self.upload_page: ("업로드", "진행 상황을 확인하면서 업로드를 제어합니다.", 6),
                    self.result_page: ("결과", "성공, 실패, 미해결 항목을 정리해서 확인합니다.", 7),
                }
                for page in (
                    self.settings_page,
                    self.project_page,
                    self.file_page,
                    self.root_item_page,
                    self.mapping_page,
                    self.validation_page,
                    self.upload_page,
                    self.result_page,
                ):
                    page.request_content_reflow = self._fit_window_to_current_page
                self._show_page(self.settings_page)
                if self.session_state.workflow_preset is not None:
                    self._apply_workflow_preset(self.session_state.workflow_preset, startup=True)
                else:
                    self.statusBar().showMessage("GUI 스켈레톤이 준비되었습니다.")

            def _show_page(self, page) -> None:
                self.stack.setCurrentWidget(page)
                title, subtitle, active_index = self.page_meta.get(page, ("", "", -1))
                self.page_title_label.setText(title)
                self.page_subtitle_label.setText(subtitle)
                for index, label in enumerate(self.step_labels):
                    label.setProperty("active", index == active_index)
                    label.setProperty("complete", active_index >= 0 and index < active_index)
                    label.style().unpolish(label)
                    label.style().polish(label)
                self._fit_window_to_current_page(allow_grow=True)

            def _attach_navigation(
                self,
                page,
                previous_page=None,
                next_page=None,
                next_handler=None,
                restart_handler=None,
            ) -> None:
                def _go_previous():
                    if previous_page is not None:
                        self._show_page(previous_page)

                def _go_next():
                    try:
                        if next_handler is not None:
                            next_handler()
                            return
                        if next_page is not None:
                            self._show_page(next_page)
                    except Exception as exc:
                        self.statusBar().showMessage(str(exc))
                        self._show_error_dialog("작업 실패", str(exc))

                def _restart():
                    try:
                        if restart_handler is not None:
                            restart_handler()
                    except Exception as exc:
                        self.statusBar().showMessage(str(exc))
                        self._show_error_dialog("작업 실패", str(exc))

                page.request_previous = _go_previous
                page.request_next = _go_next
                page.request_restart = _restart

            def _show_error_dialog(self, title: str, message: str) -> None:
                QMessageBox = self.qt["QMessageBox"]
                text = str(message or "").strip() or "알 수 없는 오류가 발생했습니다."
                QMessageBox.critical(self, str(title or "오류"), text)

            def _show_info_dialog(self, title: str, message: str) -> None:
                QMessageBox = self.qt["QMessageBox"]
                text = str(message or "").strip() or "작업이 완료되었습니다."
                QMessageBox.information(self, str(title or "안내"), text)

            def _on_settings_changed(self, settings: GuiSettings | None) -> GuiSettings:
                if settings is None:
                    return self.session_state.settings
                self.session_state.settings = settings
                self.statusBar().showMessage("설정 상태를 갱신했습니다.")
                return settings

            def _on_file_state_changed(self, file_state: dict[str, object]) -> None:
                self.session_state.file_state = file_state
                self.statusBar().showMessage("파일 선택 상태를 갱신했습니다.")

            def _test_connection(self, settings: GuiSettings) -> list[dict[str, object]]:
                projects = self._run_with_busy(
                    "프로젝트 목록을 불러오는 중입니다.",
                    self.codebeamer_service.test_connection_and_load_projects,
                    settings,
                )
                self.session_state.settings = settings
                self.session_state.projects = projects
                self.statusBar().showMessage("연결 테스트와 프로젝트 조회가 완료되었습니다.")
                return projects

            def _load_trackers(self, settings: GuiSettings, project_id: int) -> list[dict[str, object]]:
                trackers = self._run_with_busy(
                    "트래커 목록을 불러오는 중입니다.",
                    self.codebeamer_service.load_trackers,
                    settings,
                    project_id,
                )
                self.session_state.settings = settings
                self.session_state.trackers = trackers
                self.statusBar().showMessage("트래커 목록을 불러왔습니다.")
                return trackers

            def _load_file_preview(
                self,
                file_path: str,
                *,
                file_paths: list[str] | None = None,
                sheet_name: str,
                header_row: int,
                summary_column: str,
            ):
                preview = self._run_with_busy(
                    "Excel 시트와 미리보기를 불러오는 중입니다.",
                    self.excel_service.load_preview,
                    file_path,
                    file_paths=file_paths,
                    sheet_name=sheet_name,
                    header_row=header_row,
                    summary_column=summary_column,
                )
                self.statusBar().showMessage("Excel 미리보기를 불러왔습니다.")
                return preview

            def _current_settings_snapshot(self) -> GuiSettings:
                settings = replace(self.session_state.settings)
                get_settings = getattr(self.settings_page, "get_settings", None)
                if callable(get_settings):
                    settings = replace(get_settings())

                get_selection = getattr(self.project_page, "get_selection", None)
                if callable(get_selection):
                    selection = dict(get_selection() or {})
                    settings.default_project_id = str(selection.get("project_id") or settings.default_project_id or "")
                    settings.default_tracker_id = str(selection.get("tracker_id") or settings.default_tracker_id or "")

                file_state = self._current_file_state_snapshot()
                file_paths = [
                    str(path).strip()
                    for path in file_state.get("file_paths") or []
                    if str(path).strip()
                ]
                if file_paths:
                    settings.last_file_path = file_paths[0]
                return settings

            def _current_file_state_snapshot(self) -> dict[str, object]:
                current_state = dict(self.session_state.file_state or {})
                get_state = getattr(self.file_page, "get_state", None)
                if callable(get_state):
                    current_state.update(dict(get_state() or {}))
                return current_state

            def _apply_workflow_preset_to_mapping_context(self, mapping_context, preset: GuiWorkflowPreset) -> None:
                if preset.root_item_config:
                    mapping_context.root_item_config = dict(preset.root_item_config)
                if preset.selected_mapping:
                    mapping_context.selected_mapping = {
                        str(df_column): str(schema_field)
                        for df_column, schema_field in preset.selected_mapping.items()
                        if str(df_column).strip() and str(schema_field).strip()
                    }
                if preset.selected_default_values:
                    mapping_context.selected_default_values = {
                        str(field_name): str(value)
                        for field_name, value in preset.selected_default_values.items()
                        if str(field_name).strip() and str(value).strip()
                    }
                if preset.selected_tracker_item_settings:
                    mapping_context.selected_tracker_item_settings = {
                        str(field_name): dict(setting)
                        for field_name, setting in preset.selected_tracker_item_settings.items()
                        if str(field_name).strip() and isinstance(setting, dict)
                    }

            def _collect_workflow_preset(self) -> GuiWorkflowPreset:
                settings = self._current_settings_snapshot()
                file_state = self._current_file_state_snapshot()
                file_options = {
                    "sheet_name": str(file_state.get("sheet_name") or settings.excel_sheet_name or "0"),
                    "header_row": int(file_state.get("header_row") or settings.excel_header_row or 1),
                    "summary_column": str(file_state.get("summary_column") or settings.summary_column or "Summary"),
                }

                root_item_config: dict[str, object] = {}
                mapping_context = self.session_state.mapping_context
                if mapping_context is not None:
                    root_item_config = dict(getattr(mapping_context, "root_item_config", {}) or {})
                if self.stack.currentWidget() is self.root_item_page and mapping_context is not None:
                    root_item_config = dict(self.root_item_page.get_config() or root_item_config)

                selected_mapping: dict[str, str] = {}
                selected_default_values: dict[str, str] = {}
                selected_tracker_item_settings: dict[str, dict[str, object]] = {}
                if callable(getattr(self.mapping_page, "get_selected_mapping", None)):
                    selected_mapping = dict(self.mapping_page.get_selected_mapping() or {})
                if callable(getattr(self.mapping_page, "get_selected_default_values", None)):
                    selected_default_values = dict(self.mapping_page.get_selected_default_values() or {})
                if callable(getattr(self.mapping_page, "get_selected_tracker_item_settings", None)):
                    selected_tracker_item_settings = dict(self.mapping_page.get_selected_tracker_item_settings() or {})

                if not selected_mapping and mapping_context is not None:
                    selected_mapping = dict(getattr(mapping_context, "selected_mapping", {}) or {})
                if not selected_default_values and mapping_context is not None:
                    selected_default_values = dict(getattr(mapping_context, "selected_default_values", {}) or {})
                if not selected_tracker_item_settings and mapping_context is not None:
                    selected_tracker_item_settings = dict(getattr(mapping_context, "selected_tracker_item_settings", {}) or {})

                return GuiWorkflowPreset(
                    settings=settings,
                    file_options=file_options,
                    root_item_config=root_item_config,
                    selected_mapping=selected_mapping,
                    selected_default_values=selected_default_values,
                    selected_tracker_item_settings=selected_tracker_item_settings,
                )

            def _apply_workflow_preset(self, preset: GuiWorkflowPreset, *, startup: bool = False) -> None:
                self.session_state.workflow_preset = preset
                self.session_state.settings = replace(preset.settings)

                set_settings = getattr(self.settings_page, "set_settings", None)
                if callable(set_settings):
                    set_settings(replace(preset.settings))

                load_selection = getattr(self.project_page, "load_selection", None)
                if callable(load_selection):
                    load_selection(preset.settings.default_project_id, preset.settings.default_tracker_id)

                load_file_state = getattr(self.file_page, "load_state", None)
                if callable(load_file_state):
                    load_file_state(dict(preset.file_options or {}))
                else:
                    self.session_state.file_state.update(dict(preset.file_options or {}))

                if self.session_state.mapping_context is not None:
                    self._apply_workflow_preset_to_mapping_context(self.session_state.mapping_context, preset)
                    preview_context = self.pipeline_service.build_root_item_preview_context(
                        self.session_state.mapping_context,
                        self.session_state.mapping_context.root_item_config,
                    )
                    self.root_item_page.load_context(preview_context)
                    self.mapping_page.load_context(
                        self.session_state.mapping_context.upload_columns,
                        self.session_state.mapping_context.schema_df,
                        self.session_state.mapping_context.selected_mapping,
                        self.session_state.mapping_context.default_value_candidates,
                        self.session_state.mapping_context.selected_default_values,
                        self.session_state.mapping_context.selected_tracker_item_settings,
                    )
                    self.session_state.validation_context = None
                    self.session_state.upload_result = None
                    if self.stack.currentWidget() in {self.validation_page, self.upload_page, self.result_page}:
                        self._show_page(self.mapping_page)

                message = (
                    "저장된 전체 설정을 자동으로 불러왔습니다."
                    if startup
                    else "전체 설정을 불러왔습니다. 파일을 선택한 뒤 검증을 다시 실행하세요."
                )
                self.statusBar().showMessage(message)

            def _save_workflow_preset(self) -> None:
                try:
                    preset = self._collect_workflow_preset()
                    self.settings_store.save_workflow_preset(preset)
                    self.session_state.workflow_preset = preset
                    self.settings_store.save(preset.settings)
                except Exception as exc:
                    self.statusBar().showMessage(str(exc))
                    self._show_error_dialog("전체 설정 저장 실패", str(exc))
                    return
                self.statusBar().showMessage("전체 설정을 저장했습니다.")
                self._show_info_dialog("전체 설정 저장", "전체 설정을 저장했습니다.")

            def _load_workflow_preset(self) -> None:
                try:
                    preset = self.settings_store.load_workflow_preset()
                    if preset is None:
                        self._show_error_dialog("전체 설정 없음", "저장된 전체 설정이 없습니다.")
                        return
                    self._apply_workflow_preset(preset)
                except Exception as exc:
                    self.statusBar().showMessage(str(exc))
                    self._show_error_dialog("전체 설정 불러오기 실패", str(exc))
                    return
                self._show_info_dialog(
                    "전체 설정 불러오기",
                    "전체 설정을 불러왔습니다. 파일과 매핑을 확인한 뒤 다시 검증하세요.",
                )

            def _show_mapping_page(self) -> None:
                self._show_page(self.mapping_page)

            def _preview_root_item_config(self, root_item_config: dict[str, object]):
                if self.session_state.mapping_context is None:
                    raise ValueError("루트 데이터 컨텍스트가 준비되지 않았습니다.")
                return self.pipeline_service.build_root_item_preview_context(
                    self.session_state.mapping_context,
                    root_item_config,
                )

            def _enter_validation_page(self) -> None:
                self._show_page(self.validation_page)

            def _enter_upload_page(self) -> None:
                self.upload_page.reset(0)
                self._show_page(self.upload_page)

            def _enter_result_page(self) -> None:
                if self.session_state.upload_result is not None:
                    self.result_page.set_results(self.session_state.upload_result)
                self._show_page(self.result_page)

            def _restart_upload_flow(self) -> None:
                self.session_state.validation_context = None
                self.session_state.upload_result = None
                self.upload_success_count = 0
                self.upload_failed_count = 0
                self._show_page(self.project_page)

            def _on_prepare_root_item_context(self) -> None:
                settings = self.session_state.settings
                if not settings.default_project_id or not settings.default_tracker_id:
                    raise ValueError("프로젝트와 트래커를 먼저 선택해야 합니다.")
                mapping_context = self._run_with_busy(
                    "매핑 대상 컬럼과 스키마를 준비하는 중입니다.",
                    self.pipeline_service.prepare_mapping_context,
                    settings,
                    self.session_state.file_state,
                )
                if self.session_state.workflow_preset is not None:
                    self._apply_workflow_preset_to_mapping_context(
                        mapping_context,
                        self.session_state.workflow_preset,
                    )
                self.session_state.mapping_context = mapping_context
                root_preview_context = self.pipeline_service.build_root_item_preview_context(
                    mapping_context,
                    mapping_context.root_item_config,
                )
                self.root_item_page.load_context(root_preview_context)
                self._show_page(self.root_item_page)

            def _on_confirm_root_item_config(self) -> None:
                if self.session_state.mapping_context is None:
                    raise ValueError("매핑 컨텍스트가 준비되지 않았습니다.")
                self.session_state.mapping_context.root_item_config = self.root_item_page.get_config()
                self.mapping_page.load_context(
                    self.session_state.mapping_context.upload_columns,
                    self.session_state.mapping_context.schema_df,
                    self.session_state.mapping_context.selected_mapping,
                    self.session_state.mapping_context.default_value_candidates,
                    self.session_state.mapping_context.selected_default_values,
                    self.session_state.mapping_context.selected_tracker_item_settings,
                )
                self._show_page(self.mapping_page)

            def _validate_mapping(
                self,
                selected_mapping: dict[str, str],
                selected_default_values: dict[str, str],
                selected_tracker_item_settings: dict[str, dict[str, object]],
            ) -> None:
                if self.session_state.mapping_context is None:
                    raise ValueError("매핑 컨텍스트가 준비되지 않았습니다.")
                validation_context = self._run_with_busy(
                    "매핑을 검증하고 payload를 준비하는 중입니다.",
                    self.pipeline_service.validate_mapping,
                    self.session_state.mapping_context,
                    selected_mapping,
                    selected_default_values,
                    selected_tracker_item_settings,
                )
                self.session_state.validation_context = validation_context
                self.validation_page.set_results(
                    validation_context.issue_df,
                    validation_context.has_blocking_issues,
                    validation_context.summary_stats,
                )

            def _start_upload(self) -> None:
                if self.session_state.mapping_context is None:
                    self.upload_page.status_label.setText("업로드 컨텍스트가 없습니다.")
                    return
                output_dir = str(Path(self.session_state.settings.output_dir))
                self.upload_success_count = 0
                self.upload_failed_count = 0
                self.upload_retry_count = 0
                self.upload_total_count = 0
                self._upload_event_started_at = {}
                self._upload_batch_started_at = time.perf_counter()
                self.upload_worker = UploadWorker(
                    self.pipeline_service,
                    settings=self.session_state.settings,
                    file_state=self.session_state.file_state,
                    mapping_context=self.session_state.mapping_context,
                    dry_run=self.upload_page.dry_run_checkbox.isChecked(),
                    continue_on_error=self.upload_page.continue_checkbox.isChecked(),
                    output_dir=output_dir,
                )
                self.upload_worker.progress_changed.connect(self._on_upload_progress)
                self.upload_worker.upload_event.connect(self._on_upload_event)
                self.upload_worker.upload_finished.connect(self._on_upload_finished)
                self.upload_worker.upload_failed.connect(self._on_upload_failed)
                self.upload_page.start_button.setEnabled(False)
                self.upload_page.pause_button.setEnabled(True)
                self.upload_page.cancel_button.setEnabled(True)
                self.upload_page.status_label.setText("업로드 실행 중")
                self.upload_worker.start()

            def _pause_upload(self) -> None:
                if self.upload_worker is not None:
                    self.upload_worker.request_pause()
                    self.upload_page.pause_button.setEnabled(False)
                    self.upload_page.resume_button.setEnabled(True)
                    self.upload_page.status_label.setText("일시정지 요청됨")

            def _resume_upload(self) -> None:
                if self.upload_worker is not None:
                    self.upload_worker.request_resume()
                    self.upload_page.pause_button.setEnabled(True)
                    self.upload_page.resume_button.setEnabled(False)
                    self.upload_page.status_label.setText("업로드 재개")

            def _cancel_upload(self) -> None:
                if self.upload_worker is not None:
                    self.upload_worker.request_cancel()
                    self.upload_page.status_label.setText("중단 요청됨")

            @staticmethod
            def _format_clock(timestamp: float | None = None) -> str:
                if timestamp is None:
                    timestamp = time.time()
                return datetime.fromtimestamp(timestamp).strftime("%H:%M:%S")

            @staticmethod
            def _format_duration(seconds: float | None) -> str:
                if seconds is None:
                    return "-"
                if seconds < 1:
                    return f"{seconds:.2f}초"
                if seconds < 60:
                    return f"{seconds:.1f}초"
                minutes = int(seconds // 60)
                remainder = seconds - (minutes * 60)
                return f"{minutes}분 {remainder:.1f}초"

            @staticmethod
            def _upload_event_key(event: dict[str, object]) -> str:
                source_file_path = str(event.get("source_file_path") or "").strip()
                row_id = event.get("row_id")
                if row_id is None:
                    return f"{source_file_path}::__root__::{str(event.get('upload_name') or '').strip()}"
                return f"{source_file_path}::{row_id}"

            @staticmethod
            def _display_item_name(file_label: str, upload_name: str) -> str:
                prefix = f"[{file_label}] "
                if file_label and upload_name.startswith(prefix):
                    return upload_name[len(prefix):].strip() or upload_name
                return upload_name or "-"

            def _append_timestamped_log(self, message: str) -> None:
                text = str(message or "").strip()
                if not text:
                    return
                self.upload_page.log_view.appendPlainText(f"{self._format_clock()} | {text}")

            def _update_upload_counter(self) -> None:
                self.upload_page.counter_label.setText(
                    f"성공 {self.upload_success_count} / 실패 {self.upload_failed_count} / 재시도 {self.upload_retry_count}"
                )
                completed_count = self.upload_success_count + self.upload_failed_count
                self.upload_page.total_label.setText(
                    f"총 대상 {self.upload_total_count}건 / 완료 {completed_count}건"
                )

            def _update_upload_time_label(self) -> None:
                if self._upload_batch_started_at is None:
                    self.upload_page.time_label.setText("배치 시간: -")
                    return
                elapsed = time.perf_counter() - self._upload_batch_started_at
                self.upload_page.time_label.setText(
                    f"배치 시간: {self._format_duration(elapsed)} 경과 (현재 시각 {self._format_clock()})"
                )

            def _on_upload_event(self, event: dict) -> None:
                event_type = str(event.get("type") or "")
                message = str(event.get("message") or "").strip()
                raw_item_name = str(event.get("upload_name") or "-").strip() or "-"
                file_label = str(event.get("source_file") or "").strip() or "-"
                item_name = self._display_item_name(file_label, raw_item_name)
                row_key = self._upload_event_key(event)

                self._update_upload_time_label()

                if event_type == "log":
                    self._append_timestamped_log(message)
                    return

                if event_type == "batch_total":
                    self.upload_total_count = int(event.get("total") or 0)
                    self._update_upload_counter()
                    self._append_timestamped_log(f"총 업로드 예정 건수: {self.upload_total_count}")
                    return

                if event_type == "row_started":
                    started_at = time.perf_counter()
                    self._upload_event_started_at[row_key] = started_at
                    self.upload_page.record_activity_started(
                        row_key,
                        file_label,
                        item_name,
                        self._format_clock(),
                    )
                    self._append_timestamped_log(f"시작 | {raw_item_name}")
                    return

                if event_type not in {"row_success", "row_failed"}:
                    return

                started_at = self._upload_event_started_at.get(row_key)
                elapsed = None if started_at is None else (time.perf_counter() - started_at)
                if event_type == "row_success":
                    self.upload_success_count += 1
                    status_text = "성공"
                    if not message:
                        message = "업로드 완료"
                else:
                    self.upload_failed_count += 1
                    status_text = "실패"
                    if not message:
                        message = "업로드 실패"
                    response_json = event.get("response_json")
                    if response_json not in (None, ""):
                        self.upload_page.response_view.setPlainText(str(response_json))

                self.upload_page.record_activity_finished(
                    row_key,
                    file_label,
                    item_name,
                    status=status_text,
                    finished_at=self._format_clock(),
                    duration_text=self._format_duration(elapsed),
                    message=message,
                )
                self._update_upload_counter()
                self._update_upload_time_label()
                self._append_timestamped_log(f"{status_text} | {message}")

            def _on_upload_progress(self, current: int, total: int, upload_name: str) -> None:
                self.upload_page.progress_bar.setMaximum(max(total, 1))
                self.upload_page.progress_bar.setValue(current)
                self.upload_page.current_label.setText(f"현재 항목: {upload_name or '-'}")
                self._update_upload_time_label()

            def _on_upload_finished(self, result: dict) -> None:
                self.session_state.upload_result = result
                success_df = result.get("success_df")
                failed_df = result.get("failed_df")
                unresolved_df = result.get("unresolved_df")
                self.upload_success_count = 0 if success_df is None else len(success_df)
                self.upload_failed_count = 0 if failed_df is None else len(failed_df)
                self._update_upload_counter()
                if failed_df is not None and not getattr(failed_df, "empty", True) and "error_response_json" in failed_df.columns:
                    self.upload_page.response_view.setPlainText(str(failed_df.iloc[0].get("error_response_json") or ""))
                self._update_upload_time_label()
                self._append_timestamped_log("배치 업로드가 완료되었습니다.")
                self.upload_page.status_label.setText("업로드 완료")
                self.upload_page.pause_button.setEnabled(False)
                self.upload_page.resume_button.setEnabled(False)
                self.upload_page.cancel_button.setEnabled(False)
                self.upload_page.result_button.setEnabled(True)
                unresolved_count = 0 if unresolved_df is None else len(unresolved_df)
                if self.upload_failed_count or unresolved_count:
                    self._show_error_dialog(
                        "업로드 결과 확인 필요",
                        f"배치 업로드는 종료되었지만 실패 {self.upload_failed_count}건, 미해결 {unresolved_count}건이 남아 있습니다.",
                    )

            def _on_upload_failed(self, message: str) -> None:
                self.upload_page.status_label.setText(message)
                self._update_upload_time_label()
                self._append_timestamped_log(message)
                self.upload_page.pause_button.setEnabled(False)
                self.upload_page.resume_button.setEnabled(False)
                self.upload_page.cancel_button.setEnabled(False)
                self.upload_page.result_button.setEnabled(True)
                if "사용자 요청으로 중단" not in str(message):
                    self._show_error_dialog("업로드 오류", message)

        return _MainWindow(settings_store)
