"""Comprehensive unit tests for Phase 5 PySide6 High-Complexity Workspaces & Resolvers."""
from __future__ import annotations

import os
import sys
import unittest
from unittest.mock import MagicMock, patch

import pandas as pd
from PySide6.QtCore import QPoint, Qt
from PySide6.QtWidgets import QApplication

import config
from models import AppState
from repository import REVIEWED_COLUMN
from ui_qt.base_queue import QtSpecimenQueueController
from ui_qt.gbif_review import GbifBatchReconciliationWorker, QtGbifReviewDialog
from ui_qt.historical_resolver import QtHistoricalResolverDialog
from ui_qt.main_window import QtMainWindow
from ui_qt.new_database_wizard import QtNewDatabaseWizard
from ui_qt.problem_queue import QtProblemQueueDialog

app = QApplication.instance() or QApplication(sys.argv)


def _create_mock_app_state() -> AppState:
    """Create populated AppState instance for Phase 5 tests."""
    state = AppState()
    state.config = {
        "ui_sections": {
            "registration": [
                {"name": "Genus", "type": "text"},
                {"name": "Species", "type": "text"},
                {"name": "Author", "type": "text"},
                {"name": "Family", "type": "text"},
                {"name": "TaxonID", "type": "text"},
                {"name": "Comment", "type": "text"},
            ],
            "location": [
                {"name": "Building", "type": "text"},
                {"name": "Floor", "type": "choice"},
                {"name": "Cabinet", "type": "text"},
                {"name": "Drawer", "type": "text"},
            ],
            "problems": [
                {"name": "Genus_Problem", "type": "bool", "category": "taxonomy", "maps_to": "Genus"},
                {"name": "Species_Problem", "type": "bool", "category": "taxonomy", "maps_to": "Species"},
                {"name": "Author_Problem", "type": "bool", "category": "taxonomy", "maps_to": "Author"},
                {"name": "Family_Problem", "type": "bool", "category": "taxonomy", "maps_to": "Family"},
                {"name": "Other_problem", "type": "bool", "category": "notes", "maps_to": "Comment"},
            ],
        }
    }
    state.config_name = "Default (NHMO Vascular Plants)"
    state.excel_path = "mock_db.xlsx"
    state.output_path = "mock_db.xlsx"

    records = {
        "1001": {
            "Genus": "Pinus",
            "Species": "sylvestris",
            "Author": "L.",
            "Family": "Pinaceae",
            "TaxonID": "5285637",
            "Comment": "Historical collection",
        },
        "1002": {
            "Genus": "Betula",
            "Species": "pendula",
            "Author": "Roth",
            "Family": "Betulaceae",
            "TaxonID": "5331916",
            "Comment": "",
        },
        "1003": {
            "Genus": "Abies",
            "Species": "alba",
            "Author": "Mill.",
            "Family": "Pinaceae",
            "TaxonID": "2685484",
            "Comment": "Specimen in good condition",
        },
    }
    state.df_reg = pd.DataFrame.from_dict(records, orient="index")
    state.df_reg.index.name = "ObjectID"

    obs = {
        "1001": {
            REVIEWED_COLUMN: False,
            "Genus_Problem": False,
            "Species_Problem": False,
            "Author_Problem": True,
            "Family_Problem": False,
            "Other_problem": False,
        },
        "1002": {
            REVIEWED_COLUMN: True,
            "Genus_Problem": False,
            "Species_Problem": False,
            "Author_Problem": False,
            "Family_Problem": False,
            "Other_problem": True,
        },
        "1003": {
            REVIEWED_COLUMN: False,
            "Genus_Problem": True,
            "Species_Problem": False,
            "Author_Problem": False,
            "Family_Problem": False,
            "Other_problem": False,
        },
    }
    state.df_obs = pd.DataFrame.from_dict(obs, orient="index")
    state.df_obs.index.name = "ObjectID"

    state.df_log = pd.DataFrame(columns=[
        "Timestamp", "User", "Action", "ObjectID", "Reviewed", "ChangedFields", "ChangedValues",
        "ProblemsChanged", "ProblemsChangedValues", "LocationChanged", "LocationChangedValues"
    ])
    state.active_object_ids = ["1001", "1002", "1003"]
    state.current_object_id = "1001"
    state.dirty = False
    state.undo_stacks = {}
    state.redo_stacks = {}

    # Mock historical database books
    book_df = pd.DataFrame({
        "ObjectID": ["1001", "1003"],
        "Genus": ["Pinus", "Abies"],
        "Species": ["sylvestris", "pectinata"],  # Discrepancy for 1003: alba vs pectinata
        "Author": ["Linnaeus", "Lam."],
    })
    state.historical_dbs = [
        {"name": "Archival Catalog 1904", "df_reg": book_df}
    ]

    return state


