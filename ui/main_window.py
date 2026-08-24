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
from ui.unified_settings import open_unified_settings
from ui.location_panel import create_location_panel
from ui.dashboard import DashboardMixin
from ui.database_ops import DatabaseOpsMixin
from ui.log_viewer import LogViewerMixin

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import os
import sys
import re
import time
import math
from datetime import datetime

import pandas as pd
import getpass
import utils

# Pre-compiled regex patterns for speed optimization
_NUMERIC_OID_PATTERN = re.compile(r"\b(\d+)\b")
_NORMALIZE_NON_WORD_PATTERN = re.compile(r'[^\w\s]')
_NORMALIZE_SPACE_PATTERN = re.compile(r'\s+')

import uuid

from collections import OrderedDict
import config
from config import sc
from repository import ExcelRepository, REVIEWED_COLUMN, REVIEWED_AT_COLUMN
from models import AppState
from utils import debug_error

def is_light_color(color, widget=None):
    if not color:
        return True
    try:
        if widget:
            r_16, g_16, b_16 = widget.winfo_rgb(color)
            r, g, b = r_16 // 256, g_16 // 256, b_16 // 256
        else:
            hex_color = color.lstrip('#')
            if len(hex_color) == 3:
                hex_color = "".join(c*2 for c in hex_color)
            r, g, b = int(hex_color[0:2], 16), int(hex_color[2:4], 16), int(hex_color[4:6], 16)
    except Exception:
        return True
    brightness = (r * 299 + g * 587 + b * 114) / 1000
    return brightness > 127

def adjust_color_brightness(color, factor, widget=None):
    if not color:
        return "#ffffff"
    try:
        if widget:
            r_16, g_16, b_16 = widget.winfo_rgb(color)
            r, g, b = r_16 // 256, g_16 // 256, b_16 // 256
        else:
            hex_color = color.lstrip('#')
            if len(hex_color) == 3:
                hex_color = "".join(c*2 for c in hex_color)
            r, g, b = int(hex_color[0:2], 16), int(hex_color[2:4], 16), int(hex_color[4:6], 16)
    except Exception:
        return color
    
    r = max(0, min(255, int(r * (1 + factor))))
    g = max(0, min(255, int(g * (1 + factor))))
    b = max(0, min(255, int(b * (1 + factor))))
    
    return f"#{r:02x}{g:02x}{b:02x}"

def make_tk_button_hoverable(btn, hover_bg=None, hover_fg=None):
    orig_bg = btn.cget("bg")
    orig_fg = btn.cget("fg")
    
    if not hover_bg:
        active_bg = btn.cget("activebackground")
        if active_bg and active_bg != orig_bg:
            hover_bg = active_bg
        else:
            hover_bg = adjust_color_brightness(orig_bg, -0.1 if is_light_color(orig_bg, btn) else 0.1, btn)
            
    btn._orig_bg = orig_bg
    btn._orig_fg = orig_fg
    btn._hover_bg = hover_bg
    btn._hover_fg = hover_fg
    
    def on_enter(e):
        if btn.cget("state") != "disabled":
            h_bg = getattr(btn, "_hover_bg", hover_bg)
            h_fg = getattr(btn, "_hover_fg", hover_fg)
            if h_bg:
                btn.config(bg=h_bg)
            if h_fg:
                btn.config(fg=h_fg)

    def on_leave(e):
        if btn.cget("state") != "disabled":
            o_bg = getattr(btn, "_orig_bg", orig_bg)
            o_fg = getattr(btn, "_orig_fg", orig_fg)
            btn.config(bg=o_bg, fg=o_fg)

    btn.bind("<Enter>", on_enter, add="+")
    btn.bind("<Leave>", on_leave, add="+")

def _apply_hover_to_all_tk_buttons(parent, main_ui=None):
    for child in parent.winfo_children():
        if child.winfo_class() == "Button":
            if main_ui and child == getattr(main_ui, "reviewed_button", None):
                pass
            else:
                make_tk_button_hoverable(child)
        _apply_hover_to_all_tk_buttons(child, main_ui)

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

# BulkEditWindow, NewDatabaseWizard, AddObjectsWizard, ZoomableImagePopup, and
# requests are imported lazily inside the methods that need them so that startup
# time is not spent loading unused subsystems.

MAX_IMAGE_CACHE = 40



class ToolTipManager:
    def __init__(self, delay=500):
        self.delay = delay
        self._id = None
        self.tooltip = None

    def enter(self, w, t, is_dark, e):
        self.schedule(w, t, is_dark, e)

    def leave(self, w, e):
        self.unschedule(w)
        self.hide()

    def schedule(self, w, t, is_dark, e):
        self.unschedule(w)
        x = e.x_root + 15
        y = e.y_root + 15
        self._id = w.after(self.delay, lambda: self.show(w, t, is_dark, x, y))

    def unschedule(self, w):
        if self._id:
            w.after_cancel(self._id)
            self._id = None

    def show(self, w, t, is_dark, x, y):
        self.hide()
        self.tooltip = tk.Toplevel(w)
        self.tooltip.wm_overrideredirect(True)
        self.tooltip.wm_geometry(f"+{x}+{y}")

        from config import sc
        bg_col = "#1e1e2d" if is_dark else "#f2f5f1"
        fg_col = "#ffffff" if is_dark else "#000000"
        border_col = "#444748" if is_dark else "#cccccc"

        lbl = tk.Label(self.tooltip, text=t,
                       background=bg_col, foreground=fg_col,
                       font=("Inter", sc(9)),
                       padx=sc(6), pady=sc(4),
                       borderwidth=1, relief="solid", highlightbackground=border_col)
        lbl.pack()

    def hide(self):
        if self.tooltip:
            try:
                self.tooltip.destroy()
            except tk.TclError:
                pass
            self.tooltip = None



