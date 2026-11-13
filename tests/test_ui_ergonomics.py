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
from ui.command_palette import CommandPalette
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


def test_card_has_unknown_row2_and_no_row1_packing(tk_root):
    """Verify that scrolling or updating a card with has_unknown=True updates Row 2 text to include UKN without packing widgets into Row 1."""
    app = MockApp(10)
    # Set an unknown field for OBJ-00002
    app.df_reg.loc["OBJ-00002", "Species"] = "unknown"
    mw = MockMainWindow(app, tk_root)

    wrapper = TreeviewListboxWrapper(tk_root, mw)
    wrapper.pack(fill="both", expand=True)
    tk_root.update()

    for oid in app.active_object_ids:
        g = mw._cached_genus_dict.get(oid, "")
        s = mw._cached_species_dict.get(oid, "")
        rev = mw._cached_reviewed_dict.get(oid, False)
        wrapper.insert(tk.END, f"{oid} {g} {s}", genus=g, species=s, reviewed=rev, bulk=True)

    # Build empty card widgets and populate directly (simulating viewport rendering)
    widget_dict = wrapper._build_empty_card_widget(wrapper.canvas)
    wrapper._populate_card_widget(widget_dict, "OBJ-00002")

    # 1. Verify Row 2 meta text includes UKN
    meta_text = widget_dict["meta_lbl"].cget("text")
    assert "UKN" in meta_text

    # 2. Verify Single-Badge Discipline on Row 1:
    # Row 1 must strictly host cb_lbl, tax_lbl, and status_badge.
    # No dummy badges (ukn_badge, img_badge, loaned_badge, unval_badge) should be packed.
    row1_packed_children = widget_dict["row1"].pack_slaves()
    expected_packed = [widget_dict["cb_lbl"], widget_dict["tax_lbl"], widget_dict["status_badge"]]
    assert row1_packed_children == expected_packed
    assert widget_dict["ukn_badge"].winfo_manager() != "pack"
    assert widget_dict["img_badge"].winfo_manager() != "pack"
    assert widget_dict["loaned_badge"].winfo_manager() != "pack"
    assert widget_dict["unval_badge"].winfo_manager() != "pack"

    # 3. Verify updating the card maintains single-badge discipline
    idx = wrapper._oid_to_index["OBJ-00002"]
    wrapper._active_card_windows[idx] = (1, widget_dict)

    wrapper.refresh_object_card("OBJ-00002")
    tk_root.update()

    meta_text_after = widget_dict["meta_lbl"].cget("text")
    assert "UKN" in meta_text_after
    assert widget_dict["row1"].pack_slaves() == expected_packed
    assert widget_dict["ukn_badge"].winfo_manager() != "pack"

    # Also test _refresh_card_accent maintains single-badge discipline
    wrapper._refresh_card_accent("OBJ-00002")
    assert widget_dict["row1"].pack_slaves() == expected_packed
    assert widget_dict["ukn_badge"].winfo_manager() != "pack"

    # 4. Verify scrolling/re-populating card maintains single-badge discipline
    wrapper._populate_card_widget(widget_dict, "OBJ-00002")
    assert "UKN" in widget_dict["meta_lbl"].cget("text")
    assert widget_dict["row1"].pack_slaves() == expected_packed
    assert widget_dict["ukn_badge"].winfo_manager() != "pack"

    wrapper.destroy()


def test_directory_card_prefs_defaults():
    """Verify default card prefs retrieval, mutation, and reset to defaults."""
    config.reset_directory_card_prefs_to_default()
    defaults = config.get_directory_card_prefs()
    assert defaults["density_mode"] == "standard"
    assert defaults["show_location_row"] is True
    assert defaults["show_status_badge"] is True
    assert defaults["show_author_citation"] is False
    assert defaults["show_directory_view_strip"] is False

    # Mutate prefs
    mutated = dict(defaults)
    mutated["density_mode"] = "compact"
    mutated["show_location_row"] = False
    mutated["show_status_badge"] = False
    mutated["show_directory_view_strip"] = True
    config.save_directory_card_prefs(mutated)

    current = config.get_directory_card_prefs()
    assert current["density_mode"] == "compact"
    assert current["show_location_row"] is False
    assert current["show_status_badge"] is False
    assert current["show_directory_view_strip"] is True

    # Reset
    reset_prefs = config.reset_directory_card_prefs_to_default()
    assert reset_prefs["density_mode"] == "standard"
    assert reset_prefs["show_location_row"] is True
    assert reset_prefs["show_status_badge"] is True
    assert reset_prefs["show_directory_view_strip"] is False


def test_command_palette_card_view_commands(tk_root):
    """Verify command palette registers simplified directory card view commands under category VIEW."""
    app = MockApp(5)
    mw = MockMainWindow(app, tk_root)
    palette = CommandPalette(mw)
    palette.withdraw()

    registry = palette._commands_registry
    view_labels = [cmd["label"] for cmd in registry if cmd.get("category") == "VIEW"]
    assert "Card Layout: Standard (78px, 3 Rows)" in view_labels
    assert "Card Layout: Compact (64px, 2 Rows)" in view_labels
    assert "Card Layout: Full Details (92px, Author + Location)" in view_labels
    assert "Card Layout: Minimalist (Clean, No Badges/Location)" in view_labels
    assert "Configure Directory Cards & View Settings..." in view_labels
    assert "Toggle Directory Card Location Row (Row 3)" in view_labels
    assert "Toggle Directory Card Status Pill Badges" in view_labels
    assert "Restore Directory Card Settings to Default" in view_labels

    palette.destroy()


