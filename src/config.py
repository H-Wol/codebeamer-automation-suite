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

    excel_header_row: int
    excel_summary_col: str
    excel_sheet_name: str | int

    log_level: str
    output_dir: str


def _to_optional_int(value: str | None) -> int | None:
    """비어 있는 문자열은 None으로, 값이 있으면 정수로 바꾼다."""
    if value is None or str(value).strip() == "":
        return None
    return int(value)


def _to_sheet_name(value: str | None) -> str | int:
    """시트 설정값을 숫자 인덱스 또는 시트 이름으로 정리한다."""
    if value is None or str(value).strip() == "":
        return 0
    text = str(value).strip()
    return int(text) if text.isdigit() else text


def load_config() -> AppConfig:
    """환경 변수와 기본값을 읽어 프로그램 실행 설정을 만든다."""
    base_url = os.getenv("CODEBEAMER_BASE_URL", "").strip()
    username = os.getenv("CODEBEAMER_USERNAME", "").strip()
    password = os.getenv("CODEBEAMER_PASSWORD", "").strip()

    if not base_url:
        raise ValueError("CODEBEAMER_BASE_URL is required")
    if not username:
        raise ValueError("CODEBEAMER_USERNAME is required")
    if not password:
        raise ValueError("CODEBEAMER_PASSWORD is required")

    return AppConfig(
        base_url=base_url.rstrip("/"),
        username=username,
        password=password,
        default_project_id=_to_optional_int(os.getenv("DEFAULT_PROJECT_ID")),
        default_tracker_id=_to_optional_int(os.getenv("DEFAULT_TRACKER_ID")),
        excel_header_row=int(os.getenv("EXCEL_HEADER_ROW", "1")),
        excel_summary_col=os.getenv("EXCEL_SUMMARY_COL", "Summary"),
        excel_sheet_name=_to_sheet_name(os.getenv("EXCEL_SHEET_NAME", "0")),
        log_level=os.getenv("LOG_LEVEL", "INFO").upper(),
        output_dir=os.getenv("OUTPUT_DIR", "output"),
    )
