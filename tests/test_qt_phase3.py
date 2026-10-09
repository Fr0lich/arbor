"""Comprehensive unit tests for Phase 3 PySide6 editing & configuration dialogs."""
from __future__ import annotations

import os
import sys
import unittest
from unittest.mock import MagicMock, patch

import pandas as pd
from PySide6.QtWidgets import QApplication, QMessageBox

import config
from models import AppState
from repository import REVIEWED_COLUMN
from ui_qt.add_objects import QtAddObjectsDialog
from ui_qt.bulk_edit import QtBulkEditDialog
from ui_qt.group_editor import QtGroupEditorDialog
from ui_qt.main_window import QtMainWindow
from ui_qt.unified_settings import QtUnifiedSettingsDialog

app = QApplication.instance() or QApplication(sys.argv)


def _create_mock_app_state() -> AppState:
    """Create populated AppState instance for Phase 3 tests."""
    state = AppState()
    cfg_name = next(iter(config.DATABASE_CONFIGS)) if config.DATABASE_CONFIGS else "Test"
    state.config = {
        "ui_sections": {
            "registration": [
                {"name": "Genus", "type": "text"},
                {"name": "Species", "type": "text"},
                {"name": "Collector", "type": "text"},
                {"name": "Collection", "type": "text"},
            ],
            "location": [
                {"name": "Building", "type": "text"},
                {"name": "Floor", "type": "choice"},
            ],
            "problems": [
                {"name": "Genus_Problem", "type": "bool"},
                {"name": "Species_Problem", "type": "bool"},
            ],
        }
    }
    state.config_name = cfg_name
    state.excel_path = "mock_db.xlsx"
    state.output_path = "mock_db.xlsx"

    records = {
        "1001": {
            "Genus": "Pinus",
            "Species": "sylvestris",
            "Collector": "Linné",
            "Collection": "Herbarium Oslo",
            "Building": "Lid's hus",
            "Floor": "3",
        },
        "1002": {
            "Genus": "Abies",
            "Species": "alba",
            "Collector": "Smith",
            "Collection": "Herbarium Oslo",
            "Building": "Lid's hus",
            "Floor": "2",
        },
        "1003": {
            "Genus": "Betula",
            "Species": "pendula",
            "Collector": "Jones",
            "Collection": "Herbarium Bergen",
            "Building": "Botanisk",
            "Floor": "1",
        },
    }
    state.df_reg = pd.DataFrame.from_dict(records, orient="index")
    state.df_reg.index.name = "ObjectID"

    obs = {
        "1001": {REVIEWED_COLUMN: False, "Genus_Problem": False, "Species_Problem": False},
        "1002": {REVIEWED_COLUMN: False, "Genus_Problem": True, "Species_Problem": False},
        "1003": {REVIEWED_COLUMN: True, "Genus_Problem": False, "Species_Problem": False},
    }
    state.df_obs = pd.DataFrame.from_dict(obs, orient="index")
    state.df_obs.index.name = "ObjectID"

    state.df_log = pd.DataFrame(columns=[
        "Timestamp", "ObjectID", "Action", "ChangedFields", "ChangedValues",
        "ProblemsChanged", "ProblemsChangedValues", "LocationChanged", "LocationChangedValues"
    ])
    state.active_object_ids = ["1001", "1002", "1003"]
    state.current_object_id = "1001"
    state.dirty = False
    return state


