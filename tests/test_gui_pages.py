from __future__ import annotations

import unittest
from types import SimpleNamespace

import pandas as pd

from src.gui.pages import _project_selection_refresh_button_text
from src.gui.pages import _project_selection_source_signature
from src.gui.pages import _project_selection_status_text
from src.gui.pages import _settings_mode_description
from src.gui.pages import _settings_mode_toggle_text
from src.gui.pages import _build_tracker_item_regex_preview_text
from src.gui.pages import _tracker_item_sample_values


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


if __name__ == "__main__":
    unittest.main()
