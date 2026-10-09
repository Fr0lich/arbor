"""Comprehensive unit tests for Phase 2 PySide6 dialogs and main workspace menus."""
from __future__ import annotations

import os
import sys
import unittest

import pandas as pd
from PySide6.QtWidgets import QApplication

import config
from models import AppState
from repository import REVIEWED_COLUMN
from ui_qt.dashboard import QtDatabaseStatisticsDialog
from ui_qt.main_window import QtMainWindow
from ui_qt.quick_peek import QtQuickPeekDialog
from ui_qt.recent_activity_dialog import QtRecentActivityDialog
import main_qt

app = QApplication.instance() or QApplication(sys.argv)


def _create_mock_app_state() -> AppState:
    """Construct an AppState populated with mock data for testing."""
    state = AppState()
    cfg_name = next(iter(config.DATABASE_CONFIGS)) if config.DATABASE_CONFIGS else "Test"
    state.config = config.DATABASE_CONFIGS.get(cfg_name, {})
    state.config_name = cfg_name
    state.excel_path = "mock_database.xlsx"
    state.output_path = "mock_database.xlsx"

    # Mock registration
    records = {
        "1001": {
            "Genus": "Pinus",
            "Species": "sylvestris",
            "Family": "Pinaceae",
            "Collector": "Linné",
            "Building": "Lid's hus",
            "Floor": "3",
            "Room": "301",
            "Cabinet": "C1",
        },
        "1002": {
            "Genus": "Abies",
            "Species": "alba",
            "Family": "Pinaceae",
            "Collector": "Smith",
            "Building": "Lid's hus",
            "Floor": "2",
            "Room": "205",
            "Cabinet": "C2",
        },
        "1003": {
            "Genus": "Betula",
            "Species": "pendula",
            "Family": "Betulaceae",
            "Collector": "Jones",
            "Building": "Økern",
            "Floor": "1",
            "Room": "101",
            "Cabinet": "C3",
        },
    }
    state.df_reg = pd.DataFrame.from_dict(records, orient="index")
    state.df_reg.index.name = "ObjectID"

    # Mock observation
    obs = {
        "1001": {REVIEWED_COLUMN: True, "Genus_Problem": False, "Species_Problem": False},
        "1002": {REVIEWED_COLUMN: False, "Genus_Problem": True, "Species_Problem": False},
        "1003": {REVIEWED_COLUMN: False, "Genus_Problem": False, "Species_Problem": False},
    }
    state.df_obs = pd.DataFrame.from_dict(obs, orient="index")
    state.df_obs.index.name = "ObjectID"

    # Mock log
    logs = [
        {
            "Timestamp": "2026-10-09 10:15:00",
            "ObjectID": "1001",
            "Action": "EDIT",
            "ChangedFields": "Collector",
            "ChangedValues": "Smith  Linné",
            "ProblemsChanged": "",
            "ProblemsChangedValues": "",
            "LocationChanged": "",
            "LocationChangedValues": "",
        },
        {
            "Timestamp": "2026-10-09 10:20:00",
            "ObjectID": "1002",
            "Action": "REVIEWED",
            "ChangedFields": "",
            "ChangedValues": "",
            "ProblemsChanged": "Genus_Problem",
            "ProblemsChangedValues": "False  True",
            "LocationChanged": "",
            "LocationChangedValues": "",
        },
    ]
    state.df_log = pd.DataFrame(logs)
    state.active_object_ids = ["1001", "1002", "1003"]
    state.current_object_id = "1001"
    return state


