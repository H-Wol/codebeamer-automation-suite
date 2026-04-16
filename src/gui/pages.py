from __future__ import annotations

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
        from PySide6.QtWidgets import QProgressBar
        from PySide6.QtWidgets import QPushButton
        from PySide6.QtWidgets import QSpinBox
        from PySide6.QtWidgets import QTabWidget
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
        "QProgressBar": QProgressBar,
        "QPushButton": QPushButton,
        "QSpinBox": QSpinBox,
        "QTabWidget": QTabWidget,
        "QTableWidget": QTableWidget,
        "QTableWidgetItem": QTableWidgetItem,
        "QVBoxLayout": QVBoxLayout,
        "QWidget": QWidget,
    }


def create_settings_page(
    settings_store,
    initial_settings,
    on_settings_changed,
    on_connection_test,
    on_project_selected,
):
    qt = _require_qt()
    QWidget = qt["QWidget"]
    QVBoxLayout = qt["QVBoxLayout"]
    QFormLayout = qt["QFormLayout"]
    QHBoxLayout = qt["QHBoxLayout"]
    QLabel = qt["QLabel"]
    QLineEdit = qt["QLineEdit"]
    QCheckBox = qt["QCheckBox"]
    QComboBox = qt["QComboBox"]
    QSpinBox = qt["QSpinBox"]
    QDoubleSpinBox = qt["QDoubleSpinBox"]
    QPushButton = qt["QPushButton"]

    page = QWidget()
    page.setObjectName("settings_page")
    page.selected_project_id = initial_settings.default_project_id
    page.selected_tracker_id = initial_settings.default_tracker_id

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
    project_combo = QComboBox()
    project_combo.setEnabled(False)
    tracker_combo = QComboBox()
    tracker_combo.setEnabled(False)
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
    form.addRow("Project", project_combo)
    form.addRow("Tracker", tracker_combo)
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
            default_project_id=str(project_combo.currentData() or page.selected_project_id or "").strip(),
            default_tracker_id=str(tracker_combo.currentData() or page.selected_tracker_id or "").strip(),
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
        page.selected_project_id = loaded.default_project_id
        page.selected_tracker_id = loaded.default_tracker_id
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

    def _handle_project_changed(index: int) -> None:
        project_id = project_combo.itemData(index)
        current = _collect_settings()
        if project_id in (None, ""):
            tracker_combo.clear()
            tracker_combo.setEnabled(False)
            return
        page.selected_project_id = str(project_id)
        try:
            trackers = on_project_selected(current, int(project_id))
        except Exception as exc:
            status_label.setText(f"트래커 조회 실패: {exc}")
            tracker_combo.clear()
            tracker_combo.setEnabled(False)
            return
        _set_items(tracker_combo, trackers, current.default_tracker_id)
        if tracker_combo.currentData() not in (None, ""):
            page.selected_tracker_id = str(tracker_combo.currentData())
        status_label.setText(f"프로젝트 {project_combo.currentText()}의 트래커를 불러왔습니다.")

    def _handle_tracker_changed(index: int) -> None:
        tracker_id = tracker_combo.itemData(index)
        if tracker_id not in (None, ""):
            page.selected_tracker_id = str(tracker_id)

    def _test_connection() -> None:
        current = _collect_settings()
        if not current.base_url or not current.username or not current.password:
            status_label.setText("연결 테스트에는 Base URL, Username, Password 가 필요합니다.")
            return
        try:
            projects = on_connection_test(current)
        except Exception as exc:
            status_label.setText(f"연결 실패: {exc}")
            project_combo.clear()
            tracker_combo.clear()
            project_combo.setEnabled(False)
            tracker_combo.setEnabled(False)
            return
        _set_items(project_combo, projects, current.default_project_id)
        status_label.setText("연결에 성공했습니다. 프로젝트 목록을 불러왔습니다.")
        if project_combo.count() > 0:
            selected_index = project_combo.currentIndex()
            if selected_index < 0:
                selected_index = 0
                project_combo.setCurrentIndex(0)
            _handle_project_changed(selected_index)

    def _go_next():
        current = _collect_settings()
        if not current.base_url or not current.username:
            status_label.setText("Base URL 과 Username 은 필수입니다.")
            return
        on_settings_changed(current)
        page.request_next()

    load_button.clicked.connect(_load)
    save_button.clicked.connect(_save)
    project_combo.currentIndexChanged.connect(_handle_project_changed)
    tracker_combo.currentIndexChanged.connect(_handle_tracker_changed)
    next_button.clicked.connect(_go_next)
    test_button = QPushButton("연결 테스트")
    buttons.insertWidget(2, test_button)
    test_button.clicked.connect(_test_connection)

    page.set_projects = lambda items, selected_id="": _set_items(project_combo, items, selected_id)
    page.set_trackers = lambda items, selected_id="": _set_items(tracker_combo, items, selected_id)

    return page


