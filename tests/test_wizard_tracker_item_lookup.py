from __future__ import annotations

import unittest

import pandas as pd

from src.mapping_service import MappingService
from src.models import TrackerItemResolutionMode
from src.wizard import CodebeamerUploadWizard


class FakeTrackerItemClient:
    def __init__(self) -> None:
        self.search_calls: list[tuple[int, str]] = []

    def search_tracker_items_by_name(self, *, tracker_id: int, name: str, **kwargs):
        del kwargs
        self.search_calls.append((tracker_id, name))
        lookup = {
            "REQ-100": [{"id": 101, "name": "REQ-100", "type": "TrackerItemReference"}],
            "REQ-200": [{"id": 202, "name": "REQ-200", "type": "TrackerItemReference"}],
        }
        return lookup.get(name, [])


class WizardTrackerItemLookupTest(unittest.TestCase):
    def setUp(self) -> None:
        self.client = FakeTrackerItemClient()
        self.mapper = MappingService()
        self.wizard = CodebeamerUploadWizard(
            client=self.client,
            processor=None,
            mapper=self.mapper,
        )
        self.wizard.state.schema_df = self.mapper.flatten_schema_fields([
            {
                "id": 15,
                "name": "연관 요구사항",
                "type": "TrackerItemChoiceField",
                "multipleValues": True,
                "valueModel": "ChoiceFieldValue<TrackerItemReference>",
            }
        ])
        self.wizard.state.upload_df = pd.DataFrame([
            {"_row_id": 1, "related_items": ["REQ-100", "REQ-200"]},
            {"_row_id": 2, "related_items": ["REQ-100"]},
        ])

    def test_process_option_mapping_deduplicates_tracker_item_query_values(self) -> None:
        self.wizard.process_option_mapping(
            {"related_items": "연관 요구사항"},
            selected_tracker_item_settings={
                "연관 요구사항": {
                    "mode": TrackerItemResolutionMode.QUERY.value,
                    "source_tracker_ids": [13526611],
                }
            },
        )

        self.assertEqual(
            self.client.search_calls,
            [(13526611, "REQ-100"), (13526611, "REQ-200")],
        )

        converted = self.wizard.state.converted_upload_df
        self.assertIsNotNone(converted)
        first_values = converted.iloc[0]["related_items__resolved"]
        second_values = converted.iloc[1]["related_items__resolved"]
        self.assertEqual([value["id"] for value in first_values], [101, 202])
        self.assertEqual([value["id"] for value in second_values], [101])


if __name__ == "__main__":
    unittest.main()
