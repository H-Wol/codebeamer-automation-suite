from __future__ import annotations

import json
from html import escape

try:
    from PySide6.QtCore import Qt
    from PySide6.QtCore import Signal
    from PySide6.QtGui import QImage
    from PySide6.QtGui import QPixmap
    from PySide6.QtWidgets import QAbstractItemView
    from PySide6.QtWidgets import QComboBox
    from PySide6.QtWidgets import QDialog
    from PySide6.QtWidgets import QDialogButtonBox
    from PySide6.QtWidgets import QFrame
    from PySide6.QtWidgets import QGraphicsPixmapItem
    from PySide6.QtWidgets import QGraphicsScene
    from PySide6.QtWidgets import QGraphicsView
    from PySide6.QtWidgets import QHBoxLayout
    from PySide6.QtWidgets import QHeaderView
    from PySide6.QtWidgets import QLabel
    from PySide6.QtWidgets import QPlainTextEdit
    from PySide6.QtWidgets import QPushButton
    from PySide6.QtWidgets import QScrollArea
    from PySide6.QtWidgets import QSplitter
    from PySide6.QtWidgets import QTabWidget
    from PySide6.QtWidgets import QTableWidget
    from PySide6.QtWidgets import QTableWidgetItem
    from PySide6.QtWidgets import QVBoxLayout
    from PySide6.QtWidgets import QWidget
except ImportError as exc:  # pragma: no cover
    raise RuntimeError("GUI 실행에는 PySide6 패키지가 필요합니다.") from exc

from .tracker_content_models import AttachmentResource
from .tracker_content_models import AttachmentSummary
from .tracker_comment_models import ItemComment
from .tracker_comment_models import ItemCommentsSnapshot
from .tracker_query_models import TrackerItemDetail
from .wiki_renderer import codebeamer_wiki_to_html
from .wiki_renderer import is_explicit_wiki_type
from .wiki_content_view import WikiContentView


