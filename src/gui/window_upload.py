from __future__ import annotations

from pathlib import Path
import time

from src.upload_policy import upload_mode_action_label as gui_upload_mode_action_label

from .window_support import _format_clock_text
from .window_support import _format_duration_text
from .window_support import _format_upload_eta_text
from .window_support import _format_upload_progress_text
from .window_support import UploadProgressState
from .worker import UploadWorker


class WindowUploadMixin:
    def _start_upload(self) -> None:
        if self.session_state.mapping_context is None:
            self.upload_page.status_label.setText("업로드 컨텍스트가 없습니다.")
            return
        if self.session_state.settings.offline_mode and not self.upload_page.dry_run_checkbox.isChecked():
            message = "테스트 모드에서는 Dry Run만 실행할 수 있습니다."
            self.upload_page.status_label.setText(message)
            self._show_error_dialog("테스트 모드 업로드 제한", message)
            return
        output_dir = str(Path(self.session_state.settings.output_dir))
        self.upload_page.reset(0)
        self.upload_progress = UploadProgressState(
            batch_started_at=time.perf_counter()
        )
        self.upload_worker = UploadWorker(
            self.pipeline_service,
            settings=self.session_state.settings,
            file_state=self.session_state.file_state,
            mapping_context=self.session_state.mapping_context,
            dry_run=self.upload_page.dry_run_checkbox.isChecked(),
            continue_on_error=self.upload_page.continue_checkbox.isChecked(),
            output_dir=output_dir,
        )
        self.upload_worker.progress_changed.connect(self._on_upload_progress)
        self.upload_worker.upload_event.connect(self._on_upload_event)
        self.upload_worker.upload_finished.connect(self._on_upload_finished)
        self.upload_worker.upload_failed.connect(self._on_upload_failed)
        self.upload_page.start_button.setEnabled(False)
        self.upload_page.pause_button.setEnabled(True)
        self.upload_page.cancel_button.setEnabled(True)
        action_label = gui_upload_mode_action_label(
            getattr(self.session_state.settings, "upload_mode", None)
        )
        self.upload_page.status_label.setText(f"{action_label} 실행 중")
        self.upload_worker.start()

    def _pause_upload(self) -> None:
        if self.upload_worker is not None:
            self.upload_worker.request_pause()
            self.upload_page.pause_button.setEnabled(False)
            self.upload_page.resume_button.setEnabled(True)
            self.upload_page.status_label.setText("일시정지 요청됨")

    def _resume_upload(self) -> None:
        if self.upload_worker is not None:
            self.upload_worker.request_resume()
            self.upload_page.pause_button.setEnabled(True)
            self.upload_page.resume_button.setEnabled(False)
            self.upload_page.status_label.setText("업로드 재개")

    def _cancel_upload(self) -> None:
        if self.upload_worker is not None:
            self.upload_worker.request_cancel()
            self.upload_page.status_label.setText("중단 요청됨")

    @staticmethod
    def _format_clock(timestamp: float | None = None) -> str:
        return _format_clock_text(timestamp)

    @staticmethod
    def _format_duration(seconds: float | None) -> str:
        return _format_duration_text(seconds)

    @staticmethod
    def _upload_event_key(event: dict[str, object]) -> str:
        source_file_path = str(event.get("source_file_path") or "").strip()
        row_id = event.get("row_id")
        if row_id is None:
            return f"{source_file_path}::__root__::{str(event.get('upload_name') or '').strip()}"
        return f"{source_file_path}::{row_id}"

    @staticmethod
    def _display_item_name(file_label: str, upload_name: str) -> str:
        prefix = f"[{file_label}] "
        if file_label and upload_name.startswith(prefix):
            return upload_name[len(prefix):].strip() or upload_name
        return upload_name or "-"

    @staticmethod
    def _normalize_phase_key(phase: object) -> str:
        normalized = str(phase or "").strip().lower()
        if normalized == "create":
            return "insert"
        return normalized

    @classmethod
    def _phase_display_name(cls, phase: object) -> str:
        phase_key = cls._normalize_phase_key(phase)
        if phase_key == "insert":
            return "생성"
        if phase_key == "update":
            return "수정"
        return "-"

    @staticmethod
    def _count_phase_rows(df, phase: str) -> int:
        if df is None or getattr(df, "empty", True) or "phase" not in df.columns:
            return 0
        phase_series = df["phase"].fillna("").astype(str).str.lower()
        return int(phase_series.eq(phase).sum())

    def _append_timestamped_log(self, message: str) -> None:
        text = str(message or "").strip()
        if not text:
            return
        self.upload_page.log_view.appendPlainText(f"{self._format_clock()} | {text}")

    def _update_upload_counter(self) -> None:
        progress = self.upload_progress
        self.upload_page.counter_label.setText(
            f"성공 {progress.success_count} / 실패 {progress.failed_count} / 재시도 {progress.retry_count}"
        )
        completed_count = progress.success_count + progress.failed_count
        self.upload_page.total_label.setText(
            f"총 대상 {progress.total_count}건 / 완료 {completed_count}건"
        )
        self.upload_page.phase_total_label.setText(
            "단계별 총 대상: "
            f"생성 {int(progress.phase_totals.get('insert', 0))}건 / "
            f"수정 {int(progress.phase_totals.get('update', 0))}건"
        )
        self.upload_page.phase_counter_label.setText(
            "단계별 결과: "
            f"생성 성공 {int(progress.phase_counts.get('insert_success', 0))} / "
            f"실패 {int(progress.phase_counts.get('insert_failed', 0))} | "
            f"수정 성공 {int(progress.phase_counts.get('update_success', 0))} / "
            f"실패 {int(progress.phase_counts.get('update_failed', 0))}"
        )

    def _update_upload_progress_widgets(self) -> None:
        total = max(int(self.upload_progress.total), 0)
        completed = max(int(self.upload_progress.current), 0)
        clamped_completed = min(completed, total) if total > 0 else 0
        self.upload_page.progress_bar.setMaximum(max(total, 1))
        self.upload_page.progress_bar.setValue(clamped_completed)
        progress_text = _format_upload_progress_text(clamped_completed, total)
        self.upload_page.progress_label.setText(progress_text)
        self.upload_page.progress_bar.setFormat(progress_text.replace("진행률 ", ""))

    def _update_upload_time_label(self) -> None:
        if self.upload_progress.batch_started_at is None:
            self.upload_page.time_label.setText("배치 시간: -")
            self.upload_page.eta_label.setText("예상 종료: -")
            return
        elapsed = time.perf_counter() - self.upload_progress.batch_started_at
        self.upload_page.time_label.setText(
            f"배치 시간: {self._format_duration(elapsed)} 경과 (현재 시각 {self._format_clock()})"
        )
        self.upload_page.eta_label.setText(
            _format_upload_eta_text(
                now_timestamp=time.time(),
                elapsed_seconds=elapsed,
                completed_count=self.upload_progress.current,
                total_count=self.upload_progress.total,
            )
        )

    def _on_upload_event(self, event: dict) -> None:
        event_type = str(event.get("type") or "")
        message = str(event.get("message") or "").strip()
        raw_item_name = str(event.get("upload_name") or "-").strip() or "-"
        file_label = str(event.get("source_file") or "").strip() or "-"
        item_name = self._display_item_name(file_label, raw_item_name)
        row_key = self._upload_event_key(event)

        self._update_upload_time_label()

        if event_type == "log":
            self._append_timestamped_log(message)
            return

        if event_type == "batch_total":
            self.upload_progress.total_count = int(event.get("total") or 0)
            phase_totals = event.get("phase_totals") or {}
            self.upload_progress.phase_totals = {
                "insert": int(phase_totals.get("insert") or 0),
                "update": int(phase_totals.get("update") or 0),
            }
            self.upload_progress.total = self.upload_progress.total_count
            self._update_upload_progress_widgets()
            self._update_upload_counter()
            self._append_timestamped_log(
                f"총 업로드 예정 건수: {self.upload_progress.total_count}"
            )
            return

        if event_type == "phase_started":
            self.upload_progress.current_phase = self._normalize_phase_key(
                event.get("phase")
            )
            phase_name = self._phase_display_name(
                self.upload_progress.current_phase
            )
            total = int(event.get("total") or 0)
            self.upload_page.phase_label.setText(f"현재 단계: {phase_name} ({total}건)")
            self.upload_page.status_label.setText(f"{phase_name} 단계 실행 중")
            self._append_timestamped_log(f"{phase_name} 단계 시작 | 대상 {total}건")
            return

        if event_type == "phase_finished":
            phase_key = self._normalize_phase_key(event.get("phase"))
            phase_name = self._phase_display_name(phase_key)
            success_count = int(event.get("success") or 0)
            failed_count = int(event.get("failed") or 0)
            unresolved_count = int(event.get("unresolved") or 0)
            self._append_timestamped_log(
                f"{phase_name} 단계 완료 | 성공 {success_count} / 실패 {failed_count} / 미해결 {unresolved_count}"
            )
            if self.upload_progress.current_phase == phase_key:
                self.upload_page.phase_label.setText(f"현재 단계: {phase_name} 완료")
            return

        if event_type == "row_started":
            started_at = time.perf_counter()
            self.upload_progress.event_started_at[row_key] = started_at
            phase_name = self._phase_display_name(event.get("phase"))
            self.upload_page.record_activity_started(
                row_key,
                file_label,
                phase_name,
                item_name,
                self._format_clock(),
            )
            self._append_timestamped_log(f"{phase_name} 시작 | {raw_item_name}")
            return

        if event_type not in {"row_success", "row_failed"}:
            return

        started_at = self.upload_progress.event_started_at.get(row_key)
        elapsed = None if started_at is None else (time.perf_counter() - started_at)
        if event_type == "row_success":
            self.upload_progress.success_count += 1
            phase_key = self._normalize_phase_key(event.get("phase"))
            if phase_key == "insert":
                self.upload_progress.phase_counts["insert_success"] += 1
            elif phase_key == "update":
                self.upload_progress.phase_counts["update_success"] += 1
            status_text = "성공"
            if not message:
                message = "업로드 완료"
        else:
            self.upload_progress.failed_count += 1
            phase_key = self._normalize_phase_key(event.get("phase"))
            if phase_key == "insert":
                self.upload_progress.phase_counts["insert_failed"] += 1
            elif phase_key == "update":
                self.upload_progress.phase_counts["update_failed"] += 1
            status_text = "실패"
            if not message:
                message = "업로드 실패"
            response_json = event.get("response_json")
            if response_json not in (None, ""):
                self.upload_page.response_view.setPlainText(str(response_json))
                if hasattr(self.upload_page, "detail_tabs") and hasattr(self.upload_page, "response_tab"):
                    self.upload_page.detail_tabs.setCurrentWidget(self.upload_page.response_tab)
        phase_name = self._phase_display_name(event.get("phase"))

        self.upload_page.record_activity_finished(
            row_key,
            file_label,
            phase_name,
            item_name,
            status=status_text,
            finished_at=self._format_clock(),
            duration_text=self._format_duration(elapsed),
            message=message,
        )
        self._update_upload_counter()
        self._update_upload_time_label()
        self._append_timestamped_log(f"{phase_name} {status_text} | {message}")

    def _on_upload_progress(self, current: int, total: int, upload_name: str) -> None:
        self.upload_progress.current = max(int(current), 0)
        self.upload_progress.total = max(int(total), 0)
        self._update_upload_progress_widgets()
        phase_name = self._phase_display_name(self.upload_progress.current_phase)
        if phase_name != "-":
            self.upload_page.current_label.setText(f"현재 항목: [{phase_name}] {upload_name or '-'}")
        else:
            self.upload_page.current_label.setText(f"현재 항목: {upload_name or '-'}")
        self._update_upload_time_label()

    def _on_upload_finished(self, result: dict) -> None:
        self.session_state.upload_result = result
        self.upload_worker = None
        success_df = result.get("success_df")
        failed_df = result.get("failed_df")
        unresolved_df = result.get("unresolved_df")
        self.upload_progress.success_count = (
            0 if success_df is None else len(success_df)
        )
        self.upload_progress.failed_count = (
            0 if failed_df is None else len(failed_df)
        )
        phase_results = result.get("phase_results") or {}
        self.upload_progress.phase_totals = {
            "insert": int((phase_results.get("insert") or {}).get("total", self.upload_progress.phase_totals.get("insert", 0)) or 0),
            "update": int((phase_results.get("update") or {}).get("total", self.upload_progress.phase_totals.get("update", 0)) or 0),
        }
        self.upload_progress.phase_counts = {
            "insert_success": int((phase_results.get("insert") or {}).get("success", self._count_phase_rows(success_df, "insert")) or 0),
            "insert_failed": int(
                ((phase_results.get("insert") or {}).get("failed", 0) or 0)
                + self._count_phase_rows(unresolved_df, "insert")
            ),
            "update_success": int((phase_results.get("update") or {}).get("success", self._count_phase_rows(success_df, "update")) or 0),
            "update_failed": int(
                ((phase_results.get("update") or {}).get("failed", 0) or 0)
                + self._count_phase_rows(unresolved_df, "update")
            ),
        }
        self.upload_progress.current = (
            self.upload_progress.success_count + self.upload_progress.failed_count
        )
        self._update_upload_progress_widgets()
        self._update_upload_counter()
        if failed_df is not None and not getattr(failed_df, "empty", True) and "error_response_json" in failed_df.columns:
            self.upload_page.response_view.setPlainText(str(failed_df.iloc[0].get("error_response_json") or ""))
            if hasattr(self.upload_page, "detail_tabs") and hasattr(self.upload_page, "response_tab"):
                self.upload_page.detail_tabs.setCurrentWidget(self.upload_page.response_tab)
        self._update_upload_time_label()
        self.upload_page.eta_label.setText(f"예상 종료: 완료됨 ({self._format_clock()})")
        self._append_timestamped_log("배치 업로드가 완료되었습니다.")
        self.upload_page.status_label.setText("업로드 완료")
        self.upload_page.phase_label.setText("현재 단계: 완료")
        self.upload_page.start_button.setEnabled(True)
        self.upload_page.pause_button.setEnabled(False)
        self.upload_page.resume_button.setEnabled(False)
        self.upload_page.cancel_button.setEnabled(False)
        self.upload_page.result_button.setEnabled(True)
        unresolved_count = 0 if unresolved_df is None else len(unresolved_df)
        if self.upload_progress.failed_count or unresolved_count:
            self._show_error_dialog(
                "업로드 결과 확인 필요",
                f"배치 업로드는 종료되었지만 실패 {self.upload_progress.failed_count}건, 미해결 {unresolved_count}건이 남아 있습니다.",
            )

    def _on_upload_failed(self, message: str) -> None:
        self.upload_worker = None
        self.upload_page.status_label.setText(message)
        self._update_upload_time_label()
        self.upload_page.eta_label.setText(f"예상 종료: 중단됨 ({self._format_clock()})")
        self._append_timestamped_log(message)
        self.upload_page.start_button.setEnabled(True)
        self.upload_page.pause_button.setEnabled(False)
        self.upload_page.resume_button.setEnabled(False)
        self.upload_page.cancel_button.setEnabled(False)
        self.upload_page.result_button.setEnabled(True)
        if "사용자 요청으로 중단" not in str(message):
            self._show_error_dialog("업로드 오류", message)
