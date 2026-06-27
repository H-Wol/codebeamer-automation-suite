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
    """배치 업로드를 백그라운드에서 실행하고 진행 상황을 signal 로 알린다."""

    def __new__(
        cls,
        pipeline_service,
        *,
        settings,
        file_state,
        mapping_context,
        dry_run: bool,
        continue_on_error: bool,
        output_dir: str,
    ):
        qt = _require_qt()
        base_cls = qt["QThread"]
        Signal = qt["Signal"]

        class _UploadWorker(base_cls):
            log_message = Signal(str)
            progress_changed = Signal(int, int, str)
            upload_event = Signal(object)
            upload_finished = Signal(object)
            upload_failed = Signal(str)

            def __init__(
                self,
                pipeline_service,
                settings,
                file_state,
                mapping_context,
                dry_run: bool,
                continue_on_error: bool,
                output_dir: str,
            ) -> None:
                super().__init__()
                self.pipeline_service = pipeline_service
                self.settings = settings
                self.file_state = dict(file_state)
                self.mapping_context = mapping_context
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
                    progress_state = {"completed": 0, "total": 1}

                    def _event_callback(event: dict[str, object]) -> None:
                        while self._pause_requested and not self._cancel_requested:
                            time.sleep(0.1)
                        if self._cancel_requested:
                            raise RuntimeError("__UPLOAD_CANCELLED__")

                        event_type = str(event.get("type"))
                        self.upload_event.emit(dict(event))
                        if event_type == "batch_total":
                            total_value = event.get("total")
                            try:
                                progress_state["total"] = max(int(total_value), 1)
                            except Exception:
                                progress_state["total"] = 1
                            self.progress_changed.emit(
                                progress_state["completed"],
                                progress_state["total"],
                                "",
                            )
                        elif event_type == "row_started":
                            self.progress_changed.emit(
                                progress_state["completed"],
                                progress_state["total"],
                                str(event.get("upload_name") or ""),
                            )
                        elif event_type in {"row_success", "row_failed"}:
                            progress_state["completed"] += 1
                            self.progress_changed.emit(
                                progress_state["completed"],
                                progress_state["total"],
                                str(event.get("upload_name") or ""),
                            )
                        elif event_type == "log":
                            message = str(event.get("message") or "")
                            if message:
                                self.log_message.emit(message)

                    result = self.pipeline_service.run_batch_upload(
                        self.settings,
                        self.file_state,
                        self.mapping_context,
                        dry_run=self.dry_run,
                        continue_on_error=self.continue_on_error,
                        output_dir=self.output_dir,
                        event_callback=_event_callback,
                        cancel_requested=lambda: self._cancel_requested,
                        pause_requested=lambda: self._pause_requested,
                    )
                    self.upload_finished.emit(result)
                except Exception as exc:
                    if str(exc) == "__UPLOAD_CANCELLED__":
                        self.upload_failed.emit("업로드가 사용자 요청으로 중단되었습니다.")
                        return
                    self.upload_failed.emit(str(exc))

        return _UploadWorker(
            pipeline_service,
            settings,
            file_state,
            mapping_context,
            dry_run=dry_run,
            continue_on_error=continue_on_error,
            output_dir=output_dir,
        )


class BackgroundTask:
    """짧은 GUI 보조 작업을 백그라운드에서 실행하는 범용 worker다."""

    def __new__(cls, func, *args, **kwargs):
        qt = _require_qt()
        base_cls = qt["QThread"]
        Signal = qt["Signal"]

        class _BackgroundTask(base_cls):
            completed = Signal(object)
            failed = Signal(object)

            def __init__(self, func, args, kwargs) -> None:
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

        return _BackgroundTask(func, args, kwargs)
