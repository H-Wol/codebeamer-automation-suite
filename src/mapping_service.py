from __future__ import annotations

import pandas as pd


class MappingService:
    def __init__(self, logger=None):
        self.logger = logger

    def flatten_schema_fields(self, schema: dict | list) -> pd.DataFrame:
        candidates = []

        # Handle direct list (schema.json format)
        if isinstance(schema, list):
            candidates = schema
        # Handle dict with fieldDefinitions or fields key
        elif isinstance(schema, dict):
            for key in ["fieldDefinitions", "fields"]:
                if key in schema and isinstance(schema[key], list):
                    candidates = schema[key]
                    break

        rows = []
        for field in candidates:
            # Check if field has options (for choice/option fields)
            options = field.get("options", [])
            has_options = len(options) > 0

            # Check if field is TableField
            is_table_field = field.get("type") == "TableField"
            columns = field.get("columns", []) if is_table_field else None

            rows.append({
                "field_id": field.get("id"),
                "field_name": field.get("name"),
                "field_label": field.get("label") or field.get("title"),
                "field_type": field.get("type"),
                "mandatory": any(field.get("mandatoryInStatuses", [])) if field.get("mandatoryInStatuses") else field.get("mandatory", False),
                "tracker_item_field": field.get("trackerItemField", field.get("name", None)),
                "value_model": field.get("valueModel"),
                "reference_type": field.get("referenceType"),
                "has_options": has_options,
                "multiple_values": field.get("multipleValues", False),
                "options": options if has_options else None,
                "is_table_field": is_table_field,
                "table_columns": columns,
                "raw": field,
            })
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
                "status": "UNMAPPED" if not mapped_schema_field else ("OK" if schema_exists else "SCHEMA_FIELD_MISSING"),
            }

            if mapped_schema_field and schema_exists:
                matched = schema_df[schema_df["field_name"] == mapped_schema_field]
                if not matched.empty:
                    m = matched.iloc[0]
                    row["field_id"] = m["field_id"]
                    row["field_label"] = m.get("field_label")
                    row["field_type"] = m["field_type"]
                    row["mandatory"] = m["mandatory"]
                    row["value_model"] = m["value_model"]
                    row["reference_type"] = m.get("reference_type")
                    row["hidden"] = m.get("raw", {}).get("hidden", False)
                    row["is_option_field"] = m.get("has_options", False) or (m.get("reference_type") is not None) or (
                        isinstance(m.get("value_model"), str) and "Choice" in m.get("value_model", "")
                    )
                    row["tracker_item_field"] = m.get("tracker_item_field")

            rows.append(row)

        return pd.DataFrame(rows)

    def get_option_field_candidates(self, schema_df: pd.DataFrame) -> pd.DataFrame:
        # Fields with options are those that have:
        # - reference_type (UserReference, ChoiceOptionReference, TrackerItemReference)
        # - or valueModel containing "Choice"
        # - or actual options in the field definition
        mask = (
            schema_df["reference_type"].notna() |
            schema_df["value_model"].astype(str).str.contains("Choice", case=False, na=False) |
            schema_df["has_options"].fillna(False)
        )
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
            raise ValueError(f"중복 옵션명이 있습니다: {sorted(duplicates)}")

        return result

    def build_option_maps_from_schema(self, schema_df: pd.DataFrame) -> dict[str, dict]:
        """
        Schema에 정의된 옵션들로부터 option_maps를 생성합니다.
        Returns: {field_name: {"name_map": {...}, "reference_type": "...", "multiple_values": bool}}
        """
        option_maps = {}

        for _, row in schema_df.iterrows():
            field_name = row["field_name"]
            if not field_name:
                continue

            # options가 있는 경우 (ChoiceOptionField 등)
            options = row.get("options")
            if options and len(options) > 0:
                try:
                    name_map = self.build_option_name_map(options)
                    option_maps[field_name] = {
                        "name_map": name_map,
                        "reference_type": row.get("reference_type"),
                        "multiple_values": row.get("multiple_values", False),
                        "options": options,
                    }
                except ValueError:
                    if self.logger:
                        self.logger.warning(f"중복 옵션이 있습니다: {field_name}")
                    continue

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
                    "status": "DF_COLUMN_MISSING",
                })
                continue

            if schema_field not in option_maps:
                errors.append({
                    "df_column": df_col,
                    "schema_field": schema_field,
                    "_row_id": None,
                    "raw_value": None,
                    "status": "OPTION_MAP_MISSING",
                })
                continue

            name_map = option_maps[schema_field]["name_map"]
            multiple_values = option_maps[schema_field].get("multiple_values", False)

            for _, row in upload_df.iterrows():
                raw_value = row[df_col]
                if raw_value is None or str(raw_value).strip() == "":
                    continue

                # multipleValues가 true면 구분자로 분리해서 확인
                if multiple_values and isinstance(raw_value, list):
                    for val in raw_value:
                        if not val:
                            continue
                        key = val
                        if key not in name_map:
                            errors.append({
                                "_row_id": row.get("_row_id"),
                                "df_column": df_col,
                                "schema_field": schema_field,
                                "raw_value": val,
                                "status": "OPTION_NOT_FOUND",
                            })
                else:
                    key = str(raw_value).strip()
                    if key not in name_map:
                        errors.append({
                            "_row_id": row.get("_row_id"),
                            "df_column": df_col,
                            "schema_field": schema_field,
                            "raw_value": raw_value,
                            "status": "OPTION_NOT_FOUND",
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

            name_map = option_maps[schema_field]["name_map"]
            reference_type = option_maps[schema_field].get("reference_type")
            multiple_values = option_maps[schema_field].get("multiple_values", False)

            resolved_values = []
            for _, row in work.iterrows():
                raw_value = row[df_col]
                if raw_value is None or str(raw_value).strip() == "":
                    resolved_values.append(None)
                    continue

                # multipleValues가 true면 구분자로 분리
                if multiple_values and isinstance(raw_value, list):
                    # 쉼표, 세미콜론, | 등 다양한 구분자 지원
                    resolved_list = []
                    for val in raw_value:
                        if not val:
                            continue
                        opt = name_map.get(val)
                        if opt:
                            ref = {
                                "id": opt.get("id"),
                                "name": opt.get("name"),
                            }
                            if reference_type:
                                ref["type"] = reference_type
                            resolved_list.append(ref)

                    resolved_values.append(resolved_list if resolved_list else None)
                else:
                    # multipleValues가 false면 단일 옵션
                    key = str(raw_value).strip()
                    opt = name_map.get(key)
                    if not opt:
                        resolved_values.append(None)
                        continue

                    ref = {
                        "id": opt.get("id"),
                        "name": opt.get("name"),
                    }
                    if reference_type:
                        ref["type"] = reference_type

                    resolved_values.append(ref)

            work[f"{df_col}__resolved"] = resolved_values

        return work
