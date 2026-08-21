"""
ui/settings_old.py — Legacy Settings Window Implementations (Archive)

This file preserves the original implementations of the four legacy settings
dialogs that existed before UnifiedSettingsWindow was made the single entry-point.

These are NOT imported by the application. They serve as a rollback reference.

To revert:
    1. Copy the method body back into main_window.py (open_settings_window,
       open_advanced_settings, show_settings_dropdown).
    2. Copy open_layout_settings back into layout_settings.py (LayoutSettingsMixin).
    3. Copy open_focus_settings back into main_window.py.
    4. Remove the from ui.unified_settings import … line and shim helpers.
"""

# ---------------------------------------------------------------------------
# NOTE: The code below is provided as standalone functions that mirror the
# original method bodies. They are NOT meant to be called directly.
# ---------------------------------------------------------------------------

# ============================================================================
# 1. open_settings_window (was in ui/main_window.py ObjectProgramUI)
# ============================================================================
def _LEGACY_open_settings_window(self):
    """
    Original general settings dialog with two tabs: General and Appearance.
    Footer had an 'Advanced...' button that opened AdvancedSettingsWindow.
    """
    if hasattr(self, "settings_window") and self.settings_window and self.settings_window.winfo_exists():
        self.settings_window.lift()
        self.settings_window.focus_force()
        return

    from config import sc
    import utils
    import config as _cfg

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

    import tkinter as tk
    from tkinter import ttk, messagebox

    FONT_HEADLINE = ("Hanken Grotesk", sc(14), "bold")
    FONT_LABEL = ("JetBrains Mono", sc(10), "bold")
    FONT_DATA = ("JetBrains Mono", sc(11))

    win = tk.Toplevel(self.root)
    self.settings_window = win
    win.title("Settings")
    win.resizable(True, True)
    win.transient(self.root)
    win.grab_set()

    utils.center_and_fit_toplevel(win, sc(520), sc(420))

    win.bind("<Destroy>", lambda e: setattr(self, "settings_window", None) if e.widget == win else None)
    win.bind("<Escape>", lambda e: win.destroy())

    main_container = tk.Frame(win, bg=COLORS["surface"], bd=0, highlightthickness=0)
    main_container.pack(fill="both", expand=True)

    header = tk.Frame(main_container, bg=COLORS["surface_container_low"], height=sc(56))
    header.pack(fill="x", side="top")
    header.pack_propagate(False)
    tk.Frame(header, bg=COLORS["outline"], height=1).pack(fill="x", side="bottom")

    left_header = tk.Frame(header, bg=COLORS["surface_container_low"])
    left_header.pack(side="left", fill="y", padx=sc(16))
    tk.Label(left_header, text="Settings", font=FONT_HEADLINE, fg=COLORS["primary"],
             bg=COLORS["surface_container_low"]).pack(side="left", pady=sc(12))

    tab_nav = tk.Frame(main_container, bg=COLORS["surface_container_highest"], height=sc(40))
    tab_nav.pack(fill="x", side="top")
    tk.Frame(tab_nav, bg=COLORS["outline"], height=1).pack(fill="x", side="bottom")

    tab_content_area = tk.Frame(main_container, bg=COLORS["surface"])
    tab_content_area.pack(fill="both", expand=True)

    settings_tabs = {}
    settings_tab_buttons = {}

    def show_tab(tab_name):
        for name, frame in settings_tabs.items():
            frame.pack_forget()
        settings_tabs[tab_name].pack(fill="both", expand=True)
        for name, btn_tuple in settings_tab_buttons.items():
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
        btn = tk.Button(btn_frame, text=label, font=FONT_LABEL, fg=COLORS["on_surface_variant"],
                        bg=COLORS["surface_container_highest"], bd=0, relief="flat", padx=sc(16),
                        cursor="hand2", command=lambda n=name: show_tab(n))
        btn.pack(side="top", fill="both", expand=True)
        settings_tab_buttons[name] = (btn, bottom_border)

    create_tab_btn("general", "General")
    create_tab_btn("appearance", "Appearance")

    def create_group(parent, title):
        group = tk.Frame(parent, bg=COLORS["surface"], highlightbackground=COLORS["outline"], highlightthickness=1)
        group.pack(fill="x", pady=(0, sc(12)))
        tk.Label(group, text=title.upper(), font=FONT_LABEL, fg=COLORS["on_surface_variant"],
                 bg=COLORS["surface"]).pack(anchor="w", padx=sc(12), pady=(sc(12), sc(6)))
        content = tk.Frame(group, bg=COLORS["surface"])
        content.pack(fill="x", padx=sc(12), pady=(0, sc(12)))
        return content

    # TAB 1: GENERAL
    tab_general = tk.Frame(tab_content_area, bg=COLORS["surface"])
    settings_tabs["general"] = tab_general
    general_inner = tk.Frame(tab_general, bg=COLORS["surface"])
    general_inner.pack(fill="both", expand=True, padx=sc(16), pady=sc(16))

    g_autosave = create_group(general_inner, "Autosave Settings")
    f_auto = tk.Frame(g_autosave, bg=COLORS["surface"])
    f_auto.pack(fill="x", pady=sc(4))
    tk.Label(f_auto, text="Autosave every (minutes):", font=FONT_DATA, fg=COLORS["on_surface"],
             bg=COLORS["surface"]).pack(side="left")
    current_minutes = _cfg.AUTOSAVE_INTERVAL_MS // 60000
    autosave_var = tk.StringVar(value=str(current_minutes))
    spin_frame = tk.Frame(f_auto, bg=COLORS["surface"], highlightbackground=COLORS["outline"], highlightthickness=1)
    spin_frame.pack(side="left", padx=sc(12))
    spin = ttk.Spinbox(spin_frame, from_=1, to=60, textvariable=autosave_var, width=6, font=FONT_DATA)
    spin.pack(padx=sc(2), pady=sc(2))
    tk.Label(g_autosave, text="Note: Saves are done atomically using background pickles.",
             font=("Segoe UI", sc(9)), fg=COLORS["on_surface_variant"], bg=COLORS["surface"]).pack(anchor="w", pady=(sc(6), 0))

    g_system = create_group(general_inner, "System Guidance")
    f_tutorial = tk.Frame(g_system, bg=COLORS["surface"])
    f_tutorial.pack(fill="x", pady=sc(4))
    prefs = _cfg.load_prefs()
    disable_tutorials = prefs.get("disable_tutorials", False)
    tutorials_var = tk.BooleanVar(value=not disable_tutorials)
    chk_frame = tk.Frame(f_tutorial, bg=COLORS["surface"])
    chk_frame.pack(fill="x", pady=sc(2))
    chk = tk.Checkbutton(chk_frame, variable=tutorials_var, bg=COLORS["surface"],
                         activebackground=COLORS["surface"], selectcolor=COLORS["surface"],
                         bd=0, highlightthickness=0, cursor="hand2")
    chk.pack(side="left")
    tk.Label(chk_frame, text="Enable Interactive Tutorials", font=FONT_DATA,
             fg=COLORS["on_surface"], bg=COLORS["surface"]).pack(side="left", padx=sc(8))
    tk.Label(g_system, text="Disabling tutorials stops workflow wizards and guidance banners.",
             font=("Segoe UI", sc(9)), fg=COLORS["on_surface_variant"], bg=COLORS["surface"]).pack(anchor="w", pady=(sc(6), 0))

    # TAB 2: APPEARANCE
    tab_appearance = tk.Frame(tab_content_area, bg=COLORS["surface"])
    settings_tabs["appearance"] = tab_appearance
    appearance_inner = tk.Frame(tab_appearance, bg=COLORS["surface"])
    appearance_inner.pack(fill="both", expand=True, padx=sc(16), pady=sc(16))
    g_scaling = create_group(appearance_inner, "Interface Scaling")
    detected_scale = getattr(_cfg, "_detected_scale", 1.0)
    current_scale = prefs.get("ui_scale", _cfg.UI_SCALE)
    lbl_info = tk.Label(g_scaling,
                        text=f"DPI Ratio Detected: {detected_scale:.0%}   |   Active Scale: {current_scale:.0%}",
                        font=FONT_LABEL, fg=COLORS["secondary"], bg=COLORS["surface"])
    lbl_info.pack(anchor="w", pady=(0, sc(8)))
    scale_var = tk.DoubleVar(value=current_scale)
    options = [0.75, 0.90, 1.0, 1.10, 1.25, 1.50]
    labels = ["75%    very compact", "90%    compact", "100%   default (rec.)",
              "110%   slightly larger", "125%   large", "150%   very large"]
    radio_container = tk.Frame(g_scaling, bg=COLORS["surface"])
    radio_container.pack(fill="x", pady=sc(4))
    col1 = tk.Frame(radio_container, bg=COLORS["surface"])
    col1.pack(side="left", expand=True, fill="both")
    col2 = tk.Frame(radio_container, bg=COLORS["surface"])
    col2.pack(side="left", expand=True, fill="both")
    for idx, (val, lbl) in enumerate(zip(options, labels)):
        target_col = col1 if idx < 3 else col2
        f_rad = tk.Frame(target_col, bg=COLORS["surface"])
        f_rad.pack(fill="x", pady=sc(2))
        rad = tk.Radiobutton(f_rad, variable=scale_var, value=val, bg=COLORS["surface"],
                             activebackground=COLORS["surface"], bd=0, highlightthickness=0, cursor="hand2")
        rad.pack(side="left")
        lbl_rad = tk.Label(f_rad, text=lbl, font=FONT_DATA, fg=COLORS["on_surface"], bg=COLORS["surface"])
        lbl_rad.pack(side="left", padx=sc(8))
    lbl_warning = tk.Label(g_scaling, text="⚠ Changes to UI Scale require a restart of Arbor to take full effect.",
                           font=("Segoe UI", sc(9), "bold"), fg=COLORS["search_orange"], bg=COLORS["surface"])
    lbl_warning.pack(anchor="w", pady=(sc(10), 0))

    # Footer Action Bar
    footer = tk.Frame(main_container, bg=COLORS["surface_container_low"], height=sc(56))
    footer.pack(fill="x", side="bottom")
    footer.pack_propagate(False)
    tk.Frame(footer, bg=COLORS["outline"], height=1).pack(fill="x", side="top")
    left_footer = tk.Frame(footer, bg=COLORS["surface_container_low"])
    left_footer.pack(side="left", fill="y", padx=sc(16))
    tk.Button(left_footer, text="Advanced...", font=FONT_LABEL, fg=COLORS["on_surface"],
              bg=COLORS["surface"], bd=1, relief="solid", padx=sc(16), pady=sc(4),
              cursor="hand2", command=self.open_advanced_settings).pack(side="left", pady=sc(12))
    right_footer = tk.Frame(footer, bg=COLORS["surface_container_low"])
    right_footer.pack(side="right", fill="y", padx=sc(16))
    tk.Button(right_footer, text="Cancel", font=FONT_LABEL, fg=COLORS["on_surface"],
              bg=COLORS["surface"], bd=1, relief="solid", padx=sc(16), pady=sc(4),
              cursor="hand2", command=win.destroy).pack(side="left", padx=sc(8), pady=sc(12))

    def _save_settings():
        try:
            mins = int(autosave_var.get())
            if mins < 1 or mins > 60:
                raise ValueError()
        except ValueError:
            messagebox.showerror("Error", "Autosave interval must be a number between 1 and 60 minutes.", parent=win)
            return
        prefs = _cfg.load_prefs() or {}
        old_autosave_ms = _cfg.AUTOSAVE_INTERVAL_MS
        new_autosave_ms = mins * 60 * 1000
        old_disable_tutorials = prefs.get("disable_tutorials", False)
        new_disable_tutorials = not tutorials_var.get()
        old_ui_scale = prefs.get("ui_scale", _cfg.UI_SCALE)
        new_ui_scale = scale_var.get()
        scale_changed = (new_ui_scale != old_ui_scale)
        if new_autosave_ms != old_autosave_ms:
            _cfg.AUTOSAVE_INTERVAL_MS = new_autosave_ms
            if getattr(self, "_autosave_job", None):
                try:
                    self.root.after_cancel(self._autosave_job)
                except Exception:
                    pass
                self._autosave_job = None
            if hasattr(self, "_schedule_autosave"):
                self._schedule_autosave()
        if new_disable_tutorials != old_disable_tutorials:
            prefs["disable_tutorials"] = new_disable_tutorials
            if new_disable_tutorials:
                from ui.tutorial import TutorialManager
                try:
                    TutorialManager().close_tutorial()
                except Exception:
                    pass
        if scale_changed:
            prefs["ui_scale"] = new_ui_scale
            prefs["user_set"] = True
        prefs["autosave_interval"] = mins
        _cfg.save_prefs(prefs)
        win.destroy()
        if scale_changed:
            messagebox.showinfo("Restart Required",
                                "UI Scale changes will take effect after restarting the application.",
                                parent=self.root)

    apply_btn = tk.Button(right_footer, text="Save Settings  |  Ctrl+Enter", font=FONT_LABEL,
                          fg=COLORS["on_primary"], bg=COLORS["botanical_green"], bd=0, relief="flat",
                          padx=sc(16), pady=sc(4), cursor="hand2", command=_save_settings)
    apply_btn.pack(side="left", pady=sc(12))
    win.bind("<Control-Return>", lambda e: _save_settings())
    show_tab("general")


