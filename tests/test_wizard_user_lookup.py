from __future__ import annotations

import atexit
import unittest

import pandas as pd

from src.mapping_service import MappingService
from src.models import OptionMapKind
from src.models import UserInfo
from src.wizard import CodebeamerUploadWizard

try:
    import xlwings._xlmac as _xlmac

    atexit.unregister(_xlmac.clean_up)
except Exception:
    pass


class NotFoundError(Exception):
    def __init__(self) -> None:
        self.response = type("Response", (), {"status_code": 404})()
        super().__init__("not found")


class FakeClient:
    def __init__(self) -> None:
        self.get_user_by_name_calls = 0
        self.get_user_by_email_calls = 0
        self.search_user_infos_calls = 0
        self.users_by_name: dict[str, UserInfo] = {}
        self.users_by_email: dict[str, UserInfo] = {}
        self.search_results_by_name: dict[str, list[UserInfo]] = {}

    def get_user_by_name(self, name: str) -> UserInfo:
        self.get_user_by_name_calls += 1
        if name not in self.users_by_name:
            raise NotFoundError()
        return self.users_by_name[name]

    def get_user_by_email(self, email: str) -> UserInfo:
        self.get_user_by_email_calls += 1
        if email not in self.users_by_email:
            raise NotFoundError()
        return self.users_by_email[email]

    def search_user_infos(self, *, name=None, email=None, project_id=None, **kwargs) -> list[UserInfo]:
        self.search_user_infos_calls += 1
        if email is not None:
            return []
        return self.search_results_by_name.get(name, [])


class WizardUserLookupTest(unittest.TestCase):
    def setUp(self) -> None:
        self.client = FakeClient()
        self.wizard = CodebeamerUploadWizard(
            client=self.client,
            processor=None,
            mapper=MappingService(),
        )
        self.wizard.select_project(101)

    def test_lookup_uses_cached_aliases_without_additional_requests(self) -> None:
        user = UserInfo(
            id=7,
            name="Jane Doe",
            firstName="Jane",
            lastName="Doe",
            email="jane@example.com",
        )
        self.client.users_by_name[user.name] = user

        first_resolved, first_user_info, first_status, first_error = self.wizard._lookup_user_reference("Jane Doe")
        second_resolved, second_user_info, second_status, second_error = self.wizard._lookup_user_reference(
            "jane@example.com"
        )

        self.assertEqual(first_status, "RESOLVED")
        self.assertIsNone(first_error)
        self.assertEqual(first_resolved, second_resolved)
        self.assertEqual(first_user_info, second_user_info)
        self.assertEqual(second_status, "RESOLVED")
        self.assertIsNone(second_error)
        self.assertEqual(self.client.get_user_by_name_calls, 1)
        self.assertEqual(self.client.get_user_by_email_calls, 0)

    def test_lookup_cache_is_cleared_when_project_changes(self) -> None:
        user = UserInfo(
            id=9,
            name="John Smith",
            firstName="John",
            lastName="Smith",
            email="john@example.com",
        )
        self.client.users_by_name[user.name] = user

        self.wizard._lookup_user_reference("John Smith")
        self.wizard.select_project(202)
        self.wizard._lookup_user_reference("John Smith")

        self.assertEqual(self.client.get_user_by_name_calls, 2)

    def test_resolve_user_reference_fields_reuses_cached_search_results(self) -> None:
        user = UserInfo(
            id=11,
            name="Fallback User",
            firstName="Fallback",
            lastName="User",
            email="fallback@example.com",
        )
        self.client.search_results_by_name[user.name] = [user]

        upload_df = pd.DataFrame([
            {"_row_id": 1, "owner": "Fallback User"},
            {"_row_id": 2, "owner": "Fallback User"},
        ])
        option_mapping = {"owner": "Owner"}
        option_maps = {
            "Owner": {
                "kind": OptionMapKind.USER_LOOKUP.value,
                "multiple_values": False,
            }
        }

        resolved_df = self.wizard._resolve_user_reference_fields(upload_df, option_mapping, option_maps)

        self.assertEqual(self.client.get_user_by_name_calls, 1)
        self.assertEqual(self.client.search_user_infos_calls, 1)
        self.assertEqual(list(resolved_df["owner__lookup_status"]), ["RESOLVED", "RESOLVED"])
        self.assertTrue(resolved_df["owner__user_info"].notna().all())
        self.assertEqual(resolved_df.iloc[0]["owner__resolved"]["id"], 11)
        self.assertEqual(resolved_df.iloc[1]["owner__resolved"]["id"], 11)


if __name__ == "__main__":
    unittest.main()
