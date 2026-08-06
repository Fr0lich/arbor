"""
ui/main_window.py

This module implements the main workspace layout (primary layout) of the arbor application.
It integrates various mixins (Autosave, ImageHandler, Suggestions, etc.) and constructs the
dynamic database visualizer window using Tkinter.
"""

from ui.widgets import ToggleSwitch, TreeviewListboxWrapper
from ui.autosave_handler import AutosaveMixin
from ui.image_handler import ImageHandlerMixin
from ui.historical_suggestions import HistoricalSuggestionsMixin
from ui.layout_settings import LayoutSettingsMixin
from ui.dashboard import DashboardMixin
from ui.database_ops import DatabaseOpsMixin

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import os
import re
import time
import threading
from datetime import datetime
import pandas as pd
import getpass
from PIL import Image, ImageTk

# Pre-compiled regex patterns for speed optimization
_NUMERIC_OID_PATTERN = re.compile(r"\b(\d+)\b")
_NORMALIZE_NON_WORD_PATTERN = re.compile(r'[^\w\s]')
_NORMALIZE_SPACE_PATTERN = re.compile(r'\s+')

from io import BytesIO
import json
import uuid

from collections import OrderedDict
from config import DATABASE_CONFIGS, AUTOSAVE_INTERVAL_MS, AUTOSAVE_SUFFIX, sc
from repository import ExcelRepository, REVIEWED_COLUMN, REVIEWED_AT_COLUMN, ONLINE_EXISTS_COLUMN
from models import AppState
from utils import debug_error

class LabelWrapper:
    def __init__(self, real_label, ui):
        self.real = real_label
        self.ui = ui
        
    def config(self, cnf=None, **kw):
        if cnf is not None:
            kw.update(cnf)
        text = kw.get("text")
        if text is not None:
            if hasattr(self.ui, "_loading_window") and self.ui._loading_window and self.ui._loading_window.win.winfo_exists():
                self.ui._loading_window.update_status_text(text)
        try:
            return self.real.config(**kw)
        except Exception:
            pass
            
    def configure(self, cnf=None, **kw):
        return self.config(cnf, **kw)
        
    def cget(self, option):
        return self.real.cget(option)
        
    def __getitem__(self, key):
        return self.real[key]
        
    def __setitem__(self, key, value):
        self.real[key] = value
        if key == "text":
            if hasattr(self.ui, "_loading_window") and self.ui._loading_window and self.ui._loading_window.win.winfo_exists():
                self.ui._loading_window.update_status_text(value)
                
    def __getattr__(self, name):
        return getattr(self.real, name)


class ProgressbarWrapper:
    def __init__(self, real_progressbar, ui):
        self.real = real_progressbar
        self.ui = ui
        
    def configure(self, cnf=None, **kw):
        if cnf is not None:
            kw.update(cnf)
        value = kw.get("value")
        maximum = kw.get("maximum")
        
        if hasattr(self.ui, "_loading_window") and self.ui._loading_window and self.ui._loading_window.win.winfo_exists():
            self.ui._loading_window.update_progress_bar(value, maximum)
        try:
            return self.real.configure(**kw)
        except Exception:
            pass
            
    def config(self, cnf=None, **kw):
        return self.configure(cnf, **kw)
        
    def cget(self, option):
        return self.real.cget(option)
        
    def __getitem__(self, key):
        return self.real[key]
        
    def __setitem__(self, key, value):
        self.real[key] = value
        if key == "value":
            if hasattr(self.ui, "_loading_window") and self.ui._loading_window and self.ui._loading_window.win.winfo_exists():
                self.ui._loading_window.update_progress_bar(value=value)
                
    def __getattr__(self, name):
        return getattr(self.real, name)

# BulkEditWindow, NewDatabaseWizard, AddObjectsWindow, ZoomableImagePopup, and
# requests are imported lazily inside the methods that need them so that startup
# time is not spent loading unused subsystems.

MAX_IMAGE_CACHE = 40



class ObjectProgramUI(
    AutosaveMixin,
    ImageHandlerMixin,
    HistoricalSuggestionsMixin,
    LayoutSettingsMixin,
    DashboardMixin,
    DatabaseOpsMixin
):
# ---------- UI helpers ----------
    @property
    def autoAdvanceOnReview(self):
        return self.auto_advance_var.get()

    @autoAdvanceOnReview.setter
    def autoAdvanceOnReview(self, val):
        self.auto_advance_var.set(bool(val))

    def labeled_entry(self, parent, text, textvar):
        """
        Lager en flyttbar rad med Label + Entry
        """
        frame = ttk.Frame(parent)
        lbl = ttk.Label(frame, text=text, width=25)
        ent = ttk.Entry(frame, textvariable=textvar)

        lbl.grid(row=0, column=0, sticky="w", padx=(0, 6))
        ent.grid(row=0, column=1, sticky="ew")

        frame.columnconfigure(1, weight=1)
        return frame

    def __init__(self, root, app: AppState):




        self.root = root
        self.app = app
        self._loading_window = None

        if self.app.undo_stacks is None:
            self.app.undo_stacks = {}


        self.object_loaded = False
        self._image_paths = []
        self._rendered_paths = None
        self._thumb_cards = []

        self.history_stack = []

        self.last_object_id = None

        self.reg_vars = {}
        self.reg_entries = {}
        self.reg_row_frames = {}
        self._accordion_collapsed = {}
        self._accordion_groups = {}

        self.focus_mode_var = tk.BooleanVar(value=False)
        self.focus_fallback_var = tk.BooleanVar(value=True)
        self.focus_visibility_vars = {}
        self.forward_stack = []

        self.problem_vars = {}
        self.prob_border_bars = {}   # tk.Frame border bar per mapped problem field
        self.prob_label_widgets = {} # ttk.Label per mapped problem field
        self.location_vars = {}
        self.filter_vars = {}
        self.images_missing_var = tk.StringVar(value="")
        
        self.toolbar_buttons = {}
        self.toolbar_vars = {}
        
        self.show_list_var = tk.BooleanVar(value=True)
        self.show_search_var = tk.BooleanVar(value=True)
        self.show_images_var = tk.BooleanVar(value=True)
        self.location_in_center_var = tk.BooleanVar(value=False)
        self.show_image_tools_var = tk.BooleanVar(value=True)
        self.show_bulk_edit_var = tk.BooleanVar(value=True)
        self.show_reg_var = tk.BooleanVar(value=True)
        
        self.snap_lock_var = tk.BooleanVar(value=False)
        self.image_stack_var = tk.BooleanVar(value=False)
        self.dashboard_mode_var = tk.StringVar(value="Window")
        self.focus_dynamic_update_var = tk.BooleanVar(value=True)
        self.layout_dynamic_update_var = tk.BooleanVar(value=True)
        self.large_reviewed_button_var = tk.BooleanVar(value=True)
        self.auto_advance_var = tk.BooleanVar(value=True)



        self.image_render_cache = OrderedDict()
        self.dark_mode_active = False
        self.ignored_words_file = "ignored_words.json"
        self.ignored_words = []
        self.ignored_words_variations = tk.BooleanVar(value=True)
        self.load_ignored_words()
        self.original_pil_cache = OrderedDict()
        self.image_zoom_factor = 1.0
        self.image_rotation_angle = 0
        self.filter_window = None
        self.history_window = None
        self.recent_window = None
        self.sort_directions = {"ID": True, "Genus": True, "Species": True, "Status": True}
        self.status_badge_colors = {
            "saved": {"bg": "#d4edda", "fg": "#155724"},
            "autosaved": {"bg": "#e2f0fe", "fg": "#0a58ca"},
            "unsaved": {"bg": "#fff3cd", "fg": "#856404"},
            "error": {"bg": "#f8d7da", "fg": "#721c24"}
        }

        self.filter_mode = tk.StringVar(value="AND")

        self.root.title("arbor")
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        self.image_mode = None  # "folder" eller "online"
        self.image_folder = None
        self.image_index = {}   # ObjectID -> list of file paths
        self.image_status = {}
        self.image_cache = OrderedDict()  # url -> ImageTk.PhotoImage


        # Lazy-initialized on first image fetch; see _get_http_session()
        self.http = None
        self._image_load_token = 0
        self.image_view_mode = "gallery"  # eller "stack"

        self._history_cache = OrderedDict()

        self._problem_cache = {}

        self._list_dirty = False
        self._inline_search_job = None       # debounce timer for live search
        self._banner_timer_id = None
        self._search_index_cache = None      # lazy search index {oid: token_string}

        # Row-dict caches for refresh_list() — rebuilt only when data changes
        self._cached_reg_dict: dict = None   # type: ignore[assignment]
        self._cached_obs_dict: dict = None   # type: ignore[assignment]
        self._cached_reviewed_dict: dict = {}
        self._cached_genus_dict: dict = {}
        self._cached_species_dict: dict = {}
        self._row_cache_dirty: bool = True

        self.problem_to_field = {}
        self.problem_columns = []
        self.location_columns = []
        self.filter_problems = []

        self._nav_job = None
        self._nav_pending_step = 0

        self._is_navigating = False
        self._nav_idle_job = None

        show_all = False



        

        self.root.bind("<Left>", self._safe_nav_left)
        self.root.bind("<Right>", self._safe_nav_right)
        
        self.root.bind("<Control-n>", lambda e: self.add_new_object())
        self.root.bind("<Control-N>", lambda e: self._quick_new_object())
        self.root.bind("<Control-D>", lambda e: self._duplicate_current_object())
        self.root.bind("<Control-Delete>", lambda e: self.delete_current_object())
        
        # Dashboard toggle
        self.root.bind("<Control-j>", lambda e: self.open_session_dashboard_window())
        self.root.bind("<Control-s>", lambda e: self.save_session("SAVE"))
        self.root.bind("<Control-g>", lambda e: self.open_filter_menu())
        self.root.bind("<Control-z>", self._smart_undo)
        self.root.bind("<Control-y>", self.redo)
        self.root.bind("<Control-n>", self._shortcut_new_object)
        self.root.bind("<F1>", lambda e: self.show_shortcuts())
        self.root.bind("<Control-r>", lambda e: self.mark_current_as_reviewed())
        self.root.bind("<Control-Return>", lambda e: self.mark_current_as_reviewed())
        self.root.bind("<Control-KP_Enter>", lambda e: self.mark_current_as_reviewed())

        self.root.bind("<space>", self._toggle_problem_checkbox)

        self.root.bind("<Control-f>", self.focus_search)
        self.root.bind("<Control-q>", self.toggle_focus_mode_shortcut)
        self.root.bind("<Control-h>", self.open_history_shortcut)

        self.root.bind("<Control-e>", self._focus_first_reg)
        self.root.bind("<Control-Prior>", lambda e: self._switch_reg_tab(-1))
        self.root.bind("<Control-Next>", lambda e: self._switch_reg_tab(1))

        self.root.bind("<Shift-E>", lambda e: self.focus_first_empty_reg())


        self.root.bind("<Control-l>", self._focus_first_location)
        self.root.bind("<Control-p>", self._focus_first_problem)
        self.root.bind("<Control-i>", self._focus_first_reg)
        self.root.bind("<Control-o>", self._focus_object_list)
        self.root.bind("<Control-Shift-P>", self._focus_first_problem)
        self.root.bind("<F3>", self._focus_first_problem)
        self.root.bind("<Control-Shift-L>", self._focus_first_location)
        self.root.bind("<F4>", self._focus_first_location)

        self.root.bind("<Alt-Left>", lambda e: self.go_back())
        self.root.bind("<Alt-Right>", lambda e: self.go_forward())


        self.root.bind("<Control-b>", self._next_image_shortcut)
        self.root.bind("<Shift-Left>", self._prev_image_shortcut)
        self.root.bind("<Shift-Right>", self._next_image_shortcut)
        self.root.bind("<Control-plus>", lambda e: self.zoom_image_in())
        self.root.bind("<Control-equal>", lambda e: self.zoom_image_in())
        self.root.bind("<Control-minus>", lambda e: self.zoom_image_out())
        self.root.bind("<Control-r>", lambda e: self.rotate_image())
        self.root.bind("<Control-R>", lambda e: self.rotate_image())
        self.root.bind("<Control-Key-0>", lambda e: self.reset_image_view())


        self.root.bind("<Control-Delete>", self._shortcut_delete_object)
        self.root.bind("<Control-Shift-N>", self._shortcut_quick_new_object)
        self.root.bind("<Control-Shift-D>", self._shortcut_duplicate_object)
        self.root.bind("<Control-Shift-C>", self._copy_field_value)
        self.root.bind("<Control-Shift-V>", self._paste_field_value)

        self.root.bind("<Control-k>", self._apply_default_data_preset_shortcut)
        self.root.bind("<Control-K>", self._apply_default_data_preset_shortcut)

        # Collapsible Panel Toggles for Laptop Views
        self.root.bind("<F6>", self.toggle_list_panel_shortcut)
        self.root.bind("<F7>", self.toggle_reg_panel_shortcut)
        self.root.bind("<F8>", self.toggle_images_panel_shortcut)



        self._skip_validation_once = False


        self.field_undo_stack = []

        if self.app.redo_stacks is None:
            self.app.redo_stacks = {}

        self.loading_object = False
        self.initializing = True


        self.object_id_var = tk.StringVar()
        self._init_focus_prefs()
        self.build_menu()
        self.build_ui()
        self.apply_saved_layout()
        self._autosave_job = None
        self.root.bind("<Button-1>", self._hide_search_if_outside)
        style = ttk.Style(self.root)


        self.filter_location_vars = {
            "Building": tk.StringVar(value=""),
            "Floor": tk.StringVar(value=""),
            "Cabinet": tk.StringVar(value="")
        }


        self.filter_modes = {
            "Problems": tk.StringVar(value="OR"),
            "Images": tk.StringVar(value="OR"),
            "Status": tk.StringVar(value="OR"),
            "Text": tk.StringVar(value="OR"),
            "Unknown": tk.StringVar(value="OR"),
        }

        style.configure(
            "Dirty.TButton",
            foreground="red"
        )


        style.configure(
            "HistoryHighlight.TLabel",
            background="#fff3a3",   # lys gul
            font=("Segoe UI", sc(10), "bold")
        )


        self.update_history_button_state()
        style.configure(
            "Highlight.TEntry",
            fieldbackground="#fff3a3"  # lys gul
        )

        style.configure("Hover.TLabel", background="#eeeeee")
        style.configure("Hover.TFrame", background="#eeeeee")


    def _get_http_session(self):
        """Return the shared requests.Session, creating it on first call.

        The session is not created during __init__ because it triggers network
        library initialisation which is slow and unnecessary in offline/folder mode.
        """
        if self.http is None:
            import requests
            self.http = requests.Session()
        return self.http

    def apply_config(self):
        """Apply the active database config to the UI.

        Reads self.app.config and rebuilds all column maps, filter variable
        dicts, and field lists (reg_columns, location_columns, problem_columns,
        problem_to_field, filter_problems). Then calls build_sections() to
        re-create all field widgets.

        Must be called whenever self.app.config changes (i.e. after opening a
        new file with a different config key).
        """
        sections = self.app.config["ui_sections"]

        self.problem_to_field = {}
        self.problem_columns = []
        self.location_columns = []
        self.reg_columns = []
        self.choice_fields = set()

        self.unknown_fields = [
            u["maps_to"] for u in sections.get("unknown_fields", [])
        ]

        # REG
        for field in sections["registration"]:
            self.reg_columns.append(field["name"])
            if field.get("type") == "choice":
                self.choice_fields.add(field["name"])

        # LOCATION
        for field in sections["location"]:
            self.location_columns.append(field["name"])

        # PROBLEMS
        for field in sections["problems"]:
            name = field["name"]
            self.problem_columns.append(name)

            if "maps_to" in field:
                self.problem_to_field[name] = field["maps_to"]

        # filter (som fÃ¸r)
        self.filter_problems = self.problem_columns + [
            "Images_Missing",
            "Has_Images",
            "Reviewed",
            "Not_Reviewed",
            "Comment_Empty",
            "Comment_Not_Empty",
            "Extra_Empty",
            "Extra_Not_Empty",
        ]

        self.filter_vars = {
            col: tk.BooleanVar(value=False)
            for col in self.filter_problems
        }

        self.filter_vars["Any_Problem"] = tk.BooleanVar(value=False)
        # Status combination filters
        self.filter_vars["Reviewed_With_Problem"] = tk.BooleanVar(value=False)
        self.filter_vars["Problem_With_History"]  = tk.BooleanVar(value=False)
        self.filter_vars["Has_History"]           = tk.BooleanVar(value=False)



        
        self.build_sections()

#-- BUILD SECTIONS

    def _init_focus_prefs(self):
        import config
        prefs = config.load_prefs() or {}
        if "focus_presets" not in prefs:
            prefs["focus_presets"] = {}
            
        self.focus_mode_var.set(prefs.get("focus_mode_active", False))
        self.focus_fallback_var.set(prefs.get("focus_fallback", True))
        
        saved_vis = prefs.get("focus_visibility", {})
        
        self.focus_visibility_vars["Problems"] = tk.BooleanVar(value=saved_vis.get("Problems", True))
        self.focus_visibility_vars["Location"] = tk.BooleanVar(value=saved_vis.get("Location", True))
        
        # Note: Dynamic registration fields will be initialized in build_sections()

    def _rebuild_focus_registration_menu(self):
        if not hasattr(self, "focus_reg_menu"):
            return
        self.focus_reg_menu.delete(0, 'end')
        
        if getattr(self.app, "config", None) and "ui_sections" in self.app.config:
            import config
            prefs = config.load_prefs() or {}
            saved_vis = prefs.get("focus_visibility", {})
            
            for field in self.app.config["ui_sections"].get("registration", []):
                name = field["name"]
                if name not in self.focus_visibility_vars:
                    self.focus_visibility_vars[name] = tk.BooleanVar(value=saved_vis.get(name, True))
                    
                self.focus_reg_menu.add_checkbutton(
                    label=name, 
                    variable=self.focus_visibility_vars[name], 
                    command=self.update_reg_fields_visibility
                )



    def _create_loc_widget(self, parent, name, ftype, field_def, font_family, font_size, bg_col, fg_col, bd_col, is_horiz=False):
        var = self.location_vars.get(name)
        if not var: return None
        
        container = tk.Frame(parent, bg=bg_col)
        
        if ftype == "checkbox":
            cb_frame = tk.Frame(container, bg=bg_col)
            cb_frame.pack(fill="x")
            
            # Custom checkbox style
            cb = tk.Checkbutton(
                cb_frame, 
                text="ACTIVE LOAN" if is_horiz else "ACTIVE LOAN STATUS", 
                variable=var,
                onvalue="True", offvalue="False",
                command=lambda n=name, v=var: self._on_checkbox_change(n, v),
                bg=bg_col, fg="#000000",
                font=("JetBrains Mono", sc(font_size), "bold"),
                activebackground=bg_col,
                activeforeground="#000000",
                highlightthickness=0, bd=0
            )
            cb.pack(side="left")
            widget = cb
        else:
            if is_horiz:
                # Label on top
                lbl = tk.Label(container, text=name.upper(), font=("JetBrains Mono", sc(font_size-2), "bold"),
                             bg=bg_col, fg="#444748", anchor="w")
                lbl.pack(fill="x", pady=(0,2))
            else:
                # Label on left
                lbl = tk.Label(container, text=name.upper(), width=14, font=("JetBrains Mono", sc(font_size), "bold"),
                             bg=bg_col, fg="#444748", anchor="w")
                lbl.pack(side="left")

            if ftype == "choice":
                choices = field_def.get("choices", [])
                if "" not in choices:
                    choices = [""] + choices
                widget = ttk.Combobox(
                    container, textvariable=var,
                    values=choices,
                    state="readonly" if name != "Stored as" else "normal",
                    font=(font_family, sc(font_size))
                )
                widget.bind("<<ComboboxSelected>>", lambda e: self.commit_current_object())
                if is_horiz:
                    widget.pack(fill="x", expand=True)
                else:
                    widget.pack(side="left", fill="x", expand=True)
            else:
                widget = tk.Entry(
                    container, textvariable=var,
                    state="disabled" if field_def.get("readonly") else "normal",
                    font=(font_family, sc(font_size)),
                    bg="#ffffff", fg="#000000",
                    insertbackground="#000000",
                    highlightthickness=1, highlightbackground=bd_col, highlightcolor="#000000",
                    relief="flat"
                )
                widget.bind("<FocusOut>", lambda e: self.commit_current_object())
                if is_horiz:
                    widget.pack(fill="x", expand=True)
                else:
                    widget.pack(side="left", fill="x", expand=True)
        
        self.location_entries.append(widget)
        widget.bind("<Shift-Up>", self._location_nav_up)
        widget.bind("<Shift-Down>", self._location_nav_down)
        widget.bind("<Control-Up>", self._location_nav_up)
        widget.bind("<Control-Down>", self._location_nav_down)
        widget.bind("<Return>", self._location_nav_down)
        
        return container

    def _build_presets_ui(self, parent_frame, bg_col, bd_col, is_horiz):
        presets_frame = tk.Frame(parent_frame, bg=bg_col)
        
        import config
        prefs = config.load_prefs()
        preset_names = list(prefs.get("data_presets", {}).keys())
        
        if not hasattr(self, "active_preset_var"):
            self.active_preset_var = tk.StringVar()
            if "Default" in preset_names:
                self.active_preset_var.set("Default")
            elif preset_names:
                self.active_preset_var.set(preset_names[0])
                
        self.active_preset_cb = ttk.Combobox(
            presets_frame, 
            textvariable=self.active_preset_var, 
            values=preset_names, 
            state="normal", 
            width=8 if is_horiz else 12
        )
        self.active_preset_cb.pack(side="left", padx=4)
        self.add_tooltip(self.active_preset_cb, "The preset that will be applied when you press Ctrl+K")
        
        def save_current_as_preset():
            name = self.active_preset_var.get().strip()
            if not name:
                name = "Default"
                self.active_preset_var.set(name)
                
            prefs = config.load_prefs()
            if "data_presets" not in prefs:
                prefs["data_presets"] = {}
                
            vals = {}
            for k, var in self.location_vars.items():
                v = var.get().strip()
                if v:
                    vals[k] = v
                    
            prefs["data_presets"][name] = vals
            config.save_prefs(prefs)
            self.app.config_prefs = prefs
            
            names = list(prefs["data_presets"].keys())
            self.active_preset_cb["values"] = names
            self.system_status.config(text=f"Saved preset: {name}")
            self._refresh_load_data_preset_menu()

        save_btn = ttk.Button(presets_frame, text="Save", width=5, command=save_current_as_preset)
        save_btn.pack(side="left", padx=2)
        self.add_tooltip(save_btn, "Save current Location fields to this preset")
        
        apply_btn = ttk.Button(presets_frame, text="Apply", width=5, command=self._apply_default_data_preset_shortcut)
        apply_btn.pack(side="left", padx=2)
        self.add_tooltip(apply_btn, "Apply this preset to the fields above (Ctrl+K)")
        
        return presets_frame

    def _build_vertical_location_ui(self):
        bg_col = "#ffffff"
        bd_col = "#d1d1d1"
        
        main_box = tk.Frame(self.location_frame, bg=bg_col, highlightthickness=1, highlightbackground=bd_col)
        main_box.pack(fill="both", expand=True, padx=4, pady=4)
        
        # Header
        hdr = tk.Frame(main_box, bg="#f3f3f3", highlightthickness=0)
        hdr.pack(fill="x")
        
        title = tk.Label(hdr, text="LOCATION", font=("Hanken Grotesk", sc(12), "bold"), bg="#f3f3f3", fg="#000000")
        title.pack(side="left", padx=8, pady=4)
        
        tk.Frame(main_box, bg=bd_col, height=1).pack(fill="x") # sep
        
        content = tk.Frame(main_box, bg=bg_col)
        content.pack(fill="both", expand=True, padx=12, pady=12)
        
        field_names_order = ["Stored as", "Building", "Floor", "Cabinet", "Extra"]
        
        for name in field_names_order:
            field = next((f for f in self.app.config["ui_sections"]["location"] if f["name"] == name), None)
            if not field: continue
            
            row = self._create_loc_widget(content, name, field.get("type", "text"), field, "JetBrains Mono", 10, bg_col, "#000000", bd_col, is_horiz=False)
            if row:
                row.pack(fill="x", pady=4)
                
        tk.Frame(content, bg=bd_col, height=1).pack(fill="x", pady=8) # sep
        
        loan_field = next((f for f in self.app.config["ui_sections"]["location"] if f["name"] == "Loaned out"), None)
        if loan_field:
            row = self._create_loc_widget(content, "Loaned out", "checkbox", loan_field, "JetBrains Mono", 10, bg_col, "#000000", bd_col, is_horiz=False)
            if row:
                children = row.winfo_children()
                if children:
                    cb_frame = children[0]
                    presets_ui = self._build_presets_ui(cb_frame, bg_col, bd_col, is_horiz=False)
                    presets_ui.pack(side="right", padx=(10, 0))
                row.pack(fill="x", pady=4)

    def _build_horizontal_location_ui(self):
        bg_col = "#ffffff"
        bd_col = "#d1d1d1"
        
        main_box = tk.Frame(self.loc_frame_horizontal, bg=bg_col, highlightthickness=1, highlightbackground=bd_col)
        main_box.pack(fill="both", expand=True, padx=4, pady=4)
        
        # Header
        hdr = tk.Frame(main_box, bg="#f3f3f3", highlightthickness=0)
        hdr.pack(fill="x")
        
        title = tk.Label(hdr, text="LOCATION", font=("JetBrains Mono", sc(10), "bold"), bg="#f3f3f3", fg="#444748")
        title.pack(side="left", padx=8, pady=4)
        
        loan_field = next((f for f in self.app.config["ui_sections"]["location"] if f["name"] == "Loaned out"), None)
        if loan_field:
            row = self._create_loc_widget(hdr, "Loaned out", "checkbox", loan_field, "JetBrains Mono", 9, "#f3f3f3", "#000000", bd_col, is_horiz=True)
            if row:
                children = row.winfo_children()
                if children:
                    cb_frame = children[0]
                    presets_ui = self._build_presets_ui(cb_frame, "#f3f3f3", bd_col, is_horiz=True)
                    presets_ui.pack(side="left", padx=(0, 10))
                row.pack(side="right", padx=8)
                
        tk.Frame(main_box, bg=bd_col, height=1).pack(fill="x") # sep
        
        # Content Grid
        content = tk.Frame(main_box, bg=bg_col)
        content.pack(fill="x", padx=8, pady=8)
        
        # 5 columns
        for i in range(5):
            content.columnconfigure(i, weight=1, uniform="col")
            
        field_names_order = ["Stored as", "Building", "Floor", "Cabinet", "Extra"]
        
        # We need 5 columns for horizontal
        for idx, name in enumerate(field_names_order):
            field = next((f for f in self.app.config["ui_sections"]["location"] if f["name"] == name), None)
            if not field: continue
            
            cell = tk.Frame(content, bg=bg_col)
            cell.grid(row=0, column=idx, sticky="nsew", padx=4)
            
            row = self._create_loc_widget(cell, name, field.get("type", "text"), field, "JetBrains Mono", 10, bg_col, "#000000", bd_col, is_horiz=True)
            if row:
                row.pack(fill="x")


    def build_sections(self):
        self._rebuild_focus_registration_menu()

        # Initialize problem vars first so they are available for inline problem checkboxes
        self.problem_vars.clear()
        self.problem_checkbuttons = []
        for field in self.app.config["ui_sections"]["problems"]:
            name = field["name"]
            var = tk.BooleanVar()
            self.problem_vars[name] = var
            var.trace_add("write", lambda *_, n=name: self.update_problems_default_view())

        if not hasattr(self, "images_missing_var"):
            self.images_missing_var = tk.StringVar()
        # -------- REG --------
        if hasattr(self, "reg_notebook") and self.reg_notebook.winfo_exists():
            for tab in self.reg_notebook.tabs():
                self.reg_notebook.forget(tab)
    
        self.reg_vars.clear()
        self.reg_entries.clear()
        self.reg_row_frames.clear()
        self.reg_entry_list = []

        self.no_problems_msg_label = ttk.Label(
            self.reg_data_frame,
            text="No active problems for this object. All fields hidden.",
            foreground="#2b8a3e",
            font=("Segoe UI", sc(10), "italic"),
            anchor="center"
        )

        # Build reverse map for inline problem checkboxes
        field_to_problem = {v: k for k, v in self.problem_to_field.items()}
        self.prob_border_bars.clear()
        self.prob_label_widgets.clear()

        # Build single Specimen Audit tab with cards
        all_fields = [f["name"] for f in self.app.config["ui_sections"]["registration"]]
        self._reg_tabs = {}
        
        # Define cards with themes, header icons and ordered fields
        card_defs = [
            {
                "id": "taxonomy",
                "title": "Taxonomy & Scientific Name",
                "icon": "🧬",
                "fields": ["Genus", "Species", "Author", "Family", "Higher Classification"]
            },
            {
                "id": "collection",
                "title": "Collection & Specimen Metadata",
                "icon": "📦",
                "fields": ["Collector", "Innsammling Nr.", "Collection Date", "Collection Place", "Variant", "(N) Plant Part", "Plant Part", "Box Label", "Conservation Status", "UID"]
            },
            {
                "id": "notes",
                "title": "Audit Notes & Descriptions",
                "icon": "📝",
                "fields": ["Observation", "Comment", "ProblemDescription"]
            }
        ]

        # Safeguard: Append any other registration fields in config not explicitly assigned to any card
        assigned_fields = set()
        for c in card_defs:
            assigned_fields.update(c["fields"])
        unassigned_fields = [f for f in all_fields if f not in assigned_fields]
        if unassigned_fields:
            card_defs[1]["fields"].extend(unassigned_fields)

        self.card_defs_ordered = [c["id"] for c in card_defs]
        self.card_frames = {}
        
        is_dark = getattr(self, "dark_mode_active", False)
        card_bg = "#1e1e2d" if is_dark else "#ffffff"
        header_bg = "#252538" if is_dark else "#f5f5f5"
        border_color = "#313244" if is_dark else "#e2e2e2"
        fg_color = "#cdd6f4" if is_dark else "#1a1c1c"
        
        # Create a single tab container for Specimen Audit
        tab_container = ttk.Frame(self.reg_notebook)
        
        # Scrollable canvas inside the tab container
        tab_canvas = tk.Canvas(tab_container, highlightthickness=0, bg="#1e1e2d" if is_dark else "#f9f9f9")
        tab_scroll = ttk.Scrollbar(tab_container, orient="vertical", command=tab_canvas.yview)
        tab_frame = ttk.Frame(tab_canvas, style="RightPane.TFrame")

        tab_frame.bind(
            "<Configure>",
            lambda e, tc=tab_canvas: tc.configure(scrollregion=tc.bbox("all"))
        )
        tab_win_id = tab_canvas.create_window((0, 0), window=tab_frame, anchor="nw")
        tab_canvas.configure(yscrollcommand=tab_scroll.set)
        tab_canvas.bind(
            "<Configure>",
            lambda e, tc=tab_canvas, twid=tab_win_id: tc.itemconfig(twid, width=e.width)
        )

        # Mousewheel scrolling specific to this tab
        def _make_mousewheel_scroller(canvas):
            return lambda e: canvas.yview_scroll(int(-1*(e.delta/120)), "units")

        mw_scroller = _make_mousewheel_scroller(tab_canvas)
        tab_container.bind("<Enter>", lambda e, mws=mw_scroller: tab_container.bind_all("<MouseWheel>", mws))
        tab_container.bind("<Leave>", lambda e: tab_container.unbind_all("<MouseWheel>"))

        tab_canvas.pack(side="left", fill="both", expand=True)
        tab_scroll.pack(side="right", fill="y")

        self._reg_tabs["Specimen Audit"] = {
            "container": tab_container,
            "canvas": tab_canvas,
            "frame": tab_frame,
            "fields": all_fields
        }

        self.reg_notebook.add(tab_container, text="Specimen Audit")

        # Generate card layout inside the tab frame
        for c in card_defs:
            card_id = c["id"]
            card_title = c["title"]
            icon = c["icon"]
            fields_to_render = c["fields"]
            
            # Card frame (outer container with 1px border)
            card_frame = tk.Frame(tab_frame, bg=card_bg, highlightthickness=1, highlightbackground=border_color, bd=0)
            card_frame.pack(fill="x", padx=10, pady=8)
            
            self.card_frames[card_id] = {
                "frame": card_frame,
                "fields": fields_to_render
            }
            
            # Header panel inside card
            header_frame = tk.Frame(card_frame, bg=header_bg, padx=8, pady=6)
            header_frame.pack(fill="x")
            
            icon_lbl = tk.Label(header_frame, text=icon, font=("Segoe UI", sc(11)), bg=header_bg, fg=fg_color)
            icon_lbl.pack(side="left", padx=(0, 6))
            
            title_lbl = tk.Label(header_frame, text=card_title, font=("Hanken Grotesk", sc(11), "bold"), bg=header_bg, fg=fg_color)
            title_lbl.pack(side="left")
            
            # Card content area
            body_frame = tk.Frame(card_frame, bg=card_bg, padx=12, pady=12)
            body_frame.pack(fill="x")
            
            body_frame.columnconfigure(0, weight=1)
            
            current_row = 0
            for fname in fields_to_render:
                field = next((f for f in self.app.config["ui_sections"]["registration"] if f["name"] == fname), None)
                if not field:
                    continue

                name = field["name"]
                ftype = field.get("type", "text")
                var = tk.StringVar()
                self.reg_vars[name] = var

                # Single individual field row
                frame = tk.Frame(body_frame, bg=card_bg)
                self.reg_row_frames[name] = frame

                # Col 0: border bar + optional problem checkbox
                col0_frame = tk.Frame(frame, bg=card_bg)
                col0_frame.grid(row=0, column=0, sticky="nsw", padx=(2, 2))

                prob_col = field_to_problem.get(name)
                if prob_col:
                    prob_var = self.problem_vars[prob_col]

                    border_bar = tk.Frame(col0_frame, width=3, bd=0, highlightthickness=0)
                    border_bar.pack(side="left", fill="y", padx=(0, 2))
                    self.prob_border_bars[name] = border_bar

                    cb = ttk.Checkbutton(
                        col0_frame, text="", variable=prob_var,
                        command=lambda n=name, pc=prob_col: (
                            self._update_problem_row_style(n, self.problem_vars[pc].get()),
                            self.commit_current_object()
                        )
                    )
                    cb.pack(side="left")
                    self.add_tooltip(cb, f"Flag as having a problem ({prob_col.replace('_', ' ')}). Tab + Space to toggle.")

                    prob_var.trace_add(
                        "write",
                        lambda *_, n=name, pc=prob_col: self.root.after_idle(
                            lambda: self._update_problem_row_style(n, self.problem_vars[pc].get())
                        )
                    )
                else:
                    tk.Frame(col0_frame, width=3, bd=0, highlightthickness=0, bg=card_bg).pack(side="left", fill="y", padx=(0, 2))
                    spacer_lbl = tk.Frame(col0_frame, width=16, bg=card_bg)
                    spacer_lbl.pack(side="left")

                # Col 1: Label with bold clean typography
                lbl = tk.Label(frame, text=name, width=22, anchor="w", font=("Hanken Grotesk", sc(10), "bold"), bg=card_bg, fg=fg_color)
                lbl.grid(row=0, column=1, sticky="w", padx=(0, 6))
                if prob_col:
                    self.prob_label_widgets[name] = lbl

                # Col 2: input widget based on type
                if ftype == "choice":
                    choices = field.get("choices", [])
                    if "" not in choices:
                        choices = [""] + choices
                    widget = ttk.Combobox(frame, textvariable=var, values=choices)
                elif ftype == "checkbox":
                    widget = ttk.Checkbutton(
                        frame,
                        text="",
                        variable=var,
                        onvalue="True",
                        offvalue="False",
                        command=lambda n=name, v=var: self._on_checkbox_change(n, v)
                    )
                elif ftype == "multiline" or name == "Conservation Status":
                    widget = tk.Text(
                        frame, height=3,
                        relief="flat", bd=0,
                        highlightthickness=1, highlightbackground=border_color,
                        highlightcolor="#000000" if not is_dark else "#cdd6f4",
                        insertbackground="#000000" if not is_dark else "#cdd6f4",
                        bg="#ffffff" if not is_dark else "#181825",
                        fg="#1a1c1c" if not is_dark else "#cdd6f4",
                        font=("Hanken Grotesk", sc(10))
                    )
                    def bind_text_events(w):
                        w.bind("<KeyRelease>", self._on_text_change)
                    bind_text_events(widget)
                else:
                    widget = tk.Entry(
                        frame, textvariable=var,
                        relief="flat", bd=0,
                        highlightthickness=1, highlightbackground=border_color,
                        highlightcolor="#000000" if not is_dark else "#cdd6f4",
                        insertbackground="#000000" if not is_dark else "#cdd6f4",
                        bg="#ffffff" if not is_dark else "#181825",
                        fg="#1a1c1c" if not is_dark else "#cdd6f4",
                        font=("Hanken Grotesk", sc(10))
                    )
                    widget.bind("<KeyRelease>", lambda e, n=name, w=widget: self._on_autocomplete_key(e, n, w), add="+")
                    widget.bind("<KeyRelease>", lambda e: self.root.after(500, self._validate_fields), add="+")
                    widget.bind("<FocusOut>", lambda e, n=name, w=widget: self._run_fuzzy_match(n, w), add="+")

                    if field.get("readonly"):
                        widget.configure(state="disabled")

                self.reg_entries[name] = widget
                self.reg_entry_list.append(widget)

                widget.grid(row=0, column=2, sticky="ew")

                # Bind general keys
                widget.bind("<Shift-Up>", self._reg_nav_up)
                widget.bind("<Shift-Down>", self._reg_nav_down)
                widget.bind("<Control-Up>", self._reg_nav_up)
                widget.bind("<Control-Down>", self._reg_nav_down)
                if ftype != "multiline":
                    widget.bind("<Return>", self._reg_nav_down)

                frame.columnconfigure(0, minsize=sc(28), weight=0)
                frame.columnconfigure(1, minsize=sc(180), weight=0)
                frame.columnconfigure(2, weight=1)

                frame.grid(row=current_row, column=0, sticky="ew", pady=4)
                current_row += 1

        # -------- PROBLEMS TAB --------
        tab_container = ttk.Frame(self.reg_notebook)
        tab_canvas = tk.Canvas(tab_container, highlightthickness=0)
        tab_scroll = ttk.Scrollbar(tab_container, orient="vertical", command=tab_canvas.yview)
        tab_frame = ttk.Frame(tab_canvas)
        
        tab_frame.bind(
            "<Configure>",
            lambda e, tc=tab_canvas: tc.configure(scrollregion=tc.bbox("all"))
        )
        tab_win_id = tab_canvas.create_window((0, 0), window=tab_frame, anchor="nw")
        tab_canvas.configure(yscrollcommand=tab_scroll.set)
        tab_canvas.bind(
            "<Configure>",
            lambda e, tc=tab_canvas, twid=tab_win_id: tc.itemconfig(twid, width=e.width)
        )
        
        tab_canvas.pack(side="left", fill="both", expand=True)
        tab_scroll.pack(side="right", fill="y")

        self.reg_notebook.add(tab_container, text="Problems")
        self._reg_tabs["Problems"] = {
            "container": tab_container,
            "canvas": tab_canvas,
            "frame": tab_frame,
            "fields": []
        }

        # Create a frame for the editable checkbuttons
        edit_frame = ttk.Frame(tab_frame, padding=12)
        edit_frame.pack(fill="x")
        
        # Populate editable checkbuttons for all problems
        self.problem_checkbuttons = []
        for i, field in enumerate(self.app.config["ui_sections"]["problems"]):
            name = field["name"]
            var = self.problem_vars.get(name)
            if not var:
                var = tk.BooleanVar()
                self.problem_vars[name] = var
                
            cb = ttk.Checkbutton(
                edit_frame,
                text=name.replace("_", " "),
                variable=var,
                command=lambda: self.update_reg_fields_visibility(skip_snap=True)
            )
            row = i // 2
            col = i % 2
            cb.grid(row=row, column=col, sticky="w", padx=10, pady=6)
            self.problem_checkbuttons.append(cb)
            
        edit_frame.columnconfigure(0, weight=1)
        edit_frame.columnconfigure(1, weight=1)
        
        # A separator before the summary list
        ttk.Separator(tab_frame, orient="horizontal").pack(fill="x", pady=10)
        
        # Self.problem_frame for the active problems list (rebuilt dynamically)
        self.problem_frame = ttk.Frame(tab_frame, padding=12)
        self.problem_frame.pack(fill="both", expand=True)
        self.problem_frame.tutorial_id = "problem_flags_frame"

        # -------- LOCATION --------
        for w in self.location_frame.winfo_children():
            w.destroy()
        if hasattr(self, 'loc_frame_horizontal'):
            for w in self.loc_frame_horizontal.winfo_children():
                w.destroy()

        self.location_vars.clear()
        self.location_entries = []

        for field in self.app.config["ui_sections"]["location"]:
            name = field["name"]
            var = tk.StringVar()
            self.location_vars[name] = var

        self._build_vertical_location_ui()
        if hasattr(self, 'loc_frame_horizontal'):
            self._build_horizontal_location_ui()

        # 2. Defaults container (Moved inside Location UI builders)

        # -------- PROBLEMS --------
        # Render the initial problems default view (only active problems)
        self.update_problems_default_view()



