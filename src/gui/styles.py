from __future__ import annotations

from pathlib import Path


_ASSETS_DIR = Path(__file__).resolve().parent / "assets"
_COMBO_ARROW_PATH = (_ASSETS_DIR / "chevron-down.svg").as_posix()

DEFAULT_GUI_THEME = "kepico"
GUI_THEME_LABELS = {
    "kepico": "케피코",
    "igloo": "이글루",
}
GUI_THEME_CHOICES = [(key, label) for key, label in GUI_THEME_LABELS.items()]

_BASE_GUI_STYLESHEET = """
QMainWindow {
    background: #F4F7FB;
}

QWidget#app_root {
    background: #F4F7FB;
}

QWidget#header_card, QWidget#page_card {
    background: #FFFFFF;
    border: 1px solid #D8E1EA;
    border-radius: 10px;
}

QScrollArea#page_scroll_area {
    background: transparent;
    border: none;
}

QScrollArea#page_scroll_area > QWidget > QWidget {
    background: transparent;
}

QLabel {
    color: #13263A;
}

QLabel#app_title {
    color: #0E4A84;
    font-size: 18px;
    font-weight: 700;
}

QLabel#app_subtitle {
    color: #5B6B7F;
    font-size: 11px;
}

QLabel#page_title {
    color: #13263A;
    font-size: 17px;
    font-weight: 700;
    padding-bottom: 1px;
}

QLabel#section_label {
    color: #5B6B7F;
    font-size: 11px;
    padding-bottom: 2px;
}

QLabel#mode_title {
    color: #13263A;
    font-size: 14px;
    font-weight: 700;
}

QLabel#mode_badge {
    color: #0E4A84;
    background: #EAF4FB;
    border: 1px solid #CBE4F3;
    border-radius: 10px;
    padding: 4px 10px;
    font-size: 10px;
    font-weight: 700;
}

QLabel#status_label {
    color: #0E4A84;
    background: #EAF4FB;
    border: 1px solid #CBE4F3;
    border-radius: 8px;
    padding: 7px 10px;
}

QToolButton#section_toggle {
    color: #0E4A84;
    background: transparent;
    border: none;
    padding: 2px 0;
    font-weight: 700;
}

QToolButton#section_toggle:hover {
    color: #1260A8;
}

QFrame#advanced_card {
    background: #F8FBFD;
    border: 1px solid #D8E1EA;
    border-radius: 10px;
}

QWidget#busy_overlay {
    background: rgba(19, 38, 58, 0.22);
}

QDialog#alert_dialog {
    background: #F4F7FB;
}

QFrame#alert_surface {
    background: #FFFFFF;
    border: 1px solid #D8E1EA;
    border-radius: 16px;
}

QFrame#alert_surface[tone="error"] {
    border: 1px solid #F1C9C9;
}

QFrame#alert_surface[tone="info"] {
    border: 1px solid #CBE4F3;
}

QLabel#alert_badge {
    color: #0E4A84;
    background: #EAF4FB;
    border: 1px solid #CBE4F3;
    border-radius: 20px;
    font-size: 18px;
    font-weight: 700;
}

QLabel#alert_badge[tone="error"] {
    color: #C24141;
    background: #FDEEEE;
    border: 1px solid #F2C9C9;
}

QLabel#alert_title {
    color: #13263A;
    font-size: 16px;
    font-weight: 700;
}

QLabel#alert_message {
    color: #4E5F72;
}

QPlainTextEdit#alert_details {
    color: #425466;
    background: #F8FBFD;
    border: 1px solid #D8E1EA;
    border-radius: 10px;
    padding: 8px 10px;
}

QFrame#busy_card {
    background: #FFFFFF;
    border: 1px solid #C8D6E3;
    border-radius: 16px;
}

QLabel#busy_title {
    color: #13263A;
    font-size: 16px;
    font-weight: 700;
}

QLabel#busy_message {
    color: #5B6B7F;
    font-size: 11px;
}

QLabel#summary_label {
    color: #13263A;
    background: #F7FAFD;
    border: 1px solid #D8E1EA;
    border-radius: 8px;
    padding: 8px 10px;
    font-weight: 600;
}

QLabel#step_badge {
    color: #6B7B8D;
    background: #EEF3F8;
    border: 1px solid #D8E1EA;
    border-radius: 12px;
    padding: 5px 10px;
    font-size: 10px;
    font-weight: 600;
}

QLabel#step_badge[active="true"] {
    color: #FFFFFF;
    background: #0E4A84;
    border: 1px solid #0E4A84;
}

QLabel#step_badge[complete="true"] {
    color: #0E4A84;
    background: #E4F3FB;
    border: 1px solid #B6DAEE;
}

QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox {
    min-height: 28px;
    padding: 1px 8px;
    border: 1px solid #C9D5E2;
    border-radius: 8px;
    background: #FFFFFF;
    color: #13263A;
}

QComboBox {
    padding-right: 28px;
}

QComboBox::drop-down {
    subcontrol-origin: padding;
    subcontrol-position: top right;
    width: 24px;
    border: none;
    background: transparent;
}

QComboBox::down-arrow {
    image: url("{combo_arrow}");
    width: 12px;
    height: 12px;
}

QComboBox QAbstractItemView {
    color: #13263A;
    background: #FFFFFF;
    border: 1px solid #C9D5E2;
    selection-background-color: #DCEFFD;
    selection-color: #13263A;
    outline: 0;
}

QComboBox QAbstractItemView::item {
    min-height: 24px;
    padding: 4px 8px;
}

QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus {
    border: 1px solid #00A7D6;
}

QLineEdit:disabled, QComboBox:disabled, QSpinBox:disabled, QDoubleSpinBox:disabled {
    color: #7E8B99;
    background: #EEF2F6;
    border: 1px solid #D5DEE7;
}

QPushButton {
    min-height: 28px;
    padding: 0 10px;
    border-radius: 8px;
    border: 1px solid #C9D5E2;
    background: #FFFFFF;
    color: #13263A;
    font-weight: 600;
}

QPushButton:hover {
    background: #F4F8FC;
}

QPushButton:disabled {
    color: #7E8B99;
    background: #E8EEF4;
    border-color: #CBD6E1;
}

QPushButton#primary_button {
    background: #0E4A84;
    color: #FFFFFF;
    border: 1px solid #0E4A84;
}

QPushButton#primary_button:hover {
    background: #1260A8;
}

QPushButton#primary_button:disabled {
    color: #F7FAFD;
    background: #A9BBCD;
    border: 1px solid #A9BBCD;
}

QPushButton#mode_toggle {
    min-width: 72px;
    min-height: 34px;
    padding: 0 14px;
    border-radius: 17px;
    border: 1px solid #C9D5E2;
    background: #FFFFFF;
    color: #5B6B7F;
    font-weight: 700;
}

QPushButton#mode_toggle:hover {
    background: #F4F8FC;
}

QPushButton#mode_toggle:checked {
    background: #0E4A84;
    color: #FFFFFF;
    border: 1px solid #0E4A84;
}

QPushButton#mode_toggle:checked:hover {
    background: #1260A8;
}

QPushButton#danger_button {
    background: #FFFFFF;
    color: #C24141;
    border: 1px solid #E8B7B7;
}

QPushButton#danger_button:hover {
    background: #FFF6F6;
}

QPushButton#danger_button:disabled {
    color: #C7A7A7;
    background: #F6EEEE;
    border: 1px solid #E7D7D7;
}

QTableWidget, QPlainTextEdit, QTabWidget::pane {
    background: #FFFFFF;
    border: 1px solid #D8E1EA;
    border-radius: 10px;
}

QTableWidget {
    gridline-color: #E6EDF4;
    alternate-background-color: #F8FBFD;
    selection-background-color: #DCEFFD;
    selection-color: #13263A;
}

QHeaderView::section {
    background: #EEF4F9;
    color: #425466;
    border: none;
    border-right: 1px solid #D8E1EA;
    border-bottom: 1px solid #D8E1EA;
    padding: 6px 6px;
    font-weight: 700;
}

QProgressBar {
    min-height: 14px;
    border: 1px solid #D8E1EA;
    border-radius: 7px;
    background: #ECF2F7;
    text-align: center;
}

QProgressBar::chunk {
    border-radius: 7px;
    background: #00A7D6;
}

QProgressBar#busy_progress {
    min-height: 10px;
    border-radius: 5px;
}

QCheckBox {
    spacing: 8px;
    color: #13263A;
}

QCheckBox:disabled {
    color: #7E8B99;
}

QStatusBar {
    background: #FFFFFF;
    color: #5B6B7F;
    border-top: 1px solid #D8E1EA;
}

QScrollBar:vertical {
    background: #EFF4F8;
    width: 12px;
    margin: 4px 2px 4px 2px;
    border-radius: 6px;
}

QScrollBar::handle:vertical {
    background: #B8C7D5;
    min-height: 28px;
    border-radius: 6px;
}

QScrollBar::handle:vertical:hover {
    background: #97AEC3;
}

QScrollBar::add-line:vertical,
QScrollBar::sub-line:vertical,
QScrollBar::add-page:vertical,
QScrollBar::sub-page:vertical {
    background: transparent;
    border: none;
}
"""
_BASE_GUI_STYLESHEET = _BASE_GUI_STYLESHEET.replace("{combo_arrow}", _COMBO_ARROW_PATH)

