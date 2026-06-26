from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from typing import Any

from src.mapping_service import MappingService
from src.tracker_contract import build_tracker_contract_bundle
from src.tracker_contract import save_tracker_contract_bundle
from src.tracker_contract import scaffold_start_kit_templates


class StaticSchemaClient:
    def __init__(self, schema: dict[str, Any]) -> None:
        self.schema = schema

    def get_tracker_schema(self, tracker_id: int) -> dict[str, Any]:
        del tracker_id
        return self.schema


class TrackerContractTest(unittest.TestCase):
    def setUp(self) -> None:
        self.schema = {
            "fields": [
                {
                    "id": 1,
                    "name": "Summary",
                    "type": "TextField",
                    "trackerItemField": "name",
                    "valueModel": "TextFieldValue",
                },
                {
                    "id": 2,
                    "name": "Status",
                    "type": "OptionChoiceField",
                    "trackerItemField": "status",
                    "valueModel": "ChoiceFieldValue<ChoiceOptionReference>",
                    "options": [
                        {"id": 101, "name": "Open", "type": "ChoiceOptionReference"},
                    ],
                },
                {
                    "id": 3,
                    "name": "Owner",
                    "type": "ReferenceField",
                    "referenceType": "UserReference",
                    "valueModel": "ChoiceFieldValue<UserReference>",
                },
                {
                    "id": 4,
                    "name": "Mystery",
                    "type": "ReferenceField",
                },
            ]
        }
        self.client = StaticSchemaClient(self.schema)
        self.mapper = MappingService()

    def test_build_tracker_contract_bundle_marks_runtime_schema_as_source_of_truth(self) -> None:
        bundle = build_tracker_contract_bundle(
            client=self.client,
            mapper=self.mapper,
            project_id=10,
            tracker_id=20,
        )

        self.assertEqual(bundle.project_id, 10)
        self.assertEqual(bundle.tracker_id, 20)
        self.assertTrue(bundle.contract["schema_policy"]["fetch_at_runtime"])
        self.assertEqual(
            bundle.contract["schema_policy"]["runtime_endpoint"],
            "/v3/trackers/20/schema",
        )
        self.assertIn("Summary", [field["field_name"] for field in bundle.contract["field_summary"]["builtin_fields"]])
        self.assertIn("Owner", bundle.contract["field_summary"]["lookup_required_fields"])
        self.assertEqual(bundle.contract["field_summary"]["unsupported_fields"][0]["field_name"], "Mystery")

    def test_save_tracker_contract_bundle_writes_contract_files(self) -> None:
        bundle = build_tracker_contract_bundle(
            client=self.client,
            mapper=self.mapper,
            project_id=10,
            tracker_id=20,
        )

        with tempfile.TemporaryDirectory() as tmp_dir:
            written_files = save_tracker_contract_bundle(bundle, tmp_dir)

            for path in written_files.values():
                self.assertTrue(path.exists())

            contract = json.loads((Path(tmp_dir) / "tracker-contract.json").read_text(encoding="utf-8"))
            self.assertEqual(contract["tracker_id"], 20)
            self.assertTrue(contract["schema_policy"]["fetch_at_runtime"])

    def test_scaffold_start_kit_templates_copies_missing_files_only(self) -> None:
        template_dir = Path(tempfile.mkdtemp())
        output_dir = Path(tempfile.mkdtemp())
        try:
            readme_path = template_dir / "README.md"
            nested_path = template_dir / "nested" / "config.json"
            nested_path.parent.mkdir(parents=True, exist_ok=True)
            readme_path.write_text("template readme", encoding="utf-8")
            nested_path.write_text('{"ok": true}', encoding="utf-8")

            copied_files = scaffold_start_kit_templates(template_dir, output_dir)
            self.assertEqual(len(copied_files), 2)
            self.assertTrue((output_dir / "README.md").exists())
            self.assertTrue((output_dir / "nested" / "config.json").exists())

            (output_dir / "README.md").write_text("customized", encoding="utf-8")
            copied_files_second = scaffold_start_kit_templates(template_dir, output_dir)
            self.assertEqual(copied_files_second, [])
            self.assertEqual((output_dir / "README.md").read_text(encoding="utf-8"), "customized")
        finally:
            for root in (template_dir, output_dir):
                for path in sorted(root.rglob("*"), reverse=True):
                    if path.is_file():
                        path.unlink()
                    elif path.is_dir():
                        path.rmdir()
                root.rmdir()


if __name__ == "__main__":
    unittest.main()
