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
from ui.widgets import ToggleSwitch, create_toggle_row


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
        "surface": "#f9f9f9",
        "surface_container_low": "#f3f3f3",
        "surface_container_highest": "#e2e2e2",
        "card_bg": "#ffffff",
        "on_surface": "#1a1c1c",
        "on_surface_variant": "#4c4546",
        "outline": "#747878",
        "outline_variant": "#c4c7c7",
        "primary": "#000000",
        "on_primary": "#ffffff",
        "secondary": "#2e6b30",
        "error": "#ba1a1a",
        "search_orange": "#d9480f",
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
        if event.widget == self.win:
            # Clean up any bound mousewheel events when window closes
            try:
                self.win.unbind_all("<MouseWheel>")
            except Exception:
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
        title_lbl.pack(side="left", pady=(sc(6), 0), anchor="w")

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
        """Initialize draft Variables from config and prefs."""
        p = self.prefs

        # General
        current_mins = config.AUTOSAVE_INTERVAL_MS // 60000
        self.var_autosave_mins = tk.StringVar(value=str(p.get("autosave_interval", current_mins)))
        self.var_disable_tutorials = tk.BooleanVar(value=p.get("disable_tutorials", False))
        self.var_excel_backup = tk.BooleanVar(value=p.get("enable_excel_import_backup", True))
        self.var_log_verbosity = tk.StringVar(value=p.get("log_verbosity", "ERROR"))
        self.var_archive_limit = tk.StringVar(value=str(p.get("autosave_archive_limit", 10)))

        # Appearance & Visuals
        self.var_dark_mode = tk.BooleanVar(value=p.get("dark_mode", False))
        self.var_ui_scale = tk.DoubleVar(value=p.get("ui_scale", getattr(config, "UI_SCALE", 1.0)))
        self.var_problem_highlights = tk.BooleanVar(value=p.get("enable_problem_highlights", True))
        self.var_highlight_color = tk.StringVar(value=p.get("problem_highlight_color", "Default (Red)"))
        self.var_large_reviewed_btn = tk.BooleanVar(value=p.get("large_reviewed_button", False))
        self.var_snap_lock = tk.BooleanVar(value=p.get("snap_lock", False))

        # Layout & Panels
        self.var_show_list = tk.BooleanVar(value=p.get("show_list", True))
        self.var_show_search = tk.BooleanVar(value=p.get("show_search", True))
        self.var_show_reg = tk.BooleanVar(value=p.get("show_reg", True))
        self.var_show_images = tk.BooleanVar(value=p.get("show_images", True))
        self.var_location_center = tk.BooleanVar(value=p.get("location_in_center", False))
        self.var_show_image_tools = tk.BooleanVar(value=p.get("show_image_tools", True))
        self.var_show_bulk_edit = tk.BooleanVar(value=p.get("show_bulk_edit", True))
        self.var_dashboard_embedded = tk.BooleanVar(value=(p.get("dashboard_mode", "Window") == "Embedded"))
        self.var_image_stack = tk.BooleanVar(value=p.get("image_stack", False))
        self.var_layout_dynamic = tk.BooleanVar(value=False)  # runtime-only, not persisted

        # Focus Mode
        self.var_focus_mode = tk.BooleanVar(value=p.get("focus_mode", False))
        self.var_focus_fallback = tk.BooleanVar(value=p.get("focus_fallback", True))
        self.var_focus_dynamic = tk.BooleanVar(value=p.get("focus_dynamic_update", False))
        self.var_focus_sec_problems = tk.BooleanVar(value=p.get("focus_sec_problems", True))
        self.var_focus_sec_location = tk.BooleanVar(value=p.get("focus_sec_location", True))

        # Advanced
        self.var_resampling = tk.StringVar(value=p.get("image_resampling_algorithm", "LANCZOS (High Quality)"))
        self.var_url_pattern = tk.StringVar(value=p.get("image_url_pattern_override", ""))
        self.var_enable_bulk = tk.BooleanVar(value=p.get("enable_bulk_editor", False))
        self.var_enable_focus_toggle = tk.BooleanVar(value=p.get("enable_focus_mode_toggle", False))
        self.var_auto_resolve = tk.BooleanVar(value=p.get("auto_resolve_conflicts", False))
        self.var_strict_validation = tk.BooleanVar(value=p.get("strict_input_validation", False))

        # Toolbar draft vars (populated from app_ref.toolbar_vars if available)
        self.draft_toolbar_vars = {}
        if self.app and hasattr(self.app, "toolbar_vars"):
            for k, v in self.app.toolbar_vars.items():
                self.draft_toolbar_vars[k] = tk.BooleanVar(value=v.get())

        # Focus visibility draft vars
        self.draft_focus_visibility_vars = {}
        if self.app and hasattr(self.app, "focus_visibility_vars"):
            for k, v in self.app.focus_visibility_vars.items():
                self.draft_focus_visibility_vars[k] = tk.BooleanVar(value=v.get())

    def _build_sidebar_nav(self):
        nav_items = [
            ("general",    "⚙️  General"),
            ("appearance", "🎨  Appearance"),
            ("layout",     "📐  Layout"),
            ("focus",      "🎯  Focus Mode"),
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

        def _on_mousewheel(e):
            if canvas.winfo_exists():
                canvas.yview_scroll(int(-1 * (e.delta / 120)), "units")

        canvas.bind_all("<MouseWheel>", _on_mousewheel)

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
        ttk.Combobox(f2, textvariable=self.var_archive_limit, values=["5", "10", "20", "50"],
                     state="readonly", width=8).pack(side="left", padx=sc(12))

        create_toggle_row(card1, "Enable Backup on Excel Import", self.var_excel_backup)
        tk.Label(card1,
                 text="Note: Saves use background atomic pickles for maximum performance.",
                 font=self.FONT_SUBTITLE, fg=self.COLORS["on_surface_variant"],
                 bg=self.COLORS["card_bg"]).pack(anchor="w", pady=(sc(4), 0))

        # Card 2: Guidance & Diagnostics
        card2 = self._create_card(c, "System Guidance & Diagnostics")
        create_toggle_row(card2, "Disable Interactive Tutorials & Banners", self.var_disable_tutorials)

        f3 = tk.Frame(card2, bg=self.COLORS["card_bg"])
        f3.pack(fill="x", pady=sc(6))
        tk.Label(f3, text="System Logging Verbosity:", font=self.FONT_DATA,
                 fg=self.COLORS["on_surface"], bg=self.COLORS["card_bg"]).pack(side="left")
        ttk.Combobox(f3, textvariable=self.var_log_verbosity,
                     values=["ERROR", "WARNING", "INFO", "DEBUG"],
                     state="readonly", width=12).pack(side="left", padx=sc(12))

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
                           activebackground=self.COLORS["card_bg"]).pack(side="left")
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
        ttk.Combobox(f_clr, textvariable=self.var_highlight_color,
                     values=["Default (Red)", "Yellow", "Orange", "Blue"],
                     state="readonly", width=16).pack(side="left", padx=sc(12))

        # Card 3: Visual Controls
        card3 = self._create_card(c, "Visual Controls")
        create_toggle_row(card3, "Large 'Mark Reviewed' Button", self.var_large_reviewed_btn)
        create_toggle_row(card3, "Snap Window Layout Grid", self.var_snap_lock)

    # ── TAB 3: LAYOUT ────────────────────────────────────────────────────────
    def _build_tab_layout(self):
        c = self._create_scrollable_tab("layout")

        # Card 1: Workspace Panels
        card1 = self._create_card(c, "Workspace Panel Visibility")

        def _apply_if_dynamic():
            """If dynamic update mode is active, immediately push panel changes to the host."""
            if self.var_layout_dynamic.get():
                self._push_layout_to_app()

        def _notify_panel(key, var):
            if key == "location_center":
                self._notify_live("location_center", var.get())
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
        create_toggle_row(card1, "Show Image Zoom/Rotate Toolbar", self.var_show_image_tools,
                          command=_apply_if_dynamic)
        create_toggle_row(card1, "Show Bulk Edit Button", self.var_show_bulk_edit,
                          command=_apply_if_dynamic)

        # Card 2: Behavior
        card2 = self._create_card(c, "View & Dashboard Display")
        create_toggle_row(card2, "Embedded Session Dashboard (vs Separate Window)",
                          self.var_dashboard_embedded, command=_apply_if_dynamic)
        create_toggle_row(card2, "View Images as Stack by Default",
                          self.var_image_stack, command=_apply_if_dynamic)

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

            for idx, (name, var) in enumerate(sorted(self.draft_toolbar_vars.items())):
                row_idx = idx // 2
                col_idx = idx % 2
                cell = tk.Frame(tb_grid, bg=self.COLORS["card_bg"])
                cell.grid(row=row_idx, column=col_idx, sticky="ew", padx=sc(4), pady=sc(2))
                tk.Label(cell, text=name, font=self.FONT_DATA, fg=self.COLORS["on_surface"],
                         bg=self.COLORS["card_bg"]).pack(side="left", anchor="w")
                ToggleSwitch(cell, var, ui_ref=self.app).pack(side="right")
        else:
            card4 = self._create_card(c, "Toolbar Button Visibility")
            tk.Label(card4,
                     text="Toolbar customization is available when a database session is active.",
                     font=self.FONT_SUBTITLE, fg=self.COLORS["on_surface_variant"],
                     bg=self.COLORS["card_bg"]).pack(anchor="w")

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

            if hasattr(self.app, "dashboard_mode_var"):
                self.app.dashboard_mode_var.set(
                    "Embedded" if self.var_dashboard_embedded.get() else "Window"
                )
            if hasattr(self.app, "draft_dashboard_embedded_var"):
                self.app.draft_dashboard_embedded_var.set(self.var_dashboard_embedded.get())

            if hasattr(self.app, "image_stack_var"):
                self.app.image_stack_var.set(self.var_image_stack.get())
            if hasattr(self.app, "draft_image_stack_var"):
                self.app.draft_image_stack_var.set(self.var_image_stack.get())

            # Sync toolbar vars
            for k, v in self.draft_toolbar_vars.items():
                if hasattr(self.app, "toolbar_vars") and k in self.app.toolbar_vars:
                    self.app.toolbar_vars[k].set(v.get())
                if hasattr(self.app, "draft_toolbar_vars") and k in self.app.draft_toolbar_vars:
                    self.app.draft_toolbar_vars[k].set(v.get())

            # Trigger panel updates directly on app
            if hasattr(self.app, "toggle_list_panel"):
                self.app.toggle_list_panel()
            if hasattr(self.app, "toggle_search_panel"):
                self.app.toggle_search_panel()
            if hasattr(self.app, "toggle_location_panel"):
                self.app.toggle_location_panel()
            if hasattr(self.app, "toggle_images_panel"):
                self.app.toggle_images_panel()
            if hasattr(self.app, "toggle_reg_panel"):
                self.app.toggle_reg_panel()
            if hasattr(self.app, "toggle_image_tools"):
                self.app.toggle_image_tools()
            if hasattr(self.app, "toggle_bulk_edit_btn"):
                self.app.toggle_bulk_edit_btn()
            if hasattr(self.app, "toggle_dashboard_mode"):
                self.app.toggle_dashboard_mode()
        except Exception as e:
            print(f"[UnifiedSettings] Error pushing layout to app: {e}")

    # ── TAB 4: FOCUS MODE ────────────────────────────────────────────────────
    def _build_tab_focus(self):
        c = self._create_scrollable_tab("focus")

        # Card 1: Focus Master Switches
        card1 = self._create_card(c, "Focus Mode Controls")
        create_toggle_row(card1, "Enable Focus Mode", self.var_focus_mode)
        create_toggle_row(card1, "Dynamic Problem Fallback", self.var_focus_fallback)
        create_toggle_row(card1, "Update Fields Dynamically", self.var_focus_dynamic)

        # Card 2: Section Visibility (built-in sections)
        card2 = self._create_card(c, "Form Sections Visibility")
        create_toggle_row(card2, "Problems Section", self.var_focus_sec_problems)
        create_toggle_row(card2, "Location Section", self.var_focus_sec_location)

        # Card 3: Per-field visibility (from app.focus_visibility_vars if available)
        if self.draft_focus_visibility_vars:
            card3 = self._create_card(c, "Registration Field Visibility in Focus Mode")
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

        r1 = tk.Frame(card1, bg=self.COLORS["card_bg"])
        r1.pack(fill="x", pady=sc(4))
        tk.Label(r1, text="Saved Layout Presets:", font=self.FONT_DATA,
                 fg=self.COLORS["on_surface"], bg=self.COLORS["card_bg"]).pack(side="left")

        cb_layout = ttk.Combobox(r1, state="readonly", width=20)
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
            if self.app and hasattr(self.app, "apply_saved_layout"):
                self.app.apply_saved_layout(name)
                if hasattr(self.app, "show_list_var"):
                    self.var_show_list.set(self.app.show_list_var.get())
                if hasattr(self.app, "show_search_var"):
                    self.var_show_search.set(self.app.show_search_var.get())
                if hasattr(self.app, "show_reg_var"):
                    self.var_show_reg.set(self.app.show_reg_var.get())
                if hasattr(self.app, "show_images_var"):
                    self.var_show_images.set(self.app.show_images_var.get())
                if hasattr(self.app, "location_in_center_var"):
                    self.var_location_center.set(self.app.location_in_center_var.get())
                if hasattr(self.app, "show_image_tools_var"):
                    self.var_show_image_tools.set(self.app.show_image_tools_var.get())
                if hasattr(self.app, "show_bulk_edit_var"):
                    self.var_show_bulk_edit.set(self.app.show_bulk_edit_var.get())
                if hasattr(self.app, "dashboard_mode_var"):
                    self.var_dashboard_embedded.set(self.app.dashboard_mode_var.get() == "Embedded")
                if hasattr(self.app, "image_stack_var"):
                    self.var_image_stack.set(self.app.image_stack_var.get())
                messagebox.showinfo("Layout Loaded", f"Layout '{name}' applied.", parent=self.win)
            else:
                messagebox.showinfo("Presets", f"Layout: {name}", parent=self.win)

        ttk.Button(r1, text="Load", width=8, command=_load_layout).pack(side="left", padx=2)

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

        ttk.Button(r1, text="Delete", width=8, command=_delete_layout).pack(side="left", padx=2)

        r2 = tk.Frame(card1, bg=self.COLORS["card_bg"])
        r2.pack(fill="x", pady=sc(6))
        entry_layout = ttk.Entry(r2, width=20)
        entry_layout.pack(side="left", padx=(0, sc(8)))

        def _save_layout():
            name = entry_layout.get().strip()
            if not name:
                return
            if self.app and hasattr(self.app, "save_layout_as"):
                self.app.save_layout_as(name)
            else:
                p = config.load_prefs() or {}
                if "layouts" not in p:
                    p["layouts"] = {}
                if "saved" not in p["layouts"]:
                    p["layouts"]["saved"] = {}
                p["layouts"]["saved"][name] = {
                    "show_list": self.var_show_list.get(),
                    "show_search": self.var_show_search.get(),
                    "show_reg": self.var_show_reg.get(),
                    "show_images": self.var_show_images.get(),
                }
                config.save_prefs(p)
            _refresh_layouts()
            entry_layout.delete(0, "end")
            messagebox.showinfo("Preset Saved",
                                f"Layout preset '{name}' saved successfully!", parent=self.win)

        ttk.Button(r2, text="Save Preset", width=12, command=_save_layout).pack(side="left")

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

        ttk.Button(r3, text="Set Current as Startup Default", width=30,
                   command=_set_startup_default).pack(side="left", padx=(0, sc(4)))
        ttk.Button(r3, text="Reset to Factory", width=16,
                   command=_reset_factory).pack(side="left")

        # ── Focus Presets ──
        card2 = self._create_card(c, "Focus Presets Manager")

        rf1 = tk.Frame(card2, bg=self.COLORS["card_bg"])
        rf1.pack(fill="x", pady=sc(4))
        tk.Label(rf1, text="Saved Focus Presets:", font=self.FONT_DATA,
                 fg=self.COLORS["on_surface"], bg=self.COLORS["card_bg"]).pack(side="left")

        cb_focus = ttk.Combobox(rf1, state="readonly", width=20)
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
                for k, v in self.draft_focus_visibility_vars.items():
                    if k in vis:
                        v.set(vis[k])
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

        ttk.Button(rf1, text="Load", width=8, command=_load_focus).pack(side="left", padx=2)
        ttk.Button(rf1, text="Delete", width=8, command=_delete_focus).pack(side="left", padx=2)

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
            p["focus_presets"][name] = {
                "fallback": self.var_focus_fallback.get(),
                "visibility": vis,
            }
            config.save_prefs(p)
            _refresh_focus()
            entry_focus.delete(0, "end")
            messagebox.showinfo("Preset Saved",
                                f"Focus preset '{name}' saved!", parent=self.win)

        ttk.Button(rf2, text="Save Preset", width=12, command=_save_focus).pack(side="left")

    # ── TAB 6: ADVANCED ──────────────────────────────────────────────────────
    def _build_tab_advanced(self):
        c = self._create_scrollable_tab("advanced")

        # Card 1: Graphics & Resampling
        card1 = self._create_card(c, "Graphics & Resampling Engine")
        f_res = tk.Frame(card1, bg=self.COLORS["card_bg"])
        f_res.pack(fill="x", pady=sc(4))
        tk.Label(f_res, text="Resampling Algorithm:", font=self.FONT_DATA,
                 fg=self.COLORS["on_surface"], bg=self.COLORS["card_bg"]).pack(side="left")
        ttk.Combobox(f_res, textvariable=self.var_resampling,
                     values=["LANCZOS (High Quality)", "BILINEAR (Balanced)",
                             "NEAREST (Fast draft / Pixelated)"],
                     state="readonly", width=28).pack(side="left", padx=sc(12))

        f_url = tk.Frame(card1, bg=self.COLORS["card_bg"])
        f_url.pack(fill="x", pady=sc(6))
        tk.Label(f_url, text="Image URL Pattern Override:", font=self.FONT_DATA,
                 fg=self.COLORS["on_surface"], bg=self.COLORS["card_bg"]).pack(side="left")
        url_entry_frame = tk.Frame(f_url, bg=self.COLORS["card_bg"],
                                   highlightbackground=self.COLORS["outline_variant"],
                                   highlightthickness=1)
        url_entry_frame.pack(side="left", padx=sc(12))
        tk.Entry(url_entry_frame, textvariable=self.var_url_pattern,
                 font=self.FONT_DATA, fg=self.COLORS["on_surface"],
                 bg=self.COLORS["card_bg"], bd=0, width=28).pack(padx=sc(4), pady=sc(2))
        tk.Label(card1, text="Leave empty to use the database's default URL pattern.",
                 font=self.FONT_SUBTITLE, fg=self.COLORS["on_surface_variant"],
                 bg=self.COLORS["card_bg"]).pack(anchor="w", pady=(sc(2), 0))

        # Card 2: Feature Flags & Experimental
        card2 = self._create_card(c, "Unfinished & Experimental Features")
        create_toggle_row(card2, "Enable Bulk Editor Tool", self.var_enable_bulk)
        create_toggle_row(card2, "Show Focus Mode Header Toggle", self.var_enable_focus_toggle)
        create_toggle_row(card2, "Auto-resolve Conflicts", self.var_auto_resolve)
        create_toggle_row(card2, "Strict Input Validation", self.var_strict_validation)
        tk.Label(card2,
                 text="⚠ Some experimental features require an application restart.",
                 font=self.FONT_SUBTITLE, fg=self.COLORS["search_orange"],
                 bg=self.COLORS["card_bg"]).pack(anchor="w", pady=(sc(4), 0))

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
        _action_btn(card1, "Session Dashboard",
                    "Open the session statistics and logs dashboard.",
                    "Open Dashboard", "open_session_dashboard_window")
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

        # Card 3: Data Presets & Dictionaries
        card3 = self._create_card(c, "Presets & Dictionaries")
        _action_btn(card3, "Configure Ignored Words",
                    "Add or remove terms ignored by spelling checks.",
                    "Configure Words", "open_ignored_words_editor")
        _action_btn(card3, "Save Data Preset",
                    "Save current input fields configuration as a profile preset.",
                    "Save Preset...", "save_data_preset_dialog")
        _action_btn(card3, "Load Data Preset",
                    "Apply a previously saved input fields profile configuration.",
                    "Load Preset...", "show_load_data_preset_popup")

        # Card 4: Batch Operations
        card4 = self._create_card(c, "Batch Operations")
        _action_btn(card4, "Mark Filtered as Reviewed",
                    "Mark all currently filtered objects as reviewed.",
                    "Mark Reviewed", "batch_set_reviewed_true")
        _action_btn(card4, "Unmark Filtered as Reviewed",
                    "Unmark all currently filtered objects as reviewed.",
                    "Unmark Reviewed", "batch_set_reviewed_false")

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
        """Dispatches live updates to external observers or host application."""
        if key in self.live_callbacks:
            try:
                self.live_callbacks[key](value)
            except Exception as e:
                print(f"[UnifiedSettings] Callback error for '{key}': {e}")
        elif self.app and hasattr(self.app, f"on_settings_live_{key}"):
            try:
                getattr(self.app, f"on_settings_live_{key}")(value)
            except Exception as e:
                print(f"[UnifiedSettings] App handler error for '{key}': {e}")
        else:
            print(f"[UnifiedSettings Live Observer] {key} -> {value}")

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
        try:
            p["autosave_archive_limit"] = int(self.var_archive_limit.get())
        except ValueError:
            p["autosave_archive_limit"] = 10

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

        # ── Layout ────────────────────────────────────────────────────────────
        p["show_list"] = self.var_show_list.get()
        p["show_search"] = self.var_show_search.get()
        p["show_reg"] = self.var_show_reg.get()
        p["show_images"] = self.var_show_images.get()
        p["location_in_center"] = self.var_location_center.get()
        p["show_image_tools"] = self.var_show_image_tools.get()
        p["show_bulk_edit"] = self.var_show_bulk_edit.get()
        p["dashboard_mode"] = "Embedded" if self.var_dashboard_embedded.get() else "Window"
        p["image_stack"] = self.var_image_stack.get()

        # ── Focus ─────────────────────────────────────────────────────────────
        p["focus_mode"] = self.var_focus_mode.get()
        p["focus_fallback"] = self.var_focus_fallback.get()
        p["focus_dynamic_update"] = self.var_focus_dynamic.get()
        p["focus_sec_problems"] = self.var_focus_sec_problems.get()
        p["focus_sec_location"] = self.var_focus_sec_location.get()
        if self.draft_focus_visibility_vars:
            p["focus_visibility"] = {k: v.get() for k, v in self.draft_focus_visibility_vars.items()}

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

        # ── Write prefs["advanced"] sub-key for backward compatibility ────────
        # (apply_theme() and AdvancedSettingsWindow read from prefs["advanced"])
        adv = p.setdefault("advanced", {})
        adv["enable_problem_highlights"] = p["enable_problem_highlights"]
        adv["problem_highlight_color"] = p["problem_highlight_color"]
        adv["image_resampling_algorithm"] = p["image_resampling_algorithm"]
        adv["image_url_pattern_override"] = p["image_url_pattern_override"]
        adv["enable_bulk_editor"] = p["enable_bulk_editor"]
        adv["enable_focus_mode_toggle"] = p["enable_focus_mode_toggle"]
        adv["enable_excel_import_backup"] = p["enable_excel_import_backup"]
        adv["autosave_archive_limit"] = str(p.get("autosave_archive_limit", 10))
        adv["log_verbosity"] = p["log_verbosity"]

        # ── Persist ───────────────────────────────────────────────────────────
        config.save_prefs(p)

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

        # 2. Close tutorial manager if tutorials were disabled
        if new_disable_tutorials and not old_disable_tutorials:
            try:
                from ui.tutorial import TutorialManager
                TutorialManager().close_tutorial()
            except Exception:
                pass

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

        # 5. Refresh image rendering if algorithm changed
        if self.app and new_resampling != old_resampling:
            if hasattr(self.app, "refresh_image_rendering"):
                try:
                    self.app.refresh_image_rendering()
                except Exception as e:
                    print(f"[UnifiedSettings] refresh_image_rendering error: {e}")

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
        bg="#2e6b30", fg="#ffffff", padx=16, pady=8, bd=0, relief="flat", cursor="hand2",
        command=lambda: open_unified_settings(
            root, initial_tab="general",
            live_callbacks={"dark_mode": lambda v: _on_live("dark_mode", v)}
        )
    ).pack(pady=10)

    root.mainloop()
