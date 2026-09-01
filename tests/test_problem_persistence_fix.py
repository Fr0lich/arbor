import pytest
import pandas as pd
import tkinter as tk
from ui.main_window import ObjectProgramUI
from ui.historical_resolver import HistoricalConflictResolverWindow
from ui.widgets import TreeviewListboxWrapper
from ui.image_panel import ImagePanel
from unittest.mock import MagicMock

class MockApp:
    def __init__(self, df_reg, df_obs):
        self.df_reg = df_reg
        self.df_obs = df_obs
        self.current_object_id = None
        self.active_object_ids = list(df_reg.index)
        self.output_path = ""
        self.excel_path = ""
        self.df_log = pd.DataFrame()
        self._log_records = []
        self.undo_stacks = {}
        self.redo_stacks = {}
        self.historical_dbs = []
        self.df_photo = None
        self.dirty = False
        self.config = {
            "ui_sections": {
                "registration": [
                    {"name": "Genus", "type": "text", "maps_to": "Genus_Problem"},
                    {"name": "Species", "type": "text", "maps_to": "Species_Problem"}
                ],
                "problems": [
                    {"name": "Genus_Problem", "type": "bool", "maps_to": "Genus"},
                    {"name": "Species_Problem", "type": "bool", "maps_to": "Species"}
                ],
                "location": []
            },
            "problems": [
                {"name": "Genus_Problem", "type": "bool", "maps_to": "Genus"},
                {"name": "Species_Problem", "type": "bool", "maps_to": "Species"}
            ]
        }

def create_mock_ui(root, app):
    app.config = {
        "ui_sections": {
            "problems": [
                {"name": "Genus_Problem", "type": "bool", "maps_to": "Genus"},
                {"name": "Species_Problem", "type": "bool", "maps_to": "Species"}
            ],
            "registration": [
                {"name": "Genus", "type": "text"},
                {"name": "Species", "type": "text"}
            ]
        }
    }
    mw = ObjectProgramUI(root, app)
    mw.initializing = False
    mw.reg_by_id = app.df_reg
    mw.obs_by_id = app.df_obs
    mw.problem_to_field = {"Genus_Problem": "Genus", "Species_Problem": "Species"}
    mw.problem_columns = ["Genus_Problem", "Species_Problem"]
    mw.reg_columns = ["Genus", "Species"]
    mw.choice_fields = set()
    mw.image_panel = MagicMock()
    mw.image_panel.image_zoom_factor = 1.0
    mw.image_panel.image_rotation_angle = 0
    mw.image_panel.images_missing_var = tk.StringVar()
    mw.image_panel.images_missing_label = tk.Label(root)
    mw.image_panel.image_container = tk.Frame(root)
    mw.image_panel.show_images_var = tk.BooleanVar(value=True)
    mw.image_panel.show_image_tools_var = tk.BooleanVar(value=True)
    mw._preload_adjacent_images = MagicMock()

    mw.show_all_history_var = tk.BooleanVar(value=False)
    mw.current_object_suggestions = {}
    mw.reg_vars = {"Genus": tk.StringVar(), "Species": tk.StringVar()}
    mw.problem_vars = {"Genus_Problem": tk.BooleanVar(), "Species_Problem": tk.BooleanVar()}
    mw.reg_entries = {
        "Genus": tk.Entry(root, textvariable=mw.reg_vars["Genus"]),
        "Species": tk.Entry(root, textvariable=mw.reg_vars["Species"])
    }
    mw.reg_entry_list = list(mw.reg_entries.values())
    mw.location_vars = {}
    mw.reviewed_var = tk.BooleanVar(value=False)
    mw.reviewed_time_label = tk.Label(root)
    mw.title_label = tk.Label(root)
    mw.object_id_var = tk.StringVar()
    mw.no_image_label = tk.Label(root)
    mw.location_summary_label = tk.Label(root)
    mw.no_problems_msg_label = tk.Label(root)
    mw.object_list = TreeviewListboxWrapper(root, mw)

    return mw