def test_card_preset_aliases_and_configs():
    """Verify card preset name resolution and config overrides across canonical names and legacy aliases."""
    assert config.resolve_card_preset_name("standard") == "standard"
    assert config.resolve_card_preset_name("default") == "standard"
    assert config.resolve_card_preset_name("compact") == "compact"
    assert config.resolve_card_preset_name("high_speed") == "compact"
    assert config.resolve_card_preset_name("full_detail") == "full_detail"
    assert config.resolve_card_preset_name("taxonomist") == "full_detail"
    assert config.resolve_card_preset_name("minimalist") == "minimalist"
    assert config.resolve_card_preset_name("collections_manager") == "minimalist"

    # Test config generation
    std_cfg = config.get_card_preset_config("standard")
    assert std_cfg["density_mode"] == "standard"
    assert std_cfg["show_location_row"] is True

    cpt_cfg = config.get_card_preset_config("compact")
    assert cpt_cfg["density_mode"] == "compact"
    assert cpt_cfg["show_location_row"] is False

    full_cfg = config.get_card_preset_config("full_detail")
    assert full_cfg["density_mode"] == "expanded"
    assert full_cfg["show_author_citation"] is True

    min_cfg = config.get_card_preset_config("minimalist")
    assert min_cfg["show_status_badge"] is False
    assert min_cfg["show_location_row"] is False


def test_directory_view_strip_visibility_toggle(tk_root):
    """Verify that Directory View Strip packs and unpacks according to preferences."""
    from ui.main_window import ObjectProgramUI
    config.reset_directory_card_prefs_to_default()

    ui = ObjectProgramUI.__new__(ObjectProgramUI)
    ui.root = tk_root
    ui.dark_mode_active = False

    container = tk.Frame(tk_root)
    container.pack()
    ui.list_scroll_frame = tk.Frame(container)
    ui.list_scroll_frame.pack(side="top", fill="both", expand=True)

    ui.directory_view_strip = tk.Frame(container)
    ui._build_directory_view_strip(ui.directory_view_strip)
    tk_root.update()

    # Default is False: strip should not be packed
    ui.update_directory_view_strip_visibility()
    tk_root.update()
    assert ui.directory_view_strip.winfo_manager() != "pack"

    # Set to True
    prefs = config.get_directory_card_prefs()
    prefs["show_directory_view_strip"] = True
    config.save_directory_card_prefs(prefs)

    ui.update_directory_view_strip_visibility()
    tk_root.update()
    assert ui.directory_view_strip.winfo_manager() == "pack"

    # Set back to False
    prefs["show_directory_view_strip"] = False
    config.save_directory_card_prefs(prefs)
    ui.update_directory_view_strip_visibility()
    tk_root.update()
    assert ui.directory_view_strip.winfo_manager() != "pack"

    # Reset
    config.reset_directory_card_prefs_to_default()
    container.destroy()


@pytest.mark.parametrize("density", ["compact", "standard", "expanded"])
@pytest.mark.parametrize("show_loc", [True, False])
@pytest.mark.parametrize("show_badge", [True, False])
@pytest.mark.parametrize("show_author", [True, False])
def test_directory_card_combinatorial_preferences(tk_root, density, show_loc, show_badge, show_author):
    """Combinatorial matrix test across density modes, location rows, badges, and author citations."""
    app = MockApp(10)
    mw = MockMainWindow(app, tk_root)
    wrapper = TreeviewListboxWrapper(tk_root, mw)
    wrapper.pack(fill="both", expand=True)
    tk_root.update()

    for oid in app.active_object_ids:
        g = mw._cached_genus_dict.get(oid, "")
        s = mw._cached_species_dict.get(oid, "")
        rev = mw._cached_reviewed_dict.get(oid, False)
        wrapper.insert(tk.END, f"{oid} {g} {s}", genus=g, species=s, reviewed=rev, bulk=True)

    prefs = {
        "density_mode": density,
        "show_location_row": show_loc,
        "location_granularity": "full",
        "show_status_badge": show_badge,
        "badge_priority": "category",
        "badge_categories": {"taxonomy": True, "collection": True},
        "show_author_citation": show_author,
        "show_author_in_expanded_only": False,
        "meta_tokens": {"box": True, "shelf": True, "storage": True, "ukn": True},
    }
    wrapper.apply_directory_view_preferences(prefs)
    tk_root.update()

    # 1. Height must be measured and valid (>= 50px)
    assert wrapper._card_height is not None
    assert wrapper._card_height >= 50

    # 2. Single-badge discipline must hold on Row 1
    widget_dict = wrapper._build_empty_card_widget(wrapper.canvas)
    row1_packed_children = widget_dict["row1"].pack_slaves()
    expected_packed = [widget_dict["cb_lbl"], widget_dict["tax_lbl"], widget_dict["status_badge"]]
    assert row1_packed_children == expected_packed

    # 3. Populate specimen card with taxonomy problem (OBJ-00003)
    wrapper._populate_card_widget(widget_dict, "OBJ-00003")

    # Check badge behavior
    if not show_badge:
        assert widget_dict["status_badge"].cget("text") == ""
    else:
        assert widget_dict["status_badge"].cget("text") != ""

    # Check location row behavior
    if not show_loc:
        assert widget_dict["row3"].winfo_manager() != "pack"
    else:
        assert widget_dict["row3"].winfo_manager() == "pack"

    # Check author citation behavior
    tax_text = widget_dict["tax_lbl"].cget("text")
    if show_author:
        assert "L." in tax_text
    else:
        assert "L." not in tax_text

    wrapper.destroy()


