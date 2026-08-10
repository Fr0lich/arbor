import pytest
import tkinter as tk
from unittest.mock import MagicMock, patch
import config
from ui.advanced_settings import AdvancedSettingsWindow, ADVANCED_SETTINGS_SCHEMA

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
    assert len(ADVANCED_SETTINGS_SCHEMA) >= 2
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
        
        # Verify that all toggles from schema are registered in Tk variables
        for item in ADVANCED_SETTINGS_SCHEMA:
            if item["type"] == "toggle":
                assert item["id"] in adv_win.vars
                assert adv_win.vars[item["id"]].get() == item["default"]
        
        # Cleanup
        adv_win.win.destroy()

def test_advanced_settings_save(root, mock_main_window):
    """Test saving updated values to user preferences."""
    test_prefs = {"advanced": {"enable_bulk_editor": False, "enable_focus_mode_toggle": False}}
    
    with patch("config.load_prefs", return_value=test_prefs), \
         patch("config.save_prefs") as mock_save:
         
        adv_win = AdvancedSettingsWindow(root, mock_main_window)
        
        # Update values in the UI variables
        adv_win.vars["enable_bulk_editor"].set(True)
        adv_win.vars["enable_focus_mode_toggle"].set(True)
        
        # Call save
        adv_win.save_settings()
        
        # Verify preferences updated correctly
        saved_prefs = mock_save.call_args[0][0]
        assert saved_prefs["advanced"]["enable_bulk_editor"] is True
        assert saved_prefs["advanced"]["enable_focus_mode_toggle"] is True
        
        # Verify immediate callbacks triggered
        mock_main_window.update_focus_toggle_visibility.assert_called_once()
