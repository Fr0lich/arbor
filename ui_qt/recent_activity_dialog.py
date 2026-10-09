"""PySide6 implementation of the Recent Activity & Session History Dialog.

Wraps ``qt designer/recent_activity.ui`` and binds visited objects history and
session edit audit trail from AppState.df_log.
"""
from __future__ import annotations

from typing import Callable, Optional

import pandas as pd
from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QDialog,
    QHeaderView,
    QTableWidgetItem,
    QWidget,
)

from models import AppState
from ui_qt.loader import load_ui


ACTION_DISPLAY_MAP = {
    "EDIT": "Manual Edit",
    "MOBILE_EDIT": "Mobile Edit",
    "RESOLVE_HISTORICAL_CONFLICT": "Conflict Resolver",
    "CREATE_OBJECT_FAST": "Created Object",
    "DATABASE_CREATED": "Database Created",
    "GBIF_UPDATE": "GBIF Update",
    "GBIF_ROLLBACK": "GBIF Rollback",
    "REVIEWED": "Reviewed",
    "NOT_REVIEWED": "Not Reviewed",
    "PHOTO_ADDED": "Photo Added",
    "UNVALIDATED_UPDATE": "Unvalidated Update",
    "SAVE": "Session Save",
}


class QtRecentActivityDialog:
    """Controller wrapping ``qt designer/recent_activity.ui``."""

    def __init__(
        self,
        parent: Optional[QWidget] = None,
        app_state: Optional[AppState] = None,
        history_stack: Optional[list[str]] = None,
        on_navigate: Optional[Callable[[str], None]] = None,
        default_tab: int = 0,
    ):
        self.parent = parent
        self.app = app_state or AppState()
        self.history_stack = list(history_stack) if history_stack is not None else []
        self.on_navigate = on_navigate

        self.win: QDialog = load_ui("recent_activity.ui", parent)
        self._raw_edits: list[tuple[str, str, str, str, str]] = []

        self._setup_ui()
        if hasattr(self.win, "tab_widget"):
            self.win.tab_widget.setCurrentIndex(default_tab)

        self.refresh()

    def _setup_ui(self) -> None:
        """Configure tables, shortcuts, and event listeners."""
        # Close button
        if hasattr(self.win, "btn_close"):
            self.win.btn_close.clicked.connect(self.win.accept)

        # Navigate button
        if hasattr(self.win, "btn_navigate"):
            self.win.btn_navigate.clicked.connect(self._do_navigate)

        # Setup Visited Table
        if hasattr(self.win, "table_visited"):
            tv = self.win.table_visited
            tv.setColumnCount(3)
            tv.setHorizontalHeaderLabels(["Object ID", "Taxon / Title", "Time"])
            tv.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
            tv.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
            tv.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
            tv.verticalHeader().setVisible(False)
            tv.setSelectionBehavior(tv.SelectionBehavior.SelectRows)
            tv.setSelectionMode(tv.SelectionMode.SingleSelection)
            tv.setEditTriggers(tv.EditTrigger.NoEditTriggers)
            tv.itemDoubleClicked.connect(lambda _: self._do_navigate())

        # Setup Edits Table
        if hasattr(self.win, "table_edits"):
            te = self.win.table_edits
            te.setColumnCount(5)
            te.setHorizontalHeaderLabels(["Timestamp", "Object ID", "Action", "Field Changed", "New Value"])
            te.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
            te.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
            te.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
            te.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
            te.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
            te.verticalHeader().setVisible(False)
            te.setSelectionBehavior(te.SelectionBehavior.SelectRows)
            te.setSelectionMode(te.SelectionMode.SingleSelection)
            te.setEditTriggers(te.EditTrigger.NoEditTriggers)
            te.itemDoubleClicked.connect(lambda _: self._do_navigate())

        # Live search filter for edits
        if hasattr(self.win, "input_filter_edits"):
            self.win.input_filter_edits.textChanged.connect(self._filter_edits)

        # Escape shortcut
        QShortcut(QKeySequence(Qt.Key.Key_Escape), self.win).activated.connect(self.win.accept)

    def refresh(self) -> None:
        """Repopulate visited objects table and session edits table."""
        self._populate_visited()
        self._populate_edits()

    def _populate_visited(self) -> None:
        """Populate table_visited with navigation history."""
        if not hasattr(self.win, "table_visited"):
            return

        table = self.win.table_visited
        table.setRowCount(0)

        # Fallback to current object ID or active objects if history is empty
        items = list(self.history_stack)
        if not items and self.app.current_object_id:
            items = [self.app.current_object_id]

        seen = set()
        visited_rows = []
        for oid in reversed(items):
            oid_str = str(oid).strip()
            if not oid_str or oid_str in seen:
                continue
            seen.add(oid_str)

            title = f"Specimen #{oid_str}"
            if self.app.df_reg is not None and oid_str in self.app.df_reg.index:
                row = self.app.df_reg.loc[oid_str]
                genus = str(row.get("Genus", "")).strip() if "Genus" in row and not pd.isna(row.get("Genus")) else ""
                species = str(row.get("Species", "")).strip() if "Species" in row and not pd.isna(row.get("Species")) else ""
                taxon = f"{genus} {species}".strip()
                if taxon:
                    title = taxon

            visited_rows.append((oid_str, title, "Recent"))

        table.setRowCount(len(visited_rows))
        for row_idx, (oid_str, title, time_str) in enumerate(visited_rows):
            item_oid = QTableWidgetItem(oid_str)
            item_title = QTableWidgetItem(title)
            item_time = QTableWidgetItem(time_str)

            table.setItem(row_idx, 0, item_oid)
            table.setItem(row_idx, 1, item_title)
            table.setItem(row_idx, 2, item_time)

        if visited_rows and hasattr(self.win, "btn_navigate"):
            self.win.btn_navigate.setEnabled(True)
            table.selectRow(0)

    def _populate_edits(self) -> None:
        """Extract session log entries from app.df_log into table_edits."""
        if not hasattr(self.win, "table_edits"):
            return

        self._raw_edits = []
        df_log = getattr(self.app, "df_log", None)

        if df_log is not None and not df_log.empty:
            df = df_log.iloc[::-1]  # Most recent first
            t_col = df["Timestamp"].fillna("").astype(str).tolist() if "Timestamp" in df.columns else [""] * len(df)
            a_col = df["Action"].fillna("").astype(str).tolist() if "Action" in df.columns else [""] * len(df)
            o_col = df["ObjectID"].fillna("").astype(str).tolist() if "ObjectID" in df.columns else [""] * len(df)
            cf_col = df["ChangedFields"].fillna("").astype(str).tolist() if "ChangedFields" in df.columns else [""] * len(df)
            cv_col = df["ChangedValues"].fillna("").astype(str).tolist() if "ChangedValues" in df.columns else [""] * len(df)
            pf_col = df["ProblemsChanged"].fillna("").astype(str).tolist() if "ProblemsChanged" in df.columns else [""] * len(df)
            pv_col = df["ProblemsChangedValues"].fillna("").astype(str).tolist() if "ProblemsChangedValues" in df.columns else [""] * len(df)
            lf_col = df["LocationChanged"].fillna("").astype(str).tolist() if "LocationChanged" in df.columns else [""] * len(df)
            lv_col = df["LocationChangedValues"].fillna("").astype(str).tolist() if "LocationChangedValues" in df.columns else [""] * len(df)

            for i in range(len(df)):
                tstamp = t_col[i]
                if "T" in tstamp:
                    tstamp = tstamp.split(".")[0].replace("T", " ")

                raw_act = a_col[i]
                act = ACTION_DISPLAY_MAP.get(raw_act, raw_act)
                oid = o_col[i]

                field_parts = []
                val_parts = []

                if cf_col[i].strip() and cf_col[i] != "(no changes)":
                    field_parts.append(cf_col[i])
                    val_parts.append(cv_col[i].replace("  ", " → "))

                if pf_col[i].strip():
                    field_parts.append(f"Problems: {pf_col[i]}")
                    val_parts.append(pv_col[i].replace("  ", " → "))

                if lf_col[i].strip():
                    field_parts.append(f"Location: {lf_col[i]}")
                    val_parts.append(lv_col[i].replace("  ", " → "))

                fields_str = " | ".join(field_parts) if field_parts else cf_col[i] or "—"
                vals_str = " | ".join(val_parts) if val_parts else cv_col[i] or "—"

                self._raw_edits.append((tstamp, oid, act, fields_str, vals_str))

        self._filter_edits("")

    def _filter_edits(self, query: str = "") -> None:
        """Filter table_edits rows based on search input."""
        if not hasattr(self.win, "table_edits"):
            return

        table = self.win.table_edits
        q = (self.win.input_filter_edits.text() if hasattr(self.win, "input_filter_edits") else query).strip().lower()

        filtered = [
            row for row in self._raw_edits
            if not q or any(q in cell.lower() for cell in row)
        ]

        table.setRowCount(len(filtered))
        for row_idx, (tstamp, oid, act, fields_str, vals_str) in enumerate(filtered):
            table.setItem(row_idx, 0, QTableWidgetItem(tstamp))
            table.setItem(row_idx, 1, QTableWidgetItem(oid))
            table.setItem(row_idx, 2, QTableWidgetItem(act))
            table.setItem(row_idx, 3, QTableWidgetItem(fields_str))
            table.setItem(row_idx, 4, QTableWidgetItem(vals_str))

    def _get_selected_oid(self) -> Optional[str]:
        """Return ObjectID from selected row of the current active tab."""
        active_tab_idx = self.win.tab_widget.currentIndex() if hasattr(self.win, "tab_widget") else 0
        table = self.win.table_visited if active_tab_idx == 0 else self.win.table_edits

        sel = table.selectedItems()
        if not sel:
            return None

        row = sel[0].row()
        oid_col = 0 if active_tab_idx == 0 else 1
        item = table.item(row, oid_col)
        return item.text().strip() if item else None

    def _do_navigate(self) -> None:
        """Trigger navigation callback for selected object and close dialog."""
        oid = self._get_selected_oid()
        if not oid:
            return

        self.app.current_object_id = oid
        if self.on_navigate:
            self.on_navigate(oid)

        self.win.accept()

    def exec(self) -> int:
        return self.win.exec()

    def show(self) -> None:
        self.win.show()

    def __getattr__(self, name: str):
        return getattr(self.win, name)
