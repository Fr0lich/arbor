"""ui_qt/historical_resolver.py - Historical Books Conflict Resolver Dialog Controller.

Wraps 'qt designer/historical_resolver.ui' (HistoricalResolverDialog).
Cross-references active specimen records against loaded historical archival books
(app_state.historical_dbs), presents side-by-side discrepancy comparisons, and
allows selective or batch adoption of historical archival values into app_state.df_reg.
"""
from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional, Tuple

import pandas as pd
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QHeaderView,
    QMessageBox,
    QTableWidgetItem,
    QWidget,
)

from models import AppState
from ui_qt.base_queue import QtSpecimenQueueController
from ui_qt.loader import load_ui


class QtHistoricalResolverDialog(QDialog):
    """Controller for Historical Books Discrepancy & Conflict Resolver dialog."""

    def __init__(
        self,
        parent: Optional[QWidget] = None,
        app_state: Optional[AppState] = None,
        oid: Optional[str] = None,
        on_resolved: Optional[Callable[[str], None]] = None,
    ):
        super().__init__(parent)
        self.app = app_state or AppState()
        self.on_resolved = on_resolved

        # Load declarative Qt Designer UI
        self.dialog = load_ui("historical_resolver.ui")
        if parent:
            self.dialog.setParent(parent, Qt.Dialog)

        # Target specimen ID
        self.target_oid = str(oid or self.app.current_object_id or "")

        # Initialize base queue controller for undo snapshot & commit utilities
        self.queue_ctrl = QtSpecimenQueueController(
            app_state=self.app,
            oid_queue=[self.target_oid] if self.target_oid else [],
            parent_widget=self.dialog,
        )

        # Discrepancy rows: list of dicts {field, current_val, historical_val, source_book}
        self.discrepancies: List[Dict[str, Any]] = []

        # Connect UI and load discrepancy table
        self._setup_table_headers()
        self._connect_signals()
        self.load_discrepancies()

    def _setup_table_headers(self) -> None:
        """Format discrepancy table widget dimensions and resize modes."""
        if not hasattr(self.dialog, "table_diff"):
            return
        table = self.dialog.table_diff
        header = table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
        table.setColumnWidth(0, 140)
        table.setColumnWidth(3, 170)

    def _connect_signals(self) -> None:
        """Connect buttons in historical_resolver.ui."""
        if hasattr(self.dialog, "btn_keep_excel"):
            self.dialog.btn_keep_excel.clicked.connect(self.dialog.reject)
        if hasattr(self.dialog, "btn_close"):
            self.dialog.btn_close.clicked.connect(self.dialog.reject)
        if hasattr(self.dialog, "btn_apply_all"):
            self.dialog.btn_apply_all.clicked.connect(self.apply_resolutions)

    # -------------------------------------------------------------------------
    # Data Extraction & Cross-Referencing
    # -------------------------------------------------------------------------

    def _get_historical_entries_for_oid(self, oid: str) -> Dict[str, List[Tuple[str, str]]]:
        """Collect all historical book values for the target specimen.
        
        Returns dict of field -> list of (value, book_name).
        """
        results: Dict[str, List[Tuple[str, str]]] = {}
        if not self.app.historical_dbs or not oid:
            return results

        oid_str = str(oid).strip()

        for db in self.app.historical_dbs:
            db_name = db.get("name", "Historical Book")
            dict_cache = db.get("dict_cache", {})

            # 1. Fast cache lookup
            oid_data = dict_cache.get(oid_str)
            if oid_data is None and oid_str.isdigit():
                oid_data = dict_cache.get(int(oid_str))

            if oid_data and isinstance(oid_data, dict):
                for fld, val_list in oid_data.items():
                    if isinstance(val_list, (list, tuple)):
                        for v in val_list:
                            results.setdefault(fld, []).append((str(v).strip(), db_name))
                    elif pd.notna(val_list):
                        results.setdefault(fld, []).append((str(val_list).strip(), db_name))
                continue

            # 2. Direct df_reg search in historical db entry
            df = db.get("df_reg")
            if df is not None and hasattr(df, "index"):
                target_idx = None
                if "ObjectID" in df.columns:
                    match_mask = df["ObjectID"].astype(str) == oid_str
                    if match_mask.any():
                        match_row = df[match_mask].iloc[0]
                        for c in df.columns:
                            if c != "ObjectID" and pd.notna(match_row[c]):
                                v_str = str(match_row[c]).strip()
                                if v_str and v_str.lower() != "nan":
                                    results.setdefault(c, []).append((v_str, db_name))
                elif oid_str in df.index or (oid_str.isdigit() and int(oid_str) in df.index):
                    target_idx = oid_str if oid_str in df.index else int(oid_str)
                    match_row = df.loc[target_idx]
                    if isinstance(match_row, pd.DataFrame):
                        match_row = match_row.iloc[0]
                    for c in match_row.index:
                        if pd.notna(match_row[c]):
                            v_str = str(match_row[c]).strip()
                            if v_str and v_str.lower() != "nan":
                                results.setdefault(c, []).append((v_str, db_name))

        return results

    def load_discrepancies(self) -> None:
        """Scan target specimen against historical books and populate table_diff."""
        if not hasattr(self.dialog, "table_diff"):
            return

        table = self.dialog.table_diff
        table.setRowCount(0)
        self.discrepancies.clear()

        oid = self.target_oid
        if hasattr(self.dialog, "lbl_object_info"):
            self.dialog.lbl_object_info.setText(
                f"Specimen #{oid}: Cross-referencing against {len(self.app.historical_dbs or [])} archival historical source(s)."
            )

        if not oid or self.app.df_reg is None or oid not in self.app.df_reg.index:
            return

        cur_row = self.app.df_reg.loc[oid]
        book_records = self._get_historical_entries_for_oid(oid)

        # Collect candidate fields: union of registry fields and historical fields
        all_fields = list(dict.fromkeys(list(self.app.df_reg.columns) + list(book_records.keys())))

        for field in all_fields:
            if field == "ObjectID":
                continue

            current_val = str(cur_row.get(field, "")).strip() if field in cur_row else ""
            if current_val.lower() == "nan":
                current_val = ""

            book_vals = book_records.get(field, [])
            if not book_vals:
                continue

            # Pick primary historical book entry
            hist_val, book_src = book_vals[0]

            # Register if there is a discrepancy or historical value exists
            is_discrepancy = current_val.lower() != hist_val.lower()

            discrepancy_entry = {
                "field": field,
                "current_val": current_val,
                "historical_val": hist_val,
                "book_src": book_src,
                "is_different": is_discrepancy,
            }
            self.discrepancies.append(discrepancy_entry)

        # Populate rows
        table.setUpdatesEnabled(False)
        table.setRowCount(len(self.discrepancies))

        for row_idx, disc in enumerate(self.discrepancies):
            field = disc["field"]
            cur_v = disc["current_val"]
            hist_v = disc["historical_val"]
            diff = disc["is_different"]

            # Column 0: Field Name
            item_field = QTableWidgetItem(field)
            item_field.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            if diff:
                item_field.setForeground(Qt.darkRed)
            table.setItem(row_idx, 0, item_field)

            # Column 1: Current Excel Value
            item_cur = QTableWidgetItem(cur_v or "—")
            item_cur.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            table.setItem(row_idx, 1, item_cur)

            # Column 2: Historical Book Value
            src_tag = f" ({disc['book_src']})" if disc.get("book_src") else ""
            item_hist = QTableWidgetItem(f"{hist_v}{src_tag}")
            item_hist.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            if diff:
                item_hist.setForeground(Qt.darkGreen)
            table.setItem(row_idx, 2, item_hist)

            # Column 3: Action Selector Combo
            combo = QComboBox()
            combo.addItem("Keep Current", "keep")
            combo.addItem("Accept Book Value", "accept")
            if diff:
                combo.setCurrentIndex(1)  # Default to accept if discrepancy
            table.setCellWidget(row_idx, 3, combo)

        table.setUpdatesEnabled(True)

    # -------------------------------------------------------------------------
    # Resolutions & Batch Commits
    # -------------------------------------------------------------------------

    def apply_resolutions(self) -> None:
        """Apply selected field resolutions to app_state.df_reg and audit log."""
        if not hasattr(self.dialog, "table_diff") or not self.target_oid:
            self.dialog.accept()
            return

        table = self.dialog.table_diff
        oid = self.target_oid
        applied_count = 0

        for row_idx, disc in enumerate(self.discrepancies):
            combo = table.cellWidget(row_idx, 3)
            if isinstance(combo, QComboBox) and combo.currentData() == "accept":
                field = disc["field"]
                hist_val = disc["historical_val"]

                # Find problem columns mapping to this field
                prob_cols_to_clear = [f"{field}_Problem"]
                if field == "Genus":
                    prob_cols_to_clear.append("Genus_Problem")
                elif field == "Species":
                    prob_cols_to_clear.append("Species_Problem")
                elif field == "Author":
                    prob_cols_to_clear.append("Author_Problem")
                elif field == "Family":
                    prob_cols_to_clear.append("Family_Problem")

                success = self.queue_ctrl.commit_field_change(
                    oid=oid,
                    field=field,
                    new_val=hist_val,
                    action_name="RESOLVE_HISTORICAL_CONFLICT",
                    prob_cols_to_clear=prob_cols_to_clear,
                )
                if success:
                    applied_count += 1

        if applied_count > 0:
            QMessageBox.information(
                self.dialog,
                "Discrepancies Resolved",
                f"Successfully updated {applied_count} field(s) on Specimen #{oid} using historical records.",
            )
            if self.on_resolved:
                self.on_resolved(oid)

        self.dialog.accept()

    def exec(self) -> int:
        """Launch modal dialog."""
        return self.dialog.exec()

    def show(self) -> None:
        """Show non-modal dialog."""
        self.dialog.show()

    def close(self) -> bool:
        """Close dialog."""
        return self.dialog.close()