#-------

    def _safe_nav_left(self, event):
        if isinstance(self.root.focus_get(), (tk.Entry, ttk.Entry, tk.Text)):
            return
        self.navigate_object(-1)

    def _safe_nav_right(self, event):
        if isinstance(self.root.focus_get(), (tk.Entry, ttk.Entry, tk.Text)):
            return
        self.navigate_object(1)



#----




    def focus_first_empty_reg(self):
        for widget in self.reg_entry_list:
            try:
                val = widget.get("1.0", "end").strip() if isinstance(widget, tk.Text) else widget.get().strip()
                if not val:
                    widget.focus_set()
                    return
            except:
                continue
#----

    def open_history_shortcut(self, event=None):
        self.open_historical_suggestions()
 

#---

    def _history_nav_down(self, event):
        if not hasattr(self, "_history_widgets"):
            return

        total = len(self._history_widgets)
        if total == 0:
            return

        self._history_index = (self._history_index + 1) % total
    
        w = self._history_widgets[self._history_index]
        w.focus_set()
        w.invoke() 


        for rb in self._history_widgets:
            try:
                rb._row_frame.configure(style="TFrame")
            except Exception as e:
                debug_error("Suppressed Error", str(e))
                pass


        try:
            w._row_frame.configure(style="Hover.TFrame")
        except Exception as e:
            debug_error("Suppressed Error", str(e))
            pass

        return "break"


    def _history_nav_up(self, event):
        if not hasattr(self, "_history_widgets"):
            return

        total = len(self._history_widgets)
        if total == 0:
            return

        self._history_index = (self._history_index - 1) % total

        w = self._history_widgets[self._history_index]
        w.focus_set()
        w.invoke()


        for rb in self._history_widgets:
            try:
                rb._row_frame.configure(style="TFrame")
            except Exception as e:
                debug_error("Suppressed Error", str(e))
                pass


        try:
            w._row_frame.configure(style="Hover.TFrame")
        except Exception as e:
            debug_error("Suppressed Error", str(e))
            pass

        return "break"


    def _history_select(self, event):
        if not hasattr(self, "_history_widgets"):
            return "break"

        w = self._history_widgets[self._history_index]
    
        try:
            w.invoke()
        except Exception as e:
            debug_error("Suppressed Error", str(e))
            pass

        return "break"



#--------

    def _focus_first_reg(self, event=None):
        if self.reg_entries:
            for w in self.reg_entry_list:
                if w.winfo_ismapped():
                    w.focus_set()
                    break
        return "break"

    def _get_focused_reg_index(self):
        current = self.root.focus_get()

        for i, w in enumerate(self.reg_entry_list):
            if w == current:
                return i
        return None

    def _reg_nav_down(self, event):
        self._navigate_list(self.reg_entry_list, 1)
        return "break"

    def _reg_nav_up(self, event):
        self._navigate_list(self.reg_entry_list, -1)
        return "break"


#-------




#------ location shortcuts

    def _focus_first_location(self, event=None):
        if self.location_entries:
            self.location_entries[0].focus_set()
        return "break"

    def _focus_object_list(self, event=None):
        self.object_list.focus_set()
        if self.app.current_object_id in self.app.active_object_ids:
            try:
                idx = self.app.active_object_ids.index(self.app.current_object_id)
                self.object_list.selection_clear(0, tk.END)
                self.object_list.selection_set(idx)
                self.object_list.see(idx)
                self.object_list.activate(idx)
            except Exception:
                pass
        return "break"

    def _get_focused_location_index(self):
        current = self.root.focus_get()

        for i, w in enumerate(self.location_entries):
            if w == current:
                return i
        return None

    def _location_nav_down(self, event):
        self._navigate_list(self.location_entries, 1)
        return "break"

    def _location_nav_up(self, event):
        self._navigate_list(self.location_entries, -1)
        return "break"


#------- problem shortcuts


    def _focus_first_problem(self, event=None):
        for frame in self.reg_row_frames.values():
            for child in frame.winfo_children():
                if isinstance(child, ttk.Checkbutton):
                    child.focus_set()
                    return "break"
        return "break"


    def _get_focused_problem_index(self):
        current = self.root.focus_get()

        for i, cb in enumerate(self.problem_checkbuttons):
            if cb == current:
                return i
        return None

    def _problem_nav_down(self, event):
        self._navigate_list(self.problem_checkbuttons, 1)
        return "break"

    def _problem_nav_up(self, event):
        self._navigate_list(self.problem_checkbuttons, -1)
        return "break"

    def _toggle_specific_checkbox(self, cb):
        try:
            cb.invoke()
        except Exception as e:
            debug_error("Suppressed Error", str(e))
            pass

    def _switch_reg_tab(self, direction):
        if not hasattr(self, "reg_notebook") or not self.reg_notebook.winfo_exists():
            return
        tabs = self.reg_notebook.tabs()
        if not tabs:
            return
        current = self.reg_notebook.index("current")
        next_tab = (current + direction) % len(tabs)
        self.reg_notebook.select(next_tab)

    def _toggle_problem_checkbox(self, event):
        widget = self.root.focus_get()

        if widget in self.problem_checkbuttons:
            try:
                widget.invoke()
            except Exception as e:
                debug_error("Suppressed Error", str(e))
                pass
            return "break"


#------ navigation helper

    def _navigate_list(self, entries, step):
        current = self.root.focus_get()

        if current not in entries:
            return

        idx = entries.index(current)
        total = len(entries)
        new = (idx + step) % total

       
        for w in entries:
            try:
                w.configure(background="white")
            except Exception as e:
                debug_error("Suppressed Error", str(e))
                pass

        entries[new].focus_set()
    
        try:
            entries[new].configure(background="#d0ebff")
        except Exception as e:
            debug_error("Suppressed Error", str(e))
            pass




#---- gallery toggle





#------


    def push_undo_state(self):
        oid = self.app.current_object_id
        if not oid:
            return

        state = {
            "reg": self.app.df_reg.loc[oid].copy(),
            "obs": self.app.df_obs.loc[oid].copy(),
        }

        MAX_UNDO = 30
        stack = self.app.undo_stacks.setdefault(oid, [])

        stack.append(state)

        total = sum(len(v) for v in self.app.undo_stacks.values())

        if total > 500:
            for k in self.app.undo_stacks:
                self.app.undo_stacks[k] = self.app.undo_stacks[k][-10:]

        if len(stack) > MAX_UNDO:
            del stack[:10]


    def _clear_selection(self, var):
        var.set("")


    



    def load_historical_databases(self):
        last_dir = __import__("config").get_last_dir("last_db_dir")
        dialog_kwargs = dict(
            title="Select previous Excel databases",
            filetypes=[("Excel files", "*.xlsx")],
        )
        # Guard: only pass initialdir if it resolves to an existing directory
        if last_dir and os.path.isdir(last_dir):
            dialog_kwargs["initialdir"] = last_dir

        paths = filedialog.askopenfilenames(**dialog_kwargs)
        if not paths:
            return
        __import__("config").set_last_dir("last_db_dir", paths[0])

        self.app.historical_dbs = []

        for i, path in enumerate(paths, start=1):
            try:
                df_reg, df_obs, *_ = ExcelRepository.load_excel(path, self.app.config)
                self.app.historical_dbs.append({
                    "name": f"ARK{i}",
                    "path": path,
                    "df_reg": df_reg,
                    "reg_by_id": None,
                })

            except Exception as e:
                messagebox.showwarning(
                    "Load failed",
                    f"Could not load {path}\n{e}"
            )

        self.system_status.config(
            text=f"Loaded {len(self.app.historical_dbs)} earlier databases — pre-scanning..."
        )

        self.update_history_button_state()

        # Pre-build dict caches in a background thread so navigation is instant
        if self.app.historical_dbs:
            self._prescan_historical_dbs(self.app.historical_dbs)





    def _get_reg_by_id(self, db):

        if db.get("reg_by_id") is None:
            try:
                db["reg_by_id"] = db["df_reg"].set_index("ObjectID")
            except Exception:
                return None

        # PERFORMANCE OPTIMIZATION (Bolt):
        # Removed completely unused `value_cache` assignment which was doing
        # a very expensive `df.groupby("ObjectID").first()` operation on every DB load.
        # This significantly accelerates historical database / books file loading.

        return db["reg_by_id"]


       


#----- tool tips

    def add_tooltip(self, widget, text):
        def enter(e):
            widget.tooltip = tk.Toplevel(widget)
            widget.tooltip.wm_overrideredirect(True)
            widget.tooltip.wm_geometry(f"+{e.x_root+10}+{e.y_root+10}")
            tk.Label(widget.tooltip, text=text, background="yellow").pack()

        def leave(e):
            if hasattr(widget, "tooltip"):
                widget.tooltip.destroy()

        widget.bind("<Enter>", enter)
        widget.bind("<Leave>", leave)

#---- Menu


    def open_group_editor(self):
        if not getattr(self.app, 'config', None):
            from tkinter import messagebox
            messagebox.showinfo("No database", "Please open a database first.", parent=self.root)
            return
            
        all_fields = [f["name"] for f in self.app.config.get("ui_sections", {}).get("registration", [])]
        current_groups = self.app.config.get("reg_groups", [])
        
        def _on_save(new_groups):
            self.app.config["reg_groups"] = new_groups
            
            # Save to user_prefs.json
            import config, os
            prefs = config.load_prefs()
            if "custom_databases" not in prefs:
                prefs["custom_databases"] = {}
                
            profile_name = None
            for p_name, p_conf in prefs.get("custom_databases", {}).items():
                if p_conf == self.app.config:
                    profile_name = p_name
                    break
            
            if not profile_name:
                if self.app.excel_path:
                    profile_name = os.path.basename(self.app.excel_path).replace(".xlsx", "")
                else:
                    profile_name = "CustomProfile"
                    
            if profile_name in prefs.get("custom_databases", {}):
                prefs["custom_databases"][profile_name]["reg_groups"] = new_groups
            else:
                prefs["custom_databases"][profile_name] = self.app.config
                
            config.save_prefs(prefs)
            
            # Refresh UI
            self.build_sections()
            if self.app.current_object_id:
                self.load_object(self.app.current_object_id)
                
            self.show_banner("Field groups updated successfully.", "success")
            
        from ui.group_editor import FieldGroupEditorDialog
        FieldGroupEditorDialog(self.root, all_fields, current_groups, _on_save)

    def build_menu(self):
        menubar = tk.Menu(self.root)

        
        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(label="New Database", command=self.create_new_database)
        file_menu.add_command(label="Open Excel", command=self.open_excel)
        file_menu.add_command(label="Save", command=lambda: self.save_session("SAVE"))
        file_menu.add_command(label="Save As...", command=self.save_as)
        file_menu.add_command(label="Export filtered list...", command=self.export_filtered_list)
        file_menu.add_separator()
        file_menu.add_command(label="Restore earlier autosave...", command=self.open_autosave_manager)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.on_close)
        menubar.add_cascade(label="File", menu=file_menu)

        
        img_menu = tk.Menu(menubar, tearoff=0)
        img_menu.add_command(label="Image Source", command=self.open_image_menu)
        img_menu.add_command(label="Toggle image view", command=self.toggle_image_view)
        menubar.add_cascade(label="Images", menu=img_menu)

        
        data_menu = tk.Menu(menubar, tearoff=0)
        data_menu.add_command(label="Load Books", command=self.load_books_file)
        data_menu.add_command(label="Load earlier databases", command=self.load_historical_databases)
        data_menu.add_command(label="Edit Field Groups...", command=self.open_group_editor)
        data_menu.add_separator()
        data_menu.add_command(label="Configure Ignored Words...", command=self.open_ignored_words_editor)
        data_menu.add_separator()
        
        self.data_presets_menu = tk.Menu(data_menu, tearoff=0)
        data_menu.add_cascade(label="Data Presets", menu=self.data_presets_menu)
        
        self.load_data_preset_menu = tk.Menu(self.data_presets_menu, tearoff=0)
        self.data_presets_menu.add_command(label="Save Current Fields as Preset...", command=self.save_data_preset_dialog)
        self.data_presets_menu.add_cascade(label="Load Preset", menu=self.load_data_preset_menu)
        self._refresh_load_data_preset_menu()
        
        menubar.add_cascade(label="Data", menu=data_menu)


        
        tools_menu = tk.Menu(menubar, tearoff=0)
        tools_menu.add_command(label="Bulk Edit", command=self.open_bulk_edit_window)
        menubar.add_cascade(label="Tools", menu=tools_menu)
        # FILTER
        filter_menu = tk.Menu(menubar, tearoff=0)
        filter_menu.add_command(label="Open Filter Menu", command=self.open_filter_menu)
        menubar.add_cascade(label="Filter", menu=filter_menu)

        view_menu = tk.Menu(menubar, tearoff=0)
        view_menu.add_command(label="Statistics", command=self.show_statistics)
        view_menu.add_command(label="Session Dashboard", command=self.open_session_dashboard_window)
        view_menu.add_command(label="Dark Mode", command=self.toggle_dark_mode)



        menubar.add_cascade(label="View", menu=view_menu)

        # ADVANCED
        advanced_menu = tk.Menu(menubar, tearoff=0)
        advanced_menu.add_command(label="Create new Object", command=self.add_new_object)
        advanced_menu.add_command(label="Delete Object", command=self.delete_current_object)
        advanced_menu.add_separator()
        advanced_menu.add_command(
            label="Mark filtered as Reviewed",
            command=lambda: self._batch_set_reviewed(True)
        )
        advanced_menu.add_command(
            label="Unmark filtered as Reviewed",
            command=lambda: self._batch_set_reviewed(False)
        )
        menubar.add_cascade(label="Advanced", menu=advanced_menu)

        # FOCUS
        self._build_focus_menu(menubar)
        # LAYOUT
        self._build_layout_menu(menubar)
        # HELP
        menubar.add_command(label="Help", command=self.open_help_window)

        # SETTINGS
        settings_menu = tk.Menu(menubar, tearoff=0)
        settings_menu.add_command(
            label="Autosave interval...",
            command=self.open_autosave_settings
        )
        settings_menu.add_command(
            label="Configure Registration Tabs...",
            command=self.open_tab_config_editor
        )
        settings_menu.add_separator()
        settings_menu.add_command(
            label="UI Scale...",
            command=self.open_ui_scale_settings
        )
        menubar.add_cascade(label="Settings", menu=settings_menu)
        self.menubar = menubar
        self.root.config(menu=menubar)


#-------- Def shortcuts



    def _shortcut_new_object(self, event):
        widget = self.root.focus_get()
        if isinstance(widget, (tk.Entry, ttk.Entry, tk.Text)):
            return
        self.add_new_object()

    def _shortcut_delete_object(self, event):
        widget = self.root.focus_get()
        if isinstance(widget, (tk.Entry, ttk.Entry, tk.Text)):
            return
        self.delete_current_object()

    def add_new_object(self):
        if self.app.df_reg is None:
            return
        from ui.add_objects import AddObjectsWindow
        AddObjectsWindow(self.root, self.app, self)
        
    def show_create_dropdown(self):
        btn = self.toolbar_buttons["CREATE"]
        x = btn.winfo_rootx()
        y = btn.winfo_rooty() + btn.winfo_height()
        
        if hasattr(self, "create_dropdown") and self.create_dropdown and self.create_dropdown.winfo_exists():
            self.create_dropdown.destroy()
            self.create_dropdown = None
            return
            
        win = tk.Toplevel(self.root)
        self.create_dropdown = win
        win.overrideredirect(True)
        win.transient(self.root)
        
        is_dark = getattr(self, "dark_mode_active", False)
        bg_col = "#1e1e2d" if is_dark else "#ffffff"
        fg_col = "#cdd6f4" if is_dark else "#1a1c1c"
        border_col = "#313244" if is_dark else "#c4c7c7"
        hover_col = "#313244" if is_dark else "#e2e2e2"
        
        win.configure(bg=bg_col, highlightthickness=1, highlightbackground=border_col)
        
        options = [
            ("New Object", self.add_new_object),
            ("New Database", self.create_new_database)
        ]
        
        for label_text, cmd in options:
            lbl = tk.Label(
                win, 
                text=label_text, 
                font=("Hanken Grotesk" if not is_dark else "Segoe UI", sc(10)),
                bg=bg_col, 
                fg=fg_col,
                anchor="w",
                padx=16,
                pady=10,
                cursor="hand2"
            )
            lbl.pack(fill="x")
            
            def make_hover_handlers(w=lbl):
                w.bind("<Enter>", lambda e: w.configure(bg=hover_col))
                w.bind("<Leave>", lambda e: w.configure(bg=bg_col))
                
            make_hover_handlers(lbl)
            
            def make_click_handler(c=cmd):
                def on_click(e):
                    win.destroy()
                    self.create_dropdown = None
                    c()
                return on_click
                
            lbl.bind("<Button-1>", make_click_handler(cmd))
            
        win.update_idletasks()
        width = max(sc(130), win.winfo_reqwidth())
        win.geometry(f"{width}x{win.winfo_reqheight()}+{x}+{y}")
        
        def _dismiss_dropdown(event=None):
            if not win.winfo_exists():
                return
            # Check if click was inside the dropdown bounding box
            wx = win.winfo_rootx()
            wy = win.winfo_rooty()
            ww = win.winfo_width()
            wh = win.winfo_height()
            ex, ey = event.x_root, event.y_root
            if not (wx <= ex <= wx + ww and wy <= ey <= wy + wh):
                win.destroy()
                self.create_dropdown = None
                self.root.unbind("<Button-1>")

        win.bind("<Escape>", lambda e: (win.destroy(), setattr(self, "create_dropdown", None), self.root.unbind("<Button-1>")))
        # Delay binding so the click that opened the dropdown doesn't immediately close it
        self.root.after(100, lambda: self.root.bind("<Button-1>", _dismiss_dropdown))
        
    def delete_current_object(self):
        oid = self.app.current_object_id
        if not oid:
            return
            
        from tkinter import messagebox
        if not messagebox.askyesno("Confirm Delete", f"Are you sure you want to delete object {oid}?"):
            return
            
        if self.app.df_reg is not None and oid in self.app.df_reg.index:
            self.app.df_reg.drop(index=oid, inplace=True)
        if self.app.df_obs is not None and oid in self.app.df_obs.index:
            self.app.df_obs.drop(index=oid, inplace=True)
            
        self.app.dirty = True
        self.update_dirty_ui()
        self._invalidate_row_cache()
        self.refresh_list()

        
        if not self.app.df_reg.empty:
            self.load_object(self.app.df_reg.index[0])
        else:
            self.app.current_object_id = None
            
    def _shortcut_quick_new_object(self, event):
        if self.app.df_reg is None:
            return

        existing_ids = [int(x) for x in self.app.df_reg.index if str(x).isdigit()]
        oid = str(max(existing_ids) + 1 if existing_ids else 1)

        
        new_reg_row = {col: "" for col in self.app.df_reg.columns}
        new_reg_row["ObjectID"] = oid
        new_reg_row["UID"] = uuid.uuid4().hex[:8]
        self.app.df_reg.loc[oid] = new_reg_row

        
        new_obs_row = {col: False for col in self.problem_columns}
        new_obs_row.update({
            "Images_Missing": True
        })

        for col in self.location_columns:
            new_obs_row[col] = ""

        self.app.df_obs.loc[oid] = new_obs_row

        
        if not self.app.df_photo.empty:
            new_photo_row = {col: "" for col in self.app.df_photo.columns}
            self.app.df_photo.loc[oid] = new_photo_row

        self.app.active_object_ids.append(oid)
        self._invalidate_row_cache()
        self.invalidate_search_index()
        self.refresh_list()
    
        idx = len(self.app.active_object_ids) - 1
        self.object_list.selection_clear(0, tk.END)
        self.object_list.selection_set(idx)
        self.object_list.see(idx)

        self.load_object(oid)
    
        self.app.dirty = True
        self.update_dirty_ui()

        self.log_action("CREATE_OBJECT_FAST", ["ObjectID"], [f"Created {oid}"])



    def _shortcut_duplicate_object(self, event):
        oid = self.app.current_object_id
        if not oid:
            return

        existing_ids = [int(x) for x in self.app.df_reg.index if str(x).isdigit()]
        new_oid = str(max(existing_ids) + 1 if existing_ids else 1)
    
  
        new_reg = self.app.df_reg.loc[oid].copy()
        new_reg["ObjectID"] = new_oid
        new_reg["UID"] = uuid.uuid4().hex[:8]   

        self.app.df_reg.loc[new_oid] = new_reg

 
        new_obs = self.app.df_obs.loc[oid].copy()
        new_obs["ProblemDescription"] = ""
        self.app.df_obs.loc[new_oid] = new_obs

   
        if not self.app.df_photo.empty and oid in self.app.df_photo.index:
            new_photo = self.app.df_photo.loc[oid].copy()
            self.app.df_photo.loc[new_oid] = new_photo

        self.app.active_object_ids.append(new_oid)
        self._invalidate_row_cache()
        self.invalidate_search_index()
        self.refresh_list()
    
        idx = len(self.app.active_object_ids) - 1
        self.object_list.selection_clear(0, tk.END)
        self.object_list.selection_set(idx)
        self.object_list.see(idx)

        self.load_object(new_oid)
    
        self.app.dirty = True
        self.update_dirty_ui()

        self.log_action(
            "DUPLICATE_OBJECT",
            ["ObjectID"],
            [f"Duplicated {oid} {new_oid}"]
        )



#---


    def enable_offline_mode(self):
        self.image_mode = "offline"
        self.update_image_view_button()
        self.image_cache.clear()
        self.system_status.config(text="Offline image mode enabled")

        if self.app.current_object_id:
            self.load_images(self.app.current_object_id)

#-------

    def _on_text_change(self, event):
        self._store_field_state(event)

    def open_bulk_edit_window(self):
        sel = self.object_list.curselection()
        pre_selected = [self.app.active_object_ids[i] for i in sel] if sel else []
        from ui.bulk_edit import BulkEditWindow
        BulkEditWindow(self.root, self.app, self, pre_selected)

    def _on_checkbox_change(self, name, var):
        if name == "Loaned out":
            from datetime import datetime
            if var.get() == "True":
                self.reg_vars["Loaned out date"].set(datetime.now().strftime("%d.%m.%Y %H:%M:%S"))
            else:
                self.reg_vars["Loaned out date"].set("")
        self.commit_current_object()


# --- HovedGuide


    def show_main_help(self):
        message = (
            "ARBOR SYSTEM USER GUIDE\n\n"
            "1. WORKSPACE PANELS\n"
            " - Left Panel: Displays the list of objects. Use the search bar to find objects by ID, genus, or species.\n"
            " - Middle Panel: Displays the high-resolution images. Supports zoom/pan (mouse drag & scroll) and rotation.\n"
            " - Right Panel: The registration editor. Re-write or choose fields, flag/clear problem statuses, and save your changes.\n\n"
            "2. PROBLEM WORKFLOW\n"
            " - Fields with errors are flagged in red. Unmapped problems appear below the main fields.\n"
            " - Review historical databases by clicking the 'History' indicator when discrepancies occur.\n"
            " - Once problems are resolved, click 'Mark as Reviewed' at the bottom of the right panel.\n\n"
            "3. FOCUS & LAYOUT SETTINGS\n"
            " - Toggle panels or customize sashes from the View and Layout menus.\n"
            " - Focus mode hides sections or fields that you do not need, making it ideal for small laptop screens."
        )

  
        win = tk.Toplevel(self.root)
        win.title("User Guide")
        import utils
        utils.center_and_fit_toplevel(win, 620, 700)
        win.bind("<Escape>", lambda e: win.destroy())

        canvas = tk.Canvas(win)
        sb = ttk.Scrollbar(win, orient="vertical", command=canvas.yview)
        frame = ttk.Frame(canvas, padding=16)
        frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        canvas.create_window((0, 0), window=frame, anchor="nw")
        canvas.configure(yscrollcommand=sb.set)
        canvas.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")

        txt = tk.Text(
            frame,
            wrap="word",
            width=72,
            height=40,
            font=("Consolas", sc(9)),
            relief="flat",
            bg=win.cget("bg"),
            state="normal"
        )
        txt.pack(fill="both", expand=True)
        txt.insert("1.0", message)
        txt.config(state="disabled")

      
        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        canvas.bind_all("<MouseWheel>", _on_mousewheel)
        win.protocol("WM_DELETE_WINDOW", lambda: (
            canvas.unbind_all("<MouseWheel>"), win.destroy()
        ))

        ttk.Button(win, text="Close", command=lambda: (
            canvas.unbind_all("<MouseWheel>"), win.destroy()
        )).pack(side="bottom", pady=8)


    def show_quick_help(self):
        message = (
            "ARBOR KEYBOARD SHORTCUTS CHEAT SHEET\n\n"
            "Ctrl + S : Save session\n"
            "Ctrl + Q : Toggle Focus Mode\n"
            "Ctrl + G : Open Filter Menu\n"
            "Ctrl + H : Open Historical suggestions\n"
            "Ctrl + N : Create new blank Object\n"
            "Ctrl + Shift + N : Quick create new Object\n"
            "Ctrl + D : Duplicate current object\n"
            "Ctrl + Shift + P / F3 : Open editable Problem Flags window\n"
            "Ctrl + Shift + L / F4 : Open editable Location window\n"
            "Right Arrow / Left Arrow : Navigate Next / Prev object\n"
            "Down Arrow / Up Arrow : Navigate list rows"
        )

        messagebox.showinfo("Quick Start", message)


    def show_about(self):
        messagebox.showinfo(
            "About arbor",
            "Arbor Botanical Database Management System\nVersion 1.2"
        )


    # def open_settings_window(self):



    def open_help_window(self):
        if hasattr(self, "help_win") and self.help_win and self.help_win.winfo_exists():
            self.help_win.focus_force()
            self.help_win.focus_set()
            self.help_win.lift()
            return
            
        win = tk.Toplevel(self.root)
        self.help_win = win
        win.title("Help Center")
        win.resizable(False, False)
        win.transient(self.root)
        
        import utils
        # Size of the dialog
        w_width = sc(400)
        w_height = sc(320)
        utils.center_and_fit_toplevel(win, w_width, w_height)
        
        bg_color = "#1e1e2e" if self.dark_mode_active else "#f3f3f3"
        win.configure(background=bg_color)
        win.bind("<Escape>", lambda e: win.destroy())
        
        # Main padding frame
        frame = ttk.Frame(win, padding=sc(16))
        frame.pack(fill="both", expand=True)
        
        # Header Title
        lbl_header = ttk.Label(
            frame,
            text="HELP CENTER",
            font=("Segoe UI", sc(12), "bold"),
            foreground="#1a1c1c" if not self.dark_mode_active else "#cdd6f4"
        )
        lbl_header.pack(anchor="w", pady=(0, 10))
        
        ttk.Separator(frame, orient="horizontal").pack(fill="x", pady=(0, 15))
        
        # Options definition
        def run_help_cmd(cmd):
            win.destroy()
            cmd()
            
        def start_main_tutorial():
            from ui.tutorial import TutorialManager
            TutorialManager().start_tutorial("main_tutorial", self.root)
            
        options = [
            ("Interactive Tutorial", "Guided walkthrough of the main workspace.", start_main_tutorial),
            ("User Guide", "Complete guide and detailed documentation.", self.show_main_help),
            ("Keyboard Shortcuts", "HUD cheat sheet for all keys and navigation.", self.show_shortcuts),
            ("Quick Start", "Basic shortcuts and workflow summary.", self.show_quick_help),
            ("About", "Application version and build details.", self.show_about)
        ]
        
        # Render options list
        for name, desc, cmd in options:
            btn_frame = ttk.Frame(frame)
            btn_frame.pack(fill="x", pady=sc(6))
            
            btn = ttk.Button(
                btn_frame,
                text=name,
                width=18,
                command=lambda c=cmd: run_help_cmd(c),
                style="Primary.TButton"
            )
            btn.pack(side="left", padx=(0, 10))
            
            lbl_desc = ttk.Label(
                btn_frame,
                text=desc,
                font=("Segoe UI", sc(8.5)),
                foreground="gray"
            )
            lbl_desc.pack(side="left", fill="x", expand=True)
            
        # Footer
        close_btn = ttk.Button(
            frame,
            text="Close",
            command=win.destroy,
            style="Tool.TButton",
            width=10
        )
        close_btn.pack(side="bottom", pady=(15, 0))


