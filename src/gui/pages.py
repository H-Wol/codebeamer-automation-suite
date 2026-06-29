from __future__ import annotations

from pathlib import Path

from .services import DEFAULT_TRACKER_ITEM_ID_REGEX
from .services import ROOT_ASSIGNMENT_MODE_FILE_SOURCE
from .services import ROOT_ASSIGNMENT_MODE_FIXED_VALUE
from src.models import TrackerItemResolutionMode


USER_HIDDEN_TABLE_COLUMNS = {
    "_row_id",
    "parent_row_id",
    "depth",
    "_summary_indent",
    "_start_excel_row",
    "_end_excel_row",
    "_excel_row",
    "payload_json",
    "payload_status",
    "payload_error",
    "error_response_json",
    "source_file_path",
}


def _is_hidden_user_table_column(column_name: object) -> bool:
    text = str(column_name or "").strip()
    if not text:
        return False
    if text in USER_HIDDEN_TABLE_COLUMNS:
        return True
    if text.startswith("_"):
        return True
    if "__" in text:
        return True
    return False

def _require_qt():
    try:
        from PySide6.QtCore import Qt
        from PySide6.QtWidgets import QCheckBox
        from PySide6.QtWidgets import QComboBox
        from PySide6.QtWidgets import QDoubleSpinBox
        from PySide6.QtWidgets import QFileDialog
        from PySide6.QtWidgets import QFrame
        from PySide6.QtWidgets import QFormLayout
        from PySide6.QtWidgets import QHBoxLayout
        from PySide6.QtWidgets import QHeaderView
        from PySide6.QtWidgets import QLabel
        from PySide6.QtWidgets import QLineEdit
        from PySide6.QtWidgets import QPlainTextEdit
        from PySide6.QtWidgets import QProgressBar
        from PySide6.QtWidgets import QPushButton
        from PySide6.QtWidgets import QSizePolicy
        from PySide6.QtWidgets import QSpinBox
        from PySide6.QtWidgets import QTabWidget
        from PySide6.QtWidgets import QTableWidget
        from PySide6.QtWidgets import QTableWidgetItem
        from PySide6.QtWidgets import QToolButton
        from PySide6.QtWidgets import QVBoxLayout
        from PySide6.QtWidgets import QWidget
    except ImportError as exc:
        raise RuntimeError("GUI 실행에는 PySide6 패키지가 필요합니다.") from exc

    return {
        "Qt": Qt,
        "QCheckBox": QCheckBox,
        "QComboBox": QComboBox,
        "QDoubleSpinBox": QDoubleSpinBox,
        "QFileDialog": QFileDialog,
        "QFrame": QFrame,
        "QFormLayout": QFormLayout,
        "QHBoxLayout": QHBoxLayout,
        "QHeaderView": QHeaderView,
        "QLabel": QLabel,
        "QLineEdit": QLineEdit,
        "QPlainTextEdit": QPlainTextEdit,
        "QProgressBar": QProgressBar,
        "QPushButton": QPushButton,
        "QSizePolicy": QSizePolicy,
        "QSpinBox": QSpinBox,
        "QTabWidget": QTabWidget,
        "QTableWidget": QTableWidget,
        "QTableWidgetItem": QTableWidgetItem,
        "QToolButton": QToolButton,
        "QVBoxLayout": QVBoxLayout,
        "QWidget": QWidget,
    }


def _configure_table_columns(table, minimum_widths: list[int]) -> None:
    qt = _require_qt()
    QHeaderView = qt["QHeaderView"]
    header = table.horizontalHeader()
    header.setStretchLastSection(False)
    header.setMinimumSectionSize(80)
    for column_index in range(table.columnCount()):
        header.setSectionResizeMode(column_index, QHeaderView.ResizeToContents)
    table.resizeColumnsToContents()
    for column_index, minimum_width in enumerate(minimum_widths):
        if column_index >= table.columnCount():
            break
        if table.columnWidth(column_index) < minimum_width:
            table.setColumnWidth(column_index, minimum_width)
    if table.columnCount() > 0:
        header.setSectionResizeMode(table.columnCount() - 1, QHeaderView.Stretch)


def _configure_form_layout(form) -> None:
    qt = _require_qt()
    Qt = qt["Qt"]
    QFormLayout = qt["QFormLayout"]

    form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
    form.setFormAlignment(
        Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop
    )
    form.setLabelAlignment(
        Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
    )
    form.setHorizontalSpacing(14)
    form.setVerticalSpacing(8)


def _configure_form_field(widget, *, minimum_width: int = 240) -> None:
    qt = _require_qt()
    QSizePolicy = qt["QSizePolicy"]
    widget.setMinimumWidth(minimum_width)
    widget.setSizePolicy(
        QSizePolicy.Policy.Expanding,
        QSizePolicy.Policy.Fixed,
    )


def create_settings_page(
    settings_store,
    initial_settings,
    on_settings_changed,
):
    qt = _require_qt()
    QWidget = qt["QWidget"]
    QVBoxLayout = qt["QVBoxLayout"]
    QFormLayout = qt["QFormLayout"]
    QHBoxLayout = qt["QHBoxLayout"]
    QLabel = qt["QLabel"]
    QLineEdit = qt["QLineEdit"]
    QFrame = qt["QFrame"]
    QCheckBox = qt["QCheckBox"]
    QSpinBox = qt["QSpinBox"]
    QDoubleSpinBox = qt["QDoubleSpinBox"]
    QPushButton = qt["QPushButton"]
    QToolButton = qt["QToolButton"]
    Qt = qt["Qt"]

    page = QWidget()
    page.setObjectName("settings_page")
    layout = QVBoxLayout(page)
    layout.setContentsMargins(6, 6, 6, 6)
    layout.setSpacing(10)
    layout.setAlignment(Qt.AlignmentFlag.AlignTop)

    form = QFormLayout()
    _configure_form_layout(form)
    base_url = QLineEdit(initial_settings.base_url)
    username = QLineEdit(initial_settings.username)
    password = QLineEdit(initial_settings.password)
    password.setEchoMode(QLineEdit.EchoMode.Password)
    save_password = QCheckBox("비밀번호 저장")
    save_password.setChecked(initial_settings.save_password)
    header_row = QSpinBox()
    header_row.setMinimum(1)
    header_row.setValue(initial_settings.excel_header_row)
    summary_column = QLineEdit(initial_settings.summary_column)
    sheet_name = QLineEdit(initial_settings.excel_sheet_name)
    retry_delay = QDoubleSpinBox()
    retry_delay.setMinimum(0.0)
    retry_delay.setMaximum(3600.0)
    retry_delay.setValue(initial_settings.rate_limit_retry_delay_seconds)
    retry_delay.setDecimals(2)
    retry_count = QSpinBox()
    retry_count.setMinimum(0)
    retry_count.setMaximum(999)
    retry_count.setValue(initial_settings.rate_limit_max_retries)
    output_dir = QLineEdit(initial_settings.output_dir)

    for field_widget in (
        base_url,
        username,
        password,
    ):
        _configure_form_field(field_widget)

    form.addRow("Base URL", base_url)
    form.addRow("Username", username)
    form.addRow("Password", password)
    form.addRow("", save_password)
    layout.addLayout(form)

    advanced_toggle = QToolButton()
    advanced_toggle.setObjectName("section_toggle")
    advanced_toggle.setText("추가 설정")
    advanced_toggle.setCheckable(True)
    advanced_toggle.setChecked(False)
    advanced_toggle.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
    advanced_toggle.setArrowType(Qt.ArrowType.RightArrow)
    advanced_toggle.setAutoRaise(True)
    layout.addWidget(advanced_toggle)

    advanced_card = QFrame()
    advanced_card.setObjectName("advanced_card")
    advanced_card.hide()
    advanced_layout = QVBoxLayout(advanced_card)
    advanced_layout.setContentsMargins(14, 12, 14, 12)
    advanced_layout.setSpacing(8)

    advanced_description = QLabel("자주 바꾸지 않는 업로드 옵션입니다.")
    advanced_description.setObjectName("section_label")
    advanced_layout.addWidget(advanced_description)

    advanced_form = QFormLayout()
    _configure_form_layout(advanced_form)
    advanced_form.setContentsMargins(0, 0, 0, 0)

    for field_widget in (
        header_row,
        summary_column,
        sheet_name,
        retry_delay,
        retry_count,
        output_dir,
    ):
        _configure_form_field(field_widget)

    advanced_form.addRow("Header Row", header_row)
    advanced_form.addRow("Summary Column", summary_column)
    advanced_form.addRow("Sheet Name", sheet_name)
    advanced_form.addRow("Retry Delay", retry_delay)
    advanced_form.addRow("Max Retries", retry_count)
    advanced_form.addRow("Output Directory", output_dir)
    advanced_layout.addLayout(advanced_form)
    layout.addWidget(advanced_card)

    status_label = QLabel("")
    status_label.setObjectName("status_label")
    status_label.hide()
    layout.addWidget(status_label)
    page._current_settings = initial_settings

    buttons = QHBoxLayout()
    load_button = QPushButton("불러오기")
    save_button = QPushButton("저장")
    next_button = QPushButton("다음")
    next_button.setObjectName("primary_button")
    next_button.setEnabled(
        bool(initial_settings.base_url and initial_settings.username and initial_settings.password)
    )
    buttons.addWidget(load_button)
    buttons.addWidget(save_button)
    buttons.addStretch(1)
    buttons.addWidget(next_button)
    layout.addLayout(buttons)
    layout.addStretch(1)

    def _update_next_button_state() -> None:
        next_button.setEnabled(
            bool(base_url.text().strip() and username.text().strip() and password.text())
        )

    def _collect_settings():
        current_settings = getattr(page, "_current_settings", initial_settings)
        return type(initial_settings)(
            base_url=base_url.text().strip(),
            username=username.text().strip(),
            password=password.text(),
            save_password=save_password.isChecked(),
            default_project_id=str(getattr(current_settings, "default_project_id", "") or ""),
            default_tracker_id=str(getattr(current_settings, "default_tracker_id", "") or ""),
            excel_header_row=header_row.value(),
            summary_column=summary_column.text().strip() or "Summary",
            excel_sheet_name=sheet_name.text().strip() or "0",
            rate_limit_retry_delay_seconds=retry_delay.value(),
            rate_limit_max_retries=retry_count.value(),
            output_dir=output_dir.text().strip() or "output",
            last_file_path=str(getattr(current_settings, "last_file_path", "") or ""),
        )

    def _set_status(message: str) -> None:
        status_label.setVisible(bool(message))
        status_label.setText(message)
        request_content_reflow = getattr(page, "request_content_reflow", None)
        if callable(request_content_reflow):
            request_content_reflow(allow_grow=bool(message))

    def _apply_settings(loaded) -> None:
        page._current_settings = loaded
        base_url.setText(loaded.base_url)
        username.setText(loaded.username)
        password.setText(loaded.password)
        save_password.setChecked(loaded.save_password)
        header_row.setValue(loaded.excel_header_row)
        summary_column.setText(loaded.summary_column)
        sheet_name.setText(loaded.excel_sheet_name)
        retry_delay.setValue(loaded.rate_limit_retry_delay_seconds)
        retry_count.setValue(loaded.rate_limit_max_retries)
        output_dir.setText(loaded.output_dir)
        _update_next_button_state()

    def _load():
        loaded = settings_store.load()
        _apply_settings(loaded)
        on_settings_changed(loaded)
        _set_status("설정을 불러왔습니다.")

    def _save():
        current = _collect_settings()
        page._current_settings = current
        settings_store.save(current)
        on_settings_changed(current)
        _set_status("설정을 저장했습니다.")

    def _go_next():
        current = _collect_settings()
        if not current.base_url or not current.username or not current.password:
            _set_status("Base URL, Username, Password 는 필수입니다.")
            return
        on_settings_changed(current)
        page.request_next()

    load_button.clicked.connect(_load)
    save_button.clicked.connect(_save)
    next_button.clicked.connect(_go_next)
    base_url.textChanged.connect(lambda _: _update_next_button_state())
    username.textChanged.connect(lambda _: _update_next_button_state())
    password.textChanged.connect(lambda _: _update_next_button_state())
    advanced_toggle.toggled.connect(
        lambda checked: (
            advanced_card.setVisible(checked),
            advanced_toggle.setArrowType(
                Qt.ArrowType.DownArrow if checked else Qt.ArrowType.RightArrow
            ),
            getattr(page, "request_content_reflow", lambda **_: None)(allow_grow=checked),
        )
    )

    page.get_settings = _collect_settings
    page.set_settings = _apply_settings
    return page


