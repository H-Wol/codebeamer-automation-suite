from __future__ import annotations

import unittest

import pandas as pd

from src.gui.pages import _build_tracker_item_regex_preview_text
from src.gui.pages import _tracker_item_sample_values


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
