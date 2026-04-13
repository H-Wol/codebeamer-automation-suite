from __future__ import annotations

from typing import Any
import pandas as pd
import xlwings as xw


class ExcelHierarchyProcessor:
    def __init__(self, header_row: int = 1, summary_col: str = "요약", logger=None):
        """Excel 파일을 계층형 업로드 데이터로 바꾸기 위한 기본 설정을 저장한다."""
        self.header_row = header_row
        self.summary_col = summary_col
        self.logger = logger

    @staticmethod
    def is_blank(value: Any) -> bool:
        """값이 비어 있는 셀인지 판정한다."""
        if value is None:
            return True
        if isinstance(value, float) and pd.isna(value):
            return True
        if isinstance(value, str) and value.strip() == "":
            return True
        return False

    @classmethod
    def normalize_scalar(cls, value: Any) -> Any:
        """셀 값을 비교하기 쉬운 형태로 정리한다."""
        if cls.is_blank(value):
            return None
        if isinstance(value, str):
            return value.strip()
        return value

    @classmethod
    def collect_values(cls, values: list[Any], single_to_scalar: bool = False):
        """여러 행에 흩어진 값을 모아 하나의 값 또는 목록으로 만든다."""
        cleaned = [cls.normalize_scalar(v)
                   for v in values if not cls.is_blank(v)]
        if not cleaned:
            return None
        if single_to_scalar and len(cleaned) == 1:
            return cleaned[0]
        return cleaned

    @classmethod
    def keep_value(cls, values: list[Any], mode: str = "first"):
        """여러 값 중 첫 값, 마지막 값, 전체 목록 중 하나를 선택한다."""
        cleaned = [cls.normalize_scalar(v)
                   for v in values if not cls.is_blank(v)]
        if not cleaned:
            return None
        if mode == "first":
            return cleaned[0]
        if mode == "last":
            return cleaned[-1]
        if mode == "list":
            return cleaned
        raise ValueError("mode must be one of: first, last, list")

    @classmethod
    def list_to_multiline_text(cls, value: Any) -> str | None:
        """목록 값을 줄바꿈 문자열로 바꿔 사람이 읽기 쉽게 만든다."""
        if value is None:
            return None
        if isinstance(value, list):
            vals = [str(v).strip() for v in value if not cls.is_blank(v)]
            return "\n".join(vals) if vals else None
        text = str(value).strip()
        return text or None

    def read_excel(self, file_path: str, sheet_name: str | int = 0, visible: bool = False) -> pd.DataFrame:
        """Excel 시트를 읽어 각 행의 들여쓰기 정보까지 포함한 DataFrame을 만든다."""
        app = xw.App(visible=visible, add_book=False)
        app.display_alerts = False
        app.screen_updating = False
        wb = None

        try:
            wb = app.books.open(file_path)
            sht = wb.sheets[sheet_name]
            used_range = sht.used_range
            values = used_range.value

            headers = values[self.header_row - 1]
            headers = [str(h).strip(
            ) if h is not None else f"Unnamed_{i}" for i, h in enumerate(headers)]

            if self.summary_col not in headers:
                raise ValueError(f"'{self.summary_col}' 컬럼을 찾을 수 없습니다.")

            summary_col_idx_1based = headers.index(self.summary_col) + 1
            data_rows = values[self.header_row:]
            used_start_row = used_range.row
            used_start_col = used_range.column

            records = []
            for i, row in enumerate(data_rows, start=self.header_row + 1):
                row = list(row) if isinstance(row, list) else [row]

                if len(row) < len(headers):
                    row += [None] * (len(headers) - len(row))
                elif len(row) > len(headers):
                    row = row[:len(headers)]

                if all(self.is_blank(v) for v in row):
                    continue

                excel_row = used_start_row + (i - 1)
                excel_col = used_start_col + (summary_col_idx_1based - 1)
                cell = sht.range((excel_row, excel_col))

                indent_level = 0
                try:
                    indent_level = int(cell.api.IndentLevel)
                except Exception:
                    summary_val = row[summary_col_idx_1based - 1]
                    if isinstance(summary_val, str):
                        leading_spaces = len(summary_val) - \
                            len(summary_val.lstrip(" "))
                        indent_level = leading_spaces // 4

                record = dict(zip(headers, row))
                record["_excel_row"] = excel_row
                record["_summary_indent"] = indent_level
                records.append(record)

            return pd.DataFrame(records)

        finally:
            if wb is not None:
                try:
                    wb.close()
                except Exception:
                    pass
            app.quit()

    def merge_multiline_records(
        self,
        raw_df: pd.DataFrame,
        list_cols: list[str],
        keep_mode: str = "first",
        single_to_scalar: bool = False,
    ) -> pd.DataFrame:
        """여러 물리적 행으로 나뉜 한 레코드를 하나의 논리적 행으로 합친다."""
        work = raw_df.copy().reset_index(drop=True)

        group_ids = []
        current_group = 0
        for _, row in work.iterrows():
            if not self.is_blank(row[self.summary_col]):
                current_group += 1
            group_ids.append(current_group)

        work["_group"] = group_ids
        work = work[work["_group"] > 0].copy()

        keep_cols = [c for c in work.columns if c not in [
            self.summary_col, "_group"] + list_cols]
        merged_rows = []

        for _, group_df in work.groupby("_group", sort=True):
            row_out = {
                self.summary_col: self.keep_value(group_df[self.summary_col].tolist(), mode="first"),
                "_summary_indent": self.keep_value(group_df["_summary_indent"].tolist(), mode="first"),
                "_start_excel_row": self.keep_value(group_df["_excel_row"].tolist(), mode="first"),
                "_end_excel_row": self.keep_value(group_df["_excel_row"].tolist(), mode="last"),
            }

            for col in list_cols:
                row_out[col] = self.collect_values(
                    group_df[col].tolist(), single_to_scalar=single_to_scalar)

            for col in keep_cols:
                if col in ["_summary_indent", "_excel_row"]:
                    continue
                row_out[col] = self.keep_value(
                    group_df[col].tolist(), mode=keep_mode)

            merged_rows.append(row_out)

        merged_df = pd.DataFrame(merged_rows).reset_index(drop=True)
        merged_df["_row_id"] = merged_df.index
        return merged_df

    def add_hierarchy_by_indent(self, merged_df: pd.DataFrame) -> pd.DataFrame:
        """들여쓰기 수준을 보고 부모-자식 관계를 계산한다."""
        work = merged_df.copy().reset_index(drop=True)

        parent_row_ids = []
        depths = []
        stack = []
        prev_indent = None

        for idx, row in work.iterrows():
            current_indent = int(row["_summary_indent"]) if not self.is_blank(
                row["_summary_indent"]) else 0

            if prev_indent is not None and current_indent > prev_indent + 1:
                raise ValueError(
                    f"들여쓰기 단계가 1단계 이상 점프했습니다. row_id={idx}, prev={prev_indent}, current={current_indent}"
                )

            while stack and stack[-1]["indent"] >= current_indent:
                stack.pop()

            parent_row_id = stack[-1]["row_id"] if stack else None
            parent_row_ids.append(parent_row_id)
            depths.append(current_indent)

            stack.append({"row_id": idx, "indent": current_indent})
            prev_indent = current_indent

        work["depth"] = depths
        work["parent_row_id"] = parent_row_ids
        return work

    def build_upload_df(self, hierarchy_df: pd.DataFrame, list_cols: list[str] | None = None) -> pd.DataFrame:
        """업로드에 바로 쓸 수 있는 최소 형태의 DataFrame을 만든다."""
        work = hierarchy_df.copy()
        list_cols = list_cols or []

        work["upload_name"] = work[self.summary_col].apply(
            self.normalize_scalar)
        return work
