import tkinter as tk
from tkinter import ttk
import utils

class LogViewerMixin:
    def open_log_viewer_window(self):
        """Backward compatibility wrapper for legacy callers."""
        self.open_recent_activity_window(default_tab=1)

    def open_recent_activity_window(self, default_tab=0):
        """
        Opens a unified Recent Activity window containing:
          - Tab 1: Recently Visited Objects (with Object ID & Specimen Title)
          - Tab 2: Recent Edits Log (Time, Action, Object ID, Changes)
        
        Designed based on Stitch UI styling matching the 'Filter objects' dialog.
        Dimensions scale dynamically based on display resolution to support laptop screens.
        Selecting/double-clicking records triggers navigation in the main workspace and auto-closes.
        """
        # If window is already open, raise/focus and select the appropriate tab
        if hasattr(self, "recent_act_win") and self.recent_act_win and self.recent_act_win.winfo_exists():
            self.recent_act_win.lift()
            self.recent_act_win.focus_force()
            if hasattr(self, "_select_activity_tab"):
                self._select_activity_tab(default_tab)
            return

        from config import sc
        import utils

        is_dark = getattr(self, "dark_mode_active", False)
        COLORS = {
            "surface": "#1e1e2e" if is_dark else "#f9f9f9",
            "surface_dim": "#181825" if is_dark else "#dadada",
            "surface_container_low": "#181825" if is_dark else "#f3f3f3",
            "surface_container_highest": "#313244" if is_dark else "#e2e2e2",
            "on_surface": "#cdd6f4" if is_dark else "#1a1c1c",
            "on_surface_variant": "#bac2de" if is_dark else "#444748",
            "outline": "#45475a" if is_dark else "#747878",
            "outline_variant": "#585b70" if is_dark else "#c4c7c7",
            "primary": "#cdd6f4" if is_dark else "#000000",
            "on_primary": "#1e1e2e" if is_dark else "#ffffff",
            "secondary": "#a6e3a1" if is_dark else "#3b6934",
            "error": "#f38ba8" if is_dark else "#ba1a1a",
            "botanical_green": "#a6e3a1" if is_dark else "#3e7b3e",
            "search_orange": "#fab387" if is_dark else "#d9480f",
            "surface_tint": "#cdd6f4" if is_dark else "#5f5e5e"
        }

        # Local fonts styled according to Stitch/Filter specs
        FONT_HEADLINE = ("Hanken Grotesk", sc(14), "bold")
        FONT_LABEL = ("JetBrains Mono", sc(10), "bold")
        FONT_DATA = ("JetBrains Mono", sc(11))
        FONT_TEXT = ("Inter", sc(11))

        # Main window setup
        win = tk.Toplevel(self.root)
        self.recent_act_win = win
        win.title("Recent Activity")
        win.configure(bg=COLORS["surface"])
        win.bind("<Destroy>", lambda e: setattr(self, "recent_act_win", None) if e.widget == win else None)
        win.bind("<Escape>", lambda e: win.destroy())

        # Determine dynamic size based on screen size (50% screen width, 55% screen height)
        # Bounded by a minimum of 800 x 480 (scaled) to ensure proper readability of columns.
        screen_w = self.root.winfo_screenwidth()
        screen_h = self.root.winfo_screenheight()
        width = max(sc(800), int(screen_w * 0.5))
        height = max(sc(480), int(screen_h * 0.55))
        utils.center_and_fit_toplevel(win, width, height)

        main_container = tk.Frame(win, bg=COLORS["surface"], bd=0, highlightthickness=0)
        main_container.pack(fill="both", expand=True)

        # 1. Header Frame (Filter-styled)
        header = tk.Frame(main_container, bg=COLORS["surface_container_low"], height=sc(56))
        header.pack(fill="x", side="top")
        header.pack_propagate(False)
        tk.Frame(header, bg=COLORS["outline"], height=1).pack(fill="x", side="bottom")

        left_header = tk.Frame(header, bg=COLORS["surface_container_low"])
        left_header.pack(side="left", fill="y", padx=sc(16))

        tk.Label(left_header, text="Recent Activity", font=FONT_HEADLINE, fg=COLORS["primary"], bg=COLORS["surface_container_low"]).pack(side="left")

        btn_refresh = tk.Button(
            left_header, text="↻ Refresh", font=FONT_TEXT,
            bg=COLORS["surface_container_low"], fg=COLORS["primary"],
            activebackground=COLORS["surface_container_highest"],
            activeforeground=COLORS["primary"],
            bd=0, cursor="hand2", padx=sc(8), pady=sc(2),
            command=lambda: populate_activity_data()
        )
        btn_refresh.pack(side="left", padx=(sc(16), 0))

        lbl_desc = tk.Label(header, text="Track recently visited or edited objects", font=FONT_TEXT, fg=COLORS["on_surface_variant"], bg=COLORS["surface_container_low"])
        lbl_desc.pack(side="right", padx=sc(16), pady=sc(16))

        # 2. Custom Tabs Bar (Filter-styled)
        tab_nav = tk.Frame(main_container, bg=COLORS["surface_container_highest"], height=sc(40))
        tab_nav.pack(fill="x", side="top")
        tk.Frame(tab_nav, bg=COLORS["outline"], height=1).pack(fill="x", side="bottom")

        tab_content_area = tk.Frame(main_container, bg=COLORS["surface"])
        tab_content_area.pack(fill="both", expand=True)

        self.activity_tabs = {}
        self.activity_tab_buttons = {}

        def show_tab(tab_name):
            for name, frame in self.activity_tabs.items():
                frame.pack_forget()
            self.activity_tabs[tab_name].pack(fill="both", expand=True)
            
            for name, btn_tuple in self.activity_tab_buttons.items():
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
            self.activity_tab_buttons[name] = (btn, bottom_border)

        create_tab_btn("visited", "Visited Objects")
        create_tab_btn("edits", "Recent Edits")

        # Tab 1: Visited Objects Frame
        frame_visited = tk.Frame(tab_content_area, bg=COLORS["surface"])
        self.activity_tabs["visited"] = frame_visited

        tree_frame_v = ttk.Frame(frame_visited)
        tree_frame_v.pack(fill="both", expand=True, padx=sc(10), pady=(sc(10), 0))

        scroll_y_v = ttk.Scrollbar(tree_frame_v, orient="vertical")
        scroll_y_v.pack(side="right", fill="y")

        tree_v = ttk.Treeview(tree_frame_v, columns=("ObjectID", "Specimen"), show="headings", yscrollcommand=scroll_y_v.set)
        tree_v.heading("ObjectID", text="Object ID")
        tree_v.heading("Specimen", text="Specimen")

        tree_v.column("ObjectID", width=sc(150), minwidth=sc(100))
        tree_v.column("Specimen", width=sc(550), minwidth=sc(200), stretch=True)

        tree_v.pack(side="left", fill="both", expand=True)
        scroll_y_v.config(command=tree_v.yview)

        # Tab 2: Recent Edits Frame
        frame_edits = tk.Frame(tab_content_area, bg=COLORS["surface"])
        self.activity_tabs["edits"] = frame_edits

        tree_frame_e = ttk.Frame(frame_edits)
        tree_frame_e.pack(fill="both", expand=True, padx=sc(10), pady=(sc(10), 0))

        scroll_y_e = ttk.Scrollbar(tree_frame_e, orient="vertical")
        scroll_y_e.pack(side="right", fill="y")

        tree_e = ttk.Treeview(tree_frame_e, columns=("ObjectID", "Time", "Action", "Changes"), show="headings", yscrollcommand=scroll_y_e.set)
        tree_e.heading("ObjectID", text="Object ID")
        tree_e.heading("Time", text="Time")
        tree_e.heading("Action", text="Action")
        tree_e.heading("Changes", text="Changes")

        tree_e.column("ObjectID", width=sc(100), minwidth=sc(60))
        tree_e.column("Time", width=sc(140), minwidth=sc(100))
        tree_e.column("Action", width=sc(130), minwidth=sc(60))
        tree_e.column("Changes", width=sc(410), minwidth=sc(200), stretch=True)

        tree_e.pack(side="left", fill="both", expand=True)
        scroll_y_e.config(command=tree_e.yview)

        def populate_activity_data():
            # Clear existing items
            tree_v.delete(*tree_v.get_children())
            tree_e.delete(*tree_e.get_children())

            # Populate Visited
            recent_visited = []
            if hasattr(self, "history_stack") and self.history_stack:
                recent_visited = list(reversed(self.history_stack[-20:]))
                for oid in recent_visited:
                    title = self.object_title(oid)
                    tree_v.insert("", "end", values=(oid, title))

            # Populate Edits
            df_log = getattr(self.app, "df_log", None)
            if df_log is not None and not df_log.empty:
                cols = df_log.columns
                for row in reversed(list(df_log.itertuples(index=False, name=None))):
                    row_dict = dict(zip(cols, row))
                    tstamp = row_dict.get("Timestamp", "")
                    if "T" in str(tstamp):
                        try:
                            tstamp = str(tstamp).split('.')[0].replace("T", " ")
                        except Exception:
                            pass
                    action = row_dict.get("Action", "")
                    
                    # Map technical action names to user-friendly display labels
                    display_action = action
                    if action == "EDIT":
                        display_action = "Manual Edit"
                    elif action == "RESOLVE_HISTORICAL_CONFLICT":
                        display_action = "Conflict Resolver"
                    elif action == "CREATE_OBJECT_FAST":
                        display_action = "Created Object"

                    obj_id = row_dict.get("ObjectID", "")
                    c_fields = row_dict.get("ChangedFields", "")
                    c_vals = row_dict.get("ChangedValues", "")
                    p_fields = row_dict.get("ProblemsChanged", "")
                    p_vals = row_dict.get("ProblemsChangedValues", "")
                    l_fields = row_dict.get("LocationChanged", "")
                    l_vals = row_dict.get("LocationChangedValues", "")

                    changes_parts = []
                    if c_fields and str(c_fields).strip() and str(c_fields) != "(no changes)":
                        val_str = str(c_vals).strip()
                        if val_str:
                            parts = []
                            for p in val_str.split(" | "):
                                if "  " in p:
                                    p = p.replace("  ", " → ")
                                parts.append(p)
                            val_str = ", ".join(parts)
                            changes_parts.append(f"Data: {val_str}")
                        else:
                            changes_parts.append(f"Data: {c_fields}")

                    if p_fields and str(p_fields).strip():
                        val_str = str(p_vals).strip()
                        if val_str:
                            parts = []
                            for p in val_str.split(" | "):
                                if "  " in p:
                                    p = p.replace("  ", " → ")
                                parts.append(p)
                            val_str = ", ".join(parts)
                            changes_parts.append(f"Problems: {val_str}")
                        else:
                            changes_parts.append(f"Problems: {p_fields}")

                    if l_fields and str(l_fields).strip():
                        val_str = str(l_vals).strip()
                        if val_str:
                            parts = []
                            for p in val_str.split(" | "):
                                if "  " in p:
                                    p = p.replace("  ", " → ")
                                parts.append(p)
                            val_str = ", ".join(parts)
                            changes_parts.append(f"Location: {val_str}")
                        else:
                            changes_parts.append(f"Location: {l_fields}")

                    changes = " | ".join(changes_parts)
                    if not changes and c_fields == "(no changes)":
                        changes = "(no changes)"

                    tree_e.insert("", "end", values=(obj_id, tstamp, display_action, changes))
            
            # Reset button state
            try:
                update_btn_state()
            except Exception:
                pass

        # Populate initially on show
        populate_activity_data()

        # Helper functions to fetch selected ObjectID across tabs
        def get_selected_oid():
            active_tab = None
            for name, frame in self.activity_tabs.items():
                if frame.winfo_viewable():
                    active_tab = name
                    break
            
            if active_tab == "visited":
                sel = tree_v.selection()
                if sel:
                    return tree_v.item(sel[0])["values"][0]
            elif active_tab == "edits":
                sel = tree_e.selection()
                if sel:
                    return tree_e.item(sel[0])["values"][0]
            return None

        def update_btn_state(event=None):
            oid = get_selected_oid()
            if oid:
                btn_goto.config(state="normal")
            else:
                btn_goto.config(state="disabled")

        # Dynamic Button State Binding
        tree_v.bind("<<TreeviewSelect>>", update_btn_state)
        tree_e.bind("<<TreeviewSelect>>", update_btn_state)

        # Navigation action (runs load_object, updates main list, and closes window)
        def do_navigate(event=None):
            oid = get_selected_oid()
            if not oid:
                return
            
            oid = str(oid)
            self.object_list.selection_clear(0, tk.END)
            if oid in self.app.active_object_ids:
                list_idx = self.app.active_object_ids.index(oid)
                self.object_list.selection_set(list_idx)
                self.object_list.see(list_idx)
            
            self.load_object(oid)
            win.destroy()

        # Keyboard and Double-click navigation bindings
        tree_v.bind("<Double-Button-1>", do_navigate)
        tree_v.bind("<Return>", do_navigate)
        tree_e.bind("<Double-Button-1>", do_navigate)
        tree_e.bind("<Return>", do_navigate)

        # Footer Frame
        footer = tk.Frame(main_container, bg=COLORS["surface"], height=sc(48))
        footer.pack(fill="x", side="bottom", padx=sc(10), pady=sc(10))

        btn_close = tk.Button(footer, text="Close", font=FONT_LABEL, fg=COLORS["on_surface"], bg=COLORS["surface"], bd=1, relief="solid", padx=sc(16), pady=sc(4), cursor="hand2", command=win.destroy)
        btn_close.pack(side="left")

        btn_goto = tk.Button(footer, text="Go to", font=FONT_LABEL, fg=COLORS["on_surface"], bg=COLORS["surface"], bd=1, relief="solid", padx=sc(16), pady=sc(4), cursor="hand2", command=do_navigate, state="disabled")
        btn_goto.pack(side="right")

        # Expose dynamic tab switching function
        def select_tab(tab_idx):
            if tab_idx == 0:
                show_tab("visited")
            else:
                show_tab("edits")
            update_btn_state()

        self._select_activity_tab = select_tab
        select_tab(default_tab)
