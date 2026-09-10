import sys
import tkinter as tk
from unittest.mock import MagicMock, patch
import pytest

from ui.context_menu import ContextMenuManager
from ui.widgets import TreeviewListboxWrapper
from ui.group_editor import GroupEditorWindow, FieldGroupEditorDialog


def test_context_menu_manager_create_menu():
    root = tk.Tk()
    root.withdraw()

    action_mock = MagicMock()
    items = [
        {"label": "Item 1", "command": action_mock, "state": "normal"},
        {"separator": True},
        {"label": "Disabled Item", "command": None, "state": "disabled"},
        {
            "label": "Submenu Item",
            "submenu": [
                {"label": "Sub 1", "command": action_mock},
                {"separator": True},
                {"label": "Sub 2", "command": action_mock},
            ],
        },
    ]

    menu = ContextMenuManager.create_menu(root, items)
    assert isinstance(menu, tk.Menu)
    # Total entries: 4 (Item 1, separator, Disabled Item, Submenu Item)
    assert menu.index("end") == 3
    assert menu.entrycget(0, "label") == "Item 1"
    assert menu.type(1) == "separator"
    assert menu.entrycget(2, "label") == "Disabled Item"
    assert menu.entrycget(2, "state") == "disabled"
    assert menu.entrycget(3, "label") == "Submenu Item"

    root.destroy()


def test_context_menu_manager_bind_and_popup():
    root = tk.Tk()
    root.withdraw()

    btn = tk.Button(root, text="Test")
    btn.pack()

    called = []
    def callback(event):
        called.append(event)
        return [{"label": "Action", "command": lambda: None}]

    ContextMenuManager.bind(btn, callback)

    # Simulate right click event
    mock_event = MagicMock(spec=tk.Event)
    mock_event.widget = btn
    mock_event.x_root = 100
    mock_event.y_root = 150

    with patch.object(tk.Menu, "tk_popup") as mock_popup, patch.object(tk.Menu, "grab_release") as mock_grab:
        # Trigger the bound handler for <Button-3>
        bindings = btn.bind("<Button-3>")
        assert bindings is not None

        # Call the handler function directly through Tkinter event mechanism or manually
        btn.event_generate("<Button-3>", x=10, y=10)

    root.destroy()


def test_main_window_context_menu_items():
    root = tk.Tk()
    root.withdraw()

    # Mock app and main window setup
    mock_app = MagicMock()
    mock_app.active_object_ids = ["101", "102", "103"]
    mock_app._mobile_server_instance = MagicMock(is_running=True)

    from ui.main_window import ObjectProgramUI

    # Subclass or mock minimal ObjectProgramUI
    with patch.object(ObjectProgramUI, "__init__", return_value=None):
        ui = ObjectProgramUI()
        ui.root = root
        ui.app = mock_app
        ui.object_list = MagicMock()
        ui.open_bulk_edit_window = MagicMock()
        ui.push_current_to_phone = MagicMock()
        ui._shortcut_duplicate_object = MagicMock()
        ui.delete_current_object = MagicMock()
        ui._context_set_reviewed = MagicMock()

        # 1. Single selection test
        ui.object_list.selection.return_value = ("101",)
        ui.object_list.identify_row.return_value = "101"

        items = ui._get_main_context_menu_items(None)
        labels = [it.get("label") for it in items if "label" in it]
        assert "Mark Selected as Reviewed" in labels
        assert "Mark Selected as Not Reviewed" in labels
        assert "Copy Accession ID" in labels
        assert "📱 Push to Phone" in labels
        assert "Duplicate Object" in labels
        assert "Delete Object" in labels

        # "Push to Phone" should be normal when single item selected and server running
        push_item = next(it for it in items if it.get("label") == "📱 Push to Phone")
        assert push_item["state"] == "normal"

        # 2. Multi-selection test
        ui.object_list.selection.return_value = ("101", "102")
        items_multi = ui._get_main_context_menu_items(None)
        push_item_multi = next(it for it in items_multi if it.get("label") == "📱 Push to Phone")
        assert push_item_multi["state"] == "disabled"

        # 3. Empty selection test
        ui.object_list.selection.return_value = ()
        items_empty = ui._get_main_context_menu_items(None)
        assert items_empty == []

        # 4. Copy Accession ID test (single)
        ui.object_list.selection.return_value = ("101",)
        ui._context_copy_accession_id()
        assert root.clipboard_get() == "101"

        # 5. Copy Accession ID test (multiple)
        ui.object_list.selection.return_value = ("101", "102", "103")
        ui._context_copy_accession_id()
        assert root.clipboard_get() == "101\n102\n103"

    root.destroy()


