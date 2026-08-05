from __future__ import annotations

from dataclasses import dataclass
from dataclasses import replace
import json
from typing import Any
from typing import Callable

try:
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QAbstractItemView
    from PySide6.QtWidgets import QApplication
    from PySide6.QtWidgets import QComboBox
    from PySide6.QtWidgets import QFrame
    from PySide6.QtWidgets import QHBoxLayout
    from PySide6.QtWidgets import QHeaderView
    from PySide6.QtWidgets import QLabel
    from PySide6.QtWidgets import QLineEdit
    from PySide6.QtWidgets import QPlainTextEdit
    from PySide6.QtWidgets import QPushButton
    from PySide6.QtWidgets import QSplitter
    from PySide6.QtWidgets import QTabWidget
    from PySide6.QtWidgets import QTableWidget
    from PySide6.QtWidgets import QTableWidgetItem
    from PySide6.QtWidgets import QTreeWidget
    from PySide6.QtWidgets import QTreeWidgetItem
    from PySide6.QtWidgets import QTextBrowser
    from PySide6.QtWidgets import QVBoxLayout
    from PySide6.QtWidgets import QWidget
except ImportError as exc:  # pragma: no cover - GUI dependency guard
    raise RuntimeError("GUI 실행에는 PySide6 패키지가 필요합니다.") from exc

from .settings_store import GuiSettings
from .activity_history import ActivityOperation
from .activity_history import ActivityRecord
from .activity_history import ActivityResult
from .tracker_item_editor import EditableTrackerField
from .tracker_item_editor import EditableTrackerSchema
from .tracker_item_editor import TrackerItemEditorService
from .tracker_item_editor import TrackerItemFieldChange
from .tracker_item_editor import TrackerItemWriteError
from .tracker_item_editor_dialog import TrackerItemEditorDialog
from .tracker_item_editor_panel import ConfirmItemDeleteDialog
from .tracker_item_editor_panel import TrackerItemEditorPanel
from .tracker_item_create_dialog import TrackerItemCreateDialog
from .tracker_item_create_dialog import TrackerItemCreateRequest
from .tracker_bulk_update import BulkUpdateRunStore
from .tracker_bulk_update import TrackerBulkUpdateService
from .tracker_bulk_update_dialog import BulkUpdateProgressDialog
from .tracker_bulk_update_dialog import BulkUpdateRequest
from .tracker_bulk_update_dialog import TrackerBulkUpdateDialog
from .tracker_condition_builder import TrackerConditionBuilder
from .tracker_query_models import PageResult
from .tracker_query_models import ProjectSummary
from .tracker_query_models import TrackerFieldValue
from .tracker_query_models import TrackerItemContext
from .tracker_query_models import TrackerItemDetail
from .tracker_query_models import TrackerItemSummary
from .tracker_query_models import TrackerQuery
from .tracker_query_models import TrackerSearchMode
from .tracker_query_models import TrackerQueryServiceError
from .tracker_query_models import TrackerSummary
from .tracker_query_service import TrackerQueryService
from .tracker_baseline_compare import BaselineComparisonKind
from .tracker_baseline_compare import BaselineComparisonResult
from .tracker_baseline_compare import BaselineComparisonSource
from .tracker_baseline_compare import TrackerBaseline
from .tracker_baseline_compare import TrackerItemComparison
from .tracker_table_field_dialog import TrackerTableFieldDialog
from .tracker_table_field_dialog import is_table_field
from .tracker_table_field_dialog import table_field_summary
from .worker import BackgroundTask
from .worker import BulkUpdateWorker
from .wiki_renderer import codebeamer_wiki_to_html
from .wiki_renderer import is_explicit_wiki_type
from .wiki_renderer import payload_uses_wiki


ITEM_SUMMARY_ROLE = int(Qt.ItemDataRole.UserRole) + 1
PLACEHOLDER_ROLE = int(Qt.ItemDataRole.UserRole) + 2
CHILDREN_LOADED_ROLE = int(Qt.ItemDataRole.UserRole) + 3
HIERARCHY_FETCH_PAGE_SIZE = 500
DEFAULT_SEARCH_PAGE_SIZE = 50

REQUEST_BUSY_MESSAGES = {
    "projects": "프로젝트 목록을 불러오는 중입니다.",
    "trackers": "트래커 목록을 불러오는 중입니다.",
    "roots": "최상위 아이템을 불러오는 중입니다.",
    "detail": "아이템 상세 정보를 불러오는 중입니다.",
    "create_schema": "새 아이템 생성 필드를 확인하는 중입니다.",
    "item_create": "새 트래커 아이템을 생성하는 중입니다.",
    "search": "현재 트래커에서 아이템을 검색하는 중입니다.",
    "search_schema": "다중 조건 검색 필드를 확인하는 중입니다.",
    "search_all": "검색 결과 전체 대상을 확인하는 중입니다.",
    "baseline_list": "비교 가능한 baseline 목록을 불러오는 중입니다.",
    "baseline_compare": "두 기준의 검색 결과 전체를 비교하는 중입니다.",
    "direct": "아이템 ID의 위치와 계층을 확인하는 중입니다.",
    "editor_schema": "수정 가능한 필드를 확인하는 중입니다.",
    "item_write": "트래커 아이템 변경 사항을 반영하는 중입니다.",
}


@dataclass(frozen=True)
class _DirectItemResult:
    context: TrackerItemContext
    ancestor_path: tuple[TrackerItemSummary, ...]


class _BaselineComparisonPanel(QWidget):
    """현재 트래커 전체를 두 읽기 전용 기준에서 비교하는 탭."""

    _KIND_LABELS = {
        BaselineComparisonKind.ADDED: "추가",
        BaselineComparisonKind.REMOVED: "삭제",
        BaselineComparisonKind.CHANGED: "변경",
        BaselineComparisonKind.UNCHANGED: "변경 없음",
    }

    def __init__(
        self,
        run_comparison: Callable[[BaselineComparisonSource, BaselineComparisonSource], None],
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._run_comparison = run_comparison
        self._result: BaselineComparisonResult | None = None

        layout = QVBoxLayout(self)
        source_row = QHBoxLayout()
        source_row.addWidget(QLabel("기준 A", self))
        self.before_combo = QComboBox(self)
        self.before_combo.addItem("현재 상태", None)
        source_row.addWidget(self.before_combo, 1)
        source_row.addWidget(QLabel("기준 B", self))
        self.after_combo = QComboBox(self)
        self.after_combo.addItem("선택하세요", "")
        self.after_combo.addItem("현재 상태", None)
        source_row.addWidget(self.after_combo, 1)
        self.run_button = QPushButton("선택 아이템 비교", self)
        self.run_button.setObjectName("primary_button")
        self.run_button.clicked.connect(self._run)
        source_row.addWidget(self.run_button)
        layout.addLayout(source_row)

        self.status_label = QLabel("왼쪽 현재 계층에서 아이템을 선택하세요.", self)
        self.status_label.setObjectName("tracker_panel_status")
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)

        filter_row = QHBoxLayout()
        filter_row.addWidget(QLabel("표시", self))
        self.kind_filter = QComboBox(self)
        self.kind_filter.addItem("전체", "all")
        self.kind_filter.addItem("변경만", "changed")
        for kind, label in self._KIND_LABELS.items():
            self.kind_filter.addItem(label, kind.value)
        self.kind_filter.currentIndexChanged.connect(self._render_items)
        filter_row.addWidget(self.kind_filter)
        filter_row.addStretch(1)
        layout.addLayout(filter_row)

        self.table = QTableWidget(0, 4, self)
        self.table.setHorizontalHeaderLabels(["유형", "ID", "요약", "변경 필드"])
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.table.itemSelectionChanged.connect(self._render_detail)
        layout.addWidget(self.table, 2)

        self.detail = QTableWidget(0, 3, self)
        self.detail.setHorizontalHeaderLabels(["필드", "기준 A", "기준 B"])
        self.detail.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.detail.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.detail.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.detail.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.detail.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.detail, 1)

    def _source(self, combo: QComboBox) -> BaselineComparisonSource | None:
        value = combo.currentData()
        if value == "":
            return None
        return BaselineComparisonSource(None if value is None else int(value))

    def _run(self) -> None:
        before = self._source(self.before_combo)
        after = self._source(self.after_combo)
        if before is None or after is None:
            self.status_label.setText("비교할 두 기준을 선택하세요.")
            return
        if before == after:
            self.status_label.setText("서로 다른 두 비교 기준을 선택하세요.")
            return
        self.run_button.setEnabled(False)
        self.status_label.setText("선택한 아이템을 두 기준에서 조회하는 중입니다.")
        self._run_comparison(before, after)

    def set_baselines(self, baselines: tuple[TrackerBaseline, ...]) -> None:
        self.before_combo.clear()
        self.after_combo.clear()
        self.before_combo.addItem("현재 상태", None)
        self.after_combo.addItem("선택하세요", "")
        self.after_combo.addItem("현재 상태", None)
        for baseline in baselines:
            label = baseline.name
            if baseline.created_at:
                label = f"{label} ({baseline.created_at})"
            self.before_combo.addItem(label, baseline.baseline_id)
            self.after_combo.addItem(label, baseline.baseline_id)
        self.status_label.setText(
            f"현재 트래커에서 비교 가능한 baseline {len(baselines)}개를 불러왔습니다."
        )

    def sources(self) -> tuple[BaselineComparisonSource | None, BaselineComparisonSource | None]:
        return self._source(self.before_combo), self._source(self.after_combo)

    def set_result(self, result: BaselineComparisonResult) -> None:
        self._result = result
        self.run_button.setEnabled(True)
        self.status_label.setText(
            "추가 {added}개 · 삭제 {removed}개 · 변경 {changed}개 · 변경 없음 {unchanged}개".format(
                added=result.count(BaselineComparisonKind.ADDED),
                removed=result.count(BaselineComparisonKind.REMOVED),
                changed=result.count(BaselineComparisonKind.CHANGED),
                unchanged=result.count(BaselineComparisonKind.UNCHANGED),
            )
        )
        self._render_items()
        if self.table.rowCount() > 0:
            self.table.selectRow(0)

    def set_error(self, message: str) -> None:
        self.run_button.setEnabled(True)
        self.status_label.setText(message)

    def _render_items(self) -> None:
        result = self._result
        self.table.setRowCount(0)
        self.detail.setRowCount(0)
        if result is None:
            return
        selected = str(self.kind_filter.currentData() or "changed")
        items = result.items if selected == "all" else tuple(
            item for item in result.items if item.kind.value == selected
        )
        self.table.setRowCount(len(items))
        for row, comparison in enumerate(items):
            values = (
                self._KIND_LABELS[comparison.kind],
                str(comparison.item_id),
                comparison.name,
                str(len(comparison.fields)),
            )
            for column, value in enumerate(values):
                cell = QTableWidgetItem(value)
                if column == 0:
                    cell.setData(ITEM_SUMMARY_ROLE, comparison)
                self.table.setItem(row, column, cell)

    def _render_detail(self) -> None:
        selected = self.table.selectedItems()
        if not selected:
            return
        comparison = self.table.item(selected[0].row(), 0).data(ITEM_SUMMARY_ROLE)
        if not isinstance(comparison, TrackerItemComparison):
            return
        self.detail.setRowCount(0)
        if comparison.kind != BaselineComparisonKind.CHANGED:
            return
        self.detail.setRowCount(len(comparison.fields))
        for row, field in enumerate(comparison.fields):
            self.detail.setItem(row, 0, QTableWidgetItem(field.label))
            self.detail.setItem(row, 1, QTableWidgetItem(field.before_text()))
            self.detail.setItem(row, 2, QTableWidgetItem(field.after_text()))


