from __future__ import annotations

import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from src.gui.tracker_query_models import TrackerFieldValue
from src.gui.tracker_table_field_dialog import TrackerTableFieldDialog
from src.gui.tracker_table_field_dialog import table_field_dimensions
from src.gui.tracker_table_field_dialog import table_field_summary


class TrackerTableFieldDialogTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        self.field = TrackerFieldValue.from_raw(
            {
                "fieldId": 1000000,
                "name": "Test Steps",
                "type": "TableFieldValue",
                "columns": [
                    {"id": 1000001, "name": "Action", "type": "WikiTextField"},
                    {"id": 1000002, "name": "Expected", "type": "TextField"},
                ],
                "values": [
                    [
                        {
                            "fieldId": 1000001,
                            "name": "Action",
                            "value": "%%(color:red)__Run__%%",
                        },
                        {
                            "fieldId": 1000002,
                            "name": "Expected",
                            "value": "%%(color:red)raw text%%",
                        },
                    ],
                    [
                        {
                            "fieldId": 1000001,
                            "name": "Action",
                            "type": "WikiTextFieldValue",
                            "value": "Second",
                        }
                    ],
                ],
            }
        )
        self.dialog = TrackerTableFieldDialog(self.field)

    def tearDown(self) -> None:
        self.dialog.close()
        self._app.processEvents()

    def test_table_dimensions_preserve_rows_and_columns(self) -> None:
        self.assertEqual(table_field_dimensions(self.field), (2, 2))
        self.assertEqual(table_field_summary(self.field), "2행 × 2열")
        self.assertEqual(self.dialog.table.rowCount(), 2)
        self.assertEqual(self.dialog.table.columnCount(), 2)

    def test_only_explicit_wiki_column_uses_rich_text_widget(self) -> None:
        wiki_widget = self.dialog.table.cellWidget(0, 0)
        plain_widget = self.dialog.table.cellWidget(0, 1)

        self.assertIsNotNone(wiki_widget)
        self.assertIn("color: red", wiki_widget.text())
        self.assertNotIn("%%", wiki_widget.text())
        self.assertIsNone(plain_widget)
        self.assertEqual(
            self.dialog.table.item(0, 1).text(),
            "%%(color:red)raw text%%",
        )

    def test_source_toggle_restores_raw_wiki_text(self) -> None:
        self.dialog.source_toggle.setChecked(True)
        self._app.processEvents()

        self.assertIsNone(self.dialog.table.cellWidget(0, 0))
        self.assertEqual(
            self.dialog.table.item(0, 0).text(),
            "%%(color:red)__Run__%%",
        )


if __name__ == "__main__":
    unittest.main()