def create_project_selection_page(
    initial_settings,
    on_settings_changed,
    on_connection_test,
    on_project_selected,
    on_error=None,
):
    qt = _require_qt()
    QWidget = qt["QWidget"]
    QVBoxLayout = qt["QVBoxLayout"]
    QFormLayout = qt["QFormLayout"]
    QHBoxLayout = qt["QHBoxLayout"]
    QLabel = qt["QLabel"]
    QComboBox = qt["QComboBox"]
    QPushButton = qt["QPushButton"]
    Qt = qt["Qt"]

    page = QWidget()
    page.selected_project_id = initial_settings.default_project_id
    page.selected_tracker_id = initial_settings.default_tracker_id

    layout = QVBoxLayout(page)
    layout.setContentsMargins(6, 6, 6, 6)
    layout.setSpacing(10)
    layout.setAlignment(Qt.AlignmentFlag.AlignTop)

    form = QFormLayout()
    _configure_form_layout(form)
    project_combo = QComboBox()
    project_combo.setEnabled(False)
    tracker_combo = QComboBox()
    tracker_combo.setEnabled(False)
    _configure_form_field(project_combo)
    _configure_form_field(tracker_combo)
    form.addRow("프로젝트", project_combo)
    form.addRow("트래커", tracker_combo)
    layout.addLayout(form)

    status_label = QLabel("연결 테스트를 실행하면 프로젝트 목록을 불러옵니다.")
    status_label.setObjectName("status_label")
    layout.addWidget(status_label)

    buttons = QHBoxLayout()
    previous_button = QPushButton("이전")
    refresh_button = QPushButton("프로젝트 불러오기")
    next_button = QPushButton("다음")
    refresh_button.setObjectName("primary_button")
    next_button.setObjectName("primary_button")
    next_button.setEnabled(bool(page.selected_project_id and page.selected_tracker_id))
    buttons.addWidget(previous_button)
    buttons.addWidget(refresh_button)
    buttons.addStretch(1)
    buttons.addWidget(next_button)
    layout.addLayout(buttons)
    layout.addStretch(1)

    def _update_next_button_state() -> None:
        next_button.setEnabled(bool(page.selected_project_id and page.selected_tracker_id))

    def _set_items(combo, items: list[dict], selected_id: str) -> None:
        combo.blockSignals(True)
        combo.clear()
        for item in items:
            combo.addItem(item["name"], item["id"])
        combo.setEnabled(bool(items))
        if selected_id:
            index = combo.findData(int(selected_id)) if selected_id.isdigit() else -1
            if index >= 0:
                combo.setCurrentIndex(index)
        combo.blockSignals(False)

    def _current_settings():
        settings = on_settings_changed(None)
        return settings

    def _refresh_projects() -> None:
        settings = _current_settings()
        try:
            projects = on_connection_test(settings)
        except Exception as exc:
            message = f"프로젝트 조회 실패: {exc}"
            status_label.setText(message)
            if callable(on_error):
                on_error("프로젝트 조회 실패", message)
            project_combo.clear()
            tracker_combo.clear()
            project_combo.setEnabled(False)
            tracker_combo.setEnabled(False)
            page.selected_project_id = ""
            page.selected_tracker_id = ""
            _update_next_button_state()
            return
        _set_items(project_combo, projects, page.selected_project_id)
        status_label.setText("프로젝트 목록을 불러왔습니다.")
        if project_combo.count() > 0:
            selected_index = project_combo.currentIndex()
            if selected_index < 0:
                selected_index = 0
                project_combo.setCurrentIndex(0)
            _handle_project_changed(selected_index)

    def _handle_project_changed(index: int) -> None:
        project_id = project_combo.itemData(index)
        if project_id in (None, ""):
            tracker_combo.clear()
            tracker_combo.setEnabled(False)
            page.selected_project_id = ""
            page.selected_tracker_id = ""
            _update_next_button_state()
            return
        page.selected_project_id = str(project_id)
        page.selected_tracker_id = ""
        _update_next_button_state()
        settings = _current_settings()
        settings.default_project_id = page.selected_project_id
        try:
            trackers = on_project_selected(settings, int(project_id))
        except Exception as exc:
            message = f"트래커 조회 실패: {exc}"
            status_label.setText(message)
            if callable(on_error):
                on_error("트래커 조회 실패", message)
            tracker_combo.clear()
            tracker_combo.setEnabled(False)
            _update_next_button_state()
            return
        _set_items(tracker_combo, trackers, page.selected_tracker_id)
        if tracker_combo.currentData() not in (None, ""):
            page.selected_tracker_id = str(tracker_combo.currentData())
        _update_next_button_state()
        status_label.setText(f"프로젝트 {project_combo.currentText()}의 트래커를 불러왔습니다.")

    def _handle_tracker_changed(index: int) -> None:
        tracker_id = tracker_combo.itemData(index)
        if tracker_id not in (None, ""):
            page.selected_tracker_id = str(tracker_id)
        else:
            page.selected_tracker_id = ""
        _update_next_button_state()

    def _go_next() -> None:
        if not page.selected_project_id or not page.selected_tracker_id:
            status_label.setText("프로젝트와 트래커를 모두 선택해야 합니다.")
            return
        settings = _current_settings()
        settings.default_project_id = page.selected_project_id
        settings.default_tracker_id = page.selected_tracker_id
        on_settings_changed(settings)
        page.request_next()

    previous_button.clicked.connect(lambda: page.request_previous())
    refresh_button.clicked.connect(_refresh_projects)
    next_button.clicked.connect(_go_next)
    project_combo.currentIndexChanged.connect(_handle_project_changed)
    tracker_combo.currentIndexChanged.connect(_handle_tracker_changed)

    def _load_selection(project_id: str, tracker_id: str) -> None:
        page.selected_project_id = str(project_id or "")
        page.selected_tracker_id = str(tracker_id or "")
        if page.selected_project_id.isdigit() and project_combo.count() > 0:
            project_index = project_combo.findData(int(page.selected_project_id))
            if project_index >= 0:
                project_combo.setCurrentIndex(project_index)
        if page.selected_tracker_id.isdigit() and tracker_combo.count() > 0:
            tracker_index = tracker_combo.findData(int(page.selected_tracker_id))
            if tracker_index >= 0:
                tracker_combo.setCurrentIndex(tracker_index)
        _update_next_button_state()

    def _get_selection() -> dict[str, str]:
        return {
            "project_id": str(page.selected_project_id or ""),
            "tracker_id": str(page.selected_tracker_id or ""),
        }

    page.load_selection = _load_selection
    page.get_selection = _get_selection
    return page


