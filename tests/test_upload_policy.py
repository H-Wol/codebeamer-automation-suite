from __future__ import annotations

import unittest

from src.upload_policy import DEFAULT_TRACKER_ITEM_ID_REGEX
from src.upload_policy import UPLOAD_MODE_CREATE
from src.upload_policy import UPLOAD_MODE_UPDATE
from src.upload_policy import UPLOAD_MODE_UPSERT
from src.upload_policy import default_operation_scope
from src.upload_policy import normalize_all_or_none_operation_scope
from src.upload_policy import normalize_operation_scope
from src.upload_policy import normalize_upload_mode
from src.upload_policy import scope_applies_to_operation
from src.upload_policy import scope_applies_to_upload_mode
from src.upload_policy import upload_mode_action_label
from src.upload_policy import upload_mode_allows_root_items
from src.upload_policy import upload_mode_supports_create
from src.upload_policy import upload_mode_supports_update


class UploadPolicyTest(unittest.TestCase):
    def test_normalize_upload_mode_defaults_unknown_values_to_create(self) -> None:
        self.assertEqual(normalize_upload_mode(None), UPLOAD_MODE_CREATE)
        self.assertEqual(normalize_upload_mode(" unknown "), UPLOAD_MODE_CREATE)
        self.assertEqual(normalize_upload_mode(" UPSERT "), UPLOAD_MODE_UPSERT)

    def test_mode_capabilities_share_one_policy(self) -> None:
        self.assertTrue(upload_mode_supports_create(UPLOAD_MODE_CREATE))
        self.assertFalse(upload_mode_supports_update(UPLOAD_MODE_CREATE))
        self.assertFalse(upload_mode_allows_root_items(UPLOAD_MODE_UPDATE))
        self.assertTrue(upload_mode_supports_create(UPLOAD_MODE_UPSERT))
        self.assertTrue(upload_mode_supports_update(UPLOAD_MODE_UPSERT))

    def test_action_labels_match_user_visible_operations(self) -> None:
        self.assertEqual(upload_mode_action_label(UPLOAD_MODE_CREATE), "업로드")
        self.assertEqual(upload_mode_action_label(UPLOAD_MODE_UPDATE), "업데이트")
        self.assertEqual(upload_mode_action_label(UPLOAD_MODE_UPSERT), "혼합 처리")

    def test_default_operation_scope_matches_upload_mode(self) -> None:
        self.assertEqual(default_operation_scope(UPLOAD_MODE_CREATE), {"create": True, "update": False})
        self.assertEqual(default_operation_scope(UPLOAD_MODE_UPDATE), {"create": False, "update": True})
        self.assertEqual(default_operation_scope(UPLOAD_MODE_UPSERT), {"create": True, "update": True})

    def test_normalize_operation_scope_preserves_explicit_flags(self) -> None:
        self.assertEqual(
            normalize_operation_scope({"create": False}, upload_mode=UPLOAD_MODE_UPSERT),
            {"create": False, "update": True},
        )

    def test_scope_checks_use_operation_and_mode(self) -> None:
        create_only = {"create": True, "update": False}
        self.assertTrue(
            scope_applies_to_operation(
                create_only,
                UPLOAD_MODE_CREATE,
                upload_mode=UPLOAD_MODE_UPSERT,
            )
        )
        self.assertFalse(
            scope_applies_to_operation(
                create_only,
                UPLOAD_MODE_UPDATE,
                upload_mode=UPLOAD_MODE_UPSERT,
            )
        )
        self.assertTrue(scope_applies_to_upload_mode(create_only, upload_mode=UPLOAD_MODE_UPSERT))
        self.assertFalse(scope_applies_to_upload_mode(create_only, upload_mode=UPLOAD_MODE_UPDATE))
        self.assertTrue(scope_applies_to_upload_mode(create_only, UPLOAD_MODE_CREATE))

    def test_all_or_none_scope_preserves_mode_default_when_enabled(self) -> None:
        self.assertEqual(
            normalize_all_or_none_operation_scope(
                {"create": False, "update": True},
                upload_mode=UPLOAD_MODE_UPSERT,
            ),
            {"create": True, "update": True},
        )
        self.assertEqual(
            normalize_all_or_none_operation_scope(
                {"create": False, "update": False},
                upload_mode=UPLOAD_MODE_UPSERT,
            ),
            {"create": False, "update": False},
        )

    def test_tracker_item_regex_is_shared(self) -> None:
        self.assertIn(r"(\d+)", DEFAULT_TRACKER_ITEM_ID_REGEX)


if __name__ == "__main__":
    unittest.main()
