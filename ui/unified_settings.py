"""
ui/unified_settings.py - Unified Settings UI for Arbor

Consolidates General Settings, Layout Settings, Focus Settings, Advanced Settings,
and Tools into a clean, modern, single-window layout with vertical sidebar navigation.

Designed as a self-contained, modular component that can run standalone for development
or be integrated into the main Arbor application via open_unified_settings().
"""

import os
import sys
import tkinter as tk
from tkinter import ttk, messagebox

# Adjust path for standalone execution
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.abspath(os.path.join(current_dir, ".."))
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

import config
from config import sc
from ui.widgets import ToggleSwitch, create_toggle_row, create_info_badge
from ui.state import app_bus, SETTINGS_CHANGED, LAYOUT_CHANGED

SETTING_INFO_TEXTS = {
    "focus_fallback": (
        "When Focus Mode is active, records without open problems automatically display standard "
        "registration fields so you are never left with an empty screen.\n\n"
        "Excel Impact: Displays default catalog fields from the 'Registration' sheet even when all "
        "problem flag columns on the 'Observation' sheet are FALSE."
    ),
    "focus_dynamic_update": (
        "As you navigate between specimen cards, the form dynamically shows only the specific fields "
        "that have problem flags for that active record.\n\n"
        "Excel Impact: Filters visible inputs based on which problem columns are set to TRUE in "
        "the 'Observation' sheet row for the active ObjectID."
    ),
    "snap_lock": (
        "Automatically snaps and adjusts panel widths when entering Focus Mode to optimize visible "
        "screen space for problem fields and specimen photos.\n\n"
        "Technical: Smoothly adjusts workspace sash dividers without modifying any saved database fields."
    ),
    "image_url_pattern_override": (
        "Custom web address template for viewing specimen photographs online if your museum hosts scans on a web server.\n\n"
        "Data Tokens: {id} (Alphanumeric ID), {num} (Numeric only), {num:04d} (4-digit padded), {suffix} (photo variant).\n"
        "Excel Impact: Overrides default URL generation for links stored in the 'Photo' sheet. Leave blank for default."
    ),
    "image_resampling_algorithm": (
        "Rendering filter used during image zoom to ensure label handwriting and plant parts remain legible:\n\n"
        "• LANCZOS: Maximum clarity and sharpness (best for reading faded handwriting).\n"
        "• BILINEAR: Smooth and balanced performance.\n"
        "• NEAREST: No smoothing (pixelated), fastest for low-spec computer hardware."
    ),
    "auto_advance_history": (
        "After accepting a historical suggestion to resolve a conflict, Arbor immediately jumps to "
        "the next card that has outstanding historical suggestions.\n\n"
        "Excel Impact: Applies accepted values to the 'Registration' sheet, records the edit in the "
        "'Log' sheet, and advances to the next conflicting record."
    ),
    "autosave_archive_limit": (
        "The threshold of historical session backups stored before Arbor prompts you to review or clean up old restore points.\n\n"
        "Excel / Safety: Timestamped backup copies of your workbook are preserved in the '.arbor_backups/' "
        "folder to ensure no curation work can be lost."
    ),
    "enable_excel_import_backup": (
        "Automatically generates a timestamped safety backup copy of your current dataset before importing external Excel sheets.\n\n"
        "Excel / Safety: Creates a safety snapshot inside 'backups/' before any external import to prevent overwriting records."
    ),
    "strict_input_validation": (
        "Enforces strict data format checks before committing edits or navigating away, ensuring consistent data entry.\n\n"
        "Excel Impact: Validates text formatting before writing to the 'Registration' sheet rather than solely showing a visual tint."
    ),
    "require_mobile_pin": (
        "Requires security PIN authentication for phone or tablet devices connecting via the Mobile Companion.\n\n"
        "Network / Security: When enabled, mobile browsers must enter the 4-digit PIN shown on the computer screen before viewing records."
    ),
    "mobile_autosave_on_stop": (
        "When enabled, stopping the Mobile Companion server automatically writes all pending mobile updates "
        "to the Excel workbook on disk without prompting.\n\n"
        "Excel Impact: Writes in-memory mobile edits to the '.xlsx' file immediately. When disabled (default), "
        "Arbor prompts for confirmation to ensure no edits are saved unintentionally."
    ),
    "directory_view_strip": (
        "When enabled, adds a compact toolbar directly above the specimen directory with 1-click density buttons (Compact ⚡, Standard 🗂️, Full Details 🌿), a physical location toggle (📍), and a quick settings button (⚙️).\n\n"
        "Interface Ergonomics: Gives instant access to switch density and toggle storage locations in-situ without opening Settings. Default is off to keep the directory header clean and minimal."
    ),
}