class ObjectProgramUI(
    AutosaveMixin,
    ImageHandlerMixin,
    HistoricalSuggestionsMixin,
    LayoutSettingsMixin,
    DashboardMixin,
    DatabaseOpsMixin,
    LogViewerMixin
):
# ---------- UI helpers ----------

    def _has_history(self, oid) -> bool:
        presence = getattr(self, "_history_presence_set", None)
        if presence is not None:
            return oid in presence or str(oid) in presence
        return False

    def _problems_have_history(self, oid) -> bool:
        sug = getattr(self, "_has_suggestions_set", None)
        if sug is None:
            return False   # scan not complete yet
        return oid in sug or str(oid) in sug

    def save_user_pref(self, key, value):
        import config
        prefs = config.load_prefs()
        prefs[key] = value
        config.save_prefs(prefs)
        setattr(self, key, value)

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
        
        import config
        _init_prefs = config.load_prefs() or {}
        
        self.left_pinned = tk.BooleanVar(value=_init_prefs.get("left_pinned", True))
        self._drawer_anim_job = None
        self._drawer_current_width = 0
        self._drawer_is_open = False

        self.show_list_var = tk.BooleanVar(value=_init_prefs.get("show_list", True))
        self.show_search_var = tk.BooleanVar(value=_init_prefs.get("show_search", True))
        self.show_images_var = tk.BooleanVar(value=_init_prefs.get("show_images", True))
        self.location_in_center_var = tk.BooleanVar(value=_init_prefs.get("location_in_center", False))
        self.show_image_tools_var = tk.BooleanVar(value=_init_prefs.get("show_image_tools", True))
        self.show_bulk_edit_var = tk.BooleanVar(value=_init_prefs.get("show_bulk_edit", True))
        self.show_reg_var = tk.BooleanVar(value=_init_prefs.get("show_reg", True))
        
        self.snap_lock_var = tk.BooleanVar(value=_init_prefs.get("snap_lock", False))
        self.image_stack_var = tk.BooleanVar(value=_init_prefs.get("image_stack", False))
        self.focus_dynamic_update_var = tk.BooleanVar(value=_init_prefs.get("focus_dynamic_update", True))
        self.layout_dynamic_update_var = tk.BooleanVar(value=_init_prefs.get("layout_dynamic_update", True))
        self.large_reviewed_button_var = tk.BooleanVar(value=_init_prefs.get("large_reviewed_button", True))
        self.auto_advance_var = tk.BooleanVar(value=_init_prefs.get("auto_advance_on_review", True))
        self.auto_advance_history_var = tk.BooleanVar(value=_init_prefs.get("auto_advance_history", False))
        self.auto_resolve_conflicts_var = tk.BooleanVar(value=_init_prefs.get("auto_resolve_conflicts", False))
        self.strict_input_validation_var = tk.BooleanVar(value=_init_prefs.get("strict_input_validation", False))

        def _on_auto_advance_changed(*args):
            try:
                import config
                p = config.load_prefs() or {}
                p["auto_advance_on_review"] = self.auto_advance_var.get()
                config.save_prefs(p)
            except Exception:
                pass

        def _on_auto_advance_history_changed(*args):
            try:
                import config
                p = config.load_prefs() or {}
                p["auto_advance_history"] = self.auto_advance_history_var.get()
                config.save_prefs(p)
            except Exception:
                pass

        self.auto_advance_var.trace_add("write", _on_auto_advance_changed)
        self.auto_advance_history_var.trace_add("write", _on_auto_advance_history_changed)



        self.image_render_cache = OrderedDict()
        self.dark_mode_active = False
        if getattr(sys, 'frozen', False):
            _app_base_dir = os.path.dirname(sys.executable)
        else:
            _app_base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.ignored_words_file = os.path.join(_app_base_dir, "ignored_words.json")
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
            "saved":     {"bg": "#d4edda", "fg": "#155724"},
            "saving":    {"bg": "#e8f4fd", "fg": "#1565c0"},   # U2-F: zero-latency "Saving…" state
            "autosaved": {"bg": "#e2f0fe", "fg": "#0a58ca"},
            "unsaved":   {"bg": "#fff3cd", "fg": "#856404"},
            "error":     {"bg": "#f8d7da", "fg": "#721c24"}
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
        self._search_index_cache = None

        from backend.search import SearchEngine
        from backend.filter import FilterManager
        self.search_engine = SearchEngine()
        self.filter_manager = FilterManager()

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
        
        # Database Statistics shortcut
        self.root.bind("<Control-j>", lambda e: self.show_statistics())
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

        self.root.bind("<Control-q>", self.toggle_focus_mode_shortcut)
        self.root.bind("<Control-h>", self.open_history_shortcut)

        self.root.bind("<Control-e>", self._focus_first_reg)
        self.root.bind("<Control-Prior>", lambda e: self._switch_reg_tab(-1))
        self.root.bind("<Control-Next>", lambda e: self._switch_reg_tab(1))

        


        self.root.bind("<Control-l>", self._focus_first_location)
        self.root.bind("<Control-p>", self._focus_first_problem)
        self.root.bind("<Control-i>", self._focus_first_reg)
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
        self.root.bind("<Alt-r>", lambda e: self.rotate_image())
        self.root.bind("<Control-R>", lambda e: self.rotate_image())
        self.root.bind("<Control-Key-0>", lambda e: self.reset_image_view())


        self.root.bind("<Control-Delete>", self._shortcut_delete_object)
        self.root.bind("<Control-Shift-N>", self._shortcut_quick_new_object)
        self.root.bind("<Control-Shift-D>", self._shortcut_duplicate_object)
        self.root.bind("<Control-Shift-C>", self._copy_field_value)
        self.root.bind("<Control-Shift-V>", self._paste_field_value)

        self.root.bind("<Control-k>", self._apply_default_data_preset_shortcut)
        self.root.bind("<Control-K>", self._apply_default_data_preset_shortcut)

        self.root.bind("<Control-o>", self.handle_ctrl_o)
        self.root.bind("<Control-O>", self.handle_ctrl_o)

        self.root.bind("<Control-f>", self.handle_ctrl_f)
        self.root.bind("<Control-F>", self.handle_ctrl_f)

        # Collapsible Panel Toggles for Laptop Views
        self.root.bind("<F6>", self.toggle_list_panel_shortcut)
        self.root.bind("<F7>", self.toggle_reg_panel_shortcut)
        self.root.bind("<F8>", self.toggle_images_panel_shortcut)



        self._skip_validation_once = False


        self.field_undo_stack = []
        self.loaded_problem_states = {}

        if self.app.redo_stacks is None:
            self.app.redo_stacks = {}

        self.loading_object = False
        self.initializing = True


        self.object_id_var = tk.StringVar()
        self._init_focus_prefs()
        self.data_presets_menu = tk.Menu(self.root, tearoff=0)
        self.load_data_preset_menu = tk.Menu(self.data_presets_menu, tearoff=0)
        self.data_presets_menu.add_command(label="Save Current Fields as Preset...", command=self.save_data_preset_dialog)
        self.data_presets_menu.add_cascade(label="Load Preset", menu=self.load_data_preset_menu)
        self._refresh_load_data_preset_menu()
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

        # U2-E: Automatically apply hover to all tk.Button elements in main UI
        _apply_hover_to_all_tk_buttons(self.root, self)
        self._apply_pin_state()


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

            if "maps_to" in field and field["maps_to"] and field["maps_to"] != "Other" and name != "Other_problem":
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
            
        self.focus_mode_var.set(prefs.get("focus_mode", prefs.get("focus_mode_active", False)))
        self.focus_fallback_var.set(prefs.get("focus_fallback", True))
        
        saved_vis = prefs.get("focus_visibility", {})
        
        self.focus_visibility_vars["Problems"] = tk.BooleanVar(value=saved_vis.get("Problems", prefs.get("focus_sec_problems", True)))
        self.focus_visibility_vars["Location"] = tk.BooleanVar(value=saved_vis.get("Location", prefs.get("focus_sec_location", True)))
        
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
        
        is_dark = getattr(self, "dark_mode_active", False)
        # Determine theme colors
        lbl_fg = "#a6adc8" if is_dark else "#444748"
        entry_bg = "#2a2b3c" if is_dark else "#ffffff"
        entry_fg = "#e8ebe9" if is_dark else "#000000"
        entry_insert = "#e8ebe9" if is_dark else "#000000"
        cb_fg = "#e8ebe9" if is_dark else "#000000"
        cb_active_bg = "#181c19" if is_dark else bg_col
        cb_active_fg = "#e8ebe9" if is_dark else "#000000"
        
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
                bg=bg_col, fg=cb_fg,
                font=("JetBrains Mono", sc(font_size), "bold"),
                activebackground=cb_active_bg,
                activeforeground=cb_active_fg,
                selectcolor=bg_col,
                highlightthickness=0, bd=0
            , cursor="hand2")
            cb.pack(side="left")
            widget = cb
        else:
            if is_horiz:
                # Label on top
                lbl = tk.Label(container, text=name.upper(), font=("JetBrains Mono", sc(font_size-2), "bold"),
                             bg=bg_col, fg=lbl_fg, anchor="w")
                lbl.pack(fill="x", pady=(0,2))
            else:
                # Label on left
                lbl = tk.Label(container, text=name.upper(), width=14, font=("JetBrains Mono", sc(font_size), "bold"),
                             bg=bg_col, fg=lbl_fg, anchor="w")
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
                , cursor="hand2")
                widget.bind("<<ComboboxSelected>>", lambda e: self.commit_current_object())
                if is_horiz:
                    widget.pack(fill="x", expand=True, ipady=sc(3))
                else:
                    widget.pack(side="left", fill="x", expand=True, ipady=sc(3))
            else:
                entry_container = tk.Frame(container, bg=bg_col)
                widget = tk.Entry(
                    entry_container, textvariable=var,
                    state="disabled" if field_def.get("readonly") else "normal",
                    font=(font_family, sc(font_size)),
                    bg=entry_bg, fg=entry_fg,
                    insertbackground=entry_insert,
                    highlightthickness=1, highlightbackground=bd_col, highlightcolor=entry_bg,
                    relief="flat"
                )
                widget.pack(fill="x", expand=True, ipady=sc(3))
                
                focus_line = tk.Frame(entry_container, height=sc(2), bg=bg_col)
                focus_line.pack(fill="x", side="bottom")
                
                def make_focus_handlers(w, fl, ec, default_bg):
                    def on_focus_in(e):
                        is_dark = self.dark_mode_active if hasattr(self, "dark_mode_active") else False
                        fl.configure(bg="#a6e3a1" if is_dark else "#3a7d44")
                    def on_focus_out(e):
                        fl.configure(bg=default_bg)
                    w.bind("<FocusIn>", on_focus_in, add="+")
                    w.bind("<FocusOut>", on_focus_out, add="+")
                    
                make_focus_handlers(widget, focus_line, entry_container, bg_col)
                
                widget.bind("<FocusOut>", lambda e: self.commit_current_object())
                
                if is_horiz:
                    entry_container.pack(fill="x", expand=True)
                else:
                    entry_container.pack(side="left", fill="x", expand=True)
        
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
        , cursor="hand2")
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
        is_dark = getattr(self, "dark_mode_active", False)
        self.location_panel = create_location_panel(
            self.location_frame,
            mode="vertical",
            location_vars=self.location_vars,
            config_ref=getattr(self.app, "config", None),
            live_callbacks={"on_commit": lambda *args: self.commit_current_object()},
            dark_mode=is_dark
        )
        self.location_panel.pack(fill="both", expand=True)
        if hasattr(self.location_panel, "field_entries"):
            for w in self.location_panel.field_entries:
                self.location_entries.append(w)

    def _build_horizontal_location_ui(self):
        import config
        prefs = config.load_prefs() or {}
        is_dark = getattr(self, "dark_mode_active", False)
        mode = "horizontal_2row" if prefs.get("location_2row", False) else "horizontal_1row"
        self.location_panel_horiz = create_location_panel(
            self.loc_frame_horizontal,
            mode=mode,
            location_vars=self.location_vars,
            config_ref=getattr(self.app, "config", None),
            live_callbacks={"on_commit": lambda *args: self.commit_current_object()},
            dark_mode=is_dark
        )
        self.location_panel_horiz.pack(fill="both", expand=True)
        if hasattr(self.location_panel_horiz, "field_entries"):
            for w in self.location_panel_horiz.field_entries:
                self.location_entries.append(w)



    def refresh_gbif_button(self):
        if not hasattr(self, "gbif_btn"): return
        import config
        prefs = config.load_prefs()
        show_gbif = prefs.get("enable_gbif", False)
        if show_gbif:
            self.gbif_btn.pack(side="right", padx=6)
        else:
            self.gbif_btn.pack_forget()

    def check_gbif_action(self):
        if not self.app.current_object_id:
            return

        genus = self.reg_vars.get("Genus", tk.StringVar()).get().strip()
        species = self.reg_vars.get("Species", tk.StringVar()).get().strip()

        if not genus and not species:
            messagebox.showinfo("GBIF Check", "Genus and Species are empty.", parent=self.root)
            return

        import threading

        def run_check():
            import backend.gbif
            result = backend.gbif.check_gbif(genus, species)
            self.root.after(0, lambda: self._on_gbif_result(result, genus, species))

        self.show_inline_banner("Checking GBIF...", "info", "🔍")
        threading.Thread(target=run_check, daemon=True).start()

    def _on_gbif_result(self, result, old_genus, old_species):
        self.hide_banner()
        if not result:
            messagebox.showwarning("GBIF Check", "Could not find a match for this scientific name or an error occurred.", parent=self.root)
            return

        old_author = self.reg_vars.get("Author", tk.StringVar()).get().strip()

        import tkinter.messagebox as mb

        # If it's a synonym, fetch the accepted name and then prompt to update
        if result.get("synonym") and result.get("acceptedUsageKey"):
            import backend.gbif
            def fetch_accepted():
                acc = backend.gbif.get_accepted_name(result["acceptedUsageKey"])
                self.root.after(0, lambda: self._prompt_synonym_update(acc, old_genus, old_species, old_author))
            self.show_inline_banner("Fetching accepted name...", "info", "🔄")
            import threading
            threading.Thread(target=fetch_accepted, daemon=True).start()
            return

        # Match found, check for differences
        new_genus = result.get("genus", "")
        new_species = result.get("species", "")
        new_author = result.get("author", "")

        # GBIF can sometimes return canonical name in species if the rank is species.
        # But if we searched for Quercus robur, the species is 'Quercus robur'.
        # However if we searched for 'Aster novae-angliae', it might return that as species.

        # If we have a fuzzy match or a different spelling
        if result.get("matchType") in ("FUZZY",) or (new_genus and new_genus.lower() != old_genus.lower()) or (new_species and new_species.lower() != old_species.lower() and new_species != f"{old_genus} {old_species}".strip()):
            ans = mb.askyesno("GBIF Spelling Update",
                f"Found a match with a different spelling:\n\nCurrent: {old_genus} {old_species}\nGBIF: {new_genus} {new_species}\n\nUpdate to GBIF spelling?", parent=self.root)
            if ans:
                self._apply_gbif_update(result, False, old_genus, old_species, old_author)
            elif new_author and new_author != old_author:
                 # Even if they refuse the spelling update, ask about author
                 self._prompt_author_update(new_author, old_author, old_genus, old_species)
            return

        # If it's an exact match but the author is different/missing
        if new_author and new_author != old_author:
            self._prompt_author_update(new_author, old_author, old_genus, old_species)
        elif result.get("matchType") == "EXACT":
            mb.showinfo("GBIF Check", f"Name is up to date and valid.\nMatch: {result.get('scientificName')}", parent=self.root)
        else:
             mb.showinfo("GBIF Check", f"Match found (Type: {result.get('matchType')}).\nMatch: {result.get('scientificName')}", parent=self.root)

    def _prompt_synonym_update(self, acc_result, old_genus, old_species, old_author):
        self.hide_banner()
        if not acc_result:
            import tkinter.messagebox as mb
            mb.showwarning("GBIF Check", "Could not fetch accepted name.", parent=self.root)
            return

        new_genus = acc_result.get("genus", "")
        new_species = acc_result.get("species", "")
        new_author = acc_result.get("author", "")

        import tkinter.messagebox as mb
        ans = mb.askyesno("GBIF Synonym Detected",
            f"The name '{old_genus} {old_species}' is a synonym.\n\n"
            f"Accepted name:\n{new_genus} {new_species} {new_author}\n\n"
            f"Would you like to update to this accepted name?", parent=self.root)

        if ans:
            self._apply_gbif_update(acc_result, True, old_genus, old_species, old_author)

    def _prompt_author_update(self, new_author, old_author, old_genus="", old_species=""):
        import tkinter.messagebox as mb
        ans = mb.askyesno("GBIF Author Update",
            f"Update Author?\n\n" \
            f"Current: {old_author or '(Empty)'}\n"
            f"GBIF: {new_author}", parent=self.root)
        if ans:
            if "Author" in self.reg_vars:
                self.reg_vars["Author"].set(new_author)

            # preserve original author
            if old_author:
                old_name = f"{old_genus} {old_species} {old_author}".strip()
                comment_var = self.reg_vars.get("Comment")
                if comment_var and "Comment" in self.reg_entries:
                    text_widget = self.reg_entries["Comment"]
                    current_text = text_widget.get("1.0", tk.END).strip()
                    note = f"Author updated from: {old_name}."
                    if current_text:
                        text_widget.insert(tk.END, "\n" + note)
                    else:
                        text_widget.insert("1.0", note)

            self.commit_current_object()
            self.show_inline_banner("Author updated.", "success", "✓")

    def _apply_gbif_update(self, result, is_synonym_update, old_genus, old_species, old_author):
        if not result:
            self.hide_banner()
            return

        new_genus = result.get("genus", "")
        new_species = result.get("species", "")
        new_author = result.get("author", "")

        # Extract species epithet if species is full canonical name
        if new_genus and new_species and new_species.startswith(new_genus + " "):
             new_species = new_species[len(new_genus):].strip()

        if "Genus" in self.reg_vars and new_genus:
            self.reg_vars["Genus"].set(new_genus)
        if "Species" in self.reg_vars and new_species:
            self.reg_vars["Species"].set(new_species)
        if "Author" in self.reg_vars and new_author:
            self.reg_vars["Author"].set(new_author)

        # Always add a comment to preserve original name including author
        old_name = f"{old_genus} {old_species} {old_author}".strip()
        comment_var = self.reg_vars.get("Comment")
        if comment_var and "Comment" in self.reg_entries:
            text_widget = self.reg_entries["Comment"]
            current_text = text_widget.get("1.0", tk.END).strip()
            note = f"Updated from synonym: {old_name}." if is_synonym_update else f"Updated spelling from: {old_name}."
            if current_text:
                text_widget.insert(tk.END, "\n" + note)
            else:
                text_widget.insert("1.0", note)

        self.commit_current_object()
        self.hide_banner()
        self.show_inline_banner("Taxonomy updated from GBIF.", "success", "✓")


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
        fg_color = "#e8ebe9" if is_dark else "#2c302e"
        
        # Create a single tab container for Specimen Audit
        tab_container = ttk.Frame(self.reg_notebook)
        
        # Scrollable canvas inside the tab container
        tab_canvas = tk.Canvas(tab_container, highlightthickness=0, bg="#1e1e2d" if is_dark else "#fbfaf8")
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
            lambda e, tc=tab_canvas, twid=tab_win_id: tc.itemconfig(twid, width=e.width) if getattr(tc, "_last_width", None) != e.width and not setattr(tc, "_last_width", e.width) else None
        )

        # Mousewheel scrolling specific to this tab
        def _make_mousewheel_scroller(canvas):
            return lambda e: canvas.yview_scroll(int(-1*(e.delta/120)), "units")

        mw_scroller = _make_mousewheel_scroller(tab_canvas)
        tab_container.bind("<Enter>", lambda e, mws=mw_scroller: tab_container.bind_all("<MouseWheel>", mws))
        tab_container.bind("<Leave>", lambda e: tab_container.unbind_all("<MouseWheel>"))

        tab_canvas.pack(side="left", fill="both", expand=True)
        tab_scroll.pack(side="right", fill="y")

        self._reg_tabs["General Data"] = {
            "container": tab_container,
            "canvas": tab_canvas,
            "frame": tab_frame,
            "fields": all_fields
        }

        self.reg_notebook.add(tab_container, text="General Data")

        # Create O(1) lookup dictionary for registration config
        reg_config_dict = {f["name"]: f for f in self.app.config.get("ui_sections", {}).get("registration", [])}

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
            
            if card_id == "taxonomy":
                import config
                prefs = config.load_prefs()
                show_gbif = prefs.get("enable_gbif", False)

                self.gbif_btn = tk.Label(header_frame, text="🔍 Check GBIF", font=("Segoe UI", sc(9), "bold"), bg="#2b8a3e", fg="#ffffff", cursor="hand2", padx=6, pady=2)
                if show_gbif:
                    self.gbif_btn.pack(side="right", padx=6)
                self.gbif_btn.bind("<Button-1>", lambda e: self.check_gbif_action())
                self.gbif_btn.bind("<Enter>", lambda e, w=self.gbif_btn: w.config(bg="#3bc954"))
                self.gbif_btn.bind("<Leave>", lambda e, w=self.gbif_btn: w.config(bg="#2b8a3e"))

            # Card content area
            body_frame = tk.Frame(card_frame, bg=card_bg, padx=12, pady=12)
            body_frame.pack(fill="x")
            
            body_frame.columnconfigure(0, weight=1)
            
            current_row = 0
            for fname in fields_to_render:
                field = reg_config_dict.get(fname)
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
                    , cursor="hand2")
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
                lbl = tk.Label(frame, text=name, width=15, anchor="w", font=("Hanken Grotesk", sc(10), "bold"), bg=card_bg, fg=fg_color)
                lbl.grid(row=0, column=1, sticky="w", padx=(0, 6))
                if prob_col:
                    self.prob_label_widgets[name] = lbl

                # Col 2: input widget based on type
                if ftype == "choice":
                    choices = field.get("choices", [])
                    if "" not in choices:
                        choices = [""] + choices
                    widget = ttk.Combobox(frame, textvariable=var, values=choices, cursor="hand2")
                    widget.bind("<<ComboboxSelected>>", lambda e: self.commit_current_object())
                elif ftype == "checkbox":
                    widget = ttk.Checkbutton(
                        frame,
                        text="",
                        variable=var,
                        onvalue="True",
                        offvalue="False",
                        command=lambda n=name, v=var: self._on_checkbox_change(n, v)
                    , cursor="hand2")
                elif ftype == "multiline" or name in ("Conservation Status", "Observation", "Comment", "ProblemDescription", "Problem Description"):
                    widget = tk.Text(
                        frame, height=3,
                        relief="flat", bd=0,
                        highlightthickness=1, highlightbackground=border_color,
                        highlightcolor="#000000" if not is_dark else "#e8ebe9",
                        insertbackground="#000000" if not is_dark else "#e8ebe9",
                        bg="#ffffff" if not is_dark else "#212622",
                        fg="#2c302e" if not is_dark else "#e8ebe9",
                        font=("Hanken Grotesk", sc(10)),
                        undo=True, maxundo=-1, autoseparators=True
                    )
                    def bind_text_events(w):
                        w.bind("<KeyRelease>", self._on_text_change)
                        w.bind("<FocusOut>", lambda e: self.commit_current_object(), add="+")
                    bind_text_events(widget)
                else:
                    entry_container = tk.Frame(frame, bg=card_bg)
                    widget = tk.Entry(
                        entry_container, textvariable=var,
                        relief="flat", bd=0,
                        highlightthickness=1, highlightbackground=border_color,
                        highlightcolor="#ffffff" if is_dark else "#f2f5f1",
                        insertbackground="#000000" if not is_dark else "#e8ebe9",
                        bg="#ffffff" if not is_dark else "#212622",
                        fg="#2c302e" if not is_dark else "#e8ebe9",
                        font=("Hanken Grotesk", sc(10))
                    )
                    widget.pack(fill="x", expand=True, ipady=sc(3))
                    
                    focus_line = tk.Frame(entry_container, height=sc(2), bg=card_bg)
                    focus_line.pack(fill="x", side="bottom")
                    
                    def make_focus_handlers(w, fl, ec, default_bg):
                        def on_focus_in(e):
                            is_dark = getattr(self, "dark_mode_active", False)
                            fl.configure(bg="#a6e3a1" if is_dark else "#3a7d44")
                        def on_focus_out(e):
                            fl.configure(bg=default_bg)
                        w.bind("<FocusIn>", on_focus_in, add="+")
                        w.bind("<FocusOut>", on_focus_out, add="+")
                        
                    make_focus_handlers(widget, focus_line, entry_container, card_bg)

                    widget.bind("<KeyRelease>", lambda e, n=name, w=widget: self._on_autocomplete_key(e, n, w), add="+")
                    widget.bind("<KeyRelease>", lambda e: self.root.after(500, self._validate_fields), add="+")
                    widget.bind("<FocusOut>", lambda e, n=name, w=widget: self._run_fuzzy_match(n, w), add="+")
                    widget.bind("<FocusOut>", lambda e: self.commit_current_object(), add="+")

                    if field.get("readonly"):
                        widget.configure(state="disabled")

                self.reg_entries[name] = widget
                self.reg_entry_list.append(widget)

                # Correctly place the widget or its container based on the type
                if ftype == "multiline" or name in ("Conservation Status", "Observation", "Comment", "ProblemDescription", "Problem Description"):
                    widget.grid(row=0, column=2, sticky="ew", pady=sc(2))
                elif ftype in ("choice", "checkbox"):
                    widget.grid(row=0, column=2, sticky="ew")
                else:
                    entry_container.grid(row=0, column=2, sticky="ew")

                # Bind general keys
                widget.bind("<Shift-Up>", self._reg_nav_up)
                widget.bind("<Shift-Down>", self._reg_nav_down)
                widget.bind("<Control-Up>", self._reg_nav_up)
                widget.bind("<Control-Down>", self._reg_nav_down)
                if ftype != "multiline":
                    widget.bind("<Return>", self._reg_nav_down)

                frame.columnconfigure(0, minsize=sc(28), weight=0)
                frame.columnconfigure(1, minsize=sc(120), weight=0)
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
            lambda e, tc=tab_canvas, twid=tab_win_id: tc.itemconfig(twid, width=e.width) if getattr(tc, "_last_width", None) != e.width and not setattr(tc, "_last_width", e.width) else None
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
                command=lambda: (
                    self.update_reg_fields_visibility(skip_snap=True),
                    self.commit_current_object()
                )
            , cursor="hand2")
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
            except Exception:
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

    def _get_active_location_entries(self):
        is_center = hasattr(self, "location_in_center_var") and self.location_in_center_var.get()
        panel = getattr(self, "location_panel_horiz", None) if is_center else getattr(self, "location_panel", None)
        if panel and hasattr(panel, "field_entries") and panel.field_entries:
            return panel.field_entries
        if self.location_entries:
            visible = [w for w in self.location_entries if w.winfo_exists() and w.winfo_ismapped()]
            if visible:
                return visible
            return self.location_entries
        return []

    def _focus_first_location(self, event=None):
        entries = self._get_active_location_entries()
        if entries:
            entries[0].focus_set()
        elif self.location_entries:
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
        entries = self._get_active_location_entries()
        for i, w in enumerate(entries if entries else self.location_entries):
            if w == current:
                return i
        return None

    def _location_nav_down(self, event):
        entries = self._get_active_location_entries()
        self._navigate_list(entries if entries else self.location_entries, 1)
        return "break"

    def _location_nav_up(self, event):
        entries = self._get_active_location_entries()
        self._navigate_list(entries if entries else self.location_entries, -1)
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
        if isinstance(widget, (tk.Entry, ttk.Entry, tk.Text, ttk.Combobox)):
            return

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

        from models import MAX_UNDO_PER_OBJECT  # P1-F: single constant, no scattered literals
        stack = self.app.undo_stacks.setdefault(oid, [])

        stack.append(state)

        total = sum(len(v) for v in self.app.undo_stacks.values())

        if total > 500:
            for k in self.app.undo_stacks:
                self.app.undo_stacks[k] = self.app.undo_stacks[k][-MAX_UNDO_PER_OBJECT:]

        if len(stack) > MAX_UNDO_PER_OBJECT:
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
            threading.Thread(
                target=self._prescan_suggestions_worker,
                daemon=True
            ).start()





    def _get_reg_by_id(self, db):
        if not db:
            return None
        if db.get("reg_by_id") is None:
            df_reg = db.get("df_reg")
            if df_reg is None or not isinstance(df_reg, pd.DataFrame):
                return None
            try:
                if "ObjectID" in df_reg.columns:
                    db["reg_by_id"] = df_reg.set_index("ObjectID")
                else:
                    db["reg_by_id"] = df_reg
            except Exception:
                return None

        return db.get("reg_by_id")


       


