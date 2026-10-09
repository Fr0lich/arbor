"""Comprehensive unit tests for Phase 4 PySide6 Filter Dialog & GBIF Validator."""
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
from ui_qt.filter_dialog import QtFilterDialog, QtTriStateRow
from ui_qt.gbif_dialog import QtGbifUpdateDialog
from ui_qt.main_window import QtMainWindow

app = QApplication.instance() or QApplication(sys.argv)


def _create_mock_app_state() -> AppState:
    """Create populated AppState instance for Phase 4 tests."""
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
                {"name": "Other_problem", "type": "bool", "category": "notes"},
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
            "Building": "Lid's hus",
            "Floor": "3",
            "Cabinet": "C1",
            "Drawer": "D1",
            "Extra": "Stored in cold room",
        },
        "1002": {
            REVIEWED_COLUMN: True,
            "Genus_Problem": False,
            "Species_Problem": False,
            "Author_Problem": False,
            "Family_Problem": False,
            "Other_problem": True,
            "Building": "Botanisk",
            "Floor": "1",
            "Cabinet": "C2",
            "Drawer": "D3",
            "Extra": "",
        },
        "1003": {
            REVIEWED_COLUMN: False,
            "Genus_Problem": True,
            "Species_Problem": False,
            "Author_Problem": False,
            "Family_Problem": False,
            "Other_problem": False,
            "Building": "Lid's hus",
            "Floor": "2",
            "Cabinet": "C1",
            "Drawer": "D2",
            "Extra": "Relocated recently",
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
    return state


class TestQtFilterDialog(unittest.TestCase):
    """Unit tests for QtFilterDialog controller."""

    def setUp(self):
        self.app_state = _create_mock_app_state()
        self.dialog = QtFilterDialog(app_state=self.app_state)

    def test_init_and_tabs_populated(self):
        """Verify that all tabs and tri-state rows are initialized properly."""
        self.assertIsNotNone(self.dialog.dialog)
        self.assertEqual(self.dialog.dialog.tabs_filter.count(), 4)

        # Tab names
        tab_titles = [self.dialog.dialog.tabs_filter.tabText(i) for i in range(4)]
        self.assertIn("Status & General", tab_titles)
        self.assertIn("Problems & History", tab_titles)
        self.assertIn("Images", tab_titles)
        self.assertIn("Location", tab_titles)

        # Core rows present
        self.assertIn("Reviewed", self.dialog.rows)
        self.assertIn("Has_Comment", self.dialog.rows)
        self.assertIn("Has_Location_Comment", self.dialog.rows)
        self.assertIn("Any_Problem", self.dialog.rows)
        self.assertIn("Genus_Problem", self.dialog.rows)
        self.assertIn("Has_Images", self.dialog.rows)

        # Location inputs
        self.assertIn("Building", self.dialog.location_inputs)
        self.assertIn("Floor", self.dialog.location_inputs)
        self.assertIn("Cabinet", self.dialog.location_inputs)
        self.assertIn("Drawer", self.dialog.location_inputs)

    def test_tristate_row_cycling_and_aliases(self):
        """Test cycling states and setting via string aliases."""
        row = QtTriStateRow("Reviewed", "Reviewed")
        self.assertEqual(row.state, "Ignore")

        # Forward cycle: Ignore -> Has -> Not -> Ignore
        row.cycle(1)
        self.assertEqual(row.state, "Has")
        self.assertEqual(row.btn_indicator.text(), "✓")

        row.cycle(1)
        self.assertEqual(row.state, "Not")
        self.assertEqual(row.btn_indicator.text(), "−")

        row.cycle(1)
        self.assertEqual(row.state, "Ignore")
        self.assertEqual(row.btn_indicator.text(), " ")

        # Aliases
        row.set_state("Yes")
        self.assertEqual(row.state, "Has")

        row.set_state("No")
        self.assertEqual(row.state, "Not")

        row.set_state("Any")
        self.assertEqual(row.state, "Ignore")

    def test_filtering_execution_and_matches(self):
        """Verify query execution across df_reg and df_obs."""
        # 1. Filter Reviewed == Has -> only 1002
        self.dialog.rows["Reviewed"].set_state("Has")
        matches = self.dialog._compute_matches()
        self.assertEqual(matches, ["1002"])

        # 2. Filter Reviewed == Not -> 1001, 1003
        self.dialog.rows["Reviewed"].set_state("Not")
        matches = self.dialog._compute_matches()
        self.assertEqual(sorted(matches), ["1001", "1003"])

        # Reset Reviewed
        self.dialog.rows["Reviewed"].set_state("Ignore")

        # 3. Filter by Location Building == "Botanisk" -> only 1002
        self.dialog.location_inputs["Building"].setText("Botanisk")
        matches = self.dialog._compute_matches()
        self.assertEqual(matches, ["1002"])

        # 4. Filter by Location Building == "Lid's hus" -> 1001, 1003
        self.dialog.location_inputs["Building"].setText("Lid's hus")
        matches = self.dialog._compute_matches()
        self.assertEqual(sorted(matches), ["1001", "1003"])

    def test_apply_and_clear_filter(self):
        """Verify applying and resetting filters mutates AppState correctly."""
        applied_batches = []
        cleared_called = []

        self.dialog.on_apply = lambda m: applied_batches.append(m)
        self.dialog.on_clear = lambda: cleared_called.append(True)

        # Set filter
        self.dialog.rows["Reviewed"].set_state("Has")
        self.dialog.apply_filter()

        self.assertEqual(len(applied_batches), 1)
        self.assertEqual(applied_batches[0], ["1002"])
        self.assertEqual(self.app_state.active_object_ids, ["1002"])

        # Clear filter
        self.dialog.clear_filter()
        self.assertEqual(len(cleared_called), 1)
        self.assertEqual(sorted(self.app_state.active_object_ids), ["1001", "1002", "1003"])
        self.assertEqual(self.dialog.rows["Reviewed"].state, "Ignore")

    def test_preset_management(self):
        """Test preset saving, loading, and deletion."""
        preset_name = "test_phase4_preset_temp"

        # Configure state
        self.dialog.rows["Reviewed"].set_state("Has")
        self.dialog.rows["Has_Comment"].set_state("Has")
        self.dialog.location_inputs["Building"].setText("Lid's hus")

        # Save preset programmatically
        saved = self.dialog.save_preset(name=preset_name)
        self.assertTrue(saved)

        # Reset
        self.dialog.clear_filter()
        self.assertEqual(self.dialog.rows["Reviewed"].state, "Ignore")
        self.assertEqual(self.dialog.location_inputs["Building"].text(), "")

        # Load preset programmatically
        loaded = self.dialog.load_preset(preset_name=preset_name)
        self.assertTrue(loaded)
        self.assertEqual(self.dialog.rows["Reviewed"].state, "Has")
        self.assertEqual(self.dialog.rows["Has_Comment"].state, "Has")
        self.assertEqual(self.dialog.location_inputs["Building"].text(), "Lid's hus")

        # Delete preset
        deleted = self.dialog.delete_preset(preset_name)
        self.assertTrue(deleted)


class TestQtGbifUpdateDialog(unittest.TestCase):
    """Unit tests for QtGbifUpdateDialog controller."""

    def setUp(self):
        self.app_state = _create_mock_app_state()

    def test_init_and_metadata_binding(self):
        """Verify extraction and population of active specimen metadata."""
        dialog = QtGbifUpdateDialog(
            app_state=self.app_state,
            oid="1001",
            auto_query=False,
        )
        self.assertEqual(dialog.current_data["genus"], "Pinus")
        self.assertEqual(dialog.current_data["species"], "sylvestris")
        self.assertEqual(dialog.current_data["author"], "L.")
        self.assertEqual(dialog.current_data["family"], "Pinaceae")
        self.assertEqual(dialog.current_data["taxon_id"], "5285637")

        # UI labels
        self.assertEqual(dialog.dialog.lbl_target_info.text(), "Object #1001")
        self.assertIn("Pinus", dialog.dialog.lbl_cur_genus.text())
        self.assertIn("sylvestris", dialog.dialog.lbl_cur_species.text())
        self.assertIn("L.", dialog.dialog.lbl_cur_author.text())
        self.assertIn("Pinaceae", dialog.dialog.lbl_cur_family.text())

    @patch("backend.gbif.check_gbif")
    def test_query_gbif_mock_response_match(self, mock_check):
        """Verify population of GBIF reconciliation diff cards and badges."""
        mock_check.return_value = {
            "matchType": "EXACT",
            "status": "ACCEPTED",
            "canonicalName": "Pinus sylvestris",
            "scientificName": "Pinus sylvestris L., 1753",
            "genus": "Pinus",
            "species": "sylvestris",
            "author": "Linnaeus, 1753",
            "family": "Pinaceae",
            "rank": "SPECIES",
            "confidence": 98,
            "usageKey": 5285637,
            "taxonKey": 5285637,
            "synonym": False,
        }

        dialog = QtGbifUpdateDialog(
            app_state=self.app_state,
            oid="1001",
            auto_query=False,
        )
        res = dialog.query_gbif(blocking=True)
        self.assertIsNotNone(res)
        self.assertEqual(dialog.gbif_result["genus"], "Pinus")
        self.assertEqual(dialog.gbif_result["author"], "Linnaeus, 1753")

        # Label verifications
        self.assertIn("Pinus", dialog.dialog.lbl_gbif_genus.text())
        self.assertIn("Linnaeus, 1753", dialog.dialog.lbl_gbif_author.text())
        self.assertIn("CONFIDENCE: 98%", dialog.dialog.lbl_confidence_badge.text())
        self.assertTrue(dialog.dialog.btn_accept.isEnabled())

    @patch("backend.gbif.check_gbif")
    def test_selective_acceptance_and_commit(self, mock_check):
        """Verify selective commitment of fields to df_reg, df_obs, and df_log."""
        mock_check.return_value = {
            "matchType": "EXACT",
            "status": "ACCEPTED",
            "canonicalName": "Pinus sylvestris",
            "scientificName": "Pinus sylvestris Linnaeus",
            "genus": "Pinus",
            "species": "sylvestris",
            "author": "Linnaeus",
            "family": "Pinaceae",
            "rank": "SPECIES",
            "confidence": 96,
            "usageKey": 999999,
            "taxonKey": 999999,
            "synonym": False,
        }

        applied_callbacks = []
        dialog = QtGbifUpdateDialog(
            app_state=self.app_state,
            oid="1001",
            on_applied=lambda r: applied_callbacks.append(r),
            auto_query=False,
        )
        dialog.query_gbif(blocking=True)

        # Author and TaxonID only
        dialog.dialog.chk_apply_genus.setChecked(False)
        dialog.dialog.chk_apply_species.setChecked(False)
        dialog.dialog.chk_apply_author.setChecked(True)
        dialog.dialog.chk_apply_family.setChecked(False)
        dialog.dialog.chk_apply_taxon_id.setChecked(True)

        dialog.apply_updates()

        # df_reg updated
        self.assertEqual(self.app_state.df_reg.loc["1001", "Author"], "Linnaeus")
        self.assertEqual(str(self.app_state.df_reg.loc["1001", "TaxonID"]), "999999")
        self.assertEqual(self.app_state.df_reg.loc["1001", "Genus"], "Pinus")  # unchanged

        # df_obs mapped problem cleared: Author_Problem was True -> now False
        self.assertFalse(bool(self.app_state.df_obs.loc["1001", "Author_Problem"]))

        # Undo stack recorded
        self.assertIn("1001", self.app_state.undo_stacks)
        self.assertEqual(len(self.app_state.undo_stacks["1001"]), 1)
        self.assertEqual(self.app_state.undo_stacks["1001"][0]["reg"]["Author"], "L.")

        # df_log recorded
        self.assertTrue(any(self.app_state.df_log["Action"] == "GBIF_UPDATE"))
        self.assertTrue(self.app_state.dirty)
        self.assertEqual(len(applied_callbacks), 1)

    @patch("backend.gbif.check_gbif")
    def test_query_network_error_and_no_match(self, mock_check):
        """Verify handling of network timeout and no match found."""
        # 1. Network error
        mock_check.return_value = {"error": "Connection timed out"}
        dialog = QtGbifUpdateDialog(app_state=self.app_state, oid="1001", auto_query=False)
        dialog.query_gbif(blocking=True)

        self.assertIn("NETWORK ERROR", dialog.dialog.lbl_confidence_badge.text())
        self.assertFalse(dialog.dialog.btn_accept.isEnabled())

        # 2. No match
        mock_check.return_value = {}
        dialog = QtGbifUpdateDialog(app_state=self.app_state, oid="1001", auto_query=False)
        dialog.query_gbif(blocking=True)

        self.assertIn("NO MATCH", dialog.dialog.lbl_confidence_badge.text())
        self.assertFalse(dialog.dialog.btn_accept.isEnabled())


class TestPhase4MainWindowIntegration(unittest.TestCase):
    """Unit tests for Phase 4 triggers and integration inside QtMainWindow."""

    def setUp(self):
        self.app_state = _create_mock_app_state()
        self.main_win = QtMainWindow(app_state=self.app_state)

    def test_open_filter_dialog_wired(self):
        """Verify filter button and Data menu triggers open QtFilterDialog."""
        with patch.object(QtFilterDialog, "exec", return_value=0):
            self.main_win.open_filter_dialog()
            self.assertIsNotNone(self.main_win.filter_dialog)

    def test_search_bar_query_filtering(self):
        """Verify that typing into the search bar filters active objects."""
        # Query for 'Betula' -> only 1002 matches
        self.main_win._on_search_query_changed("Betula")
        self.assertEqual(self.main_win.app.active_object_ids, ["1002"])

        # Clear search
        self.main_win._on_search_query_changed("")
        self.assertEqual(sorted(self.main_win.app.active_object_ids), ["1001", "1002", "1003"])

    def test_validate_current_specimen_wired(self):
        """Verify GBIF verification trigger in QtMainWindow."""
        with patch.object(QtGbifUpdateDialog, "exec", return_value=0) as mock_exec:
            self.main_win.validate_current_specimen_gbif()
            mock_exec.assert_called_once()

    def test_tree_context_menu_request(self):
        """Verify context menu request handler on tree_objects."""
        pos = QPoint(10, 10)
        # Should execute safely without error
        self.main_win._show_tree_context_menu(pos)


if __name__ == "__main__":
    unittest.main()
