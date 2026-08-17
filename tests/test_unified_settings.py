import os
import sys
import tkinter as tk
import pytest

current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.abspath(os.path.join(current_dir, ".."))
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

import config
from ui.unified_settings import UnifiedSettingsWindow, open_unified_settings

@pytest.fixture
def tk_root():
    try:
        root = tk.Tk()
        root.withdraw()
        yield root
        root.destroy()
    except Exception as e:
        pytest.skip(f"Tkinter display not available: {e}")

def test_unified_settings_initialization(tk_root):
    win = UnifiedSettingsWindow(tk_root, initial_tab="general")
    assert win.win.winfo_exists()
    assert win.active_tab == "general"
    assert "general" in win.tabs
    assert "appearance" in win.tabs
    assert "layout" in win.tabs
    assert "focus" in win.tabs
    assert "presets" in win.tabs
    assert "advanced" in win.tabs
    win.win.destroy()

def test_unified_settings_tab_navigation(tk_root):
    win = UnifiedSettingsWindow(tk_root, initial_tab="appearance")
    assert win.active_tab == "appearance"

    win.show_tab("focus")
    assert win.active_tab == "focus"

    win.show_tab("presets")
    assert win.active_tab == "presets"
    win.win.destroy()

def test_unified_settings_live_callbacks(tk_root):
    events = {}

    def _callback(val):
        events["dark_mode"] = val

    win = UnifiedSettingsWindow(tk_root, initial_tab="appearance", live_callbacks={"dark_mode": _callback})
    win.var_dark_mode.set(True)
    win._notify_live("dark_mode", True)

    assert events.get("dark_mode") is True
    win.win.destroy()

def test_unified_settings_save_prefs(tk_root, tmp_path, monkeypatch):
    test_prefs_file = str(tmp_path / "user_prefs.json")
    monkeypatch.setattr(config, "_PREFS_PATH", test_prefs_file)
    monkeypatch.setattr(config, "_prefs_cache", None)

    win = UnifiedSettingsWindow(tk_root, initial_tab="general")
    win.var_autosave_mins.set("15")
    win.var_dark_mode.set(True)
    win.save_settings()

    loaded = config.load_prefs()
    assert loaded.get("autosave_interval") == 15
    assert loaded.get("dark_mode") is True

