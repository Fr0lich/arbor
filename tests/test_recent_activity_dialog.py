import pytest
import tkinter as tk
import pandas as pd
from ui.recent_activity_dialog import RecentActivityDialog, open_recent_activity_dialog, COLORS_LIGHT, COLORS_DARK


@pytest.fixture
def tk_root():
    try:
        root = tk.Tk()
        root.withdraw()
        yield root
        root.destroy()
    except Exception as e:
        pytest.skip(f"Tkinter display not available: {e}")


@pytest.fixture
def mock_data():
    mock_history = ["1001", "1002", "1003"]
    mock_df_log = pd.DataFrame([
        {
            "Timestamp": "2026-08-17T10:15:30.123",
            "Action": "EDIT",
            "ObjectID": "1001",
            "ChangedFields": "Genus",
            "ChangedValues": "Pinus  Abies",
            "ProblemsChanged": "",
            "ProblemsChangedValues": "",
            "LocationChanged": "",
            "LocationChangedValues": ""
        },
        {
            "Timestamp": "2026-08-17T10:45:00.000",
            "Action": "RESOLVE_HISTORICAL_CONFLICT",
            "ObjectID": "1002",
            "ChangedFields": "Species",
            "ChangedValues": "sylvestris  alba",
            "ProblemsChanged": "Species_Problem",
            "ProblemsChangedValues": "True  False",
            "LocationChanged": "",
            "LocationChangedValues": ""
        }
    ])
    return mock_history, mock_df_log


def test_recent_activity_dialog_init(tk_root, mock_data):
    history, df_log = mock_data
    dialog = open_recent_activity_dialog(tk_root, history_stack=history, df_log=df_log, default_tab=0)
    assert isinstance(dialog, RecentActivityDialog)
    assert dialog.title() == "Recent Activity"
    assert dialog.active_tab_name == "visited"

    # Visited rows populated
    items = dialog.tree_v.get_children()
    assert len(items) == 3

    dialog.destroy()


def test_recent_activity_dialog_tab_switch(tk_root, mock_data):
    history, df_log = mock_data
    dialog = open_recent_activity_dialog(tk_root, history_stack=history, df_log=df_log, default_tab=1)
    assert dialog.active_tab_name == "edits"

    items = dialog.tree_e.get_children()
    assert len(items) == 2

    dialog.destroy()


def test_recent_activity_dark_mode(tk_root, mock_data):
    history, df_log = mock_data
    dialog = open_recent_activity_dialog(tk_root, history_stack=history, df_log=df_log, dark_mode=True)
    assert dialog.colors == COLORS_DARK
    dialog.destroy()


def test_visited_header_sorting(tk_root, mock_data):
    history, df_log = mock_data
    dialog = open_recent_activity_dialog(tk_root, history_stack=history, df_log=df_log, default_tab=0)

    # Initial sort for visited is desc by ObjectID (1003, 1002, 1001)
    items = dialog.tree_v.get_children()
    first_id = dialog.tree_v.item(items[0])["values"][0]
    assert str(first_id) == "1003"

    # Sort ascending by clicking ObjectID header
    dialog._sort_visited("ObjectID")
    items = dialog.tree_v.get_children()
    first_id = dialog.tree_v.item(items[0])["values"][0]
    assert str(first_id) == "1001"

    dialog.destroy()


def test_edits_header_sorting(tk_root, mock_data):
    history, df_log = mock_data
    dialog = open_recent_activity_dialog(tk_root, history_stack=history, df_log=df_log, default_tab=1)

    # Sort by Action column
    dialog._sort_edits("Action")
    items = dialog.tree_e.get_children()
    assert len(items) == 2
    act0 = dialog.tree_e.item(items[0])["values"][2]
    act1 = dialog.tree_e.item(items[1])["values"][2]
    assert act0 <= act1

    dialog.destroy()


def test_search_and_action_filtering(tk_root, mock_data):
    history, df_log = mock_data
    dialog = open_recent_activity_dialog(tk_root, history_stack=history, df_log=df_log, default_tab=1)

    # Test Search Query
    dialog.search_query.set("1002")
    items = dialog.tree_e.get_children()
    assert len(items) == 1
    assert str(dialog.tree_e.item(items[0])["values"][0]) == "1002"

    # Reset search query
    dialog.search_query.set("")
    items = dialog.tree_e.get_children()
    assert len(items) == 2

    # Test Action Filter Chip
    dialog._set_action_filter("Manual Edit")
    items = dialog.tree_e.get_children()
    assert len(items) == 1
    assert dialog.tree_e.item(items[0])["values"][2] == "Manual Edit"

    dialog.destroy()


def test_callbacks_invocation(tk_root, mock_data):
    history, df_log = mock_data
    nav_events = []
    ref_events = []
    close_events = []

    callbacks = {
        "on_navigate": lambda oid: nav_events.append(oid),
        "on_refresh": lambda: ref_events.append(True),
        "on_close": lambda: close_events.append(True)
    }

    dialog = open_recent_activity_dialog(
        tk_root, history_stack=history, df_log=df_log,
        live_callbacks=callbacks, default_tab=0
    )

    # Refresh callback
    dialog._handle_refresh()
    assert len(ref_events) == 1

    # Select item & navigate callback
    items = dialog.tree_v.get_children()
    dialog.tree_v.selection_set(items[0])
    target_oid = str(dialog.tree_v.item(items[0])["values"][0])
    dialog._do_navigate()

    assert len(nav_events) == 1
    assert nav_events[0] == target_oid
    assert len(close_events) == 1
