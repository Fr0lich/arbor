"""PySide6 implementation of the Quick Peek Overlay Card Dialog.

Wraps ``qt designer/quick_peek.ui`` and displays specimen metadata, status badge,
and thumbnail preview with inline navigation triggers.
"""
from __future__ import annotations

import os
from typing import Callable, Optional

import pandas as pd
from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence, QPixmap, QShortcut
from PySide6.QtWidgets import (
    QDialog,
    QWidget,
)

from models import AppState
from repository import REVIEWED_COLUMN
from ui_qt.loader import load_ui


class QtQuickPeekDialog:
    """Controller wrapping ``qt designer/quick_peek.ui``."""

    def __init__(
        self,
        parent: Optional[QWidget] = None,
        app_state: Optional[AppState] = None,
        oid: Optional[str] = None,
        on_open_full: Optional[Callable[[str], None]] = None,
    ):
        self.parent = parent
        self.app = app_state or AppState()
        self.current_oid: Optional[str] = str(oid) if oid is not None else None
        self.on_open_full = on_open_full

        self.win: QDialog = load_ui("quick_peek.ui", parent)

        self._setup_ui()
        if self.current_oid:
            self.load_object(self.current_oid)
        elif self.app.current_object_id:
            self.load_object(str(self.app.current_object_id))

    def _setup_ui(self) -> None:
        """Connect buttons, actions, and shortcuts."""
        if hasattr(self.win, "btn_close"):
            self.win.btn_close.clicked.connect(self.win.accept)

        if hasattr(self.win, "btn_open_full"):
            self.win.btn_open_full.clicked.connect(self._do_open_full)

        # ESC to close
        QShortcut(QKeySequence(Qt.Key.Key_Escape), self.win).activated.connect(self.win.accept)

    def load_object(self, oid: str) -> None:
        """Populate the metadata card and image preview for a given ObjectID."""
        self.current_oid = str(oid)
        df_reg = self.app.df_reg
        df_obs = self.app.df_obs

        if hasattr(self.win, "lbl_oid"):
            self.win.lbl_oid.setText(f"#{self.current_oid}")

        if df_reg is None or self.current_oid not in df_reg.index:
            if hasattr(self.win, "lbl_title"):
                self.win.lbl_title.setText(f"Specimen #{self.current_oid} (Not in registry)")
            if hasattr(self.win, "badge_status"):
                self.win.badge_status.setText("UNKNOWN")
                self.win.badge_status.setStyleSheet("background-color: #747878; color: #ffffff; padding: 3px 6px; font-weight: bold;")
            return

        reg_row = df_reg.loc[self.current_oid]

        # Botanical title
        genus = str(reg_row.get("Genus", "")).strip() if "Genus" in reg_row and not pd.isna(reg_row.get("Genus")) else ""
        species = str(reg_row.get("Species", "")).strip() if "Species" in reg_row and not pd.isna(reg_row.get("Species")) else ""
        author = str(reg_row.get("Author", "")).strip() if "Author" in reg_row and not pd.isna(reg_row.get("Author")) else ""

        taxon_parts = [p for p in [genus, species, author] if p]
        taxon_name = " ".join(taxon_parts) if taxon_parts else "Unidentified Specimen"

        if hasattr(self.win, "lbl_title"):
            self.win.lbl_title.setText(taxon_name)

        # Status badge (Reviewed vs Problem vs Unreviewed)
        is_reviewed = False
        has_problems = False
        if df_obs is not None and self.current_oid in df_obs.index:
            obs_row = df_obs.loc[self.current_oid]
            if REVIEWED_COLUMN in obs_row and bool(obs_row[REVIEWED_COLUMN]):
                is_reviewed = True

            prob_cols = [c for c in df_obs.columns if c.endswith("_Problem")]
            for p in prob_cols:
                if bool(obs_row.get(p, False)):
                    has_problems = True
                    break

        if hasattr(self.win, "badge_status"):
            badge = self.win.badge_status
            if is_reviewed:
                badge.setText("REVIEWED")
                badge.setStyleSheet("background-color: #3a7d44; color: #ffffff; font-family: 'Courier New', monospace; font-size: 10px; font-weight: bold; padding: 3px 6px;")
            elif has_problems:
                badge.setText("PROBLEMS")
                badge.setStyleSheet("background-color: #c93a40; color: #ffffff; font-family: 'Courier New', monospace; font-size: 10px; font-weight: bold; padding: 3px 6px;")
            else:
                badge.setText("UNREVIEWED")
                badge.setStyleSheet("background-color: #747878; color: #ffffff; font-family: 'Courier New', monospace; font-size: 10px; font-weight: bold; padding: 3px 6px;")

        # Metadata Card Fields
        family = str(reg_row.get("Family", "")).strip() if "Family" in reg_row and not pd.isna(reg_row.get("Family")) else "—"
        collector = str(reg_row.get("Collector", "")).strip() if "Collector" in reg_row and not pd.isna(reg_row.get("Collector")) else "—"

        # Location details
        building = str(reg_row.get("Building", "")).strip() if "Building" in reg_row and not pd.isna(reg_row.get("Building")) else ""
        floor = str(reg_row.get("Floor", "")).strip() if "Floor" in reg_row and not pd.isna(reg_row.get("Floor")) else ""
        room = str(reg_row.get("Room", "")).strip() if "Room" in reg_row and not pd.isna(reg_row.get("Room")) else ""
        cabinet = str(reg_row.get("Cabinet", "")).strip() if "Cabinet" in reg_row and not pd.isna(reg_row.get("Cabinet")) else ""

        loc_parts = []
        if building:
            loc_parts.append(f"Bldg: {building}")
        if floor:
            loc_parts.append(f"Fl: {floor}")
        if room:
            loc_parts.append(f"Rm: {room}")
        if cabinet:
            loc_parts.append(f"Cab: {cabinet}")
        location_str = ", ".join(loc_parts) if loc_parts else "—"

        if hasattr(self.win, "lbl_genus"):
            self.win.lbl_genus.setText(f"Genus: {genus or '—'}")
        if hasattr(self.win, "lbl_species"):
            self.win.lbl_species.setText(f"Species: {species or '—'}")
        if hasattr(self.win, "lbl_family"):
            self.win.lbl_family.setText(f"Family: {family}")
        if hasattr(self.win, "lbl_collector"):
            self.win.lbl_collector.setText(f"Collector: {collector}")
        if hasattr(self.win, "lbl_location"):
            self.win.lbl_location.setText(f"Location: {location_str}")

        # Image Thumbnail Preview
        self._load_image_preview()

    def _load_image_preview(self) -> None:
        """Find local thumbnail image or render fallback label."""
        if not hasattr(self.win, "lbl_image"):
            return

        lbl = self.win.lbl_image
        lbl.clear()
        lbl.setText("No image preview available")

        if not self.current_oid:
            return

        # Check local folders or cache
        image_path = None
        candidates = []

        cfg = getattr(self.app, "config", None)
        offline_dir = getattr(cfg, "offline_image_dir", None) if cfg else None
        if offline_dir and os.path.exists(offline_dir):
            candidates.append(os.path.join(offline_dir, f"{self.current_oid}.jpg"))
            candidates.append(os.path.join(offline_dir, f"{self.current_oid}.png"))
            candidates.append(os.path.join(offline_dir, str(self.current_oid)))

        # Also check last selected image directory
        import config
        last_img_dir = config.get_last_dir("last_image_dir")
        if last_img_dir and os.path.exists(last_img_dir):
            candidates.append(os.path.join(last_img_dir, f"{self.current_oid}.jpg"))
            candidates.append(os.path.join(last_img_dir, f"{self.current_oid}.jpeg"))
            candidates.append(os.path.join(last_img_dir, f"{self.current_oid}.png"))

        for cand in candidates:
            if os.path.isfile(cand):
                image_path = cand
                break
            elif os.path.isdir(cand):
                files = [
                    os.path.join(cand, f) for f in os.listdir(cand)
                    if f.lower().endswith((".jpg", ".jpeg", ".png"))
                ]
                if files:
                    image_path = files[0]
                    break

        if image_path and os.path.exists(image_path):
            pixmap = QPixmap(image_path)
            if not pixmap.isNull():
                scaled = pixmap.scaled(
                    260, 320,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation
                )
                lbl.setPixmap(scaled)
                lbl.setText("")

    def _do_open_full(self) -> None:
        """Trigger navigation callback for current object and close dialog."""
        if self.current_oid:
            self.app.current_object_id = self.current_oid
            if self.on_open_full:
                self.on_open_full(self.current_oid)
        self.win.accept()

    def exec(self) -> int:
        return self.win.exec()

    def show(self) -> None:
        self.win.show()

    def __getattr__(self, name: str):
        return getattr(self.win, name)
