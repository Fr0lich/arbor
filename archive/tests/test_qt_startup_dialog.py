"""Unit tests for QtStartupDialog controller."""
import os
import sys
import unittest

from PySide6.QtWidgets import QApplication

from models import AppState
from ui_qt.startup_dialog import QtStartupDialog

app = QApplication.instance() or QApplication(sys.argv)


class TestQtStartupDialog(unittest.TestCase):

    def setUp(self):
        self.app_state = AppState()
        self.dialog = QtStartupDialog(app_state=self.app_state)

    def test_dialog_loaded(self):
        self.assertIsNotNone(self.dialog.win)
        self.assertEqual(self.dialog.win.objectName(), "StartupDialog")

    def test_image_mode_toggling(self):
        self.dialog.set_image_mode("online")
        self.assertEqual(self.dialog.image_mode_val, "online")
        self.assertTrue(self.dialog.win.folder_picker_container.isHidden())

        self.dialog.set_image_mode("folder")
        self.assertEqual(self.dialog.image_mode_val, "folder")
        self.assertFalse(self.dialog.win.folder_picker_container.isHidden())

        self.dialog.set_image_mode("offline")
        self.assertEqual(self.dialog.image_mode_val, "offline")
        self.assertTrue(self.dialog.win.folder_picker_container.isHidden())

    def test_launch_state_refresh(self):
        # Empty path should disable launch button
        self.dialog.win.input_db_path.setText("")
        self.dialog._refresh_launch_state()
        self.assertFalse(self.dialog.win.btn_launch.isEnabled())
        self.assertIn("Please select", self.dialog.win.lbl_status.text())

        # Existing file path should enable launch button
        existing_path = os.path.abspath(__file__)
        self.dialog.win.input_db_path.setText(existing_path)
        self.dialog._refresh_launch_state()
        self.assertTrue(self.dialog.win.btn_launch.isEnabled())
        self.assertEqual(self.dialog.win.lbl_status.text(), "Ready to launch!")


if __name__ == "__main__":
    unittest.main()
