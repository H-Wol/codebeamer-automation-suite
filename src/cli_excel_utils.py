from __future__ import annotations

import xlwings as xw


def list_sheet_names(file_path: str) -> list[str]:
    """Excel 파일 안에 있는 시트 이름 목록을 읽어온다."""
    app = xw.App(visible=False, add_book=False)
    app.display_alerts = False
    app.screen_updating = False
    wb = None

    try:
        wb = app.books.open(file_path)
        return [sheet.name for sheet in wb.sheets]
    finally:
        if wb is not None:
            try:
                wb.close()
            except Exception:
                pass
        app.quit()


def read_headers(file_path: str, sheet_name: str | int, header_row: int = 1) -> list[str]:
    """지정한 시트의 헤더 행을 읽어 컬럼 이름 목록으로 돌려준다."""
    app = xw.App(visible=False, add_book=False)
    app.display_alerts = False
    app.screen_updating = False
    wb = None

    try:
        wb = app.books.open(file_path)
        sht = wb.sheets[sheet_name]
        used_range = sht.used_range
        values = used_range.value

        if not values or len(values) < header_row:
            return []

        headers = values[header_row - 1]
        return [str(h).strip() if h is not None else f"Unnamed_{i}" for i, h in enumerate(headers)]
    finally:
        if wb is not None:
            try:
                wb.close()
            except Exception:
                pass
        app.quit()