class TestQtSpecimenQueueController(unittest.TestCase):
    """Unit tests for the base queue controller engine."""

    def setUp(self):
        self.app_state = _create_mock_app_state()
        self.ctrl = QtSpecimenQueueController(
            app_state=self.app_state,
            oid_queue=["1001", "1002", "1003"],
        )

    def test_queue_initialization_and_boundaries(self):
        """Test initial state and navigation bounds."""
        self.assertEqual(self.ctrl.current_index, 0)
        self.assertEqual(self.ctrl.current_oid, "1001")
        self.assertFalse(self.ctrl.can_prev)
        self.assertTrue(self.ctrl.can_next)
        self.assertEqual(self.ctrl.total_count, 3)

    def test_navigation_forward_and_backward(self):
        """Test forward and backward stepping in queue."""
        # Next -> 1002
        self.assertTrue(self.ctrl.navigate_next())
        self.assertEqual(self.ctrl.current_oid, "1002")
        self.assertTrue(self.ctrl.can_prev)
        self.assertTrue(self.ctrl.can_next)

        # Next -> 1003
        self.assertTrue(self.ctrl.navigate_next())
        self.assertEqual(self.ctrl.current_oid, "1003")
        self.assertFalse(self.ctrl.can_next)

        # Prev -> 1002
        self.assertTrue(self.ctrl.navigate_prev())
        self.assertEqual(self.ctrl.current_oid, "1002")

    def test_commit_field_change_and_undo(self):
        """Test atomic field modification, undo snapshot creation, and audit logging."""
        committed = self.ctrl.commit_field_change(
            oid="1001",
            field="Author",
            new_val="Linnaeus, 1753",
            action_name="TEST_RESOLVE",
            prob_cols_to_clear=["Author_Problem"],
        )
        self.assertTrue(committed)

        # Verify df_reg mutation
        self.assertEqual(self.app_state.df_reg.loc["1001", "Author"], "Linnaeus, 1753")

        # Verify df_obs unflagged
        self.assertFalse(self.app_state.df_obs.loc["1001", "Author_Problem"])

        # Verify undo snapshot pushed
        self.assertIn("1001", self.app_state.undo_stacks)
        self.assertEqual(len(self.app_state.undo_stacks["1001"]), 1)
        self.assertEqual(self.app_state.undo_stacks["1001"][0]["df_reg"]["Author"], "L.")

        # Verify audit log appended
        self.assertTrue(any(self.app_state.df_log["Action"] == "TEST_RESOLVE"))
        self.assertTrue(self.app_state.dirty)


class TestQtProblemQueueDialog(unittest.TestCase):
    """Unit tests for ProblemQueueDialog controller."""

    def setUp(self):
        self.app_state = _create_mock_app_state()
        self.dialog = QtProblemQueueDialog(
            app_state=self.app_state,
        )

    def test_auto_detection_of_problem_records(self):
        """Verify queue auto-detects 1001 (Author_Problem), 1002 (Other_problem), 1003 (Genus_Problem)."""
        self.assertEqual(self.dialog.queue_ctrl.oid_queue, ["1001", "1002", "1003"])
        self.assertEqual(self.dialog.queue_ctrl.current_oid, "1001")

        # Position label
        self.assertIn("PROBLEM 1 OF 3", self.dialog.dialog.lbl_queue_pos.text())

    def test_target_field_binding(self):
        """Verify target field input populated with current value."""
        # 1001 has Author_Problem -> maps to Author ("L.")
        self.assertEqual(self.dialog.dialog.lbl_field_name.text(), "Author:")
        self.assertEqual(self.dialog.dialog.input_fix_value.text(), "L.")

    def test_resolve_current_and_queue_advance(self):
        """Verify resolving unflags problem and steps to next specimen."""
        resolved_callbacks = []
        self.dialog.on_resolved = lambda oid: resolved_callbacks.append(oid)

        self.dialog.dialog.input_fix_value.setText("L.")  # Keep or refine
        self.dialog.resolve_current()

        self.assertEqual(resolved_callbacks, ["1001"])
        # Advanced to next problem: 1002 (Other_problem -> maps to Comment)
        self.assertEqual(self.dialog.queue_ctrl.current_oid, "1002")
        self.assertEqual(self.dialog.dialog.lbl_field_name.text(), "Comment:")


