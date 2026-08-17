import tkinter as tk
from tkinter import ttk
import pandas as pd
import utils
import config
from config import sc

# Color schemes matching AI_UI_GUIDE.md & Arbor design tokens
COLORS_LIGHT = {
    "surface": "#f9f9f9",
    "surface_dim": "#dadada",
    "surface_container_low": "#f3f3f3",
    "surface_container": "#eeeeee",
    "surface_container_high": "#e8e8e8",
    "surface_container_highest": "#e2e2e2",
    "on_surface": "#1a1c1c",
    "on_surface_variant": "#4c4546",
    "outline": "#7e7576",
    "outline_variant": "#cfc4c5",
    "primary": "#000000",
    "on_primary": "#ffffff",
    "primary_container": "#1b1b1b",
    "on_primary_container": "#848484",
    "secondary": "#2e6b30",
    "on_secondary": "#ffffff",
    "secondary_container": "#adf0a6",
    "on_secondary_container": "#326f34",
    "error": "#ba1a1a",
    "on_error": "#ffffff",
    "header_bg": "#f3f3f3",
    "card_bg": "#ffffff",
    "chip_bg": "#e2e2e2",
    "chip_active_bg": "#000000",
    "chip_active_fg": "#ffffff",
    "row_even": "#ffffff",
    "row_odd": "#f8f9fa",
    "select_bg": "#e2e2e2",
    "select_fg": "#000000",
    "sort_active": "#2e6b30"
}

COLORS_DARK = {
    "surface": "#1e1e2e",
    "surface_dim": "#181825",
    "surface_container_low": "#181825",
    "surface_container": "#1e1e2e",
    "surface_container_high": "#252538",
    "surface_container_highest": "#313244",
    "on_surface": "#cdd6f4",
    "on_surface_variant": "#bac2de",
    "outline": "#45475a",
    "outline_variant": "#585b70",
    "primary": "#cdd6f4",
    "on_primary": "#1e1e2e",
    "primary_container": "#313244",
    "on_primary_container": "#a6adc8",
    "secondary": "#a6e3a1",
    "on_secondary": "#1e1e2e",
    "secondary_container": "#252538",
    "on_secondary_container": "#a6e3a1",
    "error": "#f38ba8",
    "on_error": "#1e1e2e",
    "header_bg": "#181825",
    "card_bg": "#252538",
    "chip_bg": "#313244",
    "chip_active_bg": "#a6e3a1",
    "chip_active_fg": "#1e1e2e",
    "row_even": "#1e1e2e",
    "row_odd": "#181825",
    "select_bg": "#313244",
    "select_fg": "#cdd6f4",
    "sort_active": "#a6e3a1"
}


