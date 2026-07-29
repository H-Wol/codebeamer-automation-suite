from __future__ import annotations

from types import SimpleNamespace
import unittest
from unittest.mock import Mock

import pandas as pd

from src.gui.batch_upload import BatchUploadService
from src.models import PayloadStatus
from src.upload_policy import UPLOAD_MODE_UPSERT


class BatchUploadServiceTest(unittest.TestCase):
    def setUp(self) -> None:
        self.service = BatchUploadService(
            mapper=Mock(),
            create_wizard=Mock(),
            root_items=Mock(),
            batch_validation=Mock(),
        )

    def test_phase_ready_counts_separate_upsert_create_and_update(self) -> None:
        wizard = SimpleNamespace(
            state=SimpleNamespace(
                upload_mode=UPLOAD_MODE_UPSERT,
                payload_df=pd.DataFrame(
                    [
                        {
                            "payload_status": PayloadStatus.READY.value,
                            "_operation": "create",
                        },
                        {
                            "payload_status": PayloadStatus.READY.value,
                            "_operation": "update",
                        },
                    ]
                ),
            )
        )

        insert_count, update_count = self.service._phase_ready_counts(
            wizard,
            root_item_specs=[Mock()],
        )

        self.assertEqual(insert_count, 2)
        self.assertEqual(update_count, 1)

    def test_batch_output_dir_is_stable_per_file_index(self) -> None:
        output_dir = self.service._batch_output_dir(
            "output",
            "folder/Requirements.xlsx",
            3,
        )

        self.assertTrue(output_dir.endswith("003_Requirements"))


if __name__ == "__main__":
    unittest.main()