class TestQtHistoricalResolverDialog(unittest.TestCase):
    """Unit tests for HistoricalResolverDialog controller."""

    def setUp(self):
        self.app_state = _create_mock_app_state()
        # Test on specimen 1003 which has Species="alba", while book has Species="pectinata"
        self.dialog = QtHistoricalResolverDialog(
            app_state=self.app_state,
            oid="1003",
        )

    def test_discrepancy_table_population(self):
        """Verify discrepancy detection for specimen 1003."""
        table = self.dialog.dialog.table_diff
        self.assertGreater(table.rowCount(), 0)

        # Species row discrepancy
        species_entry = next((d for d in self.dialog.discrepancies if d["field"] == "Species"), None)
        self.assertIsNotNone(species_entry)
        self.assertEqual(species_entry["current_val"], "alba")
        self.assertEqual(species_entry["historical_val"], "pectinata")
        self.assertTrue(species_entry["is_different"])

    @patch("PySide6.QtWidgets.QMessageBox.information")
    def test_apply_resolutions_commits_historical_value(self, mock_msg):
        """Verify accepting historical book value updates df_reg and clears problems."""
        resolved_called = []
        self.dialog.on_resolved = lambda oid: resolved_called.append(oid)

        # Apply resolutions
        self.dialog.apply_resolutions()

        self.assertEqual(resolved_called, ["1003"])
        # df_reg updated to book value "pectinata"
        self.assertEqual(self.app_state.df_reg.loc["1003", "Species"], "pectinata")
        self.assertTrue(any(self.app_state.df_log["Action"] == "RESOLVE_HISTORICAL_CONFLICT"))


class TestQtGbifReviewDialog(unittest.TestCase):
    """Unit tests for GBIF batch taxonomy reconciliation review."""

    def setUp(self):
        self.app_state = _create_mock_app_state()
        self.dialog = QtGbifReviewDialog(
            app_state=self.app_state,
            auto_start=False,
        )

    @patch("ui_qt.gbif_review.check_gbif")
    def test_batch_worker_and_table_population(self, mock_check):
        """Test reconciliation chunk worker and table row creation."""
        mock_check.return_value = {
            "matchType": "EXACT",
            "status": "ACCEPTED",
            "scientificName": "Pinus sylvestris L.",
            "genus": "Pinus",
            "species": "sylvestris",
            "confidence": 97,
        }

        candidates = [
            {"oid": "1001", "genus": "Pinus", "species": "sylvestris"}
        ]
        worker = GbifBatchReconciliationWorker(candidates)
        results = []
        worker.finished_all.connect(lambda res: results.extend(res))
        worker.run()

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["status"], "ACCEPTED")
        self.assertEqual(results[0]["confidence"], 97)

        # Load into dialog
        self.dialog._on_worker_finished(results)
        self.assertEqual(self.dialog.dialog.table_review.rowCount(), 1)

    def test_bulk_selection_helpers(self):
        """Test Select All, Deselect All, and Only High Confidence."""
        self.dialog.results = [
            {"oid": "1001", "confidence": 95, "status": "ACCEPTED", "checked": False},
            {"oid": "1002", "confidence": 60, "status": "SYNONYM", "checked": False},
        ]
        self.dialog._refresh_table()

        # Select all
        self.dialog.select_all()
        self.assertTrue(all(r["checked"] for r in self.dialog.results))

        # Deselect all
        self.dialog.deselect_all()
        self.assertFalse(any(r["checked"] for r in self.dialog.results))

        # Select confident
        self.dialog.select_confident()
        self.assertTrue(self.dialog.results[0]["checked"])
        self.assertFalse(self.dialog.results[1]["checked"])

    @patch("PySide6.QtWidgets.QMessageBox.information")
    def test_vectorized_accept_selected_commits(self, mock_msg):
        """Test vectorized batch acceptance updates df_reg and clears problems."""
        self.dialog.results = [
            {
                "oid": "1001",
                "matched_name": "Pinus sylvestris L.",
                "gbif_data": {
                    "genus": "Pinus",
                    "species": "sylvestris",
                    "author": "Linnaeus, 1753",
                    "family": "Pinaceae",
                    "usageKey": 5285637,
                },
                "checked": True,
            }
        ]

        applied_counts = []
        self.dialog.on_applied = lambda cnt: applied_counts.append(cnt)

        self.dialog.accept_selected()

        self.assertEqual(applied_counts, [1])
        self.assertEqual(self.app_state.df_reg.loc["1001", "Author"], "Linnaeus, 1753")
        self.assertTrue(self.app_state.df_obs.loc["1001", REVIEWED_COLUMN])
        self.assertTrue(any(self.app_state.df_log["Action"] == "GBIF_BATCH_UPDATE"))


