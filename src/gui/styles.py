from __future__ import annotations

from pathlib import Path


_ASSETS_DIR = Path(__file__).resolve().parent / "assets"
_COMBO_ARROW_PATH = (_ASSETS_DIR / "chevron-down.svg").as_posix()


GUI_STYLESHEET = """
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
"""
GUI_STYLESHEET = GUI_STYLESHEET.replace("{combo_arrow}", _COMBO_ARROW_PATH)
