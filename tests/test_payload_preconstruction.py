from __future__ import annotations

import unittest

import pandas as pd

from src.mapping_service import MappingService
from src.models import ColorFieldValue
from src.models import CountryFieldValue
from src.models import DateFieldValue
from src.models import DecimalFieldValue
from src.models import DurationFieldValue
from src.models import IntegerFieldValue
from src.models import LanguageFieldValue
from src.models import PayloadTargetKind
from src.models import PreconstructionKind
from src.models import ReferenceType
from src.models import TrackerItemBase
from src.models import UserInfo
from src.models import UrlFieldValue
from src.models import WikiTextFieldValue
from src.wizard import CodebeamerUploadWizard


class TrackerItemPreconstructionTest(unittest.TestCase):
    def test_create_field_value_uses_official_single_value_models(self) -> None:
        """공식 문서에서 확인된 단일 값 FieldValue 구현체를 우선 사용해야 한다."""
        item = TrackerItemBase()
        cases = [
            (
                {"field_id": 1, "field_name": "Due Date", "field_type": "DateField"},
                "2026-04-14",
                DateFieldValue,
            ),
            (
                {"field_id": 11, "field_name": "Color", "field_type": "ColorField"},
                "#ffffff",
                ColorFieldValue,
            ),
            (
                {"field_id": 12, "field_name": "Country", "field_type": "CountryField"},
                "KR",
                CountryFieldValue,
            ),
            (
                {"field_id": 2, "field_name": "Score", "field_type": "DecimalField"},
                "1.5",
                DecimalFieldValue,
            ),
            (
                {"field_id": 3, "field_name": "Spent", "field_type": "DurationField"},
                "30",
                DurationFieldValue,
            ),
            (
                {"field_id": 4, "field_name": "Size", "field_type": "IntegerField"},
                "5",
                IntegerFieldValue,
            ),
            (
                {"field_id": 13, "field_name": "Language", "field_type": "LanguageField"},
                "ko",
                LanguageFieldValue,
            ),
            (
                {"field_id": 5, "field_name": "Link", "field_type": "UrlField"},
                "https://example.com",
                UrlFieldValue,
            ),
            (
                {"field_id": 6, "field_name": "Notes", "field_type": "WikiTextField"},
                "Some wiki text",
                WikiTextFieldValue,
            ),
        ]

        for field_info, raw_value, expected_type in cases:
            with self.subTest(field_type=field_info["field_type"]):
                field_info["preconstruction_kind"] = PreconstructionKind.FIELD_VALUE.value
                value = item._create_field_value(field_info, raw_value)
                self.assertIsInstance(value, expected_type)

    def test_set_field_value_sets_builtin_direct_scalar(self) -> None:
        """builtin direct 필드는 값이 바로 기본 속성에 들어가야 한다."""
        item = TrackerItemBase()

        item.set_field_value(
            "name",
            "REQ-001",
            {
                "field_name": "Summary",
                "field_type": "TextField",
                "is_supported": True,
                "payload_target_kind": PayloadTargetKind.BUILTIN_FIELD.value,
                "preconstruction_kind": PreconstructionKind.BUILTIN_DIRECT.value,
            },
        )

        self.assertEqual(item.name, "REQ-001")

    def test_set_field_value_builds_custom_field_value(self) -> None:
        """custom field는 알맞은 FieldValue 객체로 감싸져야 한다."""
        item = TrackerItemBase()

        item.set_field_value(
            "Approved",
            True,
            {
                "field_id": 7,
                "field_name": "Approved",
                "field_type": "BoolField",
                "value_model": "BoolFieldValue",
                "is_supported": True,
                "payload_target_kind": PayloadTargetKind.CUSTOM_FIELD.value,
                "preconstruction_kind": PreconstructionKind.FIELD_VALUE.value,
            },
        )

        payload = item.create_new_item_payload()
        self.assertEqual(len(payload["customFields"]), 1)
        self.assertEqual(payload["customFields"][0]["type"], "BoolFieldValue")
        self.assertTrue(payload["customFields"][0]["value"])

    def test_set_field_value_builds_builtin_reference_list(self) -> None:
        """builtin 다중 reference 필드는 reference 목록으로 저장돼야 한다."""
        item = TrackerItemBase()

        item.set_field_value(
            "assignedTo",
            [{"id": 10, "name": "Jane Doe", "type": "UserReference"}],
            {
                "field_name": "Assigned To",
                "field_type": "ReferenceField",
                "reference_type": ReferenceType.USER.value,
                "multiple_values": True,
                "is_supported": True,
                "payload_target_kind": PayloadTargetKind.BUILTIN_FIELD.value,
                "preconstruction_kind": PreconstructionKind.REFERENCE_LIST.value,
            },
        )

        payload = item.create_new_item_payload()
        self.assertEqual(payload["assignedTo"][0]["id"], 10)
        self.assertEqual(payload["assignedTo"][0]["type"], ReferenceType.USER.value)

    def test_set_field_value_parses_tracker_item_reference_from_bracket_text(self) -> None:
        """TrackerItemReference는 `[]` 안 첫 번째 정수를 파싱해 만들어야 한다."""
        item = TrackerItemBase()

        item.set_field_value(
            "subjects",
            ["Candidate [20263671] extra text", "[20263672] another"],
            {
                "field_name": "Subjects",
                "field_type": "TrackerItemChoiceField",
                "reference_type": ReferenceType.TRACKER_ITEM.value,
                "multiple_values": True,
                "is_supported": True,
                "payload_target_kind": PayloadTargetKind.BUILTIN_FIELD.value,
                "preconstruction_kind": PreconstructionKind.REFERENCE_LIST.value,
            },
        )

        payload = item.create_new_item_payload()
        self.assertEqual([value["id"] for value in payload["subjects"]], [20263671, 20263672])
        self.assertEqual(
            [value["type"] for value in payload["subjects"]],
            [ReferenceType.TRACKER_ITEM.value, ReferenceType.TRACKER_ITEM.value],
        )

    def test_set_field_value_rejects_unsupported_field(self) -> None:
        """지원하지 않는 필드는 payload 생성 전에 바로 거부해야 한다."""
        item = TrackerItemBase()

        with self.assertRaisesRegex(ValueError, "unsupported"):
            item.set_field_value(
                "mysteryField",
                "value",
                {
                    "field_name": "Mystery",
                    "field_type": "OptionChoiceField",
                    "is_supported": False,
                    "unsupported_reason": "schema가 불명확합니다.",
                    "payload_target_kind": PayloadTargetKind.CUSTOM_FIELD.value,
                    "preconstruction_kind": PreconstructionKind.NONE.value,
                },
            )