def test_manual_edit_clears_auto_problem_and_persists():
    """Verifies that editing a field with an auto-detected problem clears the problem flag and persists across object navigation."""
    try:
        root = tk.Tk()
        root.withdraw()
    except Exception:
        pytest.skip("Tkinter display not available")

    df_reg = pd.DataFrame({
        "ObjectID": ["OBJ1", "OBJ2"],
        "Genus": ["", "Abies"],
        "Species": ["", "alba"]
    }).set_index("ObjectID")

    df_obs = pd.DataFrame({
        "ObjectID": ["OBJ1", "OBJ2"],
        "Genus_Problem": [False, False],
        "Species_Problem": [False, False],
        "Reviewed": [False, False]
    }).set_index("ObjectID")

    app = MockApp(df_reg, df_obs)
    mw = create_mock_ui(root, app)

    # Load OBJ1 (has blank Genus -> auto_val = True for Genus_Problem)
    mw.load_object("OBJ1")
    assert bool(mw.problem_vars["Genus_Problem"].get()) is True
    assert app.df_reg.at["OBJ1", "Genus"] == ""

    # User manually types "Pinus" into Genus
    mw.reg_vars["Genus"].set("Pinus")

    # Navigate to OBJ2 (should commit OBJ1 changes first)
    mw.load_object("OBJ2")

    # Verify OBJ1 in df_reg is now "Pinus" and Genus_Problem in df_obs is False
    assert app.df_reg.at["OBJ1", "Genus"] == "Pinus"
    assert bool(app.df_obs.at["OBJ1", "Genus_Problem"]) is False

    # Navigate back to OBJ1
    mw.load_object("OBJ1")
    assert mw.reg_vars["Genus"].get() == "Pinus"
    assert bool(mw.problem_vars["Genus_Problem"].get()) is False

    root.destroy()

def test_historical_resolver_persistence():
    """Verifies that applying a resolution via HistoricalConflictResolverWindow updates caches, df_reg, and df_obs across navigation."""
    try:
        root = tk.Tk()
        root.withdraw()
    except Exception:
        pytest.skip("Tkinter display not available")

    df_reg = pd.DataFrame({
        "ObjectID": ["OBJ1", "OBJ2"],
        "Genus": ["", "Picea"],
        "Species": ["", "abies"]
    }).set_index("ObjectID")

    df_obs = pd.DataFrame({
        "ObjectID": ["OBJ1", "OBJ2"],
        "Genus_Problem": [True, False],
        "Species_Problem": [False, False],
        "Reviewed": [False, False]
    }).set_index("ObjectID")

    app = MockApp(df_reg, df_obs)
    mw = create_mock_ui(root, app)

    mw.load_object("OBJ1")
    assert bool(mw.problem_vars["Genus_Problem"].get()) is True

    # Open resolver with suggestions structure: {field: {value: {source_name}}}
    suggestions = {"Genus": {"Pinus": {"DB1"}}}
    resolver = HistoricalConflictResolverWindow(mw, "OBJ1", suggestions)
    resolver.res_vars["Genus"].set("Pinus")
    resolver.apply_all()

    # Verify DF updated and problem cleared
    assert app.df_reg.at["OBJ1", "Genus"] == "Pinus"
    assert bool(app.df_obs.at["OBJ1", "Genus_Problem"]) is False

    # Navigate to OBJ2 and back to OBJ1
    mw.load_object("OBJ2")
    mw.load_object("OBJ1")

    assert mw.reg_vars["Genus"].get() == "Pinus"
    assert bool(mw.problem_vars["Genus_Problem"].get()) is False

    root.destroy()

def test_card_live_update():
    """Verifies that refresh_object_card updates card taxonomy labels live when an object field is edited."""
    try:
        root = tk.Tk()
        root.withdraw()
    except Exception:
        pytest.skip("Tkinter display not available")

    df_reg = pd.DataFrame({
        "ObjectID": ["OBJ1"],
        "Genus": ["Quercus"],
        "Species": ["robur"]
    }).set_index("ObjectID")

    df_obs = pd.DataFrame({
        "ObjectID": ["OBJ1"],
        "Genus_Problem": [False],
        "Species_Problem": [False],
        "Reviewed": [False]
    }).set_index("ObjectID")

    app = MockApp(df_reg, df_obs)
    mw = create_mock_ui(root, app)

    listbox = mw.object_list
    listbox.insert(0, "OBJ1", genus="Quercus", species="robur")
    mw.load_object("OBJ1")

    # Change genus to "Betula"
    mw.reg_vars["Genus"].set("Betula")
    mw.commit_current_object()

    # Verify item_data in listbox has been refreshed live
    assert listbox.item_data["OBJ1"]["genus"] == "Betula"
    assert listbox.item_data["OBJ1"]["values"] == ["☐", "OBJ1", "Betula", "robur"]

    root.destroy()

