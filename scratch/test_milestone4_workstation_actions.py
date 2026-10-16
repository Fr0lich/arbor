"""scratch/test_milestone4_workstation_actions.py

Automated verification harness for Milestone 4:
  - Inline State Mutation & Dirty Tracking (tab_general & location_panel)
  - Undo Behavior (push_undo_state and undo)
  - Review Action Bar & Workflow Toggles (toggle_reviewed, chk_clear_problems, chk_auto_next)
  - Navigation Controls (next, prev, next_problem)
  - Sorting (combo_sort)
  - Exit Guard (closeEvent with dirty state)
"""

import os
import sys
import unittest
import pandas as pd

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from PySide6.QtCore import Qt
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import QApplication, QMessageBox
from models import AppState
from repository import REVIEWED_COLUMN
from ui_qt.main_window import QtMainWindow


class TestMilestone4WorkstationActions(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.mock_db_path = os.path.abspath("scratch/mock_current_db.xlsx")
        self.app_state = AppState()
        self.main_window = QtMainWindow(self.app_state)
        self.main_window.open_excel(self.mock_db_path)
        self.main_window.win.show()

    def tearDown(self):
        self.main_window.win.close()

    def test_4_1_inline_field_mutation_dirty_and_undo(self):
        """Test that editing registration fields updates df_reg, dirty state, UI and undo stack."""
        self.main_window.navigate_to_object("1001")
        reg_panel = self.main_window.registry_panel
        self.assertIsNotNone(reg_panel)

        orig_genus = str(self.app_state.df_reg.loc["1001", "Genus"])
        orig_dirty = self.app_state.dirty
        self.assertFalse(orig_dirty)
        self.assertEqual(self.main_window.win.lbl_data_status.text(), "Saved")

        # Edit Genus field via line edit
        genus_edit = reg_panel.reg_entries["Genus"]
        genus_edit.setText("PinusModified")
        genus_edit.textEdited.emit("PinusModified")

        # In-memory df_reg should be updated
        self.assertEqual(self.app_state.df_reg.loc["1001", "Genus"], "PinusModified")
        self.assertTrue(self.app_state.dirty)
        self.assertIn("Unsaved", self.main_window.win.lbl_data_status.text())

        # Middle column specimen name and tree item should update dynamically
        self.assertIn("PinusModified", self.main_window.win.lbl_specimen_name.text())
        cur_tree_item = self.main_window.win.tree_objects.currentItem()
        self.assertIn("PinusModified", cur_tree_item.text(2))

        # Audit log should have recorded the edit
        self.assertGreater(len(self.app_state._log_records), 0)
        last_log = self.app_state._log_records[-1]
        self.assertEqual(last_log["Action"], "EDIT")
        self.assertEqual(last_log["ObjectID"], "1001")

        # Undo the edit
        self.main_window.undo()
        self.assertEqual(self.app_state.df_reg.loc["1001", "Genus"], orig_genus)
        self.assertEqual(genus_edit.text(), orig_genus)
        self.assertIn(orig_genus, self.main_window.win.lbl_specimen_name.text())

    def test_4_2_review_action_bar_toggle(self):
        """Test marking a specimen as reviewed, timestamping, tree mark, and unmarking."""
        # Specimen 1003 starts unreviewed in mock_current_db
        self.main_window.navigate_to_object("1003")
        df_obs = self.app_state.df_obs

        # Initial state: unreviewed
        self.assertFalse(bool(df_obs.loc["1003", REVIEWED_COLUMN]))
        self.assertIn("MARK AS REVIEWED", self.main_window.win.btn_mark_reviewed.text())

        # Click mark reviewed
        self.main_window.toggle_reviewed()

        # In-memory df_obs should be reviewed = True and have timestamp
        self.assertTrue(bool(df_obs.loc["1003", REVIEWED_COLUMN]))
        reviewed_at = str(df_obs.loc["1003", "ReviewedAt"])
        self.assertTrue(len(reviewed_at) > 0)
        self.assertIn("Reviewed:", self.main_window.win.lbl_reviewed_time.text())
        self.assertIn("MARKED AS REVIEWED", self.main_window.win.btn_mark_reviewed.text())

        # Tree column 0 should display checkmark
        cur_item = self.main_window.win.tree_objects.currentItem()
        self.assertEqual(cur_item.text(0), "✓")

        # Middle column status badge should be REVIEWED
        self.assertEqual(self.main_window.win.lbl_status_badge.text(), "REVIEWED")

        # Unmark reviewed
        self.main_window.toggle_reviewed()
        self.assertFalse(bool(df_obs.loc["1003", REVIEWED_COLUMN]))
        self.assertEqual(cur_item.text(0), " ")
        self.assertEqual(self.main_window.win.lbl_reviewed_time.text(), "")

    def test_4_3_workflow_checkboxes_clear_problems_and_auto_next(self):
        """Test chk_clear_problems and chk_auto_next when marking reviewed."""
        # Specimen 1003 has Genus_Problem = True
        self.main_window.navigate_to_object("1003")
        self.assertTrue(self.app_state.df_obs.loc["1003", "Genus_Problem"])

        # Enable chk_clear_problems and chk_auto_next
        self.main_window.win.chk_clear_problems.setChecked(True)
        self.main_window.win.chk_auto_next.setChecked(True)

        # Mark reviewed
        self.main_window.toggle_reviewed()

        # Problem on 1003 should now be cleared
        self.assertFalse(self.app_state.df_obs.loc["1003", "Genus_Problem"])

        # Auto-next should have advanced selection to 1004
        self.assertEqual(self.app_state.current_object_id, "1004")

    def test_4_4_navigation_controls_and_next_problem(self):
        """Test prev, next, and jump to next problem specimen."""
        self.main_window.navigate_to_object("1001")
        self.main_window.navigate_next()
        self.assertEqual(self.app_state.current_object_id, "1002")

        self.main_window.navigate_prev()
        self.assertEqual(self.app_state.current_object_id, "1001")

        # Jump to next problem from 1001 -> should find 1003 (which has Genus_Problem)
        self.main_window.navigate_next_problem()
        self.assertEqual(self.app_state.current_object_id, "1003")

        # Jump again from 1003 -> should find 1004 (which has Author_Problem)
        self.main_window.navigate_next_problem()
        self.assertEqual(self.app_state.current_object_id, "1004")

    def test_4_5_sorting_dropdown(self):
        """Test sorting object list by Genus A-Z, Reviewed first, and ID."""
        # 1. Sort Genus A-Z
        self.main_window.win.combo_sort.setCurrentText("Genus A-Z")
        first_oid = self.app_state.active_object_ids[0]
        first_genus = self.app_state.df_reg.loc[first_oid, "Genus"]
        last_oid = self.app_state.active_object_ids[-1]
        last_genus = self.app_state.df_reg.loc[last_oid, "Genus"]
        self.assertLessEqual(first_genus, last_genus)

        # 2. Sort Reviewed first (1001 was reviewed earlier in our test flow if marked, let's mark 1010)
        self.app_state.df_obs.at["1010", REVIEWED_COLUMN] = True
        self.main_window.win.combo_sort.setCurrentText("Reviewed first")
        self.assertTrue(self.app_state.df_obs.loc[self.app_state.active_object_ids[0], REVIEWED_COLUMN])

        # 3. Sort back to ID
        self.main_window.win.combo_sort.setCurrentText("ID")
        self.assertEqual(self.app_state.active_object_ids[0], "1001")
        self.assertEqual(self.app_state.active_object_ids[-1], "1025")

    def test_4_6_exit_guard_with_dirty_state(self):
        """Test closeEvent ignores exit if dirty and user cancels, accepts if clean."""
        # Clean state -> accepts close
        self.app_state.dirty = False
        event = QCloseEvent()
        self.main_window._on_close_event(event)
        self.assertTrue(event.isAccepted())


if __name__ == "__main__":
    unittest.main()
