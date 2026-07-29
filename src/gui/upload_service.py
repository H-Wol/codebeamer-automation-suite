from __future__ import annotations

from pathlib import Path
import time
from typing import Any

import pandas as pd

from src.codebeamer_client import CodebeamerClient
from src.excel_reader import ExcelReader
from src.hierarchy_processor import HierarchyProcessor
from src.mapping_service import MappingService
from src.models import OptionMapKind
from src.models import PayloadStatus
from src.models import TrackerItemResolutionMode
from src.upload_pipeline import load_tracker_schema_df
from src.upload_pipeline import prepare_upload_dataframe
from src.upload_pipeline import run_validation_pipeline
from src.upload_pipeline import suggest_mapping_from_headers
from src.upload_policy import BLOCKING_OPTION_STATUSES
from src.upload_policy import DEFAULT_TRACKER_ITEM_ID_REGEX
from src.upload_policy import UPLOAD_MODE_CREATE as GUI_UPLOAD_MODE_CREATE
from src.upload_policy import UPLOAD_MODE_UPDATE as GUI_UPLOAD_MODE_UPDATE
from src.upload_policy import UPLOAD_MODE_UPSERT as GUI_UPLOAD_MODE_UPSERT
from src.upload_policy import USER_LOOKUP_FAILURE_SUFFIXES
from src.upload_policy import default_operation_scope
from src.upload_policy import normalize_operation_scope
from src.upload_policy import normalize_upload_mode as normalize_gui_upload_mode
from src.upload_policy import scope_applies_to_upload_mode
from src.upload_policy import upload_mode_action_label as gui_upload_mode_action_label
from src.upload_policy import upload_mode_allows_root_items as gui_upload_mode_allows_root_items
from src.upload_policy import upload_mode_supports_update as gui_upload_mode_supports_update
from src.wizard import CodebeamerUploadWizard

