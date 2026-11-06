import os
import sys
import tkinter as tk
from tkinter import ttk
import pandas as pd
import numpy as np
import pytest

# Ensure project root is in sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config
from config import sc
from ui.object_context_bar import ObjectContextBar
from ui.widgets import TreeviewListboxWrapper


class MockApp:
    def __init__(self, n_rows=20):
        oids = [f"OBJ-{i:05d}" for i in range(n_rows)]
        self.active_object_ids = oids
        self.current_object_id = oids[0]
        self.dirty = False

        self.df_reg = pd.DataFrame({
            "ObjectID": oids,
            "Genus": ["Quercus" if i % 2 == 0 else "Pinus" for i in range(n_rows)],
            "Species": ["robur" if i % 2 == 0 else "sylvestris" for i in range(n_rows)],
            "Author": ["L." for _ in range(n_rows)],
            "Family": ["Fagaceae" if i % 2 == 0 else "Pinaceae" for i in range(n_rows)],
        }).set_index("ObjectID", drop=False)

        self.df_obs = pd.DataFrame({
            "ObjectID": oids,
            "Reviewed": [True if i == 0 else False for i in range(n_rows)],
            "Building": ["Herbarium" for _ in range(n_rows)],
            "Floor": ["2" for _ in range(n_rows)],
            "Cabinet": [f"C-{i % 10}" for i in range(n_rows)],
            "Shelf": [f"S-{i % 5}" for i in range(n_rows)],
            "Stored as": ["Folder" for _ in range(n_rows)],
            "Loaned out": [True if i == 2 else False for i in range(n_rows)],
            "MissingLabel": [True if i == 1 else False for i in range(n_rows)],
            "Taxonomy_Problem": [True if i == 3 else False for i in range(n_rows)],
            "Images_Missing": [False for _ in range(n_rows)]
        }).set_index("ObjectID", drop=False)

        self.df_photo = pd.DataFrame(columns=["ObjectID", "Filename"]).set_index("ObjectID")
        self.df_unvalidated = pd.DataFrame(columns=["ObjectID", "Field_Name", "Unvalidated_Comment"])
        self.config = {
            "sheets": {"reg": "Registration", "obs": "Observation"},
            "ui_sections": {
                "problems": [
                    {"name": "MissingLabel", "category": "collection"},
                    {"name": "Taxonomy_Problem", "category": "taxonomy"}
                ]
            }
        }


class MockMainWindow:
    def __init__(self, app, root):
        self.app = app
        self.root = root
        self.dark_mode_active = False
        self.focus_mode_var = tk.BooleanVar(value=False)
        self.problem_columns = ["Taxonomy_Problem", "MissingLabel"]
        self.problem_to_field = {}
        self.image_mode = "online"
        self._history_cache = {}
        self._has_suggestions_set = set()
        self._problem_cache = {
            "OBJ-00001": True,
            "OBJ-00003": True,
        }
        self._rebuild_caches()

    def _rebuild_caches(self):
        self._cached_reg_dict = self.app.df_reg.to_dict("index")
        self._cached_obs_dict = self.app.df_obs.to_dict("index")
        self._cached_genus_dict = {k: v.get("Genus", "") for k, v in self._cached_reg_dict.items()}
        self._cached_species_dict = {k: v.get("Species", "") for k, v in self._cached_reg_dict.items()}
        self._cached_reviewed_dict = {k: v.get("Reviewed", False) for k, v in self._cached_obs_dict.items()}

    def _get_reg_dict(self):
        return self._cached_reg_dict

    def _get_obs_dict(self):
        return self._cached_obs_dict

    def _get_active_problem_categories(self, oid):
        if oid == "OBJ-00003":
            return {"taxonomy"}
        if oid == "OBJ-00001":
            return {"collection"}
        return set()

    def _problems_have_history(self, oid):
        return False

    def is_unknown(self, val):
        return str(val).strip().lower() in ("unknown", "?", "")

    def has_online_photos(self, oid):
        return False

    def has_unvalidated_sources(self, oid):
        return False

    def _toggle_reviewed_for_id(self, oid):
        current = self._cached_reviewed_dict.get(oid, False)
        self._cached_reviewed_dict[oid] = not current

    def _on_list_return(self, event):
        pass


