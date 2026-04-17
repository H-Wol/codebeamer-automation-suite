from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .pages import create_file_selection_page
from .pages import create_mapping_page
from .pages import create_project_selection_page
from .pages import create_settings_page
from .pages import create_validation_page
from .pages import create_upload_page
from .pages import create_result_page
from .services import GuiCodebeamerService
from .services import GuiExcelService
from .services import GuiUploadPipelineService
from .settings_store import GuiSettings
from .settings_store import GuiSettingsStore
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
                header_layout.addWidget(title)
                header_layout.addWidget(subtitle)

                steps_row = QHBoxLayout()
                steps_row.setSpacing(8)
                self.step_labels = []
                for step_name in ("설정", "프로젝트", "파일", "매핑", "검증", "업로드", "결과"):
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
                )
                self.file_page = create_file_selection_page(
                    self.session_state.settings,
                    self._on_file_state_changed,
                    self._load_file_preview,
                )
                self.mapping_page = create_mapping_page(self._validate_mapping)
                self.validation_page = create_validation_page()
                self.upload_page = create_upload_page(
                    self._start_upload,
                    self._pause_upload,
                    self._resume_upload,
                    self._cancel_upload,
                )
                self.result_page = create_result_page()

                self._attach_navigation(self.settings_page, next_page=self.project_page)
                self._attach_navigation(
                    self.project_page,
                    previous_page=self.settings_page,
                    next_page=self.file_page,
                )
                self._attach_navigation(
                    self.file_page,
                    previous_page=self.project_page,
                    next_handler=self._on_prepare_mapping_context,
                )
                self._attach_navigation(
                    self.mapping_page,
                    previous_page=self.file_page,
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
                    self.mapping_page: ("컬럼 매핑", "업로드할 컬럼만 선택하고 Codebeamer 필드와 연결합니다.", 3),
                    self.validation_page: ("검증", "문제가 있는 항목만 먼저 확인하고 수정 여부를 판단합니다.", 4),
                    self.upload_page: ("업로드", "진행 상황을 확인하면서 업로드를 제어합니다.", 5),
                    self.result_page: ("결과", "성공, 실패, 미해결 항목을 정리해서 확인합니다.", 6),
                }
                for page in (
                    self.settings_page,
                    self.project_page,
                    self.file_page,
                    self.mapping_page,
                    self.validation_page,
                    self.upload_page,
                    self.result_page,
                ):
                    page.request_content_reflow = self._fit_window_to_current_page
                self._show_page(self.settings_page)
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
                    if next_handler is not None:
                        next_handler()
                        return
                    if next_page is not None:
                        self._show_page(next_page)

                def _restart():
                    if restart_handler is not None:
                        restart_handler()

                page.request_previous = _go_previous
                page.request_next = _go_next
                page.request_restart = _restart

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

            def _load_file_preview(self, file_path: str, *, sheet_name: str, header_row: int):
                preview = self._run_with_busy(
                    "Excel 시트와 미리보기를 불러오는 중입니다.",
                    self.excel_service.load_preview,
                    file_path,
                    sheet_name=sheet_name,
                    header_row=header_row,
                )
                self.statusBar().showMessage("Excel 미리보기를 불러왔습니다.")
                return preview

            def _show_mapping_page(self) -> None:
                self._show_page(self.mapping_page)

            def _enter_validation_page(self) -> None:
                self._show_page(self.validation_page)

            def _enter_upload_page(self) -> None:
                self.upload_page.reset(
                    len(self.session_state.mapping_context.wizard.state.upload_df)
                    if self.session_state.mapping_context is not None
                    else 0
                )
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

            def _on_prepare_mapping_context(self) -> None:
                settings = self.session_state.settings
                if not settings.default_project_id or not settings.default_tracker_id:
                    raise ValueError("프로젝트와 트래커를 먼저 선택해야 합니다.")
                mapping_context = self._run_with_busy(
                    "매핑 대상 컬럼과 스키마를 준비하는 중입니다.",
                    self.pipeline_service.prepare_mapping_context,
                    settings,
                    self.session_state.file_state,
                )
                self.session_state.mapping_context = mapping_context
                self.mapping_page.load_context(
                    mapping_context.upload_columns,
                    mapping_context.schema_df,
                    mapping_context.selected_mapping,
                )
                self._show_page(self.mapping_page)

            def _validate_mapping(self, selected_mapping: dict[str, str]) -> None:
                if self.session_state.mapping_context is None:
                    raise ValueError("매핑 컨텍스트가 준비되지 않았습니다.")
                validation_context = self._run_with_busy(
                    "매핑을 검증하고 payload를 준비하는 중입니다.",
                    self.pipeline_service.validate_mapping,
                    self.session_state.mapping_context,
                    selected_mapping,
                )
                self.session_state.validation_context = validation_context
                self.validation_page.set_results(
                    validation_context.issue_df,
                    validation_context.has_blocking_issues,
                )

            def _start_upload(self) -> None:
                if self.session_state.mapping_context is None:
                    self.upload_page.status_label.setText("업로드 컨텍스트가 없습니다.")
                    return
                wizard = self.session_state.mapping_context.wizard
                output_dir = str(Path(self.session_state.settings.output_dir))
                self.upload_success_count = 0
                self.upload_failed_count = 0
                self.upload_worker = UploadWorker(
                    wizard,
                    dry_run=self.upload_page.dry_run_checkbox.isChecked(),
                    continue_on_error=self.upload_page.continue_checkbox.isChecked(),
                    output_dir=output_dir,
                )
                self.upload_worker.log_message.connect(self._on_upload_log_message)
                self.upload_worker.progress_changed.connect(self._on_upload_progress)
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

            def _on_upload_log_message(self, message: str) -> None:
                self.upload_page.log_view.appendPlainText(message)

            def _on_upload_progress(self, current: int, total: int, upload_name: str) -> None:
                self.upload_page.progress_bar.setMaximum(max(total, 1))
                self.upload_page.progress_bar.setValue(current)
                self.upload_page.current_label.setText(f"현재 항목: {upload_name or '-'}")

            def _on_upload_finished(self, result: dict) -> None:
                self.session_state.upload_result = result
                success_df = result.get("success_df")
                failed_df = result.get("failed_df")
                self.upload_success_count = 0 if success_df is None else len(success_df)
                self.upload_failed_count = 0 if failed_df is None else len(failed_df)
                self.upload_page.counter_label.setText(
                    f"성공 {self.upload_success_count} / 실패 {self.upload_failed_count} / 재시도 0"
                )
                if failed_df is not None and not getattr(failed_df, "empty", True) and "error_response_json" in failed_df.columns:
                    self.upload_page.response_view.setPlainText(str(failed_df.iloc[0].get("error_response_json") or ""))
                self.upload_page.status_label.setText("업로드 완료")
                self.upload_page.pause_button.setEnabled(False)
                self.upload_page.resume_button.setEnabled(False)
                self.upload_page.cancel_button.setEnabled(False)
                self.upload_page.result_button.setEnabled(True)

            def _on_upload_failed(self, message: str) -> None:
                self.upload_page.status_label.setText(message)
                self.upload_page.log_view.appendPlainText(message)
                self.upload_page.pause_button.setEnabled(False)
                self.upload_page.resume_button.setEnabled(False)
                self.upload_page.cancel_button.setEnabled(False)
                self.upload_page.result_button.setEnabled(True)

        return _MainWindow(settings_store)