class TrackerWorkspacePage(QWidget):
    """프로젝트와 트래커를 기준으로 계층, 검색, 상세를 연결한다."""

    def __init__(
        self,
        *,
        settings_provider: Callable[[], GuiSettings],
        service: TrackerQueryService | None = None,
        editor_service: TrackerItemEditorService | None = None,
        open_settings: Callable[[], None] | None = None,
        delete_confirmer: Callable[[TrackerItemDetail], bool] | None = None,
        create_request_provider: Callable[
            [EditableTrackerSchema, TrackerSummary, TrackerItemDetail | None],
            TrackerItemCreateRequest | None,
        ]
        | None = None,
        activity_recorder: Callable[[ActivityRecord], None] | None = None,
        bulk_update_service: TrackerBulkUpdateService | None = None,
        bulk_run_store: BulkUpdateRunStore | None = None,
        bulk_chunk_size_saver: Callable[[int], None] | None = None,
        bulk_request_provider: Callable[..., BulkUpdateRequest | None] | None = None,
        busy_started: Callable[[str], object] | None = None,
        busy_finished: Callable[[object], None] | None = None,
        task_factory=BackgroundTask,
        synchronous: bool = False,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("tracker_workspace_page")
        self.settings_provider = settings_provider
        self.service = service or TrackerQueryService()
        self.editor_service = editor_service or TrackerItemEditorService(
            query_service=self.service
        )
        self.open_settings = open_settings
        self.delete_confirmer = delete_confirmer
        self.create_request_provider = create_request_provider
        self.activity_recorder = activity_recorder
        self.bulk_update_service = bulk_update_service or TrackerBulkUpdateService()
        self.bulk_run_store = bulk_run_store
        self.bulk_chunk_size_saver = bulk_chunk_size_saver
        self.bulk_request_provider = bulk_request_provider
        self.busy_started = busy_started
        self.busy_finished = busy_finished
        self.task_factory = task_factory
        self.synchronous = bool(synchronous)

        self._activated = False
        self._settings_fingerprint: tuple[Any, ...] | None = None
        self._projects: tuple[ProjectSummary, ...] = ()
        self._trackers: tuple[TrackerSummary, ...] = ()
        self._current_project: ProjectSummary | None = None
        self._current_tracker: TrackerSummary | None = None
        self._root_cache: dict[int, tuple[TrackerItemSummary, ...]] = {}
        self._child_cache: dict[int, tuple[TrackerItemSummary, ...]] = {}
        self._request_tokens: dict[str, int] = {}
        self._tasks: set[Any] = set()
        self._search_page = 1
        self._last_search_query: TrackerQuery | None = None
        self._last_search_result: PageResult[TrackerItemSummary] | None = None
        self._search_schema: EditableTrackerSchema | None = None
        self._selected_search_ids: set[int] = set()
        self._all_search_selected = False
        self._excluded_search_ids: set[int] = set()
        self._selected_item_id: int | None = None
        self._baseline_selected_item_id: int | None = None
        self._current_detail: TrackerItemDetail | None = None
        self._description_text = ""
        self._description_uses_wiki = False
        self._pre_editor_splitter_sizes: list[int] | None = None
        self._create_busy = False
        self._editor_dialog: TrackerItemEditorDialog | None = None
        self._bulk_worker = None
        self._bulk_progress_dialog: BulkUpdateProgressDialog | None = None

        self._build_ui()
        self._reset_workspace("프로젝트와 트래커를 불러오면 조회를 시작할 수 있습니다.")

    def _build_ui(self) -> None:
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(18, 16, 18, 16)
        root_layout.setSpacing(10)

        heading_row = QHBoxLayout()
        heading_row.setSpacing(8)
        title_group = QVBoxLayout()
        title_group.setSpacing(2)
        title = QLabel("트래커 작업공간")
        title.setObjectName("application_route_title")
        subtitle = QLabel(
            "프로젝트와 트래커를 선택해 계층을 탐색하거나, 현재 트래커 안에서 아이템을 검색합니다."
        )
        subtitle.setObjectName("application_route_description")
        subtitle.setWordWrap(True)
        title_group.addWidget(title)
        title_group.addWidget(subtitle)
        heading_row.addLayout(title_group, 1)

        self.direct_id_input = QLineEdit(self)
        self.direct_id_input.setObjectName("tracker_direct_id_input")
        self.direct_id_input.setPlaceholderText("아이템 ID")
        self.direct_id_input.setAccessibleName("아이템 ID 바로 열기")
        self.direct_id_input.setMaximumWidth(130)
        self.direct_id_input.returnPressed.connect(self._open_direct_item)
        heading_row.addWidget(self.direct_id_input)
        self.direct_open_button = QPushButton("ID 바로 열기", self)
        self.direct_open_button.setObjectName("primary_button")
        self.direct_open_button.clicked.connect(self._open_direct_item)
        heading_row.addWidget(self.direct_open_button)
        root_layout.addLayout(heading_row)

        context_card = QFrame(self)
        context_card.setObjectName("tracker_context_card")
        context_layout = QHBoxLayout(context_card)
        context_layout.setContentsMargins(12, 10, 12, 10)
        context_layout.setSpacing(8)

        project_label = QLabel("프로젝트")
        project_label.setObjectName("tracker_context_label")
        context_layout.addWidget(project_label)
        self.project_combo = QComboBox(context_card)
        self.project_combo.setObjectName("tracker_project_combo")
        self.project_combo.setMinimumWidth(150)
        self.project_combo.setSizeAdjustPolicy(
            QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon
        )
        self.project_combo.setMinimumContentsLength(18)
        self.project_combo.activated.connect(self._on_project_activated)
        context_layout.addWidget(self.project_combo, 1)

        tracker_label = QLabel("트래커")
        tracker_label.setObjectName("tracker_context_label")
        context_layout.addWidget(tracker_label)
        self.tracker_combo = QComboBox(context_card)
        self.tracker_combo.setObjectName("tracker_tracker_combo")
        self.tracker_combo.setMinimumWidth(150)
        self.tracker_combo.setSizeAdjustPolicy(
            QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon
        )
        self.tracker_combo.setMinimumContentsLength(18)
        self.tracker_combo.activated.connect(self._on_tracker_activated)
        context_layout.addWidget(self.tracker_combo, 1)

        self.create_item_button = QPushButton("새 아이템", context_card)
        self.create_item_button.setObjectName("primary_button")
        self.create_item_button.setToolTip(
            "현재 트래커에 최상위 또는 선택 아이템의 하위 항목을 만듭니다."
        )
        self.create_item_button.clicked.connect(self._create_item)
        context_layout.addWidget(self.create_item_button)

        self.refresh_context_button = QPushButton("새로고침", context_card)
        self.refresh_context_button.clicked.connect(lambda: self.activate(force=True))
        context_layout.addWidget(self.refresh_context_button)
        root_layout.addWidget(context_card)

        status_row = QHBoxLayout()
        self.workspace_status_label = QLabel("")
        self.workspace_status_label.setObjectName("tracker_workspace_status")
        self.workspace_status_label.setWordWrap(True)
        status_row.addWidget(self.workspace_status_label, 1)
        self.open_settings_button = QPushButton("설정 열기", self)
        self.open_settings_button.setVisible(self.open_settings is not None)
        if self.open_settings is not None:
            self.open_settings_button.clicked.connect(self.open_settings)
        status_row.addWidget(self.open_settings_button)
        root_layout.addLayout(status_row)

        self.workspace_mode_tabs = QTabWidget(self)
        self.workspace_mode_tabs.setObjectName("tracker_workspace_mode_tabs")
        browse_page = QWidget(self.workspace_mode_tabs)
        browse_page_layout = QVBoxLayout(browse_page)
        browse_page_layout.setContentsMargins(0, 0, 0, 0)

        splitter = QSplitter(Qt.Orientation.Horizontal, browse_page)
        splitter.setObjectName("tracker_workspace_splitter")
        splitter.setChildrenCollapsible(False)
        self.workspace_splitter = splitter

        browser_panel = QFrame(splitter)
        browser_panel.setObjectName("tracker_workspace_panel")
        browser_panel.setMinimumWidth(300)
        browser_layout = QVBoxLayout(browser_panel)
        browser_layout.setContentsMargins(10, 10, 10, 10)
        browser_layout.setSpacing(8)

        self.browser_tabs = QTabWidget(browser_panel)
        self.browser_tabs.setObjectName("tracker_browser_tabs")
        self.browser_tabs.addTab(self._build_hierarchy_tab(), "계층")
        self.browser_tabs.addTab(self._build_search_tab(), "트래커 검색")
        browser_layout.addWidget(self.browser_tabs, 1)

        detail_panel = QFrame(splitter)
        detail_panel.setObjectName("tracker_workspace_panel")
        detail_panel.setMinimumWidth(300)
        detail_layout = QVBoxLayout(detail_panel)
        detail_layout.setContentsMargins(12, 10, 12, 10)
        detail_layout.setSpacing(8)

        detail_heading = QHBoxLayout()
        self.detail_title = QLabel("아이템 상세")
        self.detail_title.setObjectName("tracker_detail_title")
        detail_heading.addWidget(self.detail_title, 1)
        self.detail_refresh_button = QPushButton("상세 새로고침", detail_panel)
        self.detail_refresh_button.setToolTip("현재 아이템의 최신 version과 필드를 다시 조회합니다.")
        self.detail_refresh_button.clicked.connect(self._reload_current_detail)
        self.detail_refresh_button.setEnabled(False)
        detail_heading.addWidget(self.detail_refresh_button)
        self.detail_id_badge = QPushButton("", detail_panel)
        self.detail_id_badge.setObjectName("tracker_id_copy_button")
        self.detail_id_badge.setCursor(Qt.CursorShape.PointingHandCursor)
        self.detail_id_badge.setToolTip("클릭하면 아이템 ID 숫자만 복사합니다.")
        self.detail_id_badge.setAccessibleName("아이템 ID 복사")
        self.detail_id_badge.clicked.connect(self._copy_selected_item_id)
        self.detail_id_badge.hide()
        detail_heading.addWidget(self.detail_id_badge)
        detail_layout.addLayout(detail_heading)

        self.detail_breadcrumb = QLabel("선택한 아이템이 없습니다.")
        self.detail_breadcrumb.setObjectName("tracker_detail_breadcrumb")
        self.detail_breadcrumb.setWordWrap(True)
        detail_layout.addWidget(self.detail_breadcrumb)

        self.detail_warning = QLabel("")
        self.detail_warning.setObjectName("tracker_detail_warning")
        self.detail_warning.setWordWrap(True)
        self.detail_warning.hide()
        detail_layout.addWidget(self.detail_warning)

        self.detail_tabs = QTabWidget(detail_panel)
        self.detail_tabs.setObjectName("tracker_detail_tabs")
        self.detail_tabs.addTab(self._build_overview_tab(), "개요")
        self.detail_tabs.addTab(self._build_raw_tab(), "원본 JSON")

        self.editor_host = QWidget(self.detail_tabs)
        self.editor_host.setObjectName("tracker_item_editor_host")
        self.editor_host_layout = QVBoxLayout(self.editor_host)
        self.editor_host_layout.setContentsMargins(0, 0, 0, 0)
        self.editor_host_layout.setSpacing(6)
        editor_toolbar = QHBoxLayout()
        editor_toolbar.addStretch(1)
        self.popout_editor_button = QPushButton(
            "새 창에서 크게 수정",
            self.editor_host,
        )
        self.popout_editor_button.clicked.connect(self._show_editor_in_window)
        editor_toolbar.addWidget(self.popout_editor_button)
        self.editor_host_layout.addLayout(editor_toolbar)
        self.editor_placeholder = QLabel(
            "수정 화면이 새 창에 열려 있습니다.",
            self.editor_host,
        )
        self.editor_placeholder.setObjectName("tracker_panel_status")
        self.editor_placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.editor_placeholder.hide()
        self.editor_host_layout.addWidget(self.editor_placeholder, 1)
        self.editor_panel = TrackerItemEditorPanel(
            save_requested=self._save_item_changes,
            transition_requested=self._transition_item_status,
            delete_requested=self._delete_current_item,
            parent=self.editor_host,
        )
        self.editor_host_layout.addWidget(self.editor_panel, 1)
        self.editor_tab_index = self.detail_tabs.addTab(self.editor_host, "수정")
        self.detail_tabs.currentChanged.connect(self._on_detail_tab_changed)
        detail_layout.addWidget(self.detail_tabs, 1)

        splitter.addWidget(browser_panel)
        splitter.addWidget(detail_panel)
        splitter.setStretchFactor(0, 6)
        splitter.setStretchFactor(1, 5)
        splitter.setSizes([560, 470])
        browse_page_layout.addWidget(splitter, 1)
        self.workspace_mode_tabs.addTab(browse_page, "트래커 조회")
        self.baseline_mode_index = self.workspace_mode_tabs.addTab(
            self._build_baseline_workspace(), "Baseline 비교"
        )
        self.workspace_mode_tabs.currentChanged.connect(self._on_workspace_mode_changed)
        root_layout.addWidget(self.workspace_mode_tabs, 1)

    def _build_hierarchy_tab(self) -> QWidget:
        tab = QWidget(self)
        tab.setObjectName("tracker_hierarchy_tab")
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(6, 8, 6, 6)
        layout.setSpacing(6)

        toolbar = QHBoxLayout()
        self.tree_status_label = QLabel("트래커를 선택하세요.")
        self.tree_status_label.setObjectName("tracker_panel_status")
        toolbar.addWidget(self.tree_status_label, 1)
        self.reload_roots_button = QPushButton("최상위 다시 불러오기", tab)
        self.reload_roots_button.clicked.connect(
            lambda: self._load_roots(force=True)
        )
        toolbar.addWidget(self.reload_roots_button)
        layout.addLayout(toolbar)

        self.item_tree = QTreeWidget(tab)
        self.item_tree.setObjectName("tracker_item_tree")
        self.item_tree.setColumnCount(2)
        self.item_tree.setHeaderLabels(["ID", "요약"])
        self.item_tree.setAlternatingRowColors(True)
        self.item_tree.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.item_tree.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.item_tree.setUniformRowHeights(True)
        self.item_tree.header().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.item_tree.header().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.item_tree.itemExpanded.connect(self._on_tree_item_expanded)
        self.item_tree.itemSelectionChanged.connect(self._on_tree_selection_changed)
        layout.addWidget(self.item_tree, 1)
        return tab

    def _build_search_tab(self) -> QWidget:
        tab = QWidget(self)
        tab.setObjectName("tracker_search_tab")
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(6, 8, 6, 6)
        layout.setSpacing(6)

        mode_row = QHBoxLayout()
        mode_row.addWidget(QLabel("검색 방식", tab))
        self.search_mode_combo = QComboBox(tab)
        self.search_mode_combo.addItem("간편 검색", TrackerSearchMode.SIMPLE.value)
        self.search_mode_combo.addItem("다중 조건 검색", TrackerSearchMode.CONDITIONS.value)
        self.search_mode_combo.currentIndexChanged.connect(self._on_search_mode_changed)
        mode_row.addWidget(self.search_mode_combo)
        mode_row.addStretch(1)
        self.search_button = QPushButton("현재 트래커 검색", tab)
        self.search_button.setObjectName("primary_button")
        self.search_button.clicked.connect(self._run_search)
        mode_row.addWidget(self.search_button)
        self.baseline_compare_button = QPushButton("Baseline 비교", tab)
        self.baseline_compare_button.setObjectName("tracker_baseline_compare_button")
        self.baseline_compare_button.setToolTip("Baseline 비교 탭으로 이동합니다.")
        self.baseline_compare_button.clicked.connect(self._open_baseline_comparison)
        self.baseline_compare_button.hide()
        layout.addLayout(mode_row)

        self.simple_search_host = QWidget(tab)
        first_row = QHBoxLayout(self.simple_search_host)
        first_row.setContentsMargins(0, 0, 0, 0)
        self.search_text_input = QLineEdit(self.simple_search_host)
        self.search_text_input.setObjectName("tracker_search_text")
        self.search_text_input.setPlaceholderText("ID 또는 요약")
        self.search_text_input.returnPressed.connect(self._run_search)
        first_row.addWidget(self.search_text_input, 2)
        self.search_status_input = QLineEdit(self.simple_search_host)
        self.search_status_input.setObjectName("tracker_search_status")
        self.search_status_input.setPlaceholderText("상태")
        self.search_status_input.returnPressed.connect(self._run_search)
        first_row.addWidget(self.search_status_input, 1)
        self.search_assignee_input = QLineEdit(self.simple_search_host)
        self.search_assignee_input.setObjectName("tracker_search_assignee")
        self.search_assignee_input.setPlaceholderText("담당자")
        self.search_assignee_input.returnPressed.connect(self._run_search)
        first_row.addWidget(self.search_assignee_input, 1)
        layout.addWidget(self.simple_search_host)

        self.condition_builder = TrackerConditionBuilder(tab)
        self.condition_builder.hide()
        layout.addWidget(self.condition_builder)

        self.search_scope_label = QLabel("프로젝트와 트래커를 먼저 선택하세요.")
        self.search_scope_label.setObjectName("tracker_panel_status")
        self.search_scope_label.setWordWrap(True)
        layout.addWidget(self.search_scope_label)

        selection_row = QHBoxLayout()
        self.search_selection_label = QLabel("선택 0개", tab)
        self.search_selection_label.setObjectName("tracker_panel_status")
        selection_row.addWidget(self.search_selection_label)
        selection_row.addStretch(1)
        self.select_page_button = QPushButton("현재 페이지 선택", tab)
        self.select_page_button.clicked.connect(self._select_current_search_page)
        selection_row.addWidget(self.select_page_button)
        self.select_all_results_button = QPushButton("검색 결과 전체 선택", tab)
        self.select_all_results_button.clicked.connect(self._select_all_search_results)
        selection_row.addWidget(self.select_all_results_button)
        self.clear_search_selection_button = QPushButton("선택 해제", tab)
        self.clear_search_selection_button.clicked.connect(self._clear_search_selection)
        selection_row.addWidget(self.clear_search_selection_button)
        self.bulk_update_button = QPushButton("선택 항목 일괄 수정", tab)
        self.bulk_update_button.setObjectName("primary_button")
        self.bulk_update_button.clicked.connect(self._start_bulk_update)
        selection_row.addWidget(self.bulk_update_button)
        layout.addLayout(selection_row)

        self.search_table = QTableWidget(0, 5, tab)
        self.search_table.setObjectName("tracker_search_results")
        self.search_table.setHorizontalHeaderLabels(["선택", "ID", "요약", "상태", "담당자"])
        self.search_table.setAlternatingRowColors(True)
        self.search_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.search_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.search_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.search_table.verticalHeader().setVisible(False)
        self.search_table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.ResizeToContents
        )
        self.search_table.horizontalHeader().setSectionResizeMode(
            2, QHeaderView.ResizeMode.Stretch
        )
        self.search_table.horizontalHeader().setSectionResizeMode(
            3, QHeaderView.ResizeMode.ResizeToContents
        )
        self.search_table.horizontalHeader().setSectionResizeMode(
            4, QHeaderView.ResizeMode.ResizeToContents
        )
        self.search_table.itemChanged.connect(self._on_search_check_changed)
        self.search_table.itemSelectionChanged.connect(self._on_search_selection_changed)
        layout.addWidget(self.search_table, 1)

        page_row = QHBoxLayout()
        self.search_previous_button = QPushButton("이전", tab)
        self.search_previous_button.clicked.connect(
            lambda: self._run_search(page=max(self._search_page - 1, 1), reuse=True)
        )
        self.search_page_label = QLabel("1 페이지")
        self.search_page_label.setObjectName("tracker_page_label")
        self.search_next_button = QPushButton("다음", tab)
        self.search_next_button.clicked.connect(
            lambda: self._run_search(page=self._search_page + 1, reuse=True)
        )
        page_row.addStretch(1)
        page_row.addWidget(self.search_previous_button)
        page_row.addWidget(self.search_page_label)
        page_row.addWidget(self.search_next_button)
        layout.addLayout(page_row)
        return tab

    def _build_baseline_workspace(self) -> QWidget:
        page = QWidget(self)
        page.setObjectName("tracker_baseline_comparison_page")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(6, 8, 6, 6)

        splitter = QSplitter(Qt.Orientation.Horizontal, page)
        splitter.setChildrenCollapsible(False)

        tree_panel = QFrame(splitter)
        tree_layout = QVBoxLayout(tree_panel)
        tree_toolbar = QHBoxLayout()
        self.baseline_tree_status_label = QLabel("트래커를 선택하세요.", tree_panel)
        tree_toolbar.addWidget(self.baseline_tree_status_label, 1)
        self.baseline_reload_button = QPushButton("현재 계층 다시 불러오기", tree_panel)
        self.baseline_reload_button.clicked.connect(lambda: self._load_roots(force=True))
        tree_toolbar.addWidget(self.baseline_reload_button)
        tree_layout.addLayout(tree_toolbar)
        self.baseline_item_tree = QTreeWidget(tree_panel)
        self.baseline_item_tree.setColumnCount(2)
        self.baseline_item_tree.setHeaderLabels(["ID", "요약"])
        self.baseline_item_tree.setAlternatingRowColors(True)
        self.baseline_item_tree.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.baseline_item_tree.header().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.baseline_item_tree.header().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.baseline_item_tree.itemExpanded.connect(self._on_baseline_tree_item_expanded)
        self.baseline_item_tree.itemSelectionChanged.connect(self._on_baseline_tree_selection_changed)
        tree_layout.addWidget(self.baseline_item_tree, 1)

        panel = _BaselineComparisonPanel(self._run_baseline_comparison, splitter)
        panel.setObjectName("tracker_baseline_comparison_panel")
        self.baseline_comparison_panel = panel
        splitter.addWidget(tree_panel)
        splitter.addWidget(panel)
        splitter.setStretchFactor(0, 4)
        splitter.setStretchFactor(1, 6)
        splitter.setSizes([420, 620])
        layout.addWidget(splitter, 1)
        return page

    def _build_overview_tab(self) -> QWidget:
        tab = QWidget(self)
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(6, 8, 6, 6)
        layout.setSpacing(6)
        description_header = QHBoxLayout()
        description_label = QLabel("설명")
        description_label.setObjectName("tracker_detail_section_title")
        description_header.addWidget(description_label, 1)
        self.description_source_toggle = QPushButton("Wiki 원문", tab)
        self.description_source_toggle.setObjectName("mode_toggle")
        self.description_source_toggle.setCheckable(True)
        self.description_source_toggle.setVisible(False)
        self.description_source_toggle.toggled.connect(self._render_description)
        description_header.addWidget(self.description_source_toggle)
        layout.addLayout(description_header)
        self.detail_description = QTextBrowser(tab)
        self.detail_description.setObjectName("tracker_detail_description")
        self.detail_description.setReadOnly(True)
        self.detail_description.setOpenExternalLinks(False)
        self.detail_description.setPlaceholderText("아이템을 선택하면 설명을 표시합니다.")
        self.detail_description.setMaximumHeight(150)
        layout.addWidget(self.detail_description)

        fields_label = QLabel("필드")
        fields_label.setObjectName("tracker_detail_section_title")
        layout.addWidget(fields_label)
        self.detail_fields_table = QTableWidget(0, 3, tab)
        self.detail_fields_table.setObjectName("tracker_detail_fields")
        self.detail_fields_table.setHorizontalHeaderLabels(["필드", "값", "유형"])
        self.detail_fields_table.setAlternatingRowColors(True)
        self.detail_fields_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.detail_fields_table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self.detail_fields_table.verticalHeader().setVisible(False)
        self.detail_fields_table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.ResizeToContents
        )
        self.detail_fields_table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.Stretch
        )
        self.detail_fields_table.horizontalHeader().setSectionResizeMode(
            2, QHeaderView.ResizeMode.ResizeToContents
        )
        layout.addWidget(self.detail_fields_table, 1)
        return tab

    def _build_raw_tab(self) -> QWidget:
        tab = QWidget(self)
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(6, 8, 6, 6)
        self.detail_raw_json = QPlainTextEdit(tab)
        self.detail_raw_json.setObjectName("tracker_detail_raw_json")
        self.detail_raw_json.setReadOnly(True)
        self.detail_raw_json.setPlaceholderText(
            "민감한 키가 마스킹된 Codebeamer 응답을 표시합니다."
        )
        layout.addWidget(self.detail_raw_json)
        return tab

    @staticmethod
    def _settings_key(settings: GuiSettings) -> tuple[Any, ...]:
        return (
            bool(settings.offline_mode),
            str(settings.base_url or "").strip().rstrip("/"),
            str(settings.username or "").strip(),
            bool(settings.password),
            str(settings.offline_schema_path or "").strip(),
            str(settings.offline_query_data_path or "").strip(),
        )

    @staticmethod
    def _settings_available(settings: GuiSettings) -> tuple[bool, str]:
        if bool(settings.offline_mode):
            if not str(settings.offline_query_data_path or "").strip():
                return (
                    False,
                    "테스트 모드 조회 데이터 Snapshot이 필요합니다. 설정에서 파일을 지정하고 적용하세요.",
                )
            return True, "테스트 모드 조회 데이터를 사용합니다."
        if all(
            (
                str(settings.base_url or "").strip(),
                str(settings.username or "").strip(),
                str(settings.password or ""),
            )
        ):
            return True, "온라인 연결을 사용합니다."
        return False, "활성 연결이 없습니다. 설정에서 연결을 검증하고 적용하세요."

    def activate(self, *, force: bool = False) -> None:
        settings = self.settings_provider()
        fingerprint = self._settings_key(settings)
        settings_changed = fingerprint != self._settings_fingerprint
        if force or settings_changed:
            clear_cache = getattr(self.service, "clear_cache", None)
            if callable(clear_cache):
                clear_cache()
        if settings_changed:
            self._settings_fingerprint = fingerprint
            self._clear_context_state()
        available, message = self._settings_available(settings)
        self._set_available(available)
        if not available:
            self._set_workspace_status(message, tone="warning")
            self._activated = True
            return
        if self._activated and self._projects and not force and not settings_changed:
            return
        self._activated = True
        self._load_projects(force=force or settings_changed)

    def on_settings_applied(self, settings: GuiSettings | None = None) -> None:
        del settings
        self._activated = False
        self._settings_fingerprint = None
        self.activate(force=True)

    def _clear_context_state(self) -> None:
        self._invalidate_requests()
        self._projects = ()
        self._trackers = ()
        self._current_project = None
        self._current_tracker = None
        self._root_cache.clear()
        self._child_cache.clear()
        self.project_combo.clear()
        self.tracker_combo.clear()
        self.search_table.setRowCount(0)
        self._last_search_query = None
        self._last_search_result = None
        self._search_schema = None
        self._clear_search_selection()
        self._search_page = 1
        self._selected_item_id = None
        self._current_detail = None
        self._reset_detail()
        self._reset_workspace("프로젝트와 트래커를 불러오는 중입니다.")

    def _reset_workspace(self, message: str) -> None:
        self.item_tree.clear()
        self.baseline_item_tree.clear()
        self._baseline_selected_item_id = None
        self.tree_status_label.setText(message)
        self.baseline_tree_status_label.setText(message)
        self.baseline_comparison_panel.set_error(message)
        self.search_scope_label.setText("프로젝트와 트래커를 먼저 선택하세요.")
        self.search_previous_button.setEnabled(False)
        self.search_next_button.setEnabled(False)

    def _set_available(self, available: bool) -> None:
        settings = self.settings_provider()
        self.direct_id_input.setEnabled(available)
        self.direct_open_button.setEnabled(available)
        self.refresh_context_button.setEnabled(available)
        self.project_combo.setEnabled(available and bool(self._projects))
        self.tracker_combo.setEnabled(available and bool(self._trackers))
        self.reload_roots_button.setEnabled(available and self._current_tracker is not None)
        self.baseline_reload_button.setEnabled(
            available and self._current_tracker is not None
        )
        self.search_text_input.setEnabled(available and self._current_tracker is not None)
        self.search_status_input.setEnabled(available and self._current_tracker is not None)
        self.search_assignee_input.setEnabled(available and self._current_tracker is not None)
        self.search_button.setEnabled(available and self._current_tracker is not None)
        self.baseline_compare_button.setEnabled(
            available and self._current_tracker is not None and self._last_search_query is not None
        )
        self.search_mode_combo.setEnabled(available and self._current_tracker is not None)
        self.bulk_update_button.setEnabled(
            available
            and self._current_tracker is not None
            and not bool(settings.offline_mode)
            and self._selected_search_count() > 0
        )
        self.create_item_button.setEnabled(
            available
            and self._current_tracker is not None
            and not bool(settings.offline_mode)
            and not self._create_busy
        )

    def _set_workspace_status(self, message: str, *, tone: str = "info") -> None:
        self.workspace_status_label.setText(str(message or ""))
        self.workspace_status_label.setProperty("tone", tone)
        self.workspace_status_label.style().unpolish(self.workspace_status_label)
        self.workspace_status_label.style().polish(self.workspace_status_label)

    def _record_activity(self, record: ActivityRecord) -> None:
        if self.activity_recorder is None:
            return
        try:
            self.activity_recorder(record)
        except Exception:
            pass

    def _record_item_activity(
        self,
        operation: ActivityOperation,
        result: ActivityResult,
        *,
        message: str,
        detail: TrackerItemDetail | None = None,
        item_id: int | None = None,
        item_name: str = "",
        parent_item_id: int | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        item_summary = detail.summary if detail is not None else None
        tracker = self._current_tracker
        project = self._current_project
        self._record_activity(
            ActivityRecord.create(
                operation,
                result,
                source="tracker_workspace",
                summary=message,
                project_id=(
                    item_summary.project_id
                    if item_summary is not None
                    else project.project_id if project is not None else None
                ),
                project_name=(
                    item_summary.project_name
                    if item_summary is not None
                    else project.name if project is not None else ""
                ),
                tracker_id=(
                    item_summary.tracker_id
                    if item_summary is not None
                    else tracker.tracker_id if tracker is not None else None
                ),
                tracker_name=(
                    item_summary.tracker_name
                    if item_summary is not None
                    else tracker.name if tracker is not None else ""
                ),
                item_id=(detail.item_id if detail is not None else item_id),
                item_name=(
                    item_summary.name if item_summary is not None else item_name
                ),
                parent_item_id=(
                    parent_item_id
                    if parent_item_id is not None
                    else detail.parent.item_id
                    if detail is not None and detail.parent is not None
                    else None
                ),
                details=details,
            )
        )

    def _next_token(self, key: str) -> int:
        token = self._request_tokens.get(key, 0) + 1
        self._request_tokens[key] = token
        return token

    def _is_current_token(self, key: str, token: int) -> bool:
        return self._request_tokens.get(key) == token

    def _invalidate_requests(self) -> None:
        for key in tuple(self._request_tokens):
            self._next_token(key)

    def _submit(
        self,
        key: str,
        operation: Callable[[], Any],
        on_success: Callable[[Any], None],
        on_failure: Callable[[Exception], None] | None = None,
    ) -> int:
        token = self._next_token(key)
        busy_token = self._start_request_busy(key)

        def success(result: Any) -> None:
            if self._is_current_token(key, token):
                on_success(result)

        def failure(exc: Exception) -> None:
            if not self._is_current_token(key, token):
                return
            if on_failure is not None:
                on_failure(exc)
            else:
                self._show_error(exc)

        if self.synchronous:
            try:
                success(operation())
            except Exception as exc:
                failure(exc)
            finally:
                self._finish_request_busy(busy_token)
            return token

        task = self.task_factory(operation)
        self._tasks.add(task)
        task.completed.connect(success)
        task.failed.connect(failure)

        def cleanup() -> None:
            self._tasks.discard(task)
            self._finish_request_busy(busy_token)
            task.deleteLater()

        task.finished.connect(cleanup)
        try:
            task.start()
        except Exception:
            self._tasks.discard(task)
            self._finish_request_busy(busy_token)
            task.deleteLater()
            raise
        return token

    def _start_request_busy(self, key: str) -> object | None:
        if not callable(self.busy_started):
            return None
        message = REQUEST_BUSY_MESSAGES.get(key)
        if message is None and key.startswith("children:"):
            item_id = key.partition(":")[2]
            message = f"#{item_id}의 하위 아이템을 불러오는 중입니다."
        if message is None:
            message = "Codebeamer 응답을 기다리는 중입니다."
        try:
            return self.busy_started(message)
        except Exception:
            return None

    def _finish_request_busy(self, token: object | None) -> None:
        if token is None or not callable(self.busy_finished):
            return
        try:
            self.busy_finished(token)
        except Exception:
            pass

    def _show_error(self, exc: Exception, *, prefix: str = "") -> None:
        if isinstance(exc, (TrackerQueryServiceError, TrackerItemWriteError)):
            message = str(exc)
        elif isinstance(exc, ValueError):
            message = str(exc)
        else:
            message = "조회 중 예상하지 못한 오류가 발생했습니다."
        if prefix:
            message = f"{prefix}: {message}"
        self._set_workspace_status(message, tone="error")

    def _load_projects(self, *, force: bool = False) -> None:
        del force
        settings = self.settings_provider()
        self.project_combo.setEnabled(False)
        self.tracker_combo.setEnabled(False)
        self.refresh_context_button.setEnabled(False)
        self._set_workspace_status("프로젝트를 불러오는 중입니다.", tone="loading")

        def loaded(projects: tuple[ProjectSummary, ...]) -> None:
            self.refresh_context_button.setEnabled(True)
            self._projects = tuple(projects)
            self.project_combo.blockSignals(True)
            self.project_combo.clear()
            for project in self._projects:
                self.project_combo.addItem(
                    f"{project.name}  ·  {project.project_id}", project.project_id
                )
            preferred_id = self._preferred_id(
                str(settings.default_project_id or ""),
                self._current_project.project_id if self._current_project else None,
            )
            index = self._combo_index_for_id(self.project_combo, preferred_id)
            if index < 0 and self.project_combo.count():
                index = 0
            self.project_combo.setCurrentIndex(index)
            self.project_combo.blockSignals(False)
            if index < 0:
                self._current_project = None
                self._trackers = ()
                self.tracker_combo.clear()
                self._set_available(True)
                self._set_workspace_status("조회 가능한 프로젝트가 없습니다.", tone="warning")
                self._reset_workspace("조회 가능한 프로젝트가 없습니다.")
                return
            self.project_combo.setEnabled(True)
            self._current_project = self._projects[index]
            self._set_workspace_status(
                f"{len(self._projects)}개 프로젝트를 불러왔습니다. 트래커를 조회합니다."
            )
            self._load_trackers(self._current_project)

        def failed(exc: Exception) -> None:
            self.refresh_context_button.setEnabled(True)
            self._set_available(True)
            self._show_error(exc, prefix="프로젝트 조회 실패")

        self._submit("projects", lambda: self.service.load_projects(settings), loaded, failed)

    @staticmethod
    def _preferred_id(primary: str, fallback: int | None) -> int | None:
        for value in (primary, fallback):
            try:
                normalized = int(value) if value not in (None, "") else None
            except (TypeError, ValueError):
                normalized = None
            if normalized is not None and normalized > 0:
                return normalized
        return None

    @staticmethod
    def _combo_index_for_id(combo: QComboBox, entity_id: int | None) -> int:
        if entity_id is None:
            return -1
        for index in range(combo.count()):
            try:
                if int(combo.itemData(index)) == int(entity_id):
                    return index
            except (TypeError, ValueError):
                continue
        return -1

    def _on_project_activated(self, index: int) -> None:
        if not (0 <= int(index) < len(self._projects)):
            return
        project = self._projects[int(index)]
        if self._current_project == project and self._trackers:
            return
        self._current_project = project
        self._current_tracker = None
        self._selected_item_id = None
        self._reset_detail()
        self._load_trackers(project)

    def _load_trackers(self, project: ProjectSummary) -> None:
        settings = self.settings_provider()
        project_id = project.project_id
        self.tracker_combo.setEnabled(False)
        self.reload_roots_button.setEnabled(False)
        self.search_button.setEnabled(False)
        self._set_workspace_status(
            f"'{project.name}' 프로젝트의 트래커를 불러오는 중입니다.",
            tone="loading",
        )

        def loaded(trackers: tuple[TrackerSummary, ...]) -> None:
            if self._current_project is None or self._current_project.project_id != project_id:
                return
            self._trackers = tuple(trackers)
            self.tracker_combo.blockSignals(True)
            self.tracker_combo.clear()
            for tracker in self._trackers:
                self.tracker_combo.addItem(
                    self._tracker_combo_text(tracker), tracker.tracker_id
                )
            preferred_id = self._preferred_id(
                str(settings.default_tracker_id or ""),
                self._current_tracker.tracker_id if self._current_tracker else None,
            )
            index = self._combo_index_for_id(self.tracker_combo, preferred_id)
            if index < 0 and self.tracker_combo.count():
                index = 0
            self.tracker_combo.setCurrentIndex(index)
            self.tracker_combo.blockSignals(False)
            if index < 0:
                self._current_tracker = None
                self._set_available(True)
                self._set_workspace_status(
                    f"'{project.name}' 프로젝트에 조회 가능한 트래커가 없습니다.",
                    tone="warning",
                )
                self._reset_workspace("조회 가능한 트래커가 없습니다.")
                return
            self._current_tracker = self._trackers[index]
            self._set_available(True)
            self._update_search_scope()
            self._set_workspace_status(
                f"'{self._current_tracker.name}' 트래커의 최상위 아이템을 조회합니다."
            )
            self._load_roots()

        def failed(exc: Exception) -> None:
            self._trackers = ()
            self.tracker_combo.clear()
            self._current_tracker = None
            self._set_available(True)
            self._show_error(exc, prefix="트래커 조회 실패")
            self._reset_workspace("트래커를 불러오지 못했습니다.")

        self._submit(
            "trackers",
            lambda: self.service.load_trackers(
                settings,
                project.project_id,
                project_name=project.name,
            ),
            loaded,
            failed,
        )

    def _on_tracker_activated(self, index: int) -> None:
        if not (0 <= int(index) < len(self._trackers)):
            return
        tracker = self._trackers[int(index)]
        if self._current_tracker == tracker:
            return
        self._current_tracker = tracker
        self._selected_item_id = None
        self._baseline_selected_item_id = None
        self._last_search_query = None
        self._last_search_result = None
        self._search_schema = None
        self.condition_builder.setEnabled(False)
        self._clear_search_selection()
        self.search_table.setRowCount(0)
        self.baseline_item_tree.clear()
        self.baseline_comparison_panel.set_error("Baseline 목록을 불러오는 중입니다.")
        self._reset_detail()
        self._update_search_scope()
        self._set_available(True)
        self._load_roots()
        if self.workspace_mode_tabs.currentIndex() == self.baseline_mode_index:
            self._refresh_baseline_comparison()

    def _update_search_scope(self) -> None:
        if self._current_tracker is None:
            self.search_scope_label.setText("프로젝트와 트래커를 먼저 선택하세요.")
            return
        self.search_scope_label.setText(
            f"검색 범위: {self._current_tracker.name} ({self._current_tracker.tracker_id}) · "
            "ID 바로 열기와 달리 이 트래커 밖의 아이템은 검색하지 않습니다."
        )

    @staticmethod
    def _tracker_combo_text(tracker: TrackerSummary) -> str:
        type_name = str(tracker.type_name or "").strip()
        suffix = ""
        if type_name and type_name.casefold() not in {
            "tracker",
            "trackerreference",
        }:
            suffix = f" · {type_name}"
        return f"{tracker.name}  ·  {tracker.tracker_id}{suffix}"

    def _load_roots(self, *, force: bool = False) -> None:
        tracker = self._current_tracker
        project = self._current_project
        if tracker is None:
            self._set_workspace_status("트래커를 먼저 선택하세요.", tone="warning")
            return
        cache_key = tracker.tracker_id
        if cache_key in self._root_cache and not force:
            self._render_roots(self._root_cache[cache_key])
            return
        if force:
            self._root_cache.pop(tracker.tracker_id, None)
            self._child_cache.clear()

        settings = self.settings_provider()
        tracker_id = tracker.tracker_id
        self.tree_status_label.setText("최상위 아이템을 불러오는 중입니다.")
        self.reload_roots_button.setEnabled(False)

        def loaded(items: tuple[TrackerItemSummary, ...]) -> None:
            if self._current_tracker is None or self._current_tracker.tracker_id != tracker_id:
                return
            self._root_cache[cache_key] = items
            self.reload_roots_button.setEnabled(True)
            self._render_roots(items)
            self._set_workspace_status(
                f"'{tracker.name}' 트래커의 계층을 조회할 수 있습니다."
            )

        def failed(exc: Exception) -> None:
            self.reload_roots_button.setEnabled(True)
            self.item_tree.clear()
            self.tree_status_label.setText("최상위 아이템을 불러오지 못했습니다.")
            self._show_error(exc, prefix="계층 조회 실패")

        self._submit(
            "roots",
            lambda: self.service.load_all_top_level_items(
                settings,
                tracker_id,
                tracker_name=tracker.name,
                project_id=project.project_id if project else tracker.project_id,
                project_name=project.name if project else tracker.project_name,
                page_size=HIERARCHY_FETCH_PAGE_SIZE,
            ),
            loaded,
            failed,
        )

    def _render_roots(self, items: tuple[TrackerItemSummary, ...]) -> None:
        self.item_tree.blockSignals(True)
        self.item_tree.clear()
        for summary in items:
            self.item_tree.addTopLevelItem(self._tree_item(summary))
        self.item_tree.blockSignals(False)
        if items:
            self.tree_status_label.setText(f"최상위 아이템 {len(items)}개 · 전체 표시")
        else:
            self.tree_status_label.setText("최상위 아이템이 없습니다.")
        self._render_baseline_roots(items)

    def _render_baseline_roots(self, items: tuple[TrackerItemSummary, ...]) -> None:
        self.baseline_item_tree.blockSignals(True)
        self.baseline_item_tree.clear()
        for summary in items:
            self.baseline_item_tree.addTopLevelItem(self._tree_item(summary))
        self.baseline_item_tree.blockSignals(False)
        self.baseline_tree_status_label.setText(
            f"현재 최상위 아이템 {len(items)}개" if items else "현재 최상위 아이템이 없습니다."
        )

    def _tree_item(self, summary: TrackerItemSummary) -> QTreeWidgetItem:
        item = QTreeWidgetItem(
            [
                str(summary.item_id),
                summary.name,
            ]
        )
        item.setData(0, ITEM_SUMMARY_ROLE, summary)
        children_known = summary.child_count is not None or any(
            key in summary.raw_reference for key in ("hasChildren", "leaf", "children")
        )
        children_may_exist = summary.has_children or not children_known
        item.setData(0, CHILDREN_LOADED_ROLE, not children_may_exist)
        if children_may_exist:
            item.addChild(self._placeholder_item("펼치면 직접 하위 아이템을 불러옵니다."))
        return item

    @staticmethod
    def _placeholder_item(text: str) -> QTreeWidgetItem:
        placeholder = QTreeWidgetItem(["", text])
        placeholder.setData(0, PLACEHOLDER_ROLE, True)
        placeholder.setDisabled(True)
        return placeholder

    def _on_tree_item_expanded(self, item: QTreeWidgetItem) -> None:
        summary = item.data(0, ITEM_SUMMARY_ROLE)
        if not isinstance(summary, TrackerItemSummary):
            return
        if bool(item.data(0, CHILDREN_LOADED_ROLE)):
            return
        cached = self._child_cache.get(summary.item_id)
        if cached is not None:
            self._replace_tree_children(item, cached)
            return

        tracker = self._current_tracker
        project = self._current_project
        if tracker is None:
            return
        tracker_id = tracker.tracker_id
        settings = self.settings_provider()
        item.takeChildren()
        item.addChild(self._placeholder_item("하위 아이템을 불러오는 중입니다."))

        def loaded(children: tuple[TrackerItemSummary, ...]) -> None:
            if self._current_tracker is None or self._current_tracker.tracker_id != tracker_id:
                return
            self._child_cache[summary.item_id] = children
            self._replace_tree_children(item, children)
            self._set_workspace_status(
                f"#{summary.item_id}의 직접 하위 아이템 {len(children)}개를 모두 불러왔습니다."
            )

        def failed(exc: Exception) -> None:
            item.takeChildren()
            item.addChild(self._placeholder_item("하위 조회 실패 · 접었다가 다시 펼쳐 재시도"))
            item.setData(0, CHILDREN_LOADED_ROLE, False)
            self._show_error(exc, prefix=f"#{summary.item_id} 하위 조회 실패")

        self._submit(
            f"children:{summary.item_id}",
            lambda: self.service.load_all_child_items(
                settings,
                summary.item_id,
                tracker_id=tracker_id,
                tracker_name=tracker.name,
                project_id=project.project_id if project else tracker.project_id,
                project_name=project.name if project else tracker.project_name,
                page_size=HIERARCHY_FETCH_PAGE_SIZE,
            ),
            loaded,
            failed,
        )

    def _on_baseline_tree_item_expanded(self, item: QTreeWidgetItem) -> None:
        summary = item.data(0, ITEM_SUMMARY_ROLE)
        if not isinstance(summary, TrackerItemSummary):
            return
        if bool(item.data(0, CHILDREN_LOADED_ROLE)):
            return
        cached = self._child_cache.get(summary.item_id)
        if cached is not None:
            self._replace_tree_children(item, cached)
            return
        tracker = self._current_tracker
        project = self._current_project
        if tracker is None:
            return
        tracker_id = tracker.tracker_id
        settings = self.settings_provider()
        item.takeChildren()
        item.addChild(self._placeholder_item("하위 아이템을 불러오는 중입니다."))

        def loaded(children: tuple[TrackerItemSummary, ...]) -> None:
            if self._current_tracker is None or self._current_tracker.tracker_id != tracker_id:
                return
            self._child_cache[summary.item_id] = children
            self._replace_tree_children(item, children)

        def failed(exc: Exception) -> None:
            item.takeChildren()
            item.addChild(self._placeholder_item("하위 조회 실패 · 다시 펼쳐 재시도"))
            item.setData(0, CHILDREN_LOADED_ROLE, False)
            self.baseline_comparison_panel.set_error(str(exc))

        self._submit(
            f"baseline_children:{summary.item_id}",
            lambda: self.service.load_all_child_items(
                settings,
                summary.item_id,
                tracker_id=tracker_id,
                tracker_name=tracker.name,
                project_id=project.project_id if project else tracker.project_id,
                project_name=project.name if project else tracker.project_name,
                page_size=HIERARCHY_FETCH_PAGE_SIZE,
            ),
            loaded,
            failed,
        )

    def _replace_tree_children(
        self,
        parent_item: QTreeWidgetItem,
        children: tuple[TrackerItemSummary, ...] | list[TrackerItemSummary],
    ) -> None:
        parent_item.takeChildren()
        for summary in children:
            parent_item.addChild(self._tree_item(summary))
        parent_item.setData(0, CHILDREN_LOADED_ROLE, True)

    def _on_tree_selection_changed(self) -> None:
        selected = self.item_tree.selectedItems()
        if not selected:
            return
        summary = selected[0].data(0, ITEM_SUMMARY_ROLE)
        if isinstance(summary, TrackerItemSummary):
            self._load_detail(summary.item_id)

    def _on_baseline_tree_selection_changed(self) -> None:
        selected = self.baseline_item_tree.selectedItems()
        if not selected:
            return
        summary = selected[0].data(0, ITEM_SUMMARY_ROLE)
        if not isinstance(summary, TrackerItemSummary):
            return
        self._baseline_selected_item_id = summary.item_id
        before, after = self.baseline_comparison_panel.sources()
        if before is not None and after is not None and before != after:
            self._run_baseline_comparison(before, after)
        else:
            self.baseline_comparison_panel.set_error(
                f"#{summary.item_id}을(를) 선택했습니다. 비교할 두 기준을 선택하세요."
            )

    def _on_search_selection_changed(self) -> None:
        selected = self.search_table.selectedItems()
        if not selected:
            return
        summary = self.search_table.item(selected[0].row(), 1).data(ITEM_SUMMARY_ROLE)
        if isinstance(summary, TrackerItemSummary):
            self._load_detail(summary.item_id)

    def _on_search_check_changed(self, item: QTableWidgetItem) -> None:
        if item.column() != 0:
            return
        id_item = self.search_table.item(item.row(), 1)
        summary = id_item.data(ITEM_SUMMARY_ROLE) if id_item is not None else None
        if not isinstance(summary, TrackerItemSummary):
            return
        checked = item.checkState() == Qt.CheckState.Checked
        if self._all_search_selected:
            if checked:
                self._excluded_search_ids.discard(summary.item_id)
            else:
                self._excluded_search_ids.add(summary.item_id)
        elif checked:
            self._selected_search_ids.add(summary.item_id)
        else:
            self._selected_search_ids.discard(summary.item_id)
        self._update_search_selection_ui()

    def _show_detail_id_badge(self, item_id: int) -> None:
        normalized_id = int(item_id)
        self.detail_id_badge.setText(f"#{normalized_id}")
        self.detail_id_badge.setToolTip(
            f"클릭하면 아이템 ID {normalized_id} 숫자만 복사합니다."
        )
        self.detail_id_badge.show()

    def _load_detail(self, item_id: int) -> None:
        normalized_id = int(item_id)
        self._selected_item_id = normalized_id
        settings = self.settings_provider()
        self.detail_title.setText("아이템 상세를 불러오는 중입니다.")
        self.detail_refresh_button.setEnabled(False)
        self._show_detail_id_badge(normalized_id)

        def loaded(detail: TrackerItemDetail) -> None:
            if self._selected_item_id != normalized_id:
                return
            self._render_detail(detail)

        def failed(exc: Exception) -> None:
            if self._selected_item_id != normalized_id:
                return
            self.detail_title.setText("아이템 상세")
            self.detail_refresh_button.setEnabled(True)
            self.detail_breadcrumb.setText(f"#{normalized_id} 상세를 불러오지 못했습니다.")
            self._show_error(exc, prefix="상세 조회 실패")

        self._submit(
            "detail",
            lambda: self.service.load_detail(settings, normalized_id),
            loaded,
            failed,
        )

    def _copy_selected_item_id(self) -> None:
        item_id = self._selected_item_id
        if item_id is None:
            return
        clipboard_text = str(int(item_id))
        QApplication.clipboard().setText(clipboard_text)
        self.detail_id_badge.setToolTip(f"ID {clipboard_text} 복사 완료")
        self._set_workspace_status(
            f"아이템 ID {clipboard_text}가 클립보드에 복사되었습니다."
        )

    def _reload_current_detail(self) -> None:
        if self._selected_item_id is not None:
            self._load_detail(self._selected_item_id)

    def _create_item(self) -> None:
        tracker = self._current_tracker
        if tracker is None:
            self._set_workspace_status("생성할 트래커를 먼저 선택하세요.", tone="warning")
            return
        settings = self.settings_provider()
        if bool(settings.offline_mode):
            self._set_workspace_status(
                "테스트 모드에서는 새 아이템을 생성할 수 없습니다.",
                tone="warning",
            )
            return

        tracker_id = tracker.tracker_id
        selected_detail = (
            self._current_detail
            if self._current_detail is not None
            and self._current_detail.summary.tracker_id == tracker_id
            else None
        )
        self._create_busy = True
        self._set_available(True)
        self._set_workspace_status(
            f"'{tracker.name}' 트래커의 생성 필드를 확인하는 중입니다.",
            tone="loading",
        )

        def schema_loaded(schema: EditableTrackerSchema) -> None:
            current_tracker = self._current_tracker
            if current_tracker is None or current_tracker.tracker_id != tracker_id:
                self._finish_create_busy()
                return
            try:
                request = (
                    self.create_request_provider(schema, current_tracker, selected_detail)
                    if self.create_request_provider is not None
                    else TrackerItemCreateDialog.request(
                        schema,
                        tracker_name=current_tracker.name,
                        selected_detail=selected_detail,
                        parent=self,
                    )
                )
            except Exception as exc:
                self._finish_create_busy()
                self._show_error(exc, prefix="생성 입력 준비 실패")
                return
            if request is None:
                self._finish_create_busy()
                self._set_workspace_status("새 아이템 생성을 취소했습니다.")
                return
            parent_detail = (
                selected_detail
                if selected_detail is not None
                and request.parent_item_id == selected_detail.item_id
                else None
            )
            requested_name = next(
                (
                    str(change.value or "").strip()
                    for change in request.changes
                    if change.field.tracker_item_field == "name"
                ),
                "",
            )
            self._set_workspace_status(
                f"'{current_tracker.name}' 트래커에 새 아이템을 생성하는 중입니다.",
                tone="loading",
            )

            def created(detail: TrackerItemDetail) -> None:
                self._finish_create_busy()
                self._record_item_activity(
                    ActivityOperation.TRACKER_CREATE,
                    ActivityResult.SUCCESS,
                    message=f"#{detail.item_id} 아이템을 생성했습니다.",
                    detail=detail,
                    parent_item_id=request.parent_item_id,
                    details={
                        "field_count": len(request.changes),
                        "position": (
                            "child" if request.parent_item_id is not None else "root"
                        ),
                    },
                )
                self._show_created_item(
                    detail,
                    parent_item_id=request.parent_item_id,
                    parent_detail=parent_detail,
                )

            def create_failed(exc: Exception) -> None:
                self._finish_create_busy()
                result = (
                    ActivityResult.PARTIAL
                    if isinstance(exc, TrackerItemWriteError)
                    and exc.operation in {
                        "create_item_response",
                        "load_created_detail",
                    }
                    else ActivityResult.FAILED
                )
                self._record_item_activity(
                    ActivityOperation.TRACKER_CREATE,
                    result,
                    message=(
                        "아이템 생성 결과를 확인해야 합니다."
                        if result == ActivityResult.PARTIAL
                        else "아이템 생성에 실패했습니다."
                    ),
                    item_name=requested_name,
                    parent_item_id=request.parent_item_id,
                    details={"error": str(exc)},
                )
                prefix = (
                    "생성 결과 확인 필요"
                    if isinstance(exc, TrackerItemWriteError)
                    and exc.operation in {
                        "create_item_response",
                        "load_created_detail",
                    }
                    else "아이템 생성 실패"
                )
                self._show_error(exc, prefix=prefix)

            self._submit(
                "item_create",
                lambda: self.editor_service.create_item(
                    settings,
                    tracker_id=tracker_id,
                    schema=schema,
                    changes=request.changes,
                    parent_item_id=request.parent_item_id,
                ),
                created,
                create_failed,
            )

        def schema_failed(exc: Exception) -> None:
            self._finish_create_busy()
            self._show_error(exc, prefix="생성 schema 조회 실패")

        self._submit(
            "create_schema",
            lambda: self.editor_service.load_create_schema(settings, tracker_id),
            schema_loaded,
            schema_failed,
        )

    def _finish_create_busy(self) -> None:
        self._create_busy = False
        available, _ = self._settings_available(self.settings_provider())
        self._set_available(available)

    def _find_tree_item(self, item_id: int) -> QTreeWidgetItem | None:
        def find_from(item: QTreeWidgetItem) -> QTreeWidgetItem | None:
            summary = item.data(0, ITEM_SUMMARY_ROLE)
            if isinstance(summary, TrackerItemSummary) and summary.item_id == int(item_id):
                return item
            for child_index in range(item.childCount()):
                found = find_from(item.child(child_index))
                if found is not None:
                    return found
            return None

        for top_index in range(self.item_tree.topLevelItemCount()):
            found = find_from(self.item_tree.topLevelItem(top_index))
            if found is not None:
                return found
        return None

    def _show_created_item(
        self,
        detail: TrackerItemDetail,
        *,
        parent_item_id: int | None,
        parent_detail: TrackerItemDetail | None,
    ) -> None:
        tracker_id = detail.summary.tracker_id
        if tracker_id is not None:
            self._invalidate_tracker_cache(tracker_id)

        self.item_tree.blockSignals(True)
        try:
            created_item = self._tree_item(detail.summary)
            if parent_item_id is None:
                self.item_tree.insertTopLevelItem(0, created_item)
            else:
                parent_item = self._find_tree_item(parent_item_id)
                if parent_item is None:
                    parent_summary = (
                        parent_detail.summary
                        if parent_detail is not None
                        else TrackerItemSummary(
                            item_id=int(parent_item_id),
                            name=(
                                detail.parent.name
                                if detail.parent is not None
                                else str(parent_item_id)
                            ),
                            tracker_id=detail.summary.tracker_id,
                            tracker_name=detail.summary.tracker_name,
                            project_id=detail.summary.project_id,
                            project_name=detail.summary.project_name,
                            has_children=True,
                        )
                    )
                    parent_item = self._tree_item(
                        replace(parent_summary, has_children=True)
                    )
                    parent_item.takeChildren()
                    parent_item.setData(0, CHILDREN_LOADED_ROLE, False)
                    self.item_tree.clear()
                    self.item_tree.addTopLevelItem(parent_item)
                parent_summary = parent_item.data(0, ITEM_SUMMARY_ROLE)
                if isinstance(parent_summary, TrackerItemSummary):
                    current_count = parent_summary.child_count or 0
                    parent_item.setData(
                        0,
                        ITEM_SUMMARY_ROLE,
                        replace(
                            parent_summary,
                            has_children=True,
                            child_count=max(current_count + 1, 1),
                        ),
                    )
                placeholder_index = next(
                    (
                        index
                        for index in range(parent_item.childCount())
                        if bool(parent_item.child(index).data(0, PLACEHOLDER_ROLE))
                    ),
                    -1,
                )
                if placeholder_index >= 0:
                    parent_item.insertChild(placeholder_index, created_item)
                else:
                    parent_item.addChild(created_item)
                parent_item.setExpanded(True)
            self.item_tree.clearSelection()
            self.item_tree.setCurrentItem(created_item)
            created_item.setSelected(True)
            self.item_tree.scrollToItem(created_item)
        finally:
            self.item_tree.blockSignals(False)

        self.browser_tabs.setCurrentIndex(0)
        self.detail_tabs.setCurrentIndex(0)
        self._selected_item_id = detail.item_id
        self._render_detail(detail)
        position_text = (
            "최상위"
            if parent_item_id is None
            else f"#{parent_item_id}의 하위"
        )
        self.tree_status_label.setText(
            f"새 아이템 #{detail.item_id} · {position_text} · 전체 목록은 다시 불러오기로 갱신"
        )
        self._set_workspace_status(
            f"#{detail.item_id} '{detail.summary.name}' 아이템을 생성했습니다."
        )

    def _run_search(self, *, page: int = 1, reuse: bool = False) -> None:
        tracker = self._current_tracker
        if tracker is None:
            self._set_workspace_status("검색할 트래커를 먼저 선택하세요.", tone="warning")
            return
        if reuse and self._last_search_query is not None:
            query = replace(self._last_search_query, page=max(int(page), 1))
        elif self.search_mode_combo.currentData() == TrackerSearchMode.CONDITIONS.value:
            if self._search_schema is None:
                self._load_search_schema(run_after=True)
                return
            try:
                groups = self.condition_builder.values()
                query = TrackerQuery(
                    tracker_id=tracker.tracker_id,
                    mode=TrackerSearchMode.CONDITIONS,
                    groups=groups,
                    page=max(int(page), 1),
                    page_size=DEFAULT_SEARCH_PAGE_SIZE,
                    sort="item.id ASC",
                )
                query.build_cbql()
            except Exception as exc:
                self._set_workspace_status(str(exc), tone="warning")
                return
        else:
            text = self.search_text_input.text().strip()
            status = self.search_status_input.text().strip()
            assignee = self.search_assignee_input.text().strip()
            if not any((text, status, assignee)):
                self._set_workspace_status(
                    "트래커 검색에는 ID/요약, 상태, 담당자 중 하나 이상을 입력하세요.",
                    tone="warning",
                )
                return
            query = TrackerQuery(
                tracker_id=tracker.tracker_id,
                mode=TrackerSearchMode.SIMPLE,
                text=text,
                status=status,
                assignee=assignee,
                page=max(int(page), 1),
                page_size=DEFAULT_SEARCH_PAGE_SIZE,
                sort="item.id ASC",
            )
        if not reuse:
            self._clear_search_selection()
        self._last_search_query = replace(query, page=1)
        tracker_id = tracker.tracker_id
        settings = self.settings_provider()
        self.search_button.setEnabled(False)
        self.search_scope_label.setText(
            f"{tracker.name} ({tracker_id}) 안에서 검색하는 중입니다."
        )

        def loaded(result: PageResult[TrackerItemSummary]) -> None:
            if self._current_tracker is None or self._current_tracker.tracker_id != tracker_id:
                return
            self.search_button.setEnabled(True)
            self.baseline_compare_button.setEnabled(True)
            self._render_search_results(result)
            self._set_workspace_status(
                f"현재 트래커에서 검색 결과 {result.total}개를 찾았습니다."
            )

        def failed(exc: Exception) -> None:
            self.search_button.setEnabled(True)
            self.baseline_compare_button.setEnabled(self._last_search_query is not None)
            self._update_search_scope()
            self._show_error(exc, prefix="트래커 검색 실패")

        self._submit("search", lambda: self.service.search(settings, query), loaded, failed)

    def _open_baseline_comparison(self) -> None:
        self.workspace_mode_tabs.setCurrentIndex(self.baseline_mode_index)
        self._refresh_baseline_comparison()

    def _on_workspace_mode_changed(self, index: int) -> None:
        if int(index) == self.baseline_mode_index:
            self._refresh_baseline_comparison()

    def _refresh_baseline_comparison(self) -> None:
        tracker = self._current_tracker
        if tracker is None:
            self.baseline_comparison_panel.set_error("비교할 트래커를 먼저 선택하세요.")
            return
        settings = self.settings_provider()

        def loaded(baselines: tuple[TrackerBaseline, ...]) -> None:
            if self._current_tracker is not None and self._current_tracker.tracker_id == tracker.tracker_id:
                self.baseline_comparison_panel.set_baselines(baselines)
                roots = self._root_cache.get(tracker.tracker_id)
                if roots is not None:
                    self._render_baseline_roots(roots)

        def failed(exc: Exception) -> None:
            self.baseline_comparison_panel.set_error(f"Baseline 목록 조회 실패: {exc}")

        self._submit(
            "baseline_list",
            lambda: self.service.load_tracker_baselines(settings, tracker.tracker_id),
            loaded,
            failed,
        )

    def _run_baseline_comparison(
        self,
        before_source: BaselineComparisonSource,
        after_source: BaselineComparisonSource,
    ) -> None:
        tracker = self._current_tracker
        if tracker is None:
            self.baseline_comparison_panel.set_error("비교할 트래커를 먼저 선택하세요.")
            return
        item_id = self._baseline_selected_item_id
        if item_id is None:
            self.baseline_comparison_panel.set_error("왼쪽 현재 계층에서 비교할 아이템을 선택하세요.")
            return
        settings = self.settings_provider()

        def loaded(result: BaselineComparisonResult) -> None:
            self.baseline_comparison_panel.set_result(result)

        def failed(exc: Exception) -> None:
            self.baseline_comparison_panel.set_error(str(exc))

        self._submit(
            "baseline_compare",
            lambda: self.service.compare_item_at_sources(
                settings,
                item_id,
                tracker.tracker_id,
                before_source=before_source,
                after_source=after_source,
            ),
            loaded,
            failed,
        )

    def _render_search_results(self, result: PageResult[TrackerItemSummary]) -> None:
        self.search_table.blockSignals(True)
        self.search_table.setRowCount(len(result.items))
        for row, summary in enumerate(result.items):
            check_item = QTableWidgetItem("")
            check_item.setFlags(
                Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsUserCheckable
            )
            selected = (
                summary.item_id not in self._excluded_search_ids
                if self._all_search_selected
                else summary.item_id in self._selected_search_ids
            )
            check_item.setCheckState(
                Qt.CheckState.Checked if selected else Qt.CheckState.Unchecked
            )
            self.search_table.setItem(row, 0, check_item)
            values = (
                str(summary.item_id),
                summary.name,
                summary.status or "-",
                ", ".join(summary.assignees) or "-",
            )
            for column, value in enumerate(values, start=1):
                cell = QTableWidgetItem(value)
                if column == 1:
                    cell.setData(ITEM_SUMMARY_ROLE, summary)
                self.search_table.setItem(row, column, cell)
        self.search_table.blockSignals(False)
        self._last_search_result = result
        self._search_page = result.page
        visible_end = min(result.page * result.page_size, result.total)
        visible_start = 0 if not result.items else ((result.page - 1) * result.page_size) + 1
        self.search_scope_label.setText(
            f"검색 범위: {self._current_tracker.name} ({self._current_tracker.tracker_id}) · "
            f"{result.total}개 중 {visible_start}–{visible_end}개"
        )
        self.search_page_label.setText(f"{result.page} 페이지")
        pagination_available = result.server_honored_pagination
        self.search_previous_button.setEnabled(pagination_available and result.has_previous)
        self.search_next_button.setEnabled(pagination_available and result.has_next)
        self._update_search_selection_ui()

    def _on_search_mode_changed(self, *args) -> None:
        del args
        condition_mode = (
            self.search_mode_combo.currentData() == TrackerSearchMode.CONDITIONS.value
        )
        self.simple_search_host.setVisible(not condition_mode)
        self.condition_builder.setVisible(condition_mode)
        self._last_search_query = None
        self._last_search_result = None
        self.search_table.setRowCount(0)
        self._clear_search_selection()
        if condition_mode and self._current_tracker is not None:
            self._load_search_schema()

    def _load_search_schema(self, *, run_after: bool = False) -> None:
        tracker = self._current_tracker
        if tracker is None:
            return
        if self._search_schema is not None and self._search_schema.tracker_id == tracker.tracker_id:
            if run_after:
                self._run_search()
            return
        tracker_id = tracker.tracker_id
        settings = self.settings_provider()

        def loaded(schema: EditableTrackerSchema) -> None:
            if self._current_tracker is None or self._current_tracker.tracker_id != tracker_id:
                return
            self._search_schema = schema
            self.condition_builder.set_schema(schema)
            if run_after:
                self._run_search()

        def failed(exc: Exception) -> None:
            self._show_error(exc, prefix="검색 schema 조회 실패")

        self._submit(
            "search_schema",
            lambda: self.editor_service.load_create_schema(settings, tracker_id),
            loaded,
            failed,
        )

    def _selected_search_count(self) -> int:
        if self._all_search_selected and self._last_search_result is not None:
            return max(self._last_search_result.total - len(self._excluded_search_ids), 0)
        return len(self._selected_search_ids)

    def _update_search_selection_ui(self) -> None:
        count = self._selected_search_count()
        suffix = " · 검색 결과 전체 기준" if self._all_search_selected else ""
        self.search_selection_label.setText(f"선택 {count:,}개{suffix}")
        has_result = self._last_search_result is not None and bool(
            self._last_search_result.items
        )
        self.select_page_button.setEnabled(has_result)
        self.select_all_results_button.setEnabled(has_result)
        self.clear_search_selection_button.setEnabled(count > 0)
        settings = self.settings_provider()
        self.bulk_update_button.setEnabled(
            count > 0
            and self._current_tracker is not None
            and not bool(settings.offline_mode)
        )

    def _select_current_search_page(self) -> None:
        result = self._last_search_result
        if result is None:
            return
        if self._all_search_selected:
            self._excluded_search_ids.difference_update(
                summary.item_id for summary in result.items
            )
        else:
            self._selected_search_ids.update(summary.item_id for summary in result.items)
        self._render_search_results(result)

    def _select_all_search_results(self) -> None:
        if self._last_search_result is None:
            return
        self._all_search_selected = True
        self._selected_search_ids.clear()
        self._excluded_search_ids.clear()
        self._render_search_results(self._last_search_result)

    def _clear_search_selection(self) -> None:
        self._selected_search_ids.clear()
        self._all_search_selected = False
        self._excluded_search_ids.clear()
        if hasattr(self, "search_table"):
            self.search_table.blockSignals(True)
            for row in range(self.search_table.rowCount()):
                item = self.search_table.item(row, 0)
                if item is not None:
                    item.setCheckState(Qt.CheckState.Unchecked)
            self.search_table.blockSignals(False)
        if hasattr(self, "search_selection_label"):
            self._update_search_selection_ui()

    def _start_bulk_update(self) -> None:
        if self._selected_search_count() <= 0:
            return
        if self._all_search_selected:
            query = self._last_search_query
            if query is None:
                return
            settings = self.settings_provider()
            exclusions = set(self._excluded_search_ids)

            def loaded(items: tuple[TrackerItemSummary, ...]) -> None:
                item_ids = tuple(
                    item.item_id for item in items if item.item_id not in exclusions
                )
                self._prepare_bulk_update(item_ids)

            self._submit(
                "search_all",
                lambda: self.service.load_all_search_items(settings, query),
                loaded,
                lambda exc: self._show_error(exc, prefix="전체 검색 결과 조회 실패"),
            )
            return
        self._prepare_bulk_update(tuple(sorted(self._selected_search_ids)))

    def _prepare_bulk_update(
        self,
        item_ids: tuple[int, ...],
        *,
        initial_field_ids: tuple[int, ...] = (),
        initial_clear_field_ids: tuple[int, ...] = (),
        initial_atomic: bool = True,
        initial_chunk_size: int | None = None,
    ) -> None:
        tracker = self._current_tracker
        if tracker is None or not item_ids:
            return
        settings = self.settings_provider()
        if bool(settings.offline_mode):
            self._set_workspace_status(
                "테스트 모드에서는 일괄 수정할 수 없습니다.", tone="warning"
            )
            return
        tracker_id = tracker.tracker_id

        def loaded(schema: EditableTrackerSchema) -> None:
            if self._current_tracker is None or self._current_tracker.tracker_id != tracker_id:
                return
            kwargs = {
                "tracker_name": tracker.name,
                "target_count": len(item_ids),
                "initial_chunk_size": (
                    initial_chunk_size
                    if initial_chunk_size is not None
                    else int(getattr(settings, "bulk_update_chunk_size", 1000) or 1000)
                ),
                "initial_field_ids": initial_field_ids,
                "initial_clear_field_ids": initial_clear_field_ids,
                "initial_atomic": initial_atomic,
                "parent": self,
            }
            request = (
                self.bulk_request_provider(schema, **kwargs)
                if self.bulk_request_provider is not None
                else TrackerBulkUpdateDialog.request(schema, **kwargs)
            )
            if request is None:
                return
            if callable(self.bulk_chunk_size_saver):
                self.bulk_chunk_size_saver(request.chunk_size)
            self._execute_bulk_update(item_ids, schema, request)

        self._submit(
            "editor_schema",
            lambda: self.editor_service.load_create_schema(settings, tracker_id),
            loaded,
            lambda exc: self._show_error(exc, prefix="일괄 수정 schema 조회 실패"),
        )

    def _execute_bulk_update(
        self,
        item_ids: tuple[int, ...],
        schema: EditableTrackerSchema,
        request: BulkUpdateRequest,
    ) -> None:
        tracker = self._current_tracker
        if tracker is None:
            return
        settings = self.settings_provider()
        progress = BulkUpdateProgressDialog(len(item_ids), self)
        worker = BulkUpdateWorker(
            self.bulk_update_service,
            settings,
            tracker_id=tracker.tracker_id,
            item_ids=item_ids,
            schema=schema,
            changes=request.changes,
            atomic=request.atomic,
            chunk_size=request.chunk_size,
        )
        self._bulk_progress_dialog = progress
        self._bulk_worker = worker
        progress.cancel_button.clicked.connect(worker.request_cancel)
        progress.cancel_button.clicked.connect(
            lambda _checked=False: progress.cancel_button.setEnabled(False)
        )
        worker.progress_changed.connect(progress.update_event)
        worker.completed.connect(self._finish_bulk_update)
        worker.failed.connect(self._fail_bulk_update)
        worker.finished.connect(self._cleanup_bulk_worker)
        progress.show()
        worker.start()

    def _finish_bulk_update(self, result) -> None:
        progress = self._bulk_progress_dialog
        if progress is not None:
            progress.accept()
        self._bulk_progress_dialog = None
        if self.bulk_run_store is not None:
            self.bulk_run_store.append(result)
        success_count = len(result.successful_item_ids)
        retry_count = len(result.retry_item_ids)
        if result.cancelled:
            activity_result = ActivityResult.CANCELLED
        elif retry_count and success_count:
            activity_result = ActivityResult.PARTIAL
        elif retry_count:
            activity_result = ActivityResult.FAILED
        else:
            activity_result = ActivityResult.SUCCESS
        tracker = self._current_tracker
        project = self._current_project
        if callable(self.activity_recorder):
            self.activity_recorder(
                ActivityRecord.create(
                    ActivityOperation.BULK_UPDATE,
                    activity_result,
                    source="tracker_workspace",
                    summary=(
                        f"일괄 수정 성공 {success_count:,}건, 재시도 대상 {retry_count:,}건"
                    ),
                    project_id=project.project_id if project else None,
                    project_name=project.name if project else "",
                    tracker_id=tracker.tracker_id if tracker else result.tracker_id,
                    tracker_name=tracker.name if tracker else "",
                    details={
                        "run_id": result.run_id,
                        "target_count": len(result.target_item_ids),
                        "success_count": success_count,
                        "failed_count": len(result.failed_item_ids),
                        "rolled_back_count": len(result.rolled_back_item_ids),
                        "unattempted_count": len(result.unattempted_item_ids),
                        "atomic": result.atomic,
                        "chunk_size": result.chunk_size,
                    },
                )
            )
        self._set_workspace_status(
            f"일괄 수정 완료: 성공 {success_count:,}건, 재시도 대상 {retry_count:,}건.",
            tone="warning" if retry_count else "info",
        )
        self._clear_search_selection()

    def _fail_bulk_update(self, exc: Exception) -> None:
        if self._bulk_progress_dialog is not None:
            self._bulk_progress_dialog.reject()
        self._bulk_progress_dialog = None
        self._show_error(exc, prefix="일괄 수정 실패")

    def _cleanup_bulk_worker(self) -> None:
        worker = self._bulk_worker
        self._bulk_worker = None
        if worker is not None:
            worker.deleteLater()

    def open_bulk_retry(self, run_id: str) -> None:
        if self.bulk_run_store is None:
            return
        record = self.bulk_run_store.get(run_id)
        if record is None:
            self._set_workspace_status("재시도 실행 기록을 찾지 못했습니다.", tone="warning")
            return
        if self._current_tracker is None or self._current_tracker.tracker_id != record.tracker_id:
            self._set_workspace_status(
                f"트래커 {record.tracker_id}을 선택한 뒤 재시도하세요.", tone="warning"
            )
            return
        if not record.retry_item_ids:
            self._set_workspace_status("이 실행 기록에는 재시도 대상이 없습니다.")
            return
        self._prepare_bulk_update(
            record.retry_item_ids,
            initial_field_ids=record.field_ids,
            initial_clear_field_ids=record.clear_field_ids,
            initial_atomic=record.atomic,
            initial_chunk_size=record.chunk_size,
        )

    def _open_direct_item(self) -> None:
        raw_id = self.direct_id_input.text().strip()
        try:
            item_id = int(raw_id)
        except (TypeError, ValueError):
            item_id = 0
        if item_id <= 0:
            self._set_workspace_status("ID 바로 열기에는 양의 정수 아이템 ID가 필요합니다.", tone="warning")
            return
        settings = self.settings_provider()
        self.direct_open_button.setEnabled(False)
        self._set_workspace_status(
            f"#{item_id}의 프로젝트, 트래커와 계층 경로를 확인하는 중입니다.",
            tone="loading",
        )

        def resolve() -> _DirectItemResult:
            context = self.service.resolve_item_context(settings, item_id)
            path = self.service.load_ancestor_path(settings, item_id)
            return _DirectItemResult(context=context, ancestor_path=path)

        def loaded(result: _DirectItemResult) -> None:
            self.direct_open_button.setEnabled(True)
            self._apply_direct_item_result(result)

        def failed(exc: Exception) -> None:
            self.direct_open_button.setEnabled(True)
            self._show_error(exc, prefix="ID 바로 열기 실패")

        self._submit("direct", resolve, loaded, failed)

    def _apply_direct_item_result(self, result: _DirectItemResult) -> None:
        context = result.context
        project = self._project_for_context(context)
        tracker = self._tracker_for_context(context, project)
        if project is not None:
            self._ensure_project_option(project)
        self._ensure_tracker_option(tracker)
        self._current_project = project
        self._current_tracker = tracker
        self.project_combo.setCurrentIndex(
            -1
            if project is None
            else self._combo_index_for_id(self.project_combo, project.project_id)
        )
        self.tracker_combo.setCurrentIndex(
            self._combo_index_for_id(self.tracker_combo, tracker.tracker_id)
        )
        self._update_search_scope()
        self._set_available(True)
        self.browser_tabs.setCurrentIndex(0)
        self._render_ancestor_path(result.ancestor_path)
        self._selected_item_id = context.item.item_id
        self._render_detail(context.item)
        self._set_workspace_status(
            f"#{context.item.item_id}을(를) 직접 열고 소속 트래커와 조상 경로를 표시했습니다."
        )

    @staticmethod
    def _project_for_context(context: TrackerItemContext) -> ProjectSummary | None:
        project_id = context.project_id or context.item.summary.project_id
        if project_id is None:
            return None
        return ProjectSummary(
            project_id=int(project_id),
            name=context.project_name or context.item.summary.project_name or "프로젝트 정보 없음",
        )

    @staticmethod
    def _tracker_for_context(
        context: TrackerItemContext,
        project: ProjectSummary | None,
    ) -> TrackerSummary:
        return TrackerSummary(
            tracker_id=context.tracker_id,
            name=context.tracker_name or context.item.summary.tracker_name or str(context.tracker_id),
            project_id=project.project_id if project else context.project_id,
            project_name=project.name if project else context.project_name,
        )

    def _ensure_project_option(self, project: ProjectSummary) -> None:
        projects = list(self._projects)
        for index, existing in enumerate(projects):
            if existing.project_id == project.project_id:
                projects[index] = project
                break
        else:
            projects.append(project)
        self._projects = tuple(projects)
        self.project_combo.blockSignals(True)
        self.project_combo.clear()
        for value in self._projects:
            self.project_combo.addItem(f"{value.name}  ·  {value.project_id}", value.project_id)
        self.project_combo.blockSignals(False)

    def _ensure_tracker_option(self, tracker: TrackerSummary) -> None:
        trackers = [
            existing
            for existing in self._trackers
            if existing.project_id in (None, tracker.project_id)
        ]
        for index, existing in enumerate(trackers):
            if existing.tracker_id == tracker.tracker_id:
                trackers[index] = tracker
                break
        else:
            trackers.append(tracker)
        self._trackers = tuple(trackers)
        self.tracker_combo.blockSignals(True)
        self.tracker_combo.clear()
        for value in self._trackers:
            self.tracker_combo.addItem(self._tracker_combo_text(value), value.tracker_id)
        self.tracker_combo.blockSignals(False)

    def _render_ancestor_path(self, path: tuple[TrackerItemSummary, ...]) -> None:
        self.item_tree.blockSignals(True)
        self.item_tree.clear()
        parent_item: QTreeWidgetItem | None = None
        target_item: QTreeWidgetItem | None = None
        for summary in path:
            tree_item = self._tree_item(summary)
            tree_item.takeChildren()
            tree_item.setData(0, CHILDREN_LOADED_ROLE, True)
            if parent_item is None:
                self.item_tree.addTopLevelItem(tree_item)
            else:
                parent_item.addChild(tree_item)
                parent_item.setExpanded(True)
            parent_item = tree_item
            target_item = tree_item
        if target_item is not None:
            target_item.setSelected(True)
            self.item_tree.scrollToItem(target_item)
        self.item_tree.blockSignals(False)
        self.tree_status_label.setText(
            f"ID 직접 접근 경로 · {len(path)}단계 · 전체 형제 노드는 '최상위 다시 불러오기'로 조회"
        )

    def _render_description(self, show_source: bool = False) -> None:
        self.description_source_toggle.setText(
            "렌더링 보기" if show_source else "Wiki 원문"
        )
        if self._description_uses_wiki and not show_source:
            self.detail_description.setHtml(
                codebeamer_wiki_to_html(self._description_text)
            )
            return
        self.detail_description.setPlainText(self._description_text)

    def _open_table_field(self, field: TrackerFieldValue) -> None:
        dialog = TrackerTableFieldDialog(field, self)
        dialog.exec()

    def _render_detail(self, detail: TrackerItemDetail) -> None:
        summary = detail.summary
        previous_editor_detail = self.editor_panel.detail
        self._current_detail = detail
        self._selected_item_id = detail.item_id
        self._update_detached_editor_title(detail)
        self.detail_title.setText(summary.name)
        self.detail_refresh_button.setEnabled(True)
        self._show_detail_id_badge(detail.item_id)
        breadcrumb_parts = [
            summary.project_name or "프로젝트 정보 없음",
            summary.tracker_name or "트래커 정보 없음",
        ]
        if detail.parent is not None:
            breadcrumb_parts.append(f"상위 #{detail.parent.item_id}")
        self.detail_breadcrumb.setText("  ›  ".join(breadcrumb_parts))
        warnings = "\n".join(detail.warnings)
        self.detail_warning.setText(warnings)
        self.detail_warning.setVisible(bool(warnings))
        self._description_text = detail.description
        self._description_uses_wiki = is_explicit_wiki_type(detail.description_format)
        self.description_source_toggle.blockSignals(True)
        self.description_source_toggle.setChecked(False)
        self.description_source_toggle.blockSignals(False)
        self.description_source_toggle.setVisible(self._description_uses_wiki)
        self._render_description(False)
        self.detail_raw_json.setPlainText(
            json.dumps(detail.raw_payload, ensure_ascii=False, indent=2, default=str)
        )

        rows: list[tuple[str, str, str]] = [
            ("ID", str(detail.item_id), "builtin"),
            ("프로젝트", summary.project_name or "-", "reference"),
            ("트래커", summary.tracker_name or "-", "reference"),
            ("상태", summary.status or "-", "reference"),
            ("담당자", ", ".join(summary.assignees) or "-", "reference"),
            ("버전", str(detail.version) if detail.version is not None else "-", "builtin"),
            ("수정 시각", summary.modified_at or "-", "builtin"),
            (
                "상위 아이템",
                (
                    f"#{detail.parent.item_id} {detail.parent.name}"
                    if detail.parent is not None
                    else "-"
                ),
                "reference",
            ),
            ("직접 하위", str(len(detail.children)), "reference"),
        ]
        self.detail_fields_table.clearContents()
        self.detail_fields_table.setRowCount(len(rows) + len(detail.custom_fields))
        for row, values in enumerate(rows):
            for column, value in enumerate(values):
                self.detail_fields_table.setItem(row, column, QTableWidgetItem(value))
        field_row_offset = len(rows)
        for field_index, field in enumerate(detail.custom_fields):
            row = field_row_offset + field_index
            self.detail_fields_table.setItem(row, 0, QTableWidgetItem(field.name))
            self.detail_fields_table.setItem(row, 2, QTableWidgetItem(field.type_name))
            if is_table_field(field):
                summary = table_field_summary(field)
                value_item = QTableWidgetItem(summary)
                value_item.setToolTip(f"{field.name}의 행·열 데이터를 엽니다.")
                self.detail_fields_table.setItem(row, 1, value_item)
                open_button = QPushButton(f"{summary} · 열어보기", self.detail_fields_table)
                open_button.clicked.connect(
                    lambda _checked=False, selected=field: self._open_table_field(selected)
                )
                self.detail_fields_table.setCellWidget(row, 1, open_button)
                continue
            text = field.display_value or "-"
            value_item = QTableWidgetItem(text)
            value_item.setToolTip(text)
            self.detail_fields_table.setItem(row, 1, value_item)
            if not (
                is_explicit_wiki_type(field.type_name)
                or payload_uses_wiki(field.raw_value)
            ):
                continue
            label = QLabel(self.detail_fields_table)
            label.setObjectName("tracker_wiki_cell")
            label.setTextFormat(Qt.TextFormat.RichText)
            label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            label.setWordWrap(True)
            label.setMargin(6)
            label.setMinimumHeight(32)
            label.setText(codebeamer_wiki_to_html(text))
            value_item.setText("")
            self.detail_fields_table.setCellWidget(row, 1, label)
            self.detail_fields_table.setRowHeight(
                row,
                max(self.detail_fields_table.rowHeight(row), 36),
            )
        self.detail_fields_table.resizeRowsToContents()
        if (
            previous_editor_detail is None
            or previous_editor_detail.item_id != detail.item_id
            or previous_editor_detail.version != detail.version
        ):
            self.editor_panel.clear()
        if self.detail_tabs.currentIndex() == self.editor_tab_index:
            self._load_editor_schema(detail)

    def _reset_detail(self) -> None:
        self._current_detail = None
        self._description_text = ""
        self._description_uses_wiki = False
        self.description_source_toggle.blockSignals(True)
        self.description_source_toggle.setChecked(False)
        self.description_source_toggle.blockSignals(False)
        self.description_source_toggle.setVisible(False)
        self.detail_title.setText("아이템 상세")
        self.detail_refresh_button.setEnabled(False)
        self.detail_id_badge.hide()
        self.detail_breadcrumb.setText("계층 또는 검색 결과에서 아이템을 선택하세요.")
        self.detail_warning.clear()
        self.detail_warning.hide()
        self.detail_description.clear()
        self.detail_fields_table.setRowCount(0)
        self.detail_raw_json.clear()
        self.editor_panel.clear()
        self._update_detached_editor_title(None)

    def _update_detached_editor_title(
        self,
        detail: TrackerItemDetail | None,
    ) -> None:
        dialog = self._editor_dialog
        if dialog is None:
            return
        title = (
            f"#{detail.item_id} {detail.summary.name} · 수정"
            if detail is not None
            else "트래커 아이템 수정"
        )
        dialog.setWindowTitle(title)
        dialog.title_label.setText(title)

    def _show_editor_in_window(self) -> None:
        dialog = self._editor_dialog
        if dialog is not None:
            dialog.show()
            dialog.raise_()
            dialog.activateWindow()
            return

        detail = self._current_detail
        title = (
            f"#{detail.item_id} {detail.summary.name} · 수정"
            if detail is not None
            else "트래커 아이템 수정"
        )
        self.editor_host_layout.removeWidget(self.editor_panel)
        self.editor_placeholder.show()
        self.popout_editor_button.setText("열린 수정 창 보기")
        dialog = TrackerItemEditorDialog(
            self.editor_panel,
            title=title,
            parent=self,
        )
        self._editor_dialog = dialog
        dialog.finished.connect(self._restore_editor_panel)
        dialog.show()

    def _restore_editor_panel(self, *args) -> None:
        del args
        dialog = self._editor_dialog
        if dialog is None:
            return
        try:
            dialog.finished.disconnect(self._restore_editor_panel)
        except (RuntimeError, TypeError):
            pass
        panel = dialog.take_panel()
        if panel is not None:
            panel.setParent(self.editor_host)
            self.editor_host_layout.addWidget(panel, 1)
            panel.show()
        self.editor_placeholder.hide()
        self.popout_editor_button.setText("새 창에서 크게 수정")
        self._editor_dialog = None
        dialog.deleteLater()

    def _on_detail_tab_changed(self, index: int) -> None:
        if int(index) != self.editor_tab_index:
            if self._pre_editor_splitter_sizes is not None:
                self.workspace_splitter.setSizes(self._pre_editor_splitter_sizes)
                self._pre_editor_splitter_sizes = None
            return
        if self._pre_editor_splitter_sizes is None:
            self._pre_editor_splitter_sizes = self.workspace_splitter.sizes()
        available_width = sum(self.workspace_splitter.sizes())
        if available_width > 0:
            browser_width = max(300, int(available_width * 0.38))
            detail_width = max(300, available_width - browser_width)
            self.workspace_splitter.setSizes([browser_width, detail_width])
        if self._current_detail is None:
            return
        editor_detail = self.editor_panel.detail
        if (
            editor_detail is not None
            and editor_detail.item_id == self._current_detail.item_id
            and editor_detail.version == self._current_detail.version
        ):
            return
        self._load_editor_schema(self._current_detail)

    def _load_editor_schema(self, detail: TrackerItemDetail) -> None:
        item_id = detail.item_id
        version = detail.version
        settings = self.settings_provider()
        self.editor_panel.set_loading("트래커 schema와 편집 가능한 필드를 확인하는 중입니다.")

        def loaded(schema) -> None:
            current = self._current_detail
            if current is None or current.item_id != item_id or current.version != version:
                return
            self.editor_panel.set_context(
                current,
                schema,
                write_enabled=not bool(settings.offline_mode),
            )

        def failed(exc: Exception) -> None:
            current = self._current_detail
            if current is None or current.item_id != item_id:
                return
            self.editor_panel.set_error(str(exc) or "편집 필드를 불러오지 못했습니다.")
            self._show_error(exc, prefix="편집 schema 조회 실패")

        self._submit(
            "editor_schema",
            lambda: self.editor_service.load_schema(settings, detail),
            loaded,
            failed,
        )

    def _save_item_changes(
        self,
        changes: tuple[TrackerItemFieldChange, ...],
    ) -> None:
        detail = self._current_detail
        if detail is None:
            return
        settings = self.settings_provider()
        item_id = detail.item_id
        self.editor_panel.set_busy(True)
        self.editor_panel.editor_status.setText(
            f"#{item_id}의 선택한 필드 {len(changes)}개를 저장하는 중입니다."
        )

        def loaded(updated_detail: TrackerItemDetail) -> None:
            self._record_item_activity(
                ActivityOperation.TRACKER_UPDATE,
                ActivityResult.SUCCESS,
                message=f"#{item_id}의 필드 {len(changes)}개를 저장했습니다.",
                detail=updated_detail,
                details={
                    "changed_fields": [change.field.label for change in changes],
                    "previous_version": detail.version,
                    "new_version": updated_detail.version,
                },
            )
            self._refresh_visible_item(updated_detail)
            self._render_detail(updated_detail)
            self._set_workspace_status(
                f"#{item_id}의 필드 {len(changes)}개를 저장했습니다."
            )

        def failed(exc: Exception) -> None:
            self._record_item_activity(
                ActivityOperation.TRACKER_UPDATE,
                ActivityResult.FAILED,
                message=f"#{item_id} 필드 저장에 실패했습니다.",
                detail=detail,
                details={
                    "changed_fields": [change.field.label for change in changes],
                    "error": str(exc),
                },
            )
            self.editor_panel.set_busy(False)
            self.editor_panel.set_error(str(exc) or "필드 저장에 실패했습니다.")
            self._show_error(exc, prefix="필드 저장 실패")

        self._submit(
            "item_write",
            lambda: self.editor_service.update_fields(
                settings,
                item_id=item_id,
                expected_version=detail.version,
                changes=changes,
            ),
            loaded,
            failed,
        )

    def _transition_item_status(
        self,
        status_field: EditableTrackerField,
        option_id: int,
    ) -> None:
        detail = self._current_detail
        if detail is None:
            return
        settings = self.settings_provider()
        item_id = detail.item_id
        target_option = next(
            (option for option in status_field.options if option.option_id == int(option_id)),
            None,
        )
        target_name = target_option.name if target_option is not None else str(option_id)
        self.editor_panel.set_busy(True)
        self.editor_panel.editor_status.setText(
            f"#{item_id} 상태를 '{target_name}'(으)로 전환하는 중입니다."
        )

        def loaded(updated_detail: TrackerItemDetail) -> None:
            self._record_item_activity(
                ActivityOperation.STATUS_TRANSITION,
                ActivityResult.SUCCESS,
                message=(
                    f"#{item_id} 상태를 "
                    f"'{updated_detail.summary.status or target_name}'(으)로 전환했습니다."
                ),
                detail=updated_detail,
                details={
                    "from_status": detail.summary.status,
                    "to_status": updated_detail.summary.status or target_name,
                    "previous_version": detail.version,
                    "new_version": updated_detail.version,
                },
            )
            self._refresh_visible_item(updated_detail)
            self._render_detail(updated_detail)
            self._set_workspace_status(
                f"#{item_id} 상태를 '{updated_detail.summary.status or target_name}'(으)로 전환했습니다."
            )

        def failed(exc: Exception) -> None:
            self._record_item_activity(
                ActivityOperation.STATUS_TRANSITION,
                ActivityResult.FAILED,
                message=f"#{item_id} 상태 전환에 실패했습니다.",
                detail=detail,
                details={
                    "from_status": detail.summary.status,
                    "to_status": target_name,
                    "error": str(exc),
                },
            )
            self.editor_panel.set_busy(False)
            self.editor_panel.set_error(str(exc) or "상태 전환에 실패했습니다.")
            self._show_error(exc, prefix="상태 전환 실패")

        self._submit(
            "item_write",
            lambda: self.editor_service.transition_status(
                settings,
                item_id=item_id,
                expected_version=detail.version,
                status_field=status_field,
                option_id=int(option_id),
            ),
            loaded,
            failed,
        )

    def _delete_current_item(self) -> None:
        detail = self._current_detail
        if detail is None:
            return
        confirmer = self.delete_confirmer
        confirmed = (
            bool(confirmer(detail))
            if confirmer is not None
            else ConfirmItemDeleteDialog.confirm(detail, self)
        )
        if not confirmed:
            return
        settings = self.settings_provider()
        item_id = detail.item_id
        tracker_id = detail.summary.tracker_id
        self.editor_panel.set_busy(True)
        self.editor_panel.editor_status.setText(f"#{item_id}을(를) 삭제하는 중입니다.")

        def loaded(result: Any) -> None:
            del result
            self._record_item_activity(
                ActivityOperation.TRACKER_DELETE,
                ActivityResult.SUCCESS,
                message=f"#{item_id} 아이템을 삭제했습니다.",
                detail=detail,
                details={"deleted_version": detail.version},
            )
            self._remove_visible_item(item_id)
            if tracker_id is not None:
                self._invalidate_tracker_cache(int(tracker_id))
            self._selected_item_id = None
            self._reset_detail()
            self._set_workspace_status(f"#{item_id}을(를) 삭제했습니다.")

        def failed(exc: Exception) -> None:
            self._record_item_activity(
                ActivityOperation.TRACKER_DELETE,
                ActivityResult.FAILED,
                message=f"#{item_id} 아이템 삭제에 실패했습니다.",
                detail=detail,
                details={"error": str(exc)},
            )
            self.editor_panel.set_busy(False)
            self.editor_panel.set_error(str(exc) or "아이템 삭제에 실패했습니다.")
            self._show_error(exc, prefix="아이템 삭제 실패")

        self._submit(
            "item_write",
            lambda: self.editor_service.delete_item(
                settings,
                item_id=item_id,
                expected_version=detail.version,
            ),
            loaded,
            failed,
        )

    def _invalidate_tracker_cache(self, tracker_id: int) -> None:
        self._root_cache.pop(int(tracker_id), None)
        self._child_cache.clear()

    def _refresh_visible_item(self, detail: TrackerItemDetail) -> None:
        summary = detail.summary
        if summary.tracker_id is not None:
            self._invalidate_tracker_cache(summary.tracker_id)

        def update_tree_item(item: QTreeWidgetItem) -> None:
            existing = item.data(0, ITEM_SUMMARY_ROLE)
            if isinstance(existing, TrackerItemSummary) and existing.item_id == detail.item_id:
                updated = replace(
                    existing,
                    name=summary.name,
                    status=summary.status,
                    assignees=summary.assignees,
                    modified_at=summary.modified_at,
                    version=summary.version,
                )
                item.setData(0, ITEM_SUMMARY_ROLE, updated)
                item.setText(1, updated.name)
            for child_index in range(item.childCount()):
                update_tree_item(item.child(child_index))

        for top_index in range(self.item_tree.topLevelItemCount()):
            update_tree_item(self.item_tree.topLevelItem(top_index))

        for row in range(self.search_table.rowCount()):
            id_item = self.search_table.item(row, 0)
            existing = id_item.data(ITEM_SUMMARY_ROLE) if id_item is not None else None
            if not isinstance(existing, TrackerItemSummary) or existing.item_id != detail.item_id:
                continue
            updated = replace(
                existing,
                name=summary.name,
                status=summary.status,
                assignees=summary.assignees,
                modified_at=summary.modified_at,
                version=summary.version,
            )
            id_item.setData(ITEM_SUMMARY_ROLE, updated)
            self.search_table.item(row, 1).setText(updated.name)
            self.search_table.item(row, 2).setText(updated.status or "-")
            self.search_table.item(row, 3).setText(", ".join(updated.assignees) or "-")

    def _remove_visible_item(self, item_id: int) -> None:
        def remove_from(parent: QTreeWidgetItem | None) -> bool:
            count = self.item_tree.topLevelItemCount() if parent is None else parent.childCount()
            for index in range(count - 1, -1, -1):
                item = (
                    self.item_tree.topLevelItem(index)
                    if parent is None
                    else parent.child(index)
                )
                summary = item.data(0, ITEM_SUMMARY_ROLE)
                if isinstance(summary, TrackerItemSummary) and summary.item_id == int(item_id):
                    if parent is None:
                        self.item_tree.takeTopLevelItem(index)
                    else:
                        parent.takeChild(index)
                    return True
                if remove_from(item):
                    return True
            return False

        remove_from(None)
        for row in range(self.search_table.rowCount() - 1, -1, -1):
            id_item = self.search_table.item(row, 0)
            summary = id_item.data(ITEM_SUMMARY_ROLE) if id_item is not None else None
            if isinstance(summary, TrackerItemSummary) and summary.item_id == int(item_id):
                self.search_table.removeRow(row)

    def shutdown(self) -> None:
        """창 종료 뒤 완료되는 요청이 화면 상태를 갱신하지 않도록 무효화한다."""
        if self._editor_dialog is not None:
            self._editor_dialog.close()
        self._invalidate_requests()
        for task in tuple(self._tasks):
            try:
                task.completed.disconnect()
                task.failed.disconnect()
            except Exception:
                pass


__all__ = [
    "CHILDREN_LOADED_ROLE",
    "DEFAULT_SEARCH_PAGE_SIZE",
    "HIERARCHY_FETCH_PAGE_SIZE",
    "ITEM_SUMMARY_ROLE",
    "PLACEHOLDER_ROLE",
    "REQUEST_BUSY_MESSAGES",
    "TrackerWorkspacePage",
]
