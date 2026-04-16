from __future__ import annotations

import time


def _require_qt():
    try:
        from PySide6.QtCore import QThread
        from PySide6.QtCore import Signal
    except ImportError as exc:
        raise RuntimeError("GUI 실행에는 PySide6 패키지가 필요합니다.") from exc
    return {"QThread": QThread, "Signal": Signal}


class UploadWorker:
    """wizard.upload 를 백그라운드에서 실행하고 진행 상황을 signal 로 알린다."""

    def __new__(cls, wizard, *, dry_run: bool, continue_on_error: bool, output_dir: str):
        qt = _require_qt()
        base_cls = qt["QThread"]
        Signal = qt["Signal"]

        class _UploadWorker(base_cls):
            log_message = Signal(str)
            progress_changed = Signal(int, int, str)
            upload_finished = Signal(object)
            upload_failed = Signal(str)

            def __init__(self, wizard, dry_run: bool, continue_on_error: bool, output_dir: str) -> None:
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
                    total_count = int((payload_df["payload_status"] == "ready").sum()) if not payload_df.empty else 0
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
                        elif event_type in {"row_success", "row_failed"}:
                            progress_state["completed"] += 1
                            self.progress_changed.emit(
                                progress_state["completed"],
                                total_count,
                                str(event.get("upload_name") or ""),
                            )
                            message = str(event.get("message") or "")
                            if message:
                                self.log_message.emit(message)
                        elif event_type == "log":
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
                        try:
                            self.wizard.save_state(self.output_dir)
                        except Exception:
                            pass
                        self.upload_failed.emit("업로드가 사용자 요청으로 중단되었습니다.")
                        return
                    self.upload_failed.emit(str(exc))

        return _UploadWorker(wizard, dry_run=dry_run, continue_on_error=continue_on_error, output_dir=output_dir)
