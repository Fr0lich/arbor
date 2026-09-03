import pytest
import tkinter as tk
from tkinter import ttk
import pandas as pd
from unittest.mock import MagicMock

from ui.widgets import TreeviewListboxWrapper
import config


@pytest.fixture
def tk_root():
    root = tk.Tk()
    root.withdraw()
    yield root
    try:
        root.destroy()
    except Exception:
        pass


def test_treeview_keyboard_navigation(tk_root):
    mock_main = MagicMock()
    mock_main.dark_mode_active = False
    mock_main.focus_mode_var = tk.BooleanVar(value=True)

    wrapper = TreeviewListboxWrapper(tk_root, mock_main)
    wrapper.pack()

    # Populate items
    wrapper.items_list = ["101", "102", "103", "104", "105"]
    wrapper.items_set = set(wrapper.items_list)
    wrapper._oid_to_index = {oid: idx for idx, oid in enumerate(wrapper.items_list)}
    for oid in wrapper.items_list:
        wrapper.item_data[oid] = {
            "values": ["☐", oid, f"Genus_{oid}", f"Species_{oid}"],
            "tags": ()
        }
    wrapper._tree_dirty = True
    wrapper._ensure_tree_synced()

    # Initial selection
    wrapper.selection_set(0)
    assert wrapper.selected_iids == ["101"]

    # Test keypress down
    wrapper._on_keypress_down(None)
    assert wrapper.selected_iids == ["102"]

    # Test keypress up
    wrapper._on_keypress_up(None)
    assert wrapper.selected_iids == ["101"]

    # Test keypress end
    wrapper._on_keypress_end(None)
    assert wrapper.selected_iids == ["105"]

    # Test keypress home
    wrapper._on_keypress_home(None)
    assert wrapper.selected_iids == ["101"]

    # Test spacebar review toggle
    wrapper._on_keypress_space(None)
    mock_main._toggle_reviewed_for_id.assert_called_once_with("101")


def test_accordion_card_toggle_behavior(tk_root):
    # Test accordion show/hide mechanics
    parent_frame = tk.Frame(tk_root)
    parent_frame.pack()

    card_frame = tk.Frame(parent_frame)
    card_frame.pack()

    header_frame = tk.Frame(card_frame)
    header_frame.pack(fill="x")
    toggle_lbl = tk.Label(header_frame, text="▼")
    toggle_lbl.pack(side="left")

    body_frame = tk.Frame(card_frame)
    body_frame.pack(fill="x")

    dummy_canvas = tk.Canvas(parent_frame)

    def _toggle():
        if body_frame.winfo_manager():
            body_frame.pack_forget()
            toggle_lbl.config(text="▶")
        else:
            body_frame.pack(fill="x")
            toggle_lbl.config(text="▼")

    assert body_frame.winfo_manager() == "pack"
    assert toggle_lbl.cget("text") == "▼"

    _toggle()
    assert body_frame.winfo_manager() == ""
    assert toggle_lbl.cget("text") == "▶"

    _toggle()
    assert body_frame.winfo_manager() == "pack"
    assert toggle_lbl.cget("text") == "▼"


def test_redo_with_text_widget(tk_root):
    from ui.main_window import ObjectProgramUI
    main = MagicMock()
    main.root = tk_root
    text = tk.Text(tk_root, undo=True)
    text.pack()
    main.root.focus_get = MagicMock(return_value=text)

    # Call unbound method redo passing main mock
    res = ObjectProgramUI.redo(main)
    assert res == "break"
    # Ensure app redo stack was not touched
    assert not main.app.redo_stacks.get.called


