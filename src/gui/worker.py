from __future__ import annotations

import time

from .qt import require_qt

QT = require_qt()
QThreadBase = QT["QThread"]
Signal = QT["Signal"]


class UploadWorker(QThreadBase):
    """배치 업로드를 백그라운드에서 실행하고 진행 상황을 signal 로 알린다."""

    log_message = Signal(str)
    progress_changed = Signal(int, int, str)
    upload_event = Signal(object)
    upload_finished = Signal(object)
    upload_failed = Signal(str)

    def __init__(
        self,
        pipeline_service,
        *,
        settings,
        file_state,
        mapping_context,
        dry_run: bool,
        continue_on_error: bool,
        output_dir: str,
    ) -> None:
        """업로드 실행에 필요한 의존성과 상태를 보관한다."""
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
        """다음 안전 지점에서 업로드를 멈추도록 요청한다."""
        self._pause_requested = True

    def request_resume(self) -> None:
        """일시정지 플래그를 해제해 다음 항목부터 업로드를 재개한다."""
        self._pause_requested = False

    def request_cancel(self) -> None:
        """다음 안전 지점에서 업로드를 중단하도록 요청한다."""
        self._cancel_requested = True

    def _handle_upload_event(
        self,
        event: dict[str, object],
        progress_state: dict[str, int],
    ) -> None:
        """파이프라인 이벤트를 GUI signal 형식으로 변환한다."""
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
            return

        if event_type == "row_started":
            self.progress_changed.emit(
                progress_state["completed"],
                progress_state["total"],
                str(event.get("upload_name") or ""),
            )
            return

        if event_type in {"row_success", "row_failed"}:
            progress_state["completed"] += 1
            self.progress_changed.emit(
                progress_state["completed"],
                progress_state["total"],
                str(event.get("upload_name") or ""),
            )
            return

        if event_type == "log":
            message = str(event.get("message") or "")
            if message:
                self.log_message.emit(message)

    def run(self) -> None:
        """배치 업로드를 실행하고 완료 또는 실패 signal 을 보낸다."""
        try:
            progress_state = {"completed": 0, "total": 1}
            result = self.pipeline_service.run_batch_upload(
                self.settings,
                self.file_state,
                self.mapping_context,
                dry_run=self.dry_run,
                continue_on_error=self.continue_on_error,
                output_dir=self.output_dir,
                event_callback=lambda event: self._handle_upload_event(event, progress_state),
                cancel_requested=lambda: self._cancel_requested,
                pause_requested=lambda: self._pause_requested,
            )
            self.upload_finished.emit(result)
        except Exception as exc:
            if str(exc) == "__UPLOAD_CANCELLED__":
                self.upload_failed.emit("업로드가 사용자 요청으로 중단되었습니다.")
                return
            self.upload_failed.emit(str(exc))


class BackgroundTask(QThreadBase):
    """짧은 GUI 보조 작업을 백그라운드에서 실행하는 범용 worker다."""

    completed = Signal(object)
    failed = Signal(object)

    def __init__(self, func, *args, **kwargs) -> None:
        """실행할 호출 객체와 인자를 저장한다."""
        super().__init__()
        self.func = func
        self.args = args
        self.kwargs = kwargs

    def run(self) -> None:
        """호출 결과를 완료 또는 실패 signal 로 전달한다."""
        try:
            result = self.func(*self.args, **self.kwargs)
            self.completed.emit(result)
        except Exception as exc:
            self.failed.emit(exc)
