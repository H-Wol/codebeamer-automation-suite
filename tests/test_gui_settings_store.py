from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from src.gui.settings_store import GuiSettings
from src.gui.settings_store import GuiSettingsStore
from src.gui.settings_store import GuiWorkflowPreset


try:
    import cryptography  # noqa: F401
except ImportError:  # pragma: no cover
    CRYPTOGRAPHY_AVAILABLE = False
else:
    CRYPTOGRAPHY_AVAILABLE = True


@unittest.skipUnless(CRYPTOGRAPHY_AVAILABLE, "cryptography 패키지가 설치된 환경에서만 실행")
class GuiSettingsStoreTest(unittest.TestCase):
    def test_save_without_password_does_not_store_encrypted_value(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            store = GuiSettingsStore(Path(tmp_dir))
            settings = GuiSettings(
                base_url="https://example.com/cb",
                username="user",
                password="secret",
                save_password=False,
            )

            store.save(settings)
            payload = json.loads(store.settings_path.read_text(encoding="utf-8"))

            self.assertEqual(payload["password_encrypted"], "")
            loaded = store.load()
            self.assertEqual(loaded.password, "")
            self.assertFalse(loaded.save_password)

    def test_save_with_password_encrypts_and_restores_password(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            store = GuiSettingsStore(Path(tmp_dir))
            settings = GuiSettings(
                base_url="https://example.com/cb",
                username="user",
                password="secret",
                save_password=True,
                summary_column="Summary",
            )

            store.save(settings)
            payload = json.loads(store.settings_path.read_text(encoding="utf-8"))

            self.assertNotEqual(payload["password_encrypted"], "")
            self.assertNotIn("secret", store.settings_path.read_text(encoding="utf-8"))

            loaded = store.load()
            self.assertEqual(loaded.password, "secret")
            self.assertTrue(loaded.save_password)
            self.assertEqual(loaded.summary_column, "Summary")

    def test_save_and_load_workflow_preset_preserves_nested_configuration(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            store = GuiSettingsStore(Path(tmp_dir))
            preset = GuiWorkflowPreset(
                settings=GuiSettings(
                    base_url="https://example.com/cb",
                    username="user",
                    password="secret",
                    save_password=True,
                    default_project_id="10",
                    default_tracker_id="1000",
                    excel_header_row=2,
                    summary_column="요약",
                    excel_sheet_name="Main",
                ),
                file_options={
                    "sheet_name": "Main",
                    "header_row": 2,
                    "summary_column": "요약",
                },
                root_item_config={
                    "enabled": False,
                    "regex_pattern": r"^(?P<name>.+)$",
                    "field_assignments": {
                        "Summary": {
                            "enabled": True,
                            "mode": "file_source",
                            "value": "group1",
                        }
                    },
                },
                selected_mapping={"Summary": "Summary", "담당자": "담당자"},
                selected_default_values={"담당자": "홍길동"},
                selected_tracker_item_settings={
                    "연관 요구사항": {
                        "mode": "query",
                        "regex_pattern": r"(\\d+)",
                        "source_tracker_ids": [13526611],
                    }
                },
            )

            store.save_workflow_preset(preset)
            payload = json.loads(store.workflow_preset_path.read_text(encoding="utf-8"))

            self.assertIn("settings", payload)
            self.assertNotIn("secret", store.workflow_preset_path.read_text(encoding="utf-8"))

            loaded = store.load_workflow_preset()
            self.assertIsNotNone(loaded)
            assert loaded is not None
            self.assertEqual(loaded.settings.password, "secret")
            self.assertEqual(loaded.settings.default_project_id, "10")
            self.assertEqual(loaded.file_options["sheet_name"], "Main")
            self.assertFalse(loaded.root_item_config["enabled"])
            self.assertEqual(loaded.root_item_config["regex_pattern"], r"^(?P<name>.+)$")
            self.assertEqual(loaded.selected_mapping["담당자"], "담당자")
            self.assertEqual(loaded.selected_default_values["담당자"], "홍길동")
            self.assertEqual(
                loaded.selected_tracker_item_settings["연관 요구사항"]["source_tracker_ids"],
                [13526611],
            )
