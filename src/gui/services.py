from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pandas as pd

from src.codebeamer_client import CodebeamerClient
from src.excel_reader import ExcelReader
from src.hierarchy_processor import HierarchyProcessor
from src.models import MappingStatus
from src.mapping_service import MappingService
from src.models import OptionCheckStatus
from src.models import PayloadStatus
from src.upload_pipeline import load_tracker_schema_df
from src.upload_pipeline import prepare_upload_dataframe
from src.upload_pipeline import run_validation_pipeline
from src.upload_pipeline import suggest_mapping_from_headers
from src.wizard import CodebeamerUploadWizard


@dataclass
class PreviewData:
    sheet_names: list[str]
    headers: list[str]
    rows: list[list[str]]
    suggested_summary: str


class GuiCodebeamerService:
    """GUI 에서 사용하는 최소 Codebeamer 조회 기능을 제공한다."""

    def __init__(self, client_factory=CodebeamerClient, logger=None) -> None:
        self.client_factory = client_factory
        self.logger = logger

    def _build_client(self, settings) -> CodebeamerClient:
        return self.client_factory(
            settings.base_url,
            settings.username,
            settings.password,
            self.logger,
            rate_limit_retry_delay_seconds=settings.rate_limit_retry_delay_seconds,
            rate_limit_max_retries=settings.rate_limit_max_retries,
        )

    @staticmethod
    def _normalize_items(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
        normalized: list[dict[str, Any]] = []
        for item in items:
            if not isinstance(item, dict):
                continue
            normalized.append({
                "id": item.get("id"),
                "name": item.get("name") or item.get("key") or str(item.get("id", "")),
            })
        return normalized

    def test_connection_and_load_projects(self, settings) -> list[dict[str, Any]]:
        projects = self._build_client(settings).get_projects()
        return self._normalize_items(projects)

    def load_trackers(self, settings, project_id: int) -> list[dict[str, Any]]:
        trackers = self._build_client(settings).get_trackers(project_id)
        return self._normalize_items(trackers)


class GuiExcelService:
    """GUI 파일 선택 화면에서 사용하는 Excel 메타데이터와 미리보기를 제공한다."""

    def __init__(self, logger=None, *, reader_cls=ExcelReader) -> None:
        self.logger = logger
        self.reader_cls = reader_cls

    @staticmethod
    def _normalize_headers(values: list[Any]) -> list[str]:
        headers: list[str] = []
        for index, value in enumerate(values):
            if value is None:
                headers.append(f"Unnamed_{index}")
            else:
                headers.append(str(value).strip())
        return headers

    @staticmethod
    def _suggest_summary(headers: list[str]) -> str:
        for header in headers:
            if header.lower() == "summary":
                return header
        for header in headers:
            if header == "요약":
                return header
        return headers[0] if headers else "Summary"

    def load_preview(
        self,
        file_path: str,
        *,
        sheet_name: str | None = None,
        header_row: int = 1,
        max_preview_rows: int = 10,
    ) -> PreviewData:
        if header_row < 1:
            raise ValueError("header_row 는 1 이상이어야 합니다.")

        header_reader = self.reader_cls(header_row=header_row, summary_col="Summary", logger=self.logger)
        sheet_names = header_reader.list_sheet_names(file_path)
        if not sheet_names:
            raise ValueError("시트가 없는 Excel 파일입니다.")

        target_sheet_name = sheet_name or sheet_names[0]
        if target_sheet_name not in sheet_names:
            target_sheet_name = sheet_names[0]

        headers = header_reader.read_headers(file_path, target_sheet_name)
        suggested_summary = self._suggest_summary(headers)
        data_reader = self.reader_cls(
            header_row=header_row,
            summary_col=suggested_summary,
            logger=self.logger,
        )
        raw_df = data_reader.read_excel(file_path=file_path, sheet_name=target_sheet_name)

        preview_headers = [header for header in headers if not str(header).startswith("_")]
        preview_rows: list[list[str]] = []
        if not raw_df.empty:
            visible_df = raw_df[preview_headers].head(max_preview_rows)
            for _, row in visible_df.iterrows():
                preview_rows.append(
                    ["" if value is None else str(value) for value in row.tolist()]
                )

        return PreviewData(
            sheet_names=sheet_names,
            headers=preview_headers,
            rows=preview_rows,
            suggested_summary=suggested_summary,
        )


BLOCKING_OPTION_STATUSES = {
    OptionCheckStatus.DIRECT_PARSE_FAILED.value,
    OptionCheckStatus.DF_COLUMN_MISSING.value,
    OptionCheckStatus.FIELD_UNSUPPORTED.value,
    OptionCheckStatus.LOOKUP_REQUIRED.value,
    OptionCheckStatus.OPTION_MAP_MISSING.value,
    OptionCheckStatus.OPTION_NOT_FOUND.value,
    OptionCheckStatus.OPTION_SOURCE_UNAVAILABLE.value,
}
USER_LOOKUP_FAILURE_SUFFIXES = (
    "USER_LOOKUP_NOT_RUN",
    "USER_LOOKUP_FAILED",
    "USER_LOOKUP_AMBIGUOUS",
    "USER_NOT_FOUND",
    "MEMBER_LOOKUP_FAILED",
    "MEMBER_LOOKUP_AMBIGUOUS",
    "MEMBER_NOT_FOUND",
)
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
DEFAULT_VALUE_COLUMN_LABEL = "(기본값)"
GUI_HIDDEN_USER_COLUMNS = GUI_EXCLUDED_MAPPING_COLUMNS | {
    "payload_json",
    "payload_status",
    "payload_error",
    "error_response_json",
}


@dataclass
class DefaultValueCandidate:
    schema_field: str
    field_type: str
    options: list[str]
    mandatory: bool


@dataclass
class MappingContext:
    wizard: CodebeamerUploadWizard
    schema_df: pd.DataFrame
    upload_columns: list[str]
    selected_mapping: dict[str, str]
    default_value_candidates: list[DefaultValueCandidate]
    selected_default_values: dict[str, str]
    list_cols: list[str]


@dataclass
class ValidationContext:
    comparison_df: pd.DataFrame
    option_check_df: pd.DataFrame
    converted_upload_df: pd.DataFrame
    issue_df: pd.DataFrame
    has_blocking_issues: bool
    summary_stats: dict[str, int]


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
        self.logger = logger
        self.mapper = MappingService(logger=logger)
        self.client_factory = client_factory
        self.excel_service = excel_service or GuiExcelService(logger=logger)
        self.reader_cls = reader_cls

    def create_wizard(self, settings) -> CodebeamerUploadWizard:
        client = self.client_factory(
            settings.base_url,
            settings.username,
            settings.password,
            self.logger,
            rate_limit_retry_delay_seconds=settings.rate_limit_retry_delay_seconds,
            rate_limit_max_retries=settings.rate_limit_max_retries,
        )
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
        return CodebeamerUploadWizard(
            client=client,
            processor=processor,
            mapper=self.mapper,
            reader=reader,
            logger=self.logger,
        )

    @staticmethod
    def _is_gui_excluded_schema_field(row: pd.Series | dict[str, Any]) -> bool:
        field_name = str((row.get("field_name") if isinstance(row, dict) else row.get("field_name")) or "").strip().lower()
        tracker_item_field = str(
            (row.get("tracker_item_field") if isinstance(row, dict) else row.get("tracker_item_field")) or ""
        ).strip().lower()
        return field_name in GUI_EXCLUDED_TARGET_FIELDS or tracker_item_field in GUI_EXCLUDED_TARGET_FIELDS

    @staticmethod
    def _gui_upload_columns(upload_df: pd.DataFrame) -> list[str]:
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
        if comparison_df is None or comparison_df.empty:
            return comparison_df
        work = comparison_df.copy()
        if "df_column" not in work.columns:
            return work
        mask = ~work["df_column"].astype(str).isin(GUI_EXCLUDED_MAPPING_COLUMNS)
        mask &= ~work["df_column"].astype(str).str.startswith("_")
        return work[mask].reset_index(drop=True)

    @staticmethod
    def _is_hidden_user_column(column_name: Any) -> bool:
        text = str(column_name or "").strip()
        if not text:
            return False
        if text in GUI_HIDDEN_USER_COLUMNS:
            return True
        if text.startswith("_"):
            return True
        if "__" in text:
            return True
        return False

    def _build_default_value_candidates(
        self,
        schema_df: pd.DataFrame,
    ) -> list[DefaultValueCandidate]:
        candidates: list[DefaultValueCandidate] = []
        for candidate in self.mapper.get_default_value_candidates(schema_df):
            candidates.append(DefaultValueCandidate(
                schema_field=str(candidate.get("field_name") or ""),
                field_type=str(candidate.get("field_type") or ""),
                options=list(candidate.get("options") or []),
                mandatory=bool(candidate.get("mandatory", False)),
            ))
        return candidates

    def prepare_mapping_context(self, settings, file_state: dict[str, Any]) -> MappingContext:
        wizard = self.create_wizard(settings)
        wizard.select_project(int(settings.default_project_id))
        wizard.select_tracker(int(settings.default_tracker_id))

        schema, schema_df = load_tracker_schema_df(wizard)
        mappable_schema_df = schema_df[
            ~schema_df.apply(self._is_gui_excluded_schema_field, axis=1)
        ].reset_index(drop=True)

        preview = self.excel_service.load_preview(
            file_state["file_path"],
            sheet_name=file_state["sheet_name"],
            header_row=int(file_state["header_row"]),
        )
        headers = preview.headers
        raw_mapping = suggest_mapping_from_headers(headers, mappable_schema_df)

        _, list_cols = prepare_upload_dataframe(
            wizard,
            file_path=file_state["file_path"],
            sheet_name=file_state["sheet_name"],
            header_row=int(file_state["header_row"]),
            summary_col=str(file_state["summary_column"]),
            selected_mapping=raw_mapping,
            schema=schema,
            schema_df=mappable_schema_df,
        )

        upload_columns = self._gui_upload_columns(wizard.state.upload_df)
        selected_mapping = {
            column: schema_field
            for column, schema_field in raw_mapping.items()
            if column in upload_columns
        }
        default_value_candidates = self._build_default_value_candidates(mappable_schema_df)

        return MappingContext(
            wizard=wizard,
            schema_df=mappable_schema_df,
            upload_columns=upload_columns,
            selected_mapping=selected_mapping,
            default_value_candidates=default_value_candidates,
            selected_default_values={},
            list_cols=list_cols,
        )

    def validate_mapping(
        self,
        mapping_context: MappingContext,
        selected_mapping: dict[str, str],
        selected_default_values: dict[str, str] | None = None,
    ) -> ValidationContext:
        wizard = mapping_context.wizard
        list_cols = self.mapper.get_list_columns_for_mapping(selected_mapping, mapping_context.schema_df)
        wizard.load_raw_dataframe(wizard.state.raw_df.copy(), list_cols=list_cols)
        normalized_default_values = {
            str(field_name).strip(): str(raw_value).strip()
            for field_name, raw_value in (selected_default_values or {}).items()
            if str(field_name).strip() and str(raw_value).strip()
        }
        mapping_context.selected_mapping = selected_mapping
        mapping_context.selected_default_values = normalized_default_values
        validation_result = run_validation_pipeline(
            wizard,
            selected_mapping,
            selected_default_values=normalized_default_values,
        )
        comparison_df = validation_result.comparison_df
        comparison_df = self._gui_visible_comparison_df(comparison_df)
        option_check_df = (
            validation_result.option_check_df
            if validation_result.option_check_df is not None
            else pd.DataFrame()
        )

        has_blocking = False
        if not option_check_df.empty:
            status_series = option_check_df["status"].fillna("").astype(str)
            has_blocking = bool(
                status_series.isin(BLOCKING_OPTION_STATUSES).any()
                or status_series.str.endswith(USER_LOOKUP_FAILURE_SUFFIXES).any()
            )

        payload_df = validation_result.payload_df
        if not payload_df.empty and (payload_df["payload_status"] != PayloadStatus.READY.value).any():
            has_blocking = True

        row_context_df = wizard.state.converted_upload_df
        if row_context_df is None or row_context_df.empty:
            row_context_df = wizard.state.upload_df

        issue_df = self._build_user_issue_df(
            comparison_df,
            option_check_df,
            payload_df,
            row_context_df=row_context_df,
            selected_default_values=normalized_default_values,
        )
        summary_stats = self._build_summary_stats(issue_df, row_context_df)
        if not issue_df.empty and issue_df["severity"].eq("오류").any():
            has_blocking = True

        return ValidationContext(
            comparison_df=comparison_df,
            option_check_df=option_check_df,
            converted_upload_df=wizard.state.converted_upload_df,
            issue_df=issue_df,
            has_blocking_issues=has_blocking,
            summary_stats=summary_stats,
        )

    @staticmethod
    def _display_text(value: Any) -> str:
        if value is None:
            return ""
        if isinstance(value, float) and pd.isna(value):
            return ""
        if isinstance(value, list):
            return ", ".join(part for part in (GuiUploadPipelineService._display_text(item) for item in value) if part)
        if isinstance(value, dict):
            if value.get("name") is not None:
                return str(value.get("name")).strip()
            return str(value).strip()
        text = str(value).strip()
        return "" if text.lower() == "nan" else text

    @staticmethod
    def _to_row_key(value: Any) -> str:
        if value is None:
            return ""
        if isinstance(value, float):
            if pd.isna(value):
                return ""
            if value.is_integer():
                return str(int(value))
            return str(value)
        if isinstance(value, int):
            return str(value)

        text = str(value).strip()
        if not text or text.lower() == "nan":
            return ""
        try:
            numeric = float(text)
        except ValueError:
            return text
        if numeric.is_integer():
            return str(int(numeric))
        return text

    @classmethod
    def _build_row_label(cls, row: pd.Series) -> str:
        start_row = cls._to_row_key(row.get("_start_excel_row"))
        end_row = cls._to_row_key(row.get("_end_excel_row"))
        excel_row = cls._to_row_key(row.get("_excel_row"))
        row_key = cls._to_row_key(row.get("_row_id"))

        if start_row and end_row and start_row != end_row:
            return f"Excel {start_row}-{end_row}행"
        if start_row:
            return f"Excel {start_row}행"
        if excel_row:
            return f"Excel {excel_row}행"
        if row_key:
            return f"행 {row_key}"
        return ""

    @classmethod
    def _build_row_context_map(cls, row_context_df: pd.DataFrame | None) -> dict[str, dict[str, Any]]:
        if row_context_df is None or row_context_df.empty:
            return {}

        row_context_map: dict[str, dict[str, Any]] = {}
        for _, row in row_context_df.iterrows():
            row_key = cls._to_row_key(row.get("_row_id"))
            if not row_key:
                continue

            item_name = cls._display_text(row.get("upload_name"))
            if not item_name:
                for fallback_column in ("Summary", "summary", "요약", "name"):
                    if fallback_column in row.index:
                        item_name = cls._display_text(row.get(fallback_column))
                    if item_name:
                        break

            row_context_map[row_key] = {
                "row_id": row_key,
                "row_label": cls._build_row_label(row),
                "item_name": item_name,
                "values": row.to_dict(),
            }

        return row_context_map

    @classmethod
    def _row_context(
        cls,
        row_key: str,
        row_context_map: dict[str, dict[str, Any]],
        *,
        fallback_item_name: str = "",
    ) -> dict[str, str]:
        context = row_context_map.get(row_key, {})
        return {
            "row_id": row_key,
            "row_label": str(context.get("row_label") or (f"행 {row_key}" if row_key else "")),
            "item_name": str(context.get("item_name") or fallback_item_name or ""),
        }

    @classmethod
    def _raw_value_from_row_context(
        cls,
        row_key: str,
        column_name: str,
        row_context_map: dict[str, dict[str, Any]],
    ) -> str:
        if not row_key or not column_name:
            return ""
        context = row_context_map.get(row_key, {})
        values = context.get("values") if isinstance(context, dict) else None
        if not isinstance(values, dict):
            return ""
        return cls._display_text(values.get(column_name))

    @staticmethod
    def _message_from_option_status(row: pd.Series) -> tuple[str, str, str]:
        status = str(row.get("status") or "")
        field_name = str(row.get("schema_field") or "")
        df_column = str(row.get("df_column") or "")
        is_default_value = (
            str(row.get("value_source") or "") == "default"
            or df_column == DEFAULT_VALUE_COLUMN_LABEL
        )

        if status == OptionCheckStatus.FIELD_UNSUPPORTED.value:
            if is_default_value:
                return (
                    "오류",
                    f"{field_name} 필드는 공통 기본값으로 바로 넣을 수 없습니다.",
                    "기본값을 비우거나, Excel 컬럼으로 직접 매핑할 수 있는지 확인하세요.",
                )
            return (
                "오류",
                f"{field_name} 필드는 현재 GUI에서 지원하지 않습니다.",
                "이 컬럼 사용을 끄거나 지원되는 다른 필드로 다시 매핑하세요.",
            )
        if status == OptionCheckStatus.LOOKUP_REQUIRED.value:
            if is_default_value:
                return (
                    "오류",
                    f"{field_name} 기본값은 추가 조회가 필요해서 바로 넣을 수 없습니다.",
                    "기본값을 비우고 행별 값으로 관리하거나, 지원 로직을 추가해야 합니다.",
                )
            return (
                "오류",
                f"{field_name} 값은 업로드 전에 추가 조회가 필요합니다.",
                "이 컬럼 사용을 끄거나, 지원되는 필드로 다시 매핑하세요.",
            )
        if status == OptionCheckStatus.OPTION_NOT_FOUND.value:
            if is_default_value:
                return (
                    "오류",
                    f"{field_name} 기본값이 현재 트래커 옵션 목록에 없습니다.",
                    "기본값을 다시 선택하고, 트래커 옵션 이름과 정확히 일치하는지 확인하세요.",
                )
            return (
                "오류",
                f"{df_column} 입력값이 현재 트래커 옵션 목록에 없습니다.",
                "Excel 값을 트래커 옵션 이름과 동일하게 수정하세요.",
            )
        if status == OptionCheckStatus.DIRECT_PARSE_FAILED.value:
            if is_default_value:
                return (
                    "오류",
                    f"{field_name} 기본값을 아이디 형식으로 해석하지 못했습니다.",
                    "숫자 ID처럼 허용되는 형식으로 값을 다시 지정하세요.",
                )
            return (
                "오류",
                f"{df_column} 값을 아이디 형식으로 해석하지 못했습니다.",
                "셀 값을 숫자 ID처럼 허용되는 형식으로 수정하세요.",
            )
        if status == OptionCheckStatus.DF_COLUMN_MISSING.value:
            return (
                "오류",
                f"매핑된 Excel 컬럼 {df_column} 을(를) 찾을 수 없습니다.",
                "파일을 다시 불러오고, 매핑 화면에서 컬럼 선택을 다시 확인하세요.",
            )
        if status == "SCHEMA_FIELD_MISSING":
            return (
                "오류",
                str(row.get("error") or "선택한 기본값 필드를 현재 스키마에서 찾을 수 없습니다."),
                "매핑 화면으로 돌아가 기본값 필드를 다시 선택하세요.",
            )
        if status == "OPTION_MAP_MISSING":
            return (
                "오류",
                str(row.get("error") or "기본값 검증에 필요한 option map을 만들 수 없습니다."),
                "트래커 스키마를 다시 불러오거나 해당 기본값을 비운 뒤 다시 검증하세요.",
            )
        if status == OptionCheckStatus.OPTION_SOURCE_UNAVAILABLE.value:
            return (
                "오류",
                f"{field_name} 필드의 값을 확인할 준비가 아직 되어 있지 않습니다.",
                "이 컬럼 사용을 끄거나 지원되는 다른 필드로 다시 매핑하세요.",
            )
        if status.endswith(("USER_LOOKUP_FAILED", "USER_LOOKUP_AMBIGUOUS", "USER_NOT_FOUND")):
            return (
                "오류",
                f"{df_column} 값으로 사용자를 찾지 못했습니다.",
                "사용자 이름, 이메일, 아이디를 확인하고 프로젝트 멤버인지 점검하세요.",
            )
        if status.endswith(("MEMBER_LOOKUP_FAILED", "MEMBER_LOOKUP_AMBIGUOUS", "MEMBER_NOT_FOUND")):
            return (
                "오류",
                f"{df_column} 값으로 담당자, 역할, 그룹을 찾지 못했습니다.",
                "입력값을 확인하고, 대상 사용자가 프로젝트 역할 또는 그룹에 포함되는지 점검하세요.",
            )
        return (
            "안내",
            str(row.get("error") or row.get("detail") or status or ""),
            "내용을 확인한 뒤 필요하면 매핑이나 입력값을 조정하세요.",
        )

    @staticmethod
    def _parse_payload_error(payload_error: str) -> dict[str, str]:
        work = str(payload_error or "").strip()
        parsed = {
            "code": "",
            "field": "",
            "df_column": "",
            "row_id": "",
            "detail": work,
        }
        if not work.startswith("[") or "]" not in work:
            return parsed

        code_end = work.find("]")
        parsed["code"] = work[1:code_end].strip()
        remainder = work[code_end + 1 :].strip()

        for key, token in (("field", "field='"), ("df_column", "df_column='")):
            token_index = remainder.find(token)
            if token_index >= 0:
                value_start = token_index + len(token)
                value_end = remainder.find("'", value_start)
                if value_end > value_start:
                    parsed[key] = remainder[value_start:value_end]

        row_token = "_row_id="
        row_index = remainder.find(row_token)
        if row_index >= 0:
            row_start = row_index + len(row_token)
            row_end = remainder.find(" ", row_start)
            parsed["row_id"] = remainder[row_start:] if row_end < 0 else remainder[row_start:row_end]

        detail_start = remainder.find(" ", row_index + len(row_token)) if row_index >= 0 else -1
        if detail_start >= 0:
            parsed["detail"] = remainder[detail_start + 1 :].strip()
        elif remainder:
            parsed["detail"] = remainder
        return parsed

    @classmethod
    def _message_from_payload_error(cls, row: pd.Series) -> tuple[str, str, str, str]:
        payload_error = str(row.get("payload_error") or "").strip()
        parsed = cls._parse_payload_error(payload_error)
        code = parsed["code"]
        field = parsed["field"] or str(row.get("upload_name") or "")
        column = parsed["df_column"]
        detail = parsed["detail"]

        if code == "FIELD_UNSUPPORTED":
            return (
                column,
                field,
                "현재 GUI에서 지원하지 않는 필드가 포함되어 있습니다.",
                "매핑에서 해당 컬럼 사용을 끄거나 다른 필드로 바꾼 뒤 다시 검증하세요.",
            )
        if code == "LOOKUP_REQUIRED":
            return (
                column,
                field,
                "필요한 값을 찾지 못해 업로드용 데이터를 만들 수 없습니다.",
                "입력값을 확인하거나, 지원되는 필드와 값으로 수정한 뒤 다시 검증하세요.",
            )
        if code == "DIRECT_PARSE_FAILED":
            return (
                column,
                field,
                "입력값을 아이디 형식으로 해석하지 못했습니다.",
                "숫자 ID처럼 허용되는 형식으로 값을 수정한 뒤 다시 검증하세요.",
            )
        if code == "OPTION_RESOLUTION_FAILED":
            return (
                column,
                field,
                "선택값을 업로드 형식으로 변환하지 못했습니다.",
                "Excel 값이나 기본값이 트래커 옵션 이름과 정확히 일치하는지 확인하세요.",
            )

        if detail:
            return (
                column,
                field,
                detail,
                "문구를 확인하고 매핑 또는 입력값을 수정한 뒤 다시 검증하세요.",
            )
        return (
            column,
            field,
            "업로드용 데이터를 만들 수 없습니다.",
            "문구를 확인하고 매핑 또는 입력값을 수정한 뒤 다시 검증하세요.",
        )

    @classmethod
    def _build_summary_stats(
        cls,
        issue_df: pd.DataFrame,
        row_context_df: pd.DataFrame | None,
    ) -> dict[str, int]:
        total_rows = 0
        if row_context_df is not None and not row_context_df.empty and "_row_id" in row_context_df.columns:
            total_rows = len({
                cls._to_row_key(value)
                for value in row_context_df["_row_id"].tolist()
                if cls._to_row_key(value)
            })

        if issue_df is None or issue_df.empty:
            return {
                "total_rows": total_rows,
                "ready_rows": total_rows,
                "error_rows": 0,
                "warning_rows": 0,
                "config_errors": 0,
                "config_warnings": 0,
                "error_count": 0,
                "info_count": 0,
            }

        row_id_series = issue_df["row_id"].fillna("").astype(str).str.strip()
        row_issue_df = issue_df[row_id_series != ""]
        config_issue_df = issue_df[row_id_series == ""]

        error_row_ids = set(
            row_issue_df.loc[row_issue_df["severity"] == "오류", "row_id"].fillna("").astype(str).str.strip()
        )
        error_row_ids.discard("")
        warning_row_ids = set(
            row_issue_df.loc[row_issue_df["severity"] != "오류", "row_id"].fillna("").astype(str).str.strip()
        )
        warning_row_ids.discard("")
        warning_row_ids -= error_row_ids

        ready_rows = total_rows - len(error_row_ids) - len(warning_row_ids)
        if ready_rows < 0:
            ready_rows = 0

        return {
            "total_rows": total_rows,
            "ready_rows": ready_rows,
            "error_rows": len(error_row_ids),
            "warning_rows": len(warning_row_ids),
            "config_errors": int(config_issue_df["severity"].eq("오류").sum()),
            "config_warnings": int(config_issue_df["severity"].eq("안내").sum()),
            "error_count": int(issue_df["severity"].eq("오류").sum()),
            "info_count": int(issue_df["severity"].eq("안내").sum()),
        }

    @classmethod
    def _build_user_issue_df(
        cls,
        comparison_df: pd.DataFrame,
        option_check_df: pd.DataFrame,
        payload_df: pd.DataFrame,
        *,
        row_context_df: pd.DataFrame | None = None,
        selected_default_values: dict[str, str] | None = None,
    ) -> pd.DataFrame:
        row_context_map = cls._build_row_context_map(row_context_df)
        issue_columns = [
            "severity",
            "category",
            "row_id",
            "row_label",
            "item_name",
            "column",
            "field",
            "raw_value",
            "message",
            "action",
        ]
        issues: list[dict[str, str]] = []

        if comparison_df is not None and not comparison_df.empty:
            for _, row in comparison_df.iterrows():
                status = str(row.get("status") or "").strip()
                if status in {MappingStatus.OK.value, "ok", "matched", ""}:
                    continue
                if status in {MappingStatus.UNMAPPED.value, "unmapped"}:
                    # GUI의 `사용` 체크박스로 제외한 컬럼은 업로드 대상이 아니므로 차단하지 않는다.
                    continue
                if status in {MappingStatus.SCHEMA_FIELD_MISSING.value, "schema_field_missing"}:
                    issues.append({
                        "severity": "오류",
                        "category": "매핑",
                        "row_id": "",
                        "row_label": "",
                        "item_name": "",
                        "column": str(row.get("df_column") or ""),
                        "field": str(row.get("selected_schema_field") or ""),
                        "raw_value": "",
                        "message": "선택한 필드를 현재 트래커 스키마에서 찾을 수 없습니다.",
                        "action": "매핑 단계에서 다른 필드를 선택하거나, 해당 컬럼 사용을 끄세요.",
                    })

        if option_check_df is not None and not option_check_df.empty:
            for _, row in option_check_df.iterrows():
                if cls._is_hidden_user_column(row.get("df_column")):
                    continue
                severity, message, action = cls._message_from_option_status(row)
                if not message:
                    continue
                if str(row.get("status") or "") == OptionCheckStatus.PRECONSTRUCTION_REQUIRED.value:
                    continue
                row_key = cls._to_row_key(row.get("_row_id"))
                row_context = cls._row_context(row_key, row_context_map)
                issues.append({
                    "severity": severity,
                    "category": "값 검증",
                    "row_id": row_context["row_id"],
                    "row_label": row_context["row_label"],
                    "item_name": row_context["item_name"],
                    "column": str(row.get("df_column") or ""),
                    "field": str(row.get("schema_field") or ""),
                    "raw_value": cls._display_text(row.get("raw_value")),
                    "message": message,
                    "action": action,
                })

        if payload_df is not None and not payload_df.empty:
            failed_df = payload_df[payload_df["payload_status"] != PayloadStatus.READY.value]
            for _, row in failed_df.iterrows():
                column, field, message, action = cls._message_from_payload_error(row)
                parsed = cls._parse_payload_error(str(row.get("payload_error") or ""))
                row_key = cls._to_row_key(parsed.get("row_id") or row.get("_row_id"))
                row_context = cls._row_context(
                    row_key,
                    row_context_map,
                    fallback_item_name=cls._display_text(row.get("upload_name")),
                )
                raw_value = ""
                if column == DEFAULT_VALUE_COLUMN_LABEL:
                    raw_value = cls._display_text((selected_default_values or {}).get(field))
                elif column:
                    raw_value = cls._raw_value_from_row_context(row_key, column, row_context_map)
                issues.append({
                    "severity": "오류",
                    "category": "Payload 생성",
                    "row_id": row_context["row_id"],
                    "row_label": row_context["row_label"],
                    "item_name": row_context["item_name"],
                    "column": column,
                    "field": field,
                    "raw_value": raw_value,
                    "message": message,
                    "action": action,
                })

        issue_df = pd.DataFrame(issues, columns=issue_columns)
        if issue_df.empty:
            return issue_df
        issue_df = issue_df.drop_duplicates().reset_index(drop=True)
        severity_order = {"오류": 0, "안내": 1}
        issue_df["_sort"] = issue_df["severity"].map(severity_order).fillna(99)
        issue_df["_config_sort"] = issue_df["row_id"].fillna("").astype(str).str.strip().ne("").astype(int)
        issue_df["_row_order"] = pd.to_numeric(issue_df["row_id"], errors="coerce").fillna(10**9)
        issue_df = issue_df.sort_values(
            by=["_sort", "_config_sort", "_row_order", "category", "column", "field"]
        ).drop(columns=["_sort", "_config_sort", "_row_order"])
        return issue_df