def test_location_persisted_even_with_skip_heavy(tk_root):
    from ui.main_window import ObjectProgramUI
    from models import AppState

    # Construct minimal app
    app = AppState()
    app.current_object_id = "101"
    app.df_reg = pd.DataFrame({"Genus": ["Quercus"]}, index=pd.Index(["101"], name="ObjectID"))
    app.df_obs = pd.DataFrame({"Cabinet": ["Cab-A"], "Reviewed": [False]}, index=pd.Index(["101"], name="ObjectID"))
    app.output_path = "dummy.xlsx"

    main = MagicMock()
    main.app = app
    main.root = tk_root
    main.initializing = False
    main.reg_entries = {}
    main.reg_vars = {}
    main.location_vars = {"Cabinet": tk.StringVar(value="Cab-B")}  # User modified Cabinet
    main.reviewed_var = tk.BooleanVar(value=False)
    main.problem_vars = {}
    main.loaded_problem_states = {}
    main.reg_field_widgets = {}
    main.app.active_object_ids = ["101"]
    main.app.redo_stacks = {}
    main.app.undo_stacks = {}
    main._cached_obs_dict = {"101": {"Cabinet": "Cab-A", "Reviewed": False}}
    main._is_navigating = True  # Simulating active arrow navigation

    # Run commit_current_object with skip_heavy=True
    ObjectProgramUI.commit_current_object(main, skip_heavy=True)

    # Location edit MUST be persisted in df_obs even when skip_heavy=True
    assert app.df_obs.at["101", "Cabinet"] == "Cab-B"
    assert app.dirty is True


def test_virtual_card_badge_toggle_and_refresh(tk_root):
    mock_main = MagicMock()
    mock_main.dark_mode_active = False
    mock_main.focus_mode_var = tk.BooleanVar(value=True)
    mock_main.app = MagicMock()
    mock_main.app.df_photo = None
    mock_main.has_unvalidated_sources.return_value = False
    mock_main._cached_reviewed_dict = None
    mock_main._get_cached_problem.return_value = False
    mock_main._problems_have_history.return_value = False
    mock_main.is_unknown.return_value = False

    obs_data = {"101": {"Loaned out": False, "Reviewed": False}}
    reg_data = {"101": {"Genus": "Quercus", "Species": "robur"}}

    mock_main._get_obs_dict.return_value = obs_data
    mock_main._get_reg_dict.return_value = reg_data

    wrapper = TreeviewListboxWrapper(tk_root, mock_main)
    wrapper.pack()

    wrapper.items_list = ["101"]
    wrapper.items_set = {"101"}
    wrapper._oid_to_index = {"101": 0}

    widget_dict = wrapper._build_empty_card_widget(wrapper.canvas)
    wrapper._active_card_windows[0] = (1, widget_dict)

    # Populate initial card widget
    wrapper._populate_card_widget(widget_dict, "101")
    loaned_badge = widget_dict["loaned_badge"]
    assert loaned_badge.winfo_exists()
    assert loaned_badge.winfo_manager() != "pack"

    # Refresh accent with loaned=False (should not destroy loaned_badge)
    wrapper._refresh_card_accent("101")
    assert loaned_badge.winfo_exists()
    assert loaned_badge.winfo_manager() != "pack"

    # refresh_object_card should run cleanly without TclError
    wrapper.refresh_object_card("101")
    assert loaned_badge.winfo_exists()

    # Now set loaned=True and refresh
    obs_data["101"]["Loaned out"] = True
    wrapper._refresh_card_accent("101")
    assert loaned_badge.winfo_exists()
    assert loaned_badge.winfo_manager() == "pack"

    wrapper.refresh_object_card("101")
    assert loaned_badge.winfo_exists()
    assert loaned_badge.winfo_manager() == "pack"

    # Toggle back to loaned=False
    obs_data["101"]["Loaned out"] = False
    wrapper._refresh_card_accent("101")
    assert loaned_badge.winfo_exists()
    assert loaned_badge.winfo_manager() != "pack"

    wrapper.refresh_object_card("101")
    assert loaned_badge.winfo_exists()
    assert loaned_badge.winfo_manager() != "pack"

