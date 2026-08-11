import pytest
import tkinter as tk
from unittest.mock import MagicMock, patch
from ui.advanced_settings import AdvancedSettingsWindow, ADVANCED_SETTINGS_SCHEMA

def test_advanced_settings_save_with_buttons():
    root = tk.Tk()
    mock_main_window = MagicMock()
    mock_main_window.root = root
    mock_main_window.dark_mode_active = False

    adv_win = AdvancedSettingsWindow(root, mock_main_window)
    try:
        adv_win.save_settings()
        print("Success")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        root.destroy()

if __name__ == "__main__":
    test_advanced_settings_save_with_buttons()
