from __future__ import annotations

import unittest

import pandas as pd

from src.mapping_service import MappingService
from src.models import TrackerItemQueryMatchStrategy
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


class FakeTrackerItemFirstMatchClient(FakeTrackerItemClient):
    def search_tracker_items_by_name(self, *, tracker_id: int, name: str, **kwargs):
        del kwargs
        self.search_calls.append((tracker_id, name))
        if name == "REQ-100":
            return [
                {"id": 101, "name": "REQ-100 candidate A", "type": "TrackerItemReference"},
                {"id": 102, "name": "REQ-100", "type": "TrackerItemReference"},
            ]
        return super().search_tracker_items_by_name(tracker_id=tracker_id, name=name)


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
        self.wizard.state.schema_df["tracker_item_source_tracker_ids"] = [[13526611]]
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

    def test_process_option_mapping_uses_first_tracker_item_query_match(self) -> None:
        self.client = FakeTrackerItemFirstMatchClient()
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
                "multipleValues": False,
                "valueModel": "ChoiceFieldValue<TrackerItemReference>",
            }
        ])
        self.wizard.state.schema_df["tracker_item_source_tracker_ids"] = [[13526611]]
        self.wizard.state.upload_df = pd.DataFrame([
            {"_row_id": 1, "related_item": "REQ-100"},
        ])

        _, option_check_df = self.wizard.process_option_mapping(
            {"related_item": "연관 요구사항"},
            selected_tracker_item_settings={
                "연관 요구사항": {
                    "mode": TrackerItemResolutionMode.QUERY.value,
                    "query_match_strategy": TrackerItemQueryMatchStrategy.FIRST.value,
                    "source_tracker_ids": [13526611],
                }
            },
        )

        self.assertNotIn("TRACKER_ITEM_LOOKUP_AMBIGUOUS", option_check_df["status"].tolist())
        converted = self.wizard.state.converted_upload_df
        self.assertIsNotNone(converted)
        self.assertEqual(converted.iloc[0]["related_item__resolved"]["id"], 101)

    def test_process_option_mapping_uses_last_tracker_item_query_match(self) -> None:
        self.client = FakeTrackerItemFirstMatchClient()
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
                "multipleValues": False,
                "valueModel": "ChoiceFieldValue<TrackerItemReference>",
            }
        ])
        self.wizard.state.schema_df["tracker_item_source_tracker_ids"] = [[13526611]]
        self.wizard.state.upload_df = pd.DataFrame([
            {"_row_id": 1, "related_item": "REQ-100"},
        ])

        _, option_check_df = self.wizard.process_option_mapping(
            {"related_item": "연관 요구사항"},
            selected_tracker_item_settings={
                "연관 요구사항": {
                    "mode": TrackerItemResolutionMode.QUERY.value,
                    "query_match_strategy": TrackerItemQueryMatchStrategy.LAST.value,
                    "source_tracker_ids": [13526611],
                }
            },
        )

        self.assertNotIn("TRACKER_ITEM_LOOKUP_AMBIGUOUS", option_check_df["status"].tolist())
        converted = self.wizard.state.converted_upload_df
        self.assertIsNotNone(converted)
        self.assertEqual(converted.iloc[0]["related_item__resolved"]["id"], 102)

    def test_process_option_mapping_uses_best_tracker_item_query_match(self) -> None:
        self.client = FakeTrackerItemFirstMatchClient()
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
                "multipleValues": False,
                "valueModel": "ChoiceFieldValue<TrackerItemReference>",
            }
        ])
        self.wizard.state.schema_df["tracker_item_source_tracker_ids"] = [[13526611]]
        self.wizard.state.upload_df = pd.DataFrame([
            {"_row_id": 1, "related_item": "REQ-100"},
        ])

        _, option_check_df = self.wizard.process_option_mapping(
            {"related_item": "연관 요구사항"},
            selected_tracker_item_settings={
                "연관 요구사항": {
                    "mode": TrackerItemResolutionMode.QUERY.value,
                    "query_match_strategy": TrackerItemQueryMatchStrategy.BEST.value,
                    "source_tracker_ids": [13526611],
                }
            },
        )

        self.assertNotIn("TRACKER_ITEM_LOOKUP_AMBIGUOUS", option_check_df["status"].tolist())
        converted = self.wizard.state.converted_upload_df
        self.assertIsNotNone(converted)
        self.assertEqual(converted.iloc[0]["related_item__resolved"]["id"], 102)

    def test_process_option_mapping_marks_ambiguous_when_strategy_is_error(self) -> None:
        self.client = FakeTrackerItemFirstMatchClient()
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
                "multipleValues": False,
                "valueModel": "ChoiceFieldValue<TrackerItemReference>",
            }
        ])
        self.wizard.state.schema_df["tracker_item_source_tracker_ids"] = [[13526611]]
        self.wizard.state.upload_df = pd.DataFrame([
            {"_row_id": 1, "related_item": "REQ-100"},
        ])

        _, option_check_df = self.wizard.process_option_mapping(
            {"related_item": "연관 요구사항"},
            selected_tracker_item_settings={
                "연관 요구사항": {
                    "mode": TrackerItemResolutionMode.QUERY.value,
                    "query_match_strategy": TrackerItemQueryMatchStrategy.ERROR.value,
                    "source_tracker_ids": [13526611],
                }
            },
        )

        self.assertIn("TRACKER_ITEM_LOOKUP_AMBIGUOUS", option_check_df["status"].tolist())
        converted = self.wizard.state.converted_upload_df
        self.assertIsNotNone(converted)
        self.assertIsNone(converted.iloc[0]["related_item__resolved"])

    def test_process_option_mapping_ignores_manual_query_ids_without_tracker_config(self) -> None:
        self.wizard.state.schema_df["tracker_item_source_tracker_ids"] = [[]]
        self.client.search_calls = []

        _, option_check_df = self.wizard.process_option_mapping(
            {"related_items": "연관 요구사항"},
            selected_tracker_item_settings={
                "연관 요구사항": {
                    "mode": TrackerItemResolutionMode.QUERY.value,
                    "source_tracker_ids": [13526611],
                }
            },
        )

        self.assertEqual(self.client.search_calls, [])
        self.assertIn("DIRECT_PARSE_FAILED", option_check_df["status"].tolist())
        self.assertNotIn("TRACKER_ITEM_LOOKUP_NOT_FOUND", option_check_df["status"].tolist())
        self.assertNotIn("TRACKER_ITEM_LOOKUP_AMBIGUOUS", option_check_df["status"].tolist())


if __name__ == "__main__":
    unittest.main()