def create_file_selection_page(initial_settings, on_file_state_changed, on_file_preview_requested, on_error=None):
    qt = _require_qt()
    QWidget = qt["QWidget"]
    QVBoxLayout = qt["QVBoxLayout"]
    QFormLayout = qt["QFormLayout"]
    QHBoxLayout = qt["QHBoxLayout"]
    QLabel = qt["QLabel"]
    QLineEdit = qt["QLineEdit"]
    QPushButton = qt["QPushButton"]
    QSpinBox = qt["QSpinBox"]
    QComboBox = qt["QComboBox"]
    QTableWidget = qt["QTableWidget"]
    QTableWidgetItem = qt["QTableWidgetItem"]
    QFileDialog = qt["QFileDialog"]

    page = QWidget()
    page.setObjectName("file_selection_page")
    layout = QVBoxLayout(page)
    layout.setContentsMargins(6, 6, 6, 6)
    layout.setSpacing(10)

    form = QFormLayout()
    _configure_form_layout(form)
    file_path = QLineEdit(initial_settings.last_file_path)
    file_path.setReadOnly(True)
    file_button = QPushButton("파일 선택")
    file_row_widget = QWidget()
    file_row = QHBoxLayout(file_row_widget)
    file_row.setContentsMargins(0, 0, 0, 0)
    file_row.setSpacing(8)
    file_row.addWidget(file_path)
    file_row.addWidget(file_button)
    preview_file = QComboBox()
    preview_file.setEditable(False)
    preview_file.setEnabled(False)
    sheet_name = QComboBox()
    sheet_name.setEditable(False)
    header_row = QSpinBox()
    header_row.setMinimum(1)
    header_row.setValue(initial_settings.excel_header_row)
    summary_column = QComboBox()
    summary_column.setEditable(True)
    summary_column.addItems(["Summary", "요약"])
    summary_column.setCurrentText(initial_settings.summary_column)
    _configure_form_field(file_path)
    _configure_form_field(file_row_widget, minimum_width=320)
    _configure_form_field(preview_file)
    _configure_form_field(sheet_name)
    _configure_form_field(header_row)
    _configure_form_field(summary_column)
    form.addRow("Excel 파일", file_row_widget)
    form.addRow("미리보기 파일", preview_file)
    form.addRow("시트", sheet_name)
    form.addRow("헤더 행", header_row)
    form.addRow("Summary 컬럼", summary_column)
    layout.addLayout(form)

    preview_label = QLabel("미리보기")
    preview_label.setObjectName("section_label")
    layout.addWidget(preview_label)
    preview_table = QTableWidget(5, 4)
    preview_table.setAlternatingRowColors(True)
    preview_table.setHorizontalHeaderLabels(["컬럼 A", "컬럼 B", "컬럼 C", "컬럼 D"])
    preview_table.setItem(0, 0, QTableWidgetItem("Summary"))
    preview_table.setItem(0, 1, QTableWidgetItem("담당자"))
    preview_table.setItem(1, 0, QTableWidgetItem("REQ-001"))
    preview_table.setItem(1, 1, QTableWidgetItem("홍길동"))
    _configure_table_columns(preview_table, [180, 180, 160, 160])
    layout.addWidget(preview_table)

    status_label = QLabel("Excel 파일과 옵션을 정한 뒤 '데이터 불러오기'를 누르세요.")
    status_label.setObjectName("status_label")
    layout.addWidget(status_label)

    buttons = QHBoxLayout()
    previous_button = QPushButton("이전")
    load_button = QPushButton("데이터 불러오기")
    next_button = QPushButton("다음")
    load_button.setObjectName("primary_button")
    next_button.setObjectName("primary_button")
    next_button.setEnabled(False)
    buttons.addWidget(previous_button)
    buttons.addWidget(load_button)
    buttons.addStretch(1)
    buttons.addWidget(next_button)
    layout.addLayout(buttons)

    page._preview_ready = False
    page._selected_file_paths = [initial_settings.last_file_path] if initial_settings.last_file_path else []
    page._preview_data = None

    def _update_next_button_state() -> None:
        next_button.setEnabled(bool(page._selected_file_paths) and page._preview_ready)

    def _selected_preview_file_path() -> str:
        preview_path = str(preview_file.currentData() or "").strip()
        if preview_path:
            return preview_path
        if page._selected_file_paths:
            return str(page._selected_file_paths[0]).strip()
        return ""

    def _update_file_display() -> None:
        selected_count = len(page._selected_file_paths)
        if selected_count <= 0:
            file_path.setText("")
            return
        if selected_count == 1:
            file_path.setText(page._selected_file_paths[0])
            return
        first_name = Path(page._selected_file_paths[0]).name
        file_path.setText(f"{selected_count}개 파일 선택됨 ({first_name} 외)")

    def _set_preview_file_items(selected_file_paths: list[str], selected_path: str | None = None) -> None:
        preview_file.blockSignals(True)
        preview_file.clear()
        for current_path in selected_file_paths:
            preview_file.addItem(Path(current_path).name, current_path)
        preview_file.setEnabled(bool(selected_file_paths))
        if selected_file_paths:
            target_path = selected_path if selected_path in selected_file_paths else selected_file_paths[0]
            target_index = preview_file.findData(target_path)
            preview_file.setCurrentIndex(target_index if target_index >= 0 else 0)
        preview_file.blockSignals(False)

    def _collect_state():
        state = {
            "file_path": _selected_preview_file_path(),
            "file_paths": list(page._selected_file_paths),
            "preview_file_path": _selected_preview_file_path(),
            "sheet_name": sheet_name.currentText().strip() or "0",
            "header_row": header_row.value(),
            "summary_column": summary_column.currentText().strip() or "Summary",
        }
        if page._preview_ready and page._preview_data is not None:
            state["preview_data"] = page._preview_data
        return state

    def _set_preview(headers: list[str], rows: list[list[str]], resolved_summary: str) -> None:
        preview_table.clear()
        preview_table.setColumnCount(len(headers))
        preview_table.setRowCount(len(rows))
        preview_table.setHorizontalHeaderLabels(headers)
        for row_index, row in enumerate(rows):
            for col_index, value in enumerate(row):
                preview_table.setItem(row_index, col_index, QTableWidgetItem(value))
        _configure_table_columns(preview_table, [180] * max(len(headers), 1))
        if resolved_summary:
            summary_column.blockSignals(True)
            if summary_column.findText(resolved_summary) < 0:
                summary_column.addItem(resolved_summary)
            summary_column.setCurrentText(resolved_summary)
            summary_column.blockSignals(False)

    def _clear_preview() -> None:
        preview_table.clear()
        preview_table.setColumnCount(0)
        preview_table.setRowCount(0)

    def _mark_preview_dirty(*, clear_sheet_names: bool = False, message: str | None = None) -> None:
        page._preview_ready = False
        page._preview_data = None
        _clear_preview()
        if clear_sheet_names:
            sheet_name.blockSignals(True)
            sheet_name.clear()
            sheet_name.blockSignals(False)
        _update_next_button_state()
        if message:
            status_label.setText(message)
            return
        if page._selected_file_paths:
            status_label.setText("설정을 바꿨습니다. '데이터 불러오기'를 눌러 다시 확인하세요.")
            return
        status_label.setText("Excel 파일과 옵션을 정한 뒤 '데이터 불러오기'를 누르세요.")

    def _set_sheet_names(names: list[str], selected_name: str) -> None:
        sheet_name.blockSignals(True)
        sheet_name.clear()
        for name in names:
            sheet_name.addItem(name)
        if names:
            index = sheet_name.findText(selected_name)
            sheet_name.setCurrentIndex(index if index >= 0 else 0)
        sheet_name.blockSignals(False)

    def _refresh_preview() -> None:
        state = _collect_state()
        page._preview_ready = False
        _update_next_button_state()
        if not state["file_paths"]:
            status_label.setText("Excel 파일을 먼저 선택해야 합니다.")
            return
        try:
            preview = on_file_preview_requested(
                state["preview_file_path"],
                file_paths=state["file_paths"],
                sheet_name=state["sheet_name"],
                header_row=state["header_row"],
                summary_column=state["summary_column"],
            )
        except Exception as exc:
            message = f"파일 미리보기 실패: {exc}"
            status_label.setText(message)
            if callable(on_error):
                on_error("파일 미리보기 실패", message)
            return
        _set_sheet_names(preview.sheet_names, state["sheet_name"])
        _set_preview(preview.headers, preview.rows, getattr(preview, "summary_column", preview.suggested_summary))
        page._preview_data = preview
        page._preview_ready = True
        _update_next_button_state()
        status_label.setText(f"{len(page._selected_file_paths)}개 파일 기준으로 시트 목록과 미리보기를 갱신했습니다.")
        on_file_state_changed(_collect_state())

    def _choose_files():
        dialog_path = page._selected_file_paths[0] if page._selected_file_paths else initial_settings.last_file_path
        selected, _ = QFileDialog.getOpenFileNames(
            page,
            "Excel 파일 선택",
            dialog_path,
            "Excel Files (*.xlsx *.xlsm *.xls)",
        )
        if selected:
            page._selected_file_paths = [str(path) for path in selected]
            _set_preview_file_items(page._selected_file_paths)
            _update_file_display()
            _mark_preview_dirty(
                clear_sheet_names=True,
                message=(
                    f"{len(page._selected_file_paths)}개 파일을 선택했습니다. "
                    "'데이터 불러오기'를 눌러 시트 목록과 미리보기를 확인하세요."
                ),
            )

    def _go_previous():
        page.request_previous()

    def _go_next():
        state = _collect_state()
        if not state["file_paths"]:
            status_label.setText("Excel 파일을 하나 이상 선택해야 합니다.")
            return
        if not page._preview_ready:
            status_label.setText("파일 설정을 마친 뒤 '데이터 불러오기'를 먼저 실행해야 합니다.")
            return
        on_file_state_changed(state)
        page.request_next()

    file_button.clicked.connect(_choose_files)
    load_button.clicked.connect(_refresh_preview)
    preview_file.currentIndexChanged.connect(lambda _: _mark_preview_dirty())
    sheet_name.currentTextChanged.connect(lambda _: _mark_preview_dirty())
    header_row.valueChanged.connect(lambda _: _mark_preview_dirty())
    summary_column.currentTextChanged.connect(lambda _: _mark_preview_dirty())
    previous_button.clicked.connect(_go_previous)
    next_button.clicked.connect(_go_next)

    _set_preview_file_items(page._selected_file_paths, initial_settings.last_file_path)
    _update_file_display()

    def _load_state(state: dict[str, object]) -> None:
        loaded_state = dict(state or {})
        loaded_file_paths = [
            str(path).strip()
            for path in loaded_state.get("file_paths") or []
            if str(path).strip()
        ]
        if loaded_file_paths:
            page._selected_file_paths = loaded_file_paths
            _set_preview_file_items(
                page._selected_file_paths,
                str(loaded_state.get("preview_file_path") or ""),
            )
            _update_file_display()

        sheet_name.blockSignals(True)
        header_row.blockSignals(True)
        summary_column.blockSignals(True)
        try:
            loaded_sheet_name = str(loaded_state.get("sheet_name") or "").strip()
            loaded_header_row = int(loaded_state.get("header_row") or initial_settings.excel_header_row or 1)
            loaded_summary = str(
                loaded_state.get("summary_column") or initial_settings.summary_column or "Summary"
            ).strip() or "Summary"

            if loaded_sheet_name and sheet_name.findText(loaded_sheet_name) < 0:
                sheet_name.addItem(loaded_sheet_name)
            if loaded_summary and summary_column.findText(loaded_summary) < 0:
                summary_column.addItem(loaded_summary)

            if loaded_sheet_name:
                sheet_name.setCurrentText(loaded_sheet_name)
            header_row.setValue(max(1, loaded_header_row))
            summary_column.setCurrentText(loaded_summary)
        finally:
            sheet_name.blockSignals(False)
            header_row.blockSignals(False)
            summary_column.blockSignals(False)

        _mark_preview_dirty(
            message="저장된 파일 설정을 불러왔습니다. '데이터 불러오기'를 눌러 다시 확인하세요.",
        )
        on_file_state_changed(_collect_state())

    page.get_state = _collect_state
    page.load_state = _load_state
    page.refresh_preview = _refresh_preview

    return page


