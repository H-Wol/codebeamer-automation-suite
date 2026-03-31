from __future__ import annotations

import pandas as pd


class MappingService:
    def __init__(self, logger=None):
        self.logger = logger

    def flatten_schema_fields(self, schema: dict) -> pd.DataFrame:
        candidates = []
        for key in ["fieldDefinitions", "fields"]:
            if key in schema and isinstance(schema[key], list):
                candidates = schema[key]
                break

        rows = []
        for field in candidates:
            rows.append({
                "field_id": field.get("id"),
                "field_name": field.get("name"),
                "field_label": field.get("label"),
                "field_type": field.get("type"),
                "mandatory": field.get("mandatory", False),
                "tracker_item_field": field.get("trackerItemField"),
                "value_model": field.get("valueModel"),
                "reference_type": field.get("referenceType"),
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

            if mapped_schema_field:
                matched = schema_df[schema_df["field_name"] == mapped_schema_field]
                if not matched.empty:
                    m = matched.iloc[0]
                    row["field_id"] = m["field_id"]
                    row["field_type"] = m["field_type"]
                    row["mandatory"] = m["mandatory"]
                    row["value_model"] = m["value_model"]
                    row["reference_type"] = m["reference_type"]

            rows.append(row)

        return pd.DataFrame(rows)

    def get_option_field_candidates(self, schema_df: pd.DataFrame) -> pd.DataFrame:
        mask = (
            schema_df["reference_type"].notna() |
            schema_df["value_model"].astype(str).str.contains("Choice", case=False, na=False)
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

            for _, row in upload_df.iterrows():
                raw_value = row[df_col]
                if raw_value is None or str(raw_value).strip() == "":
                    continue

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
            reference_type = option_maps[schema_field]["reference_type"]

            resolved_values = []
            for _, row in work.iterrows():
                raw_value = row[df_col]
                if raw_value is None or str(raw_value).strip() == "":
                    resolved_values.append(None)
                    continue

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
                    ref["_referenceType"] = reference_type

                resolved_values.append(ref)

            work[f"{df_col}__resolved"] = resolved_values

        return work
