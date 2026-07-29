from __future__ import annotations

from dataclasses import dataclass
from dataclasses import field
import json
from pathlib import Path
import re
import time
from typing import Any

import pandas as pd

from src.codebeamer_client import CodebeamerClient
from src.excel_reader import ExcelReader
from src.hierarchy_processor import HierarchyProcessor
from src.models import MappingStatus
from src.mapping_service import MappingService
from src.models import OptionMapKind
from src.models import OptionCheckStatus
from src.models import PayloadStatus
from src.models import TrackerItemQueryMatchStrategy
from src.models import TrackerItemResolutionMode
from src.upload_pipeline import load_tracker_schema_df
from src.upload_pipeline import prepare_upload_dataframe
from src.upload_pipeline import run_validation_pipeline
from src.upload_pipeline import suggest_mapping_from_headers
from src.upload_policy import UPLOAD_MODE_CREATE as GUI_UPLOAD_MODE_CREATE
from src.upload_policy import UPLOAD_MODE_UPDATE as GUI_UPLOAD_MODE_UPDATE
from src.upload_policy import UPLOAD_MODE_UPSERT as GUI_UPLOAD_MODE_UPSERT
from src.upload_policy import normalize_upload_mode as normalize_gui_upload_mode
from src.upload_policy import upload_mode_action_label as gui_upload_mode_action_label
from src.upload_policy import upload_mode_allows_root_items as gui_upload_mode_allows_root_items
from src.upload_policy import upload_mode_supports_update as gui_upload_mode_supports_update
from src.wizard import CodebeamerUploadWizard


@dataclass
class PreviewData:
    file_path: str
    sheet_name: str
    header_row: int
    summary_column: str
    sheet_names: list[str]
    headers: list[str]
    rows: list[list[str]]
    suggested_summary: str
    raw_df: pd.DataFrame
    raw_df_by_file: dict[str, pd.DataFrame] = field(default_factory=dict)


def gui_display_text(value: Any) -> str:
    """`gui_display_text` 관련 처리를 수행한다."""
    if value is None:
        return ""
    if isinstance(value, float) and pd.isna(value):
        return ""
    if isinstance(value, list):
        return ", ".join(part for part in (gui_display_text(item) for item in value) if part)
    if isinstance(value, dict):
        if value.get("name") is not None:
            return str(value.get("name")).strip()
        return str(value).strip()
    text = str(value).strip()
    return "" if text.lower() == "nan" else text


DEFAULT_OFFLINE_PROJECT_ID = 1
DEFAULT_OFFLINE_TRACKER_ID = 1
DEFAULT_OFFLINE_PROJECT_NAME = "Offline Project"
DEFAULT_OFFLINE_TRACKER_NAME = "Offline Tracker"


def _normalize_offline_id(value: Any, default_value: int) -> int:
    """`normalize_offline_id` 값을 정규화한다."""
    try:
        normalized = int(value)
    except Exception:
        return default_value
    return normalized if normalized > 0 else default_value


