from __future__ import annotations

from typing import Any

import pandas as pd

from .models import MappingStatus
from .models import OptionCheckStatus
from .models import OptionMapKind
from .models import OptionSourceKind
from .models import OptionSourceStatus
from .models import ReferenceType
from .models import SchemaFieldType
from .models import TrackerItemField
from .models import TrackerSchemaName
from .models import UserLookupStatus


class MappingService:
    def __init__(self, logger=None):
        self.logger = logger

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
    def _is_option_like_field(cls, field: pd.Series | dict[str, Any]) -> bool:
        getter = field.get
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
        has_options = bool(getter("has_options", False) or getter("options", []))
        if has_options:
            return OptionSourceKind.SCHEMA_OPTIONS.value
        if cls._is_option_like_field(field):
            return OptionSourceKind.REFERENCE_LOOKUP.value
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
                "value_model": value_model,
                "reference_type": reference_type,
                "has_options": has_options,
                "multiple_values": field.get("multipleValues", None),
                "options": options if has_options else None,
                "is_table_field": is_table_field,
                "table_columns": columns,
                "raw": field,
            }
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

            rows.append(row)

        return pd.DataFrame(rows)

    def get_option_field_candidates(self, schema_df: pd.DataFrame) -> pd.DataFrame:
        if "is_option_like" in schema_df.columns:
            mask = schema_df["is_option_like"].fillna(False)
            return schema_df[mask].copy()

        mask = schema_df.apply(self._is_option_like_field, axis=1)
        return schema_df[mask].copy()

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

    def build_option_maps_from_schema(self, schema_df: pd.DataFrame) -> dict[str, dict]:
        option_maps = {}
        option_fields = self.get_option_field_candidates(schema_df)

        for _, row in option_fields.iterrows():
            field_name = row["field_name"]
            if not field_name:
                continue

            options = row.get("options")
            if options and len(options) > 0:
                try:
                    name_map = self.build_option_name_map(options)
                    option_maps[field_name] = {
                        "kind": OptionMapKind.STATIC_OPTIONS.value,
                        "name_map": name_map,
                        "reference_type": row.get("reference_type"),
                        "multiple_values": row.get("multiple_values", False),
                        "options": options,
                        "source_status": OptionSourceStatus.READY.value,
                    }
                except ValueError:
                    if self.logger:
                        self.logger.warning(f"Duplicate options found in field: {field_name}")
                    continue
                continue

            if row.get("reference_type") == ReferenceType.USER.value:
                option_maps[field_name] = {
                    "kind": OptionMapKind.USER_LOOKUP.value,
                    "name_map": {},
                    "reference_type": row.get("reference_type"),
                    "multiple_values": row.get("multiple_values", False),
                    "options": None,
                    "source_status": OptionSourceStatus.LOOKUP_REQUIRED.value,
                }
                continue

            option_maps[field_name] = {
                "kind": OptionMapKind.REFERENCE_LOOKUP.value,
                "name_map": {},
                "reference_type": row.get("reference_type"),
                "multiple_values": row.get("multiple_values", False),
                "options": None,
                "source_status": OptionSourceStatus.LOOKUP_REQUIRED.value,
            }

        return option_maps

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
                        "_row_id": row.get("_row_id"),
                        "df_column": df_col,
                        "schema_field": schema_field,
                        "raw_value": raw_value,
                        "reference_type": option_info.get("reference_type"),
                        "status": (
                            row.get(status_col)
                            if status_col in row.index
                            else UserLookupStatus.USER_LOOKUP_NOT_RUN.value
                        ),
                        "error": row.get(error_col) if error_col in row.index else None,
                    })
                continue

            if option_info.get("kind") != OptionMapKind.STATIC_OPTIONS.value:
                errors.append({
                    "df_column": df_col,
                    "schema_field": schema_field,
                    "_row_id": None,
                    "raw_value": None,
                    "reference_type": option_info.get("reference_type"),
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
                                "_row_id": row.get("_row_id"),
                                "df_column": df_col,
                                "schema_field": schema_field,
                                "raw_value": val,
                                "status": OptionCheckStatus.OPTION_NOT_FOUND.value,
                            })
                else:
                    key = str(raw_value).strip()
                    if key not in name_map:
                        errors.append({
                            "_row_id": row.get("_row_id"),
                            "df_column": df_col,
                            "schema_field": schema_field,
                            "raw_value": raw_value,
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
