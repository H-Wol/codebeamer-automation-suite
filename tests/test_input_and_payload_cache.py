from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from typing import Any

import pandas as pd

from src.hierarchy_processor import HierarchyProcessor
from src.mapping_service import MappingService
from src.models import PayloadStatus
from src.models import UploadStatus
from src.wizard import CodebeamerUploadWizard


class StaticSchemaClient:
    def __init__(self, schema: list[dict[str, Any]]) -> None:
        self.schema = schema
        self.create_item_calls: list[dict[str, Any]] = []

    def get_tracker_schema(self, tracker_id: int):
        del tracker_id
        return self.schema

    def create_item(self, tracker_id: int, payload: dict[str, Any], parent_item_id: int | None = None):
        self.create_item_calls.append({
            "tracker_id": tracker_id,
            "payload": payload,
            "parent_item_id": parent_item_id,
        })
        return {"id": 1000 + len(self.create_item_calls)}


class FailingSchemaClient(StaticSchemaClient):
    def create_item(self, tracker_id: int, payload: dict[str, Any], parent_item_id: int | None = None):
        del tracker_id, payload, parent_item_id

        class UploadError(Exception):
            def __init__(self) -> None:
                self.response = type(
                    "Response",
                    (),
                    {
                        "status_code": 400,
                        "json": staticmethod(lambda: {
                            "message": "Invalid tracker item",
                            "details": {"field": "Status"},
                        }),
                    },
                )()
                super().__init__("upload failed")

        raise UploadError()


class CountingWizard(CodebeamerUploadWizard):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.payload_build_calls = 0

    def _build_row_payload(self, row: pd.Series, row_id: int) -> dict[str, Any]:
        self.payload_build_calls += 1
        return super()._build_row_payload(row, row_id)


class HierarchyProcessorSplitTest(unittest.TestCase):
    def test_processor_builds_hierarchy_from_raw_dataframe(self) -> None:
        processor = HierarchyProcessor(summary_col="요약")
        raw_df = pd.DataFrame([
            {"요약": "Parent", "담당": "11", "_excel_row": 2, "_summary_indent": 0},
            {"요약": None, "담당": "12", "_excel_row": 3, "_summary_indent": 0},
            {"요약": "Child", "담당": "13", "_excel_row": 4, "_summary_indent": 1},
        ])

        merged_df = processor.merge_multiline_records(raw_df, list_cols=["담당"])
        hierarchy_df = processor.add_hierarchy_by_indent(merged_df)
        upload_df = processor.build_upload_df(hierarchy_df, list_cols=["담당"])

        self.assertEqual(list(merged_df["요약"]), ["Parent", "Child"])
        self.assertEqual(merged_df.iloc[0]["담당"], ["11", "12"])
        self.assertTrue(pd.isna(hierarchy_df.iloc[0]["parent_row_id"]))
        self.assertEqual(int(hierarchy_df.iloc[1]["parent_row_id"]), 0)
        self.assertEqual(list(upload_df["upload_name"]), ["Parent", "Child"])


