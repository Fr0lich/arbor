import os
import sys
import tkinter as tk
from unittest.mock import MagicMock
import pytest

current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.abspath(os.path.join(current_dir, ".."))
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

import config
from ui.unified_settings import UnifiedSettingsWindow
from ui.location_panel import LocationPanel, create_location_panel


@pytest.fixture
def tk_root():
    try:
        root = tk.Tk()
        root.withdraw()
        yield root
        root.destroy()
    except Exception as e:
        pytest.skip(f"Tkinter display not available: {e}")


def test_unified_settings_location_center_live_callback(tk_root):
    events = {}

    def _callback(val):
        events["location_center"] = val

    win = UnifiedSettingsWindow(
        tk_root,
        initial_tab="layout",
        live_callbacks={"location_center": _callback}
    )
    win.var_location_center.set(True)
    win._notify_live("location_center", True)

    assert events.get("location_center") is True
    win.win.destroy()


def test_unified_settings_push_layout_to_app(tk_root):
    mock_app = MagicMock()
    mock_app.show_list_var = tk.BooleanVar(value=True)
    mock_app.show_search_var = tk.BooleanVar(value=True)
    mock_app.show_reg_var = tk.BooleanVar(value=True)
    mock_app.show_images_var = tk.BooleanVar(value=True)
    mock_app.location_in_center_var = tk.BooleanVar(value=False)
    mock_app.draft_location_in_center_var = tk.BooleanVar(value=False)
    mock_app.show_image_tools_var = tk.BooleanVar(value=True)
    mock_app.show_bulk_edit_var = tk.BooleanVar(value=True)
    mock_app.image_stack_var = tk.BooleanVar(value=False)
    mock_app.toolbar_vars = {}

    win = UnifiedSettingsWindow(tk_root, app_ref=mock_app, initial_tab="layout")
    win.var_location_center.set(True)
    win._push_layout_to_app()

    assert mock_app.location_in_center_var.get() is True
    assert mock_app.draft_location_in_center_var.get() is True
    win.win.destroy()


def test_unified_settings_save_location_in_center(tk_root, tmp_path, monkeypatch):
    test_prefs_file = str(tmp_path / "user_prefs.json")
    monkeypatch.setattr(config, "_PREFS_PATH", test_prefs_file)
    monkeypatch.setattr(config, "_prefs_cache", None)

    win = UnifiedSettingsWindow(tk_root, initial_tab="layout")
    win.var_location_center.set(True)
    win.save_settings()

    loaded = config.load_prefs()
    assert loaded.get("location_in_center") is True
    win.win.destroy()


def test_location_panel_integration_modes(tk_root):
    loc_vars = {
        "Stored as": tk.StringVar(value=""),
        "Building": tk.StringVar(value=""),
        "Floor": tk.StringVar(value=""),
        "Cabinet": tk.StringVar(value=""),
        "Extra": tk.StringVar(value=""),
        "Loaned out": tk.StringVar(value="False"),
    }

    vert_panel = create_location_panel(tk_root, mode="vertical", location_vars=loc_vars)
    assert isinstance(vert_panel, LocationPanel)
    assert vert_panel.mode == "vertical"

    horiz_panel = create_location_panel(tk_root, mode="horizontal_1row", location_vars=loc_vars)
    assert isinstance(horiz_panel, LocationPanel)
    assert horiz_panel.mode == "horizontal_1row"

    # Test dark mode propagation
    vert_panel.set_dark_mode(True)
    assert vert_panel.dark_mode is True
    horiz_panel.set_dark_mode(True)
    assert horiz_panel.dark_mode is True
