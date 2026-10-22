"""Dual-Docking Location Panel Component for PySide6.

Replicates Tkinter's ui/location_panel.py with 3 layout modes:
  - 'horizontal_1row': Single-row grid for Middle Column (Default).
  - 'horizontal_2row': Two-row grid for Middle Column.
  - 'vertical': Stacked card view for Left Column.

Supports live data-binding to df_obs, loan status toggle card, and
dynamic reparenting / dock toggling between Middle and Left panes.
"""

from __future__ import annotations

import logging
from typing import Callable, Optional

import pandas as pd
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QCursor, QFont
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from ui_qt.qss_tokens import (
    BORDER,
    CARD,
    CONTAINER,
    FONT_MONO,
    FONT_UI,
    GREEN,
    HAIRLINE,
    HEADER_ROW,
    RED,
    SUBTEXT,
    SURFACE,
    TEXT,
    repolish,
)

logger = logging.getLogger(__name__)

DEFAULT_LOCATION_FIELDS = [
    {
        "name": "Stored as",
        "type": "choice",
        "choices": [
            "Mounted on wooden platform",
            "Petridish",
            "in plastic box",
            "in paper box",
            "Free standing",
            "in plastic bag",
        ],
    },
    {
        "name": "Building",
        "type": "choice",
        "choices": ["Lid's hus", "Økern", "Annet"],
    },
    {
        "name": "Floor",
        "type": "choice",
        "choices": ["4", "3", "2", "1", "-1", "-2"],
    },
    {"name": "Cabinet", "type": "text"},
    {"name": "Shelf", "type": "text"},
    {"name": "Extra", "type": "text"},
    {"name": "Loaned out", "type": "checkbox"},
    {"name": "Loaned out date", "type": "text", "readonly": True},
]


class StatusToggleCard(QFrame):
    """Card toggle for loan status (STATUS: AVAILABLE vs STATUS: ON LOAN)."""

    toggled = Signal(bool)

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.is_on_loan = False
        self.setCursor(QCursor(Qt.PointingHandCursor))

        layout = QHBoxLayout(self)
        layout.setContentsMargins(6, 3, 8, 3)
        layout.setSpacing(6)

        self.color_bar = QFrame(self)
        self.color_bar.setFixedWidth(4)
        layout.addWidget(self.color_bar)

        self.lbl_status = QLabel("STATUS: AVAILABLE", self)
        self.lbl_status.setFont(QFont("Courier New", 9, QFont.Bold))
        layout.addWidget(self.lbl_status)

        self.update_style()

    def set_loan_status(self, on_loan: bool) -> None:
        self.is_on_loan = bool(on_loan)
        self.update_style()

    def update_style(self) -> None:
        bg_bar = RED if self.is_on_loan else GREEN
        text = "STATUS: ON LOAN [ACTIVE]" if self.is_on_loan else "STATUS: AVAILABLE"
        fg_text = RED if self.is_on_loan else TEXT

        self.color_bar.setStyleSheet(f"background-color: {bg_bar}; border-radius: 1px;")
        self.lbl_status.setText(text)
        self.lbl_status.setStyleSheet(f"color: {fg_text}; font-weight: bold;")

        self.setStyleSheet(f"""
            QFrame {{
                background-color: {CARD};
                border: 1px solid {HAIRLINE};
                border-radius: 2px;
            }}
            QFrame:hover {{
                background-color: {CONTAINER};
            }}
        """)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.is_on_loan = not self.is_on_loan
            self.update_style()
            self.toggled.emit(self.is_on_loan)
        super().mousePressEvent(event)


