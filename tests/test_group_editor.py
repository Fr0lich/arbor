import pytest
import tkinter as tk
from unittest.mock import MagicMock, patch
from ui.group_editor import FieldGroupEditorDialog

def test_field_group_editor_dialog_init():
    root = tk.Tk()
    root.withdraw()  # hide main window

    all_fields = ["Genus", "Species", "Collector", "CustomField"]
    current_groups = [
        {"name": "Taxonomy", "fields": ["Genus", "Species"]},
        {"name": "Collection", "fields": ["Collector"]}
    ]

    saved_groups = []
    def on_save(groups):
        saved_groups.append(groups)

    # Instantiate dialog
    dialog = FieldGroupEditorDialog(root, all_fields, current_groups, on_save)

    # 1. Verify Groups initialization
    # Miscellaneous tab should have been automatically added for "CustomField"
    assert len(dialog.groups) == 3
    assert dialog.groups[0]["name"] == "Taxonomy"
    assert dialog.groups[1]["name"] == "Collection"
    assert dialog.groups[2]["name"] == "Miscellaneous"
    assert dialog.groups[2]["fields"] == ["CustomField"]

    # 2. Verify Tab Listbox population
    assert dialog.tabs_listbox.size() == 3
    assert dialog.tabs_listbox.get(0) == "Taxonomy"
    assert dialog.tabs_listbox.get(1) == "Collection"
    assert dialog.tabs_listbox.get(2) == "Miscellaneous"

    # 3. Save Settings should trigger the callback
    dialog.save_settings()
    assert len(saved_groups) == 1
    assert saved_groups[0][0]["name"] == "Taxonomy"
    assert saved_groups[0][2]["name"] == "Miscellaneous"

    root.destroy()

def test_field_group_editor_dialog_move_field():
    root = tk.Tk()
    root.withdraw()

    all_fields = ["Genus", "Species"]
    current_groups = [
        {"name": "Taxonomy", "fields": ["Genus", "Species"]}
    ]

    dialog = FieldGroupEditorDialog(root, all_fields, current_groups, lambda g: None)

    # Select the Taxonomy tab
    dialog.tabs_listbox.selection_clear(0, tk.END)
    dialog.tabs_listbox.selection_set(0)
    dialog.on_tab_select(None)

    # Check fields in the listbox
    assert dialog.fields_listbox.size() == 2
    assert dialog.fields_listbox.get(0) == "Genus"
    assert dialog.fields_listbox.get(1) == "Species"

    # Select "Genus" (index 0) and move it down
    dialog.fields_listbox.selection_clear(0, tk.END)
    dialog.fields_listbox.selection_set(0)

    dialog.move_field_order(1)  # move down

    # Genus and Species should have swapped places
    assert dialog.groups[0]["fields"] == ["Species", "Genus"]

    root.destroy()