def _load_json_snapshot(path_value: Any, *, label: str) -> Any:
    """`load_json_snapshot` 관련 처리를 수행한다."""
    path_text = str(path_value or "").strip()
    if not path_text:
        raise ValueError(f"{label} 경로가 비어 있습니다.")

    snapshot_path = Path(path_text).expanduser()
    if not snapshot_path.is_file():
        raise ValueError(f"{label} 파일을 찾을 수 없습니다: {snapshot_path}")

    try:
        return json.loads(snapshot_path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise ValueError(f"{label} JSON을 읽을 수 없습니다: {exc}") from exc


class OfflineGuiClient:
    """로컬 schema/config snapshot만으로 GUI 오프라인 테스트를 지원한다."""

    def __init__(
        self,
        *,
        schema: dict[str, Any],
        schema_path: str,
        tracker_configuration: Any = None,
        project_id: int = DEFAULT_OFFLINE_PROJECT_ID,
        tracker_id: int = DEFAULT_OFFLINE_TRACKER_ID,
    ) -> None:
        """필요한 의존성과 상태를 초기화한다."""
        self.schema = dict(schema or {})
        self.schema_path = str(schema_path)
        self.tracker_configuration = tracker_configuration
        self.project_id = int(project_id)
        self.tracker_id = int(tracker_id)
        self.project_name = DEFAULT_OFFLINE_PROJECT_NAME
        self.tracker_name = (
            str(self.schema.get("name") or "").strip()
            or Path(self.schema_path).stem
            or DEFAULT_OFFLINE_TRACKER_NAME
        )

    @classmethod
    def from_settings(cls, settings) -> "OfflineGuiClient":
        """`from_settings` 관련 처리를 수행한다."""
        schema_path = str(getattr(settings, "offline_schema_path", "") or "").strip()
        schema = _load_json_snapshot(schema_path, label="테스트 schema")
        tracker_configuration = None
        configuration_path = str(
            getattr(settings, "offline_tracker_configuration_path", "") or ""
        ).strip()
        if configuration_path:
            tracker_configuration = _load_json_snapshot(
                configuration_path,
                label="테스트 tracker configuration",
            )
        return cls(
            schema=schema,
            schema_path=schema_path,
            tracker_configuration=tracker_configuration,
            project_id=_normalize_offline_id(
                getattr(settings, "default_project_id", ""),
                DEFAULT_OFFLINE_PROJECT_ID,
            ),
            tracker_id=_normalize_offline_id(
                getattr(settings, "default_tracker_id", ""),
                DEFAULT_OFFLINE_TRACKER_ID,
            ),
        )

    def get_projects(self) -> list[dict[str, Any]]:
        """`get_projects` 값을 반환한다."""
        return [{"id": self.project_id, "name": self.project_name}]

    def get_trackers(self, project_id: int) -> list[dict[str, Any]]:
        """`get_trackers` 값을 반환한다."""
        del project_id
        return [{"id": self.tracker_id, "name": self.tracker_name}]

    def get_tracker_schema(self, tracker_id: int) -> dict[str, Any]:
        """`get_tracker_schema` 값을 반환한다."""
        del tracker_id
        return self.schema

    def get_tracker_configuration(self, tracker_id: int) -> Any:
        """`get_tracker_configuration` 값을 반환한다."""
        del tracker_id
        if self.tracker_configuration is None:
            raise RuntimeError("offline tracker configuration snapshot is not configured")
        return self.tracker_configuration

    def create_item(self, tracker_id: int, payload: dict[str, Any], parent_item_id: int | None = None) -> dict[str, Any]:
        """`create_item` 화면을 구성한다."""
        del tracker_id, payload, parent_item_id
        raise RuntimeError("테스트 모드에서는 실제 업로드를 실행할 수 없습니다. Dry Run만 사용해야 합니다.")

    def update_item(self, item_id: int, payload: dict[str, Any]) -> dict[str, Any]:
        """`update_item` 상태를 갱신한다."""
        del item_id, payload
        raise RuntimeError("테스트 모드에서는 업데이트를 실행할 수 없습니다. Dry Run만 사용해야 합니다.")

    def get_item(self, item_id: int) -> dict[str, Any]:
        """`get_item` 값을 반환한다."""
        raise RuntimeError(f"offline snapshot does not provide item lookup by id: {item_id}")

    def get_user(self, user_id: int):
        """`get_user` 값을 반환한다."""
        raise RuntimeError(f"offline snapshot does not provide user lookup by id: {user_id}")

    def get_user_by_name(self, name: str):
        """`get_user_by_name` 값을 반환한다."""
        raise RuntimeError(f"offline snapshot does not provide user lookup by name: {name}")

    def get_user_groups(self):
        """`get_user_groups` 값을 반환한다."""
        raise RuntimeError("offline snapshot does not provide user groups")

    def get_tracker_field_permissions(self, tracker_id: int, field_id: int):
        """`get_tracker_field_permissions` 값을 반환한다."""
        raise RuntimeError(
            f"offline snapshot does not provide field permissions: {tracker_id}/{field_id}"
        )

    def search_tracker_items_by_name(self, *, tracker_id: int, name: str, **kwargs):
        """`search_tracker_items_by_name` 관련 처리를 수행한다."""
        del tracker_id, name, kwargs
        raise RuntimeError("offline snapshot does not provide tracker item lookup")


def _build_gui_client(settings, client_factory, logger=None):
    """`build_gui_client` 결과를 구성한다."""
    if bool(getattr(settings, "offline_mode", False)):
        return OfflineGuiClient.from_settings(settings)
    return client_factory(
        settings.base_url,
        settings.username,
        settings.password,
        logger,
        rate_limit_retry_delay_seconds=settings.rate_limit_retry_delay_seconds,
        rate_limit_max_retries=settings.rate_limit_max_retries,
    )


class GuiCodebeamerService:
    """GUI 에서 사용하는 최소 Codebeamer 조회 기능을 제공한다."""

    def __init__(self, client_factory=CodebeamerClient, logger=None) -> None:
        """필요한 의존성과 상태를 초기화한다."""
        self.client_factory = client_factory
        self.logger = logger

    def _build_client(self, settings):
        """`build_client` 결과를 구성한다."""
        return _build_gui_client(settings, self.client_factory, self.logger)

    @staticmethod
    def _normalize_items(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """`normalize_items` 값을 정규화한다."""
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
        """`test_connection_and_load_projects` 관련 처리를 수행한다."""
        projects = self._build_client(settings).get_projects()
        return self._normalize_items(projects)

    def load_trackers(self, settings, project_id: int) -> list[dict[str, Any]]:
        """`load_trackers` 데이터를 불러온다."""
        trackers = self._build_client(settings).get_trackers(project_id)
        return self._normalize_items(trackers)


class GuiExcelService:
    """GUI 파일 선택 화면에서 사용하는 Excel 메타데이터와 미리보기를 제공한다."""

    def __init__(self, logger=None, *, reader_cls=ExcelReader) -> None:
        """필요한 의존성과 상태를 초기화한다."""
        self.logger = logger
        self.reader_cls = reader_cls

    @staticmethod
    def _normalize_headers(values: list[Any]) -> list[str]:
        """`normalize_headers` 값을 정규화한다."""
        headers: list[str] = []
        for index, value in enumerate(values):
            if value is None:
                headers.append(f"Unnamed_{index}")
            else:
                headers.append(str(value).strip())
        return headers

    @staticmethod
    def _suggest_summary(headers: list[str]) -> str:
        """`suggest_summary` 관련 처리를 수행한다."""
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
        file_paths: list[str] | None = None,
        sheet_name: str | None = None,
        header_row: int = 1,
        summary_column: str | None = None,
        max_preview_rows: int = 10,
    ) -> PreviewData:
        """`load_preview` 데이터를 불러온다."""
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
        target_summary = str(summary_column or "").strip() or suggested_summary
        if target_summary not in headers:
            target_summary = suggested_summary
        data_reader = self.reader_cls(
            header_row=header_row,
            summary_col=target_summary,
            logger=self.logger,
        )
        raw_df = data_reader.read_excel(file_path=file_path, sheet_name=target_sheet_name)
        raw_df_by_file: dict[str, pd.DataFrame] = {
            str(file_path).strip(): raw_df,
        }
        for other_file_path in file_paths or []:
            normalized_file_path = str(other_file_path).strip()
            if not normalized_file_path or normalized_file_path in raw_df_by_file:
                continue
            raw_df_by_file[normalized_file_path] = data_reader.read_excel(
                file_path=normalized_file_path,
                sheet_name=target_sheet_name,
            )

        preview_headers = [header for header in headers if not str(header).startswith("_")]
        preview_rows: list[list[str]] = []
        if not raw_df.empty:
            visible_df = raw_df[preview_headers].head(max_preview_rows)
            for _, row in visible_df.iterrows():
                preview_rows.append([gui_display_text(value) for value in row.tolist()])

        return PreviewData(
            file_path=str(file_path),
            sheet_name=str(target_sheet_name),
            header_row=int(header_row),
            summary_column=target_summary,
            sheet_names=sheet_names,
            headers=preview_headers,
            rows=preview_rows,
            suggested_summary=suggested_summary,
            raw_df=raw_df,
            raw_df_by_file=raw_df_by_file,
        )
