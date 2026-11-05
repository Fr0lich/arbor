"""Comprehensive unit & integration tests for Tkinter Advanced Historical Search."""
from __future__ import annotations

import time
import tkinter as tk
import unittest
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from models import AppState
from ui.advanced_search import AdvancedSearchDialog


def _create_test_state():
    """Create mock AppState with test primary and historical datasets."""
    state = AppState()
    state.df_reg = pd.DataFrame(
        {
            "Genus": ["Quercus", "Pinus", "Abies", "Betula"],
            "Species": ["alba", "sylvestris", "alba", "pendula"],
            "Author": ["L.", "L.", "Mill.", "Roth"],
            "Family": ["Fagaceae", "Pinaceae", "Pinaceae", "Betulaceae"],
            "Collector": ["Smith", "Jones", "Smith", "Taylor"],
            "Locality": ["Ridge Trail", "Valley", "North Ridge", "Lake Shore"],
            "Year": ["1920", "1935", "1940", "1955"],
        },
        index=["101", "102", "103", "104"],
    )

    hist_df = pd.DataFrame(
        {
            "Genus": ["Quercus", "Pinus", "Abies"],
            "Species": ["alba", "montana", "balsamea"],  # Discrepancies for 102 & 103
        },
        index=["101", "102", "103"],
    )

    state.historical_dbs = [
        {"name": "Archival Catalog", "df_reg": hist_df}
    ]
    state.active_object_ids = list(state.df_reg.index)
    return state


class TestTkinterAdvancedSearchDialog(unittest.TestCase):
    """Unit tests for AdvancedSearchDialog in Tkinter."""

    @classmethod
    def setUpClass(cls):
        try:
            cls.root = tk.Tk()
            cls.root.withdraw()
        except Exception as exc:
            raise unittest.SkipTest(f"Tkinter display unavailable: {exc}")

    @classmethod
    def tearDownClass(cls):
        try:
            cls.root.destroy()
        except Exception:
            pass

    def setUp(self):
        self.state = _create_test_state()
        self.applied_results = []
        self.dialog = AdvancedSearchDialog(
            parent=self.root,
            app_state=self.state,
            on_applied=self.applied_results.append,
        )

    def tearDown(self):
        if self.dialog.winfo_exists():
            self.dialog.destroy()

    def test_dialog_initialization_and_widgets(self):
        """Verify presence of all required input fields and controls."""
        self.assertTrue(hasattr(self.dialog, "entry_genus"))
        self.assertTrue(hasattr(self.dialog, "entry_species"))
        self.assertTrue(hasattr(self.dialog, "entry_author"))
        self.assertTrue(hasattr(self.dialog, "entry_family"))
        self.assertTrue(hasattr(self.dialog, "entry_collector"))
        self.assertTrue(hasattr(self.dialog, "entry_locality"))
        self.assertTrue(hasattr(self.dialog, "entry_year"))

        self.assertEqual(self.dialog.var_scope.get(), "both")
        self.assertTrue(self.dialog.var_logic.get())

    def test_criteria_and_scope_extraction(self):
        """Verify criteria extraction from input fields."""
        self.dialog.entry_genus.insert(0, "Quercus")
        self.dialog.entry_species.insert(0, "alba")
        self.dialog.var_scope.set("current")
        self.dialog.var_logic.set(False)

        criteria = self.dialog.get_criteria()
        self.assertEqual(criteria, {"Genus": "Quercus", "Species": "alba"})
        self.assertEqual(self.dialog.get_scope(), "current")
        self.assertFalse(self.dialog.get_match_all())

    def test_reset_form(self):
        """Verify reset button clears text inputs and restores defaults."""
        self.dialog.entry_genus.insert(0, "Quercus")
        self.dialog.var_scope.set("current")
        self.dialog.var_logic.set(False)

        self.dialog.reset_form()

        self.assertEqual(self.dialog.entry_genus.get(), "")
        self.assertEqual(self.dialog.var_scope.get(), "both")
        self.assertTrue(self.dialog.var_logic.get())

    def test_search_execution_background_thread(self):
        """Verify search runs in background thread and triggers on_applied callback."""
        self.dialog.entry_genus.insert(0, "Quercus")
        self.dialog.var_scope.set("current")

        self.dialog.start_search()

        # Wait for thread to finish and process Tkinter events
        max_wait = 3.0
        start = time.time()
        while time.time() - start < max_wait:
            self.dialog._poll_queue()
            self.root.update_idletasks()
            self.root.update()
            if self.applied_results:
                break
            time.sleep(0.05)

        self.assertEqual(self.applied_results, [["101"]])
        self.assertEqual(self.dialog.matched_oids, ["101"])

    def test_discrepancy_search_in_dialog(self):
        """Verify historical discrepancy search correctly isolates 102."""
        self.dialog.entry_species.insert(0, "montana")
        self.dialog.var_scope.set("suggestions_only")

        self.dialog.start_search()

        max_wait = 3.0
        start = time.time()
        while time.time() - start < max_wait:
            self.dialog._poll_queue()
            self.root.update_idletasks()
            self.root.update()
            if self.applied_results:
                break
            time.sleep(0.05)

        self.assertEqual(self.applied_results, [["102"]])


class TestTkinterMainWindowIntegration(unittest.TestCase):
    """Integration test verifying Tkinter MainWindow handlers and callbacks."""

    @classmethod
    def setUpClass(cls):
        try:
            cls.root = tk.Tk()
            cls.root.withdraw()
        except Exception as exc:
            raise unittest.SkipTest(f"Tkinter display unavailable: {exc}")

    @classmethod
    def tearDownClass(cls):
        try:
            cls.root.destroy()
        except Exception:
            pass

    def test_on_advanced_search_applied(self):
        """Verify on_advanced_search_applied updates state and status display."""
        # Lightweight dummy simulating MainWindow
        class DummyUI:
            def __init__(self, root, state):
                self.root = root
                self.app = state
                self._list_dirty = False
                self.refreshed = False
                self.filter_status_label = tk.Label(root, text="")
                self.filter_button = tk.Button(root, text="Filter")

            def refresh_list(self):
                self.refreshed = True

            def update_filter_button_text(self):
                pass

        state = _create_test_state()
        ui = DummyUI(self.root, state)

        # Import handler logic as bound in ObjectProgramUI
        from ui.main_window import ObjectProgramUI
        ObjectProgramUI.on_advanced_search_applied(ui, ["101", "103"])

        self.assertEqual(state.active_object_ids, ["101", "103"])
        self.assertTrue(ui._list_dirty)
        self.assertTrue(ui.refreshed)
        self.assertIn("2 of 4", ui.filter_status_label.cget("text"))


if __name__ == "__main__":
    unittest.main()
