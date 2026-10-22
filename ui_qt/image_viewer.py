"""Image Viewer Controller for PySide6 QGraphicsView.

Manages image canvas rendering, zooming, panning, rotation,
multi-photo indexing, placeholder handling, wheel zoom,
double-click external viewer launch, and canvas context menu.
"""

from __future__ import annotations

import io
import logging
import os
import sys
from typing import Callable, Dict, List, Optional
import urllib.request
import webbrowser

import pandas as pd
from PySide6.QtCore import QEvent, QObject, QPointF, QRectF, Qt
from PySide6.QtGui import (
    QBrush,
    QColor,
    QFont,
    QImage,
    QPainter,
    QPen,
    QPixmap,
    QTransform,
)
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QGraphicsItem,
    QGraphicsPixmapItem,
    QGraphicsScene,
    QGraphicsTextItem,
    QGraphicsView,
    QHBoxLayout,
    QLabel,
    QMenu,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from ui_qt.qss_tokens import (
    BLACK,
    BORDER,
    CARD,
    CONTAINER,
    FONT_MONO,
    FONT_UI,
    HAIRLINE,
    SUBTEXT,
    SURFACE,
    TEXT,
)

logger = logging.getLogger(__name__)


class QtThumbnailCard(QFrame):
    """Clickable thumbnail card widget with active state border styling matching Tkinter."""

    def __init__(
        self,
        index: int,
        path: str,
        thumb_cache: dict[str, QPixmap],
        on_click: Callable[[int], None],
        on_double_click: Callable[[int], None],
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self.index = index
        self.path = path
        self.thumb_cache = thumb_cache
        self.on_click = on_click
        self.on_double_click = on_double_click
        self.is_active = False

        self.setFixedSize(76, 76)
        self.setCursor(Qt.PointingHandCursor)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(2, 2, 2, 2)
        layout.setSpacing(0)

        self.lbl_image = QLabel(self)
        self.lbl_image.setAlignment(Qt.AlignCenter)
        self.lbl_image.setStyleSheet("background: transparent; border: none;")
        layout.addWidget(self.lbl_image)

        self._load_thumbnail()
        self.set_active(False)

    def _load_thumbnail(self) -> None:
        """Load and cache thumbnail pixmap."""
        pix = self.thumb_cache.get(self.path)
        if pix is None and os.path.isfile(self.path):
            loaded = QPixmap(self.path)
            if not loaded.isNull():
                pix = loaded.scaled(
                    70,
                    70,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
                self.thumb_cache[self.path] = pix

        if pix and not pix.isNull():
            self.lbl_image.setPixmap(pix)
        else:
            self.lbl_image.setText(f"IMG {self.index + 1}")
            self.lbl_image.setStyleSheet(
                f"font-family: {FONT_MONO}; font-size: 10px; color: {SUBTEXT}; font-weight: bold; background: transparent;"
            )

    def set_active(self, active: bool) -> None:
        """Update border styling: 2px solid black for active, 1px solid hairline for inactive."""
        self.is_active = active
        if active:
            self.setStyleSheet(
                f"QFrame {{ background-color: {CARD}; border: 2px solid {BLACK}; border-radius: 4px; }}"
            )
        else:
            self.setStyleSheet(
                f"QFrame {{ background-color: #f8f9fa; border: 1px solid {HAIRLINE}; border-radius: 4px; }}"
                f"QFrame:hover {{ border: 1px solid {BORDER}; background-color: {CARD}; }}"
            )

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.LeftButton:
            self.on_click(self.index)
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event) -> None:
        if event.button() == Qt.LeftButton:
            self.on_double_click(self.index)
        super().mouseDoubleClickEvent(event)


class QtThumbnailStrip(QFrame):
    """Horizontal scrollable thumbnail gallery strip below the main image canvas."""

    def __init__(
        self,
        on_select_image: Callable[[int], None],
        on_open_viewer: Callable[[int], None],
        on_prev: Callable[[], None],
        on_next: Callable[[], None],
        thumb_cache: dict[str, QPixmap],
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self.on_select_image = on_select_image
        self.on_open_viewer = on_open_viewer
        self.on_prev = on_prev
        self.on_next = on_next
        self.thumb_cache = thumb_cache
        self.cards: list[QtThumbnailCard] = []

        self.setFixedHeight(94)
        self.setStyleSheet(
            f"QFrame {{ background-color: #f2f5f1; border-top: 1px solid {HAIRLINE}; border-bottom: none; }}"
        )

        strip_layout = QHBoxLayout(self)
        strip_layout.setContentsMargins(6, 4, 6, 4)
        strip_layout.setSpacing(6)

        # Previous button
        self.btn_prev = QPushButton("◀", self)
        self.btn_prev.setFixedSize(28, 68)
        self.btn_prev.setCursor(Qt.PointingHandCursor)
        self.btn_prev.setToolTip("Previous Image (Shift+Left)")
        self.btn_prev.setStyleSheet(
            f"QPushButton {{ background: {CARD}; border: 1px solid {HAIRLINE}; border-radius: 3px; font-size: 11px; font-weight: bold; color: {TEXT}; }}"
            f"QPushButton:hover {{ background: {CONTAINER}; border-color: {BORDER}; }}"
            "QPushButton:pressed { background: #dadada; }"
        )
        self.btn_prev.clicked.connect(self.on_prev)
        strip_layout.addWidget(self.btn_prev)

        # Scroll Area for thumbnails
        self.scroll_area = QScrollArea(self)
        self.scroll_area.setFixedHeight(84)
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.scroll_area.setStyleSheet("QScrollArea { background: transparent; border: none; }")

        self.container = QWidget()
        self.container.setStyleSheet("background: transparent;")
        self.container_layout = QHBoxLayout(self.container)
        self.container_layout.setContentsMargins(4, 2, 4, 2)
        self.container_layout.setSpacing(8)
        self.container_layout.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.scroll_area.setWidget(self.container)
        strip_layout.addWidget(self.scroll_area, 1)

        # Next button
        self.btn_next = QPushButton("▶", self)
        self.btn_next.setFixedSize(28, 68)
        self.btn_next.setCursor(Qt.PointingHandCursor)
        self.btn_next.setToolTip("Next Image (Shift+Right / Ctrl+B)")
        self.btn_next.setStyleSheet(
            f"QPushButton {{ background: {CARD}; border: 1px solid {HAIRLINE}; border-radius: 3px; font-size: 11px; font-weight: bold; color: {TEXT}; }}"
            f"QPushButton:hover {{ background: {CONTAINER}; border-color: {BORDER}; }}"
            "QPushButton:pressed { background: #dadada; }"
        )
        self.btn_next.clicked.connect(self.on_next)
        strip_layout.addWidget(self.btn_next)

    def set_images(self, paths: list[str], active_index: int) -> None:
        """Rebuild thumbnail cards for the given image list."""
        # Clear existing cards
        while self.container_layout.count() > 0:
            item = self.container_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()
        self.cards.clear()

        # Build new cards
        for idx, path in enumerate(paths):
            card = QtThumbnailCard(
                index=idx,
                path=path,
                thumb_cache=self.thumb_cache,
                on_click=self.on_select_image,
                on_double_click=self.on_open_viewer,
                parent=self.container,
            )
            self.cards.append(card)
            self.container_layout.addWidget(card)

        # Show strip only if at least 2 images are available
        if len(paths) > 1:
            self.setVisible(True)
            self.set_active_index(active_index)
        else:
            self.setVisible(False)

    def set_active_index(self, index: int) -> None:
        """Update active card highlight and ensure it is visible."""
        for idx, card in enumerate(self.cards):
            card.set_active(idx == index)
        if 0 <= index < len(self.cards):
            self.scroll_area.ensureWidgetVisible(self.cards[index])


class QtImageViewer(QObject):
    """Controller for Arbor's Middle Column QGraphicsView image canvas."""

    def __init__(
        self,
        graphics_view: QGraphicsView,
        lbl_images_count: Optional[QLabel] = None,
        lbl_images_missing: Optional[QLabel] = None,
        lbl_zoom_status: Optional[QLabel] = None,
    ):
        super().__init__(graphics_view)
        self.view = graphics_view
        self.lbl_count = lbl_images_count
        self.lbl_missing = lbl_images_missing
        self.lbl_zoom = lbl_zoom_status

        self.scene = QGraphicsScene(self.view)
        self.view.setScene(self.scene)
        self.view.setRenderHints(
            QPainter.Antialiasing
            | QPainter.SmoothPixmapTransform
            | QPainter.TextAntialiasing
        )
        self.view.setDragMode(QGraphicsView.ScrollHandDrag)
        self.view.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.view.setResizeAnchor(QGraphicsView.AnchorUnderMouse)
        self.view.viewport().installEventFilter(self)

        self.pixmap_item: Optional[QGraphicsPixmapItem] = None
        self.current_pixmap: Optional[QPixmap] = None
        self.current_oid: str = ""
        self.image_paths: list[str] = []
        self.current_image_index: int = 0

        self.zoom_factor: float = 1.0
        self.rotation_angle: int = 0

        # Directory and thumbnail caches for performance
        self._dir_cache: dict[str, dict[str, list[str]]] = {}
        self._thumb_cache: dict[str, QPixmap] = {}

        # Instantiate horizontal thumbnail gallery strip below the image viewport
        self.thumb_strip: Optional[QtThumbnailStrip] = None
        parent_widget = self.view.parentWidget()
        if parent_widget and parent_widget.layout():
            self.thumb_strip = QtThumbnailStrip(
                on_select_image=self.select_image,
                on_open_viewer=self.open_in_external_viewer,
                on_prev=self.prev_image,
                on_next=self.next_image,
                thumb_cache=self._thumb_cache,
                parent=parent_widget,
            )
            parent_widget.layout().addWidget(self.thumb_strip)
            self.thumb_strip.setVisible(False)

        # Initial display
        self.show_placeholder("No Specimen Selected")
        self.update_zoom_label()

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        """Handle mouse wheel zoom, double-click launch, and context menu on viewport."""
        if watched == self.view.viewport():
            if event.type() == QEvent.Wheel:
                # Zoom centered around cursor
                delta = event.angleDelta().y()
                if delta > 0:
                    self.zoom_in()
                elif delta < 0:
                    self.zoom_out()
                return True
            elif event.type() == QEvent.MouseButtonDblClick:
                if event.button() == Qt.LeftButton:
                    self.open_in_external_viewer()
                    return True
            elif event.type() == QEvent.ContextMenu:
                self.show_context_menu(event.globalPos())
                return True
        return super().eventFilter(watched, event)

    def wire_toolbar(
        self,
        btn_zoom_in: Optional[QPushButton] = None,
        btn_zoom_out: Optional[QPushButton] = None,
        btn_rotate_ccw: Optional[QPushButton] = None,
        btn_rotate_cw: Optional[QPushButton] = None,
        btn_reset_view: Optional[QPushButton] = None,
        btn_fit_view: Optional[QPushButton] = None,
    ) -> None:
        """Connect image toolbar push buttons to viewer methods."""
        if btn_zoom_in:
            btn_zoom_in.clicked.connect(self.zoom_in)
        if btn_zoom_out:
            btn_zoom_out.clicked.connect(self.zoom_out)
        if btn_rotate_ccw:
            btn_rotate_ccw.clicked.connect(self.rotate_ccw)
        if btn_rotate_cw:
            btn_rotate_cw.clicked.connect(self.rotate_cw)
        if btn_reset_view:
            btn_reset_view.clicked.connect(self.reset_view)
        if btn_fit_view:
            btn_fit_view.clicked.connect(self.fit_view)

    def _get_local_images_for_specimen(self, image_dir: str, oid: str) -> list[str]:
        """Look up local image files matching ObjectID prefix with single-pass directory caching."""
        if not image_dir or not os.path.isdir(image_dir):
            return []

        if image_dir not in self._dir_cache:
            cache: dict[str, list[str]] = {}
            try:
                for fname in os.listdir(image_dir):
                    name_lower = fname.lower()
                    if name_lower.endswith((".jpg", ".jpeg", ".png", ".tif", ".tiff", ".webp")):
                        full_path = os.path.join(image_dir, fname)
                        base = os.path.splitext(fname)[0].strip()
                        cache.setdefault(base, []).append(full_path)
                        # Also index prefix before '_' or '-'
                        prefix = base.split("_")[0].split("-")[0].strip()
                        if prefix != base:
                            cache.setdefault(prefix, []).append(full_path)
            except Exception as e:
                logger.warning(f"Error indexing image_dir: {e}")
            self._dir_cache[image_dir] = cache

        return self._dir_cache[image_dir].get(oid, [])

    def invalidate_dir_cache(self) -> None:
        """Clear local directory index cache."""
        self._dir_cache.clear()

    def select_image(self, index: int) -> None:
        """Switch active image to the given index."""
        if not self.image_paths or index < 0 or index >= len(self.image_paths):
            return
        self.current_image_index = index
        self._display_image(self.image_paths[self.current_image_index])
        self._update_counter_label()
        if self.thumb_strip:
            self.thumb_strip.set_active_index(self.current_image_index)

    def load_specimen_images(
        self,
        oid: str,
        df_reg: Optional[pd.DataFrame] = None,
        df_photo: Optional[pd.DataFrame] = None,
        image_dir: Optional[str] = None,
    ) -> None:
        """Resolve and display photo for the given specimen ObjectID."""
        self.current_oid = str(oid).strip()
        self.image_paths = []
        self.current_image_index = 0

        if not self.current_oid:
            self.show_placeholder("No Specimen Selected")
            if self.thumb_strip:
                self.thumb_strip.set_images([], 0)
            return

        # 1. Look up online photo URLs in df_reg
        if df_reg is not None and self.current_oid in df_reg.index:
            row = df_reg.loc[self.current_oid]
            if isinstance(row, pd.DataFrame):
                row = row.iloc[0]

            for col in ("Online photo 1", "Online photo 2", "Online photo 3", "Photo"):
                if col in row.index:
                    val = str(row[col]).strip()
                    if val and val.lower() not in ("nan", "none", "<na>"):
                        self.image_paths.append(val)

        # 2. Look up photos in df_photo sheet
        if df_photo is not None and self.current_oid in df_photo.index:
            p_rows = df_photo.loc[self.current_oid]
            if isinstance(p_rows, pd.Series):
                p_rows = pd.DataFrame([p_rows])

            for _, pr in p_rows.iterrows():
                for c in ("Filename", "Path", "URL", "Online photo 1"):
                    if c in pr.index:
                        p_val = str(pr[c]).strip()
                        if p_val and p_val.lower() not in ("nan", "none", "<na>") and p_val not in self.image_paths:
                            self.image_paths.append(p_val)

        # 3. Look up local files matching ObjectID in image_dir (O(1) cached lookup)
        if image_dir:
            matched_local = self._get_local_images_for_specimen(image_dir, self.current_oid)
            for full_path in matched_local:
                if full_path not in self.image_paths:
                    self.image_paths.append(full_path)

        # Update count & missing labels
        count = len(self.image_paths)
        if count > 0:
            if self.lbl_missing:
                self.lbl_missing.setVisible(False)
            self._display_image(self.image_paths[0])
            self._update_counter_label()
        else:
            if self.lbl_missing:
                self.lbl_missing.setText("No images available")
                self.lbl_missing.setVisible(True)
            if self.lbl_count:
                self.lbl_count.setText("")
            self.show_placeholder(f"No image available for specimen {self.current_oid}")

        # Update horizontal thumbnail strip
        if self.thumb_strip:
            self.thumb_strip.set_images(self.image_paths, self.current_image_index)

    def next_image(self) -> None:
        """Cycle to the next image in the specimen gallery."""
        if not self.image_paths or len(self.image_paths) <= 1:
            return
        self.current_image_index = (self.current_image_index + 1) % len(self.image_paths)
        self._display_image(self.image_paths[self.current_image_index])
        self._update_counter_label()
        if self.thumb_strip:
            self.thumb_strip.set_active_index(self.current_image_index)

    def prev_image(self) -> None:
        """Cycle to the previous image in the specimen gallery."""
        if not self.image_paths or len(self.image_paths) <= 1:
            return
        self.current_image_index = (self.current_image_index - 1) % len(self.image_paths)
        self._display_image(self.image_paths[self.current_image_index])
        self._update_counter_label()
        if self.thumb_strip:
            self.thumb_strip.set_active_index(self.current_image_index)

    def _update_counter_label(self) -> None:
        count = len(self.image_paths)
        if self.lbl_count:
            if count > 1:
                self.lbl_count.setText(f"{self.current_image_index + 1} / {count} images")
            elif count == 1:
                self.lbl_count.setText("1 image")
            else:
                self.lbl_count.setText("")

    def open_in_external_viewer(self, index: Optional[int] = None) -> None:
        """Launch specified (or active) image in system default viewer (Tkinter parity)."""
        idx = index if index is not None else self.current_image_index
        if not self.image_paths or idx < 0 or idx >= len(self.image_paths):
            return
        source = self.image_paths[idx]
        if source.startswith(("http://", "https://")):
            webbrowser.open(source)
        elif os.path.exists(source):
            try:
                if sys.platform == "win32":
                    os.startfile(source)
                elif sys.platform == "darwin":
                    import subprocess
                    subprocess.Popen(["open", source])
                else:
                    import subprocess
                    subprocess.Popen(["xdg-open", source])
            except Exception as e:
                logger.warning(f"Could not launch external viewer: {e}")

    def copy_to_clipboard(self) -> None:
        """Copy the current pixmap to the system clipboard."""
        if self.current_pixmap and not self.current_pixmap.isNull():
            QApplication.clipboard().setPixmap(self.current_pixmap)

    def show_context_menu(self, global_pos) -> None:
        """Display right-click context menu on image canvas."""
        menu = QMenu(self.view)
        menu.setStyleSheet(f"""
            QMenu {{
                background-color: {CARD};
                color: {TEXT};
                border: 1px solid {BORDER};
                padding: 4px;
                font-family: {FONT_UI};
                font-size: 12px;
            }}
            QMenu::item {{
                padding: 6px 20px 6px 14px;
                background-color: transparent;
            }}
            QMenu::item:selected {{
                background-color: {CONTAINER};
            }}
            QMenu::separator {{
                height: 1px;
                background-color: {HAIRLINE};
                margin: 4px 6px;
            }}
        """)
        has_image = self.current_pixmap is not None and not self.current_pixmap.isNull()

        act_ext = menu.addAction("🔍 Open in External Viewer", self.open_in_external_viewer)
        act_ext.setEnabled(has_image)

        act_copy = menu.addAction("📋 Copy Image to Clipboard", self.copy_to_clipboard)
        act_copy.setEnabled(has_image)

        if len(self.image_paths) > 1:
            menu.addSeparator()
            menu.addAction("➡️ Next Image (Shift+Right / Ctrl+B)", self.next_image)
            menu.addAction("⬅️ Previous Image (Shift+Left)", self.prev_image)

        menu.addSeparator()
        act_fit = menu.addAction("Fit to Viewport", self.fit_view)
        act_fit.setEnabled(has_image)
        act_reset = menu.addAction("Actual Size (100%)", self.reset_view)
        act_reset.setEnabled(has_image)
        act_rotate = menu.addAction("Rotate 90° Clockwise", self.rotate_cw)
        act_rotate.setEnabled(has_image)

        menu.exec(global_pos)

    def _display_image(self, source: str) -> None:
        """Render a local image path or remote URL onto the QGraphicsScene."""
        pixmap: Optional[QPixmap] = None

        if source.startswith(("http://", "https://")):
            try:
                req = urllib.request.Request(source, headers={"User-Agent": "Arbor/2.0"})
                with urllib.request.urlopen(req, timeout=4) as response:
                    data = response.read()
                    img = QImage.fromData(data)
                    if not img.isNull():
                        pixmap = QPixmap.fromImage(img)
            except Exception as e:
                logger.debug(f"Failed to fetch online photo {source}: {e}")
        elif os.path.exists(source):
            pixmap = QPixmap(source)

        if pixmap and not pixmap.isNull():
            self.current_pixmap = pixmap
            self.scene.clear()
            self.pixmap_item = self.scene.addPixmap(pixmap)
            self.scene.setSceneRect(QRectF(pixmap.rect()))
            self.reset_view()
            self.fit_view()
        else:
            self.show_placeholder(f"Could not load image:\n{os.path.basename(source)}")

    def show_placeholder(self, message: str) -> None:
        """Display a clean canvas placeholder when no image is available."""
        self.scene.clear()
        self.current_pixmap = None
        self.pixmap_item = None

        width = max(self.view.width(), 400)
        height = max(self.view.height(), 300)
        self.scene.setSceneRect(0, 0, width, height)

        # Background tint
        bg_brush = QBrush(QColor("#f2f5f1"))
        self.scene.setBackgroundBrush(bg_brush)

        # Icon / Card text
        text_item = QGraphicsTextItem(f"📷\n{message}")
        font = QFont("Segoe UI", 12)
        font.setBold(True)
        text_item.setFont(font)
        text_item.setDefaultTextColor(QColor("#747878"))
        text_item.setTextWidth(300)

        # Center in scene
        br = text_item.boundingRect()
        text_item.setPos((width - br.width()) / 2, (height - br.height()) / 2)
        self.scene.addItem(text_item)

        self.zoom_factor = 1.0
        self.rotation_angle = 0
        self.update_zoom_label()

    def zoom_in(self) -> None:
        """Zoom in by 25%."""
        if self.zoom_factor < 10.0:
            self.zoom_factor *= 1.25
            self._apply_transform()

    def zoom_out(self) -> None:
        """Zoom out by 20%."""
        if self.zoom_factor > 0.1:
            self.zoom_factor /= 1.25
            self._apply_transform()

    def rotate_cw(self) -> None:
        """Rotate clockwise by 90°."""
        self.rotation_angle = (self.rotation_angle + 90) % 360
        self._apply_transform()

    def rotate_ccw(self) -> None:
        """Rotate counter-clockwise by 90°."""
        self.rotation_angle = (self.rotation_angle - 90) % 360
        self._apply_transform()

    def reset_view(self) -> None:
        """Reset zoom to 100% and rotation to 0°."""
        self.zoom_factor = 1.0
        self.rotation_angle = 0
        self._apply_transform()

    def fit_view(self) -> None:
        """Fit scene contents within the current viewport."""
        rect = self.scene.itemsBoundingRect()
        if not rect.isEmpty():
            self.view.fitInView(rect, Qt.KeepAspectRatio)
            t = self.view.transform()
            self.zoom_factor = max(t.m11(), t.m22())
            self.update_zoom_label()

    def _apply_transform(self) -> None:
        """Re-apply combined zoom and rotation transform to the graphics view."""
        transform = QTransform()
        transform.rotate(self.rotation_angle)
        transform.scale(self.zoom_factor, self.zoom_factor)
        self.view.setTransform(transform)
        self.update_zoom_label()

    def update_zoom_label(self) -> None:
        """Update zoom status label (e.g. '100% | 0°')."""
        if self.lbl_zoom:
            pct = int(self.zoom_factor * 100)
            self.lbl_zoom.setText(f"{pct}% | {self.rotation_angle}°")
