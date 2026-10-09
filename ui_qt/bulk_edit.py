"""Controller for the Bulk Edit Dialog in Qt (wrapping bulk_edit.ui)."""
from __future__ import annotations

from datetime import datetime
import re
from typing import Callable, Optional

import pandas as pd
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHeaderView,
    QMessageBox,
    QTableWidgetItem,
    QWidget,
)

from models import AppState
import utils
from ui_qt.loader import load_ui


class QtBulkEditDialog:
    """Controller for find-and-replace batch manipulations across records."""

    def __init__(
        self,
        parent: Optional[QWidget] = None,
        app_state: Optional[AppState] = None,
        selected_oids: Optional[list[str]] = None,
        on_applied: Optional[Callable[[list[dict]], None]] = None,
    ):
        self.app = app_state or AppState()
        self.parent = parent
        self.selected_oids = selected_oids or (
            [self.app.current_object_id] if self.app.current_object_id else []
        )
        self.on_applied = on_applied
        self.win = load_ui("bulk_edit.ui", parent)

        self.last_diffs: list[dict] = []

        self._init_field_dropdown()
        self._setup_preview_table()
        self._wire_signals()

    def _init_field_dropdown(self) -> None:
        """Populate the combo_field with available schema columns."""
        if not hasattr(self.win, "combo_field"):
            return

        self.win.combo_field.clear()
        fields: list[str] = []

        # From app_state.config
        cfg = self.app.config or {}
        ui_sec = cfg.get("ui_sections", {})
        for sec in ("registration", "location", "problems"):
            for f in ui_sec.get(sec, []):
                fname = f.get("name")
                if fname and fname not in fields:
                    fields.append(fname)

        # From df_reg columns
        if self.app.df_reg is not None:
            for col in self.app.df_reg.columns:
                if col not in fields and col != "ObjectID":
                    fields.append(col)

        # From df_obs columns
        if self.app.df_obs is not None:
            for col in self.app.df_obs.columns:
                if col not in fields and col != "ObjectID":
                    fields.append(col)

        for f in fields:
            self.win.combo_field.addItem(f)

    def _setup_preview_table(self) -> None:
        """Configure preview table headers and sizing."""
        if hasattr(self.win, "table_preview"):
            tbl = self.win.table_preview
            tbl.setColumnCount(4)
            tbl.setHorizontalHeaderLabels(["Object ID", "Field", "Original Value", "New Value"])
            tbl.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
            tbl.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
            tbl.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
            tbl.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)

    def _wire_signals(self) -> None:
        """Connect button clicks and input changes to slots."""
        if hasattr(self.win, "btn_preview"):
            self.win.btn_preview.clicked.connect(self.preview_changes)

        if hasattr(self.win, "btn_apply"):
            self.win.btn_apply.clicked.connect(self.apply_changes)

        if hasattr(self.win, "btn_cancel"):
            self.win.btn_cancel.clicked.connect(self.win.reject)

        # Live preview update on find/replace input change
        if hasattr(self.win, "input_find"):
            self.win.input_find.textChanged.connect(lambda: self._set_status_dirty())
        if hasattr(self.win, "input_replace"):
            self.win.input_replace.textChanged.connect(lambda: self._set_status_dirty())

    def _set_status_dirty(self) -> None:
        """Update status label to prompt for preview."""
        if hasattr(self.win, "lbl_status"):
            self.win.lbl_status.setText("Parameters modified. Click 'Preview Diff' to inspect changes.")

    def get_target_oids(self) -> list[str]:
        """Determine target ObjectIDs according to scope radio buttons."""
        if hasattr(self.win, "radio_selected") and self.win.radio_selected.isChecked():
            if self.selected_oids:
                return [str(x) for x in self.selected_oids]
            elif self.app.current_object_id:
                return [str(self.app.current_object_id)]
            return [str(x) for x in self.app.active_object_ids]
        else:
            return [str(x) for x in self.app.active_object_ids]

    def _compute_replacement(self, val_str: str, find_text: str, replace_text: str, use_regex: bool, match_case: bool) -> tuple[bool, str]:
        """Determine if value matches and return (has_changed, new_value)."""
        if not find_text:
            # When find is empty, replace entire value with replacement text
            if replace_text != val_str:
                return True, replace_text
            return False, val_str

        if use_regex:
            flags = 0 if match_case else re.IGNORECASE
            try:
                if re.search(find_text, val_str, flags=flags):
                    new_val = re.sub(find_text, replace_text, val_str, flags=flags)
                    return (new_val != val_str), new_val
            except re.error as e:
                raise ValueError(f"Invalid Regular Expression: {e}")
            return False, val_str
        else:
            if not match_case:
                pattern = re.escape(find_text)
                if re.search(pattern, val_str, flags=re.IGNORECASE):
                    new_val = re.sub(pattern, lambda m: replace_text, val_str, flags=re.IGNORECASE)
                    return (new_val != val_str), new_val
            else:
                if find_text in val_str:
                    new_val = val_str.replace(find_text, replace_text)
                    return (new_val != val_str), new_val
            return False, val_str

    def preview_changes(self) -> list[dict]:
        """Dry-run find and replace, returning diffs and populating table_preview."""
        if not hasattr(self.win, "combo_field"):
            return []

        field = self.win.combo_field.currentText().strip()
        if not field:
            if hasattr(self.win, "lbl_status"):
                self.win.lbl_status.setText("Please select a target field.")
            return []

        find_text = self.win.input_find.text() if hasattr(self.win, "input_find") else ""
        replace_text = self.win.input_replace.text() if hasattr(self.win, "input_replace") else ""
        use_regex = self.win.chk_regex.isChecked() if hasattr(self.win, "chk_regex") else False
        match_case = self.win.chk_match_case.isChecked() if hasattr(self.win, "chk_match_case") else False

        target_oids = self.get_target_oids()
        diffs: list[dict] = []

        reg_df = self.app.df_reg
        obs_df = self.app.df_obs

        is_reg = reg_df is not None and field in reg_df.columns
        is_obs = obs_df is not None and field in obs_df.columns

        if not is_reg and not is_obs:
            if hasattr(self.win, "lbl_status"):
                self.win.lbl_status.setText(f"Field '{field}' not found in loaded database.")
            return []

        for oid in target_oids:
            orig_raw = None
            if is_reg and oid in reg_df.index:
                orig_raw = reg_df.at[oid, field]
            elif is_obs and oid in obs_df.index:
                orig_raw = obs_df.at[oid, field]

            orig_str = "" if pd.isna(orig_raw) else str(orig_raw)

            try:
                changed, new_str = self._compute_replacement(
                    orig_str, find_text, replace_text, use_regex, match_case
                )
            except ValueError as e:
                QMessageBox.critical(self.win, "Regex Error", str(e))
                return []

            if changed:
                diffs.append({
                    "oid": str(oid),
                    "field": field,
                    "old": orig_str,
                    "new": new_str,
                    "is_reg": is_reg,
                    "is_obs": is_obs,
                })

        self.last_diffs = diffs

        # Populate UI preview table
        if hasattr(self.win, "table_preview"):
            tbl = self.win.table_preview
            tbl.setRowCount(len(diffs))
            for row, d in enumerate(diffs):
                tbl.setItem(row, 0, QTableWidgetItem(d["oid"]))
                tbl.setItem(row, 1, QTableWidgetItem(d["field"]))
                tbl.setItem(row, 2, QTableWidgetItem(d["old"]))
                tbl.setItem(row, 3, QTableWidgetItem(d["new"]))

        if hasattr(self.win, "lbl_status"):
            count = len(diffs)
            scope_desc = "selected" if self.win.radio_selected.isChecked() else "filtered"
            self.win.lbl_status.setText(
                f"Found {count} matching record(s) across {len(target_oids)} {scope_desc} objects."
            )

        return diffs

    def apply_changes(self) -> None:
        """Commit bulk modifications to AppState dataframes and log table."""
        diffs = self.preview_changes()
        if not diffs:
            QMessageBox.information(
                self.win,
                "No Changes",
                "No records matched the find criteria in the selected scope.",
            )
            return

        reply = QMessageBox.question(
            self.win,
            "Confirm Bulk Edit",
            f"Are you sure you want to apply changes to {len(diffs)} record(s)?",
            QMessageBox.Yes | QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return

        reg_df = self.app.df_reg
        obs_df = self.app.df_obs
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        new_logs: list[dict] = []

        for d in diffs:
            oid = d["oid"]
            field = d["field"]
            new_val = d["new"]
            old_val = d["old"]

            # Snapshot undo stack
            reg_snap = reg_df.loc[oid].copy() if (reg_df is not None and oid in reg_df.index) else {}
            obs_snap = obs_df.loc[oid].copy() if (obs_df is not None and oid in obs_df.index) else {}
            self.app.undo_stacks.setdefault(oid, []).append({
                "reg": reg_snap,
                "obs": obs_snap,
            })

            # Commit to DataFrames
            if d["is_reg"] and reg_df is not None and oid in reg_df.index:
                reg_df.at[oid, field] = new_val
                if field == "Loaned out" and "Loaned out date" in reg_df.columns:
                    loaned_date = now_str if utils.parse_bool(new_val) else ""
                    reg_df.at[oid, "Loaned out date"] = loaned_date

            if d["is_obs"] and obs_df is not None and oid in obs_df.index:
                # Parse boolean if observation problem flag
                if field.endswith("_Problem") or field in ("Reviewed", "Images_Missing", "Images_Problem", "Images_Wrong"):
                    new_val_bool = utils.parse_bool(new_val)
                    obs_df.at[oid, field] = new_val_bool
                else:
                    obs_df.at[oid, field] = new_val

            # Create log entry
            log_entry = {
                "Timestamp": now_str,
                "ObjectID": oid,
                "Action": "BULK_EDIT",
                "ChangedFields": field,
                "ChangedValues": f"{old_val} -> {new_val}",
                "ProblemsChanged": "",
                "ProblemsChangedValues": "",
                "LocationChanged": "",
                "LocationChangedValues": "",
            }
            new_logs.append(log_entry)
            if hasattr(self.app, "_log_records"):
                self.app._log_records.append(log_entry)

        # Append to df_log
        if new_logs:
            df_new_logs = pd.DataFrame(new_logs)
            if self.app.df_log is not None and not self.app.df_log.empty:
                self.app.df_log = pd.concat([self.app.df_log, df_new_logs], ignore_index=True)
            else:
                self.app.df_log = df_new_logs

        self.app.dirty = True

        if self.on_applied:
            try:
                self.on_applied(diffs)
            except Exception:
                pass

        if hasattr(self.win, "lbl_status"):
            self.win.lbl_status.setText(f"Successfully updated {len(diffs)} record(s).")

        self.win.accept()

    def exec(self) -> int:
        """Display modal dialog and return exit code."""
        return self.win.exec()
