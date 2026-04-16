from __future__ import annotations

import json
from dataclasses import asdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any


APP_DIR_NAME = ".codebeamer-automation-suite"
SETTINGS_FILE_NAME = "gui_settings.json"
KEY_FILE_NAME = "gui_settings.key"


@dataclass
class GuiSettings:
    base_url: str = ""
    username: str = ""
    password: str = ""
    save_password: bool = False
    default_project_id: str = ""
    default_tracker_id: str = ""
    excel_header_row: int = 1
    summary_column: str = "Summary"
    excel_sheet_name: str = "0"
    rate_limit_retry_delay_seconds: float = 1.0
    rate_limit_max_retries: int = 5
    output_dir: str = "output"
    last_file_path: str = ""


class GuiSettingsStore:
    """GUI 설정 파일과 암호화된 비밀번호를 저장/조회한다."""

    def __init__(self, root_dir: Path | None = None) -> None:
        self.root_dir = root_dir or (Path.home() / APP_DIR_NAME)
        self.settings_path = self.root_dir / SETTINGS_FILE_NAME
        self.key_path = self.root_dir / KEY_FILE_NAME

    def load(self) -> GuiSettings:
        if not self.settings_path.exists():
            return GuiSettings()

        payload = json.loads(self.settings_path.read_text(encoding="utf-8"))
        password = ""
        encrypted_password = payload.pop("password_encrypted", "")
        if payload.get("save_password") and encrypted_password:
            password = self._decrypt_password(encrypted_password)

        return GuiSettings(
            password=password,
            **{key: value for key, value in payload.items() if key in GuiSettings.__dataclass_fields__},
        )

    def save(self, settings: GuiSettings) -> None:
        self.root_dir.mkdir(parents=True, exist_ok=True)
        payload = asdict(settings)

        password = payload.pop("password", "")
        if settings.save_password and password:
            payload["password_encrypted"] = self._encrypt_password(password)
        else:
            payload["password_encrypted"] = ""
        self.settings_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def _get_fernet(self):
        try:
            from cryptography.fernet import Fernet
        except ImportError as exc:
            raise RuntimeError(
                "GUI 암호화 저장에는 cryptography 패키지가 필요합니다."
            ) from exc

        self.root_dir.mkdir(parents=True, exist_ok=True)
        if not self.key_path.exists():
            self.key_path.write_bytes(Fernet.generate_key())
        return Fernet(self.key_path.read_bytes())

    def _encrypt_password(self, password: str) -> str:
        return self._get_fernet().encrypt(password.encode("utf-8")).decode("utf-8")

    def _decrypt_password(self, encrypted_password: str) -> str:
        return self._get_fernet().decrypt(encrypted_password.encode("utf-8")).decode("utf-8")