#----- tool tips

    def add_tooltip(self, widget, text):
        if not hasattr(self, "_tooltip_manager"):
            self._tooltip_manager = ToolTipManager()

        is_dark = getattr(self, "dark_mode_active", False)
        widget.bind("<Enter>", lambda e, w=widget, t=text, d=is_dark: self._tooltip_manager.enter(w, t, d, e))
        widget.bind("<Leave>", lambda e, w=widget: self._tooltip_manager.leave(w, e))
        widget.bind("<ButtonPress>", lambda e, w=widget: self._tooltip_manager.leave(w, e), add="+")

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
        FieldGroupEditorDialog(self.root, all_fields, current_groups, _on_save, self.app)




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
        from ui.add_objects import AddObjectsWizard
        AddObjectsWizard(self.root, self.app, self)
        
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
        fg_col = "#e8ebe9" if is_dark else "#2c302e"
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
            self.app.df_reg = self.app.df_reg.drop(index=oid)
        if self.app.df_obs is not None and oid in self.app.df_obs.index:
            self.app.df_obs = self.app.df_obs.drop(index=oid)
            
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
    
  
        new_reg = self.app.df_reg.loc[[oid]].copy()
        new_reg.index = [new_oid]
        new_reg["ObjectID"] = new_oid
        new_reg["UID"] = uuid.uuid4().hex[:8]

        self.app.df_reg = pd.concat([self.app.df_reg, new_reg])


        new_obs = self.app.df_obs.loc[[oid]].copy()
        new_obs.index = [new_oid]
        new_obs["ProblemDescription"] = ""
        self.app.df_obs = pd.concat([self.app.df_obs, new_obs])


        if not self.app.df_photo.empty and oid in self.app.df_photo.index:
            new_photo = self.app.df_photo.loc[[oid]].copy()
            new_photo.index = [new_oid]
            self.app.df_photo = pd.concat([self.app.df_photo, new_photo])

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
            val = str(var.get()).strip().lower()
            if "Loaned out date" in self.reg_vars:
                if val in ("true", "1"):
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


    def open_advanced_settings(self):
        """Shim: opens the unified settings window on the Advanced tab."""
        self._open_unified("advanced")

    def update_focus_toggle_visibility(self):
        if not hasattr(self, "focus_quick_frame"):
            return
        import config
        advanced_prefs = config.load_prefs().get("advanced", {})
        if advanced_prefs.get("enable_focus_mode_toggle", False):
            self.focus_quick_frame.pack(side="right", padx=(0, 4))
        else:
            self.focus_quick_frame.pack_forget()

    def refresh_image_rendering(self):
        if hasattr(self, "image_render_cache"):
            self.image_render_cache.clear()
        if hasattr(self, "refresh_image_view"):
            try:
                self.refresh_image_view()
            except Exception as e:
                print(f"Error refreshing image view: {e}")

    def refresh_styles_and_highlights(self, enable_hl_override=None, color_override=None):
        if hasattr(self, "apply_theme"):
            try:
                self.apply_theme(enable_hl_override=enable_hl_override, color_override=color_override)
            except Exception as e:
                print(f"Error applying theme: {e}")
        if hasattr(self, "_update_all_problem_row_styles"):
            try:
                self._update_all_problem_row_styles(enable_hl_override=enable_hl_override, color_override=color_override)
            except Exception as e:
                print(f"Error updating problem styles: {e}")

    def show_load_data_preset_popup(self):
        popup = tk.Menu(self.root, tearoff=0)
        import config
        prefs = config.load_prefs()
        saved = prefs.get("data_presets", {})
        if not saved:
            popup.add_command(label="(No saved presets)", state="disabled")
        else:
            for name in sorted(saved.keys()):
                popup.add_command(label=name, command=lambda n=name: self.apply_saved_data_preset(n))
        popup.post(self.root.winfo_pointerx(), self.root.winfo_pointery())

    def show_file_dropdown(self):
        popup = tk.Menu(self.root, tearoff=0)
        popup.add_command(label="New Database", command=self.create_new_database)
        popup.add_command(label="Open Excel", command=self.open_excel)
        popup.add_command(label="Save", command=lambda: self.save_session("SAVE"))
        popup.add_command(label="Save As...", command=self.save_as)
        popup.add_command(label="Export filtered list...", command=self.export_filtered_list)
        popup.add_separator()
        popup.add_command(label="Restore earlier autosave...", command=self.open_autosave_manager)
        popup.add_separator()
        popup.add_command(label="Exit", command=self.on_close)
        popup.post(self.root.winfo_pointerx(), self.root.winfo_pointery())

    def show_data_dropdown(self):
        popup = tk.Menu(self.root, tearoff=0)
        popup.add_command(label="Load Books", command=self.load_books_file)
        popup.add_command(label="Load earlier databases", command=self.load_historical_databases)
        popup.post(self.root.winfo_pointerx(), self.root.winfo_pointery())

    def show_images_dropdown(self):
        popup = tk.Menu(self.root, tearoff=0)
        popup.add_command(label="Image Source", command=self.open_image_menu)
        popup.add_command(label="Toggle image view", command=self.toggle_image_view)
        popup.post(self.root.winfo_pointerx(), self.root.winfo_pointery())

    def show_create_dropdown(self):
        popup = tk.Menu(self.root, tearoff=0)
        popup.add_command(label="New Object", command=self.add_new_object)
        popup.add_command(label="New Database", command=self.create_new_database)
        popup.post(self.root.winfo_pointerx(), self.root.winfo_pointery())



    def _open_unified(self, tab="general"):
        """Open or switch-to-tab the unified settings window."""
        win_ref = getattr(self, "_unified_settings_win", None)
        if win_ref is not None:
            try:
                if win_ref.win.winfo_exists():
                    win_ref.show_tab(tab)
                    win_ref.win.lift()
                    win_ref.win.focus_force()
                    return
            except Exception:
                pass
        self._unified_settings_win = open_unified_settings(
            self.root,
            app_ref=self,
            initial_tab=tab,
            live_callbacks={
                "dark_mode":               self._live_dark_mode,
                "show_list":               lambda v: (self.show_list_var.set(v), self.toggle_list_panel()),
                "show_search":             lambda v: (self.show_search_var.set(v), self.toggle_search_panel()),
                "show_reg":                lambda v: (self.show_reg_var.set(v), self.toggle_reg_panel()),
                "show_images":             lambda v: (self.show_images_var.set(v), self.toggle_images_panel()),
                "location_center":         lambda v: (self.location_in_center_var.set(v), self.toggle_location_panel()),
                "location_2row":           lambda v: self._live_location_2row(v),
                "problem_highlights":      lambda v: self.refresh_styles_and_highlights(enable_hl_override=v),
                "problem_highlight_color": lambda v: self.refresh_styles_and_highlights(color_override=v),
                "large_reviewed_btn":      lambda v: (self.large_reviewed_button_var.set(v), self.update_reviewed_button_state()),
                "snap_lock":               lambda v: self.snap_lock_var.set(v),
                "show_image_tools":        lambda v: (self.show_image_tools_var.set(v), self.toggle_image_tools()),
                "show_bulk_edit":          lambda v: (self.show_bulk_edit_var.set(v), self.toggle_bulk_edit_btn()),
                "image_stack":             lambda v: self._live_image_stack(v),
                "focus_mode":              lambda v: (self.focus_mode_var.set(v), self.update_reg_fields_visibility()),
                "focus_fallback":          lambda v: (self.focus_fallback_var.set(v), self.update_reg_fields_visibility()),
            }
        )
        # Ensure the ref is cleared when the window is closed
        try:
            self._unified_settings_win.win.bind(
                "<Destroy>",
                lambda e, s=self: setattr(s, "_unified_settings_win", None)
                if e.widget == s._unified_settings_win.win else None
            )
        except Exception:
            pass

    def _live_dark_mode(self, value):
        """Live callback: toggle dark mode only when value actually changes."""
        if bool(value) != bool(getattr(self, "dark_mode_active", False)):
            self.toggle_dark_mode()

    def _live_location_2row(self, val):
        mode = "horizontal_2row" if val else "horizontal_1row"
        if hasattr(self, "location_panel_horiz") and hasattr(self.location_panel_horiz, "set_layout_mode"):
            self.location_panel_horiz.set_layout_mode(mode)

    def _live_image_stack(self, val):
        self.image_stack_var.set(val)
        self.image_view_mode = "stack" if val else "gallery"
        if hasattr(self, "update_image_view_button"):
            self.update_image_view_button()
        if hasattr(self, "refresh_image_view"):
            self.refresh_image_view()

    def batch_set_reviewed_true(self):
        self._batch_set_reviewed(True)

    def batch_set_reviewed_false(self):
        self._batch_set_reviewed(False)



    def open_settings_window(self):
        """Shim: opens the unified settings window on the General tab."""
        self._open_unified("general")



    def open_help_window(self):
        if hasattr(self, "help_win") and self.help_win and self.help_win.winfo_exists():
            self.help_win.focus_force()
            self.help_win.focus_set()
            self.help_win.lift()
            return
            
        win = tk.Toplevel(self.root)
        self.help_win = win
        win.title("Help Center")
        win.resizable(True, True)
        win.transient(self.root)
        
        import utils
        # Size of the dialog
        w_width = sc(400)
        w_height = sc(320)
        utils.center_and_fit_toplevel(win, w_width, w_height)
        
        bg_color = "#181c19" if self.dark_mode_active else "#f2f5f1"
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
            foreground="#2c302e" if not self.dark_mode_active else "#e8ebe9"
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
        except Exception:
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

        if isinstance(widget, tk.Text):
            try:
                widget.edit_undo()
            except tk.TclError:
                pass
            return "break"

        if isinstance(widget, (tk.Entry, ttk.Entry)):
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
                try:
                    widget.edit_reset()
                except tk.TclError:
                    pass
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
        from models import MAX_UNDO_PER_OBJECT  # P1-F
        ustack = self.app.undo_stacks.setdefault(oid, [])

        ustack.append(current)

        if len(ustack) > MAX_UNDO_PER_OBJECT:
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
        """Shim: opens the unified settings window on the Focus tab."""
        self._open_unified("focus")

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
            if str(self.reg_outer) not in self.panes.panes():
                self.panes.add(self.reg_outer, weight=3)
        else:
            self.panes.forget(self.reg_outer)


    def _apply_default_data_preset_shortcut(self, event=None):
        # Trigger apply_active_preset on the active location panel if present
        is_center = hasattr(self, "location_in_center_var") and self.location_in_center_var.get()
        active_panel = getattr(self, "location_panel_horiz", None) if is_center else getattr(self, "location_panel", None)
        if active_panel and hasattr(active_panel, "apply_active_preset"):
            active_panel.apply_active_preset()
            return "break"
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
                    try:
                        widget.edit_reset()
                    except tk.TclError:
                        pass
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

    def toggle_left_pin(self, event=None):
        is_pinned = not self.left_pinned.get()
        self.left_pinned.set(is_pinned)
        
        prefs = config.load_prefs() or {}
        prefs["left_pinned"] = is_pinned
        config.save_prefs(prefs)
        
        self._apply_pin_state(animate=True)
        return "break"

    def _apply_pin_state(self, animate=False):
        if not hasattr(self, "left_content_frame") or not hasattr(self, "left_frame"):
            return
            
        if self.left_pinned.get():
            # Hide overlay if currently active
            if hasattr(self, "_drawer_anim_job") and self._drawer_anim_job is not None:
                try:
                    self.root.after_cancel(self._drawer_anim_job)
                except Exception:
                    pass
                self._drawer_anim_job = None
            self._drawer_current_width = 0
            self._drawer_is_open = False
            if hasattr(self, "drawer_overlay"):
                self.drawer_overlay.place_forget()

            # Pack content frame directly into left_frame
            self.left_content_frame.pack(in_=self.left_frame, side="left", fill="both", expand=True)
            if hasattr(self, "pin_btn"):
                self.pin_btn.config(bg=config.RAIL_THEME.get("icon_hover_bg", "#e9ece5"))
            


            target_sash = sc(300)
            if animate:
                self._animate_sash_transition(target_sash)
            elif hasattr(self, "panes"):
                try:
                    self.panes.sashpos(0, target_sash)
                except Exception:
                    pass
        else:
            # Unpinned mode: forget content frame from left_frame layout
            self.left_content_frame.pack_forget()
            if hasattr(self, "pin_btn"):
                self.pin_btn.config(bg=config.RAIL_THEME.get("rail_bg", "#fbfaf8"))
            


            target_sash = sc(config.RAIL_THEME.get("rail_width", 40))
            if animate:
                self._animate_sash_transition(target_sash)
            elif hasattr(self, "panes"):
                try:
                    self.panes.sashpos(0, target_sash)
                except Exception:
                    pass

    def _animate_sash_transition(self, target_sash):
        import math
        if not hasattr(self, "panes"):
            return
            
        try:
            start_sash = self.panes.sashpos(0)
        except Exception:
            start_sash = target_sash
            
        distance = float(target_sash - start_sash)
        if abs(distance) < 2:
            try:
                self.panes.sashpos(0, target_sash)
            except Exception:
                pass
            return
            
        duration = float(config.DRAWER_THEME.get("anim_duration_ms", 140))
        step_interval = int(config.DRAWER_THEME.get("anim_step_interval_ms", 8))
        start_time = time.time() * 1000.0

        def _step():
            now = time.time() * 1000.0
            elapsed = now - start_time
            if elapsed >= duration:
                try:
                    self.panes.sashpos(0, target_sash)
                except Exception:
                    pass
            else:
                progress = max(0.0, min(1.0, elapsed / duration))
                ease_progress = 0.5 - 0.5 * math.cos(progress * math.pi)
                current_pos = int(start_sash + distance * ease_progress)
                try:
                    self.panes.sashpos(0, current_pos)
                except Exception:
                    pass
                self.root.after(step_interval, _step)

        _step()

    def handle_ctrl_o(self, event=None):
        return self.toggle_left_pin(event)

    def handle_ctrl_l(self, event=None):
        return self.handle_ctrl_o(event)

    def handle_ctrl_f(self, event=None):
        if not self.left_pinned.get():
            self.toggle_left_pin()
        
        if hasattr(self, "_inline_search_entry"):
            self._inline_search_entry.focus_set()
            try:
                self._inline_search_entry.select_range(0, tk.END)
                if self._inline_search_var.get() == self._inline_search_placeholder:
                    self._inline_search_entry.delete(0, tk.END)
                    self._inline_search_entry.config(foreground="black")
            except Exception:
                pass
        return "break"

    def toggle_floating_drawer_shortcut(self, event=None):
        return self.handle_ctrl_o(event)

    def toggle_floating_drawer(self, event=None):
        return self.handle_ctrl_o(event)

    def open_drawer(self):
        self._drawer_is_open = True
        if hasattr(self, "left_content_frame") and hasattr(self, "drawer_overlay"):
            self.left_content_frame.pack(in_=self.drawer_overlay, fill="both", expand=True)
            self.drawer_overlay.lift()
            self.left_content_frame.lift()
            if hasattr(self, "left_panes"):
                self.left_panes.pack(fill="both", expand=True)
        
        target_w = sc(config.DRAWER_THEME.get("drawer_width", 300))
        self._animate_drawer(target_w)

        try:
            self.root.update_idletasks()
            if hasattr(self, "left_content_frame"):
                self.left_content_frame.update_idletasks()
            if hasattr(self, "object_list") and hasattr(self.object_list, "update_idletasks"):
                self.object_list.update_idletasks()
            if hasattr(self, "refresh_list"):
                self.refresh_list()
        except Exception:
            pass

    def close_drawer(self):
        self._drawer_is_open = False
        self._animate_drawer(0)
        if hasattr(self, "left_pinned") and self.left_pinned.get():
            self._apply_pin_state(animate=False)

    def _animate_drawer(self, target_width):
        import math
        if hasattr(self, "_drawer_anim_job") and self._drawer_anim_job is not None:
            try:
                self.root.after_cancel(self._drawer_anim_job)
            except Exception:
                pass
            self._drawer_anim_job = None

        if not config.DRAWER_THEME.get("enable_animation", True):
            self._drawer_current_width = float(target_width)
            self._update_drawer_geometry()
            if target_width == 0:
                if hasattr(self, "drawer_overlay"):
                    self.drawer_overlay.place_forget()
            return

        duration = float(config.DRAWER_THEME.get("anim_duration_ms", 140))
        step_interval = int(config.DRAWER_THEME.get("anim_step_interval_ms", 8))
        start_w = float(self._drawer_current_width)
        distance = float(target_width - start_w)

        if abs(distance) < 1:
            self._drawer_current_width = float(target_width)
            self._update_drawer_geometry()
            if target_width == 0:
                if hasattr(self, "drawer_overlay"):
                    self.drawer_overlay.place_forget()
            return

        start_time = time.time() * 1000.0

        def _step():
            now = time.time() * 1000.0
            elapsed = now - start_time
            if elapsed >= duration:
                self._drawer_current_width = float(target_width)
                self._drawer_anim_job = None
                self._update_drawer_geometry()
                if target_width == 0:
                    if hasattr(self, "drawer_overlay"):
                        self.drawer_overlay.place_forget()
            else:
                progress = max(0.0, min(1.0, elapsed / duration))
                ease_progress = 0.5 - 0.5 * math.cos(progress * math.pi)
                self._drawer_current_width = start_w + distance * ease_progress
                self._update_drawer_geometry()
                self._drawer_anim_job = self.root.after(step_interval, _step)

        _step()

    def _update_drawer_geometry(self):
        if not hasattr(self, "drawer_overlay") or not hasattr(self, "left_frame"):
            return
        w = int(self._drawer_current_width)
        if w <= 0:
            self.drawer_overlay.place_forget()
            return
            
        try:
            self.root.update_idletasks()
            rail_x = self.left_frame.winfo_rootx() - self.root.winfo_rootx()
            rail_w = self.left_frame.winfo_width()
            top_y = self.left_frame.winfo_rooty() - self.root.winfo_rooty()
            h = self.left_frame.winfo_height()

            self.drawer_overlay.place(
                x=rail_x + rail_w,
                y=top_y,
                width=w,
                height=h
            )
            self.drawer_overlay.lift()
        except Exception:
            pass

    def _on_global_click_for_drawer(self, event):
        if hasattr(self, "left_pinned") and self.left_pinned.get():
            return
        if not hasattr(self, "drawer_overlay") or not self.drawer_overlay.winfo_exists():
            return
            
        if self._drawer_is_open or self._drawer_current_width > 0:
            try:
                widget = event.widget
                curr = widget
                while curr is not None and curr != self.root:
                    if curr == self.drawer_overlay or curr == getattr(self, "rail_frame", None):
                        return
                    curr = getattr(curr, "master", None)
                
                self.close_drawer()
            except Exception:
                pass

    def toggle_list_panel(self):
        if self.show_list_var.get():
            if str(self.left_frame) not in self.panes.panes():
                self.panes.insert(0, self.left_frame, weight=1)
        else:
            self.panes.forget(self.left_frame)
            
    def toggle_search_panel(self):
        if hasattr(self, "search_bar_frame"):
            if self.show_search_var.get():
                self.search_bar_frame.pack(fill="x", padx=0, pady=(0, 2), before=self.search_bar_frame.master.winfo_children()[1] if len(self.search_bar_frame.master.winfo_children()) > 1 else None)
            else:
                self.search_bar_frame.pack_forget()
                

    def _sync_middle_panes(self):
        if not hasattr(self, 'middle_panes'):
            return
            
        # Temporarily forget panes to manage ordering and visibility safely
        if hasattr(self, 'right_frame') and str(self.right_frame) in self.middle_panes.panes():
            self.middle_panes.forget(self.right_frame)
        if hasattr(self, 'loc_frame_horizontal') and str(self.loc_frame_horizontal) in self.middle_panes.panes():
            self.middle_panes.forget(self.loc_frame_horizontal)

        # Re-add visible panes in order: images at top, location at bottom
        if self.show_images_var.get():
            # U2-A: 200px minimum keeps image panel usable when sash is dragged left
            self.middle_panes.add(self.right_frame, weight=3)
            self.refresh_image_view()

        focus_active = hasattr(self, "focus_mode_var") and self.focus_mode_var.get()
        show_loc = not (focus_active and not self.focus_visibility_vars.get("Location", tk.BooleanVar(value=True)).get())

        if hasattr(self, 'location_in_center_var') and self.location_in_center_var.get() and show_loc:
            # U2-A: 130px minimum keeps location rows readable
            self.middle_panes.add(self.loc_frame_horizontal, weight=1)

    def toggle_location_panel(self):
        if hasattr(self, 'location_in_center_var') and self.location_in_center_var.get():
            if hasattr(self, 'loc_container'):
                self.loc_container.pack_forget()
                if hasattr(self, 'left_panes') and hasattr(self, 'left_bottom_container'):
                    if str(self.left_bottom_container) in self.left_panes.panes():
                        self.left_panes.forget(self.left_bottom_container)
            self._sync_middle_panes()
        else:
            if hasattr(self, 'loc_frame_horizontal') and str(self.loc_frame_horizontal) in self.middle_panes.panes():
                self.middle_panes.forget(self.loc_frame_horizontal)
            if hasattr(self, 'loc_container'):
                if hasattr(self, 'left_panes') and hasattr(self, 'left_bottom_container'):
                    if str(self.left_bottom_container) not in self.left_panes.panes():
                        self.left_panes.add(self.left_bottom_container, weight=0)
                self.loc_container.pack(side="top", fill="x")

    def toggle_images_panel(self):
        self._sync_middle_panes()
            
    def toggle_image_tools(self):
        self.image_toolbar.pack_forget()
        if self.show_image_tools_var.get():
            self.image_toolbar.pack(before=self.image_box, fill="x", pady=(2, 4))

    def toggle_bulk_edit_btn(self):
        if hasattr(self, 'bulk_edit_btn'):
            import config
            advanced_prefs = config.load_prefs().get("advanced", {})
            if not advanced_prefs.get("enable_bulk_editor", False):
                self.bulk_edit_btn.pack_forget()
                return

            if self.show_bulk_edit_var.get():
                self.bulk_edit_btn.pack(side="bottom", fill="x", pady=(2, 0))
            else:
                self.bulk_edit_btn.pack_forget()








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
            style="Nav.TButton",
            command=self._open_unified
        )
        self.sb_settings_btn.grid(row=0, column=0, sticky="nsew", padx=(6, 2), pady=3)

        sep = ttk.Separator(self.sb_buttons_frame, orient="vertical")
        sep.grid(row=0, column=1, sticky="ns", pady=3)

        self.sb_help_btn = ttk.Button(
            self.sb_buttons_frame,
            text="HELP",
            style="Nav.TButton",
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
        # U2-H: Filter-active badge — amber dot that appears when any filter is active.
        # Created here; populated/cleared by update_object_count().
        self._filter_active_badge = tk.Label(
            sb_left, text="", bg=statusbar_bg, fg="#e07b39",
            font=("Courier New", sc(9), "bold"), padx=4
        )
        self._filter_active_badge.pack(side="left")

        # Right links group
        sb_right = tk.Frame(sb_bottom, bg=statusbar_bg)
        sb_right.pack(side="right", fill="y")

        def _sb_link(parent, text, cmd):
            # U2-C: #c8c8c8 on #1c1b1b achieves ~7.5:1 contrast ratio (WCAG AA+)
            # replaces #aaaaaa which was only ~3.5:1 (fails AA)
            lbl = tk.Label(parent, text=text, bg=statusbar_bg, fg="#c8c8c8",
                           font=("Courier New", sc(9)), padx=8, cursor="hand2")
            lbl.pack(side="right")
            lbl.bind("<Button-1>", lambda e: cmd())
            lbl.bind("<Enter>", lambda e: lbl.config(fg="#ffffff"))
            lbl.bind("<Leave>", lambda e: lbl.config(fg="#c8c8c8"))
            return lbl

        _sb_link(sb_right, "DB_STATUS",  self.show_statistics)   # placeholder — connect later
        _sb_link(sb_right, "LOG_VIEWER", self.open_log_viewer_window)

        # ----------------------------------------------------------------
        # LAYER 2: Stitch Top Navigation Bar
        # Replaces the old 2-row raw-grid toolbar.
        # Structure: [TITLE] [FILE|DATA|PROBLEMS|CREATE|HISTORY] ... [STATUS]
        # ----------------------------------------------------------------
        nav_bar_bg = "#e9ece5"
        nav_border = "#8b948d"

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
        btn_file = _nav_btn(nav_links_frame, "FILE ▾",     self.show_file_dropdown)
        self.add_tooltip(btn_file, "Database file options")




        # DATA — opens data menu
        btn_dat = _nav_btn(nav_links_frame, "DATA",   self.open_load_data_menu)
        self.add_tooltip(btn_dat, "Load historical databases")

        # IMAGES — jump to next problem
        btn_img = _nav_btn(nav_links_frame, "IMAGES ▾", self.show_images_dropdown)
        self.add_tooltip(btn_img, "Image source and view options")

        # CREATE — add new object or database
        btn_create = _nav_btn(nav_links_frame, "CREATE",   self.show_create_dropdown)
        self.add_tooltip(btn_create, "Create a new object or database")

        # HISTORY — recent objects popup
        btn_hist = _nav_btn(nav_links_frame, "RECENT",  self.open_recent_popup)
        self.add_tooltip(btn_hist, "View recently visited objects")

        # 1px separator before secondary controls
        tk.Frame(nav_bar, bg=nav_border, width=1).pack(side="left", fill="y", pady=8)

        # --- Secondary toolbar controls (kept for feature compatibility) ---
        secondary_frame = ttk.Frame(nav_bar)
        secondary_frame.pack(side="left", fill="y", padx=4)

        self.toolbar_buttons['Prev'] = ttk.Button(
            secondary_frame, text="◄", style="Nav.TButton",
            command=lambda: self.navigate_object(-1))
        self.toolbar_buttons['Prev'].pack(side="left", padx=1)
        self.add_tooltip(self.toolbar_buttons['Prev'], "Previous in list")

        self.toolbar_buttons['Next'] = ttk.Button(
            secondary_frame, text="►", style="Nav.TButton",
            command=lambda: self.navigate_object(1))
        self.toolbar_buttons['Next'].pack(side="left", padx=1)
        self.add_tooltip(self.toolbar_buttons['Next'], "Next in list")

        self.toolbar_buttons['Last'] = ttk.Button(
            secondary_frame, text="Last", style="Nav.TButton",
            command=self.goto_last_object)
        self.toolbar_buttons['Last'].pack(side="left", padx=2)
        self.add_tooltip(self.toolbar_buttons['Last'], "Return to last visited object")




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









        self.show_all_history_var = tk.BooleanVar(value=False)

        # --- Right side: status indicators ---
        status_container = ttk.Frame(nav_bar)
        status_container.pack(side="right", fill="y", padx=(0, 16))

        # Online status dot + label
        status_dot_frame = ttk.Frame(status_container)
        status_dot_frame.pack(anchor="center", side="right")
        self._online_dot = tk.Canvas(status_dot_frame, width=8, height=8,
                                     highlightthickness=0, bg=nav_bar_bg)
        self._online_dot.create_oval(1, 1, 7, 7, fill="#3a7d44", outline="")
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
            self.root, bg="#fef08a",
            highlightthickness=1, highlightbackground="#facc15"
        )

        # Main 3-column paned workspace (below nav bar, above status bar)
        panes = ttk.Panedwindow(self.root, orient="horizontal")
        panes.pack(fill="both", expand=True)
        self.panes = panes


      
        left = ttk.Frame(panes)
        self.left_frame = left
        panes.add(left, weight=0)
        self.left_frame.bind("<Configure>", self.on_left_frame_configure, add="+")

        # Persistent Action Rail frame on the left edge
        rail = tk.Frame(
            left,
            bg=config.RAIL_THEME.get("rail_bg", "#fbfaf8"),
            highlightthickness=1,
            highlightbackground=config.RAIL_THEME.get("rail_border", "#d1d1d1"),
            width=sc(config.RAIL_THEME.get("rail_width", 40))
        )
        rail.pack_propagate(False)
        self.rail_frame = rail
        rail.pack(side="left", fill="y")

        # Action Rail buttons
        self.pin_btn = tk.Button(
            rail, text="📌",
            font=("Segoe UI Symbol", sc(11)),
            bg=config.RAIL_THEME.get("rail_bg", "#fbfaf8"),
            fg=config.RAIL_THEME.get("icon_active_fg", "#000000"),
            activebackground=config.RAIL_THEME.get("icon_hover_bg", "#e9ece5"),
            bd=0, relief="flat", cursor="hand2",
            command=self.toggle_left_pin
        )
        self.pin_btn.pack(side="top", fill="x", pady=(sc(6), sc(4)), padx=sc(4))
        self.add_tooltip(self.pin_btn, "Toggle Docked / Unpinned Focus Mode")

        self.drawer_btn = tk.Button(
            rail, text="🔍",
            font=("Segoe UI Symbol", sc(11)),
            bg=config.RAIL_THEME.get("rail_bg", "#fbfaf8"),
            fg=config.RAIL_THEME.get("icon_active_fg", "#000000"),
            activebackground=config.RAIL_THEME.get("icon_hover_bg", "#e9ece5"),
            bd=0, relief="flat", cursor="hand2",
            command=self.toggle_floating_drawer
        )
        self.drawer_btn.pack(side="top", fill="x", pady=sc(4), padx=sc(4))
        self.add_tooltip(self.drawer_btn, "Open Object Drawer (Ctrl+O)")

        self.filter_indicator = tk.Label(
            rail, text="⚡",
            font=("Segoe UI Symbol", sc(10), "bold"),
            bg=config.RAIL_THEME.get("rail_bg", "#fbfaf8"),
            fg=config.RAIL_THEME.get("indicator_active_bg", "#C62828"),
            bd=0
        )
        self.filter_indicator.pack(side="top", fill="x", pady=sc(4), padx=sc(4))
        self.filter_indicator.pack_forget()

        # Content frame holding list, search, and location widgets (master is self.root to allow unclipped reparenting into drawer_overlay)
        self.left_content_frame = ttk.Frame(self.root)
        self.left_content_frame.pack(in_=left, side="left", fill="both", expand=True)

        # Floating Overlay Drawer Container (root-level floating frame, zero clipping)
        self.drawer_overlay = tk.Frame(
            self.root,
            bg=config.DRAWER_THEME.get("drawer_bg", "#ffffff"),
            highlightthickness=1,
            highlightbackground=config.DRAWER_THEME.get("drawer_border", "#c4c7c7")
        )
        self.root.bind_all("<Button-1>", self._on_global_click_for_drawer, add="+")

        self.review_progress_label = None
        self.review_progress = None

        self.filter_status_label = ttk.Label(
            self.left_content_frame,
            text="",
            foreground="#c0392b",
            font=("Segoe UI", sc(8), "bold")
        )
        self.filter_status_label.pack(fill="x", padx=6, pady=(0, 2))

        sort_frame = ttk.Frame(self.left_content_frame)
        sort_frame.pack(fill="x", padx=4, pady=(0, 2))

        self.sort_var = tk.StringVar(value="ID")

        sort_cb = ttk.Combobox(
            sort_frame,
            textvariable=self.sort_var,
            values=["ID", "Genus A-Z", "Reviewed first", "Problems first"],
            state="readonly",
            width=16
        , cursor="hand2")
        sort_cb.pack(side="left", padx=(4, 0))

        sort_cb.bind(
            "<<ComboboxSelected>>",
            lambda e: self._sort_object_list(self.sort_var.get())
        )

        # Create self.left_panes vertical paned window
        self.left_panes = ttk.Panedwindow(self.left_content_frame, orient="vertical")
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
        self.toolbar_buttons['Filter'] = ttk.Button(sort_frame, text="Filter", style="Nav.TButton", command=self.open_filter_menu)
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
        self._last_search_query = self._inline_search_placeholder
        self._inline_search_entry = tk.Entry(
            search_container,
            textvariable=self._inline_search_var,
            font=("Hanken Grotesk", sc(10)),
            bg="#ffffff", fg="#2c302e",
            relief="flat", bd=0,
            insertbackground="#000000"
        )
        self._inline_search_entry.pack(side="left", fill="x", expand=True, padx=(sc(8), sc(4)), pady=sc(5))
        self._inline_search_entry.bind("<KeyRelease>",  self._on_inline_search_key)
        self._inline_search_entry.bind("<Escape>",      self._clear_inline_search)
        self._inline_search_entry.bind("<FocusIn>",     self._search_focus_in)
        self._inline_search_entry.bind("<FocusOut>",    self._search_focus_out)
        self._inline_search_entry.bind("<Button-1>",    self._search_focus_in)
        self._inline_search_entry.bind("<Return>",      self._on_search_bar_enter)
        self._inline_search_entry.bind("<Down>",        self._on_search_arrow_down)
        self._inline_search_entry.bind("<Up>",          self._on_search_arrow_up)
        
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
            activebackground="#ffffff", activeforeground="#c93a40",
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
        advanced_prefs = config.load_prefs().get("advanced", {})
        if advanced_prefs.get("enable_bulk_editor", False):
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
            fg="#c93a40",
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

        # --- Middle Panedwindow for resizable Location panel ---
        self.middle_panes = ttk.Panedwindow(middle, orient="vertical")
        self.middle_panes.pack(fill="both", expand=True)

        # --- Horizontal Location Container ---
        self.loc_frame_horizontal = tk.Frame(self.middle_panes, bg="#f5f5f5")
        # will be added in toggle_location_panel()

        right = ttk.Frame(self.middle_panes, style="MiddlePane.TFrame")
        self.right_frame = right
        # U2-A: 200px minimum ensures image panel never collapses below usable size
        self.middle_panes.add(right, weight=3)

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
            style="Nav.TButton",
            command=self.toggle_image_view
        )
        self.view_btn.pack(side="right")
        self.update_image_view_button()

        self.source_btn = ttk.Button(
            header,
            text="Source...",
            style="Nav.TButton",
            command=self.open_image_menu
        )
        self.source_btn.pack(side="right", padx=(0, 4))

        self.images_missing_label = ttk.Label(
            header,
            text="",
            foreground="#c93a40",
            font=("Segoe UI", sc(9), "bold"),
            style="MiddlePane.TLabel"
        )
        self.images_missing_label.pack(side="right", padx=(0, 8))

        # Image Control Overlay Toolbar
        from ui.image_toolbar import create_image_toolbar
        self.image_toolbar = create_image_toolbar(
            parent=right,
            live_callbacks={
                "zoom_in": self.zoom_image_in,
                "zoom_out": self.zoom_image_out,
                "rotate_cw": lambda: self.rotate_image(90) if hasattr(self, 'rotate_image') else None,
                "rotate_ccw": lambda: self.rotate_image(-90) if hasattr(self, 'rotate_image') else None,
                "reset": self.reset_image_view,
                "fit": getattr(self, "fit_image_view", self.reset_image_view),
                "design_toggle": lambda mode: self.save_user_pref("image_button_style", mode)
            },
            design_mode=getattr(self, "image_button_style", "standard"),
            dark_mode=getattr(self, "dark_mode_active", False),
            zoom_level=getattr(self, "image_zoom_factor", 1.0),
            rotation_angle=getattr(self, "image_rotation_angle", 0)
        )
        self.image_toolbar.pack(fill="x", padx=6, pady=(0, 2))

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

        self.image_canvas.configure(yscrollcommand=self._on_image_scroll)
        
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
            bg="#ffffff", fg="#2c302e",
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
        self.focus_quick_frame = ttk.Frame(reg_header, style="RightPane.TFrame")
        self.focus_quick_frame.pack(side="right", padx=(0, 4))

        self.focus_problems_cb = ToggleSwitch(
            self.focus_quick_frame,
            self.focus_mode_var,
            command=self.toggle_focus_mode_from_ui,
            ui_ref=self
        )
        self.focus_problems_cb.pack(side="right", padx=(4, 0))
        ttk.Label(self.focus_quick_frame, text="Focus Mode", font=("Hanken Grotesk", sc(9))).pack(side="right")
        self.update_focus_toggle_visibility()

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
        self.reviewed_button.bind("<ButtonPress-1>", self._on_reviewed_btn_press)
        self.reviewed_button.bind("<ButtonRelease-1>", self._on_reviewed_btn_release)

        # Row 1b: Secondary action — clear problems checkbutton + status indicators
        action_row1b = ttk.Frame(action_bar, style="RightPane.TFrame")
        action_row1b.pack(fill="x", pady=(4, 0))

        is_dark = getattr(self, "dark_mode_active", False)
        bg_col = "#1e1e2d" if is_dark else "#ffffff"
        fg_col = "#e8ebe9" if is_dark else "#2c302e"
        bg_pane = "#212622" if is_dark else "#fbfaf8"

        # Grid frame for checkboxes (prevents horizontal overflow)
        grid_frame = ttk.Frame(action_row1b, style="RightPane.TFrame")
        grid_frame.pack(side="left", fill="both", expand=True)

        self.clear_problems_var = tk.BooleanVar(value=False)
        self.clear_problems_cb = tk.Checkbutton(
            grid_frame,
            text="Clear Problems & Mark Reviewed",
            variable=self.clear_problems_var,
            command=self._clear_problems_and_mark_reviewed,
            font=("Segoe UI", sc(9.5)),
            bg=bg_pane, fg=fg_col,
            activebackground=bg_pane, activeforeground=fg_col,
            selectcolor=bg_col,
            relief="flat", bd=0, highlightthickness=0,
            cursor="hand2",
            padx=sc(4), pady=sc(3)  # U2-B: explicit padding for larger click target
        )
        self.clear_problems_cb.grid(row=0, column=0, sticky="w", padx=2, pady=1)
        self.add_tooltip(
            self.clear_problems_cb,
            "Uncheck all problem flags and mark this object as reviewed (stays on current object)"
        )

        self.auto_next_cb = tk.Checkbutton(
            grid_frame,
            text="Auto-next after review",
            variable=self.auto_advance_var,
            font=("Segoe UI", sc(9.5)),
            bg=bg_pane, fg=fg_col,
            activebackground=bg_pane, activeforeground=fg_col,
            selectcolor=bg_col,
            relief="flat", bd=0, highlightthickness=0,
            cursor="hand2",
            padx=sc(4), pady=sc(3)  # U2-B: explicit padding for larger click target
        )
        self.auto_next_cb.grid(row=0, column=1, sticky="w", padx=2, pady=1)
        self.add_tooltip(
            self.auto_next_cb,
            "Automatically advance to the next item when marked as reviewed"
        )

        self.auto_next_history_cb = tk.Checkbutton(
            grid_frame,
            text="Auto-next with Historical Suggestion",
            variable=self.auto_advance_history_var,
            font=("Segoe UI", sc(9.5)),
            bg=bg_pane, fg=fg_col,
            activebackground=bg_pane, activeforeground=fg_col,
            selectcolor=bg_col,
            relief="flat", bd=0, highlightthickness=0,
            cursor="hand2",
            padx=sc(4), pady=sc(3)
        )
        self.auto_next_history_cb.grid(row=1, column=0, columnspan=2, sticky="w", padx=2, pady=1)
        self.add_tooltip(
            self.auto_next_history_cb,
            "Automatically advance to the next unreviewed item with historical suggestions when marked as reviewed"
        )

        # Status frame for labels (stacked vertically on the right)
        status_frame = ttk.Frame(action_row1b, style="RightPane.TFrame")
        status_frame.pack(side="right", fill="y", padx=4)

        self.reviewed_time_label = ttk.Label(
            status_frame,
            text="",
            foreground="gray",
            font=("Segoe UI", sc(8))
        )
        self.reviewed_time_label.pack(side="bottom", anchor="e")

        # Unsaved indicator dot on the right
        self.data_status_action = ttk.Label(
            status_frame,
            text="",
            foreground="gray",
            font=("Segoe UI", sc(8))
        )
        self.data_status_action.pack(side="top", anchor="e")

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

        # U2-H: Filter-active indicator — a small coloured dot next to the count
        # gives an at-a-glance signal that the list is filtered, even in low light.
        if hasattr(self, "_filter_active_badge"):
            total = len(self.app.df_reg) if self.app.df_reg is not None else 0
            shown = len(self.app.active_object_ids) if self.app.active_object_ids else 0
            is_filtered = (shown < total) and total > 0
            self._filter_active_badge.config(
                text=" ● FILTER" if is_filtered else "",
                fg="#e07b39"  # amber — visible in both light and dark themes
            )