class TestQtUnifiedSettingsDialog(unittest.TestCase):
    """Unit tests for QtUnifiedSettingsDialog controller."""

    def setUp(self):
        self.state = _create_mock_app_state()

    def test_init_and_tab_navigation(self):
        """Test default and programmatic tab selection."""
        dlg = QtUnifiedSettingsDialog(app_state=self.state, default_tab="appearance")
        self.assertIsNotNone(dlg.win)
        self.assertEqual(dlg.win.tab_widget.currentIndex(), 1)

        dlg._select_tab("profiles")
        self.assertEqual(dlg.win.tab_widget.currentIndex(), 2)

        dlg._select_tab("advanced")
        self.assertEqual(dlg.win.tab_widget.currentIndex(), 3)

        dlg._select_tab("general")
        self.assertEqual(dlg.win.tab_widget.currentIndex(), 0)

    def test_populate_and_save_settings(self):
        """Test reading preferences and persisting modified values."""
        saved_prefs = {}

        def on_save(p):
            saved_prefs.update(p)

        dlg = QtUnifiedSettingsDialog(app_state=self.state, on_save=on_save)

        # Mutate controls
        dlg.win.spin_autosave.setValue(15)
        dlg.win.combo_scale.setCurrentIndex(2)  # 125%
        dlg.win.chk_confirm_delete.setChecked(False)
        dlg.win.chk_dark_mode.setChecked(True)
        dlg.win.chk_problem_highlights.setChecked(True)
        dlg.win.combo_highlight_color.setCurrentText("Yellow")
        dlg.win.chk_debug_logging.setChecked(True)

        with patch("config.save_prefs") as mock_save:
            dlg.save_settings()
            self.assertTrue(mock_save.called)
            persisted = mock_save.call_args[0][0]
            self.assertEqual(persisted["autosave_interval"], 15)
            self.assertEqual(persisted["ui_scale"], 1.25)
            self.assertFalse(persisted["confirm_delete"])
            self.assertTrue(persisted["dark_mode"])
            self.assertEqual(persisted["problem_highlight_color"], "Yellow")
            self.assertTrue(persisted["debug_logging"])

        self.assertEqual(saved_prefs.get("autosave_interval"), 15)

    def test_validation_autosave_range(self):
        """Test autosave interval boundary validation."""
        dlg = QtUnifiedSettingsDialog(app_state=self.state)
        dlg.win.spin_autosave.setMinimum(0)
        dlg.win.spin_autosave.setValue(0)

        with patch("PySide6.QtWidgets.QMessageBox.critical") as mock_msg:
            with patch("config.save_prefs") as mock_save:
                dlg.save_settings()
                self.assertTrue(mock_msg.called)
                self.assertFalse(mock_save.called)

    def test_profile_management(self):
        """Test adding and selecting database profiles."""
        dlg = QtUnifiedSettingsDialog(app_state=self.state)
        initial_count = dlg.win.list_profiles.count()

        # Add custom profile via mock input dialog
        with patch("PySide6.QtWidgets.QInputDialog.getText", return_value=("Test_Profile_Phase3", True)):
            dlg._add_profile()
            self.assertEqual(dlg.win.list_profiles.count(), initial_count + 1)
            self.assertIn("Test_Profile_Phase3", dlg.prefs.get("custom_databases", {}))


class TestQtGroupEditorDialog(unittest.TestCase):
    """Unit tests for QtGroupEditorDialog controller."""

    def setUp(self):
        self.state = _create_mock_app_state()

    def test_initialization_empty_and_populated(self):
        """Test dialog startup and member population."""
        self.state.specimen_groups = {"Conifers": ["1001", "1002"]}
        dlg = QtGroupEditorDialog(app_state=self.state)

        self.assertIsNotNone(dlg.win)
        self.assertEqual(dlg.win.list_groups.count(), 1)
        self.assertIn("Conifers (2)", dlg.win.list_groups.item(0).text())

        # Select group and verify members
        dlg._refresh_members_list("Conifers")
        self.assertEqual(dlg.win.list_members.count(), 2)

    def test_create_and_delete_group(self):
        """Test adding and deleting specimen groups."""
        dlg = QtGroupEditorDialog(app_state=self.state)
        dlg.win.input_group_name.setText("Deciduous")
        dlg.create_group()

        self.assertIn("Deciduous", dlg.groups)
        self.assertEqual(len(dlg.groups["Deciduous"]), 0)
        self.assertTrue(self.state.dirty)

        # Delete group
        with patch("PySide6.QtWidgets.QMessageBox.question", return_value=QMessageBox.Yes):
            dlg.delete_group()
            self.assertNotIn("Deciduous", dlg.groups)

    def test_add_current_and_filtered_objects(self):
        """Test assigning active and batch filtered specimens to a group."""
        dlg = QtGroupEditorDialog(app_state=self.state)
        dlg.win.input_group_name.setText("Field_Collection")
        dlg.create_group()

        # Add current object 1001
        dlg.add_current_object()
        self.assertIn("1001", dlg.groups["Field_Collection"])

        # Add all filtered objects (1001, 1002, 1003)
        with patch("PySide6.QtWidgets.QMessageBox.information"):
            dlg.add_filtered_objects()
            self.assertEqual(len(dlg.groups["Field_Collection"]), 3)
            self.assertIn("1002", dlg.groups["Field_Collection"])
            self.assertIn("1003", dlg.groups["Field_Collection"])

        # Remove member
        dlg.win.list_members.setCurrentRow(0)
        dlg.remove_selected_member()
        self.assertEqual(len(dlg.groups["Field_Collection"]), 2)


