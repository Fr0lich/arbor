import pytest
import tkinter as tk
import pandas as pd
from unittest.mock import MagicMock, patch
from models import AppState
from ui.object_problem_resolver import ObjectProblemResolver, ProblemQueueDialog
from ui.main_window import ObjectProgramUI
import config


def test_object_problem_resolver_single_mode_taxonomy_and_provenance():
    root = tk.Tk()
    root.withdraw()
    try:
        app = AppState()
        app.config = config.DATABASE_CONFIGS["Økonomisk Botanisk"]
        app.df_reg = pd.DataFrame([{
            "ObjectID": "1001",
            "Genus": "OldGenus",
            "Species": "sylvestris",
            "Collector": "OldCollector"
        }]).set_index("ObjectID")
        app.df_obs = pd.DataFrame([{
            "ObjectID": "1001",
            "Genus_Problem": True,
            "Collector_Problem": True
        }]).set_index("ObjectID")
        app.df_photo = pd.DataFrame(columns=["ObjectID", "ImagePath"]).set_index("ObjectID")
        app.df_log = pd.DataFrame()
        app._log_records = []
        app.current_object_id = "1001"

        main_app = MagicMock()
        main_app.root = root
        main_app.app = app
        main_app.current_object_id = "1001"
        main_app.problem_to_field = {
            "Genus_Problem": "Genus",
            "Collector_Problem": "Collector"
        }
        main_app.problem_vars = {
            "Genus_Problem": tk.BooleanVar(value=True),
            "Collector_Problem": tk.BooleanVar(value=True)
        }
        main_app.reg_vars = {
            "Genus": tk.StringVar(value="OldGenus"),
            "Collector": tk.StringVar(value="OldCollector")
        }
        main_app.reg_entries = {}
        main_app._cached_reg_dict = {"1001": {"Genus": "OldGenus", "Collector": "OldCollector"}}
        main_app._cached_obs_dict = {"1001": {"Genus_Problem": True, "Collector_Problem": True}}
        main_app.loaded_problem_states = {"Genus_Problem": True, "Collector_Problem": True}
        main_app.push_undo_state = ObjectProgramUI.push_undo_state.__get__(main_app, MagicMock)
        main_app.log_action = MagicMock()

        suggestions = {
            "Genus": {"Pinus": ["Book1.xlsx"]},
            "Collector": {"Smith, J.": ["Book1.xlsx"]}
        }

        with patch("config.load_prefs", return_value={"completed_tutorials": ["historical_resolver"]}):
            resolver = ObjectProblemResolver(main_app, "1001", suggestions)
            
            # Verify queue mode is False for single object
            assert resolver._is_queue_mode is False
            assert resolver.oid == "1001"

            # Check taxonomy detection
            assert "Genus" in resolver._taxonomy_fields
            assert "Collector" not in resolver._taxonomy_fields

            # Provenance field (Collector) must be blank by default regardless of suggestions
            assert resolver.res_vars["Collector"].get() == ""

            # Populate manually or via suggestion
            resolver.res_vars["Genus"].set("Pinus")
            resolver.res_vars["Collector"].set("Smith, J.")

            # Apply
            resolver.apply_all()

            # Verify df_reg and df_obs are updated immediately
            assert app.df_reg.at["1001", "Genus"] == "Pinus"
            assert app.df_reg.at["1001", "Collector"] == "Smith, J."
            assert bool(app.df_obs.at["1001", "Genus_Problem"]) is False
            assert bool(app.df_obs.at["1001", "Collector_Problem"]) is False

            # Undo state recorded
            assert len(app.undo_stacks.get("1001", [])) == 1
    finally:
        root.destroy()


