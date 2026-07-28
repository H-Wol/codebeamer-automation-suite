from __future__ import annotations

import unittest

from src.gui.main_window import _estimate_upload_remaining_seconds
from src.gui.main_window import _format_clock_text
from src.gui.main_window import _format_upload_eta_text
from src.gui.main_window import _format_upload_progress_text
from src.gui.main_window import _merge_root_item_page_configs
from src.gui.main_window import _merge_window_preferences
from src.gui.main_window import _window_size_from_settings
from src.gui.settings_store import GuiSettings


class GuiMainWindowProgressTest(unittest.TestCase):
    def test_estimate_upload_remaining_seconds_returns_none_without_completed_rows(self) -> None:
        self.assertIsNone(_estimate_upload_remaining_seconds(12.0, 0, 10))

    def test_estimate_upload_remaining_seconds_uses_average_per_completed_row(self) -> None:
        self.assertAlmostEqual(_estimate_upload_remaining_seconds(20.0, 4, 10), 30.0)

    def test_format_upload_progress_text_includes_percentage_and_counts(self) -> None:
        self.assertEqual(_format_upload_progress_text(3, 8), "진행률 37.5% (3 / 8)")

    def test_format_upload_eta_text_returns_unknown_when_estimate_is_not_ready(self) -> None:
        self.assertEqual(
            _format_upload_eta_text(
                now_timestamp=1_700_000_000.0,
                elapsed_seconds=5.0,
                completed_count=0,
                total_count=10,
            ),
            "예상 종료: -",
        )

    def test_format_upload_eta_text_returns_finish_clock_and_remaining_duration(self) -> None:
        now_timestamp = 1_700_000_000.0
        finish_timestamp = now_timestamp + 30.0
        self.assertEqual(
            _format_upload_eta_text(
                now_timestamp=now_timestamp,
                elapsed_seconds=30.0,
                completed_count=3,
                total_count=6,
            ),
            f"예상 종료: {_format_clock_text(finish_timestamp)} (남은 약 30.0초)",
        )

    def test_format_upload_eta_text_marks_completed_batches(self) -> None:
        now_timestamp = 1_700_000_000.0
        self.assertEqual(
            _format_upload_eta_text(
                now_timestamp=now_timestamp,
                elapsed_seconds=30.0,
                completed_count=6,
                total_count=6,
            ),
            f"예상 종료: 완료됨 ({_format_clock_text(now_timestamp)})",
        )


class GuiMainWindowRootConfigMergeTest(unittest.TestCase):
    def test_merge_root_item_page_configs_preserves_structure_and_field_values(self) -> None:
        merged = _merge_root_item_page_configs(
            {"enabled": False, "group_enabled": False},
            structure_config={
                "enabled": True,
                "group_enabled": True,
                "group_by_column": "Folder",
            },
            field_config={
                "field_assignments": {
                    "Summary": {"enabled": True, "mode": "fixed_value", "value": "REQ"}
                },
                "field_sources": {"Summary": "__file_stem__"},
            },
        )

        self.assertTrue(merged["enabled"])
        self.assertTrue(merged["group_enabled"])
        self.assertEqual(merged["group_by_column"], "Folder")
        self.assertEqual(
            merged["field_assignments"],
            {"Summary": {"enabled": True, "mode": "fixed_value", "value": "REQ"}},
        )
        self.assertEqual(merged["field_sources"], {"Summary": "__file_stem__"})


class GuiMainWindowPreferencesTest(unittest.TestCase):
    def test_window_size_from_settings_clamps_invalid_values(self) -> None:
        settings = GuiSettings(window_width=400, window_height="bad")

        self.assertEqual(_window_size_from_settings(settings), (860, 780))

    def test_merge_window_preferences_preserves_current_window_state(self) -> None:
        current = GuiSettings(
            window_width=1440,
            window_height=900,
            window_is_maximized=False,
            window_is_fullscreen=True,
            theme_name="kefico",
        )
        incoming = GuiSettings(
            window_width=1160,
            window_height=780,
            window_is_maximized=True,
            window_is_fullscreen=False,
            theme_name="igloo",
        )

        merged = _merge_window_preferences(current, incoming)

        self.assertEqual(merged.window_width, 1440)
        self.assertEqual(merged.window_height, 900)
        self.assertFalse(merged.window_is_maximized)
        self.assertTrue(merged.window_is_fullscreen)
        self.assertEqual(merged.theme_name, "igloo")


if __name__ == "__main__":
    unittest.main()
