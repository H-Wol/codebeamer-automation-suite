from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from .models import WizardState
from .codebeamer_client import CodebeamerClient
from .excel_processor_v2 import ExcelHierarchyProcessorV2
from .mapping_service import MappingService


class CodebeamerUploadWizardV2:
    def __init__(self, client: CodebeamerClient, processor: ExcelHierarchyProcessorV2, mapper: MappingService, logger=None):
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
            raise ValueError("먼저 project_id를 선택해야 합니다.")
        return self.client.get_trackers(self.state.project_id)

    def select_tracker(self, tracker_id: int, sample_item_id: int | None = None) -> None:
        self.state.tracker_id = tracker_id
        self.state.sample_item_id = sample_item_id

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
            raise ValueError("먼저 tracker_id를 선택해야 합니다.")
        if self.state.upload_df is None:
            raise ValueError("먼저 엑셀을 읽어야 합니다.")

        self.state.selected_mapping = selected_mapping
        self.state.schema = self.client.get_tracker_schema(self.state.tracker_id)
        self.state.schema_df = self.mapper.flatten_schema_fields(self.state.schema)
        self.state.comparison_df = self.mapper.compare_upload_df_with_schema(
            upload_df=self.state.upload_df,
            schema_df=self.state.schema_df,
            selected_mapping=selected_mapping,
        )
        return self.state.comparison_df

    def check_option_fields(self, selected_option_mapping: dict[str, str]) -> pd.DataFrame:
        if self.state.schema_df is None:
            raise ValueError("먼저 스키마를 불러와야 합니다.")
        if self.state.upload_df is None:
            raise ValueError("먼저 upload_df가 필요합니다.")
        if self.state.sample_item_id is None:
            raise ValueError("sample_item_id가 필요합니다.")

        self.state.selected_option_mapping = selected_option_mapping
        option_maps = {}

        for schema_field in selected_option_mapping.values():
            matched = self.state.schema_df[self.state.schema_df["field_name"] == schema_field]
            if matched.empty:
                continue

            row = matched.iloc[0]
            field_id = int(row["field_id"])
            options = self.client.get_field_options(self.state.sample_item_id, field_id)
            option_maps[schema_field] = {
                "field_id": field_id,
                "reference_type": row["reference_type"],
                "name_map": self.mapper.build_option_name_map(options),
                "options": options,
            }

        self.state.option_maps = option_maps
        self.state.option_check_df = self.mapper.check_option_alignment(
            upload_df=self.state.upload_df,
            option_mapping=selected_option_mapping,
            option_maps=option_maps,
        )
        self.state.converted_upload_df = self.mapper.apply_option_resolution(
            upload_df=self.state.upload_df,
            option_mapping=selected_option_mapping,
            option_maps=option_maps,
        )
        return self.state.option_check_df

    def preview_payload(self, row_id: int) -> dict:
        if self.state.converted_upload_df is not None:
            df = self.state.converted_upload_df
        elif self.state.upload_df is not None:
            df = self.state.upload_df
        else:
            raise ValueError("업로드용 데이터가 없습니다.")

        row_df = df[df["_row_id"] == row_id]
        if row_df.empty:
            raise ValueError(f"_row_id={row_id} 행을 찾을 수 없습니다.")

        row = row_df.iloc[0]
        payload = {"name": row["upload_name"]}

        if "upload_description" in row.index and row["upload_description"] is not None:
            payload["description"] = row["upload_description"]

        for df_col, schema_field in self.state.selected_option_mapping.items():
            resolved_col = f"{df_col}__resolved"
            if resolved_col in row.index and row[resolved_col] is not None:
                payload[schema_field] = row[resolved_col]

        return payload

    def upload(self, dry_run: bool = False, continue_on_error: bool = True) -> dict:
        if self.state.tracker_id is None:
            raise ValueError("tracker_id가 없습니다.")
        if self.state.upload_df is None and self.state.converted_upload_df is None:
            raise ValueError("업로드용 데이터가 없습니다.")

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

                payload = self.preview_payload(row_id)

                try:
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

                except Exception as e:
                    failed_logs.append({
                        "_row_id": row_id,
                        "parent_row_id": row["parent_row_id"],
                        "upload_name": row["upload_name"],
                        "error": str(e),
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
            "raw_df.xlsx": self.state.raw_df,
            "merged_df.xlsx": self.state.merged_df,
            "hierarchy_df.xlsx": self.state.hierarchy_df,
            "upload_df.xlsx": self.state.upload_df,
            "converted_upload_df.xlsx": self.state.converted_upload_df,
            "schema_df.xlsx": self.state.schema_df,
            "comparison_df.xlsx": self.state.comparison_df,
            "option_check_df.xlsx": self.state.option_check_df,
        }

        for name, df in frames.items():
            if isinstance(df, pd.DataFrame) and not df.empty:
                df.to_excel(out / name, index=False)

        if self.state.schema is not None:
            with open(out / "schema.json", "w", encoding="utf-8") as f:
                json.dump(self.state.schema, f, ensure_ascii=False, indent=2)

        if self.state.option_maps is not None:
            with open(out / "option_maps.json", "w", encoding="utf-8") as f:
                json.dump(self.state.option_maps, f, ensure_ascii=False, indent=2)

        if self.state.upload_result is not None:
            for key in ["success_df", "failed_df", "unresolved_df"]:
                df = self.state.upload_result.get(key)
                if isinstance(df, pd.DataFrame) and not df.empty:
                    df.to_excel(out / f"{key}.xlsx", index=False)

            with open(out / "created_map.json", "w", encoding="utf-8") as f:
                json.dump(self.state.upload_result.get("created_map", {}), f, ensure_ascii=False, indent=2)
