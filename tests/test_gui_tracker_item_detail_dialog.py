from __future__ import annotations

import base64
import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from src.gui.tracker_content_models import AttachmentResource
from src.gui.tracker_content_models import AttachmentSummary
from src.gui.tracker_item_detail_dialog import TrackerItemDetailDialog
from src.gui.tracker_query_models import TrackerItemDetail


PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
)


class TrackerItemDetailDialogTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        from PySide6.QtWidgets import QApplication

        cls.app = QApplication.instance() or QApplication([])

    def detail(self) -> TrackerItemDetail:
        return TrackerItemDetail.from_raw(
            {
                "id": 1205,
                "name": "Large detail",
                "description": "설명",
                "version": 4,
                "status": {"id": 1, "name": "Open"},
                "tracker": {
                    "id": 24680001,
                    "name": "Requirements",
                    "project": {"id": 246800, "name": "Sample Project"},
                },
                "customFields": [
                    {"fieldId": 1000, "name": "Risk", "type": "TextFieldValue", "value": "Low"}
                ],
            }
        )

    def test_dialog_shows_full_detail_and_zoomable_image(self) -> None:
        dialog = TrackerItemDetailDialog(
            self.detail(),
            description_html="<p>설명</p>",
            attachments=(AttachmentSummary(28, "sample.png", mime_type="image/png"),),
            image_resources=(AttachmentResource("attachment-28", "image/png", PNG),),
        )
        dialog.show()
        self.app.processEvents()

        self.assertIn("#1205", dialog.windowTitle())
        self.assertEqual(dialog.image_combo.count(), 1)
        self.assertIn("확대", dialog.image_status.text())
        dialog.image_view.actual_size()
        self.assertAlmostEqual(dialog.image_view.transform().m11(), 1.0)
        dialog.image_view.zoom_in()
        self.assertAlmostEqual(dialog.image_view.transform().m11(), 1.25)
        dialog.image_view.zoom_out()
        self.assertAlmostEqual(dialog.image_view.transform().m11(), 1.0)
        dialog.close()

    def test_dialog_disables_image_controls_without_loaded_resource(self) -> None:
        dialog = TrackerItemDetailDialog(
            self.detail(),
            description_html="<p>설명</p>",
            attachments=(AttachmentSummary(29, "sample.pdf", mime_type="application/pdf"),),
        )

        self.assertEqual(dialog.image_combo.count(), 0)
        self.assertFalse(dialog.image_combo.isEnabled())
        self.assertIn("없습니다", dialog.image_status.text())


if __name__ == "__main__":
    unittest.main()