def create_root_item_page(on_preview_requested):
    qt = _require_qt()
    QWidget = qt["QWidget"]
    QVBoxLayout = qt["QVBoxLayout"]
    QFormLayout = qt["QFormLayout"]
    QHBoxLayout = qt["QHBoxLayout"]
    QLabel = qt["QLabel"]
    QLineEdit = qt["QLineEdit"]
    QComboBox = qt["QComboBox"]
    QCheckBox = qt["QCheckBox"]
    QPushButton = qt["QPushButton"]
    QTableWidget = qt["QTableWidget"]
    QTableWidgetItem = qt["QTableWidgetItem"]

    page = QWidget()
    layout = QVBoxLayout(page)
    layout.setContentsMargins(6, 6, 6, 6)
    layout.setSpacing(10)

    description_label = QLabel(
        "파일명 기반으로 생성할 최상위 부모 데이터의 이름과 필드 값을 설정합니다. "
        "필드별로 파일명/정규식 값을 쓰거나 스키마 선택값을 고를 수 있습니다."
    )
    description_label.setWordWrap(True)
    description_label.setObjectName("section_label")
    layout.addWidget(description_label)

    form = QFormLayout()
    _configure_form_layout(form)
    regex_target = QComboBox()
    regex_target.addItem("파일명(확장자 제외)", "file_stem")
    regex_target.addItem("전체 파일명", "file_name")
    regex_pattern = QLineEdit()
    regex_pattern.setPlaceholderText(r"예: ^(?P<project>[A-Z]+)_(?P<title>.+)$")
    _configure_form_field(regex_target)
    _configure_form_field(regex_pattern, minimum_width=320)
    form.addRow("정규식 대상", regex_target)
    form.addRow("정규식", regex_pattern)
    layout.addLayout(form)

    preview_label = QLabel("파일명 파싱 미리보기")
    preview_label.setObjectName("section_label")
    layout.addWidget(preview_label)

    preview_table = QTableWidget(0, 0)
    preview_table.setAlternatingRowColors(True)
    layout.addWidget(preview_table)

    field_label = QLabel("상단 데이터 필드 매핑")
    field_label.setObjectName("section_label")
    layout.addWidget(field_label)

    field_table = QTableWidget(0, 6)
    field_table.setHorizontalHeaderLabels(["사용", "Codebeamer 필드", "타입", "필수", "값 방식", "값"])
    field_table.setAlternatingRowColors(True)
    _configure_table_columns(field_table, [80, 240, 180, 90, 160, 240])
    layout.addWidget(field_table)

    status_label = QLabel("")
    status_label.setObjectName("status_label")
    layout.addWidget(status_label)

    buttons = QHBoxLayout()
    previous_button = QPushButton("이전")
    next_button = QPushButton("다음")
    next_button.setObjectName("primary_button")
    next_button.setEnabled(False)
    buttons.addWidget(previous_button)
    buttons.addStretch(1)
    buttons.addWidget(next_button)
    layout.addLayout(buttons)

    page._loaded = False
    page._refreshing = False
    page._field_candidates = []
    page._current_preview_context = None

    def _current_field_assignments() -> dict[str, dict[str, object]]:
        field_assignments: dict[str, dict[str, object]] = {}
        for row_index in range(field_table.rowCount()):
            enabled_widget = field_table.cellWidget(row_index, 0)
            mode_combo = field_table.cellWidget(row_index, 4)
            value_combo = field_table.cellWidget(row_index, 5)
            field_item = field_table.item(row_index, 1)
            if enabled_widget is None or mode_combo is None or value_combo is None or field_item is None:
                continue
            mode_key = str(mode_combo.currentData() or ROOT_ASSIGNMENT_MODE_FILE_SOURCE)
            field_assignments[field_item.text()] = {
                "enabled": bool(enabled_widget.isChecked()),
                "mode": mode_key,
                "value": (
                    str(value_combo.currentData() or "").strip()
                    if mode_key == ROOT_ASSIGNMENT_MODE_FILE_SOURCE
                    else value_combo.currentText().strip()
                ),
            }
        return field_assignments

    def _legacy_field_sources(field_assignments: dict[str, dict[str, object]]) -> dict[str, str]:
        field_sources: dict[str, str] = {}
        for schema_field, assignment in field_assignments.items():
            if not bool(assignment.get("enabled")):
                continue
            if str(assignment.get("mode") or "") != ROOT_ASSIGNMENT_MODE_FILE_SOURCE:
                continue
            source_key = str(assignment.get("value") or "").strip()
            if source_key:
                field_sources[schema_field] = source_key
        return field_sources

    def get_config() -> dict[str, object]:
        field_assignments = _current_field_assignments()
        return {
            "regex_pattern": regex_pattern.text().strip(),
            "regex_target": str(regex_target.currentData() or "file_stem"),
            "field_assignments": field_assignments,
            "field_sources": _legacy_field_sources(field_assignments),
        }

    def _column_label(column_name: str, source_options) -> str:
        if column_name == "file_name":
            return "파일"
        if column_name == "parse_target":
            return "파싱 대상"
        if column_name == "matched":
            return "일치"
        source_lookup = {str(option.key): str(option.label) for option in source_options}
        return source_lookup.get(column_name, column_name)

    def _mode_options(candidate) -> list[tuple[str, str]]:
        options: list[tuple[str, str]] = []
        if bool(candidate.allows_file_source):
            options.append(("파일명/정규식", ROOT_ASSIGNMENT_MODE_FILE_SOURCE))
        if bool(candidate.allows_fixed_value):
            options.append((
                "직접 입력" if bool(getattr(candidate, "allows_custom_value", False)) else "고정값",
                ROOT_ASSIGNMENT_MODE_FIXED_VALUE,
            ))
        return options

    def _populate_value_combo(value_combo, candidate, preview_context, mode_key: str, selected_value: str) -> None:
        value_combo.blockSignals(True)
        value_combo.clear()
        value_combo.setEditable(False)
        value_combo.addItem("", "")

        if mode_key == ROOT_ASSIGNMENT_MODE_FILE_SOURCE:
            for option in preview_context.source_options:
                value_combo.addItem(str(option.label), str(option.key))
        elif mode_key == ROOT_ASSIGNMENT_MODE_FIXED_VALUE:
            if bool(getattr(candidate, "allows_custom_value", False)):
                value_combo.setEditable(True)
                if value_combo.lineEdit() is not None:
                    value_combo.lineEdit().setPlaceholderText("직접 입력")
                value_combo.setCurrentText(selected_value)
            else:
                for option_name in getattr(candidate, "fixed_options", []):
                    value_combo.addItem(str(option_name), str(option_name))
                selected_index = value_combo.findData(selected_value)
                value_combo.setCurrentIndex(selected_index if selected_index >= 0 else 0)
        else:
            selected_index = value_combo.findData(selected_value)
            value_combo.setCurrentIndex(selected_index if selected_index >= 0 else 0)
        value_combo.blockSignals(False)

    def _sync_row_enabled_state(enabled_widget, mode_combo, value_combo, *, candidate) -> None:
        row_enabled = bool(enabled_widget.isChecked()) and bool(candidate.supported)
        has_mode_choice = mode_combo.count() > 0 and str(mode_combo.itemData(0) or "").strip() != ""
        mode_combo.setEnabled(row_enabled and has_mode_choice)
        value_combo.setEnabled(row_enabled and has_mode_choice)

    def _refresh_preview() -> None:
        if not page._loaded or page._refreshing:
            return
        page._refreshing = True
        try:
            preview_context = on_preview_requested(get_config())
            page.load_context(preview_context)
        finally:
            page._refreshing = False

    def load_context(preview_context) -> None:
        page._current_preview_context = preview_context
        page._loaded = False

        regex_pattern.blockSignals(True)
        regex_target.blockSignals(True)
        regex_pattern.setText(str(preview_context.regex_pattern or ""))
        target_index = regex_target.findData(str(preview_context.regex_target or "file_stem"))
        regex_target.setCurrentIndex(target_index if target_index >= 0 else 0)
        regex_pattern.blockSignals(False)
        regex_target.blockSignals(False)

        preview_headers = [
            _column_label(column_name, preview_context.source_options)
            for column_name in preview_context.preview_columns
        ]
        preview_table.clear()
        preview_table.setColumnCount(len(preview_headers))
        preview_table.setHorizontalHeaderLabels(preview_headers)
        preview_table.setRowCount(len(preview_context.preview_rows))
        for row_index, row_values in enumerate(preview_context.preview_rows):
            for col_index, column_name in enumerate(preview_context.preview_columns):
                preview_table.setItem(
                    row_index,
                    col_index,
                    QTableWidgetItem(str(row_values.get(column_name) or "")),
                )
        _configure_table_columns(preview_table, [180] * max(len(preview_headers), 1))

        current_field_assignments = dict(preview_context.field_assignments)
        field_table.setRowCount(len(preview_context.field_candidates))
        for row_index, candidate in enumerate(preview_context.field_candidates):
            enabled_widget = QCheckBox()
            current_assignment = dict(current_field_assignments.get(candidate.schema_field) or {})
            selected_mode = str(
                current_assignment.get("mode") or ROOT_ASSIGNMENT_MODE_FILE_SOURCE
            ).strip()
            selected_value = str(current_assignment.get("value") or "").strip()
            enabled_widget.setChecked(bool(current_assignment.get("enabled")))
            enabled_widget.setEnabled(bool(candidate.supported))
            field_table.setCellWidget(row_index, 0, enabled_widget)
            field_table.setItem(row_index, 1, QTableWidgetItem(candidate.schema_field))
            field_table.setItem(row_index, 2, QTableWidgetItem(candidate.field_type))
            field_table.setItem(row_index, 3, QTableWidgetItem("yes" if candidate.mandatory else "no"))

            mode_combo = QComboBox()
            mode_options = _mode_options(candidate)
            if not mode_options:
                mode_combo.addItem("지원 안 함", "")
            else:
                for mode_label, mode_key in mode_options:
                    mode_combo.addItem(mode_label, mode_key)
                mode_index = mode_combo.findData(selected_mode)
                if mode_index < 0:
                    mode_index = 0
                mode_combo.setCurrentIndex(mode_index)
            field_table.setCellWidget(row_index, 4, mode_combo)

            value_combo = QComboBox()
            _populate_value_combo(
                value_combo,
                candidate,
                preview_context,
                str(mode_combo.currentData() or ""),
                selected_value,
            )
            field_table.setCellWidget(row_index, 5, value_combo)
            _sync_row_enabled_state(
                enabled_widget,
                mode_combo,
                value_combo,
                candidate=candidate,
            )

            def _on_enabled_toggled(_checked, *, checkbox=enabled_widget, mode_widget=mode_combo, value_widget=value_combo, row_candidate=candidate):
                _sync_row_enabled_state(
                    checkbox,
                    mode_widget,
                    value_widget,
                    candidate=row_candidate,
                )
                _refresh_preview()

            def _on_mode_changed(_index, *, mode_widget=mode_combo, value_widget=value_combo, row_candidate=candidate):
                _populate_value_combo(
                    value_widget,
                    row_candidate,
                    preview_context,
                    str(mode_widget.currentData() or ""),
                    "",
                )
                _refresh_preview()

            enabled_widget.toggled.connect(_on_enabled_toggled)
            mode_combo.currentIndexChanged.connect(_on_mode_changed)
            value_combo.currentTextChanged.connect(lambda _text: _refresh_preview())

        _configure_table_columns(field_table, [80, 240, 180, 90, 160, 240])
        status_label.setText(str(preview_context.status_message or ""))
        next_button.setEnabled(not bool(preview_context.has_blocking_issues))
        page._loaded = True

    previous_button.clicked.connect(lambda: page.request_previous())
    next_button.clicked.connect(lambda: page.request_next())
    regex_pattern.textChanged.connect(lambda _text: _refresh_preview())
    regex_target.currentIndexChanged.connect(lambda _index: _refresh_preview())

    page.get_config = get_config
    page.load_context = load_context
    return page