class TestQtNewDatabaseWizard(unittest.TestCase):
    """Unit tests for NewDatabaseWizard controller."""

    def setUp(self):
        self.app_state = _create_mock_app_state()
        self.wizard = QtNewDatabaseWizard(
            app_state=self.app_state,
        )

    def test_profiles_populated(self):
        """Verify list_templates populated with configured database schema profiles."""
        self.assertGreater(self.wizard.wizard.list_templates.count(), 0)

    @patch("PySide6.QtWidgets.QMessageBox.information")
    @patch("repository.ExcelRepository.save_excel")
    def test_wizard_completion_initializes_database(self, mock_save, mock_msg):
        """Verify wizard acceptance builds initial dataframes and saves workbook."""
        temp_dest = "tests/scratch_new_db.xlsx"
        self.wizard.wizard.input_save_path.setText(temp_dest)
        self.wizard.wizard.input_collection_name.setText("Test Herbarium 2026")

        completed_callbacks = []
        self.wizard.on_completed = lambda path, profile: completed_callbacks.append((path, profile))

        self.wizard._on_wizard_accepted()

        self.assertEqual(len(completed_callbacks), 1)
        self.assertEqual(completed_callbacks[0][0], temp_dest)
        self.assertIsNotNone(self.app_state.df_reg)
        self.assertIsNotNone(self.app_state.df_obs)
        self.assertEqual(self.app_state.excel_path, temp_dest)
        mock_save.assert_called_once()


class TestPhase5MainWindowIntegration(unittest.TestCase):
    """Unit tests for Phase 5 triggers and integration inside QtMainWindow."""

    def setUp(self):
        self.app_state = _create_mock_app_state()
        self.main_win = QtMainWindow(app_state=self.app_state)

    def test_open_problem_queue_wired(self):
        """Verify problem queue opener in QtMainWindow."""
        with patch.object(QtProblemQueueDialog, "exec", return_value=0) as mock_exec:
            self.main_win.open_problem_queue()
            mock_exec.assert_called_once()

    def test_open_historical_resolver_wired(self):
        """Verify historical resolver opener in QtMainWindow."""
        with patch.object(QtHistoricalResolverDialog, "exec", return_value=0) as mock_exec:
            self.main_win.open_historical_resolver(oid="1001")
            mock_exec.assert_called_once()

    def test_open_gbif_batch_review_wired(self):
        """Verify GBIF batch review opener in QtMainWindow."""
        with patch.object(QtGbifReviewDialog, "exec", return_value=0) as mock_exec:
            self.main_win.open_gbif_batch_review()
            mock_exec.assert_called_once()

    def test_create_new_database_launches_wizard(self):
        """Verify New Database trigger launches QtNewDatabaseWizard."""
        with patch.object(QtNewDatabaseWizard, "exec", return_value=0) as mock_exec:
            self.main_win.create_new_database()
            mock_exec.assert_called_once()


if __name__ == "__main__":
    unittest.main()