# ============================================================================
# 2. open_advanced_settings (was in ui/main_window.py ObjectProgramUI)
# ============================================================================
def _LEGACY_open_advanced_settings(self):
    """
    Original advanced settings dialog using AdvancedSettingsWindow from
    ui/advanced_settings.py.  Now replaced by open_unified_settings(initial_tab="advanced").
    """
    if hasattr(self, "advanced_settings_win") and self.advanced_settings_win \
            and self.advanced_settings_win.win.winfo_exists():
        self.advanced_settings_win.win.lift()
        self.advanced_settings_win.win.focus_force()
        return
    from ui.advanced_settings import AdvancedSettingsWindow
    self.advanced_settings_win = AdvancedSettingsWindow(self.root, self)


# ============================================================================
# 3. show_settings_dropdown (was in ui/main_window.py ObjectProgramUI)
# ============================================================================
def _LEGACY_show_settings_dropdown(self):
    """
    Original settings dropdown menu with four separate entries, each opening
    its own legacy dialog. Now all entries open open_unified_settings().
    """
    import tkinter as tk
    popup = tk.Menu(self.root, tearoff=0)
    popup.add_command(label="General Settings...",  command=self.open_settings_window)
    popup.add_command(label="Layout Settings...",   command=self.open_layout_settings)
    popup.add_command(label="Focus Settings...",    command=self.open_focus_settings)
    popup.add_separator()
    popup.add_command(label="Advanced Settings...", command=self.open_advanced_settings)
    popup.post(self.root.winfo_pointerx(), self.root.winfo_pointery())


