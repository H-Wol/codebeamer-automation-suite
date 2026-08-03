from __future__ import annotations

import unittest

from src.gui.wiki_renderer import codebeamer_wiki_to_html
from src.gui.wiki_renderer import is_explicit_wiki_type
from src.gui.wiki_renderer import payload_uses_wiki
from src.gui.wiki_renderer import sanitize_wiki_style


class WikiRendererTest(unittest.TestCase):
    def test_wiki_detection_requires_explicit_metadata(self) -> None:
        self.assertTrue(is_explicit_wiki_type("WikiTextField"))
        self.assertTrue(is_explicit_wiki_type("WikiTextFieldValue"))
        self.assertTrue(payload_uses_wiki({"descriptionFormat": "Wiki"}))
        self.assertFalse(payload_uses_wiki({"type": "TextFieldValue"}))
        self.assertFalse(payload_uses_wiki({"value": "%%(color:red)text%%"}))

    def test_style_block_is_rendered_and_theme_foreground_is_removed(self) -> None:
        rendered = codebeamer_wiki_to_html(
            "%%(color:black;font-style:normal;)안전한 내용%%"
        )

        self.assertEqual(
            rendered,
            '<span style="font-style: normal">안전한 내용</span>',
        )

    def test_named_color_and_basic_emphasis_are_rendered(self) -> None:
        rendered = codebeamer_wiki_to_html("%%red __중요__%%")

        self.assertEqual(
            rendered,
            '<span style="color: red"><strong>중요</strong></span>',
        )

    def test_unsafe_html_and_css_are_not_executed(self) -> None:
        rendered = codebeamer_wiki_to_html(
            "%%(color:url(evil);font-weight:bold)"
            "<script>alert(1)</script>%%"
        )

        self.assertNotIn("url(", rendered)
        self.assertNotIn("<script>", rendered)
        self.assertIn("&lt;script&gt;", rendered)
        self.assertIn("font-weight: bold", rendered)

    def test_style_sanitizer_keeps_only_allowlisted_properties(self) -> None:
        style = sanitize_wiki_style(
            "color:#336699; position:fixed; text-decoration:underline"
        )

        self.assertEqual(style, "color: #336699; text-decoration: underline")


if __name__ == "__main__":
    unittest.main()
