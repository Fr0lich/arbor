import tkinter as tk
from tkinter import ttk
from config import sc

class FilterPanel:
    @staticmethod
    def build_filter_ui(app, left_content_frame):
        app.filter_status_label = ttk.Label(
            left_content_frame,
            text="",
            foreground="#c0392b",
            font=("Segoe UI", sc(8), "bold")
        )
        app.filter_status_label.pack(fill="x", padx=6, pady=(0, 2))

        sort_frame = ttk.Frame(left_content_frame)
        sort_frame.pack(fill="x", padx=4, pady=(0, 2))

        app.sort_var = tk.StringVar(value="ID")

        sort_cb = ttk.Combobox(
            sort_frame, cursor="hand2",
            textvariable=app.sort_var,
            values=["ID", "Genus A-Z", "Reviewed first", "Problems first"],
            state="readonly",
            width=16
        )
        sort_cb.pack(side="left", padx=(4, 0))

        sort_cb.bind(
            "<<ComboboxSelected>>",
            lambda e: app._sort_object_list(app.sort_var.get())
        )

        # Create app.left_panes vertical paned window
        app.left_panes = ttk.Panedwindow(left_content_frame, orient="vertical")
        app.left_panes.pack(fill="both", expand=True)

        # Bottom container in left column for Location, Settings, and Help
        app.left_bottom_container = ttk.Frame(app.left_panes, style="LeftPane.TFrame")

        app.left_bottom_sep = ttk.Separator(app.left_bottom_container, orient="horizontal")
        app.left_bottom_sep.pack(fill="x", side="top")

        # --- Location container (relocated here) ---
        loc_container = ttk.Frame(app.left_bottom_container, padding=(8, 6), style="LeftPane.TFrame")
        app.loc_container = loc_container
        loc_container.pack(side="top", fill="x")

        loc_box = ttk.Frame(loc_container, style="LeftPane.TFrame")
        loc_box.pack(fill="both", expand=True)
        app.location_frame = loc_box

        # Settings and Help buttons relocated to status bar sb_top.


        # LIST container
        # Note: the list_container passed should probably be created outside or inside.
        # Looking at original code, list_container is created right here:
        list_container = ttk.Frame(app.left_panes, style="LeftPane.TFrame")
        app.left_panes.add(list_container, weight=1)
        app.left_panes.add(app.left_bottom_container, weight=0)

        # ---------- FILTER ----------
        app.toolbar_buttons['Filter'] = ttk.Button(sort_frame, text="Filter", style="Nav.TButton", command=app.open_filter_menu, cursor="hand2")
        app.toolbar_buttons['Filter'].pack(side="left", padx=(4, 0))
        app.filter_btn = app.toolbar_buttons['Filter']
        app.add_tooltip(app.toolbar_buttons['Filter'], "Ctrl+G")

        app.sync_filter_btn = ttk.Button(sort_frame, text="📱 Sync to Mobile", style="Nav.TButton", command=app.push_filter_to_mobile, cursor="hand2")
        app.sync_filter_btn.pack(side="left", padx=(4, 0))
        app.add_tooltip(app.sync_filter_btn, "Push working batch filter to mobile session")
        app.sync_filter_btn.config(state="disabled")

        app.search_count_label = None




        # --- Sleek Integrated Search Bar ---
        search_container = tk.Frame(
            list_container,
            bg="#ffffff",
            highlightthickness=1,
            highlightbackground="#d1d1d1"
        )
        app.search_bar_frame = search_container
        app.search_bar_frame.tutorial_id = "search_entry"
        search_container.pack(fill="x", padx=0, pady=(0, sc(6)))

        app._inline_search_var = tk.StringVar()
        app._inline_search_placeholder = "Search ID, Genus, Species..."
        app._last_search_query = app._inline_search_placeholder
        app._inline_search_entry = tk.Entry(
            search_container,
            textvariable=app._inline_search_var,
            font=("Hanken Grotesk", sc(10)),
            bg="#ffffff", fg="#2c302e",
            relief="flat", bd=0,
            insertbackground="#000000"
        )
        app._inline_search_entry.pack(side="left", fill="x", expand=True, padx=(sc(8), sc(4)), pady=sc(5))
        app._inline_search_entry.bind("<KeyRelease>",  app._on_inline_search_key)
        app._inline_search_entry.bind("<Escape>",      app._clear_inline_search)
        app._inline_search_entry.bind("<FocusIn>",     app._search_focus_in)
        app._inline_search_entry.bind("<FocusOut>",    app._search_focus_out)
        app._inline_search_entry.bind("<Button-1>",    app._search_focus_in)
        app._inline_search_entry.bind("<Return>",      app._on_search_bar_enter)
        app._inline_search_entry.bind("<Down>",        app._on_search_arrow_down)
        app._inline_search_entry.bind("<Up>",          app._on_search_arrow_up)

        def _focus_list(event):
            app.object_list.focus_set()
            if not app.object_list.selection():
                children = app.object_list.get_children()
                if children:
                    app.object_list.selection_set(children[0])
            return "break"
        app._inline_search_entry.bind("<Tab>", _focus_list)

        # Placeholder setup
        app._inline_search_entry.insert(0, app._inline_search_placeholder)
        app._inline_search_entry.config(foreground="gray")

        # Flat integrated clear button
        app.toolbar_buttons['X'] = tk.Button(
            search_container,
            text="✕",
            font=("Hanken Grotesk", sc(9.5), "bold"),
            bg="#ffffff", fg="gray",
            activebackground="#ffffff", activeforeground="#c93a40",
            relief="flat", bd=0, cursor="hand2",
            command=app._clear_inline_search
        )
        app.toolbar_buttons['X'].pack(side="right", padx=(sc(4), sc(8)), pady=sc(4))
        app.add_tooltip(app.toolbar_buttons['X'], "Clear Search (resets filter)")

        # Result count label embedded inside
        app._search_count_label = tk.Label(
            search_container,
            text="",
            font=("JetBrains Mono", sc(9)),
            bg="#ffffff", fg="gray"
        )
        app._search_count_label.pack(side="right", padx=(sc(4), 0), pady=sc(4))

        return list_container
