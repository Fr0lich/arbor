"""Unit and integration tests for QtFilterDialog and main window filter integration."""
import os
import sys
import unittest
import pandas as pd
from PySide6.QtWidgets import QApplication

from models import AppState
from ui_qt.filter_dialog import QtFilterDialog, QtTriStateRow
from ui_qt.main_window import QtMainWindow

_APP = QApplication.instance() or QApplication(sys.argv)


class TestQtFilterDialog(unittest.TestCase):
    def setUp(self):
        self.state = AppState()
        self.state.df_reg = pd.DataFrame(
            {
                "Genus": ["Pinus", "Betula", "Abies", "Quercus"],
                "Species": ["sylvestris", "pendula", "alba", "robur"],
                "Building": ["Herbarium", "Herbarium", "Annex", "Herbarium"],
                "Cabinet": ["C1", "C2", "C1", "C3"],
            },
            index=["101", "102", "103", "104"],
        )
        self.state.df_obs = pd.DataFrame(
            {
                "Reviewed": [True, False, False, True],
                "Taxonomy_Problem": [False, True, False, False],
                "Images_Missing": [False, True, False, False],
            },
            index=["101", "102", "103", "104"],
        )
        self.state.active_object_ids = ["101", "102", "103", "104"]

    def test_tristate_row_cycling(self):
        row = QtTriStateRow("test_key", "Test Property")
        self.assertEqual(row.state, "Ignore")

        # Forward cycle: Ignore -> Has -> Not -> Ignore
        row.cycle(1)
        self.assertEqual(row.state, "Has")
        self.assertEqual(row.btn_indicator.text(), "✓")
        self.assertEqual(row.lbl_badge.text(), "HAS (✓)")

        row.cycle(1)
        self.assertEqual(row.state, "Not")
        self.assertEqual(row.btn_indicator.text(), "−")
        self.assertEqual(row.lbl_badge.text(), "NOT (−)")

        row.cycle(1)
        self.assertEqual(row.state, "Ignore")
        self.assertEqual(row.btn_indicator.text(), " ")
        self.assertEqual(row.lbl_badge.text(), "IGNORE")

        # Backward cycle: Ignore -> Not -> Has -> Ignore
        row.cycle(-1)
        self.assertEqual(row.state, "Not")
        row.cycle(-1)
        self.assertEqual(row.state, "Has")

    def test_dialog_tabs_and_rows_initialization(self):
        dlg = QtFilterDialog(app_state=self.state)
        # Verify 4 tabs exist
        tabs = dlg.dialog.tabs_filter
        self.assertEqual(tabs.count(), 4)
        tab_titles = [tabs.tabText(i) for i in range(tabs.count())]
        self.assertIn("Status & General", tab_titles)
        self.assertIn("Problems & History", tab_titles)
        self.assertIn("Images", tab_titles)
        self.assertIn("Location", tab_titles)

        # Verify key rows exist
        self.assertIn("Reviewed", dlg.rows)
        self.assertIn("Has_Images", dlg.rows)
        self.assertIn("Any_Problem", dlg.rows)
        self.assertIn("Building", dlg.location_inputs)

    def test_live_search_row_filtering(self):
        dlg = QtFilterDialog(app_state=self.state)
        rev_row = dlg.rows["Reviewed"]
        comment_row = dlg.rows["Has_Comment"]

        # Search for "reviewed"
        dlg.dialog.input_filter_search.setText("reviewed")
        self.assertFalse(rev_row.isHidden())
        self.assertTrue(comment_row.isHidden())

        # Clear search
        dlg.dialog.input_filter_search.setText("")
        self.assertFalse(rev_row.isHidden())
        self.assertFalse(comment_row.isHidden())

    def test_apply_filter_has_reviewed(self):
        applied = []
        dlg = QtFilterDialog(app_state=self.state, on_apply=lambda res: applied.append(res))
        dlg.rows["Reviewed"].set_state("Has")
        dlg.apply_filter()

        self.assertEqual(len(applied), 1)
        # 101 and 104 are Reviewed=True
        self.assertEqual(applied[0], ["101", "104"])
        self.assertEqual(self.state.active_object_ids, ["101", "104"])

    def test_apply_filter_not_reviewed(self):
        applied = []
        dlg = QtFilterDialog(app_state=self.state, on_apply=lambda res: applied.append(res))
        dlg.rows["Reviewed"].set_state("Not")
        dlg.apply_filter()

        self.assertEqual(len(applied), 1)
        # 102 and 103 are Reviewed=False
        self.assertEqual(applied[0], ["102", "103"])

    def test_clear_filter(self):
        dlg = QtFilterDialog(app_state=self.state)
        dlg.rows["Reviewed"].set_state("Has")
        dlg.location_inputs["Building"].setText("Herbarium")

        dlg.clear_filter(show_feedback=False)
        self.assertEqual(dlg.rows["Reviewed"].state, "Ignore")
        self.assertEqual(dlg.location_inputs["Building"].text(), "")

    def test_main_window_filter_integration(self):
        main_win = QtMainWindow(self.state)
        # Initially all 4 items present in tree
        self.assertEqual(main_win.win.tree_objects.topLevelItemCount(), 4)

        # Apply filter for Reviewed = Has
        main_win.on_filter_applied(["101", "104"])
        self.assertEqual(main_win.win.tree_objects.topLevelItemCount(), 2)
        self.assertIn("Filter active: 2 of 4 objects", main_win.win.lbl_filter_status.text())

        # Clear filter
        main_win.clear_filter()
        self.assertEqual(main_win.win.tree_objects.topLevelItemCount(), 4)
        self.assertEqual(main_win.win.lbl_filter_status.text(), "")


if __name__ == "__main__":
    unittest.main()
