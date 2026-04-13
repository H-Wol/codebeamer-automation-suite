from __future__ import annotations

from typing import Any

import pandas as pd

from .models import FieldValueType
from .models import LookupTargetKind
from .models import MappingStatus
from .models import OptionCheckStatus
from .models import OptionMapKind
from .models import OptionSourceKind
from .models import OptionSourceStatus
from .models import PayloadTargetKind
from .models import PreconstructionKind
from .models import ReferenceType
from .models import ResolvedFieldKind
from .models import ResolutionStrategy
from .models import SchemaFieldType
from .models import TrackerItemBase
from .models import TrackerItemField
from .models import TrackerSchemaName
from .models import UserLookupStatus


class MappingService:
    def __init__(self, logger=None):
        self.logger = logger

    @staticmethod
    def _is_truthy_flag(value: Any) -> bool:
        if isinstance(value, bool):
            return value
        if value is None:
            return False
        if isinstance(value, str):
            return value.strip().lower() == "true"
        return bool(value)

    @staticmethod
    def _extract_status_option_ids(fields: list[dict[str, Any]]) -> set[int]:
        for field in fields:
            tracker_item_field = field.get("trackerItemField")
            field_name = field.get("name")
            options = field.get("options") or []
            if (
                tracker_item_field == TrackerItemField.STATUS.value
                or field_name == TrackerSchemaName.STATUS.value
            ):
                return {
                    option["id"]
                    for option in options
                    if isinstance(option, dict) and option.get("id") is not None
                }
        return set()

    @staticmethod
    def _build_mandatory_metadata(
        field: dict[str, Any],
        all_status_option_ids: set[int],
    ) -> dict[str, Any]:
        mandatory_statuses = field.get("mandatoryInStatuses") or []
        mandatory_status_ids = {
            status["id"]
            for status in mandatory_statuses
            if isinstance(status, dict) and status.get("id") is not None
        }
        is_always_mandatory = bool(field.get("mandatory", False))
        covers_all_statuses = bool(all_status_option_ids) and mandatory_status_ids == all_status_option_ids
        mandatory = is_always_mandatory or covers_all_statuses

        return {
            "mandatory": mandatory,
            "mandatory_mode": (
                "always" if mandatory
                else "conditional" if mandatory_statuses
                else "never"
            ),
            "mandatory_statuses": mandatory_statuses,
            "mandatory_status_names": [
                status.get("name") for status in mandatory_statuses if status.get("name")
            ],
        }

    @staticmethod
    def _is_choice_value_model(value_model: Any) -> bool:
        return isinstance(value_model, str) and "Choice" in value_model

    @classmethod
    def _resolve_payload_target_kind(cls, field: dict[str, Any]) -> str:
        tracker_item_field = field.get("trackerItemField")
        if TrackerItemBase.has_builtin_field(tracker_item_field):
            return PayloadTargetKind.BUILTIN_FIELD.value
        if field.get("id") is not None and field.get("name"):
            return PayloadTargetKind.CUSTOM_FIELD.value
        return PayloadTargetKind.UNSUPPORTED.value

    @classmethod
    def _reference_detail(cls, resolved_field_kind: str, field: dict[str, Any]) -> str:
        if resolved_field_kind == ResolvedFieldKind.STATIC_OPTION.value:
            return field.get("referenceType") or ReferenceType.CHOICE_OPTION.value
        if resolved_field_kind == ResolvedFieldKind.USER_REFERENCE.value:
            return ReferenceType.USER.value
        if field.get("referenceType"):
            return str(field["referenceType"])
        return "generic reference candidate"

    @classmethod
    def _field_value_detail(cls, resolved_field_kind: str, field: dict[str, Any]) -> str:
        if resolved_field_kind == ResolvedFieldKind.SCALAR_BOOL.value:
            return FieldValueType.BOOL.value
        if resolved_field_kind == ResolvedFieldKind.TABLE.value:
            return FieldValueType.TABLE.value
        if resolved_field_kind in {
            ResolvedFieldKind.STATIC_OPTION.value,
            ResolvedFieldKind.USER_REFERENCE.value,
            ResolvedFieldKind.GENERIC_REFERENCE.value,
        }:
            return f"{FieldValueType.CHOICE.value}<{cls._reference_detail(resolved_field_kind, field)}>"

        value_model = field.get("valueModel")
        if isinstance(value_model, str) and value_model.endswith("FieldValue"):
            return value_model
        return FieldValueType.TEXT.value

    @classmethod
    def _resolve_field_kind(cls, field: dict[str, Any]) -> dict[str, Any]:
        field_type = field.get("type")
        reference_type = field.get("referenceType")
        has_options = bool(field.get("options"))
        value_model = field.get("valueModel")
        payload_target_kind = cls._resolve_payload_target_kind(field)

        result = {
            "resolved_field_kind": ResolvedFieldKind.UNSUPPORTED.value,
            "resolution_strategy": ResolutionStrategy.UNKNOWN_TYPE.value,
            "is_supported": payload_target_kind != PayloadTargetKind.UNSUPPORTED.value,
            "unsupported_reason": None,
            "payload_target_kind": payload_target_kind,
        }

        if payload_target_kind == PayloadTargetKind.UNSUPPORTED.value:
            result["unsupported_reason"] = (
                "trackerItemField가 builtin field로 해석되지 않았고 custom field로도 판정할 수 없습니다."
            )

        if field_type == SchemaFieldType.TABLE.value:
            result["resolved_field_kind"] = ResolvedFieldKind.TABLE.value
            result["resolution_strategy"] = ResolutionStrategy.TYPE_TABLE.value
            return result

        if field_type == SchemaFieldType.BOOL.value:
            result["resolved_field_kind"] = ResolvedFieldKind.SCALAR_BOOL.value
            result["resolution_strategy"] = ResolutionStrategy.TYPE_BOOL.value
            return result

        if field_type == SchemaFieldType.OPTION_CHOICE.value:
            if has_options:
                result["resolved_field_kind"] = ResolvedFieldKind.STATIC_OPTION.value
                result["resolution_strategy"] = ResolutionStrategy.TYPE_OPTION_WITH_OPTIONS.value
                return result
            if reference_type == ReferenceType.USER.value:
                result["resolved_field_kind"] = ResolvedFieldKind.USER_REFERENCE.value
                result["resolution_strategy"] = ResolutionStrategy.TYPE_OPTION_WITH_USER_REFERENCE.value
                return result
            if reference_type:
                result["resolved_field_kind"] = ResolvedFieldKind.GENERIC_REFERENCE.value
                result["resolution_strategy"] = ResolutionStrategy.TYPE_OPTION_WITH_REFERENCE_TYPE.value
                return result

            result["resolved_field_kind"] = ResolvedFieldKind.UNSUPPORTED.value
            result["resolution_strategy"] = ResolutionStrategy.TYPE_OPTION_AMBIGUOUS.value
            result["is_supported"] = False
            if cls._is_choice_value_model(value_model):
                result["unsupported_reason"] = (
                    "OptionChoiceField인데 options/referenceType이 없고 valueModel만 choice 계열이라 확정할 수 없습니다."
                )
            else:
                result["unsupported_reason"] = (
                    "OptionChoiceField인데 options와 referenceType이 모두 없어 안전하게 해석할 수 없습니다."
                )
            return result

        if field_type == SchemaFieldType.REFERENCE.value:
            if reference_type == ReferenceType.USER.value:
                result["resolved_field_kind"] = ResolvedFieldKind.USER_REFERENCE.value
                result["resolution_strategy"] = ResolutionStrategy.TYPE_REFERENCE_WITH_USER_REFERENCE.value
                return result
            if reference_type:
                result["resolved_field_kind"] = ResolvedFieldKind.GENERIC_REFERENCE.value
                result["resolution_strategy"] = ResolutionStrategy.TYPE_REFERENCE_WITH_REFERENCE_TYPE.value
                return result

            result["resolved_field_kind"] = ResolvedFieldKind.GENERIC_REFERENCE.value
            result["resolution_strategy"] = ResolutionStrategy.TYPE_REFERENCE_WITHOUT_REFERENCE_TYPE.value
            result["is_supported"] = False
            result["unsupported_reason"] = (
                "ReferenceField인데 referenceType이 없어 어떤 reference 객체를 구성해야 하는지 확정할 수 없습니다."
            )
            return result

        if cls._is_choice_value_model(value_model):
            result["resolved_field_kind"] = ResolvedFieldKind.UNSUPPORTED.value
            result["resolution_strategy"] = ResolutionStrategy.UNKNOWN_TYPE.value
            result["is_supported"] = False
            result["unsupported_reason"] = (
                "valueModel이 choice 계열이지만 type/options/referenceType 조합이 없어 보조 신호만으로는 해석할 수 없습니다."
            )
            return result

        result["resolved_field_kind"] = ResolvedFieldKind.SCALAR_TEXT.value
        result["resolution_strategy"] = (
            ResolutionStrategy.BUILTIN_SCALAR.value
            if payload_target_kind == PayloadTargetKind.BUILTIN_FIELD.value
            else ResolutionStrategy.CUSTOM_SCALAR.value
        )
        return result

    @classmethod
    def _resolve_preconstruction(cls, field_resolution: dict[str, Any]) -> dict[str, Any]:
        resolved_field_kind = field_resolution["resolved_field_kind"]
        payload_target_kind = field_resolution["payload_target_kind"]
        multiple_values = cls._is_truthy_flag(field_resolution.get("multiple_values"))
        is_supported = field_resolution.get("is_supported", True)
        unsupported_reason = field_resolution.get("unsupported_reason")

        result = {
            "requires_lookup": False,
            "lookup_target_kind": LookupTargetKind.NONE.value,
            "preconstruction_kind": PreconstructionKind.NONE.value,
            "preconstruction_detail": None,
            "payload_target_kind": payload_target_kind,
            "is_supported": is_supported,
            "unsupported_reason": unsupported_reason,
        }

        if payload_target_kind == PayloadTargetKind.UNSUPPORTED.value:
            return result

        if resolved_field_kind == ResolvedFieldKind.TABLE.value:
            if payload_target_kind == PayloadTargetKind.BUILTIN_FIELD.value:
                result["is_supported"] = False
                result["unsupported_reason"] = (
                    result["unsupported_reason"] or "TableField는 builtin field에 직접 매핑할 수 없습니다."
                )
                return result
            result["preconstruction_kind"] = PreconstructionKind.TABLE_FIELD_VALUE.value
            result["preconstruction_detail"] = FieldValueType.TABLE.value
            return result

        if resolved_field_kind == ResolvedFieldKind.SCALAR_BOOL.value:
            if payload_target_kind == PayloadTargetKind.BUILTIN_FIELD.value:
                result["preconstruction_kind"] = PreconstructionKind.BUILTIN_DIRECT.value
                result["preconstruction_detail"] = "bool"
            else:
                result["preconstruction_kind"] = PreconstructionKind.FIELD_VALUE.value
                result["preconstruction_detail"] = FieldValueType.BOOL.value
            return result

        if resolved_field_kind == ResolvedFieldKind.SCALAR_TEXT.value:
            if payload_target_kind == PayloadTargetKind.BUILTIN_FIELD.value:
                result["preconstruction_kind"] = PreconstructionKind.BUILTIN_DIRECT.value
                result["preconstruction_detail"] = (
                    field_resolution.get("tracker_item_field") or "builtin scalar"
                )
            else:
                result["preconstruction_kind"] = PreconstructionKind.FIELD_VALUE.value
                result["preconstruction_detail"] = cls._field_value_detail(
                    resolved_field_kind,
                    field_resolution,
                )
            return result

        if resolved_field_kind == ResolvedFieldKind.STATIC_OPTION.value:
            if payload_target_kind == PayloadTargetKind.BUILTIN_FIELD.value:
                result["preconstruction_kind"] = (
                    PreconstructionKind.REFERENCE_LIST.value
                    if multiple_values
                    else PreconstructionKind.REFERENCE.value
                )
                result["preconstruction_detail"] = cls._reference_detail(resolved_field_kind, field_resolution)
            else:
                result["preconstruction_kind"] = PreconstructionKind.FIELD_VALUE.value
                result["preconstruction_detail"] = cls._field_value_detail(
                    resolved_field_kind,
                    field_resolution,
                )
            return result

        if resolved_field_kind == ResolvedFieldKind.USER_REFERENCE.value:
            result["requires_lookup"] = True
            result["lookup_target_kind"] = LookupTargetKind.USER.value
            if payload_target_kind == PayloadTargetKind.BUILTIN_FIELD.value:
                result["preconstruction_kind"] = (
                    PreconstructionKind.REFERENCE_LIST.value
                    if multiple_values
                    else PreconstructionKind.REFERENCE.value
                )
                result["preconstruction_detail"] = ReferenceType.USER.value
            else:
                result["preconstruction_kind"] = PreconstructionKind.FIELD_VALUE.value
                result["preconstruction_detail"] = cls._field_value_detail(
                    resolved_field_kind,
                    field_resolution,
                )
            return result

        if resolved_field_kind == ResolvedFieldKind.GENERIC_REFERENCE.value:
            result["requires_lookup"] = True
            result["lookup_target_kind"] = LookupTargetKind.REFERENCE.value
            if payload_target_kind == PayloadTargetKind.BUILTIN_FIELD.value:
                result["preconstruction_kind"] = (
                    PreconstructionKind.REFERENCE_LIST.value
                    if multiple_values
                    else PreconstructionKind.REFERENCE.value
                )
                result["preconstruction_detail"] = cls._reference_detail(resolved_field_kind, field_resolution)
            else:
                result["preconstruction_kind"] = PreconstructionKind.FIELD_VALUE.value
                result["preconstruction_detail"] = cls._field_value_detail(
                    resolved_field_kind,
                    field_resolution,
                )
            return result

        return result

    @classmethod
    def _is_option_like_field(cls, field: pd.Series | dict[str, Any]) -> bool:
        getter = field.get
        resolved_field_kind = getter("resolved_field_kind")
        if resolved_field_kind in {
            ResolvedFieldKind.STATIC_OPTION.value,
            ResolvedFieldKind.USER_REFERENCE.value,
            ResolvedFieldKind.GENERIC_REFERENCE.value,
        }:
            return True

        has_options = bool(getter("has_options", False) or getter("options", []))
        reference_type = getter("reference_type") or getter("referenceType")
        value_model = getter("value_model") or getter("valueModel")
        field_type = getter("field_type") or getter("type")
        return (
            has_options
            or bool(reference_type)
            or cls._is_choice_value_model(value_model)
            or field_type in {SchemaFieldType.REFERENCE.value, SchemaFieldType.OPTION_CHOICE.value}
        )

    @classmethod
    def _detect_option_source_kind(cls, field: pd.Series | dict[str, Any]) -> str | None:
        getter = field.get
        resolved_field_kind = getter("resolved_field_kind")
        if resolved_field_kind == ResolvedFieldKind.STATIC_OPTION.value:
            return OptionSourceKind.SCHEMA_OPTIONS.value
        if resolved_field_kind in {
            ResolvedFieldKind.USER_REFERENCE.value,
            ResolvedFieldKind.GENERIC_REFERENCE.value,
        }:
            return OptionSourceKind.REFERENCE_LOOKUP.value
        if cls._is_option_like_field(field):
            return OptionSourceKind.UNSUPPORTED.value
        return None

    def flatten_schema_fields(self, schema: dict | list) -> pd.DataFrame:
        candidates = []

        if isinstance(schema, list):
            candidates = schema
        elif isinstance(schema, dict):
            for key in ["fieldDefinitions", "fields"]:
                if key in schema and isinstance(schema[key], list):
                    candidates = schema[key]
                    break

        all_status_option_ids = self._extract_status_option_ids(candidates)
        rows = []
        for field in candidates:
            options = field.get("options", [])
            has_options = len(options) > 0
            is_table_field = field.get("type") == SchemaFieldType.TABLE.value
            columns = field.get("columns", []) if is_table_field else None
            reference_type = field.get("referenceType")
            value_model = field.get("valueModel")
            multiple_values = self._is_truthy_flag(field.get("multipleValues"))
            mandatory_meta = self._build_mandatory_metadata(field, all_status_option_ids)

            if columns:
                columns = [
                    {
                        **column,
                        **self._build_mandatory_metadata(column, all_status_option_ids),
                    }
                    for column in columns
                ]

            row = {
                "field_id": field.get("id"),
                "field_name": field.get("name"),
                "field_label": field.get("label") or field.get("title"),
                "field_type": field.get("type"),
                "mandatory": mandatory_meta["mandatory"],
                "mandatory_mode": mandatory_meta["mandatory_mode"],
                "mandatory_statuses": mandatory_meta["mandatory_statuses"],
                "mandatory_status_names": mandatory_meta["mandatory_status_names"],
                "tracker_item_field": field.get("trackerItemField", field.get("name", None)),
                "raw_tracker_item_field": field.get("trackerItemField"),
                "value_model": value_model,
                "reference_type": reference_type,
                "has_options": has_options,
                "multiple_values": multiple_values,
                "options": options if has_options else None,
                "is_table_field": is_table_field,
                "table_columns": columns,
                "raw": field,
            }
            row.update(self._resolve_field_kind(field))
            row.update(self._resolve_preconstruction(row))
            row["is_option_like"] = self._is_option_like_field(row)
            row["option_source_kind"] = self._detect_option_source_kind(row)
            rows.append(row)

        return pd.DataFrame(rows)

    def compare_upload_df_with_schema(
        self,
        upload_df: pd.DataFrame,
        schema_df: pd.DataFrame,
        selected_mapping: dict[str, str],
    ) -> pd.DataFrame:
        schema_field_names = set(schema_df["field_name"].dropna().astype(str).str.strip())
        upload_columns = set(upload_df.columns)

        rows = []
        for df_col in sorted(upload_columns):
            mapped_schema_field = selected_mapping.get(df_col)
            schema_exists = mapped_schema_field in schema_field_names if mapped_schema_field else False

            row = {
                "df_column": df_col,
                "selected_schema_field": mapped_schema_field,
                "df_exists": True,
                "schema_field_exists": schema_exists,
                "status": (
                    MappingStatus.UNMAPPED.value
                    if not mapped_schema_field
                    else (
                        MappingStatus.OK.value
                        if schema_exists
                        else MappingStatus.SCHEMA_FIELD_MISSING.value
                    )
                ),
            }

            if mapped_schema_field and schema_exists:
                matched = schema_df[schema_df["field_name"] == mapped_schema_field]
                if not matched.empty:
                    match = matched.iloc[0]
                    row["field_id"] = match["field_id"]
                    row["field_label"] = match.get("field_label")
                    row["field_type"] = match["field_type"]
                    row["mandatory"] = match["mandatory"]
                    row["mandatory_mode"] = match.get("mandatory_mode")
                    row["mandatory_status_names"] = match.get("mandatory_status_names")
                    row["value_model"] = match["value_model"]
                    row["reference_type"] = match.get("reference_type")
                    row["hidden"] = match.get("raw", {}).get("hidden", False)
                    row["is_option_field"] = bool(match.get("is_option_like", False))
                    row["option_source_kind"] = match.get("option_source_kind")
                    row["tracker_item_field"] = match.get("tracker_item_field")
                    row["resolved_field_kind"] = match.get("resolved_field_kind")
                    row["resolution_strategy"] = match.get("resolution_strategy")
                    row["is_supported"] = match.get("is_supported")
                    row["unsupported_reason"] = match.get("unsupported_reason")
                    row["requires_lookup"] = match.get("requires_lookup")
                    row["lookup_target_kind"] = match.get("lookup_target_kind")
                    row["preconstruction_kind"] = match.get("preconstruction_kind")
                    row["preconstruction_detail"] = match.get("preconstruction_detail")
                    row["payload_target_kind"] = match.get("payload_target_kind")

            rows.append(row)

        return pd.DataFrame(rows)

    def get_option_field_candidates(self, schema_df: pd.DataFrame) -> pd.DataFrame:
        if "is_option_like" in schema_df.columns:
            mask = schema_df["is_option_like"].fillna(False)
            return schema_df[mask].copy()

        mask = schema_df.apply(self._is_option_like_field, axis=1)
        return schema_df[mask].copy()

    def get_list_columns_for_mapping(
        self,
        selected_mapping: dict[str, str],
        schema_df: pd.DataFrame,
    ) -> list[str]:
        if schema_df.empty or not selected_mapping:
            return []

        multiple_value_fields = {
            row["field_name"]
            for _, row in schema_df.iterrows()
            if row.get("field_name") and self._is_truthy_flag(row.get("multiple_values"))
        }

        return [
            df_col
            for df_col, schema_field in selected_mapping.items()
            if schema_field in multiple_value_fields
        ]

    @staticmethod
    def build_option_name_map(options: list[dict]) -> dict:
        result = {}
        duplicates = set()

        for opt in options:
            name = opt.get("name")
            if not name:
                continue
            key = str(name).strip()
            if key in result:
                duplicates.add(key)
            else:
                result[key] = opt

        if duplicates:
            raise ValueError(f"Duplicate option names found: {sorted(duplicates)}")

        return result

    @staticmethod
    def _option_map_metadata(row: pd.Series | dict[str, Any]) -> dict[str, Any]:
        getter = row.get
        return {
            "resolved_field_kind": getter("resolved_field_kind"),
            "resolution_strategy": getter("resolution_strategy"),
            "is_supported": getter("is_supported"),
            "unsupported_reason": getter("unsupported_reason"),
            "requires_lookup": getter("requires_lookup"),
            "lookup_target_kind": getter("lookup_target_kind"),
            "preconstruction_kind": getter("preconstruction_kind"),
            "preconstruction_detail": getter("preconstruction_detail"),
            "payload_target_kind": getter("payload_target_kind"),
        }

    def build_option_maps_from_schema(self, schema_df: pd.DataFrame) -> dict[str, dict]:
        option_maps = {}
        option_fields = self.get_option_field_candidates(schema_df)

        for _, row in option_fields.iterrows():
            field_name = row["field_name"]
            if not field_name:
                continue

            metadata = self._option_map_metadata(row)
            resolved_field_kind = row.get("resolved_field_kind")
            reference_type = row.get("reference_type")
            multiple_values = row.get("multiple_values", False)

            if resolved_field_kind == ResolvedFieldKind.STATIC_OPTION.value:
                options = row.get("options") or []
                try:
                    name_map = self.build_option_name_map(options)
                except ValueError:
                    if self.logger:
                        self.logger.warning(f"Duplicate options found in field: {field_name}")
                    option_maps[field_name] = {
                        "kind": OptionMapKind.UNSUPPORTED.value,
                        "name_map": {},
                        "reference_type": reference_type,
                        "multiple_values": multiple_values,
                        "options": options,
                        "source_status": OptionSourceStatus.UNSUPPORTED.value,
                        "resolver_available": False,
                        **metadata,
                        "unsupported_reason": "schema options에 중복 name이 있어 안전하게 option map을 만들 수 없습니다.",
                    }
                    continue

                option_maps[field_name] = {
                    "kind": OptionMapKind.STATIC_OPTIONS.value,
                    "name_map": name_map,
                    "reference_type": reference_type,
                    "multiple_values": multiple_values,
                    "options": options,
                    "source_status": OptionSourceStatus.READY.value,
                    "resolver_available": True,
                    **metadata,
                }
                continue

            if resolved_field_kind == ResolvedFieldKind.USER_REFERENCE.value:
                option_maps[field_name] = {
                    "kind": OptionMapKind.USER_LOOKUP.value,
                    "name_map": {},
                    "reference_type": reference_type,
                    "multiple_values": multiple_values,
                    "options": None,
                    "source_status": (
                        OptionSourceStatus.LOOKUP_REQUIRED.value
                        if metadata["is_supported"]
                        else OptionSourceStatus.UNSUPPORTED.value
                    ),
                    "resolver_available": True,
                    **metadata,
                }
                continue

            if resolved_field_kind == ResolvedFieldKind.GENERIC_REFERENCE.value:
                unsupported_reason = metadata["unsupported_reason"]
                if metadata["is_supported"] and not unsupported_reason:
                    unsupported_reason = "generic_reference용 resolver가 아직 구현되지 않았습니다."

                option_maps[field_name] = {
                    "kind": OptionMapKind.REFERENCE_LOOKUP.value,
                    "name_map": {},
                    "reference_type": reference_type,
                    "multiple_values": multiple_values,
                    "options": None,
                    "source_status": OptionSourceStatus.LOOKUP_REQUIRED.value,
                    "resolver_available": False,
                    **metadata,
                    "unsupported_reason": unsupported_reason,
                }
                continue

            option_maps[field_name] = {
                "kind": OptionMapKind.UNSUPPORTED.value,
                "name_map": {},
                "reference_type": reference_type,
                "multiple_values": multiple_values,
                "options": row.get("options"),
                "source_status": OptionSourceStatus.UNSUPPORTED.value,
                "resolver_available": False,
                **metadata,
            }

        return option_maps

    @staticmethod
    def _validation_context(
        df_col: str,
        schema_field: str,
        option_info: dict[str, Any],
        *,
        row_id: Any = None,
        raw_value: Any = None,
        error: str | None = None,
    ) -> dict[str, Any]:
        return {
            "df_column": df_col,
            "schema_field": schema_field,
            "_row_id": row_id,
            "raw_value": raw_value,
            "reference_type": option_info.get("reference_type"),
            "resolved_field_kind": option_info.get("resolved_field_kind"),
            "resolution_strategy": option_info.get("resolution_strategy"),
            "is_supported": option_info.get("is_supported"),
            "unsupported_reason": option_info.get("unsupported_reason"),
            "requires_lookup": option_info.get("requires_lookup"),
            "lookup_target_kind": option_info.get("lookup_target_kind"),
            "preconstruction_kind": option_info.get("preconstruction_kind"),
            "preconstruction_detail": option_info.get("preconstruction_detail"),
            "payload_target_kind": option_info.get("payload_target_kind"),
            "error": error,
        }

    def check_option_alignment(
        self,
        upload_df: pd.DataFrame,
        option_mapping: dict[str, str],
        option_maps: dict[str, dict],
    ) -> pd.DataFrame:
        errors = []

        for df_col, schema_field in option_mapping.items():
            if df_col not in upload_df.columns:
                errors.append({
                    "df_column": df_col,
                    "schema_field": schema_field,
                    "_row_id": None,
                    "raw_value": None,
                    "status": OptionCheckStatus.DF_COLUMN_MISSING.value,
                })
                continue

            if schema_field not in option_maps:
                errors.append({
                    "df_column": df_col,
                    "schema_field": schema_field,
                    "_row_id": None,
                    "raw_value": None,
                    "status": OptionCheckStatus.OPTION_MAP_MISSING.value,
                })
                continue

            option_info = option_maps[schema_field]

            if not option_info.get("is_supported", True) or option_info.get("kind") == OptionMapKind.UNSUPPORTED.value:
                errors.append({
                    **self._validation_context(df_col, schema_field, option_info),
                    "status": OptionCheckStatus.FIELD_UNSUPPORTED.value,
                })
                continue

            if option_info.get("preconstruction_kind") in {
                PreconstructionKind.FIELD_VALUE.value,
                PreconstructionKind.REFERENCE.value,
                PreconstructionKind.REFERENCE_LIST.value,
                PreconstructionKind.TABLE_FIELD_VALUE.value,
            }:
                errors.append({
                    **self._validation_context(df_col, schema_field, option_info),
                    "status": OptionCheckStatus.PRECONSTRUCTION_REQUIRED.value,
                })

            if option_info.get("kind") == OptionMapKind.USER_LOOKUP.value:
                resolved_col = f"{df_col}__resolved"
                status_col = f"{df_col}__lookup_status"
                error_col = f"{df_col}__lookup_error"

                for _, row in upload_df.iterrows():
                    raw_value = row[df_col]
                    if raw_value is None or str(raw_value).strip() == "":
                        continue

                    resolved_value = row.get(resolved_col) if resolved_col in row.index else None
                    if resolved_value is not None:
                        continue

                    errors.append({
                        **self._validation_context(
                            df_col,
                            schema_field,
                            option_info,
                            row_id=row.get("_row_id"),
                            raw_value=raw_value,
                            error=(row.get(error_col) if error_col in row.index else None),
                        ),
                        "status": (
                            row.get(status_col)
                            if status_col in row.index
                            else UserLookupStatus.USER_LOOKUP_NOT_RUN.value
                        ),
                    })
                continue

            if option_info.get("kind") == OptionMapKind.REFERENCE_LOOKUP.value:
                errors.append({
                    **self._validation_context(
                        df_col,
                        schema_field,
                        option_info,
                        error=option_info.get("unsupported_reason")
                        or "generic_reference lookup resolver가 아직 구현되지 않았습니다.",
                    ),
                    "status": OptionCheckStatus.LOOKUP_REQUIRED.value,
                })
                continue

            if option_info.get("kind") != OptionMapKind.STATIC_OPTIONS.value:
                errors.append({
                    **self._validation_context(df_col, schema_field, option_info),
                    "status": OptionCheckStatus.OPTION_SOURCE_UNAVAILABLE.value,
                })
                continue

            name_map = option_info["name_map"]
            multiple_values = option_info.get("multiple_values", False)

            for _, row in upload_df.iterrows():
                raw_value = row[df_col]
                if raw_value is None or str(raw_value).strip() == "":
                    continue

                if multiple_values and isinstance(raw_value, list):
                    for val in raw_value:
                        if not val:
                            continue
                        key = str(val).strip()
                        if key not in name_map:
                            errors.append({
                                **self._validation_context(
                                    df_col,
                                    schema_field,
                                    option_info,
                                    row_id=row.get("_row_id"),
                                    raw_value=val,
                                ),
                                "status": OptionCheckStatus.OPTION_NOT_FOUND.value,
                            })
                else:
                    key = str(raw_value).strip()
                    if key not in name_map:
                        errors.append({
                            **self._validation_context(
                                df_col,
                                schema_field,
                                option_info,
                                row_id=row.get("_row_id"),
                                raw_value=raw_value,
                            ),
                            "status": OptionCheckStatus.OPTION_NOT_FOUND.value,
                        })

        return pd.DataFrame(errors)

    def apply_option_resolution(
        self,
        upload_df: pd.DataFrame,
        option_mapping: dict[str, str],
        option_maps: dict[str, dict],
    ) -> pd.DataFrame:
        work = upload_df.copy()

        for df_col, schema_field in option_mapping.items():
            if df_col not in work.columns or schema_field not in option_maps:
                continue

            option_info = option_maps[schema_field]
            if option_info.get("kind") == OptionMapKind.USER_LOOKUP.value:
                resolved_col = f"{df_col}__resolved"
                if resolved_col not in work.columns:
                    work[resolved_col] = [None] * len(work)
                continue

            if option_info.get("kind") != OptionMapKind.STATIC_OPTIONS.value:
                work[f"{df_col}__resolved"] = [None] * len(work)
                continue

            name_map = option_info["name_map"]
            reference_type = option_info.get("reference_type")
            multiple_values = option_info.get("multiple_values", False)

            resolved_values = []
            for _, row in work.iterrows():
                raw_value = row[df_col]
                if raw_value is None or str(raw_value).strip() == "":
                    resolved_values.append(None)
                    continue

                if multiple_values and isinstance(raw_value, list):
                    resolved_list = []
                    for val in raw_value:
                        if not val:
                            continue
                        key = str(val).strip()
                        opt = name_map.get(key)
                        if opt:
                            resolved_list.append({
                                "id": opt.get("id"),
                                "name": opt.get("name"),
                                "type": reference_type or ReferenceType.CHOICE_OPTION.value,
                            })

                    resolved_values.append(resolved_list if resolved_list else None)
                else:
                    key = str(raw_value).strip()
                    opt = name_map.get(key)
                    if not opt:
                        resolved_values.append(None)
                        continue
                    resolved_values.append({
                        "id": opt.get("id"),
                        "name": opt.get("name"),
                        "type": reference_type or ReferenceType.CHOICE_OPTION.value,
                    })

            work[f"{df_col}__resolved"] = resolved_values

        return work
