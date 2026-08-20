import unittest
import tkinter as tk
from unittest.mock import MagicMock, patch
import config
from models import AppState

class TestHybridDockableRail(unittest.TestCase):
    def setUp(self):
        self.root = tk.Tk()
        self.root.withdraw()
        self.app = AppState()
        self.app.active_object_ids = ["1001", "1002"]
        self.app.df_reg = MagicMock()
        self.app.df_reg.__len__.return_value = 2

    def tearDown(self):
        try:
            self.root.destroy()
        except Exception:
            pass

    def test_theme_tokens_exist(self):
        self.assertIn("rail_bg", config.RAIL_THEME)
        self.assertIn("rail_width", config.RAIL_THEME)
        self.assertIn("drawer_bg", config.DRAWER_THEME)
        self.assertIn("anim_duration_ms", config.DRAWER_THEME)
        self.assertEqual(config.RAIL_THEME["rail_width"], 40)
        self.assertEqual(config.DRAWER_THEME["drawer_width"], 300)

    @patch("ui.main_window.ExcelRepository")
    def test_pin_toggle_and_drawer_actions(self, mock_repo):
        from ui.main_window import ObjectProgramUI
        
        mw = ObjectProgramUI(self.root, self.app)
        
        self.assertTrue(hasattr(mw, "left_pinned"))
        self.assertTrue(hasattr(mw, "rail_frame"))
        self.assertTrue(hasattr(mw, "drawer_overlay"))

        initial_pin = mw.left_pinned.get()
        mw.toggle_left_pin()
        self.assertEqual(mw.left_pinned.get(), not initial_pin)

        if mw.left_pinned.get():
            mw.toggle_left_pin()
        self.assertFalse(mw.left_pinned.get())

        mw.toggle_floating_drawer()
        self.assertTrue(mw._drawer_is_open)

        mw.close_drawer()
        self.assertFalse(mw._drawer_is_open)

    @patch("ui.main_window.ExcelRepository")
    def test_interruptible_animation(self, mock_repo):
        from ui.main_window import ObjectProgramUI
        mw = ObjectProgramUI(self.root, self.app)
        mw.left_pinned.set(False)

        mw.open_drawer()
        self.assertTrue(mw._drawer_is_open)

        mw.close_drawer()
        self.assertFalse(mw._drawer_is_open)

    @patch("ui.main_window.ExcelRepository")
    def test_control_f_and_control_l_shortcuts(self, mock_repo):
        from ui.main_window import ObjectProgramUI
        mw = ObjectProgramUI(self.root, self.app)
        mw.left_pinned.set(False)

        # Test Ctrl+F (focus_search) opens drawer when unpinned
        mw.focus_search()
        self.assertTrue(mw._drawer_is_open)

        # Test toggle_floating_drawer_shortcut closes it when called again
        mw.toggle_floating_drawer_shortcut()
        self.assertFalse(mw._drawer_is_open)

        # Test calling toggle_floating_drawer_shortcut again opens drawer
        mw.toggle_floating_drawer_shortcut()
        self.assertTrue(mw._drawer_is_open)

if __name__ == "__main__":
    unittest.main()