#------

    def focus_search(self, event=None):
        """Ctrl+F / Ctrl+L: Open drawer if unpinned, then focus the inline live search bar."""
        if hasattr(self, "left_pinned") and not self.left_pinned.get():
            self.toggle_left_pin()
        
        if hasattr(self, "_inline_search_entry"):
            self._inline_search_entry.focus_set()
            try:
                self._inline_search_entry.select_range(0, tk.END)
                if self._inline_search_var.get() == self._inline_search_placeholder:
                    self._inline_search_entry.delete(0, tk.END)
                    self._inline_search_entry.config(foreground="black")
            except Exception:
                pass
        return "break"



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




    def open_load_data_menu(self):
        if (
            hasattr(self, "advanced_win")
            and self.advanced_win
            and self.advanced_win.winfo_exists()
        ):
            self.advanced_win.focus_force()
            self.advanced_win.lift()
            return

        win = tk.Toplevel(self.root)
        self.advanced_win = win

        win.title("Data Options")
        win.resizable(True, True)
        win.transient(self.root)

        bg_color = "#181c19" if self.dark_mode_active else "#f2f5f1"
        win.configure(background=bg_color)

        import utils
        utils.center_and_fit_toplevel(win, sc(400), sc(250))

        win.bind("<Escape>", lambda e: win.destroy())

        frame = ttk.Frame(win, padding=sc(16))
        frame.pack(fill="both", expand=True)

        # Header
        lbl_header = ttk.Label(
            frame,
            text="DATA OPTIONS",
            font=("Segoe UI", sc(12), "bold"),
            foreground="#2c302e" if not self.dark_mode_active else "#e8ebe9"
        )
        lbl_header.pack(anchor="w", pady=(0, 10))

        ttk.Separator(frame, orient="horizontal").pack(fill="x", pady=(0, 15))

        def run_cmd(cmd):
            win.destroy()
            cmd()

        # Buttons
        ttk.Button(
            frame,
            text="Load books",
            command=lambda: run_cmd(self.load_books_file)
        ).pack(fill="x", pady=(0, 6))

        ttk.Button(
            frame,
            text="Load earlier databases",
            command=lambda: run_cmd(self.load_historical_databases)
        ).pack(fill="x", pady=(0, 12))

        ttk.Separator(frame, orient="horizontal").pack(fill="x", pady=(0, 12))

        ttk.Checkbutton(
            frame,
            text="Show all historical data",
            variable=self.show_all_history_var,
            command=self._on_history_toggle
        , cursor="hand2").pack(anchor="w")





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

        is_dark = getattr(self, "dark_mode_active", False)
        bg_color = "#181c19" if is_dark else "#f2f5f1"
        fg_title = "#e8ebe9" if is_dark else "#2c302e"
        fg_label = "#a6adc8" if is_dark else "#444748"
        fg_nomatch = "#c93a40" if is_dark else "#c93a40"
        fg_cat = "#89b4fa" if is_dark else "#1976d2"
        bg_key = "#11111b" if is_dark else "#e0e0e0"
        fg_key = "#f9e2af" if is_dark else "#000000"
        fg_desc = "#a6adc8" if is_dark else "#444748"
        fg_footer = "#585b70" if is_dark else "#757575"

        win.configure(background=bg_color)
        win.transient(self.root)
        
        # Close on Escape
        win.bind("<Escape>", lambda e: win.destroy())
        
        # Title
        title_frame = tk.Frame(win, bg=bg_color)
        title_frame.pack(fill="x", padx=20, pady=(15, 10))
        
        tk.Label(
            title_frame,
            text="Keyboard Shortcuts Cheat Sheet",
            font=("Segoe UI", sc(16), "bold"),
            fg=fg_title,
            bg=bg_color
        ).pack(side="left")
        
        # Search Box
        search_frame = tk.Frame(win, bg=bg_color)
        search_frame.pack(fill="x", padx=20, pady=(0, 15))
        
        tk.Label(
            search_frame,
            text="Search: ",
            font=("Segoe UI", sc(10), "bold"),
            fg=fg_label,
            bg=bg_color
        ).pack(side="left")
        
        search_var = tk.StringVar()
        search_ent = ttk.Entry(search_frame, textvariable=search_var, font=("Segoe UI", sc(10)))
        search_ent.pack(side="left", fill="x", expand=True, padx=(5, 0))
        search_ent.focus_set()
        
        # Content frame (Canvas + Scrollbar)
        content_outer = tk.Frame(win, bg=bg_color)
        content_outer.pack(fill="both", expand=True, padx=20, pady=(0, 10))
        
        canvas = tk.Canvas(content_outer, bg=bg_color, highlightthickness=0)
        scrollbar = ttk.Scrollbar(content_outer, orient="vertical", command=canvas.yview)
        scroll_content = tk.Frame(canvas, bg=bg_color)
        
        scroll_content.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        window_id = canvas.create_window((0, 0), window=scroll_content, anchor="nw")
        canvas.bind(
            "<Configure>",
            lambda e: canvas.itemconfig(window_id, width=e.width) if getattr(canvas, "_last_width", None) != e.width and not setattr(canvas, "_last_width", e.width) else None
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
            ("FOCUS", "Ctrl+J", "Open Database Statistics"),
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
                    fg=fg_nomatch,
                    bg=bg_color
                ).pack(pady=20)
                return
                
            for cat, items in categories.items():
                cat_frame = tk.Frame(scroll_content, bg=bg_color)
                cat_frame.pack(fill="x", pady=(10, 5), anchor="w")
                
                # Category Header
                tk.Label(
                    cat_frame,
                    text=cat,
                    font=("Segoe UI", sc(11), "bold"),
                    fg=fg_cat,
                    bg=bg_color
                ).pack(anchor="w", padx=5)
                
                # Grid of shortcuts
                grid_frame = tk.Frame(scroll_content, bg=bg_color)
                grid_frame.pack(fill="x", padx=15, pady=2, anchor="w")
                grid_frame.columnconfigure(0, minsize=220)
                grid_frame.columnconfigure(1, weight=1)
                
                for r, (keys, desc) in enumerate(items):
                    # Key label (capsule look)
                    key_container = tk.Frame(grid_frame, bg=bg_key, bd=1, relief="ridge", padx=6, pady=3)
                    key_container.grid(row=r, column=0, sticky="w", pady=3, padx=(0, 10))
                    
                    # Split keys by '+' or '/' or ',' to draw individual keycaps if desired, or just show text
                    tk.Label(
                        key_container,
                        text=keys,
                        font=("Consolas", sc(10), "bold"),
                        fg=fg_key,
                        bg=bg_key
                    ).pack()
                    
                    # Description
                    tk.Label(
                        grid_frame,
                        text=desc,
                        font=("Segoe UI", sc(10)),
                        fg=fg_desc,
                        bg=bg_color,
                        wraplength=550,
                        justify="left"
                    ).grid(row=r, column=1, sticky="w", pady=3)
                    
        # Initial draw
        draw_shortcuts()
        
        # Search binding
        search_var.trace_add("write", lambda *args: draw_shortcuts(search_var.get()))
        
        # Footer
        footer = tk.Frame(win, bg=bg_color)
        footer.pack(fill="x", side="bottom", pady=10, padx=20)
        
        tk.Label(
            footer,
            text="Press Escape to close this window.",
            font=("Segoe UI", sc(9), "italic"),
            fg=fg_footer,
            bg=bg_color
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
                   loc_fields=None, loc_values=None,
                   oid=None):

        target_oid = oid if oid is not None else self.app.current_object_id
        
        # Helper to join lists into strings for logging
        def jf(arr): return ", ".join(arr) if isinstance(arr, list) else (arr or "")
        def jv(arr): return " | ".join(arr) if isinstance(arr, list) else (arr or "")

        has_any = bool(changed_fields or prob_fields or loc_fields)
        if not has_any and action != "SAVE":
            cf_text = "(no changes)"
        else:
            cf_text = jf(changed_fields)

        if not hasattr(self.app, "_log_records") or not self.app._log_records:
            if self.app.df_log is not None and not self.app.df_log.empty:
                self.app._log_records = self.app.df_log.to_dict(orient="records")
            else:
                self.app._log_records = []

        is_reviewed = "Yes" if action == "REVIEWED" else "No" if action == "NOT_REVIEWED" else ""

        # Merge contiguous edits for the same object
        if action in ("EDIT", "REVIEWED", "NOT_REVIEWED") and self.app._log_records:
            last_entry = self.app._log_records[-1]
            if last_entry.get("Action") in ("EDIT", "REVIEWED", "NOT_REVIEWED") and last_entry.get("ObjectID") == target_oid:
                # Update timestamp and action
                last_entry["Timestamp"] = datetime.now().isoformat(timespec="seconds")

                if action == "EDIT":
                    last_entry["Action"] = "EDIT"
                elif action in ("REVIEWED", "NOT_REVIEWED"):
                    last_entry["Reviewed"] = is_reviewed
                    if last_entry.get("Action") != "EDIT":
                        last_entry["Action"] = action

                # Merge ChangedFields
                existing_cf = set(x.strip() for x in last_entry.get("ChangedFields", "").split(",") if x.strip() and x.strip() != "(no changes)")
                new_cf = set(x.strip() for x in (cf_text or "").split(",") if x.strip() and x.strip() != "(no changes)")
                merged_cf = existing_cf.union(new_cf)
                last_entry["ChangedFields"] = ", ".join(sorted(merged_cf)) if merged_cf else "(no changes)"

                # Merge ChangedValues
                existing_cv = last_entry.get("ChangedValues", "")
                new_cv = jv(changed_values)
                if new_cv:
                    last_entry["ChangedValues"] = f"{existing_cv} | {new_cv}" if existing_cv else new_cv

                # Merge ProblemsChanged
                existing_pc = set(x.strip() for x in last_entry.get("ProblemsChanged", "").split(",") if x.strip())
                new_pc = set(x.strip() for x in jf(prob_fields).split(",") if x.strip())
                merged_pc = existing_pc.union(new_pc)
                last_entry["ProblemsChanged"] = ", ".join(sorted(merged_pc)) if merged_pc else ""

                # Merge ProblemsChangedValues
                existing_pcv = last_entry.get("ProblemsChangedValues", "")
                new_pcv = jv(prob_values)
                if new_pcv:
                    last_entry["ProblemsChangedValues"] = f"{existing_pcv} | {new_pcv}" if existing_pcv else new_pcv

                # Merge LocationChanged
                existing_lc = set(x.strip() for x in last_entry.get("LocationChanged", "").split(",") if x.strip())
                new_lc = set(x.strip() for x in jf(loc_fields).split(",") if x.strip())
                merged_lc = existing_lc.union(new_lc)
                last_entry["LocationChanged"] = ", ".join(sorted(merged_lc)) if merged_lc else ""

                # Replace LocationChangedValues entirely with the newest unified string
                new_lcv = jv(loc_values)
                if new_lcv:
                    last_entry["LocationChangedValues"] = new_lcv

                self.app.df_log = pd.DataFrame(self.app._log_records)
                return

        entry = {
            "Timestamp": datetime.now().isoformat(timespec="seconds"),
            "Action": action,
            "Reviewed": is_reviewed,
            "ObjectID": target_oid,
            "ChangedFields": cf_text or ("(no changes)" if not has_any else ""),
            "ChangedValues": jv(changed_values),
            "ProblemsChanged": jf(prob_fields),
            "ProblemsChangedValues": jv(prob_values),
            "LocationChanged": jf(loc_fields),
            "LocationChangedValues": jv(loc_values),
            "User": getpass.getuser(),
            "SourceFile": os.path.basename(self.app.excel_path) if self.app.excel_path else "",
            "OutputFile": os.path.basename(self.app.output_path) if self.app.output_path else "",
        }

        self.app._log_records.append(entry)
        self.app.df_log = pd.DataFrame(self.app._log_records)

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
        auto_prob_changed_fields = []
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
            old = utils.fmt_pandas_val(self.app.df_reg.at[oid, col] if oid in self.app.df_reg.index and col in self.app.df_reg.columns else "")

            if isinstance(widget, tk.Text):
                new = widget.get("1.0", tk.END).strip()
            else:
                new = self.reg_vars[col].get()

            if old != new:
                ensure_undo()

                self.app.df_reg.at[oid, col] = new
                if getattr(self, "_cached_reg_dict", None) is not None and oid in self._cached_reg_dict:
                    self._cached_reg_dict[oid][col] = new
                if col == "Genus" and getattr(self, "_cached_genus_dict", None) is not None:
                    self._cached_genus_dict[oid] = new
                elif col == "Species" and getattr(self, "_cached_species_dict", None) is not None:
                    self._cached_species_dict[oid] = new

                reg_changed_fields.append(col)
                reg_changed_values.append(f'{col}: "{old}"  "{new}"')

                # If a field mapped to a problem column is populated with a non-empty value, auto-clear the problem flag
                if new.strip() != "":
                    for p_col, f_name in self.problem_to_field.items():
                        if f_name == col and p_col in self.problem_vars:
                            if self.problem_vars[p_col].get():
                                self.problem_vars[p_col].set(False)
                                self.app.df_obs.at[oid, p_col] = False
                                if getattr(self, "_cached_obs_dict", None) is not None and oid in self._cached_obs_dict:
                                    self._cached_obs_dict[oid][p_col] = False
                                self.loaded_problem_states[p_col] = False


        # -------- PROBLEMS --------
        for col, var in self.problem_vars.items():

            new = bool(var.get())

            # Check for edits against the underlying database state so auto-detected problems are saved
            db_val = False
            if col in self.app.df_obs.columns:
                val = self.app.df_obs.at[oid, col] if oid in self.app.df_obs.index else False
                db_val = bool(val) if not pd.isna(val) else False

            if col not in self.app.df_obs.columns:
                self.app.df_obs[col] = False

            if db_val != new:
                ensure_undo()
                self.app.df_obs.at[oid, col] = new
                if getattr(self, "_cached_obs_dict", None) is not None and oid in self._cached_obs_dict:
                    self._cached_obs_dict[oid][col] = new

                # If the current value matches the value that was loaded (which includes auto-detections),
                # then this change is just saving an auto-detection to the DB, not a manual user edit.
                loaded_val = self.loaded_problem_states.get(col, db_val)
                if new != loaded_val:
                    prob_changed_fields.append(col)
                    prob_changed_values.append(f'{col}: "{db_val}"  "{new}"')
                else:
                    auto_prob_changed_fields.append(col)
                
                self._list_dirty = True
                self.loaded_problem_states[col] = new

        # -------- LOCATION --------
        if not skip_heavy:
            loc_changed = False
            for col, var in self.location_vars.items():
                old = utils.fmt_pandas_val(self.app.df_obs.at[oid, col] if oid in self.app.df_obs.index and col in self.app.df_obs.columns else "")
                new = var.get()

                if old != new:
                    ensure_undo()
                    self.app.df_obs.at[oid, col] = new
                    if getattr(self, "_cached_obs_dict", None) is not None and oid in self._cached_obs_dict:
                        self._cached_obs_dict[oid][col] = new
                    loc_changed = True

            if loc_changed:
                loc_changed_fields.append("Location")
                loc_vals = []
                for col, var in self.location_vars.items():
                    val = var.get()
                    if val:
                        loc_vals.append(f"{col}: {val}")
                loc_changed_values.append(", ".join(loc_vals))

        # -------- REVIEWED --------
        old = bool(self.app.df_obs.at[oid, REVIEWED_COLUMN]) if oid in self.app.df_obs.index and REVIEWED_COLUMN in self.app.df_obs.columns else False
        new = bool(self.reviewed_var.get())

        if old != new:
            ensure_undo()
            self.app.df_obs.at[oid, REVIEWED_COLUMN] = new
            if getattr(self, "_cached_obs_dict", None) is not None and oid in self._cached_obs_dict:
                self._cached_obs_dict[oid][REVIEWED_COLUMN] = new
            if getattr(self, "_cached_reviewed_dict", None) is not None:
                self._cached_reviewed_dict[oid] = new

            if new:
                now = datetime.now().strftime("%d.%m.%Y %H:%M")
                self.app.df_obs.at[oid, REVIEWED_AT_COLUMN] = now
                if getattr(self, "_cached_obs_dict", None) is not None and oid in self._cached_obs_dict:
                    self._cached_obs_dict[oid][REVIEWED_AT_COLUMN] = now
                self.reviewed_time_label.config(text=f"( {now} )")
                reg_changed_values.append(f"Reviewed set at {now}")
            else:
                self.app.df_obs.at[oid, REVIEWED_AT_COLUMN] = ""
                if getattr(self, "_cached_obs_dict", None) is not None and oid in self._cached_obs_dict:
                    self._cached_obs_dict[oid][REVIEWED_AT_COLUMN] = ""
                self.reviewed_time_label.config(text="")
                reg_changed_values.append("Reviewed removed")

            reg_changed_fields.append(REVIEWED_COLUMN)
            self.update_reviewed_button_state()


        has_changes = (
            bool(reg_changed_fields) or 
            bool(prob_changed_fields) or 
            bool(loc_changed_fields)
        )

        has_auto_changes = bool(auto_prob_changed_fields)

        if has_changes or has_auto_changes:
            self.app.dirty = True
            self.update_dirty_ui()
            self._list_dirty = True
            
            if has_changes:
                # Log the edit immediately so it's captured in the continuous session
                self.log_action("EDIT",
                                reg_changed_fields, reg_changed_values,
                                prob_changed_fields, prob_changed_values,
                                loc_changed_fields, loc_changed_values)

                self.update_history_indicator(oid)

            self._problem_cache.pop(oid, None)
            s_oid = str(oid)
            self._problem_cache.pop(s_oid, None)
            if s_oid.isdigit():
                self._problem_cache.pop(int(s_oid), None)
            if hasattr(self, "invalidate_history_cache"):
                self.invalidate_history_cache(oid)
            
            if {"Genus", "Species"} & set(reg_changed_fields):
                self.invalidate_search_index()

            # Always update list item color so badges and text colors refresh instantly
            self.update_list_item_color(oid)

            if reg_changed_fields and getattr(self.app, 'historical_dbs', None) and getattr(self, '_has_suggestions_set', None) is not None:
                sug = self.collect_historical_suggestions(oid, show_all_override=False)
                has_real = any(k != "(No data found)" for vals in sug.values() for k in vals)
                if has_real:
                    self._has_suggestions_set.add(oid)
                else:
                    self._has_suggestions_set.discard(oid)

                if hasattr(self, "_history_cache"):
                    keys_to_remove = [k for k in self._history_cache if k[0] == oid]
                    for k in keys_to_remove:
                        self._history_cache.pop(k, None)

        




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
        obs_dict = self._get_obs_dict() if hasattr(self, "_get_obs_dict") else None
        if obs_dict is not None:
            obs = obs_dict.get(oid)
            if obs is None and str(oid).isdigit():
                obs = obs_dict.get(int(oid))
            if obs is None:
                self.location_summary_label.config(text="")
                return
        elif hasattr(self, "obs_by_id") and self.obs_by_id is not None and oid in self.obs_by_id.index:
            obs = self.obs_by_id.loc[oid]
            if isinstance(obs, pd.DataFrame):
                obs = obs.iloc[0].to_dict()
            elif isinstance(obs, pd.Series):
                obs = obs.to_dict()
        else:
            self.location_summary_label.config(text="")
            return




        floor = utils.fmt_pandas_val(obs.get("Floor", ""))
        cabinet = utils.fmt_pandas_val(obs.get("Cabinet", ""))
        building = utils.fmt_pandas_val(obs.get("Building", ""))
        extra = utils.fmt_pandas_val(obs.get(" ", ""))


        loaned_raw = obs.get("Loaned out", False)
        loaned = utils.parse_bool(loaned_raw)


  
      



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

    def show_traceback_dialog(self, title, message, traceback_text, is_crash=False):
        """Displays a scrollable monospace traceback dialog for errors."""
        dialog = tk.Toplevel(self.root)
        dialog.title(title)
        dialog.resizable(True, True)
        dialog.minsize(sc(550), sc(400))  # U2-G: scaled to DPI
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

        if is_crash:
            def emergency_autosave():
                try:
                    import json
                    data = {
                        "df_reg": self.app.df_reg.copy() if self.app.df_reg is not None else None,
                        "df_obs": self.app.df_obs.copy() if self.app.df_obs is not None else None,
                        "df_photo": self.app.df_photo.copy() if self.app.df_photo is not None else None,
                        "df_log": getattr(self.app, 'df_log', None).copy() if getattr(self.app, 'df_log', None) is not None else None
                    }
                    json_data = {
                        k: v.to_json(orient="table") if v is not None else None
                        for k, v in data.items()
                    }
                    save_path = self._autosave_path() + ".crash"
                    with open(save_path, "w") as f:
                        json.dump(json_data, f)
                    from tkinter import messagebox
                    messagebox.showinfo("Emergency Save", f"Data safely backed up to:\n{save_path}", parent=dialog)
                except Exception as e:
                    from tkinter import messagebox
                    messagebox.showerror("Emergency Save Failed", f"Failed to autosave:\n{e}", parent=dialog)

            save_btn = ttk.Button(footer, text="Emergency Autosave", command=emergency_autosave)
            save_btn.pack(side="left", padx=10)

            quit_btn = ttk.Button(footer, text="Quit Application", command=self.root.destroy)
            quit_btn.pack(side="right")
        else:
            close_btn = ttk.Button(footer, text="Close", command=dialog.destroy)
            close_btn.pack(side="right")

    def show_banner(self, text, banner_type="info", duration_ms=4000, action_callback=None):
        """Displays an inline notification banner at the top of the workspace with a slide-in transition."""
        if not hasattr(self, "_inline_banner_frame"):
            return

        # Configure colors based on type from config.BANNER_THEME
        colors = getattr(config, "BANNER_THEME", {
            "success": {"bg": "#dcfce7", "border": "#22c55e", "fg": "#14532d", "icon": "✔"},
            "warning": {"bg": "#fef9c3", "border": "#eab308", "fg": "#713f12", "icon": "⚠"},
            "error":   {"bg": "#fee2e2", "border": "#ef4444", "fg": "#7f1d1d", "icon": "✘"},
            "info":    {"bg": "#dbeafe", "border": "#3b82f6", "fg": "#1e3a8a", "icon": "ℹ"},
        })
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

        if action_callback:
            def _on_click(e):
                action_callback()
                self.hide_banner()

            for w in (self._inline_banner_frame, inner, icon_lbl, text_lbl):
                w.bind("<Button-1>", _on_click)
                w.config(cursor="hand2")
        else:
            self._inline_banner_frame.unbind("<Button-1>")
            for w in (self._inline_banner_frame, inner, icon_lbl, text_lbl):
                w.config(cursor="")

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

        # Cancel any ongoing animations and auto-dismiss timer
        if hasattr(self, "_banner_anim_id") and self._banner_anim_id:
            self.root.after_cancel(self._banner_anim_id)
            self._banner_anim_id = None

        if hasattr(self, "_banner_timer_id") and self._banner_timer_id:
            self.root.after_cancel(self._banner_timer_id)
            self._banner_timer_id = None

        # Measure dimensions
        self._inline_banner_frame.update_idletasks()
        h = max(self._inline_banner_frame.winfo_reqheight(), 40)

        # Slide-in animation from top (-h) to 10
        start_y = -h
        end_y = 10
        steps = 8
        interval = 10

        def animate_show(step_idx=0):
            if not self.root.winfo_exists() or not self._inline_banner_frame.winfo_exists():
                self._banner_anim_id = None
                return
            if step_idx > steps:
                self._inline_banner_frame.place(relx=0.5, y=end_y, anchor="n")
                self._banner_anim_id = None
                return
            p = step_idx / steps
            # Cosine ease-out: math.sin(p * pi / 2)
            p_eased = math.sin(p * (math.pi / 2))
            curr_y = start_y + (end_y - start_y) * p_eased
            self._inline_banner_frame.place(relx=0.5, y=int(curr_y), anchor="n")
            self._banner_anim_id = self.root.after(interval, lambda: animate_show(step_idx + 1))

        # Start sliding in
        animate_show(0)

        if duration_ms > 0:
            self._banner_timer_id = self.root.after(duration_ms, self.hide_banner)

    def hide_banner(self):
        """Hides the inline notification banner with a slide-out animation."""
        if hasattr(self, "_banner_timer_id") and self._banner_timer_id:
            self.root.after_cancel(self._banner_timer_id)
            self._banner_timer_id = None

        if hasattr(self, "_banner_anim_id") and self._banner_anim_id:
            self.root.after_cancel(self._banner_anim_id)
            self._banner_anim_id = None

        if not hasattr(self, "_inline_banner_frame") or not self._inline_banner_frame.winfo_exists():
            return

        try:
            info = self._inline_banner_frame.place_info()
            if not info:
                return  # Not placed
            current_y = int(info.get("y", 10))
        except Exception:
            self._inline_banner_frame.place_forget()
            return

        h = max(self._inline_banner_frame.winfo_reqheight(), 40)
        start_y = current_y
        end_y = -h
        steps = 8
        interval = 10

        def animate_hide(step_idx=0):
            if not self.root.winfo_exists() or not self._inline_banner_frame.winfo_exists():
                self._banner_anim_id = None
                return
            if step_idx > steps:
                self._inline_banner_frame.place_forget()
                self._banner_anim_id = None
                return
            p = step_idx / steps
            # Cosine ease-out for slide-out
            p_eased = math.sin(p * (math.pi / 2))
            curr_y = start_y + (end_y - start_y) * p_eased
            self._inline_banner_frame.place(relx=0.5, y=int(curr_y), anchor="n")
            self._banner_anim_id = self.root.after(interval, lambda: animate_hide(step_idx + 1))

        animate_hide(0)







    


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
        # Card click drives navigation directly via _deferred_list_select;
        # suppress this handler to avoid a duplicate (and potentially search-blocked) load.
        if getattr(self.object_list, "_card_driving_nav", False):
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
            
            if self._is_searching() or self.root.focus_get() == self._inline_search_entry:
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
            self._nav_idle_job = self.root.after(15, self._navigation_finished)
            
            # Fast selection load (15ms)
            if hasattr(self, '_list_select_job') and self._list_select_job:
                try:
                    self.root.after_cancel(self._list_select_job)
                except Exception:
                    pass
                
            self._list_select_job = self.root.after(15, lambda: self._deferred_list_select(oid))

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

        if hasattr(self, "left_pinned") and not self.left_pinned.get() and getattr(self, "_drawer_is_open", False):
            self.close_drawer()



    def _format_int_like(self, value):
        if pd.isna(value) or value == "":
            return "Unknown"
        if isinstance(value, float) and value.is_integer():
            return str(int(value))
        return str(value)

    def load_object(self, oid, is_history_nav=False):
        # Convert oid type for pandas index compatibility (checks string first, then integer if needed)
        if oid not in self.reg_by_id.index:
            try:
                if str(oid).isdigit():
                    int_oid = int(oid)
                    if int_oid in self.reg_by_id.index:
                        oid = int_oid
            except Exception:
                pass

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
            self.commit_current_object()
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

            reg_dict = self._get_reg_dict()
            obs_dict = self._get_obs_dict()
            reg = reg_dict.get(oid)
            if reg is None:
                try:
                    reg = self.reg_by_id.loc[oid]
                    if isinstance(reg, pd.DataFrame):
                        reg = reg.iloc[0].to_dict()
                    elif isinstance(reg, pd.Series):
                        reg = reg.to_dict()
                except Exception:
                    reg = {}
            obs = obs_dict.get(oid)
            if obs is None:
                try:
                    obs = self.obs_by_id.loc[oid]
                    if isinstance(obs, pd.DataFrame):
                        obs = obs.iloc[0].to_dict()
                    elif isinstance(obs, pd.Series):
                        obs = obs.to_dict()
                except Exception:
                    obs = {}


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
                var.set(utils.fmt_pandas_val(val))


            # Location and registration fields updated from obs/reg dicts
            

            for col, widget in self.reg_entries.items():
                value = utils.fmt_pandas_val(reg.get(col, ""))


                if isinstance(widget, tk.Text):
                    if not skip_heavy:
                        widget.delete("1.0", tk.END)
                        widget.insert("1.0", str(value))
                        try:
                            widget.edit_reset()
                        except tk.TclError:
                            pass
                else:
                    if self.reg_vars[col].get() != value:
                        self.reg_vars[col].set(value)
                    if isinstance(widget, ttk.Combobox) and col not in self.choice_fields:
                        vals = self.current_object_suggestions.get(col, [])
                        widget.configure(values=vals)

            for prob_col, v in self.problem_vars.items():
                val = obs.get(prob_col, False)
                obs_val = bool(val) if not pd.isna(val) else False

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

            # Save the loaded state of all problem checkbuttons so we can detect real edits later
            self.loaded_problem_states = {
                col: bool(v.get()) for col, v in self.problem_vars.items()
            }

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

        self._validate_fields()

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
        val = self.app.df_obs.loc[oid, "Images_Missing"]
        if isinstance(val, pd.Series):
            return not bool(val.iloc[0])
        return not bool(val)







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
                self.commit_current_object()
                try:
                    self._write_excel(self.app.output_path)
                except Exception as e:
                    from utils import debug_error
                    debug_error("on_close sync save", str(e))
                    messagebox.showerror("Save Error", f"Failed to save on exit: {e}")
                    return

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
        win.minsize(sc(660), sc(420))  # U2-G: scaled to DPI
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
                import sys
                path = os.path.abspath(log_path)

                # Sanitize the argument to prevent argument injection.
                # Valid existing Windows paths cannot contain double quotes or other malicious injection characters.
                if '"' in path:
                    return

                if sys.platform.startswith("win"):
                    if os.path.exists(path):
                        subprocess.Popen(["explorer", "/select,", path])
                    else:
                        parent_dir = os.path.dirname(path)
                        if os.path.isdir(parent_dir):
                            subprocess.Popen(["explorer", parent_dir])
                elif sys.platform.startswith("darwin"):
                    if os.path.exists(path):
                        subprocess.Popen(["open", "-R", path])
                    else:
                        parent_dir = os.path.dirname(path)
                        if os.path.isdir(parent_dir):
                            subprocess.Popen(["open", parent_dir])
                else:
                    # Linux and other platforms
                    parent_dir = os.path.dirname(path) if not os.path.isdir(path) else path
                    if os.path.isdir(parent_dir):
                        subprocess.Popen(["xdg-open", parent_dir])
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
        for field in self.reg_entries:
            self._refresh_field_background(field)





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
        self._nav_idle_job = self.root.after(15, self._navigation_finished)

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

        # Fast load (15ms)
        if hasattr(self, '_list_select_job') and self._list_select_job:
            try:
                self.root.after_cancel(self._list_select_job)
            except Exception:
                pass
                
        self._list_select_job = self.root.after(15, lambda: self._deferred_list_select(oid))


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
        win.resizable(True, True)
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
            fg="#2c302e"
        ).pack(anchor="w", pady=(0, 15))

        # Input Grid container
        grid_frame = ttk.Frame(frame)
        grid_frame.pack(fill="both", expand=True)

        orig_location_entries = list(getattr(self, "location_entries", []))
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
                , cursor="hand2")
            elif ftype == "checkbox":
                widget = ttk.Checkbutton(
                    grid_frame, text="", variable=var,
                    onvalue="True", offvalue="False",
                    command=lambda n=name, v=var: self._on_checkbox_change(n, v)
                , cursor="hand2")
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
            bg="#2c302e", fg="#ffffff",
            font=("Segoe UI", sc(9.5), "bold"),
            relief="flat", bd=0, cursor="hand2",
            padx=16, pady=6,
            command=save_and_close
        )
        done_btn.pack(side="right")
        done_btn.bind("<Enter>", lambda e: done_btn.config(bg="#333333"))
        done_btn.bind("<Leave>", lambda e: done_btn.config(bg="#2c302e"))

        # CANCEL Button (Secondary outline style)
        cancel_btn = tk.Button(
            footer, text="CANCEL",
            bg=win.cget("bg"), fg="#2c302e",
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
        
        # When closing, restore self.location_entries.
        def restore_locations(e):
            if e.widget == win:
                self.location_entries = orig_location_entries

        win.bind("<Destroy>", restore_locations)

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
                row_frame, text="✔", fg="#3a7d44", bg=self.root.cget("bg"),
                font=("Segoe UI", sc(11), "bold")
            )
            lbl_icon.pack(side="left", padx=(0, 6))
            
            lbl_text = ttk.Label(
                row_frame, text="No active problems flagged.",
                foreground="#3a7d44",
                font=("Segoe UI", sc(9.5), "bold")
            )
            lbl_text.pack(side="left")
        else:
            for prob_name in active_problems:
                row_frame = ttk.Frame(self.problem_frame)
                row_frame.pack(fill="x", pady=2, padx=4)
                
                lbl_icon = tk.Label(
                    row_frame, text="⚠", fg="#c93a40", bg=self.root.cget("bg"),
                    font=("Segoe UI", sc(10), "bold")
                )
                lbl_icon.pack(side="left", padx=(0, 6))
                
                lbl_text = ttk.Label(
                    row_frame, text=prob_name.replace("_", " "),
                    foreground="#c93a40",
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
        win.resizable(True, True)
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
            fg="#c93a40"
        ).pack(side="left")

        # Checkbutton Grid container
        grid_frame = ttk.Frame(frame)
        grid_frame.pack(fill="both", expand=True)

        orig_problem_checkbuttons = list(getattr(self, "problem_checkbuttons", []))
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
                command=lambda: (
                    self.update_reg_fields_visibility(skip_snap=True),
                    self.commit_current_object()
                )
            , cursor="hand2")
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
            foreground="#c93a40",
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
            bg="#2c302e", fg="#ffffff",
            font=("Segoe UI", sc(9.5), "bold"),
            relief="flat", bd=0, cursor="hand2",
            padx=16, pady=6,
            command=save_and_close
        )
        done_btn.pack(side="right")
        done_btn.bind("<Enter>", lambda e: done_btn.config(bg="#333333"))
        done_btn.bind("<Leave>", lambda e: done_btn.config(bg="#2c302e"))

        # CANCEL Button (Secondary outline)
        cancel_btn = tk.Button(
            footer, text="CANCEL",
            bg=win.cget("bg"), fg="#2c302e",
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
        
        # When closing, restore self.problem_checkbuttons.
        def restore_problems(e):
            if e.widget == win:
                self.problem_checkbuttons = orig_problem_checkbuttons

        win.bind("<Destroy>", restore_problems)

    # ---------- Filter ----------
    def open_filter_menu(self):
        if hasattr(self, "filter_window") and self.filter_window and self.filter_window.winfo_exists():
            self.filter_window.lift()
            self.filter_window.focus_force()
            return

        from config import sc
        import utils
        
        COLORS = {
            "surface": "#fbfaf8",
            "surface_dim": "#dadada",
            "surface_container_low": "#f2f5f1",
            "surface_container_highest": "#e2e2e2",
            "on_surface": "#2c302e",
            "on_surface_variant": "#444748",
            "outline": "#747878",
            "outline_variant": "#c4c7c7",
            "primary": "#000000",
            "on_primary": "#ffffff",
            "secondary": "#3a7d44",
            "error": "#c93a40",
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

        # Global Match Mode Toggle (Right side of tab_nav)
        global_mode_frame = tk.Frame(tab_nav, bg=COLORS["surface_container_highest"])
        global_mode_frame.pack(side="right", fill="y", padx=sc(16))

        tk.Label(global_mode_frame, text="Match criteria:", font=FONT_LABEL, fg=COLORS["on_surface_variant"], bg=COLORS["surface_container_highest"]).pack(side="left", padx=(0, sc(8)))

        from tkinter import ttk
        style = ttk.Style(self.root)
        style.configure("GlobalMode.TCombobox", fieldbackground=COLORS["surface"], background=COLORS["surface"], borderwidth=0)

        def on_global_mode_change(event):
            val = global_mode_cb.get()
            if "ALL" in val.upper():
                self.filter_mode.set("AND")
            else:
                self.filter_mode.set("OR")
            self.update_filter_button_text()

        current_mode = self.filter_mode.get()
        cb_val = "All selected (AND)" if current_mode == "AND" else "Any selected (OR)"

        global_mode_cb = ttk.Combobox(global_mode_frame, values=["All selected (AND)", "Any selected (OR)"], state="readonly", width=18, style="GlobalMode.TCombobox", cursor="hand2")
        global_mode_cb.set(cb_val)
        global_mode_cb.pack(side="left", pady=sc(8))
        global_mode_cb.bind("<<ComboboxSelected>>", on_global_mode_change)

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
            chk = tk.Checkbutton(f, variable=var, bg=COLORS["surface"], activebackground=COLORS["surface"], selectcolor=COLORS["surface"], bd=0, highlightthickness=0, command=self.update_filter_button_text, cursor="hand2")
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
            rad = tk.Radiobutton(f, variable=var, value=val, bg=COLORS["surface"], activebackground=COLORS["surface"], bd=0, highlightthickness=0, cursor="hand2")
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

        p_status = create_group(status_left, "Processing Status")
        make_chk(p_status, "Reviewed", self.filter_vars["Reviewed"], COLORS["secondary"])
        make_chk(p_status, "Not Reviewed (Pending)", self.filter_vars["Not_Reviewed"], COLORS["surface_tint"])
        make_chk(p_status, "Reviewed + Has Problem", self.filter_vars["Reviewed_With_Problem"], COLORS["error"])
        make_chk(p_status, "Problem + Has History", self.filter_vars["Problem_With_History"], COLORS["error"])
        make_chk(p_status, "Has Suggestions from Books", self.filter_vars["Has_History"], COLORS["outline_variant"])

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
        probs_canvas.bind("<Configure>", lambda e: probs_canvas.itemconfig(probs_canvas_window, width=e.width) if getattr(probs_canvas, "_last_width", None) != e.width and not setattr(probs_canvas, "_last_width", e.width) else None)
        probs_canvas.configure(yscrollcommand=probs_scrollbar.set)
        
        probs_canvas.pack(side="left", fill="both", expand=True, padx=(sc(16), 0), pady=sc(16))
        probs_scrollbar.pack(side="right", fill="y", pady=sc(16))
        
        def _on_prob_scroll(event):
            probs_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        self.root.after(100, lambda: self._bind_canvas_mousewheel(probs_canvas, _on_prob_scroll))

        p_list = create_group(probs_inner, "Problems Checklist")
        normal_problems = [p for p in self.problem_columns if "Image" not in p]
        for col in normal_problems:
            make_chk(p_list, col.replace("_", " "), self.filter_vars.get(col), COLORS["error"])
        make_chk(p_list, "Any problem (except images)", self.filter_vars.get("Any_Problem"), COLORS["error"])
        
        u_list = create_group(probs_inner, "Unknown values")
        if not hasattr(self, "filter_unknown_var"):
            self.filter_unknown_var = tk.BooleanVar()
        make_chk(u_list, "Show objects with unknown fields", self.filter_unknown_var)

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

        # TAB 4: LOCATION
        tab_loc = tk.Frame(tab_content_area, bg=COLORS["surface"])
        self.filter_tabs["location"] = tab_loc
        
        loc_canvas = tk.Canvas(tab_loc, bg=COLORS["surface"], highlightthickness=0, bd=0)
        loc_scrollbar = tk.Scrollbar(tab_loc, orient="vertical", command=loc_canvas.yview)
        loc_inner = tk.Frame(loc_canvas, bg=COLORS["surface"])
        
        loc_inner.bind("<Configure>", lambda e: loc_canvas.configure(scrollregion=loc_canvas.bbox("all")))
        loc_canvas_window = loc_canvas.create_window((0, 0), window=loc_inner, anchor="nw")
        loc_canvas.bind("<Configure>", lambda e: loc_canvas.itemconfig(loc_canvas_window, width=e.width) if getattr(loc_canvas, "_last_width", None) != e.width and not setattr(loc_canvas, "_last_width", e.width) else None)
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
                cb = ttk.Combobox(ent_frame, textvariable=self.filter_location_vars[name], values=vals, state="readonly", style="Flat.TCombobox", cursor="hand2")
                cb.pack(fill="x", expand=True, padx=sc(2), pady=sc(2))
                cb.bind("<BackSpace>", lambda e, w=cb: (w.set(""), self.update_filter_button_text()))
                cb.bind("<Delete>", lambda e, w=cb: (w.set(""), self.update_filter_button_text()))
            else:
                ent = tk.Entry(ent_frame, textvariable=self.filter_location_vars[name], font=FONT_DATA, bg=COLORS["surface"], fg=COLORS["on_surface"], bd=0, insertbackground=COLORS["primary"])
                ent.pack(fill="x", expand=True, padx=sc(4), pady=sc(2))
                
            all_widgets.append((name.lower(), f, COLORS["surface"]))

        # Cache children for Quick Search
        for text, frame, orig_bg in all_widgets:
            cached = []
            for child in frame.winfo_children():
                if isinstance(child, tk.Frame) and child.cget("width") == 4: continue
                cached.append(child)
            frame._cached_children = cached

        # Quick Search
        def on_search(*args):
            q = search_var.get().lower().strip()
            for text, frame, orig_bg in all_widgets:
                if not q:
                    bg_color = orig_bg
                elif q in text:
                    bg_color = COLORS["surface_container_highest"]
                else:
                    bg_color = orig_bg

                frame.config(bg=bg_color)
                for child in getattr(frame, "_cached_children", []):
                    try: child.config(bg=bg_color)
                    except Exception: pass
                        
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
                "mode": self.filter_mode.get()
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

            # Load global mode or gracefully fallback from legacy multi-mode presets
            legacy_modes = preset.get("modes", {})
            if "mode" in preset:
                self.filter_mode.set(preset["mode"])
            elif legacy_modes:
                # If any legacy mode was AND, assume AND to be safe, else OR
                if any(m == "AND" for m in legacy_modes.values()):
                    self.filter_mode.set("AND")
                else:
                    self.filter_mode.set("OR")
            else:
                self.filter_mode.set("AND")
                    
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
            val = self.app.df_obs.loc[oid, prob_col]
            if isinstance(val, pd.Series):
                return bool(val.iloc[0])
            return bool(val)

      
        if prob_col == "Reviewed":
            val = self.app.df_obs.loc[oid, REVIEWED_COLUMN]
            if isinstance(val, pd.Series):
                return bool(val.iloc[0])
            return bool(val)

        if oid not in self.obs_by_id.index:
            return False

        if prob_col == "Has_Images":
            if self.image_mode == "online":
                return True
            elif self.image_mode == "offline":
                return False
            val = self.app.df_obs.loc[oid, "Images_Missing"]
            if isinstance(val, pd.Series):
                return not bool(val.iloc[0])
            return not bool(val)

        if prob_col == "Images_Missing":
            if self.image_mode in ("online", "offline"):
                return False
            val = self.app.df_obs.loc[oid, "Images_Missing"]
            if isinstance(val, pd.Series):
                return bool(val.iloc[0])
            return bool(val)

      
        obs_dict = self._get_obs_dict()
        obs = obs_dict.get(oid) or self.obs_by_id.loc[oid]
        if isinstance(obs, pd.DataFrame):
            obs = obs.iloc[0]

        reg_dict = self._get_reg_dict()
        reg = reg_dict.get(oid) or self.reg_by_id.loc[oid]
        if isinstance(reg, pd.DataFrame):
            reg = reg.iloc[0]

      
        value = obs.get(prob_col, False)
        if isinstance(value, pd.Series):
            value = value.iloc[0]

        obs_val = bool(value)

      
        auto_val = False

   
        if prob_col in self.problem_to_field:
            field = self.problem_to_field.get(prob_col)
            if not field or field not in reg:
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

            if key in ["Images_Missing", "Has_Images"]:
                groups["Images"].append(key)

            elif key in self.problem_columns:
                if "Image" in key:
                    groups["Images"].append(key)
                else:
                    groups["Problems"].append(key)

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
        history_set = getattr(self, "_has_suggestions_set", None)
        if (history_set is None or len(history_set) == 0) and getattr(self.app, "historical_dbs", None) and hasattr(self, "collect_historical_suggestions"):
            history_set = set()
            for oid in getattr(self.app, "active_object_ids", []):
                sug = self.collect_historical_suggestions(oid, show_all_override=False)
                if sug and any(list(v.keys()) != ["(No data found)"] for v in sug.values()):
                    history_set.add(oid)
                    s_oid = str(oid)
                    history_set.add(s_oid)
                    if s_oid.isdigit():
                        history_set.add(int(s_oid))
            self._has_suggestions_set = history_set
        elif history_set is None:
            history_set = set()

        building_var = self.filter_location_vars.get("Building")
        floor_var = self.filter_location_vars.get("Floor")
        cabinet_var = self.filter_location_vars.get("Cabinet")

        building_filter = building_var.get() if building_var else ""
        floor_filter = floor_var.get() if floor_var else ""
        cabinet_filter = cabinet_var.get().strip().lower() if cabinet_var else ""

        matched = self.filter_manager.apply_filter(
            df_reg=self.app.df_reg,
            reg_dict=reg_dict,
            obs_dict=obs_dict,
            history_set=history_set,
            groups=groups,
            global_mode=filter_state["mode"],
            not_reviewed_only=not_reviewed_only,
            location_filters=(building_filter, floor_filter, cabinet_filter),
            problem_columns=self.problem_columns,
            problem_to_field=self.problem_to_field,
            unknown_fields=self.unknown_fields,
            image_mode=self.image_mode
        )

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

 
        if self.image_mode == "online":
            has_images = True
        elif self.image_mode == "offline":
            has_images = False
        else:
            val = self.app.df_obs.loc[oid, "Images_Missing"]
            if isinstance(val, pd.Series):
                has_images = not bool(val.iloc[0])
            else:
                has_images = not bool(val)

   
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
        if oid in self._problem_cache:
            return self._problem_cache[oid]
        s_oid = str(oid)
        if s_oid in self._problem_cache:
            return self._problem_cache[s_oid]
        if s_oid.isdigit():
            i_oid = int(s_oid)
            if i_oid in self._problem_cache:
                return self._problem_cache[i_oid]

        # If not cached, calculate and store
        try:
            val = self.has_any_problem(
                oid,
                include_image_problems=(self.image_mode == "folder")
            )
            self._problem_cache[oid] = val
            self._problem_cache[s_oid] = val
            return val
        except Exception:
            self._problem_cache[oid] = False
            return False

    def _has_history(self, oid):
        """Returns True if object appears in any loaded historical database."""
        if not self.app.historical_dbs:
            return False
            
        try:
            lookup_key = int(oid) if str(oid).isdigit() else oid
        except Exception:
            lookup_key = oid

        for db in self.app.historical_dbs:
            reg_by_id = db.get("reg_by_id")
            if reg_by_id is not None:
                if lookup_key in reg_by_id.index or str(oid) in reg_by_id.index:
                    return True
        return False

    # ---- Live Search methods ----
    def _on_inline_search_key(self, event=None):
        """Debounce: wait 250ms after last keystroke before filtering."""
        # Ignore non-text navigation/modifier keys
        if event and event.keysym in (
            "Up", "Down", "Return", "Escape", "Tab", 
            "Shift_L", "Shift_R", "Control_L", "Control_R", "Alt_L", "Alt_R",
            "Left", "Right", "Home", "End"
        ):
            return

        query = self._inline_search_var.get()
        if hasattr(self, "_last_search_query") and query == self._last_search_query:
            return
        self._last_search_query = query

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
            matched = self.search_engine.apply_search(query, index)

            if matched is None:
                matched = []

            self.app.active_object_ids = matched
            self.refresh_list()

            total = len(self.app.df_reg) if self.app.df_reg is not None else 0
            color = "green" if matched else "red"
            self._search_count_label.config(text=f"{len(matched)}/{total}", foreground=color)
        finally:
            self._is_applying_search = False

    def _clear_inline_search(self, event=None):
        self._inline_search_var.set("")
        self._last_search_query = self._inline_search_placeholder
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

    def _on_search_arrow_down(self, event=None):
        if not self.app.active_object_ids:
            return "break"
        sel = self.object_list.curselection()
        if sel:
            curr_idx = sel[0]
            new_idx = min(curr_idx + 1, len(self.app.active_object_ids) - 1)
        else:
            new_idx = 0
            
        self.object_list.selection_clear(0, tk.END)
        self.object_list.selection_set(new_idx)
        self.object_list.see(new_idx)
        return "break"

    def _on_search_arrow_up(self, event=None):
        if not self.app.active_object_ids:
            return "break"
        sel = self.object_list.curselection()
        if sel:
            curr_idx = sel[0]
            new_idx = max(curr_idx - 1, 0)
        else:
            new_idx = 0
            
        self.object_list.selection_clear(0, tk.END)
        self.object_list.selection_set(new_idx)
        self.object_list.see(new_idx)
        return "break"

    def _get_search_index(self):
        """
        Return the search index {oid: token_dict}.
        During startup the index is pre-built by _precompute_startup_caches() so this
        method just returns the cached result. After a data-changing operation that
        calls invalidate_search_index(), the cache is rebuilt lazily here covering
        ALL registration columns for maximum recall.
        """
        if self._search_index_cache is not None:
            return self._search_index_cache

        self._search_index_cache = self.search_engine.get_search_index(
            self.app.df_reg,
            self._get_reg_dict()
        )
        return self._search_index_cache

    def invalidate_search_index(self):
        """Call after any data change that affects Genus, Species, or ObjectID."""
        self._search_index_cache = None
        self.search_engine.invalidate_search_index()

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
        
        # Commit current changes before loading the new object
        if not self._is_navigating:
            self._is_navigating = True
            self.commit_current_object()
            
        if self._nav_idle_job:
            try:
                self.root.after_cancel(self._nav_idle_job)
            except Exception:
                pass
        self._nav_idle_job = self.root.after(150, self._navigation_finished)
        
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
        
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S") if value else ""
        
        for oid in selection:
            try:
                lookup_key = int(oid) if str(oid).isdigit() and int(oid) in self.app.df_obs.index else oid
            except Exception:
                lookup_key = oid

            self.app.redo_stacks.setdefault(lookup_key, []).clear()
            self.app.df_obs.at[lookup_key, REVIEWED_COLUMN] = value
            self.app.df_obs.at[lookup_key, REVIEWED_AT_COLUMN] = now

            if getattr(self, "_cached_obs_dict", None) is not None and lookup_key in self._cached_obs_dict:
                self._cached_obs_dict[lookup_key][REVIEWED_COLUMN] = value
                self._cached_obs_dict[lookup_key][REVIEWED_AT_COLUMN] = now
            if getattr(self, "_cached_reviewed_dict", None) is not None:
                self._cached_reviewed_dict[lookup_key] = value
                self._cached_reviewed_dict[oid] = value

            s_oid = str(oid)
            self._problem_cache.pop(oid, None)
            self._problem_cache.pop(s_oid, None)
            if s_oid.isdigit():
                self._problem_cache.pop(int(s_oid), None)

            # Update item values so CardView item_data is synchronized
            current_vals = list(self.object_list.item(oid, "values") or [])
            if current_vals:
                current_vals[0] = "☑" if value else "☐"
                self.object_list.item(oid, values=current_vals)

            self.update_list_item_color(oid)
            self.log_action("REVIEWED" if value else "NOT_REVIEWED", ["Reviewed"], [f'Reviewed: "{value}"'], oid=lookup_key)
            
        self.app.dirty = True
        self.update_dirty_ui()
        self.update_review_progress()
        self.update_reviewed_button_state()
        
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
                            if field and field in reg_row:
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
        history_set = getattr(self, "_has_suggestions_set", set())
        if history_set is None:
            history_set = set()

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
            self.object_list._schedule_viewport_update()


    def update_filter_button_text(self):
        active = [k for k, v in self.filter_vars.items() if v.get()]

        if getattr(self, "filter_unknown_var", None) and self.filter_unknown_var.get():
            active.append("Unknown")

        if hasattr(self, "filter_location_vars"):
            for loc_k, loc_v in self.filter_location_vars.items():
                val = loc_v.get().strip() if hasattr(loc_v, "get") else ""
                if val:
                    active.append(f"{loc_k}:{val}")

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

        # Vectorized assignment for efficiency
        self.app.df_obs.loc[ids, REVIEWED_COLUMN] = value
        self.app.df_obs.loc[ids, REVIEWED_AT_COLUMN] = now

        for oid in ids:
            self.log_action("REVIEWED" if value else "NOT_REVIEWED", ["Reviewed"], [f'Reviewed: "{value}"'], oid=oid)

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
        self.open_recent_activity_window(default_tab=0)



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
                try:
                    widget.edit_reset()
                except tk.TclError:
                    pass
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

            # Check if location should be in the left column or center column
            loc_in_center = hasattr(self, 'location_in_center_var') and self.location_in_center_var.get()

            if show_loc and not loc_in_center:
                if str(self.left_bottom_container) not in self.left_panes.panes():
                    self.left_panes.add(self.left_bottom_container, weight=0)
                self.loc_container.pack(side="top", fill="x")
            else:
                # Either we're hiding location entirely (due to focus mode) OR it's centered
                # If it's centered, it's managed by `_sync_middle_panes` instead.
                # So we just ensure it's not in the left pane.
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
                if frame.winfo_manager() != "grid":
                    frame.grid()
                visible_count += 1
            else:
                if frame.winfo_manager() == "grid":
                    frame.grid_remove()
                

        # Unknown/missing values section
        if hasattr(self, "unknown_fields_container"):
            frame = self.unknown_fields_container
            is_visible = True
            if focus_active:
                is_visible = False
                
            if is_visible:
                if frame.winfo_manager() != "grid":
                    frame.grid()
                visible_count += 1
            else:
                if frame.winfo_manager() == "grid":
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




    def _refresh_field_background(self, field_name):
        widget = self.reg_entries.get(field_name)
        if not widget:
            return

        is_dark = getattr(self, "dark_mode_active", self.app.config.get("theme", "dark") == "dark")
        norm_bg = "#212622" if is_dark else "#ffffff"
        warn_bg = "#5c4d00" if is_dark else "#fff3cd"
        err_bg = "#5c1e1e" if is_dark else "#f8d7da"
        unknown_bg = "#5c461a" if is_dark else "#ffe4b3"
        suggest_bg = "#5c571a" if is_dark else "#fff3a3"

        # Determine if there's an active problem flag mapping to this field
        is_active_problem = False
        prob_col = None
        for p_col, f_name in self.problem_to_field.items():
            if f_name == field_name:
                prob_col = p_col
                break
        if prob_col and self.problem_vars.get(prob_col) and self.problem_vars[prob_col].get():
            is_active_problem = True

        # Validation rules
        genus = self.reg_vars.get("Genus", tk.StringVar()).get().strip()
        species = self.reg_vars.get("Species", tk.StringVar()).get().strip()
        building = self.reg_vars.get("Building", tk.StringVar()).get().strip()
        loc_prob = self.problem_vars.get("Loc_Problem", tk.BooleanVar()).get()

        color = norm_bg

        if is_active_problem:
            # Active problem tint highlight
            hl_color_name = "Default (Red)"
            try:
                import config
                advanced_prefs = config.load_prefs().get("advanced", {})
                if advanced_prefs.get("enable_problem_highlights", True):
                    hl_color_name = advanced_prefs.get("problem_highlight_color", "Default (Red)")
            except Exception:
                pass
            
            if "Yellow" in hl_color_name:
                tint = "#5f5b2e" if is_dark else "#fff9c4"
            elif "Orange" in hl_color_name:
                tint = "#5f4520" if is_dark else "#ffe0b2"
            elif "Blue" in hl_color_name:
                tint = "#203a5f" if is_dark else "#e3f2fd"
            else:  # Default (Red)
                tint = "#5c1e1e" if is_dark else "#ffdad6"
            color = tint
        elif field_name == "Species" and genus and not species:
            color = warn_bg
        elif field_name == "Building" and not building and not loc_prob:
            color = err_bg
        else:
            # Unknown or Historical Suggestions
            raw_val = self.reg_vars.get(field_name, tk.StringVar()).get()
            if isinstance(raw_val, pd.Series):
                raw_val = raw_val.iloc[0]
            raw_val = str(raw_val)

            if self.is_unknown(raw_val):
                color = unknown_bg
            elif getattr(self, "show_all_history_var", None) and self.show_all_history_var.get():
                if self.current_object_suggestions and field_name in self.collect_historical_suggestions(self.app.current_object_id):
                    color = suggest_bg
            else:
                color = norm_bg

        # Set background/style on widget
        try:
            if isinstance(widget, (tk.Text, tk.Entry)):
                widget.config(background=color)
            elif isinstance(widget, ttk.Combobox):
                if color == warn_bg:
                    widget.configure(style="Warning.TCombobox")
                elif color == err_bg:
                    widget.configure(style="Error.TCombobox")
                elif is_active_problem:
                    widget.configure(style="Problem.TCombobox")
                else:
                    widget.configure(style="TCombobox")
            elif isinstance(widget, ttk.Entry):
                if color == warn_bg:
                    widget.configure(style="Warning.TEntry")
                elif color == err_bg:
                    widget.configure(style="Error.TEntry")
                elif is_active_problem:
                    widget.configure(style="Problem.TEntry")
                else:
                    widget.configure(style="TEntry")
        except Exception as e:
            debug_error("Suppressed Error in _refresh_field_background", str(e))


    def _validate_fields(self, event=None):
        if self._is_navigating or self.loading_object:
            return

        for f_name in self.reg_entries.keys():
            self._refresh_field_background(f_name)


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
            genus_dict = getattr(self, "_cached_genus_dict", None)
            def get_genus(oid):
                if genus_dict is not None and oid in genus_dict:
                    return str(genus_dict[oid] or "").lower()
                val = self.app.df_reg.loc[oid]
                if isinstance(val, pd.DataFrame):
                    val = val.iloc[0]
                return str(val.get("Genus", "")).lower()
            sorted_ids = sorted(ids, key=get_genus, reverse=not ascending)
        elif col == "Species":
            species_dict = getattr(self, "_cached_species_dict", None)
            def get_species(oid):
                if species_dict is not None and oid in species_dict:
                    return str(species_dict[oid] or "").lower()
                val = self.app.df_reg.loc[oid]
                if isinstance(val, pd.DataFrame):
                    val = val.iloc[0]
                return str(val.get("Species", "")).lower()
            sorted_ids = sorted(ids, key=get_species, reverse=not ascending)
        elif col == "Status":
            def status_key(oid):
                try:
                    val = self.app.df_obs.loc[oid, REVIEWED_COLUMN]
                    if isinstance(val, pd.Series):
                        reviewed = bool(val.iloc[0])
                    else:
                        reviewed = bool(val)
                except Exception:
                    reviewed = False
                has_problem = self._get_cached_problem(oid)
                has_history = self._problems_have_history(oid)
                
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


    def _bind_canvas_mousewheel(self, canvas, handler):
        """Bind mousewheel to a canvas without touching any child bindtags."""
        canvas.bind("<MouseWheel>", handler)



    def _on_reviewed_clicked(self):
        """Mark as reviewed and automatically advance if autoAdvanceOnReview is enabled."""
        self.mark_current_as_reviewed()

    def _animate_reviewed_button(self, target_bg, target_fg, duration_ms=80):
        # Cancel any previous animation
        if hasattr(self, "_btn_anim_id") and self._btn_anim_id:
            try:
                self.root.after_cancel(self._btn_anim_id)
            except Exception:
                pass
            self._btn_anim_id = None
        
        try:
            start_bg = self.reviewed_button.cget("bg")
            start_fg = self.reviewed_button.cget("fg")
        except Exception:
            start_bg = target_bg
            start_fg = target_fg
            
        def parse_color(c):
            try:
                r_16, g_16, b_16 = self.reviewed_button.winfo_rgb(c)
                return (r_16 // 256, g_16 // 256, b_16 // 256)
            except Exception:
                c_hex = str(c).lstrip('#')
                if len(c_hex) == 3:
                    c_hex = "".join(x*2 for x in c_hex)
                try:
                    return (int(c_hex[0:2], 16), int(c_hex[2:4], 16), int(c_hex[4:6], 16))
                except Exception:
                    return (128, 128, 128)

        start_bg_rgb = parse_color(start_bg)
        start_fg_rgb = parse_color(start_fg)
        target_bg_rgb = parse_color(target_bg)
        target_fg_rgb = parse_color(target_fg)
        
        steps = 8
        interval = 10
        
        def step(current_step):
            if not self.root.winfo_exists() or not self.reviewed_button.winfo_exists():
                self._btn_anim_id = None
                return
            if current_step > steps:
                try:
                    self.reviewed_button.config(bg=target_bg, fg=target_fg)
                except Exception:
                    pass
                self._btn_anim_id = None
                return
            
            p = current_step / steps
            bg_r = int(start_bg_rgb[0] + (target_bg_rgb[0] - start_bg_rgb[0]) * p)
            bg_g = int(start_bg_rgb[1] + (target_bg_rgb[1] - start_bg_rgb[1]) * p)
            bg_b = int(start_bg_rgb[2] + (target_bg_rgb[2] - start_bg_rgb[2]) * p)
            
            fg_r = int(start_fg_rgb[0] + (target_fg_rgb[0] - start_fg_rgb[0]) * p)
            fg_g = int(start_fg_rgb[1] + (target_fg_rgb[1] - start_fg_rgb[1]) * p)
            fg_b = int(start_fg_rgb[2] + (target_fg_rgb[2] - start_fg_rgb[2]) * p)
            
            color_bg = f"#{bg_r:02x}{bg_g:02x}{bg_b:02x}"
            color_fg = f"#{fg_r:02x}{fg_g:02x}{fg_b:02x}"
            
            try:
                self.reviewed_button.config(bg=color_bg, fg=color_fg)
            except Exception:
                pass
                
            self._btn_anim_id = self.root.after(interval, lambda: step(current_step + 1))
            
        step(0)

    def update_reviewed_button_state(self):
        oid = self.app.current_object_id
        large_size = self.large_reviewed_button_var.get()
        padx_val = sc(32) if large_size else sc(18)
        pady_val = sc(14) if large_size else sc(8)

        if not oid:
            self.reviewed_button.config(
                text="✓ Mark as Reviewed",
                state="disabled",
                activebackground="#f2f5f1",
                activeforeground="gray",
                highlightbackground="gray",
                padx=padx_val, pady=pady_val
            )
            self._animate_reviewed_button("#f2f5f1", "gray")
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
                activebackground="#f2f5f1",
                activeforeground="#3a7d44",
                highlightbackground="#3a7d44",
                padx=padx_val, pady=pady_val
            )
            self._animate_reviewed_button("#ffffff", "#3a7d44")
        else:
            self.reviewed_button.config(
                text="✓ MARK AS REVIEWED",
                activebackground="#2e5228",
                activeforeground="#ffffff",
                highlightbackground="#3a7d44",
                padx=padx_val, pady=pady_val
            )
            self._animate_reviewed_button("#3a7d44", "#ffffff")

    def _on_reviewed_btn_enter(self, event):
        if not self.app.current_object_id:
            return
        if hasattr(self, "_btn_anim_id") and self._btn_anim_id:
            try:
                self.root.after_cancel(self._btn_anim_id)
            except Exception:
                pass
            self._btn_anim_id = None
        if bool(self.reviewed_var.get()):
            self.reviewed_button.config(bg="#f2f5f1")
        else:
            self.reviewed_button.config(bg="#2e5228")

    def _on_reviewed_btn_leave(self, event):
        if not self.app.current_object_id:
            return
        if hasattr(self, "_btn_anim_id") and self._btn_anim_id:
            try:
                self.root.after_cancel(self._btn_anim_id)
            except Exception:
                pass
            self._btn_anim_id = None
        if bool(self.reviewed_var.get()):
            self.reviewed_button.config(bg="#ffffff")
        else:
            self.reviewed_button.config(bg="#3a7d44")

    def _on_reviewed_btn_press(self, event):
        if not self.app.current_object_id:
            return
        if hasattr(self, "_btn_anim_id") and self._btn_anim_id:
            try:
                self.root.after_cancel(self._btn_anim_id)
            except Exception:
                pass
            self._btn_anim_id = None
        if bool(self.reviewed_var.get()):
            self.reviewed_button.config(bg="#dcdcdc")
        else:
            self.reviewed_button.config(bg="#203f1b")

    def _on_reviewed_btn_release(self, event):
        if not self.app.current_object_id:
            return
        if hasattr(self, "_btn_anim_id") and self._btn_anim_id:
            try:
                self.root.after_cancel(self._btn_anim_id)
            except Exception:
                pass
            self._btn_anim_id = None
        x = event.x
        y = event.y
        w = event.widget.winfo_width()
        h = event.widget.winfo_height()
        inside = (0 <= x <= w) and (0 <= y <= h)
        if inside:
            if bool(self.reviewed_var.get()):
                self.reviewed_button.config(bg="#f2f5f1")
            else:
                self.reviewed_button.config(bg="#2e5228")
        else:
            if bool(self.reviewed_var.get()):
                self.reviewed_button.config(bg="#ffffff")
            else:
                self.reviewed_button.config(bg="#3a7d44")

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

    def _update_problem_row_style(self, field_name, is_active, enable_hl_override=None, color_override=None):
        """Apply or remove the red visual treatment on a registration row.

        Called whenever a mapped problem var changes (trace) or on load.
        Updates three elements independently so any missing ref is safe to skip:
          1. Left border bar (3px tk.Frame) — red accent or transparent
          2. Field label (ttk.Label) — error foreground or normal
          3. Entry / Combobox widget — Problem.TEntry style or TEntry
        """
        # Get advanced settings for highlights
        import config
        prefs = config.load_prefs() or {}
        advanced_prefs = prefs.get("advanced", {})
        enable_hl = enable_hl_override if enable_hl_override is not None else prefs.get("enable_problem_highlights", advanced_prefs.get("enable_problem_highlights", True))
        hl_color_name = color_override if color_override is not None else prefs.get("problem_highlight_color", advanced_prefs.get("problem_highlight_color", "Default (Red)"))

        is_dark = getattr(self, "dark_mode_active", False)
        
        # Determine colors
        if not enable_hl:
            err_fg = "#e8ebe9" if is_dark else "#2c302e"
            bar_active = "#181c19" if is_dark else "#f2f5f1"
            tint = "#181c19" if is_dark else "#ffffff"
        else:
            if "Yellow" in hl_color_name:
                err_fg = "#f9e2af" if is_dark else "#b28000"
                bar_active = "#f9e2af" if is_dark else "#b28000"
                tint = "#5f5b2e" if is_dark else "#fff9c4"
            elif "Orange" in hl_color_name:
                err_fg = "#fab387" if is_dark else "#b25900"
                bar_active = "#fab387" if is_dark else "#b25900"
                tint = "#5f4520" if is_dark else "#ffe0b2"
            elif "Blue" in hl_color_name:
                err_fg = "#89b4fa" if is_dark else "#0066b2"
                bar_active = "#89b4fa" if is_dark else "#0066b2"
                tint = "#203a5f" if is_dark else "#e3f2fd"
            else:  # Default (Red)
                err_fg = "#c93a40" if is_dark else "#c93a40"
                bar_active = "#c93a40" if not is_dark else "#c93a40"
                tint = "#5c1e1e" if is_dark else "#ffdad6"

        norm_fg     = "#e8ebe9" if is_dark else "#2c302e"
        bar_normal  = "#181c19" if is_dark else "#f2f5f1"  # matches ttk.Frame bg — invisible

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
        self._refresh_field_background(field_name)
                
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

    def _update_all_problem_row_styles(self, enable_hl_override=None, color_override=None):
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
                self._update_problem_row_style(field_name, is_active, enable_hl_override=enable_hl_override, color_override=color_override)
        
        self._update_accordion_badges()

    def update_list_item_color(self, oid):
        if not self.app.active_object_ids or oid not in self.app.active_object_ids:
            return
            
        if getattr(self, "_cached_reviewed_dict", None) is not None:
            reviewed = bool(self._cached_reviewed_dict.get(oid, False))
        elif getattr(self, "_cached_obs_dict", None) is not None and oid in self._cached_obs_dict:
            reviewed = bool(self._cached_obs_dict[oid].get(REVIEWED_COLUMN, False))
        else:
            try:
                reviewed = bool(self.app.df_obs.loc[oid, REVIEWED_COLUMN])
            except Exception:
                reviewed = False
            
        has_problem = self._get_cached_problem(oid)
        has_history = self._problems_have_history(oid)
        
        color = None
        if reviewed:
            color = "#4CAF50" if self.dark_mode_active else "#2E7D32"
        elif has_problem and has_history:
            color = "#BB86FC" if self.dark_mode_active else "#7B1FA2"
        elif has_problem:
            color = "#f28b82" if self.dark_mode_active else "#C62828"
        elif has_history:
            color = "#5ab0e8" if self.dark_mode_active else "#0284C7"
            
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

        if hasattr(self.object_list, "refresh_object_card"):
            self.object_list.refresh_object_card(oid)
        elif hasattr(self.object_list, "_refresh_card_accent"):
            self.object_list._refresh_card_accent(oid)

    def mark_current_as_reviewed(self):
        oid = self.app.current_object_id
        if not oid:
            return
        was_reviewed = bool(self.reviewed_var.get())
        self._toggle_reviewed_for_id(oid)
        
        # If toggled ON to Reviewed:
        if not was_reviewed:
            if self.autoAdvanceOnReview:
                if oid in self.app.active_object_ids:
                    idx = self.app.active_object_ids.index(oid)
                    if idx + 1 < len(self.app.active_object_ids):
                        self.navigate_object(1)
            elif getattr(self, "auto_advance_history_var", None) and self.auto_advance_history_var.get():
                self.goto_next_problem_with_history()

    def _toggle_reviewed_for_id(self, oid):
        if not oid:
            return
        self.push_undo_state()
        
        # Toggle in df_obs
        try:
            lookup_key = int(oid) if str(oid).isdigit() and int(oid) in self.app.df_obs.index else oid
        except Exception:
            lookup_key = oid

        current = False
        if self.app.df_obs is not None and lookup_key in self.app.df_obs.index:
            try:
                current = bool(self.app.df_obs.loc[lookup_key, REVIEWED_COLUMN])
            except Exception:
                pass
        new_val = not current
        
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S") if new_val else ""
        self.app.df_obs.at[lookup_key, REVIEWED_COLUMN] = new_val
        self.app.df_obs.at[lookup_key, REVIEWED_AT_COLUMN] = now

        if getattr(self, "_cached_obs_dict", None) is not None and lookup_key in self._cached_obs_dict:
            self._cached_obs_dict[lookup_key][REVIEWED_COLUMN] = new_val
            self._cached_obs_dict[lookup_key][REVIEWED_AT_COLUMN] = now
        if getattr(self, "_cached_reviewed_dict", None) is not None:
            self._cached_reviewed_dict[lookup_key] = new_val
            self._cached_reviewed_dict[oid] = new_val

        s_oid = str(oid)
        self._problem_cache.pop(oid, None)
        self._problem_cache.pop(s_oid, None)
        if s_oid.isdigit():
            self._problem_cache.pop(int(s_oid), None)

        # Synchronize CardView item_data
        current_vals = list(self.object_list.item(oid, "values") or [])
        if current_vals:
            current_vals[0] = "☑" if new_val else "☐"
            self.object_list.item(oid, values=current_vals)
        
        # If this is the currently active object, also update the checkbox variable
        if oid == self.app.current_object_id:
            self.reviewed_var.set(new_val)
            self.reviewed_time_label.config(text=now if new_val else "")

        self.log_action("REVIEWED" if new_val else "NOT_REVIEWED", ["Reviewed"], [f'Reviewed: "{new_val}"'], oid=lookup_key)
            
        self.app.dirty = True
        self.update_dirty_ui()
        self.update_list_item_color(oid)
        self.update_review_progress()
        self._list_dirty = True
        self.update_reviewed_button_state()




    def load_ignored_words(self):
        import json
        read_path = self.ignored_words_file
        if not os.path.exists(read_path):
            try:
                from utils import get_resource_path
                bundled = get_resource_path("ignored_words.json")
                if os.path.exists(bundled):
                    read_path = bundled
            except Exception:
                pass

        if os.path.exists(read_path):
            try:
                with open(read_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.ignored_words = data.get("words", [])
                    self.ignored_words_variations.set(data.get("variations", True))
            except Exception as e:
                debug_error("Load ignored words failed", str(e))
                self.ignored_words = []
        else:
            self.ignored_words = []
            self.ignored_words_variations.set(True)
            try:
                self.save_ignored_words()
            except Exception:
                pass

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
        
        bg_color = "#181c19" if self.dark_mode_active else "#f0f0f0"
        fg_color = "#e8ebe9" if self.dark_mode_active else "black"
        field_bg = "#212622" if self.dark_mode_active else "white"
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
        , cursor="hand2")
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

