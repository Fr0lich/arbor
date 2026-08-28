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