def create_placeholder_page(title_text: str, description: str):
    qt = _require_qt()
    QWidget = qt["QWidget"]
    QVBoxLayout = qt["QVBoxLayout"]
    QHBoxLayout = qt["QHBoxLayout"]
    QLabel = qt["QLabel"]
    QPushButton = qt["QPushButton"]
    QPlainTextEdit = qt["QPlainTextEdit"]

    page = QWidget()
    layout = QVBoxLayout(page)
    layout.setContentsMargins(6, 6, 6, 6)
    layout.setSpacing(10)

    body = QPlainTextEdit()
    body.setReadOnly(True)
    body.setPlainText(description)
    layout.addWidget(body)

    buttons = QHBoxLayout()
    previous_button = QPushButton("이전")
    next_button = QPushButton("다음")
    buttons.addWidget(previous_button)
    buttons.addStretch(1)
    buttons.addWidget(next_button)
    layout.addLayout(buttons)

    previous_button.clicked.connect(lambda: page.request_previous())
    next_button.clicked.connect(lambda: page.request_next())
    return page


def create_mapping_page(on_validate_requested, on_error=None):
    qt = _require_qt()
    Qt = qt["Qt"]
    QWidget = qt["QWidget"]
    QVBoxLayout = qt["QVBoxLayout"]
    QHBoxLayout = qt["QHBoxLayout"]
    QLabel = qt["QLabel"]
    QPushButton = qt["QPushButton"]
    QTableWidget = qt["QTableWidget"]
    QTableWidgetItem = qt["QTableWidgetItem"]
    QCheckBox = qt["QCheckBox"]
    QComboBox = qt["QComboBox"]
    QLineEdit = qt["QLineEdit"]

    page = QWidget()
    layout = QVBoxLayout(page)
    layout.setContentsMargins(6, 6, 6, 6)
    layout.setSpacing(10)
    info_label = QLabel("")
    info_label.setObjectName("section_label")
    layout.addWidget(info_label)

    table = QTableWidget(0, 6)
    table.setHorizontalHeaderLabels(["사용", "Excel 컬럼", "Codebeamer 필드", "타입", "다중값", "지원 여부"])
    table.setAlternatingRowColors(True)
    _configure_table_columns(table, [90, 240, 240, 180, 100, 100])
    layout.addWidget(table)

    default_label = QLabel("공통 기본값")
    default_label.setObjectName("section_label")
    layout.addWidget(default_label)

    default_help_label = QLabel("행 값이 있으면 행 값이 우선하고, 비어 있으면 아래 기본값을 사용합니다.")
    default_help_label.setWordWrap(True)
    layout.addWidget(default_help_label)

    default_table = QTableWidget(0, 4)
    default_table.setHorizontalHeaderLabels(["Codebeamer 필드", "타입", "기본값", "필수"])
    default_table.setAlternatingRowColors(True)
    _configure_table_columns(default_table, [240, 180, 240, 90])
    layout.addWidget(default_table)

    tracker_item_label = QLabel("Tracker Item 처리")
    tracker_item_label.setObjectName("section_label")
    layout.addWidget(tracker_item_label)

    tracker_item_help_label = QLabel(
        "TrackerItemChoiceField 는 정규식으로 ID를 추출하거나, configuration 기반 source tracker에서 이름으로 미리 조회할 수 있습니다."
    )
    tracker_item_help_label.setWordWrap(True)
    layout.addWidget(tracker_item_help_label)

    tracker_item_table = QTableWidget(0, 5)
    tracker_item_table.setHorizontalHeaderLabels(["Excel 컬럼", "Codebeamer 필드", "방식", "정규식", "조회 소스"])
    tracker_item_table.setAlternatingRowColors(True)
    _configure_table_columns(tracker_item_table, [220, 220, 140, 280, 200])
    layout.addWidget(tracker_item_table)

    status_label = QLabel("")
    status_label.setObjectName("status_label")
    layout.addWidget(status_label)

    buttons = QHBoxLayout()
    previous_button = QPushButton("이전")
    validate_button = QPushButton("검증 실행")
    next_button = QPushButton("다음")
    validate_button.setObjectName("primary_button")
    next_button.setObjectName("primary_button")
    next_button.setEnabled(False)
    buttons.addWidget(previous_button)
    buttons.addWidget(validate_button)
    buttons.addStretch(1)
    buttons.addWidget(next_button)
    layout.addLayout(buttons)

    page._mapping_validated = False
    page._schema_rows_by_name = {}
    page._tracker_item_settings = {}

    def _mark_dirty() -> None:
        page._mapping_validated = False
        next_button.setEnabled(False)

    def _tracker_item_candidates(mapping: dict[str, str]) -> list[dict[str, object]]:
        candidates: list[dict[str, object]] = []
        for df_column, schema_field in mapping.items():
            schema_row = page._schema_rows_by_name.get(schema_field, {})
            if str(schema_row.get("field_type") or "").strip() != "TrackerItemChoiceField":
                continue
            source_tracker_ids = [
                int(value)
                for value in (schema_row.get("tracker_item_source_tracker_ids") or [])
                if str(value).strip()
            ]
            candidates.append({
                "df_column": df_column,
                "schema_field": schema_field,
                "source_tracker_ids": source_tracker_ids,
                "supports_query": bool(source_tracker_ids),
            })
        return candidates

    def _sync_tracker_item_regex_state(mode_combo, regex_edit) -> None:
        is_regex = mode_combo.currentData() == TrackerItemResolutionMode.REGEX.value
        regex_edit.setEnabled(is_regex)
        regex_edit.setPlaceholderText(
            "ID를 추출할 정규식"
            if is_regex
            else "query 모드에서는 선택 파일 전체 값을 중복 제거 후 사전 조회합니다."
        )

    def _populate_tracker_item_table(mapping: dict[str, str], tracker_item_settings: dict[str, dict[str, object]]) -> None:
        page._tracker_item_settings = {
            str(schema_field): dict(setting)
            for schema_field, setting in (tracker_item_settings or {}).items()
            if str(schema_field).strip() and isinstance(setting, dict)
        }
        candidates = _tracker_item_candidates(mapping)
        tracker_item_table.setRowCount(len(candidates))

        for row_index, candidate in enumerate(candidates):
            df_column = str(candidate.get("df_column") or "")
            schema_field = str(candidate.get("schema_field") or "")
            supports_query = bool(candidate.get("supports_query"))
            source_tracker_ids = list(candidate.get("source_tracker_ids") or [])
            selected_setting = page._tracker_item_settings.get(schema_field, {})
            default_mode = (
                TrackerItemResolutionMode.QUERY.value
                if supports_query
                else TrackerItemResolutionMode.REGEX.value
            )
            selected_mode = str(selected_setting.get("mode") or default_mode).strip()
            if selected_mode == TrackerItemResolutionMode.QUERY.value and not supports_query:
                selected_mode = TrackerItemResolutionMode.REGEX.value
            selected_regex = str(selected_setting.get("regex_pattern") or DEFAULT_TRACKER_ITEM_ID_REGEX).strip()

            column_item = QTableWidgetItem(df_column)
            column_item.setData(Qt.ItemDataRole.UserRole, {
                "schema_field": schema_field,
                "source_tracker_ids": source_tracker_ids,
            })
            tracker_item_table.setItem(row_index, 0, column_item)
            tracker_item_table.setItem(row_index, 1, QTableWidgetItem(schema_field))

            mode_combo = QComboBox()
            mode_combo.addItem("정규식 ID 추출", TrackerItemResolutionMode.REGEX.value)
            if supports_query:
                mode_combo.addItem("이름/summary 조회", TrackerItemResolutionMode.QUERY.value)
            mode_index = mode_combo.findData(selected_mode)
            mode_combo.setCurrentIndex(mode_index if mode_index >= 0 else 0)
            tracker_item_table.setCellWidget(row_index, 2, mode_combo)

            regex_edit = QLineEdit(selected_regex)
            tracker_item_table.setCellWidget(row_index, 3, regex_edit)
            _sync_tracker_item_regex_state(mode_combo, regex_edit)

            source_text = (
                ", ".join(f"tracker {tracker_id}" for tracker_id in source_tracker_ids)
                if source_tracker_ids
                else "configuration source 없음"
            )
            tracker_item_table.setItem(row_index, 4, QTableWidgetItem(source_text))

            mode_combo.currentIndexChanged.connect(
                lambda _index, combo=mode_combo, edit=regex_edit: (_sync_tracker_item_regex_state(combo, edit), _mark_dirty())
            )
            regex_edit.textChanged.connect(lambda _text: _mark_dirty())

        _configure_table_columns(tracker_item_table, [220, 220, 140, 280, 200])
        if candidates:
            tracker_item_help_label.setText(
                "TrackerItemChoiceField 는 정규식 ID 추출 또는 source tracker 사전 조회 중 하나를 선택하세요."
            )
        else:
            tracker_item_help_label.setText("현재 매핑에는 별도 Tracker Item 처리 설정이 필요한 필드가 없습니다.")

    def _configure_default_value_widget(combo, candidate, selected_default: str) -> None:
        combo.blockSignals(True)
        combo.clear()
        combo.setEditable(False)
        combo.addItem("")

        options = list(getattr(candidate, "options", []) or [])
        for option_name in options:
            combo.addItem(str(option_name))

        if bool(getattr(candidate, "allows_custom_value", False)):
            combo.setEditable(True)
            if combo.lineEdit() is not None:
                combo.lineEdit().setPlaceholderText("직접 입력")
            combo.setCurrentText(selected_default)
        else:
            target_index = combo.findText(selected_default)
            combo.setCurrentIndex(target_index if target_index >= 0 else 0)
        combo.blockSignals(False)

    def load_context(
        upload_columns: list[str],
        schema_df,
        selected_mapping: dict[str, str],
        default_value_candidates: list,
        selected_default_values: dict[str, str],
        selected_tracker_item_settings: dict[str, dict[str, object]],
    ) -> None:
        page._mapping_validated = False
        next_button.setEnabled(False)
        page._schema_rows_by_name = {
            str(row["field_name"]): row
            for _, row in schema_df.iterrows()
            if row.get("field_name")
        }
        schema_field_names = sorted(page._schema_rows_by_name.keys())
        table.setRowCount(len(upload_columns))
        for row_index, column_name in enumerate(upload_columns):
            enabled_widget = QCheckBox()
            enabled_widget.setChecked(column_name in selected_mapping)
            table.setCellWidget(row_index, 0, enabled_widget)
            table.setItem(row_index, 1, QTableWidgetItem(column_name))

            combo = QComboBox()
            combo.addItem("")
            combo.addItems(schema_field_names)
            if column_name in selected_mapping and combo.findText(selected_mapping[column_name]) >= 0:
                combo.setCurrentText(selected_mapping[column_name])
            table.setCellWidget(row_index, 2, combo)

            schema_field = selected_mapping.get(column_name)
            schema_row = page._schema_rows_by_name.get(schema_field, {})
            table.setItem(row_index, 3, QTableWidgetItem(str(schema_row.get("field_type") or "")))
            table.setItem(row_index, 4, QTableWidgetItem(str(bool(schema_row.get("multiple_values", False)))))
            table.setItem(row_index, 5, QTableWidgetItem("yes" if schema_row.get("is_supported", True) else "no"))

            def _on_combo_changed(_text, row=row_index):
                selected_name = table.cellWidget(row, 2).currentText().strip()
                schema = page._schema_rows_by_name.get(selected_name, {})
                table.setItem(row, 3, QTableWidgetItem(str(schema.get("field_type") or "")))
                table.setItem(row, 4, QTableWidgetItem(str(bool(schema.get("multiple_values", False)))))
                table.setItem(row, 5, QTableWidgetItem("yes" if schema.get("is_supported", True) else "no"))
                _populate_tracker_item_table(get_selected_mapping(), get_selected_tracker_item_settings())
                _mark_dirty()

            combo.currentTextChanged.connect(_on_combo_changed)
            enabled_widget.toggled.connect(
                lambda _checked: (_populate_tracker_item_table(get_selected_mapping(), get_selected_tracker_item_settings()), _mark_dirty())
            )

        default_table.setRowCount(len(default_value_candidates))
        for row_index, candidate in enumerate(default_value_candidates):
            schema_field = str(getattr(candidate, "schema_field", ""))
            default_table.setItem(row_index, 0, QTableWidgetItem(schema_field))
            default_table.setItem(row_index, 1, QTableWidgetItem(str(getattr(candidate, "field_type", ""))))

            combo = QComboBox()
            selected_default = str(selected_default_values.get(schema_field, "") or "")
            _configure_default_value_widget(combo, candidate, selected_default)
            combo.currentTextChanged.connect(lambda _text: _mark_dirty())
            default_table.setCellWidget(row_index, 2, combo)

            default_table.setItem(
                row_index,
                3,
                QTableWidgetItem("yes" if bool(getattr(candidate, "mandatory", False)) else "no"),
            )

        _configure_table_columns(table, [90, 240, 240, 180, 100, 100])
        _configure_table_columns(default_table, [240, 180, 240, 90])
        _populate_tracker_item_table(selected_mapping, selected_tracker_item_settings)
        info_label.setText(f"매핑 대상 컬럼 {len(upload_columns)}개. id, parent 는 제외됩니다.")
        if default_value_candidates:
            default_help_label.setText("행 값이 있으면 행 값이 우선하고, 비어 있으면 아래 기본값을 사용합니다.")
        else:
            default_help_label.setText("선택 가능한 공통 기본값 필드가 없습니다.")
        status_label.setText("")

    def get_selected_mapping() -> dict[str, str]:
        mapping: dict[str, str] = {}
        for row_index in range(table.rowCount()):
            enabled_widget = table.cellWidget(row_index, 0)
            combo = table.cellWidget(row_index, 2)
            if enabled_widget is None or combo is None:
                continue
            if not enabled_widget.isChecked():
                continue
            schema_field = combo.currentText().strip()
            if not schema_field:
                continue
            column_name_item = table.item(row_index, 1)
            if column_name_item is None:
                continue
            mapping[column_name_item.text()] = schema_field
        return mapping

    def get_selected_default_values() -> dict[str, str]:
        default_values: dict[str, str] = {}
        for row_index in range(default_table.rowCount()):
            field_item = default_table.item(row_index, 0)
            combo = default_table.cellWidget(row_index, 2)
            if field_item is None or combo is None:
                continue
            selected_value = combo.currentText().strip()
            if not selected_value:
                continue
            default_values[field_item.text()] = selected_value
        return default_values

    def get_selected_tracker_item_settings() -> dict[str, dict[str, object]]:
        settings: dict[str, dict[str, object]] = {}
        for row_index in range(tracker_item_table.rowCount()):
            source_item = tracker_item_table.item(row_index, 0)
            mode_combo = tracker_item_table.cellWidget(row_index, 2)
            regex_edit = tracker_item_table.cellWidget(row_index, 3)
            if source_item is None or mode_combo is None or regex_edit is None:
                continue
            metadata = source_item.data(Qt.ItemDataRole.UserRole) or {}
            schema_field = str(metadata.get("schema_field") or "").strip()
            if not schema_field:
                continue
            settings[schema_field] = {
                "mode": str(mode_combo.currentData() or TrackerItemResolutionMode.REGEX.value),
                "regex_pattern": regex_edit.text().strip(),
                "source_tracker_ids": list(metadata.get("source_tracker_ids") or []),
            }
        return settings

    def _validate() -> None:
        mapping = get_selected_mapping()
        if not mapping:
            status_label.setText("최소 1개 이상의 컬럼을 매핑해야 합니다.")
            return
        try:
            on_validate_requested(
                mapping,
                get_selected_default_values(),
                get_selected_tracker_item_settings(),
            )
        except Exception as exc:
            message = f"검증 실패: {exc}"
            status_label.setText(message)
            if callable(on_error):
                on_error("검증 실패", message)
            page._mapping_validated = False
            next_button.setEnabled(False)
            return
        status_label.setText("검증이 완료되었습니다.")
        page._mapping_validated = True
        next_button.setEnabled(True)

    previous_button.clicked.connect(lambda: page.request_previous())
    validate_button.clicked.connect(_validate)
    next_button.clicked.connect(lambda: page.request_next())

    page.load_context = load_context
    page.get_selected_mapping = get_selected_mapping
    page.get_selected_default_values = get_selected_default_values
    page.get_selected_tracker_item_settings = get_selected_tracker_item_settings
    return page