_IGLOO_THEME_OVERRIDES = """
QMainWindow {
    background: #F2FBFC;
}

QWidget#app_root {
    background: #F2FBFC;
}

QWidget#header_card, QWidget#page_card {
    border: 1px solid #D3E7E9;
}

QScrollArea#page_scroll_area > QWidget > QWidget {
    background: transparent;
}

QLabel#app_title {
    color: #0B6E70;
}

QLabel#app_subtitle, QLabel#section_label, QLabel#busy_message {
    color: #60797E;
}

QLabel#mode_title {
    color: #153A3F;
}

QLabel#mode_badge {
    color: #0B6E70;
    background: #E5F7F6;
    border: 1px solid #BFE6E2;
}

QLabel#status_label {
    color: #0B6E70;
    background: #E5F7F6;
    border: 1px solid #BFE6E2;
}

QToolButton#section_toggle {
    color: #0B6E70;
}

QToolButton#section_toggle:hover {
    color: #15918D;
}

QFrame#advanced_card {
    background: #F7FCFC;
    border: 1px solid #D3E7E9;
}

QDialog#alert_dialog {
    background: #F2FBFC;
}

QLabel#alert_badge {
    color: #0B6E70;
    background: #E5F7F6;
    border: 1px solid #BFE6E2;
}

QFrame#busy_card {
    border: 1px solid #C8E0E2;
}

QLabel#summary_label {
    background: #F6FCFC;
    border: 1px solid #D3E7E9;
}

QLabel#step_badge {
    color: #6C8489;
    background: #EEF7F8;
    border: 1px solid #D3E7E9;
}

QLabel#step_badge[active="true"] {
    background: #0B6E70;
    border: 1px solid #0B6E70;
}

QLabel#step_badge[complete="true"] {
    color: #0B6E70;
    background: #E0F5F3;
    border: 1px solid #AEDFD9;
}

QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus {
    border: 1px solid #16B3AC;
}

QComboBox QAbstractItemView {
    color: #153A3F;
    background: #FFFFFF;
    border: 1px solid #C7DFE2;
    selection-background-color: #D9F0EF;
    selection-color: #153A3F;
}

QPushButton:hover {
    background: #F1FAFB;
}

QPushButton#primary_button {
    background: #0B6E70;
    border: 1px solid #0B6E70;
}

QPushButton#primary_button:hover {
    background: #15918D;
}

QPushButton#primary_button:disabled {
    background: #AAC8C8;
    border: 1px solid #AAC8C8;
}

QPushButton#mode_toggle {
    color: #60797E;
}

QPushButton#mode_toggle:hover {
    background: #F1FAFB;
}

QPushButton#mode_toggle:checked {
    background: #0B6E70;
    border: 1px solid #0B6E70;
}

QPushButton#mode_toggle:checked:hover {
    background: #15918D;
}

QTableWidget, QPlainTextEdit, QTabWidget::pane {
    border: 1px solid #D3E7E9;
}

QTableWidget {
    gridline-color: #E4EFF1;
    alternate-background-color: #F7FCFC;
    selection-background-color: #D9F0EF;
}

QHeaderView::section {
    background: #EEF8F9;
    color: #486368;
    border-right: 1px solid #D3E7E9;
    border-bottom: 1px solid #D3E7E9;
}

QProgressBar {
    border: 1px solid #D3E7E9;
    background: #EAF4F5;
}

QProgressBar::chunk {
    background: #16B3AC;
}

QStatusBar {
    color: #60797E;
    border-top: 1px solid #D3E7E9;
}

QScrollBar:vertical {
    background: #EAF5F6;
}

QScrollBar::handle:vertical {
    background: #A6C9CC;
}

QScrollBar::handle:vertical:hover {
    background: #7FB4B8;
}
"""

_THEME_OVERRIDES = {
    "kepico": "",
    "igloo": _IGLOO_THEME_OVERRIDES,
}


def normalize_gui_theme_name(theme_name: str | None) -> str:
    normalized = str(theme_name or "").strip().lower()
    return normalized if normalized in GUI_THEME_LABELS else DEFAULT_GUI_THEME


def build_gui_stylesheet(theme_name: str | None = None) -> str:
    normalized_theme = normalize_gui_theme_name(theme_name)
    return f"{_BASE_GUI_STYLESHEET}\n{_THEME_OVERRIDES.get(normalized_theme, '')}".strip()


GUI_STYLESHEET = build_gui_stylesheet()
