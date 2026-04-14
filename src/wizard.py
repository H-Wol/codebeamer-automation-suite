from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd

from .codebeamer_client import CodebeamerClient
from .excel_processor import ExcelHierarchyProcessor
from .mapping_service import MappingService
from .models import DomainModel
from .models import FieldValueType
from .models import OptionMapKind
from .models import ReferenceType
from .models import TableFieldValue
from .models import TrackerItemBase
from .models import UploadStatus
from .models import UserInfo
from .models import UserLookupStatus
from .models import WizardState


UserLookupCacheEntry = tuple[dict[str, Any] | None, dict[str, Any] | None, str, str | None]


class CodebeamerUploadWizard:
    def __init__(
        self,
        client: CodebeamerClient,
        processor: ExcelHierarchyProcessor,
        mapper: MappingService,
        logger=None,
    ):
        """업로드 전체 흐름을 묶어 실행하는 조정 객체를 만든다."""
        self.client = client
        self.processor = processor
        self.mapper = mapper
        self.logger = logger
        self.state = WizardState()

    def load_projects(self) -> list[dict]:
        """사용자가 선택할 프로젝트 목록을 가져온다."""
        return self.client.get_projects()

    def select_project(self, project_id: int) -> None:
        """작업 대상을 프로젝트 단위로 바꾸고 관련 캐시를 초기화한다."""
        if self.state.project_id != project_id:
            self.state.user_lookup_cache.clear()
        self.state.project_id = project_id

    def load_trackers(self) -> list[dict]:
        """현재 프로젝트 안에서 선택 가능한 트래커 목록을 가져온다."""
        if self.state.project_id is None:
            raise ValueError("project_id must be selected first.")
        return self.client.get_trackers(self.state.project_id)

    def load_tracker_items(self, tracker_id: int) -> list[dict]:
        """트래커 안의 아이템 목록을 가져온다."""
        return self.client.get_tracker_items(tracker_id)

    def load_root_items(self, tracker_id: int) -> list[dict]:
        """트래커 루트 바로 아래의 아이템만 가져온다."""
        return self.client.get_tracker_children(tracker_id)

    def select_tracker(self, tracker_id: int) -> None:
        """업로드 대상 트래커를 저장한다."""
        self.state.tracker_id = tracker_id

    def read_excel(self, file_path: str, sheet_name: str | int = 0, list_cols: list[str] | None = None) -> None:
        """Excel 파일을 읽어 업로드에 필요한 중간 DataFrame들을 모두 만든다."""
        if list_cols is None:
            list_cols = []

        self.state.list_cols = list_cols
        self.state.raw_df = self.processor.read_excel(file_path=file_path, sheet_name=sheet_name)
        self.state.merged_df = self.processor.merge_multiline_records(self.state.raw_df, list_cols=list_cols)
        self.state.hierarchy_df = self.processor.add_hierarchy_by_indent(self.state.merged_df)
        self.state.upload_df = self.processor.build_upload_df(self.state.hierarchy_df, list_cols=list_cols)

    def load_schema_and_compare(self, selected_mapping: dict[str, str]) -> pd.DataFrame:
        """트래커 schema를 읽고 업로드 컬럼과 비교 결과를 만든다."""
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
        """`TableFieldName.ColumnName` 형태의 Excel 컬럼을 자동으로 감지한다."""
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

    @staticmethod
    def _normalize_lookup_text(value: Any) -> str:
        """lookup에 쓸 값을 공백 없는 문자열로 정리한다."""
        if value is None:
            return ""
        return str(value).strip()

    @staticmethod
    def _http_status_code(exc: Exception) -> int | None:
        """예외 안에 담긴 HTTP 상태 코드를 안전하게 꺼낸다."""
        response = getattr(exc, "response", None)
        return getattr(response, "status_code", None)

    def _user_lookup_cache_key(self, value: Any) -> tuple[int | None, str]:
        """현재 프로젝트 기준으로 사용자 lookup 캐시 키를 만든다."""
        return (self.state.project_id, self._normalize_lookup_text(value).casefold())

    @classmethod
    def _user_lookup_aliases(cls, user_info: dict[str, Any] | None) -> set[str]:
        """한 사용자를 다시 찾기 쉬우도록 ID 문자열만 별칭으로 만든다."""
        if not user_info:
            return set()

        return {
            normalized.casefold()
            for value in [user_info.get("id")]
            if (normalized := cls._normalize_lookup_text(value))
        }

    def _cache_user_lookup_entry(
        self,
        lookup_text: str,
        entry: UserLookupCacheEntry,
    ) -> UserLookupCacheEntry:
        """사용자 lookup 결과를 원래 입력값과 별칭 키 모두에 저장한다."""
        cache_key = self._user_lookup_cache_key(lookup_text)
        self.state.user_lookup_cache[cache_key] = entry

        resolved, user_info, _, _ = entry
        if resolved is not None and user_info is not None:
            for alias in self._user_lookup_aliases(user_info):
                self.state.user_lookup_cache[(self.state.project_id, alias)] = entry

        return entry

    @classmethod
    def _parse_user_id(cls, raw_value: Any) -> int:
        """사용자 lookup 입력을 정수 ID로 해석한다."""
        lookup_text = cls._normalize_lookup_text(raw_value)
        if not lookup_text:
            raise ValueError("user id is empty")
        return int(lookup_text)

    @staticmethod
    def _to_user_reference(candidate: UserInfo) -> dict[str, Any]:
        """사용자 상세 객체를 업로드용 사용자 참조 dict로 바꾼다."""
        reference = candidate.to_reference()
        reference.type = ReferenceType.USER.value
        return reference.to_dict()

    def _lookup_user_reference(
        self,
        raw_value: Any,
    ) -> UserLookupCacheEntry:
        """사용자 ID로 사용자를 찾아 reference와 상세 정보를 함께 돌려준다."""
        lookup_text = self._normalize_lookup_text(raw_value)
        cache_key = self._user_lookup_cache_key(lookup_text)
        if cache_key in self.state.user_lookup_cache:
            return self.state.user_lookup_cache[cache_key]

        try:
            user_id = self._parse_user_id(raw_value)

            try:
                direct_match = self.client.get_user(user_id)
            except Exception as exc:
                if self._http_status_code(exc) != 404:
                    raise
                direct_match = None

            if direct_match is not None:
                resolved = self._to_user_reference(direct_match)
                user_info = direct_match.to_dict()
                return self._cache_user_lookup_entry(
                    lookup_text,
                    (resolved, user_info, UserLookupStatus.RESOLVED.value, None),
                )

            return self._cache_user_lookup_entry(
                lookup_text,
                (None, None, UserLookupStatus.USER_NOT_FOUND.value, None),
            )
        except Exception as exc:
            error_message = ""
            if hasattr(exc, "response") and exc.response is not None:
                try:
                    error_message = str(exc.response.json())
                except Exception:
                    error_message = str(exc)
            else:
                error_message = str(exc)
            return self._cache_user_lookup_entry(
                lookup_text,
                (None, None, UserLookupStatus.USER_LOOKUP_FAILED.value, error_message),
            )

    def _resolve_user_reference_value(
        self,
        raw_value: Any,
        *,
        multiple_values: bool,
    ) -> tuple[Any, Any, str | None, str | None]:
        """단일 값 또는 목록 값을 사용자 reference 형태로 해석한다."""
        if multiple_values and isinstance(raw_value, list):
            resolved_values = []
            user_infos = []
            for item in raw_value:
                if item is None or self._normalize_lookup_text(item) == "":
                    continue
                resolved, user_info, status, error = self._lookup_user_reference(item)
                if resolved is None:
                    return None, None, status, error
                resolved_values.append(resolved)
                user_infos.append(user_info)
            return (
                resolved_values if resolved_values else None,
                user_infos if user_infos else None,
                UserLookupStatus.RESOLVED.value,
                None,
            )

        resolved, user_info, status, error = self._lookup_user_reference(raw_value)
        return resolved, user_info, status, error

    def _resolve_user_reference_fields(
        self,
        upload_df: pd.DataFrame,
        option_mapping: dict[str, str],
        option_maps: dict[str, dict],
    ) -> pd.DataFrame:
        """UserReference 필드의 각 행 값을 미리 찾아 `__resolved` 컬럼에 넣는다."""
        work = upload_df.copy()

        for df_col, schema_field in option_mapping.items():
            option_info = option_maps.get(schema_field, {})
            if option_info.get("kind") != OptionMapKind.USER_LOOKUP.value:
                continue

            resolved_values = []
            user_infos = []
            statuses = []
            errors = []
            multiple_values = option_info.get("multiple_values", False)

            for _, row in work.iterrows():
                raw_value = row[df_col]
                if raw_value is None or (isinstance(raw_value, str) and raw_value.strip() == ""):
                    resolved_values.append(None)
                    user_infos.append(None)
                    statuses.append(None)
                    errors.append(None)
                    continue

                resolved, user_info, status, error = self._resolve_user_reference_value(
                    raw_value,
                    multiple_values=multiple_values,
                )
                resolved_values.append(resolved)
                user_infos.append(user_info)
                statuses.append(status)
                errors.append(error)

            work[f"{df_col}__resolved"] = resolved_values
            work[f"{df_col}__user_info"] = user_infos
            work[f"{df_col}__lookup_status"] = statuses
            work[f"{df_col}__lookup_error"] = errors

        return work

    def process_option_mapping(
        self,
        selected_mapping: dict[str, str],
        selected_option_mapping: dict[str, str] | None = None,
    ) -> tuple[dict[str, str], pd.DataFrame]:
        """옵션/참조형 필드를 찾아 lookup과 검증을 한 번에 수행한다."""
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

        lookup_ready_df = self._resolve_user_reference_fields(
            upload_df=self.state.upload_df,
            option_mapping=selected_option_mapping,
            option_maps=option_maps,
        )

        option_check_df = self.mapper.check_option_alignment(
            upload_df=lookup_ready_df,
            option_mapping=selected_option_mapping,
            option_maps=option_maps,
        )
        self.state.option_check_df = option_check_df

        self.state.converted_upload_df = self.mapper.apply_option_resolution(
            upload_df=lookup_ready_df,
            option_mapping=selected_option_mapping,
            option_maps=option_maps,
        )

        return selected_option_mapping, option_check_df

    def _serialize_payload_value(self, value: Any) -> Any:
        """payload 안의 모델 객체를 재귀적으로 일반 자료형으로 바꾼다."""
        if isinstance(value, DomainModel):
            return value.to_dict()
        if isinstance(value, list):
            return [self._serialize_payload_value(item) for item in value]
        if isinstance(value, dict):
            return {key: self._serialize_payload_value(item) for key, item in value.items()}
        return value

    @staticmethod
    def _has_row_value(row: pd.Series, column_name: str) -> bool:
        """행 안에 실제로 업로드할 값이 들어 있는지 확인한다."""
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

    @staticmethod
    def _schema_field_info(field_row: pd.Series, schema_field: str) -> dict[str, Any]:
        """schema 비교 행에서 payload 생성에 필요한 정보만 골라낸다."""
        return {
            "field_id": field_row.get("field_id"),
            "field_type": field_row.get("field_type"),
            "field_name": schema_field,
            "multiple_values": field_row.get("multiple_values", False),
            "reference_type": field_row.get("reference_type"),
            "value_model": field_row.get("value_model"),
            "resolved_field_kind": field_row.get("resolved_field_kind"),
            "resolution_strategy": field_row.get("resolution_strategy"),
            "is_supported": field_row.get("is_supported", True),
            "unsupported_reason": field_row.get("unsupported_reason"),
            "requires_lookup": field_row.get("requires_lookup", False),
            "lookup_target_kind": field_row.get("lookup_target_kind"),
            "preconstruction_kind": field_row.get("preconstruction_kind"),
            "preconstruction_detail": field_row.get("preconstruction_detail"),
            "payload_target_kind": field_row.get("payload_target_kind"),
            "tracker_item_field": field_row.get("tracker_item_field"),
        }

    @staticmethod
    def _raise_payload_error(
        code: str,
        *,
        schema_field: str,
        row_id: int,
        df_col: str,
        detail: str,
    ) -> None:
        """payload 생성 중 발생한 구조화된 오류를 같은 형식으로 만든다."""
        raise ValueError(
            f"[{code}] field='{schema_field}' df_column='{df_col}' _row_id={row_id} {detail}"
        )

    def _ensure_field_ready_for_payload(
        self,
        *,
        field_row: pd.Series,
        schema_field: str,
        df_col: str,
        row_id: int,
    ) -> None:
        """현재 field가 업로드 가능한 상태인지 payload 생성 전에 점검한다."""
        if not field_row.get("is_supported", True):
            self._raise_payload_error(
                "FIELD_UNSUPPORTED",
                schema_field=schema_field,
                df_col=df_col,
                row_id=row_id,
                detail=(
                    f"reason={field_row.get('unsupported_reason')!r} "
                    f"strategy={field_row.get('resolution_strategy')!r} "
                    f"payload_target={field_row.get('payload_target_kind')!r} "
                    f"preconstruction={field_row.get('preconstruction_kind')!r}"
                ),
            )

        if field_row.get("requires_lookup") and df_col not in self.state.selected_option_mapping:
            self._raise_payload_error(
                "LOOKUP_REQUIRED",
                schema_field=schema_field,
                df_col=df_col,
                row_id=row_id,
                detail=(
                    f"lookup_target={field_row.get('lookup_target_kind')!r} "
                    f"preconstruction={field_row.get('preconstruction_kind')!r} "
                    f"detail={field_row.get('preconstruction_detail')!r}"
                ),
            )

    def _resolve_option_field_value(self, row: pd.Series, row_id: int, df_col: str, schema_field: str) -> Any:
        """옵션 또는 참조형 필드의 실제 업로드 값을 `__resolved` 기준으로 꺼낸다."""
        option_info = (self.state.option_maps or {}).get(schema_field, {})
        resolved_col = f"{df_col}__resolved"
        status_col = f"{df_col}__lookup_status"
        error_col = f"{df_col}__lookup_error"

        if not option_info.get("is_supported", True) or option_info.get("kind") == OptionMapKind.UNSUPPORTED.value:
            self._raise_payload_error(
                "FIELD_UNSUPPORTED",
                schema_field=schema_field,
                df_col=df_col,
                row_id=row_id,
                detail=(
                    f"reason={option_info.get('unsupported_reason')!r} "
                    f"strategy={option_info.get('resolution_strategy')!r} "
                    f"preconstruction={option_info.get('preconstruction_kind')!r}"
                ),
            )

        if resolved_col in row.index and row[resolved_col] is not None:
            return row[resolved_col]

        if not self._has_row_value(row, df_col):
            return None

        if option_info.get("kind") == OptionMapKind.USER_LOOKUP.value:
            lookup_status = (
                row[status_col]
                if status_col in row.index
                else UserLookupStatus.USER_LOOKUP_NOT_RUN.value
            )
            lookup_error = row[error_col] if error_col in row.index else None
            detail = (
                f"value={row[df_col]!r} lookup_status={lookup_status!r} "
                f"preconstruction={option_info.get('preconstruction_kind')!r}"
            )
            if lookup_error:
                detail = f"{detail} error={lookup_error!r}"
            self._raise_payload_error(
                "LOOKUP_REQUIRED",
                schema_field=schema_field,
                df_col=df_col,
                row_id=row_id,
                detail=detail,
            )

        if option_info.get("kind") == OptionMapKind.REFERENCE_LOOKUP.value:
            self._raise_payload_error(
                "LOOKUP_REQUIRED",
                schema_field=schema_field,
                df_col=df_col,
                row_id=row_id,
                detail=(
                    f"reference_type={option_info.get('reference_type')!r} "
                    f"lookup_target={option_info.get('lookup_target_kind')!r} "
                    f"preconstruction={option_info.get('preconstruction_kind')!r} "
                    f"detail={option_info.get('preconstruction_detail')!r} "
                    f"reason={option_info.get('unsupported_reason')!r}"
                ),
            )

        self._raise_payload_error(
            "OPTION_RESOLUTION_FAILED",
            schema_field=schema_field,
            df_col=df_col,
            row_id=row_id,
            detail=f"value={row[df_col]!r}",
        )

    def _build_table_custom_fields(self, row: pd.Series) -> list[TableFieldValue]:
        """현재 행에서 TableField 값들을 모아 custom field payload로 만든다."""
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
                "type": col_def.get("valueModel", FieldValueType.TEXT.value),
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
        """한 행이 실제로 어떤 payload로 업로드되는지 미리 만들어 보여준다."""
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

            if not tracker_field:
                continue

            field_value = None
            if df_col in self.state.selected_option_mapping:
                if not self._has_row_value(row, df_col):
                    continue
                self._ensure_field_ready_for_payload(
                    field_row=field_row,
                    schema_field=schema_field,
                    df_col=df_col,
                    row_id=row_id,
                )
                field_value = self._resolve_option_field_value(row, row_id, df_col, schema_field)
            elif self._has_row_value(row, df_col):
                self._ensure_field_ready_for_payload(
                    field_row=field_row,
                    schema_field=schema_field,
                    df_col=df_col,
                    row_id=row_id,
                )
                field_value = row[df_col]

            if field_value is None:
                continue

            field_info = self._schema_field_info(field_row, schema_field)
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
        """부모-자식 순서를 지키며 업로드를 실행하고 결과를 모아 돌려준다."""
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
                        "status": UploadStatus.SUCCESS.value,
                    })
                    print(f"Row {row['upload_name']} uploaded successfully: item_id={result['id']}")

                except Exception as exc:
                    error_message = ""
                    if hasattr(exc, "response") and exc.response is not None:
                        try:
                            error_message = str(exc.response.json())
                        except Exception:
                            error_message = str(exc)
                    else:
                        error_message = str(exc)

                    failed_logs.append({
                        "_row_id": row_id,
                        "parent_row_id": row["parent_row_id"],
                        "upload_name": row["upload_name"],
                        "error": error_message,
                        "status": UploadStatus.FAILED.value,
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
        """현재 세션의 DataFrame, schema, 결과를 파일로 저장한다."""
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
                df.to_csv(out / name, index=False)

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
