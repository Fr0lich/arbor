import pytest
import tkinter as tk
import pandas as pd
from unittest.mock import MagicMock, patch
from models import AppState
from ui.historical_resolver import HistoricalConflictResolverWindow
from ui.main_window import ObjectProgramUI
import config


def test_historical_resolver_apply_creates_undo_snapshot():
    root = tk.Tk()
    try:
        app = AppState()
        app.config = config.DATABASE_CONFIGS["Økonomisk Botanisk"]
        app.df_reg = pd.DataFrame([{"ObjectID": "1001", "Genus": "OldGenus", "Species": "sylvestris"}]).set_index("ObjectID")
        app.df_obs = pd.DataFrame([{"ObjectID": "1001", "Genus_Problem": True}]).set_index("ObjectID")
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
        main_app.reg_vars = {"Genus": tk.StringVar(value="OldGenus")}
        main_app.reg_entries = {}
        main_app._cached_reg_dict = {"1001": {"Genus": "OldGenus"}}
        main_app._cached_obs_dict = {"1001": {"Genus_Problem": True}}
        main_app.loaded_problem_states = {"Genus_Problem": True}

        # Bind real push_undo_state
        main_app.push_undo_state = ObjectProgramUI.push_undo_state.__get__(main_app, MagicMock)
        main_app.log_action = MagicMock()

        suggestions = {"Genus": {"NewGenus": ["DB1"]}}

        with patch("config.load_prefs", return_value={"completed_tutorials": ["historical_resolver"]}):
            resolver = HistoricalConflictResolverWindow(main_app, "1001", suggestions)
            resolver.res_vars["Genus"].set("NewGenus")

            # Before apply, undo stack is empty
            assert len(app.undo_stacks.get("1001", [])) == 0

            # Apply resolution
            resolver.fields = ["Genus"]
            resolver.apply_all()

            # Undo stack must have captured the pre-resolution state
            assert len(app.undo_stacks.get("1001", [])) == 1
            snapshot = app.undo_stacks["1001"][-1]
            assert snapshot["reg"]["Genus"] == "OldGenus"
            assert bool(snapshot["obs"]["Genus_Problem"]) is True

            # And in-memory DataFrame was updated
            assert app.df_reg.at["1001", "Genus"] == "NewGenus"
            assert bool(app.df_obs.at["1001", "Genus_Problem"]) is False
    finally:
        root.destroy()


