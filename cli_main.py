from __future__ import annotations

from pathlib import Path

from src.cli_excel_utils import list_sheet_names
from src.cli_excel_utils import read_headers
from src.cli_helpers import choose_one
from src.cli_helpers import confirm
from src.codebeamer_client import CodebeamerClient
from src.config import load_config
from src.excel_processor import ExcelHierarchyProcessor
from src.logger import setup_logger
from src.mapping_service import MappingService
from src.models import OptionCheckStatus
from src.wizard import CodebeamerUploadWizard


BLOCKING_OPTION_STATUSES = {
    OptionCheckStatus.DF_COLUMN_MISSING.value,
    OptionCheckStatus.FIELD_UNSUPPORTED.value,
    OptionCheckStatus.LOOKUP_REQUIRED.value,
    OptionCheckStatus.OPTION_MAP_MISSING.value,
    OptionCheckStatus.OPTION_NOT_FOUND.value,
    OptionCheckStatus.OPTION_SOURCE_UNAVAILABLE.value,
}
INFO_OPTION_STATUSES = {
    OptionCheckStatus.PRECONSTRUCTION_REQUIRED.value,
}
USER_LOOKUP_FAILURE_SUFFIXES = (
    "USER_LOOKUP_NOT_RUN",
    "USER_LOOKUP_FAILED",
    "USER_LOOKUP_AMBIGUOUS",
    "USER_NOT_FOUND",
)


def _suggest_excel_path() -> str | None:
    """자주 쓰는 위치에서 기본 Excel 파일 경로를 찾아 제안한다."""
    candidates = [
        Path("./data/codebeamer_test_data_en_small.xlsx"),
        Path("./data.xlsx"),
    ]
    for candidate in candidates:
        if candidate.exists():
            return str(candidate)
    return None


def _prompt_excel_path() -> str:
    """사용자에게 Excel 파일 경로를 묻고 기본 경로가 있으면 함께 제안한다."""
    suggested = _suggest_excel_path()
    if suggested:
        raw = input(f"Excel file path (Enter={suggested}): ").strip()
        return raw or suggested
    return input("Excel file path: ").strip()


def _auto_match_columns(upload_columns: list[str], schema_field_names: set[str]) -> dict[str, str]:
    """Excel 컬럼 이름과 schema 필드 이름이 비슷하면 자동 매핑을 제안한다."""
    selected_mapping: dict[str, str] = {}

    for col in upload_columns:
        matched_field = None

        if col in schema_field_names:
            matched_field = col
        else:
            for schema_field in schema_field_names:
                if col.lower() == schema_field.lower():
                    matched_field = schema_field
                    break

        if matched_field and confirm(f"Map '{col}' -> '{matched_field}'?", default=True):
            selected_mapping[col] = matched_field
            print(f"  mapped: {col} -> {matched_field}")

    return selected_mapping


def _print_option_check_summary(option_check_df):
    """옵션 검증 결과를 읽기 쉬운 정보와 차단 이슈로 나눠 출력한다."""
    if option_check_df.empty:
        print("옵션/참조형 필드 검증 통과")
        return False

    print("\n[옵션 검증 결과]")
    print(option_check_df)

    status_series = option_check_df["status"].fillna("")
    info_df = option_check_df[status_series.isin(INFO_OPTION_STATUSES)]
    blocking_df = option_check_df[
        status_series.isin(BLOCKING_OPTION_STATUSES)
        | status_series.astype(str).str.endswith(USER_LOOKUP_FAILURE_SUFFIXES)
    ]

    if not info_df.empty:
        print("\n[사전 구성 정보]")
        print(
            info_df[
                [
                    "df_column",
                    "schema_field",
                    "resolved_field_kind",
                    "preconstruction_kind",
                    "preconstruction_detail",
                    "payload_target_kind",
                ]
            ].drop_duplicates()
        )

    if not blocking_df.empty:
        print("\n[차단 이슈 요약]")

        unsupported_df = blocking_df[
            blocking_df["status"] == OptionCheckStatus.FIELD_UNSUPPORTED.value
        ]
        if not unsupported_df.empty:
            print("- 미지원 필드가 있습니다. unsupported_reason을 확인해야 합니다.")

        lookup_required_df = blocking_df[
            blocking_df["status"] == OptionCheckStatus.LOOKUP_REQUIRED.value
        ]
        if not lookup_required_df.empty:
            print("- generic_reference lookup resolver가 없어 payload 생성 전에 중단됩니다.")

        option_not_found_df = blocking_df[
            blocking_df["status"] == OptionCheckStatus.OPTION_NOT_FOUND.value
        ]
        if not option_not_found_df.empty:
            print("- schema option에 없는 값이 업로드 데이터에 있습니다.")

        user_lookup_df = blocking_df[
            blocking_df["status"].astype(str).str.endswith(USER_LOOKUP_FAILURE_SUFFIXES)
        ]
        if not user_lookup_df.empty:
            print("- 사용자 lookup 실패 행이 있습니다. __lookup_error 또는 error 컬럼을 확인해야 합니다.")

        print("\n[차단 이슈 상세]")
        print(blocking_df)
        return True

    return False


