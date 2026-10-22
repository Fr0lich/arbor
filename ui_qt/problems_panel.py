"""ui_qt/problems_panel.py - Problems Tab Checklist & Active Flag Summary.

Replicates Tkinter's ui/registry_panel.py (lines 516-546) and ui/main_window.py:
  1. 2-column grid of problem checkboxes from config['ui_sections']['problems'].
  2. Horizontal separator line.
  3. Dynamic summary list of active problem flags:
     - Green '✔ No active problems flagged.' when clean.
     - Red '⚠ <Problem Name>' items for each active problem flag.
"""

from __future__ import annotations

import logging
from typing import Callable, Optional

import pandas as pd
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QCursor, QFont
from PySide6.QtWidgets import (
    QCheckBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from ui_qt.qss_tokens import (
    CARD,
    FONT_UI,
    GREEN,
    HAIRLINE,
    RED,
    SUBTEXT,
    SURFACE,
    TEXT,
)

logger = logging.getLogger(__name__)


class QtProblemsPanel(QWidget):
    """Controller and view for the specimen Problems tab."""

    problem_toggled = Signal(str, bool)

    def __init__(
        self,
        config_ref: dict | None = None,
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self.config_ref = config_ref or {}
        self.current_oid: str | None = None
        self.problem_cbs: dict[str, QCheckBox] = {}
        self.on_problem_toggled_callback: Optional[Callable[[str, bool], None]] = None

        self._build_ui()

    def _build_ui(self) -> None:
        """Construct the checklist grid, separator, and active summary area."""
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(12, 12, 12, 12)
        root_layout.setSpacing(10)

        # 1. Two-Column Checkbox Grid
        self.grid_widget = QWidget(self)
        self.grid_layout = QGridLayout(self.grid_widget)
        self.grid_layout.setContentsMargins(0, 0, 0, 0)
        self.grid_layout.setHorizontalSpacing(16)
        self.grid_layout.setVerticalSpacing(8)
        self.grid_layout.setColumnStretch(0, 1)
        self.grid_layout.setColumnStretch(1, 1)

        problems_cfg = self.config_ref.get("ui_sections", {}).get("problems", [])
        if not problems_cfg:
            problems_cfg = [
                {"name": "Genus_Problem"},
                {"name": "Species_Problem"},
                {"name": "Family_Problem"},
                {"name": "Author_Problem"},
                {"name": "PlantPart_Problem"},
                {"name": "Collector_Problem"},
                {"name": "Collection_Date_Problem"},
                {"name": "Collection_Place_Problem"},
                {"name": "Box_Label_Problem"},
                {"name": "Images_Problem"},
                {"name": "Other_problem"},
            ]

        self.problem_cbs.clear()
        for idx, p_item in enumerate(problems_cfg):
            p_name = p_item.get("name", "")
            if not p_name:
                continue

            display_name = p_name.replace("_", " ")
            cb = QCheckBox(display_name, self.grid_widget)
            cb.setCursor(QCursor(Qt.PointingHandCursor))
            cb.setFont(QFont("Segoe UI", 9))
            cb.setStyleSheet(f"""
                QCheckBox {{
                    color: {TEXT};
                    font-family: {FONT_UI};
                    spacing: 6px;
                }}
                QCheckBox:hover {{
                    color: #000000;
                }}
            """)
            cb.toggled.connect(lambda checked, pn=p_name: self._on_cb_toggled(pn, checked))
            self.problem_cbs[p_name] = cb

            row = idx // 2
            col = idx % 2
            self.grid_layout.addWidget(cb, row, col, Qt.AlignLeft | Qt.AlignVCenter)

        root_layout.addWidget(self.grid_widget)

        # 2. Horizontal Separator
        separator = QFrame(self)
        separator.setFrameShape(QFrame.HLine)
        separator.setFrameShadow(QFrame.Sunken)
        separator.setStyleSheet(f"background-color: {HAIRLINE}; max-height: 1px;")
        root_layout.addWidget(separator)

        # 3. Active Problem Summary Section
        lbl_summary_title = QLabel("ACTIVE PROBLEM FLAGS", self)
        lbl_summary_title.setFont(QFont("Segoe UI", 8, QFont.Bold))
        lbl_summary_title.setStyleSheet(f"color: {SUBTEXT}; letter-spacing: 0.5px;")
        root_layout.addWidget(lbl_summary_title)

        self.summary_container = QWidget(self)
        self.summary_layout = QVBoxLayout(self.summary_container)
        self.summary_layout.setContentsMargins(4, 4, 4, 4)
        self.summary_layout.setSpacing(4)
        root_layout.addWidget(self.summary_container)

        root_layout.addStretch()

        self._render_summary([])

    def _on_cb_toggled(self, problem_name: str, checked: bool) -> None:
        """Handle user toggling a problem checkbox."""
        active = self.get_active_problems()
        self._render_summary(active)

        self.problem_toggled.emit(problem_name, checked)
        if self.on_problem_toggled_callback:
            self.on_problem_toggled_callback(problem_name, checked)

    def _render_summary(self, active_problems: list[str]) -> None:
        """Render active problem flags or clean status matching Tkinter."""
        while self.summary_layout.count():
            item = self.summary_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

        if not active_problems:
            row = QWidget(self.summary_container)
            h = QHBoxLayout(row)
            h.setContentsMargins(4, 4, 4, 4)
            h.setSpacing(8)

            lbl_icon = QLabel("✔", row)
            lbl_icon.setFont(QFont("Segoe UI", 11, QFont.Bold))
            lbl_icon.setStyleSheet(f"color: {GREEN};")
            h.addWidget(lbl_icon)

            lbl_text = QLabel("No active problems flagged.", row)
            lbl_text.setFont(QFont("Segoe UI", 9, QFont.Bold))
            lbl_text.setStyleSheet(f"color: {GREEN};")
            h.addWidget(lbl_text)
            h.addStretch()

            self.summary_layout.addWidget(row)
        else:
            for p_name in active_problems:
                row = QWidget(self.summary_container)
                h = QHBoxLayout(row)
                h.setContentsMargins(4, 2, 4, 2)
                h.setSpacing(8)

                lbl_icon = QLabel("⚠", row)
                lbl_icon.setFont(QFont("Segoe UI", 10, QFont.Bold))
                lbl_icon.setStyleSheet(f"color: {RED};")
                h.addWidget(lbl_icon)

                lbl_text = QLabel(p_name.replace("_", " "), row)
                lbl_text.setFont(QFont("Segoe UI", 9, QFont.Bold))
                lbl_text.setStyleSheet(f"color: {RED};")
                h.addWidget(lbl_text)
                h.addStretch()

                self.summary_layout.addWidget(row)

    def populate_specimen(self, oid: str, df_obs: pd.DataFrame | None) -> list[str]:
        """Populate checkboxes for given specimen and return list of active problems."""
        self.current_oid = oid

        for cb in self.problem_cbs.values():
            cb.blockSignals(True)

        try:
            obs_row = None
            if df_obs is not None and oid in df_obs.index:
                obs_row = df_obs.loc[oid]
                if isinstance(obs_row, pd.DataFrame):
                    obs_row = obs_row.iloc[0]

            for p_name, cb in self.problem_cbs.items():
                is_active = False
                if obs_row is not None and p_name in obs_row.index:
                    is_active = bool(obs_row[p_name])
                cb.setChecked(is_active)

            active = self.get_active_problems()
            self._render_summary(active)
            return active
        finally:
            for cb in self.problem_cbs.values():
                cb.blockSignals(False)

    def set_problem_state(self, problem_name: str, active: bool) -> None:
        """Programmatically update a single problem state and re-render summary."""
        cb = self.problem_cbs.get(problem_name)
        if cb:
            cb.blockSignals(True)
            cb.setChecked(active)
            cb.blockSignals(False)

        current_active = self.get_active_problems()
        self._render_summary(current_active)

    def get_active_problems(self) -> list[str]:
        """Return list of active problem names, excluding Images_Missing."""
        active = []
        for p_name, cb in self.problem_cbs.items():
            if p_name == "Images_Missing":
                continue
            if cb.isChecked():
                active.append(p_name)
        return active

    def clear(self) -> None:
        """Clear all checkboxes and summary."""
        self.current_oid = None
        for cb in self.problem_cbs.values():
            cb.blockSignals(True)
            cb.setChecked(False)
            cb.blockSignals(False)
        self._render_summary([])

    def focus_first_checkbox(self) -> bool:
        """Focus the first problem checkbox in the grid."""
        if self.problem_cbs:
            cb = next(iter(self.problem_cbs.values()))
            cb.setFocus()
            return True
        return False

    def toggle_focused_checkbox(self) -> bool:
        """Toggle the currently focused problem checkbox."""
        for cb in self.problem_cbs.values():
            if cb.hasFocus():
                cb.toggle()
                return True
        return False
