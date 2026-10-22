"""ui_qt/advanced_search.py - Advanced Historical Search Dialog Controller & Background Worker.

Wraps 'qt designer/advanced_search.ui' (AdvancedSearchDialog).
Executes multi-field queries across primary specimen records (app_state.df_reg)
and attached historical archival ledger books (app_state.historical_dbs) via
a dedicated non-blocking QThread worker.
"""
from __future__ import annotations

from typing import Callable, Optional

from PySide6.QtCore import QObject, Qt, QThread, Signal
from PySide6.QtWidgets import QButtonGroup, QDialog, QWidget

from backend.search import execute_advanced_historical_search
from models import AppState
from ui_qt.loader import load_ui


class AdvancedSearchWorker(QThread):
    """Background worker executing advanced historical search without blocking the Qt event loop."""

    progress = Signal(int)
    finished = Signal(list)
    error = Signal(str)

    def __init__(
        self,
        df_reg,
        historical_dbs: list[dict] | None,
        field_criteria: dict[str, str],
        scope: str = "both",
        match_all: bool = True,
        parent: Optional[QObject] = None,
    ):
        super().__init__(parent)
        self.df_reg = df_reg
        self.historical_dbs = historical_dbs
        self.field_criteria = field_criteria
        self.scope = scope
        self.match_all = match_all
        self._is_cancelled = False

    def cancel(self) -> None:
        """Signal the worker to abort execution gracefully."""
        self._is_cancelled = True

    def run(self) -> None:
        try:
            results = execute_advanced_historical_search(
                df_reg=self.df_reg,
                historical_dbs=self.historical_dbs,
                field_criteria=self.field_criteria,
                scope=self.scope,
                match_all=self.match_all,
                is_cancelled=lambda: self._is_cancelled,
                progress_callback=self.progress.emit,
            )
            if not self._is_cancelled:
                self.finished.emit(results)
        except Exception as exc:
            if not self._is_cancelled:
                self.error.emit(str(exc))


