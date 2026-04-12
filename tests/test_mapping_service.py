from __future__ import annotations

import unittest

import pandas as pd

from src.mapping_service import MappingService


class MappingServiceTest(unittest.TestCase):
    def setUp(self) -> None:
        self.service = MappingService()

    def test_get_list_columns_for_mapping_returns_only_multiple_value_fields(self) -> None:
        schema_df = pd.DataFrame([
            {"field_name": "Summary", "multiple_values": False},
            {"field_name": "Assignees", "multiple_values": True},
            {"field_name": "Categories", "multiple_values": "true"},
            {"field_name": "Priority", "multiple_values": None},
        ])
        selected_mapping = {
            "요약": "Summary",
            "담당자": "Assignees",
            "분류": "Categories",
            "우선순위": "Priority",
        }

        list_columns = self.service.get_list_columns_for_mapping(selected_mapping, schema_df)

        self.assertEqual(list_columns, ["담당자", "분류"])

    def test_get_list_columns_for_mapping_returns_empty_for_empty_mapping(self) -> None:
        schema_df = pd.DataFrame([
            {"field_name": "Assignees", "multiple_values": True},
        ])

        list_columns = self.service.get_list_columns_for_mapping({}, schema_df)

        self.assertEqual(list_columns, [])


if __name__ == "__main__":
    unittest.main()
