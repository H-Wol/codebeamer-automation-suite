from __future__ import annotations

import unittest

import pandas as pd

from src.mapping_service import MappingService
from src.models import FieldValueType
from src.models import LookupTargetKind
from src.models import OptionCheckStatus
from src.models import OptionMapKind
from src.models import OptionSourceStatus
from src.models import PayloadTargetKind
from src.models import PreconstructionKind
from src.models import ReferenceType
from src.models import ResolvedFieldKind
from src.models import UserLookupStatus


class MappingServiceTest(unittest.TestCase):
    def setUp(self) -> None:
        self.service = MappingService()

    @staticmethod
    def _field_by_name(schema_df: pd.DataFrame, field_name: str) -> pd.Series:
        matched = schema_df[schema_df["field_name"] == field_name]
        if matched.empty:
            raise AssertionError(f"Field not found in schema_df: {field_name}")
        return matched.iloc[0]

    def test_get_list_columns_for_mapping_returns_only_multiple_value_fields(self) -> None:
        schema_df = pd.DataFrame([
            {"field_name": "Summary", "multiple_values": False},
            {"field_name": "Assignees", "multiple_values": True},
            {"field_name": "Categories", "multiple_values": "true"},
            {"field_name": "Priority", "multiple_values": None},
        ])
        selected_mapping = {
            "요약": "Summary",
            "담당자": "Assignees",
            "분류": "Categories",
            "우선순위": "Priority",
        }

        list_columns = self.service.get_list_columns_for_mapping(selected_mapping, schema_df)

        self.assertEqual(list_columns, ["담당자", "분류"])

    def test_get_list_columns_for_mapping_returns_empty_for_empty_mapping(self) -> None:
        schema_df = pd.DataFrame([
            {"field_name": "Assignees", "multiple_values": True},
        ])

        list_columns = self.service.get_list_columns_for_mapping({}, schema_df)

        self.assertEqual(list_columns, [])

    def test_flatten_schema_fields_resolves_field_kind_and_preconstruction(self) -> None:
        schema = [
            {
                "id": 1,
                "name": "Summary",
                "type": "TextField",
                "trackerItemField": "name",
                "valueModel": "TextFieldValue",
            },
            {
                "id": 2,
                "name": "Phase",
                "type": "OptionChoiceField",
                "options": [{"id": 11, "name": "Draft"}],
                "valueModel": "ChoiceFieldValue<ChoiceOptionReference>",
            },
            {
                "id": 3,
                "name": "Owner",
                "type": "ReferenceField",
                "referenceType": "UserReference",
                "valueModel": "ChoiceFieldValue<UserReference>",
            },
            {
                "id": 4,
                "name": "Related Candidate",
                "type": "ReferenceField",
                "referenceType": "TrackerItemReference",
                "multipleValues": True,
                "valueModel": "ChoiceFieldValue<TrackerItemReference>",
            },
            {
                "id": 5,
                "name": "Related Missing Type",
                "type": "ReferenceField",
                "multipleValues": False,
            },
            {
                "id": 6,
                "name": "Choice Hint Only",
                "type": "OptionChoiceField",
                "valueModel": "ChoiceFieldValue<AbstractReference>",
            },
            {
                "id": 7,
                "name": "Checklist",
                "type": "TableField",
                "columns": [],
            },
            {
                "id": 8,
                "name": "Approved",
                "type": "BoolField",
                "valueModel": "BoolFieldValue",
            },
            {
                "id": 9,
                "name": "Status",
                "type": "OptionChoiceField",
                "trackerItemField": "status",
                "options": [{"id": 21, "name": "Open"}],
                "valueModel": "ChoiceFieldValue<ChoiceOptionReference>",
            },
            {
                "id": 10,
                "name": "Assigned To",
                "type": "ReferenceField",
                "trackerItemField": "assignedTo",
                "referenceType": "UserReference",
                "multipleValues": True,
                "valueModel": "ChoiceFieldValue<UserReference>",
            },
        ]

        schema_df = self.service.flatten_schema_fields(schema)

        summary = self._field_by_name(schema_df, "Summary")
        self.assertEqual(summary["resolved_field_kind"], ResolvedFieldKind.SCALAR_TEXT.value)
        self.assertEqual(summary["payload_target_kind"], PayloadTargetKind.BUILTIN_FIELD.value)
        self.assertEqual(summary["preconstruction_kind"], PreconstructionKind.BUILTIN_DIRECT.value)
        self.assertTrue(summary["is_supported"])

        approved = self._field_by_name(schema_df, "Approved")
        self.assertEqual(approved["resolved_field_kind"], ResolvedFieldKind.SCALAR_BOOL.value)
        self.assertEqual(approved["preconstruction_kind"], PreconstructionKind.FIELD_VALUE.value)
        self.assertEqual(approved["preconstruction_detail"], FieldValueType.BOOL.value)

        checklist = self._field_by_name(schema_df, "Checklist")
        self.assertEqual(checklist["resolved_field_kind"], ResolvedFieldKind.TABLE.value)
        self.assertEqual(checklist["preconstruction_kind"], PreconstructionKind.TABLE_FIELD_VALUE.value)
        self.assertEqual(checklist["preconstruction_detail"], FieldValueType.TABLE.value)

        phase = self._field_by_name(schema_df, "Phase")
        self.assertEqual(phase["resolved_field_kind"], ResolvedFieldKind.STATIC_OPTION.value)
        self.assertEqual(phase["payload_target_kind"], PayloadTargetKind.CUSTOM_FIELD.value)
        self.assertEqual(phase["preconstruction_kind"], PreconstructionKind.FIELD_VALUE.value)
        self.assertEqual(phase["requires_lookup"], False)

        owner = self._field_by_name(schema_df, "Owner")
        self.assertEqual(owner["resolved_field_kind"], ResolvedFieldKind.USER_REFERENCE.value)
        self.assertEqual(owner["lookup_target_kind"], LookupTargetKind.USER.value)
        self.assertTrue(owner["requires_lookup"])
        self.assertEqual(owner["preconstruction_kind"], PreconstructionKind.FIELD_VALUE.value)

        related_candidate = self._field_by_name(schema_df, "Related Candidate")
        self.assertEqual(related_candidate["resolved_field_kind"], ResolvedFieldKind.GENERIC_REFERENCE.value)
        self.assertTrue(related_candidate["requires_lookup"])
        self.assertEqual(related_candidate["lookup_target_kind"], LookupTargetKind.REFERENCE.value)
        self.assertEqual(related_candidate["preconstruction_kind"], PreconstructionKind.FIELD_VALUE.value)
        self.assertTrue(related_candidate["is_supported"])

        related_missing_type = self._field_by_name(schema_df, "Related Missing Type")
        self.assertEqual(related_missing_type["resolved_field_kind"], ResolvedFieldKind.GENERIC_REFERENCE.value)
        self.assertFalse(related_missing_type["is_supported"])
        self.assertIn("referenceType", related_missing_type["unsupported_reason"])

        choice_hint = self._field_by_name(schema_df, "Choice Hint Only")
        self.assertEqual(choice_hint["resolved_field_kind"], ResolvedFieldKind.UNSUPPORTED.value)
        self.assertFalse(choice_hint["is_supported"])
        self.assertIn("valueModel", choice_hint["unsupported_reason"])

        status = self._field_by_name(schema_df, "Status")
        self.assertEqual(status["payload_target_kind"], PayloadTargetKind.BUILTIN_FIELD.value)
        self.assertEqual(status["preconstruction_kind"], PreconstructionKind.REFERENCE.value)

        assigned_to = self._field_by_name(schema_df, "Assigned To")
        self.assertEqual(assigned_to["payload_target_kind"], PayloadTargetKind.BUILTIN_FIELD.value)
        self.assertEqual(assigned_to["preconstruction_kind"], PreconstructionKind.REFERENCE_LIST.value)

    def test_compare_upload_df_with_schema_includes_resolution_columns(self) -> None:
        schema_df = self.service.flatten_schema_fields([
            {
                "id": 1,
                "name": "Owner",
                "type": "ReferenceField",
                "referenceType": "UserReference",
                "valueModel": "ChoiceFieldValue<UserReference>",
            }
        ])
        upload_df = pd.DataFrame([{"owner": "Jane Doe"}])
        comparison_df = self.service.compare_upload_df_with_schema(
            upload_df=upload_df,
            schema_df=schema_df,
            selected_mapping={"owner": "Owner"},
        )

        row = comparison_df.iloc[0]
        self.assertEqual(row["resolved_field_kind"], ResolvedFieldKind.USER_REFERENCE.value)
        self.assertTrue(row["is_supported"])
        self.assertTrue(row["requires_lookup"])
        self.assertEqual(row["lookup_target_kind"], LookupTargetKind.USER.value)
        self.assertEqual(row["preconstruction_kind"], PreconstructionKind.FIELD_VALUE.value)
        self.assertEqual(row["payload_target_kind"], PayloadTargetKind.CUSTOM_FIELD.value)

    def test_build_option_maps_from_schema_distinguishes_field_resolution_states(self) -> None:
        schema_df = self.service.flatten_schema_fields([
            {
                "id": 1,
                "name": "Phase",
                "type": "OptionChoiceField",
                "options": [{"id": 11, "name": "Draft"}],
                "valueModel": "ChoiceFieldValue<ChoiceOptionReference>",
            },
            {
                "id": 2,
                "name": "Owner",
                "type": "ReferenceField",
                "referenceType": "UserReference",
                "valueModel": "ChoiceFieldValue<UserReference>",
            },
            {
                "id": 3,
                "name": "Related Candidate",
                "type": "ReferenceField",
                "referenceType": "TrackerItemReference",
                "valueModel": "ChoiceFieldValue<TrackerItemReference>",
            },
            {
                "id": 4,
                "name": "Choice Hint Only",
                "type": "OptionChoiceField",
                "valueModel": "ChoiceFieldValue<AbstractReference>",
            },
        ])

        option_maps = self.service.build_option_maps_from_schema(schema_df)

        self.assertEqual(option_maps["Phase"]["kind"], OptionMapKind.STATIC_OPTIONS.value)
        self.assertEqual(option_maps["Phase"]["source_status"], OptionSourceStatus.READY.value)

        self.assertEqual(option_maps["Owner"]["kind"], OptionMapKind.USER_LOOKUP.value)
        self.assertEqual(option_maps["Owner"]["source_status"], OptionSourceStatus.LOOKUP_REQUIRED.value)
        self.assertTrue(option_maps["Owner"]["resolver_available"])

        self.assertEqual(option_maps["Related Candidate"]["kind"], OptionMapKind.REFERENCE_LOOKUP.value)
        self.assertFalse(option_maps["Related Candidate"]["resolver_available"])
        self.assertIn("resolver", option_maps["Related Candidate"]["unsupported_reason"])

        self.assertEqual(option_maps["Choice Hint Only"]["kind"], OptionMapKind.UNSUPPORTED.value)
        self.assertEqual(option_maps["Choice Hint Only"]["source_status"], OptionSourceStatus.UNSUPPORTED.value)

    def test_check_option_alignment_surfaces_early_resolution_risks(self) -> None:
        schema_df = self.service.flatten_schema_fields([
            {
                "id": 1,
                "name": "Phase",
                "type": "OptionChoiceField",
                "options": [{"id": 11, "name": "Draft"}],
                "valueModel": "ChoiceFieldValue<ChoiceOptionReference>",
            },
            {
                "id": 2,
                "name": "Owner",
                "type": "ReferenceField",
                "referenceType": "UserReference",
                "valueModel": "ChoiceFieldValue<UserReference>",
            },
            {
                "id": 3,
                "name": "Related Candidate",
                "type": "ReferenceField",
                "referenceType": "TrackerItemReference",
                "valueModel": "ChoiceFieldValue<TrackerItemReference>",
            },
            {
                "id": 4,
                "name": "Choice Hint Only",
                "type": "OptionChoiceField",
                "valueModel": "ChoiceFieldValue<AbstractReference>",
            },
        ])
        option_maps = self.service.build_option_maps_from_schema(schema_df)
        upload_df = pd.DataFrame([
            {
                "_row_id": 1,
                "phase": "Missing",
                "owner": "Jane Doe",
                "related": "REQ-1",
                "choice_hint": "Anything",
            }
        ])
        option_mapping = {
            "phase": "Phase",
            "owner": "Owner",
            "related": "Related Candidate",
            "choice_hint": "Choice Hint Only",
        }

        result = self.service.check_option_alignment(upload_df, option_mapping, option_maps)
        statuses = set(result["status"].tolist())

        self.assertIn(OptionCheckStatus.PRECONSTRUCTION_REQUIRED.value, statuses)
        self.assertIn(OptionCheckStatus.OPTION_NOT_FOUND.value, statuses)
        self.assertIn(OptionCheckStatus.LOOKUP_REQUIRED.value, statuses)
        self.assertIn(OptionCheckStatus.FIELD_UNSUPPORTED.value, statuses)
        self.assertIn(UserLookupStatus.USER_LOOKUP_NOT_RUN.value, statuses)


if __name__ == "__main__":
    unittest.main()