class TestQtBulkEditDialog(unittest.TestCase):
    """Unit tests for QtBulkEditDialog controller."""

    def setUp(self):
        self.state = _create_mock_app_state()

    def test_field_dropdown_population(self):
        """Test combo_field contains registration and problem columns."""
        dlg = QtBulkEditDialog(app_state=self.state)
        fields = [dlg.win.combo_field.itemText(i) for i in range(dlg.win.combo_field.count())]
        self.assertIn("Genus", fields)
        self.assertIn("Species", fields)
        self.assertIn("Collector", fields)
        self.assertIn("Building", fields)
        self.assertIn("Genus_Problem", fields)

    def test_dry_run_preview_diffs(self):
        """Test dry run calculation does not modify actual data."""
        dlg = QtBulkEditDialog(app_state=self.state)
        dlg.win.combo_field.setCurrentText("Collector")
        dlg.win.input_find.setText("Smith")
        dlg.win.input_replace.setText("Schmidt")
        dlg.win.radio_all.setChecked(True)

        diffs = dlg.preview_changes()
        self.assertEqual(len(diffs), 1)
        self.assertEqual(diffs[0]["oid"], "1002")
        self.assertEqual(diffs[0]["old"], "Smith")
        self.assertEqual(diffs[0]["new"], "Schmidt")

        # Verify df_reg is NOT mutated yet
        self.assertEqual(self.state.df_reg.at["1002", "Collector"], "Smith")
        self.assertFalse(self.state.dirty)

    def test_regex_matching_and_apply(self):
        """Test regex find-and-replace and committing changes to df_reg and df_log."""
        dlg = QtBulkEditDialog(app_state=self.state)
        dlg.win.combo_field.setCurrentText("Collection")
        dlg.win.input_find.setText(r"^Herbarium\s+(.*)$")
        dlg.win.input_replace.setText(r"Museum \1")
        dlg.win.chk_regex.setChecked(True)
        dlg.win.radio_all.setChecked(True)

        with patch("PySide6.QtWidgets.QMessageBox.question", return_value=QMessageBox.Yes):
            dlg.apply_changes()

        # Check modifications
        self.assertEqual(self.state.df_reg.at["1001", "Collection"], "Museum Oslo")
        self.assertEqual(self.state.df_reg.at["1002", "Collection"], "Museum Oslo")
        self.assertEqual(self.state.df_reg.at["1003", "Collection"], "Museum Bergen")
        self.assertTrue(self.state.dirty)

        # Check audit log entries
        self.assertGreater(len(self.state.df_log), 0)
        last_log = self.state.df_log.iloc[-1]
        self.assertEqual(last_log["Action"], "BULK_EDIT")
        self.assertEqual(last_log["ChangedFields"], "Collection")


