from __future__ import annotations

from dataclasses import replace

from .batch_window import BatchUploadWindow
from .settings_store import GuiSettings
from .settings_store import GuiSettingsStore
from .window_support import _estimate_upload_remaining_seconds
from .window_support import _format_clock_text
from .window_support import _format_duration_text
from .window_support import _format_upload_eta_text
from .window_support import _format_upload_progress_text
from .window_support import _merge_root_item_page_configs
from .window_support import _merge_window_preferences
from .window_support import _require_qt
from .window_support import _window_size_from_settings


ROUTE_TRACKER_WORKSPACE = "tracker_workspace"
ROUTE_BATCH_UPLOAD = "batch_upload"
ROUTE_ACTIVITY = "activity"
ROUTE_SETTINGS = "settings"

APP_ROUTE_LABELS = {
    ROUTE_TRACKER_WORKSPACE: "트래커 작업공간",
    ROUTE_BATCH_UPLOAD: "배치 작업",
    ROUTE_ACTIVITY: "실행 기록",
    ROUTE_SETTINGS: "설정",
}


_QT = _require_qt()
QMainWindow = _QT["QMainWindow"]


class MainWindow(QMainWindow):
    """조회·배치·기록·설정을 전환하는 최상위 애플리케이션 셸."""

    def __init__(self, settings_store: GuiSettingsStore) -> None:
        super().__init__()
        self.qt = _QT
        self.settings_store = settings_store
        initial_settings = settings_store.load()
        self._last_normal_window_width = max(int(initial_settings.window_width), 860)
        self._last_normal_window_height = max(int(initial_settings.window_height), 620)
        self.current_route = ""
        self.route_widgets: dict[str, object] = {}
        self.nav_buttons: dict[str, object] = {}

        self._build_application_shell(initial_settings)
        self.setWindowTitle("Codebeamer Automation Suite")
        self.setMinimumSize(860, 620)
        self.resize(*_window_size_from_settings(initial_settings))
        self._show_route(ROUTE_TRACKER_WORKSPACE)

        if bool(getattr(initial_settings, "window_is_fullscreen", False)):
            self.showFullScreen()
        elif bool(getattr(initial_settings, "window_is_maximized", False)):
            self.showMaximized()

    def _build_application_shell(self, initial_settings: GuiSettings) -> None:
        QWidget = self.qt["QWidget"]
        QFrame = self.qt["QFrame"]
        QHBoxLayout = self.qt["QHBoxLayout"]
        QLabel = self.qt["QLabel"]
        QPushButton = self.qt["QPushButton"]
        QStackedWidget = self.qt["QStackedWidget"]
        QVBoxLayout = self.qt["QVBoxLayout"]

        root = QWidget(self)
        root.setObjectName("application_shell_root")
        root_layout = QVBoxLayout(root)
        root_layout.setContentsMargins(10, 8, 10, 8)
        root_layout.setSpacing(8)

        header = QFrame(root)
        header.setObjectName("application_header")
        header.setMinimumHeight(56)
        self.application_header = header
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(14, 10, 14, 10)
        header_layout.setSpacing(10)

        title_group = QVBoxLayout()
        title_group.setSpacing(2)
        title = QLabel("Codebeamer Automation Suite")
        title.setObjectName("application_title")
        subtitle = QLabel("트래커 조회와 배치 작업을 한 곳에서 관리합니다.")
        subtitle.setObjectName("application_subtitle")
        title_group.addWidget(title)
        title_group.addWidget(subtitle)
        header_layout.addLayout(title_group)
        header_layout.addStretch(1)

        self.mode_badge = QLabel("")
        self.mode_badge.setObjectName("application_mode_badge")
        header_layout.addWidget(self.mode_badge)
        self._update_mode_badge(initial_settings)

        body_layout = QHBoxLayout()
        body_layout.setSpacing(8)

        navigation = QFrame(root)
        navigation.setObjectName("application_navigation")
        navigation.setMinimumWidth(170)
        navigation.setMaximumWidth(220)
        navigation_layout = QVBoxLayout(navigation)
        navigation_layout.setContentsMargins(10, 12, 10, 12)
        navigation_layout.setSpacing(6)

        navigation_title = QLabel("작업 영역")
        navigation_title.setObjectName("application_navigation_title")
        navigation_layout.addWidget(navigation_title)

        for route, label in APP_ROUTE_LABELS.items():
            button = QPushButton(label, navigation)
            button.setObjectName("application_nav_button")
            button.setCheckable(True)
            button.clicked.connect(
                lambda checked=False, selected_route=route: self._show_route(selected_route)
            )
            navigation_layout.addWidget(button)
            self.nav_buttons[route] = button
        navigation_layout.addStretch(1)

        content = QFrame(root)
        content.setObjectName("application_content")
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)

        self.route_stack = QStackedWidget(content)
        self.route_stack.setObjectName("application_route_stack")
        content_layout.addWidget(self.route_stack)

        self.tracker_workspace_page = self._create_placeholder_page(
            title="트래커 작업공간",
            phase="Foundation 1",
            description=(
                "프로젝트와 트래커를 선택한 뒤 계층 탐색, 조건 검색, 상세 조회로 이어지는 "
                "작업공간입니다."
            ),
            scope_text=(
                "현재 버전에서는 최상위 앱 셸과 작업 경로를 먼저 구성합니다. "
                "실제 아이템 조회는 조회 서비스와 아이템 탐색 화면 구현 단계에서 순차적으로 활성화합니다."
            ),
        )

        self.batch_page = QWidget(content)
        self.batch_page.setObjectName("batch_route_page")
        batch_layout = QVBoxLayout(self.batch_page)
        batch_layout.setContentsMargins(0, 0, 0, 0)
        batch_layout.setSpacing(0)
        self.batch_window = BatchUploadWindow(
            self.settings_store,
            parent=self.batch_page,
            embedded=True,
            settings_changed_callback=self._on_batch_settings_changed,
        )
        batch_layout.addWidget(self.batch_window)

        self.activity_page = self._create_placeholder_page(
            title="실행 기록",
            phase="Foundation 1",
            description="쓰기 작업과 조회 결과 내보내기의 실행 결과를 확인하는 영역입니다.",
            scope_text=(
                "현재 배치 작업의 세부 진행 로그와 결과는 기존 마법사에서 계속 확인할 수 있습니다. "
                "통합 실행 기록은 쓰기 작업과 내보내기 흐름이 연결되는 단계에서 추가합니다."
            ),
        )
        self.settings_center_page = self._create_placeholder_page(
            title="설정",
            phase="Foundation 2",
            description="연결 profile, 화면, 네트워크·저장소, 테스트 모드를 관리하는 전용 설정 영역입니다.",
            scope_text=(
                "전용 설정 센터와 기존 설정 변환은 다음 구현 단계에서 추가합니다. "
                "그 전까지 현재 연결과 업로드 설정은 배치 작업의 첫 단계에서 그대로 사용할 수 있습니다."
            ),
            action_text="배치 작업의 기존 설정 열기",
            action_handler=self._open_existing_batch_settings,
        )

        self.route_widgets = {
            ROUTE_TRACKER_WORKSPACE: self.tracker_workspace_page,
            ROUTE_BATCH_UPLOAD: self.batch_page,
            ROUTE_ACTIVITY: self.activity_page,
            ROUTE_SETTINGS: self.settings_center_page,
        }
        for route in APP_ROUTE_LABELS:
            self.route_stack.addWidget(self.route_widgets[route])

        body_layout.addWidget(navigation)
        body_layout.addWidget(content, 1)

        root_layout.addWidget(header)
        root_layout.addLayout(body_layout, 1)
        self.setCentralWidget(root)

    def _create_placeholder_page(
        self,
        *,
        title: str,
        phase: str,
        description: str,
        scope_text: str,
        action_text: str | None = None,
        action_handler=None,
    ):
        QWidget = self.qt["QWidget"]
        QFrame = self.qt["QFrame"]
        QHBoxLayout = self.qt["QHBoxLayout"]
        QLabel = self.qt["QLabel"]
        QPushButton = self.qt["QPushButton"]
        QVBoxLayout = self.qt["QVBoxLayout"]

        page = QWidget()
        page.setObjectName("application_route_page")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(24, 22, 24, 22)
        layout.setSpacing(14)

        heading_row = QHBoxLayout()
        heading_row.setSpacing(10)
        heading = QLabel(title)
        heading.setObjectName("application_route_title")
        heading_row.addWidget(heading)
        heading_row.addStretch(1)
        phase_badge = QLabel(phase)
        phase_badge.setObjectName("application_phase_badge")
        heading_row.addWidget(phase_badge)
        layout.addLayout(heading_row)

        description_label = QLabel(description)
        description_label.setObjectName("application_route_description")
        description_label.setWordWrap(True)
        layout.addWidget(description_label)

        scope_card = QFrame(page)
        scope_card.setObjectName("application_placeholder_card")
        scope_layout = QVBoxLayout(scope_card)
        scope_layout.setContentsMargins(16, 14, 16, 14)
        scope_layout.setSpacing(8)

        scope_title = QLabel("현재 구현 범위")
        scope_title.setObjectName("application_placeholder_title")
        scope_label = QLabel(scope_text)
        scope_label.setObjectName("application_route_description")
        scope_label.setWordWrap(True)
        scope_layout.addWidget(scope_title)
        scope_layout.addWidget(scope_label)

        if action_text and action_handler is not None:
            action_row = QHBoxLayout()
            action_row.addStretch(1)
            action_button = QPushButton(action_text)
            action_button.setObjectName("primary_button")
            action_button.clicked.connect(action_handler)
            action_row.addWidget(action_button)
            scope_layout.addLayout(action_row)

        layout.addWidget(scope_card)
        layout.addStretch(1)
        return page

    def _show_route(self, route: str) -> None:
        if route not in self.route_widgets:
            raise ValueError(f"알 수 없는 작업 영역입니다: {route}")
        self.current_route = route
        self.route_stack.setCurrentWidget(self.route_widgets[route])
        for button_route, button in self.nav_buttons.items():
            button.setChecked(button_route == route)
        if route == ROUTE_BATCH_UPLOAD:
            self.statusBar().hide()
            return
        self.statusBar().show()
        self.statusBar().showMessage(f"{APP_ROUTE_LABELS[route]} 화면을 열었습니다.")

    def _open_existing_batch_settings(self) -> None:
        self._show_route(ROUTE_BATCH_UPLOAD)
        self.batch_window._show_page(self.batch_window.settings_page)
        self.batch_window.statusBar().showMessage("기존 배치 설정 페이지를 열었습니다.")

    def _on_batch_settings_changed(self, settings: GuiSettings) -> None:
        self._update_mode_badge(settings)

    def _update_mode_badge(self, settings: GuiSettings) -> None:
        if bool(getattr(settings, "offline_mode", False)):
            text = "테스트 모드"
            mode = "test"
        elif str(getattr(settings, "base_url", "") or "").strip():
            text = "온라인 설정"
            mode = "online"
        else:
            text = "연결 미설정"
            mode = "unconfigured"
        self.mode_badge.setText(text)
        self.mode_badge.setProperty("mode", mode)
        self.mode_badge.style().unpolish(self.mode_badge)
        self.mode_badge.style().polish(self.mode_badge)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        if not self.isFullScreen() and not self.isMaximized():
            self._last_normal_window_width = max(int(self.width()), self.minimumWidth())
            self._last_normal_window_height = max(int(self.height()), self.minimumHeight())

    def closeEvent(self, event) -> None:
        current_settings = replace(self.batch_window.session_state.settings)
        updated_settings = replace(
            current_settings,
            window_width=max(int(self._last_normal_window_width), self.minimumWidth()),
            window_height=max(int(self._last_normal_window_height), self.minimumHeight()),
            window_is_maximized=bool(self.isMaximized()),
            window_is_fullscreen=bool(self.isFullScreen()),
        )
        self.batch_window.session_state.settings = updated_settings
        try:
            self.settings_store.save(updated_settings)
        except Exception:
            pass
        super().closeEvent(event)


__all__ = [
    "APP_ROUTE_LABELS",
    "BatchUploadWindow",
    "MainWindow",
    "ROUTE_ACTIVITY",
    "ROUTE_BATCH_UPLOAD",
    "ROUTE_SETTINGS",
    "ROUTE_TRACKER_WORKSPACE",
    "_estimate_upload_remaining_seconds",
    "_format_clock_text",
    "_format_duration_text",
    "_format_upload_eta_text",
    "_format_upload_progress_text",
    "_merge_root_item_page_configs",
    "_merge_window_preferences",
    "_window_size_from_settings",
]
