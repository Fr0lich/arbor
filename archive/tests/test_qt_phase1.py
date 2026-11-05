"""Comprehensive unit tests for Phase 1 PySide6 dialogs."""
import os
import sys
import tempfile
import unittest

from PySide6.QtWidgets import QApplication

from models import AppState
from ui_qt.help_dialogs import QtKeyboardShortcutsDialog, QtUserGuideDialog
from ui_qt.ignored_words_dialog import QtIgnoredWordsDialog
from ui_qt.loading_dialog import QtLoadingDialog
from ui_qt.log_viewer import QtErrorLogDialog
from ui_qt.startup_dialog import QtStartupDialog

app = QApplication.instance() or QApplication(sys.argv)


class TestPhase1Dialogs(unittest.TestCase):

    def test_startup_dialog(self):
        state = AppState()
        dialog = QtStartupDialog(app_state=state)
        self.assertIsNotNone(dialog.win)
        self.assertEqual(dialog.win.objectName(), "StartupDialog")

    def test_user_guide_dialog(self):
        dlg = QtUserGuideDialog()
        self.assertTrue(len(dlg.browser.toPlainText()) > 0)

    def test_shortcuts_dialog(self):
        dlg = QtKeyboardShortcutsDialog()
        self.assertGreater(dlg.table.rowCount(), 5)
        # Test filtering
        dlg._filter_table("Save")
        visible_count = sum(not dlg.table.isRowHidden(r) for r in range(dlg.table.rowCount()))
        self.assertGreaterEqual(visible_count, 1)

    def test_error_log_dialog(self):
        with tempfile.NamedTemporaryFile("w+", delete=False, suffix=".log") as f:
            f.write("2026-10-05 [INFO] App started\n2026-10-05 [ERROR] Sample test failure\n")
            temp_path = f.name

        try:
            dlg = QtErrorLogDialog(log_path=temp_path)
            self.assertIn("Sample test failure", dlg.text_area.toPlainText())
            dlg._filter_log("ERROR")
            self.assertIn("ERROR", dlg.text_area.toPlainText())
            self.assertNotIn("INFO", dlg.text_area.toPlainText())
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)

    def test_ignored_words_dialog(self):
        with tempfile.NamedTemporaryFile("w+", delete=False, suffix=".json") as f:
            f.write('{"words": ["cultivar", "forma"], "variations": true}')
            temp_path = f.name

        try:
            dlg = QtIgnoredWordsDialog(file_path=temp_path)
            self.assertEqual(dlg.list_widget.count(), 2)
            self.assertTrue(dlg.chk_variations.isChecked())

            # Add word
            dlg.input_word.setText("subspecies")
            dlg._add_word()
            self.assertEqual(dlg.list_widget.count(), 3)

            # Save
            dlg._save_and_close()
            with open(temp_path, "r", encoding="utf-8") as f:
                saved = f.read()
            self.assertIn("subspecies", saved)
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)

    def test_loading_dialog(self):
        dlg = QtLoadingDialog()
        dlg.set_status("Parsing records...")
        self.assertEqual(dlg.lbl_status.text(), "Parsing records...")
        dlg.set_progress(50)
        self.assertEqual(dlg.progress_bar.value(), 50)
        dlg.set_indeterminate(True)
        self.assertEqual(dlg.progress_bar.maximum(), 0)


if __name__ == "__main__":
    unittest.main()
