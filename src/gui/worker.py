from __future__ import annotations

import time
from typing import Any
from typing import Callable

from src.models import PayloadStatus

from .qt import QThreadBase
from .qt import Signal


class UploadWorker(QThreadBase):
    """wizard.upload 를 백그라운드에서 실행하고 진행 상황을 signal 로 알린다."""

    log_message = Signal(str)
    progress_changed = Signal(int, int, str)
    upload_finished = Signal(object)
    upload_failed = Signal(str)

    def __init__(self, wizard, *, dry_run: bool, continue_on_error: bool, output_dir: str) -> None:
        super().__init__()
        self.wizard = wizard
        self.dry_run = dry_run
        self.continue_on_error = continue_on_error
        self.output_dir = output_dir
        self._pause_requested = False
        self._cancel_requested = False

    def request_pause(self) -> None:
        self._pause_requested = True

    def request_resume(self) -> None:
        self._pause_requested = False

    def request_cancel(self) -> None:
        self._cancel_requested = True

    def run(self) -> None:
        try:
            payload_df = self.wizard.build_payloads()
            total_count = (
                int((payload_df["payload_status"] == PayloadStatus.READY.value).sum())
                if not payload_df.empty
                else 0
            )
            progress_state = {"completed": 0}

            def _event_callback(event: dict[str, object]) -> None:
                while self._pause_requested and not self._cancel_requested:
                    time.sleep(0.1)
                if self._cancel_requested:
                    raise RuntimeError("__UPLOAD_CANCELLED__")

                event_type = str(event.get("type"))
                if event_type == "row_started":
                    self.progress_changed.emit(
                        progress_state["completed"],
                        total_count,
                        str(event.get("upload_name") or ""),
                    )
                    return

                if event_type in {"row_success", "row_failed"}:
                    progress_state["completed"] += 1
                    self.progress_changed.emit(
                        progress_state["completed"],
                        total_count,
                        str(event.get("upload_name") or ""),
                    )
                    message = str(event.get("message") or "")
                    if message:
                        self.log_message.emit(message)
                    return

                if event_type == "log":
                    self.log_message.emit(str(event.get("message") or ""))

            result = self.wizard.upload(
                dry_run=self.dry_run,
                continue_on_error=self.continue_on_error,
                event_callback=_event_callback,
                cancel_requested=lambda: self._cancel_requested,
                pause_requested=lambda: self._pause_requested,
            )
            self.wizard.save_state(self.output_dir)
            self.upload_finished.emit(result)
        except Exception as exc:
            if str(exc) == "__UPLOAD_CANCELLED__":
                self._handle_cancelled_upload()
                return
            self.upload_failed.emit(str(exc))

    def _handle_cancelled_upload(self) -> None:
        try:
            self.wizard.save_state(self.output_dir)
        except Exception:
            pass
        self.upload_failed.emit("업로드가 사용자 요청으로 중단되었습니다.")


class BackgroundTask(QThreadBase):
    """짧은 GUI 보조 작업을 백그라운드에서 실행하는 범용 worker다."""

    completed = Signal(object)
    failed = Signal(object)

    def __init__(self, func: Callable[..., Any], *args, **kwargs) -> None:
        super().__init__()
        self.func = func
        self.args = args
        self.kwargs = kwargs

    def run(self) -> None:
        try:
            result = self.func(*self.args, **self.kwargs)
            self.completed.emit(result)
        except Exception as exc:
            self.failed.emit(exc)