class TestQtAddObjectsDialog(unittest.TestCase):
    """Unit tests for QtAddObjectsDialog controller."""

    def setUp(self):
        self.state = _create_mock_app_state()

    def test_sequential_id_generation(self):
        """Test sequential range calculation with prefixes and suffixes."""
        dlg = QtAddObjectsDialog(app_state=self.state)
        dlg.win.input_prefix.setText("NHM-")
        dlg.win.input_start_id.setText("5001")
        dlg.win.spin_count.setValue(3)
        dlg.win.input_suffix.setText("-A")

        ids = dlg.generate_object_ids()
        self.assertEqual(ids, ["NHM-5001-A", "NHM-5002-A", "NHM-5003-A"])

    def test_duplicate_validation(self):
        """Test duplicate detection against existing df_reg.index."""
        dlg = QtAddObjectsDialog(app_state=self.state)
        dlg.win.input_prefix.setText("")
        dlg.win.input_start_id.setText("1001")  # Already exists!
        dlg.win.spin_count.setValue(2)

        duplicates = dlg.validate_ids(dlg.generate_object_ids())
        self.assertIn("1001", duplicates)
        self.assertIn("1002", duplicates)

        with patch("PySide6.QtWidgets.QMessageBox.critical") as mock_crit:
            dlg.create_objects()
            self.assertTrue(mock_crit.called)
            # Ensure no objects were inserted
            self.assertEqual(len(self.state.df_reg), 3)

    def test_batch_object_creation_and_defaults(self):
        """Test batch insertion into df_reg, df_obs, active_object_ids, and df_log."""
        created_oids = []

        def on_created(oids):
            created_oids.extend(oids)

        dlg = QtAddObjectsDialog(app_state=self.state, on_created=on_created)
        dlg.win.input_prefix.setText("SPEC-")
        dlg.win.input_start_id.setText("2001")
        dlg.win.spin_count.setValue(2)
        dlg.win.input_def_genus.setText("Salix")
        dlg.win.input_def_species.setText("caprea")
        dlg.win.input_def_collector.setText("Linné")
        dlg.win.input_def_collection.setText("Herbarium Oslo")
        dlg.win.input_def_location.setText("Lid's hus")

        dlg.create_objects()

        self.assertEqual(created_oids, ["SPEC-2001", "SPEC-2002"])
        self.assertIn("SPEC-2001", self.state.df_reg.index)
        self.assertIn("SPEC-2002", self.state.df_reg.index)
        self.assertIn("SPEC-2001", self.state.df_obs.index)
        self.assertIn("SPEC-2002", self.state.df_obs.index)
        self.assertIn("SPEC-2001", self.state.active_object_ids)
        self.assertIn("SPEC-2002", self.state.active_object_ids)

        # Check default metadata populated
        self.assertEqual(self.state.df_reg.at["SPEC-2001", "Genus"], "Salix")
        self.assertEqual(self.state.df_reg.at["SPEC-2001", "Species"], "caprea")
        self.assertEqual(self.state.df_reg.at["SPEC-2001", "Building"], "Lid's hus")
        self.assertFalse(self.state.df_obs.at["SPEC-2001", REVIEWED_COLUMN])
        self.assertFalse(self.state.df_obs.at["SPEC-2001", "Genus_Problem"])

        self.assertTrue(self.state.dirty)
        self.assertEqual(self.state.current_object_id, "SPEC-2001")


class TestPhase3MainWindowIntegration(unittest.TestCase):
    """Test QtMainWindow integration and wiring of Phase 3 dialogs."""

    def setUp(self):
        self.state = _create_mock_app_state()
        self.main_win = QtMainWindow(app_state=self.state)

    def test_open_unified_settings_wired(self):
        """Test open_unified_settings creates and executes dialog."""
        with patch.object(QtUnifiedSettingsDialog, "exec", return_value=0) as mock_exec:
            self.main_win.open_unified_settings(default_tab="appearance")
            self.assertTrue(mock_exec.called)

    def test_open_group_editor_wired(self):
        """Test open_group_editor creates and executes dialog."""
        with patch.object(QtGroupEditorDialog, "exec", return_value=0) as mock_exec:
            self.main_win.open_group_editor()
            self.assertTrue(mock_exec.called)

    def test_open_bulk_edit_wired(self):
        """Test open_bulk_edit creates and executes dialog."""
        with patch.object(QtBulkEditDialog, "exec", return_value=0) as mock_exec:
            self.main_win.open_bulk_edit()
            self.assertTrue(mock_exec.called)

    def test_create_new_object_wired(self):
        """Test create_new_object launches QtAddObjectsDialog."""
        with patch.object(QtAddObjectsDialog, "exec", return_value=0) as mock_exec:
            self.main_win.create_new_object()
            self.assertTrue(mock_exec.called)


if __name__ == "__main__":
    unittest.main()
