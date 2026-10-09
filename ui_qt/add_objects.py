"""Controller for the Add Objects Dialog in Qt (wrapping add_objects.ui)."""
from __future__ import annotations

from datetime import datetime
import re
from typing import Callable, Optional

import pandas as pd
from PySide6.QtWidgets import (
    QMessageBox,
    QWidget,
)

from models import AppState
from repository import REVIEWED_COLUMN
from ui_qt.loader import load_ui


class QtAddObjectsDialog:
    """Controller for generating and creating single or sequential specimen records."""

    def __init__(
        self,
        parent: Optional[QWidget] = None,
        app_state: Optional[AppState] = None,
        on_created: Optional[Callable[[list[str]], None]] = None,
    ):
        self.app = app_state or AppState()
        self.parent = parent
        self.on_created = on_created
        self.win = load_ui("add_objects.ui", parent)

        self._init_defaults()
        self._wire_signals()

    def _init_defaults(self) -> None:
        """Calculate next available sequential ID and set initial inputs."""
        reg_df = self.app.df_reg

        # Find next numerical ID
        if reg_df is not None and not reg_df.empty:
            numeric_ids = [int(x) for x in reg_df.index if str(x).isdigit()]
            next_num = max(numeric_ids) + 1 if numeric_ids else 1001
        else:
            next_num = 1001

        if hasattr(self.win, "input_start_id"):
            self.win.input_start_id.setText(str(next_num))

        if hasattr(self.win, "spin_count"):
            self.win.spin_count.setValue(1)

        # Pre-fill defaults from current object if available
        if hasattr(self.win, "chk_duplicate_current"):
            self.win.chk_duplicate_current.toggled.connect(self._on_duplicate_toggled)

    def _on_duplicate_toggled(self, checked: bool) -> None:
        """Fill or clear default values based on current object metadata."""
        if not checked:
            return

        cid = self.app.current_object_id
        reg_df = self.app.df_reg
        if not cid or reg_df is None or cid not in reg_df.index:
            return

        row = reg_df.loc[cid]

        def _val(col: str) -> str:
            v = row.get(col, "")
            return "" if pd.isna(v) else str(v).strip()

        if hasattr(self.win, "input_def_genus"):
            self.win.input_def_genus.setText(_val("Genus"))
        if hasattr(self.win, "input_def_species"):
            self.win.input_def_species.setText(_val("Species"))
        if hasattr(self.win, "input_def_collector"):
            self.win.input_def_collector.setText(_val("Collector"))
        if hasattr(self.win, "input_def_collection"):
            self.win.input_def_collection.setText(_val("Collection"))
        if hasattr(self.win, "input_def_location"):
            self.win.input_def_location.setText(_val("Building") or _val("Location"))

    def _wire_signals(self) -> None:
        """Connect button events and input changes."""
        if hasattr(self.win, "btn_create"):
            self.win.btn_create.clicked.connect(self.create_objects)

        if hasattr(self.win, "btn_cancel"):
            self.win.btn_cancel.clicked.connect(self.win.reject)

    def generate_object_ids(self) -> list[str]:
        """Generate list of new ObjectIDs based on prefix, start, count, and suffix."""
        prefix = self.win.input_prefix.text().strip() if hasattr(self.win, "input_prefix") else ""
        start_raw = self.win.input_start_id.text().strip() if hasattr(self.win, "input_start_id") else ""
        count = self.win.spin_count.value() if hasattr(self.win, "spin_count") else 1
        suffix = self.win.input_suffix.text().strip() if hasattr(self.win, "input_suffix") else ""

        if not start_raw:
            reg_df = self.app.df_reg
            numeric_ids = [int(x) for x in reg_df.index if str(x).isdigit()] if (reg_df is not None and not reg_df.empty) else []
            start_num = max(numeric_ids) + 1 if numeric_ids else 1001
        elif start_raw.isdigit():
            start_num = int(start_raw)
        else:
            # Extract numbers from start_raw if it contains prefix/suffix
            m = re.match(r"^([A-Za-z_\-\s]*?)(\d+)([A-Za-z_\-\s]*)$", start_raw)
            if m:
                extracted_prefix, num_str, extracted_suffix = m.groups()
                if not prefix:
                    prefix = extracted_prefix
                if not suffix:
                    suffix = extracted_suffix
                start_num = int(num_str)
            else:
                # Fallback: if not parseable into sequential number, only single object ID allowed
                if count > 1:
                    raise ValueError(
                        f"Non-numeric Starting ID '{start_raw}' cannot be incremented. "
                        "Please provide a numeric start value or set Number of Objects to 1."
                    )
                return [f"{prefix}{start_raw}{suffix}"]

        # Format number with padding if original start_raw had leading zeros
        pad_len = 0
        if start_raw.isdigit() and start_raw.startswith("0") and len(start_raw) > 1:
            pad_len = len(start_raw)

        new_ids: list[str] = []
        for i in range(count):
            num = start_num + i
            num_formatted = f"{num:0{pad_len}d}" if pad_len > 0 else str(num)
            new_ids.append(f"{prefix}{num_formatted}{suffix}")

        return new_ids

    def validate_ids(self, ids: list[str]) -> list[str]:
        """Check for existing duplicate IDs in df_reg. Return list of duplicates."""
        reg_df = self.app.df_reg
        if reg_df is None or reg_df.empty:
            return []

        existing_index = set(str(x) for x in reg_df.index)
        duplicates = [oid for oid in ids if oid in existing_index]
        return duplicates

    def create_objects(self) -> None:
        """Validate inputs and batch insert new records into AppState."""
        if self.app.df_reg is None:
            QMessageBox.warning(self.win, "No Database", "Please open or create a database first.")
            return

        try:
            new_ids = self.generate_object_ids()
        except ValueError as e:
            QMessageBox.critical(self.win, "Invalid ID Range", str(e))
            return

        if not new_ids:
            QMessageBox.warning(self.win, "No IDs", "No object IDs generated.")
            return

        duplicates = self.validate_ids(new_ids)
        if duplicates:
            dup_summary = ", ".join(duplicates[:6])
            if len(duplicates) > 6:
                dup_summary += f" ... (+{len(duplicates) - 6} more)"
            QMessageBox.critical(
                self.win,
                "Duplicate Object IDs",
                f"The following Object ID(s) already exist in the database:\n{dup_summary}\n\n"
                "Please choose a different starting number or prefix.",
            )
            return

        reg_df = self.app.df_reg
        obs_df = self.app.df_obs

        # Read default values from UI
        defaults: dict[str, str] = {}
        if hasattr(self.win, "input_def_genus") and self.win.input_def_genus.text().strip():
            defaults["Genus"] = self.win.input_def_genus.text().strip()
        if hasattr(self.win, "input_def_species") and self.win.input_def_species.text().strip():
            defaults["Species"] = self.win.input_def_species.text().strip()
        if hasattr(self.win, "input_def_collector") and self.win.input_def_collector.text().strip():
            defaults["Collector"] = self.win.input_def_collector.text().strip()
        if hasattr(self.win, "input_def_collection") and self.win.input_def_collection.text().strip():
            defaults["Collection"] = self.win.input_def_collection.text().strip()
        if hasattr(self.win, "input_def_location") and self.win.input_def_location.text().strip():
            loc_val = self.win.input_def_location.text().strip()
            if "Building" in reg_df.columns:
                defaults["Building"] = loc_val
            elif "Location" in reg_df.columns:
                defaults["Location"] = loc_val

        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        new_logs: list[dict] = []

        # Batch insert rows
        for oid in new_ids:
            # Insert into df_reg
            reg_row = {col: pd.NA for col in reg_df.columns}
            for k, v in defaults.items():
                if k in reg_row:
                    reg_row[k] = v
            reg_df.loc[oid] = reg_row

            # Insert into df_obs
            if obs_df is not None:
                obs_row = {col: pd.NA for col in obs_df.columns}
                if REVIEWED_COLUMN in obs_row:
                    obs_row[REVIEWED_COLUMN] = False
                for col in obs_df.columns:
                    if col.endswith("_Problem") or col in ("Images_Missing", "Images_Problem", "Images_Wrong"):
                        obs_row[col] = False
                obs_df.loc[oid] = obs_row

            # Append to active_object_ids
            self.app.active_object_ids.append(oid)

            # Audit log entry
            log_entry = {
                "Timestamp": now_str,
                "ObjectID": oid,
                "Action": "CREATE",
                "ChangedFields": "New Object",
                "ChangedValues": ", ".join(f"{k}={v}" for k, v in defaults.items()) if defaults else "Blank Record",
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
        self.app.current_object_id = new_ids[0]

        if self.on_created:
            try:
                self.on_created(new_ids)
            except Exception:
                pass

        self.win.accept()

    def exec(self) -> int:
        """Display modal dialog and return exit code."""
        return self.win.exec()
