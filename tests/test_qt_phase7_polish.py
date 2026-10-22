"""tests/test_qt_phase7_polish.py - Test suite for Phase 7 Polish & Interactions.

Covers:
  - Rapid-entry focus jumping (Search, Tree, Registration, Location, Problems)
  - Specimen lifecycle (duplication, quick creation, deletion, multi-selection reviewed)
  - Undo and Redo stack restoration
  - Image canvas navigation, multi-photo gallery pagination, zoom, and clipboard
  - Layout toggles (F6, F7, F8)
  - Window splitter persistence
"""

import os
import sys
import unittest
import pandas as pd
from PySide6.QtWidgets import QApplication, QMessageBox
from PySide6.QtCore import Qt

from models import AppState
from repository import ExcelRepository, _normalize_object_id_series
from ui_qt.main_window import QtMainWindow

MOCK_DB_PATH = os.path.abspath("scratch/mock_current_db.xlsx")


class TestQtPhase7Polish(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication(sys.argv)
        # Suppress interactive dialog popups during tests
        cls._orig_question = QMessageBox.question
        QMessageBox.question = lambda *args, **kwargs: QMessageBox.Yes

    @classmethod
    def tearDownClass(cls):
        QMessageBox.question = cls._orig_question

    def setUp(self):
        self.state = AppState()
        self.win = QtMainWindow(self.state)
        self.win.open_excel(MOCK_DB_PATH)
        self.win.win.show()
        QApplication.processEvents()

    def tearDown(self):
        self.win.win.close()
        QApplication.processEvents()

    def test_focus_transitions(self):
        """Verify rapid-entry keyboard focus navigation methods."""
        self.win.win.activateWindow()
        QApplication.processEvents()

        # Focus search bar
        self.win.focus_search_bar()
        QApplication.processEvents()
        self.assertTrue(self.win.win.edit_search.hasFocus() or QApplication.focusWidget() == self.win.win.edit_search)

        # Focus object tree
        self.win.focus_object_tree()
        QApplication.processEvents()
        self.assertTrue(self.win.win.tree_objects.hasFocus() or QApplication.focusWidget() == self.win.win.tree_objects)

        # Focus first registration field (should switch to tab 0)
        self.win.focus_first_reg_field()
        QApplication.processEvents()
        self.assertEqual(self.win.win.tabs_registration.currentIndex(), 0)

        # Focus first location field
        self.win.focus_first_location_field()
        QApplication.processEvents()
        has_loc_focus = any(w.hasFocus() or QApplication.focusWidget() == w for w in self.win.location_panel.entries.values())
        self.assertTrue(has_loc_focus)

        # Focus first problem checkbox (should switch to tab 1)
        self.win.focus_first_problem_checkbox()
        QApplication.processEvents()
        self.assertEqual(self.win.win.tabs_registration.currentIndex(), 1)
        has_prob_focus = any(cb.hasFocus() or QApplication.focusWidget() == cb for cb in self.win.problems_panel.problem_cbs.values())
        self.assertTrue(has_prob_focus)

        # Switch registration tabs
        self.win.switch_registration_tab(1)
        self.assertEqual(self.win.win.tabs_registration.currentIndex(), 0)
        self.win.switch_registration_tab(1)
        self.assertEqual(self.win.win.tabs_registration.currentIndex(), 1)

    def test_undo_and_redo_stack(self):
        """Verify field editing followed by undo and redo."""
        self.win.navigate_to_object("1001")
        initial_genus = str(self.state.df_reg.loc["1001", "Genus"])

        # Edit field
        self.win._on_field_edited("Genus", "ModifiedGenus")
        self.assertEqual(str(self.state.df_reg.loc["1001", "Genus"]), "ModifiedGenus")
        self.assertTrue(self.state.dirty)

        # Undo
        self.win.undo()
        self.assertEqual(str(self.state.df_reg.loc["1001", "Genus"]), initial_genus)

        # Redo
        self.win.redo()
        self.assertEqual(str(self.state.df_reg.loc["1001", "Genus"]), "ModifiedGenus")

        # Clean up with undo
        self.win.undo()
        self.assertEqual(str(self.state.df_reg.loc["1001", "Genus"]), initial_genus)

    def test_specimen_lifecycle(self):
        """Verify duplication, quick creation, and deletion of specimens."""
        self.win.navigate_to_object("1001")
        initial_count = len(self.state.active_object_ids)

        # 1. Duplicate specimen 1001
        self.win.duplicate_current_specimen()
        dup_oid = self.state.current_object_id
        self.assertNotEqual(dup_oid, "1001")
        self.assertEqual(len(self.state.active_object_ids), initial_count + 1)
        self.assertEqual(str(self.state.df_reg.loc[dup_oid, "Genus"]), "Pinus")

        # 2. Quick create new object
        self.win.quick_create_new_object()
        created_oid = self.state.current_object_id
        self.assertNotEqual(created_oid, dup_oid)
        self.assertEqual(len(self.state.active_object_ids), initial_count + 2)

        # 3. Delete created object
        self.win.delete_current_specimen()
        self.assertNotIn(created_oid, self.state.active_object_ids)
        self.assertNotIn(created_oid, self.state.df_reg.index)
        self.assertEqual(len(self.state.active_object_ids), initial_count + 1)

        # 4. Delete duplicated object
        self.win.navigate_to_object(dup_oid)
        self.win.delete_current_specimen()
        self.assertNotIn(dup_oid, self.state.active_object_ids)
        self.assertEqual(len(self.state.active_object_ids), initial_count)

    def test_multi_selection_reviewed_and_clipboard(self):
        """Verify setting reviewed status on selection and copying accession ID."""
        self.win.navigate_to_object("1001")
        self.win.copy_current_accession_id()
        self.assertEqual(QApplication.clipboard().text(), "1001")

        # Mark reviewed for selection
        self.win.set_reviewed_for_selection(False)
        self.assertFalse(bool(self.state.df_obs.loc["1001", "Reviewed"]))

        self.win.set_reviewed_for_selection(True)
        self.assertTrue(bool(self.state.df_obs.loc["1001", "Reviewed"]))

    def test_image_viewer_gallery_and_zoom(self):
        """Verify multi-photo gallery pagination, zoom, and rotation."""
        viewer = self.win.image_viewer
        self.assertIsNotNone(viewer)

        # Load specimen with images or mock image paths
        viewer.image_paths = ["https://example.com/photo1.jpg", "https://example.com/photo2.jpg"]
        viewer.current_image_index = 0
        viewer._update_counter_label()
        self.assertIn("1 / 2 images", viewer.lbl_count.text())

        # Next image
        viewer.next_image()
        self.assertEqual(viewer.current_image_index, 1)
        self.assertIn("2 / 2 images", viewer.lbl_count.text())

        # Wrap around to first image
        viewer.next_image()
        self.assertEqual(viewer.current_image_index, 0)

        # Previous image wrap
        viewer.prev_image()
        self.assertEqual(viewer.current_image_index, 1)

        # Zoom operations
        initial_zoom = viewer.zoom_factor
        viewer.zoom_in()
        self.assertGreater(viewer.zoom_factor, initial_zoom)
        viewer.zoom_out()
        self.assertAlmostEqual(viewer.zoom_factor, initial_zoom, places=2)

        # Rotation
        self.assertEqual(viewer.rotation_angle, 0)
        viewer.rotate_cw()
        self.assertEqual(viewer.rotation_angle, 90)
        viewer.rotate_ccw()
        self.assertEqual(viewer.rotation_angle, 0)

        # Reset view
        viewer.reset_view()
        self.assertEqual(viewer.zoom_factor, 1.0)
        self.assertEqual(viewer.rotation_angle, 0)

    def test_layout_toggles_and_preferences(self):
        """Verify panel toggles (F6, F7, F8) and splitter size saving."""
        # Left pane toggle
        initial_left_hidden = self.win.win.pane_left.isHidden()
        self.win.toggle_left_panel()
        self.assertNotEqual(self.win.win.pane_left.isHidden(), initial_left_hidden)
        self.win.toggle_left_panel()
        self.assertEqual(self.win.win.pane_left.isHidden(), initial_left_hidden)

        # Right pane toggle
        initial_right_hidden = self.win.win.pane_right.isHidden()
        self.win.toggle_registration_panel()
        self.assertNotEqual(self.win.win.pane_right.isHidden(), initial_right_hidden)
        self.win.toggle_registration_panel()
        self.assertEqual(self.win.win.pane_right.isHidden(), initial_right_hidden)

        # Middle pane toggle
        initial_center_hidden = self.win.win.pane_center.isHidden()
        self.win.toggle_image_panel()
        self.assertNotEqual(self.win.win.pane_center.isHidden(), initial_center_hidden)
        self.win.toggle_image_panel()
        self.assertEqual(self.win.win.pane_center.isHidden(), initial_center_hidden)

        # Preferences persistence
        self.win._save_window_preferences()
        import config
        prefs = config.load_prefs()
        self.assertIn("splitter_sizes", prefs)
        self.assertIn("location_in_center", prefs)


if __name__ == "__main__":
    unittest.main()
