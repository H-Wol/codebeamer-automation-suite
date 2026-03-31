from __future__ import annotations

from src.config import load_config
from src.logger import setup_logger
from src.codebeamer_client import CodebeamerClient
from src.excel_processor import ExcelHierarchyProcessor
from src.mapping_service import MappingService
from src.wizard import CodebeamerUploadWizard


def main():
    cfg = load_config()
    logger = setup_logger("cb-uploader", level=cfg.log_level, log_file="logs/app.log")

    client = CodebeamerClient(
        base_url=cfg.base_url,
        username=cfg.username,
        password=cfg.password,
        logger=logger,
    )
    processor = ExcelHierarchyProcessor(
        header_row=cfg.excel_header_row,
        summary_col=cfg.excel_summary_col,
        logger=logger,
    )
    mapper = MappingService(logger=logger)

    wizard = CodebeamerUploadWizard(client=client, processor=processor, mapper=mapper, logger=logger)

    projects = wizard.load_projects()
    print("\n[Projects]")
    for p in projects[:20]:
        print(p["id"], p["name"])

    project_id = cfg.default_project_id or int(input("\nSelect project_id: ").strip())
    wizard.select_project(project_id)

    trackers = wizard.load_trackers()
    print("\n[Trackers]")
    for t in trackers[:50]:
        print(t["id"], t["name"])

    tracker_id = cfg.default_tracker_id or int(input("\nSelect tracker_id: ").strip())
    sample_item_id = cfg.default_sample_item_id or int(input("Sample item id for options: ").strip())
    wizard.select_tracker(tracker_id=tracker_id, sample_item_id=sample_item_id)

    file_path = input("\nExcel file path: ").strip()
    wizard.read_excel(file_path=file_path, sheet_name=cfg.excel_sheet_name)

    selected_mapping = {
        "upload_name": "name",
        "upload_description": "description",
    }
    comparison_df = wizard.load_schema_and_compare(selected_mapping)
    print("\n[Schema Comparison]")
    print(comparison_df[["df_column", "selected_schema_field", "status"]])

    selected_option_mapping = {}
    option_check_df = wizard.check_option_fields(selected_option_mapping)
    print("\n[Option Check]")
    print(option_check_df.head(20))

    print("\n[Payload Preview row_id=0]")
    print(wizard.preview_payload(0))

    dry_run = input("\nDry run? (y/n): ").strip().lower() == "y"
    result = wizard.upload(dry_run=dry_run, continue_on_error=True)
    print("\n[Upload Result]")
    print(result["success_df"].head(20) if not result["success_df"].empty else "No success rows")
    print(result["failed_df"].head(20) if not result["failed_df"].empty else "No failed rows")

    wizard.save_state(cfg.output_dir)


if __name__ == "__main__":
    main()
