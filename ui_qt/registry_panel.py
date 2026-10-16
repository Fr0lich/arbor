"""Dynamic Registration Panel for PySide6 replicating Tkinter's ui/registry_panel.py.

Constructs 3 collapsible section cards:
  1. Taxonomy & Scientific Name
  2. Collection & Specimen Metadata
  3. Audit Notes & Descriptions

Populates live field values, binds problem checkboxes, and updates card problem badges.
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
    QPlainTextEdit,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from ui_qt.qss_tokens import (
    BORDER,
    CARD,
    FONT_MONO,
    FONT_UI,
    HAIRLINE,
    HEADER_ROW,
    RED,
    SUBTEXT,
    SURFACE,
    TEXT,
    repolish,
)

logger = logging.getLogger(__name__)


class CollapsibleCardHeader(QFrame):
    """Clickable header bar for a registration card section."""

    def __init__(
        self,
        title: str,
        icon: str,
        on_toggle: Callable[[], None],
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self.on_toggle = on_toggle
        self.setCursor(QCursor(Qt.PointingHandCursor))
        self.setStyleSheet(f"""
            QFrame {{
                background-color: #f5f5f5;
                border-bottom: 1px solid {HAIRLINE};
                padding: 2px 4px;
            }}
            QFrame:hover {{
                background-color: #ebebeb;
            }}
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 5, 8, 5)
        layout.setSpacing(6)

        self.lbl_chevron = QLabel("▼")
        self.lbl_chevron.setFont(QFont("Segoe UI", 8, QFont.Bold))
        self.lbl_chevron.setStyleSheet(f"color: {SUBTEXT};")
        layout.addWidget(self.lbl_chevron)

        self.lbl_icon = QLabel(icon)
        self.lbl_icon.setFont(QFont("Segoe UI Symbol", 10))
        layout.addWidget(self.lbl_icon)

        self.lbl_title = QLabel(title)
        self.lbl_title.setFont(QFont("Segoe UI", 9, QFont.Bold))
        self.lbl_title.setStyleSheet(f"color: {TEXT}; font-weight: bold;")
        layout.addWidget(self.lbl_title)

        self.lbl_badge = QLabel("")
        self.lbl_badge.setFont(QFont("Courier New", 8, QFont.Bold))
        self.lbl_badge.setStyleSheet(f"color: {RED}; font-weight: bold; padding-left: 6px;")
        self.lbl_badge.setVisible(False)
        layout.addWidget(self.lbl_badge)

        layout.addStretch()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.on_toggle()
        super().mousePressEvent(event)

    def set_collapsed(self, collapsed: bool):
        self.lbl_chevron.setText("▶" if collapsed else "▼")

    def set_problem_count(self, count: int):
        if count > 0:
            self.lbl_badge.setText(f"({count} PROBLEM{'S' if count > 1 else ''})")
            self.lbl_badge.setVisible(True)
        else:
            self.lbl_badge.setText("")
            self.lbl_badge.setVisible(False)


