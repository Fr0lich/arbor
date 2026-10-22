"""Comprehensive unit & integration tests for Advanced Historical Search (PySide6)."""
from __future__ import annotations

import sys
import unittest
from unittest.mock import MagicMock, patch

import pandas as pd
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from backend.search import execute_advanced_historical_search
from models import AppState
from ui_qt.advanced_search import AdvancedSearchWorker, QtAdvancedSearchDialog
from ui_qt.main_window import QtMainWindow

app = QApplication.instance() or QApplication(sys.argv)


def _create_test_datasets():
    """Create test primary df_reg and historical_dbs with known discrepancies."""
    # Primary registry
    df_reg = pd.DataFrame(
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

    # Historical book 1
    # 101: Genus matches Quercus (same as reg)
    # 102: Species has discrepancy: "montana" vs current "sylvestris"
    # 103: Genus matches Abies (same as reg)
    # 105: Historical-only record: "Fagus", "grandifolia"
    hist_df1 = pd.DataFrame(
        {
            "Genus": ["Quercus", "Pinus", "Abies", "Fagus"],
            "Species": ["alba", "montana", "alba", "grandifolia"],
            "Author": ["L.", "L.", "Mill.", "Ehrh."],
            "Locality": ["Ridge Trail", "High Mountain", "North Ridge", "Forest Reserve"],
        },
        index=["101", "102", "103", "105"],
    )

    # Historical book 2
    # 103: Species discrepancy: "balsamea" vs current "alba"
    hist_df2 = pd.DataFrame(
        {
            "Genus": ["Abies"],
            "Species": ["balsamea"],
        },
        index=["103"],
    )

    historical_dbs = [
        {"name": "Archival Ledger 1910", "df_reg": hist_df1},
        {"name": "Field Notes 1925", "reg_by_id": hist_df2},
    ]

    return df_reg, historical_dbs


class TestBackendAdvancedSearch(unittest.TestCase):
    """Unit tests for backend.search.execute_advanced_historical_search."""

    def setUp(self):
        self.df_reg, self.historical_dbs = _create_test_datasets()

    def test_scope_current(self):
        """Current scope matches only primary registry df_reg."""
        # Query matching primary 101
        res = execute_advanced_historical_search(
            df_reg=self.df_reg,
            historical_dbs=self.historical_dbs,
            field_criteria={"Genus": "Quercus"},
            scope="current",
        )
        self.assertEqual(res, ["101"])

        # Query matching historical-only record 105 must return empty in current scope
        res_hist_only = execute_advanced_historical_search(
            df_reg=self.df_reg,
            historical_dbs=self.historical_dbs,
            field_criteria={"Genus": "Fagus"},
            scope="current",
        )
        self.assertEqual(res_hist_only, [])

        # Query matching historical discrepancy ("montana") returns empty in current scope
        res_discrepancy = execute_advanced_historical_search(
            df_reg=self.df_reg,
            historical_dbs=self.historical_dbs,
            field_criteria={"Species": "montana"},
            scope="current",
        )
        self.assertEqual(res_discrepancy, [])

    def test_scope_suggestions_only_discrepancies(self):
        """suggestions_only matches historical entries that differ from current registry values."""
        # Query "montana": 102 in historical has "montana", while df_reg has "sylvestris" -> Discrepancy!
        res_102 = execute_advanced_historical_search(
            df_reg=self.df_reg,
            historical_dbs=self.historical_dbs,
            field_criteria={"Species": "montana"},
            scope="suggestions_only",
        )
        self.assertIn("102", res_102)

        # Query "balsamea": 103 in historical book 2 has "balsamea", while df_reg has "alba" -> Discrepancy!
        res_103 = execute_advanced_historical_search(
            df_reg=self.df_reg,
            historical_dbs=self.historical_dbs,
            field_criteria={"Species": "balsamea"},
            scope="suggestions_only",
        )
        self.assertIn("103", res_103)

        # Query "alba": for 101, both historical and df_reg have "alba" (IDENTICAL, not discrepancy)
        # Therefore, 101 must NOT be matched under suggestions_only!
        res_alba = execute_advanced_historical_search(
            df_reg=self.df_reg,
            historical_dbs=self.historical_dbs,
            field_criteria={"Species": "alba"},
            scope="suggestions_only",
        )
        self.assertNotIn("101", res_alba)

    def test_scope_both(self):
        """Both scope returns matches from either primary or historical sources."""
        # "montana" is in historical book (for 102)
        res_both = execute_advanced_historical_search(
            df_reg=self.df_reg,
            historical_dbs=self.historical_dbs,
            field_criteria={"Species": "montana"},
            scope="both",
        )
        self.assertIn("102", res_both)

        # "sylvestris" is in current df_reg (for 102)
        res_curr = execute_advanced_historical_search(
            df_reg=self.df_reg,
            historical_dbs=self.historical_dbs,
            field_criteria={"Species": "sylvestris"},
            scope="both",
        )
        self.assertIn("102", res_curr)

        # "Fagus" is in historical-only (105)
        res_fagus = execute_advanced_historical_search(
            df_reg=self.df_reg,
            historical_dbs=self.historical_dbs,
            field_criteria={"Genus": "Fagus"},
            scope="both",
        )
        self.assertIn("105", res_fagus)

    def test_match_all_and_vs_or(self):
        """Test boolean combination of multi-field criteria."""
        # 101: Genus=Quercus, Collector=Smith
        # 103: Genus=Abies, Collector=Smith
        criteria = {"Genus": "Quercus", "Collector": "Smith"}

        # AND: only 101 matches both
        res_and = execute_advanced_historical_search(
            df_reg=self.df_reg,
            historical_dbs=self.historical_dbs,
            field_criteria=criteria,
            scope="current",
            match_all=True,
        )
        self.assertEqual(res_and, ["101"])

        # OR: both 101 (Quercus & Smith) and 103 (Smith) match
        res_or = execute_advanced_historical_search(
            df_reg=self.df_reg,
            historical_dbs=self.historical_dbs,
            field_criteria=criteria,
            scope="current",
            match_all=False,
        )
        self.assertIn("101", res_or)
        self.assertIn("103", res_or)
        self.assertEqual(len(res_or), 2)

    def test_empty_criteria_and_edge_cases(self):
        """Test graceful handling of empty queries and empty dataframes."""
        # Empty criteria returns all registry IDs
        all_ids = execute_advanced_historical_search(
            df_reg=self.df_reg,
            historical_dbs=self.historical_dbs,
            field_criteria={},
            scope="both",
        )
        self.assertEqual(all_ids, ["101", "102", "103", "104"])

        # None df_reg returns empty list
        none_res = execute_advanced_historical_search(
            df_reg=None,
            historical_dbs=self.historical_dbs,
            field_criteria={"Genus": "Quercus"},
        )
        self.assertEqual(none_res, [])

    def test_cancellation(self):
        """Search aborts immediately if is_cancelled returns True."""
        res = execute_advanced_historical_search(
            df_reg=self.df_reg,
            historical_dbs=self.historical_dbs,
            field_criteria={"Genus": "Quercus"},
            is_cancelled=lambda: True,
        )
        self.assertEqual(res, [])


class TestQtAdvancedSearchWorker(unittest.TestCase):
    """Unit tests for AdvancedSearchWorker background thread."""

    def setUp(self):
        self.df_reg, self.historical_dbs = _create_test_datasets()

    def test_worker_run_and_signals(self):
        """Worker executes and emits finished signal with matches."""
        worker = AdvancedSearchWorker(
            df_reg=self.df_reg,
            historical_dbs=self.historical_dbs,
            field_criteria={"Genus": "Quercus"},
            scope="current",
            match_all=True,
        )

        results_captured = []
        progress_captured = []

        worker.finished.connect(results_captured.append)
        worker.progress.connect(progress_captured.append)

        # Run synchronously for test determinism
        worker.run()

        self.assertEqual(results_captured, [["101"]])
        self.assertTrue(len(progress_captured) > 0)

    def test_worker_cancellation(self):
        """Worker cancellation stops emission of finished results."""
        worker = AdvancedSearchWorker(
            df_reg=self.df_reg,
            historical_dbs=self.historical_dbs,
            field_criteria={"Genus": "Quercus"},
            scope="current",
            match_all=True,
        )

        results_captured = []
        worker.finished.connect(results_captured.append)

        worker.cancel()
        worker.run()

        self.assertEqual(results_captured, [])


class TestQtAdvancedSearchDialog(unittest.TestCase):
    """Unit tests for QtAdvancedSearchDialog controller."""

    def setUp(self):
        self.df_reg, self.historical_dbs = _create_test_datasets()
        self.app_state = AppState()
        self.app_state.df_reg = self.df_reg
        self.app_state.historical_dbs = self.historical_dbs
        self.app_state.active_object_ids = list(self.df_reg.index)

        self.applied_results = []
        self.dialog = QtAdvancedSearchDialog(
            app_state=self.app_state,
            on_applied=self.applied_results.append,
        )

    def tearDown(self):
        self.dialog.close()

    def test_dialog_initialization(self):
        """Verify initial UI state and defaults."""
        self.assertTrue(hasattr(self.dialog.dialog, "edit_genus"))
        self.assertTrue(hasattr(self.dialog.dialog, "edit_species"))
        self.assertTrue(hasattr(self.dialog.dialog, "radio_scope_both"))
        self.assertTrue(hasattr(self.dialog.dialog, "radio_logic_and"))
        self.assertTrue(self.dialog.dialog.radio_scope_both.isChecked())
        self.assertTrue(self.dialog.dialog.radio_logic_and.isChecked())

    def test_criteria_and_scope_extraction(self):
        """Verify reading user inputs."""
        self.dialog.dialog.edit_genus.setText("Quercus")
        self.dialog.dialog.edit_species.setText("alba")
        self.dialog.dialog.radio_scope_current.setChecked(True)
        self.dialog.dialog.radio_logic_or.setChecked(True)

        self.assertEqual(
            self.dialog.get_criteria(),
            {"Genus": "Quercus", "Species": "alba"},
        )
        self.assertEqual(self.dialog.get_scope(), "current")
        self.assertFalse(self.dialog.get_match_all())

    def test_reset_form(self):
        """Reset button clears inputs and restores defaults."""
        self.dialog.dialog.edit_genus.setText("Quercus")
        self.dialog.dialog.radio_scope_current.setChecked(True)
        self.dialog.dialog.radio_logic_or.setChecked(True)

        self.dialog.reset_form()

        self.assertEqual(self.dialog.dialog.edit_genus.text(), "")
        self.assertTrue(self.dialog.dialog.radio_scope_both.isChecked())
        self.assertTrue(self.dialog.dialog.radio_logic_and.isChecked())

    def test_search_execution_and_callback(self):
        """Executing search populates matched_oids and triggers callback."""
        self.dialog.dialog.edit_genus.setText("Quercus")
        self.dialog.dialog.radio_scope_current.setChecked(True)

        # Trigger search
        self.dialog.start_search()
        # Wait for worker thread to finish
        if self.dialog.worker:
            self.dialog.worker.wait(3000)
        app.processEvents()

        self.assertEqual(self.dialog.matched_oids, ["101"])
        self.assertEqual(self.applied_results, [["101"]])


class TestQtMainWindowAdvancedSearchIntegration(unittest.TestCase):
    """Integration tests verifying MainWindow integration."""

    def setUp(self):
        self.df_reg, self.historical_dbs = _create_test_datasets()
        self.app_state = AppState()
        self.app_state.df_reg = self.df_reg
        self.app_state.df_obs = pd.DataFrame(index=self.df_reg.index)
        self.app_state.df_photo = pd.DataFrame(index=self.df_reg.index)
        self.app_state.historical_dbs = self.historical_dbs
        self.app_state.active_object_ids = list(self.df_reg.index)

        self.main_window = QtMainWindow(app_state=self.app_state)

    def tearDown(self):
        self.main_window.win.close()

    def test_btn_advanced_search_exists_and_wired(self):
        """btn_advanced_search exists in search bar layout."""
        self.assertTrue(hasattr(self.main_window.win, "btn_advanced_search"))

    def test_menu_data_has_advanced_search_action(self):
        """Data menu contains Advanced Historical Search action."""
        actions = [a.text() for a in self.main_window.menu_data.actions()]
        self.assertIn("Advanced Historical Search...", actions)

    def test_on_advanced_search_applied_updates_workspace(self):
        """Applying advanced search updates active_object_ids and filter indicators."""
        filtered_ids = ["101", "103"]
        self.main_window.on_advanced_search_applied(filtered_ids)

        # Verify app_state updated
        self.assertEqual(self.app_state.active_object_ids, ["101", "103"])

        # Verify filter indicator label
        if hasattr(self.main_window.win, "lbl_filter_status"):
            text = self.main_window.win.lbl_filter_status.text()
            self.assertIn("2 of 4", text)

        # Verify status bar badge
        if hasattr(self.main_window.win, "lbl_sb_filter_badge"):
            self.assertFalse(self.main_window.win.lbl_sb_filter_badge.isHidden())
            self.assertIn("SEARCH: 2/4", self.main_window.win.lbl_sb_filter_badge.text())


if __name__ == "__main__":
    unittest.main()
