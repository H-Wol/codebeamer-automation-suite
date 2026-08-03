from __future__ import annotations

from dataclasses import replace

from src.upload_policy import UPLOAD_MODE_UPDATE as GUI_UPLOAD_MODE_UPDATE
from src.upload_policy import normalize_upload_mode as normalize_gui_upload_mode
from src.upload_policy import upload_mode_action_label as gui_upload_mode_action_label

from .settings_store import GuiSettings
from .settings_store import GuiWorkflowPreset
from .window_support import _merge_root_item_page_configs
from .window_support import UploadProgressState
from .window_support import _merge_window_preferences


class WindowWorkflowMixin:
    def _on_settings_changed(self, settings: GuiSettings | None) -> GuiSettings:
        if settings is None:
            return self.session_state.settings
        normalized_theme = self._apply_theme(settings.theme_name)
        self.session_state.settings = replace(
            settings,
            theme_name=normalized_theme,
        )
        self.statusBar().showMessage("설정 상태를 갱신했습니다.")
        return self.session_state.settings

    def _on_file_state_changed(self, file_state: dict[str, object]) -> None:
        self.session_state.file_state = file_state
        self.statusBar().showMessage("파일 선택 상태를 갱신했습니다.")

    def _test_connection(self, settings: GuiSettings) -> list[dict[str, object]]:
        busy_message = (
            "테스트 프로젝트 목록을 불러오는 중입니다."
            if bool(getattr(settings, "offline_mode", False))
            else "프로젝트 목록을 불러오는 중입니다."
        )
        projects = self._run_with_busy(
            busy_message,
            self.codebeamer_service.test_connection_and_load_projects,
            settings,
        )
        self.session_state.settings = settings
        self.session_state.projects = projects
        self.statusBar().showMessage(
            "테스트 프로젝트 목록을 불러왔습니다."
            if bool(getattr(settings, "offline_mode", False))
            else "연결 테스트와 프로젝트 조회가 완료되었습니다."
        )
        return projects

    def _load_trackers(self, settings: GuiSettings, project_id: int) -> list[dict[str, object]]:
        trackers = self._run_with_busy(
            "트래커 목록을 불러오는 중입니다.",
            self.codebeamer_service.load_trackers,
            settings,
            project_id,
        )
        self.session_state.settings = settings
        self.session_state.trackers = trackers
        self.statusBar().showMessage("트래커 목록을 불러왔습니다.")
        return trackers

    def _load_file_preview(
        self,
        file_path: str,
        *,
        file_paths: list[str] | None = None,
        sheet_name: str,
        header_row: int,
        summary_column: str,
    ):
        preview = self._run_with_busy(
            "Excel 시트와 미리보기를 불러오는 중입니다.",
            self.excel_service.load_preview,
            file_path,
            file_paths=file_paths,
            sheet_name=sheet_name,
            header_row=header_row,
            summary_column=summary_column,
        )
        self.statusBar().showMessage("Excel 미리보기를 불러왔습니다.")
        return preview

    def _current_settings_snapshot(self) -> GuiSettings:
        settings = replace(self.session_state.settings)
        get_settings = getattr(self.settings_page, "get_settings", None)
        if callable(get_settings):
            settings = replace(get_settings())

        get_selection = getattr(self.project_page, "get_selection", None)
        if callable(get_selection):
            selection = dict(get_selection() or {})
            settings.default_project_id = str(selection.get("project_id") or settings.default_project_id or "")
            settings.default_tracker_id = str(selection.get("tracker_id") or settings.default_tracker_id or "")

        file_state = self._current_file_state_snapshot()
        file_paths = [
            str(path).strip()
            for path in file_state.get("file_paths") or []
            if str(path).strip()
        ]
        if file_paths:
            settings.last_file_path = file_paths[0]
        return settings

    def _current_file_state_snapshot(self) -> dict[str, object]:
        current_state = dict(self.session_state.file_state or {})
        get_state = getattr(self.file_page, "get_state", None)
        if callable(get_state):
            current_state.update(dict(get_state() or {}))
        return current_state

    def _apply_workflow_preset_to_mapping_context(self, mapping_context, preset: GuiWorkflowPreset) -> None:
        """`apply_workflow_preset_to_mapping_context` 변경을 적용한다."""
        self.pipeline_service.apply_saved_workflow_values(
            mapping_context,
            root_item_config=dict(preset.root_item_config or {}),
            selected_mapping=dict(preset.selected_mapping or {}),
            selected_mapping_modes=dict(preset.selected_mapping_modes or {}),
            selected_default_values=dict(preset.selected_default_values or {}),
            selected_default_value_modes=dict(preset.selected_default_value_modes or {}),
            selected_tracker_item_settings=dict(preset.selected_tracker_item_settings or {}),
        )

    def _collect_workflow_preset(self) -> GuiWorkflowPreset:
        """`collect_workflow_preset` 정보를 수집한다."""
        settings = self._current_settings_snapshot()
        file_state = self._current_file_state_snapshot()
        file_options = {
            "sheet_name": str(file_state.get("sheet_name") or settings.excel_sheet_name or "0"),
            "header_row": int(file_state.get("header_row") or settings.excel_header_row or 1),
            "summary_column": str(file_state.get("summary_column") or settings.summary_column or "Summary"),
        }

        root_item_config: dict[str, object] = {}
        mapping_context = self.session_state.mapping_context
        if mapping_context is not None:
            root_item_config = dict(getattr(mapping_context, "root_item_config", {}) or {})
        current_page = getattr(self, "_current_page", None)
        if current_page in {getattr(self, "root_item_structure_page", None), getattr(self, "root_item_field_page", None)} and mapping_context is not None:
            structure_config = (
                self.root_item_structure_page.get_config()
                if callable(getattr(self.root_item_structure_page, "get_config", None))
                else None
            )
            field_config = (
                self.root_item_field_page.get_config()
                if callable(getattr(self.root_item_field_page, "get_config", None))
                else None
            )
            root_item_config = _merge_root_item_page_configs(
                root_item_config,
                structure_config=structure_config,
                field_config=field_config,
            )

        selected_mapping: dict[str, str] = {}
        selected_mapping_modes: dict[str, dict[str, bool]] = {}
        selected_default_values: dict[str, str] = {}
        selected_default_value_modes: dict[str, dict[str, bool]] = {}
        selected_tracker_item_settings: dict[str, dict[str, object]] = {}
        if callable(getattr(self.mapping_page, "get_selected_mapping", None)):
            selected_mapping = dict(self.mapping_page.get_selected_mapping() or {})
        if callable(getattr(self.mapping_page, "get_selected_mapping_modes", None)):
            selected_mapping_modes = dict(self.mapping_page.get_selected_mapping_modes() or {})
        if callable(getattr(self.mapping_page, "get_selected_default_values", None)):
            selected_default_values = dict(self.mapping_page.get_selected_default_values() or {})
        if callable(getattr(self.mapping_page, "get_selected_default_value_modes", None)):
            selected_default_value_modes = dict(self.mapping_page.get_selected_default_value_modes() or {})
        if callable(getattr(self.mapping_page, "get_selected_tracker_item_settings", None)):
            selected_tracker_item_settings = dict(self.mapping_page.get_selected_tracker_item_settings() or {})

        if not selected_mapping and mapping_context is not None:
            selected_mapping = dict(getattr(mapping_context, "selected_mapping", {}) or {})
        if not selected_mapping_modes and mapping_context is not None:
            selected_mapping_modes = dict(getattr(mapping_context, "selected_mapping_modes", {}) or {})
        if not selected_default_values and mapping_context is not None:
            selected_default_values = dict(getattr(mapping_context, "selected_default_values", {}) or {})
        if not selected_default_value_modes and mapping_context is not None:
            selected_default_value_modes = dict(getattr(mapping_context, "selected_default_value_modes", {}) or {})
        if not selected_tracker_item_settings and mapping_context is not None:
            selected_tracker_item_settings = dict(getattr(mapping_context, "selected_tracker_item_settings", {}) or {})

        return GuiWorkflowPreset(
            settings=settings,
            file_options=file_options,
            root_item_config=root_item_config,
            selected_mapping=selected_mapping,
            selected_mapping_modes=selected_mapping_modes,
            selected_default_values=selected_default_values,
            selected_default_value_modes=selected_default_value_modes,
            selected_tracker_item_settings=selected_tracker_item_settings,
        )

    def _apply_workflow_preset(self, preset: GuiWorkflowPreset, *, startup: bool = False) -> None:
        """`apply_workflow_preset` 변경을 적용한다."""
        self.session_state.workflow_preset = preset
        if self.settings_store.app_settings_path.exists():
            current = self.session_state.settings
            self.session_state.settings = replace(
                current,
                upload_mode=normalize_gui_upload_mode(preset.settings.upload_mode),
                excel_header_row=max(int(preset.settings.excel_header_row or 1), 1),
                summary_column=str(preset.settings.summary_column or "Summary"),
                excel_sheet_name=str(preset.settings.excel_sheet_name or "0"),
                last_file_path=str(preset.settings.last_file_path or current.last_file_path or ""),
            )
            self._apply_theme(current.theme_name)
        else:
            normalized_theme = self._apply_theme(preset.settings.theme_name)
            self.session_state.settings = _merge_window_preferences(
                self.session_state.settings,
                replace(preset.settings, theme_name=normalized_theme),
            )

        set_settings = getattr(self.settings_page, "set_settings", None)
        if callable(set_settings):
            set_settings(replace(self.session_state.settings))

        load_selection = getattr(self.project_page, "load_selection", None)
        if callable(load_selection):
            load_selection(self.session_state.settings.default_project_id, self.session_state.settings.default_tracker_id)

        load_file_state = getattr(self.file_page, "load_state", None)
        if callable(load_file_state):
            load_file_state(dict(preset.file_options or {}))
        else:
            self.session_state.file_state.update(dict(preset.file_options or {}))

        if self.session_state.mapping_context is not None:
            self._apply_workflow_preset_to_mapping_context(self.session_state.mapping_context, preset)
            preview_context = self.pipeline_service.build_root_item_preview_context(
                self.session_state.mapping_context,
                self.session_state.mapping_context.root_item_config,
            )
            self.root_item_structure_page.load_context(preview_context)
            self.root_item_field_page.load_context(preview_context)
            self.mapping_page.load_context(
                self.session_state.mapping_context.upload_mode,
                self.session_state.mapping_context.upload_columns,
                self.session_state.mapping_context.schema_df,
                self.session_state.mapping_context.selected_mapping,
                self.session_state.mapping_context.selected_mapping_modes,
                self.session_state.mapping_context.default_value_candidates,
                self.session_state.mapping_context.selected_default_values,
                self.session_state.mapping_context.selected_default_value_modes,
                self.session_state.mapping_context.selected_tracker_item_settings,
                self.session_state.mapping_context.wizard.state.upload_df,
            )
            self.session_state.validation_context = None
            self.session_state.upload_result = None
            if getattr(self, "_current_page", None) in {
                self.validation_page,
                self.upload_page,
                self.result_page,
            }:
                self._show_page(self.mapping_page)

        message = (
            "저장된 전체 설정을 자동으로 불러왔습니다."
            if startup
            else "전체 설정을 불러왔습니다. 파일을 선택한 뒤 검증을 다시 실행하세요."
        )
        self.statusBar().showMessage(message)

    def _save_workflow_preset(self) -> None:
        try:
            preset = self._collect_workflow_preset()
            self.settings_store.save_workflow_preset(preset)
            self.session_state.workflow_preset = preset
            if not self.settings_store.app_settings_path.exists():
                self.settings_store.save(preset.settings)
        except Exception as exc:
            self.statusBar().showMessage(str(exc))
            self._show_error_dialog("전체 설정 저장 실패", str(exc))
            return
        self.statusBar().showMessage("전체 설정을 저장했습니다.")
        self._show_info_dialog("전체 설정 저장", "전체 설정을 저장했습니다.")

    def _load_workflow_preset(self) -> None:
        try:
            preset = self.settings_store.load_workflow_preset()
            if preset is None:
                self._show_error_dialog("전체 설정 없음", "저장된 전체 설정이 없습니다.")
                return
            self._apply_workflow_preset(preset)
        except Exception as exc:
            self.statusBar().showMessage(str(exc))
            self._show_error_dialog("전체 설정 불러오기 실패", str(exc))
            return
        self._show_info_dialog(
            "전체 설정 불러오기",
            "전체 설정을 불러왔습니다. 파일과 매핑을 확인한 뒤 다시 검증하세요.",
        )

    def _show_mapping_page(self) -> None:
        self._show_page(self.mapping_page)

    def _preview_root_item_config(self, root_item_config: dict[str, object]):
        """`preview_root_item_config` 미리보기를 계산한다."""
        if self.session_state.mapping_context is None:
            raise ValueError("루트 데이터 컨텍스트가 준비되지 않았습니다.")
        return self.pipeline_service.build_root_item_preview_context(
            self.session_state.mapping_context,
            root_item_config,
        )

    def _enter_validation_page(self) -> None:
        self._show_page(self.validation_page)

    def _enter_upload_page(self) -> None:
        self.upload_page.reset(0)
        if self.session_state.settings.offline_mode:
            self.upload_page.dry_run_checkbox.setChecked(True)
            self.upload_page.dry_run_checkbox.setEnabled(False)
            self.upload_page.status_label.setText("테스트 모드에서는 Dry Run만 실행할 수 있습니다.")
        else:
            self.upload_page.dry_run_checkbox.setEnabled(True)
            action_label = gui_upload_mode_action_label(
                getattr(self.session_state.settings, "upload_mode", None)
            )
            self.upload_page.status_label.setText(f"{action_label} 준비 완료")
        self._show_page(self.upload_page)

    def _enter_result_page(self) -> None:
        if self.session_state.upload_result is not None:
            self.result_page.set_results(self.session_state.upload_result)
        self._show_page(self.result_page)

    def _restart_upload_flow(self) -> None:
        self.session_state.validation_context = None
        self.session_state.upload_result = None
        self.upload_progress = UploadProgressState()
        self._show_page(self.project_page)

    def _on_prepare_root_item_context(self) -> None:
        settings = self.session_state.settings
        if not settings.default_project_id or not settings.default_tracker_id:
            raise ValueError("프로젝트와 트래커를 먼저 선택해야 합니다.")
        mapping_context = self._run_with_busy(
            "매핑 대상 컬럼과 스키마를 준비하는 중입니다.",
            self.pipeline_service.prepare_mapping_context,
            settings,
            self.session_state.file_state,
        )
        if self.session_state.workflow_preset is not None:
            self._apply_workflow_preset_to_mapping_context(
                mapping_context,
                self.session_state.workflow_preset,
            )
        self.session_state.mapping_context = mapping_context
        upload_mode = normalize_gui_upload_mode(mapping_context.upload_mode)
        if upload_mode == GUI_UPLOAD_MODE_UPDATE:
            self._attach_navigation(
                self.mapping_page,
                previous_page=self.file_page,
                next_page=self.validation_page,
                next_handler=self._enter_validation_page,
            )
            self.mapping_page.load_context(
                self.session_state.mapping_context.upload_mode,
                self.session_state.mapping_context.upload_columns,
                self.session_state.mapping_context.schema_df,
                self.session_state.mapping_context.selected_mapping,
                self.session_state.mapping_context.selected_mapping_modes,
                self.session_state.mapping_context.default_value_candidates,
                self.session_state.mapping_context.selected_default_values,
                self.session_state.mapping_context.selected_default_value_modes,
                self.session_state.mapping_context.selected_tracker_item_settings,
                self.session_state.mapping_context.wizard.state.upload_df,
            )
            self._show_page(self.mapping_page)
            return

        self._attach_navigation(
            self.mapping_page,
            previous_page=self.root_item_field_page,
            next_page=self.validation_page,
            next_handler=self._enter_validation_page,
        )
        root_preview_context = self.pipeline_service.build_root_item_preview_context(
            mapping_context,
            mapping_context.root_item_config,
        )
        self.root_item_structure_page.load_context(root_preview_context)
        self.root_item_field_page.load_context(root_preview_context)
        self._show_page(self.root_item_structure_page)

    def _on_confirm_root_item_structure_config(self) -> None:
        if self.session_state.mapping_context is None:
            raise ValueError("매핑 컨텍스트가 준비되지 않았습니다.")
        root_item_config = _merge_root_item_page_configs(
            self.session_state.mapping_context.root_item_config,
            structure_config=(
                self.root_item_structure_page.get_config()
                if callable(getattr(self.root_item_structure_page, "get_config", None))
                else None
            ),
            field_config=(
                self.root_item_field_page.get_config()
                if callable(getattr(self.root_item_field_page, "get_config", None))
                else None
            ),
        )
        self.session_state.mapping_context.root_item_config = root_item_config
        root_preview_context = self.pipeline_service.build_root_item_preview_context(
            self.session_state.mapping_context,
            self.session_state.mapping_context.root_item_config,
        )
        self.root_item_field_page.load_context(root_preview_context)
        self._show_page(self.root_item_field_page)

    def _on_confirm_root_item_field_config(self) -> None:
        if self.session_state.mapping_context is None:
            raise ValueError("매핑 컨텍스트가 준비되지 않았습니다.")
        self.session_state.mapping_context.root_item_config = self.root_item_field_page.get_config()
        self.mapping_page.load_context(
            self.session_state.mapping_context.upload_mode,
            self.session_state.mapping_context.upload_columns,
            self.session_state.mapping_context.schema_df,
            self.session_state.mapping_context.selected_mapping,
            self.session_state.mapping_context.selected_mapping_modes,
            self.session_state.mapping_context.default_value_candidates,
            self.session_state.mapping_context.selected_default_values,
            self.session_state.mapping_context.selected_default_value_modes,
            self.session_state.mapping_context.selected_tracker_item_settings,
            self.session_state.mapping_context.wizard.state.upload_df,
        )
        self._show_page(self.mapping_page)

    def _validate_mapping(
        self,
        selected_mapping: dict[str, str],
        selected_mapping_modes: dict[str, dict[str, bool]],
        selected_default_values: dict[str, str],
        selected_default_value_modes: dict[str, dict[str, bool]],
        selected_tracker_item_settings: dict[str, dict[str, object]],
    ) -> None:
        """`validate_mapping` 입력을 검증한다."""
        if self.session_state.mapping_context is None:
            raise ValueError("매핑 컨텍스트가 준비되지 않았습니다.")
        validation_context = self._run_with_busy(
            "매핑을 검증하고 payload를 준비하는 중입니다.",
            self.pipeline_service.validate_mapping,
            self.session_state.mapping_context,
            selected_mapping,
            selected_default_values,
            selected_tracker_item_settings,
            selected_mapping_modes=selected_mapping_modes,
            selected_default_value_modes=selected_default_value_modes,
        )
        self.session_state.validation_context = validation_context
        self.validation_page.set_results(
            validation_context.issue_df,
            validation_context.has_blocking_issues,
            validation_context.summary_stats,
        )
