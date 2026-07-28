from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from src.gui.settings_store import GuiSettings
from src.gui.settings_store import GuiSettingsStore
from src.gui.settings_store import GuiWorkflowPreset
from src.gui.settings_store import GUI_UPLOAD_MODE_UPSERT
from src.gui.settings_store import GUI_UPLOAD_MODE_UPDATE
from src.gui.styles import DEFAULT_GUI_THEME


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
                theme_name="igloo",
                base_url="https://example.com/cb",
                username="user",
                password="secret",
                save_password=False,
                offline_mode=True,
                offline_schema_path="/tmp/schema.json",
            )

            store.save(settings)
            payload = json.loads(store.settings_path.read_text(encoding="utf-8"))

            self.assertEqual(payload["password_encrypted"], "")
            loaded = store.load()
            self.assertEqual(loaded.password, "")
            self.assertFalse(loaded.save_password)
            self.assertTrue(loaded.offline_mode)
            self.assertEqual(loaded.offline_schema_path, "/tmp/schema.json")
            self.assertEqual(loaded.theme_name, "igloo")

    def test_save_with_password_encrypts_and_restores_password(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            store = GuiSettingsStore(Path(tmp_dir))
            settings = GuiSettings(
                theme_name="kepico",
                window_width=1600,
                window_height=920,
                window_is_maximized=True,
                window_is_fullscreen=False,
                base_url="https://example.com/cb",
                username="user",
                password="secret",
                save_password=True,
                summary_column="Summary",
                upload_mode=GUI_UPLOAD_MODE_UPDATE,
            )

            store.save(settings)
            payload = json.loads(store.settings_path.read_text(encoding="utf-8"))

            self.assertNotEqual(payload["password_encrypted"], "")
            self.assertNotIn("secret", store.settings_path.read_text(encoding="utf-8"))

            loaded = store.load()
            self.assertEqual(loaded.password, "secret")
            self.assertTrue(loaded.save_password)
            self.assertEqual(loaded.summary_column, "Summary")
            self.assertEqual(loaded.theme_name, DEFAULT_GUI_THEME)
            self.assertEqual(loaded.upload_mode, GUI_UPLOAD_MODE_UPDATE)
            self.assertEqual(loaded.window_width, 1600)
            self.assertEqual(loaded.window_height, 920)
            self.assertTrue(loaded.window_is_maximized)
            self.assertFalse(loaded.window_is_fullscreen)

    def test_save_and_load_workflow_preset_preserves_nested_configuration(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            store = GuiSettingsStore(Path(tmp_dir))
            preset = GuiWorkflowPreset(
                settings=GuiSettings(
                    theme_name="igloo",
                    base_url="https://example.com/cb",
                    username="user",
                    password="secret",
                    save_password=True,
                    default_project_id="10",
                    default_tracker_id="1000",
                    excel_header_row=2,
                    summary_column="요약",
                    excel_sheet_name="Main",
                    upload_mode=GUI_UPLOAD_MODE_UPDATE,
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
                selected_mapping_modes={
                    "Summary": {"create": True, "update": True},
                    "담당자": {"create": True, "update": False},
                },
                selected_default_values={"담당자": "홍길동"},
                selected_default_value_modes={
                    "담당자": {"create": False, "update": True},
                },
                selected_tracker_item_settings={
                    "연관 요구사항": {
                        "mode": "query",
                        "query_match_strategy": "last",
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
            self.assertEqual(loaded.settings.theme_name, "igloo")
            self.assertEqual(loaded.settings.upload_mode, GUI_UPLOAD_MODE_UPDATE)
            self.assertEqual(loaded.file_options["sheet_name"], "Main")
            self.assertFalse(loaded.root_item_config["enabled"])
            self.assertEqual(loaded.root_item_config["regex_pattern"], r"^(?P<name>.+)$")
            self.assertEqual(loaded.selected_mapping["담당자"], "담당자")
            self.assertEqual(loaded.selected_mapping_modes["Summary"], {"create": True, "update": True})
            self.assertEqual(loaded.selected_mapping_modes["담당자"], {"create": True, "update": False})
            self.assertEqual(loaded.selected_default_values["담당자"], "홍길동")
            self.assertEqual(loaded.selected_default_value_modes["담당자"], {"create": False, "update": True})
            self.assertEqual(
                loaded.selected_tracker_item_settings["연관 요구사항"]["source_tracker_ids"],
                [13526611],
            )
            self.assertEqual(
                loaded.selected_tracker_item_settings["연관 요구사항"]["query_match_strategy"],
                "last",
            )

    def test_load_normalizes_unknown_theme_name_to_default(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            store = GuiSettingsStore(Path(tmp_dir))
            store.root_dir.mkdir(parents=True, exist_ok=True)
            store.settings_path.write_text(
                json.dumps({"theme_name": "unknown", "password_encrypted": ""}, ensure_ascii=False),
                encoding="utf-8",
            )

            loaded = store.load()

            self.assertEqual(loaded.theme_name, DEFAULT_GUI_THEME)

    def test_load_normalizes_unknown_upload_mode_to_create(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            store = GuiSettingsStore(Path(tmp_dir))
            store.root_dir.mkdir(parents=True, exist_ok=True)
            store.settings_path.write_text(
                json.dumps({"upload_mode": "unknown", "password_encrypted": ""}, ensure_ascii=False),
                encoding="utf-8",
            )

            loaded = store.load()

            self.assertEqual(loaded.upload_mode, "create")

    def test_load_preserves_upsert_upload_mode(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            store = GuiSettingsStore(Path(tmp_dir))
            store.root_dir.mkdir(parents=True, exist_ok=True)
            store.settings_path.write_text(
                json.dumps({"upload_mode": GUI_UPLOAD_MODE_UPSERT, "password_encrypted": ""}, ensure_ascii=False),
                encoding="utf-8",
            )

            loaded = store.load()

            self.assertEqual(loaded.upload_mode, GUI_UPLOAD_MODE_UPSERT)
