import tkinter as tk
from tkinter import ttk

class NavigationBar:
    @staticmethod
    def build_nav_ui(app, parent_frame):
        from config import sc
        from ui.main_window import LabelWrapper

        # ----------------------------------------------------------------
        # LAYER 2: Stitch Top Navigation Bar
        # Replaces the old 2-row raw-grid toolbar.
        # Structure: [TITLE] [FILE|DATA|PROBLEMS|CREATE|HISTORY] ... [STATUS]
        # ----------------------------------------------------------------
        nav_bar_bg = "#e9ece5"
        nav_border = "#8b948d"

        nav_bar = tk.Frame(parent_frame, bg=nav_bar_bg, height=48,
                           highlightthickness=1, highlightbackground=nav_border,
                           highlightcolor=nav_border)
        nav_bar.pack(fill="x", side="top")
        nav_bar.pack_propagate(False)
        app.nav_bar = nav_bar
        app.nav_separators = []

        # App title
        app.nav_title_lbl = tk.Label(
            nav_bar,
            text="arbor",
            bg=nav_bar_bg,
            fg="#000000",
            font=("Segoe UI", sc(12), "bold"),
            padx=16
        )
        app.nav_title_lbl.pack(side="left", anchor="center")

        # 1px vertical separator after title
        sep1 = tk.Frame(nav_bar, bg=nav_border, width=1)
        sep1.pack(side="left", fill="y", pady=8)
        app.nav_separators.append(sep1)

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
            btn = ttk.Button(parent, text=label, style="Nav.TButton", command=cmd, cursor="hand2")
            btn.pack(side="left", fill="y")
            app.toolbar_buttons[label] = btn
            app.toolbar_vars[label] = tk.BooleanVar(value=True)
            return btn
        # FILE — database & session operations
        btn_file = _nav_btn(nav_links_frame, "FILE ▾", app.show_file_dropdown)
        app.add_tooltip(btn_file, "Database file options, export & backups")

        # SPECIMEN — specimen records & verification
        btn_spec = _nav_btn(nav_links_frame, "SPECIMEN ▾", app.show_specimen_dropdown)
        app.add_tooltip(btn_spec, "Specimen accession options (New, Duplicate, Delete, Review)")
        app.toolbar_buttons["CREATE"] = btn_spec

        # AUDIT & TOOLS — GBIF, Problem Queue, Historical Books, Statistics, Bulk Edit
        btn_tools = _nav_btn(nav_links_frame, "🌿 AUDIT & TOOLS ▾", app.show_audit_tools_dropdown)
        app.add_tooltip(btn_tools, "Taxonomy validation, problem queue & historical tools")
        app.toolbar_buttons["DATA"] = btn_tools
        app.toolbar_buttons["🌿 GBIF ▾"] = btn_tools

        # VIEW — Image display, rotation & panel visibility (Focus mode omitted)
        btn_view = _nav_btn(nav_links_frame, "VIEW ▾", app.show_view_dropdown)
        app.add_tooltip(btn_view, "Image viewport, rotation & workspace panels")
        app.toolbar_buttons["IMAGES ▾"] = btn_view

        # MOBILE — opens mobile companion dialog
        btn_mob = _nav_btn(nav_links_frame, "📱 MOBILE", app.open_mobile_dialog)
        app.add_tooltip(btn_mob, "Connect your phone to review & edit records remotely")

        # SETTINGS — opens unified settings
        btn_settings = _nav_btn(nav_links_frame, "⚙ SETTINGS", lambda: app._open_unified("general"))
        app.add_tooltip(btn_settings, "Application preferences & database profiles")
        app.toolbar_buttons["SETTINGS"] = btn_settings

        # HELP — documentation & tutorials
        btn_help = _nav_btn(nav_links_frame, "❓ HELP ▾", app.show_help_dropdown)
        app.add_tooltip(btn_help, "User guide, shortcuts HUD, and interactive tutorials")
        app.toolbar_buttons["HELP"] = btn_help

        # 1px separator before secondary controls
        sep2 = tk.Frame(nav_bar, bg=nav_border, width=1)
        app.nav_separators.append(sep2)
        app.secondary_nav_sep = sep2

        # --- Secondary toolbar controls (segmented button clusters) ---
        secondary_frame = ttk.Frame(nav_bar)
        app.secondary_nav_frame = secondary_frame

        # Segment 1: Directional navigation cluster
        nav_grp = ttk.Frame(secondary_frame)
        nav_grp.pack(side="left", fill="y", padx=(1, 3))

        app.toolbar_buttons['Prev'] = ttk.Button(
            nav_grp, text="◄", style="Nav.TButton",
            command=lambda: app.navigate_object(-1), cursor="hand2")
        app.toolbar_buttons['Prev'].pack(side="left", padx=1)
        app.add_tooltip(app.toolbar_buttons['Prev'], "Previous in list (Left Arrow)")

        app.toolbar_buttons['Next'] = ttk.Button(
            nav_grp, text="►", style="Nav.TButton",
            command=lambda: app.navigate_object(1), cursor="hand2")
        app.toolbar_buttons['Next'].pack(side="left", padx=1)
        app.add_tooltip(app.toolbar_buttons['Next'], "Next in list (Right Arrow)")

        app.toolbar_buttons['Last'] = ttk.Button(
            nav_grp, text="Last", style="Nav.TButton",
            command=app.goto_last_object, cursor="hand2")
        app.toolbar_buttons['Last'].pack(side="left", padx=1)
        app.add_tooltip(app.toolbar_buttons['Last'], "Return to last visited object")

        sep_mid = tk.Frame(secondary_frame, bg=nav_border, width=1)
        sep_mid.pack(side="left", fill="y", pady=6, padx=3)
        app.nav_separators.append(sep_mid)

        # Segment 2: Problem jump cluster
        prob_grp = ttk.Frame(secondary_frame)
        prob_grp.pack(side="left", fill="y", padx=(2, 2))

        app.toolbar_buttons['Next Problem'] = ttk.Button(
            prob_grp, text="⚠ Next Problem", style="Primary.TButton",
            command=app.goto_next_problem, cursor="hand2")
        app.toolbar_buttons['Next Problem'].pack(side="left", padx=1)
        app.add_tooltip(app.toolbar_buttons['Next Problem'], "Jump to next problem")

        app.next_history_btn = ttk.Button(
            prob_grp, text="Next+Hist", style="Primary.TButton",
            command=app.goto_next_problem_with_history, state="disabled", cursor="hand2")
        app.next_history_btn.pack(side="left", padx=1)
        app.toolbar_buttons['Next+Hist'] = app.next_history_btn
        app.add_tooltip(app.next_history_btn, "Jump to next object with suggestions")

        # Load preference: default to False (hidden)
        import config as cfg
        p = cfg.load_prefs() or {}
        show_sec = bool(p.get("show_secondary_nav", False))
        app.show_secondary_nav_var = tk.BooleanVar(value=show_sec)

        def _apply_secondary_nav(show=None):
            val = app.show_secondary_nav_var.get() if show is None else bool(show)
            app.show_secondary_nav_var.set(val)
            if val:
                if sep2.winfo_manager() != "pack":
                    sep2.pack(side="left", fill="y", pady=8)
                if secondary_frame.winfo_manager() != "pack":
                    secondary_frame.pack(side="left", fill="y", padx=4)
            else:
                if secondary_frame.winfo_manager() == "pack":
                    secondary_frame.pack_forget()
                if sep2.winfo_manager() == "pack":
                    sep2.pack_forget()

        app.apply_secondary_nav_visibility = _apply_secondary_nav
        if show_sec:
            sep2.pack(side="left", fill="y", pady=8)
            secondary_frame.pack(side="left", fill="y", padx=4)

        app.show_all_history_var = tk.BooleanVar(value=False)

        # --- Right side: status indicators ---
        status_container = ttk.Frame(nav_bar)
        status_container.pack(side="right", fill="y", padx=(0, sc(16)))
        app.status_container = status_container
        app._online_dot = None  # Deprecated fake indicator removed

        # Data status badge (saved / unsaved)
        app.data_status = tk.Label(
            status_container,
            anchor="e",
            bg=nav_bar_bg,
            font=("Segoe UI", sc(9), "bold")
        )
        app.data_status.pack(side="right", padx=(0, sc(8)))

        # System status (loading messages etc.)
        real_system_status = ttk.Label(
            status_container,
            anchor="e",
            foreground="#444748"
        )
        real_system_status.pack(side="right", padx=(0, 4))
        app.system_status = LabelWrapper(real_system_status, app)

        # Object count label now lives in the sort_frame (left panel), near Filter button.
        # A placeholder is created here so update_object_count() doesn't fail before build_ui finishes.
        app.search_count_label = ttk.Label(
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
        from ui.main_window import ProgressbarWrapper
        app.image_scan_progress = ProgressbarWrapper(real_image_scan_progress, app)
