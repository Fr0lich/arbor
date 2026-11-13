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

    def test_command_palette_mousewheel_scrolling(self):
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

            # Verify canvas and items_frame were constructed
            self.assertIsNotNone(palette.canvas)
            self.assertIsNotNone(palette.items_frame)

            # Verify scrolltag from bind_mousewheel was applied to items_frame
            tag = f"ScrollTag_{id(palette.canvas)}"
            self.assertIn(tag, palette.items_frame.bindtags())

            # Verify canvas has bindings for MouseWheel and Linux Button-4/5
            canvas_bindings = palette.canvas.bind()
            self.assertIn("<MouseWheel>", canvas_bindings)
            self.assertIn("<Button-4>", canvas_bindings)
            self.assertIn("<Button-5>", canvas_bindings)

            # Verify no destructive global bind_all was placed on root
            root_bindings = root.bind()
            self.assertNotIn("<MouseWheel>", root_bindings)

            palette.destroy()
            root.destroy()
        except tk.TclError:
            pass

    def test_command_palette_card_view_presets_update_config(self):
        import tkinter as tk
        from unittest.mock import MagicMock
        import config
        from ui.command_palette import CommandPalette
        from ui.main_window import ObjectProgramUI

        try:
            root = tk.Tk()
            root.withdraw()
            mock_ui = MagicMock(spec=ObjectProgramUI)
            mock_ui.root = root
            mock_ui.dark_mode_active = False
            mock_ui.app_state = None
            mock_ui.object_list = MagicMock()
            mock_ui.show_toast = MagicMock()

            # Wire real card persona and toggle methods to mock_ui
            mock_ui.apply_card_persona = lambda name: ObjectProgramUI.apply_card_persona(mock_ui, name)
            mock_ui.apply_card_preset = lambda name: ObjectProgramUI.apply_card_preset(mock_ui, name)
            mock_ui.toggle_card_location_row = lambda: ObjectProgramUI.toggle_card_location_row(mock_ui)
            mock_ui.toggle_card_status_badges = lambda: ObjectProgramUI.toggle_card_status_badges(mock_ui)
            mock_ui.restore_default_card_settings = lambda: ObjectProgramUI.restore_default_card_settings(mock_ui)

            palette = CommandPalette(mock_ui)

            # Find all card commands
            card_commands = [c for c in palette._commands_registry if "card" in c.get("label", "").lower()]
            self.assertGreaterEqual(len(card_commands), 7)

            # Test 1: Compact Preset
            compact_cmd = next(c for c in palette._commands_registry if "compact" in c.get("label", "").lower() and "card layout" in c.get("label", "").lower())
            compact_cmd["action"]()
            prefs = config.get_directory_card_prefs()
            self.assertEqual(prefs["density_mode"], "compact")
            self.assertFalse(prefs["show_location_row"])
            mock_ui.show_toast.assert_called_with("Card View Preset: Compact")

            # Test 2: Full Detail Preset
            full_cmd = next(c for c in palette._commands_registry if "full details" in c.get("label", "").lower() and "card layout" in c.get("label", "").lower())
            full_cmd["action"]()
            prefs = config.get_directory_card_prefs()
            self.assertEqual(prefs["density_mode"], "expanded")
            self.assertTrue(prefs["show_location_row"])
            self.assertTrue(prefs["show_author_citation"])
            mock_ui.show_toast.assert_called_with("Card View Preset: Full Detail")

            # Test 3: Minimalist Preset
            min_cmd = next(c for c in palette._commands_registry if "minimalist" in c.get("label", "").lower())
            min_cmd["action"]()
            prefs = config.get_directory_card_prefs()
            self.assertFalse(prefs["show_status_badge"])
            mock_ui.show_toast.assert_called_with("Card View Preset: Minimalist")

            # Test 4: Standard Preset
            std_cmd = next(c for c in palette._commands_registry if "standard" in c.get("label", "").lower())
            std_cmd["action"]()
            prefs = config.get_directory_card_prefs()
            self.assertEqual(prefs["density_mode"], "standard")
            mock_ui.show_toast.assert_called_with("Card View Preset: Standard")

            # Test 5: Toggle Location Row
            loc_cmd = next(c for c in palette._commands_registry if "location row" in c.get("label", "").lower())
            prev_loc = config.get_directory_card_prefs().get("show_location_row", True)
            loc_cmd["action"]()
            self.assertEqual(config.get_directory_card_prefs().get("show_location_row"), not prev_loc)

            # Test 6: Toggle Status Badges
            badge_cmd = next(c for c in palette._commands_registry if "status pill badges" in c.get("label", "").lower())
            prev_badge = config.get_directory_card_prefs().get("show_status_badge", True)
            badge_cmd["action"]()
            self.assertEqual(config.get_directory_card_prefs().get("show_status_badge"), not prev_badge)

            # Test 7: Restore to Default
            restore_cmd = next(c for c in palette._commands_registry if "restore" in c.get("label", "").lower() and "card" in c.get("label", "").lower())
            restore_cmd["action"]()
            prefs = config.get_directory_card_prefs()
            self.assertEqual(prefs["density_mode"], "standard")
            self.assertTrue(prefs["show_location_row"])
            self.assertTrue(prefs["show_status_badge"])

            # Verify directory object_list was informed on each dispatch
            self.assertGreaterEqual(mock_ui.object_list.apply_directory_view_preferences.call_count, 7)

            palette.destroy()
            root.destroy()
        except tk.TclError:
            pass


if __name__ == "__main__":
    unittest.main()