def test_object_problem_resolver_queue_mode_navigation():
    root = tk.Tk()
    root.withdraw()
    try:
        app = AppState()
        app.config = config.DATABASE_CONFIGS["Økonomisk Botanisk"]
        app.df_reg = pd.DataFrame([
            {"ObjectID": "1001", "Genus": "OldGenus1", "Species": "sp1"},
            {"ObjectID": "1002", "Genus": "OldGenus2", "Species": "sp2"},
            {"ObjectID": "1003", "Genus": "OldGenus3", "Species": "sp3"},
        ]).set_index("ObjectID")
        app.df_obs = pd.DataFrame([
            {"ObjectID": "1001", "Genus_Problem": True},
            {"ObjectID": "1002", "Genus_Problem": True},
            {"ObjectID": "1003", "Genus_Problem": True},
        ]).set_index("ObjectID")
        app.df_photo = pd.DataFrame(columns=["ObjectID", "ImagePath"]).set_index("ObjectID")
        app.df_log = pd.DataFrame()
        app._log_records = []
        app.current_object_id = "1001"

        main_app = MagicMock()
        main_app.root = root
        main_app.app = app
        main_app.current_object_id = "1001"
        main_app.problem_to_field = {"Genus_Problem": "Genus"}
        main_app.problem_vars = {"Genus_Problem": tk.BooleanVar(value=True)}
        main_app.reg_vars = {"Genus": tk.StringVar(value="OldGenus1")}
        main_app.reg_entries = {}
        main_app._cached_reg_dict = {}
        main_app._cached_obs_dict = {}
        main_app.loaded_problem_states = {}
        main_app.push_undo_state = ObjectProgramUI.push_undo_state.__get__(main_app, MagicMock)
        main_app.log_action = MagicMock()
        main_app.collect_historical_suggestions = lambda oid, **kwargs: {"Genus": {f"NewGenus_{oid}": ["Book1.xlsx"]}}

        with patch("config.load_prefs", return_value={"completed_tutorials": ["historical_resolver"]}):
            resolver = ObjectProblemResolver(main_app, ["1001", "1002", "1003"])
            
            assert resolver._is_queue_mode is True
            assert resolver.oid == "1001"
            assert resolver._queue_idx == 0

            # Step to next object
            resolver._queue_navigate(1)
            assert resolver.oid == "1002"
            assert resolver._queue_idx == 1

            # Resolve 1002 and apply
            resolver.res_vars["Genus"].set("NewGenus_1002")
            resolver.apply_all()

            # Immediate persistence of 1002
            assert app.df_reg.at["1002", "Genus"] == "NewGenus_1002"
            assert bool(app.df_obs.at["1002", "Genus_Problem"]) is False

            # apply_all in queue mode advances to 1003
            assert resolver.oid == "1003"
            assert resolver._queue_idx == 2
    finally:
        root.destroy()


def test_problem_queue_dialog_filtering_and_matching():
    root = tk.Tk()
    root.withdraw()
    try:
        app = AppState()
        app.config = config.DATABASE_CONFIGS["Økonomisk Botanisk"]
        app.df_reg = pd.DataFrame([
            {"ObjectID": "1", "Genus": "Rosa"},
            {"ObjectID": "2", "Genus": "Quercus"},
            {"ObjectID": "3", "Genus": "Pinus"},
        ]).set_index("ObjectID")
        app.df_obs = pd.DataFrame([
            {"ObjectID": "1", "Genus_Problem": True, "Collector_Problem": False, "Other_problem": False},
            {"ObjectID": "2", "Genus_Problem": False, "Collector_Problem": True, "Other_problem": False},
            {"ObjectID": "3", "Genus_Problem": False, "Collector_Problem": False, "Other_problem": True},
        ]).set_index("ObjectID")
        app.active_object_ids = ["1", "2", "3"]

        main_app = MagicMock()
        main_app.root = root
        main_app.app = app
        main_app._get_obs_dict.return_value = {
            "1": {"Genus_Problem": True, "Collector_Problem": False, "Other_problem": False},
            "2": {"Genus_Problem": False, "Collector_Problem": True, "Other_problem": False},
            "3": {"Genus_Problem": False, "Collector_Problem": False, "Other_problem": True},
        }

        dialog = ProblemQueueDialog(root, main_app)

        # All categories selected -> matches 1, 2, 3
        matching = dialog._get_matching_oids()
        assert set(matching) == {"1", "2", "3"}

        # Deselect collection and notes -> only taxonomy matches (1)
        dialog.cat_collection_var.set(False)
        dialog.cat_notes_var.set(False)
        dialog.cat_physical_var.set(False)
        matching_tax = dialog._get_matching_oids()
        assert matching_tax == ["1"]

        dialog.destroy()
    finally:
        root.destroy()