#--------


    def _store_field_state(self, event):
        widget = event.widget

        try:
            if isinstance(widget, tk.Text):
                value = widget.get("1.0", tk.END)
            else:
                value = widget.get()
        except:
            return

        now = time.time()

        if self.field_undo_stack:
            last = self.field_undo_stack[-1]

            if (
                last["widget"] == widget and
                now - last.get("time", 0) < 0.7
            ):
                last["value"] = value
                last["time"] = now
                return

        self.field_undo_stack.append({
            "widget": widget,
            "value": value,
            "time": now
        })

        if len(self.field_undo_stack) > 100:
            self.field_undo_stack.pop(0)

#-- def toggle reviewed shortcut

    def toggle_reviewed_shortcut(self, event=None):
        oid = self.app.current_object_id
        if not oid:
            return

        current = bool(self.reviewed_var.get())
        new = not current

      
        self.push_undo_state()

        self.reviewed_var.set(new)

        self.commit_current_object()

        state = "SET" if new else "UNSET"

        self.system_status.config(
            text=f"Reviewed = {new}",
            foreground="green" if new else "gray"
        )

        self._list_dirty = True
        self.update_reviewed_button_state()

#---

    def toggle_focus_mode_shortcut(self, event=None):
        oid = self.app.current_object_id
        if not oid:
            return

        current = bool(self.focus_mode_var.get())
        new = not current


        self.push_undo_state()


        self.focus_mode_var.set(new)


        self.update_reg_fields_visibility()


        state = "SET" if new else "UNSET"
        self.log_action("FOCUS_MODE_TOGGLE", ["Focus Mode"], [state])


        self.system_status.config(
            text=f"Focus Mode = {new}",
            foreground="green" if new else "gray"
        )

        self._list_dirty = True

        import config
        prefs = config.load_prefs() or {}
        prefs["focus_mode_active"] = new
        config.save_prefs(prefs)

    def toggle_focus_mode_from_ui(self):
        active = bool(self.focus_mode_var.get())
        self.update_reg_fields_visibility()
        import config
        prefs = config.load_prefs() or {}
        prefs["focus_mode_active"] = active
        config.save_prefs(prefs)



#--- def undo

    def undo(self, event=None):
        oid = self.app.current_object_id
        if not oid:
            return

        stack = self.app.undo_stacks.get(oid)
        if not stack:
            return


        current = {
            "reg": self.app.df_reg.loc[oid].copy(),
            "obs": self.app.df_obs.loc[oid].copy(),
        }
        MAX_REDO = 30
        rstack = self.app.redo_stacks.setdefault(oid, [])

        rstack.append(current)

        if len(rstack) > MAX_REDO:
            del rstack[:10]

        state = stack.pop()

        self.app.df_reg.loc[oid] = state["reg"]
        self.app.df_obs.loc[oid] = state["obs"]
    
        self._invalidate_row_cache()
        self.invalidate_search_index()
        self.refresh_list()

        self.load_object(oid)

        self.app.dirty = True
        self.update_dirty_ui()



#---- def smart undo

    def _smart_undo(self, event):
        widget = self.root.focus_get()

        if isinstance(widget, (tk.Entry, ttk.Entry, tk.Text)):
            return self.undo_field(event)

        return self.undo(event)


#---- 

    def undo_field(self, event):
        if not self.field_undo_stack:
            return

        last = self.field_undo_stack.pop()

        widget = last["widget"]
        value = last["value"]

        try:
            if isinstance(widget, tk.Text):
                widget.delete("1.0", tk.END)
                widget.insert("1.0", value)
            else:
                widget.delete(0, tk.END)
                widget.insert(0, value)
        except Exception as e:
            debug_error("Suppressed Error", str(e))
            pass

     
        self.app.dirty = True
        self.update_dirty_ui()



#---- def redo

    def redo(self, event=None):
        oid = self.app.current_object_id
        if not oid:
            return

        stack = self.app.redo_stacks.get(oid, [])
        if len(stack) == 0:
            return



        current = {
            "reg": self.app.df_reg.loc[oid].copy(),
            "obs": self.app.df_obs.loc[oid].copy(),
        }
        MAX_UNDO = 30
        ustack = self.app.undo_stacks.setdefault(oid, [])

        ustack.append(current)

        if len(ustack) > MAX_UNDO:
            del ustack[:10]

        state = stack.pop()

        self.app.df_reg.loc[oid] = state["reg"]
        self.app.df_obs.loc[oid] = state["obs"]

        self._invalidate_row_cache()
        self.invalidate_search_index()
        self.refresh_list()

        self.load_object(oid)

        self.app.dirty = True
        self.update_dirty_ui()

#------
    def _position_search_popup(self):
        entry = self.root.focus_get()
        if not isinstance(entry, ttk.Entry):
            return

        x = entry.winfo_rootx()
        y = entry.winfo_rooty() + entry.winfo_height()
        w = entry.winfo_width()

        self.search_popup.geometry(f"{w}x200+{x}+{y}")

    def _on_search_select(self, event=None):
        if not self.search_listbox.curselection():
            return

        text = self.search_listbox.get(self.search_listbox.curselection()[0])
        oid = text.split("--temp--")[0].strip()

        self.object_id_var.set(oid)
        self.search_popup.withdraw()
        self.root.focus_set()

        self.load_object(oid)
    def _search_move_down(self, event):
        if self.search_popup.state() == "normal" and self.search_listbox.size() > 0:
            self.search_listbox.focus_set()
            self.search_listbox.selection_clear(0, tk.END)
            self.search_listbox.selection_set(0)
            return "break"
    def _on_search_enter(self, event):
        if self.search_popup.state() == "normal":
            self._on_search_select()
            return "break"
        else:
            self.load_object_from_entry()


# ------ sÃ¸ke_index 1

    def build_search_index(self):
        # PERFORMANCE OPTIMIZATION (Bolt): This method was previously building an expensive search index list
        # that was entirely unused in the codebase (the live search actually uses `_get_search_index()`).
        # Making this a fast no-op eliminates unnecessary CPU/memory overhead on database loads.
        self.search_index = []
        return

#---- progress bar

    def _show_progress(self, text="Working", maximum=100):
        if hasattr(self, "_loading_window") and self._loading_window and self._loading_window.win.winfo_exists():
            self._loading_window.update_progress_bar(0, maximum)
            self._loading_window.update_status_text(text)
            return

        self.system_status.config(text=text)
        self.image_scan_progress.configure(
            value=0,
            maximum=maximum,
            mode="determinate"
        )
        self.image_scan_progress.pack(anchor="e", pady=(2, 0))

    def _hide_progress(self, text=""):
        if hasattr(self, "_loading_window") and self._loading_window and self._loading_window.win.winfo_exists():
            self._loading_window.finish(text)
            return

        self.image_scan_progress.pack_forget()
        self.system_status.config(text=text)
        self.root.after(1500, lambda: self.system_status.config(text=""))



#---- dirty state

    def update_dirty_ui(self):
        config_name = getattr(self.app, "config_name", None)
        title = f"arbor {config_name}" if config_name else "arbor"
        if self.app.dirty:
            self.set_status_badge("unsaved", "Unsaved changes")
        else:
            ts = datetime.now().strftime("%H:%M:%S")
            self.set_status_badge("saved", f" Saved ({ts})")
        self.root.title(title)


#--- autosave


    def open_ui_scale_settings(self):
        """Let the user choose a UI scale factor. Saved to user_prefs.json; requires restart."""
        import config as _cfg
        import json

        prefs_path = _cfg._PREFS_PATH


        # Load current prefs
        try:
            with open(prefs_path, "r", encoding="utf-8") as f:
                prefs = json.load(f)
        except Exception:
            prefs = {}

        current_scale = prefs.get("ui_scale", _cfg.UI_SCALE)
        detected = getattr(_cfg, "_detected_scale", 1.0)

        win = tk.Toplevel(self.root)
        win.title("UI Scale")
        # No hardcoded geometry  let Tkinter size to fit contents on any screen
        win.resizable(True, True)
        win.grab_set()

        frame = ttk.Frame(win, padding=20)
        frame.pack(fill="both", expand=True)

        ttk.Label(
            frame,
            text="UI Scale  (font & widget size)",
            font=("Segoe UI", sc(11), "bold")
        ).pack(anchor="w", pady=(0, 4))

        ttk.Label(
            frame,
            text=(
                f"Screen DPI ratio detected: {detected:.0%}\n"
                f"Currently active: {current_scale:.0%}\n"
                f"Changes take effect after restarting the application."
            ),
            foreground="gray",
            justify="left"
        ).pack(anchor="w", pady=(0, 12))

        ttk.Separator(frame, orient="horizontal").pack(fill="x", pady=(0, 10))

        options = [0.75, 0.90, 1.0, 1.10, 1.25]
        labels  = [
            "75%    very compact",
            "90%    compact",
            "100%   default (recommended)",
            "110%   slightly larger",
            "125%   large",
        ]

        scale_var = tk.DoubleVar(value=current_scale)

        for val, lbl in zip(options, labels):
            ttk.Radiobutton(
                frame,
                text=lbl,
                variable=scale_var,
                value=val
            ).pack(anchor="w", pady=2)

        ttk.Separator(frame, orient="horizontal").pack(fill="x", pady=(12, 0))

        btn_frame = ttk.Frame(frame)
        btn_frame.pack(fill="x", pady=(8, 0))

        def _apply():
            chosen = scale_var.get()
            prefs["ui_scale"] = chosen
            prefs["user_set"] = True   # mark as explicit user choice
            try:
                with open(prefs_path, "w", encoding="utf-8") as f:
                    json.dump(prefs, f, indent=2)
            except Exception as e:
                messagebox.showerror("Error", f"Could not save preferences:\n{e}")
                return
            win.destroy()
            messagebox.showinfo(
                "Restart required",
                f"UI Scale set to {chosen:.0%}.\n\nPlease restart the application for the change to take effect."
            )

        ttk.Button(btn_frame, text="Apply", command=_apply, width=10).pack(side="right", padx=(6, 0))
        ttk.Button(btn_frame, text="Cancel", command=win.destroy, width=10).pack(side="left")

        # Let Tk calculate the required size, then lock it
        win.update_idletasks()
        win.minsize(win.winfo_reqwidth() + 20, win.winfo_reqheight() + 10)





    def open_tab_config_editor(self):
        from ui.group_editor import GroupEditorWindow
        GroupEditorWindow(self.root, self.app, self)

















#---------Image Scan



    def _extract_numeric_object_id(self, filename):
        name = os.path.splitext(filename)[0]

        # Finn første rene tallsekvens
        m = _NUMERIC_OID_PATTERN.search(name)
        if not m:
            return None

        try:
            return int(m.group(1))
        except ValueError:
            return None


# ---------- Historical data ----------



#-----

















#------