def create_validation_page():
    qt = _require_qt()
    QWidget = qt["QWidget"]
    QVBoxLayout = qt["QVBoxLayout"]
    QHBoxLayout = qt["QHBoxLayout"]
    QLabel = qt["QLabel"]
    QPushButton = qt["QPushButton"]
    QTableWidget = qt["QTableWidget"]
    QTableWidgetItem = qt["QTableWidgetItem"]

    page = QWidget()
    layout = QVBoxLayout(page)
    layout.setContentsMargins(6, 6, 6, 6)
    layout.setSpacing(10)
    summary_label = QLabel("")
    summary_label.setObjectName("summary_label")
    layout.addWidget(summary_label)

    table = QTableWidget(0, 7)
    table.setHorizontalHeaderLabels(["상태", "행", "항목", "컬럼", "입력값", "문제", "조치"])
    table.setAlternatingRowColors(True)
    _configure_table_columns(table, [90, 120, 180, 160, 160, 260, 280])
    layout.addWidget(table)

    status_label = QLabel("")
    status_label.setObjectName("status_label")
    layout.addWidget(status_label)

    buttons = QHBoxLayout()
    previous_button = QPushButton("이전")
    next_button = QPushButton("다음")
    next_button.setObjectName("primary_button")
    next_button.setEnabled(False)
    buttons.addWidget(previous_button)
    buttons.addStretch(1)
    buttons.addWidget(next_button)
    layout.addLayout(buttons)

    page.has_blocking_issues = True

    def set_results(issue_df, has_blocking_issues: bool, summary_stats: dict | None = None) -> None:
        rows: list[list[str]] = []
        if issue_df is not None and not issue_df.empty:
            for _, row in issue_df.iterrows():
                rows.append([
                    str(row.get("severity") or ""),
                    str(row.get("row_label") or ""),
                    str(row.get("item_name") or ""),
                    str(row.get("column") or ""),
                    str(row.get("raw_value") or ""),
                    str(row.get("message") or ""),
                    str(row.get("action") or ""),
                ])
        table.setRowCount(len(rows))
        for row_index, values in enumerate(rows):
            for col_index, value in enumerate(values):
                table.setItem(row_index, col_index, QTableWidgetItem(value))
        _configure_table_columns(table, [90, 120, 180, 160, 160, 260, 280])

        summary_stats = summary_stats or {}
        total_rows = int(summary_stats.get("total_rows", 0))
        ready_rows = int(summary_stats.get("ready_rows", 0))
        error_rows = int(summary_stats.get("error_rows", 0))
        warning_rows = int(summary_stats.get("warning_rows", 0))
        config_errors = int(summary_stats.get("config_errors", 0))
        config_warnings = int(summary_stats.get("config_warnings", 0))
        file_count = int(summary_stats.get("file_count", 1))
        batch_total_rows = int(summary_stats.get("batch_total_rows", total_rows))

        summary_parts = []
        if file_count > 1:
            summary_parts.append(f"선택 파일 {file_count}개")
            summary_parts.append(f"전체 예상 항목 {batch_total_rows}행")
            summary_parts.append(f"대표 파일 검증 {total_rows}행")
        else:
            summary_parts.append(f"전체 {total_rows}행")

        summary_parts.extend([
            f"바로 업로드 가능 {ready_rows}행",
            f"수정 필요 {error_rows}행",
            f"안내 {warning_rows}행",
        ])
        if config_errors:
            summary_parts.append(f"설정 오류 {config_errors}건")
        if config_warnings:
            summary_parts.append(f"설정 안내 {config_warnings}건")
        summary_label.setText(" | ".join(summary_parts))
        page.has_blocking_issues = has_blocking_issues
        next_button.setEnabled(not has_blocking_issues)
        if has_blocking_issues:
            status_label.setText("수정이 필요한 항목이 있어 업로드를 시작할 수 없습니다.")
        elif not rows:
            status_label.setText("문제가 있는 항목이 없습니다. 바로 업로드할 수 있습니다.")
        else:
            status_label.setText("오류는 없고 업로드 전에 확인할 안내 항목만 남아 있습니다.")

    def _go_next():
        if page.has_blocking_issues:
            status_label.setText("차단 이슈를 해결해야 다음 단계로 이동할 수 있습니다.")
            return
        page.request_next()

    previous_button.clicked.connect(lambda: page.request_previous())
    next_button.clicked.connect(_go_next)
    page.set_results = set_results
    return page


