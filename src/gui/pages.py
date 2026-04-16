from __future__ import annotations

from dataclasses import dataclass


def _require_qt():
    try:
        from PySide6.QtCore import Qt
        from PySide6.QtWidgets import QCheckBox
        from PySide6.QtWidgets import QComboBox
        from PySide6.QtWidgets import QDoubleSpinBox
        from PySide6.QtWidgets import QFileDialog
        from PySide6.QtWidgets import QFormLayout
        from PySide6.QtWidgets import QHBoxLayout
        from PySide6.QtWidgets import QLabel
        from PySide6.QtWidgets import QLineEdit
        from PySide6.QtWidgets import QPlainTextEdit
        from PySide6.QtWidgets import QPushButton
        from PySide6.QtWidgets import QSpinBox
        from PySide6.QtWidgets import QStackedWidget
        from PySide6.QtWidgets import QTableWidget
        from PySide6.QtWidgets import QTableWidgetItem
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
        "QFormLayout": QFormLayout,
        "QHBoxLayout": QHBoxLayout,
        "QLabel": QLabel,
        "QLineEdit": QLineEdit,
        "QPlainTextEdit": QPlainTextEdit,
        "QPushButton": QPushButton,
        "QSpinBox": QSpinBox,
        "QStackedWidget": QStackedWidget,
        "QTableWidget": QTableWidget,
        "QTableWidgetItem": QTableWidgetItem,
        "QVBoxLayout": QVBoxLayout,
        "QWidget": QWidget,
    }


@dataclass
class NavigationContext:
    go_previous: callable
    go_next: callable


def create_settings_page(settings_store, initial_settings, on_settings_changed):
    qt = _require_qt()
    QWidget = qt["QWidget"]
    QVBoxLayout = qt["QVBoxLayout"]
    QFormLayout = qt["QFormLayout"]
    QHBoxLayout = qt["QHBoxLayout"]
    QLabel = qt["QLabel"]
    QLineEdit = qt["QLineEdit"]
    QCheckBox = qt["QCheckBox"]
    QSpinBox = qt["QSpinBox"]
    QDoubleSpinBox = qt["QDoubleSpinBox"]
    QPushButton = qt["QPushButton"]

    page = QWidget()
    page.setObjectName("settings_page")

    layout = QVBoxLayout(page)
    title = QLabel("설정")
    title.setStyleSheet("font-size: 20px; font-weight: 600;")
    layout.addWidget(title)

    form = QFormLayout()
    base_url = QLineEdit(initial_settings.base_url)
    username = QLineEdit(initial_settings.username)
    password = QLineEdit(initial_settings.password)
    password.setEchoMode(QLineEdit.EchoMode.Password)
    save_password = QCheckBox("비밀번호 저장")
    save_password.setChecked(initial_settings.save_password)
    project_id = QLineEdit(initial_settings.default_project_id)
    tracker_id = QLineEdit(initial_settings.default_tracker_id)
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

    form.addRow("Base URL", base_url)
    form.addRow("Username", username)
    form.addRow("Password", password)
    form.addRow("", save_password)
    form.addRow("Default Project ID", project_id)
    form.addRow("Default Tracker ID", tracker_id)
    form.addRow("Header Row", header_row)
    form.addRow("Summary Column", summary_column)
    form.addRow("Sheet Name", sheet_name)
    form.addRow("Retry Delay", retry_delay)
    form.addRow("Max Retries", retry_count)
    form.addRow("Output Directory", output_dir)
    layout.addLayout(form)

    status_label = QLabel("")
    layout.addWidget(status_label)

    buttons = QHBoxLayout()
    load_button = QPushButton("불러오기")
    save_button = QPushButton("저장")
    next_button = QPushButton("다음")
    buttons.addWidget(load_button)
    buttons.addWidget(save_button)
    buttons.addStretch(1)
    buttons.addWidget(next_button)
    layout.addLayout(buttons)

    def _collect_settings():
        return type(initial_settings)(
            base_url=base_url.text().strip(),
            username=username.text().strip(),
            password=password.text(),
            save_password=save_password.isChecked(),
            default_project_id=project_id.text().strip(),
            default_tracker_id=tracker_id.text().strip(),
            excel_header_row=header_row.value(),
            summary_column=summary_column.text().strip() or "Summary",
            excel_sheet_name=sheet_name.text().strip() or "0",
            rate_limit_retry_delay_seconds=retry_delay.value(),
            rate_limit_max_retries=retry_count.value(),
            output_dir=output_dir.text().strip() or "output",
            last_file_path=initial_settings.last_file_path,
        )

    def _load():
        loaded = settings_store.load()
        base_url.setText(loaded.base_url)
        username.setText(loaded.username)
        password.setText(loaded.password)
        save_password.setChecked(loaded.save_password)
        project_id.setText(loaded.default_project_id)
        tracker_id.setText(loaded.default_tracker_id)
        header_row.setValue(loaded.excel_header_row)
        summary_column.setText(loaded.summary_column)
        sheet_name.setText(loaded.excel_sheet_name)
        retry_delay.setValue(loaded.rate_limit_retry_delay_seconds)
        retry_count.setValue(loaded.rate_limit_max_retries)
        output_dir.setText(loaded.output_dir)
        on_settings_changed(loaded)
        status_label.setText("설정을 불러왔습니다.")

    def _save():
        current = _collect_settings()
        settings_store.save(current)
        on_settings_changed(current)
        status_label.setText("설정을 저장했습니다.")

    def _go_next():
        current = _collect_settings()
        if not current.base_url or not current.username:
            status_label.setText("Base URL 과 Username 은 필수입니다.")
            return
        on_settings_changed(current)
        page.request_next()

    load_button.clicked.connect(_load)
    save_button.clicked.connect(_save)
    next_button.clicked.connect(_go_next)

    return page


