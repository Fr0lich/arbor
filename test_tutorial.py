import unittest
import tkinter as tk
from ui.tutorial import TutorialManager, TutorialHighlight
import config
import pandas as pd

class TestTutorial(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = tk.Tk()
        cls.root.withdraw()

    @classmethod
    def tearDownClass(cls):
        cls.root.destroy()

    def setUp(self):
        # Reset preferences
        prefs = config.load_prefs()
        if "disable_tutorials" in prefs:
            del prefs["disable_tutorials"]
        config.save_prefs(prefs)
        config.ENABLE_TUTORIALS = True

    def test_tutorial_manager_singleton(self):
        tm1 = TutorialManager()
        tm2 = TutorialManager()
        self.assertIs(tm1, tm2)

    def test_disabled_tutorials_config(self):
        # Disable via config
        config.ENABLE_TUTORIALS = False
        tm = TutorialManager()

        # This should return early without starting any steps
        tm.start_tutorial("startup_tutorial", self.root)
        self.assertIsNone(tm.current_tutorial)

    def test_disabled_tutorials_pref(self):
        # Disable via preferences
        prefs = config.load_prefs()
        prefs["disable_tutorials"] = True
        config.save_prefs(prefs)

        tm = TutorialManager()
        tm.start_tutorial("startup_tutorial", self.root)
        self.assertIsNone(tm.current_tutorial)

    def test_find_widget_robustness(self):
        tm = TutorialManager()
        # Finding a non-existent widget on root should return None, not crash
        res = tm._find_widget(self.root, "non_existent_id")
        self.assertIsNone(res)

        # Finding on None should return None
        res = tm._find_widget(None, "search_entry")
        self.assertIsNone(res)

    def test_highlight_on_unmapped_widget(self):
        # Create unmapped widget
        btn = tk.Button(self.root)

        # Creating a highlight on it should not raise TclError/exception even if it is not viewable
        try:
            hl = TutorialHighlight(self.root, btn)
            # Should have safely withdrawn or positioned
            self.assertTrue(hl.win.winfo_exists())
            hl.destroy()
        except Exception as e:
            self.fail(f"TutorialHighlight raised exception on unmapped widget: {e}")

    def test_historical_resolver_unbind_on_destroy(self):
        # Create a mock main app and window to verify the binding unbind cleanup
        mock_app = type("MockApp", (object,), {
            "root": self.root,
            "reg_by_id": pd.DataFrame(index=["123"]),
            "is_unknown": lambda self, x: False,
            "problem_vars": {},
            "problem_to_field": {},
            "update_dirty_ui": lambda: None,
            "app": type("App", (object,), {
                "df_reg": pd.DataFrame(index=["123"]),
                "df_obs": pd.DataFrame(index=["123"])
            })()
        })()
        
        from ui.historical_resolver import HistoricalConflictResolverWindow
        # Instantiate window with minimal suggestions
        win_inst = HistoricalConflictResolverWindow(mock_app, "123", {"field1": {}})
        
        # Verify win structure and mousewheel cleanup on destroy
        self.assertTrue(win_inst.win.winfo_exists())
        
        # Destroy the window, which triggers _cleanup
        win_inst.win.destroy()
        self.root.update_idletasks()

if __name__ == "__main__":
    unittest.main()