class QtAdvancedSearchDialog(QDialog):
    """Controller for Advanced Historical Search dialog."""

    def __init__(
        self,
        parent: Optional[QWidget] = None,
        app_state: Optional[AppState] = None,
        on_applied: Optional[Callable[[list[str]], None]] = None,
    ):
        super().__init__(parent)
        self.app = app_state or AppState()
        self.on_applied = on_applied
        self.worker: Optional[AdvancedSearchWorker] = None
        self.matched_oids: list[str] = []

        # Load declarative Qt Designer UI
        self.dialog = load_ui("advanced_search.ui")
        if parent:
            self.dialog.setParent(parent, Qt.Dialog)

        self._wire_ui()

    def _wire_ui(self) -> None:
        """Connect buttons, shortcuts, and inputs to handlers."""
        # Isolate radio button groups so scope toggles do not conflict with logic toggles
        self.group_scope = QButtonGroup(self)
        self.group_scope.addButton(self.dialog.radio_scope_current)
        self.group_scope.addButton(self.dialog.radio_scope_suggestions)
        self.group_scope.addButton(self.dialog.radio_scope_both)

        self.group_logic = QButtonGroup(self)
        self.group_logic.addButton(self.dialog.radio_logic_and)
        self.group_logic.addButton(self.dialog.radio_logic_or)

        self.dialog.radio_scope_both.setChecked(True)
        self.dialog.radio_logic_and.setChecked(True)

        self.dialog.btn_search.clicked.connect(self.start_search)
        self.dialog.btn_reset.clicked.connect(self.reset_form)
        self.dialog.btn_close.clicked.connect(self.on_close_clicked)

        # Trigger search when user presses Enter/Return in any input field
        for edit in self._get_input_fields().values():
            edit.returnPressed.connect(self.start_search)

        # Initial visual states
        if hasattr(self.dialog, "progress_bar"):
            self.dialog.progress_bar.setVisible(False)
            self.dialog.progress_bar.setValue(0)

    def _get_input_fields(self) -> dict[str, QWidget]:
        """Map standard field names to their respective QLineEdit widgets."""
        return {
            "Genus": self.dialog.edit_genus,
            "Species": self.dialog.edit_species,
            "Author": self.dialog.edit_author,
            "Family": self.dialog.edit_family,
            "Collector": self.dialog.edit_collector,
            "Locality": self.dialog.edit_locality,
            "Year": self.dialog.edit_year,
        }

    def get_criteria(self) -> dict[str, str]:
        """Extract non-empty search criteria from input fields."""
        criteria: dict[str, str] = {}
        for field, widget in self._get_input_fields().items():
            text = widget.text().strip()
            if text:
                criteria[field] = text
        return criteria

    def get_scope(self) -> str:
        """Determine selected search scope mode."""
        if self.dialog.radio_scope_current.isChecked():
            return "current"
        if self.dialog.radio_scope_suggestions.isChecked():
            return "suggestions_only"
        return "both"

    def get_match_all(self) -> bool:
        """Return True for AND logic, False for OR logic."""
        return self.dialog.radio_logic_and.isChecked()

    def start_search(self) -> None:
        """Initiate background search query."""
        if self.worker and self.worker.isRunning():
            return

        criteria = self.get_criteria()
        scope = self.get_scope()
        match_all = self.get_match_all()

        # Update UI to running state
        self.dialog.btn_search.setEnabled(False)
        self.dialog.btn_search.setText("Searching...")
        if hasattr(self.dialog, "progress_bar"):
            self.dialog.progress_bar.setVisible(True)
            self.dialog.progress_bar.setValue(0)
        self.dialog.lbl_status.setText("Querying records and historical ledgers...")

        # Initialize background worker
        hist_dbs = getattr(self.app, "historical_dbs", None)
        self.worker = AdvancedSearchWorker(
            df_reg=self.app.df_reg,
            historical_dbs=hist_dbs,
            field_criteria=criteria,
            scope=scope,
            match_all=match_all,
            parent=self,
        )
        self.worker.progress.connect(self._on_search_progress)
        self.worker.finished.connect(self._on_search_finished)
        self.worker.error.connect(self._on_search_error)
        self.worker.start()

    def _on_search_progress(self, val: int) -> None:
        if hasattr(self.dialog, "progress_bar"):
            self.dialog.progress_bar.setValue(val)

    def _on_search_finished(self, matched_oids: list[str]) -> None:
        self.matched_oids = matched_oids
        self.dialog.btn_search.setEnabled(True)
        self.dialog.btn_search.setText("Search")
        if hasattr(self.dialog, "progress_bar"):
            self.dialog.progress_bar.setValue(100)

        match_count = len(matched_oids)
        status_msg = f"Search complete: {match_count} specimen(s) found."
        self.dialog.lbl_status.setText(status_msg)

        if self.on_applied:
            self.on_applied(matched_oids)

        self.dialog.accept()

    def _on_search_error(self, err_msg: str) -> None:
        self.dialog.btn_search.setEnabled(True)
        self.dialog.btn_search.setText("Search")
        self.dialog.lbl_status.setText(f"Error during search: {err_msg}")

    def reset_form(self) -> None:
        """Clear all inputs and reset toggles to defaults."""
        for widget in self._get_input_fields().values():
            widget.clear()

        self.dialog.radio_scope_both.setChecked(True)
        self.dialog.radio_logic_and.setChecked(True)

        if hasattr(self.dialog, "progress_bar"):
            self.dialog.progress_bar.setVisible(False)
            self.dialog.progress_bar.setValue(0)

        self.dialog.lbl_status.setText("Criteria reset. Enter search terms and click Search.")

    def on_close_clicked(self) -> None:
        """Cancel running worker and close dialog."""
        if self.worker and self.worker.isRunning():
            self.worker.cancel()
            self.worker.wait(500)
        self.dialog.reject()

    def exec(self) -> int:
        """Execute dialog modally."""
        return self.dialog.exec()

    def show(self) -> None:
        """Show dialog non-modally."""
        self.dialog.show()

    def close(self) -> bool:
        """Close dialog."""
        return self.dialog.close()