class WizardPayloadResolutionTest(unittest.TestCase):
    def setUp(self) -> None:
        """payload preview 테스트에 쓸 wizard를 준비한다."""
        self.mapper = MappingService()
        self.wizard = CodebeamerUploadWizard(
            client=None,
            processor=None,
            mapper=self.mapper,
        )

    def test_preview_payload_fails_early_for_generic_reference_without_resolver(self) -> None:
        """resolver가 없는 generic reference는 preview 단계에서 즉시 실패해야 한다."""
        self.wizard.state.schema_df = self.mapper.flatten_schema_fields([
            {
                "id": 3,
                "name": "Related Candidate",
                "type": "ReferenceField",
                "referenceType": "TrackerItemReference",
                "valueModel": "ChoiceFieldValue<TrackerItemReference>",
            }
        ])
        self.wizard.state.selected_mapping = {"related": "Related Candidate"}
        self.wizard.state.selected_option_mapping = {"related": "Related Candidate"}
        self.wizard.state.option_maps = self.mapper.build_option_maps_from_schema(self.wizard.state.schema_df)
        self.wizard.state.upload_df = pd.DataFrame([
            {"_row_id": 1, "upload_name": "REQ-1", "related": "REQ-2"}
        ])

        with self.assertRaisesRegex(ValueError, r"\[LOOKUP_REQUIRED\]"):
            self.wizard.preview_payload(1)

    def test_preview_payload_fails_early_for_unsupported_field(self) -> None:
        """미지원 필드는 preview 단계에서 즉시 `FIELD_UNSUPPORTED`를 내야 한다."""
        self.wizard.state.schema_df = self.mapper.flatten_schema_fields([
            {
                "id": 4,
                "name": "Choice Hint Only",
                "type": "OptionChoiceField",
                "valueModel": "ChoiceFieldValue<AbstractReference>",
            }
        ])
        self.wizard.state.selected_mapping = {"choice_hint": "Choice Hint Only"}
        self.wizard.state.selected_option_mapping = {"choice_hint": "Choice Hint Only"}
        self.wizard.state.option_maps = self.mapper.build_option_maps_from_schema(self.wizard.state.schema_df)
        self.wizard.state.upload_df = pd.DataFrame([
            {"_row_id": 1, "upload_name": "REQ-1", "choice_hint": "Anything"}
        ])

        with self.assertRaisesRegex(ValueError, r"\[FIELD_UNSUPPORTED\]"):
            self.wizard.preview_payload(1)

    def test_preview_payload_builds_member_field_from_user_ids(self) -> None:
        """MemberField는 사용자 ID를 조회해 `values=[UserReference]` 형태로 만들어야 한다."""

        class FakeUserClient:
            def get_user_by_name(self, name: str) -> UserInfo:
                return UserInfo(id=100 + len(name), name=name)

            def get_user(self, user_id: int) -> UserInfo:
                return UserInfo(id=user_id, name=f"User {user_id}")

        wizard = CodebeamerUploadWizard(
            client=FakeUserClient(),
            processor=None,
            mapper=self.mapper,
        )
        wizard.select_project(1)
        wizard.state.schema_df = self.mapper.flatten_schema_fields([
            {
                "id": 9,
                "name": "시험 담당자",
                "type": "MemberField",
                "valueModel": "ChoiceFieldValue",
                "multipleValues": True,
            }
        ])
        wizard.state.selected_mapping = {"members": "시험 담당자"}
        wizard.state.selected_option_mapping = {"members": "시험 담당자"}
        wizard.state.option_maps = self.mapper.build_option_maps_from_schema(wizard.state.schema_df)
        wizard.state.upload_df = pd.DataFrame([
            {"_row_id": 1, "upload_name": "REQ-1", "members": ["Kim QA", "Lee QA"]}
        ])
        wizard.state.converted_upload_df = wizard._resolve_user_reference_fields(
            wizard.state.upload_df,
            wizard.state.selected_option_mapping,
            wizard.state.option_maps,
        )

        payload = wizard.preview_payload(1)
        custom_field = payload["customFields"][0]

        self.assertEqual(custom_field["name"], "시험 담당자")
        self.assertEqual(custom_field["type"], "ChoiceFieldValue")
        self.assertEqual([value["name"] for value in custom_field["values"]], ["Kim QA", "Lee QA"])
        self.assertEqual([value["type"] for value in custom_field["values"]], ["UserReference", "UserReference"])

    def test_preview_payload_builds_tracker_item_choice_field_from_bracket_text(self) -> None:
        """TrackerItemChoiceField는 입력 문자열에서 item id를 직접 파싱해야 한다."""
        self.wizard.state.schema_df = self.mapper.flatten_schema_fields([
            {
                "id": 15,
                "name": "연관 요구사항",
                "type": "TrackerItemChoiceField",
                "multipleValues": True,
                "valueModel": "ChoiceFieldValue<TrackerItemReference>",
            }
        ])
        self.wizard.state.selected_mapping = {"related_items": "연관 요구사항"}
        self.wizard.state.selected_option_mapping = {"related_items": "연관 요구사항"}
        self.wizard.state.option_maps = self.mapper.build_option_maps_from_schema(self.wizard.state.schema_df)
        self.wizard.state.upload_df = pd.DataFrame([
            {
                "_row_id": 1,
                "upload_name": "REQ-1",
                "related_items": ["Candidate [20263671] extra", "20263672"],
            }
        ])
        self.wizard.state.converted_upload_df = self.mapper.apply_option_resolution(
            self.wizard.state.upload_df,
            self.wizard.state.selected_option_mapping,
            self.wizard.state.option_maps,
        )

        payload = self.wizard.preview_payload(1)
        custom_field = payload["customFields"][0]

        self.assertEqual(custom_field["name"], "연관 요구사항")
        self.assertEqual(custom_field["type"], "ChoiceFieldValue")
        self.assertEqual([value["id"] for value in custom_field["values"]], [20263671, 20263672])
        self.assertEqual(
            [value["type"] for value in custom_field["values"]],
            ["TrackerItemReference", "TrackerItemReference"],
        )


if __name__ == "__main__":
    unittest.main()
