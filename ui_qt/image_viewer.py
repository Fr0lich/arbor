"""Image Viewer Controller for PySide6 QGraphicsView.

Manages image canvas rendering, zooming, panning, rotation,
multi-photo indexing, and placeholder handling.
"""

from __future__ import annotations

import io
import logging
import os
from typing import Optional
import urllib.request

import pandas as pd
from PySide6.QtCore import QPointF, QRectF, Qt
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
    QGraphicsItem,
    QGraphicsPixmapItem,
    QGraphicsScene,
    QGraphicsTextItem,
    QGraphicsView,
    QLabel,
    QPushButton,
)

from ui_qt.qss_tokens import FONT_MONO, FONT_UI, HAIRLINE, SUBTEXT, SURFACE, TEXT

logger = logging.getLogger(__name__)


class QtImageViewer:
    """Controller for Arbor's Middle Column QGraphicsView image canvas."""

    def __init__(
        self,
        graphics_view: QGraphicsView,
        lbl_images_count: Optional[QLabel] = None,
        lbl_images_missing: Optional[QLabel] = None,
        lbl_zoom_status: Optional[QLabel] = None,
    ):
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

        self.pixmap_item: Optional[QGraphicsPixmapItem] = None
        self.current_pixmap: Optional[QPixmap] = None
        self.current_oid: str = ""
        self.image_paths: list[str] = []
        self.current_image_index: int = 0

        self.zoom_factor: float = 1.0
        self.rotation_angle: int = 0

        # Initial display
        self.show_placeholder("No Specimen Selected")
        self.update_zoom_label()

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

        # 3. Look up local files matching ObjectID in image_dir
        if image_dir and os.path.isdir(image_dir):
            try:
                for fname in os.listdir(image_dir):
                    name_lower = fname.lower()
                    if name_lower.endswith((".jpg", ".jpeg", ".png", ".tif", ".tiff", ".webp")):
                        base = os.path.splitext(fname)[0]
                        if base == self.current_oid or base.startswith(f"{self.current_oid}_") or base.startswith(f"{self.current_oid}-"):
                            full_path = os.path.join(image_dir, fname)
                            if full_path not in self.image_paths:
                                self.image_paths.append(full_path)
            except Exception as e:
                logger.warning(f"Error listing image_dir: {e}")

        # Update count & missing labels
        count = len(self.image_paths)
        if self.lbl_count:
            self.lbl_count.setText(f"{count} image{'s' if count != 1 else ''}" if count > 0 else "")

        if count > 0:
            if self.lbl_missing:
                self.lbl_missing.setVisible(False)
            self._display_image(self.image_paths[0])
        else:
            if self.lbl_missing:
                self.lbl_missing.setText("No images available")
                self.lbl_missing.setVisible(True)
            self.show_placeholder(f"No image available for specimen {self.current_oid}")

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
            # Estimate zoom factor from transform
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
