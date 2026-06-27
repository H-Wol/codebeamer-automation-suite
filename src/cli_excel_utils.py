from __future__ import annotations

from .excel_reader import ExcelReader


def list_sheet_names(file_path: str) -> list[str]:
    """Excel 파일 안에 있는 시트 이름 목록을 읽어온다."""
    return ExcelReader().list_sheet_names(file_path)


def read_headers(file_path: str, sheet_name: str | int, header_row: int = 1) -> list[str]:
    """지정한 시트의 헤더 행을 읽어 컬럼 이름 목록으로 돌려준다."""
    return ExcelReader(header_row=header_row).read_headers(file_path, sheet_name)
