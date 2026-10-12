"""ui_qt/base_queue.py - Reusable Multi-Specimen Queue Base Controller for Arbor.

Provides shared queue navigation (Previous, Next, Jump), boundary verification,
undo state recording, atomic field commit helpers, and audit logging for deep
resolvers (ProblemQueueDialog, HistoricalResolverDialog).
"""
from __future__ import annotations

import getpass
from datetime import datetime
from typing import Any, Callable, List, Optional

import pandas as pd
from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QLabel, QMessageBox, QWidget

from models import AppState


class QtSpecimenQueueController(QObject):
    """Base controller for multi-specimen resolution and queue navigation."""

    specimen_changed = Signal(str)  # Emitted with the new oid when queue index changes
    queue_completed = Signal()      # Emitted when reaching the end of queue

    def __init__(
        self,
        app_state: AppState,
        oid_queue: Optional[List[str]] = None,
        parent_widget: Optional[QWidget] = None,
    ):
        super().__init__()
        self.app = app_state
        self.parent_widget = parent_widget
        self._oid_queue: List[str] = [str(x).strip() for x in (oid_queue or []) if str(x).strip()]
        self._queue_idx: int = 0

    # -------------------------------------------------------------------------
    # Queue State & Properties
    # -------------------------------------------------------------------------

    @property
    def oid_queue(self) -> List[str]:
        return self._oid_queue

    @property
    def current_index(self) -> int:
        return self._queue_idx

    @property
    def total_count(self) -> int:
        return len(self._oid_queue)

    @property
    def current_oid(self) -> Optional[str]:
        if 0 <= self._queue_idx < len(self._oid_queue):
            return self._oid_queue[self._queue_idx]
        return None

    @property
    def can_prev(self) -> bool:
        return self._queue_idx > 0

    @property
    def can_next(self) -> bool:
        return self._queue_idx < len(self._oid_queue) - 1

    def set_queue(self, queue: List[str], target_oid: Optional[str] = None) -> None:
        """Update the active queue list and reset index."""
        self._oid_queue = [str(x).strip() for x in queue if str(x).strip()]
        if target_oid and target_oid in self._oid_queue:
            self._queue_idx = self._oid_queue.index(target_oid)
        else:
            self._queue_idx = 0

        current = self.current_oid
        if current:
            self.specimen_changed.emit(current)

    # -------------------------------------------------------------------------
    # Navigation
    # -------------------------------------------------------------------------

    def navigate_next(self) -> bool:
        """Advance to next specimen in queue."""
        if self.can_next:
            self._queue_idx += 1
            cur = self.current_oid
            if cur:
                self.specimen_changed.emit(cur)
            return True
        self.queue_completed.emit()
        return False

    def navigate_prev(self) -> bool:
        """Step back to previous specimen in queue."""
        if self.can_prev:
            self._queue_idx -= 1
            cur = self.current_oid
            if cur:
                self.specimen_changed.emit(cur)
            return True
        return False

    def navigate_to(self, index: int) -> bool:
        """Jump to specific index within the queue."""
        if 0 <= index < len(self._oid_queue):
            self._queue_idx = index
            cur = self.current_oid
            if cur:
                self.specimen_changed.emit(cur)
            return True
        return False

    def update_queue_badge(self, label: QLabel, prefix: str = "SPECIMEN") -> None:
        """Update queue progress badge label text (e.g. 'PROBLEM 3 OF 14')."""
        if not label:
            return
        total = self.total_count
        pos = self._queue_idx + 1 if total > 0 else 0
        label.setText(f"{prefix} {pos} OF {total}".upper())

    # -------------------------------------------------------------------------
    # State Mutation, Undo & Audit Logging
    # -------------------------------------------------------------------------

    def push_specimen_undo(self, oid: str) -> None:
        """Capture undo state snapshot for target specimen before edits."""
        if not oid or self.app.df_reg is None:
            return

        with self.app.df_lock:
            if oid not in self.app.df_reg.index:
                return

            reg_snapshot = dict(self.app.df_reg.loc[oid])
            obs_snapshot = dict(self.app.df_obs.loc[oid]) if self.app.df_obs is not None and oid in self.app.df_obs.index else {}

            entry = {
                "oid": oid,
                "timestamp": datetime.now().isoformat(),
                "df_reg": reg_snapshot,
                "df_obs": obs_snapshot,
            }

            if not isinstance(self.app.undo_stacks, dict):
                self.app.undo_stacks = {}
            self.app.undo_stacks.setdefault(oid, []).append(entry)

            if isinstance(self.app.redo_stacks, dict) and oid in self.app.redo_stacks:
                self.app.redo_stacks[oid].clear()

    def commit_field_change(
        self,
        oid: str,
        field: str,
        new_val: Any,
        action_name: str = "RESOLVE_FIELD",
        prob_cols_to_clear: Optional[List[str]] = None,
    ) -> bool:
        """Atomically mutate a field in df_reg, unflag problems in df_obs, and append audit log."""
        if not oid or self.app.df_reg is None or oid not in self.app.df_reg.index:
            return False

        old_val = self.app.df_reg.loc[oid, field] if field in self.app.df_reg.columns else ""
        if pd.isna(old_val):
            old_val = ""

        # Avoid redundant write if identical
        if str(old_val).strip() == str(new_val).strip():
            # Still unflag problem if requested
            if prob_cols_to_clear and self.app.df_obs is not None and oid in self.app.df_obs.index:
                with self.app.df_lock:
                    for pc in prob_cols_to_clear:
                        if pc in self.app.df_obs.columns:
                            self.app.df_obs.loc[oid, pc] = False
                    self.app.dirty = True
            return True

        # Push undo snapshot first
        self.push_specimen_undo(oid)

        with self.app.df_lock:
            # Update registry
            if field in self.app.df_reg.columns:
                self.app.df_reg.loc[oid, field] = new_val

            # Clear problem flags
            prob_changed_fields = []
            prob_changed_values = []
            if prob_cols_to_clear and self.app.df_obs is not None and oid in self.app.df_obs.index:
                for pc in prob_cols_to_clear:
                    if pc in self.app.df_obs.columns:
                        was_prob = bool(self.app.df_obs.loc[oid, pc])
                        if was_prob:
                            self.app.df_obs.loc[oid, pc] = False
                            prob_changed_fields.append(pc)
                            prob_changed_values.append(f'{pc}: "True" -> "False"')

            # Audit log entry
            now_iso = datetime.now().isoformat(timespec="seconds")
            user = getpass.getuser()

            log_entry = {
                "Timestamp": now_iso,
                "User": user,
                "Action": action_name,
                "ObjectID": oid,
                "Reviewed": "",
                "ChangedFields": field,
                "ChangedValues": f'{field}: "{old_val}" -> "{new_val}"',
                "ProblemsChanged": "; ".join(prob_changed_fields),
                "ProblemsChangedValues": "; ".join(prob_changed_values),
                "LocationChanged": "",
                "LocationChangedValues": "",
            }

            if self.app.df_log is not None:
                self.app.df_log = pd.concat(
                    [self.app.df_log, pd.DataFrame([log_entry])],
                    ignore_index=True,
                )

            self.app.dirty = True

        return True
