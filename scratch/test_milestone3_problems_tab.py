"""scratch/test_milestone3_problems_tab.py

Automated verification harness for Milestone 3:
  - Problems Tab Checklist (tab_problems)
  - Amber Problem Tints and Bidirectional Synchronization with Registration form (tab_general)
  - Exclusion of Images_Missing from Problem Queue Detection
  - Status Bar Metrics & Active Position Index
"""

import os
import sys
import unittest
import pandas as pd

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from PySide6.QtWidgets import QApplication
from models import AppState
from repository import REVIEWED_COLUMN
from ui_qt.main_window import QtMainWindow
from ui_qt.problem_queue import QtProblemQueueDialog


class TestMilestone3ProblemsTab(unittest.TestCase):
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

    def test_3_1_problems_tab_checklist_and_summary_rendering(self):
        """Test that tab_problems renders checkboxes and summary for specimen."""
        problems_panel = self.main_window.problems_panel
        self.assertIsNotNone(problems_panel, "QtProblemsPanel should be instantiated in tab_problems")

        # Verify all config problems have corresponding checkboxes
        cfg_problems = self.app_state.config.get("ui_sections", {}).get("problems", [])
        for p in cfg_problems:
            p_name = p.get("name")
            self.assertIn(p_name, problems_panel.problem_cbs, f"Checkbox for {p_name} must exist")

        # Select specimen '1003' (has Genus_Problem = True in mock_current_db)
        self.main_window.navigate_to_object("1003")

        # Checkboxes should reflect df_obs state
        self.assertTrue(problems_panel.problem_cbs["Genus_Problem"].isChecked(), "Genus_Problem checkbox should be checked")
        self.assertFalse(problems_panel.problem_cbs["Species_Problem"].isChecked(), "Species_Problem checkbox should be unchecked")
        self.assertFalse(problems_panel.problem_cbs["PlantPart_Problem"].isChecked(), "PlantPart_Problem should be unchecked")

        # Tab text should show count
        tab_text = self.main_window.win.tabs_registration.tabText(1)
        self.assertIn("Problems (1)", tab_text, f"Tab header should display active count: {tab_text}")

        # Status badge should show problem count
        badge_text = self.main_window.win.lbl_status_badge.text()
        self.assertIn("1 PROBLEM", badge_text, f"Status badge should display '1 PROBLEM', got '{badge_text}'")

        # Summary layout should contain 1 warning row
        active = problems_panel.get_active_problems()
        self.assertEqual(active, ["Genus_Problem"])
        self.assertEqual(problems_panel.summary_layout.count(), 1)

    def test_3_2_amber_problem_tints_and_card_badges(self):
        """Test amber problem highlight tints on registration fields in tab_general."""
        reg_panel = self.main_window.registry_panel
        self.assertIsNotNone(reg_panel)

        # Select specimen '1003' (Genus_Problem flagged)
        self.main_window.navigate_to_object("1003")

        # Genus widget should have amber background style
        genus_widget = reg_panel.reg_entries.get("Genus")
        species_widget = reg_panel.reg_entries.get("Species")
        family_widget = reg_panel.reg_entries.get("Family")

        self.assertIn("#fef9e7", genus_widget.styleSheet(), "Genus widget should be tinted amber")
        self.assertIn("#d9a036", genus_widget.styleSheet(), "Genus widget should have amber border")
        self.assertNotIn("#fef9e7", species_widget.styleSheet(), "Species widget should NOT be tinted")
        self.assertNotIn("#fef9e7", family_widget.styleSheet(), "Family widget should NOT be tinted")

        # Taxonomy card header badge should show count
        tax_card = reg_panel.cards.get("group_0") or reg_panel.cards.get("taxonomy")
        self.assertIsNotNone(tax_card)
        self.assertTrue(tax_card.header.lbl_badge.isVisible())
        self.assertIn("1 PROBLEM", tax_card.header.lbl_badge.text())

    def test_3_3_bidirectional_toggle_synchronization(self):
        """Test that toggling a checkbox in tab_problems synchronizes tab_general and df_obs."""
        self.main_window.navigate_to_object("1003")
        problems_panel = self.main_window.problems_panel
        reg_panel = self.main_window.registry_panel

        # Currently 1003 has Genus_Problem = True. Uncheck it in tab_problems
        problems_panel.problem_cbs["Genus_Problem"].setChecked(False)

        # df_obs should be updated
        self.assertFalse(self.app_state.df_obs.loc["1003", "Genus_Problem"])
        self.assertTrue(self.app_state.dirty)

        # Inline checkbox in tab_general should also be unchecked
        self.assertFalse(reg_panel.problem_cbs["Genus_Problem"].isChecked())

        # Genus widget amber tint should be removed
        genus_widget = reg_panel.reg_entries.get("Genus")
        self.assertNotIn("#fef9e7", genus_widget.styleSheet(), "Amber tint should be removed when problem is unflagged")

        # Tab text should now show Problems without count
        tab_text = self.main_window.win.tabs_registration.tabText(1)
        self.assertEqual("Problems", tab_text)

        # Now toggle inline checkbox in tab_general for Species_Problem
        reg_panel.problem_cbs["Species_Problem"].setChecked(True)

        # tab_problems checkbox should now be checked
        self.assertTrue(problems_panel.problem_cbs["Species_Problem"].isChecked())
        self.assertTrue(self.app_state.df_obs.loc["1003", "Species_Problem"])

        # Tab text should show Problems (1)
        tab_text = self.main_window.win.tabs_registration.tabText(1)
        self.assertIn("Problems (1)", tab_text)

        # Species widget in tab_general should now be tinted amber
        species_widget = reg_panel.reg_entries.get("Species")
        self.assertIn("#fef9e7", species_widget.styleSheet(), "Species widget should now be tinted amber")

    def test_3_4_problem_queue_excludes_images_missing(self):
        """Verify that _detect_problem_queue excludes specimens whose only issue is Images_Missing."""
        # Create a clean record that ONLY has Images_Missing = True
        df_obs = self.app_state.df_obs
        df_obs.at["1001", "Images_Missing"] = True
        for col in df_obs.columns:
            if col.endswith("_Problem") or col == "Other_problem":
                df_obs.at["1001", col] = False

        dlg = QtProblemQueueDialog(parent=None, app_state=self.app_state)
        queue_oids = dlg.queue_ctrl.oid_queue

        # '1001' must NOT be in the problem queue
        self.assertNotIn("1001", queue_oids, "Specimens with ONLY Images_Missing must NOT enter problem queue")

        # '1003' (which has Genus_Problem) MUST be in the problem queue
        self.assertIn("1003", queue_oids, "Specimens with real problem flags must enter problem queue")

    def test_3_5_status_bar_metrics_and_position_index(self):
        """Verify status bar object counts, reviewed stats, problem count, and specimen index."""
        # Active position indicator
        self.main_window.navigate_to_object("1001")
        id_badge_text = self.main_window.win.lbl_id_badge.text()
        self.assertIn("ID: 1001 (1 of 25)", id_badge_text, f"ID badge should show position index, got '{id_badge_text}'")

        self.main_window.navigate_to_object("1005")
        id_badge_text = self.main_window.win.lbl_id_badge.text()
        self.assertIn("ID: 1005 (5 of 25)", id_badge_text, f"ID badge should show position index, got '{id_badge_text}'")

        # Status bar counters
        self.main_window.update_status_bar()
        self.assertIn("OBJECTS: 25", self.main_window.win.lbl_sb_object_count.text())
        self.assertIn("REVIEWED:", self.main_window.win.lbl_sb_reviewed.text())
        self.assertIn("PROBLEMS:", self.main_window.win.lbl_sb_problems.text())


if __name__ == "__main__":
    unittest.main()