def test_unknown_fixed_removes_yellow_highlights():
    """Verifies that replacing an unknown value removes yellow background highlights and updates card status badge away from yellow UKN."""
    try:
        root = tk.Tk()
        root.withdraw()
    except Exception:
        pytest.skip("Tkinter display not available")

    df_reg = pd.DataFrame({
        "ObjectID": ["OBJ1"],
        "Genus": ["Unknown"],
        "Species": ["sylvestris"]
    }).set_index("ObjectID")

    df_obs = pd.DataFrame({
        "ObjectID": ["OBJ1"],
        "Genus_Problem": [False],
        "Species_Problem": [False],
        "Reviewed": [False]
    }).set_index("ObjectID")

    app = MockApp(df_reg, df_obs)
    mw = create_mock_ui(root, app)

    mw.load_object("OBJ1")
    assert mw.is_unknown(mw.reg_vars["Genus"].get()) is True

    # Fix the unknown value
    mw.reg_vars["Genus"].set("Pinus")
    mw.commit_current_object()

    # Re-validate fields
    mw._validate_fields()
    genus_bg = mw.reg_entries["Genus"].cget("background")
    assert genus_bg != "#ffe4b3"
    assert genus_bg != "#fff3a3"

    # Test card status badge fallback for clean unreviewed object is UNREV (not bright yellow UKN)
    widgets = mw.object_list._build_empty_card_widget(mw.object_list.canvas)
    populated = mw.object_list._populate_card_widget(widgets, "OBJ1")
    status_badge = widgets["status_badge"]
    assert status_badge.cget("text") == "UNREV"

    root.destroy()

def test_invalidate_row_cache_and_undo_redo_sync():
    """Verifies that _invalidate_row_cache properly clears problem caches and undo/redo updates problem flags."""
    try:
        root = tk.Tk()
        root.withdraw()
    except Exception:
        pytest.skip("Tkinter display not available")

    df_reg = pd.DataFrame({
        "ObjectID": ["OBJ1"],
        "Genus": ["Pinus"],
        "Species": ["sylvestris"]
    }).set_index("ObjectID")

    df_obs = pd.DataFrame({
        "ObjectID": ["OBJ1"],
        "Genus_Problem": [False],
        "Species_Problem": [False],
        "Reviewed": [False]
    }).set_index("ObjectID")

    app = MockApp(df_reg, df_obs)
    mw = create_mock_ui(root, app)
    mw.load_object("OBJ1")

    # Pre-populate problem cache
    mw._problem_cache["OBJ1"] = False
    assert mw._problem_cache.get("OBJ1") is False

    # Perform an edit that introduces a problem
    mw.reg_vars["Genus"].set("")
    mw.commit_current_object()

    # Verify problem cache is cleared/invalidated for OBJ1
    assert "OBJ1" not in mw._problem_cache or mw._problem_cache["OBJ1"] is True
    assert mw.is_problem_active("OBJ1", "Genus_Problem") is True

    # Test Undo
    mw.undo()
    assert mw.reg_vars["Genus"].get() == "Pinus"
    assert mw.is_problem_active("OBJ1", "Genus_Problem") is False

    # Test Redo
    mw.redo()
    assert mw.reg_vars["Genus"].get() == ""
    assert mw.is_problem_active("OBJ1", "Genus_Problem") is True

    root.destroy()

def test_is_problem_active_safe_lookup_nonexistent_ids():
    """Verifies that is_problem_active safely returns False for non-existent IDs without raising KeyError."""
    try:
        root = tk.Tk()
        root.withdraw()
    except Exception:
        pytest.skip("Tkinter display not available")

    df_reg = pd.DataFrame({
        "ObjectID": ["OBJ1"],
        "Genus": ["Pinus"],
        "Species": ["sylvestris"]
    }).set_index("ObjectID")

    df_obs = pd.DataFrame({
        "ObjectID": ["OBJ1"],
        "Genus_Problem": [False],
        "Species_Problem": [False],
        "Reviewed": [False]
    }).set_index("ObjectID")

    app = MockApp(df_reg, df_obs)
    mw = create_mock_ui(root, app)

    # Calling with a non-existent ObjectID should safely return False
    assert mw.is_problem_active("NON_EXISTENT", "Other_problem") is False
    assert mw.is_problem_active("NON_EXISTENT", "Reviewed") is False
    assert mw.is_problem_active("NON_EXISTENT", "Genus_Problem") is False
    assert mw.is_problem_active(99999, "Genus_Problem") is False

    root.destroy()