def create_upload_page(on_start_requested, on_pause_requested, on_resume_requested, on_cancel_requested):
    qt = _require_qt()
    QWidget = qt["QWidget"]
    QVBoxLayout = qt["QVBoxLayout"]
    QHBoxLayout = qt["QHBoxLayout"]
    QLabel = qt["QLabel"]
    QPushButton = qt["QPushButton"]
    QPlainTextEdit = qt["QPlainTextEdit"]
    QProgressBar = qt["QProgressBar"]
    QCheckBox = qt["QCheckBox"]
    QTableWidget = qt["QTableWidget"]
    QTableWidgetItem = qt["QTableWidgetItem"]

    page = QWidget()
    layout = QVBoxLayout(page)
    layout.setContentsMargins(6, 6, 6, 6)
    layout.setSpacing(10)

    page.progress_bar = QProgressBar()
    layout.addWidget(page.progress_bar)

    page.current_label = QLabel("현재 항목: -")
    page.total_label = QLabel("총 대상 0건 / 완료 0건")
    page.counter_label = QLabel("성공 0 / 실패 0 / 재시도 0")
    page.status_label = QLabel("준비")
    page.status_label.setObjectName("status_label")
    layout.addWidget(page.current_label)
    layout.addWidget(page.total_label)
    layout.addWidget(page.counter_label)
    layout.addWidget(page.status_label)

    page.time_label = QLabel("배치 시간: -")
    page.time_label.setObjectName("section_label")
    layout.addWidget(page.time_label)

    page.dry_run_checkbox = QCheckBox("Dry Run")
    page.continue_checkbox = QCheckBox("Continue on error")
    page.continue_checkbox.setChecked(True)
    opts = QHBoxLayout()
    opts.addWidget(page.dry_run_checkbox)
    opts.addWidget(page.continue_checkbox)
    opts.addStretch(1)
    layout.addLayout(opts)

    page.log_view = QPlainTextEdit()
    page.log_view.setReadOnly(True)
    page.log_view.setPlaceholderText("업로드 진행 로그와 시각이 여기에 표시됩니다.")
    page.log_view.setMinimumHeight(120)
    layout.addWidget(page.log_view)

    activity_label = QLabel("항목별 진행 기록")
    activity_label.setObjectName("section_label")
    layout.addWidget(activity_label)

    page.activity_table = QTableWidget(0, 7)
    page.activity_table.setHorizontalHeaderLabels(["파일", "항목", "상태", "시작", "완료", "소요", "로그"])
    page.activity_table.setAlternatingRowColors(True)
    page.activity_table.setMinimumHeight(220)
    _configure_table_columns(page.activity_table, [160, 180, 100, 110, 110, 90, 320])
    layout.addWidget(page.activity_table)

    page._activity_row_map = {}

    page.response_view = QPlainTextEdit()
    page.response_view.setReadOnly(True)
    page.response_view.setPlaceholderText("실패한 요청의 서버 응답 JSON이 여기에 표시됩니다.")
    page.response_view.setMinimumHeight(100)
    layout.addWidget(page.response_view)

    buttons = QHBoxLayout()
    page.start_button = QPushButton("시작")
    page.pause_button = QPushButton("일시정지")
    page.resume_button = QPushButton("재개")
    page.cancel_button = QPushButton("중단")
    page.result_button = QPushButton("결과 화면으로 이동")
    page.start_button.setObjectName("primary_button")
    page.resume_button.setObjectName("primary_button")
    page.cancel_button.setObjectName("danger_button")
    page.result_button.setObjectName("primary_button")
    page.pause_button.setEnabled(False)
    page.resume_button.setEnabled(False)
    page.cancel_button.setEnabled(False)
    page.result_button.setEnabled(False)
    buttons.addWidget(page.start_button)
    buttons.addWidget(page.pause_button)
    buttons.addWidget(page.resume_button)
    buttons.addWidget(page.cancel_button)
    buttons.addStretch(1)
    buttons.addWidget(page.result_button)
    layout.addLayout(buttons)

    page.start_button.clicked.connect(on_start_requested)
    page.pause_button.clicked.connect(on_pause_requested)
    page.resume_button.clicked.connect(on_resume_requested)
    page.cancel_button.clicked.connect(on_cancel_requested)
    page.result_button.clicked.connect(lambda: page.request_next())

    def _set_activity_cell(row_index: int, col_index: int, value: str) -> None:
        item = page.activity_table.item(row_index, col_index)
        if item is None:
            item = QTableWidgetItem(value)
            page.activity_table.setItem(row_index, col_index, item)
            return
        item.setText(value)

    def _ensure_activity_row(row_key: str, file_label: str, item_name: str) -> int:
        if row_key in page._activity_row_map:
            row_index = int(page._activity_row_map[row_key])
        else:
            row_index = page.activity_table.rowCount()
            page.activity_table.insertRow(row_index)
            page._activity_row_map[row_key] = row_index
        _set_activity_cell(row_index, 0, file_label)
        _set_activity_cell(row_index, 1, item_name)
        return row_index

    def record_activity_started(row_key: str, file_label: str, item_name: str, started_at: str) -> None:
        row_index = _ensure_activity_row(row_key, file_label, item_name)
        _set_activity_cell(row_index, 2, "진행 중")
        _set_activity_cell(row_index, 3, started_at)
        _set_activity_cell(row_index, 4, "")
        _set_activity_cell(row_index, 5, "")
        _set_activity_cell(row_index, 6, "업로드 시작")
        _configure_table_columns(page.activity_table, [160, 180, 100, 110, 110, 90, 320])
        page.activity_table.scrollToBottom()

    def record_activity_finished(
        row_key: str,
        file_label: str,
        item_name: str,
        *,
        status: str,
        finished_at: str,
        duration_text: str,
        message: str,
    ) -> None:
        row_index = _ensure_activity_row(row_key, file_label, item_name)
        _set_activity_cell(row_index, 2, status)
        if not page.activity_table.item(row_index, 3):
            _set_activity_cell(row_index, 3, finished_at)
        _set_activity_cell(row_index, 4, finished_at)
        _set_activity_cell(row_index, 5, duration_text)
        _set_activity_cell(row_index, 6, message)
        _configure_table_columns(page.activity_table, [160, 180, 100, 110, 110, 90, 320])
        page.activity_table.scrollToBottom()

    def reset(total_count: int) -> None:
        page.progress_bar.setMaximum(max(total_count, 1))
        page.progress_bar.setValue(0)
        page.current_label.setText("현재 항목: -")
        page.total_label.setText("총 대상 0건 / 완료 0건")
        page.counter_label.setText("성공 0 / 실패 0 / 재시도 0")
        page.status_label.setText("준비")
        page.time_label.setText("배치 시간: -")
        page.activity_table.setRowCount(0)
        page._activity_row_map = {}
        page.log_view.clear()
        page.response_view.clear()
        page.result_button.setEnabled(False)

    page.record_activity_started = record_activity_started
    page.record_activity_finished = record_activity_finished
    page.reset = reset
    return page


