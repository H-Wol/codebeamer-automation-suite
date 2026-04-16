from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pandas as pd

from src.codebeamer_client import CodebeamerClient
from src.excel_reader import ExcelReader
from src.hierarchy_processor import HierarchyProcessor
from src.mapping_service import MappingService
from src.models import OptionCheckStatus
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


@dataclass
class MappingContext:
    wizard: CodebeamerUploadWizard
    schema_df: pd.DataFrame
    upload_columns: list[str]
    selected_mapping: dict[str, str]
    list_cols: list[str]


@dataclass
class ValidationContext:
    comparison_df: pd.DataFrame
    option_check_df: pd.DataFrame
    converted_upload_df: pd.DataFrame
    issue_df: pd.DataFrame
    has_blocking_issues: bool


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
    def _auto_match_columns(
        upload_columns: list[str],
        schema_field_names: set[str],
        table_field_names: set[str] | None = None,
    ) -> dict[str, str]:
        selected_mapping: dict[str, str] = {}
        table_field_names = table_field_names or set()
        for column in upload_columns:
            if column in schema_field_names:
                selected_mapping[column] = column
                continue

            if "." in column:
                potential_table_field = column.split(".", 1)[0].strip()
                if potential_table_field in table_field_names:
                    selected_mapping[column] = potential_table_field
                    continue

            for schema_field in schema_field_names:
                if column.lower() == schema_field.lower():
                    selected_mapping[column] = schema_field
                    break
        return selected_mapping

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

    def prepare_mapping_context(self, settings, file_state: dict[str, Any]) -> MappingContext:
        wizard = self.create_wizard(settings)
        wizard.select_project(int(settings.default_project_id))
        wizard.select_tracker(int(settings.default_tracker_id))

        schema = wizard.client.get_tracker_schema(wizard.state.tracker_id)
        schema_df = self.mapper.flatten_schema_fields(schema)
        mappable_schema_df = schema_df[
            ~schema_df.apply(self._is_gui_excluded_schema_field, axis=1)
        ].reset_index(drop=True)

        preview = self.excel_service.load_preview(
            file_state["file_path"],
            sheet_name=file_state["sheet_name"],
            header_row=int(file_state["header_row"]),
        )
        headers = preview.headers
        table_field_names = set(
            mappable_schema_df[
                mappable_schema_df.get("is_table_field", False).fillna(False)
            ]["field_name"].dropna().astype(str).tolist()
        )
        raw_mapping = self._auto_match_columns(
            headers,
            set(mappable_schema_df["field_name"].dropna().astype(str).str.strip()),
            table_field_names=table_field_names,
        )
        list_cols = self.mapper.get_list_columns_for_mapping(raw_mapping, mappable_schema_df)

        reader = wizard.reader
        if reader is None:
            raise ValueError("wizard.reader 가 준비되지 않았습니다.")
        reader.header_row = int(file_state["header_row"])
        reader.summary_col = str(file_state["summary_column"])
        raw_df = reader.read_excel(
            file_path=file_state["file_path"],
            sheet_name=file_state["sheet_name"],
        )
        wizard.load_raw_dataframe(raw_df, list_cols=list_cols)
        wizard.state.schema = schema
        wizard.state.schema_df = schema_df
        wizard._detect_table_field_columns()

        upload_columns = self._gui_upload_columns(wizard.state.upload_df)
        selected_mapping = {
            column: schema_field
            for column, schema_field in raw_mapping.items()
            if column in upload_columns
        }

        return MappingContext(
            wizard=wizard,
            schema_df=mappable_schema_df,
            upload_columns=upload_columns,
            selected_mapping=selected_mapping,
            list_cols=list_cols,
        )

    def validate_mapping(
        self,
        mapping_context: MappingContext,
        selected_mapping: dict[str, str],
    ) -> ValidationContext:
        wizard = mapping_context.wizard
        list_cols = self.mapper.get_list_columns_for_mapping(selected_mapping, mapping_context.schema_df)
        wizard.load_raw_dataframe(wizard.state.raw_df.copy(), list_cols=list_cols)
        comparison_df = wizard.load_schema_and_compare(selected_mapping)
        comparison_df = self._gui_visible_comparison_df(comparison_df)
        _, option_check_df = wizard.process_option_mapping(selected_mapping)
        option_check_df = option_check_df if option_check_df is not None else pd.DataFrame()

        has_blocking = False
        if not option_check_df.empty:
            status_series = option_check_df["status"].fillna("").astype(str)
            has_blocking = bool(
                status_series.isin(BLOCKING_OPTION_STATUSES).any()
                or status_series.str.endswith(USER_LOOKUP_FAILURE_SUFFIXES).any()
            )

        payload_df = wizard.build_payloads(force=True)
        if not payload_df.empty and (payload_df["payload_status"] != "ready").any():
            has_blocking = True

        issue_df = self._build_user_issue_df(comparison_df, option_check_df, payload_df)
        if not issue_df.empty and issue_df["severity"].eq("오류").any():
            has_blocking = True

        return ValidationContext(
            comparison_df=comparison_df,
            option_check_df=option_check_df,
            converted_upload_df=wizard.state.converted_upload_df,
            issue_df=issue_df,
            has_blocking_issues=has_blocking,
        )

    @staticmethod
    def _message_from_option_status(row: pd.Series) -> tuple[str, str]:
        status = str(row.get("status") or "")
        field_name = str(row.get("schema_field") or "")
        df_column = str(row.get("df_column") or "")
        value = row.get("raw_value")

        if status == OptionCheckStatus.FIELD_UNSUPPORTED.value:
            return "오류", f"현재 GUI에서 지원하지 않는 필드입니다. 필드: {field_name}"
        if status == OptionCheckStatus.LOOKUP_REQUIRED.value:
            return "오류", f"추가 조회 로직이 필요한 필드입니다. 필드: {field_name}"
        if status == OptionCheckStatus.OPTION_NOT_FOUND.value:
            return "오류", f"선택값을 찾을 수 없습니다. 컬럼: {df_column}"
        if status == OptionCheckStatus.DIRECT_PARSE_FAILED.value:
            return "오류", f"아이디 형식으로 해석할 수 없습니다. 컬럼: {df_column}"
        if status.endswith(("USER_LOOKUP_FAILED", "USER_LOOKUP_AMBIGUOUS", "USER_NOT_FOUND")):
            return "오류", f"사용자를 찾지 못했습니다. 컬럼: {df_column}"
        if status.endswith(("MEMBER_LOOKUP_FAILED", "MEMBER_LOOKUP_AMBIGUOUS", "MEMBER_NOT_FOUND")):
            return "오류", f"담당자/역할/그룹을 찾지 못했습니다. 컬럼: {df_column}"
        if status == OptionCheckStatus.PRECONSTRUCTION_REQUIRED.value:
            return "안내", f"업로드 전에 내부 변환이 필요한 필드입니다. 필드: {field_name}"
        return "안내", str(row.get("error") or row.get("detail") or status or value or "")

    @classmethod
    def _build_user_issue_df(
        cls,
        comparison_df: pd.DataFrame,
        option_check_df: pd.DataFrame,
        payload_df: pd.DataFrame,
    ) -> pd.DataFrame:
        issues: list[dict[str, str]] = []

        if comparison_df is not None and not comparison_df.empty:
            for _, row in comparison_df.iterrows():
                status = str(row.get("status") or "")
                if status in {"ok", "matched", ""}:
                    continue
                if status == "unmapped":
                    issues.append({
                        "severity": "오류",
                        "category": "매핑",
                        "column": str(row.get("df_column") or ""),
                        "field": "",
                        "message": "Codebeamer 필드에 연결되지 않은 컬럼입니다.",
                    })
                elif status == "schema_field_missing":
                    issues.append({
                        "severity": "오류",
                        "category": "매핑",
                        "column": str(row.get("df_column") or ""),
                        "field": str(row.get("selected_schema_field") or ""),
                        "message": "선택한 필드를 현재 트래커 스키마에서 찾을 수 없습니다.",
                    })

        if option_check_df is not None and not option_check_df.empty:
            for _, row in option_check_df.iterrows():
                severity, message = cls._message_from_option_status(row)
                if not message:
                    continue
                issues.append({
                    "severity": severity,
                    "category": "값 검증",
                    "column": str(row.get("df_column") or ""),
                    "field": str(row.get("schema_field") or ""),
                    "message": message,
                })

        if payload_df is not None and not payload_df.empty:
            failed_df = payload_df[payload_df["payload_status"] != "ready"]
            for _, row in failed_df.iterrows():
                issues.append({
                    "severity": "오류",
                    "category": "Payload 생성",
                    "column": "",
                    "field": str(row.get("upload_name") or ""),
                    "message": str(row.get("payload_error") or "Payload를 만들지 못했습니다."),
                })

        issue_df = pd.DataFrame(issues)
        if issue_df.empty:
            return issue_df
        issue_df = issue_df.drop_duplicates().reset_index(drop=True)
        severity_order = {"오류": 0, "안내": 1}
        issue_df["_sort"] = issue_df["severity"].map(severity_order).fillna(99)
        issue_df = issue_df.sort_values(by=["_sort", "category", "column", "field"]).drop(columns=["_sort"])
        return issue_df