class QtLocationPanel(QFrame):
    """Decoupled Location Panel Component with dual-docking support."""

    field_changed = Signal(str, str)
    toggle_dock_requested = Signal()

    def __init__(
        self,
        config_ref: Optional[dict] = None,
        mode: str = "horizontal_1row",
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self.config_ref = config_ref or {}
        self.mode = mode  # 'horizontal_1row', 'horizontal_2row', or 'vertical'
        self.entries: dict[str, QWidget] = {}
        self.current_oid: str = ""

        self.setObjectName("location_panel_root")
        self.setStyleSheet(f"""
            QFrame#location_panel_root {{
                background-color: {SURFACE};
                border: 1px solid {HAIRLINE};
                border-radius: 2px;
            }}
        """)

        self.root_layout = QVBoxLayout(self)
        self.root_layout.setContentsMargins(6, 6, 6, 6)
        self.root_layout.setSpacing(4)

        self.build_ui()

    def _get_field_defs(self) -> list[dict]:
        loc_sections = self.config_ref.get("ui_sections", {}).get("location", [])
        if loc_sections:
            return loc_sections
        return DEFAULT_LOCATION_FIELDS

    def set_layout_mode(self, mode: str) -> None:
        """Switch visual mode: 'horizontal_1row', 'horizontal_2row', or 'vertical'."""
        if mode in ("horizontal_1row", "horizontal_2row", "vertical") and mode != self.mode:
            self.mode = mode
            self.build_ui()
            if self.current_oid:
                # Retain currently loaded data
                pass

    def build_ui(self) -> None:
        """Rebuild panel UI according to current layout mode."""
        # Clear existing layout children
        while self.root_layout.count():
            item = self.root_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

        self.entries.clear()

        # 1. Header Row
        header_frame = QFrame(self)
        header_frame.setStyleSheet(f"background-color: {HEADER_ROW}; border-bottom: 1px solid {HAIRLINE};")
        header_layout = QHBoxLayout(header_frame)
        header_layout.setContentsMargins(8, 4, 8, 4)
        header_layout.setSpacing(8)

        lbl_title = QLabel("📍 LOCATION", header_frame)
        lbl_title.setFont(QFont("Segoe UI", 9, QFont.Bold))
        lbl_title.setStyleSheet(f"color: {TEXT}; font-weight: bold;")
        header_layout.addWidget(lbl_title)

        # Dock Toggle Button
        btn_dock = QPushButton("⇄ Toggle Dock", header_frame)
        btn_dock.setFont(QFont("Segoe UI", 8))
        btn_dock.setCursor(QCursor(Qt.PointingHandCursor))
        btn_dock.setToolTip("Toggle location panel between Middle column and Left column")
        btn_dock.setStyleSheet(f"""
            QPushButton {{
                background-color: {CARD};
                color: {TEXT};
                border: 1px solid {BORDER};
                padding: 2px 8px;
                font-size: 11px;
            }}
            QPushButton:hover {{
                background-color: {CONTAINER};
            }}
        """)
        btn_dock.clicked.connect(lambda: self.toggle_dock_requested.emit())
        header_layout.addWidget(btn_dock)

        header_layout.addStretch()

        # Loan Status Toggle Card
        self.loan_card = StatusToggleCard(header_frame)
        self.loan_card.toggled.connect(self._on_loan_toggled)
        header_layout.addWidget(self.loan_card)

        self.root_layout.addWidget(header_frame)

        # 2. Field Controls Layout
        content_widget = QWidget(self)
        field_defs = self._get_field_defs()
        regular_fields = [f for f in field_defs if f.get("name") not in ("Loaned out", "Loaned out date")]

        if self.mode == "vertical":
            # Stacked vertical layout for Left column
            content_layout = QGridLayout(content_widget)
            content_layout.setContentsMargins(6, 6, 6, 6)
            content_layout.setHorizontalSpacing(8)
            content_layout.setVerticalSpacing(5)
            content_layout.setColumnStretch(0, 0)
            content_layout.setColumnStretch(1, 1)

            for row_idx, f in enumerate(regular_fields):
                name = f["name"]
                lbl = QLabel(name, content_widget)
                lbl.setFont(QFont("Segoe UI", 9, QFont.Bold))
                lbl.setStyleSheet(f"color: {TEXT}; font-weight: bold;")
                content_layout.addWidget(lbl, row_idx, 0, Qt.AlignVCenter | Qt.AlignLeft)

                widget = self._create_field_widget(content_widget, f)
                content_layout.addWidget(widget, row_idx, 1)
                self.entries[name] = widget

        elif self.mode == "horizontal_2row":
            # 2-Row grid for Middle column
            content_layout = QGridLayout(content_widget)
            content_layout.setContentsMargins(6, 6, 6, 6)
            content_layout.setHorizontalSpacing(10)
            content_layout.setVerticalSpacing(6)

            cols_per_row = max((len(regular_fields) + 1) // 2, 3)
            for idx, f in enumerate(regular_fields):
                row = (idx // cols_per_row) * 2
                col = idx % cols_per_row
                name = f["name"]

                lbl = QLabel(name, content_widget)
                lbl.setFont(QFont("Segoe UI", 8, QFont.Bold))
                lbl.setStyleSheet(f"color: {SUBTEXT}; font-weight: bold;")
                content_layout.addWidget(lbl, row, col)

                widget = self._create_field_widget(content_widget, f)
                content_layout.addWidget(widget, row + 1, col)
                self.entries[name] = widget

        else:
            # Default horizontal_1row for Middle column
            content_layout = QHBoxLayout(content_widget)
            content_layout.setContentsMargins(6, 6, 6, 6)
            content_layout.setSpacing(10)

            for f in regular_fields:
                name = f["name"]
                field_box = QWidget(content_widget)
                box_layout = QVBoxLayout(field_box)
                box_layout.setContentsMargins(0, 0, 0, 0)
                box_layout.setSpacing(2)

                lbl = QLabel(name, field_box)
                lbl.setFont(QFont("Segoe UI", 8, QFont.Bold))
                lbl.setStyleSheet(f"color: {SUBTEXT}; font-weight: bold;")
                box_layout.addWidget(lbl)

                widget = self._create_field_widget(field_box, f)
                box_layout.addWidget(widget)
                self.entries[name] = widget

                content_layout.addWidget(field_box)

        self.root_layout.addWidget(content_widget)

    def _create_field_widget(self, parent: QWidget, field_def: dict) -> QWidget:
        name = field_def["name"]
        ftype = field_def.get("type", "text")
        choices = field_def.get("choices", [])
        is_readonly = bool(field_def.get("readonly", False))

        if ftype == "choice" and choices:
            combo = QComboBox(parent)
            combo.setFont(QFont("Courier New", 9))
            combo.setStyleSheet(f"""
                QComboBox {{
                    background-color: {CARD};
                    color: {TEXT};
                    border: 1px solid {HAIRLINE};
                    border-radius: 1px;
                    padding: 3px 6px;
                    font-family: {FONT_MONO};
                }}
                QComboBox:focus {{
                    border: 1px solid {BORDER};
                }}
            """)
            combo.addItem("")
            for c in choices:
                combo.addItem(str(c))
            combo.currentTextChanged.connect(lambda txt, fn=name: self.field_changed.emit(fn, txt))
            return combo
        else:
            line_edit = QLineEdit(parent)
            line_edit.setFont(QFont("Courier New", 9))
            line_edit.setStyleSheet(f"""
                QLineEdit {{
                    background-color: {CARD};
                    color: {TEXT};
                    border: 1px solid {HAIRLINE};
                    border-radius: 1px;
                    padding: 3px 6px;
                    font-family: {FONT_MONO};
                }}
                QLineEdit:focus {{
                    border: 1px solid {BORDER};
                }}
                QLineEdit:read-only {{
                    background-color: {HEADER_ROW};
                    color: {SUBTEXT};
                }}
            """)
            if is_readonly:
                line_edit.setReadOnly(True)
            line_edit.textEdited.connect(lambda txt, fn=name: self.field_changed.emit(fn, txt))
            return line_edit

    def _on_loan_toggled(self, is_loaned: bool) -> None:
        self.field_changed.emit("Loaned out", str(is_loaned))

    def populate_specimen(self, oid: str, df_obs: Optional[pd.DataFrame]) -> None:
        """Populate location fields for the given specimen."""
        self.current_oid = str(oid).strip()

        # Block signals during programmatic update
        for w in self.entries.values():
            w.blockSignals(True)

        try:
            if df_obs is None or self.current_oid not in df_obs.index:
                self.clear()
                return

            row = df_obs.loc[self.current_oid]
            if isinstance(row, pd.DataFrame):
                row = row.iloc[0]

            for field_name, widget in self.entries.items():
                val = ""
                if field_name in row.index:
                    raw = row[field_name]
                    if not pd.isna(raw):
                        val = str(raw).strip()

                if isinstance(widget, QLineEdit):
                    widget.setText(val)
                elif isinstance(widget, QComboBox):
                    widget.setCurrentText(val)

            # Update loan toggle
            is_loaned = False
            if "Loaned out" in row.index and not pd.isna(row["Loaned out"]):
                is_loaned = str(row["Loaned out"]).lower() in ("true", "1", "yes")
            self.loan_card.set_loan_status(is_loaned)

        finally:
            for w in self.entries.values():
                w.blockSignals(False)

    def clear(self) -> None:
        """Clear all location fields."""
        for widget in self.entries.values():
            widget.blockSignals(True)
            if isinstance(widget, QLineEdit):
                widget.clear()
            elif isinstance(widget, QComboBox):
                widget.setCurrentIndex(0)
            widget.blockSignals(False)
        self.loan_card.set_loan_status(False)

    def get_location_values(self) -> dict[str, str]:
        """Read all location field values."""
        vals = {}
        for fn, w in self.entries.items():
            if isinstance(w, QLineEdit):
                vals[fn] = w.text().strip()
            elif isinstance(w, QComboBox):
                vals[fn] = w.currentText().strip()
        vals["Loaned out"] = str(self.loan_card.is_on_loan)
        return vals

    def focus_first_field(self) -> bool:
        """Focus the first editable field (Building or Stored as)."""
        for fn in ("Building", "Stored as", "Floor", "Cabinet"):
            if fn in self.entries:
                w = self.entries[fn]
                w.setFocus()
                if isinstance(w, QLineEdit):
                    w.selectAll()
                return True
        if self.entries:
            w = next(iter(self.entries.values()))
            w.setFocus()
            if isinstance(w, QLineEdit):
                w.selectAll()
            return True
        return False
