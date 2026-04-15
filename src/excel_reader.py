from __future__ import annotations

from typing import Any

import pandas as pd
import xlwings as xw


class ExcelReader:
    """Excel 파일에서 raw DataFrame만 읽어오는 입력 전용 reader다."""

    def __init__(self, header_row: int = 1, summary_col: str = "Summary", logger=None):
        self.header_row = header_row
        self.summary_col = summary_col
        self.logger = logger

    @staticmethod
    def is_blank(value: Any) -> bool:
        if value is None:
            return True
        if isinstance(value, float) and pd.isna(value):
            return True
        if isinstance(value, str) and value.strip() == "":
            return True
        return False

    @staticmethod
    def _normalize_headers(headers: list[Any]) -> list[str]:
        return [
            str(header).strip() if header is not None else f"Unnamed_{index}"
            for index, header in enumerate(headers)
        ]

    def list_sheet_names(self, file_path: str) -> list[str]:
        app = xw.App(visible=False, add_book=False)
        app.display_alerts = False
        app.screen_updating = False
        workbook = None

        try:
            workbook = app.books.open(file_path)
            return [sheet.name for sheet in workbook.sheets]
        finally:
            if workbook is not None:
                try:
                    workbook.close()
                except Exception:
                    pass
            app.quit()

    def read_headers(self, file_path: str, sheet_name: str | int) -> list[str]:
        app = xw.App(visible=False, add_book=False)
        app.display_alerts = False
        app.screen_updating = False
        workbook = None

        try:
            workbook = app.books.open(file_path)
            sheet = workbook.sheets[sheet_name]
            values = sheet.used_range.value
            if not values or len(values) < self.header_row:
                return []
            headers = values[self.header_row - 1]
            return self._normalize_headers(headers)
        finally:
            if workbook is not None:
                try:
                    workbook.close()
                except Exception:
                    pass
            app.quit()

    def _resolve_indent_level(self, cell: Any, summary_value: Any) -> int:
        try:
            return int(cell.api.IndentLevel)
        except Exception:
            if isinstance(summary_value, str):
                leading_spaces = len(summary_value) - len(summary_value.lstrip(" "))
                return leading_spaces // 4
        return 0

    def read_excel(self, file_path: str, sheet_name: str | int = 0, visible: bool = False) -> pd.DataFrame:
        """Excel 시트를 읽고 `_excel_row`, `_summary_indent` 메타정보를 포함한 raw DataFrame을 만든다."""
        app = xw.App(visible=visible, add_book=False)
        app.display_alerts = False
        app.screen_updating = False
        workbook = None

        try:
            workbook = app.books.open(file_path)
            sheet = workbook.sheets[sheet_name]
            used_range = sheet.used_range
            values = used_range.value

            headers = self._normalize_headers(values[self.header_row - 1])
            if self.summary_col not in headers:
                raise ValueError(f"'{self.summary_col}' 컬럼을 찾을 수 없습니다.")

            summary_col_idx_1based = headers.index(self.summary_col) + 1
            data_rows = values[self.header_row:]
            used_start_row = used_range.row
            used_start_col = used_range.column

            records = []
            for relative_index, row in enumerate(data_rows, start=self.header_row + 1):
                normalized_row = list(row) if isinstance(row, list) else [row]

                if len(normalized_row) < len(headers):
                    normalized_row += [None] * (len(headers) - len(normalized_row))
                elif len(normalized_row) > len(headers):
                    normalized_row = normalized_row[:len(headers)]

                if all(self.is_blank(value) for value in normalized_row):
                    continue

                excel_row = used_start_row + (relative_index - 1)
                excel_col = used_start_col + (summary_col_idx_1based - 1)
                summary_cell = sheet.range((excel_row, excel_col))
                summary_value = normalized_row[summary_col_idx_1based - 1]
                indent_level = self._resolve_indent_level(summary_cell, summary_value)

                record = dict(zip(headers, normalized_row))
                record["_excel_row"] = excel_row
                record["_summary_indent"] = indent_level
                records.append(record)

            return pd.DataFrame(records)
        finally:
            if workbook is not None:
                try:
                    workbook.close()
                except Exception:
                    pass
            app.quit()
