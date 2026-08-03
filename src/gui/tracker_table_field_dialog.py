from __future__ import annotations

from copy import deepcopy
from typing import Any

try:
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QAbstractItemView
    from PySide6.QtWidgets import QDialog
    from PySide6.QtWidgets import QDialogButtonBox
    from PySide6.QtWidgets import QHBoxLayout
    from PySide6.QtWidgets import QHeaderView
    from PySide6.QtWidgets import QLabel
    from PySide6.QtWidgets import QPushButton
    from PySide6.QtWidgets import QTableWidget
    from PySide6.QtWidgets import QTableWidgetItem
    from PySide6.QtWidgets import QVBoxLayout
except ImportError as exc:  # pragma: no cover - GUI dependency guard
    raise RuntimeError("GUI 실행에는 PySide6 패키지가 필요합니다.") from exc

from .tracker_query_models import TrackerFieldValue
from .wiki_renderer import codebeamer_wiki_to_html
from .wiki_renderer import payload_uses_wiki


def is_table_field(field: TrackerFieldValue) -> bool:
    type_name = str(field.type_name or "").strip().casefold()
    raw_type = str(field.raw_value.get("type") or "").strip().casefold()
    return "tablefield" in type_name or "tablefield" in raw_type


def _row_payloads(payload: dict[str, Any]) -> list[list[dict[str, Any]]]:
    raw_rows = payload.get("values")
    if not isinstance(raw_rows, list):
        return []
    rows: list[list[dict[str, Any]]] = []
    for raw_row in raw_rows:
        if isinstance(raw_row, list):
            rows.append([cell for cell in raw_row if isinstance(cell, dict)])
            continue
        if isinstance(raw_row, dict) and isinstance(raw_row.get("values"), list):
            rows.append(
                [cell for cell in raw_row["values"] if isinstance(cell, dict)]
            )
    return rows


def _field_id(payload: dict[str, Any]) -> int | None:
    raw_id = payload.get("fieldId")
    if raw_id is None:
        raw_id = payload.get("id")
    if raw_id is None or isinstance(raw_id, bool):
        return None
    try:
        return int(raw_id)
    except (TypeError, ValueError):
        return None


def _column_key(payload: dict[str, Any], fallback_index: int) -> tuple[str, Any]:
    field_id = _field_id(payload)
    if field_id is not None:
        return ("id", field_id)
    name = str(payload.get("name") or "").strip()
    if name:
        return ("name", name.casefold())
    return ("index", fallback_index)


def _column_payloads(
    payload: dict[str, Any],
    rows: list[list[dict[str, Any]]],
) -> list[tuple[tuple[str, Any], dict[str, Any]]]:
    columns: list[tuple[tuple[str, Any], dict[str, Any]]] = []
    seen: set[tuple[str, Any]] = set()
    schema_columns = payload.get("columns")
    candidates: list[list[dict[str, Any]]] = []
    if isinstance(schema_columns, list):
        candidates.append([column for column in schema_columns if isinstance(column, dict)])
    candidates.extend(rows)
    for candidate_row in candidates:
        for index, column in enumerate(candidate_row):
            key = _column_key(column, index)
            if key in seen:
                continue
            seen.add(key)
            columns.append((key, deepcopy(column)))
    return columns


def _plain_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "예" if value else "아니요"
    if isinstance(value, dict):
        for key in ("value", "name", "summary", "id"):
            if value.get(key) not in (None, ""):
                return _plain_value(value.get(key))
        return str(value)
    if isinstance(value, (list, tuple)):
        return ", ".join(
            text for text in (_plain_value(item) for item in value) if text
        )
    return str(value).strip()


def _cell_text(payload: dict[str, Any]) -> str:
    if "value" in payload:
        return _plain_value(payload.get("value"))
    if "values" in payload:
        return _plain_value(payload.get("values"))
    return ""


