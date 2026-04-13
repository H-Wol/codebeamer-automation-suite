from __future__ import annotations

import unittest

import pandas as pd

from src.mapping_service import MappingService
from src.models import PayloadTargetKind
from src.models import PreconstructionKind
from src.models import ReferenceType
from src.models import TrackerItemBase
from src.wizard import CodebeamerUploadWizard


class TrackerItemPreconstructionTest(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
