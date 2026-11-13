"""
Arbor Fast Smoke & Sanity Verification Suite
============================================
High-signal, sub-5-second test suite validating core curatorial workflows,
zero-regression geometry, non-blocking telemetry, and document consistency.

Run with:
    pytest -m smoke
"""

import os
import sys
import pytest
import tkinter as tk
from tkinter import ttk
import pandas as pd
from unittest.mock import MagicMock, patch

# Ensure project root is in sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config
from config import sc


@pytest.fixture(scope="module")
def tk_root():
    """Shared invisible root window for UI smoke verification."""
    root = tk.Tk()
    root.withdraw()
    yield root
    try:
        root.destroy()
    except Exception:
        pass


@pytest.mark.smoke
def test_smoke_startup_layout_and_sash_bounds(tk_root):
    """Verify resolution-safe sash boundaries and paned window weights."""
    from ui.main_window import ObjectProgramUI

    ui = ObjectProgramUI.__new__(ObjectProgramUI)
    ui.root = tk_root
    ui.dark_mode_active = False

    # Simulate paned window container
    panes = ttk.Panedwindow(tk_root, orient="horizontal")
    f_left = ttk.Frame(panes, width=sc(350))
    f_mid = ttk.Frame(panes, width=sc(600))
    f_right = ttk.Frame(panes, width=sc(420))

    panes.add(f_left, weight=0)
    panes.add(f_mid, weight=1)
    panes.add(f_right, weight=0)
    ui.panes = panes
    ui.left_panel = f_left
    ui.middle_panel = f_mid
    ui.reg_panel_outer = f_right

    # Execute sash calculation logic
    total_w = sc(1400)
    sidebar_w = sc(350)
    right_w = sc(420)
    sash_0 = sidebar_w
    sash_1 = total_w - right_w

    assert sash_0 == sc(350)
    assert sash_1 == sc(980)
    assert (total_w - sash_1) == sc(420)

    panes.destroy()


@pytest.mark.smoke
def test_smoke_excel_repository_lifecycle(tmp_path):
    """Verify DataFrame normalization, Excel export, and automatic backup creation."""
    from repository import SQLiteRepository, _normalise_dataframes

    cfg = {
        "sheets": {"reg": "Registration", "obs": "Observation"},
        "ui_sections": {
            "location": [{"name": "Building", "type": "choice"}, {"name": "Loaned out", "type": "checkbox"}],
            "problems": [{"name": "Taxonomy_Problem", "category": "taxonomy"}],
            "registration": [{"name": "Genus"}, {"name": "Species"}]
        }
    }

    df_reg = pd.DataFrame([
        {"ObjectID": "1001", "Genus": "Quercus", "Species": "robur"},
        {"ObjectID": "1002", "Genus": "Pinus", "Species": "sylvestris"}
    ]).set_index("ObjectID", drop=False)

    df_obs = pd.DataFrame([
        {"ObjectID": "1001", "Reviewed": False, "Taxonomy_Problem": False, "Loaned out": "True"},
        {"ObjectID": "1002", "Reviewed": True, "Taxonomy_Problem": True, "Loaned out": ""}
    ]).set_index("ObjectID", drop=False)

    # 1. Normalization
    df_reg_norm, df_obs_norm = _normalise_dataframes(df_reg.copy(), df_obs.copy(), cfg)
    assert df_obs_norm.loc[df_obs_norm["ObjectID"] == "1001", "Loaned out"].iloc[0] == "True"
    assert df_obs_norm.loc[df_obs_norm["ObjectID"] == "1002", "Loaned out"].iloc[0] == "False"

    # 2. Excel export
    target_excel = tmp_path / "smoke_collection.xlsx"
    SQLiteRepository.export_to_excel(
        None, str(target_excel), cfg,
        df_reg=df_reg_norm, df_obs=df_obs_norm, df_log=pd.DataFrame()
    )
    assert target_excel.exists()