class ZoomableImageView(QGraphicsView):
    """메모리 이미지의 화면 맞춤과 단계 확대를 제공한다."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._scene = QGraphicsScene(self)
        self.setScene(self._scene)
        self._pixmap_item: QGraphicsPixmapItem | None = None
        self._fit_mode = True
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorViewCenter)

    def set_image(self, data: bytes) -> bool:
        image = QImage.fromData(data)
        self._scene.clear()
        self._pixmap_item = None
        if image.isNull():
            return False
        self._pixmap_item = self._scene.addPixmap(QPixmap.fromImage(image))
        self._scene.setSceneRect(self._pixmap_item.boundingRect())
        self.fit_image()
        return True

    def fit_image(self) -> None:
        if self._pixmap_item is None:
            return
        self.resetTransform()
        self.fitInView(self._pixmap_item, Qt.AspectRatioMode.KeepAspectRatio)
        self._fit_mode = True

    def actual_size(self) -> None:
        if self._pixmap_item is None:
            return
        self.resetTransform()
        self._fit_mode = False

    def zoom_in(self) -> None:
        if self._pixmap_item is None:
            return
        self.scale(1.25, 1.25)
        self._fit_mode = False

    def zoom_out(self) -> None:
        if self._pixmap_item is None:
            return
        self.scale(0.8, 0.8)
        self._fit_mode = False

    def resizeEvent(self, event) -> None:  # noqa: N802 - Qt API
        super().resizeEvent(event)
        if self._fit_mode:
            self.fit_image()

    def wheelEvent(self, event) -> None:  # noqa: N802 - Qt API
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            self.zoom_in() if event.angleDelta().y() > 0 else self.zoom_out()
            event.accept()
            return
        super().wheelEvent(event)


class TrackerItemDetailDialog(QDialog):
    comments_requested = Signal(bool)
    comment_attachment_save_requested = Signal(object)

    def __init__(
        self,
        detail: TrackerItemDetail,
        *,
        description_html: str,
        attachments: tuple[AttachmentSummary, ...] = (),
        image_resources: tuple[AttachmentResource, ...] = (),
        baseline_id: int | None = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.detail = detail
        self.attachments = attachments
        self.image_resources = {
            resource.resource_key: resource for resource in image_resources
        }
        self.baseline_id = baseline_id
        self._comments_state = "idle"
        self.comment_views: dict[str, WikiContentView] = {}
        self._comment_image_html: dict[str, str] = {}
        self._comment_resources: dict[str, dict[str, AttachmentResource]] = {}
        self.setWindowTitle(f"아이템 상세 · #{detail.item_id} {detail.summary.name}")
        self.setMinimumSize(860, 620)
        self.resize(1200, 820)

        layout = QVBoxLayout(self)
        heading = QLabel(
            f"#{detail.item_id} · {detail.summary.name}"
            + (f" · Baseline #{baseline_id}" if baseline_id is not None else ""),
            self,
        )
        heading.setObjectName("tracker_detail_title")
        layout.addWidget(heading)
        context = QLabel(
            "  ›  ".join(
                value
                for value in (
                    detail.summary.project_name,
                    detail.summary.tracker_name,
                    detail.summary.status,
                    f"version {detail.version}" if detail.version is not None else "",
                )
                if value
            ),
            self,
        )
        context.setWordWrap(True)
        context.setObjectName("tracker_detail_breadcrumb")
        layout.addWidget(context)

        self.tabs = QTabWidget(self)
        self.tabs.addTab(self._build_overview_tab(description_html), "개요")
        self.comments_tab = self._build_comments_tab()
        self.tabs.addTab(self.comments_tab, "댓글")
        self.image_tab = self._build_image_tab()
        self.tabs.addTab(self.image_tab, "첨부 이미지")
        self.tabs.addTab(self._build_raw_tab(), "원본 JSON")
        self.tabs.currentChanged.connect(self._comments_tab_changed)
        layout.addWidget(self.tabs, 1)

        if baseline_id is not None:
            self.comments_status.setText(
                "과거 시점의 댓글 조회를 지원하지 않습니다. 현재 댓글을 대신 조회하지 않습니다."
            )
            self.comments_retry.setEnabled(False)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close, self)
        close_button = buttons.button(QDialogButtonBox.StandardButton.Close)
        if close_button is not None:
            close_button.setText("닫기")
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _build_comments_tab(self) -> QWidget:
        tab = QWidget(self)
        layout = QVBoxLayout(tab)
        toolbar = QHBoxLayout()
        self.comments_status = QLabel("탭을 열면 댓글을 조회합니다.", tab)
        self.comments_status.setWordWrap(True)
        toolbar.addWidget(self.comments_status, 1)
        self.comments_retry = QPushButton("다시 시도", tab)
        self.comments_retry.hide()
        self.comments_retry.clicked.connect(lambda: self.comments_requested.emit(True))
        toolbar.addWidget(self.comments_retry)
        layout.addLayout(toolbar)
        self.comments_scroll = QScrollArea(tab)
        self.comments_scroll.setWidgetResizable(True)
        self.comments_container = QWidget(self.comments_scroll)
        self.comments_layout = QVBoxLayout(self.comments_container)
        self.comments_layout.addStretch(1)
        self.comments_scroll.setWidget(self.comments_container)
        layout.addWidget(self.comments_scroll, 1)
        return tab

    def _comments_tab_changed(self, _index: int) -> None:
        if self.baseline_id is not None:
            return
        if self.tabs.currentWidget() is self.comments_tab and self._comments_state == "idle":
            self.set_comments_loading()
            self.comments_requested.emit(False)

    def set_comments_loading(self) -> None:
        self._comments_state = "loading"
        self.comments_status.setText("댓글을 불러오는 중입니다.")
        self.comments_retry.hide()

    def set_comments_error(self, message: str) -> None:
        self._comments_state = "error"
        self.comments_status.setText(str(message))
        self.comments_retry.show()

    @staticmethod
    def _comment_depth(comment: ItemComment, by_id: dict[str, ItemComment]) -> int:
        depth = 0
        parent_id = comment.reply_to_id
        visited: set[str] = set()
        while parent_id and parent_id in by_id and parent_id not in visited and depth < 4:
            visited.add(parent_id)
            depth += 1
            parent_id = by_id[parent_id].reply_to_id
        return depth

    @staticmethod
    def _comment_attachment_is_image(attachment: AttachmentSummary) -> bool:
        mime = str(attachment.mime_type or "").split(";", 1)[0].strip().casefold()
        if mime:
            return mime.startswith("image/")
        return attachment.name.casefold().endswith((".bmp", ".gif", ".jpeg", ".jpg", ".png", ".webp"))

    def set_comments(self, snapshot: ItemCommentsSnapshot) -> None:
        self._comments_state = "loaded"
        while self.comments_layout.count() > 1:
            item = self.comments_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        self.comment_views.clear()
        self._comment_image_html.clear()
        self._comment_resources.clear()
        by_id = {comment.comment_id: comment for comment in snapshot.comments if comment.comment_id}
        for comment in snapshot.comments:
            frame = QFrame(self.comments_container)
            frame.setObjectName("tracker_comment_card")
            frame_layout = QVBoxLayout(frame)
            depth = self._comment_depth(comment, by_id)
            frame_layout.setContentsMargins(12 + depth * 24, 10, 12, 10)
            meta = QLabel(
                " · ".join(value for value in (comment.author or "작성자 없음", comment.created_at or "시각 없음", f"답글 → {comment.reply_to_id}" if comment.reply_to_id else "") if value),
                frame,
            )
            meta.setObjectName("tracker_comment_meta")
            frame_layout.addWidget(meta)
            view = WikiContentView(frame)
            source_html = (
                codebeamer_wiki_to_html(comment.body)
                if is_explicit_wiki_type(comment.format_name)
                else "<p>" + escape(comment.body).replace("\n", "<br>") + "</p>"
            )
            image_blocks = []
            for attachment in comment.attachments:
                if self._comment_attachment_is_image(attachment):
                    resource_key = f"comment-{comment.comment_id}-attachment-{attachment.attachment_id}"
                    image_blocks.append(
                        f'<p><b>{escape(attachment.name)}</b><br><img src="cb-attachment://{resource_key}" alt="{escape(attachment.name)}"></p>'
                    )
                else:
                    row = QHBoxLayout()
                    row.addWidget(QLabel(f"첨부: {attachment.name}", frame), 1)
                    save = QPushButton("저장", frame)
                    save.clicked.connect(lambda _checked=False, value=attachment: self.comment_attachment_save_requested.emit(value))
                    row.addWidget(save)
                    frame_layout.addLayout(row)
            view.setHtml(source_html + "".join(image_blocks))
            view.setMinimumHeight(100)
            frame_layout.insertWidget(1, view)
            self.comment_views[comment.comment_id] = view
            self._comment_image_html[comment.comment_id] = "".join(image_blocks)
            self._comment_resources[comment.comment_id] = {}
            self.comments_layout.insertWidget(self.comments_layout.count() - 1, frame)
        self.comments_status.setText(f"댓글 {len(snapshot.comments)}개" if snapshot.comments else "댓글이 없습니다.")
        self.comments_retry.hide()

    def set_comment_html(self, comment_id: str, html: str) -> None:
        view = self.comment_views.get(str(comment_id))
        if view is not None:
            view.setHtml(str(html or "") + self._comment_image_html.get(str(comment_id), ""))
            for resource in self._comment_resources.get(str(comment_id), {}).values():
                view.add_attachment_resource(resource)

    def add_comment_resource(self, comment_id: str, resource: AttachmentResource) -> bool:
        view = self.comment_views.get(str(comment_id))
        if view is None or not view.add_attachment_resource(resource):
            return False
        self._comment_resources.setdefault(str(comment_id), {})[resource.resource_key] = resource
        return True

    def _build_overview_tab(self, description_html: str) -> QWidget:
        tab = QWidget(self)
        layout = QVBoxLayout(tab)
        splitter = QSplitter(Qt.Orientation.Vertical, tab)

        description = WikiContentView(splitter)
        description.setObjectName("tracker_detail_dialog_description")
        description.setHtml(description_html)
        for resource in self.image_resources.values():
            description.add_attachment_resource(resource)
        splitter.addWidget(description)

        fields = QTableWidget(0, 3, splitter)
        fields.setObjectName("tracker_detail_dialog_fields")
        fields.setHorizontalHeaderLabels(["필드", "값", "유형"])
        fields.setAlternatingRowColors(True)
        fields.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        fields.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        fields.verticalHeader().setVisible(False)
        fields.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        fields.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        fields.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        rows = [
            ("ID", str(self.detail.item_id), "builtin"),
            ("프로젝트", self.detail.summary.project_name or "-", "reference"),
            ("트래커", self.detail.summary.tracker_name or "-", "reference"),
            ("상태", self.detail.summary.status or "-", "reference"),
            ("담당자", ", ".join(self.detail.summary.assignees) or "-", "reference"),
            ("버전", str(self.detail.version) if self.detail.version is not None else "-", "builtin"),
            *(
                (field.name, field.display_value, field.type_name)
                for field in self.detail.custom_fields
            ),
        ]
        fields.setRowCount(len(rows))
        for row, values in enumerate(rows):
            for column, value in enumerate(values):
                fields.setItem(row, column, QTableWidgetItem(str(value)))
        fields.resizeRowsToContents()
        splitter.addWidget(fields)
        splitter.setStretchFactor(0, 2)
        splitter.setStretchFactor(1, 3)
        layout.addWidget(splitter, 1)
        return tab

    def _build_image_tab(self) -> QWidget:
        tab = QWidget(self)
        layout = QVBoxLayout(tab)
        toolbar = QHBoxLayout()
        self.image_combo = QComboBox(tab)
        toolbar.addWidget(self.image_combo, 1)
        zoom_out = QPushButton("축소", tab)
        actual = QPushButton("100%", tab)
        fit = QPushButton("화면 맞춤", tab)
        zoom_in = QPushButton("확대", tab)
        toolbar.addWidget(zoom_out)
        toolbar.addWidget(actual)
        toolbar.addWidget(fit)
        toolbar.addWidget(zoom_in)
        layout.addLayout(toolbar)
        self.image_view = ZoomableImageView(tab)
        self.image_view.setObjectName("tracker_detail_dialog_image")
        layout.addWidget(self.image_view, 1)
        self.image_status = QLabel("표시할 수 있는 이미지 첨부가 없습니다.", tab)
        self.image_status.setWordWrap(True)
        layout.addWidget(self.image_status)

        for attachment in self.attachments:
            key = f"attachment-{attachment.attachment_id}"
            if key in self.image_resources:
                self.image_combo.addItem(attachment.name, key)
        self.image_combo.currentIndexChanged.connect(self._show_selected_image)
        zoom_out.clicked.connect(self.image_view.zoom_out)
        actual.clicked.connect(self.image_view.actual_size)
        fit.clicked.connect(self.image_view.fit_image)
        zoom_in.clicked.connect(self.image_view.zoom_in)
        controls_enabled = self.image_combo.count() > 0
        for widget in (self.image_combo, zoom_out, actual, fit, zoom_in):
            widget.setEnabled(controls_enabled)
        if controls_enabled:
            self._show_selected_image(0)
        return tab

    def _show_selected_image(self, _index: int) -> None:
        resource = self.image_resources.get(str(self.image_combo.currentData() or ""))
        if resource is None:
            self.image_status.setText("표시할 수 있는 이미지 첨부가 없습니다.")
            return
        if self.image_view.set_image(resource.data):
            self.image_status.setText(
                "Ctrl+마우스 휠 또는 상단 버튼으로 확대·축소할 수 있습니다."
            )
        else:
            self.image_status.setText("이미지 데이터를 해석할 수 없습니다.")

    def _build_raw_tab(self) -> QWidget:
        tab = QWidget(self)
        layout = QVBoxLayout(tab)
        raw = QPlainTextEdit(tab)
        raw.setReadOnly(True)
        raw.setPlainText(
            json.dumps(self.detail.raw_payload, ensure_ascii=False, indent=2, default=str)
        )
        layout.addWidget(raw)
        return tab


__all__ = ["TrackerItemDetailDialog", "ZoomableImageView"]
