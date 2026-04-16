from __future__ import annotations

from dataclasses import dataclass

from .pages import create_file_selection_page
from .pages import create_placeholder_page
from .pages import create_settings_page
from .settings_store import GuiSettings
from .settings_store import GuiSettingsStore


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
                )
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
                )
                self.file_page = create_file_selection_page(
                    self.session_state.settings,
                    self._on_file_state_changed,
                )
                self.mapping_page = create_placeholder_page(
                    "컬럼 매핑",
                    "체크박스/콤보박스 기반 컬럼 매핑 UI 는 다음 단계에서 실제 schema 와 연결합니다.\n"
                    "- id, parent 는 매핑 대상에서 제외\n"
                    "- multipleValues, lookup, preconstruction 정보는 읽기 전용으로 표시",
                )
                self.validation_page = create_placeholder_page(
                    "검증",
                    "검증 결과 요약 카드와 상세 테이블은 다음 단계에서 comparison_df 와 option_check_df 를 연결합니다.",
                )
                self.upload_page = create_placeholder_page(
                    "업로드",
                    "Progress bar, pause/resume/cancel, 실시간 로그, 실패 응답 JSON 표시는 다음 단계에서 worker 와 연결합니다.",
                )
                self.result_page = create_placeholder_page(
                    "결과",
                    "성공/실패/unresolved/created_map 결과 탭은 다음 단계에서 upload_result 와 연결합니다.",
                )

                self._attach_navigation(self.settings_page, next_page=self.file_page)
                self._attach_navigation(self.file_page, previous_page=self.settings_page, next_page=self.mapping_page)
                self._attach_navigation(self.mapping_page, previous_page=self.file_page, next_page=self.validation_page)
                self._attach_navigation(self.validation_page, previous_page=self.mapping_page, next_page=self.upload_page)
                self._attach_navigation(self.upload_page, previous_page=self.validation_page, next_page=self.result_page)
                self._attach_navigation(self.result_page, previous_page=self.upload_page)

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

            def _attach_navigation(self, page, previous_page=None, next_page=None) -> None:
                def _go_previous():
                    if previous_page is not None:
                        self.stack.setCurrentWidget(previous_page)

                def _go_next():
                    if next_page is not None:
                        self.stack.setCurrentWidget(next_page)

                page.request_previous = _go_previous
                page.request_next = _go_next

            def _on_settings_changed(self, settings: GuiSettings) -> None:
                self.session_state.settings = settings
                self.statusBar().showMessage("설정 상태를 갱신했습니다.")

            def _on_file_state_changed(self, file_state: dict[str, object]) -> None:
                self.session_state.file_state = file_state
                self.statusBar().showMessage("파일 선택 상태를 갱신했습니다.")

        return _MainWindow(settings_store)