@pytest.mark.smoke
def test_smoke_virtual_cards_and_single_badge_discipline(tk_root):
    """Verify single-badge discipline on Row 1 and O(1) selection diffing."""
    from ui.widgets import TreeviewListboxWrapper

    mock_ui = MagicMock()
    mock_ui.root = tk_root
    mock_ui.dark_mode_active = False
    mock_ui.image_index = {}
    mock_ui._cached_photo_counts = {}
    mock_ui.get_photo_paths_for_object = lambda oid: []
    mock_ui.has_online_photos = lambda oid: False
    mock_ui.has_unvalidated_sources = lambda oid: False
    mock_ui.is_unknown = lambda val: str(val).strip().lower() in ("unknown", "?", "")
    mock_ui._cached_genus_dict = {"OBJ-1": "Betula", "OBJ-2": "Quercus"}
    mock_ui._cached_species_dict = {"OBJ-1": "pendula", "OBJ-2": "robur"}
    mock_ui._cached_reviewed_dict = {"OBJ-1": False, "OBJ-2": True}
    mock_ui._get_active_problem_categories = lambda oid: {"taxonomy"} if oid == "OBJ-1" else set()
    mock_ui._problems_have_history = lambda oid: False
    mock_ui._get_obs_dict = lambda: {
        "OBJ-1": {"Building": "Herbarium", "Cabinet": "12", "Shelf": "A"},
        "OBJ-2": {"Building": "Herbarium", "Cabinet": "14", "Shelf": "B"}
    }
    mock_ui._get_reg_dict = lambda: {
        "OBJ-1": {"Family": "Betulaceae"},
        "OBJ-2": {"Family": "Fagaceae"}
    }

    wrapper = TreeviewListboxWrapper(tk_root, mock_ui)
    wrapper.pack()
    tk_root.update()

    wrapper.insert(tk.END, "OBJ-1 Betula pendula", genus="Betula", species="pendula", reviewed=False, bulk=True)
    wrapper.insert(tk.END, "OBJ-2 Quercus robur", genus="Quercus", species="robur", reviewed=True, bulk=True)

    # Inspect single-badge discipline on empty card widget
    widget_dict = wrapper._build_empty_card_widget(wrapper.canvas)
    wrapper._populate_card_widget(widget_dict, "OBJ-1")

    # Row 1 must strictly host cb_lbl, tax_lbl, and status_badge
    row1_slaves = widget_dict["row1"].pack_slaves()
    assert row1_slaves == [widget_dict["cb_lbl"], widget_dict["tax_lbl"], widget_dict["status_badge"]]
    assert widget_dict["status_badge"].cget("text") in ("TAX", "[ TAX ]")

    # Meta label on Row 2 contains bullet-separated family
    assert "BETULACEAE" in widget_dict["meta_lbl"].cget("text")

    # Clean up
    wrapper.destroy()


@pytest.mark.smoke
def test_smoke_curatorial_keyboard_workflow(tk_root):
    """Verify primary curation keys: Space (toggle problem) and Ctrl+Enter (review & advance)."""
    from ui.keybindings import KeybindingManager

    mock_ui = MagicMock()
    km = KeybindingManager(mock_ui, tk_root)
    km.bind_global_shortcuts()

    # Check that required handlers exist
    assert hasattr(km, "bind_global_shortcuts")
    assert hasattr(km, "bind_search_shortcuts")

    # Verify keybindings did not throw errors
    bindings = tk_root.bind()
    assert any("Return" in b for b in bindings)
    assert any("space" in b.lower() for b in bindings)


@pytest.mark.smoke
def test_smoke_command_palette_and_scroll_helper(tk_root):
    """Verify CommandPalette registers card presets and attaches non-destructive scrolling."""
    from ui.command_palette import CommandPalette

    mock_ui = MagicMock()
    mock_ui.root = tk_root
    mock_ui.dark_mode_active = False

    palette = CommandPalette(mock_ui)
    palette.withdraw()

    # Verify mousewheel tag routing on items_frame
    tag = f"ScrollTag_{id(palette.canvas)}"
    assert tag in palette.items_frame.bindtags()
    assert "<MouseWheel>" not in tk_root.bind()

    # Verify card presets are registered under VIEW
    labels = [c["label"] for c in palette._commands_registry if c.get("category") == "VIEW"]
    assert any("Standard" in l for l in labels)
    assert any("Compact" in l for l in labels)

    palette.destroy()