class UnifiedSettingsWindow:
    """
    Unified Settings Modal Dialog featuring:
    - Vertical Sidebar Navigation
    - Card-based scrollable content area
    - Immediate live updates for UI toggles
    - Combined Layout & Focus Presets management
    - Tools panel for action shortcuts
    """

    COLORS = {
        "surface": "#fbfaf8",
        "surface_container_low": "#f2f5f1",
        "surface_container_highest": "#e9ece5",
        "card_bg": "#ffffff",
        "on_surface": "#2c302e",
        "on_surface_variant": "#4c4546",
        "outline": "#747878",
        "outline_variant": "#c4c7c7",
        "primary": "#000000",
        "on_primary": "#ffffff",
        "secondary": "#3a7d44",
        "error": "#c93a40",
        "search_orange": "#d95c14",
        "surface_tint": "#5e5e5e",
        "sidebar_bg": "#ebebeb",
        "sidebar_active": "#ffffff"
    }

    def __init__(self, parent, app_ref=None, initial_tab="general", live_callbacks=None):
        self.parent = parent
        self.app = app_ref
        self.live_callbacks = live_callbacks or {}

        # Typography tokens
        self.FONT_HEADLINE = ("Lora", sc(14), "bold")
        self.FONT_SUBTITLE = ("Inter", sc(9))
        self.FONT_TAB = ("Inter", sc(10), "bold")
        self.FONT_LABEL = ("Inter", sc(10), "bold")
        self.FONT_DATA = ("Inter", sc(10))
        self.FONT_MONO = ("JetBrains Mono", sc(9), "bold")

        # Load preferences
        self.prefs = config.load_prefs() or {}

        # Create window
        self.win = tk.Toplevel(parent)
        self.win.title("Application Settings")
        self.win.resizable(True, True)
        self.win.transient(parent)
        self.win.grab_set()

        # Window geometry and positioning
        import utils
        utils.center_and_fit_toplevel(self.win, sc(820), sc(600))

        self.win.bind("<Escape>", lambda e: self.win.destroy())
        self.win.bind("<Destroy>", lambda e: self._on_destroy(e))

        # Main Container
        self.main_container = tk.Frame(self.win, bg=self.COLORS["surface"])
        self.main_container.pack(fill="both", expand=True)

        # 1. Header Bar
        self._build_header()

        # 2. Body Container (Sidebar + Content Split)
        self.body_frame = tk.Frame(self.main_container, bg=self.COLORS["surface"])
        self.body_frame.pack(fill="both", expand=True)

        # Left Sidebar
        self.sidebar_frame = tk.Frame(self.body_frame, bg=self.COLORS["sidebar_bg"], width=sc(180))
        self.sidebar_frame.pack(side="left", fill="y")
        self.sidebar_frame.pack_propagate(False)
        tk.Frame(self.sidebar_frame, bg=self.COLORS["outline_variant"], width=1).pack(side="right", fill="y")

        # Right Content Area
        self.content_frame = tk.Frame(self.body_frame, bg=self.COLORS["surface"])
        self.content_frame.pack(side="right", fill="both", expand=True)

        # 3. Footer Action Bar
        self._build_footer()

        # State Draft Variables
        self._init_draft_variables()

        # Navigation State
        self.tabs = {}
        self.tab_buttons = {}
        self.active_tab = None

        # Build Tabs
        self._build_sidebar_nav()
        self._build_all_tabs()

        # Show Initial Tab
        self.show_tab(initial_tab if initial_tab in self.tabs else "general")

    def _on_destroy(self, event):
        pass

    def _build_header(self):
        header = tk.Frame(self.main_container, bg=self.COLORS["surface_container_low"], height=sc(52))
        header.pack(fill="x", side="top")
        header.pack_propagate(False)
        tk.Frame(header, bg=self.COLORS["outline_variant"], height=1).pack(fill="x", side="bottom")

        left = tk.Frame(header, bg=self.COLORS["surface_container_low"])
        left.pack(side="left", fill="y", padx=sc(16))

        title_lbl = tk.Label(
            left, text="Application Settings", font=self.FONT_HEADLINE,
            fg=self.COLORS["primary"], bg=self.COLORS["surface_container_low"]
        )
        title_lbl.pack(side="top", pady=(sc(6), 0), anchor="w")

        sub_lbl = tk.Label(
            left, text="Configure system preferences, workspace layout, theme options, and focus modes",
            font=self.FONT_SUBTITLE, fg=self.COLORS["on_surface_variant"],
            bg=self.COLORS["surface_container_low"]
        )
        sub_lbl.pack(side="top", anchor="w")

    def _build_footer(self):
        footer = tk.Frame(self.main_container, bg=self.COLORS["surface_container_low"], height=sc(52))
        footer.pack(fill="x", side="bottom")
        footer.pack_propagate(False)
        tk.Frame(footer, bg=self.COLORS["outline_variant"], height=1).pack(fill="x", side="top")

        left = tk.Frame(footer, bg=self.COLORS["surface_container_low"])
        left.pack(side="left", fill="y", padx=sc(16))
        tk.Button(
            left, text="Restore Defaults", font=self.FONT_SUBTITLE,
            fg=self.COLORS["on_surface_variant"], bg=self.COLORS["surface"], bd=1,
            relief="solid", padx=sc(12), pady=sc(4), cursor="hand2", command=self.restore_defaults
        ).pack(side="left", pady=sc(10))

        right = tk.Frame(footer, bg=self.COLORS["surface_container_low"])
        right.pack(side="right", fill="y", padx=sc(16))

        tk.Button(
            right, text="Cancel", font=self.FONT_LABEL,
            fg=self.COLORS["on_surface"], bg=self.COLORS["surface"], bd=1,
            relief="solid", padx=sc(16), pady=sc(4), cursor="hand2", command=self.win.destroy
        ).pack(side="left", padx=sc(6), pady=sc(10))

        tk.Button(
            right, text="Save & Apply", font=self.FONT_LABEL,
            fg=self.COLORS["on_primary"], bg=self.COLORS["secondary"], bd=0,
            relief="flat", padx=sc(18), pady=sc(4), cursor="hand2", command=self.save_settings
        ).pack(side="left", padx=sc(6), pady=sc(10))

    def _init_draft_variables(self):
        """Initialize draft Variables from live host app state and saved prefs."""
        p = self.prefs
        app = self.app

        def _get_val(attr_name, default):
            if not app:
                return default
            obj = getattr(app, attr_name, None)
            if obj is None:
                return default
            if isinstance(obj, tk.Variable):
                try:
                    val = obj.get()
                    if not isinstance(val, (bool, str, int, float)):
                        return default
                    return val
                except Exception:
                    return default
            if isinstance(obj, (bool, str, int, float)):
                return obj
            return default

        # General
        current_mins = config.AUTOSAVE_INTERVAL_MS // 60000
        self.var_autosave_mins = tk.StringVar(value=str(p.get("autosave_interval", current_mins)))
        self.var_disable_tutorials = tk.BooleanVar(value=p.get("disable_tutorials", False))
        self.var_excel_backup = tk.BooleanVar(value=p.get("enable_excel_import_backup", True))
        self.var_log_verbosity = tk.StringVar(value=p.get("log_verbosity", "ERROR"))
        self.var_archive_limit = tk.StringVar(value=str(p.get("autosave_archive_limit", 10)))
        self.var_mobile_autosave_on_stop = tk.BooleanVar(value=bool(p.get("mobile_autosave_on_stop", False)))
        
        auto_adv = _get_val("auto_advance_var", p.get("auto_advance_on_review", True))
        auto_adv_hist = _get_val("auto_advance_history_var", p.get("auto_advance_history", False))
        self.var_auto_advance = tk.BooleanVar(value=bool(auto_adv))
        self.var_auto_advance_history = tk.BooleanVar(value=bool(auto_adv_hist))

        # Appearance & Visuals
        dark_active = _get_val("dark_mode_active", p.get("dark_mode", False))
        self.var_dark_mode = tk.BooleanVar(value=bool(dark_active))
        self.var_ui_scale = tk.DoubleVar(value=p.get("ui_scale", getattr(config, "UI_SCALE", 1.0)))
        self.var_problem_highlights = tk.BooleanVar(value=p.get("enable_problem_highlights", True))
        self.var_highlight_color = tk.StringVar(value=p.get("problem_highlight_color", "Default (Red)"))
        
        large_rev = _get_val("large_reviewed_button_var", p.get("large_reviewed_button", True))
        self.var_large_reviewed_btn = tk.BooleanVar(value=bool(large_rev))
        
        snap_lck = _get_val("snap_lock_var", p.get("snap_lock", False))
        self.var_snap_lock = tk.BooleanVar(value=bool(snap_lck))

        # Directory Card View Preferences
        card_p = config.get_directory_card_prefs()
        self.var_card_density = tk.StringVar(value=card_p.get("density_mode", "standard"))
        self.var_card_show_loc = tk.BooleanVar(value=bool(card_p.get("show_location_row", True)))
        self.var_card_loc_granularity = tk.StringVar(value=card_p.get("location_granularity", "full"))
        self.var_card_show_badge = tk.BooleanVar(value=bool(card_p.get("show_status_badge", True)))
        self.var_card_show_author = tk.BooleanVar(value=bool(card_p.get("show_author_citation", False)))
        self.var_card_fallback = tk.StringVar(value=card_p.get("unknown_taxon_fallback", "unknown"))
        self.var_card_badge_priority = tk.StringVar(value=card_p.get("badge_priority_preset", "default"))
        self.var_card_accent_mode = tk.StringVar(value=card_p.get("accent_strip_mode", "problems"))
        self.var_card_show_view_strip = tk.BooleanVar(value=bool(card_p.get("show_directory_view_strip", False)))

        vis_cats = card_p.get("visible_badge_categories", {})
        self.var_badge_cats = {
            k: tk.BooleanVar(value=bool(vis_cats.get(k, True)))
            for k in ("reviewed", "taxonomy", "provenance", "physical", "media", "conflicts", "general_err", "unreviewed")
        }

        vis_meta = card_p.get("visible_meta_tags", {})
        self.var_meta_tags = {
            k: tk.BooleanVar(value=bool(vis_meta.get(k, True)))
            for k in ("family", "photos", "loan", "unknown", "unvalidated")
        }
        self.var_preview_status = tk.StringVar(value="taxonomy")
        self._preview_widgets = {}

        # Layout & Panels
        combine_imgs = _get_val("combine_images_var", p.get("combine_local_and_online", False))
        self.var_combine_images = tk.BooleanVar(value=bool(combine_imgs))

        show_lst = _get_val("show_list_var", p.get("show_list", True))
        show_srch = _get_val("show_search_var", p.get("show_search", True))
        show_rg = _get_val("show_reg_var", p.get("show_reg", True))
        show_imgs = _get_val("show_images_var", p.get("show_images", True))
        loc_center = _get_val("location_in_center_var", p.get("location_in_center", True))
        
        loc_2r = True
        if app and hasattr(app, "location_panel_horiz") and getattr(app, "location_panel_horiz", None) is not None:
            mode_val = getattr(app.location_panel_horiz, "layout_mode", None)
            if isinstance(mode_val, str):
                loc_2r = (mode_val == "horizontal_2row")
            else:
                loc_2r = p.get("location_2row", True)
        else:
            loc_2r = p.get("location_2row", True)
            
        show_img_tls = _get_val("show_image_tools_var", p.get("show_image_tools", True))
        show_blk = _get_val("show_bulk_edit_var", p.get("show_bulk_edit", True))
        
        img_stk = _get_val("image_stack_var", p.get("image_stack", False))

        self.var_show_list = tk.BooleanVar(value=bool(show_lst))
        self.var_show_search = tk.BooleanVar(value=bool(show_srch))
        self.var_show_reg = tk.BooleanVar(value=bool(show_rg))
        self.var_show_images = tk.BooleanVar(value=bool(show_imgs))
        self.var_location_center = tk.BooleanVar(value=bool(loc_center))
        self.var_location_2row = tk.BooleanVar(value=bool(loc_2r))
        self.var_show_image_tools = tk.BooleanVar(value=bool(show_img_tls))
        self.var_show_bulk_edit = tk.BooleanVar(value=bool(show_blk))
        self.var_image_stack = tk.BooleanVar(value=bool(img_stk))
        show_sec_nav = _get_val("show_secondary_nav_var", p.get("show_secondary_nav", False))
        self.var_show_secondary_nav = tk.BooleanVar(value=bool(show_sec_nav))
        self.var_layout_dynamic = tk.BooleanVar(value=False)  # runtime-only, not persisted

        # Focus Mode
        focus_m = _get_val("focus_mode_var", p.get("focus_mode", p.get("focus_mode_active", False)))
        focus_fb = _get_val("focus_fallback_var", p.get("focus_fallback", True))
        focus_dyn = _get_val("focus_dynamic_update_var", p.get("focus_dynamic_update", False))
        
        self.var_focus_mode = tk.BooleanVar(value=bool(focus_m))
        self.var_focus_fallback = tk.BooleanVar(value=bool(focus_fb))
        self.var_focus_dynamic = tk.BooleanVar(value=bool(focus_dyn))

        # Focus section visibility (Problems & Location)
        saved_vis = p.get("focus_visibility", {})
        if app and hasattr(app, "focus_visibility_vars") and isinstance(app.focus_visibility_vars, dict) and "Problems" in app.focus_visibility_vars:
            prob_vis = _get_val("Problems", saved_vis.get("Problems", p.get("focus_sec_problems", True)))
            if "Problems" in app.focus_visibility_vars and isinstance(app.focus_visibility_vars["Problems"], tk.Variable):
                try:
                    prob_vis = app.focus_visibility_vars["Problems"].get()
                except Exception:
                    pass
        else:
            prob_vis = saved_vis.get("Problems", p.get("focus_sec_problems", True))

        if app and hasattr(app, "focus_visibility_vars") and isinstance(app.focus_visibility_vars, dict) and "Location" in app.focus_visibility_vars:
            loc_vis = saved_vis.get("Location", p.get("focus_sec_location", True))
            if "Location" in app.focus_visibility_vars and isinstance(app.focus_visibility_vars["Location"], tk.Variable):
                try:
                    loc_vis = app.focus_visibility_vars["Location"].get()
                except Exception:
                    pass
        else:
            loc_vis = saved_vis.get("Location", p.get("focus_sec_location", True))

        self.var_focus_sec_problems = tk.BooleanVar(value=bool(prob_vis))
        self.var_focus_sec_location = tk.BooleanVar(value=bool(loc_vis))

        # Advanced
        self.var_resampling = tk.StringVar(value=p.get("image_resampling_algorithm", "LANCZOS (High Quality)"))
        self.var_url_pattern = tk.StringVar(value=p.get("image_url_pattern_override", ""))
        self.var_enable_bulk = tk.BooleanVar(value=p.get("enable_bulk_editor", False))
        self.var_enable_focus_toggle = tk.BooleanVar(value=p.get("enable_focus_mode_toggle", False))
        self.var_auto_resolve = tk.BooleanVar(value=p.get("auto_resolve_conflicts", False))
        self.var_strict_validation = tk.BooleanVar(value=p.get("strict_input_validation", False))
        self.var_enable_gbif = tk.BooleanVar(value=p.get("enable_gbif", False))
        self.var_gbif_max_workers = tk.IntVar(value=int(p.get("gbif_max_workers", 5)))
        self.var_require_mobile_pin = tk.BooleanVar(value=p.get("require_mobile_pin", True))

        # Toolbar draft vars
        self.draft_toolbar_vars = {}
        if app and hasattr(app, "toolbar_vars") and isinstance(app.toolbar_vars, dict):
            for k, v in app.toolbar_vars.items():
                if isinstance(v, tk.Variable):
                    try:
                        self.draft_toolbar_vars[k] = tk.BooleanVar(value=bool(v.get()))
                    except Exception:
                        self.draft_toolbar_vars[k] = tk.BooleanVar(value=True)
                elif isinstance(v, bool):
                    self.draft_toolbar_vars[k] = tk.BooleanVar(value=v)
        else:
            tb_saved = p.get("toolbar_buttons", {})
            for k, v in tb_saved.items():
                self.draft_toolbar_vars[k] = tk.BooleanVar(value=bool(v))

        # Focus visibility draft vars (per-field registration fields)
        self.draft_focus_visibility_vars = {}
        if app and hasattr(app, "focus_visibility_vars") and isinstance(app.focus_visibility_vars, dict):
            for k, v in app.focus_visibility_vars.items():
                if k not in ("Problems", "Location"):
                    if isinstance(v, tk.Variable):
                        try:
                            self.draft_focus_visibility_vars[k] = tk.BooleanVar(value=bool(v.get()))
                        except Exception:
                            self.draft_focus_visibility_vars[k] = tk.BooleanVar(value=True)
                    elif isinstance(v, bool):
                        self.draft_focus_visibility_vars[k] = tk.BooleanVar(value=v)
        else:
            for k, v in saved_vis.items():
                if k not in ("Problems", "Location"):
                    self.draft_focus_visibility_vars[k] = tk.BooleanVar(value=bool(v))

        # Ignored words dictionary draft state
        self.draft_ignored_words = []
        self.var_ignored_variations = tk.BooleanVar(value=True)
        if app and hasattr(app, "ignored_words") and isinstance(app.ignored_words, list):
            self.draft_ignored_words = list(app.ignored_words)
            if hasattr(app, "ignored_words_variations") and isinstance(app.ignored_words_variations, tk.Variable):
                self.var_ignored_variations.set(bool(app.ignored_words_variations.get()))
        else:
            try:
                from ui.ignored_words_dialog import load_ignored_words
                from utils import get_resource_path
                ipath = get_resource_path("ignored_words.json")
                words, variations = load_ignored_words(ipath)
                self.draft_ignored_words = list(words)
                self.var_ignored_variations.set(bool(variations))
            except Exception:
                self.draft_ignored_words = []
                self.var_ignored_variations.set(True)

    def _build_sidebar_nav(self):
        nav_items = [
            ("general",    "⚙️  General"),
            ("appearance", "🎨  Appearance"),
            ("layout",     "📐  Layout"),
            ("presets",    "📁  Presets"),
            ("advanced",   "⚡  Advanced"),
            ("tools",      "🛠️  Tools"),
        ]

        title_frame = tk.Frame(self.sidebar_frame, bg=self.COLORS["sidebar_bg"])
        title_frame.pack(fill="x", pady=(sc(12), sc(6)), padx=sc(12))
        tk.Label(
            title_frame, text="CATEGORIES", font=self.FONT_MONO,
            fg=self.COLORS["on_surface_variant"], bg=self.COLORS["sidebar_bg"]
        ).pack(anchor="w")

        for key, label in nav_items:
            btn_frame = tk.Frame(self.sidebar_frame, bg=self.COLORS["sidebar_bg"])
            btn_frame.pack(fill="x", pady=sc(2))

            border_strip = tk.Frame(btn_frame, bg=self.COLORS["sidebar_bg"], width=4)
            border_strip.pack(side="left", fill="y")

            btn = tk.Button(
                btn_frame, text=label, font=self.FONT_TAB, fg=self.COLORS["on_surface_variant"],
                bg=self.COLORS["sidebar_bg"], bd=0, relief="flat", anchor="w", padx=sc(12),
                pady=sc(8), cursor="hand2", command=lambda k=key: self.show_tab(k)
            )
            btn.pack(side="left", fill="x", expand=True)

            self.tab_buttons[key] = (btn, border_strip, btn_frame)

    def show_tab(self, tab_key):
        if self.active_tab and self.active_tab in self.tabs:
            self.tabs[self.active_tab].pack_forget()

        self.active_tab = tab_key
        if tab_key in self.tabs:
            self.tabs[tab_key].pack(fill="both", expand=True)

        for k, (btn, border, frame) in self.tab_buttons.items():
            if k == tab_key:
                btn.config(fg=self.COLORS["primary"], bg=self.COLORS["sidebar_active"],
                           font=self.FONT_TAB)
                border.config(bg=self.COLORS["secondary"])
                frame.config(bg=self.COLORS["sidebar_active"])
            else:
                btn.config(fg=self.COLORS["on_surface_variant"], bg=self.COLORS["sidebar_bg"])
                border.config(bg=self.COLORS["sidebar_bg"])
                frame.config(bg=self.COLORS["sidebar_bg"])

    def _create_card(self, parent, category_tag):
        """Creates a modern card container."""
        outer = tk.Frame(parent, bg=self.COLORS["surface"], pady=sc(6))
        outer.pack(fill="x")

        card = tk.Frame(
            outer, bg=self.COLORS["card_bg"],
            highlightbackground=self.COLORS["outline_variant"], highlightthickness=1
        )
        card.pack(fill="x")

        tag_frame = tk.Frame(card, bg=self.COLORS["surface_container_low"], height=sc(28))
        tag_frame.pack(fill="x", side="top")
        tag_frame.pack_propagate(False)

        tk.Label(
            tag_frame, text=category_tag.upper(), font=self.FONT_MONO,
            fg=self.COLORS["on_surface_variant"], bg=self.COLORS["surface_container_low"]
        ).pack(side="left", padx=sc(12), pady=sc(4))

        tk.Frame(tag_frame, bg=self.COLORS["outline_variant"], height=1).pack(fill="x", side="bottom")

        content = tk.Frame(card, bg=self.COLORS["card_bg"], padx=sc(14), pady=sc(12))
        content.pack(fill="x")
        return content

    def _create_scrollable_tab(self, tab_key):
        tab_frame = tk.Frame(self.content_frame, bg=self.COLORS["surface"])
        self.tabs[tab_key] = tab_frame

        canvas = tk.Canvas(tab_frame, highlightthickness=0, bd=0, bg=self.COLORS["surface"])
        scrollbar = ttk.Scrollbar(tab_frame, orient="vertical", command=canvas.yview)
        scroll_content = tk.Frame(canvas, bg=self.COLORS["surface"])

        scroll_content.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        win_id = canvas.create_window((0, 0), window=scroll_content, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.bind("<Configure>", lambda e: canvas.itemconfig(win_id, width=e.width))

        from ui.scroll_helper import bind_mousewheel
        bind_mousewheel(canvas, scroll_content)

        canvas.pack(side="left", fill="both", expand=True, padx=sc(12), pady=sc(8))
        scrollbar.pack(side="right", fill="y", pady=sc(8))

        return scroll_content

    def _build_all_tabs(self):
        self._build_tab_general()
        self._build_tab_appearance()
        self._build_tab_layout()
        self._build_tab_focus()
        self._build_tab_presets()
        self._build_tab_advanced()
        self._build_tab_tools()

    # ── TAB 1: GENERAL ──────────────────────────────────────────────────────
    def _build_tab_general(self):
        c = self._create_scrollable_tab("general")

        # Card 1: Autosave & Storage
        card1 = self._create_card(c, "Autosave & Storage")

        f1 = tk.Frame(card1, bg=self.COLORS["card_bg"])
        f1.pack(fill="x", pady=sc(4))
        tk.Label(f1, text="Autosave interval (minutes):", font=self.FONT_DATA,
                 fg=self.COLORS["on_surface"], bg=self.COLORS["card_bg"]).pack(side="left")
        spin_frame = tk.Frame(f1, bg=self.COLORS["card_bg"],
                              highlightbackground=self.COLORS["outline_variant"], highlightthickness=1)
        spin_frame.pack(side="left", padx=sc(12))
        ttk.Spinbox(spin_frame, from_=1, to=60, textvariable=self.var_autosave_mins,
                    width=6, font=self.FONT_DATA).pack(padx=2, pady=2)

        f2 = tk.Frame(card1, bg=self.COLORS["card_bg"])
        f2.pack(fill="x", pady=sc(6))
        tk.Label(f2, text="Autosave archive warning limit:", font=self.FONT_DATA,
                 fg=self.COLORS["on_surface"], bg=self.COLORS["card_bg"]).pack(side="left")
        create_info_badge(f2, SETTING_INFO_TEXTS["autosave_archive_limit"], ui_ref=self.app or self).pack(side="left", padx=(sc(6), sc(8)))
        ttk.Combobox(f2, textvariable=self.var_archive_limit, values=["5", "10", "20", "50"],
                     state="readonly", width=8, cursor="hand2").pack(side="left", padx=sc(4))

        create_toggle_row(card1, "Enable Backup on Excel Import", self.var_excel_backup,
                          ui_ref=self.app or self, info_text=SETTING_INFO_TEXTS["enable_excel_import_backup"])
        create_toggle_row(card1, "Auto-save when mobile server is stopped", self.var_mobile_autosave_on_stop,
                          ui_ref=self.app or self, info_text=SETTING_INFO_TEXTS["mobile_autosave_on_stop"])
        tk.Label(card1,
                 text="Note: Saves use background atomic pickles for maximum performance.",
                 font=self.FONT_SUBTITLE, fg=self.COLORS["on_surface_variant"],
                 bg=self.COLORS["card_bg"]).pack(anchor="w", pady=(sc(4), 0))

        # Card 2: Guidance & Diagnostics
        card2 = self._create_card(c, "System Guidance & Diagnostics")
        create_toggle_row(card2, "Disable Interactive Tutorials & Banners", self.var_disable_tutorials, ui_ref=self.app or self)

        f3 = tk.Frame(card2, bg=self.COLORS["card_bg"])
        f3.pack(fill="x", pady=sc(6))
        tk.Label(f3, text="System Logging Verbosity:", font=self.FONT_DATA,
                 fg=self.COLORS["on_surface"], bg=self.COLORS["card_bg"]).pack(side="left")
        ttk.Combobox(f3, textvariable=self.var_log_verbosity,
                     values=["ERROR", "WARNING", "INFO", "DEBUG"],
                     state="readonly", width=12, cursor="hand2").pack(side="left", padx=sc(12))

        # Card 3: Workflow & Auto-Advance
        card3 = self._create_card(c, "Workflow & Navigation")
        create_toggle_row(card3, "Auto-advance to next object when marked Reviewed", self.var_auto_advance, ui_ref=self.app or self)
        create_toggle_row(card3, "Auto-advance when resolving with Historical Suggestion", self.var_auto_advance_history,
                          ui_ref=self.app or self, info_text=SETTING_INFO_TEXTS["auto_advance_history"])

    # ── TAB 2: APPEARANCE ────────────────────────────────────────────────────
    def _build_tab_appearance(self):
        c = self._create_scrollable_tab("appearance")

        # Card 1: Theme & Display Scaling
        card1 = self._create_card(c, "Theme & Interface Scaling")

        def _on_theme_toggle():
            self._notify_live("dark_mode", self.var_dark_mode.get())

        create_toggle_row(card1, "Dark Theme Mode", self.var_dark_mode, command=_on_theme_toggle)
        tk.Frame(card1, bg=self.COLORS["outline_variant"], height=1).pack(fill="x", pady=sc(8))

        det = getattr(config, "_detected_scale", 1.0)
        lbl_dpi = tk.Label(
            card1,
            text=f"Detected DPI: {det:.0%}  |  Active Scale: {self.var_ui_scale.get():.0%}",
            font=self.FONT_LABEL, fg=self.COLORS["secondary"], bg=self.COLORS["card_bg"]
        )
        lbl_dpi.pack(anchor="w", pady=(0, sc(6)))

        scale_frame = tk.Frame(card1, bg=self.COLORS["card_bg"])
        scale_frame.pack(fill="x", pady=sc(2))

        scales = [(0.75, "75% compact"), (0.90, "90%"), (1.0, "100% default"),
                  (1.10, "110%"), (1.25, "125% large"), (1.50, "150%")]
        col1 = tk.Frame(scale_frame, bg=self.COLORS["card_bg"])
        col1.pack(side="left", expand=True, fill="both")
        col2 = tk.Frame(scale_frame, bg=self.COLORS["card_bg"])
        col2.pack(side="left", expand=True, fill="both")

        for idx, (val, lbl) in enumerate(scales):
            target = col1 if idx < 3 else col2
            f_r = tk.Frame(target, bg=self.COLORS["card_bg"])
            f_r.pack(fill="x", pady=1)
            tk.Radiobutton(f_r, variable=self.var_ui_scale, value=val,
                           bg=self.COLORS["card_bg"],
                           activebackground=self.COLORS["card_bg"], cursor="hand2").pack(side="left")
            tk.Label(f_r, text=lbl, font=self.FONT_DATA, fg=self.COLORS["on_surface"],
                     bg=self.COLORS["card_bg"]).pack(side="left", padx=4)

        tk.Label(card1, text="⚠ Changes to UI Scale ratio require restarting Arbor to take full effect.",
                 font=self.FONT_SUBTITLE, fg=self.COLORS["search_orange"],
                 bg=self.COLORS["card_bg"]).pack(anchor="w", pady=(sc(6), 0))

        # Card 2: Problem Highlights
        card2 = self._create_card(c, "Problem Field Highlights")

        def _on_highlight_toggle():
            self._notify_live("problem_highlights", self.var_problem_highlights.get())

        create_toggle_row(card2, "Enable Problem Field Highlights", self.var_problem_highlights,
                          command=_on_highlight_toggle)

        f_clr = tk.Frame(card2, bg=self.COLORS["card_bg"])
        f_clr.pack(fill="x", pady=sc(6))
        tk.Label(f_clr, text="Highlight Color Style:", font=self.FONT_DATA,
                 fg=self.COLORS["on_surface"], bg=self.COLORS["card_bg"]).pack(side="left")
        cb_hl = ttk.Combobox(f_clr, textvariable=self.var_highlight_color,
                             values=["Default (Red)", "Yellow", "Orange", "Blue"],
                             state="readonly", width=16, cursor="hand2")
        cb_hl.pack(side="left", padx=sc(12))
        cb_hl.bind("<<ComboboxSelected>>", lambda e: self._notify_live("problem_highlight_color", self.var_highlight_color.get()))

        # Card 3: Directory Cards & View Ergonomics
        card_dir = self._create_card(c, "Specimen Directory Cards & View Ergonomics")

        # 1. Quick Profiles
        tk.Label(card_dir, text="QUICK CARD LAYOUT PROFILES", font=self.FONT_LABEL,
                 fg=self.COLORS["secondary"], bg=self.COLORS["card_bg"]).pack(anchor="w", pady=(0, sc(4)))
        p_row = tk.Frame(card_dir, bg=self.COLORS["card_bg"])
        p_row.pack(fill="x", pady=(0, sc(8)))

        def _profile_btn(parent, text, cmd):
            btn = tk.Button(parent, text=text, font=self.FONT_DATA, bg=self.COLORS["surface_container_highest"],
                            fg=self.COLORS["on_surface"], activebackground=self.COLORS["secondary"],
                            activeforeground="#ffffff", relief="flat", bd=0, padx=sc(8), pady=sc(3),
                            cursor="hand2", command=cmd)
            btn.pack(side="left", padx=(0, sc(6)))
            return btn

        _profile_btn(p_row, "🗂️ Standard", lambda: self._apply_card_preset_in_settings("standard"))
        _profile_btn(p_row, "⚡ Compact", lambda: self._apply_card_preset_in_settings("compact"))
        _profile_btn(p_row, "🌿 Full Details", lambda: self._apply_card_preset_in_settings("full_detail"))
        _profile_btn(p_row, "📖 Minimalist", lambda: self._apply_card_preset_in_settings("minimalist"))
        _profile_btn(p_row, "↺ Defaults", lambda: self._reset_card_settings_to_default_ui())

        tk.Frame(card_dir, bg=self.COLORS["outline_variant"], height=1).pack(fill="x", pady=sc(6))

        # 2. Live Interactive Card Preview
        self._build_card_preview_widget(card_dir)

        tk.Frame(card_dir, bg=self.COLORS["outline_variant"], height=1).pack(fill="x", pady=sc(6))

        # 3. Badge Reference Legend & Priority
        self._build_badge_legend_widget(card_dir)

        tk.Frame(card_dir, bg=self.COLORS["outline_variant"], height=1).pack(fill="x", pady=sc(6))

        # 4. Row 1: Title & Status Badges
        tk.Label(card_dir, text="ROW 1: TITLE & STATUS PILL BADGE", font=self.FONT_LABEL,
                 fg=self.COLORS["on_surface"], bg=self.COLORS["card_bg"]).pack(anchor="w", pady=(0, sc(4)))

        create_toggle_row(card_dir, "Append Botanical Author Citation (e.g. Quercus robur L.)", self.var_card_show_author,
                          command=self._sync_card_settings_live)

        create_toggle_row(card_dir, "Enable Status Pill Badges", self.var_card_show_badge,
                          command=self._sync_card_settings_live)

        f_prio = tk.Frame(card_dir, bg=self.COLORS["card_bg"])
        f_prio.pack(fill="x", pady=sc(3))
        tk.Label(f_prio, text="Badge Priority Workflow:", font=self.FONT_DATA,
                 fg=self.COLORS["on_surface"], bg=self.COLORS["card_bg"]).pack(side="left")
        cb_prio = ttk.Combobox(f_prio, textvariable=self.var_card_badge_priority,
                               values=["default", "taxonomist", "collections_manager"],
                               state="readonly", width=18, cursor="hand2")
        cb_prio.pack(side="left", padx=sc(10))
        cb_prio.bind("<<ComboboxSelected>>", lambda e: self._sync_card_settings_live())

        f_cats = tk.Frame(card_dir, bg=self.COLORS["card_bg"])
        f_cats.pack(fill="x", pady=sc(4))
        cat_labels = [
            ("taxonomy", "Taxonomy [TAX]"),
            ("provenance", "Provenance [PROV]"),
            ("physical", "Storage Box [BOX]"),
            ("media", "Media [IMG]"),
            ("conflicts", "Conflicts [CFCT]"),
            ("reviewed", "Reviewed [REV]"),
            ("general_err", "Errors [ERR]"),
            ("unreviewed", "Unreviewed [UNREV]"),
        ]
        for idx, (cat_key, cat_name) in enumerate(cat_labels):
            var = self.var_badge_cats[cat_key]
            cb = tk.Checkbutton(f_cats, text=cat_name, variable=var, font=self.FONT_DATA,
                                bg=self.COLORS["card_bg"], activebackground=self.COLORS["card_bg"],
                                cursor="hand2", command=self._sync_card_settings_live)
            cb.grid(row=idx // 2, column=idx % 2, sticky="w", padx=sc(6), pady=sc(2))

        tk.Frame(card_dir, bg=self.COLORS["outline_variant"], height=1).pack(fill="x", pady=sc(6))

        # 5. Row 2 Metadata Tokens
        tk.Label(card_dir, text="ROW 2: INLINE METADATA TAGS", font=self.FONT_LABEL,
                 fg=self.COLORS["on_surface"], bg=self.COLORS["card_bg"]).pack(anchor="w", pady=(0, sc(4)))

        f_meta = tk.Frame(card_dir, bg=self.COLORS["card_bg"])
        f_meta.pack(fill="x", pady=sc(4))
        meta_labels = [
            ("family", "Botanical Family (e.g. FAGACEAE)"),
            ("photos", "Photos Count (e.g. 2 photos)"),
            ("loan", "Loan Status (LOAN)"),
            ("unknown", "Unknown Warning (UKN)"),
            ("unvalidated", "Unvalidated Note (UNVAL)"),
        ]
        for idx, (m_key, m_name) in enumerate(meta_labels):
            var = self.var_meta_tags[m_key]
            cb = tk.Checkbutton(f_meta, text=m_name, variable=var, font=self.FONT_DATA,
                                bg=self.COLORS["card_bg"], activebackground=self.COLORS["card_bg"],
                                cursor="hand2", command=self._sync_card_settings_live)
            cb.grid(row=idx // 2, column=idx % 2, sticky="w", padx=sc(6), pady=sc(2))

        tk.Frame(card_dir, bg=self.COLORS["outline_variant"], height=1).pack(fill="x", pady=sc(6))

        # 6. Row 3 Physical Storage Location
        tk.Label(card_dir, text="ROW 3: PHYSICAL VAULT LOCATION", font=self.FONT_LABEL,
                 fg=self.COLORS["on_surface"], bg=self.COLORS["card_bg"]).pack(anchor="w", pady=(0, sc(4)))

        create_toggle_row(card_dir, "Show Physical Location (Row 3)", self.var_card_show_loc,
                          command=self._sync_card_settings_live)

        f_gran = tk.Frame(card_dir, bg=self.COLORS["card_bg"])
        f_gran.pack(fill="x", pady=sc(3))
        tk.Label(f_gran, text="Location Detail Level:", font=self.FONT_DATA,
                 fg=self.COLORS["on_surface"], bg=self.COLORS["card_bg"]).pack(side="left")
        cb_gran = ttk.Combobox(f_gran, textvariable=self.var_card_loc_granularity,
                               values=["full", "compact", "none"],
                               state="readonly", width=14, cursor="hand2")
        cb_gran.pack(side="left", padx=sc(10))
        cb_gran.bind("<<ComboboxSelected>>", lambda e: self._sync_card_settings_live())

        tk.Frame(card_dir, bg=self.COLORS["outline_variant"], height=1).pack(fill="x", pady=sc(6))

        # 7. Card Layout & Vertical Density
        tk.Label(card_dir, text="CARD SIZING & DENSITY", font=self.FONT_LABEL,
                 fg=self.COLORS["on_surface"], bg=self.COLORS["card_bg"]).pack(anchor="w", pady=(0, sc(4)))

        f_den = tk.Frame(card_dir, bg=self.COLORS["card_bg"])
        f_den.pack(fill="x", pady=sc(3))
        tk.Label(f_den, text="Vertical Density Mode:", font=self.FONT_DATA,
                 fg=self.COLORS["on_surface"], bg=self.COLORS["card_bg"]).pack(side="left")
        cb_den = ttk.Combobox(f_den, textvariable=self.var_card_density,
                              values=["compact", "standard", "expanded"],
                              state="readonly", width=14, cursor="hand2")
        cb_den.pack(side="left", padx=sc(10))
        cb_den.bind("<<ComboboxSelected>>", lambda e: self._sync_card_settings_live())

        tk.Label(card_dir,
                 text="Compact (64px) shows ~15 cards on screen • Standard (78px) ~12 cards • Expanded (92px) ~10 cards",
                 font=("Inter", sc(8)), fg=self.COLORS["on_surface_variant"], bg=self.COLORS["card_bg"]).pack(anchor="w", pady=(sc(2), sc(6)))

        create_toggle_row(card_dir, "Show Directory View Strip (Header Quick Controls)", self.var_card_show_view_strip,
                          command=self._sync_card_settings_live, ui_ref=self.app or self,
                          info_text=SETTING_INFO_TEXTS.get("directory_view_strip", ""))

        tk.Frame(card_dir, bg=self.COLORS["outline_variant"], height=1).pack(fill="x", pady=sc(8))

        # 8. Return to Default Button
        btn_reset = tk.Button(card_dir, text="↺ Return to Default Card Settings", font=self.FONT_LABEL,
                              bg=self.COLORS["surface_container_highest"], fg=self.COLORS["error"],
                              activebackground=self.COLORS["error"], activeforeground="#ffffff",
                              relief="flat", bd=0, padx=sc(10), pady=sc(5), cursor="hand2",
                              command=self._reset_card_settings_to_default_ui)
        btn_reset.pack(anchor="w", pady=(sc(2), 0))

        # Card 4: Visual Controls
        card3 = self._create_card(c, "Visual Controls")
        create_toggle_row(card3, "Snap Window Layout Grid", self.var_snap_lock,
                          command=lambda: self._notify_live("snap_lock", self.var_snap_lock.get()),
                          ui_ref=self.app or self, info_text=SETTING_INFO_TEXTS["snap_lock"])

    # ── TAB 3: LAYOUT ────────────────────────────────────────────────────────
    def _build_tab_layout(self):
        c = self._create_scrollable_tab("layout")

        # Card 1: Workspace Panels
        card1 = self._create_card(c, "Workspace Panel Visibility")
        card1.tutorial_id = "layout_toggles"

        def _apply_if_dynamic():
            """If dynamic update mode is active, immediately push panel changes to the host."""
            if self.var_layout_dynamic.get():
                self._push_layout_to_app()

        def _notify_panel(key, var):
            if key == "location_center":
                self._notify_live("location_center", var.get())
            elif key == "location_2row":
                self._notify_live("location_2row", var.get())
            else:
                self._notify_live(f"show_{key}", var.get())
            _apply_if_dynamic()

        create_toggle_row(card1, "Show Object List Panel", self.var_show_list,
                          command=lambda: _notify_panel("list", self.var_show_list))
        create_toggle_row(card1, "Show Live Search Panel", self.var_show_search,
                          command=lambda: _notify_panel("search", self.var_show_search))
        create_toggle_row(card1, "Show Registration Form Panel", self.var_show_reg,
                          command=lambda: _notify_panel("reg", self.var_show_reg))
        create_toggle_row(card1, "Show Images Panel", self.var_show_images,
                          command=lambda: _notify_panel("images", self.var_show_images))
        create_toggle_row(card1, "Place Location Panel in Center View", self.var_location_center,
                          command=lambda: _notify_panel("location_center", self.var_location_center))
        create_toggle_row(card1, "Compact 2-Row Location Layout (Center View)", self.var_location_2row,
                          command=lambda: _notify_panel("location_2row", self.var_location_2row))
        create_toggle_row(card1, "Show Image Zoom/Rotate Toolbar", self.var_show_image_tools,
                          command=lambda: (_notify_panel("image_tools", self.var_show_image_tools), self._notify_live("show_image_tools", self.var_show_image_tools.get())))
        create_toggle_row(card1, "Show Bulk Edit Button", self.var_show_bulk_edit,
                          command=lambda: (_notify_panel("bulk_edit", self.var_show_bulk_edit), self._notify_live("show_bulk_edit", self.var_show_bulk_edit.get())))

        def _on_secondary_nav_toggle():
            if self.app and hasattr(self.app, "apply_secondary_nav_visibility"):
                self.app.apply_secondary_nav_visibility(self.var_show_secondary_nav.get())
            self._notify_live("show_secondary_nav", self.var_show_secondary_nav.get())
            _apply_if_dynamic()

        create_toggle_row(card1, "Show Quick Navigation & Problem Jumps (Top Bar)", self.var_show_secondary_nav,
                          command=_on_secondary_nav_toggle, ui_ref=self.app or self,
                          info_text="Displays ◄ ► Last and Next Problem jump buttons in the top navigation bar for rapid navigation.\n\nExcel Impact: Jumps directly to records where any problem flag column on the Observation sheet is TRUE.")

        # Card 2: Behavior
        card2 = self._create_card(c, "View Display Options")
        create_toggle_row(card2, "Combine Local and Online Images",
                          self.var_combine_images,
                          command=lambda: (_apply_if_dynamic(), self._notify_live("combine_images", self.var_combine_images.get())),
                          ui_ref=self.app or self)
        create_toggle_row(card2, "View Images as Stack by Default",
                          self.var_image_stack,
                          command=lambda: (_apply_if_dynamic(), self._notify_live("image_stack", self.var_image_stack.get())),
                          ui_ref=self.app or self)

        # Card 3: Update Mode
        card3 = self._create_card(c, "Live Update Behaviour")
        create_toggle_row(card3, "Apply panel changes dynamically (without saving)",
                          self.var_layout_dynamic)
        tk.Label(card3,
                 text="When enabled, panel toggles above take effect immediately in the workspace.",
                 font=self.FONT_SUBTITLE, fg=self.COLORS["on_surface_variant"],
                 bg=self.COLORS["card_bg"]).pack(anchor="w", pady=(sc(2), 0))

        # Card 4: Toolbar Buttons (only shown if app_ref exposes toolbar_vars)
        if self.draft_toolbar_vars:
            card4 = self._create_card(c, "Toolbar Button Visibility")
            tb_grid = tk.Frame(card4, bg=self.COLORS["card_bg"])
            tb_grid.pack(fill="x")
            tb_grid.columnconfigure(0, weight=1)
            tb_grid.columnconfigure(1, weight=1)

            def _make_tb_toggle_cmd(name, var):
                def _cmd():
                    if self.app and hasattr(self.app, "toolbar_vars") and name in self.app.toolbar_vars:
                        self.app.toolbar_vars[name].set(var.get())
                        if hasattr(self.app, "_toggle_toolbar_buttons"):
                            self.app._toggle_toolbar_buttons()
                return _cmd

            for idx, (name, var) in enumerate(sorted(self.draft_toolbar_vars.items())):
                row_idx = idx // 2
                col_idx = idx % 2
                cell = tk.Frame(tb_grid, bg=self.COLORS["card_bg"])
                cell.grid(row=row_idx, column=col_idx, sticky="ew", padx=sc(4), pady=sc(2))
                tk.Label(cell, text=name, font=self.FONT_DATA, fg=self.COLORS["on_surface"],
                         bg=self.COLORS["card_bg"]).pack(side="left", anchor="w")
                ToggleSwitch(cell, var, command=_make_tb_toggle_cmd(name, var), ui_ref=self.app).pack(side="right")
        else:
            card4 = self._create_card(c, "Toolbar Button Visibility")
            tk.Label(card4,
                     text="Toolbar customization is available when a database session is active.",
                     font=self.FONT_SUBTITLE, fg=self.COLORS["on_surface_variant"],
                     bg=self.COLORS["card_bg"]).pack(anchor="w")

        # Card 5: Registration Field Visibility
        if self.draft_focus_visibility_vars:
            card5 = self._create_card(c, "Registration Field Visibility")
            for field_name, var in sorted(self.draft_focus_visibility_vars.items()):
                create_toggle_row(card5, field_name, var)
        elif self.app is not None:
            card5 = self._create_card(c, "Registration Field Visibility")
            tk.Label(card5,
                     text="Load a database first to configure per-field visibility.",
                     font=self.FONT_SUBTITLE, fg=self.COLORS["on_surface_variant"],
                     bg=self.COLORS["card_bg"]).pack(anchor="w")

    def _collect_layout_state(self):
        """Collect and return a comprehensive dictionary of all current layout values."""
        preset = {
            "show_list": self.var_show_list.get(),
            "show_search": self.var_show_search.get(),
            "show_reg": self.var_show_reg.get(),
            "show_images": self.var_show_images.get(),
            "location_in_center": self.var_location_center.get(),
            "location_2row": self.var_location_2row.get(),
            "show_image_tools": self.var_show_image_tools.get(),
            "show_bulk_edit": self.var_show_bulk_edit.get(),
            "show_secondary_nav": self.var_show_secondary_nav.get(),
            "combine_local_and_online": self.var_combine_images.get(),
            "image_stack": self.var_image_stack.get(),
            "large_reviewed_button": self.var_large_reviewed_btn.get(),
            "snap_lock": self.var_snap_lock.get(),
            "auto_advance": self.var_auto_advance.get(),
            "auto_advance_history": self.var_auto_advance_history.get(),
            "auto_resolve_conflicts": self.var_auto_resolve.get(),
            "strict_input_validation": self.var_strict_validation.get(),
            "toolbar_buttons": {k: v.get() for k, v in self.draft_toolbar_vars.items()},
            "focus_mode": self.var_focus_mode.get(),
            "focus_fallback": self.var_focus_fallback.get(),
            "focus_dynamic_update": self.var_focus_dynamic.get(),
            "focus_sec_problems": self.var_focus_sec_problems.get(),
            "focus_sec_location": self.var_focus_sec_location.get(),
            "focus_visibility": {k: v.get() for k, v in self.draft_focus_visibility_vars.items()}
        }
        return preset

    def _push_layout_to_app(self):
        """Push draft layout variables to the host application and apply immediately."""
        if not self.app:
            return
        try:
            if hasattr(self.app, "show_list_var"):
                self.app.show_list_var.set(self.var_show_list.get())
            if hasattr(self.app, "draft_show_list_var"):
                self.app.draft_show_list_var.set(self.var_show_list.get())

            if hasattr(self.app, "show_search_var"):
                self.app.show_search_var.set(self.var_show_search.get())
            if hasattr(self.app, "draft_show_search_var"):
                self.app.draft_show_search_var.set(self.var_show_search.get())

            if hasattr(self.app, "show_reg_var"):
                self.app.show_reg_var.set(self.var_show_reg.get())
            if hasattr(self.app, "draft_show_reg_var"):
                self.app.draft_show_reg_var.set(self.var_show_reg.get())

            if hasattr(self.app, "show_images_var"):
                self.app.show_images_var.set(self.var_show_images.get())
            if hasattr(self.app, "draft_show_images_var"):
                self.app.draft_show_images_var.set(self.var_show_images.get())

            if hasattr(self.app, "location_in_center_var"):
                self.app.location_in_center_var.set(self.var_location_center.get())
            if hasattr(self.app, "draft_location_in_center_var"):
                self.app.draft_location_in_center_var.set(self.var_location_center.get())

            if hasattr(self.app, "show_image_tools_var"):
                self.app.show_image_tools_var.set(self.var_show_image_tools.get())
            if hasattr(self.app, "draft_show_image_tools_var"):
                self.app.draft_show_image_tools_var.set(self.var_show_image_tools.get())

            if hasattr(self.app, "show_bulk_edit_var"):
                self.app.show_bulk_edit_var.set(self.var_show_bulk_edit.get())
            if hasattr(self.app, "draft_show_bulk_edit_var"):
                self.app.draft_show_bulk_edit_var.set(self.var_show_bulk_edit.get())

            if hasattr(self.app, "show_secondary_nav_var"):
                self.app.show_secondary_nav_var.set(self.var_show_secondary_nav.get())
            if hasattr(self.app, "apply_secondary_nav_visibility"):
                self.app.apply_secondary_nav_visibility(self.var_show_secondary_nav.get())

            if hasattr(self.app, "combine_images_var"):
                self.app.combine_images_var.set(self.var_combine_images.get())
            if hasattr(self.app, "draft_combine_images_var"):
                self.app.draft_combine_images_var.set(self.var_combine_images.get())

            if hasattr(self.app, "image_stack_var"):
                self.app.image_stack_var.set(self.var_image_stack.get())
                self.app.image_view_mode = "stack" if self.var_image_stack.get() else "gallery"
            if hasattr(self.app, "draft_image_stack_var"):
                self.app.draft_image_stack_var.set(self.var_image_stack.get())

            if hasattr(self.app, "large_reviewed_button_var"):
                self.app.large_reviewed_button_var.set(self.var_large_reviewed_btn.get())

            if hasattr(self.app, "snap_lock_var"):
                self.app.snap_lock_var.set(self.var_snap_lock.get())

            if hasattr(self.app, "auto_advance_var"):
                self.app.auto_advance_var.set(self.var_auto_advance.get())
            if hasattr(self.app, "auto_advance_history_var"):
                self.app.auto_advance_history_var.set(self.var_auto_advance_history.get())
            if hasattr(self.app, "auto_resolve_conflicts_var"):
                self.app.auto_resolve_conflicts_var.set(self.var_auto_resolve.get())
            if hasattr(self.app, "strict_input_validation_var"):
                self.app.strict_input_validation_var.set(self.var_strict_validation.get())

            # Sync toolbar vars
            for k, v in self.draft_toolbar_vars.items():
                if hasattr(self.app, "toolbar_vars") and k in self.app.toolbar_vars:
                    self.app.toolbar_vars[k].set(v.get())
                if hasattr(self.app, "draft_toolbar_vars") and k in self.app.draft_toolbar_vars:
                    self.app.draft_toolbar_vars[k].set(v.get())

            # Sync focus mode & visibility
            if hasattr(self.app, "focus_mode_var"):
                self.app.focus_mode_var.set(self.var_focus_mode.get())
            if hasattr(self.app, "focus_fallback_var"):
                self.app.focus_fallback_var.set(self.var_focus_fallback.get())
            if hasattr(self.app, "focus_dynamic_update_var"):
                self.app.focus_dynamic_update_var.set(self.var_focus_dynamic.get())
            if hasattr(self.app, "focus_visibility_vars"):
                if "Problems" in self.app.focus_visibility_vars:
                    self.app.focus_visibility_vars["Problems"].set(self.var_focus_sec_problems.get())
                if "Location" in self.app.focus_visibility_vars:
                    self.app.focus_visibility_vars["Location"].set(self.var_focus_sec_location.get())
                for k, v in self.draft_focus_visibility_vars.items():
                    if k in self.app.focus_visibility_vars:
                        self.app.focus_visibility_vars[k].set(v.get())

            # Publish layout change event to EventBus
            app_bus.publish(LAYOUT_CHANGED, preset=self._collect_layout_state())
        except Exception as e:
            print(f"[UnifiedSettings] Error pushing layout to app: {e}")

    # ── TAB 4: FOCUS MODE ────────────────────────────────────────────────────
    def _build_tab_focus(self):
        c = self._create_scrollable_tab("focus")

        # Card 1: Focus Master Switches
        card1 = self._create_card(c, "Focus Mode Controls")
        card1.tutorial_id = "focus_options"
        create_toggle_row(card1, "Enable Focus Mode", self.var_focus_mode, ui_ref=self.app or self)
        create_toggle_row(card1, "Dynamic Problem Fallback", self.var_focus_fallback,
                          ui_ref=self.app or self, info_text=SETTING_INFO_TEXTS["focus_fallback"])
        create_toggle_row(card1, "Update Fields Dynamically", self.var_focus_dynamic,
                          ui_ref=self.app or self, info_text=SETTING_INFO_TEXTS["focus_dynamic_update"])

        # Card 2: Section Visibility (built-in sections)
        card2 = self._create_card(c, "Form Sections Visibility")
        create_toggle_row(card2, "Problems Section", self.var_focus_sec_problems, ui_ref=self.app or self)
        create_toggle_row(card2, "Location Section", self.var_focus_sec_location, ui_ref=self.app or self)

        # Card 3: Per-field visibility (from app.focus_visibility_vars if available)
        if self.draft_focus_visibility_vars:
            card3 = self._create_card(c, "Registration Field Visibility in Focus Mode")
            card3.tutorial_id = "focus_fields"
            for field_name, var in sorted(self.draft_focus_visibility_vars.items()):
                create_toggle_row(card3, field_name, var)
        elif self.app is not None:
            # App connected but no vars yet
            card3 = self._create_card(c, "Registration Field Visibility in Focus Mode")
            tk.Label(card3,
                     text="Load a database first to configure per-field focus visibility.",
                     font=self.FONT_SUBTITLE, fg=self.COLORS["on_surface_variant"],
                     bg=self.COLORS["card_bg"]).pack(anchor="w")

    # ── TAB 5: PRESETS ───────────────────────────────────────────────────────
    def _build_tab_presets(self):
        c = self._create_scrollable_tab("presets")

        # ── Layout Presets ──
        card1 = self._create_card(c, "Layout Presets Manager")
        card1.tutorial_id = "layout_presets"

        r1 = tk.Frame(card1, bg=self.COLORS["card_bg"])
        r1.pack(fill="x", pady=sc(4))
        tk.Label(r1, text="Saved Layout Presets:", font=self.FONT_DATA,
                 fg=self.COLORS["on_surface"], bg=self.COLORS["card_bg"]).pack(side="left")

        cb_layout = ttk.Combobox(r1, state="readonly", width=20, cursor="hand2")
        cb_layout.pack(side="left", padx=sc(8))

        def _refresh_layouts():
            p = config.load_prefs() or {}
            saved = p.get("layouts", {}).get("saved", {})
            cb_layout["values"] = sorted(saved.keys())

        _refresh_layouts()

        def _load_layout():
            name = cb_layout.get()
            if not name:
                return
            p = config.load_prefs() or {}
            layout = p.get("layouts", {}).get("saved", {}).get(name)
            if not layout:
                return
            self.var_show_list.set(layout.get("show_list", True))
            self.var_show_search.set(layout.get("show_search", True))
            self.var_show_reg.set(layout.get("show_reg", True))
            self.var_show_images.set(layout.get("show_images", True))
            self.var_location_center.set(layout.get("location_in_center", False))
            self.var_location_2row.set(layout.get("location_2row", False))
            self.var_show_image_tools.set(layout.get("show_image_tools", True))
            self.var_show_bulk_edit.set(layout.get("show_bulk_edit", True))
            self.var_combine_images.set(layout.get("combine_local_and_online", False))
            self.var_image_stack.set(layout.get("image_stack", False))
            self.var_large_reviewed_btn.set(layout.get("large_reviewed_button", True))
            self.var_snap_lock.set(layout.get("snap_lock", False))
            self.var_focus_mode.set(layout.get("focus_problems", False))
            if "toolbar_buttons" in layout:
                for tb_name, tb_val in layout["toolbar_buttons"].items():
                    if tb_name in self.draft_toolbar_vars:
                        self.draft_toolbar_vars[tb_name].set(tb_val)

            if self.app and hasattr(self.app, "apply_saved_layout"):
                self.app.apply_saved_layout(name)
            elif self.app:
                self._push_layout_to_app()
            messagebox.showinfo("Layout Loaded", f"Layout '{name}' applied.", parent=self.win)

        tk.Button(
            r1, text="Load", font=self.FONT_DATA, fg=self.COLORS["on_surface"],
            bg=self.COLORS["surface"], bd=1, relief="solid", padx=sc(8), pady=sc(2),
            cursor="hand2", command=_load_layout
        ).pack(side="left", padx=sc(4))

        def _delete_layout():
            name = cb_layout.get()
            if not name or name in ("Default", "Startup Default"):
                return
            p = config.load_prefs() or {}
            if "layouts" in p and "saved" in p["layouts"] and name in p["layouts"]["saved"]:
                del p["layouts"]["saved"][name]
                config.save_prefs(p)
                _refresh_layouts()
                cb_layout.set("")

        tk.Button(
            r1, text="Delete", font=self.FONT_DATA, fg=self.COLORS["error"],
            bg=self.COLORS["surface"], bd=1, relief="solid", padx=sc(8), pady=sc(2),
            cursor="hand2", command=_delete_layout
        ).pack(side="left", padx=sc(4))

        r2 = tk.Frame(card1, bg=self.COLORS["card_bg"])
        r2.pack(fill="x", pady=sc(6))
        entry_layout = ttk.Entry(r2, width=20)
        entry_layout.pack(side="left", padx=(0, sc(8)))

        def _save_layout():
            name = entry_layout.get().strip()
            if not name:
                return
            p = config.load_prefs() or {}
            if "layouts" not in p:
                p["layouts"] = {}
            if "saved" not in p["layouts"]:
                p["layouts"]["saved"] = {}
            layout = {
                "show_list": self.var_show_list.get(),
                "show_search": self.var_show_search.get(),
                "show_reg": self.var_show_reg.get(),
                "show_images": self.var_show_images.get(),
                "location_in_center": self.var_location_center.get(),
                "location_2row": self.var_location_2row.get(),
                "show_image_tools": self.var_show_image_tools.get(),
                "show_bulk_edit": self.var_show_bulk_edit.get(),
                "combine_local_and_online": self.var_combine_images.get(),
                "image_stack": self.var_image_stack.get(),
                "large_reviewed_button": self.var_large_reviewed_btn.get(),
                "snap_lock": self.var_snap_lock.get(),
                "focus_problems": self.var_focus_mode.get(),
                "toolbar_buttons": {k: v.get() for k, v in self.draft_toolbar_vars.items()},
            }
            if self.app:
                if hasattr(self.app, "root"):
                    layout["window_state"] = self.app.root.state()
                    layout["window_geometry"] = self.app.root.geometry()
                if hasattr(self.app, "middle_panes"):
                    try:
                        layout["middle_sash"] = self.app.middle_panes.sashpos(0)
                    except Exception:
                        pass
                if hasattr(self.app, "panes"):
                    try:
                        layout["main_sashes"] = [self.app.panes.sashpos(0), self.app.panes.sashpos(1)]
                    except Exception:
                        pass
            p["layouts"]["saved"][name] = layout
            config.save_prefs(p)
            _refresh_layouts()
            entry_layout.delete(0, "end")
            messagebox.showinfo("Preset Saved",
                                f"Layout preset '{name}' saved successfully!", parent=self.win)

        tk.Button(
            r2, text="Save Preset", font=self.FONT_DATA, fg=self.COLORS["on_primary"],
            bg=self.COLORS["secondary"], bd=0, relief="flat", padx=sc(10), pady=sc(3),
            cursor="hand2", command=_save_layout
        ).pack(side="left")

        r3 = tk.Frame(card1, bg=self.COLORS["card_bg"])
        r3.pack(fill="x", pady=sc(4))

        def _set_startup_default():
            if self.app and hasattr(self.app, "set_current_as_startup_default"):
                self.app.set_current_as_startup_default()
                messagebox.showinfo("Startup Default",
                                    "Current layout set as startup default.", parent=self.win)

        def _reset_factory():
            if messagebox.askyesno("Reset Layout", "Reset all layouts to factory defaults?",
                                   parent=self.win):
                if self.app and hasattr(self.app, "reset_layout_to_factory"):
                    self.app.reset_layout_to_factory()
                else:
                    p = config.load_prefs() or {}
                    if "layouts" in p:
                        del p["layouts"]
                        config.save_prefs(p)
                _refresh_layouts()

        tk.Button(
            r3, text="Set Current as Startup Default", font=self.FONT_DATA,
            fg=self.COLORS["on_surface"], bg=self.COLORS["surface"], bd=1,
            relief="solid", padx=sc(10), pady=sc(3), cursor="hand2",
            command=_set_startup_default
        ).pack(side="left", padx=(0, sc(6)))

        tk.Button(
            r3, text="Reset to Factory", font=self.FONT_DATA,
            fg=self.COLORS["on_surface_variant"], bg=self.COLORS["surface"], bd=1,
            relief="solid", padx=sc(10), pady=sc(3), cursor="hand2",
            command=_reset_factory
        ).pack(side="left")

        # ── Focus Presets ──
        card2 = self._create_card(c, "Focus Presets Manager")
        card2.tutorial_id = "focus_presets"

        rf1 = tk.Frame(card2, bg=self.COLORS["card_bg"])
        rf1.pack(fill="x", pady=sc(4))
        tk.Label(rf1, text="Saved Focus Presets:", font=self.FONT_DATA,
                 fg=self.COLORS["on_surface"], bg=self.COLORS["card_bg"]).pack(side="left")

        cb_focus = ttk.Combobox(rf1, state="readonly", width=20, cursor="hand2")
        cb_focus.pack(side="left", padx=sc(8))

        def _refresh_focus():
            p = config.load_prefs() or {}
            saved = p.get("focus_presets", {})
            cb_focus["values"] = sorted(saved.keys())

        _refresh_focus()

        def _load_focus():
            name = cb_focus.get()
            if not name:
                return
            p = config.load_prefs() or {}
            preset = p.get("focus_presets", {}).get(name)
            if preset:
                self.var_focus_fallback.set(preset.get("fallback", True))
                self.var_focus_mode.set(True)
                vis = preset.get("visibility", {})
                if "Problems" in vis:
                    self.var_focus_sec_problems.set(vis["Problems"])
                if "Location" in vis:
                    self.var_focus_sec_location.set(vis["Location"])
                for k, v in self.draft_focus_visibility_vars.items():
                    if k in vis:
                        v.set(vis[k])
                if self.app:
                    self._push_layout_to_app()
                messagebox.showinfo("Focus Preset", f"Preset '{name}' loaded.", parent=self.win)

        def _delete_focus():
            name = cb_focus.get()
            if not name:
                return
            p = config.load_prefs() or {}
            if "focus_presets" in p and name in p["focus_presets"]:
                del p["focus_presets"][name]
                config.save_prefs(p)
                _refresh_focus()
                cb_focus.set("")

        tk.Button(
            rf1, text="Load", font=self.FONT_DATA, fg=self.COLORS["on_surface"],
            bg=self.COLORS["surface"], bd=1, relief="solid", padx=sc(8), pady=sc(2),
            cursor="hand2", command=_load_focus
        ).pack(side="left", padx=sc(4))

        tk.Button(
            rf1, text="Delete", font=self.FONT_DATA, fg=self.COLORS["error"],
            bg=self.COLORS["surface"], bd=1, relief="solid", padx=sc(8), pady=sc(2),
            cursor="hand2", command=_delete_focus
        ).pack(side="left", padx=sc(4))

        rf2 = tk.Frame(card2, bg=self.COLORS["card_bg"])
        rf2.pack(fill="x", pady=sc(6))
        entry_focus = ttk.Entry(rf2, width=20)
        entry_focus.pack(side="left", padx=(0, sc(8)))

        def _save_focus():
            name = entry_focus.get().strip()
            if not name:
                return
            p = config.load_prefs() or {}
            if "focus_presets" not in p:
                p["focus_presets"] = {}
            vis = {k: v.get() for k, v in self.draft_focus_visibility_vars.items()}
            vis["Problems"] = self.var_focus_sec_problems.get()
            vis["Location"] = self.var_focus_sec_location.get()
            p["focus_presets"][name] = {
                "fallback": self.var_focus_fallback.get(),
                "visibility": vis,
            }
            config.save_prefs(p)
            _refresh_focus()
            entry_focus.delete(0, "end")
            messagebox.showinfo("Preset Saved",
                                f"Focus preset '{name}' saved!", parent=self.win)

        tk.Button(
            rf2, text="Save Preset", font=self.FONT_DATA, fg=self.COLORS["on_primary"],
            bg=self.COLORS["secondary"], bd=0, relief="flat", padx=sc(10), pady=sc(3),
            cursor="hand2", command=_save_focus
        ).pack(side="left")

    # ── TAB 6: ADVANCED ──────────────────────────────────────────────────────
    def _build_tab_advanced(self):
        c = self._create_scrollable_tab("advanced")

        # Card 1: Graphics & Resampling
        card1 = self._create_card(c, "Graphics & Resampling Engine")
        f_res = tk.Frame(card1, bg=self.COLORS["card_bg"])
        f_res.pack(fill="x", pady=sc(4))
        tk.Label(f_res, text="Resampling Algorithm:", font=self.FONT_DATA,
                 fg=self.COLORS["on_surface"], bg=self.COLORS["card_bg"]).pack(side="left")
        create_info_badge(f_res, SETTING_INFO_TEXTS["image_resampling_algorithm"], ui_ref=self.app or self).pack(side="left", padx=(sc(6), sc(8)))
        ttk.Combobox(f_res, textvariable=self.var_resampling,
                     values=["LANCZOS (High Quality)", "BILINEAR (Balanced)",
                             "NEAREST (Fast draft / Pixelated)"],
                     state="readonly", width=28, cursor="hand2").pack(side="left", padx=sc(4))

        f_url = tk.Frame(card1, bg=self.COLORS["card_bg"])
        f_url.pack(fill="x", pady=sc(6))
        tk.Label(f_url, text="Image URL Pattern Override:", font=self.FONT_DATA,
                 fg=self.COLORS["on_surface"], bg=self.COLORS["card_bg"]).pack(side="left")
        create_info_badge(f_url, SETTING_INFO_TEXTS["image_url_pattern_override"], ui_ref=self.app or self).pack(side="left", padx=(sc(6), sc(8)))
        url_entry_frame = tk.Frame(f_url, bg=self.COLORS["card_bg"],
                                   highlightbackground=self.COLORS["outline_variant"],
                                   highlightthickness=1)
        url_entry_frame.pack(side="left", padx=sc(4))
        tk.Entry(url_entry_frame, textvariable=self.var_url_pattern,
                 font=self.FONT_DATA, fg=self.COLORS["on_surface"],
                 bg=self.COLORS["card_bg"], bd=0, width=28).pack(padx=sc(4), pady=sc(2))
        tk.Label(card1, text="Leave empty to use the database's default URL pattern.",
                 font=self.FONT_SUBTITLE, fg=self.COLORS["on_surface_variant"],
                 bg=self.COLORS["card_bg"]).pack(anchor="w", pady=(sc(2), 0))

        # Card 2: Feature Flags & Experimental
        card2 = self._create_card(c, "Unfinished & Experimental Features")
        create_toggle_row(card2, "Enable Bulk Editor Tool", self.var_enable_bulk, ui_ref=self.app or self)
        create_toggle_row(card2, "Auto-resolve Conflicts", self.var_auto_resolve, ui_ref=self.app or self)
        create_toggle_row(card2, "Strict Input Validation", self.var_strict_validation,
                          ui_ref=self.app or self, info_text=SETTING_INFO_TEXTS["strict_input_validation"])
        create_toggle_row(card2, "Require PIN for Mobile Companion", self.var_require_mobile_pin,
                          ui_ref=self.app or self, info_text=SETTING_INFO_TEXTS["require_mobile_pin"])
        tk.Label(card2,
                 text="⚠ Some experimental features require an application restart.",
                 font=self.FONT_SUBTITLE, fg=self.COLORS["search_orange"],
                 bg=self.COLORS["card_bg"]).pack(anchor="w", pady=(sc(4), 0))

        # Card 3: Taxonomy & Validation
        card3 = self._create_card(c, "Taxonomy & Validation")
        create_toggle_row(card3, "Enable GBIF Validation", self.var_enable_gbif,
                          command=lambda: self._notify_live("enable_gbif", self.var_enable_gbif.get()),
                          ui_ref=self.app or self, info_text="Shows the 'Check GBIF' button to verify plant names against global taxonomic databases.\n\nExcel Impact: Matched names update Genus and Species columns on the Registration sheet upon curator confirmation.")

        f_workers = tk.Frame(card3, bg=self.COLORS["card_bg"])
        f_workers.pack(fill="x", pady=sc(6))
        tk.Label(f_workers, text="GBIF Batch Concurrency:", font=self.FONT_DATA,
                 fg=self.COLORS["on_surface"], bg=self.COLORS["card_bg"]).pack(side="left")
        create_info_badge(f_workers, "Controls how many plant names Arbor checks simultaneously during batch verification.\n\nTechnical: Number of background worker threads (1-10). Lower values reduce timeouts on slower network connections.", ui_ref=self.app or self).pack(side="left", padx=(sc(6), sc(8)))
        ttk.Combobox(f_workers, textvariable=self.var_gbif_max_workers,
                     values=[1, 2, 3, 4, 5, 6, 8, 10],
                     state="readonly", width=6, cursor="hand2").pack(side="left", padx=sc(4))

    # ── TAB 7: TOOLS ─────────────────────────────────────────────────────────
    def _build_tab_tools(self):
        c = self._create_scrollable_tab("tools")

        def _action_btn(parent, label, description, btn_text, callback_name):
            """Helper: one row with a label, description, and action button."""
            row = tk.Frame(parent, bg=self.COLORS["card_bg"])
            row.pack(fill="x", pady=sc(6))
            left = tk.Frame(row, bg=self.COLORS["card_bg"])
            left.pack(side="left", fill="both", expand=True)
            tk.Label(left, text=label, font=self.FONT_LABEL, fg=self.COLORS["on_surface"],
                     bg=self.COLORS["card_bg"]).pack(anchor="w")
            if description:
                tk.Label(left, text=description, font=self.FONT_SUBTITLE,
                         fg=self.COLORS["on_surface_variant"],
                         bg=self.COLORS["card_bg"]).pack(anchor="w", pady=(sc(1), 0))
            tk.Button(row, text=btn_text, font=self.FONT_LABEL,
                      fg=self.COLORS["on_surface"], bg=self.COLORS["surface"],
                      bd=1, relief="solid", padx=sc(12), pady=sc(4),
                      cursor="hand2",
                      command=lambda cb=callback_name: self._execute_action(cb)).pack(
                side="right", padx=sc(8), pady=sc(4))

        # Card 1: Interface Shortcuts
        card1 = self._create_card(c, "Interface")
        _action_btn(card1, "Toggle Dark Mode",
                    "Switch the interface theme between light and dark mode.",
                    "Toggle Theme", "toggle_dark_mode")
        _action_btn(card1, "Database Statistics",
                    "Examine overall counts and checklists of registered records.",
                    "View Statistics", "show_statistics")

        # Card 2: Registration & Layout Tools
        card2 = self._create_card(c, "Registration & Layout")
        _action_btn(card2, "Configure Registration Tabs",
                    "Configure the metadata accordions and panels layout.",
                    "Configure Tabs", "open_tab_config_editor")
        _action_btn(card2, "Edit Field Groups",
                    "Add, remove, or customize grouping of text input fields.",
                    "Edit Groups", "open_group_editor")
        _action_btn(card2, "Focus Settings",
                    "Configure field visibility and behaviors when focusing problems.",
                    "Open Focus Settings", "open_focus_settings")

        # Card 3: Data Presets & Profiles
        card3 = self._create_card(c, "Presets & Profiles")
        _action_btn(card3, "Save Data Preset",
                    "Save current input fields configuration as a profile preset.",
                    "Save Preset...", "save_data_preset_dialog")
        _action_btn(card3, "Load Data Preset",
                    "Apply a previously saved input fields profile configuration.",
                    "Load Preset...", "show_load_data_preset_popup")

        # Card 4: Suggestions Whitelist (Ignored Words)
        card_words = self._create_card(c, "Botanical Whitelist (Ignored Words)")
        tk.Label(
            card_words,
            text="Terms and tokens entered here (one per line) will be ignored during suggestion checks, discrepancy flags, and botanical reviews.",
            font=self.FONT_SUBTITLE, fg=self.COLORS["on_surface_variant"], bg=self.COLORS["card_bg"],
            wraplength=sc(560), justify="left"
        ).pack(anchor="w", pady=(0, sc(6)))

        tf = tk.Frame(card_words, bg=self.COLORS["card_bg"])
        tf.pack(fill="x", pady=sc(4))

        sb = ttk.Scrollbar(tf)
        sb.pack(side="right", fill="y")

        self.text_ignored_words = tk.Text(
            tf, height=6, font=("JetBrains Mono", sc(9)),
            bg=self.COLORS["surface"], fg=self.COLORS["on_surface"],
            insertbackground=self.COLORS["on_surface"],
            highlightbackground=self.COLORS["outline_variant"],
            highlightcolor=self.COLORS["secondary"],
            highlightthickness=1, bd=0, yscrollcommand=sb.set
        )
        self.text_ignored_words.pack(side="left", fill="both", expand=True)
        sb.config(command=self.text_ignored_words.yview)

        if self.draft_ignored_words:
            self.text_ignored_words.insert("1.0", "\n".join(self.draft_ignored_words))

        vf = tk.Frame(card_words, bg=self.COLORS["card_bg"])
        vf.pack(fill="x", pady=(sc(6), sc(2)))

        tk.Checkbutton(
            vf, text="Include variations (ignore capitalization, punctuation, and extra whitespace)",
            variable=self.var_ignored_variations, font=self.FONT_SUBTITLE,
            bg=self.COLORS["card_bg"], fg=self.COLORS["on_surface"],
            activebackground=self.COLORS["card_bg"], selectcolor=self.COLORS["surface"],
            cursor="hand2"
        ).pack(side="left")

        def _save_ignored_words_now():
            raw_text = self.text_ignored_words.get("1.0", "end").strip()
            words = [line.strip() for line in raw_text.split("\n") if line.strip()]
            var_val = self.var_ignored_variations.get()
            self.draft_ignored_words = words
            if self.app:
                if hasattr(self.app, "ignored_words"):
                    self.app.ignored_words = words
                if hasattr(self.app, "ignored_words_variations"):
                    self.app.ignored_words_variations.set(var_val)
                if hasattr(self.app, "save_ignored_words"):
                    self.app.save_ignored_words()
                if hasattr(self.app, "_history_cache"):
                    self.app._history_cache.clear()
                if hasattr(self.app, "show_toast"):
                    self.app.show_toast(f"Saved {len(words)} ignored words", "success")
                else:
                    messagebox.showinfo("Ignored Words", f"Saved {len(words)} ignored words.", parent=self.win)
            else:
                try:
                    from ui.ignored_words_dialog import save_ignored_words
                    from utils import get_resource_path
                    ipath = get_resource_path("ignored_words.json")
                    save_ignored_words(ipath, words, var_val)
                    messagebox.showinfo("Ignored Words", f"Saved {len(words)} ignored words.", parent=self.win)
                except Exception as e:
                    messagebox.showerror("Error", f"Failed to save ignored words: {e}", parent=self.win)

        tk.Button(
            vf, text="Save Words", font=self.FONT_DATA,
            fg=self.COLORS["on_primary"], bg=self.COLORS["secondary"], bd=0,
            relief="flat", padx=sc(10), pady=sc(3), cursor="hand2",
            command=_save_ignored_words_now
        ).pack(side="right")

        # Card 4: Batch Operations
        card4 = self._create_card(c, "Batch Operations")
        _action_btn(card4, "Mark Filtered as Reviewed",
                    "Mark all currently filtered objects as reviewed.",
                    "Mark Reviewed", "batch_set_reviewed_true")
        _action_btn(card4, "Unmark Filtered as Reviewed",
                    "Unmark all currently filtered objects as reviewed.",
                    "Unmark Reviewed", "batch_set_reviewed_false")

        # Card 5: Guidance & Tutorials
        card5 = self._create_card(c, "Tutorials & Guidance")
        _action_btn(card5, "Reset Tutorial Progress",
                    "Clear completed tutorial flags so interactive guides show again.",
                    "Reset Tutorials", "reset_tutorials")

        # Card 6: Application Updates & Version
        card6 = self._create_card(c, "Application Updates & Version")

        curr_ver = getattr(config, "APP_VERSION", "2.1.0")
        ver_row = tk.Frame(card6, bg=self.COLORS["surface"])
        ver_row.pack(fill="x", padx=sc(8), pady=(sc(4), sc(8)))
        tk.Label(ver_row, text="Installed Version:", font=self.FONT_LABEL,
                 fg=self.COLORS["on_surface"], bg=self.COLORS["surface"]).pack(side="left")
        tk.Label(ver_row, text=f"v{curr_ver}", font=self.FONT_DATA,
                 fg=self.COLORS["primary"], bg=self.COLORS["surface"], padx=sc(6)).pack(side="left")

        _action_btn(card6, "Check for Updates Now",
                    "Query GitHub releases to detect and download new Arbor updates.",
                    "Check Now", "check_updates")

        repo_frame = tk.Frame(card6, bg=self.COLORS["surface"])
        repo_frame.pack(fill="x", padx=sc(8), pady=(sc(6), sc(4)))
        tk.Label(repo_frame, text="GitHub Repository:", font=self.FONT_LABEL,
                 fg=self.COLORS["on_surface"], bg=self.COLORS["surface"]).pack(anchor="w")
        
        repo_sub = tk.Frame(repo_frame, bg=self.COLORS["surface"])
        repo_sub.pack(fill="x", pady=(sc(2), 0))
        
        self.entry_update_repo = tk.Entry(
            repo_sub, font=self.FONT_DATA, bg=self.COLORS["surface"],
            fg=self.COLORS["on_surface"], relief="flat", bd=sc(1)
        )
        self.entry_update_repo.insert(0, config.get_update_repo())
        self.entry_update_repo.pack(side="left", fill="x", expand=True, padx=(0, sc(6)))

        def _save_repo_target():
            new_r = self.entry_update_repo.get().strip()
            if "/" in new_r:
                config.set_update_repo(new_r)
                if self.app and hasattr(self.app, "show_toast"):
                    self.app.show_toast(f"Update repository set to {new_r}", "success")
                else:
                    messagebox.showinfo("Repository Updated", f"Update repository set to: {new_r}", parent=self.win)
            else:
                messagebox.showerror("Invalid Repository", "Repository must be in 'owner/repo' format (e.g. Fr0lich/arbor).", parent=self.win)

        def _reset_repo_target():
            config.set_update_repo(config.DEFAULT_GITHUB_REPO)
            self.entry_update_repo.delete(0, "end")
            self.entry_update_repo.insert(0, config.DEFAULT_GITHUB_REPO)
            if self.app and hasattr(self.app, "show_toast"):
                self.app.show_toast(f"Reset to default repository: {config.DEFAULT_GITHUB_REPO}", "info")
            else:
                messagebox.showinfo("Repository Reset", f"Reset to default repository: {config.DEFAULT_GITHUB_REPO}", parent=self.win)

        tk.Button(
            repo_sub, text="Save Repo", font=self.FONT_DATA,
            fg=self.COLORS["on_primary"], bg=self.COLORS["secondary"], bd=0,
            relief="flat", padx=sc(8), pady=sc(2), cursor="hand2",
            command=_save_repo_target
        ).pack(side="left", padx=(0, sc(4)))

        tk.Button(
            repo_sub, text="Reset Default", font=self.FONT_DATA,
            fg=self.COLORS["on_surface"], bg=self.COLORS["surface"], bd=0,
            relief="flat", padx=sc(8), pady=sc(2), cursor="hand2",
            command=_reset_repo_target
        ).pack(side="left")

        if not self.app:
            note = tk.Frame(c, bg=self.COLORS["surface"], pady=sc(8))
            note.pack(fill="x")
            tk.Label(note,
                     text="ℹ️  Tools are only active when launched from within a running Arbor session.",
                     font=self.FONT_SUBTITLE, fg=self.COLORS["on_surface_variant"],
                     bg=self.COLORS["surface"]).pack(anchor="w", padx=sc(4))

    def _execute_action(self, callback_name):
        """Dispatch a named action to the host application."""
        if not callback_name:
            return
        if callback_name == "check_updates":
            from ui.update_dialog import check_for_updates_ui
            check_for_updates_ui(self.win, app=self.app, manual=True)
            return
        if callback_name == "reset_tutorials":
            p = config.load_prefs() or {}
            p["completed_tutorials"] = []
            config.save_prefs(p)
            messagebox.showinfo("Tutorials Reset",
                                "Tutorial progress has been reset. Interactive tutorials can be launched from the Help Center at any time.",
                                parent=self.win)
            return
        if callback_name == "open_ignored_words_editor":
            if hasattr(self, "text_ignored_words") and self.text_ignored_words.winfo_exists():
                self.show_tab("tools")
                self.text_ignored_words.focus_set()
                return

        if not self.app:
            messagebox.showinfo("No Session",
                                "This action requires an active Arbor session.",
                                parent=self.win)
            return
        method = getattr(self.app, callback_name, None)
        if method and callable(method):
            try:
                method()
            except Exception as e:
                messagebox.showerror("Error",
                                     f"Action '{callback_name}' failed:\n{e}",
                                     parent=self.win)
        else:
            messagebox.showerror("Not Implemented",
                                 f"Action '{callback_name}' is not available.",
                                 parent=self.win)

    # ── LIVE CALLBACKS ───────────────────────────────────────────────────────
    def _notify_live(self, key, value):
        """Dispatches live updates to external observers or host application via EventBus."""
        # Publish to the EventBus — primary notification path
        app_bus.publish(SETTINGS_CHANGED, key=key, value=value)
        # Fallback: direct caller-supplied callbacks (legacy support)
        if key in self.live_callbacks:
            try:
                self.live_callbacks[key](value)
            except Exception as e:
                pass

    def _get_current_directory_card_dict(self):
        return {
            "density_mode": self.var_card_density.get(),
            "show_location_row": self.var_card_show_loc.get(),
            "location_granularity": self.var_card_loc_granularity.get(),
            "show_status_badge": self.var_card_show_badge.get(),
            "show_author_citation": self.var_card_show_author.get(),
            "unknown_taxon_fallback": self.var_card_fallback.get(),
            "badge_priority_preset": self.var_card_badge_priority.get(),
            "accent_strip_mode": self.var_card_accent_mode.get(),
            "visible_badge_categories": {k: v.get() for k, v in self.var_badge_cats.items()},
            "visible_meta_tags": {k: v.get() for k, v in self.var_meta_tags.items()},
            "show_directory_view_strip": self.var_card_show_view_strip.get()
        }

    def _sync_card_settings_live(self):
        card_dict = self._get_current_directory_card_dict()
        config.save_directory_card_prefs(card_dict)
        self._notify_live("directory_card_display_changed", card_dict)
        self._refresh_live_preview()

    def _apply_card_preset_in_settings(self, preset_name):
        import config
        prefs = config.get_card_preset_config(preset_name)
        self.var_card_density.set(prefs["density_mode"])
        self.var_card_show_loc.set(prefs["show_location_row"])
        self.var_card_loc_granularity.set(prefs["location_granularity"])
        self.var_card_show_badge.set(prefs["show_status_badge"])
        self.var_card_show_author.set(prefs["show_author_citation"])
        self.var_card_badge_priority.set(prefs.get("badge_priority_preset", "default"))
        self._sync_card_settings_live()

    def _apply_card_persona_in_settings(self, persona_name):
        return self._apply_card_preset_in_settings(persona_name)

    def _reset_card_settings_to_default_ui(self):
        default_prefs = config.reset_directory_card_prefs_to_default()
        self.var_card_density.set(default_prefs["density_mode"])
        self.var_card_show_loc.set(default_prefs["show_location_row"])
        self.var_card_loc_granularity.set(default_prefs["location_granularity"])
        self.var_card_show_badge.set(default_prefs["show_status_badge"])
        self.var_card_show_author.set(default_prefs["show_author_citation"])
        self.var_card_fallback.set(default_prefs["unknown_taxon_fallback"])
        self.var_card_badge_priority.set(default_prefs["badge_priority_preset"])
        self.var_card_accent_mode.set(default_prefs["accent_strip_mode"])
        for k, v in default_prefs["visible_badge_categories"].items():
            if k in self.var_badge_cats:
                self.var_badge_cats[k].set(v)
        for k, v in default_prefs["visible_meta_tags"].items():
            if k in self.var_meta_tags:
                self.var_meta_tags[k].set(v)
        self.var_card_show_view_strip.set(default_prefs.get("show_directory_view_strip", False))
        self._sync_card_settings_live()

    def _build_card_preview_widget(self, parent):
        """Constructs an interactive live preview card widget with real-time feedback."""
        from config import sc

        container = tk.Frame(parent, bg=self.COLORS["card_bg"])
        container.pack(fill="x", pady=(sc(2), sc(6)))

        bar = tk.Frame(container, bg=self.COLORS["card_bg"])
        bar.pack(fill="x", pady=(0, sc(4)))

        tk.Label(bar, text="Sample Record Status:", font=self.FONT_DATA,
                 fg=self.COLORS["on_surface_variant"], bg=self.COLORS["card_bg"]).pack(side="left", padx=(0, sc(8)))

        sample_options = [
            ("taxonomy", "⚠️ Taxonomy"),
            ("provenance", "📍 Missing Label"),
            ("box", "📦 Storage Box"),
            ("reviewed", "✓ Reviewed"),
        ]

        for st_key, st_label in sample_options:
            b = tk.Radiobutton(
                bar, text=st_label, value=st_key, variable=self.var_preview_status,
                font=self.FONT_DATA, bg=self.COLORS["card_bg"],
                activebackground=self.COLORS["card_bg"],
                cursor="hand2", command=self._refresh_live_preview
            )
            b.pack(side="left", padx=(0, sc(6)))

        card_box = tk.Frame(container, bg=self.COLORS["surface_container_highest"],
                            highlightbackground=self.COLORS["outline_variant"],
                            highlightthickness=1, padx=sc(2), pady=sc(2))
        card_box.pack(fill="x")

        card_inner = tk.Frame(card_box, bg=self.COLORS["card_bg"])
        card_inner.pack(fill="x")

        accent_strip = tk.Frame(card_inner, bg=self.COLORS["error"], width=sc(4))
        accent_strip.pack(side="left", fill="y")

        card_body = tk.Frame(card_inner, bg=self.COLORS["card_bg"])
        card_body.pack(side="left", fill="both", expand=True, padx=sc(6), pady=sc(4))

        row1 = tk.Frame(card_body, bg=self.COLORS["card_bg"])
        row1.pack(fill="x", anchor="w")

        cb_lbl = tk.Label(row1, text="[ ]", font=("Inter", sc(9)),
                          fg=self.COLORS["on_surface_variant"], bg=self.COLORS["card_bg"])
        cb_lbl.pack(side="left", padx=(0, sc(4)))

        tax_lbl = tk.Label(row1, text="Quercus robur", font=("Inter", sc(9), "bold"),
                           fg=self.COLORS["on_surface"], bg=self.COLORS["card_bg"], anchor="w")
        tax_lbl.pack(side="left", fill="x", expand=True)

        badge_lbl = tk.Label(row1, text="[ TAX ]", font=("JetBrains Mono", sc(8), "bold"),
                             fg="#ffffff", bg=self.COLORS["error"], padx=sc(4), pady=sc(1))
        badge_lbl.pack(side="right", padx=(sc(4), 0))

        row2 = tk.Frame(card_body, bg=self.COLORS["card_bg"])
        row2.pack(fill="x", anchor="w", pady=(sc(1), 0))

        meta_lbl = tk.Label(row2, text="OBJ-00042 • FAGACEAE • 2 photos • UKN",
                            font=("Inter", sc(8)), fg=self.COLORS["on_surface_variant"],
                            bg=self.COLORS["card_bg"], anchor="w")
        meta_lbl.pack(side="left", fill="x", expand=True)

        row3 = tk.Frame(card_body, bg=self.COLORS["card_bg"])
        row3.pack(fill="x", anchor="w", pady=(sc(2), 0))

        loc_lbl = tk.Label(row3, text="📍 Herbarium • Floor 2 • Cabinet 04 • Shelf B",
                           font=("Inter", sc(8)), fg=self.COLORS["on_surface_variant"],
                           bg=self.COLORS["card_bg"], anchor="w")
        loc_lbl.pack(side="left", fill="x", expand=True)

        self._preview_widgets = {
            "card_body": card_body,
            "accent_strip": accent_strip,
            "cb_lbl": cb_lbl,
            "tax_lbl": tax_lbl,
            "badge_lbl": badge_lbl,
            "row2": row2,
            "meta_lbl": meta_lbl,
            "row3": row3,
            "loc_lbl": loc_lbl,
        }

        self._refresh_live_preview()

    def _refresh_live_preview(self):
        """Dynamically re-render the sample card to reflect all current user preferences."""
        if not hasattr(self, "_preview_widgets") or not self._preview_widgets:
            return

        from config import sc
        st = self.var_preview_status.get() if hasattr(self, "var_preview_status") else "taxonomy"

        samples = {
            "taxonomy": {
                "taxon": "Quercus robur", "author": "L.", "id": "OBJ-00042", "fam": "FAGACEAE",
                "badge": "[ TAX ]", "badge_bg": "#ba1a1a", "accent": "#ba1a1a", "rev": False,
                "photos": "2 photos", "loan": "", "ukn": "UKN", "unval": "",
                "loc_full": "📍 Herbarium • Floor 2 • Cabinet 04 • Shelf B",
                "loc_compact": "📍 C-04 • S-B",
            },
            "provenance": {
                "taxon": "Pinus sylvestris", "author": "L.", "id": "OBJ-00108", "fam": "PINACEAE",
                "badge": "[ PROV ]", "badge_bg": "#d95c14", "accent": "#d95c14", "rev": False,
                "photos": "1 photo", "loan": "LOAN", "ukn": "", "unval": "UNVAL",
                "loc_full": "📍 Herbarium • Floor 1 • Cabinet 12 • Shelf A",
                "loc_compact": "📍 C-12 • S-A",
            },
            "box": {
                "taxon": "Betula pendula", "author": "Roth", "id": "OBJ-00215", "fam": "BETULACEAE",
                "badge": "[ BOX ]", "badge_bg": "#4a7b9d", "accent": "#4a7b9d", "rev": False,
                "photos": "No photos", "loan": "", "ukn": "", "unval": "",
                "loc_full": "📍 Vault B • Floor B1 • Cabinet 02 • Shelf 3",
                "loc_compact": "📍 C-02 • S-3",
            },
            "reviewed": {
                "taxon": "Fraxinus excelsior", "author": "L.", "id": "OBJ-00350", "fam": "OLEACEAE",
                "badge": "[ REV ]", "badge_bg": "#3a7d44", "accent": "#3a7d44", "rev": True,
                "photos": "3 photos", "loan": "", "ukn": "", "unval": "",
                "loc_full": "📍 Herbarium • Floor 3 • Cabinet 08 • Shelf C",
                "loc_compact": "📍 C-08 • S-C",
            },
        }

        data = samples.get(st, samples["taxonomy"])

        # 1. Row 1 Taxon & Author
        if self.var_card_show_author.get():
            self._preview_widgets["tax_lbl"].config(text=f"{data['taxon']} {data['author']}")
        else:
            self._preview_widgets["tax_lbl"].config(text=data["taxon"])

        self._preview_widgets["cb_lbl"].config(text="[☑]" if data["rev"] else "[ ]")
        self._preview_widgets["accent_strip"].config(bg=data["accent"])

        if self.var_card_show_badge.get():
            self._preview_widgets["badge_lbl"].config(
                text=data["badge"], bg=data["badge_bg"], fg="#ffffff"
            )
        else:
            self._preview_widgets["badge_lbl"].config(
                text="", bg=self.COLORS["card_bg"], fg=self.COLORS["card_bg"]
            )

        # 2. Row 2 Metadata
        meta_parts = [data["id"]]
        if self.var_meta_tags.get("family") and self.var_meta_tags["family"].get():
            meta_parts.append(data["fam"])
        if self.var_meta_tags.get("photos") and self.var_meta_tags["photos"].get() and data["photos"]:
            meta_parts.append(data["photos"])
        if self.var_meta_tags.get("loan") and self.var_meta_tags["loan"].get() and data["loan"]:
            meta_parts.append(data["loan"])
        if self.var_meta_tags.get("unknown") and self.var_meta_tags["unknown"].get() and data["ukn"]:
            meta_parts.append(data["ukn"])
        if self.var_meta_tags.get("unvalidated") and self.var_meta_tags["unvalidated"].get() and data["unval"]:
            meta_parts.append(data["unval"])

        self._preview_widgets["meta_lbl"].config(text=" • ".join(meta_parts))

        # 3. Row 3 Location
        show_loc = self.var_card_show_loc.get() and self.var_card_loc_granularity.get() != "none"
        if show_loc:
            loc_str = data["loc_full"] if self.var_card_loc_granularity.get() == "full" else data["loc_compact"]
            self._preview_widgets["loc_lbl"].config(text=loc_str)
            if self._preview_widgets["row3"].winfo_manager() != "pack":
                self._preview_widgets["row3"].pack(fill="x", anchor="w", pady=(sc(2), 0))
        else:
            if self._preview_widgets["row3"].winfo_manager() == "pack":
                self._preview_widgets["row3"].pack_forget()

        # 4. Density padding
        mode = self.var_card_density.get()
        pad_y = sc(2) if mode == "compact" else (sc(6) if mode == "expanded" else sc(4))
        self._preview_widgets["card_body"].pack_configure(pady=pad_y)

    def _build_badge_legend_widget(self, parent):
        """Constructs an explanatory visual reference for status pill badges and priority rules."""
        from config import sc

        legend_box = tk.Frame(parent, bg=self.COLORS["surface_container_low"],
                              highlightbackground=self.COLORS["outline_variant"],
                              highlightthickness=1, padx=sc(10), pady=sc(8))
        legend_box.pack(fill="x", pady=(sc(2), sc(6)))

        tk.Label(legend_box, text="STATUS BADGE REFERENCE & PRIORITY RULE", font=self.FONT_LABEL,
                 fg=self.COLORS["secondary"], bg=self.COLORS["surface_container_low"]).pack(anchor="w")

        rule_text = (
            "Single-Badge Discipline: To maintain instant scrolling (0ms latency), Row 1 displays strictly ONE "
            "status pill badge for the highest-priority issue. Secondary problem tags appear on Row 2."
        )
        tk.Label(legend_box, text=rule_text, font=self.FONT_DATA, wraplength=sc(560),
                 justify="left", fg=self.COLORS["on_surface_variant"],
                 bg=self.COLORS["surface_container_low"]).pack(anchor="w", pady=(sc(2), sc(4)))

        priority_chain = "Priority: Taxonomy [TAX]  ▶  Provenance [PROV]  ▶  Storage Box [BOX]  ▶  Media [IMG]  ▶  Conflicts [CFCT]  ▶  Reviewed [REV]"
        tk.Label(legend_box, text=priority_chain, font=("JetBrains Mono", sc(8), "bold"),
                 fg=self.COLORS["on_surface"], bg=self.COLORS["surface_container_low"]).pack(anchor="w", pady=(0, sc(6)))

        grid_frame = tk.Frame(legend_box, bg=self.COLORS["surface_container_low"])
        grid_frame.pack(fill="x")

        badges_info = [
            ("[ TAX ]", "#ba1a1a", "Taxonomy Discrepancy", "Species, Genus, or Family problem"),
            ("[ PROV ]", "#d95c14", "Provenance / Locality", "MissingLabel, Date, or Locality issue"),
            ("[ BOX ]", "#4a7b9d", "Physical Storage Container", "Box_Label_Problem, PlantPart issue"),
            ("[ IMG ]", "#6750a4", "Media / Image Missing", "Missing voucher photos or scan errors"),
            ("[ CFCT ]", "#d9a036", "Historical Conflict", "Workbook mismatch or unvalidated notes"),
            ("[ REV+ERR ]", "#3a7d44", "Reviewed with Warnings", "Marked reviewed but retains active flags"),
            ("[ REV ]", "#3a7d44", "Clean Reviewed Record", "Verified specimen with zero open problems"),
            ("[ UNREV ]", "#757d77", "Unreviewed Record", "Good standing with no flagged errors"),
        ]

        for i, (b_code, b_color, b_title, b_desc) in enumerate(badges_info):
            r = i // 2
            col = i % 2
            cell = tk.Frame(grid_frame, bg=self.COLORS["surface_container_low"])
            cell.grid(row=r, column=col, sticky="w", padx=sc(6), pady=sc(2))

            pill = tk.Label(cell, text=b_code, font=("JetBrains Mono", sc(7), "bold"),
                            fg="#ffffff", bg=b_color, padx=sc(4), pady=sc(1))
            pill.pack(side="left")

            desc = tk.Label(cell, text=f" {b_title}: {b_desc}", font=("Inter", sc(8)),
                            fg=self.COLORS["on_surface"], bg=self.COLORS["surface_container_low"])
            desc.pack(side="left")

    # ── RESTORE DEFAULTS ─────────────────────────────────────────────────────
    def restore_defaults(self):
        if messagebox.askyesno("Restore Defaults",
                               "Are you sure you want to reset all settings to their default values?",
                               parent=self.win):
            p = config.load_prefs() or {}
            p.clear()
            config.save_prefs(p)
            self.prefs = {}
            self._init_draft_variables()
            messagebox.showinfo("Settings", "Default settings restored. Please reopen settings.",
                                parent=self.win)

    # ── SAVE SETTINGS ────────────────────────────────────────────────────────
    def save_settings(self):
        """Persists draft variables to user_prefs.json via config module."""
        # ── Validate ──────────────────────────────────────────────────────────
        try:
            mins = int(self.var_autosave_mins.get())
            if mins < 1 or mins > 60:
                raise ValueError()
        except ValueError:
            messagebox.showerror("Error",
                                 "Autosave interval must be a number between 1 and 60 minutes.",
                                 parent=self.win)
            return

        old_prefs = config.load_prefs() or {}
        p = dict(old_prefs)  # work on a copy

        # ── General ───────────────────────────────────────────────────────────
        old_autosave_ms = config.AUTOSAVE_INTERVAL_MS
        new_autosave_ms = mins * 60 * 1000
        p["autosave_interval"] = mins

        old_disable_tutorials = old_prefs.get("disable_tutorials", False)
        new_disable_tutorials = self.var_disable_tutorials.get()
        p["disable_tutorials"] = new_disable_tutorials
        p["enable_excel_import_backup"] = self.var_excel_backup.get()
        p["log_verbosity"] = self.var_log_verbosity.get()
        p["auto_advance_on_review"] = self.var_auto_advance.get()
        p["auto_advance_history"] = self.var_auto_advance_history.get()
        try:
            p["autosave_archive_limit"] = int(self.var_archive_limit.get())
        except ValueError:
            p["autosave_archive_limit"] = 10
        p["mobile_autosave_on_stop"] = bool(self.var_mobile_autosave_on_stop.get())

        # ── Appearance & Visuals ──────────────────────────────────────────────
        old_ui_scale = old_prefs.get("ui_scale", getattr(config, "UI_SCALE", 1.0))
        new_ui_scale = self.var_ui_scale.get()
        scale_changed = new_ui_scale != old_ui_scale
        p["dark_mode"] = self.var_dark_mode.get()
        p["ui_scale"] = new_ui_scale
        if scale_changed:
            p["user_set"] = True
        p["enable_problem_highlights"] = self.var_problem_highlights.get()
        p["problem_highlight_color"] = self.var_highlight_color.get()
        p["large_reviewed_button"] = self.var_large_reviewed_btn.get()
        p["snap_lock"] = self.var_snap_lock.get()

        # ── Directory Card View Settings ─────────────────────────────────────
        card_p = self._get_current_directory_card_dict()
        p["directory_card_display"] = card_p
        self._notify_live("directory_card_display_changed", card_p)

        # ── Layout ────────────────────────────────────────────────────────────
        p["show_list"] = self.var_show_list.get()
        p["show_search"] = self.var_show_search.get()
        p["show_reg"] = self.var_show_reg.get()
        p["show_images"] = self.var_show_images.get()
        p["location_in_center"] = self.var_location_center.get()
        p["location_2row"] = self.var_location_2row.get()
        p["show_image_tools"] = self.var_show_image_tools.get()
        p["show_bulk_edit"] = self.var_show_bulk_edit.get()
        p["show_secondary_nav"] = self.var_show_secondary_nav.get()
        p["combine_local_and_online"] = self.var_combine_images.get()
        p["image_stack"] = self.var_image_stack.get()
        p["toolbar_buttons"] = {k: v.get() for k, v in self.draft_toolbar_vars.items()}

        # ── Focus ─────────────────────────────────────────────────────────────
        p["focus_mode"] = self.var_focus_mode.get()
        p["focus_mode_active"] = self.var_focus_mode.get()
        p["focus_fallback"] = self.var_focus_fallback.get()
        p["focus_dynamic_update"] = self.var_focus_dynamic.get()
        p["focus_sec_problems"] = self.var_focus_sec_problems.get()
        p["focus_sec_location"] = self.var_focus_sec_location.get()
        f_vis = {k: v.get() for k, v in self.draft_focus_visibility_vars.items()}
        f_vis["Problems"] = self.var_focus_sec_problems.get()
        f_vis["Location"] = self.var_focus_sec_location.get()
        p["focus_visibility"] = f_vis

        # ── Advanced ──────────────────────────────────────────────────────────
        old_resampling = old_prefs.get("image_resampling_algorithm", "LANCZOS (High Quality)")
        new_resampling = self.var_resampling.get()
        p["image_resampling_algorithm"] = new_resampling
        p["image_url_pattern_override"] = self.var_url_pattern.get()
        p["enable_bulk_editor"] = self.var_enable_bulk.get()
        old_focus_toggle = old_prefs.get("enable_focus_mode_toggle", False)
        new_focus_toggle = self.var_enable_focus_toggle.get()
        p["enable_focus_mode_toggle"] = new_focus_toggle
        p["auto_resolve_conflicts"] = self.var_auto_resolve.get()
        p["strict_input_validation"] = self.var_strict_validation.get()
        p["require_mobile_pin"] = self.var_require_mobile_pin.get()
        p["enable_gbif"] = self.var_enable_gbif.get()
        try:
            p["gbif_max_workers"] = int(self.var_gbif_max_workers.get())
        except Exception:
            p["gbif_max_workers"] = 5

        # ── Write prefs["advanced"] sub-key for backward compatibility ────────
        # (apply_theme() and AdvancedSettingsWindow read from prefs["advanced"])
        adv = p.setdefault("advanced", {})
        adv["enable_problem_highlights"] = p["enable_problem_highlights"]
        adv["problem_highlight_color"] = p["problem_highlight_color"]
        adv["image_resampling_algorithm"] = p["image_resampling_algorithm"]
        adv["image_url_pattern_override"] = p["image_url_pattern_override"]
        adv["enable_bulk_editor"] = p["enable_bulk_editor"]
        adv["enable_focus_mode_toggle"] = p["enable_focus_mode_toggle"]
        adv["require_mobile_pin"] = p["require_mobile_pin"]
        adv["enable_gbif"] = p["enable_gbif"]
        adv["gbif_max_workers"] = p["gbif_max_workers"]
        adv["enable_excel_import_backup"] = p["enable_excel_import_backup"]
        adv["autosave_archive_limit"] = str(p.get("autosave_archive_limit", 10))
        adv["log_verbosity"] = p["log_verbosity"]

        # ── Ignored Words ─────────────────────────────────────────────────────
        if hasattr(self, "text_ignored_words") and self.text_ignored_words.winfo_exists():
            raw_text = self.text_ignored_words.get("1.0", "end").strip()
            words = [line.strip() for line in raw_text.split("\n") if line.strip()]
            var_val = self.var_ignored_variations.get() if hasattr(self, "var_ignored_variations") else True
            if self.app:
                if hasattr(self.app, "ignored_words"):
                    self.app.ignored_words = words
                if hasattr(self.app, "ignored_words_variations"):
                    self.app.ignored_words_variations.set(var_val)
                if hasattr(self.app, "save_ignored_words"):
                    self.app.save_ignored_words()
                if hasattr(self.app, "_history_cache"):
                    self.app._history_cache.clear()
            else:
                try:
                    from ui.ignored_words_dialog import save_ignored_words
                    from utils import get_resource_path
                    ipath = get_resource_path("ignored_words.json")
                    save_ignored_words(ipath, words, var_val)
                except Exception:
                    pass

        # ── Persist ───────────────────────────────────────────────────────────
        config.save_prefs(p)
        try:
            import utils
            utils.reload_log_level()
        except Exception:
            pass

        # ── Post-save side-effects ────────────────────────────────────────────
        restart_needed = False

        # 1. Reschedule autosave if interval changed
        if self.app and new_autosave_ms != old_autosave_ms:
            try:
                config.AUTOSAVE_INTERVAL_MS = new_autosave_ms
                if getattr(self.app, "_autosave_job", None):
                    try:
                        self.app.root.after_cancel(self.app._autosave_job)
                    except Exception:
                        pass
                    self.app._autosave_job = None
                if hasattr(self.app, "_schedule_autosave"):
                    self.app._schedule_autosave()
            except Exception as e:
                print(f"[UnifiedSettings] Autosave reschedule error: {e}")

        # 3. Push layout changes & apply
        if self.app:
            self._push_layout_to_app()

        # 4. Refresh problem highlights if changed
        if self.app and (p["enable_problem_highlights"] != old_prefs.get("enable_problem_highlights", True)
                         or p["problem_highlight_color"] != old_prefs.get("problem_highlight_color", "Default (Red)")):
            if hasattr(self.app, "refresh_styles_and_highlights"):
                try:
                    self.app.refresh_styles_and_highlights()
                except Exception as e:
                    print(f"[UnifiedSettings] refresh_styles_and_highlights error: {e}")

        # 5. Refresh image rendering if algorithm or pattern changed
        if self.app and (new_resampling != old_resampling or p["image_url_pattern_override"] != old_prefs.get("image_url_pattern_override", "")):
            if hasattr(self.app, "refresh_image_rendering"):
                try:
                    self.app.refresh_image_rendering()
                except Exception as e:
                    print(f"[UnifiedSettings] refresh_image_rendering error: {e}")
            if hasattr(self.app, "load_images_for_current"):
                try:
                    self.app.load_images_for_current()
                except Exception as e:
                    pass

        # 6. Update focus toggle visibility
        if self.app and new_focus_toggle != old_focus_toggle:
            if hasattr(self.app, "update_focus_toggle_visibility"):
                try:
                    self.app.update_focus_toggle_visibility()
                except Exception as e:
                    print(f"[UnifiedSettings] update_focus_toggle_visibility error: {e}")

        # 7. Handle restart-required settings
        if scale_changed or p.get("enable_bulk_editor") != old_prefs.get("enable_bulk_editor", False):
            restart_needed = True

        # ── Close window ──────────────────────────────────────────────────────
        self.win.destroy()

        # ── Post-destroy notifications ────────────────────────────────────────
        if restart_needed:
            root = getattr(self.app, "root", self.parent) if self.app else self.parent
            messagebox.showinfo(
                "Restart Required",
                "Some settings will take full effect after restarting Arbor.",
                parent=root
            )


# ── Public Launcher ──────────────────────────────────────────────────────────
def open_unified_settings(parent_win, app_ref=None, initial_tab="general", live_callbacks=None):
    """Launcher function for embedding into host application."""
    return UnifiedSettingsWindow(parent_win, app_ref=app_ref,
                                 initial_tab=initial_tab, live_callbacks=live_callbacks)


# ── Standalone Test Runner ────────────────────────────────────────────────────
if __name__ == "__main__":
    root = tk.Tk()
    root.title("Unified Settings Test Harness")
    root.geometry("400x300")

    def _on_live(key, val):
        print(f"[TEST HARNESS OBSERVER] Event '{key}': {val}")

    tk.Label(root, text="Arbor Settings UI Test Harness",
             font=("Lora", 14, "bold")).pack(pady=20)
    tk.Button(
        root, text="Open Unified Settings", font=("Inter", 11, "bold"),
        bg="#3a7d44", fg="#ffffff", padx=16, pady=8, bd=0, relief="flat", cursor="hand2",
        command=lambda: open_unified_settings(
            root, initial_tab="general",
            live_callbacks={"dark_mode": lambda v: _on_live("dark_mode", v)}
        )
    ).pack(pady=10)

    root.mainloop()