class RecentActivityDialog(tk.Toplevel):
    """
    Unified Recent Activity Window featuring:
      - Styled Column Headers ('Object ID', 'Time', 'Action', 'Changes', 'Specimen') matching Arbor buttons & menus
      - Interactive sorting (Ascending / Descending) on header buttons
      - Live search & filter bar with action type chips
      - Light / Dark theme support following AI_UI_GUIDE.md
      - Decoupled callback hooks via live_callbacks
    """

    def __init__(self, parent, history_stack=None, df_log=None, live_callbacks=None, dark_mode=False, default_tab=0, get_object_title_fn=None):
        super().__init__(parent)

        self.parent = parent
        self.history_stack = history_stack if history_stack is not None else []
        self.df_log = df_log
        self.live_callbacks = live_callbacks or {}
        self.dark_mode = dark_mode
        self.get_object_title_fn = get_object_title_fn or (lambda oid: f"Specimen record #{oid}")

        self.colors = COLORS_DARK if self.dark_mode else COLORS_LIGHT

        # Sort state tracker: column -> direction ('asc', 'desc', None)
        self.sort_state_visited = {"col": "ObjectID", "direction": "desc"}
        self.sort_state_edits = {"col": "Time", "direction": "desc"}

        # Filter state
        self.search_query = tk.StringVar(value="")
        self.action_filter = tk.StringVar(value="All")

        # Fonts scaled via sc()
        self.FONT_HEADLINE = ("Lora", sc(14), "bold")
        self.FONT_LABEL = ("JetBrains Mono", sc(10), "bold")
        self.FONT_DATA = ("JetBrains Mono", sc(11))
        self.FONT_TEXT = ("Inter", sc(11))

        self._setup_window()
        self._setup_styles()
        self._build_ui()

        # Select initial tab
        self._select_tab("visited" if default_tab == 0 else "edits")

        # Initial data population
        self.refresh_data()

    def _setup_window(self):
        self.title("Recent Activity")
        self.configure(bg=self.colors["surface"])

        screen_w = self.winfo_screenwidth()
        screen_h = self.winfo_screenheight()
        width = max(sc(840), int(screen_w * 0.52))
        height = max(sc(500), int(screen_h * 0.58))
        utils.center_and_fit_toplevel(self, width, height)

        self.bind("<Escape>", lambda e: self._on_close())
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _setup_styles(self):
        self.style = ttk.Style(self)
        try:
            self.style.theme_use("clam")
        except Exception:
            pass

        # Treeview styling matching Arbor's flat buttons & menus
        heading_bg = self.colors["surface_container_low"]
        heading_fg = self.colors["on_surface"]
        select_bg = self.colors["select_bg"]
        select_fg = self.colors["select_fg"]
        row_bg = self.colors["surface"]

        self.style.configure(
            "RecentActivity.Treeview",
            background=row_bg,
            foreground=heading_fg,
            fieldbackground=row_bg,
            rowheight=sc(30),
            borderwidth=0,
            font=self.FONT_TEXT
        )
        self.style.map(
            "RecentActivity.Treeview",
            background=[("selected", select_bg)],
            foreground=[("selected", select_fg)]
        )

        # Header button style - flat with solid hairline border
        self.style.configure(
            "RecentActivity.Treeview.Heading",
            background=heading_bg,
            foreground=heading_fg,
            font=self.FONT_LABEL,
            relief="flat",
            borderwidth=1,
            padding=(sc(8), sc(6))
        )
        self.style.map(
            "RecentActivity.Treeview.Heading",
            background=[("active", self.colors["surface_container_highest"])],
            foreground=[("active", self.colors["primary"])]
        )

    def _build_ui(self):
        main_container = tk.Frame(self, bg=self.colors["surface"])
        main_container.pack(fill="both", expand=True)

        # 1. Header Frame (Title + Refresh + Theme indicator)
        header = tk.Frame(main_container, bg=self.colors["header_bg"], height=sc(56))
        header.pack(fill="x", side="top")
        header.pack_propagate(False)
        tk.Frame(header, bg=self.colors["outline_variant"], height=1).pack(fill="x", side="bottom")

        left_header = tk.Frame(header, bg=self.colors["header_bg"])
        left_header.pack(side="left", fill="y", padx=sc(16))

        tk.Label(
            left_header, text="Recent Activity",
            font=self.FONT_HEADLINE, fg=self.colors["primary"],
            bg=self.colors["header_bg"]
        ).pack(side="left")

        btn_refresh = tk.Button(
            left_header, text="↻ Refresh", font=self.FONT_TEXT,
            bg=self.colors["surface_container_low"], fg=self.colors["primary"],
            activebackground=self.colors["surface_container_highest"],
            activeforeground=self.colors["primary"],
            bd=1, relief="solid", cursor="hand2", padx=sc(10), pady=sc(2),
            command=self._handle_refresh
        )
        btn_refresh.pack(side="left", padx=(sc(16), 0))

        lbl_desc = tk.Label(
            header, text="Track recently visited objects & audit edits",
            font=self.FONT_TEXT, fg=self.colors["on_surface_variant"],
            bg=self.colors["header_bg"]
        )
        lbl_desc.pack(side="right", padx=sc(16), pady=sc(16))

        # 2. Filter & Search Toolbar Bar
        toolbar = tk.Frame(main_container, bg=self.colors["surface_container"], height=sc(48))
        toolbar.pack(fill="x", side="top", padx=sc(12), pady=(sc(8), 0))

        # Search Box
        search_frame = tk.Frame(toolbar, bg=self.colors["card_bg"], bd=1, relief="solid")
        search_frame.pack(side="left", fill="y", pady=sc(4))

        tk.Label(
            search_frame, text="🔍", font=("Inter", sc(10)),
            fg=self.colors["on_surface_variant"], bg=self.colors["card_bg"]
        ).pack(side="left", padx=(sc(8), sc(4)))

        search_entry = tk.Entry(
            search_frame, textvariable=self.search_query,
            font=self.FONT_TEXT, bg=self.colors["card_bg"],
            fg=self.colors["on_surface"], bd=0, highlightthickness=0, width=24
        )
        search_entry.pack(side="left", fill="both", expand=True, padx=(0, sc(4)))
        self.search_query.trace_add("write", lambda *args: self.apply_filters())

        btn_clear = tk.Button(
            search_frame, text="✕", font=self.FONT_TEXT,
            bg=self.colors["card_bg"], fg=self.colors["on_surface_variant"],
            bd=0, cursor="hand2", command=lambda: self.search_query.set("")
        )
        btn_clear.pack(side="right", padx=sc(4))

        # Action Filter Chips
        chips_frame = tk.Frame(toolbar, bg=self.colors["surface_container"])
        chips_frame.pack(side="right", fill="y", pady=sc(4))

        tk.Label(
            chips_frame, text="Filter Action:", font=self.FONT_LABEL,
            fg=self.colors["on_surface_variant"], bg=self.colors["surface_container"]
        ).pack(side="left", padx=(0, sc(8)))

        self.chip_buttons = {}
        action_options = ["All", "Manual Edit", "Conflict Resolver", "Created Object"]
        for opt in action_options:
            btn = tk.Button(
                chips_frame, text=opt, font=self.FONT_LABEL,
                bd=1, relief="solid", cursor="hand2", padx=sc(8), pady=sc(2),
                command=lambda o=opt: self._set_action_filter(o)
            )
            btn.pack(side="left", padx=sc(2))
            self.chip_buttons[opt] = btn
        self._update_chip_styles()

        # 3. Custom Tabs Bar
        tab_nav = tk.Frame(main_container, bg=self.colors["surface_container_highest"], height=sc(40))
        tab_nav.pack(fill="x", side="top", pady=(sc(8), 0))
        tk.Frame(tab_nav, bg=self.colors["outline_variant"], height=1).pack(fill="x", side="bottom")

        self.activity_tabs = {}
        self.activity_tab_buttons = {}

        def create_tab_btn(name, label):
            btn_frame = tk.Frame(tab_nav, bg=self.colors["surface_container_highest"])
            btn_frame.pack(side="left", fill="y")

            tk.Frame(btn_frame, bg=self.colors["outline_variant"], width=1).pack(side="right", fill="y")
            bottom_border = tk.Frame(btn_frame, bg=self.colors["outline_variant"], height=2)
            bottom_border.pack(side="bottom", fill="x")

            btn = tk.Button(
                btn_frame, text=label, font=self.FONT_LABEL,
                fg=self.colors["on_surface_variant"], bg=self.colors["surface_container_highest"],
                bd=0, relief="flat", padx=sc(18), cursor="hand2",
                command=lambda: self._select_tab(name)
            )
            btn.pack(side="top", fill="both", expand=True)
            self.activity_tab_buttons[name] = (btn, bottom_border)

        create_tab_btn("visited", "VISITED OBJECTS")
        create_tab_btn("edits", "RECENT EDITS LOG")

        # Content Container
        content_area = tk.Frame(main_container, bg=self.colors["surface"])
        content_area.pack(fill="both", expand=True)

        # Tab 1: Visited Objects Frame
        frame_visited = tk.Frame(content_area, bg=self.colors["surface"])
        self.activity_tabs["visited"] = frame_visited

        tree_frame_v = tk.Frame(frame_visited, bg=self.colors["surface"])
        tree_frame_v.pack(fill="both", expand=True, padx=sc(12), pady=sc(8))

        scroll_y_v = ttk.Scrollbar(tree_frame_v, orient="vertical")
        scroll_y_v.pack(side="right", fill="y")

        self.tree_v = ttk.Treeview(
            tree_frame_v, columns=("ObjectID", "Specimen"),
            show="headings", style="RecentActivity.Treeview",
            yscrollcommand=scroll_y_v.set
        )
        self.tree_v.column("ObjectID", width=sc(160), minwidth=sc(100))
        self.tree_v.column("Specimen", width=sc(620), minwidth=sc(250), stretch=True)

        self.tree_v.pack(side="left", fill="both", expand=True)
        scroll_y_v.config(command=self.tree_v.yview)

        # Bind Visited Headings for Sorting
        self.tree_v.heading("ObjectID", text="OBJECT ID ⇅", command=lambda: self._sort_visited("ObjectID"))
        self.tree_v.heading("Specimen", text="SPECIMEN ⇅", command=lambda: self._sort_visited("Specimen"))

        # Tab 2: Recent Edits Frame
        frame_edits = tk.Frame(content_area, bg=self.colors["surface"])
        self.activity_tabs["edits"] = frame_edits

        tree_frame_e = tk.Frame(frame_edits, bg=self.colors["surface"])
        tree_frame_e.pack(fill="both", expand=True, padx=sc(12), pady=sc(8))

        scroll_y_e = ttk.Scrollbar(tree_frame_e, orient="vertical")
        scroll_y_e.pack(side="right", fill="y")

        self.tree_e = ttk.Treeview(
            tree_frame_e, columns=("ObjectID", "Time", "Action", "Changes"),
            show="headings", style="RecentActivity.Treeview",
            yscrollcommand=scroll_y_e.set
        )
        self.tree_e.column("ObjectID", width=sc(110), minwidth=sc(70))
        self.tree_e.column("Time", width=sc(150), minwidth=sc(110))
        self.tree_e.column("Action", width=sc(140), minwidth=sc(90))
        self.tree_e.column("Changes", width=sc(420), minwidth=sc(200), stretch=True)

        self.tree_e.pack(side="left", fill="both", expand=True)
        scroll_y_e.config(command=self.tree_e.yview)

        # Bind Edits Headings for Sorting
        self.tree_e.heading("ObjectID", text="OBJECT ID ⇅", command=lambda: self._sort_edits("ObjectID"))
        self.tree_e.heading("Time", text="TIME ⇅", command=lambda: self._sort_edits("Time"))
        self.tree_e.heading("Action", text="ACTION ⇅", command=lambda: self._sort_edits("Action"))
        self.tree_e.heading("Changes", text="CHANGES ⇅", command=lambda: self._sort_edits("Changes"))

        # Row Tags for Alternating Colors
        for tree in (self.tree_v, self.tree_e):
            tree.tag_configure("even", background=self.colors["row_even"])
            tree.tag_configure("odd", background=self.colors["row_odd"])

        # Dynamic Selection & Double-Click Navigation Bindings
        self.tree_v.bind("<<TreeviewSelect>>", self._update_btn_state)
        self.tree_e.bind("<<TreeviewSelect>>", self._update_btn_state)

        self.tree_v.bind("<Double-Button-1>", self._do_navigate)
        self.tree_v.bind("<Return>", self._do_navigate)
        self.tree_e.bind("<Double-Button-1>", self._do_navigate)
        self.tree_e.bind("<Return>", self._do_navigate)

        # Footer Frame
        footer = tk.Frame(main_container, bg=self.colors["surface"], height=sc(48))
        footer.pack(fill="x", side="bottom", padx=sc(12), pady=sc(10))

        self.lbl_count = tk.Label(
            footer, text="0 records found", font=self.FONT_TEXT,
            fg=self.colors["on_surface_variant"], bg=self.colors["surface"]
        )
        self.lbl_count.pack(side="left", padx=sc(4))

        self.btn_goto = tk.Button(
            footer, text="Go to Object ➔", font=self.FONT_LABEL,
            fg=self.colors["on_primary"], bg=self.colors["primary"],
            activebackground=self.colors["primary_container"],
            activeforeground=self.colors["on_primary"],
            bd=1, relief="solid", padx=sc(16), pady=sc(4), cursor="hand2",
            command=self._do_navigate, state="disabled"
        )
        self.btn_goto.pack(side="right", padx=(sc(8), 0))

        self.btn_close = tk.Button(
            footer, text="Close", font=self.FONT_LABEL,
            fg=self.colors["on_surface"], bg=self.colors["surface"],
            activebackground=self.colors["surface_container_highest"],
            bd=1, relief="solid", padx=sc(16), pady=sc(4), cursor="hand2",
            command=self._on_close
        )
        self.btn_close.pack(side="right")

    def _select_tab(self, tab_name):
        self.active_tab_name = tab_name
        for name, frame in self.activity_tabs.items():
            frame.pack_forget()
        self.activity_tabs[tab_name].pack(fill="both", expand=True)

        for name, (btn, border) in self.activity_tab_buttons.items():
            if name == tab_name:
                btn.config(fg=self.colors["primary"], bg=self.colors["surface"])
                border.config(bg=self.colors["primary"])
            else:
                btn.config(fg=self.colors["on_surface_variant"], bg=self.colors["surface_container_highest"])
                border.config(bg=self.colors["outline_variant"])

        self.apply_filters()
        self._update_btn_state()

    def _set_action_filter(self, action_name):
        self.action_filter.set(action_name)
        self._update_chip_styles()
        self.apply_filters()

    def _update_chip_styles(self):
        curr = self.action_filter.get()
        for opt, btn in self.chip_buttons.items():
            if opt == curr:
                btn.config(
                    bg=self.colors["chip_active_bg"],
                    fg=self.colors["chip_active_fg"]
                )
            else:
                btn.config(
                    bg=self.colors["chip_bg"],
                    fg=self.colors["on_surface"]
                )

    def refresh_data(self):
        self._raw_visited_data = []
        self._raw_edits_data = []

        # Parse history stack
        if self.history_stack:
            seen = set()
            for item in reversed(self.history_stack):
                oid = str(item)
                if oid not in seen:
                    seen.add(oid)
                    title = self.get_object_title_fn(oid)
                    self._raw_visited_data.append((oid, title))

        # Parse df_log
        if self.df_log is not None and not self.df_log.empty:
            cols = list(self.df_log.columns)
            for row in reversed(list(self.df_log.itertuples(index=False, name=None))):
                row_dict = dict(zip(cols, row))
                tstamp = str(row_dict.get("Timestamp", ""))
                if "T" in tstamp:
                    tstamp = tstamp.split('.')[0].replace("T", " ")

                raw_act = str(row_dict.get("Action", ""))
                display_act = raw_act
                if raw_act == "EDIT":
                    display_act = "Manual Edit"
                elif raw_act == "RESOLVE_HISTORICAL_CONFLICT":
                    display_act = "Conflict Resolver"
                elif raw_act == "CREATE_OBJECT_FAST":
                    display_act = "Created Object"

                obj_id = str(row_dict.get("ObjectID", ""))
                c_fields = str(row_dict.get("ChangedFields", ""))
                c_vals = str(row_dict.get("ChangedValues", ""))
                p_fields = str(row_dict.get("ProblemsChanged", ""))
                p_vals = str(row_dict.get("ProblemsChangedValues", ""))
                l_fields = str(row_dict.get("LocationChanged", ""))
                l_vals = str(row_dict.get("LocationChangedValues", ""))

                changes_parts = []
                if c_fields and c_fields.strip() and c_fields != "(no changes)":
                    val_str = c_vals.strip()
                    if val_str:
                        parts = [p.replace("  ", " → ") for p in val_str.split(" | ")]
                        changes_parts.append(f"Data: {', '.join(parts)}")
                    else:
                        changes_parts.append(f"Data: {c_fields}")

                if p_fields and p_fields.strip():
                    val_str = p_vals.strip()
                    if val_str:
                        parts = [p.replace("  ", " → ") for p in val_str.split(" | ")]
                        changes_parts.append(f"Problems: {', '.join(parts)}")
                    else:
                        changes_parts.append(f"Problems: {p_fields}")

                if l_fields and l_fields.strip():
                    val_str = l_vals.strip()
                    if val_str:
                        parts = [p.replace("  ", " → ") for p in val_str.split(" | ")]
                        changes_parts.append(f"Location: {', '.join(parts)}")
                    else:
                        changes_parts.append(f"Location: {l_fields}")

                changes = " | ".join(changes_parts)
                if not changes and c_fields == "(no changes)":
                    changes = "(no changes)"

                self._raw_edits_data.append((obj_id, tstamp, display_act, changes))

        self.apply_filters()

    def apply_filters(self):
        q = self.search_query.get().strip().lower()
        act_f = self.action_filter.get()

        # Clear existing
        self.tree_v.delete(*self.tree_v.get_children())
        self.tree_e.delete(*self.tree_e.get_children())

        # Filter visited
        filtered_visited = []
        for oid, spec in getattr(self, "_raw_visited_data", []):
            if not q or (q in oid.lower() or q in spec.lower()):
                filtered_visited.append((oid, spec))

        # Sort visited
        col_v = self.sort_state_visited["col"]
        dir_v = self.sort_state_visited["direction"]
        idx_v = 0 if col_v == "ObjectID" else 1
        filtered_visited.sort(key=lambda r: r[idx_v], reverse=(dir_v == "desc"))

        for i, (oid, spec) in enumerate(filtered_visited):
            tag = "even" if i % 2 == 0 else "odd"
            self.tree_v.insert("", "end", values=(oid, spec), tags=(tag,))

        # Filter edits
        filtered_edits = []
        for oid, tstamp, act, changes in getattr(self, "_raw_edits_data", []):
            match_q = (not q) or (q in oid.lower() or q in tstamp.lower() or q in act.lower() or q in changes.lower())
            match_act = (act_f == "All") or (act == act_f)
            if match_q and match_act:
                filtered_edits.append((oid, tstamp, act, changes))

        # Sort edits
        col_e = self.sort_state_edits["col"]
        dir_e = self.sort_state_edits["direction"]
        col_map_e = {"ObjectID": 0, "Time": 1, "Action": 2, "Changes": 3}
        idx_e = col_map_e.get(col_e, 1)
        filtered_edits.sort(key=lambda r: r[idx_e], reverse=(dir_e == "desc"))

        for i, (oid, tstamp, act, changes) in enumerate(filtered_edits):
            tag = "even" if i % 2 == 0 else "odd"
            self.tree_e.insert("", "end", values=(oid, tstamp, act, changes), tags=(tag,))

        # Update counter
        count = len(filtered_visited) if self.active_tab_name == "visited" else len(filtered_edits)
        self.lbl_count.config(text=f"{count} records found")

        self._update_heading_labels()

    def _sort_visited(self, col_name):
        if self.sort_state_visited["col"] == col_name:
            self.sort_state_visited["direction"] = "asc" if self.sort_state_visited["direction"] == "desc" else "desc"
        else:
            self.sort_state_visited["col"] = col_name
            self.sort_state_visited["direction"] = "asc"
        self.apply_filters()

    def _sort_edits(self, col_name):
        if self.sort_state_edits["col"] == col_name:
            self.sort_state_edits["direction"] = "asc" if self.sort_state_edits["direction"] == "desc" else "desc"
        else:
            self.sort_state_edits["col"] = col_name
            self.sort_state_edits["direction"] = "asc"
        self.apply_filters()

    def _update_heading_labels(self):
        # Update visited header titles with direction arrows matching Arbor style
        v_col = self.sort_state_visited["col"]
        v_dir = "▲" if self.sort_state_visited["direction"] == "asc" else "▼"
        self.tree_v.heading("ObjectID", text=f"OBJECT ID {' ' + v_dir if v_col == 'ObjectID' else ' ⇅'}")
        self.tree_v.heading("Specimen", text=f"SPECIMEN {' ' + v_dir if v_col == 'Specimen' else ' ⇅'}")

        # Update edits header titles
        e_col = self.sort_state_edits["col"]
        e_dir = "▲" if self.sort_state_edits["direction"] == "asc" else "▼"
        self.tree_e.heading("ObjectID", text=f"OBJECT ID {' ' + e_dir if e_col == 'ObjectID' else ' ⇅'}")
        self.tree_e.heading("Time", text=f"TIME {' ' + e_dir if e_col == 'Time' else ' ⇅'}")
        self.tree_e.heading("Action", text=f"ACTION {' ' + e_dir if e_col == 'Action' else ' ⇅'}")
        self.tree_e.heading("Changes", text=f"CHANGES {' ' + e_dir if e_col == 'Changes' else ' ⇅'}")

    def get_selected_oid(self):
        tree = self.tree_v if self.active_tab_name == "visited" else self.tree_e
        sel = tree.selection()
        if sel:
            return tree.item(sel[0])["values"][0]
        return None

    def _update_btn_state(self, event=None):
        oid = self.get_selected_oid()
        if oid:
            self.btn_goto.config(state="normal")
        else:
            self.btn_goto.config(state="disabled")

    def _do_navigate(self, event=None):
        oid = self.get_selected_oid()
        if not oid:
            return
        oid = str(oid)

        nav_fn = self.live_callbacks.get("on_navigate")
        if callable(nav_fn):
            nav_fn(oid)

        self._on_close()

    def _handle_refresh(self):
        ref_fn = self.live_callbacks.get("on_refresh")
        if callable(ref_fn):
            ref_fn()
        self.refresh_data()

    def _on_close(self):
        close_fn = self.live_callbacks.get("on_close")
        if callable(close_fn):
            close_fn()
        self.destroy()


