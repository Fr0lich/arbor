import tkinter as tk
from tkinter import ttk
from config import sc
from ui.widgets import ToggleSwitch, create_toggle_row

class LayoutSettingsMixin:
    def _build_layout_menu(self, menubar):
        menubar.add_command(label="Layout", command=self.open_layout_settings)



    def _init_layout_draft_vars(self):
        self.draft_show_list_var = tk.BooleanVar(value=self.show_list_var.get())
        self.draft_show_search_var = tk.BooleanVar(value=self.show_search_var.get())
        self.draft_show_reg_var = tk.BooleanVar(value=self.show_reg_var.get())
        self.draft_show_images_var = tk.BooleanVar(value=self.show_images_var.get())
        self.draft_location_in_center_var = tk.BooleanVar(value=self.location_in_center_var.get())
        self.draft_show_image_tools_var = tk.BooleanVar(value=self.show_image_tools_var.get())
        self.draft_show_bulk_edit_var = tk.BooleanVar(value=self.show_bulk_edit_var.get())

        self.draft_layout_focus_mode_var = tk.BooleanVar(value=self.focus_mode_var.get())
        self.draft_snap_lock_var = tk.BooleanVar(value=self.snap_lock_var.get())
        self.draft_image_stack_var = tk.BooleanVar(value=self.image_stack_var.get())
        self.draft_dashboard_embedded_var = tk.BooleanVar(value=(self.dashboard_mode_var.get() == "Embedded"))
        self.draft_large_reviewed_button_var = tk.BooleanVar(value=self.large_reviewed_button_var.get())

        self.draft_toolbar_vars = {}
        for k, v in self.toolbar_vars.items():
            self.draft_toolbar_vars[k] = tk.BooleanVar(value=v.get())


    def _on_apply_layout_settings(self):
        # Copy drafts to main variables
        self.show_list_var.set(self.draft_show_list_var.get())
        self.show_search_var.set(self.draft_show_search_var.get())
        self.show_reg_var.set(self.draft_show_reg_var.get())
        self.show_images_var.set(self.draft_show_images_var.get())
        self.location_in_center_var.set(self.draft_location_in_center_var.get())
        self.show_image_tools_var.set(self.draft_show_image_tools_var.get())
        self.show_bulk_edit_var.set(self.draft_show_bulk_edit_var.get())

        self.focus_mode_var.set(self.draft_layout_focus_mode_var.get())
        self.snap_lock_var.set(self.draft_snap_lock_var.get())
        self.image_stack_var.set(self.draft_image_stack_var.get())

        self.large_reviewed_button_var.set(self.draft_large_reviewed_button_var.get())
        self.dashboard_mode_var.set("Embedded" if self.draft_dashboard_embedded_var.get() else "Window")

        for k, v in self.draft_toolbar_vars.items():
            self.toolbar_vars[k].set(v.get())

        # Apply changes in UI
        self.toggle_list_panel()
        self.toggle_search_panel()
        self.toggle_location_panel()
        self.toggle_images_panel()
        self.toggle_reg_panel()
        self.toggle_image_tools()
        self.toggle_bulk_edit_btn()
        self.toggle_dashboard_mode()
        self._toggle_toolbar_buttons()
        self.update_reg_fields_visibility()

        self.image_view_mode = "stack" if self.image_stack_var.get() else "gallery"
        if hasattr(self, "view_btn"):
            self.view_btn.config(text=f"View: {self.image_view_mode}")

        # Save layout as last applied layout state
        self.save_layout_as("Last Applied")
        self.system_status.config(text="Layout settings applied.")


    def _build_layout_presets_section(self, main_frame):
        preset_lf = ttk.LabelFrame(main_frame, text="Layout Presets", padding=sc(8))
        preset_lf.pack(fill="x", pady=(0, 10))

        preset_row1 = ttk.Frame(preset_lf)
        preset_row1.pack(fill="x", pady=2)
        ttk.Label(preset_row1, text="Load Preset:").pack(side="left", padx=2)

        self.layout_dialog_preset_cb = ttk.Combobox(preset_row1, state="readonly", width=18)
        self.layout_dialog_preset_cb.pack(side="left", fill="x", expand=True, padx=4)

        def on_load_preset(event=None):
            val = self.layout_dialog_preset_cb.get()
            if val:
                import config
                prefs = config.load_prefs()
                layout = prefs.get("layouts", {}).get("saved", {}).get(val)
                if layout:
                    self.draft_show_list_var.set(layout.get("show_list", True))
                    self.draft_show_search_var.set(layout.get("show_search", True))
                    self.draft_show_reg_var.set(layout.get("show_reg", True))
                    self.draft_show_images_var.set(layout.get("show_images", True))
                    self.draft_location_in_center_var.set(layout.get("location_in_center", False))
                    self.draft_show_image_tools_var.set(layout.get("show_image_tools", True))
                    self.draft_show_bulk_edit_var.set(layout.get("show_bulk_edit", True))
                    self.draft_layout_focus_mode_var.set(layout.get("focus_problems", False))
                    self.draft_snap_lock_var.set(layout.get("snap_lock", False))
                    self.draft_image_stack_var.set(layout.get("image_stack", False))
                    self.draft_dashboard_embedded_var.set(layout.get("dashboard_mode", "Window") == "Embedded")
                    self.draft_large_reviewed_button_var.set(layout.get("large_reviewed_button", True))

                    if "toolbar_buttons" in layout:
                        for tb_name, tb_val in layout["toolbar_buttons"].items():
                            if tb_name in self.draft_toolbar_vars:
                                self.draft_toolbar_vars[tb_name].set(tb_val)
                    if self.layout_dynamic_update_var.get():
                        self._on_apply_layout_settings()

        self.layout_dialog_preset_cb.bind("<<ComboboxSelected>>", on_load_preset)

        def refresh_preset_cb():
            import config
            prefs = config.load_prefs() or {}
            presets = prefs.get("layouts", {}).get("saved", {})
            names = sorted(presets.keys())
            self.layout_dialog_preset_cb['values'] = names
            if names:
                self.layout_dialog_preset_cb.set("")
            if hasattr(self, "layout_quick_cb"):
                self.layout_quick_cb['values'] = names

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
            prefs = config.load_prefs()
            if "layouts" not in prefs:
                prefs["layouts"] = {"startup_default": None, "saved": {}}
            if "saved" not in prefs["layouts"]:
                prefs["layouts"]["saved"] = {}

            try:
                mid_sash = self.middle_panes.sashpos(0)
            except Exception:
                mid_sash = 400

            try:
                main_sashes = [self.panes.sashpos(0), self.panes.sashpos(1)]
            except Exception:
                main_sashes = [300, 800]

            tb_states = {k: v.get() for k, v in self.draft_toolbar_vars.items()}

            layout = {
                "window_state": self.root.state(),
                "window_geometry": self.root.geometry(),
                "main_sashes": main_sashes,
                "middle_sash": mid_sash,
                "focus_problems": self.draft_layout_focus_mode_var.get(),
                "image_view_mode": "stack" if self.draft_image_stack_var.get() else "gallery",
                "toolbar_buttons": tb_states,
                "show_list": self.draft_show_list_var.get(),
                "show_search": self.draft_show_search_var.get(),
                "show_reg": self.draft_show_reg_var.get(),
                "show_images": self.draft_show_images_var.get(),
                "location_in_center": self.draft_location_in_center_var.get(),
                "show_image_tools": self.draft_show_image_tools_var.get(),
                "show_bulk_edit": self.draft_show_bulk_edit_var.get(),
                "snap_lock": self.draft_snap_lock_var.get(),
                "image_stack": self.draft_image_stack_var.get(),
                "dashboard_mode": "Embedded" if self.draft_dashboard_embedded_var.get() else "Window",
                "large_reviewed_button": self.draft_large_reviewed_button_var.get(),
                "active_filter": self.app.active_filter_dict.copy() if hasattr(self.app, 'active_filter_dict') else {}
            }
            prefs["layouts"]["saved"][name] = layout
            config.save_prefs(prefs)
            refresh_preset_cb()
            preset_name_var.set("")
            self.system_status.config(text=f"Layout preset '{name}' saved.")

        ttk.Button(preset_row2, text="Save", command=on_save_preset, width=6, style="Primary.TButton").pack(side="left", padx=2)

        def on_delete_preset():
            val = self.layout_dialog_preset_cb.get()
            if not val or val == "Default" or val == "Startup Default":
                return
            import config
            prefs = config.load_prefs() or {}
            if "layouts" in prefs and "saved" in prefs["layouts"] and val in prefs["layouts"]["saved"]:
                del prefs["layouts"]["saved"][val]
                config.save_prefs(prefs)
                refresh_preset_cb()
                self.system_status.config(text=f"Layout preset '{val}' deleted.")

        ttk.Button(preset_row2, text="Delete", command=on_delete_preset, width=6, style="Tool.TButton").pack(side="left", padx=2)
        refresh_preset_cb()

        preset_row3 = ttk.Frame(preset_lf)
        preset_row3.pack(fill="x", pady=(6, 2))
        ttk.Button(preset_row3, text="Set Current as Startup Default", command=self.set_current_as_startup_default, style="Primary.TButton").pack(side="left", fill="x", expand=True, padx=2)
        ttk.Button(preset_row3, text="Reset Layout to Factory", command=self.reset_layout_to_factory, style="Tool.TButton").pack(side="right", fill="x", expand=True, padx=2)

        return preset_lf


    def _build_layout_options_section(self, main_frame, win, bg_color):
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

        def _on_mousewheel(e):
            if canvas.winfo_exists():
                canvas.yview_scroll(int(-1*(e.delta/120)), "units")
        win.bind_all("<MouseWheel>", _on_mousewheel)

        self._layout_canvas = canvas

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        def on_switch_toggle():
            if self.layout_dynamic_update_var.get():
                self._on_apply_layout_settings()

        def create_toggle_row(parent, label_text, var, command=None, ui_ref=None):
            row = ttk.Frame(parent)
            row.pack(fill="x", pady=sc(4))
            lbl = ttk.Label(row, text=label_text)
            lbl.pack(side="left", anchor="w")
            cmd = command if command is not None else on_switch_toggle
            ref = ui_ref if ui_ref is not None else self
            sw = ToggleSwitch(row, var, command=cmd, ui_ref=ref)
            sw.pack(side="right")
            return row

        def create_section(title, parent, key):
            import config
            prefs = config.load_prefs()
            expanded_sections = prefs.get("layout_settings_expanded_section", {})
            is_expanded = expanded_sections.get(key, False)

            section_frame = ttk.Frame(parent)
            section_frame.pack(fill="x", pady=(0, sc(10)))

            header_frame = ttk.Frame(section_frame)
            header_frame.pack(fill="x")

            content_frame = ttk.Frame(section_frame, padding=(sc(16), 0, 0, 0))
            if is_expanded:
                content_frame.pack(fill="x")

            arrow_var = tk.StringVar(value="▾" if is_expanded else "▸")
            arrow_lbl = tk.Label(header_frame, textvariable=arrow_var, font=("Segoe UI", sc(10)), bg=bg_color, fg="#444748" if not getattr(self, "dark_mode_active", False) else "#cdd6f4")
            arrow_lbl.pack(side="left", padx=(0, sc(4)))

            title_lbl = tk.Label(header_frame, text=title, font=("Hanken Grotesk", sc(10), "bold"), bg=bg_color, fg="#444748" if not getattr(self, "dark_mode_active", False) else "#cdd6f4")
            title_lbl.pack(side="left")

            def toggle_section(event=None):
                import config
                current_prefs = config.load_prefs()
                current_expanded = current_prefs.get("layout_settings_expanded_section", {})

                currently_expanded = (arrow_var.get() == "▾")
                new_expanded = not currently_expanded

                if new_expanded:
                    arrow_var.set("▾")
                    content_frame.pack(fill="x")
                else:
                    arrow_var.set("▸")
                    content_frame.pack_forget()

                current_expanded[key] = new_expanded
                current_prefs["layout_settings_expanded_section"] = current_expanded
                config.save_prefs(current_prefs)

            arrow_lbl.bind("<Button-1>", toggle_section)
            title_lbl.bind("<Button-1>", toggle_section)
            header_frame.bind("<Button-1>", toggle_section)

            return content_frame

        panels_content = create_section("Panels & Layout", scrollable_frame, "panels_and_layout")
        create_toggle_row(panels_content, "Object ID List (Left)", self.draft_show_list_var, command=on_switch_toggle, ui_ref=self)
        create_toggle_row(panels_content, "Searchbar", self.draft_show_search_var, command=on_switch_toggle, ui_ref=self)
        create_toggle_row(panels_content, "Registration Panel (Right)", self.draft_show_reg_var, command=on_switch_toggle, ui_ref=self)
        create_toggle_row(panels_content, "Images Panel (Middle Top)", self.draft_show_images_var, command=on_switch_toggle, ui_ref=self)
        create_toggle_row(panels_content, "Location Window Position: Left / Center", self.draft_location_in_center_var, command=on_switch_toggle, ui_ref=self)
        create_toggle_row(panels_content, "Image Zoom Tools", self.draft_show_image_tools_var, command=on_switch_toggle, ui_ref=self)
        create_toggle_row(panels_content, "Bulk Edit Button", self.draft_show_bulk_edit_var, command=on_switch_toggle, ui_ref=self)

        toolbar_content = create_section("Toolbar & Buttons", scrollable_frame, "toolbar_and_buttons")
        tb_grid = ttk.Frame(toolbar_content)
        tb_grid.pack(fill="x")
        tb_grid.columnconfigure(0, weight=1)
        tb_grid.columnconfigure(1, weight=1)

        for idx, (name, var) in enumerate(sorted(self.draft_toolbar_vars.items())):
            row = idx // 2
            col = idx % 2
            cell = ttk.Frame(tb_grid, padding=sc(2))
            cell.grid(row=row, column=col, sticky="ew")

            lbl = ttk.Label(cell, text=name)
            lbl.pack(side="left", anchor="w")
            sw = ToggleSwitch(cell, var, command=on_switch_toggle, ui_ref=self)
            sw.pack(side="right")

        behavior_content = create_section("Behavior", scrollable_frame, "behavior")
        create_toggle_row(behavior_content, "Focus Mode by default", self.draft_layout_focus_mode_var, command=on_switch_toggle, ui_ref=self)
        create_toggle_row(behavior_content, "Snap lock when focusing problems", self.draft_snap_lock_var, command=on_switch_toggle, ui_ref=self)
        create_toggle_row(behavior_content, "View images as stack by default", self.draft_image_stack_var, command=on_switch_toggle, ui_ref=self)
        create_toggle_row(behavior_content, "Embedded Session Dashboard", self.draft_dashboard_embedded_var, command=on_switch_toggle, ui_ref=self)

        appearance_content = create_section("Appearance", scrollable_frame, "appearance")
        create_toggle_row(appearance_content, "Large Mark as Reviewed Button", self.draft_large_reviewed_button_var, command=on_switch_toggle, ui_ref=self)

        return scroll_container


    def _build_layout_bottom_buttons(self, main_frame, win):
        btn_row = ttk.Frame(main_frame, padding=(0, 6, 0, 0))
        btn_row.pack(fill="x", side="bottom")

        def _close_layout_win():
            if hasattr(self, "_layout_canvas") and self._layout_canvas.winfo_exists():
                win.unbind_all("<MouseWheel>")
            win.destroy()

        win.protocol("WM_DELETE_WINDOW", _close_layout_win)

        def on_ok():
            self._on_apply_layout_settings()
            _close_layout_win()

        ttk.Button(btn_row, text="Cancel", command=_close_layout_win, width=10, style="Tool.TButton").pack(side="right", padx=4)
        ttk.Button(btn_row, text="OK", command=on_ok, width=10, style="Primary.TButton").pack(side="right", padx=4)

        apply_btn = ttk.Button(btn_row, text="Apply", command=self._on_apply_layout_settings, width=10, style="Primary.TButton")
        apply_btn.pack(side="right", padx=4)

        return btn_row, apply_btn, _close_layout_win

    def open_layout_settings(self):
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

        dyn_cb = ttk.Checkbutton(
            dyn_frame,
            text="Update dynamically",
            variable=self.layout_dynamic_update_var,
            command=toggle_dynamic_update
        )
        dyn_cb.pack(side="left")

        scroll_container = self._build_layout_options_section(main_frame, win, bg_color)

        btn_row, apply_btn, close_win = self._build_layout_bottom_buttons(main_frame, win)

        if self.layout_dynamic_update_var.get():
            apply_btn.config(state="disabled")
        else:
            apply_btn.config(state="normal")

        # Tutorial bindings
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

    def save_layout_as_dialog(self):
        from tkinter import simpledialog
        name = simpledialog.askstring("Save Layout", "Enter a name for this layout:")
        if not name:
            return
        self.save_layout_as(name)


    def save_layout_as(self, name):
        import config
        prefs = config.load_prefs()
        if "layouts" not in prefs:
            prefs["layouts"] = {"startup_default": None, "saved": {}}
        if "saved" not in prefs["layouts"]:
            prefs["layouts"]["saved"] = {}

        try:
            mid_sash = self.middle_panes.sashpos(0)
            if self.focus_mode_var.get() and hasattr(self, "_last_manual_middle_sash"):
                mid_sash = self._last_manual_middle_sash
        except Exception:
            mid_sash = 400

        try:
            main_sashes = [self.panes.sashpos(0), self.panes.sashpos(1)]
        except Exception:
            main_sashes = [300, 800]

        # Save toolbar button visibility
        tb_states = {k: v.get() for k, v in self.toolbar_vars.items()}

        layout = {
            "window_state": self.root.state(),
            "window_geometry": self.root.geometry(),
            "main_sashes": main_sashes,
            "middle_sash": mid_sash,
            "focus_problems": self.focus_mode_var.get(),
            "image_view_mode": getattr(self, "image_view_mode", "gallery"),
            "toolbar_buttons": tb_states,
            "show_list": self.show_list_var.get(),
            "show_search": self.show_search_var.get(),
            "show_images": self.show_images_var.get(),
            "location_in_center": self.location_in_center_var.get(),
            "show_image_tools": self.show_image_tools_var.get(),
            "show_bulk_edit": self.show_bulk_edit_var.get(),
            "show_reg": self.show_reg_var.get(),
            "snap_lock": self.snap_lock_var.get(),
            "image_stack": self.image_stack_var.get(),
            "dashboard_mode": self.dashboard_mode_var.get(),
            "large_reviewed_button": self.large_reviewed_button_var.get(),
            "active_filter": self.app.active_filter_dict.copy() if hasattr(self.app, 'active_filter_dict') else {}
        }

        prefs["layouts"]["saved"][name] = layout
        config.save_prefs(prefs)
        self._refresh_load_layout_menu()
        self.system_status.config(text=f"Layout '{name}' saved!")


    def set_current_as_startup_default(self):
        import config
        from tkinter import messagebox
        prefs = config.load_prefs()
        saved = prefs.get("layouts", {}).get("saved", {})
        if not saved:
            messagebox.showinfo("No Layouts", "Please save a layout first using 'Save Current Layout As...'")
            return

        self.save_layout_as("Startup Default")
        prefs = config.load_prefs()
        prefs["layouts"]["startup_default"] = "Startup Default"
        config.save_prefs(prefs)
        self.system_status.config(text="Startup default layout updated!")


    def apply_saved_layout(self, name="Default"):
        import config
        prefs = config.load_prefs()
        layout = prefs.get("layouts", {}).get("saved", {}).get(name)
        if not layout:
            # No saved layout — apply resolution-aware sash defaults
            def _set_default_sashes():
                try:
                    screen_w = self.root.winfo_screenwidth()
                    if screen_w < 1400:
                        left_w  = sc(240)
                        right_w = screen_w - sc(300)
                    else:
                        left_w  = sc(280)
                        right_w = screen_w - sc(360)
                    self.panes.sashpos(0, left_w)
                    self.panes.sashpos(1, right_w)
                except Exception:
                    pass
            self.root.after(100, _set_default_sashes)
            return

        if hasattr(self, "layout_quick_cb"):
            self.layout_quick_cb.set(name)

        state = layout.get("window_state", "normal")
        if state == "zoomed":
            self.root.state("zoomed")
        else:
            self.root.state("normal")
            geom = layout.get("window_geometry")
            if geom:
                self.root.geometry(geom)

        self.focus_mode_var.set(layout.get("focus_problems", False))
        self.snap_lock_var.set(layout.get("snap_lock", False))
        self.image_stack_var.set(layout.get("image_stack", False))
        self.dashboard_mode_var.set(layout.get("dashboard_mode", "Window"))
        self.show_list_var.set(layout.get("show_list", True))
        self.show_search_var.set(layout.get("show_search", True))
        self.show_images_var.set(layout.get("show_images", True))
        self.location_in_center_var.set(layout.get("location_in_center", False))
        self.show_image_tools_var.set(layout.get("show_image_tools", True))
        self.show_bulk_edit_var.set(layout.get("show_bulk_edit", True))
        self.show_reg_var.set(layout.get("show_reg", True))
        self.large_reviewed_button_var.set(layout.get("large_reviewed_button", True))
        self.update_reviewed_button_state()

        # Load toolbar button visibility
        tb_states = layout.get("toolbar_buttons", {})
        for name, state in tb_states.items():
            if name in self.toolbar_vars:
                self.toolbar_vars[name].set(state)
        self._toggle_toolbar_buttons()

        # Apply filters
        active_filter = layout.get("active_filter", {})
        if hasattr(self.app, 'active_filter_dict') and active_filter != self.app.active_filter_dict:
            self.app.active_filter_dict = active_filter
            if hasattr(self, '_apply_filter'):
                self._apply_filter()

        # Toggle panels
        self.toggle_list_panel()
        self.toggle_search_panel()
        self.toggle_location_panel()
        self.toggle_images_panel()
        self.toggle_reg_panel()
        self.toggle_image_tools()
        self.toggle_dashboard_mode()
        self.toggle_bulk_edit_btn()
        self.update_reg_fields_visibility()

        self.image_view_mode = layout.get("image_view_mode", "gallery")
        if self.image_stack_var.get():
            self.image_view_mode = "stack"

        if hasattr(self, "view_btn"):
            self.view_btn.config(text=f"View: {self.image_view_mode}")

        if "toolbar_buttons" in layout:
            for tb_name, val in layout["toolbar_buttons"].items():
                if tb_name in self.toolbar_vars:
                    self.toolbar_vars[tb_name].set(val)
            self._toggle_toolbar_buttons()

        def _set_sashes():
            try:
                sashes = layout.get("main_sashes", [])
                if len(sashes) == 2:
                    self.panes.sashpos(0, sashes[0])
                    self.panes.sashpos(1, sashes[1])
            except Exception:
                pass
            try:
                mid_sash = layout.get("middle_sash")
                if mid_sash:
                    self.middle_panes.sashpos(0, mid_sash)
            except Exception:
                pass

        self.root.after(50, _set_sashes)
        self.system_status.config(text=f"Applied layout: {name}")


    def reset_layout_to_factory(self):
        import config
        prefs = config.load_prefs()
        if "layouts" in prefs:
            del prefs["layouts"]
            config.save_prefs(prefs)
            self._refresh_load_layout_menu()
            self.system_status.config(text="Layout reset to factory. Restart app to see changes.")


    def toggle_dark_mode(self):
        self.dark_mode_active = not self.dark_mode_active
        self.apply_theme()

    def _ensure_theme_widgets_registered(self):
        if getattr(self, "_theme_widgets_registered", False):
            return
        
        self._theme_sb_top_widgets = []
        self._theme_sb_bottom_widgets = []
        self._theme_loc_vert_widgets = []
        self._theme_loc_horiz_widgets = []
        self._theme_loc_labels = []
        self._theme_loc_checkbuttons = []
        
        def collect_widgets(parent, lst):
            if not parent:
                return
            for child in parent.winfo_children():
                lst.append(child)
                collect_widgets(child, lst)
                
        if hasattr(self, "sb_top"):
            collect_widgets(self.sb_top, self._theme_sb_top_widgets)
        if hasattr(self, "sb_bottom"):
            collect_widgets(self.sb_bottom, self._theme_sb_bottom_widgets)
            
        if hasattr(self, "location_frame"):
            collect_widgets(self.location_frame, self._theme_loc_vert_widgets)
            for w in self._theme_loc_vert_widgets:
                if isinstance(w, tk.Label):
                    self._theme_loc_labels.append(w)
                elif isinstance(w, tk.Checkbutton):
                    self._theme_loc_checkbuttons.append(w)
                    
        if hasattr(self, "loc_frame_horizontal"):
            collect_widgets(self.loc_frame_horizontal, self._theme_loc_horiz_widgets)
            for w in self._theme_loc_horiz_widgets:
                if isinstance(w, tk.Label):
                    self._theme_loc_labels.append(w)
                elif isinstance(w, tk.Checkbutton):
                    self._theme_loc_checkbuttons.append(w)
                    
        self._theme_widgets_registered = True

    def apply_theme(self):
        import config
        self._ensure_theme_widgets_registered()
        style = ttk.Style(self.root)
        theme_name = config.get_theme()

        # Always use 'clam' as base — required for full border/color control on Windows.
        # Native themes (vista, xpnative) lock widget rendering and prevent Stitch styling.
        style.theme_use("clam")

        if self.dark_mode_active:
            bg_color = "#1e1e2e"
            fg_color = "#cdd6f4"
            field_bg = "#181825"
            select_bg = "#45475a"
            select_fg = "#cdd6f4"
            border_color = "#313244"
            nav_bg = "#181825"
            nav_active_fg = "#cdd6f4"
            statusbar_bg = "#181825"
            statusbar_fg = "#cdd6f4"
            reviewed_fg = "#a6e3a1"   # green (dark mode)
            problem_fg  = "#f38ba8"   # red (dark mode)

            style.configure(".", background=bg_color, foreground=fg_color, bordercolor=border_color)
            style.configure("TFrame", background=bg_color)
            style.configure("TLabel", background=bg_color, foreground=fg_color)
            style.configure("LeftPane.TFrame", background="#1e1e2e")
            style.configure("MiddlePane.TFrame", background="#181825")
            style.configure("RightPane.TFrame", background="#1e1e2e")
            style.configure("LeftPane.TLabel", background="#1e1e2e", foreground=fg_color)
            cb_opts = {
                "indicatorbackground": field_bg,
                "indicatorforeground": fg_color,
                "upperbordercolor": border_color,
                "lowerbordercolor": border_color
            }
            style.configure("LeftPane.TCheckbutton", background="#1e1e2e", foreground=fg_color, **cb_opts)
            style.map("LeftPane.TCheckbutton",
                      background=[("active", "#1e1e2e")],
                      indicatorbackground=[("pressed", bg_color), ("selected", select_bg)])
            style.configure("RightPane.TLabel", background="#1e1e2e", foreground=fg_color)
            style.configure("RightPane.TCheckbutton", background="#1e1e2e", foreground=fg_color, **cb_opts)
            style.map("RightPane.TCheckbutton",
                      background=[("active", "#1e1e2e")],
                      indicatorbackground=[("pressed", bg_color), ("selected", select_bg)])
            style.configure("MiddlePane.TLabel", background="#181825", foreground=fg_color)
            style.configure("TButton", background=field_bg, foreground=fg_color,
                            bordercolor=border_color, lightcolor=border_color, darkcolor=border_color,
                            relief="flat", borderwidth=1)
            style.map("TButton", background=[("active", select_bg), ("pressed", select_bg)])

            style.configure("Tool.TButton", font=("Segoe UI", sc(9)), padding=2,
                            background=field_bg, foreground=fg_color, bordercolor=border_color,
                            relief="flat", borderwidth=1)
            style.map("Tool.TButton", background=[("active", select_bg), ("pressed", select_bg)])

            # Stitch: Nav links — flat, no border, text-only appearance
            style.configure("Nav.TButton", font=("Segoe UI", sc(9), "bold"), padding=(8, 6),
                            background=nav_bg, foreground=nav_active_fg, relief="flat", borderwidth=0)
            style.map("Nav.TButton", background=[("active", select_bg)], foreground=[("active", select_fg)])

            # Stitch: Primary action button — solid filled background
            style.configure("Primary.TButton", font=("Segoe UI", sc(9), "bold"), padding=(10, 6),
                            background="#45475a", foreground=fg_color, relief="flat", borderwidth=1,
                            bordercolor=border_color)
            style.map("Primary.TButton", background=[("active", select_bg), ("pressed", "#585b70")])

            # Stitch: Section headers inside forms — bold uppercase label with bottom separator
            style.configure("SectionHeader.TLabel", font=("Segoe UI", sc(9), "bold"),
                            background=bg_color, foreground="#9399b2", padding=(0, 4))

            # Stitch: Status bar labels — monospace, dark background
            style.configure("StatusBar.TLabel", font=("Courier New", sc(9)),
                            background=statusbar_bg, foreground=statusbar_fg, padding=(4, 0))

            style.configure("TEntry", fieldbackground=field_bg, foreground=fg_color,
                            insertcolor=fg_color, bordercolor=border_color, relief="flat", borderwidth=1)
            style.map("TEntry", fieldbackground=[("readonly", field_bg)])

            style.configure("TCombobox", fieldbackground=field_bg, foreground=fg_color,
                            insertcolor=fg_color, bordercolor=border_color, arrowcolor=fg_color)
            style.map("TCombobox", fieldbackground=[("readonly", field_bg)],
                      selectbackground=[("readonly", select_bg)], selectforeground=[("readonly", select_fg)])

            style.configure("TCheckbutton", background=bg_color, foreground=fg_color, **cb_opts)
            style.map("TCheckbutton",
                      background=[("active", bg_color)],
                      indicatorbackground=[("pressed", bg_color), ("selected", select_bg)])

            style.configure("Treeview", background=field_bg, foreground=fg_color,
                            fieldbackground=field_bg, bordercolor=border_color, rowheight=28)
            style.map("Treeview", background=[("selected", select_bg)])

            self.object_list.tag_configure("odd", background="#181825")
            self.object_list.tag_configure("even", background="#1e1e2e")
            # Stitch row status tags
            self.object_list.tag_configure("reviewed", foreground=reviewed_fg)
            self.object_list.tag_configure("problem",  foreground=problem_fg)

            style.configure("Treeview.Heading", background=bg_color, foreground=fg_color, bordercolor=border_color)
            style.map("Treeview.Heading", background=[("active", select_bg)])

            style.configure("TNotebook", background=bg_color, bordercolor=border_color)
            style.configure("TNotebook.Tab", background=field_bg, foreground=fg_color, bordercolor=border_color)
            style.map("TNotebook.Tab", background=[("selected", bg_color)])

            # Get advanced settings for highlights
            advanced_prefs = config.load_prefs().get("advanced", {})
            enable_hl = advanced_prefs.get("enable_problem_highlights", True)
            hl_color_name = advanced_prefs.get("problem_highlight_color", "Default (Red)")
            
            if not enable_hl:
                problem_bg = "#181825"
                problem_fg = fg_color
            else:
                if "Yellow" in hl_color_name:
                    problem_bg = "#5f5b2e"
                    problem_fg = "#f9e2af"
                elif "Orange" in hl_color_name:
                    problem_bg = "#5f4520"
                    problem_fg = "#fab387"
                elif "Blue" in hl_color_name:
                    problem_bg = "#203a5f"
                    problem_fg = "#89b4fa"
                else:  # Default (Red)
                    problem_bg = "#5c1e1e"
                    problem_fg = "#f38ba8"

            style.configure("Problem.TEntry", fieldbackground=problem_bg, foreground=problem_fg)
            style.configure("Problem.TCombobox", fieldbackground=problem_bg, foreground=problem_fg)

            style.configure("Dirty.TButton", foreground="#f38ba8", background=field_bg)
            style.configure("HistoryHighlight.TLabel", background="#f9e2af", foreground="#1e1e2e",
                            font=("Segoe UI", sc(10), "bold"))
            style.configure("Highlight.TEntry", fieldbackground="#f9e2af", foreground="#1e1e2e")
            style.configure("Hover.TLabel", background="#313244")
            style.configure("Hover.TFrame", background="#313244")
            style.configure("Success.TEntry", fieldbackground="#a6e3a1", foreground="#1e1e2e")
            style.configure("Success.TCombobox", fieldbackground="#a6e3a1", foreground="#1e1e2e")

            self.status_badge_colors = {
                "saved":     {"bg": "#2e3f2f", "fg": "#a6e3a1"},
                "autosaved": {"bg": "#1e2e3e", "fg": "#89b4fa"},
                "unsaved":   {"bg": "#3e3f2f", "fg": "#f9e2af"},
                "error":     {"bg": "#3e1e1e", "fg": "#f38ba8"}
            }

            self.root.configure(background=bg_color)
            if hasattr(self, "title_problem_count_label"):
                self.title_problem_count_label.configure(bg="#181825")
            if hasattr(self, "image_canvas"):
                self.image_canvas.configure(background=field_bg, highlightbackground=border_color)
            if hasattr(self, "problem_canvas"):
                self.problem_canvas.configure(background=bg_color, highlightbackground=border_color)
            if getattr(self, "reg_canvas", None):
                self.reg_canvas.configure(background=bg_color, highlightbackground=border_color)
            if hasattr(self, "_status_bar_frame"):
                self._status_bar_frame.configure(bg=statusbar_bg)
            if hasattr(self, "sb_top"):
                self.sb_top.configure(bg=bg_color)
                for w in self._theme_sb_top_widgets:
                    if w.winfo_exists() and not w.winfo_class().startswith("T"):
                        try:
                            w.configure(bg=bg_color)
                        except Exception:
                            pass
            if hasattr(self, "sb_buttons_frame"):
                self.sb_buttons_frame.configure(bg=bg_color)
            if hasattr(self, "sb_bottom"):
                self.sb_bottom.configure(bg=statusbar_bg)
                for w in self._theme_sb_bottom_widgets:
                    if w.winfo_exists() and not w.winfo_class().startswith("T"):
                        try:
                            w.configure(bg=statusbar_bg)
                        except Exception:
                            pass
                for lbl in self._status_bar_labels.values():
                    lbl.configure(bg=statusbar_bg, fg=statusbar_fg)

            for w in self.reg_entries.values():
                if isinstance(w, (tk.Text, tk.Entry)):
                    w.configure(background=field_bg, foreground=fg_color,
                                insertbackground=fg_color, highlightbackground=border_color)

            if hasattr(self, "_inline_search_entry"):
                self.search_bar_frame.configure(bg=field_bg, highlightbackground=border_color)
                self._inline_search_entry.configure(bg=field_bg, fg=fg_color if self._inline_search_var.get() != self._inline_search_placeholder else "gray", insertbackground=fg_color)
                self.toolbar_buttons['X'].configure(bg=field_bg, fg=fg_color, activebackground=field_bg, activeforeground=reviewed_fg)
                self._search_count_label.configure(bg=field_bg, fg="gray")

            if hasattr(self, "dark_mode_btn"):
                self.dark_mode_btn.config(text="Light Mode")

        else:
            # --- Stitch light mode palette (ui_palette/DESIGN.md) ---
            bg_color    = "#f3f3f3"   # surface-container-low
            fg_color    = "#1a1c1c"   # on-surface
            field_bg    = "#ffffff"   # surface-container-lowest
            select_bg   = "#e2e2e2"   # surface-variant
            select_fg   = "#1a1c1c"
            border_color = "#c4c7c7"  # outline-variant
            nav_bg      = "#f9f9f9"   # surface
            primary_btn_bg  = "#000000"  # primary
            primary_btn_fg  = "#ffffff"  # on-primary
            statusbar_bg    = "#1c1b1b"  # primary-container (dark)
            statusbar_fg    = "#e2e2e2"  # on-primary-container
            reviewed_fg = "#3b6934"   # secondary (green) — reviewed rows
            problem_fg  = "#ba1a1a"   # error (red)       — problem rows

            style.configure(".", background=bg_color, foreground=fg_color,
                            bordercolor=border_color, lightcolor=border_color, darkcolor=border_color)
            style.configure("TFrame", background=bg_color)
            style.configure("TLabel", background=bg_color, foreground=fg_color)
            style.configure("LeftPane.TFrame", background="#f5f5f5")
            style.configure("MiddlePane.TFrame", background="#ffffff")
            style.configure("RightPane.TFrame", background="#f5f5f5")
            style.configure("LeftPane.TLabel", background="#f5f5f5", foreground=fg_color)
            cb_opts = {
                "indicatorbackground": field_bg,
                "indicatorforeground": fg_color,
                "upperbordercolor": border_color,
                "lowerbordercolor": border_color
            }
            style.configure("LeftPane.TCheckbutton", background="#f5f5f5", foreground=fg_color, **cb_opts)
            style.map("LeftPane.TCheckbutton",
                      background=[("active", "#f5f5f5")],
                      indicatorbackground=[("pressed", bg_color), ("selected", select_bg)])
            style.configure("RightPane.TLabel", background="#f5f5f5", foreground=fg_color)
            style.configure("RightPane.TCheckbutton", background="#f5f5f5", foreground=fg_color, **cb_opts)
            style.map("RightPane.TCheckbutton",
                      background=[("active", "#f5f5f5")],
                      indicatorbackground=[("pressed", bg_color), ("selected", select_bg)])
            style.configure("MiddlePane.TLabel", background="#ffffff", foreground=fg_color)
            style.configure("TButton", background="#e8e8e8", foreground=fg_color,
                            bordercolor=border_color, lightcolor="#e8e8e8", darkcolor="#c4c7c7",
                            relief="flat", borderwidth=1)
            style.map("TButton", background=[("active", select_bg), ("pressed", "#cccccc")])

            style.configure("Tool.TButton", font=("Segoe UI", sc(9)), padding=2,
                            background="#e8e8e8", foreground=fg_color, bordercolor=border_color,
                            relief="flat", borderwidth=1)
            style.map("Tool.TButton", background=[("active", select_bg), ("pressed", "#cccccc")])

            # Stitch: Nav links — flat, no border, text-only
            style.configure("Nav.TButton", font=("Segoe UI", sc(9), "bold"), padding=(8, 6),
                            background=nav_bg, foreground="#444748", relief="flat", borderwidth=0)
            style.map("Nav.TButton", background=[("active", select_bg)], foreground=[("active", fg_color)])

            # Stitch: Primary action button — solid black, white text
            style.configure("Primary.TButton", font=("Segoe UI", sc(9), "bold"), padding=(10, 6),
                            background=primary_btn_bg, foreground=primary_btn_fg,
                            relief="flat", borderwidth=1, bordercolor=primary_btn_bg)
            style.map("Primary.TButton",
                      background=[("active", "#333333"), ("pressed", "#555555")],
                      foreground=[("active", primary_btn_fg)])

            # Stitch: Section headers — bold uppercase, muted foreground, separated by bottom border
            style.configure("SectionHeader.TLabel",
                            font=("Segoe UI", sc(9), "bold"),
                            background="#f5f5f5", foreground="#444748", padding=(0, 4))

            # Stitch: Status bar labels — monospace, dark bar background
            style.configure("StatusBar.TLabel", font=("Courier New", sc(9)),
                            background=statusbar_bg, foreground=statusbar_fg, padding=(4, 0))

            style.configure("TEntry", fieldbackground=field_bg, foreground=fg_color,
                            insertcolor=fg_color, bordercolor=border_color, relief="flat", borderwidth=1)
            style.map("TEntry", fieldbackground=[("readonly", bg_color)])

            style.configure("TCombobox", fieldbackground=field_bg, foreground=fg_color,
                            insertcolor=fg_color, bordercolor=border_color, arrowcolor=fg_color)
            style.map("TCombobox", fieldbackground=[("readonly", bg_color)],
                      selectbackground=[("readonly", select_bg)], selectforeground=[("readonly", select_fg)])

            style.configure("TCheckbutton", background=bg_color, foreground=fg_color, **cb_opts)
            style.map("TCheckbutton",
                      background=[("active", bg_color)],
                      indicatorbackground=[("pressed", bg_color), ("selected", select_bg)])

            style.configure("Treeview", background=field_bg, foreground=fg_color,
                            fieldbackground=field_bg, bordercolor=border_color, rowheight=28)
            style.map("Treeview", background=[("selected", select_bg)])
            style.configure("Treeview.Heading", background="#e8e8e8", foreground=fg_color, bordercolor=border_color)
            style.map("Treeview.Heading", background=[("active", select_bg)])

            self.object_list.tag_configure("odd",  background="#f3f3f3")
            self.object_list.tag_configure("even", background="#ffffff")
            # Stitch row status tags — text color signals reviewed/problem state
            self.object_list.tag_configure("reviewed", foreground=reviewed_fg)
            self.object_list.tag_configure("problem",  foreground=problem_fg)

            style.configure("TNotebook", background=bg_color, bordercolor=border_color)
            style.configure("TNotebook.Tab", background="#e8e8e8", foreground=fg_color, bordercolor=border_color)
            style.map("TNotebook.Tab", background=[("selected", bg_color)])

            style.configure("Dirty.TButton", foreground="red", background="#e8e8e8")
            style.configure("HistoryHighlight.TLabel", background="#fff3a3", foreground="black",
                            font=("Segoe UI", sc(10), "bold"))
            style.configure("Highlight.TEntry", fieldbackground="#fff3a3", foreground="black")
            style.configure("Hover.TLabel", background="#eeeeee")
            style.configure("Hover.TFrame", background="#eeeeee")
            # Get advanced settings for highlights
            advanced_prefs = config.load_prefs().get("advanced", {})
            enable_hl = advanced_prefs.get("enable_problem_highlights", True)
            hl_color_name = advanced_prefs.get("problem_highlight_color", "Default (Red)")
            
            if not enable_hl:
                problem_bg = "#ffffff"
                problem_fg = fg_color
            else:
                if "Yellow" in hl_color_name:
                    problem_bg = "#fff9c4"
                    problem_fg = "#1a1c1c"
                elif "Orange" in hl_color_name:
                    problem_bg = "#ffe0b2"
                    problem_fg = "#1a1c1c"
                elif "Blue" in hl_color_name:
                    problem_bg = "#e3f2fd"
                    problem_fg = "#1a1c1c"
                else:  # Default (Red)
                    problem_bg = "#ffdad6"
                    problem_fg = "#ba1a1a"

            style.configure("Problem.TEntry", fieldbackground=problem_bg, foreground=problem_fg)
            style.configure("Problem.TCombobox", fieldbackground=problem_bg, foreground=problem_fg)

            self.status_badge_colors = {
                "saved":     {"bg": "#d4edda", "fg": "#155724"},
                "autosaved": {"bg": "#e2f0fe", "fg": "#0a58ca"},
                "unsaved":   {"bg": "#fff3cd", "fg": "#856404"},
                "error":     {"bg": "#f8d7da", "fg": "#721c24"}
            }

            self.root.configure(background=bg_color)
            if hasattr(self, "title_problem_count_label"):
                self.title_problem_count_label.configure(bg="#ffffff")

            if hasattr(self, "image_canvas"):
                self.image_canvas.configure(background="#f5f5f5", highlightbackground="#d0d0d0")
            if hasattr(self, "problem_canvas"):
                self.problem_canvas.configure(background=bg_color, highlightbackground="#d0d0d0")
            if getattr(self, "reg_canvas", None):
                self.reg_canvas.configure(background=bg_color, highlightbackground="#d0d0d0")
            if hasattr(self, "_status_bar_frame"):
                self._status_bar_frame.configure(bg=statusbar_bg)
            if hasattr(self, "sb_top"):
                self.sb_top.configure(bg=bg_color)
                for w in self._theme_sb_top_widgets:
                    if w.winfo_exists() and not w.winfo_class().startswith("T"):
                        try:
                            w.configure(bg=bg_color)
                        except Exception:
                            pass
            if hasattr(self, "sb_buttons_frame"):
                self.sb_buttons_frame.configure(bg=bg_color)
            if hasattr(self, "sb_bottom"):
                self.sb_bottom.configure(bg=statusbar_bg)
                for w in self._theme_sb_bottom_widgets:
                    if w.winfo_exists() and not w.winfo_class().startswith("T"):
                        try:
                            w.configure(bg=statusbar_bg)
                        except Exception:
                            pass
                for lbl in self._status_bar_labels.values():
                    lbl.configure(bg=statusbar_bg, fg=statusbar_fg)

            for w in self.reg_entries.values():
                if isinstance(w, (tk.Text, tk.Entry)):
                    w.configure(background="white", foreground="black",
                                insertbackground="black", highlightbackground="#d0d0d0")

            if hasattr(self, "_inline_search_entry"):
                self.search_bar_frame.configure(bg="white", highlightbackground="#d0d0d0")
                self._inline_search_entry.configure(bg="white", fg="black" if self._inline_search_var.get() != self._inline_search_placeholder else "gray", insertbackground="black")
                self.toolbar_buttons['X'].configure(bg="white", fg="black", activebackground="white", activeforeground="#ba1a1a")
                self._search_count_label.configure(bg="white", fg="gray")

            if hasattr(self, "dark_mode_btn"):
                self.dark_mode_btn.config(text="Dark Mode")

        # --- Update Location Widgets Theme dynamically ---
        loc_bg = "#1e1e2e" if self.dark_mode_active else "#f5f5f5"
        loc_horiz_bg = "#1e1e2e" if self.dark_mode_active else "#f3f3f3"
        lbl_fg = "#a6adc8" if self.dark_mode_active else "#444748"
        title_fg = "#cdd6f4" if self.dark_mode_active else "#1a1c1c"
        entry_bg = "#2a2b3c" if self.dark_mode_active else "#ffffff"
        entry_fg = "#cdd6f4" if self.dark_mode_active else "#000000"
        entry_insert = "#cdd6f4" if self.dark_mode_active else "#000000"
        border_col = "#313244" if self.dark_mode_active else "#c4c7c7"

        # Update vertical location background
        if hasattr(self, "location_frame") and self.location_frame.winfo_exists():
            self.location_frame.configure(bg=loc_bg)
            for w in self._theme_loc_vert_widgets:
                if w.winfo_exists() and not w.winfo_class().startswith("T"):
                    try:
                        w.configure(bg=loc_bg)
                    except Exception:
                        pass

        # Update horizontal location background
        if hasattr(self, "loc_frame_horizontal") and self.loc_frame_horizontal.winfo_exists():
            self.loc_frame_horizontal.configure(bg=loc_horiz_bg)
            for w in self._theme_loc_horiz_widgets:
                if w.winfo_exists() and not w.winfo_class().startswith("T"):
                    try:
                        w.configure(bg=loc_horiz_bg)
                    except Exception:
                        pass

        # Update labels foreground
        for w in self._theme_loc_labels:
            if w.winfo_exists():
                try:
                    if w.cget("text") == "LOCATION":
                        w.configure(fg=title_fg)
                    else:
                        w.configure(fg=lbl_fg)
                except Exception:
                    pass

        for w in self._theme_loc_checkbuttons:
            if w.winfo_exists():
                try:
                    w.configure(fg=entry_fg, activebackground=loc_bg, activeforeground=entry_fg, selectcolor=loc_bg)
                except Exception:
                    pass

        # Update entry widgets
        for w in getattr(self, "location_entries", []):
            if isinstance(w, tk.Entry) and w.winfo_exists():
                w.configure(background=entry_bg, foreground=entry_fg,
                            insertbackground=entry_insert, highlightbackground=border_col)

        if hasattr(self, "title_problem_count_label") and self.title_problem_count_label is not None:
            try:
                if self.title_problem_count_label.winfo_exists():
                    self.title_problem_count_label.configure(bg=bg_color)
            except Exception:
                pass

        self.update_dirty_ui()
