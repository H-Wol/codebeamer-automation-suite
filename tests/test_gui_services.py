from __future__ import annotations

from tests.gui_service_fixtures import *

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

    def test_offline_connection_and_tracker_loading_use_local_schema_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            schema_path = Path(tmp_dir) / "offline-schema.json"
            schema_payload = FakeClient("", "", "").get_tracker_schema(0)
            schema_payload["name"] = "Offline Tracker Snapshot"
            schema_path.write_text(json.dumps(schema_payload, ensure_ascii=False), encoding="utf-8")

            service = GuiCodebeamerService(client_factory=FakeClient)
            settings = GuiSettings(
                offline_mode=True,
                offline_schema_path=str(schema_path),
                default_project_id="501",
                default_tracker_id="601",
            )

            projects = service.test_connection_and_load_projects(settings)
            trackers = service.load_trackers(settings, 501)

            self.assertEqual(projects, [{"id": 501, "name": "Offline Project"}])
            self.assertEqual(trackers, [{"id": 601, "name": "Offline Tracker Snapshot"}])


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

            preview = GuiExcelService().load_preview(
                str(path),
                sheet_name="Main",
                header_row=1,
                max_preview_rows=5,
            )

            self.assertEqual(preview.sheet_names, ["Main", "Other"])
            self.assertEqual(preview.headers, ["Summary", "담당자", "비고"])
            self.assertEqual(preview.rows[0], ["REQ-001", "홍길동", "메모"])
            self.assertEqual(preview.suggested_summary, "Summary")

    def test_load_preview_displays_integer_like_numbers_without_decimal_suffix(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir) / "sample.xlsx"
            workbook = Workbook()
            sheet = workbook.active
            sheet.title = "Main"
            sheet.append(["Summary", "번호", "실수"])
            sheet.append(["REQ-001", 101, 1.5])
            sheet.append(["REQ-002", 202, 2.0])
            workbook.save(path)
            workbook.close()

            preview = GuiExcelService(reader_cls=FakeExcelReader).load_preview(
                str(path),
                sheet_name="Main",
                header_row=1,
                max_preview_rows=5,
            )

            self.assertEqual(preview.rows[0], ["REQ-001", "101", "1.5"])
            self.assertEqual(preview.rows[1], ["REQ-002", "202", "2"])

    def test_load_preview_preloads_raw_data_for_all_selected_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            first_path = Path(tmp_dir) / "first.xlsx"
            second_path = Path(tmp_dir) / "second.xlsx"
            for path, summary in (
                (first_path, "REQ-001"),
                (second_path, "REQ-002"),
            ):
                workbook = Workbook()
                sheet = workbook.active
                sheet.title = "Main"
                sheet.append(["Summary", "담당자"])
                sheet.append([summary, "홍길동"])
                workbook.save(path)
                workbook.close()

            CountingBatchExcelReader.reset_counts()
            preview = GuiExcelService(reader_cls=CountingBatchExcelReader).load_preview(
                str(first_path),
                file_paths=[str(first_path), str(second_path)],
                sheet_name="Main",
                header_row=1,
                summary_column="Summary",
            )

            self.assertEqual(
                sorted(preview.raw_df_by_file.keys()),
                sorted([str(first_path), str(second_path)]),
            )
            self.assertEqual(
                CountingBatchExcelReader.read_excel_calls,
                [str(first_path), str(second_path)],
            )