def create_file_selection_page(initial_settings, on_file_state_changed):
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
    title = QLabel("파일 선택")
    title.setStyleSheet("font-size: 20px; font-weight: 600;")
    layout.addWidget(title)

    form = QFormLayout()
    file_path = QLineEdit(initial_settings.last_file_path)
    file_button = QPushButton("파일 선택")
    file_row_widget = QWidget()
    file_row = QHBoxLayout(file_row_widget)
    file_row.setContentsMargins(0, 0, 0, 0)
    file_row.addWidget(file_path)
    file_row.addWidget(file_button)
    sheet_name = QLineEdit(initial_settings.excel_sheet_name)
    header_row = QSpinBox()
    header_row.setMinimum(1)
    header_row.setValue(initial_settings.excel_header_row)
    summary_column = QComboBox()
    summary_column.setEditable(True)
    summary_column.addItems(["Summary", "요약"])
    summary_column.setCurrentText(initial_settings.summary_column)
    form.addRow("Excel 파일", file_row_widget)
    form.addRow("시트", sheet_name)
    form.addRow("헤더 행", header_row)
    form.addRow("Summary 컬럼", summary_column)
    layout.addLayout(form)

    preview_label = QLabel("미리보기")
    layout.addWidget(preview_label)
    preview_table = QTableWidget(5, 4)
    preview_table.setHorizontalHeaderLabels(["컬럼 A", "컬럼 B", "컬럼 C", "컬럼 D"])
    preview_table.setItem(0, 0, QTableWidgetItem("Summary"))
    preview_table.setItem(0, 1, QTableWidgetItem("담당자"))
    preview_table.setItem(1, 0, QTableWidgetItem("REQ-001"))
    preview_table.setItem(1, 1, QTableWidgetItem("홍길동"))
    layout.addWidget(preview_table)

    status_label = QLabel("실제 Excel 미리보기와 시트 조회 연동은 다음 단계에서 구현합니다.")
    layout.addWidget(status_label)

    buttons = QHBoxLayout()
    previous_button = QPushButton("이전")
    next_button = QPushButton("다음")
    buttons.addWidget(previous_button)
    buttons.addStretch(1)
    buttons.addWidget(next_button)
    layout.addLayout(buttons)

    def _collect_state():
        return {
            "file_path": file_path.text().strip(),
            "sheet_name": sheet_name.text().strip() or "0",
            "header_row": header_row.value(),
            "summary_column": summary_column.currentText().strip() or "Summary",
        }

    def _choose_file():
        selected, _ = QFileDialog.getOpenFileName(
            page,
            "Excel 파일 선택",
            file_path.text().strip(),
            "Excel Files (*.xlsx *.xlsm *.xls)",
        )
        if selected:
            file_path.setText(selected)
            state = _collect_state()
            on_file_state_changed(state)
            status_label.setText("파일 경로를 선택했습니다. 실제 미리보기 연동은 다음 단계에서 구현합니다.")

    def _go_previous():
        page.request_previous()

    def _go_next():
        state = _collect_state()
        if not state["file_path"]:
            status_label.setText("Excel 파일 경로를 지정해야 합니다.")
            return
        on_file_state_changed(state)
        page.request_next()

    file_button.clicked.connect(_choose_file)
    previous_button.clicked.connect(_go_previous)
    next_button.clicked.connect(_go_next)

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
    title = QLabel(title_text)
    title.setStyleSheet("font-size: 20px; font-weight: 600;")
    layout.addWidget(title)

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
