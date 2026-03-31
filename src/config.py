from __future__ import annotations

import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()

@dataclass
class AppConfig:
    base_url: str
    username: str
    password: str

    default_project_id: int | None
    default_tracker_id: int | None
    default_sample_item_id: int | None

    excel_header_row: int
    excel_summary_col: str
    excel_sheet_name: str | int

    log_level: str
    output_dir: str


def load_config() -> AppConfig:
    return AppConfig(
        base_url=os.getenv("CODEBEAMER_BASE_URL", "").rstrip("/"),
        username=os.getenv("CODEBEAMER_USERNAME", ""),
        password=os.getenv("CODEBEAMER_PASSWORD", ""),
        default_project_id=int(os.getenv("DEFAULT_PROJECT_ID")) if os.getenv("DEFAULT_PROJECT_ID") else None,
        default_tracker_id=int(os.getenv("DEFAULT_TRACKER_ID")) if os.getenv("DEFAULT_TRACKER_ID") else None,
        default_sample_item_id=int(os.getenv("DEFAULT_SAMPLE_ITEM_ID")) if os.getenv("DEFAULT_SAMPLE_ITEM_ID") else None,
        excel_header_row=int(os.getenv("EXCEL_HEADER_ROW", "1")),
        excel_summary_col=os.getenv("EXCEL_SUMMARY_COL", "요약"),
        excel_sheet_name=os.getenv("EXCEL_SHEET_NAME", "0"),
        log_level=os.getenv("LOG_LEVEL", "INFO"),
        output_dir=os.getenv("OUTPUT_DIR", "output"),
    )