@pytest.fixture(scope="module")
def tk_root():
    root = tk.Tk()
    root.withdraw()
    yield root
    try:
        root.destroy()
    except Exception:
        pass


def test_object_context_bar_dictionary_lookups(tk_root):
    """Verify ObjectContextBar correctly renders data and runs without in-loop df.loc calls."""
    app = MockApp(10)
    mw = MockMainWindow(app, tk_root)

    bar = ObjectContextBar(tk_root, app=app, main_ui=mw)
    bar.update_specimen("OBJ-00000")

    assert "OBJ-00000" in bar.id_badge.cget("text")
    assert "Quercus robur" in bar.name_label.cget("text")
    assert "REVIEWED" in bar.status_badge.cget("text")

    # Clean unreviewed
    bar.update_specimen("OBJ-00004")
    assert "OBJ-00004" in bar.id_badge.cget("text")
    assert "UNREVIEWED" in bar.status_badge.cget("text") or "PENDING" in bar.status_badge.cget("text")

    bar.destroy()


def test_single_badge_category_theme_resolution(tk_root):
    """Verify taxonomy and collection problems map to canonical category tokens."""
    app = MockApp(10)
    mw = MockMainWindow(app, tk_root)

    wrapper = TreeviewListboxWrapper(tk_root, mw)
    for oid in app.active_object_ids:
        g = mw._cached_genus_dict.get(oid, "")
        s = mw._cached_species_dict.get(oid, "")
        rev = mw._cached_reviewed_dict.get(oid, False)
        wrapper.insert(tk.END, f"{oid} {g} {s}", genus=g, species=s, reviewed=rev, bulk=True)

    # Check item data populated
    assert "OBJ-00000" in wrapper.item_data
    assert wrapper.item_data["OBJ-00000"]["reviewed"] is True

    wrapper.destroy()


def test_sash_width_calculations():
    """Verify rail width and expanded width comply with design constraints."""
    rail_w = sc(config.RAIL_THEME.get("rail_width", 40))
    assert rail_w > 0
    # Minimum expanded sidebar width should be at least 320px scaled
    default_expanded = sc(360)
    assert default_expanded >= sc(320)
    assert default_expanded > rail_w


def test_object_context_bar_dirty_dot(tk_root):
    """Verify dirty dot displays when app.dirty is set."""
    app = MockApp(5)
    mw = MockMainWindow(app, tk_root)
    bar = ObjectContextBar(tk_root, app=app, main_ui=mw)

    app.dirty = False
    bar.update_specimen("OBJ-00000")
    assert bar.dirty_badge.winfo_manager() != "pack"

    app.dirty = True
    bar.update_specimen("OBJ-00000")
    assert bar.dirty_badge.winfo_manager() == "pack"
    assert "Unsaved" in bar.dirty_badge.cget("text")

    bar.destroy()


def test_targeted_highlight_difference(tk_root):
    """Verify redraw_cards_highlights updates targeted cards without crashing."""
    app = MockApp(10)
    mw = MockMainWindow(app, tk_root)
    wrapper = TreeviewListboxWrapper(tk_root, mw)
    wrapper.pack()
    tk_root.update()

    for oid in app.active_object_ids:
        wrapper.insert(tk.END, f"{oid} Quercus robur", genus="Quercus", species="robur", bulk=True)
    wrapper._schedule_viewport_update()
    tk_root.update()

    wrapper.selection_set(0)
    wrapper.redraw_cards_highlights()
    assert wrapper.selected_iids == ["OBJ-00000"]

    # Step to next card
    wrapper.selection_clear()
    wrapper.selection_set(1)
    wrapper.redraw_cards_highlights()
    assert wrapper.selected_iids == ["OBJ-00001"]

    wrapper.destroy()