def create_file_selection_page(initial_settings, on_file_state_changed, on_file_preview_requested):
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
    sheet_name = QComboBox()
    sheet_name.setEditable(False)
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

    status_label = QLabel("Excel 파일을 선택하면 시트 목록과 미리보기를 불러옵니다.")
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
            "sheet_name": sheet_name.currentText().strip() or "0",
            "header_row": header_row.value(),
            "summary_column": summary_column.currentText().strip() or "Summary",
        }

    def _set_preview(headers: list[str], rows: list[list[str]], suggested_summary: str) -> None:
        preview_table.clear()
        preview_table.setColumnCount(len(headers))
        preview_table.setRowCount(len(rows))
        preview_table.setHorizontalHeaderLabels(headers)
        for row_index, row in enumerate(rows):
            for col_index, value in enumerate(row):
                preview_table.setItem(row_index, col_index, QTableWidgetItem(value))
        if suggested_summary:
            if summary_column.findText(suggested_summary) < 0:
                summary_column.addItem(suggested_summary)
            summary_column.setCurrentText(suggested_summary)

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
        if not state["file_path"]:
            return
        try:
            preview = on_file_preview_requested(
                state["file_path"],
                sheet_name=state["sheet_name"],
                header_row=state["header_row"],
            )
        except Exception as exc:
            status_label.setText(f"파일 미리보기 실패: {exc}")
            return
        _set_sheet_names(preview.sheet_names, state["sheet_name"])
        _set_preview(preview.headers, preview.rows, preview.suggested_summary)
        status_label.setText("시트 목록과 미리보기를 갱신했습니다.")
        on_file_state_changed(_collect_state())

    def _choose_file():
        selected, _ = QFileDialog.getOpenFileName(
            page,
            "Excel 파일 선택",
            file_path.text().strip(),
            "Excel Files (*.xlsx *.xlsm *.xls)",
        )
        if selected:
            file_path.setText(selected)
            _refresh_preview()

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
    sheet_name.currentTextChanged.connect(lambda _: _refresh_preview())
    header_row.valueChanged.connect(lambda _: _refresh_preview())
    previous_button.clicked.connect(_go_previous)
    next_button.clicked.connect(_go_next)

    page.refresh_preview = _refresh_preview

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


