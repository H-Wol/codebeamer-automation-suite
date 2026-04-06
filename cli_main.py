from __future__ import annotations

from src.config import load_config
from src.logger import setup_logger
from src.codebeamer_client import CodebeamerClient
from src.excel_processor_v2 import ExcelHierarchyProcessor
from src.mapping_service import MappingService
from src.wizard import CodebeamerUploadWizard
from src.cli_helpers import choose_one, choose_many, confirm
from src.cli_excel_utils import list_sheet_names, read_headers


def main():
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
    p_idx = choose_one("프로젝트 선택", [p["name"] for p in projects])
    wizard.select_project(projects[p_idx]["id"])

    trackers = wizard.load_trackers()
    t_idx = choose_one("트래커 선택", [t["name"] for t in trackers])

    items = wizard.load_tracker_items(trackers[t_idx]["id"])
    wizard.select_tracker(trackers[t_idx]["id"])

    file_path = "./codebeamer_test_data_en_small.xlsx"
    # TODO
    # file_path = input("Excel 파일 경로 입력: ").strip()

    sheet_names = list_sheet_names(file_path)
    s_idx = choose_one("시트 선택", sheet_names)
    sheet_name = sheet_names[s_idx]

    headers = read_headers(file_path, sheet_name, header_row=cfg.excel_header_row)

    summary_col = [col for col in headers if "summary" == col.lower() or "요약" == col]
    if summary_col:
        summary_col = summary_col[0]
        print(f"자동으로 '{summary_col}' 컬럼이 요약 컬럼으로 선택되었습니다.")
    else:
        summary_idx = choose_one("요약 컬럼 선택", headers)
        summary_col = headers[summary_idx]

    list_indices = choose_many("list로 묶을 컬럼 선택", headers)
    list_cols = [headers[i] for i in list_indices]

    wizard.processor = ExcelHierarchyProcessor(
        header_row=cfg.excel_header_row,
        summary_col=summary_col,
        logger=logger,
    )

    wizard.read_excel(file_path=file_path, sheet_name=sheet_name, list_cols=list_cols)

    print("\n[컬럼 목록]")
    for col in wizard.state.upload_df.columns:
        print("-", col)

    # 스키마 로드 및 스캐마 필드명 목록 생성
    tracker_schema = wizard.client.get_tracker_schema(wizard.state.tracker_id)
    schema_df = wizard.mapper.flatten_schema_fields(tracker_schema)
    schema_field_names = set(schema_df["field_name"].dropna().astype(str).str.strip())

    selected_mapping = {}
    auto_matched = 0
    for col in wizard.state.upload_df.columns:
        matched_field = None

        # 이름이 정확히 일치하는 필드가 있으면 확인
        if col in schema_field_names:
            matched_field = col
        else:
            # 대소문자 무시하고 매칭 시도
            for schema_field in schema_field_names:
                if col.lower() == schema_field.lower():
                    matched_field = schema_field
                    break

        if matched_field:
            # 자동 매칭된 필드 확인
            if confirm(f"{col} -> {matched_field} 로 매칭할까요?"):
                selected_mapping[col] = matched_field
                print(f"✓ {col} -> {matched_field} (매칭됨)")
                auto_matched += 1
            # 사용자가 거절하면 스킵

    if auto_matched > 0:
print(f"\n[총 {auto_matched}개 컬럼 매칭됨]")

    comp = wizard.load_schema_and_compare(selected_mapping)
    print(comp[["df_column", "selected_schema_field", "status"]])

    # TableField 컬럼 정보 출력
    if wizard.state.table_field_mapping:
        print("\n[자동 감지된 TableField 컬럼]")
        for df_col, tf_info in wizard.state.table_field_mapping.items():
            print(f"✓ {df_col} -> {tf_info['table_field_name']}.{tf_info['column_name']}")
    else:
        print("\n[TableField 컬럼이 감지되지 않았습니다]")

    # 옵션 필드 매핑 처리 (wizard에서 자동 처리 + 확인)
    print("\n[옵션 필드 처리 중...]")
    selected_option_mapping, option_check_df = wizard.process_option_mapping(selected_mapping)

    if selected_option_mapping:
        print(f"✓ {len(selected_option_mapping)}개 옵션 필드 변환 설정됨")

        if not option_check_df.empty:
            print("\n⚠ 옵션 정렬 오류:")
            print(option_check_df)

            if not confirm("옵션 정렬 오류가 있습니다. 계속 진행할까요?"):
                return

        print("✓ 옵션 변환 완료")
    else:
        print("ℹ 옵션 변환이 필요 없습니다")
    is_dry = confirm("Dry run으로 진행할까요? (실제 업로드는 하지 않고 결과만 보여줌)")
    result = wizard.upload(dry_run=is_dry)
    print(result)

    save_path = input("업로드 결과를 저장할 Excel 파일 경로 입력 (skip=저장 안함): ").strip()
    if save_path:
        wizard.save_state(save_path)


if __name__ == "__main__":
    main()
