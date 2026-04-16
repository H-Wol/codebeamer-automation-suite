from __future__ import annotations


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
    border-radius: 14px;
}

QLabel#app_title {
    color: #0E4A84;
    font-size: 24px;
    font-weight: 700;
}

QLabel#app_subtitle {
    color: #5B6B7F;
    font-size: 13px;
}

QLabel#page_title {
    color: #13263A;
    font-size: 22px;
    font-weight: 700;
    padding-bottom: 2px;
}

QLabel#section_label {
    color: #5B6B7F;
    font-size: 13px;
    padding-bottom: 8px;
}

QLabel#status_label {
    color: #0E4A84;
    background: #EAF4FB;
    border: 1px solid #CBE4F3;
    border-radius: 10px;
    padding: 10px 12px;
}

QLabel#summary_label {
    color: #13263A;
    background: #F7FAFD;
    border: 1px solid #D8E1EA;
    border-radius: 10px;
    padding: 10px 12px;
    font-weight: 600;
}

QLabel#step_badge {
    color: #6B7B8D;
    background: #EEF3F8;
    border: 1px solid #D8E1EA;
    border-radius: 16px;
    padding: 8px 14px;
    font-size: 12px;
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
    min-height: 38px;
    padding: 4px 10px;
    border: 1px solid #C9D5E2;
    border-radius: 10px;
    background: #FFFFFF;
    color: #13263A;
}

QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus {
    border: 1px solid #00A7D6;
}

QPushButton {
    min-height: 38px;
    padding: 0 16px;
    border-radius: 10px;
    border: 1px solid #C9D5E2;
    background: #FFFFFF;
    color: #13263A;
    font-weight: 600;
}

QPushButton:hover {
    background: #F4F8FC;
}

QPushButton:disabled {
    color: #9AA7B5;
    background: #F5F7FA;
    border-color: #DFE6EE;
}

QPushButton#primary_button {
    background: #0E4A84;
    color: #FFFFFF;
    border: 1px solid #0E4A84;
}

QPushButton#primary_button:hover {
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

QTableWidget, QPlainTextEdit, QTabWidget::pane {
    background: #FFFFFF;
    border: 1px solid #D8E1EA;
    border-radius: 12px;
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
    padding: 10px 8px;
    font-weight: 700;
}

QProgressBar {
    min-height: 16px;
    border: 1px solid #D8E1EA;
    border-radius: 8px;
    background: #ECF2F7;
    text-align: center;
}

QProgressBar::chunk {
    border-radius: 7px;
    background: #00A7D6;
}

QCheckBox {
    spacing: 8px;
    color: #13263A;
}

QStatusBar {
    background: #FFFFFF;
    color: #5B6B7F;
    border-top: 1px solid #D8E1EA;
}
"""

