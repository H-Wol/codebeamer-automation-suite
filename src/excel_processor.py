from __future__ import annotations

from .excel_reader import ExcelReader
from .hierarchy_processor import HierarchyProcessor


class ExcelHierarchyProcessor(HierarchyProcessor):
    """기존 코드와 테스트 호환을 위한 통합 래퍼다."""

    def __init__(self, header_row: int = 1, summary_col: str = "Summary", logger=None):
        super().__init__(header_row=header_row, summary_col=summary_col, logger=logger)
        self.reader = ExcelReader(header_row=header_row, summary_col=summary_col, logger=logger)

    def list_sheet_names(self, file_path: str) -> list[str]:
        return self.reader.list_sheet_names(file_path)

    def read_headers(self, file_path: str, sheet_name: str | int) -> list[str]:
        return self.reader.read_headers(file_path, sheet_name)

    def read_excel(self, file_path: str, sheet_name: str | int = 0, visible: bool = False):
        return self.reader.read_excel(file_path=file_path, sheet_name=sheet_name, visible=visible)
