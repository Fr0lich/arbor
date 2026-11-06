"""Comprehensive unit tests for Command Palette, Fuzzy Search, Toasts, and UI shims."""

import os
import tempfile
import unittest
import pandas as pd

import utils
from backend.search import SearchEngine
from repository import REVIEWED_COLUMN, REVIEWED_AT_COLUMN


class TestFuzzySearchAndCommandPalette(unittest.TestCase):

    def test_fuzzy_score_exact_and_partial(self):
        score_exact = utils.fuzzy_score("Quercus", "Quercus")
        self.assertEqual(score_exact, 100.0)

        # Direct substring match
        score_sub = utils.fuzzy_score("Quercus", "Quercus robur L.")
        self.assertGreaterEqual(score_sub, 90.0)

        # Typo match
        score_typo = utils.fuzzy_score("Quercus rober", "Quercus robur")
        self.assertGreaterEqual(score_typo, 80.0)

    def test_fuzzy_extract(self):
        choices = ["Betula pendula", "Betula pubescens", "Quercus robur", "Pinus sylvestris"]
        matches = utils.fuzzy_extract("Betulla", choices, limit=2, score_cutoff=60.0)
        self.assertTrue(len(matches) > 0)
        top_match_name = matches[0][0]
        self.assertTrue(top_match_name.startswith("Betula"))

    def test_search_engine_fuzzy_fallback(self):
        engine = SearchEngine()
        index = {
            "101": {
                "id": "101",
                "genus_species": "quercus robur",
                "family": "fagaceae",
                "all": "101 quercus robur fagaceae oakwood"
            },
            "102": {
                "id": "102",
                "genus_species": "betula pendula",
                "family": "betulaceae",
                "all": "102 betula pendula betulaceae birch"
            }
        }

        # Exact match
        exact_results = engine.apply_search("quercus", index)
        self.assertEqual(exact_results, ["101"])

        # Misspelled match should trigger fuzzy fallback
        fuzzy_results = engine.apply_search("querkus rober", index)
        self.assertIn("101", fuzzy_results)

    def test_toast_manager(self):
        import tkinter as tk
        from ui.toast import ToastManager
        try:
            root = tk.Tk()
            root.withdraw()
            ToastManager.show(root, "Specimen verified", toast_type="success", duration_ms=100)
            self.assertIsNotNone(ToastManager._active_toast)
            ToastManager.dismiss()
            self.assertIsNone(ToastManager._active_toast)
            root.destroy()
        except tk.TclError:
            pass  # Headless display environment without virtual display

    def test_command_palette_structure(self):
        import tkinter as tk
        from unittest.mock import MagicMock
        from ui.command_palette import CommandPalette
        try:
            root = tk.Tk()
            root.withdraw()
            mock_ui = MagicMock()
            mock_ui.root = root
            mock_ui.dark_mode_active = False
            mock_ui.app_state = None

            palette = CommandPalette(mock_ui)
            self.assertGreater(len(palette._commands_registry), 10)

            # Test command filtering
            palette.search_var.set("gbif")
            self.assertTrue(any("gbif" in item.get("label", "").lower() for item in palette._current_items))

            palette.destroy()
            root.destroy()
        except tk.TclError:
            pass  # Headless display environment without virtual display



    def test_object_program_ui_shims_and_tutorials(self):
        from ui.main_window import ObjectProgramUI
        from unittest.mock import MagicMock

        # Check required method signatures
        self.assertTrue(hasattr(ObjectProgramUI, "select_object_id"))
        self.assertTrue(hasattr(ObjectProgramUI, "open_bulk_edit"))
        self.assertTrue(hasattr(ObjectProgramUI, "open_unified_settings"))
        self.assertTrue(hasattr(ObjectProgramUI, "open_gbif_dialog"))
        self.assertTrue(hasattr(ObjectProgramUI, "start_tutorial_flow"))

        # Test start_tutorial_flow dispatch
        mock_ui = MagicMock(spec=ObjectProgramUI)
        ObjectProgramUI.start_tutorial_flow(mock_ui, None)
        mock_ui.open_help_window.assert_called_once()

    def test_command_palette_actions_executable(self):
        import tkinter as tk
        from unittest.mock import MagicMock
        from ui.command_palette import CommandPalette
        from ui.main_window import ObjectProgramUI

        try:
            root = tk.Tk()
            root.withdraw()
            mock_ui = MagicMock(spec=ObjectProgramUI)
            mock_ui.root = root
            mock_ui.dark_mode_active = False

            palette = CommandPalette(mock_ui)
            for item in palette._commands_registry:
                action = item.get("action")
                if callable(action):
                    # Should execute without throwing AttributeError
                    action()

            palette.destroy()
            root.destroy()
        except tk.TclError:
            pass

    def test_command_palette_specimen_search(self):
        import tkinter as tk
        from unittest.mock import MagicMock
        from ui.command_palette import CommandPalette

        try:
            root = tk.Tk()
            root.withdraw()
            mock_ui = MagicMock()
            mock_ui.root = root
            mock_ui.dark_mode_active = False

            # Setup mock_ui.app with df_reg
            mock_app = MagicMock()
            df_reg = pd.DataFrame(
                {"Genus": ["Betula", "Quercus"], "Species": ["pendula", "robur"]},
                index=["1042", "1043"]
            )
            mock_app.df_reg = df_reg
            mock_app.df_obs = None
            mock_ui.app = mock_app

            palette = CommandPalette(mock_ui)
            # Search by ID
            palette.search_var.set("1042")
            spec_matches = [i for i in palette._current_items if i.get("type") == "specimen"]
            self.assertTrue(len(spec_matches) > 0)
            self.assertEqual(spec_matches[0]["oid"], "1042")

            # Search by Taxon
            palette.search_var.set("Quercus")
            spec_matches2 = [i for i in palette._current_items if i.get("type") == "specimen"]
            self.assertTrue(len(spec_matches2) > 0)
            self.assertEqual(spec_matches2[0]["oid"], "1043")

            palette.destroy()
            root.destroy()
        except tk.TclError:
            pass


if __name__ == "__main__":
    unittest.main()
