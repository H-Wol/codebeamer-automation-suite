from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from src.upload_policy import normalize_upload_mode as normalize_gui_upload_mode
from src.upload_policy import upload_mode_supports_update as gui_upload_mode_supports_update

from .page_common import WIDE_FORM_PANEL_MAX_WIDTH
from .page_common import _configure_card_layout
from .page_common import _configure_constrained_panel
from .page_common import _configure_form_field
from .page_common import _configure_form_layout
from .page_common import _configure_inline_layout
from .page_common import _configure_page_layout
from .page_common import _require_qt
from .page_common import _settings_upload_mode_choices


def create_batch_settings_page(
    initial_settings,
    on_settings_changed,
    on_global_settings_requested=None,
):
    """전역 연결 설정과 분리된 배치 preset 설정 페이지를 만든다."""

    qt = _require_qt()
    QWidget = qt["QWidget"]
    QVBoxLayout = qt["QVBoxLayout"]
    QFormLayout = qt["QFormLayout"]
    QHBoxLayout = qt["QHBoxLayout"]
    QLabel = qt["QLabel"]
    QFrame = qt["QFrame"]
    QComboBox = qt["QComboBox"]
    QLineEdit = qt["QLineEdit"]
    QSpinBox = qt["QSpinBox"]
    QPushButton = qt["QPushButton"]

    page = QWidget()
    page.setObjectName("batch_settings_page")
    page._current_settings = replace(initial_settings)
    page._updating_controls = False

    layout = QVBoxLayout(page)
    _configure_page_layout(layout, top_align=True)

    environment_card = QFrame(page)
    environment_card.setObjectName("advanced_card")
    _configure_constrained_panel(environment_card, max_width=WIDE_FORM_PANEL_MAX_WIDTH)
    environment_layout = QVBoxLayout(environment_card)
    _configure_card_layout(environment_layout)

    environment_title = QLabel("현재 실행 환경")
    environment_title.setObjectName("application_placeholder_title")
    environment_summary = QLabel("")
    environment_summary.setObjectName("section_label")
    environment_summary.setWordWrap(True)
    environment_layout.addWidget(environment_title)
    environment_layout.addWidget(environment_summary)

    environment_actions = QHBoxLayout()
    _configure_inline_layout(environment_actions)
    environment_actions.addStretch(1)
    global_settings_button = QPushButton("전역 설정 열기")
    global_settings_button.setEnabled(callable(on_global_settings_requested))
    environment_actions.addWidget(global_settings_button)
    environment_layout.addLayout(environment_actions)
    layout.addWidget(environment_card)

    form_card = QFrame(page)
    form_card.setObjectName("advanced_card")
    _configure_constrained_panel(form_card, max_width=WIDE_FORM_PANEL_MAX_WIDTH)
    form_layout = QVBoxLayout(form_card)
    _configure_card_layout(form_layout)

    form_description = QLabel(
        "작업 모드와 Excel 해석 기준은 배치 preset에 저장됩니다. "
        "연결·테마·테스트 모드는 전역 설정에서 관리합니다."
    )
    form_description.setObjectName("section_label")
    form_description.setWordWrap(True)
    form_layout.addWidget(form_description)

    form = QFormLayout()
    _configure_form_layout(form)
    upload_mode_combo = QComboBox()
    for value, label in _settings_upload_mode_choices():
        upload_mode_combo.addItem(label, value)
    header_row = QSpinBox()
    header_row.setMinimum(1)
    header_row.setMaximum(10_000)
    summary_column = QLineEdit()
    sheet_name = QLineEdit()
    for widget in (upload_mode_combo, header_row, summary_column, sheet_name):
        _configure_form_field(widget)
    form.addRow("작업 모드", upload_mode_combo)
    form.addRow("헤더 행", header_row)
    form.addRow("요약 컬럼", summary_column)
    form.addRow("시트 이름 또는 순서", sheet_name)
    form_layout.addLayout(form)
    layout.addWidget(form_card)

    status_label = QLabel("")
    status_label.setObjectName("status_label")
    status_label.setWordWrap(True)
    _configure_constrained_panel(status_label, max_width=WIDE_FORM_PANEL_MAX_WIDTH)
    layout.addWidget(status_label)

    actions = QHBoxLayout()
    _configure_inline_layout(actions)
    next_button = QPushButton("다음")
    next_button.setObjectName("primary_button")
    actions.addStretch(1)
    actions.addWidget(next_button)
    layout.addLayout(actions)
    layout.addStretch(1)

    def _environment_is_ready(settings) -> bool:
        if bool(getattr(settings, "offline_mode", False)):
            return bool(Path(str(settings.offline_schema_path or "")).is_file()) and not bool(
                gui_upload_mode_supports_update(upload_mode_combo.currentData())
            )
        return bool(
            str(settings.base_url or "").strip()
            and str(settings.username or "").strip()
            and str(settings.password or "")
        )

    def _refresh_environment() -> None:
        settings = page._current_settings
        if bool(getattr(settings, "offline_mode", False)):
            environment_summary.setText(
                "테스트 모드 · 실제 업로드 차단 · "
                f"Schema: {str(settings.offline_schema_path or '').strip() or '미설정'}"
            )
        elif str(getattr(settings, "base_url", "") or "").strip():
            environment_summary.setText(
                "온라인 · "
                f"{str(settings.base_url).strip()} · "
                f"{str(settings.username or '').strip() or '사용자 미설정'}"
            )
        else:
            environment_summary.setText(
                "연결 미설정 · 전역 설정에서 연결 프로필을 "
                "저장·검증·적용해야 합니다."
            )

        ready = _environment_is_ready(settings)
        next_button.setEnabled(ready)
        if ready:
            status_label.setText("배치 설정을 확인한 뒤 다음 단계로 진행할 수 있습니다.")
        elif bool(getattr(settings, "offline_mode", False)) and gui_upload_mode_supports_update(
            upload_mode_combo.currentData()
        ):
            status_label.setText(
                "테스트 모드에서는 기존 수정 또는 혼합 처리를 실행할 수 없습니다."
            )
        else:
            status_label.setText("전역 설정의 연결 또는 테스트 snapshot을 먼저 적용해야 합니다.")

    def _collect_settings():
        current = page._current_settings
        return replace(
            current,
            upload_mode=normalize_gui_upload_mode(upload_mode_combo.currentData()),
            excel_header_row=int(header_row.value()),
            summary_column=summary_column.text().strip() or "Summary",
            excel_sheet_name=sheet_name.text().strip() or "0",
        )

    def _notify_changed(*_args) -> None:
        if page._updating_controls:
            return
        page._current_settings = _collect_settings()
        on_settings_changed(replace(page._current_settings))
        _refresh_environment()

    def _set_settings(settings) -> None:
        page._updating_controls = True
        try:
            page._current_settings = replace(settings)
            upload_mode_index = upload_mode_combo.findData(
                normalize_gui_upload_mode(settings.upload_mode)
            )
            upload_mode_combo.setCurrentIndex(max(upload_mode_index, 0))
            header_row.setValue(max(int(settings.excel_header_row or 1), 1))
            summary_column.setText(str(settings.summary_column or "Summary"))
            sheet_name.setText(str(settings.excel_sheet_name or "0"))
        finally:
            page._updating_controls = False
        _refresh_environment()

    def _go_next() -> None:
        if not next_button.isEnabled():
            return
        page._current_settings = _collect_settings()
        on_settings_changed(replace(page._current_settings))
        callback = getattr(page, "request_next", None)
        if callable(callback):
            callback()

    page.get_settings = lambda: replace(_collect_settings())
    page.set_settings = _set_settings
    page.on_page_shown = _refresh_environment
    page.environment_summary = environment_summary
    page.global_settings_button = global_settings_button
    page.upload_mode_combo = upload_mode_combo
    page.header_row = header_row
    page.summary_column = summary_column
    page.sheet_name = sheet_name
    page.status_label = status_label
    page.next_button = next_button

    upload_mode_combo.currentIndexChanged.connect(_notify_changed)
    header_row.valueChanged.connect(_notify_changed)
    summary_column.textChanged.connect(_notify_changed)
    sheet_name.textChanged.connect(_notify_changed)
    next_button.clicked.connect(_go_next)
    if callable(on_global_settings_requested):
        global_settings_button.clicked.connect(on_global_settings_requested)

    _set_settings(initial_settings)
    return page


__all__ = ["create_batch_settings_page"]
