from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from .models import WizardState
from .codebeamer_client import CodebeamerClient
from .excel_processor import ExcelHierarchyProcessor
from .mapping_service import MappingService
from .models import TrackerItemBase, TableFieldValue, TextFieldValue, AbstractFieldValue


class CodebeamerUploadWizard:
    def __init__(self, client: CodebeamerClient, processor: ExcelHierarchyProcessor, mapper: MappingService, logger=None):
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

    def load_tracker_items(self, tracker_id: int) -> list[dict]:
        return self.client.get_tracker_children(tracker_id)

    def select_tracker(self, tracker_id: int) -> None:
        self.state.tracker_id = tracker_id

    def read_excel(self, file_path: str, sheet_name: str | int = 0, list_cols: list[str] | None = None) -> None:
        if list_cols is None:
            list_cols = []

        self.state.list_cols = list_cols
        self.state.raw_df = self.processor.read_excel(
            file_path=file_path, sheet_name=sheet_name)
        self.state.merged_df = self.processor.merge_multiline_records(
            self.state.raw_df, list_cols=list_cols)
        self.state.hierarchy_df = self.processor.add_hierarchy_by_indent(
            self.state.merged_df)
        self.state.upload_df = self.processor.build_upload_df(
            self.state.hierarchy_df, list_cols=list_cols)

    def load_schema_and_compare(self, selected_mapping: dict[str, str]) -> pd.DataFrame:
        if self.state.tracker_id is None:
            raise ValueError("먼저 tracker_id를 선택해야 합니다.")
        if self.state.upload_df is None:
            raise ValueError("먼저 엑셀을 읽어야 합니다.")

        self.state.selected_mapping = selected_mapping
        self.state.schema = self.client.get_tracker_schema(
            self.state.tracker_id)
        self.state.schema_df = self.mapper.flatten_schema_fields(
            self.state.schema)
        self.state.comparison_df = self.mapper.compare_upload_df_with_schema(
            upload_df=self.state.upload_df,
            schema_df=self.state.schema_df,
            selected_mapping=selected_mapping,
        )

        # TableField 매칭 처리
        self._detect_table_field_columns()

        return self.state.comparison_df

    def _detect_table_field_columns(self) -> None:
        """
        Excel 헤더에서 "TableField.ColumnName" 형식을 감지하고 TableField 매핑을 자동으로 생성합니다.
        """
        if self.state.schema_df is None or self.state.upload_df is None:
            return

        # 스키마에서 TableField 찾기
        table_fields = self.state.schema_df[self.state.schema_df.get(
            "is_table_field", False)]
        if table_fields.empty:
            return

        # 각 TableField에 대해 columns 정보 추출
        table_field_info = {}  # {table_field_name: {column_name: column_info}}

        for _, tf_row in table_fields.iterrows():
            tf_name = tf_row["field_name"]
            tf_columns = tf_row.get("table_columns", [])

            if tf_columns:
                table_field_info[tf_name] = {}
                for col_def in tf_columns:
                    col_name = col_def.get("name")
                    if col_name:
                        table_field_info[tf_name][col_name] = col_def

        # Excel 헤더에서 TableField 컬럼 찾기
        table_field_mapping = {}
        for df_col in self.state.upload_df.columns:
            # "." 포함하는 컬럼 확인
            if "." in df_col:
                parts = df_col.split(".", 1)
                if len(parts) == 2:
                    potential_tf_name = parts[0].strip()
                    potential_col_name = parts[1].strip()

                    # 실제 TableField인지 확인
                    if potential_tf_name in table_field_info:
                        if potential_col_name in table_field_info[potential_tf_name]:
                            table_field_mapping[df_col] = {
                                "table_field_name": potential_tf_name,
                                "column_name": potential_col_name,
                                "column_info": table_field_info[potential_tf_name][potential_col_name],
                            }

        self.state.table_field_mapping = table_field_mapping

    def process_option_mapping(self, selected_mapping: dict[str, str], selected_option_mapping: dict[str, str] | None = None) -> tuple[dict[str, str], pd.DataFrame]:
        """
        옵션 필드 매핑을 처리하고 옵션 변환을 적용합니다.

        Args:
            selected_mapping: 엑셀 컬럼 -> 스키마 필드 매핑
            selected_option_mapping: 옵션 변환할 엑셀 컬럼 -> 스키마 필드 매핑 (None이면 자동 감지)

        Returns:
            (selected_option_mapping, converted_upload_df) 또는 오류 시 빈 데이터프레임
        """
        if self.state.schema_df is None:
            raise ValueError("먼저 스키마를 불러와야 합니다.")
        if self.state.upload_df is None:
            raise ValueError("먼저 upload_df가 필요합니다.")

        # 옵션 필드 찾기
        option_fields = self.state.schema_df[self.state.schema_df["has_options"].fillna(
            False)].copy()

        # selected_option_mapping이 없으면 자동 감지
        if selected_option_mapping is None:
            selected_option_mapping = {}
            # 옵션 필드에 매핑된 엑셀 컬럼 찾기
            for _, field_row in option_fields.iterrows():
                field_name = field_row["field_name"]
                for excel_col, schema_field in selected_mapping.items():
                    if schema_field == field_name:
                        selected_option_mapping[excel_col] = field_name
                        break

        if not selected_option_mapping:
            # 옵션 변환이 필요 없음
            self.state.selected_option_mapping = {}
            self.state.converted_upload_df = None
            return {}, pd.DataFrame()

        # 옵션 맵 생성
        self.state.selected_option_mapping = selected_option_mapping
        option_maps = self.mapper.build_option_maps_from_schema(
            self.state.schema_df)

        self.state.option_maps = option_maps

        # 옵션 정렬 확인
        option_check_df = self.mapper.check_option_alignment(
            upload_df=self.state.upload_df,
            option_mapping=selected_option_mapping,
            option_maps=option_maps,
        )

        self.state.option_check_df = option_check_df

        # 옵션 변환 적용
        self.state.converted_upload_df = self.mapper.apply_option_resolution(
            upload_df=self.state.upload_df,
            option_mapping=selected_option_mapping,
            option_maps=option_maps,
        )

        return selected_option_mapping, option_check_df

    def _create_field_value(self, field_info: dict, value) -> AbstractFieldValue:
        """TrackerItemBase의 FieldValue 객체 생성 (deprecated - TrackerItemBase._create_field_value 사용)"""
        return TrackerItemBase()._create_field_value(field_info, value) or TextFieldValue(field_id=0, field_name="")

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

        # TrackerItemBase 객체 생성
        item = TrackerItemBase()
        item.name = str(row.get("upload_name", ""))

        # 모든 selected_mapping에 대해 처리
        for df_col, schema_field in self.state.selected_mapping.items():
            # tracker_item_field 찾기
            matched = self.state.schema_df[self.state.schema_df["field_name"]
                                           == schema_field]
            if matched.empty:
                continue

            field_row = matched.iloc[0]
            tracker_field = field_row["tracker_item_field"]
            field_id = field_row.get("field_id")
            field_type = field_row.get("field_type")
            multiple_values = field_row.get("multiple_values", False)

            if not tracker_field:
                continue

            # 필드값 결정
            field_value = None
            if df_col in self.state.selected_option_mapping:
                # 옵션 필드: resolved 값 사용
                resolved_col = f"{df_col}__resolved"
                if resolved_col in row.index and row[resolved_col] is not None:
                    field_value = row[resolved_col]
            else:
                # 비옵션 필드: 원래 값 사용
                if df_col in row.index and row[df_col] is not None:
                    field_value = row[df_col]

            if field_value is None:
                continue

                # TrackerItemBase.set_field_value를 사용해서 값 설정
            field_info = {
                'field_id': field_id,
                'field_type': field_type,
                'field_name': schema_field,
                'multiple_values': multiple_values,
                'reference_type': field_row.get('reference_type'),
                'value_model': field_row.get('value_model'),
            }
            item.set_field_value(tracker_field, field_value, field_info)

        # TableField 처리 (기존 방식 유지)
        custom_fields = []
        if self.state.table_field_mapping:
            # {table_field_name: {table_field_id, columns: [...]}}
            table_fields_by_name = {}

            # TableField의 기본 정보 수집
            for _, tf_row in self.state.schema_df[self.state.schema_df.get("is_table_field", False).fillna(False)].iterrows():
                tf_name = tf_row["field_name"]
                tf_id = tf_row["field_id"]
                tf_columns = tf_row.get("table_columns", [])

                table_fields_by_name[tf_name] = {
                    "field_id": tf_id,
                    "columns": tf_columns,
                }

            # 테이블 행 구성
            tables_data = {}  # {table_field_name: [row1, row2, ...]}

            for df_col, tf_info in self.state.table_field_mapping.items():
                tf_name = tf_info["table_field_name"]
                col_name = tf_info["column_name"]
                col_def = tf_info["column_info"]

                if tf_name not in tables_data:
                    tables_data[tf_name] = []

                # 현재 행에서 값 가져오기
                field_value = None
                if df_col in row.index and row[df_col] is not None:
                    field_value = row[df_col]

                # 테이블이 비어있으면 첫 번째 행 생성
                if not tables_data[tf_name]:
                    tables_data[tf_name].append({})

                # 첫 번째 행(현재 row에 해당)에 값 추가
                col_id = col_def.get("id")
                col_value_model = col_def.get("valueModel", "TextFieldValue")

                tables_data[tf_name][0][col_name] = {
                    "fieldId": col_id,
                    "name": col_name,
                    "value": field_value,
                    "type": col_value_model,
                }

            # customFields에 TableField 추가
            for tf_name, table_rows in tables_data.items():
                if tf_name in table_fields_by_name:
                    tf_info = table_fields_by_name[tf_name]

                    # 테이블 행을 values 형식으로 변환 (배열의 배열)
                    values = []
                    for row_data in table_rows:
                        row_fields = list(row_data.values())
                        if any(v["value"] is not None for v in row_fields):
                            values.append(row_fields)

                    if values:
                        custom_fields.append(TableFieldValue(
                            field_id=tf_info["field_id"],
                            field_name=tf_name,
                            values=values,
                        ))

        # TrackerItemBase.to_dict()를 사용해서 payload 생성 (TrackerItemCreate처럼 불필요한 필드 제거)
        payload = item.create_new_item_payload()

        # TableField가 있으면 customFields에 추가
        if custom_fields:
            existing_custom_fields = payload.get("customFields", [])
            payload["customFields"] = existing_custom_fields + custom_fields
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
                    print(
                        f"✓ Row {row['upload_name']} 업로드 성공: 생성된 아이템 ID={result['id']}")

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
            with open(out / "schema.json", "w", encoding="utf-8") as f:
                json.dump(self.state.schema, f, ensure_ascii=False, indent=2)

        if self.state.option_maps is not None:
            with open(out / "option_maps.json", "w", encoding="utf-8") as f:
                json.dump(self.state.option_maps, f,
                          ensure_ascii=False, indent=2)

        if self.state.upload_result is not None:
            for key in ["success_df", "failed_df", "unresolved_df"]:
                df = self.state.upload_result.get(key)
                if isinstance(df, pd.DataFrame) and not df.empty:
                    df.to_csv(out / f"{key}.csv", index=False)

            with open(out / "created_map.json", "w", encoding="utf-8") as f:
                json.dump(self.state.upload_result.get(
                    "created_map", {}), f, ensure_ascii=False, indent=2)
