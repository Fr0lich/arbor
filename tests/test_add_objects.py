import pytest
import tkinter as tk
import pandas as pd
from ui.add_objects import AddObjectsWizard
from repository import REVIEWED_COLUMN

class DummyApp:
    def __init__(self):
        self.config_name = "Test DB"
        self.config = {
            "ui_sections": {
                "registration": [
                    {"name": "Genus", "type": "text"},
                    {"name": "Species", "type": "text"},
                    {"name": "Status", "type": "choice", "choices": ["Valid", "Draft"]}
                ],
                "location": [
                    {"name": "Building", "type": "text"},
                    {"name": "Floor", "type": "choice", "choices": ["1", "2"]},
                    {"name": "Is_Cabinet", "type": "checkbox"}
                ],
                "problems": [
                    {"name": "Images_Problem", "type": "bool"},
                    {"name": "Other_problem", "type": "bool"}
                ]
            }
        }
        self.df_reg = pd.DataFrame(
            {"Genus": ["Quercus"], "Species": ["robur"], "Status": ["Valid"]},
            index=["1"]
        )
        self.df_reg.index.name = "ObjectID"
        self.df_obs = pd.DataFrame(
            {
                "Building": ["Main"], "Floor": ["1"], "Is_Cabinet": ["True"],
                "Images_Missing": [False], "Images_Problem": [False], "Images_Wrong": [False],
                REVIEWED_COLUMN: [False], "ReviewedAt": [""], "Online_Images_Exist": [False],
                "Other_problem": [False]
            },
            index=["1"]
        )
        self.df_obs.index.name = "ObjectID"
        self.df_photo = pd.DataFrame()
        self.active_object_ids = ["1"]
        self.dirty = False

class DummyMainWindow:
    def __init__(self, root, app):
        self.root = root
        self.app = app
        self.refreshed = False
        self.invalidated_cache = False
        self.invalidated_search = False
        self.dirty_updated = False
        self.count_updated = False
        self.progress_updated = False
        self.logged_actions = []

    def _invalidate_row_cache(self):
        self.invalidated_cache = True

    def invalidate_search_index(self):
        self.invalidated_search = True

    def refresh_list(self):
        self.refreshed = True

    def update_dirty_ui(self):
        self.dirty_updated = True

    def update_object_count(self):
        self.count_updated = True

    def update_review_progress(self):
        self.progress_updated = True

    def log_action(self, action, fields, details):
        self.logged_actions.append((action, fields, details))

from unittest.mock import patch

@pytest.fixture
def tk_env():
    root = tk.Tk()
    root.withdraw()
    app = DummyApp()
    mw = DummyMainWindow(root, app)
    with patch("tkinter.messagebox.showinfo"), \
         patch("tkinter.messagebox.showwarning"), \
         patch("tkinter.messagebox.showerror"):
        yield root, app, mw
    try:
        root.destroy()
    except Exception:
        pass

def test_wizard_init_and_render_step1(tk_env):
    root, app, mw = tk_env
    wizard = AddObjectsWizard(root, app, mw)
    assert wizard.win is not None
    assert wizard.current_step == 0
    assert wizard.subtitle_lbl.cget("text") == "1. Object IDs"
    assert wizard.target_listbox is not None
    wizard.win.destroy()

def test_auto_id_generation(tk_env):
    root, app, mw = tk_env
    wizard = AddObjectsWizard(root, app, mw)
    wizard.auto_n_var.set(3)
    wizard._generate_auto_ids()
    
    # Existing max numeric ID was 1, so auto generates 2, 3, 4
    target_oids = wizard._get_target_oids()
    assert target_oids == ["2", "3", "4"]
    assert "2" in wizard.staged_data
    assert "3" in wizard.staged_data
    assert "4" in wizard.staged_data
    wizard.win.destroy()

def test_manual_id_addition_and_removal(tk_env):
    root, app, mw = tk_env
    wizard = AddObjectsWizard(root, app, mw)
    wizard.manual_ids_var.set("A10, B20, 1") # 1 already exists in df_reg
    wizard._add_manual_ids()
    
    target_oids = wizard._get_target_oids()
    assert "A10" in target_oids
    assert "B20" in target_oids
    assert "1" not in target_oids # Prevent duplicates with database
    
    # Select A10 and remove it
    wizard.target_listbox.selection_clear(0, tk.END)
    wizard.target_listbox.selection_set(0)
    wizard._remove_selected_id()
    assert "A10" not in wizard._get_target_oids()
    assert "A10" not in wizard.staged_data
    assert "B20" in wizard._get_target_oids()
    wizard.win.destroy()

def test_step_transitions_and_metadata_editing(tk_env):
    root, app, mw = tk_env
    wizard = AddObjectsWizard(root, app, mw)
    wizard.manual_ids_var.set("OBJ_X")
    wizard._add_manual_ids()
    
    # Advance to step 2
    wizard._on_next()
    assert wizard.current_step == 1
    assert wizard.subtitle_lbl.cget("text") == "2. Initial Metadata"
    assert "Genus" in wizard.field_vars
    
    wizard.field_vars["Genus"].set("Betula")
    wizard.field_vars["Building"].set("North Wing")
    
    # Advance to step 3
    wizard._on_next()
    assert wizard.current_step == 2
    assert wizard.subtitle_lbl.cget("text") == "3. Review & Create"
    assert wizard.staged_data["OBJ_X"]["Genus"] == "Betula"
    assert wizard.staged_data["OBJ_X"]["Building"] == "North Wing"
    
    # Go back to step 2
    wizard._on_back()
    assert wizard.current_step == 1
    wizard.win.destroy()

def test_create_objects_commit(tk_env):
    root, app, mw = tk_env
    wizard = AddObjectsWizard(root, app, mw)
    wizard.manual_ids_var.set("NEW_1, NEW_2")
    wizard._add_manual_ids()
    
    # Customize NEW_1
    wizard.staged_data["NEW_1"]["Genus"] = "Acer"
    wizard.staged_data["NEW_1"]["Building"] = "Herbarium"
    
    wizard._create_objects()
    
    # Verify DataFrames updated
    assert "NEW_1" in app.df_reg.index
    assert "NEW_2" in app.df_reg.index
    assert app.df_reg.loc["NEW_1", "Genus"] == "Acer"
    assert app.df_obs.loc["NEW_1", "Building"] == "Herbarium"
    assert bool(app.df_obs.loc["NEW_1", "Images_Missing"]) is True
    assert bool(app.df_obs.loc["NEW_1", REVIEWED_COLUMN]) is False
    
    assert "NEW_1" in app.active_object_ids
    assert "NEW_2" in app.active_object_ids
    assert app.dirty is True
    assert mw.refreshed is True
    assert mw.invalidated_cache is True


    assert len(mw.logged_actions) == 2