class QtRegistrationCard(QFrame):
    """Styled card container with collapsible header and grid body."""

    def __init__(
        self,
        card_id: str,
        title: str,
        icon: str,
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self.card_id = card_id
        self.is_collapsed = False

        self.setObjectName(f"card_{card_id}")
        self.setStyleSheet(f"""
            QFrame#card_{card_id} {{
                background-color: {CARD};
                border: 1px solid {HAIRLINE};
                border-radius: 2px;
            }}
        """)

        card_layout = QVBoxLayout(self)
        card_layout.setContentsMargins(0, 0, 0, 0)
        card_layout.setSpacing(0)

        self.header = CollapsibleCardHeader(title, icon, self.toggle_collapsed, self)
        card_layout.addWidget(self.header)

        self.body = QWidget(self)
        self.body_layout = QGridLayout(self.body)
        self.body_layout.setContentsMargins(10, 8, 10, 8)
        self.body_layout.setHorizontalSpacing(8)
        self.body_layout.setVerticalSpacing(6)
        self.body_layout.setColumnStretch(0, 0)  # Checkbox column
        self.body_layout.setColumnStretch(1, 0)  # Label column
        self.body_layout.setColumnStretch(2, 1)  # Input widget column

        card_layout.addWidget(self.body)

    def toggle_collapsed(self):
        self.is_collapsed = not self.is_collapsed
        self.body.setVisible(not self.is_collapsed)
        self.header.set_collapsed(self.is_collapsed)


class QtRegistryPanel:
    """Manager and builder for the Specimen Registration cards and fields form in PySide6."""

    STANDARD_CARDS = [
        {
            "id": "taxonomy",
            "title": "Taxonomy & Scientific Name",
            "icon": "🧬",
            "fields": ["Genus", "Species", "Author", "Family", "Higher Classification"],
        },
        {
            "id": "collection",
            "title": "Collection & Specimen Metadata",
            "icon": "📦",
            "fields": [
                "Collector",
                "Innsammling Nr.",
                "Collection Date",
                "Collection Place",
                "Variant",
                "(N) Plant Part",
                "Plant Part",
                "Box Label",
                "Conservation Status",
                "Online photo 1",
                "Online photo 2",
                "Online photo 3",
                "UID",
            ],
        },
        {
            "id": "notes",
            "title": "Audit Notes & Descriptions",
            "icon": "📝",
            "fields": ["Observation", "Comment", "ProblemDescription"],
        },
    ]

    def __init__(self, parent_layout: QVBoxLayout, config_ref: dict | None = None):
        self.parent_layout = parent_layout
        self.config_ref = config_ref or {}
        self.cards: dict[str, QtRegistrationCard] = {}
        self.reg_entries: dict[str, QWidget] = {}
        self.reg_labels: dict[str, QLabel] = {}
        self.problem_cbs: dict[str, QCheckBox] = {}
        self.field_to_problem: dict[str, str] = {}
        self.card_fields: dict[str, list[str]] = {}
        self.on_field_changed_callback: Optional[Callable[[str, str], None]] = None
        self.on_problem_changed_callback: Optional[Callable[[str, bool], None]] = None

        self._build_panel()

    def _build_panel(self) -> None:
        """Construct the 3 styled card sections inside parent layout."""
        # Clear existing items in layout
        while self.parent_layout.count():
            item = self.parent_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

        self.cards.clear()
        self.reg_entries.clear()
        self.reg_labels.clear()
        self.problem_cbs.clear()
        self.field_to_problem.clear()
        self.card_fields.clear()

        # Map problem columns to registration fields
        problems_cfg = self.config_ref.get("ui_sections", {}).get("problems", [])
        for p in problems_cfg:
            p_name = p.get("name")
            maps_to = p.get("maps_to")
            if p_name and maps_to:
                self.field_to_problem[maps_to] = p_name

        # All defined registration fields from configuration
        all_reg_fields = [f["name"] for f in self.config_ref.get("ui_sections", {}).get("registration", [])]
        reg_config_map = {f["name"]: f for f in self.config_ref.get("ui_sections", {}).get("registration", [])}

        # Check if config has custom reg_groups
        reg_groups = self.config_ref.get("ui_sections", {}).get("reg_groups")
        if reg_groups:
            card_defs = []
            icons = ["🧬", "📦", "📝", "📋", "📁"]
            for idx, g in enumerate(reg_groups):
                card_defs.append({
                    "id": f"group_{idx}",
                    "title": g.get("name", f"Group {idx+1}"),
                    "icon": icons[idx % len(icons)],
                    "fields": g.get("fields", []),
                })
        else:
            card_defs = [dict(c) for c in self.STANDARD_CARDS]
            # Safeguard: Append any other registration fields in config not in standard cards to 'collection'
            assigned = set()
            for c in card_defs:
                assigned.update(c["fields"])
            unassigned = [f for f in all_reg_fields if f not in assigned]
            if unassigned:
                card_defs[1]["fields"].extend(unassigned)

        for c_def in card_defs:
            card_id = c_def["id"]
            title = c_def["title"]
            icon = c_def["icon"]
            fields = c_def["fields"]

            # Filter fields that exist in config or create dummy entry
            card = QtRegistrationCard(card_id, title, icon)
            self.cards[card_id] = card
            self.card_fields[card_id] = fields
            self.parent_layout.addWidget(card)

            current_row = 0
            for field_name in fields:
                f_meta = reg_config_map.get(field_name, {"name": field_name, "type": "text"})
                ftype = f_meta.get("type", "text")
                is_readonly = bool(f_meta.get("readonly", False))

                # Col 0: Problem checkbox (if mapped)
                prob_col = self.field_to_problem.get(field_name)
                if prob_col:
                    cb = QCheckBox(card.body)
                    cb.setToolTip(f"Flag as having a problem ({prob_col.replace('_', ' ')})")
                    cb.setCursor(QCursor(Qt.PointingHandCursor))
                    cb.toggled.connect(lambda checked, pc=prob_col, fn=field_name: self._on_problem_toggled(pc, fn, checked))
                    self.problem_cbs[prob_col] = cb
                    card.body_layout.addWidget(cb, current_row, 0, Qt.AlignVCenter)
                else:
                    spacer = QWidget(card.body)
                    spacer.setFixedWidth(16)
                    card.body_layout.addWidget(spacer, current_row, 0)

                # Col 1: Label
                lbl = QLabel(field_name, card.body)
                lbl.setFont(QFont("Segoe UI", 9, QFont.Bold))
                lbl.setStyleSheet(f"color: {TEXT}; font-weight: bold;")
                lbl.setMinimumWidth(110)
                card.body_layout.addWidget(lbl, current_row, 1, Qt.AlignVCenter | Qt.AlignLeft)
                self.reg_labels[field_name] = lbl

                # Col 2: Input Widget
                if ftype == "choice":
                    choices = f_meta.get("choices", [])
                    combo = QComboBox(card.body)
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
                    for ch in choices:
                        if ch:
                            combo.addItem(str(ch))
                    combo.currentTextChanged.connect(lambda txt, fn=field_name: self._on_field_changed(fn, txt))
                    card.body_layout.addWidget(combo, current_row, 2)
                    self.reg_entries[field_name] = combo

                elif ftype == "multiline" or field_name in (
                    "Observation",
                    "Comment",
                    "ProblemDescription",
                    "Notes",
                    "Purpose",
                    "Conservation Status",
                ):
                    text_edit = QPlainTextEdit(card.body)
                    text_edit.setFont(QFont("Courier New", 9))
                    text_edit.setFixedHeight(56)
                    text_edit.setStyleSheet(f"""
                        QPlainTextEdit {{
                            background-color: {CARD};
                            color: {TEXT};
                            border: 1px solid {HAIRLINE};
                            border-radius: 1px;
                            padding: 4px;
                            font-family: {FONT_MONO};
                        }}
                        QPlainTextEdit:focus {{
                            border: 1px solid {BORDER};
                        }}
                    """)
                    text_edit.textChanged.connect(lambda fn=field_name, te=text_edit: self._on_field_changed(fn, te.toPlainText()))
                    card.body_layout.addWidget(text_edit, current_row, 2)
                    self.reg_entries[field_name] = text_edit

                else:
                    line_edit = QLineEdit(card.body)
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
                    line_edit.textEdited.connect(lambda txt, fn=field_name: self._on_field_changed(fn, txt))
                    card.body_layout.addWidget(line_edit, current_row, 2)
                    self.reg_entries[field_name] = line_edit

                current_row += 1

        self.parent_layout.addStretch()

    def _on_field_changed(self, field_name: str, value: str) -> None:
        if self.on_field_changed_callback:
            self.on_field_changed_callback(field_name, value)

    def _on_problem_toggled(self, problem_col: str, field_name: str, checked: bool) -> None:
        self.set_field_problem_highlight(field_name, checked)
        self._update_all_card_badges()
        if self.on_problem_changed_callback:
            self.on_problem_changed_callback(problem_col, checked)

    def set_field_problem_highlight(self, field_name: str, has_problem: bool) -> None:
        """Apply or clear amber problem tint on a field's input widget."""
        widget = self.reg_entries.get(field_name)
        if not widget:
            return

        bg_color = "#fef9e7" if has_problem else CARD
        border_color = "#d9a036" if has_problem else HAIRLINE

        if isinstance(widget, QLineEdit):
            widget.setStyleSheet(f"""
                QLineEdit {{
                    background-color: {bg_color};
                    color: {TEXT};
                    border: 1px solid {border_color};
                    border-radius: 1px;
                    padding: 3px 6px;
                    font-family: {FONT_MONO};
                }}
            """)
        elif isinstance(widget, QPlainTextEdit):
            widget.setStyleSheet(f"""
                QPlainTextEdit {{
                    background-color: {bg_color};
                    color: {TEXT};
                    border: 1px solid {border_color};
                    border-radius: 1px;
                    padding: 4px;
                    font-family: {FONT_MONO};
                }}
            """)
        elif isinstance(widget, QComboBox):
            widget.setStyleSheet(f"""
                QComboBox {{
                    background-color: {bg_color};
                    color: {TEXT};
                    border: 1px solid {border_color};
                    border-radius: 1px;
                    padding: 3px 6px;
                    font-family: {FONT_MONO};
                }}
            """)

    def _update_all_card_badges(self) -> None:
        """Update problem count badges for all card headers."""
        for card_id, card in self.cards.items():
            fields = self.card_fields.get(card_id, [])
            count = 0
            for fn in fields:
                p_col = self.field_to_problem.get(fn)
                if p_col and self.problem_cbs.get(p_col) and self.problem_cbs[p_col].isChecked():
                    count += 1
            card.header.set_problem_count(count)

    def set_problem_flag(self, prob_col: str, is_flagged: bool) -> None:
        """Programmatically set a problem checkbox and update field tint and badges."""
        cb = self.problem_cbs.get(prob_col)
        if cb:
            cb.blockSignals(True)
            cb.setChecked(is_flagged)
            cb.blockSignals(False)

        maps_to = next((f for f, p in self.field_to_problem.items() if p == prob_col), None)
        if maps_to:
            self.set_field_problem_highlight(maps_to, is_flagged)
        self._update_all_card_badges()

    def populate_specimen(
        self,
        oid: str,
        df_reg: pd.DataFrame | None,
        df_obs: pd.DataFrame | None = None,
    ) -> None:
        """Populate all registration inputs and problem checkboxes for a given specimen ID."""
        if df_reg is None or oid not in df_reg.index:
            self.clear()
            return

        # Block signals during programmatic update
        for widget in self.reg_entries.values():
            widget.blockSignals(True)
        for cb in self.problem_cbs.values():
            cb.blockSignals(True)

        try:
            row = df_reg.loc[oid]
            if isinstance(row, pd.DataFrame):
                row = row.iloc[0]

            for field_name, widget in self.reg_entries.items():
                val = ""
                if field_name in row.index:
                    raw = row[field_name]
                    if not pd.isna(raw):
                        val = str(raw).strip()

                if isinstance(widget, QLineEdit):
                    widget.setText(val)
                elif isinstance(widget, QComboBox):
                    widget.setCurrentText(val)
                elif isinstance(widget, QPlainTextEdit):
                    widget.setPlainText(val)

            # Populate problem checkboxes from df_obs
            obs_row = None
            if df_obs is not None and oid in df_obs.index:
                obs_row = df_obs.loc[oid]
                if isinstance(obs_row, pd.DataFrame):
                    obs_row = obs_row.iloc[0]

            for prob_col, cb in self.problem_cbs.items():
                is_flagged = False
                if obs_row is not None and prob_col in obs_row.index:
                    is_flagged = bool(obs_row[prob_col])
                cb.setChecked(is_flagged)

                # Set field tint
                maps_to = next((f for f, p in self.field_to_problem.items() if p == prob_col), None)
                if maps_to:
                    self.set_field_problem_highlight(maps_to, is_flagged)

            self._update_all_card_badges()

        finally:
            for widget in self.reg_entries.values():
                widget.blockSignals(False)
            for cb in self.problem_cbs.values():
                cb.blockSignals(False)

    def clear(self) -> None:
        """Clear all inputs and checkboxes."""
        for widget in self.reg_entries.values():
            widget.blockSignals(True)
            if isinstance(widget, QLineEdit):
                widget.clear()
            elif isinstance(widget, QComboBox):
                widget.setCurrentIndex(0)
            elif isinstance(widget, QPlainTextEdit):
                widget.clear()
            widget.blockSignals(False)

        for cb in self.problem_cbs.values():
            cb.blockSignals(True)
            cb.setChecked(False)
            cb.blockSignals(False)

        for fn in self.reg_entries:
            self.set_field_problem_highlight(fn, False)

        for card in self.cards.values():
            card.header.set_problem_count(0)

    def get_field_values(self) -> dict[str, str]:
        """Read all current field values as a dictionary."""
        values = {}
        for fn, w in self.reg_entries.items():
            if isinstance(w, QLineEdit):
                values[fn] = w.text().strip()
            elif isinstance(w, QComboBox):
                values[fn] = w.currentText().strip()
            elif isinstance(w, QPlainTextEdit):
                values[fn] = w.toPlainText().strip()
        return values
