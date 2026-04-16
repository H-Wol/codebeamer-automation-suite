from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from openpyxl import Workbook
import pandas as pd

from src.gui.services import GuiCodebeamerService
from src.gui.services import GuiExcelService
from src.gui.services import GuiUploadPipelineService
from src.gui.settings_store import GuiSettings


class FakeExcelReader:
    def __init__(self, header_row: int = 1, summary_col: str = "Summary", logger=None) -> None:
        del logger
        self.header_row = header_row
        self.summary_col = summary_col

    def list_sheet_names(self, file_path: str) -> list[str]:
        from openpyxl import load_workbook
        wb = load_workbook(file_path, read_only=True, data_only=True)
        try:
            return wb.sheetnames
        finally:
            wb.close()

    def read_headers(self, file_path: str, sheet_name: str | int) -> list[str]:
        from openpyxl import load_workbook
        wb = load_workbook(file_path, read_only=True, data_only=True)
        try:
            ws = wb[sheet_name]
            row = next(ws.iter_rows(min_row=self.header_row, max_row=self.header_row, values_only=True), ())
            return [str(value).strip() if value is not None else f"Unnamed_{index}" for index, value in enumerate(row)]
        finally:
            wb.close()

    def read_excel(self, file_path: str, sheet_name: str | int = 0, visible: bool = False) -> pd.DataFrame:
        del visible
        from openpyxl import load_workbook
        wb = load_workbook(file_path, read_only=True, data_only=True)
        try:
            ws = wb[sheet_name]
            rows = list(ws.iter_rows(values_only=True))
            headers = self.read_headers(file_path, sheet_name)
            summary_index = headers.index(self.summary_col)
            records = []
            for excel_row, values in enumerate(rows[self.header_row:], start=self.header_row + 1):
                normalized = list(values)
                if all(value is None or str(value).strip() == "" for value in normalized[:len(headers)]):
                    continue
                record = {header: normalized[index] if index < len(normalized) else None for index, header in enumerate(headers)}
                record["_excel_row"] = excel_row
                record["_summary_indent"] = 0 if normalized[summary_index] is not None else 0
                records.append(record)
            return pd.DataFrame(records)
        finally:
            wb.close()


class FakeClient:
    def __init__(self, base_url, username, password, logger=None, **kwargs) -> None:
        del logger, kwargs
        self.base_url = base_url
        self.username = username
        self.password = password

    def get_projects(self):
        return [
            {"id": 10, "name": "Project A"},
            {"id": 20, "name": "Project B"},
        ]

    def get_trackers(self, project_id: int):
        return [
            {"id": project_id * 100, "name": f"Tracker {project_id}-1"},
            {"id": project_id * 100 + 1, "name": f"Tracker {project_id}-2"},
        ]

    def get_tracker_schema(self, tracker_id: int):
        del tracker_id
        return {
            "fields": [
                {
                    "id": 1,
                    "name": "Summary",
                    "type": "TextField",
                    "trackerItemField": "name",
                    "valueModel": "TextFieldValue",
                    "multipleValues": False,
                },
                {
                    "id": 2,
                    "name": "담당자",
                    "type": "TextField",
                    "trackerItemField": None,
                    "valueModel": "TextFieldValue",
                    "multipleValues": False,
                },
                {
                    "id": 3,
                    "name": "id",
                    "type": "TextField",
                    "trackerItemField": "id",
                    "valueModel": "TextFieldValue",
                    "multipleValues": False,
                },
                {
                    "id": 4,
                    "name": "parent",
                    "type": "TextField",
                    "trackerItemField": "parent",
                    "valueModel": "TextFieldValue",
                    "multipleValues": False,
                },
                {
                    "id": 5,
                    "name": "테이블필드",
                    "type": "TableField",
                    "trackerItemField": None,
                    "valueModel": "TableFieldValue",
                    "multipleValues": False,
                    "columns": [
                        {
                            "id": 31,
                            "name": "컬럼A",
                            "type": "TextField",
                            "valueModel": "TextFieldValue",
                        }
                    ],
                },
            ]
        }


class GuiCodebeamerServiceTest(unittest.TestCase):
    def test_connection_and_tracker_loading(self) -> None:
        service = GuiCodebeamerService(client_factory=FakeClient)
        settings = GuiSettings(
            base_url="https://example.com/cb",
            username="user",
            password="secret",
            rate_limit_retry_delay_seconds=1.0,
            rate_limit_max_retries=5,
        )

        projects = service.test_connection_and_load_projects(settings)
        trackers = service.load_trackers(settings, 10)

        self.assertEqual(projects[0]["id"], 10)
        self.assertEqual(projects[0]["name"], "Project A")
        self.assertEqual(trackers[0]["id"], 1000)
        self.assertEqual(trackers[1]["name"], "Tracker 10-2")


