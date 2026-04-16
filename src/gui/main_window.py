from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .pages import create_file_selection_page
from .pages import create_mapping_page
from .pages import create_settings_page
from .pages import create_validation_page
from .pages import create_upload_page
from .pages import create_result_page
from .services import GuiCodebeamerService
from .services import GuiExcelService
from .services import GuiUploadPipelineService
from .settings_store import GuiSettings
from .settings_store import GuiSettingsStore
from .worker import UploadWorker


def _require_qt():
    try:
        from PySide6.QtCore import QSize
        from PySide6.QtWidgets import QMainWindow
        from PySide6.QtWidgets import QMessageBox
        from PySide6.QtWidgets import QStackedWidget
        from PySide6.QtWidgets import QStatusBar
    except ImportError as exc:
        raise RuntimeError("GUI 실행에는 PySide6 패키지가 필요합니다.") from exc

    return {
        "QMainWindow": QMainWindow,
        "QMessageBox": QMessageBox,
        "QSize": QSize,
        "QStackedWidget": QStackedWidget,
        "QStatusBar": QStatusBar,
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
                self.upload_success_count = 0
                self.upload_failed_count = 0
                self.setWindowTitle("Codebeamer Upload GUI")
                self.resize(qt["QSize"](1100, 760))
                self.stack = qt["QStackedWidget"]()
                self.setCentralWidget(self.stack)
                self.setStatusBar(qt["QStatusBar"]())
                self._build_pages()

            def _build_pages(self) -> None:
                self.settings_page = create_settings_page(
                    self.settings_store,
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

                self._attach_navigation(self.settings_page, next_page=self.file_page)
                self._attach_navigation(
                    self.file_page,
                    previous_page=self.settings_page,
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
                    self.file_page,
                    self.mapping_page,
                    self.validation_page,
                    self.upload_page,
                    self.result_page,
                ):
                    self.stack.addWidget(page)

                self.stack.setCurrentWidget(self.settings_page)
                self.statusBar().showMessage("GUI 스켈레톤이 준비되었습니다.")

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
                        self.stack.setCurrentWidget(previous_page)

                def _go_next():
                    if next_handler is not None:
                        next_handler()
                        return
                    if next_page is not None:
                        self.stack.setCurrentWidget(next_page)

                def _restart():
                    if restart_handler is not None:
                        restart_handler()

                page.request_previous = _go_previous
                page.request_next = _go_next
                page.request_restart = _restart

            def _on_settings_changed(self, settings: GuiSettings) -> None:
                self.session_state.settings = settings
                self.statusBar().showMessage("설정 상태를 갱신했습니다.")

            def _on_file_state_changed(self, file_state: dict[str, object]) -> None:
                self.session_state.file_state = file_state
                self.statusBar().showMessage("파일 선택 상태를 갱신했습니다.")

            def _test_connection(self, settings: GuiSettings) -> list[dict[str, object]]:
                projects = self.codebeamer_service.test_connection_and_load_projects(settings)
                self.session_state.settings = settings
                self.session_state.projects = projects
                self.statusBar().showMessage("연결 테스트와 프로젝트 조회가 완료되었습니다.")
                return projects

            def _load_trackers(self, settings: GuiSettings, project_id: int) -> list[dict[str, object]]:
                trackers = self.codebeamer_service.load_trackers(settings, project_id)
                self.session_state.settings = settings
                self.session_state.trackers = trackers
                self.statusBar().showMessage("트래커 목록을 불러왔습니다.")
                return trackers

            def _load_file_preview(self, file_path: str, *, sheet_name: str, header_row: int):
                preview = self.excel_service.load_preview(
                    file_path,
                    sheet_name=sheet_name,
                    header_row=header_row,
                )
                self.statusBar().showMessage("Excel 미리보기를 불러왔습니다.")
                return preview

            def _show_mapping_page(self) -> None:
                self.stack.setCurrentWidget(self.mapping_page)

            def _enter_validation_page(self) -> None:
                self.stack.setCurrentWidget(self.validation_page)

            def _enter_upload_page(self) -> None:
                self.upload_page.reset(
                    len(self.session_state.mapping_context.wizard.state.upload_df)
                    if self.session_state.mapping_context is not None
                    else 0
                )
                self.stack.setCurrentWidget(self.upload_page)

            def _enter_result_page(self) -> None:
                if self.session_state.upload_result is not None:
                    self.result_page.set_results(self.session_state.upload_result)
                self.stack.setCurrentWidget(self.result_page)

            def _restart_upload_flow(self) -> None:
                self.session_state.validation_context = None
                self.session_state.upload_result = None
                self.upload_success_count = 0
                self.upload_failed_count = 0
                self.stack.setCurrentWidget(self.file_page)

            def _on_prepare_mapping_context(self) -> None:
                settings = self.session_state.settings
                if not settings.default_project_id or not settings.default_tracker_id:
                    raise ValueError("프로젝트와 트래커를 먼저 선택해야 합니다.")
                mapping_context = self.pipeline_service.prepare_mapping_context(
                    settings,
                    self.session_state.file_state,
                )
                self.session_state.mapping_context = mapping_context
                self.mapping_page.load_context(
                    mapping_context.upload_columns,
                    mapping_context.schema_df,
                    mapping_context.selected_mapping,
                )
                self.stack.setCurrentWidget(self.mapping_page)

            def _validate_mapping(self, selected_mapping: dict[str, str]) -> None:
                if self.session_state.mapping_context is None:
                    raise ValueError("매핑 컨텍스트가 준비되지 않았습니다.")
                validation_context = self.pipeline_service.validate_mapping(
                    self.session_state.mapping_context,
                    selected_mapping,
                )
                self.session_state.validation_context = validation_context
                payload_df = self.session_state.mapping_context.wizard.state.payload_df
                self.validation_page.set_results(
                    validation_context.comparison_df,
                    validation_context.option_check_df,
                    payload_df,
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