def create_mapping_page(on_validate_requested):
    qt = _require_qt()
    QWidget = qt["QWidget"]
    QVBoxLayout = qt["QVBoxLayout"]
    QHBoxLayout = qt["QHBoxLayout"]
    QLabel = qt["QLabel"]
    QPushButton = qt["QPushButton"]
    QTableWidget = qt["QTableWidget"]
    QTableWidgetItem = qt["QTableWidgetItem"]
    QCheckBox = qt["QCheckBox"]
    QComboBox = qt["QComboBox"]

    page = QWidget()
    layout = QVBoxLayout(page)
    title = QLabel("컬럼 매핑")
    title.setStyleSheet("font-size: 20px; font-weight: 600;")
    layout.addWidget(title)

    info_label = QLabel("")
    layout.addWidget(info_label)

    table = QTableWidget(0, 6)
    table.setHorizontalHeaderLabels(["사용", "Excel 컬럼", "Codebeamer 필드", "타입", "다중값", "지원 여부"])
    layout.addWidget(table)

    status_label = QLabel("")
    layout.addWidget(status_label)

    buttons = QHBoxLayout()
    previous_button = QPushButton("이전")
    validate_button = QPushButton("검증 실행")
    next_button = QPushButton("다음")
    next_button.setEnabled(False)
    buttons.addWidget(previous_button)
    buttons.addWidget(validate_button)
    buttons.addStretch(1)
    buttons.addWidget(next_button)
    layout.addLayout(buttons)

    page._mapping_validated = False
    page._schema_rows_by_name = {}

    def load_context(upload_columns: list[str], schema_df, selected_mapping: dict[str, str]) -> None:
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
                page._mapping_validated = False
                next_button.setEnabled(False)

            combo.currentTextChanged.connect(_on_combo_changed)
            enabled_widget.toggled.connect(lambda _checked: next_button.setEnabled(False))
        info_label.setText(f"매핑 대상 컬럼 {len(upload_columns)}개. id, parent 는 제외됩니다.")
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

    def _validate() -> None:
        mapping = get_selected_mapping()
        if not mapping:
            status_label.setText("최소 1개 이상의 컬럼을 매핑해야 합니다.")
            return
        try:
            on_validate_requested(mapping)
        except Exception as exc:
            status_label.setText(f"검증 실패: {exc}")
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
    title = QLabel("검증")
    title.setStyleSheet("font-size: 20px; font-weight: 600;")
    layout.addWidget(title)

    summary_label = QLabel("")
    layout.addWidget(summary_label)

    table = QTableWidget(0, 5)
    table.setHorizontalHeaderLabels(["구분", "컬럼", "필드", "상태", "메시지"])
    layout.addWidget(table)

    status_label = QLabel("")
    layout.addWidget(status_label)

    buttons = QHBoxLayout()
    previous_button = QPushButton("이전")
    next_button = QPushButton("다음")
    buttons.addWidget(previous_button)
    buttons.addStretch(1)
    buttons.addWidget(next_button)
    layout.addLayout(buttons)

    page.has_blocking_issues = True

    def set_results(comparison_df, option_check_df, payload_df, has_blocking_issues: bool) -> None:
        rows: list[list[str]] = []
        if comparison_df is not None and not comparison_df.empty:
            for _, row in comparison_df.iterrows():
                rows.append([
                    "schema",
                    str(row.get("df_column") or ""),
                    str(row.get("selected_schema_field") or ""),
                    str(row.get("status") or ""),
                    str(row.get("unsupported_reason") or ""),
                ])
        if option_check_df is not None and not option_check_df.empty:
            for _, row in option_check_df.iterrows():
                rows.append([
                    "option",
                    str(row.get("df_column") or ""),
                    str(row.get("schema_field") or ""),
                    str(row.get("status") or ""),
                    str(row.get("error") or row.get("detail") or ""),
                ])
        if payload_df is not None and not payload_df.empty:
            failed_df = payload_df[payload_df["payload_status"] != "ready"]
            for _, row in failed_df.iterrows():
                rows.append([
                    "payload",
                    str(row.get("upload_name") or ""),
                    "",
                    str(row.get("payload_status") or ""),
                    str(row.get("payload_error") or ""),
                ])

        table.setRowCount(len(rows))
        for row_index, values in enumerate(rows):
            for col_index, value in enumerate(values):
                table.setItem(row_index, col_index, QTableWidgetItem(value))

        blocking_count = sum(1 for row in rows if row[3] not in {"matched", "PRECONSTRUCTION_REQUIRED", ""})
        summary_label.setText(
            f"검증 결과 {len(rows)}건, 차단 이슈 {'있음' if has_blocking_issues else '없음'}, 표시 행 {len(rows)}"
        )
        page.has_blocking_issues = has_blocking_issues
        if has_blocking_issues:
            status_label.setText("차단 이슈가 있어 업로드 단계로 이동할 수 없습니다.")
        else:
            status_label.setText("검증을 통과했습니다.")

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

    page = QWidget()
    layout = QVBoxLayout(page)
    title = QLabel("업로드")
    title.setStyleSheet("font-size: 20px; font-weight: 600;")
    layout.addWidget(title)

    page.progress_bar = QProgressBar()
    layout.addWidget(page.progress_bar)

    page.current_label = QLabel("현재 항목: -")
    page.counter_label = QLabel("성공 0 / 실패 0 / 재시도 0")
    page.status_label = QLabel("준비")
    layout.addWidget(page.current_label)
    layout.addWidget(page.counter_label)
    layout.addWidget(page.status_label)

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
    layout.addWidget(page.log_view)

    page.response_view = QPlainTextEdit()
    page.response_view.setReadOnly(True)
    layout.addWidget(page.response_view)

    buttons = QHBoxLayout()
    page.start_button = QPushButton("시작")
    page.pause_button = QPushButton("일시정지")
    page.resume_button = QPushButton("재개")
    page.cancel_button = QPushButton("중단")
    page.result_button = QPushButton("결과 화면으로 이동")
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

    def reset(total_count: int) -> None:
        page.progress_bar.setMaximum(max(total_count, 1))
        page.progress_bar.setValue(0)
        page.current_label.setText("현재 항목: -")
        page.counter_label.setText("성공 0 / 실패 0 / 재시도 0")
        page.status_label.setText("준비")
        page.log_view.clear()
        page.response_view.clear()
        page.result_button.setEnabled(False)

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
    title = QLabel("결과")
    title.setStyleSheet("font-size: 20px; font-weight: 600;")
    layout.addWidget(title)

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
            table.setColumnCount(len(df.columns))
            table.setHorizontalHeaderLabels([str(col) for col in df.columns])
            table.setRowCount(len(df))
            for row_index, (_, row) in enumerate(df.iterrows()):
                for col_index, column_name in enumerate(df.columns):
                    table.setItem(row_index, col_index, QTableWidgetItem(str(row.get(column_name) or "")))

        failed_df = upload_result.get("failed_df")
        if failed_df is not None and not getattr(failed_df, "empty", True) and "error_response_json" in failed_df.columns:
            page.response_view.setPlainText(str(failed_df.iloc[0].get("error_response_json") or ""))
        else:
            page.response_view.clear()

    previous_button.clicked.connect(lambda: page.request_previous())
    restart_button.clicked.connect(lambda: page.request_restart())
    page.set_results = set_results
    return page
