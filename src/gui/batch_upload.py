from __future__ import annotations

from pathlib import Path
import time
from typing import Any
from typing import Callable

import pandas as pd

from src.models import PayloadStatus
from src.upload_pipeline import load_tracker_schema_df
from src.upload_pipeline import prepare_upload_dataframe
from src.upload_policy import UPLOAD_MODE_CREATE as GUI_UPLOAD_MODE_CREATE
from src.upload_policy import UPLOAD_MODE_UPDATE as GUI_UPLOAD_MODE_UPDATE
from src.upload_policy import UPLOAD_MODE_UPSERT as GUI_UPLOAD_MODE_UPSERT
from src.upload_policy import normalize_upload_mode as normalize_gui_upload_mode
from src.upload_policy import upload_mode_action_label as gui_upload_mode_action_label
from src.upload_policy import upload_mode_allows_root_items as gui_upload_mode_allows_root_items
from src.upload_policy import upload_mode_supports_update as gui_upload_mode_supports_update
from src.wizard import CodebeamerUploadWizard

from .batch_validation import BatchValidationService
from .root_item_service import RootItemService
from .upload_context import BatchUploadJob
from .upload_context import MappingContext
from .upload_context import RootItemUploadSpec


class BatchUploadService:
    """파일별 wizard 준비, 진행 제어와 batch upload 결과 집계를 담당한다."""

    def __init__(
        self,
        *,
        mapper: Any,
        create_wizard: Callable[[Any], CodebeamerUploadWizard],
        root_items: RootItemService,
        batch_validation: BatchValidationService,
    ) -> None:
        self.mapper = mapper
        self.create_wizard = create_wizard
        self.root_items = root_items
        self.batch_validation = batch_validation

    @staticmethod
    def _normalize_file_paths(file_state: dict[str, Any]) -> list[str]:
        return BatchValidationService._normalize_file_paths(file_state)

    def _cached_raw_df_for_file(
        self,
        preview_data: Any,
        file_path: str,
    ) -> pd.DataFrame | None:
        return self.batch_validation._cached_raw_df_for_file(preview_data, file_path)

    def build_root_item_payload_specs(
        self,
        mapping_context: MappingContext,
        wizard: CodebeamerUploadWizard,
        file_path: str,
    ) -> list[RootItemUploadSpec]:
        return self.root_items.build_root_item_payload_specs(
            mapping_context,
            wizard,
            file_path,
        )

    @staticmethod
    def _batch_output_dir(output_dir: str, file_path: str, index: int) -> str:
        safe_name = Path(file_path).stem.strip() or f"file_{index:03d}"
        return str(Path(output_dir) / f"{index:03d}_{safe_name}")

    @staticmethod
    def _ready_upload_count(
        wizard: CodebeamerUploadWizard,
        root_item_specs: list[RootItemUploadSpec] | None = None,
    ) -> int:
        insert_count, update_count = BatchUploadService._phase_ready_counts(
            wizard,
            root_item_specs=root_item_specs,
        )
        return insert_count + update_count

    @staticmethod
    def _phase_ready_counts(
        wizard: CodebeamerUploadWizard,
        root_item_specs: list[RootItemUploadSpec] | None = None,
    ) -> tuple[int, int]:
        payload_df = wizard.state.payload_df if wizard.state.payload_df is not None else wizard.build_payloads()
        if payload_df is None or payload_df.empty:
            return (0, 0)

        ready_df = payload_df[payload_df["payload_status"] == PayloadStatus.READY.value].copy()
        upload_mode = normalize_gui_upload_mode(getattr(wizard.state, "upload_mode", GUI_UPLOAD_MODE_CREATE))
        if ready_df.empty:
            return (0, 0)

        if upload_mode == GUI_UPLOAD_MODE_UPDATE:
            return (0, int(len(ready_df)))

        if upload_mode == GUI_UPLOAD_MODE_UPSERT and "_operation" in ready_df.columns:
            operation_series = ready_df["_operation"].fillna("").astype(str).str.lower()
            insert_count = int(operation_series.eq("create").sum())
            update_count = int(operation_series.eq("update").sum())
            if insert_count > 0 and root_item_specs:
                insert_count += len(root_item_specs)
            return (insert_count, update_count)

        insert_count = int(len(ready_df))
        if (
            insert_count > 0
            and root_item_specs
            and gui_upload_mode_allows_root_items(upload_mode)
        ):
            insert_count += len(root_item_specs)
        return (insert_count, 0)

    @staticmethod
    def _annotate_batch_result_frame(
        df: pd.DataFrame | None,
        *,
        file_label: str,
        file_path: str,
    ) -> pd.DataFrame:
        return BatchValidationService._annotate_source_frame(
            df,
            file_label=file_label,
            file_path=file_path,
        )

    def _prepare_wizard_for_file(
        self,
        settings,
        mapping_context: MappingContext,
        *,
        file_path: str,
        sheet_name: str,
        header_row: int,
        summary_col: str,
    ) -> CodebeamerUploadWizard:
        wizard = self.create_wizard(settings)
        wizard.select_project(int(settings.default_project_id))
        wizard.select_tracker(int(settings.default_tracker_id))
        wizard.state.upload_mode = normalize_gui_upload_mode(mapping_context.upload_mode)

        schema = mapping_context.wizard.state.schema
        if schema is None:
            schema, _ = load_tracker_schema_df(wizard)
        schema_df = mapping_context.schema_df

        prepare_upload_dataframe(
            wizard,
            file_path=file_path,
            sheet_name=sheet_name,
            header_row=header_row,
            summary_col=summary_col,
            selected_mapping=mapping_context.selected_mapping,
            schema=schema,
            schema_df=schema_df,
            raw_df=self._cached_raw_df_for_file(mapping_context.preview_data, file_path),
        )

        wizard.state.selected_mapping = dict(mapping_context.selected_mapping)
        wizard.state.selected_mapping_modes = {
            str(key): dict(value)
            for key, value in dict(mapping_context.selected_mapping_modes or {}).items()
            if str(key).strip() and isinstance(value, dict)
        }
        wizard.state.schema = schema
        wizard.state.schema_df = schema_df
        wizard.state.selected_default_value_modes = {
            str(key): dict(value)
            for key, value in dict(mapping_context.selected_default_value_modes or {}).items()
            if str(key).strip() and isinstance(value, dict)
        }
        wizard.state.selected_tracker_item_settings = dict(mapping_context.selected_tracker_item_settings)
        wizard.state.tracker_item_lookup_cache = dict(mapping_context.tracker_item_lookup_cache)
        wizard.state.existing_item_cache = {}
        wizard.state.comparison_df = wizard.mapper.compare_upload_df_with_schema(
            upload_df=wizard.state.upload_df,
            schema_df=schema_df,
            selected_mapping=wizard.state.selected_mapping,
        )
        wizard._detect_table_field_columns()
        wizard.process_option_mapping(
            wizard.state.selected_mapping,
            selected_mapping_modes=wizard.state.selected_mapping_modes,
            selected_default_values=mapping_context.selected_default_values,
            selected_default_value_modes=wizard.state.selected_default_value_modes,
            selected_tracker_item_settings=mapping_context.selected_tracker_item_settings,
        )
        wizard.build_payloads(
            force=True,
            fetch_existing_items=not gui_upload_mode_supports_update(mapping_context.upload_mode),
        )
        return wizard

    def run_batch_upload(
        self,
        settings,
        file_state: dict[str, Any],
        mapping_context: MappingContext,
        *,
        dry_run: bool,
        continue_on_error: bool,
        output_dir: str,
        event_callback=None,
        cancel_requested=None,
        pause_requested=None,
    ) -> dict[str, Any]:
        file_paths = mapping_context.file_paths or self._normalize_file_paths(file_state)
        if not file_paths:
            raise ValueError("업로드할 Excel 파일이 없습니다.")
        if not mapping_context.selected_mapping:
            raise ValueError("검증된 매핑이 없습니다.")
        upload_mode = normalize_gui_upload_mode(mapping_context.upload_mode)
        if gui_upload_mode_supports_update(upload_mode) and bool(getattr(settings, "offline_mode", False)):
            raise ValueError("테스트 모드에서는 기존 수정 또는 혼합 처리 작업을 실행할 수 없습니다.")
        if gui_upload_mode_supports_update(upload_mode) and mapping_context.batch_duplicate_update_item_ids:
            duplicate_ids = ", ".join(str(item_id) for item_id in sorted(mapping_context.batch_duplicate_update_item_ids))
            raise ValueError(f"배치 전체에서 중복된 업데이트 대상 id가 있습니다: {duplicate_ids}")
        action_label = gui_upload_mode_action_label(upload_mode)

        sheet_name = str(file_state["sheet_name"])
        header_row = int(file_state["header_row"])
        summary_col = str(file_state["summary_column"])

        prepared_jobs: list[BatchUploadJob] = []
        success_frames: list[pd.DataFrame] = []
        failed_frames: list[pd.DataFrame] = []
        unresolved_frames: list[pd.DataFrame] = []
        created_map_by_file: dict[str, dict[Any, Any]] = {}
        total_count = 0
        phase_total_counts = {"insert": 0, "update": 0}
        phase_results = {
            "insert": {"total": 0, "success": 0, "failed": 0, "unresolved": 0},
            "update": {"total": 0, "success": 0, "failed": 0, "unresolved": 0},
        }

        def _emit(event: dict[str, Any]) -> None:
            if event_callback is not None:
                event_callback(event)

        def _sync_control() -> None:
            """`sync_control` 상태를 동기화한다."""
            while pause_requested is not None and pause_requested():
                time.sleep(0.1)
            if cancel_requested is not None and cancel_requested():
                raise RuntimeError("__UPLOAD_CANCELLED__")

        for index, file_path in enumerate(file_paths, start=1):
            _sync_control()
            file_label = Path(file_path).name
            _emit({
                "type": "log",
                "message": f"[{file_label}] {action_label} 데이터를 준비하는 중입니다.",
            })
            try:
                wizard = self._prepare_wizard_for_file(
                    settings,
                    mapping_context,
                    file_path=file_path,
                    sheet_name=sheet_name,
                    header_row=header_row,
                    summary_col=summary_col,
                )
                if gui_upload_mode_allows_root_items(upload_mode):
                    root_item_specs = self.build_root_item_payload_specs(mapping_context, wizard, file_path)
                else:
                    root_item_specs = []
                insert_ready_count, update_ready_count = self._phase_ready_counts(wizard, root_item_specs)
                ready_count = insert_ready_count + update_ready_count
                total_count += ready_count
                phase_total_counts["insert"] += insert_ready_count
                phase_total_counts["update"] += update_ready_count
                prepared_jobs.append(BatchUploadJob(
                    file_path=file_path,
                    file_label=file_label,
                    root_item_specs=root_item_specs,
                    ready_count=ready_count,
                    insert_ready_count=insert_ready_count,
                    update_ready_count=update_ready_count,
                    output_dir=self._batch_output_dir(output_dir, file_path, index),
                    wizard=wizard,
                ))
            except Exception as exc:
                fallback_root_item_name = Path(file_path).stem.strip() or file_label
                failed_frames.append(pd.DataFrame([{
                    "source_file": file_label,
                    "source_file_path": file_path,
                    "_row_id": None,
                    "parent_row_id": None,
                    "upload_name": fallback_root_item_name,
                    "error": str(exc),
                    "status": PayloadStatus.FAILED.value,
                }]))
                _emit({
                    "type": "log",
                    "message": f"[{file_label}] 업로드 준비 실패: {exc}",
                })
                if not continue_on_error:
                    break

        _emit({
            "type": "batch_total",
            "total": total_count,
            "phase_totals": dict(phase_total_counts),
        })

        for job_index, job in enumerate(prepared_jobs, start=1):
            _sync_control()
            _emit({
                "type": "log",
                "message": f"[{job_index}/{len(prepared_jobs)}] {job.file_label} {action_label}를 시작합니다.",
            })

            def _forward_event(event: dict[str, Any]) -> None:
                forwarded = dict(event)
                forwarded["source_file"] = job.file_label
                forwarded["source_file_path"] = job.file_path

                upload_name = str(forwarded.get("upload_name") or "").strip()
                forwarded["upload_name"] = (
                    f"[{job.file_label}] {upload_name}"
                    if upload_name
                    else f"[{job.file_label}]"
                )

                message = str(forwarded.get("message") or "").strip()
                if message:
                    forwarded["message"] = f"[{job.file_label}] {message}"

                _emit(forwarded)

            if upload_mode == GUI_UPLOAD_MODE_UPDATE:
                result = job.wizard.update_items(
                    dry_run=dry_run,
                    continue_on_error=continue_on_error,
                    event_callback=_forward_event,
                    cancel_requested=cancel_requested,
                    pause_requested=pause_requested,
                )
            elif upload_mode == GUI_UPLOAD_MODE_UPSERT:
                result = job.wizard.upsert_items(
                    dry_run=dry_run,
                    continue_on_error=continue_on_error,
                    top_level_parent_specs=[
                        {
                            "key": spec.key,
                            "name": spec.name,
                            "field_values": dict(spec.field_values),
                            "row_ids": list(spec.row_ids),
                            "parent_key": spec.parent_key,
                            "kind": spec.kind,
                        }
                        for spec in job.root_item_specs
                    ],
                    event_callback=_forward_event,
                    cancel_requested=cancel_requested,
                    pause_requested=pause_requested,
                )
            else:
                result = job.wizard.upload(
                    dry_run=dry_run,
                    continue_on_error=continue_on_error,
                    top_level_parent_specs=[
                        {
                            "key": spec.key,
                            "name": spec.name,
                            "field_values": dict(spec.field_values),
                            "row_ids": list(spec.row_ids),
                            "parent_key": spec.parent_key,
                            "kind": spec.kind,
                        }
                        for spec in job.root_item_specs
                    ],
                    event_callback=_forward_event,
                    cancel_requested=cancel_requested,
                    pause_requested=pause_requested,
                )
            job.wizard.save_state(job.output_dir)
            created_map_by_file[job.file_path] = result.get("created_map", {})

            success_df = self._annotate_batch_result_frame(
                result.get("success_df"),
                file_label=job.file_label,
                file_path=job.file_path,
            )
            failed_df = self._annotate_batch_result_frame(
                result.get("failed_df"),
                file_label=job.file_label,
                file_path=job.file_path,
            )
            unresolved_df = self._annotate_batch_result_frame(
                result.get("unresolved_df"),
                file_label=job.file_label,
                file_path=job.file_path,
            )

            if not success_df.empty:
                success_frames.append(success_df)
            if not failed_df.empty:
                failed_frames.append(failed_df)
            if not unresolved_df.empty:
                unresolved_frames.append(unresolved_df)

            for phase_name in ("insert", "update"):
                if not success_df.empty and "phase" in success_df.columns:
                    phase_results[phase_name]["success"] += int(
                        success_df["phase"].fillna("").astype(str).str.lower().eq(phase_name).sum()
                    )
                if not failed_df.empty and "phase" in failed_df.columns:
                    phase_results[phase_name]["failed"] += int(
                        failed_df["phase"].fillna("").astype(str).str.lower().eq(phase_name).sum()
                    )
                if not unresolved_df.empty and "phase" in unresolved_df.columns:
                    phase_results[phase_name]["unresolved"] += int(
                        unresolved_df["phase"].fillna("").astype(str).str.lower().eq(phase_name).sum()
                    )

            if not continue_on_error and (not failed_df.empty or not unresolved_df.empty):
                break

        for phase_name in ("insert", "update"):
            phase_results[phase_name]["total"] = (
                int(phase_results[phase_name]["success"])
                + int(phase_results[phase_name]["failed"])
                + int(phase_results[phase_name]["unresolved"])
            )

        return {
            "created_map_by_file": created_map_by_file,
            "success_df": pd.concat(success_frames, ignore_index=True) if success_frames else pd.DataFrame(),
            "failed_df": pd.concat(failed_frames, ignore_index=True) if failed_frames else pd.DataFrame(),
            "unresolved_df": pd.concat(unresolved_frames, ignore_index=True) if unresolved_frames else pd.DataFrame(),
            "phase_results": phase_results,
        }
