from __future__ import annotations

import unittest
from unittest.mock import Mock
from unittest.mock import patch

import cli_main
import main as legacy_main
from src.cli_excel_utils import list_sheet_names
from src.cli_excel_utils import read_headers
from src.excel_processor import ExcelHierarchyProcessor
from src.hierarchy_processor import HierarchyProcessor


class CompatibilityWrapperTest(unittest.TestCase):
    def test_legacy_main_delegates_to_current_cli_entry_point(self) -> None:
        self.assertIs(legacy_main.main, cli_main.main)

    def test_excel_hierarchy_processor_preserves_hierarchy_contract(self) -> None:
        self.assertTrue(issubclass(ExcelHierarchyProcessor, HierarchyProcessor))

    @patch("src.cli_excel_utils.ExcelReader")
    def test_cli_excel_helpers_delegate_to_excel_reader(self, reader_type: Mock) -> None:
        reader_type.return_value.list_sheet_names.return_value = ["Sheet1"]
        reader_type.return_value.read_headers.return_value = ["Summary"]

        self.assertEqual(list_sheet_names("sample.xlsx"), ["Sheet1"])
        self.assertEqual(read_headers("sample.xlsx", "Sheet1", header_row=3), ["Summary"])
        reader_type.assert_any_call()
        reader_type.assert_any_call(header_row=3)


if __name__ == "__main__":
    unittest.main()