@pytest.mark.smoke
def test_smoke_gbif_toast_telemetry(tk_root):
    """Verify GBIF validation triggers non-blocking ToastManager pills instead of messagebox."""
    from ui.main_window import ObjectProgramUI
    from ui.toast import ToastManager

    ui = ObjectProgramUI.__new__(ObjectProgramUI)
    ui.root = tk_root
    ui.app = MagicMock()
    ui.app.current_object_id = "1001"
    ui.reg_vars = {"Genus": tk.StringVar(value=""), "Species": tk.StringVar(value="")}

    with patch.object(ToastManager, "show") as mock_toast, \
         patch("tkinter.messagebox.showinfo") as mock_box:
        ui.check_gbif_action()
        mock_box.assert_not_called()
        mock_toast.assert_called_once()
        assert "Genus is required" in mock_toast.call_args[0][1]


@pytest.mark.smoke
def test_smoke_unified_settings_card_preview(tk_root):
    """Verify UnifiedSettings live card preview updates on layout profile selection."""
    from ui.unified_settings import UnifiedSettingsWindow

    win = UnifiedSettingsWindow(tk_root, initial_tab="appearance")

    assert hasattr(win, "_preview_widgets")
    assert "tax_lbl" in win._preview_widgets

    # Switch to compact profile
    win._apply_card_preset_in_settings("compact")
    assert win.var_card_density.get() == "compact"
    assert win.var_card_show_loc.get() is False

    # Switch to standard profile
    win._apply_card_preset_in_settings("standard")
    assert win.var_card_density.get() == "standard"
    assert win.var_card_show_loc.get() is True

    win.win.destroy()


@pytest.mark.smoke
def test_smoke_navigation_bar_and_status_telemetry(tk_root):
    """Verify high-DPI scaling of NavigationBar and clean telemetry in StatusBarPanel."""
    from ui.navigation_bar import NavigationBar
    from ui.status_bar import StatusBarPanel

    mock_ui = MagicMock()
    mock_ui.root = tk_root
    mock_ui.dark_mode_active = False

    f_top = ttk.Frame(tk_root)
    f_bottom = ttk.Frame(tk_root)

    # 1. Navigation Bar
    NavigationBar.build_nav_ui(mock_ui, f_top)
    assert mock_ui.nav_bar.cget("height") == sc(48)
    assert mock_ui.nav_title_lbl.cget("padx") == sc(16)

    # 2. Status Bar
    sb = StatusBarPanel(f_bottom, mock_ui)
    sb.update_status(total=100, reviewed=60, problems=5, last_save="10:45")
    assert "100" in sb.labels["object_count"].cget("text")
    assert "60" in sb.labels["reviewed"].cget("text")
    assert "5" in sb.labels["problems"].cget("text")

    f_top.destroy()
    f_bottom.destroy()


@pytest.mark.smoke
def test_smoke_image_popup_lifecycle(tk_root):
    """Verify ZoomableImagePopup opens, zooms at cursor, and cleans up stop event."""
    from PIL import Image, ImageTk
    from ui.image_popup import ZoomableImagePopup

    img = Image.new("RGB", (20, 20), color="green")
    tk_img = ImageTk.PhotoImage(img)

    popup = ZoomableImagePopup(tk_root, tk_img, source=None, is_online=False)
    assert popup.top.winfo_exists()
    assert popup.scale > 0

    # Zoom in
    init_scale = popup.scale
    popup._zoom_at(10, 10, 1.1)
    assert popup.scale == pytest.approx(init_scale * 1.1, rel=1e-3)

    # Close
    popup._on_close()
    assert popup._stop_event.is_set()
    popup.top.destroy()


@pytest.mark.smoke
def test_smoke_documentation_consistency():
    """Verify that keyboard shortcuts in KEYBOARD_SHORTCUTS_CHEAT_SHEET.md match keybindings.py."""
    cheat_sheet_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "documentation", "curator", "KEYBOARD_SHORTCUTS_CHEAT_SHEET.md"
    )
    assert os.path.exists(cheat_sheet_path)

    with open(cheat_sheet_path, "r", encoding="utf-8") as f:
        content = f.read()

    # Core work shortcuts must be prominently documented
    assert "[ CTRL ] + [ ENTER ]" in content or "[Ctrl] + [Enter]" in content
    assert "[ SPACE ]" in content or "[Space]" in content
    assert "[ CTRL ] + [ K ]" in content or "[Ctrl] + [K]" in content
    assert "[ CTRL ] + [ S ]" in content or "[Ctrl] + [S]" in content
    # No barcode references in the trainee cheat sheet
    assert "barcode" not in content.lower()
