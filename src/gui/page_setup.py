from __future__ import annotations

from .page_common import *  # noqa: F403
def create_settings_page(
    settings_store,
    initial_settings,
    on_settings_changed,
    on_theme_changed=None,
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
    QComboBox = qt["QComboBox"]
    QFileDialog = qt["QFileDialog"]
    QSpinBox = qt["QSpinBox"]
    QDoubleSpinBox = qt["QDoubleSpinBox"]
    QPushButton = qt["QPushButton"]
    QToolButton = qt["QToolButton"]
    Qt = qt["Qt"]

    page = QWidget()
    page.setObjectName("settings_page")
    layout = QVBoxLayout(page)
    _configure_page_layout(layout, top_align=True)

    form = QFormLayout()
    _configure_form_layout(form)
    base_url = QLineEdit(initial_settings.base_url)
    username = QLineEdit(initial_settings.username)
    password = QLineEdit(initial_settings.password)
    password.setEchoMode(QLineEdit.EchoMode.Password)
    save_password = QCheckBox("비밀번호 저장")
    save_password.setChecked(initial_settings.save_password)
    mode_toggle = QPushButton()
    mode_toggle.setObjectName("mode_toggle")
    mode_toggle.setCheckable(True)
    mode_toggle.setChecked(bool(getattr(initial_settings, "offline_mode", False)))
    mode_toggle.setToolTip("저장된 schema/config snapshot으로 검증하는 테스트 모드입니다.")
    mode_badge = QLabel("테스트 모드")
    mode_badge.setObjectName("mode_badge")
    mode_badge.hide()
    mode_row_widget = QWidget()
    mode_row = QHBoxLayout(mode_row_widget)
    _configure_inline_layout(mode_row)
    mode_row.addStretch(1)
    mode_row.addWidget(mode_badge, 0, Qt.AlignmentFlag.AlignVCenter)
    mode_row.addWidget(mode_toggle, 0, Qt.AlignmentFlag.AlignVCenter)
    offline_schema_path = QLineEdit(str(getattr(initial_settings, "offline_schema_path", "") or ""))
    offline_schema_button = QPushButton("스키마 선택")
    offline_config_path = QLineEdit(
        str(getattr(initial_settings, "offline_tracker_configuration_path", "") or "")
    )
    offline_config_button = QPushButton("설정 선택")
    theme_combo = QComboBox()
    upload_mode_combo = QComboBox()
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
        offline_schema_path,
        offline_config_path,
        theme_combo,
        upload_mode_combo,
    ):
        _configure_form_field(field_widget)

    offline_schema_row_widget = QWidget()
    offline_schema_row = QHBoxLayout(offline_schema_row_widget)
    _configure_inline_layout(offline_schema_row)
    offline_schema_row.addWidget(offline_schema_path, 1)
    offline_schema_row.addWidget(offline_schema_button)

    offline_config_row_widget = QWidget()
    offline_config_row = QHBoxLayout(offline_config_row_widget)
    _configure_inline_layout(offline_config_row)
    offline_config_row.addWidget(offline_config_path, 1)
    offline_config_row.addWidget(offline_config_button)

    form.addRow("Base URL", base_url)
    form.addRow("Username", username)
    form.addRow("Password", password)
    form.addRow("", save_password)
    form.addRow("작업 모드", upload_mode_combo)
    form.addRow("테마", theme_combo)
    form.addRow("", mode_row_widget)
    form_container = QWidget()
    form_container.setLayout(form)
    _configure_constrained_panel(form_container, max_width=WIDE_FORM_PANEL_MAX_WIDTH)
    layout.addWidget(form_container)

    offline_card = QFrame()
    offline_card.setObjectName("advanced_card")
    _configure_constrained_panel(offline_card, max_width=WIDE_FORM_PANEL_MAX_WIDTH)
    offline_layout = QVBoxLayout(offline_card)
    _configure_card_layout(offline_layout)
    offline_description = QLabel("테스트 모드에서만 사용하는 snapshot 경로입니다.")
    offline_description.setObjectName("section_label")
    offline_layout.addWidget(offline_description)
    offline_form = QFormLayout()
    _configure_form_layout(offline_form)
    offline_form.setContentsMargins(0, 0, 0, 0)
    offline_form.addRow("Schema Snapshot", offline_schema_row_widget)
    offline_form.addRow("Config Snapshot", offline_config_row_widget)
    offline_layout.addLayout(offline_form)
    layout.addWidget(offline_card)

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
    _configure_constrained_panel(advanced_card, max_width=WIDE_FORM_PANEL_MAX_WIDTH)
    advanced_layout = QVBoxLayout(advanced_card)
    _configure_card_layout(advanced_layout)

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
    _configure_constrained_panel(status_label, max_width=WIDE_FORM_PANEL_MAX_WIDTH)
    layout.addWidget(status_label)
    page._current_settings = initial_settings

    buttons = QHBoxLayout()
    _configure_inline_layout(buttons)
    load_button = QPushButton("불러오기")
    save_button = QPushButton("저장")
    next_button = QPushButton("다음")
    next_button.setObjectName("primary_button")
    next_button.setEnabled(
        bool(
            getattr(initial_settings, "offline_mode", False)
            and str(getattr(initial_settings, "offline_schema_path", "") or "").strip()
            and not gui_upload_mode_supports_update(getattr(initial_settings, "upload_mode", None))
        ) or bool(initial_settings.base_url and initial_settings.username and initial_settings.password)
    )
    buttons.addWidget(load_button)
    buttons.addWidget(save_button)
    buttons.addStretch(1)
    buttons.addWidget(next_button)
    layout.addLayout(buttons)
    layout.addStretch(1)

    def _update_next_button_state() -> None:
        blocks_offline_mode = gui_upload_mode_supports_update(upload_mode_combo.currentData())
        if mode_toggle.isChecked():
            next_button.setEnabled(
                bool(Path(offline_schema_path.text().strip()).is_file()) and not blocks_offline_mode
            )
            return
        next_button.setEnabled(bool(base_url.text().strip() and username.text().strip() and password.text()))

    def _request_settings_reflow() -> None:
        request_content_reflow = getattr(page, "request_content_reflow", None)
        if callable(request_content_reflow):
            request_content_reflow(
                allow_grow=bool(
                    mode_toggle.isChecked()
                    or advanced_toggle.isChecked()
                    or status_label.isVisible()
                )
            )

    def _sync_offline_mode_state() -> None:
        is_offline = bool(mode_toggle.isChecked())
        mode_toggle.setText(_settings_mode_toggle_text(is_offline))
        mode_badge.setVisible(is_offline)
        mode_badge.setToolTip(_settings_mode_description(is_offline))
        mode_toggle.setToolTip(_settings_mode_description(is_offline))
        base_url.setEnabled(not is_offline)
        username.setEnabled(not is_offline)
        password.setEnabled(not is_offline)
        save_password.setEnabled(not is_offline)
        offline_card.setVisible(is_offline)
        offline_schema_path.setEnabled(is_offline)
        offline_schema_button.setEnabled(is_offline)
        offline_config_path.setEnabled(is_offline)
        offline_config_button.setEnabled(is_offline)
        _update_next_button_state()
        _request_settings_reflow()

    def _collect_settings():
        current_settings = getattr(page, "_current_settings", initial_settings)
        return type(initial_settings)(
            theme_name=normalize_gui_theme_name(theme_combo.currentData()),
            upload_mode=normalize_gui_upload_mode(upload_mode_combo.currentData()),
            window_width=int(getattr(current_settings, "window_width", 1160) or 1160),
            window_height=int(getattr(current_settings, "window_height", 780) or 780),
            window_is_maximized=bool(getattr(current_settings, "window_is_maximized", False)),
            window_is_fullscreen=bool(getattr(current_settings, "window_is_fullscreen", False)),
            base_url=base_url.text().strip(),
            username=username.text().strip(),
            password=password.text(),
            save_password=save_password.isChecked(),
            offline_mode=mode_toggle.isChecked(),
            offline_schema_path=offline_schema_path.text().strip(),
            offline_tracker_configuration_path=offline_config_path.text().strip(),
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
        _request_settings_reflow()

    def _apply_settings(loaded) -> None:
        page._current_settings = loaded
        base_url.setText(loaded.base_url)
        username.setText(loaded.username)
        password.setText(loaded.password)
        save_password.setChecked(loaded.save_password)
        _select_theme(normalize_gui_theme_name(getattr(loaded, "theme_name", None)))
        _select_upload_mode(normalize_gui_upload_mode(getattr(loaded, "upload_mode", None)))
        mode_toggle.setChecked(bool(getattr(loaded, "offline_mode", False)))
        offline_schema_path.setText(str(getattr(loaded, "offline_schema_path", "") or ""))
        offline_config_path.setText(str(getattr(loaded, "offline_tracker_configuration_path", "") or ""))
        header_row.setValue(loaded.excel_header_row)
        summary_column.setText(loaded.summary_column)
        sheet_name.setText(loaded.excel_sheet_name)
        retry_delay.setValue(loaded.rate_limit_retry_delay_seconds)
        retry_count.setValue(loaded.rate_limit_max_retries)
        output_dir.setText(loaded.output_dir)
        _sync_offline_mode_state()

    def _select_theme(theme_name: str) -> None:
        normalized_theme = normalize_gui_theme_name(theme_name)
        index = theme_combo.findData(normalized_theme)
        if index < 0:
            index = 0
        theme_combo.setCurrentIndex(index)

    def _select_upload_mode(upload_mode: str) -> None:
        normalized_mode = normalize_gui_upload_mode(upload_mode)
        index = upload_mode_combo.findData(normalized_mode)
        if index < 0:
            index = 0
        upload_mode_combo.setCurrentIndex(index)

    def _preview_theme() -> None:
        if callable(on_theme_changed):
            on_theme_changed(normalize_gui_theme_name(theme_combo.currentData()))

    def _choose_snapshot_path(target_widget, *, title: str) -> None:
        start_path = target_widget.text().strip() or str(getattr(page, "_current_settings", initial_settings).last_file_path or "")
        selected, _ = QFileDialog.getOpenFileName(
            page,
            title,
            start_path,
            "JSON Files (*.json)",
        )
        if selected:
            target_widget.setText(str(selected))

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
        if current.offline_mode:
            if gui_upload_mode_supports_update(current.upload_mode):
                _set_status("테스트 모드에서는 기존 수정 또는 혼합 처리를 지원하지 않습니다.")
                return
            if not current.offline_schema_path:
                _set_status("테스트 모드에서는 schema snapshot JSON 경로가 필요합니다.")
                return
            if not Path(current.offline_schema_path).is_file():
                _set_status("선택한 schema snapshot JSON 파일을 찾을 수 없습니다.")
                return
            if current.offline_tracker_configuration_path and not Path(current.offline_tracker_configuration_path).is_file():
                _set_status("선택한 tracker configuration snapshot JSON 파일을 찾을 수 없습니다.")
                return
        elif not current.base_url or not current.username or not current.password:
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
    mode_toggle.toggled.connect(lambda _: _sync_offline_mode_state())
    offline_schema_button.clicked.connect(
        lambda: _choose_snapshot_path(offline_schema_path, title="테스트 schema snapshot 선택")
    )
    offline_config_button.clicked.connect(
        lambda: _choose_snapshot_path(offline_config_path, title="테스트 tracker configuration 선택")
    )
    offline_schema_path.textChanged.connect(lambda _: _update_next_button_state())
    upload_mode_combo.currentIndexChanged.connect(lambda _: _update_next_button_state())
    theme_combo.currentIndexChanged.connect(lambda _: _preview_theme())
    advanced_toggle.toggled.connect(
        lambda checked: (
            advanced_card.setVisible(checked),
            advanced_toggle.setArrowType(
                Qt.ArrowType.DownArrow if checked else Qt.ArrowType.RightArrow
            ),
            _request_settings_reflow(),
        )
    )

    for theme_key, theme_label in GUI_THEME_CHOICES:
        theme_combo.addItem(theme_label, theme_key)
    for upload_mode, upload_mode_label in _settings_upload_mode_choices():
        upload_mode_combo.addItem(upload_mode_label, upload_mode)
    _select_theme(normalize_gui_theme_name(getattr(initial_settings, "theme_name", None)))
    _select_upload_mode(normalize_gui_upload_mode(getattr(initial_settings, "upload_mode", None)))
    _sync_offline_mode_state()
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
    _configure_page_layout(layout, top_align=True)

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
    form_container = QWidget()
    form_container.setLayout(form)
    _configure_constrained_panel(form_container)
    layout.addWidget(form_container)

    status_label = QLabel(_project_selection_status_text(bool(getattr(initial_settings, "offline_mode", False))))
    status_label.setObjectName("status_label")
    _configure_constrained_panel(status_label)
    layout.addWidget(status_label)

    buttons = QHBoxLayout()
    _configure_inline_layout(buttons)
    previous_button = QPushButton("이전")
    refresh_button = QPushButton(
        _project_selection_refresh_button_text(bool(getattr(initial_settings, "offline_mode", False)))
    )
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

    def _clear_combo_items() -> None:
        project_combo.blockSignals(True)
        tracker_combo.blockSignals(True)
        project_combo.clear()
        tracker_combo.clear()
        project_combo.setEnabled(False)
        tracker_combo.setEnabled(False)
        project_combo.blockSignals(False)
        tracker_combo.blockSignals(False)
        _update_next_button_state()

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

    def _sync_from_settings(*, auto_load: bool = False) -> None:
        settings = _current_settings()
        is_offline = bool(getattr(settings, "offline_mode", False))
        refresh_button.setText(_project_selection_refresh_button_text(is_offline))
        source_signature = _project_selection_source_signature(settings)
        source_changed = source_signature != getattr(page, "_source_signature", None)
        if source_changed:
            page._source_signature = source_signature
            page.selected_project_id = str(getattr(settings, "default_project_id", "") or "")
            page.selected_tracker_id = str(getattr(settings, "default_tracker_id", "") or "")
            _clear_combo_items()
            status_label.setText(_project_selection_status_text(is_offline))
        elif not str(status_label.text() or "").strip():
            status_label.setText(_project_selection_status_text(is_offline))

        if auto_load and is_offline and project_combo.count() == 0:
            _refresh_projects()

    def _refresh_projects() -> None:
        settings = _current_settings()
        try:
            projects = on_connection_test(settings)
        except Exception as exc:
            message = f"프로젝트 조회 실패: {exc}"
            status_label.setText(message)
            if callable(on_error):
                on_error("프로젝트 조회 실패", message)
            _clear_combo_items()
            page.selected_project_id = ""
            page.selected_tracker_id = ""
            _update_next_button_state()
            return
        _set_items(project_combo, projects, page.selected_project_id)
        status_label.setText(
            "테스트 프로젝트 목록을 불러왔습니다."
            if bool(getattr(settings, "offline_mode", False))
            else "프로젝트 목록을 불러왔습니다."
        )
        if project_combo.count() > 0:
            selected_index = project_combo.currentIndex()
            if selected_index < 0:
                selected_index = 0
                project_combo.setCurrentIndex(0)
            _handle_project_changed(selected_index)

    def _refresh_projects_for_current_settings() -> None:
        _sync_from_settings(auto_load=False)
        _refresh_projects()

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
        if bool(getattr(settings, "offline_mode", False)):
            status_label.setText("테스트 tracker snapshot 정보를 불러왔습니다.")
        else:
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
    refresh_button.clicked.connect(_refresh_projects_for_current_settings)
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
    page.on_page_shown = lambda: _sync_from_settings(auto_load=True)
    _sync_from_settings(auto_load=False)
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
    _configure_page_layout(layout)

    form = QFormLayout()
    _configure_form_layout(form)
    file_path = QLineEdit(initial_settings.last_file_path)
    file_path.setReadOnly(True)
    file_button = QPushButton("파일 선택")
    file_row_widget = QWidget()
    file_row = QHBoxLayout(file_row_widget)
    _configure_inline_layout(file_row)
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
    form_container = QWidget()
    form_container.setLayout(form)
    _configure_constrained_panel(form_container, max_width=WIDE_FORM_PANEL_MAX_WIDTH)
    layout.addWidget(form_container)

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
    _configure_data_table(preview_table, minimum_height=PREVIEW_TABLE_MIN_HEIGHT)
    _configure_table_columns(preview_table, [180, 180, 160, 160])
    page.preview_table = preview_table
    layout.addWidget(preview_table, 1)

    status_label = QLabel("Excel 파일과 옵션을 정한 뒤 '데이터 불러오기'를 누르세요.")
    status_label.setObjectName("status_label")
    _configure_constrained_panel(status_label, max_width=WIDE_FORM_PANEL_MAX_WIDTH)
    layout.addWidget(status_label)

    buttons = QHBoxLayout()
    _configure_inline_layout(buttons)
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


def create_root_item_page(on_preview_requested, *, page_mode: str = "structure"):
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

    is_structure_page = str(page_mode or "structure").strip() != "fields"
    is_field_page = not is_structure_page

    page = QWidget()
    layout = QVBoxLayout(page)
    _configure_page_layout(layout)

    description_label = QLabel(
        (
            "업로드 전에 생성할 상단 폴더 구조를 설정합니다. "
            "파일별 루트 폴더와 파일 내부 특정 컬럼 값별 그룹 폴더를 각각 독립적으로 사용할 수 있습니다."
            if is_structure_page
            else "앞 단계에서 정한 상단 폴더 구조에 어떤 필드 값을 넣을지 설정합니다."
        )
    )
    description_label.setWordWrap(True)
    description_label.setObjectName("section_label")
    _configure_constrained_panel(description_label, max_width=WIDE_FORM_PANEL_MAX_WIDTH)
    layout.addWidget(description_label)

    enable_root_item = QCheckBox("파일별 최상단 폴더 생성")
    enable_root_item.setChecked(True)
    layout.addWidget(enable_root_item)

    enable_group_folder = QCheckBox("엑셀 컬럼별 그룹 폴더 생성")
    enable_group_folder.setChecked(False)
    layout.addWidget(enable_group_folder)

    structure_summary_label = QLabel("")
    structure_summary_label.setWordWrap(True)
    structure_summary_label.setObjectName("status_label")
    _configure_constrained_panel(structure_summary_label, max_width=WIDE_FORM_PANEL_MAX_WIDTH)
    layout.addWidget(structure_summary_label)

    form = QFormLayout()
    _configure_form_layout(form)
    group_by_column = QComboBox()
    group_by_column.addItem("사용 안 함", "")
    regex_target = QComboBox()
    regex_target.addItem("파일명(확장자 제외)", "file_stem")
    regex_target.addItem("전체 파일명", "file_name")
    regex_pattern = QLineEdit()
    regex_pattern.setPlaceholderText(r"예: ^(?P<project>[A-Z]+)_(?P<title>.+)$")
    _configure_form_field(group_by_column)
    _configure_form_field(regex_target)
    _configure_form_field(regex_pattern, minimum_width=320)
    form.addRow("그룹 컬럼", group_by_column)
    form.addRow("정규식 대상", regex_target)
    form.addRow("정규식", regex_pattern)
    form_container = QWidget()
    form_container.setLayout(form)
    _configure_constrained_panel(form_container, max_width=WIDE_FORM_PANEL_MAX_WIDTH)
    layout.addWidget(form_container)

    preview_label = QLabel("상단 데이터 소스 미리보기" if is_structure_page else "상단 폴더 미리보기")
    preview_label.setObjectName("section_label")
    layout.addWidget(preview_label)

    preview_table = QTableWidget(0, 0)
    preview_table.setAlternatingRowColors(True)
    _configure_data_table(preview_table, minimum_height=PREVIEW_TABLE_MIN_HEIGHT)
    page.preview_table = preview_table
    layout.addWidget(preview_table, 1)

    field_label = QLabel("상단 폴더 필드 매핑")
    field_label.setObjectName("section_label")
    layout.addWidget(field_label)

    field_table = QTableWidget(0, 6)
    field_table.setHorizontalHeaderLabels(["사용", "Codebeamer 필드", "타입", "필수", "값 방식", "값"])
    field_table.setAlternatingRowColors(True)
    _configure_data_table(field_table, minimum_height=PRIMARY_TABLE_MIN_HEIGHT)
    _configure_table_columns(field_table, [80, 240, 180, 90, 160, 240])
    page.field_table = field_table
    layout.addWidget(field_table, 2)

    status_label = QLabel("")
    status_label.setObjectName("status_label")
    _configure_constrained_panel(status_label, max_width=WIDE_FORM_PANEL_MAX_WIDTH)
    layout.addWidget(status_label)

    buttons = QHBoxLayout()
    _configure_inline_layout(buttons)
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

    enable_root_item.setVisible(is_structure_page)
    enable_group_folder.setVisible(is_structure_page)
    form_container.setVisible(is_structure_page)
    structure_summary_label.setVisible(is_field_page)
    field_label.setVisible(is_field_page)
    field_table.setVisible(is_field_page)

    def _sync_root_enabled_state(file_root_enabled: bool, group_enabled: bool) -> None:
        has_any_root = file_root_enabled or group_enabled
        group_by_column.setEnabled(group_enabled)
        regex_target.setEnabled(has_any_root)
        regex_pattern.setEnabled(has_any_root)
        preview_table.setEnabled(has_any_root)
        field_table.setEnabled(has_any_root)
        preview_label.setEnabled(has_any_root)
        field_label.setEnabled(has_any_root)
        if group_enabled:
            field_label.setText("그룹 폴더 필드 매핑")
        elif file_root_enabled:
            field_label.setText("파일 루트 필드 매핑")
        else:
            field_label.setText("상단 데이터 필드 매핑")

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
        if not field_assignments and page._current_preview_context is not None:
            field_assignments = {
                str(schema_field): dict(assignment)
                for schema_field, assignment in dict(getattr(page._current_preview_context, "field_assignments", {}) or {}).items()
                if str(schema_field).strip() and isinstance(assignment, dict)
            }
        group_enabled = bool(enable_group_folder.isChecked())
        return {
            "enabled": bool(enable_root_item.isChecked()),
            "group_enabled": group_enabled,
            "root_mode": ROOT_ITEM_MODE_GROUP_BY_COLUMN if group_enabled else ROOT_ITEM_MODE_FILE,
            "group_by_column": str(group_by_column.currentData() or "").strip(),
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
            options.append(("소스 값", ROOT_ASSIGNMENT_MODE_FILE_SOURCE))
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
            selected_index = value_combo.findData(selected_value)
            value_combo.setCurrentIndex(selected_index if selected_index >= 0 else 0)
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

    def _bind_editable_combo_commit(combo, callback) -> None:
        line_edit = combo.lineEdit()
        if line_edit is None:
            return
        if bool(line_edit.property("_codex_commit_bound")):
            return
        line_edit.setProperty("_codex_commit_bound", True)
        line_edit.editingFinished.connect(callback)

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
        group_by_column.blockSignals(True)
        enable_root_item.blockSignals(True)
        enable_group_folder.blockSignals(True)
        enable_root_item.setChecked(bool(getattr(preview_context, "enabled", True)))
        enable_group_folder.setChecked(bool(getattr(preview_context, "group_enabled", False)))
        group_by_column.clear()
        group_by_column.addItem("사용 안 함", "")
        for column_name in getattr(preview_context, "group_column_options", []):
            group_by_column.addItem(str(column_name), str(column_name))
        group_index = group_by_column.findData(str(getattr(preview_context, "group_by_column", "") or ""))
        group_by_column.setCurrentIndex(group_index if group_index >= 0 else 0)
        regex_pattern.setText(str(preview_context.regex_pattern or ""))
        target_index = regex_target.findData(str(preview_context.regex_target or "file_stem"))
        regex_target.setCurrentIndex(target_index if target_index >= 0 else 0)
        regex_pattern.blockSignals(False)
        regex_target.blockSignals(False)
        group_by_column.blockSignals(False)
        enable_root_item.blockSignals(False)
        enable_group_folder.blockSignals(False)
        _sync_root_enabled_state(
            bool(getattr(preview_context, "enabled", True)),
            bool(getattr(preview_context, "group_enabled", False)),
        )
        if is_field_page:
            structure_parts: list[str] = []
            if bool(getattr(preview_context, "enabled", False)):
                structure_parts.append("파일별 최상단 폴더")
            if bool(getattr(preview_context, "group_enabled", False)):
                group_name = str(getattr(preview_context, "group_by_column", "") or "").strip()
                structure_parts.append(
                    f"그룹 폴더 ({group_name})" if group_name else "그룹 폴더"
                )
            structure_summary_label.setText(
                "현재 구조: " + (", ".join(structure_parts) if structure_parts else "상단 폴더 생성 안 함")
            )

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
            _bind_editable_combo_commit(value_combo, _refresh_preview)
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
                _bind_editable_combo_commit(value_widget, _refresh_preview)
                _refresh_preview()

            def _on_value_changed(_text, *, value_widget=value_combo):
                if bool(value_widget.isEditable()):
                    return
                _refresh_preview()

            enabled_widget.toggled.connect(_on_enabled_toggled)
            mode_combo.currentIndexChanged.connect(_on_mode_changed)
            value_combo.currentTextChanged.connect(_on_value_changed)

        _configure_table_columns(field_table, [80, 240, 180, 90, 160, 240])
        status_label.setText(str(preview_context.status_message or ""))
        next_button.setEnabled(not bool(preview_context.has_blocking_issues))
        page._loaded = True

    previous_button.clicked.connect(lambda: page.request_previous())
    next_button.clicked.connect(lambda: page.request_next())
    regex_pattern.textChanged.connect(lambda _text: _refresh_preview())
    regex_target.currentIndexChanged.connect(lambda _index: _refresh_preview())
    group_by_column.currentIndexChanged.connect(lambda _index: _refresh_preview())
    enable_root_item.toggled.connect(
        lambda checked: (
            _sync_root_enabled_state(bool(checked), bool(enable_group_folder.isChecked())),
            _refresh_preview(),
        )
    )
    enable_group_folder.toggled.connect(
        lambda checked: (
            _sync_root_enabled_state(bool(enable_root_item.isChecked()), bool(checked)),
            _refresh_preview(),
        )
    )

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
    _configure_page_layout(layout)

    body = QPlainTextEdit()
    body.setReadOnly(True)
    body.setPlainText(description)
    layout.addWidget(body, 1)

    buttons = QHBoxLayout()
    _configure_inline_layout(buttons)
    previous_button = QPushButton("이전")
    next_button = QPushButton("다음")
    buttons.addWidget(previous_button)
    buttons.addStretch(1)
    buttons.addWidget(next_button)
    layout.addLayout(buttons)

    previous_button.clicked.connect(lambda: page.request_previous())
    next_button.clicked.connect(lambda: page.request_next())
    return page