# ============================================================================
# 4. open_layout_settings (was in ui/layout_settings.py LayoutSettingsMixin)
# ============================================================================
def _LEGACY_open_layout_settings(self):
    """
    Original layout settings dialog. Full implementation with preset management,
    panel toggles, toolbar grid, and dynamic update mode.
    Now replaced by open_unified_settings(initial_tab="layout").
    """
    import tkinter as tk
    from tkinter import ttk
    from config import sc

    if hasattr(self, "layout_win") and getattr(self.layout_win, "winfo_exists", lambda: False)():
        self.layout_win.lift()
        return

    win = tk.Toplevel(self.root)
    win.title("Layout Settings")
    win.transient(self.root)
    win.geometry(f"{sc(460)}x{sc(600)}")
    self.layout_win = win

    bg_color = "#1e1e2e" if getattr(self, "dark_mode_active", False) else "#f3f3f3"
    win.configure(background=bg_color)

    main_frame = ttk.Frame(win, padding=sc(12))
    main_frame.pack(fill="both", expand=True)

    self._init_layout_draft_vars()

    preset_lf = self._build_layout_presets_section(main_frame)

    dyn_frame = ttk.Frame(main_frame)
    dyn_frame.pack(fill="x", pady=(0, 6))

    def toggle_dynamic_update():
        if self.layout_dynamic_update_var.get():
            apply_btn.config(state="disabled")
            self._on_apply_layout_settings()
        else:
            apply_btn.config(state="normal")

    dyn_cb = ttk.Checkbutton(dyn_frame, text="Update dynamically",
                              variable=self.layout_dynamic_update_var,
                              command=toggle_dynamic_update, cursor="hand2")
    dyn_cb.pack(side="left")

    scroll_container = self._build_layout_options_section(main_frame, win, bg_color)
    btn_row, apply_btn, close_win = self._build_layout_bottom_buttons(main_frame, win)

    if self.layout_dynamic_update_var.get():
        apply_btn.config(state="disabled")
    else:
        apply_btn.config(state="normal")

    preset_lf.tutorial_id = "layout_presets"
    scroll_container.tutorial_id = "layout_toggles"

    import config
    prefs = config.load_prefs()
    if "layout_settings" not in prefs.get("completed_tutorials", []):
        try:
            from ui.tutorial import TutorialManager
            win.after(500, lambda: TutorialManager().start_tutorial("layout_settings", win))
        except Exception:
            pass
    try:
        from ui.main_window import _apply_hover_to_all_tk_buttons
        _apply_hover_to_all_tk_buttons(win, self)
    except Exception:
        pass


