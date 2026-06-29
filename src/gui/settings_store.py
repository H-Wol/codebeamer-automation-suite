from __future__ import annotations

import json
from dataclasses import asdict
from dataclasses import dataclass
from dataclasses import field
from pathlib import Path
from typing import Any


APP_DIR_NAME = ".codebeamer-automation-suite"
SETTINGS_FILE_NAME = "gui_settings.json"
KEY_FILE_NAME = "gui_settings.key"
WORKFLOW_PRESET_FILE_NAME = "gui_workflow_preset.json"


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


@dataclass
class GuiWorkflowPreset:
    version: int = 1
    settings: GuiSettings = field(default_factory=GuiSettings)
    file_options: dict[str, Any] = field(default_factory=dict)
    root_item_config: dict[str, Any] = field(default_factory=dict)
    selected_mapping: dict[str, str] = field(default_factory=dict)
    selected_default_values: dict[str, str] = field(default_factory=dict)
    selected_tracker_item_settings: dict[str, dict[str, Any]] = field(default_factory=dict)


class GuiSettingsStore:
    """GUI 설정 파일과 암호화된 비밀번호를 저장/조회한다."""

    def __init__(self, root_dir: Path | None = None) -> None:
        self.root_dir = root_dir or (Path.home() / APP_DIR_NAME)
        self.settings_path = self.root_dir / SETTINGS_FILE_NAME
        self.key_path = self.root_dir / KEY_FILE_NAME
        self.workflow_preset_path = self.root_dir / WORKFLOW_PRESET_FILE_NAME

    def load(self) -> GuiSettings:
        if not self.settings_path.exists():
            return GuiSettings()

        payload = json.loads(self.settings_path.read_text(encoding="utf-8"))
        return self._settings_from_payload(payload)

    def save(self, settings: GuiSettings) -> None:
        self.root_dir.mkdir(parents=True, exist_ok=True)
        payload = self._settings_payload(settings)
        self.settings_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def load_workflow_preset(self) -> GuiWorkflowPreset | None:
        if not self.workflow_preset_path.exists():
            return None

        payload = json.loads(self.workflow_preset_path.read_text(encoding="utf-8"))
        raw_settings = payload.get("settings")
        settings_payload = raw_settings if isinstance(raw_settings, dict) else {}
        return GuiWorkflowPreset(
            version=int(payload.get("version") or 1),
            settings=self._settings_from_payload(settings_payload),
            file_options=self._dict_payload(payload.get("file_options")),
            root_item_config=self._dict_payload(payload.get("root_item_config")),
            selected_mapping={
                str(key): str(value)
                for key, value in self._dict_payload(payload.get("selected_mapping")).items()
                if str(key).strip() and str(value).strip()
            },
            selected_default_values={
                str(key): str(value)
                for key, value in self._dict_payload(payload.get("selected_default_values")).items()
                if str(key).strip() and str(value).strip()
            },
            selected_tracker_item_settings={
                str(key): dict(value)
                for key, value in self._dict_payload(payload.get("selected_tracker_item_settings")).items()
                if str(key).strip() and isinstance(value, dict)
            },
        )

    def save_workflow_preset(self, preset: GuiWorkflowPreset) -> None:
        self.root_dir.mkdir(parents=True, exist_ok=True)
        payload = {
            "version": int(preset.version or 1),
            "settings": self._settings_payload(preset.settings),
            "file_options": self._dict_payload(preset.file_options),
            "root_item_config": self._dict_payload(preset.root_item_config),
            "selected_mapping": {
                str(key): str(value)
                for key, value in dict(preset.selected_mapping or {}).items()
                if str(key).strip() and str(value).strip()
            },
            "selected_default_values": {
                str(key): str(value)
                for key, value in dict(preset.selected_default_values or {}).items()
                if str(key).strip() and str(value).strip()
            },
            "selected_tracker_item_settings": {
                str(key): dict(value)
                for key, value in dict(preset.selected_tracker_item_settings or {}).items()
                if str(key).strip() and isinstance(value, dict)
            },
        }
        self.workflow_preset_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    @staticmethod
    def _dict_payload(value: Any) -> dict[str, Any]:
        return dict(value) if isinstance(value, dict) else {}

    def _settings_payload(self, settings: GuiSettings) -> dict[str, Any]:
        payload = asdict(settings)
        password = payload.pop("password", "")
        if settings.save_password and password:
            payload["password_encrypted"] = self._encrypt_password(password)
        else:
            payload["password_encrypted"] = ""
        return payload

    def _settings_from_payload(self, payload: dict[str, Any]) -> GuiSettings:
        payload = dict(payload or {})
        password = ""
        encrypted_password = payload.pop("password_encrypted", "")
        if payload.get("save_password") and encrypted_password:
            password = self._decrypt_password(encrypted_password)

        return GuiSettings(
            password=password,
            **{key: value for key, value in payload.items() if key in GuiSettings.__dataclass_fields__},
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
