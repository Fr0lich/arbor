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
            btn = ttk.Button(parent, text=label, style="Nav.TButton", command=cmd, cursor="hand2")
            btn.pack(side="left", fill="y")
            app.toolbar_buttons[label] = btn
            app.toolbar_vars[label] = tk.BooleanVar(value=True)
            return btn

        # FILE — opens the file/open dialog
        btn_file = _nav_btn(nav_links_frame, "FILE ▾",     app.show_file_dropdown)
        app.add_tooltip(btn_file, "Database file options")

        # DATA — opens data menu
        btn_dat = _nav_btn(nav_links_frame, "DATA",   app.open_load_data_menu)
        app.add_tooltip(btn_dat, "Load historical databases")

        # IMAGES — jump to next problem
        btn_img = _nav_btn(nav_links_frame, "IMAGES ▾", app.show_images_dropdown)
        app.add_tooltip(btn_img, "Image source and view options")

        # CREATE — add new object or database
        btn_create = _nav_btn(nav_links_frame, "CREATE",   app.show_create_dropdown)
        app.add_tooltip(btn_create, "Create a new object or database")

        # HISTORY — recent objects popup
        btn_hist = _nav_btn(nav_links_frame, "RECENT",  app.open_recent_popup)
        app.add_tooltip(btn_hist, "View recently visited objects")

        # MOBILE — opens mobile companion dialog
        btn_mob = _nav_btn(nav_links_frame, "📱 MOBILE", app.open_mobile_dialog)
        app.add_tooltip(btn_mob, "Connect your phone to review & edit records remotely")

        # 1px separator before secondary controls
        tk.Frame(nav_bar, bg=nav_border, width=1).pack(side="left", fill="y", pady=8)

        # --- Secondary toolbar controls (kept for feature compatibility) ---
        secondary_frame = ttk.Frame(nav_bar)
        secondary_frame.pack(side="left", fill="y", padx=4)

        app.toolbar_buttons['Prev'] = ttk.Button(
            secondary_frame, text="◄", style="Nav.TButton",
            command=lambda: app.navigate_object(-1), cursor="hand2")
        app.toolbar_buttons['Prev'].pack(side="left", padx=1)
        app.add_tooltip(app.toolbar_buttons['Prev'], "Previous in list")

        app.toolbar_buttons['Next'] = ttk.Button(
            secondary_frame, text="►", style="Nav.TButton",
            command=lambda: app.navigate_object(1), cursor="hand2")
        app.toolbar_buttons['Next'].pack(side="left", padx=1)
        app.add_tooltip(app.toolbar_buttons['Next'], "Next in list")

        app.toolbar_buttons['Last'] = ttk.Button(
            secondary_frame, text="Last", style="Nav.TButton",
            command=app.goto_last_object, cursor="hand2")
        app.toolbar_buttons['Last'].pack(side="left", padx=2)
        app.add_tooltip(app.toolbar_buttons['Last'], "Return to last visited object")

        tk.Frame(secondary_frame, bg=nav_border, width=1).pack(side="left", fill="y", pady=6)

        app.toolbar_buttons['Next Problem'] = ttk.Button(
            secondary_frame, text="⚠ Next Problem", style="Primary.TButton",
            command=app.goto_next_problem, cursor="hand2")
        app.toolbar_buttons['Next Problem'].pack(side="left", padx=(4, 1))
        app.add_tooltip(app.toolbar_buttons['Next Problem'], "Jump to next problem")

        app.next_history_btn = ttk.Button(
            secondary_frame, text="Next+Hist", style="Primary.TButton",
            command=app.goto_next_problem_with_history, state="disabled", cursor="hand2")
        app.next_history_btn.pack(side="left", padx=1)
        app.toolbar_buttons['Next+Hist'] = app.next_history_btn
        app.add_tooltip(app.next_history_btn, "Jump to next object with suggestions")

        tk.Frame(secondary_frame, bg=nav_border, width=1).pack(side="left", fill="y", pady=6)

        app.show_all_history_var = tk.BooleanVar(value=False)

        # --- Right side: status indicators ---
        status_container = ttk.Frame(nav_bar)
        status_container.pack(side="right", fill="y", padx=(0, 16))

        # Online status dot + label
        status_dot_frame = ttk.Frame(status_container)
        status_dot_frame.pack(anchor="center", side="right")
        app._online_dot = tk.Canvas(status_dot_frame, width=8, height=8,
                                     highlightthickness=0, bg=nav_bar_bg)
        app._online_dot.create_oval(1, 1, 7, 7, fill="#3a7d44", outline="")
        app._online_dot.pack(side="left", padx=(0, 4))
        tk.Label(status_dot_frame, text="STATUS: ONLINE", bg=nav_bar_bg,
                 fg="#444748", font=("Courier New", sc(9))).pack(side="left")

        # Data status badge (saved / unsaved)
        app.data_status = tk.Label(
            status_container,
            anchor="e",
            bg=nav_bar_bg,
            font=("Segoe UI", sc(9), "bold")
        )
        app.data_status.pack(side="right", padx=(0, 8))

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
