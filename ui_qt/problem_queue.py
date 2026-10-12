"""ui_qt/problem_queue.py - Problem Queue Resolver Dialog Controller for Arbor.

Wraps 'qt designer/problem_queue.ui' (ProblemQueueDialog).
Supports sequential queue navigation, schema-based target field resolution,
problem unflagging, atomic commits, undo recording, and audit logging.
"""
from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional

import pandas as pd
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QMessageBox, QWidget

from models import AppState
from ui_qt.base_queue import QtSpecimenQueueController
from ui_qt.loader import load_ui


class QtProblemQueueDialog(QDialog):
    """Controller for Problem Queue Resolver modal dialog."""

    def __init__(
        self,
        parent: Optional[QWidget] = None,
        app_state: Optional[AppState] = None,
        oid_queue: Optional[List[str]] = None,
        on_resolved: Optional[Callable[[str], None]] = None,
        on_inspect: Optional[Callable[[str], None]] = None,
    ):
        super().__init__(parent)
        self.app = app_state or AppState()
        self.on_resolved = on_resolved
        self.on_inspect = on_inspect

        # Load declarative Qt Designer UI
        self.dialog = load_ui("problem_queue.ui")
        if parent:
            self.dialog.setParent(parent, Qt.Dialog)

        # Detect or initialize problem queue
        queue = oid_queue
        if queue is None:
            queue = self._detect_problem_queue()

        self.queue_ctrl = QtSpecimenQueueController(
            app_state=self.app,
            oid_queue=queue,
            parent_widget=self.dialog,
        )

        # Map problems from config
        self.problem_defs = self._load_problem_definitions()

        # Connect signals & UI
        self._connect_signals()
        self.queue_ctrl.specimen_changed.connect(self._render_current_specimen)
        self.queue_ctrl.queue_completed.connect(self._on_queue_completed)

        # Initial render
        cur_oid = self.queue_ctrl.current_oid
        if cur_oid:
            self._render_current_specimen(cur_oid)
        else:
            self._render_empty_queue()

    def _detect_problem_queue(self) -> List[str]:
        """Collect all object IDs that have active problems in df_obs."""
        if self.app.df_obs is None or self.app.df_reg is None:
            return []

        prob_cols = [c for c in self.app.df_obs.columns if c.endswith("_Problem") or c == "Other_problem" or c == "Images_Missing"]
        if not prob_cols:
            return []

        with self.app.df_lock:
            # Check row-by-row or vectorized mask
            has_prob = self.app.df_obs[prob_cols].any(axis=1)
            oids = [
                str(oid)
                for oid in self.app.df_reg.index
                if oid in has_prob.index and has_prob.loc[oid]
            ]
        return oids

    def _load_problem_definitions(self) -> Dict[str, Dict[str, Any]]:
        """Load configured problem column metadata and target field mappings."""
        defs: Dict[str, Dict[str, Any]] = {}
        cfg = self.app.config or {}
        problems_list = cfg.get("ui_sections", {}).get("problems", []) or cfg.get("problems", [])

        for p in problems_list:
            col_name = p.get("name")
            if col_name:
                defs[col_name] = {
                    "maps_to": p.get("maps_to", col_name.replace("_Problem", "")),
                    "category": p.get("category", "General Issue"),
                    "description": p.get("description", f"Flagged issue for {col_name}"),
                }

        # Common fallbacks if not explicitly listed in config
        common = {
            "Genus_Problem": {"maps_to": "Genus", "category": "Taxonomy Issue", "description": "Spelling or validation issue in Genus."},
            "Species_Problem": {"maps_to": "Species", "category": "Taxonomy Issue", "description": "Spelling or validation issue in Species."},
            "Author_Problem": {"maps_to": "Author", "category": "Taxonomy Issue", "description": "Author designation or citation problem."},
            "Family_Problem": {"maps_to": "Family", "category": "Taxonomy Issue", "description": "Family classification conflict."},
            "Images_Missing": {"maps_to": "UID", "category": "Image Issue", "description": "Associated image file is missing or corrupted."},
            "Other_problem": {"maps_to": "Comment", "category": "Miscellaneous", "description": "General note or manual problem flag."},
        }
        for k, v in common.items():
            if k not in defs:
                defs[k] = v

        return defs

    def _connect_signals(self) -> None:
        """Wire UI buttons to controller methods."""
        if hasattr(self.dialog, "btn_prev"):
            self.dialog.btn_prev.clicked.connect(self.navigate_prev)
        if hasattr(self.dialog, "btn_next"):
            self.dialog.btn_next.clicked.connect(self.navigate_next)
        if hasattr(self.dialog, "btn_resolve"):
            self.dialog.btn_resolve.clicked.connect(self.resolve_current)
        if hasattr(self.dialog, "btn_jump_main"):
            self.dialog.btn_jump_main.clicked.connect(self.inspect_in_workspace)
        if hasattr(self.dialog, "btn_close"):
            self.dialog.btn_close.clicked.connect(self.dialog.close)

    # -------------------------------------------------------------------------
    # Rendering
    # -------------------------------------------------------------------------

    def _render_empty_queue(self) -> None:
        """Render UI state when queue is empty or all resolved."""
        if hasattr(self.dialog, "lbl_queue_pos"):
            self.dialog.lbl_queue_pos.setText("QUEUE EMPTY")
            self.dialog.lbl_queue_pos.setStyleSheet("background-color: #3a7d44; color: #ffffff; padding: 3px 6px; font-weight: bold;")

        if hasattr(self.dialog, "lbl_oid_title"):
            self.dialog.lbl_oid_title.setText("No Active Problems")

        if hasattr(self.dialog, "lbl_problem_category"):
            self.dialog.lbl_problem_category.setText("All Clear")
            self.dialog.lbl_problem_category.setStyleSheet("color: #3a7d44; font-weight: bold;")

        if hasattr(self.dialog, "lbl_issue_description"):
            self.dialog.lbl_issue_description.setText("No specimens with active problem flags remain in the queue.")

        if hasattr(self.dialog, "lbl_field_name"):
            self.dialog.lbl_field_name.setText("Status:")
        if hasattr(self.dialog, "input_fix_value"):
            self.dialog.input_fix_value.setText("Resolved")
            self.dialog.input_fix_value.setEnabled(False)

        if hasattr(self.dialog, "btn_prev"):
            self.dialog.btn_prev.setEnabled(False)
        if hasattr(self.dialog, "btn_next"):
            self.dialog.btn_next.setEnabled(False)
        if hasattr(self.dialog, "btn_resolve"):
            self.dialog.btn_resolve.setEnabled(False)

    def _render_current_specimen(self, oid: str) -> None:
        """Populate dialog widgets with data for the active specimen."""
        self.queue_ctrl.update_queue_badge(getattr(self.dialog, "lbl_queue_pos", None), prefix="PROBLEM")

        # Object title
        if hasattr(self.dialog, "lbl_oid_title"):
            self.dialog.lbl_oid_title.setText(f"Object #{oid}")

        # Find active problems on this specimen
        active_prob_cols: List[str] = []
        if self.app.df_obs is not None and oid in self.app.df_obs.index:
            row = self.app.df_obs.loc[oid]
            for col in row.index:
                if (col.endswith("_Problem") or col in ("Other_problem", "Images_Missing")) and bool(row.get(col)):
                    active_prob_cols.append(col)

        # Primary problem display
        primary_col = active_prob_cols[0] if active_prob_cols else "Other_problem"
        pdef = self.problem_defs.get(primary_col, {
            "maps_to": "Comment",
            "category": "Validation Issue",
            "description": f"Flagged issue on column {primary_col}",
        })

        if hasattr(self.dialog, "lbl_problem_category"):
            self.dialog.lbl_problem_category.setText(pdef["category"])
            self.dialog.lbl_problem_category.setStyleSheet("font-weight: bold; color: #c93a40; border: none;")

        if hasattr(self.dialog, "lbl_issue_description"):
            desc = pdef["description"]
            if len(active_prob_cols) > 1:
                desc += f" (Total issues on this record: {len(active_prob_cols)})"
            self.dialog.lbl_issue_description.setText(desc)

        # Input field
        target_field = pdef["maps_to"]
        if hasattr(self.dialog, "lbl_field_name"):
            self.dialog.lbl_field_name.setText(f"{target_field}:")

        current_val = ""
        if self.app.df_reg is not None and oid in self.app.df_reg.index and target_field in self.app.df_reg.columns:
            raw = self.app.df_reg.loc[oid, target_field]
            current_val = "" if pd.isna(raw) else str(raw)

        if hasattr(self.dialog, "input_fix_value"):
            self.dialog.input_fix_value.setEnabled(True)
            self.dialog.input_fix_value.setText(current_val)
            self.dialog.input_fix_value.setFocus()
            self.dialog.input_fix_value.selectAll()

        # Update button enable states
        if hasattr(self.dialog, "btn_prev"):
            self.dialog.btn_prev.setEnabled(self.queue_ctrl.can_prev)
        if hasattr(self.dialog, "btn_next"):
            self.dialog.btn_next.setEnabled(self.queue_ctrl.can_next)
        if hasattr(self.dialog, "btn_resolve"):
            self.dialog.btn_resolve.setEnabled(True)

    # -------------------------------------------------------------------------
    # Actions
    # -------------------------------------------------------------------------

    def navigate_next(self) -> None:
        """Advance queue."""
        self.queue_ctrl.navigate_next()

    def navigate_prev(self) -> None:
        """Step back in queue."""
        self.queue_ctrl.navigate_prev()

    def inspect_in_workspace(self) -> None:
        """Jump to the current specimen in the main workspace and close dialog."""
        oid = self.queue_ctrl.current_oid
        if oid and self.on_inspect:
            self.on_inspect(oid)
        self.dialog.accept()

    def resolve_current(self) -> None:
        """Apply correction, clear problem flag, commit audit, and advance queue."""
        oid = self.queue_ctrl.current_oid
        if not oid:
            return

        # Find active problem column
        active_prob_cols: List[str] = []
        if self.app.df_obs is not None and oid in self.app.df_obs.index:
            row = self.app.df_obs.loc[oid]
            for col in row.index:
                if (col.endswith("_Problem") or col in ("Other_problem", "Images_Missing")) and bool(row.get(col)):
                    active_prob_cols.append(col)

        primary_col = active_prob_cols[0] if active_prob_cols else "Other_problem"
        pdef = self.problem_defs.get(primary_col, {"maps_to": "Comment"})
        target_field = pdef["maps_to"]

        new_val = self.dialog.input_fix_value.text().strip() if hasattr(self.dialog, "input_fix_value") else ""

        # Commit via base queue controller
        success = self.queue_ctrl.commit_field_change(
            oid=oid,
            field=target_field,
            new_val=new_val,
            action_name="RESOLVE_PROBLEM",
            prob_cols_to_clear=[primary_col],
        )

        if success and self.on_resolved:
            self.on_resolved(oid)

        # Advance to next item
        if not self.queue_ctrl.navigate_next():
            self._on_queue_completed()

    def _on_queue_completed(self) -> None:
        """Invoked when the queue has completed navigation or has no remaining items."""
        QMessageBox.information(
            self.dialog,
            "Queue Completed",
            "All issues in the current problem queue have been reviewed.",
        )
        self._render_empty_queue()

    def exec(self) -> int:
        """Launch modal dialog."""
        return self.dialog.exec()

    def show(self) -> None:
        """Show non-modal dialog."""
        self.dialog.show()

    def close(self) -> bool:
        """Close dialog."""
        return self.dialog.close()
