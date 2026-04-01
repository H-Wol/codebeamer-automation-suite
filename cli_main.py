from __future__ import annotations

import pandas as pd

from src.config import load_config
from src.logger import setup_logger
from src.codebeamer_client import CodebeamerClient
from src.excel_processor import ExcelHierarchyProcessor
from src.mapping_service import MappingService
from src.wizard import CodebeamerUploadWizard
from src.cli_helpers import choose_one, choose_many, confirm


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
    project_id = projects[p_idx]["id"]
    wizard.select_project(project_id)

    trackers = wizard.load_trackers()
    t_idx = choose_one("트래커 선택", [t["name"] for t in trackers])
    tracker_id = trackers[t_idx]["id"]

    sample_item_id = int(input("Sample item id 입력 (option 조회용): ").strip())
    wizard.select_tracker(tracker_id, sample_item_id)

    file_path = input("Excel 파일 경로 입력: ").strip()

    xls = pd.ExcelFile(file_path)
    s_idx = choose_one("시트 선택", xls.sheet_names)
    sheet_name = xls.sheet_names[s_idx]

    headers = pd.read_excel(file_path, sheet_name=sheet_name, nrows=0).columns.tolist()

    summary_idx = choose_one("요약 컬럼 선택", headers)
    summary_col = headers[summary_idx]

    list_indices = choose_many("list로 묶을 컬럼 선택", headers)
    list_cols = [headers[i] for i in list_indices]

    processor = ExcelHierarchyProcessor(
        header_row=cfg.excel_header_row,
        summary_col=summary_col,
        logger=logger,
    )
    wizard.processor = processor

    wizard.read_excel(file_path=file_path, sheet_name=sheet_name, list_cols=list_cols)

    print("\n[컬럼 목록]")
    for col in wizard.state.upload_df.columns:
        print("-", col)

    selected_mapping = {}
    for col in wizard.state.upload_df.columns:
        field = input(f"매핑할 schema field 입력 ({col}) (skip=Enter): ").strip()
        if field:
            selected_mapping[col] = field

    comp = wizard.load_schema_and_compare(selected_mapping)
    print(comp[["df_column", "selected_schema_field", "status"]])

    if not confirm("업로드 진행할까요?"):
        return

    result = wizard.upload(dry_run=False)
    print(result)


if __name__ == "__main__":
    main()