def open_recent_activity_dialog(parent, history_stack=None, df_log=None, live_callbacks=None, dark_mode=False, default_tab=0, get_object_title_fn=None):
    """
    1-Line Plug-and-Play launcher function for host applications.
    """
    dialog = RecentActivityDialog(
        parent=parent,
        history_stack=history_stack,
        df_log=df_log,
        live_callbacks=live_callbacks,
        dark_mode=dark_mode,
        default_tab=default_tab,
        get_object_title_fn=get_object_title_fn
    )
    return dialog


if __name__ == "__main__":
    # Standalone Test Harness & Debug Runner
    root = tk.Tk()
    root.title("Host Window (Test Harness)")
    root.geometry("400x200")
    root.configure(bg="#f0f0f0")

    # Generate mock sample log dataframe
    mock_log = pd.DataFrame([
        {
            "Timestamp": "2026-08-17T10:15:30.123",
            "Action": "EDIT",
            "ObjectID": "1001",
            "ChangedFields": "Genus | Collector",
            "ChangedValues": "Pinus  Abies | Smith  Jones",
            "ProblemsChanged": "",
            "ProblemsChangedValues": "",
            "LocationChanged": "",
            "LocationChangedValues": ""
        },
        {
            "Timestamp": "2026-08-17T10:45:00.000",
            "Action": "RESOLVE_HISTORICAL_CONFLICT",
            "ObjectID": "1002",
            "ChangedFields": "Species",
            "ChangedValues": "sylvestris  alba",
            "ProblemsChanged": "Species_Problem",
            "ProblemsChangedValues": "True  False",
            "LocationChanged": "",
            "LocationChangedValues": ""
        },
        {
            "Timestamp": "2026-08-17T11:05:12.450",
            "Action": "CREATE_OBJECT_FAST",
            "ObjectID": "1003",
            "ChangedFields": "Data: Object Created",
            "ChangedValues": "",
            "ProblemsChanged": "",
            "ProblemsChangedValues": "",
            "LocationChanged": "Cabinet",
            "LocationChangedValues": "  C-12"
        }
    ])

    mock_history = ["1001", "1002", "1003", "1004", "1005"]

    def sample_title(oid):
        titles = {
            "1001": "Pinus sylvestris L. - Herbarium Sheet A",
            "1002": "Abies alba Mill. - Specimen Box 4",
            "1003": "Betula pendula Roth - Mounted Platform",
            "1004": "Quercus robur L. - Wood Section",
            "1005": "Picea abies (L.) H.Karst. - Seed Collection"
        }
        return titles.get(str(oid), f"Specimen record #{oid}")

    def on_nav(oid):
        print(f"[CALLBACK] Navigating to Object ID: {oid}")

    def on_ref():
        print("[CALLBACK] Log refreshed!")

    def launch(dark=False):
        open_recent_activity_dialog(
            parent=root,
            history_stack=mock_history,
            df_log=mock_log,
            live_callbacks={"on_navigate": on_nav, "on_refresh": on_ref},
            dark_mode=dark,
            get_object_title_fn=sample_title
        )

    tk.Label(root, text="Recent Activity Standalone Harness", font=("Inter", 12, "bold"), bg="#f0f0f0").pack(pady=15)
    tk.Button(root, text="Open Recent Activity (Light Mode)", command=lambda: launch(False), padx=10, pady=5).pack(pady=5)
    tk.Button(root, text="Open Recent Activity (Dark Mode)", command=lambda: launch(True), padx=10, pady=5).pack(pady=5)

    root.mainloop()
