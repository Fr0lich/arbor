import pytest
import tkinter as tk
from unittest.mock import MagicMock, patch
import os
import sys
import config
from ui.advanced_settings import AdvancedSettingsWindow, ADVANCED_SETTINGS_SCHEMA
from utils import get_log_level, debug_log, _SESSION_LOG_PATH

@pytest.fixture
def root():
    root_win = tk.Tk()
    yield root_win
    root_win.destroy()

@pytest.fixture
def mock_main_window(root):
    main_win = MagicMock()
    main_win.root = root
    main_win.dark_mode_active = False
    return main_win

@pytest.fixture(autouse=True)
def reset_prefs_cache():
    original_cache = config._prefs_cache
    config._prefs_cache = None
    yield
    config._prefs_cache = original_cache

def test_schema_structure():
    """Verify that schema elements conform to expectations."""
    assert len(ADVANCED_SETTINGS_SCHEMA) >= 5
    for item in ADVANCED_SETTINGS_SCHEMA:
        assert "id" in item
        assert "type" in item
        assert "tab" in item
        assert "group" in item
        assert "label" in item
        assert "default" in item

def test_advanced_settings_initialization(root, mock_main_window):
    """Test instantiating AdvancedSettingsWindow and loading defaults."""
    with patch("config.load_prefs", return_value={}):
        adv_win = AdvancedSettingsWindow(root, mock_main_window)
        
        # Verify that all items from schema are registered in Tk variables
        for item in ADVANCED_SETTINGS_SCHEMA:
            assert item["id"] in adv_win.vars
            val = adv_win.vars[item["id"]].get()
            if item["type"] == "toggle":
                assert val == item["default"]
            else:
                assert str(val) == str(item["default"])
        
        # Cleanup
        adv_win.win.destroy()

def test_advanced_settings_save(root, mock_main_window):
    """Test saving updated values to user preferences."""
    test_prefs = {
        "advanced": {
            "enable_excel_import_backup": True,
            "autosave_archive_limit": "10",
            "log_verbosity": "ERROR",
            "image_resampling_algorithm": "LANCZOS (High Quality)",
            "image_url_pattern_override": "",
            "enable_problem_highlights": True,
            "problem_highlight_color": "Default (Red)"
        }
    }
    
    with patch("config.load_prefs", return_value=test_prefs), \
         patch("config.save_prefs") as mock_save:
         
        adv_win = AdvancedSettingsWindow(root, mock_main_window)
        
        # Update values in the UI variables
        adv_win.vars["enable_excel_import_backup"].set(False)
        adv_win.vars["autosave_archive_limit"].set("20")
        adv_win.vars["log_verbosity"].set("DEBUG")
        adv_win.vars["image_resampling_algorithm"].set("NEAREST (Fast draft / Pixelated)")
        adv_win.vars["image_url_pattern_override"].set("https://test.org/{num}.jpg")
        adv_win.vars["enable_problem_highlights"].set(False)
        
        # Call save
        adv_win.save_settings()
        
        # Verify preferences updated correctly
        saved_prefs = mock_save.call_args[0][0]
        assert saved_prefs["advanced"]["enable_excel_import_backup"] is False
        assert saved_prefs["advanced"]["autosave_archive_limit"] == "20"
        assert saved_prefs["advanced"]["log_verbosity"] == "DEBUG"
        assert saved_prefs["advanced"]["image_resampling_algorithm"] == "NEAREST (Fast draft / Pixelated)"
        assert saved_prefs["advanced"]["image_url_pattern_override"] == "https://test.org/{num}.jpg"
        assert saved_prefs["advanced"]["enable_problem_highlights"] is False
        
        # Verify immediate callbacks triggered
        mock_main_window.refresh_image_rendering.assert_called_once()
        mock_main_window.refresh_styles_and_highlights.assert_called_once()

def test_logger_verbosity_logic():
    """Test get_log_level and debug_log filtering logic."""
    with patch("utils.get_log_level", return_value="WARNING"), \
         patch("builtins.open") as mock_open_file:
         
        # Under WARNING level:
        # DEBUG and INFO should be ignored (no file writes)
        debug_log("DEBUG", "This should be ignored")
        debug_log("INFO", "This should also be ignored")
        mock_open_file.assert_not_called()
        
        # WARNING and ERROR should be logged
        debug_log("WARNING", "This is a warning")
        debug_log("ERROR", "This is an error")
        assert mock_open_file.call_count == 2