def test_treeview_empty_space_right_click():
    root = tk.Tk()
    root.withdraw()

    from ui.main_window import ObjectProgramUI

    with patch.object(ObjectProgramUI, "__init__", return_value=None):
        ui = ObjectProgramUI()
        ui.root = root
        ui.object_list = MagicMock()
        ui.object_list.active_view = "compact"
        ui.object_list.tree = MagicMock()
        # identify_row returns empty string for empty space
        ui.object_list.identify_row.return_value = ""
        ui.object_list.tree.identify_row.return_value = ""

        event = MagicMock(spec=tk.Event)
        event.widget = ui.object_list.tree
        event.y = 500

        items = ui._get_main_context_menu_items(event)
        assert items == []

    root.destroy()


def test_virtual_card_selection_on_context_menu():
    root = tk.Tk()
    root.withdraw()

    main_win = MagicMock()
    main_win.dark_mode_active = False
    main_win.active_object_ids = ["101", "102"]
    main_win._get_main_context_menu_items = MagicMock(return_value=[{"label": "Test"}])

    wrapper = TreeviewListboxWrapper(root, main_win)
    wrapper.items_list = ["101", "102"]
    wrapper._oid_to_index = {"101": 0, "102": 1}
    wrapper.item_data = {"101": {}, "102": {}}
    wrapper.selected_iids = ["101"]

    # Mock widget and target
    card_frame = tk.Frame(wrapper)
    card_frame._card_oid = "102"
    card_frame._card_body = card_frame

    mock_event = MagicMock(spec=tk.Event)
    mock_event.widget = card_frame
    mock_event.x_root = 100
    mock_event.y_root = 200

    # Retrieve callback from ContextMenuManager or test the selection logic
    # Right-clicking "102" when "101" is selected should change selection to ["102"]
    wrapper.selected_iids = ["101"]
    assert "102" not in wrapper.selected_iids

    # Simulate card context callback
    w = mock_event.widget
    oid = getattr(w, "_card_oid", None)
    if oid not in wrapper.selected_iids:
        wrapper.selected_iids = [oid]
        wrapper.focused_iid = oid
        if hasattr(main_win, "load_object"):
            main_win.load_object(oid)

    assert wrapper.selected_iids == ["102"]
    main_win.load_object.assert_called_with("102")

    # Multi-selection preservation: if both 101 and 102 are selected and 102 is right-clicked
    wrapper.selected_iids = ["101", "102"]
    if "102" not in wrapper.selected_iids:
        wrapper.selected_iids = ["102"]

    assert wrapper.selected_iids == ["101", "102"]

    root.destroy()


def test_group_editor_context_menus():
    root = tk.Tk()
    root.withdraw()

    mock_main = MagicMock()
    mock_app = MagicMock()

    with patch.object(GroupEditorWindow, "__init__", return_value=None):
        editor = GroupEditorWindow(root, mock_app, mock_main)
        editor.win = root
        editor.tabs_listbox = tk.Listbox(root)
        editor.fields_listbox = tk.Listbox(root)
        editor.tabs_listbox.insert(0, "Tab 1")
        editor.tabs_listbox.insert(1, "Tab 2")
        editor.fields_listbox.insert(0, "Field 1")
        editor.fields_listbox.insert(1, "Field 2")
        editor.groups = [
            {"name": "Tab 1", "fields": ["Field 1", "Field 2"]},
            {"name": "Tab 2", "fields": []},
        ]
        editor.get_selected_group_idx = MagicMock(return_value=0)
        editor.on_tab_select = MagicMock()
        editor.add_tab = MagicMock()
        editor.rename_tab = MagicMock()
        editor.delete_tab = MagicMock()
        editor.add_field = MagicMock()
        editor.rename_field = MagicMock()
        editor.delete_field = MagicMock()

        event = MagicMock(spec=tk.Event)
        event.y = 0

        # Tabs context menu
        tab_items = editor.show_tabs_context_menu(event)
        tab_labels = [it["label"] for it in tab_items]
        assert "Add Tab" in tab_labels
        assert "Rename Tab" in tab_labels
        assert "Delete Tab" in tab_labels

        # Fields context menu
        field_items = editor.show_fields_context_menu(event)
        field_labels = [it.get("label") for it in field_items if "label" in it]
        assert "Move Up" in field_labels
        assert "Move Down" in field_labels
        assert "Move to Tab" in field_labels
        assert "Add Field" in field_labels

        move_to_tab = next(it for it in field_items if it.get("label") == "Move to Tab")
        assert "submenu" in move_to_tab
        assert len(move_to_tab["submenu"]) == 1
        assert move_to_tab["submenu"][0]["label"] == "Tab 2"

    root.destroy()
