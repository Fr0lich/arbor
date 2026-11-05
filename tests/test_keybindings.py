import tkinter as tk
import unittest
from unittest.mock import MagicMock
from ui.keybindings import KeybindingManager


class TestKeybindingManager(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = tk.Tk()
        cls.root.withdraw()

    @classmethod
    def tearDownClass(cls):
        try:
            cls.root.destroy()
        except Exception:
            pass

    def setUp(self):
        self.mock_ui = MagicMock()
        self.km = KeybindingManager(self.mock_ui, self.root)

    def test_bind_global_shortcuts(self):
        """Verify all global shortcuts bind cleanly onto the root window."""
        self.km.bind_global_shortcuts()
        bound = self.root.bind()

        # Check key navigation & action shortcuts in Tkinter's canonical internal string format
        expected_patterns = [
            "<Key-Left>", "<Key-Right>", "<Alt-Key-Left>", "<Alt-Key-Right>",
            "<Control-Key-n>", "<Control-Key-r>", "<Control-Key-s>",
            "<Control-Key-k>", "<Control-Key-f>", "<Control-Key-g>",
            "<Control-Key-h>", "<Control-Key-j>", "<Control-Key-p>",
            "<Control-Key-q>", "<Control-Key-z>", "<Control-Key-y>",
            "<Key-F1>", "<Key-F6>", "<Key-F7>", "<Key-F8>", "<Key-space>",
        ]
        for pattern in expected_patterns:
            self.assertIn(pattern, bound, f"Expected {pattern} to be bound to root window.")

    def test_bind_search_shortcuts(self):
        """Verify search entry specific bindings."""
        entry = tk.Entry(self.root)
        self.km.bind_search_shortcuts(entry)
        bound = entry.bind()
        self.assertIn("<KeyRelease>", bound)
        self.assertIn("<Key-Escape>", bound)
        self.assertIn("<Key-Return>", bound)
        entry.destroy()

    def test_bind_location_shortcuts(self):
        """Verify location entry specific bindings."""
        entry = tk.Entry(self.root)
        self.km.bind_location_shortcuts(entry)
        bound = entry.bind()
        self.assertIn("<Shift-Key-Up>", bound)
        self.assertIn("<Shift-Key-Down>", bound)
        self.assertIn("<Key-Return>", bound)
        entry.destroy()

    def test_bind_problem_shortcuts(self):
        """Verify problem checkbox specific bindings."""
        cb = tk.Checkbutton(self.root)
        self.km.bind_problem_shortcuts(cb)
        bound = cb.bind()
        self.assertIn("<Shift-Key-Up>", bound)
        self.assertIn("<Shift-Key-Down>", bound)
        self.assertIn("<Key-Return>", bound)
        cb.destroy()


if __name__ == "__main__":
    unittest.main()