#--------- Books -------------







    # ---------- Helpers ----------
    def object_title(self, oid):
        if oid not in self.reg_by_id.index:
            return f"{oid} Unknown"

        row = self.reg_by_id.loc[oid]
        if isinstance(row, pd.DataFrame):
            row = row.iloc[0]

        genus = str(row.get("Genus", "")).strip()
        species = str(row.get("Species", "")).strip()

        if not genus and not species:
            return f"{oid} Unknown"

        return f"{oid} {genus} {species}".strip()





    # ---------- FOCUS MANAGEMENT ----------
    def _build_focus_menu(self, menubar):
        menubar.add_command(label="Focus", command=self.open_focus_settings)

    def open_focus_settings(self):
        if hasattr(self, "focus_win") and self.focus_win.winfo_exists():
            self.focus_win.lift()
            return
            
        win = tk.Toplevel(self.root)
        win.title("Focus Settings")
        win.transient(self.root)
        win.geometry(f"{sc(420)}x{sc(600)}")
        self.focus_win = win
        
        bg_color = "#1e1e2e" if self.dark_mode_active else "#f3f3f3"
        win.configure(background=bg_color)
        
        main_frame = ttk.Frame(win, padding=sc(12))
        main_frame.pack(fill="both", expand=True)
        
        # --- Initialize draft variables ---
        if getattr(self.app, "config", None) and "ui_sections" in self.app.config:
            import config
            prefs = config.load_prefs() or {}
            saved_vis = prefs.get("focus_visibility", {})
            for field in self.app.config["ui_sections"].get("registration", []):
                name = field["name"]
                if name not in self.focus_visibility_vars:
                    self.focus_visibility_vars[name] = tk.BooleanVar(value=saved_vis.get(name, True))

        self.draft_focus_mode_var = tk.BooleanVar(value=self.focus_mode_var.get())
        self.draft_focus_fallback_var = tk.BooleanVar(value=self.focus_fallback_var.get())
        self.draft_focus_visibility_vars = {}
        for k, v in self.focus_visibility_vars.items():
            self.draft_focus_visibility_vars[k] = tk.BooleanVar(value=v.get())

        # --- Presets Section ---
        preset_lf = ttk.LabelFrame(main_frame, text="Focus Presets", padding=sc(8))
        preset_lf.pack(fill="x", pady=(0, 10))
        
        preset_row1 = ttk.Frame(preset_lf)
        preset_row1.pack(fill="x", pady=2)
        ttk.Label(preset_row1, text="Load Preset:").pack(side="left", padx=2)
        
        self.focus_dialog_preset_cb = ttk.Combobox(preset_row1, state="readonly", width=18)
        self.focus_dialog_preset_cb.pack(side="left", fill="x", expand=True, padx=4)
        
        def on_load_preset(event=None):
            val = self.focus_dialog_preset_cb.get()
            if val:
                import config
                prefs = config.load_prefs() or {}
                preset = prefs.get("focus_presets", {}).get(val)
                if preset:
                    self.draft_focus_fallback_var.set(preset.get("fallback", True))
                    self.draft_focus_mode_var.set(True)
                    vis_state = preset.get("visibility", {})
                    for k, v in self.draft_focus_visibility_vars.items():
                        if k in vis_state:
                            v.set(vis_state[k])
                    if self.focus_dynamic_update_var.get():
                        on_apply()
                
        self.focus_dialog_preset_cb.bind("<<ComboboxSelected>>", on_load_preset)
        
        def refresh_preset_cb():
            import config
            prefs = config.load_prefs() or {}
            presets = prefs.get("focus_presets", {})
            names = sorted(presets.keys())
            self.focus_dialog_preset_cb['values'] = names
            if names:
                self.focus_dialog_preset_cb.set("")
                
        preset_row2 = ttk.Frame(preset_lf)
        preset_row2.pack(fill="x", pady=2)
        
        preset_name_var = tk.StringVar()
        preset_entry = ttk.Entry(preset_row2, textvariable=preset_name_var, width=15)
        preset_entry.pack(side="left", fill="x", expand=True, padx=2)
        
        def on_save_preset():
            name = preset_name_var.get().strip()
            if not name:
                return
            import config
            prefs = config.load_prefs() or {}
            if "focus_presets" not in prefs:
                prefs["focus_presets"] = {}
                
            vis_state = {k: v.get() for k, v in self.draft_focus_visibility_vars.items()}
            prefs["focus_presets"][name] = {
                "fallback": self.draft_focus_fallback_var.get(),
                "visibility": vis_state
            }
            config.save_prefs(prefs)
            refresh_preset_cb()
            preset_name_var.set("")
            self.system_status.config(text=f"Focus preset '{name}' saved (draft state).")
            
        ttk.Button(preset_row2, text="Save", command=on_save_preset, width=6, style="Primary.TButton").pack(side="left", padx=2)
        
        def on_delete_preset():
            val = self.focus_dialog_preset_cb.get()
            if not val:
                return
            import config
            prefs = config.load_prefs() or {}
            if "focus_presets" in prefs and val in prefs["focus_presets"]:
                del prefs["focus_presets"][val]
                config.save_prefs(prefs)
                refresh_preset_cb()
                self.system_status.config(text=f"Focus preset '{val}' deleted.")
                
        ttk.Button(preset_row2, text="Delete", command=on_delete_preset, width=6, style="Tool.TButton").pack(side="left", padx=2)
        refresh_preset_cb()
        
        # --- Update dynamically checkbox ---
        dyn_frame = ttk.Frame(main_frame)
        dyn_frame.pack(fill="x", pady=(0, 6))
        
        def toggle_dynamic_update():
            if self.focus_dynamic_update_var.get():
                apply_btn.config(state="disabled")
                on_apply()
            else:
                apply_btn.config(state="normal")
                
        dyn_cb = ttk.Checkbutton(
            dyn_frame, 
            text="Update dynamically", 
            variable=self.focus_dynamic_update_var,
            command=toggle_dynamic_update
        )
        dyn_cb.pack(side="left")

        # --- Options & Visibility Section (Scrollable Frame) ---
        scroll_container = ttk.Frame(main_frame)
        scroll_container.pack(fill="both", expand=True)

        canvas = tk.Canvas(scroll_container, highlightthickness=0, bd=0, bg=bg_color)
        scrollbar = ttk.Scrollbar(scroll_container, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        win_id = canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.bind("<Configure>", lambda e: canvas.itemconfig(win_id, width=e.width))
        
        # Mousewheel
        def _on_mousewheel(e):
            canvas.yview_scroll(int(-1*(e.delta/120)), "units")
        win.bind_all("<MouseWheel>", _on_mousewheel)
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        def on_switch_toggle():
            if self.focus_dynamic_update_var.get():
                on_apply()

        def create_toggle_row(parent, label_text, var):
            row = ttk.Frame(parent)
            row.pack(fill="x", pady=sc(4))
            lbl = ttk.Label(row, text=label_text)
            lbl.pack(side="left", anchor="w")
            sw = ToggleSwitch(row, var, command=on_switch_toggle, ui_ref=self)
            sw.pack(side="right")
            return row
            
        opts_lf = ttk.LabelFrame(scrollable_frame, text="General Options", padding=sc(8))
        opts_lf.pack(fill="x", pady=(0, 10))
        create_toggle_row(opts_lf, "Dynamic Problem Fallback", self.draft_focus_fallback_var)
        
        sec_lf = ttk.LabelFrame(scrollable_frame, text="Sections Visibility", padding=sc(8))
        sec_lf.pack(fill="x", pady=(0, 10))
        if "Problems" in self.draft_focus_visibility_vars:
            create_toggle_row(sec_lf, "Problems Section", self.draft_focus_visibility_vars["Problems"])
        if "Location" in self.draft_focus_visibility_vars:
            create_toggle_row(sec_lf, "Location Section", self.draft_focus_visibility_vars["Location"])
            
        reg_lf = ttk.LabelFrame(scrollable_frame, text="Registration Fields", padding=sc(8))
        reg_lf.pack(fill="x", pady=(0, 10))
        
        if getattr(self.app, "config", None) and "ui_sections" in self.app.config:
            for field in self.app.config["ui_sections"].get("registration", []):
                name = field["name"]
                create_toggle_row(reg_lf, name, self.draft_focus_visibility_vars[name])

        # --- Bottom Buttons (Apply, OK, Cancel) ---
        btn_row = ttk.Frame(main_frame, padding=(0, 6, 0, 0))
        btn_row.pack(fill="x", side="bottom")

        def on_apply():
            # Copy draft states to actual vars
            self.focus_mode_var.set(True)
            self.draft_focus_mode_var.set(True)
            self.focus_fallback_var.set(self.draft_focus_fallback_var.get())
            for k, v in self.draft_focus_visibility_vars.items():
                if k in self.focus_visibility_vars:
                    self.focus_visibility_vars[k].set(v.get())
            
            # Apply to main UI
            self.update_reg_fields_visibility()

            # Save preferences
            import config
            prefs = config.load_prefs() or {}
            prefs["focus_mode_active"] = True
            prefs["focus_fallback"] = self.focus_fallback_var.get()
            prefs["focus_visibility"] = {k: v.get() for k, v in self.focus_visibility_vars.items()}
            config.save_prefs(prefs)
            self.system_status.config(text="Focus settings applied and Focus Mode enabled.")

        def on_ok():
            on_apply()
            win.destroy()

        ttk.Button(btn_row, text="Cancel", command=win.destroy, width=10, style="Tool.TButton").pack(side="right", padx=4)
        ttk.Button(btn_row, text="OK", command=on_ok, width=10, style="Primary.TButton").pack(side="right", padx=4)
        
        apply_btn = ttk.Button(btn_row, text="Apply", command=on_apply, width=10, style="Primary.TButton")
        apply_btn.pack(side="right", padx=4)
        if self.focus_dynamic_update_var.get():
            apply_btn.config(state="disabled")
        else:
            apply_btn.config(state="normal")
            
        # Tutorial bindings
        preset_lf.tutorial_id = "focus_presets"
        opts_lf.tutorial_id = "focus_options"
        reg_lf.tutorial_id = "focus_fields"
        
        import config
        prefs = config.load_prefs()
        if "focus_settings" not in prefs.get("completed_tutorials", []):
            from ui.tutorial import TutorialManager
            win.after(500, lambda: TutorialManager().start_tutorial("focus_settings", win))

    def apply_saved_focus_preset(self, name):
        import config
        prefs = config.load_prefs() or {}
        preset = prefs.get("focus_presets", {}).get(name)
        if not preset:
            return
            
        self.focus_mode_var.set(True)
        self.focus_fallback_var.set(preset.get("fallback", True))
        vis_state = preset.get("visibility", {})
        for k, v in self.focus_visibility_vars.items():
            if k in vis_state:
                v.set(vis_state[k])
                
        self.update_reg_fields_visibility()
        self.system_status.config(text=f"Applied Focus Preset '{name}' and enabled Focus Mode.")
        
        prefs["focus_mode_active"] = True
        config.save_prefs(prefs)

    # ---------- LAYOUT MANAGEMENT ----------


    def toggle_reg_panel(self):
        if self.show_reg_var.get():
            self.panes.add(self.reg_outer, weight=3)
        else:
            self.panes.forget(self.reg_outer)


    def _apply_default_data_preset_shortcut(self, event=None):
        if not hasattr(self, "active_preset_var"):
            return "break"
        default = self.active_preset_var.get().strip()
        if default:
            self.apply_saved_data_preset(default)
        return "break"

    def save_data_preset_dialog(self):
        from tkinter import simpledialog
        name = simpledialog.askstring("Save Data Preset", "Enter a name for this preset:")
        if not name:
            return
            
        import config
        prefs = config.load_prefs()
        if "data_presets" not in prefs:
            prefs["data_presets"] = {}
            
        preset_data = {}
        for k, v in self.reg_vars.items():
            val = v.get().strip()
            if val:
                preset_data[k] = val
                
        prefs["data_presets"][name] = preset_data
        config.save_prefs(prefs)
        
        # Also update active presets
        if hasattr(self, "active_preset_cb"):
            names = list(prefs["data_presets"].keys())
            self.active_preset_cb["values"] = names
            self.active_preset_var.set(name)
            
        self._refresh_load_data_preset_menu()
        self.system_status.config(text=f"Saved preset '{name}'")
        
    def apply_saved_data_preset(self, name):
        import config
        prefs = config.load_prefs()
        preset = prefs.get("data_presets", {}).get(name)
        if not preset:
            return
            
        applied_count = 0
        modified_widgets = []
        for k, v in preset.items():
            if k in self.reg_vars:
                widget = self.reg_entries.get(k)
                if isinstance(widget, tk.Text):
                    widget.delete("1.0", tk.END)
                    widget.insert("1.0", v)
                    modified_widgets.append(widget)
                else:
                    self.reg_vars[k].set(v)
                    if widget:
                        modified_widgets.append(widget)
                applied_count += 1
            elif hasattr(self, "location_vars") and k in self.location_vars:
                # also support location fields
                self.location_vars[k].set(v)
                # Find the widget
                for idx, loc_name in enumerate(self.location_vars.keys()):
                    if loc_name == k and idx < len(self.location_entries):
                        modified_widgets.append(self.location_entries[idx])
                        break
                applied_count += 1
                
        # Green Flash Animation
        for w in modified_widgets:
            if isinstance(w, ttk.Entry) or isinstance(w, ttk.Combobox):
                # We can't easily style ttk widgets individually without creating dynamic styles,
                # so we can use a temporary style.
                orig_style = w.cget("style")
                w.configure(style="Success.TEntry")
                # Revert after 500ms
                self.root.after(500, lambda wid=w, s=orig_style: wid.configure(style=s))
            elif isinstance(w, tk.Text):
                orig_bg = w.cget("background")
                w.configure(background="#d4edda")
                self.root.after(500, lambda wid=w, bg=orig_bg: wid.configure(background=bg))
                
        self.commit_current_object()
        self.system_status.config(text=f"Applied Data Preset '{name}' ({applied_count} fields)")

    def _refresh_load_data_preset_menu(self):
        self.load_data_preset_menu.delete(0, 'end')
        import config
        prefs = config.load_prefs()
        saved = prefs.get("data_presets", {})
        if not saved:
            self.load_data_preset_menu.add_command(label="(No saved presets)", state="disabled")
            return
            
        for name in saved.keys():
            self.load_data_preset_menu.add_command(label=name, command=lambda n=name: self.apply_saved_data_preset(n))

    def toggle_list_panel_shortcut(self, event=None):
        self.show_list_var.set(not self.show_list_var.get())
        self.toggle_list_panel()
        return "break"

    def toggle_reg_panel_shortcut(self, event=None):
        self.show_reg_var.set(not self.show_reg_var.get())
        self.toggle_reg_panel()
        return "break"

    def toggle_images_panel_shortcut(self, event=None):
        self.show_images_var.set(not self.show_images_var.get())
        self.toggle_images_panel()
        return "break"

    def toggle_list_panel(self):
        if self.show_list_var.get():
            self.panes.insert(0, self.left_frame, weight=1)
        else:
            self.panes.forget(self.left_frame)
            
    def toggle_search_panel(self):
        if hasattr(self, "search_bar_frame"):
            if self.show_search_var.get():
                self.search_bar_frame.pack(fill="x", padx=0, pady=(0, 2), before=self.search_bar_frame.master.winfo_children()[1] if len(self.search_bar_frame.master.winfo_children()) > 1 else None)
            else:
                self.search_bar_frame.pack_forget()
                

    def toggle_location_panel(self):
        if hasattr(self, 'location_in_center_var') and self.location_in_center_var.get():
            if hasattr(self, 'loc_container'):
                self.loc_container.pack_forget()
            if hasattr(self, 'loc_frame_horizontal'):
                self.loc_frame_horizontal.pack(fill="x", pady=(8, 0), side="bottom")
        else:
            if hasattr(self, 'loc_frame_horizontal'):
                self.loc_frame_horizontal.pack_forget()
            if hasattr(self, 'loc_container'):
                self.loc_container.pack(side="top", fill="x")

    def toggle_images_panel(self):
        if self.show_images_var.get():
            self.right_frame.pack(fill="both", expand=True)
            self.refresh_image_view()
        else:
            self.right_frame.pack_forget()
            
    def toggle_image_tools(self):
        self.image_toolbar.pack_forget()
        if self.show_image_tools_var.get():
            self.image_toolbar.pack(before=self.image_box, fill="x", pady=(2, 4))

    def toggle_bulk_edit_btn(self):
        if hasattr(self, 'bulk_edit_btn'):
            if self.show_bulk_edit_var.get():
                self.bulk_edit_btn.pack(side="bottom", fill="x", pady=(2, 0))
            else:
                self.bulk_edit_btn.pack_forget()

    def toggle_dashboard_mode(self):
        if self.dashboard_mode_var.get() == "Window":
            if hasattr(self, "dash_embedded_frame") and self.dash_embedded_frame.winfo_manager():
                self.dash_embedded_frame.pack_forget()
        else:
            if hasattr(self, "dash_win") and self.dash_win.winfo_exists():
                self.dash_win.destroy()






    def _toggle_toolbar_buttons(self):
        for name, btn in self.toolbar_buttons.items():
            if name not in self.toolbar_vars:
                continue
            visible = self.toolbar_vars[name].get()
            manager = btn.winfo_manager()  # 'grid', 'pack', or '' if not mapped
            if visible:
                if manager == "grid":
                    btn.grid()
                elif manager in ("pack", ""):
                    # For pack-managed buttons, use pack_info to restore position
                    try:
                        btn.pack()
                    except Exception:
                        pass
            else:
                if manager == "grid":
                    btn.grid_remove()
                elif manager == "pack":
                    btn.pack_forget()

    def on_left_frame_configure(self, event):
        if hasattr(self, "sb_buttons_frame") and self.sb_buttons_frame.winfo_exists():
            self.sb_buttons_frame.config(width=event.width)

    # ---------- UI ----------
    def build_ui(self):
        # ----------------------------------------------------------------
        # LAYER 4: Global Status Bar — packed FIRST at bottom so panes
        # fills the remaining space above it.
        # ----------------------------------------------------------------
        statusbar_bg = "#1c1b1b"
        statusbar_fg = "#e2e2e2"

        self._status_bar_frame = tk.Frame(self.root, bg=statusbar_bg)
        self._status_bar_frame.pack(side="bottom", fill="x")

        # --- Row 1: Buttons ---
        self.sb_top = tk.Frame(self._status_bar_frame, bg=statusbar_bg, height=32)
        self.sb_top.pack(side="top", fill="x")
        self.sb_top.pack_propagate(False)

        # --- Row 2: Stats ---
        self.sb_bottom = tk.Frame(self._status_bar_frame, bg=statusbar_bg, height=24)
        self.sb_bottom.pack(side="top", fill="x")
        self.sb_bottom.pack_propagate(False)

        sb_top = self.sb_top
        sb_bottom = self.sb_bottom

        self._status_bar_labels = {}

        # Buttons (Row 1) in a frame matching left column width
        self.sb_buttons_frame = tk.Frame(self.sb_top, bg=statusbar_bg, height=32)
        self.sb_buttons_frame.pack(side="left", fill="y")
        self.sb_buttons_frame.grid_propagate(False)
        self.sb_buttons_frame.rowconfigure(0, weight=1)
        self.sb_buttons_frame.columnconfigure(0, weight=1)
        self.sb_buttons_frame.columnconfigure(1, weight=0)
        self.sb_buttons_frame.columnconfigure(2, weight=1)

        self.sb_settings_btn = ttk.Button(
            self.sb_buttons_frame,
            text="SETTINGS",
            style="Tool.TButton",
            command=self.open_focus_settings
        )
        self.sb_settings_btn.grid(row=0, column=0, sticky="nsew", padx=(6, 2), pady=3)

        sep = ttk.Separator(self.sb_buttons_frame, orient="vertical")
        sep.grid(row=0, column=1, sticky="ns", pady=3)

        self.sb_help_btn = ttk.Button(
            self.sb_buttons_frame,
            text="HELP",
            style="Tool.TButton",
            command=self.open_help_window
        )
        self.sb_help_btn.grid(row=0, column=2, sticky="nsew", padx=(2, 6), pady=3)


        # Left stats group
        sb_left = tk.Frame(sb_bottom, bg=statusbar_bg)
        sb_left.pack(side="left", fill="y")

        def _sb_label(parent, key, text):
            lbl = tk.Label(parent, text=text, bg=statusbar_bg, fg=statusbar_fg,
                           font=("Courier New", sc(9)), padx=6, pady=0, anchor="w")
            lbl.pack(side="left")
            self._status_bar_labels[key] = lbl
            return lbl

        def _sb_sep(parent):
            tk.Label(parent, text="|", bg=statusbar_bg, fg="#555555",
                     font=("Courier New", sc(9))).pack(side="left")

        _sb_label(sb_left, "object_count", "OBJECT_COUNT: —")
        _sb_sep(sb_left)
        _sb_label(sb_left, "reviewed", "REVIEWED: —")
        _sb_sep(sb_left)
        self._status_bar_problems_lbl = _sb_label(sb_left, "problems", "PROBLEMS: —")
        _sb_sep(sb_left)
        _sb_label(sb_left, "last_save", "LAST_SAVE: —")

        # Right links group
        sb_right = tk.Frame(sb_bottom, bg=statusbar_bg)
        sb_right.pack(side="right", fill="y")

        def _sb_link(parent, text, cmd):
            lbl = tk.Label(parent, text=text, bg=statusbar_bg, fg="#aaaaaa",
                           font=("Courier New", sc(9)), padx=8, cursor="hand2")
            lbl.pack(side="right")
            lbl.bind("<Button-1>", lambda e: cmd())
            lbl.bind("<Enter>", lambda e: lbl.config(fg="#ffffff"))
            lbl.bind("<Leave>", lambda e: lbl.config(fg="#aaaaaa"))
            return lbl

        _sb_link(sb_right, "DB_STATUS",  lambda: None)   # placeholder — connect later
        _sb_link(sb_right, "LOG_VIEWER", lambda: None)   # placeholder — connect later

        # ----------------------------------------------------------------
        # LAYER 2: Stitch Top Navigation Bar
        # Replaces the old 2-row raw-grid toolbar.
        # Structure: [TITLE] [FILE|NAVIGATE|PROBLEMS|CREATE|HISTORY] ... [STATUS]
        # ----------------------------------------------------------------
        nav_bar_bg = "#f9f9f9"
        nav_border = "#c4c7c7"

        nav_bar = tk.Frame(self.root, bg=nav_bar_bg, height=48,
                           highlightthickness=1, highlightbackground=nav_border,
                           highlightcolor=nav_border)
        nav_bar.pack(fill="x", side="top")
        nav_bar.pack_propagate(False)

        # App title
        tk.Label(
            nav_bar,
            text="arbor",
            bg=nav_bar_bg,
            fg="#000000",
            font=("Segoe UI", sc(12), "bold"),
            padx=16
        ).pack(side="left", anchor="center")

        # 1px vertical separator after title
        tk.Frame(nav_bar, bg=nav_border, width=1).pack(side="left", fill="y", pady=8)

        # --- Nav link buttons ---
        # Each maps to an existing command. style="Nav.TButton" applied after apply_theme().
        nav_links_frame = ttk.Frame(nav_bar)
        nav_links_frame.pack(side="left", fill="y")

        def _nav_btn(parent, label, cmd, is_active=False):
            """
            Creates a navigation button with consistent styling and packs it inside the parent container.

            Args:
                parent (tk.Widget): The container frame to pack the button into.
                label (str): The text label displayed on the button.
                cmd (function): The callback function triggered on button click.
                is_active (bool, optional): Unused flag kept for API consistency.

            Returns:
                ttk.Button: The created styled button widget.
            """
            btn = ttk.Button(parent, text=label, style="Nav.TButton", command=cmd)
            btn.pack(side="left", fill="y")
            self.toolbar_buttons[label] = btn
            self.toolbar_vars[label] = tk.BooleanVar(value=True)
            return btn

        # FILE — opens the file/open dialog
        btn_file = _nav_btn(nav_links_frame, "FILE",     self.open_excel)
        self.add_tooltip(btn_file, "Open an Excel database file")

        # NAVIGATE — active state indicator (current view, no command)
        btn_nav = _nav_btn(nav_links_frame, "NAVIGATE", lambda: None)
        self.add_tooltip(btn_nav, "Active workspace navigation view")

        # IMAGES — jump to next problem
        btn_img = _nav_btn(nav_links_frame, "IMAGES", self.open_image_menu)
        self.add_tooltip(btn_img, "Manage image folder or scan settings")

        # CREATE — add new object or database
        btn_create = _nav_btn(nav_links_frame, "CREATE",   self.show_create_dropdown)
        self.add_tooltip(btn_create, "Create a new museum object or database")

        # HISTORY — recent objects popup
        btn_hist = _nav_btn(nav_links_frame, "HISTORY",  self.open_recent_popup)
        self.add_tooltip(btn_hist, "View recently visited museum objects")

        # 1px separator before secondary controls
        tk.Frame(nav_bar, bg=nav_border, width=1).pack(side="left", fill="y", pady=8)

        # --- Secondary toolbar controls (kept for feature compatibility) ---
        secondary_frame = ttk.Frame(nav_bar)
        secondary_frame.pack(side="left", fill="y", padx=4)

        self.toolbar_buttons['Prev'] = ttk.Button(
            secondary_frame, text="◄ Prev", style="Nav.TButton",
            command=lambda: self.navigate_object(-1))
        self.toolbar_buttons['Prev'].pack(side="left", padx=1)

        self.toolbar_buttons['Next'] = ttk.Button(
            secondary_frame, text="Next ►", style="Nav.TButton",
            command=lambda: self.navigate_object(1))
        self.toolbar_buttons['Next'].pack(side="left", padx=1)

        self.toolbar_buttons['Last'] = ttk.Button(
            secondary_frame, text="Last", style="Nav.TButton",
            command=self.goto_last_object)
        self.toolbar_buttons['Last'].pack(side="left", padx=2)




        tk.Frame(secondary_frame, bg=nav_border, width=1).pack(side="left", fill="y", pady=6)

        self.toolbar_buttons['Next Problem'] = ttk.Button(
            secondary_frame, text="⚠ Next Problem", style="Primary.TButton",
            command=self.goto_next_problem)
        self.toolbar_buttons['Next Problem'].pack(side="left", padx=(4, 1))

        self.next_history_btn = ttk.Button(
            secondary_frame, text="Next+Hist", style="Primary.TButton",
            command=self.goto_next_problem_with_history, state="disabled")
        self.next_history_btn.pack(side="left", padx=1)
        self.toolbar_buttons['Next+Hist'] = self.next_history_btn
        self.add_tooltip(self.next_history_btn, "Jump to next object with suggestions")

        tk.Frame(secondary_frame, bg=nav_border, width=1).pack(side="left", fill="y", pady=6)


#free buttons
        self.toolbar_buttons['New Object'] = ttk.Button(
            secondary_frame, text="New Object", style="Nav.TButton",
            command=self.add_new_object)
        self.toolbar_buttons['New Object'].pack(side="left", padx=2)

        self.toolbar_buttons['Images'] = ttk.Button(
            secondary_frame, text="Images", style="Nav.TButton",
            command=self.open_image_menu)
        self.toolbar_buttons['Images'].pack(side="left", padx=1)

        self.toolbar_buttons['Data'] = ttk.Button(
            secondary_frame, text="Data", style="Nav.TButton",
            command=self.open_advanced_menu)
        self.toolbar_buttons['Data'].pack(side="left", padx=1)


        self.show_all_history_var = tk.BooleanVar(value=False)

        # --- Right side: status indicators ---
        status_container = ttk.Frame(nav_bar)
        status_container.pack(side="right", fill="y", padx=(0, 16))

        # Online status dot + label
        status_dot_frame = ttk.Frame(status_container)
        status_dot_frame.pack(anchor="center", side="right")
        self._online_dot = tk.Canvas(status_dot_frame, width=8, height=8,
                                     highlightthickness=0, bg=nav_bar_bg)
        self._online_dot.create_oval(1, 1, 7, 7, fill="#3b6934", outline="")
        self._online_dot.pack(side="left", padx=(0, 4))
        tk.Label(status_dot_frame, text="STATUS: ONLINE", bg=nav_bar_bg,
                 fg="#444748", font=("Courier New", sc(9))).pack(side="left")

        # Data status badge (saved / unsaved)
        self.data_status = tk.Label(
            status_container,
            anchor="e",
            bg=nav_bar_bg,
            font=("Segoe UI", sc(9), "bold")
        )
        self.data_status.pack(side="right", padx=(0, 8))

        # System status (loading messages etc.)
        real_system_status = ttk.Label(
            status_container,
            anchor="e",
            foreground="#444748"
        )
        real_system_status.pack(side="right", padx=(0, 4))
        self.system_status = LabelWrapper(real_system_status, self)

        # Object count label now lives in the sort_frame (left panel), near Filter button.
        # A placeholder is created here so update_object_count() doesn't fail before build_ui finishes.
        self.search_count_label = ttk.Label(
            status_container,
            text="",
            foreground="gray",
            font=("Segoe UI", sc(8))
        )
        # Not packed here — will be re-parented in the sort_frame below.

        # Image scan progress (hidden by default)
        real_image_scan_progress = ttk.Progressbar(
            status_container,
            orient="horizontal",
            mode="determinate",
            length=140
        )
        real_image_scan_progress.pack(side="right", padx=(0, 8))
        real_image_scan_progress.pack_forget()
        self.image_scan_progress = ProgressbarWrapper(real_image_scan_progress, self)

        # Sync toolbar_vars for all registered buttons
        for name in self.toolbar_buttons:
            if name not in self.toolbar_vars:
                self.toolbar_vars[name] = tk.BooleanVar(value=True)

        # Inline Banner Frame (hidden by default)
        self._inline_banner_frame = tk.Frame(
            self.root, bg="#fef08a", height=0,
            highlightthickness=1, highlightbackground="#facc15"
        )

        # Main 3-column paned workspace (below nav bar, above status bar)
        panes = ttk.Panedwindow(self.root, orient="horizontal")
        panes.pack(fill="both", expand=True)
        self.panes = panes


      
        left = ttk.Frame(panes)
        self.left_frame = left
        panes.add(left, weight=1)
        self.left_frame.bind("<Configure>", self.on_left_frame_configure, add="+")

      
        self.review_progress_label = None
        self.review_progress = None

    
        self.filter_status_label = ttk.Label(
            left,
            text="",
            foreground="#d9534f",
            font=("Segoe UI", sc(8))
        )
        self.filter_status_label.pack(fill="x", padx=6, pady=(0, 2))

      
        sort_frame = ttk.Frame(left)
        sort_frame.pack(fill="x", padx=4, pady=(0, 2))

        ttk.Label(sort_frame, text="Sort:", font=("Segoe UI", sc(8))).pack(side="left")

        self.sort_var = tk.StringVar(value="ID")

        sort_cb = ttk.Combobox(
            sort_frame,
            textvariable=self.sort_var,
            values=["ID", "Genus A-Z", "Reviewed first", "Problems first"],
            state="readonly",
            width=16
        )
        sort_cb.pack(side="left", padx=(4, 0))

        sort_cb.bind(
            "<<ComboboxSelected>>",
            lambda e: self._sort_object_list(self.sort_var.get())
        )

        # Create self.left_panes vertical paned window
        self.left_panes = ttk.Panedwindow(left, orient="vertical")
        self.left_panes.pack(fill="both", expand=True)

        # Bottom container in left column for Location, Settings, and Help
        self.left_bottom_container = ttk.Frame(self.left_panes, style="LeftPane.TFrame")

        self.left_bottom_sep = ttk.Separator(self.left_bottom_container, orient="horizontal")
        self.left_bottom_sep.pack(fill="x", side="top")

        # --- Location container (relocated here) ---
        loc_container = ttk.Frame(self.left_bottom_container, padding=(8, 6), style="LeftPane.TFrame")
        self.loc_container = loc_container
        loc_container.pack(side="top", fill="x")

        loc_box = ttk.Frame(loc_container, style="LeftPane.TFrame")
        loc_box.pack(fill="both", expand=True)
        self.location_frame = loc_box

        # Settings and Help buttons relocated to status bar sb_top.


        # LIST container
        list_container = ttk.Frame(self.left_panes, style="LeftPane.TFrame")
        self.left_panes.add(list_container, weight=1)
        self.left_panes.add(self.left_bottom_container, weight=0)

        # ---------- FILTER ----------
        self.toolbar_buttons['Filter'] = ttk.Button(sort_frame, text="Filter", style="Tool.TButton", command=self.open_filter_menu)
        self.toolbar_buttons['Filter'].pack(side="left", padx=(4, 0))
        self.filter_btn = self.toolbar_buttons['Filter']
        self.add_tooltip(self.toolbar_buttons['Filter'], "Ctrl+G")

        self.search_count_label = None




        # --- Sleek Integrated Search Bar ---
        search_container = tk.Frame(
            list_container, 
            bg="#ffffff", 
            highlightthickness=1, 
            highlightbackground="#d1d1d1"
        )
        self.search_bar_frame = search_container
        self.search_bar_frame.tutorial_id = "search_entry"
        search_container.pack(fill="x", padx=0, pady=(0, sc(6)))

        self._inline_search_var = tk.StringVar()
        self._inline_search_placeholder = "Search ID, Genus, Species..."
        self._inline_search_entry = tk.Entry(
            search_container,
            textvariable=self._inline_search_var,
            font=("Hanken Grotesk", sc(10)),
            bg="#ffffff", fg="#1a1c1c",
            relief="flat", bd=0,
            insertbackground="#000000"
        )
        self._inline_search_entry.pack(side="left", fill="x", expand=True, padx=(sc(8), sc(4)), pady=sc(5))
        self._inline_search_entry.bind("<KeyRelease>",  self._on_inline_search_key)
        self._inline_search_entry.bind("<Escape>",      self._clear_inline_search)
        self._inline_search_entry.bind("<FocusIn>",     self._search_focus_in)
        self._inline_search_entry.bind("<FocusOut>",    self._search_focus_out)
        self._inline_search_entry.bind("<Return>",      self._on_search_bar_enter)
        
        def _focus_list(event):
            self.object_list.focus_set()
            if not self.object_list.selection():
                children = self.object_list.get_children()
                if children:
                    self.object_list.selection_set(children[0])
            return "break"
        self._inline_search_entry.bind("<Tab>", _focus_list)
        
        # Placeholder setup
        self._inline_search_entry.insert(0, self._inline_search_placeholder)
        self._inline_search_entry.config(foreground="gray")

        # Flat integrated clear button
        self.toolbar_buttons['X'] = tk.Button(
            search_container,
            text="✕",
            font=("Hanken Grotesk", sc(9.5), "bold"),
            bg="#ffffff", fg="gray",
            activebackground="#ffffff", activeforeground="#ba1a1a",
            relief="flat", bd=0, cursor="hand2",
            command=self._clear_inline_search
        )
        self.toolbar_buttons['X'].pack(side="right", padx=(sc(4), sc(8)), pady=sc(4))
        self.add_tooltip(self.toolbar_buttons['X'], "Clear Search (resets filter)")

        # Result count label embedded inside
        self._search_count_label = tk.Label(
            search_container, 
            text="", 
            font=("JetBrains Mono", sc(9)), 
            bg="#ffffff", fg="gray"
        )
        self._search_count_label.pack(side="right", padx=(sc(4), 0), pady=sc(4))
    

        # LIST (Upgraded ttk.Treeview Grid)
        list_scroll_frame = ttk.Frame(list_container, style="LeftPane.TFrame")
        list_scroll_frame.pack(side="top", fill="both", expand=True)

        self.object_list = TreeviewListboxWrapper(
            list_scroll_frame,
            self
        )


        self.object_list_scroll = ttk.Scrollbar(
            list_scroll_frame,
            orient="vertical",
            command=self.object_list.yview
        )

        # Koble listbox -> scrollbar
        self.object_list.configure(yscrollcommand=self.object_list_scroll.set)

        self.object_list.pack(side="left", fill="both", expand=True)
        self.object_list_scroll.pack(side="right", fill="y")

        self.object_list.bind("<<ListboxSelect>>", self.on_list_select)
        self.object_list.bind("<Double-Button-1>", self._on_list_double_click)
        self.object_list.bind("<Return>", self._on_list_return)
        self.object_list.bind(
            "<MouseWheel>",
            lambda e: self.object_list.yview_scroll(int(-1 * (e.delta / 120)), "units")
        )
        self.object_list.bind("<Button-1>", self._on_list_click_pre, add="+")
        self.object_list.bind("<Button-3>", self._show_context_menu)
        self.object_list.bind("<Control-Button-1>", self._show_context_menu)

        # Context menu
        self.context_menu = tk.Menu(self.root, tearoff=0)
        self.context_menu.add_command(label="Mark Selected as Reviewed", command=lambda: self._context_set_reviewed(True))
        self.context_menu.add_command(label="Mark Selected as Not Reviewed", command=lambda: self._context_set_reviewed(False))
        self.context_menu.add_separator()
        self.context_menu.add_command(label="Bulk Edit Selected", command=self.open_bulk_edit_window)
        self.context_menu.add_command(label="Duplicate Object", command=lambda: self._shortcut_duplicate_object(None))
        self.context_menu.add_command(label="Delete Object", command=self.delete_current_object)

        self.bulk_edit_btn = ttk.Button(list_container, text="Bulk Edit Selected", state="disabled", command=self.open_bulk_edit_window)
        self.toggle_bulk_edit_btn()




        # Middle

        middle = ttk.Frame(panes, style="MiddlePane.TFrame")
        self.middle_frame = middle
        panes.add(middle, weight=3)

        # Center header: compact single row (ID | title on left, location on right)
        center_header = ttk.Frame(middle, style="MiddlePane.TFrame")
        center_header.pack(fill="x", pady=0)
        # 1px bottom border via a separator-like thin frame
        ttk.Separator(middle, orient="horizontal").pack(fill="x")

        # LEFT: ID monospace + specimen title
        self.title_label = ttk.Label(
            center_header,
            font=("Segoe UI", sc(20), "bold"),
            style="MiddlePane.TLabel"
        )
        self.title_label.pack(side="left", anchor="center", padx=(8, 0), pady=6)

        self.title_problem_count_label = tk.Label(
            center_header,
            font=("Segoe UI", sc(12), "bold"),
            fg="#ba1a1a",
            bg="#ffffff"
        )
        self.title_problem_count_label.pack(side="left", anchor="center", padx=(6, 0), pady=6)

        # RIGHT: location summary (muted, monospace)
        self.location_summary_label = ttk.Label(
            center_header,
            font=("Courier New", sc(9)),
            foreground="#444748",
            style="MiddlePane.TLabel"
        )
        self.location_summary_label.pack(side="right", anchor="center", padx=(0, 8), pady=6)

        # Middle Top (images) - packed directly in middle column since Problem Flags is relocated

        # --- Horizontal Location Container ---
        self.loc_frame_horizontal = tk.Frame(middle, bg="#f5f5f5")
        # will be packed in toggle_location_panel()

        right = ttk.Frame(middle, style="MiddlePane.TFrame")
        self.right_frame = right
        right.pack(fill="both", expand=True)

        header = ttk.Frame(right, style="MiddlePane.TFrame")
        header.pack(fill="x", pady=(4, 4), padx=6)

# open header (formerly Images)
        ttk.Label(
            header,
            text=" ",
            font=("Segoe UI", sc(10), "bold"),
            style="MiddlePane.TLabel"
        ).pack(side="left")

        self.image_count_label = ttk.Label(
            header,
            text="0 images",
            foreground="gray",
            style="MiddlePane.TLabel"
        )
        self.image_count_label.pack(side="left", padx=(10, 0))

        self.view_btn = ttk.Button(
            header,
            text="View: Gallery",
            style="Tool.TButton",
            command=self.toggle_image_view
        )
        self.view_btn.pack(side="right")
        self.update_image_view_button()

        self.images_missing_label = ttk.Label(
            header,
            text="",
            foreground="#ba1a1a",
            font=("Segoe UI", sc(9), "bold"),
            style="MiddlePane.TLabel"
        )
        self.images_missing_label.pack(side="right", padx=(0, 8))

        # Image Control Overlay Toolbar
        image_toolbar = ttk.Frame(right, style="MiddlePane.TFrame")
        self.image_toolbar = image_toolbar
        image_toolbar.pack(fill="x", padx=6, pady=(0, 2))

        ttk.Button(image_toolbar, text="Zoom +", style="Primary.TButton", command=self.zoom_image_in, width=10).pack(side="left", padx=2)
        ttk.Button(image_toolbar, text="Zoom -", style="Primary.TButton", command=self.zoom_image_out, width=10).pack(side="left", padx=2)
        ttk.Button(image_toolbar, text="Rotate 90", style="Primary.TButton", command=self.rotate_image, width=10).pack(side="left", padx=2)
        ttk.Button(image_toolbar, text="Reset", style="Primary.TButton", command=self.reset_image_view, width=8).pack(side="left", padx=2)

        image_box = ttk.Frame(right, relief="flat", padding=0, style="MiddlePane.TFrame")
        self.image_box = image_box
        image_box.pack(fill="both", expand=True)

        self.image_canvas = tk.Canvas(image_box, highlightthickness=0)

        self.image_scroll = ttk.Scrollbar(
            image_box,
            orient="vertical",
            command=self.image_canvas.yview
        )

        self.image_container = ttk.Frame(self.image_canvas)

        self.image_window = self.image_canvas.create_window(
            (0, 0),
            window=self.image_container,
            anchor="nw"
        )

        self.image_container.bind(
            "<Configure>",
            lambda e: self.image_canvas.configure(scrollregion=self.image_canvas.bbox("all"))
        )

        self.image_canvas.configure(yscrollcommand=self.image_scroll.set)
        
        self.image_canvas.pack(side="left", fill="both", expand=True)

        self.image_canvas.bind("<ButtonPress-1>", self._on_pan_start)
        self.image_canvas.bind("<B1-Motion>", self._on_pan_drag)
        self.image_scroll.pack(side="right", fill="y")

        self.image_canvas.bind("<Configure>", self._on_canvas_resize)

        self.image_container.columnconfigure(0, weight=1)
        self.image_container.columnconfigure(1, weight=1)

        self.no_image_label = ttk.Label(
            self.image_container,
            text="No images available",
            foreground="gray"
        )
        self.no_image_label.pack(pady=20)

        # Right (Scrollable registration area)
        reg_outer = ttk.Frame(panes, style="RightPane.TFrame")
        self.reg_outer = reg_outer
        panes.add(reg_outer, weight=3)

        # Create self.right_panes vertical paned window inside reg_outer
        self.right_panes = ttk.Panedwindow(reg_outer, orient="vertical")

        # Create self.reg_data_frame
        self.reg_data_frame = ttk.Frame(self.right_panes, style="RightPane.TFrame")
        self.reg_data_frame.tutorial_id = "object_editor_frame"
        self.right_panes.add(self.reg_data_frame, weight=3)

        # Registration Header Panel (fixed top inside reg_data_frame)
        reg_header = ttk.Frame(self.reg_data_frame, padding=(8, 6), style="RightPane.TFrame")
        reg_header.pack(fill="x", side="top")
        ttk.Separator(self.reg_data_frame, orient="horizontal").pack(fill="x", side="top")

        ttk.Label(
            reg_header,
            text="Registration Data",
            font=("Hanken Grotesk", sc(16), "bold")
        ).pack(side="left")

        # History suggestions button and indicator
        self.history_btn = tk.Button(
            reg_header,
            text="History",
            font=("Hanken Grotesk", sc(9)),
            bg="#ffffff", fg="#1a1c1c",
            relief="solid", bd=1, cursor="hand2",
            padx=sc(8), pady=sc(2),
            command=self.open_historical_suggestions
        )
        self.history_btn.pack(side="left", padx=(8, 0))

        self.history_indicator_label = ttk.Label(
            reg_header,
            text="",
            foreground="#444748",
            cursor="hand2",
            font=("Hanken Grotesk", sc(9))
        )
        self.history_indicator_label.tutorial_id = "history_indicator_label"
        self.history_indicator_label.pack(side="left", padx=(4, 0))
        self.history_indicator_label.bind(
            "<Button-1>",
            lambda e: self.open_historical_suggestions()
        )
        self.add_tooltip(
            self.history_indicator_label,
            "Show historical data (Ctrl+H)"
        )

        # Focus Mode toggle (stays in header)
        focus_quick_frame = ttk.Frame(reg_header, style="RightPane.TFrame")
        focus_quick_frame.pack(side="right", padx=(0, 4))

        self.focus_problems_cb = ToggleSwitch(
            focus_quick_frame,
            self.focus_mode_var,
            command=self.toggle_focus_mode_from_ui,
            ui_ref=self
        )
        self.focus_problems_cb.pack(side="right", padx=(4, 0))
        ttk.Label(focus_quick_frame, text="Focus Mode", font=("Hanken Grotesk", sc(9))).pack(side="right")

        # -------------------------------------------------------
        # Stitch: Fixed action bar — packed at BOTTOM before canvas
        # so it is always visible regardless of scroll position.
        # -------------------------------------------------------
        # Fixed action bar inside reg_outer (moves Reviewed button to very bottom)
        ttk.Separator(self.reg_outer, orient="horizontal").pack(fill="x", side="bottom")
        action_bar = ttk.Frame(self.reg_outer, padding=(8, 6), style="RightPane.TFrame")
        action_bar.pack(fill="x", side="bottom")
        self.right_panes.pack(fill="both", expand=True)

        # Row 1: Mark Reviewed button (large green, full-width)
        action_row1 = ttk.Frame(action_bar, style="RightPane.TFrame")
        action_row1.pack(fill="x", pady=(0, 2))

        self.reviewed_var = tk.BooleanVar()
        large_size = self.large_reviewed_button_var.get()
        padx_val = sc(32) if large_size else sc(18)
        pady_val = sc(14) if large_size else sc(10)
        
        self.reviewed_button = tk.Button(
            action_row1,
            text="✓ MARK AS REVIEWED",
            font=("Hanken Grotesk", sc(11), "bold"),
            relief="flat", bd=0, cursor="hand2",
            padx=padx_val, pady=pady_val,
            highlightthickness=0,
            command=self._on_reviewed_clicked
        )
        self.reviewed_button.tutorial_id = "reviewed_button"
        self.reviewed_button.pack(fill="x", expand=True)

        self.reviewed_var.trace_add("write", lambda *args: self.update_reviewed_button_state())
        self.reviewed_button.bind("<Enter>", self._on_reviewed_btn_enter)
        self.reviewed_button.bind("<Leave>", self._on_reviewed_btn_leave)

        # Row 1b: Secondary action — clear problems checkbutton + status indicators
        action_row1b = ttk.Frame(action_bar, style="RightPane.TFrame")
        action_row1b.pack(fill="x", pady=(4, 0))

        is_dark = getattr(self, "dark_mode_active", False)
        bg_col = "#1e1e2d" if is_dark else "#ffffff"
        fg_col = "#cdd6f4" if is_dark else "#1a1c1c"
        bg_pane = "#181825" if is_dark else "#f9f9f9"

        self.clear_problems_var = tk.BooleanVar(value=False)
        self.clear_problems_cb = tk.Checkbutton(
            action_row1b,
            text="Clear Problems & Mark Reviewed",
            variable=self.clear_problems_var,
            command=self._clear_problems_and_mark_reviewed,
            font=("Segoe UI", sc(9.5)),
            bg=bg_pane, fg=fg_col,
            activebackground=bg_pane, activeforeground=fg_col,
            selectcolor=bg_col,
            relief="flat", bd=0, highlightthickness=0,
            cursor="hand2"
        )
        self.clear_problems_cb.pack(side="left", padx=4)
        self.add_tooltip(
            self.clear_problems_cb,
            "Uncheck all problem flags and mark this object as reviewed (stays on current object)"
        )

        self.auto_next_cb = tk.Checkbutton(
            action_row1b,
            text="Auto-next after review",
            variable=self.auto_advance_var,
            font=("Segoe UI", sc(9.5)),
            bg=bg_pane, fg=fg_col,
            activebackground=bg_pane, activeforeground=fg_col,
            selectcolor=bg_col,
            relief="flat", bd=0, highlightthickness=0,
            cursor="hand2"
        )
        self.auto_next_cb.pack(side="left", padx=4)
        self.add_tooltip(
            self.auto_next_cb,
            "Automatically advance to the next item when marked as reviewed"
        )

        self.reviewed_time_label = ttk.Label(
            action_row1b,
            text="",
            foreground="gray",
            font=("Segoe UI", sc(8))
        )
        self.reviewed_time_label.pack(side="left", padx=(10, 0))

        # Unsaved indicator dot on the right
        self.data_status_action = ttk.Label(
            action_row1b,
            text="",
            foreground="gray",
            font=("Segoe UI", sc(8))
        )
        self.data_status_action.pack(side="right", padx=4)

        # Notebook (tabbed) registration body - packed LAST so it fills the middle of reg_data_frame
        self.reg_notebook = ttk.Notebook(self.reg_data_frame)
        self.reg_notebook.pack(side="top", fill="both", expand=True)

        self.reg_frame = self.reg_notebook
        self.reg_canvas = None  # saved for theme changes

        # Create self.split_frame (Problem Flags) as a dummy frame (no longer added to right_panes)
        split = ttk.Frame(reg_outer, style="RightPane.TFrame")
        self.split_frame = split
        self.prob_container = split
        self.problem_frame = split
        self.pop_out_prob_btn = ttk.Button(split)  # Dummy to prevent attribute errors
        self.problem_count_label = ttk.Label(split)  # Dummy to prevent attribute errors

        self.apply_theme()





#-----

    def _on_history_toggle(self):
    
      
        show_all = self.show_all_history_var.get()

     
        if hasattr(self, "_history_cache"):
            self._history_cache.clear()

    
        oid = self.app.current_object_id
        if oid:
            self.update_history_indicator(oid)

      
        for w in self.root.winfo_children():
            if isinstance(w, tk.Toplevel) and "Information from earlier databases" in str(w.title()):
                w.destroy()
                self.open_historical_suggestions()
                break



#----------
     




#------

    def update_object_count(self):
        count = len(self.app.active_object_ids) if self.app.active_object_ids else 0
        total = len(self.app.df_reg) if self.app.df_reg is not None else 0

        if hasattr(self, "search_count_label") and self.search_count_label is not None:
            try:
                if self.search_count_label.winfo_exists():
                    self.search_count_label.config(
                        text=f"Objects: {count} / {total}"
                    )
            except Exception:
                pass

        # Update status bar labels if they exist
        if hasattr(self, "_status_bar_labels"):
            self._status_bar_labels["object_count"].config(
                text=f"OBJECT_COUNT: {total:,}"
            )
            # Compute reviewed percent and problem count from df_obs if available.
            # Cache the expensive problem-column scan; only recompute when data changes.
            if self.app.df_obs is not None and len(self.app.df_obs) > 0:
                df_obs = self.app.df_obs

                # Reviewed percent — cheap column sum
                rev = int(df_obs[REVIEWED_COLUMN].sum()) if REVIEWED_COLUMN in df_obs.columns else 0
                pct = int((rev / len(df_obs)) * 100)
                self._status_bar_labels["reviewed"].config(
                    text=f"REVIEWED: {pct}%"
                )

                # Problems count — expensive; cache it
                if getattr(self, "_row_cache_dirty", True) or not hasattr(self, "_cached_problems_count"):
                    try:
                        prob_cols = [
                            c for c in df_obs.columns
                            if c not in (REVIEWED_COLUMN, "ReviewedAt")
                            and str(df_obs[c].dtype) == "bool"
                        ]
                        self._cached_problems_count = int((df_obs[prob_cols].any(axis=1)).sum()) if prob_cols else 0
                    except Exception:
                        self._cached_problems_count = 0

                problems_count = self._cached_problems_count
                self._status_bar_labels["problems"].config(text=f"PROBLEMS: {problems_count}")
                self._status_bar_problems_lbl.config(
                    fg="#ff6b6b" if problems_count > 0 else "#e2e2e2"
                )




#------

    def focus_search(self, event=None):
        """Ctrl+F: focus the inline live search bar above the object list."""
        if hasattr(self, "_inline_search_entry"):
            self._inline_search_entry.focus_set()
            self._inline_search_entry.select_range(0, tk.END)
            # Clear placeholder so user can start typing immediately
            if self._inline_search_var.get() == self._inline_search_placeholder:
                self._inline_search_entry.delete(0, tk.END)
                self._inline_search_entry.config(foreground="black")



#------


    def update_review_progress(self):
        if self.app.df_obs is None:
            return

        total = len(self.app.df_obs)

        if total == 0:
            return

        reviewed = int(self.app.df_obs[REVIEWED_COLUMN].sum())

        percent = int((reviewed / total) * 100)

      
        if hasattr(self, "review_progress") and self.review_progress is not None:
            try:
                if self.review_progress.winfo_exists():
                    self.review_progress["value"] = percent
                    self.review_progress["maximum"] = 100
            except Exception:
                pass

        if hasattr(self, "review_progress_label") and self.review_progress_label is not None:
            try:
                if self.review_progress_label.winfo_exists():
                    self.review_progress_label.config(
                        text=f"Reviewed: {percent}% ({reviewed}/{total})"
                    )
            except Exception:
                pass


#-----





    def _on_list_click_pre(self, event):
        if self.loading_object:
            return
        self.object_list.focus_set()
        self.commit_current_object()



    def open_advanced_menu(self):
        btn = self.toolbar_buttons.get('Data')
        
        menu = tk.Menu(self.root, tearoff=0)
        menu.add_command(label="Load books", command=self.load_books_file)
        menu.add_command(label="Load earlier databases", command=self.load_historical_databases)
        menu.add_separator()
        menu.add_checkbutton(
            label="Show all historical data",
            variable=self.show_all_history_var,
            command=self._on_history_toggle
        )
        
        if btn and btn.winfo_exists() and btn.winfo_ismapped():
            x = btn.winfo_rootx()
            y = btn.winfo_rooty() + btn.winfo_height()
        else:
            x = self.root.winfo_pointerx()
            y = self.root.winfo_pointery()
            
        menu.post(x, y)

    def build_search_popup(self):
        # Popup-vindu for sÃ¸ketreff
        self.search_popup = tk.Toplevel(self.root)
        self.search_popup.withdraw()  # skjult som standard
        self.search_popup.overrideredirect(True)
        self.search_popup.geometry("300x200")
        self.search_popup.transient(self.root)

        self.search_listbox = tk.Listbox(
            self.search_popup,
            exportselection=False
        )
        self.search_listbox.pack(fill="both", expand=True)

        # self.search_listbox.bind("<<ListboxSelect>>", self._on_search_select)

        self.search_listbox.bind("<Return>", self._on_search_select)
        self.search_listbox.bind("<Double-Button-1>", self._on_search_select)
        self.search_listbox.bind("<Escape>", lambda e: self.search_popup.withdraw())



    def _on_search_key(self, event):
        # The ObjectID entry is kept for exact ID jumps (press Enter).
        # Live filtering is handled by the inline search bar above the list.
        # The floating popup is no longer shown.
        pass

    def _hide_search_if_outside(self, event):
        # Popup is no longer shown; this is a no-op kept for safety
        pass



#--------
    def show_shortcuts(self):
        # Create a beautiful Toplevel HUD window
        win = tk.Toplevel(self.root)
        win.title("Keyboard Shortcuts HUD")
        import utils
        utils.center_and_fit_toplevel(win, 800, 650)
        win.configure(background="#1e1e2e") # Dark theme for heads-up display look!
        win.transient(self.root)
        
        # Close on Escape
        win.bind("<Escape>", lambda e: win.destroy())
        
        # Title
        title_frame = tk.Frame(win, bg="#1e1e2e")
        title_frame.pack(fill="x", padx=20, pady=(15, 10))
        
        tk.Label(
            title_frame,
            text="Keyboard Shortcuts Cheat Sheet",
            font=("Segoe UI", sc(16), "bold"),
            fg="#cdd6f4",
            bg="#1e1e2e"
        ).pack(side="left")
        
        # Search Box
        search_frame = tk.Frame(win, bg="#1e1e2e")
        search_frame.pack(fill="x", padx=20, pady=(0, 15))
        
        tk.Label(
            search_frame,
            text="Search: ",
            font=("Segoe UI", sc(10), "bold"),
            fg="#a6adc8",
            bg="#1e1e2e"
        ).pack(side="left")
        
        search_var = tk.StringVar()
        search_ent = ttk.Entry(search_frame, textvariable=search_var, font=("Segoe UI", sc(10)))
        search_ent.pack(side="left", fill="x", expand=True, padx=(5, 0))
        search_ent.focus_set()
        
        # Content frame (Canvas + Scrollbar)
        content_outer = tk.Frame(win, bg="#1e1e2e")
        content_outer.pack(fill="both", expand=True, padx=20, pady=(0, 10))
        
        canvas = tk.Canvas(content_outer, bg="#1e1e2e", highlightthickness=0)
        scrollbar = ttk.Scrollbar(content_outer, orient="vertical", command=canvas.yview)
        scroll_content = tk.Frame(canvas, bg="#1e1e2e")
        
        scroll_content.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        window_id = canvas.create_window((0, 0), window=scroll_content, anchor="nw")
        canvas.bind(
            "<Configure>",
            lambda e: canvas.itemconfig(window_id, width=e.width)
        )
        canvas.configure(yscrollcommand=scrollbar.set)
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # Shortcuts list
        shortcuts = [
            ("NAVIGATION", "-- / --", "Previous / Next object"),
            ("NAVIGATION", "Enter", "Load typed ObjectID in search popup"),
            ("NAVIGATION", "--", "Move to search results"),
            ("NAVIGATION", "Escape", "Close search popup"),
            ("NAVIGATION", "Alt+Left", "Go back in navigation history"),
            ("NAVIGATION", "Alt+Right", "Go forward in navigation history"),
            ("FOCUS", "Ctrl+F", "Jump to Search"),
            ("FOCUS", "Ctrl+O", "Jump to Object list"),
            ("FOCUS", "Ctrl+J", "Open Session Dashboard (popup window)"),
            ("FOCUS", "Ctrl+E / Ctrl+I", "Jump to first Registration field"),
            ("FOCUS", "Ctrl+L", "Jump to first Location field"),
            ("FOCUS", "Ctrl+P", "Jump to first Problem checkbox"),
            ("FOCUS", "Ctrl+Q", "Toggle Focus Mode"),
            ("FOCUS", "Shift+E", "Jump to first empty registration field"),
            ("LAPTOP LAYOUT", "F6", "Toggle Object List (Left Sidebar)"),
            ("LAPTOP LAYOUT", "F7", "Toggle Registration & Taxonomy (Center Panel)"),
            ("LAPTOP LAYOUT", "F8", "Toggle Images & Tools (Right Panel)"),
            ("CHECKBOXES", "Shift+--“", "Next problem checkbox"),
            ("CHECKBOXES", "Shift+--", "Previous problem checkbox"),
            ("CHECKBOXES", "Space", "Toggle focused problem checkbox"),
            ("CHECKBOXES", "Return", "Toggle focused problem checkbox (in list)"),
            ("EDITING", "Ctrl+Z", "Undo last field or problem change"),
            ("EDITING", "Ctrl+Y", "Redo last change"),
            ("EDITING", "Ctrl+S", "Save session manually"),
            ("EDITING", "Ctrl+R", "Toggle 'Reviewed' status"),
            ("EDITING", "Ctrl+Shift+C", "Copy focused field value"),
            ("EDITING", "Ctrl+Shift+V", "Paste copied value to focused field"),
            ("OBJECT MANAGEMENT", "Ctrl+N", "New object popup"),
            ("OBJECT MANAGEMENT", "Ctrl+Shift+N", "Quick create new object"),
            ("OBJECT MANAGEMENT", "Ctrl+Shift+D", "Duplicate current object"),
            ("OBJECT MANAGEMENT", "Ctrl+Delete", "Delete current object"),
            ("HISTORY & TOOLS", "Ctrl+H", "Open historical suggestions resolver"),
            ("HISTORY & TOOLS", "Ctrl+G", "Open location/problem filter menu"),
            ("HISTORY & RESOLVER", "Ctrl+A", "Apply resolved changes (resolver window only)"),
            ("IMAGE NAVIGATION", "Shift+-- / Shift+--", "Previous / Next image in gallery"),
            ("IMAGE NAVIGATION", "Double-click", "Open current image in external browser"),
            ("IMAGE NAVIGATION", "Mouse wheel", "Scroll image gallery"),
        ]
        
        # Draw shortcuts helper
        def draw_shortcuts(filter_text=""):
            for w in scroll_content.winfo_children():
                w.destroy()
                
            categories = {}
            filter_lower = filter_text.lower()
            
            for cat, keys, desc in shortcuts:
                if filter_lower and filter_lower not in cat.lower() and filter_lower not in keys.lower() and filter_lower not in desc.lower():
                    continue
                categories.setdefault(cat, []).append((keys, desc))
                
            if not categories:
                tk.Label(
                    scroll_content,
                    text="No shortcuts matched your search.",
                    font=("Segoe UI", sc(11), "italic"),
                    fg="#f38ba8",
                    bg="#1e1e2e"
                ).pack(pady=20)
                return
                
            for cat, items in categories.items():
                cat_frame = tk.Frame(scroll_content, bg="#1e1e2e")
                cat_frame.pack(fill="x", pady=(10, 5), anchor="w")
                
                # Category Header
                tk.Label(
                    cat_frame,
                    text=cat,
                    font=("Segoe UI", sc(11), "bold"),
                    fg="#89b4fa",
                    bg="#1e1e2e"
                ).pack(anchor="w", padx=5)
                
                # Grid of shortcuts
                grid_frame = tk.Frame(scroll_content, bg="#1e1e2e")
                grid_frame.pack(fill="x", padx=15, pady=2, anchor="w")
                grid_frame.columnconfigure(0, minsize=220)
                grid_frame.columnconfigure(1, weight=1)
                
                for r, (keys, desc) in enumerate(items):
                    # Key label (capsule look)
                    key_container = tk.Frame(grid_frame, bg="#11111b", bd=1, relief="ridge", padx=6, pady=3)
                    key_container.grid(row=r, column=0, sticky="w", pady=3, padx=(0, 10))
                    
                    # Split keys by '+' or '/' or ',' to draw individual keycaps if desired, or just show text
                    tk.Label(
                        key_container,
                        text=keys,
                        font=("Consolas", sc(10), "bold"),
                        fg="#f9e2af",
                        bg="#11111b"
                    ).pack()
                    
                    # Description
                    tk.Label(
                        grid_frame,
                        text=desc,
                        font=("Segoe UI", sc(10)),
                        fg="#a6adc8",
                        bg="#1e1e2e",
                        wraplength=550,
                        justify="left"
                    ).grid(row=r, column=1, sticky="w", pady=3)
                    
        # Initial draw
        draw_shortcuts()
        
        # Search binding
        search_var.trace_add("write", lambda *args: draw_shortcuts(search_var.get()))
        
        # Footer
        footer = tk.Frame(win, bg="#1e1e2e")
        footer.pack(fill="x", side="bottom", pady=10, padx=20)
        
        tk.Label(
            footer,
            text="Press Escape to close this window.",
            font=("Segoe UI", sc(9), "italic"),
            fg="#585b70",
            bg="#1e1e2e"
        ).pack(side="left")
        
        ttk.Button(
            footer,
            text="Close",
            command=win.destroy
        ).pack(side="right")


    # ---------- Logging ----------
    def log_action(self, action, 
                   changed_fields=None, changed_values=None,
                   prob_fields=None, prob_values=None,
                   loc_fields=None, loc_values=None):
        
        # Helper to join lists into strings for logging
        def jf(arr): return ", ".join(arr) if isinstance(arr, list) else (arr or "")
        def jv(arr): return " | ".join(arr) if isinstance(arr, list) else (arr or "")

        has_any = bool(changed_fields or prob_fields or loc_fields)
        if not has_any and action != "SAVE":
            cf_text = "(no changes)"
        else:
            cf_text = jf(changed_fields)

        # Defensive: ensure columns exist if the user loaded this file before the update
        for col in ["ProblemsChanged", "ProblemsChangedValues", "LocationChanged", "LocationChangedValues"]:
            if col not in self.app.df_log.columns:
                self.app.df_log[col] = ""

        self.app.df_log.loc[len(self.app.df_log)] = {
            "Timestamp": datetime.now().isoformat(timespec="seconds"),
            "Action": action,
            "ObjectID": self.app.current_object_id,
            "ChangedFields": cf_text or ("(no changes)" if not has_any else ""),
            "ChangedValues": jv(changed_values),
            "ProblemsChanged": jf(prob_fields),
            "ProblemsChangedValues": jv(prob_values),
            "LocationChanged": jf(loc_fields),
            "LocationChangedValues": jv(loc_values),
            "User": getpass.getuser(),
            "SourceFile": os.path.basename(self.app.excel_path),
            "OutputFile": os.path.basename(self.app.output_path),
        }

    # ---------- Commit ----------
    def commit_current_object(self, skip_heavy=None):

        if skip_heavy is None:
            skip_heavy = self._is_navigating

        if self.initializing:
            return [], []

        oid = self.app.current_object_id
        if not oid:
            return [], []



        reg_changed_fields = []
        reg_changed_values = []
        prob_changed_fields = []
        prob_changed_values = []
        loc_changed_fields = []
        loc_changed_values = []

        # -------- REG --------
        state_pushed = False


        def ensure_undo():
            nonlocal state_pushed
            if not state_pushed:
                self.push_undo_state()
                self.app.redo_stacks.setdefault(oid, []).clear()
                state_pushed = True


        for col, widget in self.reg_entries.items():

            old = str(self.app.df_reg.loc[oid, col])

            if isinstance(widget, tk.Text):
                new = widget.get("1.0", tk.END).strip()
            else:
                new = self.reg_vars[col].get()


            if old != new:
                ensure_undo()

                self.app.df_reg.loc[oid, col] = new
                reg_changed_fields.append(col)
                reg_changed_values.append(f'{col}: "{old}"  "{new}"')


        # -------- PROBLEMS --------
        for col, var in self.problem_vars.items():

 
            new = bool(var.get())

 
            old = bool(self.app.df_obs.loc[oid].get(col, False))

  
            if col not in self.app.df_obs.columns:
                self.app.df_obs[col] = False


            if old != new:
                ensure_undo()
                self.app.df_obs.loc[oid, col] = new

                prob_changed_fields.append(col)
                prob_changed_values.append(f'{col}: "{old}"  "{new}"')

                
                self._list_dirty = True





        # -------- TEXT --------
        

        # -------- LOCATION --------
        if not skip_heavy:
            for col, var in self.location_vars.items():
                old = str(self.app.df_obs.loc[oid, col])
                new = var.get()

                if old != new:
                    ensure_undo()
                    self.app.df_obs.loc[oid, col] = new
                    loc_changed_fields.append(col)
                    loc_changed_values.append(f'{col}: "{old}"  "{new}"')

        # -------- REVIEWED --------
        old = bool(self.app.df_obs.loc[oid, REVIEWED_COLUMN])
        new = bool(self.reviewed_var.get())

        if old != new:
            ensure_undo()
            self.app.df_obs.loc[oid, REVIEWED_COLUMN] = new
            if new:
                now = datetime.now().strftime("%d.%m.%Y %H:%M")
                self.app.df_obs.loc[oid, REVIEWED_AT_COLUMN] = now
                self.reviewed_time_label.config(text=f"( {now} )")
                reg_changed_values.append(f"Reviewed set at {now}")
            else:
                self.app.df_obs.loc[oid, REVIEWED_AT_COLUMN] = ""
                self.reviewed_time_label.config(text="")
                reg_changed_values.append("Reviewed removed")

            reg_changed_fields.append(REVIEWED_COLUMN)
            self.update_reviewed_button_state()


        has_changes = (
            bool(reg_changed_fields) or 
            bool(prob_changed_fields) or 
            bool(loc_changed_fields)
        )

        if has_changes:
            self.app.dirty = True
            self.update_dirty_ui()
            self._list_dirty = True
            self._invalidate_row_cache()
            
            # Log the edit immediately so it's captured in the continuous session
            self.log_action("EDIT", 
                            reg_changed_fields, reg_changed_values,
                            prob_changed_fields, prob_changed_values,
                            loc_changed_fields, loc_changed_values)

            self.update_history_indicator(oid)   


            self._list_dirty = True
            self._problem_cache.pop(oid, None)

            
            if {"Genus", "Species"} & set(reg_changed_fields):
                self.invalidate_search_index()

        




#------

    def _invalidate_row_cache(self):
        """Mark the refresh_list() row-dict caches as stale so they are rebuilt on next refresh."""
        self._row_cache_dirty = True

    def _get_obs_dict(self):
        if getattr(self, "_row_cache_dirty", True) or getattr(self, "_cached_obs_dict", None) is None:
            obs_df = self.app.df_obs
            self._cached_obs_dict = obs_df.to_dict(orient="index") if obs_df is not None else {}
        return self._cached_obs_dict

    def _get_reg_dict(self):
        if getattr(self, "_row_cache_dirty", True) or getattr(self, "_cached_reg_dict", None) is None:
            reg_df = self.app.df_reg
            self._cached_reg_dict = reg_df.to_dict(orient="index") if reg_df is not None else {}
        return self._cached_reg_dict


    def update_location_summary(self, oid):
        if oid not in self.obs_by_id.index:
            self.location_summary_label.config(text="")
            return

        obs = self.obs_by_id.loc[oid]
    
        if isinstance(obs, pd.DataFrame):
            obs = obs.iloc[0]




        def fmt(v):
            if pd.isna(v) or v == "":
                return ""
            if isinstance(v, float) and v.is_integer():
                return str(int(v))
            return str(v)


        floor = fmt(obs.get("Floor", ""))
        cabinet = fmt(obs.get("Cabinet", ""))
        building = fmt(obs.get("Building", ""))
        extra = fmt(obs.get(" ", ""))


        loaned_raw = obs.get("Loaned out", False)
        if isinstance(loaned_raw, str):
            loaned = loaned_raw.strip().lower() == "true"
        else:
            loaned = bool(loaned_raw)


  
      



        lines = []

        if floor or cabinet:
            lines.append(f"Floor: {floor}   |   Cabinet: {cabinet}")

        if building:
            lines.append(f"{building}")

        if loaned:
            lines.append("Loaned out: Yes")

        if extra:
            lines.append(f"{extra}")

        text = "\n".join(lines) if lines else "No location info"


    
        self.location_summary_label.config(text=text)



    # ---------- Database handling ----------

    # ---------- Excel handling ----------


#--------



    def ui_error(self, title, msg):
        self.root.after(0, lambda: messagebox.showerror(title, msg))

    def show_traceback_dialog(self, title, message, traceback_text):
        """Displays a scrollable monospace traceback dialog for errors."""
        dialog = tk.Toplevel(self.root)
        dialog.title(title)
        dialog.resizable(True, True)
        dialog.minsize(550, 400)
        dialog.grab_set()

        s = getattr(self, "_scale", 1.0)
        import utils
        utils.center_and_fit_toplevel(dialog, int(600 * s), int(450 * s))

        # Main frame
        frame = ttk.Frame(dialog, padding=15)
        frame.pack(fill="both", expand=True)

        # Title / Header
        header_lbl = ttk.Label(
            frame, text=message,
            font=("Segoe UI", sc(11), "bold"),
            wraplength=int(550 * s),
            justify="left"
        )
        header_lbl.pack(anchor="w", pady=(0, 10))

        # Text container for scrollbar
        text_frame = ttk.Frame(frame)
        text_frame.pack(fill="both", expand=True, pady=5)

        text_area = tk.Text(
            text_frame,
            wrap="none",
            font=("Courier New", sc(9.5)),
            bg="#1e1e1e", # dark background
            fg="#d4d4d4", # light gray text
            insertbackground="white",
            highlightthickness=1,
            highlightbackground="#3c3c3c",
            relief="flat"
        )
        text_area.insert("1.0", traceback_text)
        text_area.configure(state="disabled") # read-only
        text_area.pack(side="left", fill="both", expand=True)

        # Scrollbars
        v_scroll = ttk.Scrollbar(text_frame, orient="vertical", command=text_area.yview)
        v_scroll.pack(side="right", fill="y")
        text_area.config(yscrollcommand=v_scroll.set)

        h_scroll = ttk.Scrollbar(frame, orient="horizontal", command=text_area.xview)
        h_scroll.pack(fill="x", pady=(2, 8))
        text_area.config(xscrollcommand=h_scroll.set)

        # Footer frame with copy and close buttons
        footer = ttk.Frame(frame)
        footer.pack(fill="x", side="bottom")

        def copy_traceback():
            self.root.clipboard_clear()
            self.root.clipboard_append(traceback_text)
            copy_btn.config(text="Copied!")
            self.root.after(1500, lambda: copy_btn.config(text="Copy to Clipboard"))

        copy_btn = ttk.Button(footer, text="Copy to Clipboard", command=copy_traceback)
        copy_btn.pack(side="left")

        close_btn = ttk.Button(footer, text="Close", command=dialog.destroy)
        close_btn.pack(side="right")

    def show_banner(self, text, banner_type="info", duration_ms=4000):
        """Displays an inline notification banner at the top of the workspace."""
        if not hasattr(self, "_inline_banner_frame"):
            return

        # Configure colors based on type
        colors = {
            "success": {"bg": "#dcfce7", "border": "#22c55e", "fg": "#14532d", "icon": "✔"},
            "warning": {"bg": "#fef9c3", "border": "#eab308", "fg": "#713f12", "icon": "⚠"},
            "error":   {"bg": "#fee2e2", "border": "#ef4444", "fg": "#7f1d1d", "icon": "✘"},
            "info":    {"bg": "#dbeafe", "border": "#3b82f6", "fg": "#1e3a8a", "icon": "ℹ"},
        }
        cfg = colors.get(banner_type, colors["info"])

        # Update banner styles
        self._inline_banner_frame.config(
            bg=cfg["bg"],
            highlightbackground=cfg["border"],
            highlightcolor=cfg["border"],
            highlightthickness=1
        )

        # Clear existing children to rebuild or update widgets
        for child in self._inline_banner_frame.winfo_children():
            child.destroy()

        s = getattr(self, "_scale", 1.0)
        inner = tk.Frame(self._inline_banner_frame, bg=cfg["bg"])
        inner.pack(fill="x", padx=int(16*s), pady=int(6*s))

        # Icon Label
        icon_lbl = tk.Label(
            inner, text=cfg["icon"],
            bg=cfg["bg"], fg=cfg["fg"],
            font=("Segoe UI", sc(11), "bold")
        )
        icon_lbl.pack(side="left", padx=(0, int(8*s)))

        # Text Label
        text_lbl = tk.Label(
            inner, text=text,
            bg=cfg["bg"], fg=cfg["fg"],
            font=("Segoe UI", sc(10)),
            anchor="w"
        )
        text_lbl.pack(side="left", fill="x", expand=True)

        # Close Button
        close_btn = tk.Button(
            inner, text="✕",
            bg=cfg["bg"], fg=cfg["fg"],
            font=("Segoe UI", sc(10), "bold"),
            relief="flat", bd=0, cursor="hand2",
            padx=int(6*s), pady=0,
            command=self.hide_banner
        )
        close_btn.pack(side="right")

        # Close button hover effect
        def _on_enter(e):
            hover_bg = {
                "success": "#bbf7d0",
                "warning": "#fef08a",
                "error":   "#fecaca",
                "info":    "#bfdbfe"
            }.get(banner_type, "#e2e2e2")
            close_btn.config(bg=hover_bg)

        def _on_leave(e):
            close_btn.config(bg=cfg["bg"])

        close_btn.bind("<Enter>", _on_enter)
        close_btn.bind("<Leave>", _on_leave)

        # Pack at the top of root (below nav_bar)
        self._inline_banner_frame.pack(side="top", fill="x", before=self.panes)

        # Auto-dismiss timer
        if hasattr(self, "_banner_timer_id") and self._banner_timer_id:
            self.root.after_cancel(self._banner_timer_id)
            self._banner_timer_id = None

        if duration_ms > 0:
            self._banner_timer_id = self.root.after(duration_ms, self.hide_banner)

    def hide_banner(self):
        """Hides the inline notification banner."""
        if hasattr(self, "_banner_timer_id") and self._banner_timer_id:
            self.root.after_cancel(self._banner_timer_id)
            self._banner_timer_id = None
        if hasattr(self, "_inline_banner_frame"):
            self._inline_banner_frame.pack_forget()







    


    def _select_first_object(self):
        if not self.app.active_object_ids:
            return

        self.object_list.selection_clear(0, tk.END)
        self.object_list.selection_set(0)
        self.object_list.see(0)

       
        self.object_list.focus_set()

        # Tving event
        self.object_list.event_generate("<<ListboxSelect>>")

# --------- auto flag problems ---





    # ---------- Load / Save ----------
    def on_list_select(self, event=None):
        if self.loading_object:
            return

        sel = self.object_list.curselection()
        if hasattr(self, "bulk_edit_btn"):
            if len(sel) > 1:
                self.bulk_edit_btn.configure(state="normal")
            else:
                self.bulk_edit_btn.configure(state="disabled")

        if len(sel) > 1:
            return

        if sel:
            idx = sel[0]
            oid = self.app.active_object_ids[idx]
            
            if self._is_searching():
                return
                
            if oid == self.app.current_object_id:
                return

            if not self._is_navigating:
                self._is_navigating = True
                self.commit_current_object()

            if self._nav_idle_job:
                try:
                    self.root.after_cancel(self._nav_idle_job)
                except Exception:
                    pass
            self._nav_idle_job = self.root.after(150, self._navigation_finished)
            
            # Debounce selection changes (150ms)
            if hasattr(self, '_list_select_job') and self._list_select_job:
                try:
                    self.root.after_cancel(self._list_select_job)
                except Exception:
                    pass
                
            self._list_select_job = self.root.after(150, lambda: self._deferred_list_select(oid))

    def _deferred_list_select(self, oid):
        self._list_select_job = None
        if not self.root.winfo_exists():
            return
        # Ensure navigation mode is off so load_object doesn't skip anything heavy
        self._is_navigating = False
        if self._nav_idle_job:
            try:
                self.root.after_cancel(self._nav_idle_job)
            except Exception:
                pass
            self._nav_idle_job = None
            
        self.load_object(oid)
        self._fix_listbox_horizontal_scroll()



    def _format_int_like(self, value):
        if pd.isna(value) or value == "":
            return "Unknown"
        if isinstance(value, float) and value.is_integer():
            return str(int(value))
        return str(value)

    def load_object(self, oid, is_history_nav=False):
        if hasattr(self, "clear_problems_var"):
            self.clear_problems_var.set(False)
        self.image_zoom_factor = 1.0
        self.image_rotation_angle = 0
        if hasattr(self, '_list_select_job') and self._list_select_job:
            try:
                self.root.after_cancel(self._list_select_job)
            except Exception:
                pass
            self._list_select_job = None

        self.field_undo_stack.clear()

        skip_heavy = self._is_navigating

        if self.loading_object:
            return

      
        prev = self.app.current_object_id

        if prev and prev != oid:
            self.last_object_id = prev

            if not is_history_nav:
                self.forward_stack.clear()

          
            if not self.history_stack or self.history_stack[-1] != prev:
                self.history_stack.append(prev)

                if len(self.history_stack) > 50:
                    self.history_stack.pop(0)

        # Clear any lingering "Did you mean" labels from the previous object
        self._clear_all_fuzzy_labels()

        # Collect suggestions for this specific ObjectID
        self.current_object_suggestions = {}
        if oid and self.app.historical_dbs:
            for db in self.app.historical_dbs:
                dict_cache = self._get_db_dict_cache(db, oid)
                oid_data = dict_cache.get(oid, {})
                for field, field_vals in oid_data.items():
                    if field in self.reg_columns:
                        vals = self.current_object_suggestions.setdefault(field, [])
                        for v in field_vals:
                            if v not in vals:
                                vals.append(v)

        self.loading_object = True
        try:
            if not skip_heavy:
                for w in self.image_container.winfo_children():
                    w.destroy()
          


            self.no_image_label.pack_forget()

            
            if not skip_heavy:
                self.images_missing_label.config(text="")
            self.app.current_object_id = oid
            self.object_loaded = True


            self.object_id_var.set(oid)

            self.title_label.config(text=self.object_title(oid))

            reg = self.reg_by_id.loc[oid]
            if isinstance(reg, pd.DataFrame):
                reg = reg.iloc[0]

            obs = self.obs_by_id.loc[oid]
            if isinstance(obs, pd.DataFrame):
                obs = obs.iloc[0]


            if self.image_mode == "online":
                self.images_missing_var.set("Online images")
                self.images_missing_label.config(foreground="blue")

            elif self.image_mode == "offline":
                self.images_missing_var.set("Offline Mode no images available")
                self.images_missing_label.config(foreground="gray")

            else:  # folder mode
                images_missing = bool(obs.get("Images_Missing", False))

                if images_missing:
                    self.images_missing_var.set("Images missing")
                    self.images_missing_label.config(foreground="red")
                else:
                    self.images_missing_var.set("Images OK")
                    self.images_missing_label.config(foreground="green")





            self.update_history_indicator(oid)




            for col, var in self.location_vars.items():
                val = obs.get(col, "")

                if pd.isna(val) or val == "":
                    var.set("")  
                else:
                    if isinstance(val, float) and val.is_integer():
                        var.set(str(int(val)))
                    else:
                        var.set(str(val))


            if oid in self.photo_by_id.index:
                photo = self.photo_by_id.loc[oid]
                if isinstance(photo, pd.DataFrame):
                    photo = photo.iloc[0]
            else:
                photo = {}
            

            for col, widget in self.reg_entries.items():
                value = reg.get(col, "")

                if isinstance(widget, tk.Text):
                    if not skip_heavy:
                        widget.delete("1.0", tk.END)
                        widget.insert("1.0", str(value))
                else:
                    if self.reg_vars[col].get() != value:
                        self.reg_vars[col].set(value)
                    if isinstance(widget, ttk.Combobox) and col not in self.choice_fields:
                        vals = self.current_object_suggestions.get(col, [])
                        widget.configure(values=vals)

            for prob_col, v in self.problem_vars.items():
                obs_val = bool(obs.get(prob_col, False))


                if prob_col in self.problem_to_field:
                    field = self.problem_to_field[prob_col]
                    raw_val = reg.get(field)

                
                    if prob_col == "Other_problem":
                        auto_val = False
                    else:
                        auto_val = (
                            pd.isna(raw_val) or
                            (isinstance(raw_val, str) and raw_val.strip() == "")
                        )
                else:
                    auto_val = False

                display_val = obs_val or auto_val
                v.set(display_val)

            # Apply problem row styles after all vars are set (traces fire via after_idle,
            # but we also call explicitly here to guarantee correct state on load)
            self._update_all_problem_row_styles()

            self.reviewed_var.set(bool(obs.get(REVIEWED_COLUMN, False)))



            if not skip_heavy:
                self.load_images(oid)

            reviewed_at = str(obs.get(REVIEWED_AT_COLUMN, ""))

            if reviewed_at:
                self.reviewed_time_label.config(text=f"( {reviewed_at} )")
            else:
                self.reviewed_time_label.config(text="")


        finally:
            self.loading_object = False



        self.update_location_summary(oid)
        self.update_location_summary_view()
        self.update_problems_default_view()
        self.update_reviewed_button_state()



        self.app.redo_stacks.setdefault(oid, [])


        self.highlight_fields_with_suggestions(oid)



        if oid not in self.app.undo_stacks:
            self.app.undo_stacks[oid] = [{
                "reg": self.app.df_reg.loc[oid].copy(),
                "obs": self.app.df_obs.loc[oid].copy(),
            }]

        if oid not in self.app.redo_stacks:
            self.app.redo_stacks[oid] = []


        self.update_image_view_button()
        self.update_reg_fields_visibility()
        self._preload_adjacent_images(oid)
        self.update_navigation_buttons()


        # Only steal focus to first reg entry if the user is NOT actively typing
        # in the live search bar or actively navigating the listbox
        if not skip_heavy and self.reg_entry_list:
            focused = self.root.focus_get()
            is_in_search = False
            if hasattr(self, '_inline_search_entry'):
                is_in_search = (focused == self._inline_search_entry or 
                                (focused is not None and str(focused) == str(self._inline_search_entry)) or
                                getattr(self, '_is_applying_search', False))
            
            is_in_listbox = (focused == self.object_list or 
                             (focused is not None and str(focused) == str(self.object_list)))

            if not is_in_search and not is_in_listbox:
                self.reg_entry_list[0].focus_set()
        


    def _update_list_if_needed(self):
        self._list_dirty = True


    def has_images(self, oid):
        if self.image_mode in ("online", "offline"):
            return True
        return not self.app.df_obs.loc[oid, "Images_Missing"]







    def load_object_from_entry(self, _=None):
        self.commit_current_object()

        oid = self.object_id_var.get().strip()
        if oid in self.app.active_object_ids:
            self.load_object(oid)
        else:
            messagebox.showinfo("Not found","ObjectID not found")

#---- SAVE





    def on_close(self):
        if self.app.dirty:
            res = messagebox.askyesnocancel("Unsaved changes", "Save before exiting?")
            if res is None:
                return
            if res:
                self.save_session("CLOSE")

        if self._autosave_job:
            self.root.after_cancel(self._autosave_job)
            self._autosave_job = None

        # Clean up active autosave on clean exit
        if self.app.excel_path:
            autosave_path = self._autosave_path()
            if os.path.exists(autosave_path):
                try:
                    os.remove(autosave_path)
                except Exception:
                    pass

        # If errors were logged this session, offer to view the log before exit
        try:
            from utils import session_had_errors, get_session_log_path
            if session_had_errors():
                show_log = messagebox.askyesno(
                    "Errors occurred this session",
                    "One or more errors were logged during this session.\n\n"
                    "Would you like to view the error log before closing?",
                    parent=self.root
                )
                if show_log:
                    self.show_error_log_window(get_session_log_path())
                    return   # Let user close the log window; they can exit from there
        except Exception:
            pass

        self.root.destroy()


    def show_error_log_window(self, log_path: str | None = None) -> None:
        """
        Open a scrollable, styled Toplevel window that displays the current
        session error log (or any specified log file).  Provides:
          - Colour-coded lines (ERROR red, timestamp grey)
          - Copy-to-clipboard button
          - Open-in-Explorer button
          - Close-and-exit button (destroys root)
        """
        from utils import get_session_log_path
        import os

        if log_path is None:
            log_path = get_session_log_path()

        # Read log content
        try:
            if os.path.exists(log_path):
                with open(log_path, "r", encoding="utf-8", errors="replace") as f:
                    log_text = f.read()
            else:
                log_text = "(No errors have been logged yet in this session.)"
        except Exception as exc:
            log_text = f"Could not read log file:\n{exc}"

        win = tk.Toplevel(self.root)
        win.title(f"Error Log — {os.path.basename(log_path)}")
        win.resizable(True, True)
        win.minsize(660, 420)
        win.configure(bg="#1a1a2e")

        import utils
        utils.center_and_fit_toplevel(win, 760, 560)

        # ── Header bar ──────────────────────────────────────────────────────
        header = tk.Frame(win, bg="#16213e", pady=10)
        header.pack(fill="x")

        tk.Label(
            header, text="⚠  Session Error Log",
            bg="#16213e", fg="#e94560",
            font=("Segoe UI", sc(13), "bold")
        ).pack(side="left", padx=16)

        tk.Label(
            header, text=os.path.basename(log_path),
            bg="#16213e", fg="#888888",
            font=("Courier New", sc(9))
        ).pack(side="right", padx=16)

        # ── Log text area ────────────────────────────────────────────────────
        text_frame = tk.Frame(win, bg="#1a1a2e")
        text_frame.pack(fill="both", expand=True, padx=10, pady=(6, 0))

        text_area = tk.Text(
            text_frame,
            wrap="none",
            font=("Courier New", sc(9)),
            bg="#0d1117",
            fg="#c9d1d9",
            insertbackground="white",
            selectbackground="#264f78",
            highlightthickness=0,
            relief="flat",
            state="normal"
        )

        v_scroll = ttk.Scrollbar(text_frame, orient="vertical", command=text_area.yview)
        h_scroll = ttk.Scrollbar(win, orient="horizontal", command=text_area.xview)
        text_area.configure(yscrollcommand=v_scroll.set, xscrollcommand=h_scroll.set)

        v_scroll.pack(side="right", fill="y")
        text_area.pack(side="left", fill="both", expand=True)
        h_scroll.pack(fill="x", padx=10, pady=(0, 4))

        # Colour tags
        text_area.tag_configure("error_line",  foreground="#ff6b6b", font=("Courier New", sc(9), "bold"))
        text_area.tag_configure("ts_line",      foreground="#6e7681")
        text_area.tag_configure("sep_line",     foreground="#30363d")
        text_area.tag_configure("tb_line",      foreground="#adbac7")

        # Insert log content with per-line colouring
        for line in log_text.splitlines(keepends=True):
            stripped = line.lstrip()
            if stripped.startswith("[ERROR]") or "Error" in line[:30]:
                tag = "error_line"
            elif stripped.startswith("[") and "]" in stripped[:25]:  # timestamp lines
                tag = "ts_line"
            elif set(stripped.strip()).issubset(set("─═")):
                tag = "sep_line"
            else:
                tag = "tb_line"
            text_area.insert(tk.END, line, tag)

        text_area.configure(state="disabled")
        text_area.see(tk.END)   # scroll to bottom so latest error is visible

        # ── Footer bar ───────────────────────────────────────────────────────
        footer = tk.Frame(win, bg="#16213e", pady=8)
        footer.pack(fill="x", side="bottom")

        def _copy():
            win.clipboard_clear()
            win.clipboard_append(log_text)
            copy_btn.config(text="Copied!")
            win.after(1800, lambda: copy_btn.config(text="Copy to Clipboard"))

        def _open_in_explorer():
            try:
                import subprocess
                subprocess.Popen(["explorer", "/select,", os.path.abspath(log_path)])
            except Exception:
                pass

        def _close_log_and_exit():
            win.destroy()
            self.root.destroy()

        copy_btn = tk.Button(
            footer, text="Copy to Clipboard", command=_copy,
            bg="#0f3460", fg="#e0e0e0", relief="flat",
            font=("Segoe UI", sc(9)), padx=10, pady=4, cursor="hand2"
        )
        copy_btn.pack(side="left", padx=(12, 6))

        tk.Button(
            footer, text="Open Logs Folder", command=_open_in_explorer,
            bg="#0f3460", fg="#e0e0e0", relief="flat",
            font=("Segoe UI", sc(9)), padx=10, pady=4, cursor="hand2"
        ).pack(side="left", padx=6)

        tk.Button(
            footer, text="Close Log", command=win.destroy,
            bg="#333355", fg="#e0e0e0", relief="flat",
            font=("Segoe UI", sc(9)), padx=10, pady=4, cursor="hand2"
        ).pack(side="right", padx=(6, 12))

        tk.Button(
            footer, text="Close Log & Exit App", command=_close_log_and_exit,
            bg="#7a1c1c", fg="#ffffff", relief="flat",
            font=("Segoe UI", sc(9), "bold"), padx=10, pady=4, cursor="hand2"
        ).pack(side="right", padx=6)

        win.grab_set()


#--------- highlight funksjon

    def _highlight_active_field(self, widget):
        for w in self.reg_entry_list:
            try:
                w.configure(background="white")
            except Exception as e:
                debug_error("Suppressed Error", str(e))
                pass

        try:
            widget.configure(background="#d0ebff")  # lys blÃ¥
        except Exception as e:
            debug_error("Suppressed Error", str(e))
            pass


    def highlight_fields_with_suggestions(self, oid):
        # Track the last background color set per field to skip redundant Tcl calls.
        if not hasattr(self, "_field_bg_state"):
            self._field_bg_state = {}

        suggestions = self.collect_historical_suggestions(oid)

        # Use cached reg row if available
        if (not getattr(self, "_row_cache_dirty", True)
                and self._cached_reg_dict is not None
                and oid in self._cached_reg_dict):
            reg_row = self._cached_reg_dict[oid]
            def _get(field): return reg_row.get(field, "")
        else:
            reg = self.reg_by_id.loc[oid]
            if isinstance(reg, pd.DataFrame):
                reg = reg.iloc[0]
            def _get(field): return reg.get(field, "")

        def _set_bg(widget, field, color):
            if self._field_bg_state.get(field) == color:
                return  # already this color — skip Tcl call
            try:
                if isinstance(widget, tk.Text):
                    widget.configure(bg=color)
                else:
                    widget.configure(background=color)
                self._field_bg_state[field] = color
            except Exception as e:
                debug_error("Suppressed Error", str(e))

        for field, widget in self.reg_entries.items():
            if not widget:
                continue
            try:
                raw_val = _get(field)
                if isinstance(raw_val, pd.Series):
                    raw_val = raw_val.iloc[0]

                if self.is_unknown(raw_val):
                    _set_bg(widget, field, "#ffe4b3")
                elif field in suggestions:
                    _set_bg(widget, field, "#fff3a3")
                else:
                    _set_bg(widget, field, "white")
            except Exception as e:
                debug_error("Suppressed Error", str(e))





#-----







#---- go back




# --- next problem

    def goto_next_problem(self):
        self.commit_current_object()

        if not self.app.active_object_ids:
            return

        ids = self.app.active_object_ids
        n = len(ids)

        if not self.app.current_object_id or self.app.current_object_id not in ids:
            start_idx = -1
        else:
            start_idx = ids.index(self.app.current_object_id)

        # Use cached problem state; fall back to has_any_problem for cache misses
        obs_dict = self._get_obs_dict()

        for step in range(1, n + 1):
            i = (start_idx + step) % n
            oid = ids[i]

            obs_row = obs_dict.get(oid, {})
            if obs_row.get(REVIEWED_COLUMN):
                continue

            # Use _problem_cache if populated; compute on demand otherwise
            has_checkbox_problem = self._get_cached_problem(oid)

            if has_checkbox_problem:
                self.object_list.selection_clear(0, tk.END)
                self.object_list.selection_set(i)
                self.object_list.see(i)
                self.load_object(oid)
                return

        messagebox.showinfo("Done", "No more problems found")






#--- next problem with history

    def goto_next_problem_with_history(self):
        self.commit_current_object()

        if not self.app.active_object_ids:
            return

        ids = self.app.active_object_ids

        if not self.app.current_object_id or self.app.current_object_id not in ids:
            start_idx = -1
        else:
            start_idx = ids.index(self.app.current_object_id)

        total = len(ids)

        # Use cached obs dict for the reviewed check to avoid per-row .loc
        obs_dict = self._get_obs_dict()

        for step in range(1, total + 1):
            i = (start_idx + step) % total
            oid = ids[i]

            obs_row = obs_dict.get(oid, {})
            if obs_row.get(REVIEWED_COLUMN):
                continue

            suggestions = self.collect_historical_suggestions(oid)
            if not suggestions:
                continue

            match = False

            for prob_col, field in self.problem_to_field.items():

                if not self.is_problem_active(oid, prob_col):
                    continue

               
                if field in suggestions:
                    match = True
                    break

            if not match:
                continue

          
            self.object_list.selection_clear(0, tk.END)
            self.object_list.selection_set(i)
            self.object_list.see(i)
            self.load_object(oid)
            return

        messagebox.showinfo("Done", "No matching objects found")



#---- go to last object

    def goto_last_object(self):

        if not self.last_object_id:
            return

        oid = self.last_object_id



        if not oid or oid == self.app.current_object_id:
            return
    

        if oid in self.app.active_object_ids:
            idx = self.app.active_object_ids.index(oid)

            self.object_list.selection_clear(0, tk.END)
            self.object_list.selection_set(idx)
            self.object_list.see(idx)

            self.load_object(oid)


# ---------- Images ----------
























    def ensure_no_image_label(self):
        if not hasattr(self, "no_image_label") or not self.no_image_label.winfo_exists():
            self.no_image_label = ttk.Label(
                self.image_container,
                text="No images available",
                foreground="gray"
            )






    def open_image_web(self, path):
        import webbrowser
        filename = os.path.basename(path)
        webbrowser.open(f"https://www.unimus.no/photos/image/jpeg/{filename}")


    def _show_no_images_online(self):
        try:
            self.images_missing_label.config(text="No online images found")

            self.ensure_no_image_label()

            if self.no_image_label.winfo_exists():
                self.no_image_label.pack(pady=20)

        except Exception as e:
            debug_error("Suppressed Error", str(e))
            pass













    def _show_no_images_local(self):
        try:
            self.images_missing_label.config(text="Could not load images")

            self.ensure_no_image_label()

            if self.no_image_label.winfo_exists():
                self.no_image_label.pack(pady=20)

        except Exception as e:
            debug_error("Suppressed Error", str(e))
            pass










    # ---------- Navigation ----------


    def _fix_listbox_horizontal_scroll(self):
        self.object_list.xview_moveto(0)


    def navigate_object(self, step):
        total = len(self.app.active_object_ids)
        if total == 0:
            return

        if not self._is_navigating:
            self._is_navigating = True
            self.commit_current_object()

        if self._nav_idle_job:
            try:
                self.root.after_cancel(self._nav_idle_job)
            except Exception:
                pass
        self._nav_idle_job = self.root.after(150, self._navigation_finished)

        if self.app.current_object_id in self.app.active_object_ids:
            current_index = self.app.active_object_ids.index(self.app.current_object_id)
        else:
            current_index = 0

        new_idx = (current_index + step) % total
        oid = self.app.active_object_ids[new_idx]

        if oid == self.app.current_object_id:
            return

        # Instantly update listbox selection highlight
        self.object_list.selection_clear(0, tk.END)
        self.object_list.selection_set(new_idx)
        self.object_list.see(new_idx)
        self.object_list.activate(new_idx)

        # Debounce the load
        if hasattr(self, '_list_select_job') and self._list_select_job:
            try:
                self.root.after_cancel(self._list_select_job)
            except Exception:
                pass
                
        self._list_select_job = self.root.after(150, lambda: self._deferred_list_select(oid))


    def _navigation_finished(self):

        self._is_navigating = False

        if self.app.current_object_id:
            self.load_images(self.app.current_object_id)


# ---------- 


    def is_unknown(self, value):
        if value is None:
            return False

        v = str(value).strip().lower()
    
        if not v:
            return False

        return v in ("ukjent", "unknown", "?", "-")




    def open_location_window(self):
        if hasattr(self, "location_window") and self.location_window and self.location_window.winfo_exists():
            self.location_window.focus_force()
            self.location_window.focus_set()
            self.location_window.lift()
            return

        win = tk.Toplevel(self.root)
        self.location_window = win
        win.title("Edit Location")
        win.resizable(False, False)
        win.transient(self.root)

        import utils
        utils.center_and_fit_toplevel(win, sc(380), sc(340))

        frame = ttk.Frame(win, padding=15)
        frame.pack(fill="both", expand=True)

        # Header Title
        tk.Label(
            frame,
            text="EDIT LOCATION",
            font=("Segoe UI", sc(11), "bold"),
            fg="#1a1c1c"
        ).pack(anchor="w", pady=(0, 15))

        # Input Grid container
        grid_frame = ttk.Frame(frame)
        grid_frame.pack(fill="both", expand=True)

        self.location_entries = []

        # Render each location field dynamically
        for row, field in enumerate(self.app.config["ui_sections"]["location"]):
            name = field["name"]
            ftype = field.get("type", "text")
            var = self.location_vars.get(name)
            
            # Label
            lbl = ttk.Label(grid_frame, text=name, font=("Segoe UI", sc(9.5), "bold"))
            lbl.grid(row=row, column=0, sticky="w", padx=(0, 10), pady=6)

            # Input widget
            if ftype == "choice":
                choices = field.get("choices", [])
                if "" not in choices:
                    choices = [""] + choices
                widget = ttk.Combobox(
                    grid_frame, textvariable=var,
                    values=choices,
                    state="readonly" if name != "Stored as" else "normal"
                )
            elif ftype == "checkbox":
                widget = ttk.Checkbutton(
                    grid_frame, text="", variable=var,
                    onvalue="True", offvalue="False",
                    command=lambda n=name, v=var: self._on_checkbox_change(n, v)
                )
            else:
                widget = ttk.Entry(
                    grid_frame, textvariable=var,
                    state="disabled" if field.get("readonly") else "normal"
                )

            widget.grid(row=row, column=1, sticky="ew", pady=6)
            self.location_entries.append(widget)

            # Keyboard navigation bindings for entries inside pop-up
            widget.bind("<Shift-Up>", self._location_nav_up)
            widget.bind("<Shift-Down>", self._location_nav_down)
            widget.bind("<Control-Up>", self._location_nav_up)
            widget.bind("<Control-Down>", self._location_nav_down)
            widget.bind("<Return>", self._location_nav_down)

        grid_frame.columnconfigure(1, weight=1)

        # Footer actions
        footer = ttk.Frame(frame)
        footer.pack(fill="x", side="bottom", pady=(15, 0))

        def save_and_close():
            self.commit_current_object()
            win.destroy()

        # DONE Button (Primary)
        done_btn = tk.Button(
            footer, text="DONE",
            bg="#1a1c1c", fg="#ffffff",
            font=("Segoe UI", sc(9.5), "bold"),
            relief="flat", bd=0, cursor="hand2",
            padx=16, pady=6,
            command=save_and_close
        )
        done_btn.pack(side="right")
        done_btn.bind("<Enter>", lambda e: done_btn.config(bg="#333333"))
        done_btn.bind("<Leave>", lambda e: done_btn.config(bg="#1a1c1c"))

        # CANCEL Button (Secondary outline style)
        cancel_btn = tk.Button(
            footer, text="CANCEL",
            bg=win.cget("bg"), fg="#1a1c1c",
            font=("Segoe UI", sc(9.5), "bold"),
            relief="flat", bd=0, cursor="hand2",
            padx=12, pady=5,
            highlightthickness=1,
            highlightbackground="#747878",
            highlightcolor="#747878",
            command=win.destroy
        )
        cancel_btn.pack(side="right", padx=(0, 10))
        cancel_btn.bind("<Enter>", lambda e: cancel_btn.config(bg="#e2e2e2"))
        cancel_btn.bind("<Leave>", lambda e: cancel_btn.config(bg=win.cget("bg")))

        # Esc binding to close
        win.bind("<Escape>", lambda e: win.destroy())
        
        # When closing, clear self.location_entries to prevent navigation bugs
        win.bind("<Destroy>", lambda e: self.location_entries.clear() if e.widget == win else None)

    def update_location_summary_view(self):
        pass

    def update_problems_default_view(self):
        """Rebuilds the read-only list of active problem flags in the default window."""
        if not hasattr(self, "problem_frame") or not self.problem_frame.winfo_exists():
            return
        
        # Clear existing children of problem_frame
        for w in self.problem_frame.winfo_children():
            w.destroy()
            
        s = getattr(self, "_scale", 1.0)
        
        # Find all active problems
        active_problems = []
        for field in self.app.config["ui_sections"]["problems"]:
            name = field["name"]
            if name == "Images_Missing":
                continue
            var = self.problem_vars.get(name)
            if var and var.get():
                active_problems.append(name)
                
        # Also check if images are missing (from images_missing_var status)
        # (Images_Missing is excluded from active_problems to not count as a metadata problem or show in the list/title count)

        # Update title problem count label dynamically
        if hasattr(self, "title_problem_count_label") and self.title_problem_count_label is not None:
            try:
                if self.title_problem_count_label.winfo_exists():
                    count = len(active_problems)
                    if count > 0:
                        self.title_problem_count_label.config(text=f"({count} problems)")
                    else:
                        self.title_problem_count_label.config(text="")
            except Exception:
                pass

        if not active_problems:
            row_frame = ttk.Frame(self.problem_frame)
            row_frame.pack(fill="x", pady=4, padx=6)
            
            lbl_icon = tk.Label(
                row_frame, text="✔", fg="#3b6934", bg=self.root.cget("bg"),
                font=("Segoe UI", sc(11), "bold")
            )
            lbl_icon.pack(side="left", padx=(0, 6))
            
            lbl_text = ttk.Label(
                row_frame, text="No active problems flagged.",
                foreground="#3b6934",
                font=("Segoe UI", sc(9.5), "bold")
            )
            lbl_text.pack(side="left")
        else:
            for prob_name in active_problems:
                row_frame = ttk.Frame(self.problem_frame)
                row_frame.pack(fill="x", pady=2, padx=4)
                
                lbl_icon = tk.Label(
                    row_frame, text="⚠", fg="#ba1a1a", bg=self.root.cget("bg"),
                    font=("Segoe UI", sc(10), "bold")
                )
                lbl_icon.pack(side="left", padx=(0, 6))
                
                lbl_text = ttk.Label(
                    row_frame, text=prob_name.replace("_", " "),
                    foreground="#ba1a1a",
                    font=("Segoe UI", sc(9.5), "bold")
                )
                lbl_text.pack(side="left")

        # Update tab headers with problem count
        if hasattr(self, "reg_notebook") and hasattr(self, "_reg_tabs") and self.reg_notebook.winfo_exists():
            active_problems_set = set()
            for name, var in self.problem_vars.items():
                if var.get():
                    active_problems_set.add(name)
            
            for g_name, tab_info in self._reg_tabs.items():
                tab_container = tab_info["container"]
                count = 0
                if g_name == "Problems":
                    mapped_problems = set(self.problem_to_field.keys())
                    unmapped_problems = [p for p in self.problem_columns if p not in mapped_problems]
                    count = sum(1 for p in unmapped_problems if p in active_problems_set)
                else:
                    g_fields = tab_info["fields"]
                    for f in g_fields:
                        for prob_col, mapped_field in self.problem_to_field.items():
                            if mapped_field == f and prob_col in active_problems_set:
                                count += 1
                
                tab_text = f"{g_name} ({count})" if count > 0 else g_name
                self.reg_notebook.tab(tab_container, text=tab_text)

    def open_problems_window(self, event=None):
        if hasattr(self, "problems_window") and self.problems_window and self.problems_window.winfo_exists():
            self.problems_window.focus_force()
            self.problems_window.focus_set()
            self.problems_window.lift()
            return

        win = tk.Toplevel(self.root)
        self.problems_window = win
        win.title("Edit Problem Flags")
        win.resizable(False, False)
        win.transient(self.root)

        import utils
        utils.center_and_fit_toplevel(win, sc(400), sc(350))

        frame = ttk.Frame(win, padding=15)
        frame.pack(fill="both", expand=True)

        # Header
        header_frame = ttk.Frame(frame)
        header_frame.pack(fill="x", pady=(0, 15))

        tk.Label(
            header_frame,
            text="⚠ EDIT PROBLEM FLAGS",
            font=("Segoe UI", sc(11), "bold"),
            fg="#ba1a1a"
        ).pack(side="left")

        # Checkbutton Grid container
        grid_frame = ttk.Frame(frame)
        grid_frame.pack(fill="both", expand=True)

        self.problem_checkbuttons = []

        # Re-create checkbuttons in the popup sharing the same BooleanVars
        for i, field in enumerate(self.app.config["ui_sections"]["problems"]):
            name = field["name"]
            var = self.problem_vars.get(name)
            if not var:
                var = tk.BooleanVar()
                self.problem_vars[name] = var

            row = i // 2
            col = i % 2

            cb = ttk.Checkbutton(
                grid_frame,
                text=name.replace("_", " "),
                variable=var,
                command=lambda: self.update_reg_fields_visibility(skip_snap=True)
            )
            cb.grid(row=row, column=col, sticky="w", padx=10, pady=8)
            self.problem_checkbuttons.append(cb)

            cb.bind("<Shift-Up>", self._problem_nav_up)
            cb.bind("<Shift-Down>", self._problem_nav_down)
            cb.bind("<Control-Up>", self._problem_nav_up)
            cb.bind("<Control-Down>", self._problem_nav_down)
            cb.bind("<Return>", lambda e, c=cb: self._toggle_specific_checkbox(c))

        grid_frame.columnconfigure(0, weight=1)
        grid_frame.columnconfigure(1, weight=1)

        # Separator line before image status
        ttk.Separator(frame, orient="horizontal").pack(fill="x", pady=(10, 6))

        # Images missing label using the existing textvariable
        lbl = ttk.Label(
            frame,
            textvariable=self.images_missing_var,
            foreground="#ba1a1a",
            font=("Segoe UI", sc(9.5), "bold")
        )
        lbl.pack(anchor="w", pady=(0, 10))

        # Footer actions
        footer = ttk.Frame(frame)
        footer.pack(fill="x", side="bottom")

        def save_and_close():
            self.commit_current_object()
            win.destroy()

        # DONE Button (Primary)
        done_btn = tk.Button(
            footer, text="DONE",
            bg="#1a1c1c", fg="#ffffff",
            font=("Segoe UI", sc(9.5), "bold"),
            relief="flat", bd=0, cursor="hand2",
            padx=16, pady=6,
            command=save_and_close
        )
        done_btn.pack(side="right")
        done_btn.bind("<Enter>", lambda e: done_btn.config(bg="#333333"))
        done_btn.bind("<Leave>", lambda e: done_btn.config(bg="#1a1c1c"))

        # CANCEL Button (Secondary outline)
        cancel_btn = tk.Button(
            footer, text="CANCEL",
            bg=win.cget("bg"), fg="#1a1c1c",
            font=("Segoe UI", sc(9.5), "bold"),
            relief="flat", bd=0, cursor="hand2",
            padx=12, pady=5,
            highlightthickness=1,
            highlightbackground="#747878",
            highlightcolor="#747878",
            command=win.destroy
        )
        cancel_btn.pack(side="right", padx=(0, 10))
        cancel_btn.bind("<Enter>", lambda e: cancel_btn.config(bg="#e2e2e2"))
        cancel_btn.bind("<Leave>", lambda e: cancel_btn.config(bg=win.cget("bg")))

        win.bind("<Escape>", lambda e: win.destroy())
        
        # When closing, clear self.problem_checkbuttons to prevent navigation bugs
        win.bind("<Destroy>", lambda e: self.problem_checkbuttons.clear() if e.widget == win else None)

    # ---------- Filter ----------
    def open_filter_menu(self):
        if hasattr(self, "filter_window") and self.filter_window and self.filter_window.winfo_exists():
            self.filter_window.lift()
            self.filter_window.focus_force()
            return

        from config import sc
        import utils
        
        COLORS = {
            "surface": "#f9f9f9",
            "surface_dim": "#dadada",
            "surface_container_low": "#f3f3f3",
            "surface_container_highest": "#e2e2e2",
            "on_surface": "#1a1c1c",
            "on_surface_variant": "#444748",
            "outline": "#747878",
            "outline_variant": "#c4c7c7",
            "primary": "#000000",
            "on_primary": "#ffffff",
            "secondary": "#3b6934",
            "error": "#ba1a1a",
            "botanical_green": "#3e7b3e",
            "search_orange": "#d9480f",
            "surface_tint": "#5f5e5e"
        }
        
        FONT_HEADLINE = ("Hanken Grotesk", sc(14), "bold")
        FONT_LABEL = ("JetBrains Mono", sc(10), "bold")
        FONT_DATA = ("JetBrains Mono", sc(11))
        
        win = tk.Toplevel(self.root)
        self.filter_window = win
        win.title("Filter objects")
        win.geometry(f"{sc(800)}x{sc(600)}")
        win.configure(bg=COLORS["surface"])
        win.bind("<Destroy>", lambda e: setattr(self, "filter_window", None) if e.widget == win else None)
        win.bind("<Escape>", lambda e: win.destroy())
        win.bind("<Control-Return>", lambda e: self.apply_filter(win))

        main_container = tk.Frame(win, bg=COLORS["surface"], bd=0, highlightthickness=0)
        main_container.pack(fill="both", expand=True)

        header = tk.Frame(main_container, bg=COLORS["surface_container_low"], height=sc(56))
        header.pack(fill="x", side="top")
        header.pack_propagate(False)
        tk.Frame(header, bg=COLORS["outline"], height=1).pack(fill="x", side="bottom")

        left_header = tk.Frame(header, bg=COLORS["surface_container_low"])
        left_header.pack(side="left", fill="y", padx=sc(16))
        
        tk.Label(left_header, text="Filter objects", font=FONT_HEADLINE, fg=COLORS["primary"], bg=COLORS["surface_container_low"]).pack(side="left")
        
        search_frame = tk.Frame(left_header, bg=COLORS["surface"], highlightbackground=COLORS["search_orange"], highlightthickness=1)
        search_frame.pack(side="left", padx=sc(24), pady=sc(12), fill="y")
        tk.Label(search_frame, text="⌕", font=("Segoe UI", sc(12)), fg=COLORS["search_orange"], bg=COLORS["surface"]).pack(side="left", padx=(sc(8), 0))
        search_var = tk.StringVar()
        search_entry = tk.Entry(search_frame, textvariable=search_var, font=FONT_DATA, fg=COLORS["search_orange"], bg=COLORS["surface"], bd=0, insertbackground=COLORS["search_orange"], width=20)
        search_entry.pack(side="left", fill="both", expand=True, padx=sc(8), pady=sc(4))
        
        right_header = tk.Frame(header, bg=COLORS["surface_container_low"])
        right_header.pack(side="right", fill="y", padx=sc(16))
        
        def make_btn(parent, text, cmd):
            btn = tk.Button(parent, text=text, font=FONT_LABEL, fg=COLORS["on_surface"], bg=COLORS["surface"], bd=1, relief="solid", padx=sc(12), pady=sc(4), cursor="hand2", command=cmd)
            btn.pack(side="left", padx=sc(4), pady=sc(12))
            return btn
            
        make_btn(right_header, "Load Preset...", self.load_filter_preset)
        make_btn(right_header, "Save Preset...", self.save_filter_preset)

        tab_nav = tk.Frame(main_container, bg=COLORS["surface_container_highest"], height=sc(40))
        tab_nav.pack(fill="x", side="top")
        tk.Frame(tab_nav, bg=COLORS["outline"], height=1).pack(fill="x", side="bottom")

        tab_content_area = tk.Frame(main_container, bg=COLORS["surface"])
        tab_content_area.pack(fill="both", expand=True)

        self.filter_tabs = {}
        self.filter_tab_buttons = {}
        
        def show_tab(tab_name):
            for name, frame in self.filter_tabs.items():
                frame.pack_forget()
            self.filter_tabs[tab_name].pack(fill="both", expand=True)
            
            for name, btn_tuple in self.filter_tab_buttons.items():
                btn, border = btn_tuple
                if name == tab_name:
                    btn.config(fg=COLORS["primary"], bg=COLORS["surface"])
                    border.config(bg=COLORS["primary"])
                else:
                    btn.config(fg=COLORS["on_surface_variant"], bg=COLORS["surface_container_highest"])
                    border.config(bg=COLORS["outline"])
                    
        def create_tab_btn(name, label):
            btn_frame = tk.Frame(tab_nav, bg=COLORS["surface_container_highest"])
            btn_frame.pack(side="left", fill="y")
            
            tk.Frame(btn_frame, bg=COLORS["outline"], width=1).pack(side="right", fill="y")
            bottom_border = tk.Frame(btn_frame, bg=COLORS["outline"], height=2)
            bottom_border.pack(side="bottom", fill="x")
            
            btn = tk.Button(btn_frame, text=label, font=FONT_LABEL, fg=COLORS["on_surface_variant"], bg=COLORS["surface_container_highest"], bd=0, relief="flat", padx=sc(16), cursor="hand2", command=lambda n=name: show_tab(n))
            btn.pack(side="top", fill="both", expand=True)
            self.filter_tab_buttons[name] = (btn, bottom_border)
            
        create_tab_btn("status", "Status & General")
        create_tab_btn("problems", "Problems & Unknowns")
        create_tab_btn("images", "Images")
        create_tab_btn("location", "Location")

        all_widgets = []

        def create_group(parent, title):
            group = tk.Frame(parent, bg=COLORS["surface"], highlightbackground=COLORS["outline"], highlightthickness=1)
            group.pack(fill="x", pady=(0, sc(16)))
            tk.Label(group, text=title.upper(), font=FONT_LABEL, fg=COLORS["on_surface_variant"], bg=COLORS["surface"]).pack(anchor="w", padx=sc(12), pady=(sc(12), sc(8)))
            content = tk.Frame(group, bg=COLORS["surface"])
            content.pack(fill="x", padx=sc(12), pady=(0, sc(12)))
            return content

        def make_chk(parent, text, var, color_bar=None):
            f = tk.Frame(parent, bg=COLORS["surface"])
            f.pack(fill="x", pady=sc(2))
            chk = tk.Checkbutton(f, variable=var, bg=COLORS["surface"], activebackground=COLORS["surface"], bd=0, highlightthickness=0, command=self.update_filter_button_text)
            chk.pack(side="left")
            if color_bar:
                tk.Frame(f, bg=color_bar, width=4, height=sc(12)).pack(side="left", padx=(sc(4), sc(8)))
            lbl = tk.Label(f, text=text, font=FONT_DATA, fg=COLORS["on_surface"], bg=COLORS["surface"])
            lbl.pack(side="left", padx=(0, sc(8)))
            all_widgets.append((text.lower(), f, COLORS["surface"]))
            return chk
            
        def make_rad(parent, text, var, val):
            f = tk.Frame(parent, bg=COLORS["surface"])
            f.pack(fill="x", pady=sc(2))
            rad = tk.Radiobutton(f, variable=var, value=val, bg=COLORS["surface"], activebackground=COLORS["surface"], bd=0, highlightthickness=0)
            rad.pack(side="left")
            lbl = tk.Label(f, text=text, font=FONT_DATA, fg=COLORS["on_surface"], bg=COLORS["surface"])
            lbl.pack(side="left", padx=sc(8))
            all_widgets.append((text.lower(), f, COLORS["surface"]))
            return rad

        # TAB 1: STATUS
        tab_status = tk.Frame(tab_content_area, bg=COLORS["surface"])
        self.filter_tabs["status"] = tab_status
        
        status_left = tk.Frame(tab_status, bg=COLORS["surface"])
        status_left.pack(side="left", fill="both", expand=True, padx=sc(16), pady=sc(16))
        status_right = tk.Frame(tab_status, bg=COLORS["surface"])
        status_right.pack(side="right", fill="both", expand=True, padx=sc(16), pady=sc(16))
        
        c_logic = create_group(status_left, "Condition Logic")
        make_rad(c_logic, "Match ALL conditions (AND)", self.filter_modes["Status"], "AND")
        make_rad(c_logic, "Match ANY condition (OR)", self.filter_modes["Status"], "OR")

        p_status = create_group(status_left, "Processing Status")
        make_chk(p_status, "Reviewed", self.filter_vars["Reviewed"], COLORS["secondary"])
        make_chk(p_status, "Not Reviewed (Pending)", self.filter_vars["Not_Reviewed"], COLORS["surface_tint"])
        make_chk(p_status, "Reviewed + Has Problem", self.filter_vars["Reviewed_With_Problem"], COLORS["error"])
        make_chk(p_status, "Problem + Has History", self.filter_vars["Problem_With_History"], COLORS["error"])
        make_chk(p_status, "Has earlier database entry", self.filter_vars["Has_History"], COLORS["outline_variant"])

        m_pres = create_group(status_right, "Metadata Presence")
        tk.Label(m_pres, text="Comments", font=FONT_LABEL, fg=COLORS["on_surface_variant"], bg=COLORS["surface"]).pack(anchor="w")
        tk.Frame(m_pres, bg=COLORS["outline"], height=1).pack(fill="x", pady=sc(4))
        make_chk(m_pres, "Missing Comment", self.filter_vars["Comment_Empty"])
        make_chk(m_pres, "Has Comment", self.filter_vars["Comment_Not_Empty"])
        
        tk.Label(m_pres, text="Location Notes", font=FONT_LABEL, fg=COLORS["on_surface_variant"], bg=COLORS["surface"]).pack(anchor="w", pady=(sc(12), 0))
        tk.Frame(m_pres, bg=COLORS["outline"], height=1).pack(fill="x", pady=sc(4))
        make_chk(m_pres, "No Location Comment", self.filter_vars["Extra_Empty"])
        make_chk(m_pres, "Has Location Comment", self.filter_vars["Extra_Not_Empty"])

        # TAB 2: PROBLEMS
        tab_probs = tk.Frame(tab_content_area, bg=COLORS["surface"])
        self.filter_tabs["problems"] = tab_probs
        
        probs_canvas = tk.Canvas(tab_probs, bg=COLORS["surface"], highlightthickness=0, bd=0)
        probs_scrollbar = tk.Scrollbar(tab_probs, orient="vertical", command=probs_canvas.yview)
        probs_inner = tk.Frame(probs_canvas, bg=COLORS["surface"])
        
        probs_inner.bind("<Configure>", lambda e: probs_canvas.configure(scrollregion=probs_canvas.bbox("all")))
        probs_canvas_window = probs_canvas.create_window((0, 0), window=probs_inner, anchor="nw")
        probs_canvas.bind("<Configure>", lambda e: probs_canvas.itemconfig(probs_canvas_window, width=e.width))
        probs_canvas.configure(yscrollcommand=probs_scrollbar.set)
        
        probs_canvas.pack(side="left", fill="both", expand=True, padx=(sc(16), 0), pady=sc(16))
        probs_scrollbar.pack(side="right", fill="y", pady=sc(16))
        
        def _on_prob_scroll(event):
            probs_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        self.root.after(100, lambda: self._bind_mousewheel_recursive(win, _on_prob_scroll))

        p_list = create_group(probs_inner, "Problems Checklist")
        normal_problems = [p for p in self.problem_columns if "Image" not in p]
        for col in normal_problems:
            make_chk(p_list, col.replace("_", " "), self.filter_vars.get(col), COLORS["error"])
        make_chk(p_list, "Any problem (except images)", self.filter_vars.get("Any_Problem"), COLORS["error"])
        
        p_mode = create_group(probs_inner, "Problems Match Mode")
        make_rad(p_mode, "Match ALL (AND)", self.filter_modes["Problems"], "AND")
        make_rad(p_mode, "Match ANY (OR)", self.filter_modes["Problems"], "OR")
        
        u_list = create_group(probs_inner, "Unknown values")
        if not hasattr(self, "filter_unknown_var"):
            self.filter_unknown_var = tk.BooleanVar()
        make_chk(u_list, "Show objects with unknown fields", self.filter_unknown_var)
        make_rad(u_list, "Match ALL (AND)", self.filter_modes["Unknown"], "AND")
        make_rad(u_list, "Match ANY (OR)", self.filter_modes["Unknown"], "OR")

        # TAB 3: IMAGES
        tab_imgs = tk.Frame(tab_content_area, bg=COLORS["surface"])
        self.filter_tabs["images"] = tab_imgs
        
        img_inner = tk.Frame(tab_imgs, bg=COLORS["surface"])
        img_inner.pack(fill="both", expand=True, padx=sc(16), pady=sc(16))
        
        i_list = create_group(img_inner, "Images Checklist")
        image_filters = ["Images_Missing", "Has_Images"]
        image_problems = [p for p in self.problem_columns if "Image" in p]
        for col in image_filters + image_problems:
            if col in self.filter_vars:
                clean_name = col.replace("_", " ")
                bar_color = COLORS["error"] if "Missing" in col or "Problem" in col else COLORS["botanical_green"]
                make_chk(i_list, clean_name, self.filter_vars[col], bar_color)
                
        i_mode = create_group(img_inner, "Images Match Mode")
        make_rad(i_mode, "Match ALL (AND)", self.filter_modes["Images"], "AND")
        make_rad(i_mode, "Match ANY (OR)", self.filter_modes["Images"], "OR")

        # TAB 4: LOCATION
        tab_loc = tk.Frame(tab_content_area, bg=COLORS["surface"])
        self.filter_tabs["location"] = tab_loc
        
        loc_canvas = tk.Canvas(tab_loc, bg=COLORS["surface"], highlightthickness=0, bd=0)
        loc_scrollbar = tk.Scrollbar(tab_loc, orient="vertical", command=loc_canvas.yview)
        loc_inner = tk.Frame(loc_canvas, bg=COLORS["surface"])
        
        loc_inner.bind("<Configure>", lambda e: loc_canvas.configure(scrollregion=loc_canvas.bbox("all")))
        loc_canvas_window = loc_canvas.create_window((0, 0), window=loc_inner, anchor="nw")
        loc_canvas.bind("<Configure>", lambda e: loc_canvas.itemconfig(loc_canvas_window, width=e.width))
        loc_canvas.configure(yscrollcommand=loc_scrollbar.set)
        
        loc_canvas.pack(side="left", fill="both", expand=True, padx=(sc(16), 0), pady=sc(16))
        loc_scrollbar.pack(side="right", fill="y", pady=sc(16))
        
        l_group = create_group(loc_inner, "Location Fields")
        loc_fields = self.app.config.get("ui_sections", {}).get("location", [])
        
        from tkinter import ttk
        style = ttk.Style(self.root)
        style.configure("Flat.TCombobox", fieldbackground=COLORS["surface"], background=COLORS["surface"], borderwidth=0)
        
        for field in loc_fields:
            name = field["name"]
            ftype = field.get("type", "text")
            if name not in self.filter_location_vars:
                self.filter_location_vars[name] = tk.StringVar()
                
            f = tk.Frame(l_group, bg=COLORS["surface"])
            f.pack(fill="x", pady=sc(4))
            tk.Label(f, text=name, font=FONT_LABEL, fg=COLORS["on_surface"], bg=COLORS["surface"], width=20, anchor="w").pack(side="left", padx=sc(8))
            
            ent_frame = tk.Frame(f, bg=COLORS["surface"], highlightbackground=COLORS["outline"], highlightthickness=1)
            ent_frame.pack(side="left", fill="x", expand=True, padx=(0, sc(8)))
            
            if ftype in ("choice", "checkbox"):
                vals = [""] + list(field.get("choices", [])) if ftype == "choice" else ["", "True", "False"]
                cb = ttk.Combobox(ent_frame, textvariable=self.filter_location_vars[name], values=vals, state="readonly", style="Flat.TCombobox")
                cb.pack(fill="x", expand=True, padx=sc(2), pady=sc(2))
                cb.bind("<BackSpace>", lambda e, w=cb: (w.set(""), self.update_filter_button_text()))
                cb.bind("<Delete>", lambda e, w=cb: (w.set(""), self.update_filter_button_text()))
            else:
                ent = tk.Entry(ent_frame, textvariable=self.filter_location_vars[name], font=FONT_DATA, bg=COLORS["surface"], fg=COLORS["on_surface"], bd=0, insertbackground=COLORS["primary"])
                ent.pack(fill="x", expand=True, padx=sc(4), pady=sc(2))
                
            all_widgets.append((name.lower(), f, COLORS["surface"]))

        # Quick Search
        def on_search(*args):
            q = search_var.get().lower().strip()
            for text, frame, orig_bg in all_widgets:
                if not q:
                    frame.config(bg=orig_bg)
                    for child in frame.winfo_children():
                        if isinstance(child, tk.Frame) and child.cget("width") == 4: continue
                        try: child.config(bg=orig_bg)
                        except: pass
                elif q in text:
                    frame.config(bg=COLORS["surface_container_highest"])
                    for child in frame.winfo_children():
                        if isinstance(child, tk.Frame) and child.cget("width") == 4: continue
                        try: child.config(bg=COLORS["surface_container_highest"])
                        except: pass
                else:
                    frame.config(bg=orig_bg)
                    for child in frame.winfo_children():
                        if isinstance(child, tk.Frame) and child.cget("width") == 4: continue
                        try: child.config(bg=orig_bg)
                        except: pass
                        
        search_var.trace("w", on_search)

        show_tab("status")

        # FOOTER ACTION BAR
        footer = tk.Frame(main_container, bg=COLORS["surface_container_low"], height=sc(56))
        footer.pack(fill="x", side="bottom")
        footer.pack_propagate(False)
        tk.Frame(footer, bg=COLORS["outline"], height=1).pack(fill="x", side="top")

        tk.Button(footer, text="Reset All", font=FONT_LABEL, fg=COLORS["error"], bg=COLORS["surface_container_low"], bd=0, relief="flat", cursor="hand2", command=lambda: self.clear_filter(win)).pack(side="left", padx=sc(16), pady=sc(12))

        right_footer = tk.Frame(footer, bg=COLORS["surface_container_low"])
        right_footer.pack(side="right", fill="y", padx=sc(16))

        tk.Button(right_footer, text="Cancel", font=FONT_LABEL, fg=COLORS["on_surface"], bg=COLORS["surface"], bd=1, relief="solid", padx=sc(16), pady=sc(4), cursor="hand2", command=win.destroy).pack(side="left", padx=sc(8), pady=sc(12))
        
        apply_btn = tk.Button(right_footer, text="Apply Filter  |  Ctrl+Enter", font=FONT_LABEL, fg=COLORS["on_primary"], bg=COLORS["botanical_green"], bd=0, relief="flat", padx=sc(16), pady=sc(4), cursor="hand2", command=lambda: self.apply_filter(win))
        apply_btn.pack(side="left", pady=sc(12))

        # Focus handling for keyboard
        all_inputs = []
        for tab_name, frame in self.filter_tabs.items():
            for group in frame.winfo_children():
                if isinstance(group, tk.Frame) and group.cget("highlightbackground") == COLORS["outline"]:
                    content = group.winfo_children()[-1]
                    for item_frame in content.winfo_children():
                        for child in item_frame.winfo_children():
                            if isinstance(child, (tk.Checkbutton, tk.Radiobutton, tk.Entry, ttk.Combobox)):
                                all_inputs.append(child)
        self._filter_widgets = all_inputs
        self._filter_index = 0
        
        utils.center_and_fit_toplevel(win, sc(800), sc(600))

    def save_filter_preset(self):
        from tkinter import simpledialog
        name = simpledialog.askstring("Save Preset", "Enter preset name:", parent=self.filter_window)
        if name:
            import json, os
            preset = {
                "vars": {k: v.get() for k, v in self.filter_vars.items() if isinstance(v, tk.BooleanVar) and v.get()},
                "locs": {k: v.get() for k, v in self.filter_location_vars.items() if v.get()},
                "modes": {k: v.get() for k, v in self.filter_modes.items()}
            }
            presets_file = os.path.join(os.path.dirname(_PREFS_PATH), "filter_presets.json")
            try:
                if os.path.exists(presets_file):
                    with open(presets_file, "r", encoding="utf-8") as f:
                        data = json.load(f)
                else:
                    data = {}
                data[name] = preset
                with open(presets_file, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=2)
                self.show_banner(f"Saved preset '{name}'", "success")
            except Exception as e:
                self.show_banner(f"Failed to save preset: {e}", "error")

    def load_filter_preset(self):
        import json, os
        presets_file = os.path.join(os.path.dirname(_PREFS_PATH), "filter_presets.json")
        if not os.path.exists(presets_file):
            self.show_banner("No presets saved yet.", "info")
            return
            
        with open(presets_file, "r", encoding="utf-8") as f:
            data = json.load(f)
            
        if not data:
            return
            
        win = tk.Toplevel(self.filter_window)
        win.title("Load Preset")
        import utils
        utils.center_and_fit_toplevel(win, 250, 300)
        
        lb = tk.Listbox(win)
        lb.pack(fill="both", expand=True, padx=10, pady=10)
        for k in data.keys():
            lb.insert("end", k)
            
        def on_load():
            sel = lb.curselection()
            if not sel: return
            name = lb.get(sel[0])
            preset = data[name]
            
            # Clear current
            self.clear_filter(self.filter_window, destroy_win=False)
            
            # Apply preset
            for k, v in preset.get("vars", {}).items():
                if k in self.filter_vars:
                    self.filter_vars[k].set(v)
            for k, v in preset.get("locs", {}).items():
                if k in self.filter_location_vars:
                    self.filter_location_vars[k].set(v)
            for k, v in preset.get("modes", {}).items():
                if k in self.filter_modes:
                    self.filter_modes[k].set(v)
                    
            self.update_filter_button_text()
            win.destroy()
            
        ttk.Button(win, text="Load", command=on_load).pack(pady=10)

    def _filter_nav_down(self, event):
        if not hasattr(self, "_filter_widgets"):
            return

        total = len(self._filter_widgets)
        if total == 0:
            return

        self._filter_index = (self._filter_index + 1) % total
        self._filter_widgets[self._filter_index].focus_set()

        return "break"


    def _filter_nav_up(self, event):
        if not hasattr(self, "_filter_widgets"):
            return

        total = len(self._filter_widgets)
        if total == 0:
            return

        self._filter_index = (self._filter_index - 1) % total
        self._filter_widgets[self._filter_index].focus_set()

        return "break"


    def _filter_activate(self, event):
        widget = self.root.focus_get()

        try:
            widget.invoke()  
        except Exception as e:
            debug_error("Suppressed Error", str(e))
            pass

        return "break"

#----------

    def is_problem_active(self, oid, prob_col):

        if prob_col == "Other_problem":
            return bool(self.app.df_obs.loc[oid, prob_col])

      
        if prob_col == "Reviewed":
            return bool(self.app.df_obs.loc[oid, REVIEWED_COLUMN])

        if oid not in self.obs_by_id.index:
            return False

        if prob_col == "Has_Images":
            return not self.app.df_obs.loc[oid, "Images_Missing"]

        if prob_col == "Images_Missing":
            if self.image_mode in ("online", "offline"):
                return False
            return self.app.df_obs.loc[oid, "Images_Missing"]

      
        obs = self.obs_by_id.loc[oid]
        if isinstance(obs, pd.DataFrame):
            obs = obs.iloc[0]

        reg = self.reg_by_id.loc[oid]
        if isinstance(reg, pd.DataFrame):
            reg = reg.iloc[0]

      
        value = obs.get(prob_col, False)
        if isinstance(value, pd.Series):
            value = value.iloc[0]

        obs_val = bool(value)

      
        auto_val = False

   
        if prob_col in self.problem_to_field:
            field = self.problem_to_field.get(prob_col)
            if not field:
                return obs_val

            raw_val = reg.get(field, "")
            if isinstance(raw_val, pd.Series):
                raw_val = raw_val.iloc[0]




           
            is_missing = (
                pd.isna(raw_val) or
                (isinstance(raw_val, str) and raw_val.strip() == "")
            )

            is_unknown = self.is_unknown(raw_val)

            auto_val = is_missing and not is_unknown

        return obs_val or auto_val


#-------

    def build_filter_state(self):
        return {
            "problems": [c for c, v in self.filter_vars.items() if v.get()],
            "unknown": self.filter_unknown_var.get(),
            "mode": self.filter_mode.get(),
        }

#----

    def apply_filter(self, win):

        not_reviewed_only = getattr(self, "_filter_not_reviewed_only", False)
        self._filter_not_reviewed_only = False  # reset etter bruk

        filter_state = {
            "problems": [c for c, v in self.filter_vars.items() if v.get()],
            "unknown": self.filter_unknown_var.get(),
            "mode": self.filter_mode.get(),
        }

        groups = {
            "Problems": [],
            "Images": [],
            "Status": [],
            "Text": [],
            "Unknown": []
        }

       
        for key, var in self.filter_vars.items():
            if not var.get():
                continue

            if key in self.problem_columns:
                groups["Problems"].append(key)

            elif key in ["Images_Missing", "Has_Images"]:
                groups["Images"].append(key)

            elif key in ["Reviewed", "Not_Reviewed",
                         "Reviewed_With_Problem", "Problem_With_History", "Has_History"]:
                groups["Status"].append(key)

            elif key in ["Comment_Empty", "Comment_Not_Empty", "Extra_Empty", "Extra_Not_Empty"]:
                groups["Text"].append(key)

        if filter_state["unknown"]:
            groups["Unknown"].append("Unknown")


        win.destroy()

        # PERFORMANCE OPTIMIZATION (Bolt): Converting DataFrames to dictionary structures once
        # allows O(1) dictionary lookup, bypassing Pandas Series creation and .loc index overhead entirely,
        # making the bulk filtering loop ~15-40x faster.
        reg_dict = self._get_reg_dict()
        obs_dict = self._get_obs_dict()

        # Pre-populate a set of IDs that exist in historical databases to make fast_has_history O(1) set lookup
        history_set = set()
        if self.app.historical_dbs:
            for db in self.app.historical_dbs:
                reg_by_id = db.get("reg_by_id")
                if reg_by_id is not None:
                    history_set.update(reg_by_id.index)

        def fast_has_history(oid):
            return oid in history_set

        def fast_is_problem_active(oid, prob_col):
            obs_row = obs_dict.get(oid, {})
            reg_row = reg_dict.get(oid, {})

            if prob_col == "Other_problem":
                return bool(obs_row.get(prob_col, False))

            if prob_col == "Reviewed":
                return bool(obs_row.get(REVIEWED_COLUMN, False))

            if oid not in obs_dict:
                return False

            if prob_col == "Has_Images":
                return not obs_row.get("Images_Missing", False)

            if prob_col == "Images_Missing":
                if self.image_mode in ("online", "offline"):
                    return False
                return obs_row.get("Images_Missing", False)

            obs_val = bool(obs_row.get(prob_col, False))

            auto_val = False

            if prob_col in self.problem_to_field:
                field = self.problem_to_field.get(prob_col)
                if not field:
                    return obs_val

                raw_val = reg_row.get(field, "")

                is_missing = (
                    pd.isna(raw_val) or
                    (isinstance(raw_val, str) and raw_val.strip() == "")
                )

                is_unknown = self.is_unknown(raw_val)

                auto_val = is_missing and not is_unknown

            return obs_val or auto_val

        def fast_has_any_problem(oid, include_image_problems=True):
            for p in self.problem_columns:
                if p == "Images_Missing":
                    continue
                if not include_image_problems:
                    if "Image" in p:
                        continue
                if fast_is_problem_active(oid, p):
                    return True
            return False

        fast_problem_cache = {}
        def fast_get_cached_problem(oid):
            if oid not in fast_problem_cache:
                fast_problem_cache[oid] = fast_has_any_problem(
                    oid,
                    include_image_problems=(self.image_mode == "folder")
                )
            return fast_problem_cache[oid]

        def check_group(oid, items, mode):

            if not items:
                return None  # ignorer tom gruppe

            results = []
            obs_row = obs_dict.get(oid, {})
            reg_row = reg_dict.get(oid, {})

            for p in items:

                if p == "Any_Problem":
                    val = fast_has_any_problem(oid)

                elif p == "Has_Images":
                    val = not obs_row.get("Images_Missing", False)

                elif p == "Images_Missing":
                    val = obs_row.get("Images_Missing", False)

                elif p == "Reviewed":
                    val = bool(obs_row.get(REVIEWED_COLUMN, False))

                elif p == "Not_Reviewed":
                    val = not bool(obs_row.get(REVIEWED_COLUMN, False))

                elif p == "Comment_Empty":
                    val = not str(reg_row.get("Comment", "")).strip()

                elif p == "Comment_Not_Empty":
                    val = bool(str(reg_row.get("Comment", "")).strip())

                elif p == "Extra_Empty":
                    val = not str(obs_row.get("Extra", "")).strip()

                elif p == "Extra_Not_Empty":
                    val = bool(str(obs_row.get("Extra", "")).strip())

                elif p == "Unknown":
                    val = any(
                        self.is_unknown(reg_row.get(field, ""))
                        for field in self.unknown_fields
                    )

                elif p == "Reviewed_With_Problem":
                    val = (bool(obs_row.get(REVIEWED_COLUMN, False))
                           and fast_get_cached_problem(oid))

                elif p == "Problem_With_History":
                    val = fast_get_cached_problem(oid) and fast_has_history(oid)

                elif p == "Has_History":
                    val = fast_has_history(oid)

                else:
                    val = fast_is_problem_active(oid, p)

                results.append(val)

            return all(results) if mode == "AND" else any(results)

   
        building_var = self.filter_location_vars.get("Building")
        floor_var = self.filter_location_vars.get("Floor")
        cabinet_var = self.filter_location_vars.get("Cabinet")

        has_location_filter = (
            (building_var and building_var.get()) or
            (floor_var and floor_var.get()) or
            (cabinet_var and cabinet_var.get().strip())
        )

        no_filters = all(len(v) == 0 for v in groups.values()) and not has_location_filter


        if no_filters:
            self.app.active_object_ids = list(self.app.df_reg.index)
            self._list_dirty = True
            return

        matched = []

        # PERFORMANCE OPTIMIZATION (Bolt): Retrieve all Tkinter variable values once before the loop,
        # avoiding thousands of expensive Tcl interpreter roundtrips inside the loop.
        group_modes = {group_name: self.filter_modes[group_name].get() for group_name in groups}

        building_filter = building_var.get() if building_var else ""
        floor_filter = floor_var.get() if floor_var else ""
        cabinet_filter = cabinet_var.get().strip().lower() if cabinet_var else ""

        # PERFORMANCE OPTIMIZATION (Bolt): Define the helper function outside of the main loop
        # to avoid function object creation overhead on every iteration.
        def get_location_str(val):
            if pd.isna(val) or val == "":
                return ""
            if isinstance(val, float) and val.is_integer():
                return str(int(val))
            return str(val)

        for oid in self.app.df_reg.index:

         
            if not_reviewed_only:
                obs_row = obs_dict.get(oid, {})
                if obs_row.get(REVIEWED_COLUMN):
                    continue
                matched.append(oid)
                continue

            # ---------- GROUP MATCH ----------
            group_results = []

            for group_name, items in groups.items():

                mode = group_modes[group_name]
                result = check_group(oid, items, mode)

                if result is not None:
                    group_results.append(result)

            # ---------- UNKNOWN MATCH ----------
        



              

            # ---------- LOCATION MATCH ----------
            location_match = True

            obs_row = obs_dict.get(oid, {})

            # Building
            if building_filter:
                if get_location_str(obs_row.get("Building", "")) != building_filter:
                    location_match = False

            # Floor
            if floor_filter:
                if get_location_str(obs_row.get("Floor", "")) != floor_filter:
                    location_match = False

            # Cabinet (substring match)
            if cabinet_filter:
                cabinet_val = get_location_str(obs_row.get("Cabinet", "")).lower()
                if cabinet_filter.replace(" ", "") not in cabinet_val.replace(" ", ""):
                    location_match = False

            # ---------- FINAL LOGIC (beholder din original logikk) ----------
            

            
            ok = all(group_results) if group_results else True
            ok = ok and location_match

            if ok:
                matched.append(oid)

        if not matched:
            messagebox.showinfo("No results", "Filter returned no objects")

        self.app.active_object_ids = matched
        self._list_dirty = True
        self.refresh_list()  # apply_filter must actually update the list
        self.update_filter_button_text()

     
        if hasattr(self, "filter_status_label"):
            total = len(self.app.df_reg)
            shown = len(matched)
            if shown < total:
                self.filter_status_label.config(
                    text=f"Filter aktiv: {shown} av {total} objekter"
                )
            else:
                self.filter_status_label.config(text="")

        if self.app.active_object_ids:

            self.object_list.selection_clear(0, tk.END)
            self.object_list.selection_set(0)
            self.object_list.see(0)

            self.object_list.event_generate("<<ListboxSelect>>")

#----

    def has_any_problem(self, oid, include_image_problems=True):
        for p in self.problem_columns:
            if p == "Images_Missing":
                continue
            if not include_image_problems:
                if "Image" in p:
                    continue
            if self.is_problem_active(oid, p):
                return True
        return False



#----
        
    def get_object_status(self, oid):

 
        if self.image_mode in ("online", "offline"):
            has_images = True
        else:
            has_images = not self.app.df_obs.loc[oid, "Images_Missing"]

   
        has_problem = self.has_any_problem(oid)

        return {
            "has_images": has_images,
            "has_problem": has_problem,
        }

#----

    def clear_filter(self, win, destroy_win=True):
        for v in self.filter_vars.values():
            v.set(False)
        if hasattr(self, "filter_unknown_var"):
            self.filter_unknown_var.set(False)

        self.filter_mode.set("AND")

        # Reset location filters (Building/Floor dropdowns + Cabinet text)
        for v in self.filter_location_vars.values():
            v.set("")

        self.app.active_object_ids = list(self.app.df_reg.index)
        self._list_dirty = True
        self.refresh_list()
        self.update_object_count()
        self.update_filter_button_text()

        if hasattr(self, "filter_status_label"):
            self.filter_status_label.config(text="")

        if destroy_win and win:
            win.destroy()


    def _get_cached_problem(self, oid):
        """Returns True if the object has any checked problem checkbox. Result is cached."""
        if oid not in self._problem_cache:
            try:
                self._problem_cache[oid] = self.has_any_problem(
                    oid,
                    include_image_problems=(self.image_mode == "folder")
                )
            except Exception:
                self._problem_cache[oid] = False
        return self._problem_cache[oid]

    def _has_history(self, oid):
        """Returns True if object appears in any loaded historical database."""
        if not self.app.historical_dbs:
            return False
        for db in self.app.historical_dbs:
            reg_by_id = db.get("reg_by_id")
            if reg_by_id is not None and oid in reg_by_id.index:
                return True
        return False

    # ---- Live Search methods ----
    def _on_inline_search_key(self, event=None):
        """Debounce: wait 250ms after last keystroke before filtering."""
        if self._inline_search_job:
            self.root.after_cancel(self._inline_search_job)
        self._inline_search_job = self.root.after(250, self._apply_inline_search)

    def _apply_inline_search(self):
        self._is_applying_search = True
        try:
            query = self._inline_search_var.get().strip().lower()
            placeholder = self._inline_search_placeholder.lower()

            if not query or query == placeholder:
                self._search_count_label.config(text="")
                if self.app.df_reg is not None:
                    self.app.active_object_ids = list(self.app.df_reg.index)
                self.refresh_list()
                return

            index = self._get_search_index()
            matched = [oid for oid, tokens in index.items() if query in tokens]

            self.app.active_object_ids = matched
            self.refresh_list()

            total = len(self.app.df_reg) if self.app.df_reg is not None else 0
            color = "green" if matched else "red"
            self._search_count_label.config(text=f"{len(matched)}/{total}", foreground=color)
        finally:
            self._is_applying_search = False

    def _clear_inline_search(self, event=None):
        self._inline_search_var.set("")
        self._search_count_label.config(text="")
        self._inline_search_entry.delete(0, tk.END)
        self._inline_search_entry.insert(0, self._inline_search_placeholder)
        self._inline_search_entry.config(foreground="gray")
        if self.app.df_reg is not None:
            self.app.active_object_ids = list(self.app.df_reg.index)
        self.refresh_list()

    def _search_focus_in(self, event=None):
        if self._inline_search_var.get() == self._inline_search_placeholder:
            self._inline_search_entry.delete(0, tk.END)
            self._inline_search_entry.config(foreground="black")

    def _search_focus_out(self, event=None):
        if not self._inline_search_var.get().strip():
            self._inline_search_entry.delete(0, tk.END)
            self._inline_search_entry.insert(0, self._inline_search_placeholder)
            self._inline_search_entry.config(foreground="gray")

    def _get_search_index(self):
        """
        Return the search index {oid: token_string}.
        During startup the index is pre-built by _precompute_startup_caches() so this
        method just returns the cached result.  After a data-changing operation that
        calls invalidate_search_index(), the cache is rebuilt lazily here covering
        ALL registration columns (not just Genus + Species) for maximum recall.
        """
        if self._search_index_cache is not None:
            return self._search_index_cache

        index = {}
        if self.app.df_reg is None:
            return index

        df = self.app.df_reg
        # Index every column in df_reg for full-text search coverage
        all_cols = list(df.columns)
        reg_dict = self._get_reg_dict()

        for oid in df.index:
            reg_row = reg_dict.get(oid, {})
            parts = [str(oid).lower()]
            for col in all_cols:
                val = reg_row.get(col, "")
                if val and not pd.isna(val):
                    val_str = str(val).strip().lower()
                    if val_str:
                        parts.append(val_str)
            index[oid] = " ".join(parts)

        self._search_index_cache = index
        return index

    def invalidate_search_index(self):
        """Call after any data change that affects Genus, Species, or ObjectID."""
        self._search_index_cache = None

    def _on_search_bar_enter(self, event=None):
        sel = self.object_list.curselection()
        if sel:
            idx = sel[0]
        elif self.app.active_object_ids:
            idx = 0
            self.object_list.selection_clear(0, tk.END)
            self.object_list.selection_set(0)
            self.object_list.see(0)
        else:
            return
        
        oid = self.app.active_object_ids[idx]
        self.load_object(oid)

    def _is_searching(self):
        if not hasattr(self, "_inline_search_var"):
            return False
        query = self._inline_search_var.get().strip().lower()
        placeholder = self._inline_search_placeholder.lower()
        return bool(query and query != placeholder)

    def _on_list_double_click(self, event=None):
        sel = self.object_list.curselection()
        if sel:
            idx = sel[0]
            oid = self.app.active_object_ids[idx]
            self.load_object(oid)

    def _on_list_return(self, event=None):
        self._on_list_double_click()
        return "break"

    def _show_context_menu(self, event):
        iid = self.object_list.identify_row(event.y)
        if iid:
            current_selection = self.object_list.selection()
            if iid not in current_selection:
                self.object_list.selection_clear(0)
                self.object_list.selection_set(iid)
                self.object_list.focus(iid)
                self.load_object(iid)
            
            self.context_menu.post(event.x_root, event.y_root)

    def _context_set_reviewed(self, value: bool):
        selection = self.object_list.selection()
        if not selection:
            return
        
        self.push_undo_state()
        
        now = datetime.now().strftime("%d.%m.%Y %H:%M") if value else ""
        
        for oid in selection:
            self.app.redo_stacks.setdefault(oid, []).clear()
            self.app.df_obs.loc[oid, REVIEWED_COLUMN] = value
            self.app.df_obs.loc[oid, REVIEWED_AT_COLUMN] = now
            self.update_list_item_color(oid)
            
        self.app.dirty = True
        self.update_dirty_ui()
        self._problem_cache.clear()
        self._invalidate_row_cache()
        self.update_review_progress()
        self.update_dashboard()
        
        current_oid = self.app.current_object_id
        if current_oid in selection:
            self.load_object(current_oid)

    def refresh_list(self):
        self.object_list.delete(0, tk.END)

        if not self.app.active_object_ids:
            return

        obs_df = self.app.df_obs
        reg_df = self.app.df_reg

        # Use cached dicts; rebuild only when data has changed (_row_cache_dirty).
        # This avoids expensive full-DF to_dict() on every filter/search/review.
        if getattr(self, "_row_cache_dirty", True) or self._cached_reg_dict is None:
            self._cached_reg_dict = reg_df.to_dict(orient="index") if reg_df is not None else {}
            self._cached_obs_dict = obs_df.to_dict(orient="index") if obs_df is not None else {}
            self._cached_reviewed_dict = (
                obs_df[REVIEWED_COLUMN].to_dict()
                if obs_df is not None and REVIEWED_COLUMN in obs_df.columns
                else {}
            )
            self._cached_genus_dict = (
                reg_df["Genus"].to_dict()
                if reg_df is not None and "Genus" in reg_df.columns
                else {}
            )
            self._cached_species_dict = (
                reg_df["Species"].to_dict()
                if reg_df is not None and "Species" in reg_df.columns
                else {}
            )
            self._row_cache_dirty = False

        reviewed_dict = self._cached_reviewed_dict
        genus_dict    = self._cached_genus_dict
        species_dict  = self._cached_species_dict
        reg_dict      = self._cached_reg_dict
        obs_dict      = self._cached_obs_dict



        # Is image mode folder?
        include_image_problems = (self.image_mode == "folder")

        # PERFORMANCE OPTIMIZATION: Skip problem-cache computation if it was already
        # pre-built by _precompute_startup_caches() on the background thread.
        # The pre-built cache covers all active objects; we only run the O(N×M) loop
        # when the cache is stale (e.g. after a user edit or image scan completion).
        cache_complete = len(self._problem_cache) >= len(self.app.active_object_ids)

        if not cache_complete:
            # Clear and re-compute problem cache for active objects
            self._problem_cache.clear()
            problem_cols = getattr(self, "problem_columns", [])
            problem_mapping = getattr(self, "problem_to_field", {})

            for oid in self.app.active_object_ids:
                obs_row = obs_dict.get(oid, {})
                reg_row = reg_dict.get(oid, {})

                has_prob = False
                for p in problem_cols:
                    if p == "Images_Missing":
                        continue
                    if not include_image_problems:
                        if "Image" in p:
                            continue

                    # Check if problem p is active
                    is_act = False
                    if p == "Other_problem":
                        is_act = bool(obs_row.get(p, False))
                    elif p == "Reviewed":
                        is_act = bool(obs_row.get(REVIEWED_COLUMN, False))
                    elif p == "Has_Images":
                        is_act = not obs_row.get("Images_Missing", False)
                    else:
                        obs_val = bool(obs_row.get(p, False))
                        auto_val = False
                        if p in problem_mapping:
                            field = problem_mapping.get(p)
                            if field:
                                raw_val = reg_row.get(field, "")
                                is_missing = (
                                    pd.isna(raw_val) or
                                    (isinstance(raw_val, str) and raw_val.strip() == "")
                                )
                                is_unknown = self.is_unknown(raw_val)
                                auto_val = is_missing and not is_unknown
                        is_act = obs_val or auto_val

                    if is_act:
                        has_prob = True
                        break

                self._problem_cache[oid] = has_prob

        # PERFORMANCE OPTIMIZATION (Bolt): Precompute a Python set of historical object IDs
        # to perform fast O(1) membership checks instead of index scans inside the loop.
        history_set = set()
        if self.app.historical_dbs:
            for db in self.app.historical_dbs:
                reg_by_id = db.get("reg_by_id")
                if reg_by_id is not None:
                    history_set.update(reg_by_id.index)

        for i, oid in enumerate(self.app.active_object_ids):
            genus = str(genus_dict.get(oid, "")).strip()
            species = str(species_dict.get(oid, "")).strip()
            if genus == "nan" or genus == "None": genus = ""
            if species == "nan" or species == "None": species = ""

            parts = [str(oid)]
            if genus: parts.append(genus)
            if species: parts.append(species)
            title = " ".join(parts)

            reviewed = bool(reviewed_dict.get(oid, False))
            has_problem = self._problem_cache.get(oid, False)
            has_history = oid in history_set

            color = None
            if reviewed and has_problem:
                color = "#f0ad4e"
            elif reviewed:
                color = "#0bd45b"
            elif has_problem and has_history:
                color = "#bb6bd9"
            elif has_problem:
                color = "#d9534f"

            # PERFORMANCE OPTIMIZATION (Bolt): Pass pre-calculated color directly to bypass itemconfig Tcl queries entirely.
            self.object_list.insert(tk.END, title, genus=genus, species=species, reviewed=reviewed, color=color, bulk=True)

        # Trigger lazy deferred card building if in detailed view mode
        if getattr(self.object_list, "active_view", None) == "detailed":
            self.object_list._lazy_build_cards(0)


    def update_filter_button_text(self):
        active = [k for k, v in self.filter_vars.items() if v.get()]

        if getattr(self, "filter_unknown_var", None) and self.filter_unknown_var.get():
            active.append("Unknown")

        if active:
            short = ", ".join(active[:3])
            if len(active) > 3:
                short += "..."
            self.filter_btn.config(text=f"Filter ({len(active)}): {short}")
        else:
            self.filter_btn.config(text="Filter")


    def _quick_filter(self, mode):
        for v in self.filter_vars.values():
            v.set(False)

        if mode == "problems":
            self.filter_vars["Any_Problem"].set(True)
        elif mode == "images":
            self.filter_vars["Images_Missing"].set(True)
        elif mode == "not_reviewed":
            self.filter_vars["Not_Reviewed"].set(True)
        elif mode == "reviewed_problem":
            self.filter_vars["Reviewed_With_Problem"].set(True)
        elif mode == "has_history":
            self.filter_vars["Has_History"].set(True)

        self.update_filter_button_text()


# ---- Batch review

    def _batch_set_reviewed(self, value: bool):
        ids = self.app.active_object_ids
        count = len(ids)

        if count == 0:
            messagebox.showinfo("No objects", "No objects in current view")
            return

        action = "Reviewed" if value else "Not Reviewed"
        res = messagebox.askyesno(
            "Batch review",
            f"Mark {count} objects as {action}?"
        )
        if not res:
            return

        now = datetime.now().strftime("%d.%m.%Y %H:%M") if value else ""

        for oid in ids:
            self.app.df_obs.at[oid, REVIEWED_COLUMN] = value
            self.app.df_obs.at[oid, REVIEWED_AT_COLUMN] = now

        self.app.dirty = True
        self.update_dirty_ui()
        self._problem_cache.clear()
        self._invalidate_row_cache()
        self._list_dirty = True
        self.update_review_progress()
        self.system_status.config(text=f"Marked {count} objects as {action}")

        oid = self.app.current_object_id
        if oid:
            self.load_object(oid)


# ---- Recent objects

    def open_recent_popup(self):
        if not self.history_stack:
            self.system_status.config(text="No recently visited objects")
            return

        if hasattr(self, "recent_window") and self.recent_window and self.recent_window.winfo_exists():
            self.recent_window.lift()
            self.recent_window.focus_force()
            return

        win = tk.Toplevel(self.root)
        self.recent_window = win
        win.bind("<Destroy>", lambda e: setattr(self, "recent_window", None) if e.widget == win else None)
        win.title("Recently visited")
        import utils
        utils.center_and_fit_toplevel(win, 320, 320)
        win.bind("<Escape>", lambda e: win.destroy())

        ttk.Label(
            win,
            text="Recently visited",
            font=("Segoe UI", sc(10), "bold")
        ).pack(anchor="w", padx=10, pady=(10, 4))

        frame = ttk.Frame(win)
        frame.pack(fill="both", expand=True, padx=6, pady=4)

        listbox = tk.Listbox(frame, exportselection=False)
        scrollbar = ttk.Scrollbar(frame, orient="vertical", command=listbox.yview)
        listbox.configure(yscrollcommand=scrollbar.set)
        listbox.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        recent = list(reversed(self.history_stack[-20:]))
        for oid in recent:
            title = self.object_title(oid)
            listbox.insert(tk.END, title)

        def go_to(event=None):
            if not listbox.curselection():
                return
            idx = listbox.curselection()[0]
            oid = recent[idx]
            self.object_list.selection_clear(0, tk.END)
            if oid in self.app.active_object_ids:
                list_idx = self.app.active_object_ids.index(oid)
                self.object_list.selection_set(list_idx)
                self.object_list.see(list_idx)
            self.load_object(oid)
            win.destroy()

        listbox.bind("<Double-Button-1>", go_to)
        listbox.bind("<Return>", go_to)

        btns = ttk.Frame(win)
        btns.pack(fill="x", padx=6, pady=6)
        ttk.Button(btns, text="Go to", command=go_to).pack(side="right")
        ttk.Button(btns, text="Close", command=win.destroy).pack(side="left")


# ---- Export filtered list

    def export_filtered_list(self):
        if self.app.df_reg is None:
            messagebox.showinfo("No data", "Load an Excel file first")
            return

        if not self.app.active_object_ids:
            messagebox.showinfo("No objects", "No objects to export")
            return

        path = filedialog.asksaveasfilename(
            defaultextension=".xlsx",
            filetypes=[
                ("Excel files", "*.xlsx"),
                ("CSV files", "*.csv")
            ],
            initialdir=__import__("config").get_last_dir("last_db_dir"),
            title="Export filtered list"
        )
        if not path:
            return
        __import__("config").set_last_dir("last_db_dir", path)

        try:
            ids = self.app.active_object_ids
            df_reg_exp = self.app.df_reg.loc[ids].reset_index()
            df_obs_exp = self.app.df_obs.loc[ids].reset_index()
            df_merged = df_reg_exp.merge(df_obs_exp, on="ObjectID", suffixes=("", "_obs"))

            if path.lower().endswith(".csv"):
                df_merged.to_csv(path, index=False, encoding="utf-8-sig")
            else:
                df_merged.to_excel(path, index=False, engine="openpyxl")

            self.system_status.config(
                text=f"Exported {len(ids)} objects  {os.path.basename(path)}"
            )
            messagebox.showinfo(
                "Export complete",
                f"Exported {len(ids)} objects to:\n{os.path.basename(path)}"
            )

        except Exception as e:
            messagebox.showerror("Export failed", str(e))


# ---- Sort object list

    def _sort_object_list(self, sort_key):
        if not self.app.active_object_ids or self.app.df_reg is None:
            return

        ids = self.app.active_object_ids

        if sort_key == "ID":
            def id_key(oid):
                try:
                    return (0, int(oid))
                except ValueError:
                    return (1, str(oid))
            self.app.active_object_ids = sorted(ids, key=id_key)

        elif sort_key == "Genus A-Z":
            # OPTIMIZATION: use cached genus dict — O(1) per item vs creating a new
            # pandas Series per item via df_reg.loc[oid] which was O(N) allocations.
            genus_dict = self._cached_genus_dict or {}
            self.app.active_object_ids = sorted(
                ids,
                key=lambda oid: str(genus_dict.get(oid, "") or "").lower()
            )

        elif sort_key == "Reviewed first":
            # OPTIMIZATION: use cached reviewed dict — O(1) per item
            reviewed_dict = self._cached_reviewed_dict or {}
            self.app.active_object_ids = sorted(
                ids,
                key=lambda oid: 0 if bool(reviewed_dict.get(oid, False)) else 1
            )

        elif sort_key == "Problems first":
            # OPTIMIZATION: use pre-built problem cache — O(1) per item
            problem_cache = self._problem_cache or {}
            self.app.active_object_ids = sorted(
                ids,
                key=lambda oid: 0 if problem_cache.get(oid, False) else 1
            )

        self._list_dirty = True
        self.refresh_list()

        # Behold valgt objekt synlig
        oid = self.app.current_object_id
        if oid and oid in self.app.active_object_ids:
            idx = self.app.active_object_ids.index(oid)
            self.object_list.selection_clear(0, tk.END)
            self.object_list.selection_set(idx)
            self.object_list.see(idx)

        self.system_status.config(text=f"Sorted by: {sort_key}")


# ---- Copy/paste field value

    def _copy_field_value(self, event=None):
        widget = self.root.focus_get()

        for name, w in self.reg_entries.items():
            if w == widget:
                try:
                    if isinstance(widget, tk.Text):
                        value = widget.get("1.0", tk.END).strip()
                    else:
                        value = widget.get()
                    self._copied_field_name = name
                    self._copied_field_value = value
                    preview = (value[:40] + "...") if len(value) > 40 else value
                    self.system_status.config(text=f"Copied [{name}]: {preview}")
                except Exception:
                    pass
                break

        return "break"

    def _paste_field_value(self, event=None):
        if not hasattr(self, "_copied_field_name") or not hasattr(self, "_copied_field_value"):
            self.system_status.config(text="Nothing copied use Ctrl+Shift+C first")
            return "break"

        name = self._copied_field_name
        widget = self.reg_entries.get(name)

        if not widget:
            return "break"

        try:
            if isinstance(widget, tk.Text):
                widget.delete("1.0", tk.END)
                widget.insert("1.0", self._copied_field_value)
            else:
                self.reg_vars[name].set(self._copied_field_value)
            self.system_status.config(text=f"Pasted to [{name}]")
        except Exception:
            pass

        return "break"


# ---- Statistics






# ---- Clear filter quick

    def _clear_filter_quick(self):
        for v in self.filter_vars.values():
            v.set(False)
        if hasattr(self, "filter_unknown_var"):
            self.filter_unknown_var.set(False)
        self.filter_mode.set("AND")
        if hasattr(self, "filter_location_vars"):
            for v in self.filter_location_vars.values():
                v.set("")
        self.app.active_object_ids = list(self.app.df_reg.index)
        self._list_dirty = True
        self.refresh_list()
        self.update_object_count()
        self.update_filter_button_text()
        if hasattr(self, "filter_status_label"):
            self.filter_status_label.config(text="")


# =====================
# Main
# =====================



    def go_back(self):
        if not self.history_stack:
            return
        
        current = self.app.current_object_id
        if current:
            self.forward_stack.append(current)
            
        oid = self.history_stack.pop()
        
        self.object_list.selection_clear(0, tk.END)
        if oid in self.app.active_object_ids:
            idx = self.app.active_object_ids.index(oid)
            self.object_list.selection_set(idx)
            self.object_list.see(idx)
            
        self.load_object(oid, is_history_nav=True)

    def go_forward(self):
        if not self.forward_stack:
            return
            
        current = self.app.current_object_id
        oid = self.forward_stack.pop()
        
        if current:
            self.history_stack.append(current)
            if len(self.history_stack) > 50:
                self.history_stack.pop(0)
            
        self.object_list.selection_clear(0, tk.END)
        if oid in self.app.active_object_ids:
            idx = self.app.active_object_ids.index(oid)
            self.object_list.selection_set(idx)
            self.object_list.see(idx)
            
        self.load_object(oid, is_history_nav=True)

    def update_navigation_buttons(self):
        if hasattr(self, "back_btn") and self.back_btn:
            self.back_btn.config(state="normal" if self.history_stack else "disabled")
        if hasattr(self, "forward_btn") and self.forward_btn:
            self.forward_btn.config(state="normal" if self.forward_stack else "disabled")

    def snap_to_place(self, shrink=True):
        """
        Adjusts the middle panes sash position to focus layout elements.
        If shrink is True, shrinks the image panel (sash 0) to make room.
        If shrink is False, restores the previous manual sash position.
        """
        try:
            if shrink:
                # Save the last manual sash position before shrinking
                self._last_manual_middle_sash = self.middle_panes.sashpos(0)
                def _do_shrink():
                    try:
                        self.root.update_idletasks()
                        self.middle_panes.sashpos(0, sc(120))
                    except Exception:
                        pass
                self.root.after(10, _do_shrink)
            else:
                def _do_restore():
                    try:
                        if hasattr(self, "_last_manual_middle_sash"):
                            self.middle_panes.sashpos(0, self._last_manual_middle_sash)
                    except Exception:
                        pass
                self.root.after(50, _do_restore)
        except Exception:
            pass

    def update_reg_fields_visibility(self, skip_snap=False):
        if not self.object_loaded:
            return
            
        focus_active = self.focus_mode_var.get()
        focus_fallback = self.focus_fallback_var.get()
        
        # Committing problem changes instantly to update status color coding
        oid = self.app.current_object_id
        if oid and not self.loading_object:
            self.commit_current_object(skip_heavy=True)
            
        active_problem_fields = set()
        for prob_col, mapped_field in self.problem_to_field.items():
            if self.problem_vars.get(prob_col) and self.problem_vars[prob_col].get():
                active_problem_fields.add(mapped_field)
                
        # Location and Problems sections visibility
        if hasattr(self, "loc_container") and hasattr(self, "prob_container"):
            show_loc = not (focus_active and not self.focus_visibility_vars.get("Location", tk.BooleanVar(value=True)).get())
            show_prob = not (focus_active and not self.focus_visibility_vars.get("Problems", tk.BooleanVar(value=True)).get())
            
            # Repack location components safely
            self.loc_container.pack_forget()
            if show_loc:
                if str(self.left_bottom_container) not in self.left_panes.panes():
                    self.left_panes.add(self.left_bottom_container, weight=0)
                self.loc_container.pack(side="top", fill="x")
            else:
                if str(self.left_bottom_container) in self.left_panes.panes():
                    self.left_panes.forget(self.left_bottom_container)
                
            if show_prob:
                try:
                    self.reg_notebook.add(self._reg_tabs["Problems"]["container"])
                except Exception:
                    pass
            else:
                try:
                    self.reg_notebook.hide(self._reg_tabs["Problems"]["container"])
                except Exception:
                    pass
                
        visible_count = 0
        
        # Registration fields
        for field in self.app.config["ui_sections"]["registration"]:
            name = field["name"]
            frame = self.reg_row_frames.get(name)
            if not frame:
                continue
            
            is_visible = True
            if focus_active:
                field_toggle = self.focus_visibility_vars.get(name, tk.BooleanVar(value=True)).get()
                has_problem = (name in active_problem_fields)
                if focus_fallback and has_problem:
                    is_visible = True
                else:
                    is_visible = field_toggle
                    
            if is_visible:
                frame.grid()
                visible_count += 1
            else:
                frame.grid_remove()
                

        # Unknown/missing values section
        if hasattr(self, "unknown_fields_container"):
            frame = self.unknown_fields_container
            is_visible = True
            if focus_active:
                is_visible = False
                
            if is_visible:
                frame.grid()
                visible_count += 1
            else:
                frame.grid_remove()
            
        # Sjekk om i det hele tatt noe er synlig (only run when Focus Mode is active)
        if focus_active:
            for field_name, check_var in self.focus_visibility_vars.items():
                frame = self.reg_row_frames.get(field_name)
                if frame and not check_var.get():
                    if frame.winfo_manager() == "grid":
                        visible_count -= 1
                    frame.grid_remove()
                
        if focus_active and visible_count <= 0:
            self.no_problems_msg_label.config(text="No fields visible in Focus mode.")
            self.no_problems_msg_label.grid(row=0, column=0, pady=15, sticky="ew")
        else:
            self.no_problems_msg_label.grid_remove()

        # Dynamically hide card frames if all of their fields are hidden in Focus Mode
        if hasattr(self, "card_frames") and hasattr(self, "card_defs_ordered"):
            for card_id in self.card_defs_ordered:
                info = self.card_frames[card_id]
                card_frame = info["frame"]
                fields = info["fields"]
                any_visible = False
                for f in fields:
                    row_frame = self.reg_row_frames.get(f)
                    if row_frame and row_frame.winfo_manager() == "grid":
                        any_visible = True
                        break
                card_frame.pack_forget()
                if any_visible:
                    card_frame.pack(fill="x", padx=10, pady=8)

        if not skip_snap and self.snap_lock_var.get():
            self.snap_to_place(shrink=focus_active)
            
        self.update_dashboard()




    def _validate_fields(self, event=None):
        if self._is_navigating or self.loading_object:
            return

        is_dark = getattr(self, "dark_mode_active", self.app.config.get("theme", "dark") == "dark")
        warn_bg = "#5c4d00" if is_dark else "#fff3cd"
        err_bg = "#5c1e1e" if is_dark else "#f8d7da"
        norm_bg = "#181825" if is_dark else "white"

        # Initialize styles if they don't exist
        style = ttk.Style()
        if not hasattr(self, "_validation_styles_created"):
            style.map("Warning.TEntry", fieldbackground=[("!disabled", warn_bg)])
            style.map("Error.TEntry", fieldbackground=[("!disabled", err_bg)])
            style.map("Normal.TEntry", fieldbackground=[("!disabled", norm_bg)])
            self._validation_styles_created = True
        else:
            style.map("Warning.TEntry", fieldbackground=[("!disabled", warn_bg)])
            style.map("Error.TEntry", fieldbackground=[("!disabled", err_bg)])
            style.map("Normal.TEntry", fieldbackground=[("!disabled", norm_bg)])

        # Rule 1: Genus but no Species (Warning)
        genus = self.reg_vars.get("Genus", tk.StringVar()).get().strip()
        species = self.reg_vars.get("Species", tk.StringVar()).get().strip()
        
        if genus and not species and "Species" in self.reg_entries:
            self.reg_entries["Species"].configure(style="Warning.TEntry")
        elif "Species" in self.reg_entries:
            self.reg_entries["Species"].configure(style="Normal.TEntry")

        # Rule 2: Building/Location empty but no Loc Problem (Error)
        building = self.reg_vars.get("Building", tk.StringVar()).get().strip()
        loc_prob = self.problem_vars.get("Loc_Problem", tk.BooleanVar()).get()
        
        if not building and not loc_prob and "Building" in self.reg_entries:
            self.reg_entries["Building"].configure(style="Error.TEntry")
        elif "Building" in self.reg_entries:
            self.reg_entries["Building"].configure(style="Normal.TEntry")


    def _run_fuzzy_match(self, field_name, widget):
        if field_name not in ["Genus", "Species"]:
            return
            
        val = self.reg_vars[field_name].get().strip()
        if not val or len(val) < 3:
            if hasattr(widget, "fuzzy_label"):
                widget.fuzzy_label.destroy()
                delattr(widget, "fuzzy_label")
            return

        history = self.current_object_suggestions.get(field_name, [])
        if not history:
            return
            
        import difflib
        # Look for close matches that are NOT the exact typed value
        matches = difflib.get_close_matches(val, history, n=1, cutoff=0.7)
        
        if matches and matches[0].lower() != val.lower():
            suggestion = matches[0]
            if hasattr(widget, "fuzzy_label"):
                widget.fuzzy_label.destroy()
            
            lbl = ttk.Label(widget.master, text=f"Did you mean '{suggestion}'?", foreground="#4dabf7", font=("Segoe UI", 8, "underline"), cursor="hand2")
            lbl.grid(row=1, column=1, sticky="w")
            
            def apply_suggestion(e, s=suggestion, w=widget, n=field_name):
                self.reg_vars[n].set(s)
                self.commit_current_object()
                w.fuzzy_label.destroy()
                delattr(w, "fuzzy_label")
                self._validate_fields()
                
            lbl.bind("<Button-1>", apply_suggestion)
            widget.fuzzy_label = lbl
        else:
            if hasattr(widget, "fuzzy_label"):
                widget.fuzzy_label.destroy()
                delattr(widget, "fuzzy_label")

    def _clear_all_fuzzy_labels(self):
        """Destroy any 'Did you mean' suggestion labels on all registration entry widgets."""
        for widget in self.reg_entries.values():
            if hasattr(widget, "fuzzy_label"):
                try:
                    widget.fuzzy_label.destroy()
                except Exception:
                    pass
                delattr(widget, "fuzzy_label")

    def _on_autocomplete_key(self, event, name, widget):
        if event.keysym in ("Up", "Down", "Left", "Right", "Return", "Escape", "Tab", "Shift_L", "Shift_R", "Control_L", "Control_R", "Alt_L", "Alt_R"):
            return
        typed = widget.get().strip().lower()
        all_vals = self.current_object_suggestions.get(name, [])
        if not all_vals:
            return
        if not typed:
            filtered = all_vals
        else:
            filtered = [v for v in all_vals if typed in str(v).lower()]
        if isinstance(widget, ttk.Combobox):
            widget.configure(values=filtered)










    def set_status_badge(self, status_type, text=""):
        if not hasattr(self, "data_status") or not self.data_status:
            return
        colors = self.status_badge_colors.get(status_type, {"bg": "#f0f0f0", "fg": "black"})
        self.data_status.config(
            text=f" {text} ",
            background=colors["bg"],
            foreground=colors["fg"],
            relief="flat",
            padx=8,
            pady=4
        )
        # Update LAST_SAVE in status bar when saved
        if status_type in ("saved", "autosaved") and hasattr(self, "_status_bar_labels"):
            ts = datetime.now().strftime("%H:%M:%S")
            self._status_bar_labels["last_save"].config(text=f"LAST_SAVE: {ts}")

    def sort_column(self, col):
        if self.app.df_reg is None or not self.app.active_object_ids:
            return
            
        ascending = self.sort_directions.get(col, True)
        self.sort_directions[col] = not ascending
        
        ids = self.app.active_object_ids
        
        if col == "ID":
            def id_key(oid):
                try:
                    return (0, int(oid))
                except ValueError:
                    return (1, str(oid))
            sorted_ids = sorted(ids, key=id_key, reverse=not ascending)
        elif col == "Genus":
            sorted_ids = sorted(
                ids,
                key=lambda oid: str(self.app.df_reg.loc[oid].get("Genus", "")).lower(),
                reverse=not ascending
            )
        elif col == "Species":
            sorted_ids = sorted(
                ids,
                key=lambda oid: str(self.app.df_reg.loc[oid].get("Species", "")).lower(),
                reverse=not ascending
            )
        elif col == "Status":
            def status_key(oid):
                try:
                    reviewed = bool(self.app.df_obs.loc[oid, REVIEWED_COLUMN])
                except Exception:
                    reviewed = False
                has_problem = self._get_cached_problem(oid)
                has_history = self._has_history(oid)
                
                if reviewed and has_problem:
                    return 1
                elif reviewed:
                    return 2
                elif has_problem and has_history:
                    return 3
                elif has_problem:
                    return 4
                else:
                    return 5
            sorted_ids = sorted(ids, key=status_key, reverse=not ascending)
            
        self.app.active_object_ids = sorted_ids
        self._list_dirty = True
        self.refresh_list()
        
        oid = self.app.current_object_id
        if oid and oid in self.app.active_object_ids:
            idx = self.app.active_object_ids.index(oid)
            self.object_list.selection_clear(0, tk.END)
            self.object_list.selection_set(idx)
            self.object_list.see(idx)
            
        dir_char = "â–²" if ascending else "â–¼"
        self.system_status.config(text=f"Sorted by {col} {dir_char}")


    def _bind_mousewheel_recursive(self, widget, handler):
        widget.bind("<MouseWheel>", handler)
        for child in widget.winfo_children():
            self._bind_mousewheel_recursive(child, handler)



    def _on_reviewed_clicked(self):
        """Mark as reviewed and automatically advance if autoAdvanceOnReview is enabled."""
        self.mark_current_as_reviewed()

    def update_reviewed_button_state(self):
        oid = self.app.current_object_id
        large_size = self.large_reviewed_button_var.get()
        padx_val = sc(32) if large_size else sc(18)
        pady_val = sc(14) if large_size else sc(8)

        if not oid:
            self.reviewed_button.config(
                text="✓ Mark as Reviewed",
                state="disabled",
                bg="#f3f3f3",
                fg="gray",
                activebackground="#f3f3f3",
                activeforeground="gray",
                highlightbackground="gray",
                padx=padx_val, pady=pady_val
            )
            return

        self.reviewed_button.config(state="normal")
        is_reviewed = bool(self.reviewed_var.get())

        if hasattr(self, "clear_problems_var") and hasattr(self, "problem_vars"):
            all_clear = all(not var.get() for var in self.problem_vars.values())
            self.clear_problems_var.set(all_clear and is_reviewed)

        if is_reviewed:
            reviewed_at = ""
            if self.app.df_obs is not None and oid in self.app.df_obs.index:
                try:
                    reviewed_at = str(self.app.df_obs.loc[oid, REVIEWED_AT_COLUMN])
                except Exception:
                    pass
            
            time_str = ""
            if reviewed_at and reviewed_at != "nan":
                parts = reviewed_at.split()
                if len(parts) >= 2:
                    time_str = parts[1][:5]
                else:
                    time_str = reviewed_at[:5]
            
            btn_text = f"✓ REVIEWED – {time_str}" if time_str else "✓ REVIEWED"
            self.reviewed_button.config(
                text=btn_text,
                bg="#ffffff",
                fg="#3b6934",
                activebackground="#f3f3f3",
                activeforeground="#3b6934",
                highlightbackground="#3b6934",
                padx=padx_val, pady=pady_val
            )
        else:
            self.reviewed_button.config(
                text="✓ MARK AS REVIEWED",
                bg="#3b6934",
                fg="#ffffff",
                activebackground="#2e5228",
                activeforeground="#ffffff",
                highlightbackground="#3b6934",
                padx=padx_val, pady=pady_val
            )

    def _on_reviewed_btn_enter(self, event):
        if not self.app.current_object_id:
            return
        if bool(self.reviewed_var.get()):
            self.reviewed_button.config(bg="#f3f3f3")
        else:
            self.reviewed_button.config(bg="#2e5228")

    def _on_reviewed_btn_leave(self, event):
        if not self.app.current_object_id:
            return
        if bool(self.reviewed_var.get()):
            self.reviewed_button.config(bg="#ffffff")
        else:
            self.reviewed_button.config(bg="#3b6934")

    def mark_reviewed_and_next(self, event=None):
        """Mark as reviewed and automatically advance if autoAdvanceOnReview is enabled."""
        self.mark_current_as_reviewed()
        return "break"

    def _clear_problems_and_mark_reviewed(self, event=None):
        """Clear all problem flags for the current object and mark it as reviewed.
        
        Stays on the current object — no navigation — so the user can verify
        the result before moving on.
        """
        if hasattr(self, "clear_problems_var") and not self.clear_problems_var.get():
            return

        oid = self.app.current_object_id
        if not oid:
            return

        # 1. Uncheck all problem vars in the UI
        for col, var in self.problem_vars.items():
            try:
                var.set(False)
            except Exception:
                pass

        # 2. Commit the cleared problems to the dataframe
        self.commit_current_object()

        # 3. Mark as reviewed if not already (toggle only to True)
        is_reviewed = False
        if self.app.df_obs is not None and oid in self.app.df_obs.index:
            try:
                is_reviewed = bool(self.app.df_obs.loc[oid, REVIEWED_COLUMN])
            except Exception:
                pass
        if not is_reviewed:
            self._toggle_reviewed_for_id(oid)

        if hasattr(self, "clear_problems_var"):
            self.clear_problems_var.set(True)

    # ------------------------------------------------------------------
    # Problem row styling helpers
    # ------------------------------------------------------------------

    def _update_problem_row_style(self, field_name, is_active):
        """Apply or remove the red visual treatment on a registration row.

        Called whenever a mapped problem var changes (trace) or on load.
        Updates three elements independently so any missing ref is safe to skip:
          1. Left border bar (3px tk.Frame) — red accent or transparent
          2. Field label (ttk.Label) — error foreground or normal
          3. Entry / Combobox widget — Problem.TEntry style or TEntry
        """
        is_dark = getattr(self, "dark_mode_active", False)
        err_fg      = "#f38ba8" if is_dark else "#ba1a1a"
        norm_fg     = "#cdd6f4" if is_dark else "#1a1c1c"
        bar_active  = "#ba1a1a" if not is_dark else "#f38ba8"
        bar_normal  = "#1e1e2e" if is_dark else "#f3f3f3"  # matches ttk.Frame bg — invisible

        # 1. Border bar
        bar = self.prob_border_bars.get(field_name)
        if bar:
            try:
                bar.config(bg=bar_active if is_active else bar_normal)
            except Exception:
                pass

        # 2. Label
        lbl = self.prob_label_widgets.get(field_name)
        if lbl:
            try:
                lbl.config(foreground=err_fg if is_active else norm_fg)
            except Exception:
                pass

        # 3. Entry / Combobox style
        widget = self.reg_entries.get(field_name)
        if widget:
            try:
                if isinstance(widget, tk.Text):
                    # Classic Text widget — set background directly
                    tint = "#5c1e1e" if is_dark else "#ffdad6"
                    norm_bg = "#1e1e2e" if is_dark else "#ffffff"
                    widget.config(background=tint if is_active else norm_bg)
                elif isinstance(widget, ttk.Combobox):
                    widget.configure(style="Problem.TCombobox" if is_active else "TCombobox")
                elif isinstance(widget, ttk.Entry):
                    widget.configure(style="Problem.TEntry" if is_active else "TEntry")
            except Exception:
                pass
                
        # Update accordion badges if any
        self._update_accordion_badges()

    def _update_accordion_badges(self):
        """Iterate all accordion groups and count active problems within their fields."""
        if not hasattr(self, "_accordion_groups"):
            return
            
        field_to_problem = {v: k for k, v in self.problem_to_field.items()}
        for g_name, data in self._accordion_groups.items():
            badge_label = data.get("badge_label")
            if not badge_label:
                continue
                
            count = 0
            for field in data.get("fields", []):
                prob_col = field_to_problem.get(field)
                if prob_col and prob_col in self.problem_vars and self.problem_vars[prob_col].get():
                    count += 1
                    
            if count > 0:
                text = f"[{count} problem{'s' if count > 1 else ''}]"
                badge_label.config(text=text)
            else:
                badge_label.config(text="")

    def _update_all_problem_row_styles(self):
        """Refresh styling for every mapped problem field.

        Called after load_object sets all problem vars, and after undo restores state,
        so the visual treatment is always in sync with the data.
        """
        for field_name in self.prob_border_bars:
            # Find the problem column that maps to this field
            field_to_problem = {v: k for k, v in self.problem_to_field.items()}
            prob_col = field_to_problem.get(field_name)
            if prob_col and prob_col in self.problem_vars:
                is_active = bool(self.problem_vars[prob_col].get())
                self._update_problem_row_style(field_name, is_active)
        
        self._update_accordion_badges()

    def update_list_item_color(self, oid):
        if not self.app.active_object_ids or oid not in self.app.active_object_ids:
            return
            
        color = None
        try:
            reviewed = bool(self.app.df_obs.loc[oid, REVIEWED_COLUMN])
        except Exception:
            reviewed = False
            
        has_problem = self._get_cached_problem(oid)
        has_history = self._has_history(oid)
        
        if reviewed and has_problem:
            color = "#f0ad4e"
        elif reviewed:
            color = "#0bd45b"
        elif has_problem and has_history:
            color = "#bb6bd9"
        elif has_problem:
            color = "#d9534f"
            
        current_tags = list(self.object_list.item(oid, "tags") or [])
        current_tags = [t for t in current_tags if not t.startswith("color_")]
        
        if color:
            tag_name = f"color_{color.replace('#', '')}"
            self.object_list.tag_configure(tag_name, foreground=color)
            current_tags.append(tag_name)
            
        self.object_list.item(oid, tags=current_tags)

        # Update checkbox symbol
        current_vals = list(self.object_list.item(oid, "values") or [])
        if current_vals:
            current_vals[0] = "☑" if reviewed else "☐"
            self.object_list.item(oid, values=current_vals)

    def mark_current_as_reviewed(self):
        oid = self.app.current_object_id
        if not oid:
            return

        # Ensure the current item is marked as reviewed (set to True)
        self.push_undo_state()

        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.app.df_obs.loc[oid, REVIEWED_COLUMN] = True
        self.app.df_obs.loc[oid, REVIEWED_AT_COLUMN] = now

        # If this is the currently active object, also update the checkbox variable and display
        self.reviewed_var.set(True)
        self.reviewed_time_label.config(text=now)

        self.app.dirty = True
        self.update_dirty_ui()
        self.update_dashboard()
        self.update_list_item_color(oid)
        self.update_review_progress()
        self._list_dirty = True
        self.update_reviewed_button_state()

        # If autoAdvanceOnReview is True and a next item exists, advance
        if self.autoAdvanceOnReview:
            if oid in self.app.active_object_ids:
                idx = self.app.active_object_ids.index(oid)
                if idx + 1 < len(self.app.active_object_ids):
                    self.navigate_object(1)

    def _toggle_reviewed_for_id(self, oid):
        if not oid:
            return
        self.push_undo_state()
        
        # Toggle in df_obs
        current = False
        if self.app.df_obs is not None and oid in self.app.df_obs.index:
            try:
                current = bool(self.app.df_obs.loc[oid, REVIEWED_COLUMN])
            except Exception:
                pass
        new_val = not current
        
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.app.df_obs.loc[oid, REVIEWED_COLUMN] = new_val
        self.app.df_obs.loc[oid, REVIEWED_AT_COLUMN] = now
        
        # If this is the currently active object, also update the checkbox variable
        if oid == self.app.current_object_id:
            self.reviewed_var.set(new_val)
            self.reviewed_time_label.config(text=now if new_val else "")
            
        self.app.dirty = True
        self.update_dirty_ui()
        self.update_dashboard()
        self.update_list_item_color(oid)
        self.update_review_progress()
        self._list_dirty = True




    def load_ignored_words(self):
        import json
        if os.path.exists(self.ignored_words_file):
            try:
                with open(self.ignored_words_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.ignored_words = data.get("words", [])
                    self.ignored_words_variations.set(data.get("variations", True))
            except Exception as e:
                debug_error("Load ignored words failed", str(e))
                self.ignored_words = []
        else:
            self.ignored_words = []
            self.ignored_words_variations.set(True)
            self.save_ignored_words()

    def save_ignored_words(self):
        import json
        try:
            with open(self.ignored_words_file, "w", encoding="utf-8") as f:
                json.dump({
                    "words": self.ignored_words,
                    "variations": self.ignored_words_variations.get()
                }, f, indent=4, ensure_ascii=False)
        except Exception as e:
            debug_error("Save ignored words failed", str(e))

    def normalize_word(self, text, variations):
        if not text:
            return ""
        text = text.strip()
        if variations:
            text = text.lower()
            text = _NORMALIZE_NON_WORD_PATTERN.sub('', text)
            text = _NORMALIZE_SPACE_PATTERN.sub(' ', text)
            text = text.strip()
        return text

    def is_word_ignored(self, val):
        if not val or not self.ignored_words:
            return False
        
        variations = self.ignored_words_variations.get()
        val_norm = self.normalize_word(val, variations)
        
        for word in self.ignored_words:
            word_norm = self.normalize_word(word, variations)
            if variations:
                if val_norm == word_norm:
                    return True
            else:
                if val == word:
                    return True
        return False

    def open_ignored_words_editor(self):
        win = tk.Toplevel(self.root)
        win.transient(self.root)
        win.grab_set()
        win.bind("<Escape>", lambda e: win.destroy())
        
        bg_color = "#1e1e2e" if self.dark_mode_active else "#f0f0f0"
        fg_color = "#cdd6f4" if self.dark_mode_active else "black"
        field_bg = "#181825" if self.dark_mode_active else "white"
        border_color = "#313244" if self.dark_mode_active else "#d0d0d0"
        
        win.configure(background=bg_color)
        win.title("Configure Ignored Words")
        import utils
        utils.center_and_fit_toplevel(win, 500, 550)
        
        title_lbl = ttk.Label(win, text="Suggestions Filter: Ignored Words", font=("Segoe UI", sc(12), "bold"))
        title_lbl.pack(anchor="w", padx=15, pady=(15, 5))
        
        desc_lbl = ttk.Label(
            win, 
            text="Suggestions matching these words/phrases will be omitted in comparison.\nEnter one word or phrase per line.", 
            font=("Segoe UI", sc(9))
        )
        desc_lbl.pack(anchor="w", padx=15, pady=(0, 10))
        
        text_frame = ttk.Frame(win)
        text_frame.pack(fill="both", expand=True, padx=15, pady=5)
        
        text_scroll = ttk.Scrollbar(text_frame)
        text_scroll.pack(side="right", fill="y")
        
        text_area = tk.Text(
            text_frame, 
            yscrollcommand=text_scroll.set, 
            font=("Segoe UI", sc(10)),
            background=field_bg,
            foreground=fg_color,
            insertbackground=fg_color,
            highlightbackground=border_color,
            bd=1,
            relief="solid"
        )
        text_area.pack(side="left", fill="both", expand=True)
        text_scroll.config(command=text_area.yview)
        
        text_area.insert("1.0", "\n".join(self.ignored_words))
        
        vars_frame = ttk.Frame(win)
        vars_frame.pack(fill="x", padx=15, pady=10)
        
        local_vars_var = tk.BooleanVar(value=self.ignored_words_variations.get())
        cb = ttk.Checkbutton(
            vars_frame, 
            text="Include variations (ignore capitalization, punctuation, extra spacing)",
            variable=local_vars_var
        )
        cb.pack(anchor="w")
        
        btn_frame = ttk.Frame(win, padding=10)
        btn_frame.pack(fill="x", side="bottom")
        
        def on_save():
            content = text_area.get("1.0", tk.END).strip()
            words = [line.strip() for line in content.split("\n") if line.strip()]
            self.ignored_words = words
            self.ignored_words_variations.set(local_vars_var.get())
            self.save_ignored_words()
            
            if hasattr(self, "_history_cache"):
                self._history_cache.clear()
                
            if hasattr(self, "history_window") and self.history_window and self.history_window.winfo_exists():
                show_all = getattr(self.history_window, "local_show_all", False)
                self.history_window.destroy()
                self.open_historical_suggestions(show_all_override=show_all)
                
            win.destroy()
            
        ttk.Button(btn_frame, text="Save", command=on_save).pack(side="right", padx=5)
        ttk.Button(btn_frame, text="Cancel", command=win.destroy).pack(side="left", padx=5)

