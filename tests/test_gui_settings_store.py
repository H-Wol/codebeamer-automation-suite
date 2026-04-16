from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from src.gui.settings_store import GuiSettings
from src.gui.settings_store import GuiSettingsStore


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