class GuiExcelServiceTest(unittest.TestCase):
    def test_load_preview_reads_sheet_names_headers_rows_and_summary(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir) / "sample.xlsx"
            workbook = Workbook()
            sheet = workbook.active
            sheet.title = "Main"
            sheet.append(["Summary", "담당자", "비고"])
            sheet.append(["REQ-001", "홍길동", "메모"])
            sheet.append(["REQ-002", "김철수", "메모2"])
            workbook.create_sheet("Other")
            workbook.save(path)
            workbook.close()

            preview = GuiExcelService(reader_cls=FakeExcelReader).load_preview(
                str(path),
                sheet_name="Main",
                header_row=1,
                max_preview_rows=5,
            )

            self.assertEqual(preview.sheet_names, ["Main", "Other"])
            self.assertEqual(preview.headers, ["Summary", "담당자", "비고"])
            self.assertEqual(preview.rows[0], ["REQ-001", "홍길동", "메모"])
            self.assertEqual(preview.suggested_summary, "Summary")


class GuiUploadPipelineServiceTest(unittest.TestCase):
    def test_prepare_mapping_context_builds_upload_columns_and_default_mapping(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir) / "sample.xlsx"
            workbook = Workbook()
            sheet = workbook.active
            sheet.title = "Main"
            sheet.append(["Summary", "담당자", "테이블필드.컬럼A", "id", "parent"])
            sheet.append(["REQ-001", "홍길동", "값1", "1", ""])
            workbook.save(path)
            workbook.close()

            excel_service = GuiExcelService(reader_cls=FakeExcelReader)
            service = GuiUploadPipelineService(
                client_factory=FakeClient,
                excel_service=excel_service,
                reader_cls=FakeExcelReader,
            )
            settings = GuiSettings(
                base_url="https://example.com/cb",
                username="user",
                password="secret",
                default_project_id="10",
                default_tracker_id="1000",
                excel_header_row=1,
                summary_column="Summary",
                excel_sheet_name="Main",
            )
            mapping_context = service.prepare_mapping_context(
                settings,
                {
                    "file_path": str(path),
                    "sheet_name": "Main",
                    "header_row": 1,
                    "summary_column": "Summary",
                },
            )

            self.assertIn("Summary", mapping_context.upload_columns)
            self.assertIn("담당자", mapping_context.upload_columns)
            self.assertIn("테이블필드.컬럼A", mapping_context.upload_columns)
            self.assertNotIn("id", mapping_context.upload_columns)
            self.assertNotIn("parent", mapping_context.upload_columns)
            self.assertNotIn("id", mapping_context.schema_df["field_name"].tolist())
            self.assertNotIn("parent", mapping_context.schema_df["field_name"].tolist())
            self.assertEqual(mapping_context.selected_mapping["Summary"], "Summary")
            self.assertEqual(mapping_context.selected_mapping["담당자"], "담당자")
            self.assertEqual(mapping_context.selected_mapping["테이블필드.컬럼A"], "테이블필드")

    def test_build_user_issue_df_keeps_only_user_visible_issues(self) -> None:
        service = GuiUploadPipelineService(client_factory=FakeClient)
        comparison_df = pd.DataFrame([
            {"df_column": "_row_id", "selected_schema_field": "", "status": "unmapped"},
            {"df_column": "담당자", "selected_schema_field": "", "status": "unmapped"},
        ])
        option_check_df = pd.DataFrame([
            {"df_column": "담당자", "schema_field": "담당자", "status": "USER_NOT_FOUND"},
            {"df_column": "상태", "schema_field": "Status", "status": "PRECONSTRUCTION_REQUIRED"},
        ])
        payload_df = pd.DataFrame([
            {"upload_name": "REQ-001", "payload_status": "failed", "payload_error": "payload error"},
        ])

        visible_comparison_df = service._gui_visible_comparison_df(comparison_df)
        issue_df = service._build_user_issue_df(visible_comparison_df, option_check_df, payload_df)

        self.assertFalse((issue_df["column"] == "_row_id").any())
        self.assertTrue((issue_df["column"] == "담당자").any())
        self.assertTrue(issue_df["message"].str.contains("사용자를 찾지 못했습니다").any())
        self.assertTrue(issue_df["message"].str.contains("payload error").any())
