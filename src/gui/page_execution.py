from __future__ import annotations

from .page_common import *  # noqa: F403
def create_mapping_page(on_validate_requested, on_error=None):
    """`create_mapping_page` 화면을 구성한다."""
    qt = _require_qt()
    Qt = qt["Qt"]
    QColor = qt["QColor"]
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
    QTabWidget = qt["QTabWidget"]

    page = QWidget()
    layout = QVBoxLayout(page)
    _configure_page_layout(layout)
    info_label = QLabel("")
    info_label.setObjectName("section_label")
    _configure_constrained_panel(info_label, max_width=WIDE_FORM_PANEL_MAX_WIDTH)
    layout.addWidget(info_label)

    mapping_tabs = QTabWidget()
    mapping_tabs.setDocumentMode(True)

    mapping_tab = QWidget()
    mapping_tab_layout = QVBoxLayout(mapping_tab)
    _configure_inline_layout(mapping_tab_layout)
    table = QTableWidget(0, 7)
    table.setHorizontalHeaderLabels(["생성", "수정", "Excel 컬럼", "Codebeamer 필드", "타입", "다중값", "지원 여부"])
    table.setAlternatingRowColors(True)
    _configure_data_table(table, minimum_height=PRIMARY_TABLE_MIN_HEIGHT)
    _configure_table_columns(table, [70, 70, 220, 220, 170, 90, 90])
    page.mapping_table = table
    mapping_tab_layout.addWidget(table, 1)
    mapping_tabs.addTab(mapping_tab, "컬럼 매핑")

    defaults_tab = QWidget()
    defaults_tab_layout = QVBoxLayout(defaults_tab)
    _configure_inline_layout(defaults_tab_layout)
    default_label = QLabel("공통 기본값")
    default_label.setObjectName("section_label")
    defaults_tab_layout.addWidget(default_label)

    default_help_label = QLabel("행 값이 있으면 행 값이 우선하고, 비어 있으면 아래 기본값을 사용합니다.")
    default_help_label.setWordWrap(True)
    _configure_constrained_panel(default_help_label, max_width=WIDE_FORM_PANEL_MAX_WIDTH)
    defaults_tab_layout.addWidget(default_help_label)

    default_table = QTableWidget(0, 5)
    default_table.setHorizontalHeaderLabels(["적용", "Codebeamer 필드", "타입", "기본값", "필수"])
    default_table.setAlternatingRowColors(True)
    _configure_data_table(default_table, minimum_height=SECONDARY_TABLE_MIN_HEIGHT)
    _configure_table_columns(default_table, [70, 220, 170, 240, 90])
    page.default_table = default_table
    defaults_tab_layout.addWidget(default_table, 1)
    mapping_tabs.addTab(defaults_tab, "기본값")

    tracker_tab = QWidget()
    tracker_tab_layout = QVBoxLayout(tracker_tab)
    _configure_inline_layout(tracker_tab_layout)
    tracker_item_label = QLabel("Tracker Item 처리")
    tracker_item_label.setObjectName("section_label")
    tracker_tab_layout.addWidget(tracker_item_label)

    tracker_item_help_label = QLabel(
        "TrackerItemChoiceField 는 정규식으로 ID를 추출하거나, configuration 기반 source tracker에서 이름으로 미리 조회할 수 있습니다."
    )
    tracker_item_help_label.setWordWrap(True)
    _configure_constrained_panel(tracker_item_help_label, max_width=WIDE_FORM_PANEL_MAX_WIDTH)
    tracker_tab_layout.addWidget(tracker_item_help_label)

    tracker_item_table = QTableWidget(0, 7)
    tracker_item_table.setHorizontalHeaderLabels(["Excel 컬럼", "Codebeamer 필드", "방식", "다건 결과", "정규식", "예시", "조회 소스"])
    tracker_item_table.setAlternatingRowColors(True)
    _configure_data_table(tracker_item_table, minimum_height=SECONDARY_TABLE_MIN_HEIGHT)
    _configure_table_columns(tracker_item_table, [220, 220, 140, 160, 260, 320, 200])
    page.tracker_item_table = tracker_item_table
    tracker_tab_layout.addWidget(tracker_item_table, 1)
    mapping_tabs.addTab(tracker_tab, "Tracker Item")

    page.mapping_tabs = mapping_tabs
    layout.addWidget(mapping_tabs, 1)

    status_label = QLabel("")
    status_label.setObjectName("status_label")
    _configure_constrained_panel(status_label, max_width=WIDE_FORM_PANEL_MAX_WIDTH)
    layout.addWidget(status_label)

    buttons = QHBoxLayout()
    _configure_inline_layout(buttons)
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
    page._upload_preview_df = None

    def _mark_dirty() -> None:
        """`mark_dirty` 상태를 표시한다."""
        page._mapping_validated = False
        next_button.setEnabled(False)

    def _tracker_item_candidates(mapping: dict[str, str]) -> list[dict[str, object]]:
        """`tracker_item_candidates` 관련 처리를 수행한다."""
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
                "query_status": str(schema_row.get("tracker_item_query_status") or "unavailable").strip(),
            })
        return candidates

    def _tracker_item_query_strategy_options() -> list[tuple[str, str]]:
        """`tracker_item_query_strategy_options` 관련 처리를 수행한다."""
        return [
            ("가장 비슷한 값", TrackerItemQueryMatchStrategy.BEST.value),
            ("첫 번째 결과", TrackerItemQueryMatchStrategy.FIRST.value),
            ("마지막 결과", TrackerItemQueryMatchStrategy.LAST.value),
            ("오류로 처리", TrackerItemQueryMatchStrategy.ERROR.value),
        ]

    def _sync_tracker_item_controls(mode_combo, regex_edit, strategy_combo) -> None:
        """`sync_tracker_item_controls` 상태를 동기화한다."""
        is_regex = mode_combo.currentData() == TrackerItemResolutionMode.REGEX.value
        regex_edit.setEnabled(is_regex)
        strategy_combo.setEnabled(not is_regex)
        regex_edit.setPlaceholderText(
            "ID를 추출할 정규식"
            if is_regex
            else "query 모드에서는 선택 파일 전체 값을 중복 제거 후 사전 조회합니다."
        )

    def _tracker_item_example_text(df_column: str, schema_field: str, mode: str, regex_pattern: str) -> str:
        """`tracker_item_example_text` 관련 처리를 수행한다."""
        if mode != TrackerItemResolutionMode.REGEX.value:
            return "query 모드에서는 미사용"
        schema_row = page._schema_rows_by_name.get(schema_field, {})
        sample_values = _tracker_item_sample_values(page._upload_preview_df, df_column)
        return _build_tracker_item_regex_preview_text(
            sample_values,
            pattern=regex_pattern,
            multiple_values=bool(schema_row.get("multiple_values", False)),
        )

    def _refresh_tracker_item_example(row_index: int, df_column: str, schema_field: str, mode_combo, regex_edit) -> None:
        """`refresh_tracker_item_example` 표시를 새로 고친다."""
        example_item = tracker_item_table.item(row_index, 5)
        if example_item is None:
            example_item = QTableWidgetItem("")
            tracker_item_table.setItem(row_index, 5, example_item)
        example_item.setText(
            _tracker_item_example_text(
                df_column,
                schema_field,
                str(mode_combo.currentData() or TrackerItemResolutionMode.REGEX.value),
                regex_edit.text().strip(),
            )
        )

    def _populate_tracker_item_table(mapping: dict[str, str], tracker_item_settings: dict[str, dict[str, object]]) -> None:
        """`populate_tracker_item_table` 관련 처리를 수행한다."""
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
            query_status = str(candidate.get("query_status") or "unavailable").strip()
            selected_setting = page._tracker_item_settings.get(schema_field, {})
            default_mode = (
                TrackerItemResolutionMode.QUERY.value
                if supports_query
                else TrackerItemResolutionMode.REGEX.value
            )
            selected_mode = str(selected_setting.get("mode") or default_mode).strip()
            if selected_mode == TrackerItemResolutionMode.QUERY.value and not supports_query:
                selected_mode = TrackerItemResolutionMode.REGEX.value
            selected_query_strategy = str(
                selected_setting.get("query_match_strategy")
                or TrackerItemQueryMatchStrategy.BEST.value
            ).strip()
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

            strategy_combo = QComboBox()
            for label, value in _tracker_item_query_strategy_options():
                strategy_combo.addItem(label, value)
            strategy_index = strategy_combo.findData(selected_query_strategy)
            strategy_combo.setCurrentIndex(strategy_index if strategy_index >= 0 else 0)
            tracker_item_table.setCellWidget(row_index, 3, strategy_combo)

            regex_edit = QLineEdit(selected_regex)
            tracker_item_table.setCellWidget(row_index, 4, regex_edit)
            _sync_tracker_item_controls(mode_combo, regex_edit, strategy_combo)
            tracker_item_table.setItem(row_index, 5, QTableWidgetItem(""))

            source_text = (
                ", ".join(f"tracker {tracker_id}" for tracker_id in source_tracker_ids)
                if source_tracker_ids
                else (
                    "미지원 구조(정규식만 지원)"
                    if query_status == "unsupported"
                    else "configuration source 없음"
                )
            )
            tracker_item_table.setItem(row_index, 6, QTableWidgetItem(source_text))
            _refresh_tracker_item_example(row_index, df_column, schema_field, mode_combo, regex_edit)

            mode_combo.currentIndexChanged.connect(
                lambda _index, row=row_index, column=df_column, field=schema_field, combo=mode_combo, edit=regex_edit, strategy=strategy_combo: (
                    _sync_tracker_item_controls(combo, edit, strategy),
                    _refresh_tracker_item_example(row, column, field, combo, edit),
                    _mark_dirty(),
                )
            )
            regex_edit.textChanged.connect(
                lambda _text, row=row_index, column=df_column, field=schema_field, combo=mode_combo, edit=regex_edit: (
                    _refresh_tracker_item_example(row, column, field, combo, edit),
                    _mark_dirty(),
                )
            )
            strategy_combo.currentTextChanged.connect(lambda _text: _mark_dirty())

        _configure_table_columns(tracker_item_table, [220, 220, 140, 160, 260, 320, 200])
        if candidates:
            tracker_item_help_label.setText(
                "TrackerItemChoiceField 는 정규식 ID 추출 또는 source tracker 사전 조회를 선택하고, query 다건 결과 처리 방식도 지정하세요."
            )
        else:
            tracker_item_help_label.setText("현재 매핑에는 별도 Tracker Item 처리 설정이 필요한 필드가 없습니다.")

    def _configure_default_value_widget(combo, candidate, selected_default: str) -> None:
        """`configure_default_value_widget` 관련 처리를 수행한다."""
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

    def _bind_default_value_commit(combo) -> None:
        """`bind_default_value_commit` 관련 처리를 수행한다."""
        line_edit = combo.lineEdit()
        if line_edit is None:
            return
        if bool(line_edit.property("_codex_default_dirty_bound")):
            return
        line_edit.setProperty("_codex_default_dirty_bound", True)
        line_edit.editingFinished.connect(_mark_dirty)

    def _blend_colors(base_color, accent_color, ratio: float):
        """`blend_colors` 값을 섞어 계산한다."""
        clamped_ratio = max(0.0, min(float(ratio), 1.0))
        inverse_ratio = 1.0 - clamped_ratio
        return QColor(
            int(base_color.red() * inverse_ratio + accent_color.red() * clamped_ratio),
            int(base_color.green() * inverse_ratio + accent_color.green() * clamped_ratio),
            int(base_color.blue() * inverse_ratio + accent_color.blue() * clamped_ratio),
        )

    def _mapping_row_palette() -> dict[str, object]:
        """`mapping_row_palette` 관련 처리를 수행한다."""
        palette = table.palette()
        base_color = palette.base().color()
        alternate_color = palette.alternateBase().color()
        highlight_color = palette.highlight().color()
        return {
            "row_background": _blend_colors(alternate_color, highlight_color, 0.18),
            "combo_background": _blend_colors(base_color, highlight_color, 0.20),
            "combo_border": _blend_colors(base_color, highlight_color, 0.48),
        }

    def _mapping_row_active(row_index: int) -> bool:
        """`mapping_row_active` 관련 처리를 수행한다."""
        create_widget = table.cellWidget(row_index, 0)
        update_widget = table.cellWidget(row_index, 1)
        combo = table.cellWidget(row_index, 3)
        if create_widget is None or update_widget is None or combo is None:
            return False
        if not (bool(create_widget.isChecked()) or bool(update_widget.isChecked())):
            return False
        return bool(combo.currentText().strip())

    def _apply_mapping_row_highlight(row_index: int) -> None:
        """`apply_mapping_row_highlight` 변경을 적용한다."""
        colors = _mapping_row_palette()
        is_active = _mapping_row_active(row_index)
        for column_index in (2, 4, 5, 6):
            item = table.item(row_index, column_index)
            if item is None:
                continue
            item.setData(
                Qt.ItemDataRole.BackgroundRole,
                colors["row_background"] if is_active else None,
            )
        column_item = table.item(row_index, 2)
        if column_item is not None:
            font = column_item.font()
            font.setBold(is_active)
            column_item.setFont(font)

        combo = table.cellWidget(row_index, 3)
        if combo is not None:
            if is_active:
                combo.setStyleSheet(
                    "QComboBox {"
                    f" background-color: {colors['combo_background'].name()};"
                    f" border: 1px solid {colors['combo_border'].name()};"
                    " font-weight: 600;"
                    "}"
                )
            else:
                combo.setStyleSheet("")

    def _refresh_mapping_row(row_index: int) -> None:
        """`refresh_mapping_row` 표시를 새로 고친다."""
        _apply_mapping_row_highlight(row_index)
        _populate_tracker_item_table(get_selected_mapping(), get_selected_tracker_item_settings())
        _mark_dirty()

    def _default_scope_for_upload_mode(upload_mode: str) -> dict[str, bool]:
        """`default_scope_for_upload_mode` 기본값을 계산한다."""
        normalized_mode = normalize_gui_upload_mode(upload_mode)
        if normalized_mode == GUI_UPLOAD_MODE_UPDATE:
            return {"create": False, "update": True}
        if normalized_mode == GUI_UPLOAD_MODE_UPSERT:
            return {"create": True, "update": True}
        return {"create": True, "update": False}

    def _normalize_scope(raw_scope: dict[str, object] | None, *, upload_mode: str) -> dict[str, bool]:
        """`normalize_scope` 값을 정규화한다."""
        default_scope = _default_scope_for_upload_mode(upload_mode)
        payload = dict(raw_scope or {})
        return {
            "create": bool(payload.get("create", default_scope["create"])),
            "update": bool(payload.get("update", default_scope["update"])),
        }

    def _normalize_default_value_scope(raw_scope: dict[str, object] | None, *, upload_mode: str) -> dict[str, bool]:
        """`normalize_default_value_scope` 값을 정규화한다."""
        payload = dict(raw_scope or {})
        if not payload:
            return _default_scope_for_upload_mode(upload_mode)
        normalized_scope = _normalize_scope(payload, upload_mode=upload_mode)
        normalized_mode = normalize_gui_upload_mode(upload_mode)
        if normalized_mode == GUI_UPLOAD_MODE_UPDATE:
            return _default_scope_for_upload_mode(upload_mode) if bool(normalized_scope.get("update", False)) else {"create": False, "update": False}
        if normalized_mode == GUI_UPLOAD_MODE_UPSERT:
            return _default_scope_for_upload_mode(upload_mode) if bool(normalized_scope.get("create", False) or normalized_scope.get("update", False)) else {"create": False, "update": False}
        return _default_scope_for_upload_mode(upload_mode) if bool(normalized_scope.get("create", False)) else {"create": False, "update": False}

    def _sync_mapping_scope_checkboxes(create_widget, update_widget, *, upload_mode: str) -> None:
        """`sync_mapping_scope_checkboxes` 상태를 동기화한다."""
        normalized_mode = normalize_gui_upload_mode(upload_mode)
        if normalized_mode == GUI_UPLOAD_MODE_CREATE:
            create_widget.setEnabled(True)
            update_widget.setChecked(False)
            update_widget.setEnabled(False)
            return
        if normalized_mode == GUI_UPLOAD_MODE_UPDATE:
            create_widget.setChecked(False)
            create_widget.setEnabled(False)
            update_widget.setEnabled(True)
            return
        create_widget.setEnabled(True)
        update_widget.setEnabled(True)

    def load_context(
        upload_mode: str,
        upload_columns: list[str],
        schema_df,
        selected_mapping: dict[str, str],
        selected_mapping_modes: dict[str, dict[str, bool]],
        default_value_candidates: list,
        selected_default_values: dict[str, str],
        selected_default_value_modes: dict[str, dict[str, bool]],
        selected_tracker_item_settings: dict[str, dict[str, object]],
        upload_preview_df=None,
    ) -> None:
        """`load_context` 데이터를 불러온다."""
        page._mapping_validated = False
        next_button.setEnabled(False)
        page._upload_preview_df = upload_preview_df
        normalized_upload_mode = normalize_gui_upload_mode(upload_mode)
        page._mapping_upload_mode = normalized_upload_mode
        page._schema_rows_by_name = {
            str(row["field_name"]): row
            for _, row in schema_df.iterrows()
            if row.get("field_name")
        }
        schema_field_names = sorted(page._schema_rows_by_name.keys())
        table.setRowCount(len(upload_columns))
        for row_index, column_name in enumerate(upload_columns):
            create_widget = QCheckBox()
            update_widget = QCheckBox()
            is_selected = column_name in selected_mapping
            scope = (
                _normalize_scope(
                    (selected_mapping_modes or {}).get(column_name),
                    upload_mode=normalized_upload_mode,
                )
                if is_selected
                else {"create": False, "update": False}
            )
            create_widget.setChecked(bool(scope.get("create", False)))
            update_widget.setChecked(bool(scope.get("update", False)))
            _sync_mapping_scope_checkboxes(
                create_widget,
                update_widget,
                upload_mode=normalized_upload_mode,
            )
            table.setCellWidget(row_index, 0, create_widget)
            table.setCellWidget(row_index, 1, update_widget)
            table.setItem(row_index, 2, QTableWidgetItem(column_name))

            combo = QComboBox()
            combo.addItem("")
            combo.addItems(schema_field_names)
            if column_name in selected_mapping and combo.findText(selected_mapping[column_name]) >= 0:
                combo.setCurrentText(selected_mapping[column_name])
            table.setCellWidget(row_index, 3, combo)

            schema_field = selected_mapping.get(column_name)
            schema_row = page._schema_rows_by_name.get(schema_field, {})
            table.setItem(row_index, 4, QTableWidgetItem(str(schema_row.get("field_type") or "")))
            table.setItem(row_index, 5, QTableWidgetItem(str(bool(schema_row.get("multiple_values", False)))))
            table.setItem(row_index, 6, QTableWidgetItem("yes" if schema_row.get("is_supported", True) else "no"))

            def _on_combo_changed(_text, row=row_index):
                """`on_combo_changed` 이벤트를 처리한다."""
                selected_name = table.cellWidget(row, 3).currentText().strip()
                schema = page._schema_rows_by_name.get(selected_name, {})
                table.setItem(row, 4, QTableWidgetItem(str(schema.get("field_type") or "")))
                table.setItem(row, 5, QTableWidgetItem(str(bool(schema.get("multiple_values", False)))))
                table.setItem(row, 6, QTableWidgetItem("yes" if schema.get("is_supported", True) else "no"))
                _refresh_mapping_row(row)

            combo.currentTextChanged.connect(_on_combo_changed)
            create_widget.toggled.connect(lambda _checked, row=row_index: _refresh_mapping_row(row))
            update_widget.toggled.connect(lambda _checked, row=row_index: _refresh_mapping_row(row))
            _apply_mapping_row_highlight(row_index)

        default_table.setRowCount(len(default_value_candidates))
        for row_index, candidate in enumerate(default_value_candidates):
            schema_field = str(getattr(candidate, "schema_field", ""))
            create_widget = QCheckBox()
            default_scope = _normalize_default_value_scope(
                (selected_default_value_modes or {}).get(schema_field),
                upload_mode=normalized_upload_mode,
            )
            create_widget.setChecked(bool(default_scope.get("create", False) or default_scope.get("update", False)))
            create_widget.setEnabled(True)
            default_table.setCellWidget(row_index, 0, create_widget)
            default_table.setItem(row_index, 1, QTableWidgetItem(schema_field))
            default_table.setItem(row_index, 2, QTableWidgetItem(str(getattr(candidate, "field_type", ""))))

            combo = QComboBox()
            selected_default = str(selected_default_values.get(schema_field, "") or "")
            _configure_default_value_widget(combo, candidate, selected_default)
            _bind_default_value_commit(combo)
            combo.currentTextChanged.connect(lambda _text, widget=combo: None if bool(widget.isEditable()) else _mark_dirty())
            default_table.setCellWidget(row_index, 3, combo)

            default_table.setItem(
                row_index,
                4,
                QTableWidgetItem("yes" if bool(getattr(candidate, "mandatory", False)) else "no"),
            )
            create_widget.toggled.connect(lambda _checked: _mark_dirty())

        _configure_table_columns(table, [70, 70, 220, 220, 170, 90, 90])
        _configure_table_columns(default_table, [70, 220, 170, 240, 90])
        _populate_tracker_item_table(get_selected_mapping(), selected_tracker_item_settings)
        info_label.setText(
            f"매핑 대상 컬럼 {len(upload_columns)}개. id, parent 는 제외되며 생성/수정 체크를 모두 끄면 해당 컬럼은 무시됩니다."
        )
        if default_value_candidates:
            default_help_label.setText("행 값이 있으면 행 값이 우선하고, 비어 있으면 아래 기본값을 현재 처리 모드에 맞게 적용합니다.")
        else:
            default_help_label.setText("선택 가능한 공통 기본값 필드가 없습니다.")
        status_label.setText("")

    def get_selected_mapping() -> dict[str, str]:
        """`get_selected_mapping` 값을 반환한다."""
        mapping: dict[str, str] = {}
        for row_index in range(table.rowCount()):
            create_widget = table.cellWidget(row_index, 0)
            update_widget = table.cellWidget(row_index, 1)
            combo = table.cellWidget(row_index, 3)
            if create_widget is None or update_widget is None or combo is None:
                continue
            if not (bool(create_widget.isChecked()) or bool(update_widget.isChecked())):
                continue
            schema_field = combo.currentText().strip()
            if not schema_field:
                continue
            column_name_item = table.item(row_index, 2)
            if column_name_item is None:
                continue
            mapping[column_name_item.text()] = schema_field
        return mapping

    def get_selected_mapping_modes() -> dict[str, dict[str, bool]]:
        """`get_selected_mapping_modes` 값을 반환한다."""
        mapping_modes: dict[str, dict[str, bool]] = {}
        for row_index in range(table.rowCount()):
            create_widget = table.cellWidget(row_index, 0)
            update_widget = table.cellWidget(row_index, 1)
            column_name_item = table.item(row_index, 2)
            combo = table.cellWidget(row_index, 3)
            if (
                create_widget is None
                or update_widget is None
                or column_name_item is None
                or combo is None
            ):
                continue
            if not combo.currentText().strip():
                continue
            if not (bool(create_widget.isChecked()) or bool(update_widget.isChecked())):
                continue
            mapping_modes[column_name_item.text()] = {
                "create": bool(create_widget.isChecked()),
                "update": bool(update_widget.isChecked()),
            }
        return mapping_modes

    def get_selected_default_values() -> dict[str, str]:
        """`get_selected_default_values` 값을 반환한다."""
        default_values: dict[str, str] = {}
        for row_index in range(default_table.rowCount()):
            field_item = default_table.item(row_index, 1)
            combo = default_table.cellWidget(row_index, 3)
            if field_item is None or combo is None:
                continue
            selected_value = combo.currentText().strip()
            if not selected_value:
                continue
            default_values[field_item.text()] = selected_value
        return default_values

    def get_selected_default_value_modes() -> dict[str, dict[str, bool]]:
        """`get_selected_default_value_modes` 값을 반환한다."""
        default_value_modes: dict[str, dict[str, bool]] = {}
        for row_index in range(default_table.rowCount()):
            field_item = default_table.item(row_index, 1)
            create_widget = default_table.cellWidget(row_index, 0)
            combo = default_table.cellWidget(row_index, 3)
            if field_item is None or create_widget is None or combo is None:
                continue
            if not combo.currentText().strip():
                continue
            if not bool(create_widget.isChecked()):
                default_value_modes[field_item.text()] = {"create": False, "update": False}
                continue
            upload_mode_scope = _default_scope_for_upload_mode(
                getattr(page, "_mapping_upload_mode", GUI_UPLOAD_MODE_CREATE)
            )
            default_value_modes[field_item.text()] = {
                "create": bool(upload_mode_scope.get("create", False)),
                "update": bool(upload_mode_scope.get("update", False)),
            }
        return default_value_modes

    def get_selected_tracker_item_settings() -> dict[str, dict[str, object]]:
        """`get_selected_tracker_item_settings` 값을 반환한다."""
        settings: dict[str, dict[str, object]] = {}
        for row_index in range(tracker_item_table.rowCount()):
            source_item = tracker_item_table.item(row_index, 0)
            mode_combo = tracker_item_table.cellWidget(row_index, 2)
            strategy_combo = tracker_item_table.cellWidget(row_index, 3)
            regex_edit = tracker_item_table.cellWidget(row_index, 4)
            if source_item is None or mode_combo is None or strategy_combo is None or regex_edit is None:
                continue
            metadata = source_item.data(Qt.ItemDataRole.UserRole) or {}
            schema_field = str(metadata.get("schema_field") or "").strip()
            if not schema_field:
                continue
            settings[schema_field] = {
                "mode": str(mode_combo.currentData() or TrackerItemResolutionMode.REGEX.value),
                "query_match_strategy": str(
                    strategy_combo.currentData() or TrackerItemQueryMatchStrategy.BEST.value
                ),
                "regex_pattern": regex_edit.text().strip(),
                "source_tracker_ids": list(metadata.get("source_tracker_ids") or []),
            }
        return settings

    def _validate() -> None:
        """`validate` 관련 처리를 수행한다."""
        mapping = get_selected_mapping()
        if not mapping:
            status_label.setText("최소 1개 이상의 컬럼을 매핑해야 합니다.")
            return
        mapping_modes = get_selected_mapping_modes()
        selected_default_values = get_selected_default_values()
        selected_default_value_modes = get_selected_default_value_modes()
        try:
            on_validate_requested(
                mapping,
                mapping_modes,
                selected_default_values,
                selected_default_value_modes,
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
    page.get_selected_mapping_modes = get_selected_mapping_modes
    page.get_selected_default_values = get_selected_default_values
    page.get_selected_default_value_modes = get_selected_default_value_modes
    page.get_selected_tracker_item_settings = get_selected_tracker_item_settings
    return page


def create_validation_page():
    """`create_validation_page` 화면을 구성한다."""
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
    _configure_page_layout(layout)
    summary_label = QLabel("")
    summary_label.setObjectName("summary_label")
    _configure_constrained_panel(summary_label, max_width=WIDE_FORM_PANEL_MAX_WIDTH)
    layout.addWidget(summary_label)

    table = QTableWidget(0, 7)
    table.setHorizontalHeaderLabels(["상태", "행", "항목", "컬럼", "입력값", "문제", "조치"])
    table.setAlternatingRowColors(True)
    _configure_data_table(table, minimum_height=PRIMARY_TABLE_MIN_HEIGHT)
    _configure_table_columns(table, [90, 120, 180, 160, 160, 260, 280])
    page.issue_table = table
    layout.addWidget(table, 1)

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

    page.has_blocking_issues = True

    def set_results(issue_df, has_blocking_issues: bool, summary_stats: dict | None = None) -> None:
        """`set_results` 값을 설정한다."""
        rows: list[list[str]] = []
        if issue_df is not None and not issue_df.empty:
            for _, row in issue_df.iterrows():
                rows.append([
                    gui_display_text(row.get("severity")),
                    gui_display_text(row.get("row_label")),
                    gui_display_text(row.get("item_name")),
                    gui_display_text(row.get("column")),
                    gui_display_text(row.get("raw_value")),
                    gui_display_text(row.get("message")),
                    gui_display_text(row.get("action")),
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
            summary_parts.append(f"전체 검증 {total_rows}행")
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
        """`go_next` 단계 이동을 처리한다."""
        if page.has_blocking_issues:
            status_label.setText("차단 이슈를 해결해야 다음 단계로 이동할 수 있습니다.")
            return
        page.request_next()

    previous_button.clicked.connect(lambda: page.request_previous())
    next_button.clicked.connect(_go_next)
    page.set_results = set_results
    return page


def create_upload_page(on_start_requested, on_pause_requested, on_resume_requested, on_cancel_requested):
    """`create_upload_page` 화면을 구성한다."""
    qt = _require_qt()
    QWidget = qt["QWidget"]
    QVBoxLayout = qt["QVBoxLayout"]
    QHBoxLayout = qt["QHBoxLayout"]
    QTabWidget = qt["QTabWidget"]
    QLabel = qt["QLabel"]
    QPushButton = qt["QPushButton"]
    QPlainTextEdit = qt["QPlainTextEdit"]
    QProgressBar = qt["QProgressBar"]
    QCheckBox = qt["QCheckBox"]
    QTableWidget = qt["QTableWidget"]
    QTableWidgetItem = qt["QTableWidgetItem"]

    page = QWidget()
    layout = QVBoxLayout(page)
    _configure_page_layout(layout)

    page.progress_bar = QProgressBar()
    page.progress_bar.setTextVisible(True)
    page.progress_bar.setFormat("0 / 0 (0.0%)")
    layout.addWidget(page.progress_bar)
    page.progress_label = QLabel("진행률 0.0% (0 / 0)")
    page.progress_label.setObjectName("section_label")
    layout.addWidget(page.progress_label)

    page.phase_label = QLabel("현재 단계: -")
    page.current_label = QLabel("현재 항목: -")
    page.total_label = QLabel("총 대상 0건 / 완료 0건")
    page.phase_total_label = QLabel("단계별 총 대상: 생성 0건 / 수정 0건")
    page.phase_counter_label = QLabel("단계별 결과: 생성 성공 0 / 실패 0 | 수정 성공 0 / 실패 0")
    page.counter_label = QLabel("성공 0 / 실패 0 / 재시도 0")
    page.status_label = QLabel("준비")
    page.status_label.setObjectName("status_label")
    page.time_label = QLabel("배치 시간: -")
    page.time_label.setObjectName("section_label")
    page.eta_label = QLabel("예상 종료: -")
    page.eta_label.setObjectName("section_label")

    summary_row = QHBoxLayout()
    _configure_inline_layout(summary_row, spacing=10)

    left_col = QVBoxLayout()
    _configure_inline_layout(left_col, spacing=2)
    left_col.addWidget(page.phase_label)
    left_col.addWidget(page.current_label)
    summary_row.addLayout(left_col, 2)

    middle_col = QVBoxLayout()
    _configure_inline_layout(middle_col, spacing=2)
    middle_col.addWidget(page.total_label)
    middle_col.addWidget(page.counter_label)
    summary_row.addLayout(middle_col, 2)

    phase_col = QVBoxLayout()
    _configure_inline_layout(phase_col, spacing=2)
    phase_col.addWidget(page.phase_total_label)
    phase_col.addWidget(page.phase_counter_label)
    summary_row.addLayout(phase_col, 3)

    time_col = QVBoxLayout()
    _configure_inline_layout(time_col, spacing=2)
    time_col.addWidget(page.time_label)
    time_col.addWidget(page.eta_label)
    summary_row.addLayout(time_col, 2)

    layout.addLayout(summary_row)
    layout.addWidget(page.status_label)

    page.dry_run_checkbox = QCheckBox("Dry Run")
    page.continue_checkbox = QCheckBox("Continue on error")
    page.continue_checkbox.setChecked(True)
    controls = QHBoxLayout()
    _configure_inline_layout(controls)
    controls.addWidget(page.dry_run_checkbox)
    controls.addWidget(page.continue_checkbox)
    controls.addStretch(1)
    page.start_button = QPushButton("시작")
    page.pause_button = QPushButton("일시정지")
    page.resume_button = QPushButton("재개")
    page.cancel_button = QPushButton("중단")
    page.result_button = QPushButton("결과 보기")
    page.start_button.setObjectName("primary_button")
    page.resume_button.setObjectName("primary_button")
    page.cancel_button.setObjectName("danger_button")
    page.result_button.setObjectName("primary_button")
    page.pause_button.setEnabled(False)
    page.resume_button.setEnabled(False)
    page.cancel_button.setEnabled(False)
    page.result_button.setEnabled(False)
    controls.addWidget(page.start_button)
    controls.addWidget(page.pause_button)
    controls.addWidget(page.resume_button)
    controls.addWidget(page.cancel_button)
    controls.addWidget(page.result_button)
    layout.addLayout(controls)

    page.detail_tabs = QTabWidget()
    page.detail_tabs.setDocumentMode(True)
    page.detail_tabs.setMinimumHeight(UPLOAD_DETAIL_TABS_MIN_HEIGHT)

    activity_tab = QWidget()
    activity_layout = QVBoxLayout(activity_tab)
    _configure_inline_layout(activity_layout)
    page.activity_table = QTableWidget(0, 8)
    page.activity_table.setHorizontalHeaderLabels(["파일", "단계", "항목", "상태", "시작", "완료", "소요", "로그"])
    page.activity_table.setAlternatingRowColors(True)
    page.activity_table.setMinimumHeight(ACTIVITY_TABLE_MIN_HEIGHT)
    _configure_table_columns(page.activity_table, [140, 80, 160, 90, 95, 95, 80, 260])
    activity_layout.addWidget(page.activity_table)
    page.detail_tabs.addTab(activity_tab, "진행 기록")

    log_tab = QWidget()
    log_layout = QVBoxLayout(log_tab)
    _configure_inline_layout(log_layout)
    page.log_view = QPlainTextEdit()
    page.log_view.setReadOnly(True)
    page.log_view.setPlaceholderText("업로드 진행 로그와 시각이 여기에 표시됩니다.")
    log_layout.addWidget(page.log_view)
    page.detail_tabs.addTab(log_tab, "실시간 로그")

    response_tab = QWidget()
    response_layout = QVBoxLayout(response_tab)
    _configure_inline_layout(response_layout)
    page.response_view = QPlainTextEdit()
    page.response_view.setReadOnly(True)
    page.response_view.setPlaceholderText("실패한 요청의 서버 응답 JSON이 여기에 표시됩니다.")
    response_layout.addWidget(page.response_view)
    page.detail_tabs.addTab(response_tab, "실패 응답")

    page.activity_tab = activity_tab
    page.log_tab = log_tab
    page.response_tab = response_tab
    layout.addWidget(page.detail_tabs, 1)

    page._activity_row_map = {}

    page.start_button.clicked.connect(on_start_requested)
    page.pause_button.clicked.connect(on_pause_requested)
    page.resume_button.clicked.connect(on_resume_requested)
    page.cancel_button.clicked.connect(on_cancel_requested)
    page.result_button.clicked.connect(lambda: page.request_next())

    def _set_activity_cell(row_index: int, col_index: int, value: str) -> None:
        """`set_activity_cell` 값을 설정한다."""
        item = page.activity_table.item(row_index, col_index)
        if item is None:
            item = QTableWidgetItem(value)
            page.activity_table.setItem(row_index, col_index, item)
            return
        item.setText(value)

    def _ensure_activity_row(row_key: str, file_label: str, phase_name: str, item_name: str) -> int:
        """`ensure_activity_row` 상태를 보장한다."""
        if row_key in page._activity_row_map:
            row_index = int(page._activity_row_map[row_key])
        else:
            row_index = page.activity_table.rowCount()
            page.activity_table.insertRow(row_index)
            page._activity_row_map[row_key] = row_index
        _set_activity_cell(row_index, 0, file_label)
        _set_activity_cell(row_index, 1, phase_name)
        _set_activity_cell(row_index, 2, item_name)
        return row_index

    def record_activity_started(
        row_key: str,
        file_label: str,
        phase_name: str,
        item_name: str,
        started_at: str,
    ) -> None:
        """`record_activity_started` 기록을 남긴다."""
        row_index = _ensure_activity_row(row_key, file_label, phase_name, item_name)
        _set_activity_cell(row_index, 3, "진행 중")
        _set_activity_cell(row_index, 4, started_at)
        _set_activity_cell(row_index, 5, "")
        _set_activity_cell(row_index, 6, "")
        _set_activity_cell(row_index, 7, "업로드 시작")
        _configure_table_columns(page.activity_table, [140, 80, 160, 90, 95, 95, 80, 260])
        page.activity_table.scrollToBottom()

    def record_activity_finished(
        row_key: str,
        file_label: str,
        phase_name: str,
        item_name: str,
        *,
        status: str,
        finished_at: str,
        duration_text: str,
        message: str,
    ) -> None:
        """`record_activity_finished` 기록을 남긴다."""
        row_index = _ensure_activity_row(row_key, file_label, phase_name, item_name)
        _set_activity_cell(row_index, 3, status)
        if not page.activity_table.item(row_index, 4):
            _set_activity_cell(row_index, 4, finished_at)
        _set_activity_cell(row_index, 5, finished_at)
        _set_activity_cell(row_index, 6, duration_text)
        _set_activity_cell(row_index, 7, message)
        _configure_table_columns(page.activity_table, [140, 80, 160, 90, 95, 95, 80, 260])
        page.activity_table.scrollToBottom()

    def reset(total_count: int) -> None:
        """`reset` 관련 처리를 수행한다."""
        page.progress_bar.setMaximum(max(total_count, 1))
        page.progress_bar.setValue(0)
        page.progress_bar.setFormat("0 / 0 (0.0%)" if total_count <= 0 else f"0 / {total_count} (0.0%)")
        page.progress_label.setText(f"진행률 0.0% (0 / {max(total_count, 0)})")
        page.phase_label.setText("현재 단계: -")
        page.current_label.setText("현재 항목: -")
        page.total_label.setText("총 대상 0건 / 완료 0건")
        page.phase_total_label.setText("단계별 총 대상: 생성 0건 / 수정 0건")
        page.phase_counter_label.setText("단계별 결과: 생성 성공 0 / 실패 0 | 수정 성공 0 / 실패 0")
        page.counter_label.setText("성공 0 / 실패 0 / 재시도 0")
        page.status_label.setText("준비")
        page.time_label.setText("배치 시간: -")
        page.eta_label.setText("예상 종료: -")
        page.activity_table.setRowCount(0)
        page._activity_row_map = {}
        page.log_view.clear()
        page.response_view.clear()
        page.start_button.setEnabled(True)
        page.pause_button.setEnabled(False)
        page.resume_button.setEnabled(False)
        page.cancel_button.setEnabled(False)
        page.result_button.setEnabled(False)

    page.record_activity_started = record_activity_started
    page.record_activity_finished = record_activity_finished
    page.reset = reset
    return page


def create_result_page():
    """`create_result_page` 화면을 구성한다."""
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
    _configure_page_layout(layout)

    tabs = QTabWidget()
    tabs.setDocumentMode(True)
    page.result_tabs = tabs
    page.tables = {}
    for key, label in (
        ("success_df", "성공"),
        ("failed_df", "실패"),
        ("unresolved_df", "미해결"),
    ):
        tab = QWidget()
        tab_layout = QVBoxLayout(tab)
        _configure_inline_layout(tab_layout)
        table = QTableWidget(0, 0)
        table.setAlternatingRowColors(True)
        _configure_data_table(table, minimum_height=PRIMARY_TABLE_MIN_HEIGHT)
        tab_layout.addWidget(table, 1)
        tabs.addTab(tab, label)
        page.tables[key] = table
    layout.addWidget(tabs, 1)

    page.response_view = QPlainTextEdit()
    page.response_view.setReadOnly(True)
    page.response_view.setMinimumHeight(DETAIL_PANE_MIN_HEIGHT)
    layout.addWidget(page.response_view)

    buttons = QHBoxLayout()
    _configure_inline_layout(buttons)
    previous_button = QPushButton("이전")
    restart_button = QPushButton("새 업로드 시작")
    restart_button.setObjectName("primary_button")
    buttons.addWidget(previous_button)
    buttons.addStretch(1)
    buttons.addWidget(restart_button)
    layout.addLayout(buttons)

    def set_results(upload_result: dict) -> None:
        """`set_results` 값을 설정한다."""
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