def create_result_page():
    qt = _require_qt()
    QWidget = qt["QWidget"]
    QVBoxLayout = qt["QVBoxLayout"]
    QHBoxLayout = qt["QHBoxLayout"]
    QLabel = qt["QLabel"]
    QPushButton = qt["QPushButton"]
    QPlainTextEdit = qt["QPlainTextEdit"]
    QTableWidget = qt["QTableWidget"]
    QTableWidgetItem = qt["QTableWidgetItem"]
    QTabWidget = qt["QTabWidget"]

    page = QWidget()
    layout = QVBoxLayout(page)
    layout.setContentsMargins(6, 6, 6, 6)
    layout.setSpacing(10)

    tabs = QTabWidget()
    page.tables = {}
    for key, label in (
        ("success_df", "성공"),
        ("failed_df", "실패"),
        ("unresolved_df", "미해결"),
    ):
        tab = QWidget()
        tab_layout = QVBoxLayout(tab)
        table = QTableWidget(0, 0)
        table.setAlternatingRowColors(True)
        tab_layout.addWidget(table)
        tabs.addTab(tab, label)
        page.tables[key] = table
    layout.addWidget(tabs)

    page.response_view = QPlainTextEdit()
    page.response_view.setReadOnly(True)
    layout.addWidget(page.response_view)

    buttons = QHBoxLayout()
    previous_button = QPushButton("이전")
    restart_button = QPushButton("새 업로드 시작")
    restart_button.setObjectName("primary_button")
    buttons.addWidget(previous_button)
    buttons.addStretch(1)
    buttons.addWidget(restart_button)
    layout.addLayout(buttons)

    def set_results(upload_result: dict) -> None:
        for key, table in page.tables.items():
            df = upload_result.get(key)
            if df is None or getattr(df, "empty", True):
                table.setRowCount(0)
                table.setColumnCount(0)
                continue

            visible_columns = [
                column_name
                for column_name in df.columns
                if not _is_hidden_user_table_column(column_name)
            ]
            if not visible_columns:
                visible_columns = [str(col) for col in df.columns]

            table.setColumnCount(len(visible_columns))
            table.setHorizontalHeaderLabels([str(col) for col in visible_columns])
            table.setRowCount(len(df))
            for row_index, (_, row) in enumerate(df.iterrows()):
                for col_index, column_name in enumerate(visible_columns):
                    table.setItem(row_index, col_index, QTableWidgetItem(str(row.get(column_name) or "")))
            _configure_table_columns(table, [140] * max(len(visible_columns), 1))

        failed_df = upload_result.get("failed_df")
        if failed_df is not None and not getattr(failed_df, "empty", True) and "error_response_json" in failed_df.columns:
            page.response_view.setPlainText(str(failed_df.iloc[0].get("error_response_json") or ""))
        else:
            page.response_view.clear()

    previous_button.clicked.connect(lambda: page.request_previous())
    restart_button.clicked.connect(lambda: page.request_restart())
    page.set_results = set_results
    return page