class TestPhase2QtDialogs(unittest.TestCase):

    def setUp(self):
        self.state = _create_mock_app_state()

    def test_database_statistics_dialog(self):
        """Test QtDatabaseStatisticsDialog with mock AppState."""
        dlg = QtDatabaseStatisticsDialog(app_state=self.state)
        self.assertIsNotNone(dlg.win)
        self.assertEqual(dlg.win.objectName(), "DatabaseStatisticsDialog")

        # Verify progress bar and metrics
        self.assertEqual(dlg.win.bar_review_progress.value(), 33)  # 1 of 3 = 33%
        self.assertIn("1 / 3", dlg.win.lbl_prog_stats.text())
        self.assertEqual(dlg.win.lbl_total_objects.text(), "Total Objects: 3")
        self.assertIn("1", dlg.win.lbl_probs_total.text())  # 1 object with Genus_Problem

        # Verify problem breakdown table
        self.assertGreater(dlg.win.table_problems.rowCount(), 0)

        # Test empty state
        empty_state = AppState()
        dlg_empty = QtDatabaseStatisticsDialog(app_state=empty_state)
        self.assertEqual(dlg_empty.win.bar_review_progress.value(), 0)
        self.assertEqual(dlg_empty.win.lbl_total_objects.text(), "Total Objects: 0")

    def test_recent_activity_dialog(self):
        """Test QtRecentActivityDialog with visited history and edits audit log."""
        navigated_oids = []

        def on_nav(oid):
            navigated_oids.append(oid)

        dlg = QtRecentActivityDialog(
            app_state=self.state,
            history_stack=["1001", "1002"],
            on_navigate=on_nav,
            default_tab=0,
        )
        self.assertIsNotNone(dlg.win)
        self.assertEqual(dlg.win.objectName(), "RecentActivityDialog")

        # Verify visited table
        tv = dlg.win.table_visited
        self.assertEqual(tv.rowCount(), 2)
        # Most recent first ("1002" then "1001")
        self.assertEqual(tv.item(0, 0).text(), "1002")
        self.assertIn("Abies", tv.item(0, 1).text())

        # Verify edits table
        te = dlg.win.table_edits
        self.assertEqual(te.rowCount(), 2)

        # Test live search filter on edits
        dlg.win.input_filter_edits.setText("Linné")
        self.assertEqual(te.rowCount(), 1)
        self.assertEqual(te.item(0, 1).text(), "1001")

        dlg.win.input_filter_edits.setText("NonExistent")
        self.assertEqual(te.rowCount(), 0)

        dlg.win.input_filter_edits.setText("")
        self.assertEqual(te.rowCount(), 2)

        # Test navigation trigger
        tv.selectRow(0)
        dlg._do_navigate()
        self.assertEqual(navigated_oids, ["1002"])

    def test_quick_peek_dialog(self):
        """Test QtQuickPeekDialog for metadata inspection and status badge."""
        opened_oids = []

        def on_open(oid):
            opened_oids.append(oid)

        dlg = QtQuickPeekDialog(
            app_state=self.state,
            oid="1001",
            on_open_full=on_open,
        )
        self.assertIsNotNone(dlg.win)
        self.assertEqual(dlg.win.objectName(), "QuickPeekDialog")

        # Verify metadata card
        self.assertEqual(dlg.win.lbl_oid.text(), "#1001")
        self.assertIn("Pinus sylvestris", dlg.win.lbl_title.text())
        self.assertEqual(dlg.win.badge_status.text(), "REVIEWED")
        self.assertIn("Pinus", dlg.win.lbl_genus.text())
        self.assertIn("sylvestris", dlg.win.lbl_species.text())
        self.assertIn("Pinaceae", dlg.win.lbl_family.text())
        self.assertIn("Linné", dlg.win.lbl_collector.text())
        self.assertIn("Lid's hus", dlg.win.lbl_location.text())

        # Test problem status badge on 1002
        dlg.load_object("1002")
        self.assertEqual(dlg.win.lbl_oid.text(), "#1002")
        self.assertEqual(dlg.win.badge_status.text(), "PROBLEMS")

        # Test open full review trigger
        dlg._do_open_full()
        self.assertEqual(opened_oids, ["1002"])

    def test_main_window_action_bars_and_menus(self):
        """Test QtMainWindow header action bar, dropdown menus, and domain actions."""
        win = QtMainWindow(app_state=self.state)
        self.assertIsNotNone(win.win)

        # Verify tree loaded items
        self.assertEqual(win.win.tree_objects.topLevelItemCount(), 3)

        # Verify menus created
        self.assertIsNotNone(win.menu_file)
        self.assertIsNotNone(win.menu_data)
        self.assertIsNotNone(win.menu_images)
        self.assertIsNotNone(win.menu_create)
        self.assertIsNotNone(win.menu_presets)
        self.assertIsNotNone(win.menu_gbif)

        # Verify key menu actions exist
        file_action_names = [a.text() for a in win.menu_file.actions()]
        self.assertIn("New Database", file_action_names)
        self.assertIn("Open Excel...", file_action_names)
        self.assertIn("Save", file_action_names)
        self.assertIn("Save As...", file_action_names)

        data_action_names = [a.text() for a in win.menu_data.actions()]
        self.assertTrue(any("Database Statistics" in name for name in data_action_names))
        self.assertTrue(any("Recent Activity" in name for name in data_action_names))
        self.assertTrue(any("Load Books" in name for name in data_action_names))
        self.assertTrue(any("GBIF" in name for name in data_action_names))

        create_action_names = [a.text() for a in win.menu_create.actions()]
        self.assertIn("New Object", create_action_names)

        presets_action_names = [a.text() for a in win.menu_presets.actions()]
        self.assertTrue(any("Save Current Fields as Preset" in name for name in presets_action_names))

        # Test Prev/Next navigation
        win.navigate_next()
        self.assertEqual(win.app.current_object_id, "1002")
        win.navigate_prev()
        self.assertEqual(win.app.current_object_id, "1001")

        # Test domain action wrappers in main_qt
        self.assertTrue(callable(main_qt.open_excel_action))
        self.assertTrue(callable(main_qt.save_session_action))
        self.assertTrue(callable(main_qt.load_books_action))
        self.assertTrue(callable(main_qt.run_gbif_check_action))


if __name__ == "__main__":
    unittest.main()