def table_field_dimensions(field: TrackerFieldValue) -> tuple[int, int]:
    rows = _row_payloads(field.raw_value)
    columns = _column_payloads(field.raw_value, rows)
    return len(rows), len(columns)


def table_field_summary(field: TrackerFieldValue) -> str:
    row_count, column_count = table_field_dimensions(field)
    if row_count or column_count:
        return f"{row_count}행 × {column_count}열"
    return "빈 테이블"


class TrackerTableFieldDialog(QDialog):
    """TableField 행·열 구조를 보존하며 Wiki 셀만 rich text로 표시한다."""

    def __init__(self, field: TrackerFieldValue, parent=None) -> None:
        super().__init__(parent)
        self.field = field
        self.rows = _row_payloads(field.raw_value)
        self.columns = _column_payloads(field.raw_value, self.rows)
        self.setWindowTitle(f"{field.name} · 테이블 보기")
        self.setMinimumSize(720, 440)
        self.resize(920, 600)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        header = QHBoxLayout()
        title = QLabel(f"{field.name} · {table_field_summary(field)}", self)
        title.setObjectName("tracker_detail_section_title")
        header.addWidget(title, 1)
        self.source_toggle = QPushButton("Wiki 원문", self)
        self.source_toggle.setObjectName("mode_toggle")
        self.source_toggle.setCheckable(True)
        self.source_toggle.toggled.connect(self._populate)
        header.addWidget(self.source_toggle)
        layout.addLayout(header)

        self.table = QTableWidget(self)
        self.table.setObjectName("tracker_table_field_view")
        self.table.setAlternatingRowColors(True)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectItems)
        self.table.setWordWrap(True)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )
        layout.addWidget(self.table, 1)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close, parent=self)
        close_button = buttons.button(QDialogButtonBox.StandardButton.Close)
        if close_button is not None:
            close_button.setText("닫기")
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self._populate(False)

    def _cell_for_column(
        self,
        row: list[dict[str, Any]],
        key: tuple[str, Any],
        column_index: int,
    ) -> dict[str, Any] | None:
        for index, cell in enumerate(row):
            if _column_key(cell, index) == key:
                return cell
        if key[0] == "index" and column_index < len(row):
            return row[column_index]
        return None

    def _populate(self, show_source: bool = False) -> None:
        self.source_toggle.setText("렌더링 보기" if show_source else "Wiki 원문")
        self.table.clear()
        self.table.setRowCount(len(self.rows))
        self.table.setColumnCount(len(self.columns))
        self.table.setHorizontalHeaderLabels(
            [
                str(column.get("name") or f"열 {index + 1}")
                for index, (_, column) in enumerate(self.columns)
            ]
        )
        for row_index, row in enumerate(self.rows):
            for column_index, (key, column_schema) in enumerate(self.columns):
                cell = self._cell_for_column(row, key, column_index)
                if cell is None:
                    self.table.setItem(row_index, column_index, QTableWidgetItem(""))
                    continue
                text = _cell_text(cell)
                item = QTableWidgetItem(text)
                item.setToolTip(text)
                self.table.setItem(row_index, column_index, item)
                metadata = dict(column_schema)
                metadata.update(cell)
                if show_source or not payload_uses_wiki(metadata):
                    continue
                label = QLabel(self.table)
                label.setObjectName("tracker_wiki_cell")
                label.setTextFormat(Qt.TextFormat.RichText)
                label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
                label.setWordWrap(True)
                label.setMargin(6)
                label.setMinimumHeight(32)
                label.setText(codebeamer_wiki_to_html(text))
                item.setText("")
                self.table.setCellWidget(row_index, column_index, label)
                self.table.setRowHeight(
                    row_index,
                    max(self.table.rowHeight(row_index), 36),
                )
        self.table.resizeRowsToContents()


__all__ = [
    "TrackerTableFieldDialog",
    "is_table_field",
    "table_field_dimensions",
    "table_field_summary",
]