class PayloadCacheWizardTest(unittest.TestCase):
    def setUp(self) -> None:
        self.schema = [
            {
                "id": 1,
                "name": "Summary",
                "type": "TextField",
                "trackerItemField": "name",
                "valueModel": "TextFieldValue",
            }
        ]
        self.client = StaticSchemaClient(self.schema)
        self.processor = HierarchyProcessor(summary_col="요약")
        self.mapper = MappingService()

    def _build_wizard(self) -> CountingWizard:
        wizard = CountingWizard(
            client=self.client,
            processor=self.processor,
            mapper=self.mapper,
        )
        wizard.select_project(1)
        wizard.select_tracker(2)
        raw_df = pd.DataFrame([
            {"요약": "REQ-001", "_excel_row": 2, "_summary_indent": 0},
        ])
        wizard.load_raw_dataframe(raw_df, list_cols=[])
        wizard.load_schema_and_compare({"요약": "Summary"})
        wizard.process_option_mapping({"요약": "Summary"})
        return wizard

    def test_preview_and_upload_reuse_same_payload_cache(self) -> None:
        wizard = self._build_wizard()

        preview_payload = wizard.preview_payload(0)
        self.assertEqual(preview_payload["name"], "REQ-001")
        self.assertEqual(wizard.payload_build_calls, 1)

        upload_result = wizard.upload(dry_run=False)

        self.assertEqual(wizard.payload_build_calls, 1)
        self.assertEqual(len(self.client.create_item_calls), 1)
        self.assertEqual(self.client.create_item_calls[0]["payload"], preview_payload)
        self.assertEqual(upload_result["success_df"].iloc[0]["status"], UploadStatus.SUCCESS.value)

    def test_build_payloads_and_save_state_persist_payload_cache(self) -> None:
        wizard = self._build_wizard()

        payload_df = wizard.build_payloads()

        self.assertEqual(list(payload_df["payload_status"]), [PayloadStatus.READY.value])
        self.assertIn("payload_json", payload_df.columns)

        with tempfile.TemporaryDirectory() as tmp_dir:
            wizard.save_state(tmp_dir)

            payload_csv = Path(tmp_dir) / "payload_df.csv"
            payload_jsonl = Path(tmp_dir) / "payload_preview.jsonl"

            self.assertTrue(payload_csv.exists())
            self.assertTrue(payload_jsonl.exists())

            payload_df_saved = pd.read_csv(payload_csv)
            self.assertEqual(payload_df_saved.iloc[0]["payload_status"], PayloadStatus.READY.value)

            first_line = payload_jsonl.read_text(encoding="utf-8").strip().splitlines()[0]
            saved_payload = json.loads(first_line)
            self.assertEqual(saved_payload["payload_status"], PayloadStatus.READY.value)
            self.assertEqual(saved_payload["payload_json"]["name"], "REQ-001")

    def test_upload_failure_persists_response_json(self) -> None:
        wizard = CountingWizard(
            client=FailingSchemaClient(self.schema),
            processor=self.processor,
            mapper=self.mapper,
        )
        wizard.select_project(1)
        wizard.select_tracker(2)
        raw_df = pd.DataFrame([
            {"요약": "REQ-001", "_excel_row": 2, "_summary_indent": 0},
        ])
        wizard.load_raw_dataframe(raw_df, list_cols=[])
        wizard.load_schema_and_compare({"요약": "Summary"})
        wizard.process_option_mapping({"요약": "Summary"})

        upload_result = wizard.upload(dry_run=False, continue_on_error=True)

        failed_df = upload_result["failed_df"]
        self.assertEqual(failed_df.iloc[0]["error_status_code"], 400)
        self.assertEqual(
            failed_df.iloc[0]["error_response_json"],
            {"message": "Invalid tracker item", "details": {"field": "Status"}},
        )

        with tempfile.TemporaryDirectory() as tmp_dir:
            wizard.save_state(tmp_dir)

            failed_csv = Path(tmp_dir) / "failed_df.csv"
            failed_jsonl = Path(tmp_dir) / "failed_responses.jsonl"

            self.assertTrue(failed_csv.exists())
            self.assertTrue(failed_jsonl.exists())

            failed_df_saved = pd.read_csv(failed_csv)
            self.assertEqual(int(failed_df_saved.iloc[0]["error_status_code"]), 400)
            self.assertIn("Invalid tracker item", failed_df_saved.iloc[0]["error_response_json"])

            first_line = failed_jsonl.read_text(encoding="utf-8").strip().splitlines()[0]
            saved_failure = json.loads(first_line)
            self.assertEqual(saved_failure["error_status_code"], 400)
            self.assertEqual(saved_failure["error_response_json"]["message"], "Invalid tracker item")


if __name__ == "__main__":
    unittest.main()