from .service_core import GuiExcelService
from .service_core import PreviewData
from .service_core import _build_gui_client
from .service_core import gui_display_text
from .root_item_service import ROOT_ASSIGNMENT_MODE_FILE_SOURCE
from .root_item_service import ROOT_ASSIGNMENT_MODE_FIXED_VALUE
from .root_item_service import ROOT_ITEM_MODE_FILE
from .root_item_service import ROOT_ITEM_MODE_GROUP_BY_COLUMN
from .root_item_service import ROOT_SOURCE_GROUP_VALUE
from .root_item_service import RootItemService
from .tracker_config import TrackerConfigurationService
from .upload_context import BatchUploadJob
from .upload_context import DefaultValueCandidate
from .upload_context import MappingContext
from .upload_context import RootFieldCandidate
from .upload_context import RootItemPreviewContext
from .upload_context import RootItemUploadSpec
from .upload_context import RootSourceOption
from .upload_context import TrackerItemFieldCandidate
from .upload_context import ValidationContext
from .validation_presenter import ValidationPresenter
GUI_EXCLUDED_MAPPING_COLUMNS = {
    "id",
    "parent",
    "parent_row_id",
    "upload_name",
    "depth",
    "_row_id",
    "_summary_indent",
    "_start_excel_row",
    "_end_excel_row",
    "_excel_row",
}
GUI_EXCLUDED_TARGET_FIELDS = {"id", "parent"}
GUI_VALUE_KIND_STATIC_OPTIONS = "static_options"
GUI_VALUE_KIND_BOOL = "bool"
GUI_VALUE_KIND_SCALAR = "scalar"
class GuiUploadPipelineService:
    """GUI 단계가 재사용할 업로드 파이프라인 래퍼다."""

    def __init__(
        self,
        logger=None,
        *,
        client_factory=CodebeamerClient,
        excel_service: GuiExcelService | None = None,
        reader_cls=ExcelReader,
    ) -> None:
        """필요한 의존성과 상태를 초기화한다."""
        self.logger = logger
        self.mapper = MappingService(logger=logger)
        self.client_factory = client_factory
        self.reader_cls = reader_cls
        self.excel_service = excel_service or GuiExcelService(logger=logger, reader_cls=reader_cls)
        self.tracker_configuration = TrackerConfigurationService()
        self.validation_presenter = ValidationPresenter()
        self.root_items = RootItemService(
            mapper=self.mapper,
            reader_cls=reader_cls,
            logger=logger,
            is_schema_field_excluded=self._is_gui_excluded_schema_field,
        )

    @classmethod
    def _normalize_mapping_modes(
        cls,
        selected_mapping: dict[str, str],
        selected_mapping_modes: dict[str, Any] | None,
        *,
        upload_mode: str | None,
    ) -> dict[str, dict[str, bool]]:
        """`normalize_mapping_modes` 값을 정규화한다."""
        normalized_modes: dict[str, dict[str, bool]] = {}
        for df_column in selected_mapping.keys():
            normalized_column = str(df_column).strip()
            if not normalized_column:
                continue
            normalized_modes[normalized_column] = normalize_operation_scope(
                (selected_mapping_modes or {}).get(normalized_column),
                upload_mode=upload_mode,
            )
        return normalized_modes

    @classmethod
    def _normalize_default_value_modes(
        cls,
        selected_default_values: dict[str, str],
        selected_default_value_modes: dict[str, Any] | None,
        *,
        upload_mode: str | None,
    ) -> dict[str, dict[str, bool]]:
        """`normalize_default_value_modes` 값을 정규화한다."""
        normalized_modes: dict[str, dict[str, bool]] = {}
        default_scope = default_operation_scope(upload_mode)
        for schema_field in selected_default_values.keys():
            normalized_field = str(schema_field).strip()
            if not normalized_field:
                continue
            raw_scope = (selected_default_value_modes or {}).get(normalized_field)
            is_enabled = scope_applies_to_upload_mode(raw_scope, upload_mode=upload_mode)
            normalized_modes[normalized_field] = dict(default_scope) if is_enabled else {"create": False, "update": False}
        return normalized_modes

    def create_wizard(self, settings) -> CodebeamerUploadWizard:
        """`create_wizard` 화면을 구성한다."""
        client = _build_gui_client(settings, self.client_factory, self.logger)
        reader = self.reader_cls(
            header_row=settings.excel_header_row,
            summary_col=settings.summary_column,
            logger=self.logger,
        )
        processor = HierarchyProcessor(
            header_row=settings.excel_header_row,
            summary_col=settings.summary_column,
            logger=self.logger,
        )
        wizard = CodebeamerUploadWizard(
            client=client,
            processor=processor,
            mapper=self.mapper,
            reader=reader,
            logger=self.logger,
        )
        wizard.state.upload_mode = normalize_gui_upload_mode(getattr(settings, "upload_mode", None))
        return wizard

    @staticmethod
    def _is_gui_excluded_schema_field(row: pd.Series | dict[str, Any]) -> bool:
        """`is_gui_excluded_schema_field` 관련 처리를 수행한다."""
        field_name = str((row.get("field_name") if isinstance(row, dict) else row.get("field_name")) or "").strip().lower()
        tracker_item_field = str(
            (row.get("tracker_item_field") if isinstance(row, dict) else row.get("tracker_item_field")) or ""
        ).strip().lower()
        return field_name in GUI_EXCLUDED_TARGET_FIELDS or tracker_item_field in GUI_EXCLUDED_TARGET_FIELDS

    @staticmethod
    def _gui_upload_columns(upload_df: pd.DataFrame) -> list[str]:
        """`gui_upload_columns` 관련 처리를 수행한다."""
        columns: list[str] = []
        for column in upload_df.columns:
            if column in GUI_EXCLUDED_MAPPING_COLUMNS:
                continue
            if str(column).startswith("_"):
                continue
            columns.append(str(column))
        return columns

    @staticmethod
    def _gui_visible_comparison_df(comparison_df: pd.DataFrame) -> pd.DataFrame:
        """`gui_visible_comparison_df` 관련 처리를 수행한다."""
        if comparison_df is None or comparison_df.empty:
            return comparison_df
        work = comparison_df.copy()
        if "df_column" not in work.columns:
            return work
        mask = ~work["df_column"].astype(str).isin(GUI_EXCLUDED_MAPPING_COLUMNS)
        mask &= ~work["df_column"].astype(str).str.startswith("_")
        return work[mask].reset_index(drop=True)

    def _build_default_value_candidates(
        self,
        schema_df: pd.DataFrame,
    ) -> list[DefaultValueCandidate]:
        """`build_default_value_candidates` 결과를 구성한다."""
        if schema_df.empty:
            return []

        option_maps = self.mapper.build_option_maps_from_schema(schema_df)
        candidates: list[DefaultValueCandidate] = []
        for _, row in schema_df.iterrows():
            schema_field = str(row.get("field_name") or "").strip()
            if not schema_field:
                continue
            if bool(row.get("is_table_field", False)):
                continue
            if not bool(row.get("is_supported", True)):
                continue

            value_kind = ""
            options: list[str] = []
            allows_custom_value = False

            if bool(row.get("is_option_like", False)):
                option_info = option_maps.get(schema_field, {})
                if option_info.get("kind") == OptionMapKind.STATIC_OPTIONS.value:
                    value_kind = GUI_VALUE_KIND_STATIC_OPTIONS
                    options = [
                        str(option.get("name")).strip()
                        for option in option_info.get("options") or []
                        if str(option.get("name") or "").strip()
                    ]
                    if not options:
                        continue
                elif option_info.get("kind") in {
                    OptionMapKind.MEMBER_LOOKUP.value,
                    OptionMapKind.TRACKER_ITEM_DIRECT.value,
                    OptionMapKind.USER_LOOKUP.value,
                }:
                    value_kind = GUI_VALUE_KIND_SCALAR
                    allows_custom_value = True
                else:
                    continue
            else:
                field_type = str(row.get("field_type") or "").strip()
                if field_type == "BoolField":
                    value_kind = GUI_VALUE_KIND_BOOL
                    options = ["true", "false"]
                else:
                    value_kind = GUI_VALUE_KIND_SCALAR
                    allows_custom_value = True

            candidates.append(DefaultValueCandidate(
                schema_field=schema_field,
                field_type=str(row.get("field_type") or ""),
                value_kind=value_kind,
                options=options,
                mandatory=bool(row.get("mandatory", False)),
                allows_custom_value=allows_custom_value,
            ))
        return candidates

    def _enrich_schema_df_with_tracker_configuration(
        self,
        schema_df: pd.DataFrame,
        tracker_configuration: Any,
    ) -> pd.DataFrame:
        """TRACKER configuration 정보를 schema field에 연결한다."""
        return self.tracker_configuration.enrich_schema(schema_df, tracker_configuration)

    def _normalize_tracker_item_settings(
        self,
        schema_df: pd.DataFrame,
        selected_mapping: dict[str, str],
        tracker_item_settings: dict[str, dict[str, Any]] | None,
    ) -> tuple[list[TrackerItemFieldCandidate], dict[str, dict[str, Any]]]:
        """필드별 tracker item lookup 설정을 configuration 계약에 맞춰 정규화한다."""
        return self.tracker_configuration.normalize_settings(
            schema_df,
            selected_mapping,
            tracker_item_settings,
        )

    def build_root_item_preview_context(
        self,
        mapping_context: MappingContext,
        root_item_config: dict[str, Any] | None = None,
    ) -> RootItemPreviewContext:
        """루트 항목 설정을 정규화하고 미리보기 결과를 구성한다."""
        return self.root_items.build_root_item_preview_context(
            mapping_context,
            root_item_config,
        )

    def _default_root_item_config(self, schema_df: pd.DataFrame) -> dict[str, Any]:
        """매핑 단계에서 사용할 기본 루트 항목 설정을 구성한다."""
        return self.root_items._default_root_item_config(schema_df)

    @staticmethod
    def _normalize_file_paths(file_state: dict[str, Any]) -> list[str]:
        """`normalize_file_paths` 값을 정규화한다."""
        raw_paths = file_state.get("file_paths")
        normalized: list[str] = []

        if isinstance(raw_paths, (list, tuple)):
            for raw_path in raw_paths:
                text = str(raw_path or "").strip()
                if text:
                    normalized.append(text)

        if normalized:
            return normalized

        single_path = str(file_state.get("file_path") or "").strip()
        return [single_path] if single_path else []

    @classmethod
    def _representative_file_path(cls, file_state: dict[str, Any]) -> str:
        """`representative_file_path` 관련 처리를 수행한다."""
        file_paths = cls._normalize_file_paths(file_state)
        if not file_paths:
            return ""

        preview_file_path = str(file_state.get("preview_file_path") or file_state.get("file_path") or "").strip()
        if preview_file_path and preview_file_path in file_paths:
            return preview_file_path
        return file_paths[0]

    @staticmethod
    def _cached_preview_data(
        file_state: dict[str, Any],
        *,
        file_path: str,
        sheet_name: str,
        header_row: int,
        summary_column: str,
    ) -> PreviewData | None:
        """`cached_preview_data` 관련 처리를 수행한다."""
        preview_data = file_state.get("preview_data")
        if not isinstance(preview_data, PreviewData):
            return None
        if str(preview_data.file_path).strip() != str(file_path).strip():
            return None
        if str(preview_data.sheet_name).strip() != str(sheet_name).strip():
            return None
        if int(preview_data.header_row) != int(header_row):
            return None
        if str(preview_data.summary_column).strip() != str(summary_column).strip():
            return None
        return preview_data

    @staticmethod
    def _preview_raw_df_map(preview_data: PreviewData | None) -> dict[str, pd.DataFrame]:
        """`preview_raw_df_map` 미리보기를 계산한다."""
        if preview_data is None:
            return {}

        raw_df_by_file = getattr(preview_data, "raw_df_by_file", None)
        if isinstance(raw_df_by_file, dict) and raw_df_by_file:
            return {
                str(path).strip(): df
                for path, df in raw_df_by_file.items()
                if str(path).strip() and isinstance(df, pd.DataFrame)
            }

        raw_df = getattr(preview_data, "raw_df", None)
        file_path = str(getattr(preview_data, "file_path", "") or "").strip()
        if file_path and isinstance(raw_df, pd.DataFrame):
            return {file_path: raw_df}
        return {}

    @classmethod
    def _cached_raw_df_for_file(
        cls,
        preview_data: PreviewData | None,
        file_path: str,
    ) -> pd.DataFrame | None:
        """`cached_raw_df_for_file` 관련 처리를 수행한다."""
        return cls._preview_raw_df_map(preview_data).get(str(file_path).strip())

    @staticmethod
    def _visible_headers_from_raw_df(raw_df: pd.DataFrame) -> list[str]:
        """`visible_headers_from_raw_df` 관련 처리를 수행한다."""
        return [
            str(column)
            for column in raw_df.columns
            if not str(column).startswith("_")
        ]

    def _visible_headers_for_file(
        self,
        file_path: str,
        *,
        sheet_name: str,
        header_row: int,
        summary_col: str,
    ) -> list[str]:
        """`visible_headers_for_file` 관련 처리를 수행한다."""
        reader = self.reader_cls(
            header_row=header_row,
            summary_col=summary_col,
            logger=self.logger,
        )
        headers = reader.read_headers(file_path, sheet_name)
        return [header for header in headers if not str(header).startswith("_")]

    def _validate_batch_headers(
        self,
        file_paths: list[str],
        *,
        representative_file_path: str,
        expected_headers: list[str],
        sheet_name: str,
        header_row: int,
        summary_col: str,
        preview_data: PreviewData | None = None,
    ) -> None:
        """`validate_batch_headers` 입력을 검증한다."""
        for file_path in file_paths:
            if file_path == representative_file_path:
                continue

            cached_raw_df = self._cached_raw_df_for_file(preview_data, file_path)
            if cached_raw_df is not None:
                current_headers = self._visible_headers_from_raw_df(cached_raw_df)
            else:
                current_headers = self._visible_headers_for_file(
                    file_path,
                    sheet_name=sheet_name,
                    header_row=header_row,
                    summary_col=summary_col,
                )
            if current_headers != expected_headers:
                raise ValueError(
                    f"'{Path(file_path).name}' 파일의 헤더가 기준 파일과 다릅니다."
                )

    def _count_upload_rows_for_file(
        self,
        file_path: str,
        *,
        sheet_name: str,
        header_row: int,
        summary_col: str,
        list_cols: list[str],
        preview_data: PreviewData | None = None,
    ) -> int:
        """`count_upload_rows_for_file` 건수를 계산한다."""
        cached_raw_df = self._cached_raw_df_for_file(preview_data, file_path)
        if cached_raw_df is not None:
            processor = HierarchyProcessor(
                header_row=header_row,
                summary_col=summary_col,
                logger=self.logger,
            )
            merged_df = processor.merge_multiline_records(cached_raw_df.copy(), list_cols=list_cols)
            return int(len(merged_df.index))

        reader = self.reader_cls(
            header_row=header_row,
            summary_col=summary_col,
            logger=self.logger,
        )
        if hasattr(reader, "count_upload_rows"):
            try:
                return int(reader.count_upload_rows(file_path=file_path, sheet_name=sheet_name))
            except Exception:
                pass

        raw_df = reader.read_excel(file_path=file_path, sheet_name=sheet_name)
        processor = HierarchyProcessor(
            header_row=header_row,
            summary_col=summary_col,
            logger=self.logger,
        )
        merged_df = processor.merge_multiline_records(raw_df, list_cols=list_cols)
        return int(len(merged_df.index))

    def _count_batch_upload_rows(
        self,
        mapping_context: MappingContext,
        *,
        list_cols: list[str],
    ) -> int:
        """`count_batch_upload_rows` 건수를 계산한다."""
        total_rows = 0
        for file_path in mapping_context.file_paths:
            cached_raw_df = self._cached_raw_df_for_file(mapping_context.preview_data, file_path)
            if cached_raw_df is not None:
                processor = HierarchyProcessor(
                    header_row=mapping_context.header_row,
                    summary_col=mapping_context.summary_column,
                    logger=self.logger,
                )
                merged_df = processor.merge_multiline_records(
                    cached_raw_df.copy(),
                    list_cols=list_cols,
                )
                total_rows += int(len(merged_df.index))
                continue

            total_rows += self._count_upload_rows_for_file(
                file_path,
                sheet_name=mapping_context.sheet_name,
                header_row=mapping_context.header_row,
                summary_col=mapping_context.summary_column,
                list_cols=list_cols,
                preview_data=mapping_context.preview_data,
            )
        return total_rows

    def _create_validation_wizard(self, mapping_context: MappingContext) -> CodebeamerUploadWizard:
        """`create_validation_wizard` 관련 처리를 수행한다."""
        base_wizard = mapping_context.wizard
        reader = self.reader_cls(
            header_row=mapping_context.header_row,
            summary_col=mapping_context.summary_column,
            logger=self.logger,
        )
        processor = HierarchyProcessor(
            header_row=mapping_context.header_row,
            summary_col=mapping_context.summary_column,
            logger=self.logger,
        )
        wizard = CodebeamerUploadWizard(
            client=base_wizard.client,
            processor=processor,
            mapper=self.mapper,
            reader=reader,
            logger=self.logger,
        )
        wizard.state.project_id = base_wizard.state.project_id
        wizard.state.tracker_id = base_wizard.state.tracker_id
        wizard.state.upload_mode = normalize_gui_upload_mode(mapping_context.upload_mode)
        wizard.state.schema = base_wizard.state.schema
        wizard.state.schema_df = mapping_context.schema_df
        wizard.state.user_lookup_cache = dict(base_wizard.state.user_lookup_cache)
        wizard.state.member_lookup_cache = dict(base_wizard.state.member_lookup_cache)
        wizard.state.group_lookup_cache = dict(base_wizard.state.group_lookup_cache)
        wizard.state.tracker_role_cache = dict(base_wizard.state.tracker_role_cache)
        wizard.state.tracker_item_lookup_cache = dict(mapping_context.tracker_item_lookup_cache)
        return wizard

    @staticmethod
    def _annotate_source_frame(
        df: pd.DataFrame | None,
        *,
        file_label: str,
        file_path: str,
    ) -> pd.DataFrame:
        """`annotate_source_frame` 관련 처리를 수행한다."""
        if df is None or getattr(df, "empty", True):
            return pd.DataFrame()

        work = df.copy()
        if "source_file" in work.columns:
            work["source_file"] = file_label
        else:
            work.insert(0, "source_file", file_label)
        if "source_file_path" in work.columns:
            work["source_file_path"] = file_path
        else:
            insert_at = 1 if "source_file" in work.columns else 0
            work.insert(insert_at, "source_file_path", file_path)
        return work

    @staticmethod
    def _sync_validation_wizard_caches(
        target_wizard: CodebeamerUploadWizard,
        source_wizard: CodebeamerUploadWizard,
    ) -> None:
        """`sync_validation_wizard_caches` 상태를 동기화한다."""
        target_wizard.state.user_lookup_cache = dict(source_wizard.state.user_lookup_cache)
        target_wizard.state.member_lookup_cache = dict(source_wizard.state.member_lookup_cache)
        target_wizard.state.group_lookup_cache = dict(source_wizard.state.group_lookup_cache)
        target_wizard.state.tracker_role_cache = dict(source_wizard.state.tracker_role_cache)
        target_wizard.state.tracker_item_lookup_cache = dict(source_wizard.state.tracker_item_lookup_cache)

    def _raw_df_for_file(
        self,
        mapping_context: MappingContext,
        file_path: str,
    ) -> pd.DataFrame:
        """`raw_df_for_file` 관련 처리를 수행한다."""
        cached_raw_df = self._cached_raw_df_for_file(mapping_context.preview_data, file_path)
        if cached_raw_df is not None:
            return cached_raw_df.copy()

        reader = self.reader_cls(
            header_row=mapping_context.header_row,
            summary_col=mapping_context.summary_column,
            logger=self.logger,
        )
        return reader.read_excel(
            file_path=file_path,
            sheet_name=mapping_context.sheet_name,
        )

    def _upload_df_for_file(
        self,
        mapping_context: MappingContext,
        *,
        file_path: str,
        list_cols: list[str],
    ) -> pd.DataFrame:
        """`upload_df_for_file` 관련 처리를 수행한다."""
        raw_df = self._raw_df_for_file(mapping_context, file_path)
        processor = HierarchyProcessor(
            header_row=mapping_context.header_row,
            summary_col=mapping_context.summary_column,
            logger=self.logger,
        )
        merged_df = processor.merge_multiline_records(raw_df, list_cols=list_cols)
        hierarchy_df = processor.add_hierarchy_by_indent(merged_df)
        return processor.build_upload_df(hierarchy_df, list_cols=list_cols)

    @classmethod
    def _build_batch_update_duplicate_issue_df(
        cls,
        mapping_context: MappingContext,
        *,
        file_upload_dfs: dict[str, pd.DataFrame],
    ) -> tuple[set[int], pd.DataFrame]:
        """`build_batch_update_duplicate_issue_df` 결과를 구성한다."""
        issue_columns = [
            "severity",
            "category",
            "row_id",
            "row_label",
            "item_name",
            "source_file",
            "source_file_path",
            "column",
            "field",
            "raw_value",
            "message",
            "action",
        ]
        if not gui_upload_mode_supports_update(mapping_context.upload_mode):
            return set(), pd.DataFrame(columns=issue_columns)

        occurrences_by_item_id: dict[int, list[dict[str, str]]] = {}
        for file_path, upload_df in file_upload_dfs.items():
            if upload_df is None or upload_df.empty:
                continue

            id_column_name = CodebeamerUploadWizard._update_item_id_column_name(upload_df)
            if not id_column_name:
                continue

            for _, row in upload_df.iterrows():
                try:
                    item_id = CodebeamerUploadWizard._parse_update_item_id(row.get(id_column_name))
                except ValueError:
                    continue

                item_name = gui_display_text(row.get("upload_name"))
                if not item_name:
                    for fallback_column in ("Summary", "summary", "요약", "name"):
                        if fallback_column in row.index:
                            item_name = gui_display_text(row.get(fallback_column))
                        if item_name:
                            break

                occurrences_by_item_id.setdefault(item_id, []).append({
                    "file_name": Path(file_path).name,
                    "row_label": cls._build_row_label(row),
                    "item_name": item_name,
                })

        duplicate_item_ids = {
            item_id
            for item_id, occurrences in occurrences_by_item_id.items()
            if len(occurrences) > 1
        }
        if not duplicate_item_ids:
            return set(), pd.DataFrame(columns=issue_columns)

        issues: list[dict[str, str]] = []
        for item_id in sorted(duplicate_item_ids):
            occurrences = occurrences_by_item_id[item_id]
            location_texts = []
            for occurrence in occurrences[:5]:
                location = occurrence["file_name"]
                if occurrence["row_label"]:
                    location = f"{location} {occurrence['row_label']}"
                location_texts.append(location)
            remaining_count = len(occurrences) - len(location_texts)
            location_summary = ", ".join(location_texts)
            if remaining_count > 0:
                location_summary = f"{location_summary} 외 {remaining_count}건"

            issues.append({
                "severity": "오류",
                "category": "업데이트",
                "row_id": "",
                "row_label": "",
                "item_name": "",
                "column": "id",
                "field": "id",
                "raw_value": str(item_id),
                "message": f"여러 파일에서 같은 item id가 중복됩니다. 대상 id={item_id} ({location_summary})",
                "action": "한 item id는 배치 전체에서 한 번만 수정되도록 파일을 정리한 뒤 다시 검증하세요.",
            })

        return duplicate_item_ids, pd.DataFrame(issues, columns=issue_columns)

    def _build_upsert_root_item_issue_df(
        self,
        mapping_context: MappingContext,
        *,
        payload_df: pd.DataFrame,
    ) -> pd.DataFrame:
        """`build_upsert_root_item_issue_df` 결과를 구성한다."""
        del mapping_context, payload_df
        return pd.DataFrame(columns=[
            "severity",
            "category",
            "row_id",
            "row_label",
            "item_name",
            "source_file",
            "source_file_path",
            "column",
            "field",
            "raw_value",
            "message",
            "action",
        ])

    def prepare_mapping_context(self, settings, file_state: dict[str, Any]) -> MappingContext:
        """`prepare_mapping_context` 관련 처리를 수행한다."""
        file_paths = self._normalize_file_paths(file_state)
        representative_file_path = self._representative_file_path(file_state)
        if not file_paths or not representative_file_path:
            raise ValueError("Excel 파일을 먼저 선택해야 합니다.")

        wizard = self.create_wizard(settings)
        wizard.select_project(int(settings.default_project_id))
        wizard.select_tracker(int(settings.default_tracker_id))
        wizard.state.upload_mode = normalize_gui_upload_mode(getattr(settings, "upload_mode", None))

        schema, schema_df = load_tracker_schema_df(wizard)
        tracker_configuration = None
        if hasattr(wizard.client, "get_tracker_configuration"):
            try:
                tracker_configuration = wizard.client.get_tracker_configuration(int(settings.default_tracker_id))
            except Exception:
                tracker_configuration = None
        schema_df = self._enrich_schema_df_with_tracker_configuration(schema_df, tracker_configuration)
        mappable_schema_df = schema_df[
            ~schema_df.apply(self._is_gui_excluded_schema_field, axis=1)
        ].reset_index(drop=True)

        target_sheet_name = str(file_state["sheet_name"])
        target_header_row = int(file_state["header_row"])
        target_summary_column = str(file_state["summary_column"])
        preview = self._cached_preview_data(
            file_state,
            file_path=representative_file_path,
            sheet_name=target_sheet_name,
            header_row=target_header_row,
            summary_column=target_summary_column,
        )
        if preview is None:
            preview = self.excel_service.load_preview(
                representative_file_path,
                file_paths=file_paths,
                sheet_name=target_sheet_name,
                header_row=target_header_row,
                summary_column=target_summary_column,
            )
        headers = preview.headers
        self._validate_batch_headers(
            file_paths,
            representative_file_path=representative_file_path,
            expected_headers=headers,
            sheet_name=target_sheet_name,
            header_row=target_header_row,
            summary_col=target_summary_column,
            preview_data=preview,
        )
        raw_mapping = suggest_mapping_from_headers(headers, mappable_schema_df)

        _, list_cols = prepare_upload_dataframe(
            wizard,
            file_path=representative_file_path,
            sheet_name=target_sheet_name,
            header_row=target_header_row,
            summary_col=target_summary_column,
            selected_mapping=raw_mapping,
            schema=schema,
            schema_df=mappable_schema_df,
            raw_df=preview.raw_df,
        )

        upload_columns = self._gui_upload_columns(wizard.state.upload_df)
        selected_mapping = {
            column: schema_field
            for column, schema_field in raw_mapping.items()
            if column in upload_columns
        }
        selected_mapping_modes = self._normalize_mapping_modes(
            selected_mapping,
            None,
            upload_mode=wizard.state.upload_mode,
        )
        default_value_candidates = self._build_default_value_candidates(mappable_schema_df)
        selected_default_value_modes = self._normalize_default_value_modes(
            {},
            None,
            upload_mode=wizard.state.upload_mode,
        )
        tracker_item_field_candidates, selected_tracker_item_settings = self._normalize_tracker_item_settings(
            mappable_schema_df,
            selected_mapping,
            None,
        )

        default_root_item_config = self._default_root_item_config(mappable_schema_df)
        upload_mode = normalize_gui_upload_mode(getattr(settings, "upload_mode", None))
        if not gui_upload_mode_allows_root_items(upload_mode):
            default_root_item_config["enabled"] = False
            default_root_item_config["group_enabled"] = False
        elif upload_mode == GUI_UPLOAD_MODE_UPSERT:
            default_root_item_config["enabled"] = False
            default_root_item_config["group_enabled"] = False

        return MappingContext(
            wizard=wizard,
            upload_mode=upload_mode,
            schema_df=mappable_schema_df,
            upload_columns=upload_columns,
            selected_mapping=selected_mapping,
            selected_mapping_modes=selected_mapping_modes,
            default_value_candidates=default_value_candidates,
            selected_default_values={},
            selected_default_value_modes=selected_default_value_modes,
            selected_tracker_item_settings=selected_tracker_item_settings,
            tracker_item_field_candidates=tracker_item_field_candidates,
            tracker_item_lookup_cache={},
            list_cols=list_cols,
            file_paths=file_paths,
            representative_file_path=representative_file_path,
            sheet_name=target_sheet_name,
            header_row=target_header_row,
            summary_column=target_summary_column,
            preview_data=preview,
            root_item_config=default_root_item_config,
            existing_item_cache={},
            batch_duplicate_update_item_ids=set(),
        )

    @staticmethod
    def _normalize_selected_mapping(
        selected_mapping: dict[str, str] | None,
        *,
        upload_columns: list[str],
        schema_df: pd.DataFrame,
    ) -> dict[str, str]:
        """현재 upload 컬럼과 schema에 실제로 존재하는 매핑만 남긴다."""
        if not selected_mapping:
            return {}

        valid_upload_columns = {
            str(column).strip()
            for column in upload_columns
            if str(column).strip()
        }
        valid_schema_fields = {
            str(field_name).strip()
            for field_name in schema_df["field_name"].dropna().tolist()
            if str(field_name).strip()
        }

        normalized_mapping: dict[str, str] = {}
        for df_column, schema_field in selected_mapping.items():
            normalized_column = str(df_column).strip()
            normalized_field = str(schema_field).strip()
            if not normalized_column or not normalized_field:
                continue
            if normalized_column not in valid_upload_columns:
                continue
            if normalized_field not in valid_schema_fields:
                continue
            normalized_mapping[normalized_column] = normalized_field
        return normalized_mapping

    def apply_saved_workflow_values(
        self,
        mapping_context: MappingContext,
        *,
        root_item_config: dict[str, Any] | None = None,
        selected_mapping: dict[str, str] | None = None,
        selected_mapping_modes: dict[str, dict[str, bool]] | None = None,
        selected_default_values: dict[str, str] | None = None,
        selected_default_value_modes: dict[str, dict[str, bool]] | None = None,
        selected_tracker_item_settings: dict[str, dict[str, Any]] | None = None,
    ) -> None:
        """현재 파일 기준 자동 추천은 유지하고, 저장된 preset은 유효한 항목만 덮어쓴다."""
        if root_item_config:
            mapping_context.root_item_config = dict(root_item_config)

        merged_mapping = self._normalize_selected_mapping(
            mapping_context.selected_mapping,
            upload_columns=mapping_context.upload_columns,
            schema_df=mapping_context.schema_df,
        )
        merged_mapping.update(
            self._normalize_selected_mapping(
                selected_mapping,
                upload_columns=mapping_context.upload_columns,
                schema_df=mapping_context.schema_df,
            )
        )
        mapping_context.selected_mapping = merged_mapping
        mapping_context.selected_mapping_modes = self._normalize_mapping_modes(
            mapping_context.selected_mapping,
            selected_mapping_modes
            if selected_mapping_modes is not None
            else mapping_context.selected_mapping_modes,
            upload_mode=mapping_context.upload_mode,
        )

        valid_schema_fields = {
            str(field_name).strip()
            for field_name in mapping_context.schema_df["field_name"].dropna().tolist()
            if str(field_name).strip()
        }

        default_values_source = (
            selected_default_values
            if selected_default_values is not None
            else mapping_context.selected_default_values
        )
        mapping_context.selected_default_values = {
            str(field_name).strip(): str(raw_value).strip()
            for field_name, raw_value in (default_values_source or {}).items()
            if str(field_name).strip() in valid_schema_fields and str(raw_value).strip()
        }
        mapping_context.selected_default_value_modes = self._normalize_default_value_modes(
            mapping_context.selected_default_values,
            selected_default_value_modes
            if selected_default_value_modes is not None
            else mapping_context.selected_default_value_modes,
            upload_mode=mapping_context.upload_mode,
        )

        tracker_item_settings_source = (
            selected_tracker_item_settings
            if selected_tracker_item_settings is not None
            else mapping_context.selected_tracker_item_settings
        )
        (
            mapping_context.tracker_item_field_candidates,
            mapping_context.selected_tracker_item_settings,
        ) = self._normalize_tracker_item_settings(
            mapping_context.schema_df,
            mapping_context.selected_mapping,
            tracker_item_settings_source,
        )

    def validate_mapping(
        self,
        mapping_context: MappingContext,
        selected_mapping: dict[str, str],
        selected_default_values: dict[str, str] | None = None,
        selected_tracker_item_settings: dict[str, dict[str, Any]] | None = None,
        *,
        selected_mapping_modes: dict[str, dict[str, bool]] | None = None,
        selected_default_value_modes: dict[str, dict[str, bool]] | None = None,
    ) -> ValidationContext:
        """`validate_mapping` 입력을 검증한다."""
        wizard = mapping_context.wizard
        list_cols = self.mapper.get_list_columns_for_mapping(selected_mapping, mapping_context.schema_df)
        representative_file_path = mapping_context.representative_file_path
        representative_raw_df = self._raw_df_for_file(mapping_context, representative_file_path)
        wizard.load_raw_dataframe(representative_raw_df.copy(), list_cols=list_cols)
        wizard.state.upload_mode = normalize_gui_upload_mode(mapping_context.upload_mode)
        normalized_default_values = {
            str(field_name).strip(): str(raw_value).strip()
            for field_name, raw_value in (selected_default_values or {}).items()
            if str(field_name).strip() and str(raw_value).strip()
        }
        normalized_mapping_modes = self._normalize_mapping_modes(
            selected_mapping,
            selected_mapping_modes,
            upload_mode=mapping_context.upload_mode,
        )
        normalized_default_value_modes = self._normalize_default_value_modes(
            normalized_default_values,
            selected_default_value_modes,
            upload_mode=mapping_context.upload_mode,
        )
        tracker_item_field_candidates, normalized_tracker_item_settings = self._normalize_tracker_item_settings(
            mapping_context.schema_df,
            selected_mapping,
            selected_tracker_item_settings,
        )
        mapping_context.selected_mapping = selected_mapping
        mapping_context.selected_mapping_modes = normalized_mapping_modes
        mapping_context.selected_default_values = normalized_default_values
        mapping_context.selected_default_value_modes = normalized_default_value_modes
        mapping_context.selected_tracker_item_settings = normalized_tracker_item_settings
        mapping_context.tracker_item_field_candidates = tracker_item_field_candidates
        wizard.state.selected_mapping_modes = dict(normalized_mapping_modes)
        wizard.state.selected_default_value_modes = dict(normalized_default_value_modes)
        wizard.state.selected_tracker_item_settings = dict(normalized_tracker_item_settings)
        wizard.state.tracker_item_lookup_cache = dict(mapping_context.tracker_item_lookup_cache)
        wizard.state.existing_item_cache = {}
        validation_result = run_validation_pipeline(
            wizard,
            selected_mapping,
            selected_mapping_modes=normalized_mapping_modes,
            selected_default_values=normalized_default_values,
            selected_default_value_modes=normalized_default_value_modes,
            selected_tracker_item_settings=normalized_tracker_item_settings,
            fetch_existing_items=not gui_upload_mode_supports_update(mapping_context.upload_mode),
        )
        comparison_df = self._gui_visible_comparison_df(validation_result.comparison_df)
        option_check_frames = [
            self._annotate_source_frame(
                validation_result.option_check_df if validation_result.option_check_df is not None else pd.DataFrame(),
                file_label=Path(representative_file_path).name,
                file_path=representative_file_path,
            )
        ]
        payload_frames = [
            self._annotate_source_frame(
                validation_result.payload_df,
                file_label=Path(representative_file_path).name,
                file_path=representative_file_path,
            )
        ]
        row_context_frames = [
            self._annotate_source_frame(
                wizard.state.converted_upload_df if wizard.state.converted_upload_df is not None else wizard.state.upload_df,
                file_label=Path(representative_file_path).name,
                file_path=representative_file_path,
            )
        ]

        batch_wizard = None
        additional_file_paths = [
            file_path
            for file_path in mapping_context.file_paths
            if str(file_path).strip() and str(file_path).strip() != representative_file_path
        ]
        for file_path in additional_file_paths:
            if batch_wizard is None:
                batch_wizard = self._create_validation_wizard(mapping_context)
            else:
                self._sync_validation_wizard_caches(batch_wizard, wizard)
            batch_wizard.load_raw_dataframe(
                self._raw_df_for_file(mapping_context, file_path).copy(),
                list_cols=list_cols,
            )
            batch_wizard.state.selected_tracker_item_settings = dict(normalized_tracker_item_settings)
            batch_wizard.state.tracker_item_lookup_cache = dict(wizard.state.tracker_item_lookup_cache)
            batch_wizard.state.existing_item_cache = {}
            batch_validation_result = run_validation_pipeline(
                batch_wizard,
                selected_mapping,
                selected_mapping_modes=normalized_mapping_modes,
                selected_default_values=normalized_default_values,
                selected_default_value_modes=normalized_default_value_modes,
                selected_tracker_item_settings=normalized_tracker_item_settings,
                fetch_existing_items=not gui_upload_mode_supports_update(mapping_context.upload_mode),
            )
            self._sync_validation_wizard_caches(wizard, batch_wizard)
            option_check_frames.append(
                self._annotate_source_frame(
                    batch_validation_result.option_check_df if batch_validation_result.option_check_df is not None else pd.DataFrame(),
                    file_label=Path(file_path).name,
                    file_path=file_path,
                )
            )
            payload_frames.append(
                self._annotate_source_frame(
                    batch_validation_result.payload_df,
                    file_label=Path(file_path).name,
                    file_path=file_path,
                )
            )
            row_context_frames.append(
                self._annotate_source_frame(
                    batch_wizard.state.converted_upload_df if batch_wizard.state.converted_upload_df is not None else batch_wizard.state.upload_df,
                    file_label=Path(file_path).name,
                    file_path=file_path,
                )
            )

        mapping_context.tracker_item_lookup_cache = dict(wizard.state.tracker_item_lookup_cache)
        mapping_context.existing_item_cache = {}
        option_check_df = (
            pd.concat(option_check_frames, ignore_index=True)
            if any(not frame.empty for frame in option_check_frames)
            else pd.DataFrame()
        )
        payload_df = (
            pd.concat(payload_frames, ignore_index=True)
            if any(not frame.empty for frame in payload_frames)
            else pd.DataFrame()
        )
        row_context_df = (
            pd.concat(row_context_frames, ignore_index=True)
            if any(not frame.empty for frame in row_context_frames)
            else pd.DataFrame()
        )

        has_blocking = False
        if not option_check_df.empty:
            status_series = option_check_df["status"].fillna("").astype(str)
            has_blocking = bool(
                status_series.isin(BLOCKING_OPTION_STATUSES).any()
                or status_series.str.endswith(USER_LOOKUP_FAILURE_SUFFIXES).any()
            )

        if not payload_df.empty and (payload_df["payload_status"] != PayloadStatus.READY.value).any():
            has_blocking = True

        issue_df = self._build_user_issue_df(
            comparison_df,
            option_check_df,
            payload_df,
            row_context_df=row_context_df,
            selected_default_values=normalized_default_values,
        )
        mapping_context.batch_duplicate_update_item_ids = set()
        if gui_upload_mode_supports_update(mapping_context.upload_mode):
            file_upload_dfs = {
                file_path: self._upload_df_for_file(
                    mapping_context,
                    file_path=file_path,
                    list_cols=list_cols,
                )
                for file_path in mapping_context.file_paths
            }
            duplicate_item_ids, duplicate_issue_df = self._build_batch_update_duplicate_issue_df(
                mapping_context,
                file_upload_dfs=file_upload_dfs,
            )
            mapping_context.batch_duplicate_update_item_ids = set(duplicate_item_ids)
            if not duplicate_issue_df.empty:
                issue_df = pd.concat([issue_df, duplicate_issue_df], ignore_index=True)
                issue_df = self._finalize_issue_df(issue_df)
        upsert_root_issue_df = self._build_upsert_root_item_issue_df(
            mapping_context,
            payload_df=payload_df,
        )
        if not upsert_root_issue_df.empty:
            issue_df = pd.concat([issue_df, upsert_root_issue_df], ignore_index=True)
            issue_df = self._finalize_issue_df(issue_df)
        summary_stats = self._build_summary_stats(issue_df, row_context_df)
        summary_stats["file_count"] = len(mapping_context.file_paths)
        summary_stats["batch_total_rows"] = self._count_batch_upload_rows(
            mapping_context,
            list_cols=list_cols,
        )
        if not issue_df.empty and issue_df["severity"].eq("오류").any():
            has_blocking = True

        return ValidationContext(
            comparison_df=comparison_df,
            option_check_df=option_check_df,
            converted_upload_df=row_context_df,
            issue_df=issue_df,
            has_blocking_issues=has_blocking,
            summary_stats=summary_stats,
        )

    @classmethod
    def _build_row_label(cls, row: pd.Series) -> str:
        """중복 update 이슈에서 사용할 Excel 행 표시를 만든다."""
        return ValidationPresenter.build_row_label(row)

    def build_root_item_payload_specs(
        self,
        mapping_context: MappingContext,
        wizard: CodebeamerUploadWizard,
        file_path: str,
    ) -> list[RootItemUploadSpec]:
        """업로드할 파일·그룹 루트 항목 명세를 구성한다."""
        return self.root_items.build_root_item_payload_specs(
            mapping_context,
            wizard,
            file_path,
        )

    def build_root_item_payload_spec(
        self,
        mapping_context: MappingContext,
        file_path: str,
    ) -> tuple[str | None, dict[str, Any]]:
        """단일 루트 항목 호환 명세를 구성한다."""
        return self.root_items.build_root_item_payload_spec(
            mapping_context,
            file_path,
        )

    @staticmethod
    def _tracker_item_query_mapping(mapping_context: MappingContext) -> dict[str, str]:
        """`tracker_item_query_mapping` 관련 처리를 수행한다."""
        query_mapping: dict[str, str] = {}
        for df_column, schema_field in mapping_context.selected_mapping.items():
            scope = dict((mapping_context.selected_mapping_modes or {}).get(str(df_column).strip()) or {})
            if not scope_applies_to_upload_mode(
                scope,
                upload_mode=mapping_context.upload_mode,
            ):
                continue
            setting = mapping_context.selected_tracker_item_settings.get(str(schema_field).strip(), {})
            if str(setting.get("mode") or "").strip() != TrackerItemResolutionMode.QUERY.value:
                continue
            query_mapping[str(df_column).strip()] = str(schema_field).strip()
        return query_mapping

    def _prime_tracker_item_lookup_cache_for_batch(
        self,
        settings,
        mapping_context: MappingContext,
    ) -> None:
        """`prime_tracker_item_lookup_cache_for_batch` 관련 처리를 수행한다."""
        query_mapping = self._tracker_item_query_mapping(mapping_context)
        if not query_mapping:
            return

        cache_wizard = self.create_wizard(settings)
        cache_wizard.select_project(int(settings.default_project_id))
        cache_wizard.select_tracker(int(settings.default_tracker_id))
        cache_wizard.state.schema = mapping_context.wizard.state.schema
        cache_wizard.state.schema_df = mapping_context.schema_df
        cache_wizard.state.selected_mapping = dict(mapping_context.selected_mapping)
        cache_wizard.state.selected_mapping_modes = {
            str(key): dict(value)
            for key, value in dict(mapping_context.selected_mapping_modes or {}).items()
            if str(key).strip() and isinstance(value, dict)
        }
        cache_wizard.state.selected_tracker_item_settings = dict(mapping_context.selected_tracker_item_settings)
        cache_wizard.state.tracker_item_lookup_cache = dict(mapping_context.tracker_item_lookup_cache)

        option_maps = cache_wizard.mapper.build_option_maps_from_schema(mapping_context.schema_df)
        option_maps = cache_wizard._decorate_tracker_item_option_maps(option_maps)
        cache_wizard.state.option_maps = option_maps

        unique_values_by_field: dict[str, set[str]] = {}
        for file_path in mapping_context.file_paths:
            preview_raw_df = self._cached_raw_df_for_file(mapping_context.preview_data, file_path)

            prepare_upload_dataframe(
                cache_wizard,
                file_path=file_path,
                sheet_name=mapping_context.sheet_name,
                header_row=mapping_context.header_row,
                summary_col=mapping_context.summary_column,
                selected_mapping=mapping_context.selected_mapping,
                schema=mapping_context.wizard.state.schema,
                schema_df=mapping_context.schema_df,
                raw_df=preview_raw_df,
            )
            current_values = cache_wizard.collect_tracker_item_query_values(
                cache_wizard.state.upload_df,
                query_mapping,
                option_maps,
            )
            for schema_field, values in current_values.items():
                unique_values_by_field.setdefault(schema_field, set()).update(values)

        cache_wizard.prime_tracker_item_query_values(option_maps, unique_values_by_field)
        mapping_context.tracker_item_lookup_cache = dict(cache_wizard.state.tracker_item_lookup_cache)

    @staticmethod
    def _batch_output_dir(output_dir: str, file_path: str, index: int) -> str:
        """`batch_output_dir` 관련 처리를 수행한다."""
        safe_name = Path(file_path).stem.strip() or f"file_{index:03d}"
        return str(Path(output_dir) / f"{index:03d}_{safe_name}")

    @staticmethod
    def _ready_upload_count(
        wizard: CodebeamerUploadWizard,
        root_item_specs: list[RootItemUploadSpec] | None = None,
    ) -> int:
        """`ready_upload_count` 관련 처리를 수행한다."""
        insert_count, update_count = GuiUploadPipelineService._phase_ready_counts(
            wizard,
            root_item_specs=root_item_specs,
        )
        return insert_count + update_count

    @staticmethod
    def _phase_ready_counts(
        wizard: CodebeamerUploadWizard,
        root_item_specs: list[RootItemUploadSpec] | None = None,
    ) -> tuple[int, int]:
        """`phase_ready_counts` 관련 처리를 수행한다."""
        payload_df = wizard.state.payload_df if wizard.state.payload_df is not None else wizard.build_payloads()
        if payload_df is None or payload_df.empty:
            return (0, 0)

        ready_df = payload_df[payload_df["payload_status"] == PayloadStatus.READY.value].copy()
        upload_mode = normalize_gui_upload_mode(getattr(wizard.state, "upload_mode", GUI_UPLOAD_MODE_CREATE))
        if ready_df.empty:
            return (0, 0)

        if upload_mode == GUI_UPLOAD_MODE_UPDATE:
            return (0, int(len(ready_df)))

        if upload_mode == GUI_UPLOAD_MODE_UPSERT and "_operation" in ready_df.columns:
            operation_series = ready_df["_operation"].fillna("").astype(str).str.lower()
            insert_count = int(operation_series.eq("create").sum())
            update_count = int(operation_series.eq("update").sum())
            if insert_count > 0 and root_item_specs:
                insert_count += len(root_item_specs)
            return (insert_count, update_count)

        insert_count = int(len(ready_df))
        if (
            insert_count > 0
            and root_item_specs
            and gui_upload_mode_allows_root_items(upload_mode)
        ):
            insert_count += len(root_item_specs)
        return (insert_count, 0)

    @staticmethod
    def _annotate_batch_result_frame(
        df: pd.DataFrame | None,
        *,
        file_label: str,
        file_path: str,
    ) -> pd.DataFrame:
        """`annotate_batch_result_frame` 관련 처리를 수행한다."""
        return GuiUploadPipelineService._annotate_source_frame(
            df,
            file_label=file_label,
            file_path=file_path,
        )

    def _prepare_wizard_for_file(
        self,
        settings,
        mapping_context: MappingContext,
        *,
        file_path: str,
        sheet_name: str,
        header_row: int,
        summary_col: str,
    ) -> CodebeamerUploadWizard:
        """`prepare_wizard_for_file` 관련 처리를 수행한다."""
        wizard = self.create_wizard(settings)
        wizard.select_project(int(settings.default_project_id))
        wizard.select_tracker(int(settings.default_tracker_id))
        wizard.state.upload_mode = normalize_gui_upload_mode(mapping_context.upload_mode)

        schema = mapping_context.wizard.state.schema
        if schema is None:
            schema, _ = load_tracker_schema_df(wizard)
        schema_df = mapping_context.schema_df

        prepare_upload_dataframe(
            wizard,
            file_path=file_path,
            sheet_name=sheet_name,
            header_row=header_row,
            summary_col=summary_col,
            selected_mapping=mapping_context.selected_mapping,
            schema=schema,
            schema_df=schema_df,
            raw_df=self._cached_raw_df_for_file(mapping_context.preview_data, file_path),
        )

        wizard.state.selected_mapping = dict(mapping_context.selected_mapping)
        wizard.state.selected_mapping_modes = {
            str(key): dict(value)
            for key, value in dict(mapping_context.selected_mapping_modes or {}).items()
            if str(key).strip() and isinstance(value, dict)
        }
        wizard.state.schema = schema
        wizard.state.schema_df = schema_df
        wizard.state.selected_default_value_modes = {
            str(key): dict(value)
            for key, value in dict(mapping_context.selected_default_value_modes or {}).items()
            if str(key).strip() and isinstance(value, dict)
        }
        wizard.state.selected_tracker_item_settings = dict(mapping_context.selected_tracker_item_settings)
        wizard.state.tracker_item_lookup_cache = dict(mapping_context.tracker_item_lookup_cache)
        wizard.state.existing_item_cache = {}
        wizard.state.comparison_df = wizard.mapper.compare_upload_df_with_schema(
            upload_df=wizard.state.upload_df,
            schema_df=schema_df,
            selected_mapping=wizard.state.selected_mapping,
        )
        wizard._detect_table_field_columns()
        wizard.process_option_mapping(
            wizard.state.selected_mapping,
            selected_mapping_modes=wizard.state.selected_mapping_modes,
            selected_default_values=mapping_context.selected_default_values,
            selected_default_value_modes=wizard.state.selected_default_value_modes,
            selected_tracker_item_settings=mapping_context.selected_tracker_item_settings,
        )
        wizard.build_payloads(
            force=True,
            fetch_existing_items=not gui_upload_mode_supports_update(mapping_context.upload_mode),
        )
        return wizard

    def run_batch_upload(
        self,
        settings,
        file_state: dict[str, Any],
        mapping_context: MappingContext,
        *,
        dry_run: bool,
        continue_on_error: bool,
        output_dir: str,
        event_callback=None,
        cancel_requested=None,
        pause_requested=None,
    ) -> dict[str, Any]:
        """`run_batch_upload` 관련 처리를 수행한다."""
        file_paths = mapping_context.file_paths or self._normalize_file_paths(file_state)
        if not file_paths:
            raise ValueError("업로드할 Excel 파일이 없습니다.")
        if not mapping_context.selected_mapping:
            raise ValueError("검증된 매핑이 없습니다.")
        upload_mode = normalize_gui_upload_mode(mapping_context.upload_mode)
        if gui_upload_mode_supports_update(upload_mode) and bool(getattr(settings, "offline_mode", False)):
            raise ValueError("테스트 모드에서는 기존 수정 또는 혼합 처리 작업을 실행할 수 없습니다.")
        if gui_upload_mode_supports_update(upload_mode) and mapping_context.batch_duplicate_update_item_ids:
            duplicate_ids = ", ".join(str(item_id) for item_id in sorted(mapping_context.batch_duplicate_update_item_ids))
            raise ValueError(f"배치 전체에서 중복된 업데이트 대상 id가 있습니다: {duplicate_ids}")
        action_label = gui_upload_mode_action_label(upload_mode)

        sheet_name = str(file_state["sheet_name"])
        header_row = int(file_state["header_row"])
        summary_col = str(file_state["summary_column"])

        prepared_jobs: list[BatchUploadJob] = []
        success_frames: list[pd.DataFrame] = []
        failed_frames: list[pd.DataFrame] = []
        unresolved_frames: list[pd.DataFrame] = []
        created_map_by_file: dict[str, dict[Any, Any]] = {}
        total_count = 0
        phase_total_counts = {"insert": 0, "update": 0}
        phase_results = {
            "insert": {"total": 0, "success": 0, "failed": 0, "unresolved": 0},
            "update": {"total": 0, "success": 0, "failed": 0, "unresolved": 0},
        }

        def _emit(event: dict[str, Any]) -> None:
            """`emit` 관련 처리를 수행한다."""
            if event_callback is not None:
                event_callback(event)

        def _sync_control() -> None:
            """`sync_control` 상태를 동기화한다."""
            while pause_requested is not None and pause_requested():
                time.sleep(0.1)
            if cancel_requested is not None and cancel_requested():
                raise RuntimeError("__UPLOAD_CANCELLED__")

        if self._tracker_item_query_mapping(mapping_context):
            _emit({
                "type": "log",
                "message": "Tracker item query 대상 값을 파일 전체에서 모아 사전 조회하는 중입니다.",
            })
            self._prime_tracker_item_lookup_cache_for_batch(settings, mapping_context)

        for index, file_path in enumerate(file_paths, start=1):
            _sync_control()
            file_label = Path(file_path).name
            _emit({
                "type": "log",
                "message": f"[{file_label}] {action_label} 데이터를 준비하는 중입니다.",
            })
            try:
                wizard = self._prepare_wizard_for_file(
                    settings,
                    mapping_context,
                    file_path=file_path,
                    sheet_name=sheet_name,
                    header_row=header_row,
                    summary_col=summary_col,
                )
                if gui_upload_mode_allows_root_items(upload_mode):
                    root_item_specs = self.build_root_item_payload_specs(mapping_context, wizard, file_path)
                else:
                    root_item_specs = []
                insert_ready_count, update_ready_count = self._phase_ready_counts(wizard, root_item_specs)
                ready_count = insert_ready_count + update_ready_count
                total_count += ready_count
                phase_total_counts["insert"] += insert_ready_count
                phase_total_counts["update"] += update_ready_count
                prepared_jobs.append(BatchUploadJob(
                    file_path=file_path,
                    file_label=file_label,
                    root_item_specs=root_item_specs,
                    ready_count=ready_count,
                    insert_ready_count=insert_ready_count,
                    update_ready_count=update_ready_count,
                    output_dir=self._batch_output_dir(output_dir, file_path, index),
                    wizard=wizard,
                ))
            except Exception as exc:
                fallback_root_item_name = Path(file_path).stem.strip() or file_label
                failed_frames.append(pd.DataFrame([{
                    "source_file": file_label,
                    "source_file_path": file_path,
                    "_row_id": None,
                    "parent_row_id": None,
                    "upload_name": fallback_root_item_name,
                    "error": str(exc),
                    "status": PayloadStatus.FAILED.value,
                }]))
                _emit({
                    "type": "log",
                    "message": f"[{file_label}] 업로드 준비 실패: {exc}",
                })
                if not continue_on_error:
                    break

        _emit({
            "type": "batch_total",
            "total": total_count,
            "phase_totals": dict(phase_total_counts),
        })

        for job_index, job in enumerate(prepared_jobs, start=1):
            _sync_control()
            _emit({
                "type": "log",
                "message": f"[{job_index}/{len(prepared_jobs)}] {job.file_label} {action_label}를 시작합니다.",
            })

            def _forward_event(event: dict[str, Any]) -> None:
                """`forward_event` 관련 처리를 수행한다."""
                forwarded = dict(event)
                forwarded["source_file"] = job.file_label
                forwarded["source_file_path"] = job.file_path

                upload_name = str(forwarded.get("upload_name") or "").strip()
                forwarded["upload_name"] = (
                    f"[{job.file_label}] {upload_name}"
                    if upload_name
                    else f"[{job.file_label}]"
                )

                message = str(forwarded.get("message") or "").strip()
                if message:
                    forwarded["message"] = f"[{job.file_label}] {message}"

                _emit(forwarded)

            if upload_mode == GUI_UPLOAD_MODE_UPDATE:
                result = job.wizard.update_items(
                    dry_run=dry_run,
                    continue_on_error=continue_on_error,
                    event_callback=_forward_event,
                    cancel_requested=cancel_requested,
                    pause_requested=pause_requested,
                )
            elif upload_mode == GUI_UPLOAD_MODE_UPSERT:
                result = job.wizard.upsert_items(
                    dry_run=dry_run,
                    continue_on_error=continue_on_error,
                    top_level_parent_specs=[
                        {
                            "key": spec.key,
                            "name": spec.name,
                            "field_values": dict(spec.field_values),
                            "row_ids": list(spec.row_ids),
                            "parent_key": spec.parent_key,
                            "kind": spec.kind,
                        }
                        for spec in job.root_item_specs
                    ],
                    event_callback=_forward_event,
                    cancel_requested=cancel_requested,
                    pause_requested=pause_requested,
                )
            else:
                result = job.wizard.upload(
                    dry_run=dry_run,
                    continue_on_error=continue_on_error,
                    top_level_parent_specs=[
                        {
                            "key": spec.key,
                            "name": spec.name,
                            "field_values": dict(spec.field_values),
                            "row_ids": list(spec.row_ids),
                            "parent_key": spec.parent_key,
                            "kind": spec.kind,
                        }
                        for spec in job.root_item_specs
                    ],
                    event_callback=_forward_event,
                    cancel_requested=cancel_requested,
                    pause_requested=pause_requested,
                )
            job.wizard.save_state(job.output_dir)
            created_map_by_file[job.file_path] = result.get("created_map", {})

            success_df = self._annotate_batch_result_frame(
                result.get("success_df"),
                file_label=job.file_label,
                file_path=job.file_path,
            )
            failed_df = self._annotate_batch_result_frame(
                result.get("failed_df"),
                file_label=job.file_label,
                file_path=job.file_path,
            )
            unresolved_df = self._annotate_batch_result_frame(
                result.get("unresolved_df"),
                file_label=job.file_label,
                file_path=job.file_path,
            )

            if not success_df.empty:
                success_frames.append(success_df)
            if not failed_df.empty:
                failed_frames.append(failed_df)
            if not unresolved_df.empty:
                unresolved_frames.append(unresolved_df)

            for phase_name in ("insert", "update"):
                if not success_df.empty and "phase" in success_df.columns:
                    phase_results[phase_name]["success"] += int(
                        success_df["phase"].fillna("").astype(str).str.lower().eq(phase_name).sum()
                    )
                if not failed_df.empty and "phase" in failed_df.columns:
                    phase_results[phase_name]["failed"] += int(
                        failed_df["phase"].fillna("").astype(str).str.lower().eq(phase_name).sum()
                    )
                if not unresolved_df.empty and "phase" in unresolved_df.columns:
                    phase_results[phase_name]["unresolved"] += int(
                        unresolved_df["phase"].fillna("").astype(str).str.lower().eq(phase_name).sum()
                    )

            if not continue_on_error and (not failed_df.empty or not unresolved_df.empty):
                break

        for phase_name in ("insert", "update"):
            phase_results[phase_name]["total"] = (
                int(phase_results[phase_name]["success"])
                + int(phase_results[phase_name]["failed"])
                + int(phase_results[phase_name]["unresolved"])
            )

        return {
            "created_map_by_file": created_map_by_file,
            "success_df": pd.concat(success_frames, ignore_index=True) if success_frames else pd.DataFrame(),
            "failed_df": pd.concat(failed_frames, ignore_index=True) if failed_frames else pd.DataFrame(),
            "unresolved_df": pd.concat(unresolved_frames, ignore_index=True) if unresolved_frames else pd.DataFrame(),
            "phase_results": phase_results,
        }

    def _build_summary_stats(
        self,
        issue_df: pd.DataFrame,
        row_context_df: pd.DataFrame | None,
    ) -> dict[str, int]:
        return self.validation_presenter.build_summary_stats(issue_df, row_context_df)

    def _build_user_issue_df(
        self,
        comparison_df: pd.DataFrame,
        option_check_df: pd.DataFrame,
        payload_df: pd.DataFrame,
        *,
        row_context_df: pd.DataFrame | None = None,
        selected_default_values: dict[str, str] | None = None,
    ) -> pd.DataFrame:
        return self.validation_presenter.build_user_issue_df(
            comparison_df,
            option_check_df,
            payload_df,
            row_context_df=row_context_df,
            selected_default_values=selected_default_values,
        )

    def _finalize_issue_df(self, issue_df: pd.DataFrame) -> pd.DataFrame:
        return self.validation_presenter.finalize_issue_df(issue_df)

    @staticmethod
    def _parse_payload_error(payload_error: str) -> dict[str, str]:
        return ValidationPresenter.parse_payload_error(payload_error)
