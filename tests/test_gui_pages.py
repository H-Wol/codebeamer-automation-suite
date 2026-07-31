from __future__ import annotations

import os
import unittest
from types import SimpleNamespace

import pandas as pd

from src.gui.pages import _project_selection_refresh_button_text
from src.gui.pages import _project_selection_source_signature
from src.gui.pages import _project_selection_status_text
from src.gui.pages import _settings_mode_description
from src.gui.pages import _settings_mode_toggle_text
from src.gui.pages import _build_tracker_item_regex_preview_text
from src.gui.pages import _configure_constrained_panel
from src.gui.pages import _tracker_item_sample_values
from src.gui.pages import FileSelectionPage
from src.gui.pages import MappingPage
from src.gui.pages import RootItemPage
from src.gui.pages import UploadPage
from src.gui.pages import create_file_selection_page
from src.gui.pages import create_mapping_page
from src.gui.pages import create_result_page
from src.gui.pages import create_root_item_page
from src.gui.pages import create_upload_page
from src.gui.pages import create_validation_page
from src.gui.settings_store import GuiSettings
from src.gui.styles import build_gui_stylesheet


os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


class GuiPagesSettingsModeTest(unittest.TestCase):
    def test_settings_mode_toggle_text_stays_compact_in_both_states(self) -> None:
        self.assertEqual(_settings_mode_toggle_text(True), "테스트")
        self.assertEqual(_settings_mode_toggle_text(False), "테스트")

    def test_settings_mode_description_changes_by_mode(self) -> None:
        self.assertIn("snapshot", _settings_mode_description(True))
        self.assertIn("Codebeamer", _settings_mode_description(False))


class GuiPagesProjectSelectionTest(unittest.TestCase):
    def test_project_selection_status_text_changes_by_mode(self) -> None:
        self.assertIn("자동으로", _project_selection_status_text(True))
        self.assertIn("프로젝트 불러오기", _project_selection_status_text(False))

    def test_project_selection_refresh_button_text_changes_by_mode(self) -> None:
        self.assertEqual(_project_selection_refresh_button_text(True), "스냅샷 불러오기")
        self.assertEqual(_project_selection_refresh_button_text(False), "프로젝트 불러오기")

    def test_project_selection_source_signature_ignores_selected_project_id(self) -> None:
        base_settings = {
            "offline_mode": True,
            "offline_schema_path": "/tmp/schema.json",
            "offline_tracker_configuration_path": "/tmp/config.json",
            "base_url": "https://example.test",
            "username": "tester",
        }
        left = SimpleNamespace(**base_settings, default_project_id="1")
        right = SimpleNamespace(**base_settings, default_project_id="99")

        self.assertEqual(
            _project_selection_source_signature(left),
            _project_selection_source_signature(right),
        )


class GuiPagesTrackerItemPreviewTest(unittest.TestCase):
    def test_tracker_item_regex_preview_text_shows_single_and_multi_value_examples(self) -> None:
        preview_text = _build_tracker_item_regex_preview_text(
            [
                "Candidate [REQ:20263671] extra",
                ["REQ [REQ:20263672]", "20263673"],
            ],
            pattern=r"\[(?:[^:\]]+:)?(\d+)[^\]]*\]|^(\d+)(?:\.0)?$",
            multiple_values=True,
        )

        self.assertIn("Candidate [REQ:20263671] extra -> 20263671", preview_text)
        self.assertIn("REQ [REQ:20263672], 20263673 -> 20263672, 20263673", preview_text)

    def test_tracker_item_regex_preview_text_shows_short_error_labels(self) -> None:
        preview_text = _build_tracker_item_regex_preview_text(
            ["REQ-ABC"],
            pattern=r"\[(?:[^:\]]+:)?(\d+)[^\]]*\]|^(\d+)(?:\.0)?$",
            multiple_values=False,
        )

        self.assertEqual(preview_text, "REQ-ABC -> 불일치")

    def test_tracker_item_sample_values_skips_blank_and_duplicate_values(self) -> None:
        upload_preview_df = pd.DataFrame({
            "연관 요구사항": [
                "",
                None,
                "REQ-100",
                "REQ-100",
                ["REQ-200", ""],
                ["REQ-200"],
                "REQ-300",
            ]
        })

        sample_values = _tracker_item_sample_values(upload_preview_df, "연관 요구사항")

        self.assertEqual(sample_values, ["REQ-100", ["REQ-200", ""], "REQ-300"])


class GuiPagesUploadPageTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        from PySide6.QtWidgets import QApplication
        from PySide6.QtWidgets import QSizePolicy

        cls._app = QApplication.instance() or QApplication([])
        cls._expanding_policy = QSizePolicy.Policy.Expanding

    def test_upload_page_reset_restores_start_button_state(self) -> None:
        page = create_upload_page(
            lambda: None,
            lambda: None,
            lambda: None,
            lambda: None,
        )

        self.assertIsInstance(page, UploadPage)
        page.start_button.setEnabled(False)
        page.pause_button.setEnabled(True)
        page.resume_button.setEnabled(True)
        page.cancel_button.setEnabled(True)
        page.result_button.setEnabled(True)

        page.reset(3)

        self.assertTrue(page.start_button.isEnabled())
        self.assertFalse(page.pause_button.isEnabled())
        self.assertFalse(page.resume_button.isEnabled())
        self.assertFalse(page.cancel_button.isEnabled())
        self.assertFalse(page.result_button.isEnabled())
        self.assertEqual(page.progress_label.text(), "진행률 0.0% (0 / 3)")
        self.assertEqual(page.eta_label.text(), "예상 종료: -")

    def test_file_selection_preview_table_uses_expanding_layout_space(self) -> None:
        page = create_file_selection_page(
            GuiSettings(),
            lambda _state: None,
            lambda _state: None,
        )

        self.assertIsInstance(page, FileSelectionPage)
        layout = page.layout()
        preview_index = layout.indexOf(page.preview_table)

        self.assertEqual(layout.stretch(preview_index), 1)
        self.assertEqual(
            page.preview_table.sizePolicy().verticalPolicy(),
            self._expanding_policy,
        )

    def test_mapping_page_keeps_tabs_and_tables_expandable(self) -> None:
        page = create_mapping_page(lambda *_args: None)

        self.assertIsInstance(page, MappingPage)
        layout = page.layout()
        tabs_index = layout.indexOf(page.mapping_tabs)

        self.assertEqual(page.mapping_tabs.count(), 3)
        self.assertEqual(layout.stretch(tabs_index), 1)
        self.assertEqual(
            page.mapping_table.sizePolicy().verticalPolicy(),
            self._expanding_policy,
        )
        self.assertEqual(
            page.default_table.sizePolicy().verticalPolicy(),
            self._expanding_policy,
        )
        self.assertEqual(
            page.tracker_item_table.sizePolicy().verticalPolicy(),
            self._expanding_policy,
        )

    def test_mapping_table_checkbox_is_visible_and_clickable(self) -> None:
        from PySide6.QtWidgets import QStyle
        from PySide6.QtWidgets import QStyleOptionButton

        page = create_mapping_page(lambda *_args: None)
        page.load_context(
            "create",
            ["Summary"],
            pd.DataFrame([
                {
                    "field_name": "Summary",
                    "field_type": "TextField",
                    "multiple_values": False,
                    "is_supported": True,
                }
            ]),
            {"Summary": "Summary"},
            {"Summary": {"create": True, "update": False}},
            [],
            {},
            {},
            {},
        )
        previous_stylesheet = self._app.styleSheet()
        try:
            self._app.setStyleSheet(build_gui_stylesheet("kefico"))
            page.show()
            self._app.processEvents()

            checkbox = page.mapping_table.cellWidget(0, 0)
            option = QStyleOptionButton()
            checkbox.initStyleOption(option)
            indicator_rect = checkbox.style().subElementRect(
                QStyle.SubElement.SE_CheckBoxIndicator,
                option,
                checkbox,
            )

            self.assertGreaterEqual(indicator_rect.width(), 15)
            self.assertGreaterEqual(indicator_rect.height(), 15)
            self.assertTrue(checkbox.isChecked())
            checkbox.click()
            self.assertFalse(checkbox.isChecked())
        finally:
            page.close()
            self._app.setStyleSheet(previous_stylesheet)

    def test_root_item_page_is_a_concrete_widget_subclass(self) -> None:
        page = create_root_item_page(lambda *_args: None)

        self.assertIsInstance(page, RootItemPage)

    def test_validation_and_result_pages_prioritize_data_areas(self) -> None:
        validation_page = create_validation_page()
        result_page = create_result_page()

        validation_layout = validation_page.layout()
        result_layout = result_page.layout()

        self.assertEqual(
            validation_layout.stretch(validation_layout.indexOf(validation_page.issue_table)),
            1,
        )
        self.assertEqual(
            validation_page.issue_table.sizePolicy().verticalPolicy(),
            self._expanding_policy,
        )
        self.assertEqual(
            result_layout.stretch(result_layout.indexOf(result_page.result_tabs)),
            1,
        )
        self.assertEqual(
            result_page.tables["success_df"].sizePolicy().verticalPolicy(),
            self._expanding_policy,
        )

    def test_constrained_panel_remains_horizontally_responsive(self) -> None:
        from PySide6.QtWidgets import QWidget

        panel = QWidget()

        _configure_constrained_panel(panel)

        self.assertEqual(
            panel.sizePolicy().horizontalPolicy(),
            self._expanding_policy,
        )
        self.assertGreaterEqual(panel.maximumWidth(), 1_000_000)


if __name__ == "__main__":
    unittest.main()