# ============================================================================
# 5. open_focus_settings (was in ui/main_window.py ObjectProgramUI)
# ============================================================================
def _LEGACY_open_focus_settings(self):
    """
    Original focus settings dialog with presets, fallback toggle, section
    visibility controls, and per-registration-field visibility toggles.
    Now replaced by open_unified_settings(initial_tab="focus").
    """
    import tkinter as tk
    from tkinter import ttk
    from config import sc

    if hasattr(self, "focus_win") and self.focus_win.winfo_exists():
        self.focus_win.lift()
        return

    win = tk.Toplevel(self.root)
    win.title("Focus Settings")
    win.transient(self.root)
    win.geometry(f"{sc(420)}x{sc(600)}")
    win.resizable(True, True)
    self.focus_win = win

    bg_color = "#1e1e2e" if self.dark_mode_active else "#f3f3f3"
    win.configure(background=bg_color)

    main_frame = ttk.Frame(win, padding=sc(12))
    main_frame.pack(fill="both", expand=True)

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

    preset_lf = ttk.LabelFrame(main_frame, text="Focus Presets", padding=sc(8))
    preset_lf.pack(fill="x", pady=(0, 10))

    preset_row1 = ttk.Frame(preset_lf)
    preset_row1.pack(fill="x", pady=2)
    ttk.Label(preset_row1, text="Load Preset:").pack(side="left", padx=2)
    self.focus_dialog_preset_cb = ttk.Combobox(preset_row1, state="readonly", width=18, cursor="hand2")
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
        prefs["focus_presets"][name] = {"fallback": self.draft_focus_fallback_var.get(),
                                        "visibility": vis_state}
        config.save_prefs(prefs)
        refresh_preset_cb()
        preset_name_var.set("")
        self.system_status.config(text=f"Focus preset '{name}' saved (draft state).")

    ttk.Button(preset_row2, text="Save", command=on_save_preset, width=6,
               style="Primary.TButton").pack(side="left", padx=2)

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

    ttk.Button(preset_row2, text="Delete", command=on_delete_preset, width=6,
               style="Tool.TButton").pack(side="left", padx=2)
    refresh_preset_cb()

    dyn_frame = ttk.Frame(main_frame)
    dyn_frame.pack(fill="x", pady=(0, 6))

    def toggle_dynamic_update():
        if self.focus_dynamic_update_var.get():
            apply_btn.config(state="disabled")
            on_apply()
        else:
            apply_btn.config(state="normal")

    dyn_cb = ttk.Checkbutton(dyn_frame, text="Update dynamically",
                              variable=self.focus_dynamic_update_var,
                              command=toggle_dynamic_update, cursor="hand2")
    dyn_cb.pack(side="left")

    btn_row = ttk.Frame(main_frame, padding=(0, 6, 0, 0))
    btn_row.pack(fill="x", side="bottom")

    scroll_container = ttk.Frame(main_frame)
    scroll_container.pack(fill="both", expand=True, side="top")
    canvas = tk.Canvas(scroll_container, highlightthickness=0, bd=0, bg=bg_color)
    scrollbar = ttk.Scrollbar(scroll_container, orient="vertical", command=canvas.yview)
    scrollable_frame = ttk.Frame(canvas)
    scrollable_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
    win_id = canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
    canvas.configure(yscrollcommand=scrollbar.set)
    canvas.bind("<Configure>", lambda e: canvas.itemconfig(win_id, width=e.width))

    def _on_mousewheel(e):
        if canvas.winfo_exists():
            canvas.yview_scroll(int(-1 * (e.delta / 120)), "units")

    win.bind_all("<MouseWheel>", _on_mousewheel)

    def _close_focus_win():
        win.unbind_all("<MouseWheel>")
        win.destroy()

    win.protocol("WM_DELETE_WINDOW", _close_focus_win)
    canvas.pack(side="left", fill="both", expand=True)
    scrollbar.pack(side="right", fill="y")

    def on_switch_toggle():
        if self.focus_dynamic_update_var.get():
            on_apply()

    def create_toggle_row_local(parent, label_text, var):
        from ui.widgets import ToggleSwitch
        row = ttk.Frame(parent)
        row.pack(fill="x", pady=sc(4))
        lbl = ttk.Label(row, text=label_text)
        lbl.pack(side="left", anchor="w")
        sw = ToggleSwitch(row, var, command=on_switch_toggle, ui_ref=self)
        sw.pack(side="right")
        return row

    opts_lf = ttk.LabelFrame(scrollable_frame, text="General Options", padding=sc(8))
    opts_lf.pack(fill="x", pady=(0, 10))
    create_toggle_row_local(opts_lf, "Dynamic Problem Fallback", self.draft_focus_fallback_var)

    sec_lf = ttk.LabelFrame(scrollable_frame, text="Sections Visibility", padding=sc(8))
    sec_lf.pack(fill="x", pady=(0, 10))
    if "Problems" in self.draft_focus_visibility_vars:
        create_toggle_row_local(sec_lf, "Problems Section", self.draft_focus_visibility_vars["Problems"])
    if "Location" in self.draft_focus_visibility_vars:
        create_toggle_row_local(sec_lf, "Location Section", self.draft_focus_visibility_vars["Location"])

    reg_lf = ttk.LabelFrame(scrollable_frame, text="Registration Fields", padding=sc(8))
    reg_lf.pack(fill="x", pady=(0, 10))
    if getattr(self.app, "config", None) and "ui_sections" in self.app.config:
        for field in self.app.config["ui_sections"].get("registration", []):
            name = field["name"]
            create_toggle_row_local(reg_lf, name, self.draft_focus_visibility_vars[name])

    def on_apply():
        self.focus_mode_var.set(True)
        self.draft_focus_mode_var.set(True)
        self.focus_fallback_var.set(self.draft_focus_fallback_var.get())
        for k, v in self.draft_focus_visibility_vars.items():
            if k in self.focus_visibility_vars:
                self.focus_visibility_vars[k].set(v.get())
        self.update_reg_fields_visibility()
        import config
        prefs = config.load_prefs() or {}
        prefs["focus_mode_active"] = True
        prefs["focus_fallback"] = self.focus_fallback_var.get()
        prefs["focus_visibility"] = {k: v.get() for k, v in self.focus_visibility_vars.items()}
        config.save_prefs(prefs)
        self.system_status.config(text="Focus settings applied and Focus Mode enabled.")

    def on_ok():
        on_apply()
        _close_focus_win()

    ttk.Button(btn_row, text="Cancel", command=_close_focus_win, width=10,
               style="Tool.TButton").pack(side="right", padx=4)
    ttk.Button(btn_row, text="OK", command=on_ok, width=10,
               style="Primary.TButton").pack(side="right", padx=4)
    apply_btn = ttk.Button(btn_row, text="Apply", command=on_apply, width=10, style="Primary.TButton")
    apply_btn.pack(side="right", padx=4)
    if self.focus_dynamic_update_var.get():
        apply_btn.config(state="disabled")
    else:
        apply_btn.config(state="normal")

    preset_lf.tutorial_id = "focus_presets"
    opts_lf.tutorial_id = "focus_options"
    reg_lf.tutorial_id = "focus_fields"

    import config
    prefs = config.load_prefs()
    if "focus_settings" not in prefs.get("completed_tutorials", []):
        try:
            from ui.tutorial import TutorialManager
            win.after(500, lambda: TutorialManager().start_tutorial("focus_settings", win))
        except Exception:
            pass
    try:
        from ui.main_window import _apply_hover_to_all_tk_buttons
        _apply_hover_to_all_tk_buttons(win, self)
    except Exception:
        pass