def main():
    """프로젝트 선택부터 업로드 실행까지 전체 CLI 흐름을 실행한다."""
    cfg = load_config()
    logger = setup_logger("cb-cli", level=cfg.log_level)

    client = CodebeamerClient(cfg.base_url, cfg.username, cfg.password, logger)
    wizard = CodebeamerUploadWizard(
        client=client,
        processor=None,
        mapper=MappingService(logger=logger),
        logger=logger,
    )

    projects = wizard.load_projects()
    project_index = choose_one("프로젝트 선택", [p["name"] for p in projects])
    wizard.select_project(projects[project_index]["id"])

    trackers = wizard.load_trackers()
    tracker_index = choose_one("트래커 선택", [t["name"] for t in trackers])
    tracker_id = trackers[tracker_index]["id"]
    wizard.select_tracker(tracker_id)

    file_path = _prompt_excel_path()
    sheet_names = list_sheet_names(file_path)
    sheet_index = choose_one("시트 선택", sheet_names)
    sheet_name = sheet_names[sheet_index]

    headers = read_headers(file_path, sheet_name, header_row=cfg.excel_header_row)
    summary_candidates = [col for col in headers if col.lower() == "summary" or col == "요약"]
    if summary_candidates:
        summary_col = summary_candidates[0]
        print(f"자동으로 요약 컬럼을 '{summary_col}' 로 선택했습니다.")
    else:
        summary_index = choose_one("요약 컬럼 선택", headers)
        summary_col = headers[summary_index]

    tracker_schema = wizard.client.get_tracker_schema(wizard.state.tracker_id)
    schema_df = wizard.mapper.flatten_schema_fields(tracker_schema)
    schema_field_names = set(schema_df["field_name"].dropna().astype(str).str.strip())

    print("\n[컬럼 자동 매핑 확인]")
    selected_mapping = _auto_match_columns(headers, schema_field_names)

    list_cols = wizard.mapper.get_list_columns_for_mapping(selected_mapping, schema_df)
    if list_cols:
        print("\n[multipleValues 기준 자동 선택된 list 컬럼]")
        for col in list_cols:
            print("-", col)
    else:
        print("\n[multipleValues 기준 자동 선택된 list 컬럼 없음]")

    wizard.processor = ExcelHierarchyProcessor(
        header_row=cfg.excel_header_row,
        summary_col=summary_col,
        logger=logger,
    )

    wizard.read_excel(file_path=file_path, sheet_name=sheet_name, list_cols=list_cols)

    print("\n[업로드 컬럼 목록]")
    for col in wizard.state.upload_df.columns:
        print("-", col)

    comparison_df = wizard.load_schema_and_compare(selected_mapping)
    print("\n[Schema Comparison]")
    print(comparison_df[["df_column", "selected_schema_field", "status"]])

    if wizard.state.table_field_mapping:
        print("\n[자동 감지된 TableField 컬럼]")
        for df_col, tf_info in wizard.state.table_field_mapping.items():
            print(f"- {df_col} -> {tf_info['table_field_name']}.{tf_info['column_name']}")
    else:
        print("\n[감지된 TableField 컬럼 없음]")

    print("\n[옵션/참조형 필드 처리 중]")
    selected_option_mapping, option_check_df = wizard.process_option_mapping(selected_mapping)

    if selected_option_mapping:
        print(f"자동 감지된 옵션/참조형 필드 수: {len(selected_option_mapping)}")

        has_blocking_issues = _print_option_check_summary(option_check_df)
        if has_blocking_issues:
            if not confirm("차단 이슈를 확인했습니다. 그래도 계속 진행할까요?", default=False):
                return
        elif not option_check_df.empty:
            if not confirm("사전 구성 정보를 확인했습니다. 계속 진행할까요?", default=True):
                return
    else:
        print("옵션/참조형 필드 매핑 대상이 없습니다.")

    preview_row_id = int(wizard.state.upload_df["_row_id"].min())
    print(f"\n[Payload Preview row_id={preview_row_id}]")
    print(wizard.preview_payload(preview_row_id))

    is_dry = confirm("Dry run으로 진행할까요?", default=True)
    result = wizard.upload(dry_run=is_dry)

    print("\n[Upload Result]")
    success_df = result["success_df"]
    failed_df = result["failed_df"]
    unresolved_df = result["unresolved_df"]
    print(f"success={len(success_df)}, failed={len(failed_df)}, unresolved={len(unresolved_df)}")

    if not success_df.empty:
        print("\n[Success Preview]")
        print(success_df.head(20))

    if not failed_df.empty:
        print("\n[Failed Preview]")
        print(failed_df.head(20))

    if not unresolved_df.empty:
        print("\n[Unresolved Preview]")
        print(unresolved_df.head(20))

    if confirm(f"상태를 '{cfg.output_dir}' 디렉터리에 저장할까요?", default=True):
        wizard.save_state(cfg.output_dir)
        print(f"저장 완료: {cfg.output_dir}")


if __name__ == "__main__":
    main()
