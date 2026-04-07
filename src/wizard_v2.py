from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd

from .models import AbstractFieldValue
from .models import DomainModel
from .models import TableFieldValue
from .models import TextFieldValue
from .models import TrackerItemBase
from .models import WizardState
from .codebeamer_client import CodebeamerClient
from .excel_processor import ExcelHierarchyProcessor
from .mapping_service_v2 import MappingServiceV2


class CodebeamerUploadWizardV2:
    def __init__(self, client: CodebeamerClient, processor: ExcelHierarchyProcessor, mapper: MappingServiceV2, logger=None):
        self.client = client
        self.processor = processor
        self.mapper = mapper
        self.logger = logger
        self.state = WizardState()

    def load_projects(self) -> list[dict]:
        return self.client.get_projects()

    def select_project(self, project_id: int) -> None:
        self.state.project_id = project_id

    def load_trackers(self) -> list[dict]:
        if self.state.project_id is None:
            raise ValueError("project_id must be selected first.")
        return self.client.get_trackers(self.state.project_id)

    def load_tracker_items(self, tracker_id: int) -> list[dict]:
        return self.client.get_tracker_children(tracker_id)

    def select_tracker(self, tracker_id: int) -> None:
        self.state.tracker_id = tracker_id

    def read_excel(self, file_path: str, sheet_name: str | int = 0, list_cols: list[str] | None = None) -> None:
        if list_cols is None:
            list_cols = []

        self.state.list_cols = list_cols
        self.state.raw_df = self.processor.read_excel(file_path=file_path, sheet_name=sheet_name)
        self.state.merged_df = self.processor.merge_multiline_records(self.state.raw_df, list_cols=list_cols)
        self.state.hierarchy_df = self.processor.add_hierarchy_by_indent(self.state.merged_df)
        self.state.upload_df = self.processor.build_upload_df(self.state.hierarchy_df, list_cols=list_cols)

    def load_schema_and_compare(self, selected_mapping: dict[str, str]) -> pd.DataFrame:
        if self.state.tracker_id is None:
            raise ValueError("tracker_id must be selected first.")
        if self.state.upload_df is None:
            raise ValueError("upload_df is not ready. Read Excel first.")

        self.state.selected_mapping = selected_mapping
        self.state.schema = self.client.get_tracker_schema(self.state.tracker_id)
        self.state.schema_df = self.mapper.flatten_schema_fields(self.state.schema)
        self.state.comparison_df = self.mapper.compare_upload_df_with_schema(
            upload_df=self.state.upload_df,
            schema_df=self.state.schema_df,
            selected_mapping=selected_mapping,
        )

        self._detect_table_field_columns()
        return self.state.comparison_df

    def _detect_table_field_columns(self) -> None:
        if self.state.schema_df is None or self.state.upload_df is None:
            return

        table_fields = self.state.schema_df[self.state.schema_df.get("is_table_field", False)]
        if table_fields.empty:
            return

        table_field_info = {}

        for _, tf_row in table_fields.iterrows():
            tf_name = tf_row["field_name"]
            tf_columns = tf_row.get("table_columns", [])

            if tf_columns:
                table_field_info[tf_name] = {}
                for col_def in tf_columns:
                    col_name = col_def.get("name")
                    if col_name:
                        table_field_info[tf_name][col_name] = col_def

        table_field_mapping = {}
        for df_col in self.state.upload_df.columns:
            if "." not in df_col:
                continue

            parts = df_col.split(".", 1)
            if len(parts) != 2:
                continue

            potential_tf_name = parts[0].strip()
            potential_col_name = parts[1].strip()

            if potential_tf_name in table_field_info and potential_col_name in table_field_info[potential_tf_name]:
                table_field_mapping[df_col] = {
                    "table_field_name": potential_tf_name,
                    "column_name": potential_col_name,
                    "column_info": table_field_info[potential_tf_name][potential_col_name],
                }

        self.state.table_field_mapping = table_field_mapping

    def process_option_mapping(
        self,
        selected_mapping: dict[str, str],
        selected_option_mapping: dict[str, str] | None = None,
    ) -> tuple[dict[str, str], pd.DataFrame]:
        if self.state.schema_df is None:
            raise ValueError("Schema must be loaded before option processing.")
        if self.state.upload_df is None:
            raise ValueError("upload_df is required before option processing.")

        option_fields = self.mapper.get_option_field_candidates(self.state.schema_df)
        self.state.option_candidates_df = option_fields

        if selected_option_mapping is None:
            selected_option_mapping = {}
            option_field_names = set(option_fields["field_name"].dropna().astype(str))
            for excel_col, schema_field in selected_mapping.items():
                if schema_field in option_field_names:
                    selected_option_mapping[excel_col] = schema_field

        if not selected_option_mapping:
            self.state.selected_option_mapping = {}
            self.state.option_maps = {}
            self.state.option_check_df = pd.DataFrame()
            self.state.converted_upload_df = self.state.upload_df.copy()
            return {}, pd.DataFrame()

        self.state.selected_option_mapping = selected_option_mapping
        option_maps = self.mapper.build_option_maps_from_schema(self.state.schema_df)
        self.state.option_maps = option_maps

        option_check_df = self.mapper.check_option_alignment(
            upload_df=self.state.upload_df,
            option_mapping=selected_option_mapping,
            option_maps=option_maps,
        )
        self.state.option_check_df = option_check_df

        self.state.converted_upload_df = self.mapper.apply_option_resolution(
            upload_df=self.state.upload_df,
            option_mapping=selected_option_mapping,
            option_maps=option_maps,
        )

        return selected_option_mapping, option_check_df

    def _create_field_value(self, field_info: dict, value) -> AbstractFieldValue:
        return TrackerItemBase()._create_field_value(field_info, value) or TextFieldValue(field_id=0, field_name="")

    def _serialize_payload_value(self, value: Any) -> Any:
        if isinstance(value, DomainModel):
            return value.to_dict()
        if isinstance(value, list):
            return [self._serialize_payload_value(item) for item in value]
        if isinstance(value, dict):
            return {key: self._serialize_payload_value(item) for key, item in value.items()}
        return value

    @staticmethod
    def _has_row_value(row: pd.Series, column_name: str) -> bool:
        if column_name not in row.index:
            return False

        value = row[column_name]
        if value is None:
            return False
        if isinstance(value, float) and pd.isna(value):
            return False
        if isinstance(value, str) and value.strip() == "":
            return False
        return True

    def _resolve_option_field_value(self, row: pd.Series, row_id: int, df_col: str, schema_field: str) -> Any:
        option_info = (self.state.option_maps or {}).get(schema_field, {})
        resolved_col = f"{df_col}__resolved"

        if resolved_col in row.index and row[resolved_col] is not None:
            return row[resolved_col]

        if not self._has_row_value(row, df_col):
            return None

        if option_info.get("kind") == "reference_lookup":
            raise ValueError(
                f"Field '{schema_field}' requires reference lookup for type "
                f"'{option_info.get('reference_type')}' before building payload for _row_id={row_id}."
            )

        raise ValueError(
            f"Option field '{schema_field}' could not resolve value {row[df_col]!r} for _row_id={row_id}."
        )

    def _build_table_custom_fields(self, row: pd.Series) -> list[TableFieldValue]:
        custom_fields: list[TableFieldValue] = []
        if not self.state.table_field_mapping or self.state.schema_df is None:
            return custom_fields

        table_fields_by_name = {}
        table_schema_rows = self.state.schema_df[self.state.schema_df.get("is_table_field", False).fillna(False)]

        for _, tf_row in table_schema_rows.iterrows():
            tf_name = tf_row["field_name"]
            table_fields_by_name[tf_name] = {
                "field_id": tf_row["field_id"],
                "columns": tf_row.get("table_columns", []),
            }

        tables_data: dict[str, list[dict[str, dict[str, Any]]]] = {}

        for df_col, tf_info in self.state.table_field_mapping.items():
            tf_name = tf_info["table_field_name"]
            col_name = tf_info["column_name"]
            col_def = tf_info["column_info"]

            if tf_name not in tables_data:
                tables_data[tf_name] = [{}]

            field_value = row[df_col] if df_col in row.index and row[df_col] is not None else None
            tables_data[tf_name][0][col_name] = {
                "fieldId": col_def.get("id"),
                "name": col_name,
                "value": field_value,
                "type": col_def.get("valueModel", "TextFieldValue"),
            }

        for tf_name, table_rows in tables_data.items():
            if tf_name not in table_fields_by_name:
                continue

            values = []
            for row_data in table_rows:
                row_fields = list(row_data.values())
                if any(v["value"] is not None for v in row_fields):
                    values.append(row_fields)

            if values:
                custom_fields.append(
                    TableFieldValue(
                        field_id=table_fields_by_name[tf_name]["field_id"],
                        field_name=tf_name,
                        values=values,
                    )
                )

        return custom_fields

    def preview_payload(self, row_id: int) -> dict:
        if self.state.converted_upload_df is not None:
            df = self.state.converted_upload_df
        elif self.state.upload_df is not None:
            df = self.state.upload_df
        else:
            raise ValueError("No upload dataframe is available.")

        row_df = df[df["_row_id"] == row_id]
        if row_df.empty:
            raise ValueError(f"_row_id={row_id} was not found.")

        row = row_df.iloc[0]
        item = TrackerItemBase()
        item.name = str(row.get("upload_name", ""))

        for df_col, schema_field in self.state.selected_mapping.items():
            matched = self.state.schema_df[self.state.schema_df["field_name"] == schema_field]
            if matched.empty:
                continue

            field_row = matched.iloc[0]
            tracker_field = field_row["tracker_item_field"]
            field_id = field_row.get("field_id")
            field_type = field_row.get("field_type")
            multiple_values = field_row.get("multiple_values", False)

            if not tracker_field:
                continue

            field_value = None
            if df_col in self.state.selected_option_mapping:
                field_value = self._resolve_option_field_value(row, row_id, df_col, schema_field)
            elif self._has_row_value(row, df_col):
                field_value = row[df_col]

            if field_value is None:
                continue

            field_info = {
                "field_id": field_id,
                "field_type": field_type,
                "field_name": schema_field,
                "multiple_values": multiple_values,
                "reference_type": field_row.get("reference_type"),
                "value_model": field_row.get("value_model"),
            }
            item.set_field_value(tracker_field, field_value, field_info)

        payload = item.create_new_item_payload()
        table_custom_fields = self._build_table_custom_fields(row)
        if table_custom_fields:
            existing_custom_fields = payload.get("customFields", [])
            payload["customFields"] = existing_custom_fields + [
                field.to_dict() for field in table_custom_fields
            ]

        return self._serialize_payload_value(payload)

    def upload(self, dry_run: bool = False, continue_on_error: bool = True) -> dict:
        if self.state.tracker_id is None:
            raise ValueError("tracker_id is not set.")
        if self.state.upload_df is None and self.state.converted_upload_df is None:
            raise ValueError("No upload dataframe is available.")

        df = self.state.converted_upload_df if self.state.converted_upload_df is not None else self.state.upload_df
        work = df.copy().reset_index(drop=True)

        pending = set(work["_row_id"].tolist())
        created_map = {}
        success_logs = []
        failed_logs = []

        while pending:
            progress = False

            for _, row in work.iterrows():
                row_id = int(row["_row_id"])
                if row_id not in pending:
                    continue

                parent_row_id = row["parent_row_id"]
                if parent_row_id is None or pd.isna(parent_row_id):
                    parent_item_id = None
                else:
                    parent_row_id = int(parent_row_id)
                    if parent_row_id not in created_map:
                        continue
                    parent_item_id = created_map[parent_row_id]

                try:
                    payload = self.preview_payload(row_id)

                    if dry_run:
                        result = {"id": f"DRYRUN-{row_id}"}
                    else:
                        result = self.client.create_item(
                            tracker_id=self.state.tracker_id,
                            payload=payload,
                            parent_item_id=parent_item_id,
                        )

                    created_map[row_id] = result["id"]
                    pending.remove(row_id)
                    progress = True

                    success_logs.append({
                        "_row_id": row_id,
                        "parent_row_id": row["parent_row_id"],
                        "upload_name": row["upload_name"],
                        "created_item_id": result["id"],
                        "status": "SUCCESS",
                    })
                    print(f"Row {row['upload_name']} uploaded successfully: item_id={result['id']}")

                except Exception as exc:
                    failed_logs.append({
                        "_row_id": row_id,
                        "parent_row_id": row["parent_row_id"],
                        "upload_name": row["upload_name"],
                        "error": str(exc),
                        "status": "FAILED",
                    })

                    if not continue_on_error:
                        self.state.upload_result = {
                            "created_map": created_map,
                            "success_df": pd.DataFrame(success_logs),
                            "failed_df": pd.DataFrame(failed_logs),
                            "unresolved_df": work[work["_row_id"].isin(sorted(pending))].copy(),
                        }
                        return self.state.upload_result

                    pending.remove(row_id)
                    progress = True

            if not progress:
                break

        self.state.upload_result = {
            "created_map": created_map,
            "success_df": pd.DataFrame(success_logs),
            "failed_df": pd.DataFrame(failed_logs),
            "unresolved_df": work[work["_row_id"].isin(sorted(pending))].copy(),
        }
        return self.state.upload_result

    def save_state(self, output_dir: str) -> None:
        out = Path(output_dir)
        out.mkdir(parents=True, exist_ok=True)

        frames = {
            "raw_df.csv": self.state.raw_df,
            "merged_df.csv": self.state.merged_df,
            "hierarchy_df.csv": self.state.hierarchy_df,
            "upload_df.csv": self.state.upload_df,
            "converted_upload_df.csv": self.state.converted_upload_df,
            "schema_df.csv": self.state.schema_df,
            "comparison_df.csv": self.state.comparison_df,
            "option_check_df.csv": self.state.option_check_df,
        }

        for name, df in frames.items():
            if isinstance(df, pd.DataFrame) and not df.empty:
                df.to_excel(out / name, index=False)

        if self.state.schema is not None:
            with open(out / "schema.json", "w", encoding="utf-8") as file:
                json.dump(self.state.schema, file, ensure_ascii=False, indent=2)

        if self.state.option_maps is not None:
            with open(out / "option_maps.json", "w", encoding="utf-8") as file:
                json.dump(self.state.option_maps, file, ensure_ascii=False, indent=2)

        if self.state.upload_result is not None:
            for key in ["success_df", "failed_df", "unresolved_df"]:
                df = self.state.upload_result.get(key)
                if isinstance(df, pd.DataFrame) and not df.empty:
                    df.to_csv(out / f"{key}.csv", index=False)

            with open(out / "created_map.json", "w", encoding="utf-8") as file:
                json.dump(self.state.upload_result.get("created_map", {}), file, ensure_ascii=False, indent=2)
