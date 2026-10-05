"""Controller for the Qt main review workspace.

Wires layout splitters, navigation buttons, and secondary dialogs including
the Filter Objects dialog (QtFilterDialog).
"""
from __future__ import annotations

import pandas as pd
from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import QTreeWidgetItem

from models import AppState
from repository import REVIEWED_COLUMN
from ui_qt.filter_dialog import QtFilterDialog
from ui_qt.loader import load_ui


class QtMainWindow:
    """Controller for the Arbor main workspace window."""

    def __init__(self, app_state: AppState | None = None):
        self.app = app_state or AppState()
        self.win = load_ui("main_window_existing.ui")
        self.filter_dialog: QtFilterDialog | None = None

        # Mirror Tkinter pane weights: left 0 / center 3 / right 3
        self.win.splitter_main.setSizes([380, 640, 420])
        tree = self.win.tree_objects
        tree.setColumnWidth(0, 36)
        tree.setColumnWidth(1, 90)
        tree.setColumnWidth(2, 120)
        self.win.splitter_main.setStretchFactor(0, 0)
        self.win.splitter_main.setStretchFactor(1, 3)
        self.win.splitter_main.setStretchFactor(2, 3)
        self.win.splitter_left.setStretchFactor(0, 1)
        self.win.splitter_left.setStretchFactor(1, 0)

        self._wire_filter_actions()
        self.refresh_object_tree()

    def _wire_filter_actions(self) -> None:
        """Connect filter button, shortcuts, and status indicators."""
        if hasattr(self.win, "btn_filter"):
            self.win.btn_filter.clicked.connect(self.open_filter_dialog)

        # Global shortcut: Ctrl+G opens filter menu
        QShortcut(QKeySequence("Ctrl+G"), self.win).activated.connect(self.open_filter_dialog)

        # Clear search button in treeview pane
        if hasattr(self.win, "btn_clear_search"):
            self.win.btn_clear_search.clicked.connect(self.clear_filter)

    def open_filter_dialog(self) -> None:
        """Open or raise the modal Filter Objects dialog."""
        self.filter_dialog = QtFilterDialog(
            parent=self.win,
            app_state=self.app,
            on_apply=self.on_filter_applied,
            on_clear=self.on_filter_cleared,
        )
        self.filter_dialog.exec()

    def on_filter_applied(self, matched: list[str]) -> None:
        """Handler called when filter criteria are applied in QtFilterDialog."""
        if self.app:
            self.app.active_object_ids = matched

        self._update_filter_status_display()
        self.refresh_object_tree()

    def on_filter_cleared(self) -> None:
        """Handler called when filter criteria are reset in QtFilterDialog."""
        if self.app and self.app.df_reg is not None:
            self.app.active_object_ids = list(self.app.df_reg.index)
        elif self.app:
            self.app.active_object_ids = []

        self._update_filter_status_display()
        self.refresh_object_tree()

    def clear_filter(self) -> None:
        """Clear active filter directly from the main window toolbar."""
        if self.filter_dialog:
            self.filter_dialog.clear_filter(show_feedback=False)
        self.on_filter_cleared()

    def _update_filter_status_display(self) -> None:
        """Update filter status labels and indicators in the workspace."""
        total = len(self.app.df_reg) if self.app and self.app.df_reg is not None else 0
        active_count = len(self.app.active_object_ids) if self.app else 0

        is_filtered = total > 0 and active_count < total

        if hasattr(self.win, "lbl_filter_status"):
            if is_filtered:
                self.win.lbl_filter_status.setText(f"Filter active: {active_count} of {total} objects")
                self.win.lbl_filter_status.setStyleSheet("color: #c93a40; font-weight: bold;")
            else:
                self.win.lbl_filter_status.setText("")

        if hasattr(self.win, "lbl_filter_indicator"):
            self.win.lbl_filter_indicator.setVisible(is_filtered)

        if hasattr(self.win, "lbl_sb_filter_badge"):
            if is_filtered:
                self.win.lbl_sb_filter_badge.setText(f"FILTER: {active_count}/{total}")
                self.win.lbl_sb_filter_badge.setVisible(True)
            else:
                self.win.lbl_sb_filter_badge.setVisible(False)

        if hasattr(self.win, "lbl_sb_object_count"):
            self.win.lbl_sb_object_count.setText(f"OBJECTS: {active_count}")

    def refresh_object_tree(self) -> None:
        """Repopulate tree_objects from app.active_object_ids and dataframes."""
        if not hasattr(self.win, "tree_objects"):
            return

        tree = self.win.tree_objects
        tree.clear()

        if not self.app or self.app.df_reg is None:
            return

        df_reg = self.app.df_reg
        df_obs = getattr(self.app, "df_obs", None)

        for oid in self.app.active_object_ids:
            if oid not in df_reg.index:
                continue

            # Column 0: Reviewed status checkmark
            is_reviewed = False
            if df_obs is not None and oid in df_obs.index and REVIEWED_COLUMN in df_obs.columns:
                is_reviewed = bool(df_obs.loc[oid, REVIEWED_COLUMN])

            reviewed_mark = "✓" if is_reviewed else " "

            # Column 1: ObjectID
            oid_str = str(oid)

            # Column 2: Taxon name (Genus + Species)
            genus = str(df_reg.loc[oid, "Genus"]) if "Genus" in df_reg.columns and not pd.isna(df_reg.loc[oid, "Genus"]) else ""
            species = str(df_reg.loc[oid, "Species"]) if "Species" in df_reg.columns and not pd.isna(df_reg.loc[oid, "Species"]) else ""
            taxon = f"{genus} {species}".strip() or "(unnamed)"

            item = QTreeWidgetItem(tree, [reviewed_mark, oid_str, taxon])
            if is_reviewed:
                item.setForeground(0, Qt.darkGreen)

        if tree.topLevelItemCount() > 0:
            tree.setCurrentItem(tree.topLevelItem(0))

    def show(self) -> None:
        self.win.show()
