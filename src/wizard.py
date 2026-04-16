from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd

from .codebeamer_client import CodebeamerClient
from .excel_reader import ExcelReader
from .hierarchy_processor import HierarchyProcessor
from .mapping_service import MappingService
from .models import DomainModel
from .models import FieldValueType
from .models import OptionMapKind
from .models import PayloadStatus
from .models import ReferenceType
from .models import ResolvedFieldKind
from .models import GroupReference
from .models import RoleReference
from .models import TableFieldValue
from .models import TrackerItemBase
from .models import UploadStatus
from .models import UserInfo
from .models import UserGroupReference
from .models import UserLookupStatus
from .models import WizardState


UserLookupCacheEntry = tuple[dict[str, Any] | None, dict[str, Any] | None, str, str | None]
MemberLookupCacheEntry = tuple[dict[str, Any] | None, dict[str, Any] | None, str, str | None]


class CodebeamerUploadWizard:
    def __init__(
        self,
        client: CodebeamerClient,
        processor: HierarchyProcessor | None,
        mapper: MappingService,
        reader: ExcelReader | None = None,
        logger=None,
    ):
        """업로드 전체 흐름을 묶어 실행하는 조정 객체를 만든다."""
        self.client = client
        self.reader = reader
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
            self.state.member_lookup_cache.clear()
            self.state.group_lookup_cache.clear()
            self.state.tracker_role_cache.clear()
            self._invalidate_payload_cache()
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
        if self.state.tracker_id != tracker_id:
            self.state.member_lookup_cache.clear()
            self.state.tracker_role_cache.clear()
            self._invalidate_payload_cache()
        self.state.tracker_id = tracker_id

    def _invalidate_payload_cache(self) -> None:
        """입력/매핑/schema가 바뀌면 payload cache를 비운다."""
        self.state.payload_df = None

    def load_raw_dataframe(self, raw_df: pd.DataFrame, list_cols: list[str] | None = None) -> None:
        """reader가 만든 raw DataFrame을 업로드용 중간 DataFrame들로 후처리한다."""
        if self.processor is None:
            raise ValueError("processor is required to transform raw dataframe.")

        if list_cols is None:
            list_cols = []

        self.state.list_cols = list_cols
        self.state.raw_df = raw_df.copy()
        self.state.merged_df = self.processor.merge_multiline_records(self.state.raw_df, list_cols=list_cols)
        self.state.hierarchy_df = self.processor.add_hierarchy_by_indent(self.state.merged_df)
        self.state.upload_df = self.processor.build_upload_df(self.state.hierarchy_df, list_cols=list_cols)
        self.state.converted_upload_df = None
        self.state.table_field_mapping = {}
        self.state.upload_result = None
        self._invalidate_payload_cache()

    def read_excel(self, file_path: str, sheet_name: str | int = 0, list_cols: list[str] | None = None) -> None:
        """호환용 메서드다. reader로 raw DataFrame을 만든 뒤 processor로 후처리한다."""
        if self.reader is not None:
            raw_df = self.reader.read_excel(file_path=file_path, sheet_name=sheet_name)
        elif self.processor is not None and hasattr(self.processor, "read_excel"):
            raw_df = self.processor.read_excel(file_path=file_path, sheet_name=sheet_name)
        else:
            raise ValueError("reader or compatible processor.read_excel() is required to load Excel files.")
        self.load_raw_dataframe(raw_df, list_cols=list_cols)

    def _payload_source_df(self) -> pd.DataFrame:
        if self.state.converted_upload_df is not None:
            return self.state.converted_upload_df
        if self.state.upload_df is not None:
            return self.state.upload_df
        raise ValueError("No upload dataframe is available.")

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
        self._invalidate_payload_cache()

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

    @staticmethod
    def _response_json(exc: Exception) -> Any:
        """예외 안의 HTTP 응답 JSON을 안전하게 꺼낸다."""
        response = getattr(exc, "response", None)
        if response is None:
            return None
        try:
            return response.json()
        except Exception:
            return None

    def _user_lookup_cache_key(self, value: Any) -> tuple[int | None, str]:
        """현재 프로젝트 기준으로 사용자 lookup 캐시 키를 만든다."""
        return (self.state.project_id, self._normalize_lookup_text(value).casefold())

    @classmethod
    def _user_lookup_aliases(cls, user_info: dict[str, Any] | None) -> set[str]:
        """한 사용자를 다시 찾기 쉬우도록 이름과 ID를 별칭으로 만든다."""
        if not user_info:
            return set()

        return {
            normalized.casefold()
            for value in [
                user_info.get("id"),
                user_info.get("name"),
            ]
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
    def _parse_user_id(cls, raw_value: Any) -> int | None:
        """사용자 lookup 입력이 숫자 문자열이면 정수 ID로 해석한다."""
        lookup_text = cls._normalize_lookup_text(raw_value)
        if not lookup_text:
            return None
        if lookup_text.isdigit():
            return int(lookup_text)
        return None

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
        """사용자 이름을 우선 사용하고 필요시 ID로 fallback 하여 reference와 상세 정보를 돌려준다."""
        lookup_text = self._normalize_lookup_text(raw_value)
        cache_key = self._user_lookup_cache_key(lookup_text)
        if cache_key in self.state.user_lookup_cache:
            return self.state.user_lookup_cache[cache_key]

        try:
            if not lookup_text:
                raise ValueError("user lookup text is empty")

            try:
                direct_match = self.client.get_user_by_name(lookup_text)
            except Exception as exc:
                if self._http_status_code(exc) != 404:
                    raise
                direct_match = None

            if direct_match is None:
                user_id = self._parse_user_id(raw_value)
                if user_id is not None:
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

    def _member_lookup_cache_key(
        self,
        field_id: int | None,
        lookup_text: Any,
    ) -> tuple[int | None, int | None, int | None, str]:
        """MemberField lookup 결과 캐시 키를 만든다."""
        return (
            self.state.project_id,
            self.state.tracker_id,
            field_id,
            self._normalize_lookup_text(lookup_text).casefold(),
        )

    @classmethod
    def _reference_payload_to_info(cls, payload: dict[str, Any] | None) -> dict[str, Any] | None:
        """reference payload를 lookup 결과 정보 형태로 정리한다."""
        if payload is None:
            return None
        return {
            "id": payload.get("id"),
            "name": payload.get("name"),
            "type": payload.get("type"),
        }

    @staticmethod
    def _normalize_member_name_key(value: Any) -> str:
        """role/group 이름 비교용 정규화 키를 만든다."""
        if value is None:
            return ""
        return str(value).strip().casefold()

    @staticmethod
    def _extract_group_references(data: Any) -> list[dict[str, Any]]:
        """사용자 그룹 목록 응답에서 그룹 reference 후보를 평탄화한다."""
        if isinstance(data, list):
            return [item for item in data if isinstance(item, dict)]
        if isinstance(data, dict):
            for key in ("groups", "groupReferences", "items", "references"):
                value = data.get(key)
                if isinstance(value, list):
                    return [item for item in value if isinstance(item, dict)]
        return []

    @staticmethod
    def _extract_role_references(permission_matrix: Any) -> list[dict[str, Any]]:
        """field permission matrix에서 RoleReference 목록을 추출한다."""
        roles: dict[int, dict[str, Any]] = {}
        if not isinstance(permission_matrix, list):
            return []
        for status_row in permission_matrix:
            if not isinstance(status_row, dict):
                continue
            permissions = status_row.get("permissions") or []
            for permission_row in permissions:
                if not isinstance(permission_row, dict):
                    continue
                role = permission_row.get("role")
                if not isinstance(role, dict):
                    continue
                if role.get("id") is None:
                    continue
                normalized = dict(role)
                normalized.setdefault("type", ReferenceType.ROLE.value)
                roles[int(normalized["id"])] = normalized
        return list(roles.values())

    def _group_candidates(self) -> dict[str, list[dict[str, Any]]]:
        """전체 그룹 후보를 이름 키로 캐시한다."""
        cached = self.state.group_lookup_cache
        if cached:
            return cached

        grouped: dict[str, list[dict[str, Any]]] = {}
        for raw in self._extract_group_references(self.client.get_user_groups()):
            ref_type = raw.get("type") or ReferenceType.USER_GROUP.value
            key = self._normalize_member_name_key(raw.get("name"))
            if not key or raw.get("id") is None:
                continue
            grouped.setdefault(f"GROUP:{key}", []).append({
                "id": raw.get("id"),
                "name": raw.get("name"),
                "type": ref_type,
            })

        self.state.group_lookup_cache = grouped
        return grouped

    def _tracker_role_candidates(self, field_id: int | None) -> dict[str, list[dict[str, Any]]]:
        """현재 트래커/필드 기준 role 후보를 이름 키로 캐시한다."""
        if self.state.project_id is None or self.state.tracker_id is None or field_id is None:
            return {}
        cache_key = (self.state.project_id, self.state.tracker_id, int(field_id))
        cached = self.state.tracker_role_cache.get(cache_key)
        if cached is not None:
            return cached

        grouped: dict[str, list[dict[str, Any]]] = {}
        for role in self._extract_role_references(
            self.client.get_tracker_field_permissions(self.state.tracker_id, int(field_id))
        ):
            key = self._normalize_member_name_key(role.get("name"))
            if not key:
                continue
            grouped.setdefault(f"ROLE:{key}", []).append({
                "id": role.get("id"),
                "name": role.get("name"),
                "type": role.get("type") or ReferenceType.ROLE.value,
            })

        self.state.tracker_role_cache[cache_key] = grouped
        return grouped

    def _build_member_reference(self, candidate: dict[str, Any]) -> dict[str, Any]:
        """member lookup 후보를 업로드용 reference payload로 정리한다."""
        ref_type = candidate.get("type") or ReferenceType.ABSTRACT.value
        if ref_type == ReferenceType.USER.value:
            return UserInfo(id=int(candidate["id"]), name=candidate.get("name")).to_reference().to_dict()
        if ref_type == ReferenceType.ROLE.value:
            return RoleReference(id=int(candidate["id"]), name=candidate.get("name"), type=ReferenceType.ROLE.value).to_dict()
        if ref_type in {ReferenceType.GROUP.value, ReferenceType.USER_GROUP.value}:
            if ref_type == ReferenceType.GROUP.value:
                return GroupReference(
                    id=int(candidate["id"]),
                    name=candidate.get("name"),
                    type=ReferenceType.GROUP.value,
                ).to_dict()
            return UserGroupReference(
                id=int(candidate["id"]),
                name=candidate.get("name"),
                type=ReferenceType.USER_GROUP.value,
            ).to_dict()
        return {
            "id": int(candidate["id"]),
            "name": candidate.get("name"),
            "type": ref_type,
        }

    def _lookup_member_reference(
        self,
        raw_value: Any,
        *,
        field_id: int | None,
        member_types: list[str] | None,
    ) -> MemberLookupCacheEntry:
        """MemberField 값을 USER/ROLE/GROUP 후보에서 이름 기준으로 찾는다."""
        lookup_text = self._normalize_lookup_text(raw_value)
        cache_key = self._member_lookup_cache_key(field_id, lookup_text)
        if cache_key in self.state.member_lookup_cache:
            return self.state.member_lookup_cache[cache_key]

        try:
            if not lookup_text:
                raise ValueError("member lookup text is empty")

            allowed_types = [str(member_type).strip().upper() for member_type in (member_types or []) if str(member_type).strip()]
            if not allowed_types:
                allowed_types = ["USER"]

            matches: list[dict[str, Any]] = []

            if "USER" in allowed_types:
                user_resolved, user_info, user_status, user_error = self._lookup_user_reference(lookup_text)
                if user_resolved is not None and user_status == UserLookupStatus.RESOLVED.value:
                    matches.append(user_resolved)
                elif user_error and user_status not in {
                    UserLookupStatus.USER_NOT_FOUND.value,
                    UserLookupStatus.USER_LOOKUP_NOT_RUN.value,
                }:
                    entry = (None, None, UserLookupStatus.MEMBER_LOOKUP_FAILED.value, user_error)
                    self.state.member_lookup_cache[cache_key] = entry
                    return entry

            member_name_key = self._normalize_member_name_key(lookup_text)
            if "GROUP" in allowed_types:
                matches.extend(self._group_candidates().get(f"GROUP:{member_name_key}", []))
            if "ROLE" in allowed_types:
                matches.extend(self._tracker_role_candidates(field_id).get(f"ROLE:{member_name_key}", []))

            unique_matches: dict[tuple[int, str], dict[str, Any]] = {}
            for match in matches:
                if match.get("id") is None or match.get("type") is None:
                    continue
                unique_matches[(int(match["id"]), str(match["type"]))] = match

            if len(unique_matches) == 1:
                candidate = next(iter(unique_matches.values()))
                resolved = self._build_member_reference(candidate)
                info = self._reference_payload_to_info(resolved)
                entry = (resolved, info, UserLookupStatus.RESOLVED.value, None)
                self.state.member_lookup_cache[cache_key] = entry
                return entry

            if len(unique_matches) > 1:
                entry = (
                    None,
                    None,
                    UserLookupStatus.MEMBER_LOOKUP_AMBIGUOUS.value,
                    f"Ambiguous member name: {lookup_text!r}",
                )
                self.state.member_lookup_cache[cache_key] = entry
                return entry

            entry = (None, None, UserLookupStatus.MEMBER_NOT_FOUND.value, None)
            self.state.member_lookup_cache[cache_key] = entry
            return entry
        except Exception as exc:
            entry = (None, None, UserLookupStatus.MEMBER_LOOKUP_FAILED.value, str(exc))
            self.state.member_lookup_cache[cache_key] = entry
            return entry

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

    def _resolve_member_reference_value(
        self,
        raw_value: Any,
        *,
        multiple_values: bool,
        field_id: int | None,
        member_types: list[str] | None,
    ) -> tuple[Any, Any, str | None, str | None]:
        """단일 값 또는 목록 값을 member reference 형태로 해석한다."""
        if multiple_values and isinstance(raw_value, list):
            resolved_values = []
            member_infos = []
            for item in raw_value:
                if item is None or self._normalize_lookup_text(item) == "":
                    continue
                resolved, member_info, status, error = self._lookup_member_reference(
                    item,
                    field_id=field_id,
                    member_types=member_types,
                )
                if resolved is None:
                    return None, None, status, error
                resolved_values.append(resolved)
                member_infos.append(member_info)
            return (
                resolved_values if resolved_values else None,
                member_infos if member_infos else None,
                UserLookupStatus.RESOLVED.value,
                None,
            )

        return self._lookup_member_reference(
            raw_value,
            field_id=field_id,
            member_types=member_types,
        )

    def _resolve_member_reference_fields(
        self,
        upload_df: pd.DataFrame,
        option_mapping: dict[str, str],
        option_maps: dict[str, dict],
    ) -> pd.DataFrame:
        """MemberField 값을 미리 찾아 `__resolved` 컬럼에 넣는다."""
        work = upload_df.copy()

        for df_col, schema_field in option_mapping.items():
            option_info = option_maps.get(schema_field, {})
            if option_info.get("kind") != OptionMapKind.MEMBER_LOOKUP.value:
                continue

            resolved_values = []
            member_infos = []
            statuses = []
            errors = []
            multiple_values = option_info.get("multiple_values", False)
            field_id = option_info.get("field_id")
            member_types = option_info.get("member_types") or []

            for _, row in work.iterrows():
                raw_value = row[df_col]
                if raw_value is None or (isinstance(raw_value, str) and raw_value.strip() == ""):
                    resolved_values.append(None)
                    member_infos.append(None)
                    statuses.append(None)
                    errors.append(None)
                    continue

                resolved, member_info, status, error = self._resolve_member_reference_value(
                    raw_value,
                    multiple_values=multiple_values,
                    field_id=field_id,
                    member_types=member_types,
                )
                resolved_values.append(resolved)
                member_infos.append(member_info)
                statuses.append(status)
                errors.append(error)

            work[f"{df_col}__resolved"] = resolved_values
            work[f"{df_col}__user_info"] = member_infos
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
            self._invalidate_payload_cache()
            return {}, pd.DataFrame()

        self.state.selected_option_mapping = selected_option_mapping
        option_maps = self.mapper.build_option_maps_from_schema(self.state.schema_df)
        self.state.option_maps = option_maps

        lookup_ready_df = self._resolve_user_reference_fields(
            upload_df=self.state.upload_df,
            option_mapping=selected_option_mapping,
            option_maps=option_maps,
        )
        lookup_ready_df = self._resolve_member_reference_fields(
            upload_df=lookup_ready_df,
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
        self._invalidate_payload_cache()

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
        reference_type = field_row.get("reference_type")
        resolved_field_kind = field_row.get("resolved_field_kind")

        if not reference_type and resolved_field_kind == ResolvedFieldKind.TRACKER_ITEM_REFERENCE.value:
            reference_type = ReferenceType.TRACKER_ITEM.value
        if not reference_type and resolved_field_kind == ResolvedFieldKind.USER_REFERENCE.value:
            reference_type = ReferenceType.USER.value
        if not reference_type and resolved_field_kind == ResolvedFieldKind.MEMBER_REFERENCE.value:
            reference_type = ReferenceType.ABSTRACT.value

        return {
            "field_id": field_row.get("field_id"),
            "field_type": field_row.get("field_type"),
            "field_name": schema_field,
            "multiple_values": field_row.get("multiple_values", False),
            "reference_type": reference_type,
            "value_model": field_row.get("value_model"),
            "resolved_field_kind": resolved_field_kind,
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

        if option_info.get("kind") in {
            OptionMapKind.USER_LOOKUP.value,
            OptionMapKind.MEMBER_LOOKUP.value,
        }:
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

        if option_info.get("kind") == OptionMapKind.TRACKER_ITEM_DIRECT.value:
            try:
                return self.mapper.resolve_tracker_item_reference_value(
                    row[df_col],
                    multiple_values=option_info.get("multiple_values", False),
                )
            except Exception as exc:
                self._raise_payload_error(
                    "DIRECT_PARSE_FAILED",
                    schema_field=schema_field,
                    df_col=df_col,
                    row_id=row_id,
                    detail=f"value={row[df_col]!r} error={str(exc)!r}",
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

    def _build_row_payload(self, row: pd.Series, row_id: int) -> dict[str, Any]:
        """단일 행에서 순수 item payload만 계산한다."""
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

    @staticmethod
    def _unresolved_parent_error(parent_row_id: Any) -> str:
        if parent_row_id is None or pd.isna(parent_row_id):
            return "Parent row is unresolved."
        return f"Parent row {int(parent_row_id)} was not uploaded successfully."

    def build_payloads(self, force: bool = False) -> pd.DataFrame:
        """현재 업로드 대상 전체 행의 payload를 한 번에 계산해 cache한다."""
        if self.state.schema_df is None:
            raise ValueError("schema_df is required before payload generation.")

        if self.state.payload_df is not None and not force:
            return self.state.payload_df

        source_df = self._payload_source_df()
        payload_rows: list[dict[str, Any]] = []

        for _, row in source_df.iterrows():
            row_id = int(row["_row_id"])
            try:
                payload_json = self._build_row_payload(row, row_id)
                payload_rows.append({
                    "_row_id": row_id,
                    "parent_row_id": row.get("parent_row_id"),
                    "upload_name": row.get("upload_name"),
                    "payload_json": payload_json,
                    "payload_status": PayloadStatus.READY.value,
                    "payload_error": None,
                })
            except Exception as exc:
                payload_rows.append({
                    "_row_id": row_id,
                    "parent_row_id": row.get("parent_row_id"),
                    "upload_name": row.get("upload_name"),
                    "payload_json": None,
                    "payload_status": PayloadStatus.FAILED.value,
                    "payload_error": str(exc),
                })

        self.state.payload_df = pd.DataFrame(payload_rows)
        return self.state.payload_df

    def preview_payload(self, row_id: int) -> dict:
        """cache된 payload를 돌려주고, 필요하면 먼저 build_payloads를 수행한다."""
        payload_df = self.build_payloads()
        row_df = payload_df[payload_df["_row_id"] == row_id]
        if row_df.empty:
            raise ValueError(f"_row_id={row_id} was not found.")

        payload_row = row_df.iloc[0]
        if payload_row["payload_status"] != PayloadStatus.READY.value:
            raise ValueError(payload_row["payload_error"])

        return payload_row["payload_json"]

    def upload(self, dry_run: bool = False, continue_on_error: bool = True) -> dict:
        """부모-자식 순서를 지키며 업로드를 실행하고 결과를 모아 돌려준다."""
        if self.state.tracker_id is None:
            raise ValueError("tracker_id is not set.")
        payload_df = self.build_payloads()
        ready_df = payload_df[payload_df["payload_status"] == PayloadStatus.READY.value].copy()
        payload_failed_df = payload_df[payload_df["payload_status"] == PayloadStatus.FAILED.value].copy()

        pending = set(ready_df["_row_id"].tolist())
        created_map = {}
        success_logs = []
        failed_logs = [
            {
                "_row_id": int(row["_row_id"]),
                "parent_row_id": row.get("parent_row_id"),
                "upload_name": row.get("upload_name"),
                "error": row.get("payload_error"),
                "status": PayloadStatus.FAILED.value,
            }
            for _, row in payload_failed_df.iterrows()
        ]

        while pending:
            progress = False

            for _, row in ready_df.iterrows():
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
                    payload = row["payload_json"]

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
                    error_status_code = self._http_status_code(exc)
                    error_response_json = self._response_json(exc)
                    error_message = ""
                    if error_response_json is not None:
                        error_message = str(error_response_json)
                    else:
                        error_message = str(exc)

                    failed_logs.append({
                        "_row_id": row_id,
                        "parent_row_id": row["parent_row_id"],
                        "upload_name": row["upload_name"],
                        "error_status_code": error_status_code,
                        "error_response_json": error_response_json,
                        "error": error_message,
                        "status": UploadStatus.FAILED.value,
                    })

                    if not continue_on_error:
                        self.state.upload_result = {
                            "created_map": created_map,
                            "success_df": pd.DataFrame(success_logs),
                            "failed_df": pd.DataFrame(failed_logs),
                            "unresolved_df": ready_df[ready_df["_row_id"].isin(sorted(pending))].copy(),
                        }
                        return self.state.upload_result

                    pending.remove(row_id)
                    progress = True

            if not progress:
                break

        unresolved_df = ready_df[ready_df["_row_id"].isin(sorted(pending))].copy()
        if not unresolved_df.empty:
            unresolved_df["status"] = UploadStatus.UNRESOLVED_PARENT.value
            unresolved_df["error"] = unresolved_df["parent_row_id"].apply(self._unresolved_parent_error)

        self.state.upload_result = {
            "created_map": created_map,
            "success_df": pd.DataFrame(success_logs),
            "failed_df": pd.DataFrame(failed_logs),
            "unresolved_df": unresolved_df,
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
            "payload_df.csv": self.state.payload_df,
            "schema_df.csv": self.state.schema_df,
            "comparison_df.csv": self.state.comparison_df,
            "option_check_df.csv": self.state.option_check_df,
        }

        for name, df in frames.items():
            if isinstance(df, pd.DataFrame) and not df.empty:
                csv_df = df.copy()
                if "payload_json" in csv_df.columns:
                    csv_df["payload_json"] = csv_df["payload_json"].apply(
                        lambda payload: (
                            json.dumps(payload, ensure_ascii=False)
                            if payload is not None
                            else None
                        )
                    )
                csv_df.to_csv(out / name, index=False)

        if self.state.schema is not None:
            with open(out / "schema.json", "w", encoding="utf-8") as file:
                json.dump(self.state.schema, file, ensure_ascii=False, indent=2)

        if self.state.option_maps is not None:
            with open(out / "option_maps.json", "w", encoding="utf-8") as file:
                json.dump(self.state.option_maps, file, ensure_ascii=False, indent=2)

        if isinstance(self.state.payload_df, pd.DataFrame) and not self.state.payload_df.empty:
            with open(out / "payload_preview.jsonl", "w", encoding="utf-8") as file:
                for _, row in self.state.payload_df.iterrows():
                    file.write(json.dumps({
                        "_row_id": row.get("_row_id"),
                        "parent_row_id": row.get("parent_row_id"),
                        "upload_name": row.get("upload_name"),
                        "payload_status": row.get("payload_status"),
                        "payload_error": row.get("payload_error"),
                        "payload_json": row.get("payload_json"),
                    }, ensure_ascii=False))
                    file.write("\n")

        if self.state.upload_result is not None:
            for key in ["success_df", "failed_df", "unresolved_df"]:
                df = self.state.upload_result.get(key)
                if isinstance(df, pd.DataFrame) and not df.empty:
                    csv_df = df.copy()
                    if "error_response_json" in csv_df.columns:
                        csv_df["error_response_json"] = csv_df["error_response_json"].apply(
                            lambda payload: (
                                json.dumps(payload, ensure_ascii=False)
                                if payload is not None
                                else None
                            )
                        )
                    csv_df.to_csv(out / f"{key}.csv", index=False)

            failed_df = self.state.upload_result.get("failed_df")
            if isinstance(failed_df, pd.DataFrame) and not failed_df.empty:
                with open(out / "failed_responses.jsonl", "w", encoding="utf-8") as file:
                    for _, row in failed_df.iterrows():
                        file.write(json.dumps({
                            "_row_id": row.get("_row_id"),
                            "parent_row_id": row.get("parent_row_id"),
                            "upload_name": row.get("upload_name"),
                            "error_status_code": row.get("error_status_code"),
                            "error_response_json": row.get("error_response_json"),
                            "error": row.get("error"),
                            "status": row.get("status"),
                        }, ensure_ascii=False))
                        file.write("\n")

            with open(out / "created_map.json", "w", encoding="utf-8") as file:
                json.dump(self.state.upload_result.get("created_map", {}), file, ensure_ascii=False, indent=2)
