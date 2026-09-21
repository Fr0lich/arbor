"""
tests/test_sandbox_tutorials.py

Unit tests for sandboxed interactive tutorials:
- Sandbox state snapshot and zero-disk restore
- TutorialRunner HUD creation and step progression
- Review, Discrepancy, and Database tutorial flows
"""

import unittest
import tkinter as tk
import pandas as pd
from models import AppState
from ui.tutorials import (
    SandboxManager,
    TutorialRunner,
    ActionStep,
    start_review_tutorial,
    start_discrepancy_tutorial,
    start_database_tutorial
)


class MockUI:
    def __init__(self, root):
        self.root = root
        self.app = AppState()
        self.app.excel_path = "C:/fake/real_database.xlsx"
        self.app.config_name = "Standard"
        self.app.config = {"name": "Standard"}
        self.app.df_reg = pd.DataFrame([{"ObjectID": "999", "Taxon": "Real Specimen"}]).set_index("ObjectID", drop=False)
        self.app.df_obs = pd.DataFrame([{"ObjectID": "999"}]).set_index("ObjectID", drop=False)
        self.app.df_photo = pd.DataFrame()
        self.app.df_log = pd.DataFrame()
        self.app.df_unvalidated = pd.DataFrame()
        self.app.current_object_id = "999"
        self.current_id = "999"

        # Mock UI elements
        self.search_entry = tk.Entry(root)
        self.search_entry.tutorial_id = "search_entry"
        self.object_editor_frame = tk.Frame(root)
        self.object_editor_frame.tutorial_id = "object_editor_frame"
        self.history_btn = tk.Button(root, text="History")
        self.reviewed_button = tk.Button(root, text="Mark Reviewed")
        self.reviewed_button.tutorial_id = "reviewed_button"
        self.reviewed_var = tk.BooleanVar(value=False)

    def _precompute_startup_caches(self, df_reg, df_obs, df_photo):
        pass

    def _finish_open_excel(self, path, output_path, df_reg, df_obs, df_photo, df_log, df_unval=None):
        self.app.excel_path = path
        self.app.df_reg = df_reg
        self.app.df_obs = df_obs
        self.app.df_photo = df_photo
        self.app.df_log = df_log
        self.app.df_unvalidated = df_unval


class TestSandboxTutorials(unittest.TestCase):
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
        self.ui = MockUI(self.root)
        self.sm = SandboxManager()
        # Reset singleton state
        self.sm.is_sandboxed = False
        self.sm.snapshot = None

    def tearDown(self):
        if self.sm.is_sandboxed:
            self.sm.exit_sandbox(self.ui)

    def test_sandbox_enter_and_exit_isolation(self):
        orig_path = self.ui.app.excel_path
        orig_id = self.ui.app.current_object_id

        # 1. Enter sandbox
        self.sm.enter_sandbox(self.ui, mock_type="review")
        self.assertTrue(self.sm.is_sandboxed)
        self.assertEqual(self.ui.app.excel_path, "[Tutorial Sandbox]")
        # Sandbox must contain mock specimen 1001
        self.assertIn("1001", self.ui.app.df_reg.index)

        # 2. Mutate sandbox state (simulate user doing tutorial work)
        self.ui.app.df_reg.loc["1001", "Reviewed"] = True

        # 3. Exit sandbox
        self.sm.exit_sandbox(self.ui)
        self.assertFalse(self.sm.is_sandboxed)
        self.assertEqual(self.ui.app.excel_path, orig_path)
        self.assertIn("999", self.ui.app.df_reg.index)
        self.assertNotIn("1001", self.ui.app.df_reg.index)

    def test_tutorial_runner_step_progression(self):
        step1 = ActionStep(
            step_id="s1",
            title="Step One",
            instruction="Test instruction 1",
            action_hint="Hint 1"
        )
        step2 = ActionStep(
            step_id="s2",
            title="Step Two",
            instruction="Test instruction 2",
            action_hint="Hint 2"
        )

        runner = TutorialRunner(self.ui, [step1, step2], tutorial_name="Test Runner")
        self.assertIsNotNone(runner.hud_win)
        self.assertEqual(runner.current_idx, 0)
        self.assertEqual(runner.title_lbl.cget("text"), "Step One")

        # Skip to step 2
        runner.next_step()
        self.assertEqual(runner.current_idx, 1)
        self.assertEqual(runner.title_lbl.cget("text"), "Step Two")

        # Go back to step 1
        runner.prev_step()
        self.assertEqual(runner.current_idx, 0)

        # Exit tutorial cleans up HUD
        runner.exit_tutorial()
        self.assertIsNone(runner.hud_win)

    def test_start_review_tutorial(self):
        runner = start_review_tutorial(self.ui)
        self.assertTrue(self.sm.is_sandboxed)
        self.assertEqual(len(runner.steps), 5)
        self.assertEqual(runner.steps[0].step_id, "select_object")
        self.assertEqual(runner.steps[3].step_id, "mark_reviewed")

        runner.exit_tutorial()
        self.assertFalse(self.sm.is_sandboxed)

    def test_start_discrepancy_tutorial(self):
        runner = start_discrepancy_tutorial(self.ui)
        self.assertTrue(self.sm.is_sandboxed)
        self.assertEqual(len(runner.steps), 5)
        self.assertEqual(runner.steps[0].step_id, "open_resolver")
        self.assertEqual(runner.steps[3].step_id, "apply_changes")

        runner.exit_tutorial()
        self.assertFalse(self.sm.is_sandboxed)

    def test_start_database_tutorial(self):
        runner = start_database_tutorial(self.ui)
        self.assertTrue(self.sm.is_sandboxed)
        self.assertEqual(len(runner.steps), 4)
        self.assertEqual(runner.steps[0].step_id, "open_db_wizard")
        self.assertEqual(runner.steps[1].step_id, "add_new_object")

        runner.exit_tutorial()
        self.assertFalse(self.sm.is_sandboxed)


if __name__ == "__main__":
    unittest.main()
