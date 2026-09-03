import difflib
import tkinter as tk
from tkinter import ttk
import pandas as pd
from utils import debug_error
from ui.state import app_bus, PROBLEM_STATE_CHANGED


class RegistryPanel:
    """Manager and builder for the Specimen Registration cards and fields form."""

    @staticmethod
    def build_sections(ui):
        """Construct the Registration form cards, fields, problems tab, and location wiring."""
        from config import sc
        import config

        ui._rebuild_focus_registration_menu()

        # Initialize problem vars first so they are available for inline problem checkboxes
        ui.problem_vars.clear()
        ui.problem_checkbuttons = []
        for field in ui.app.config["ui_sections"]["problems"]:
            name = field["name"]
            var = tk.BooleanVar()
            ui.problem_vars[name] = var
            var.trace_add("write", lambda *_, n=name: (
                ui.update_problems_default_view(),
                app_bus.publish(PROBLEM_STATE_CHANGED, {"field": n, "value": ui.problem_vars.get(n, tk.BooleanVar()).get()})
            ))

        if not hasattr(ui, "images_missing_var"):
            ui.images_missing_var = tk.StringVar()

        # -------- REG --------
        if hasattr(ui, "reg_notebook") and ui.reg_notebook.winfo_exists():
            for tab in ui.reg_notebook.tabs():
                ui.reg_notebook.forget(tab)

        ui.reg_vars.clear()
        ui.reg_entries.clear()
        ui.reg_row_frames.clear()
        ui.reg_entry_list = []
        ui.unval_btns = {}
        ui.unval_comment_frames = {}
        ui.unval_comment_vars = {}

        ui.no_problems_msg_label = ttk.Label(
            ui.reg_data_frame,
            text="No active problems for this object. All fields hidden.",
            foreground="#2b8a3e",
            font=("Segoe UI", sc(10), "italic"),
            anchor="center"
        )

        # Build reverse map for inline problem checkboxes
        field_to_problem = {v: k for k, v in ui.problem_to_field.items()}
        ui.prob_border_bars.clear()
        ui.prob_label_widgets.clear()

        # Build single Specimen Audit tab with cards
        all_fields = [f["name"] for f in ui.app.config["ui_sections"]["registration"]]
        ui._reg_tabs = {}

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

        ui.card_defs_ordered = [c["id"] for c in card_defs]
        ui.card_frames = {}

        is_dark = getattr(ui, "dark_mode_active", False)
        card_bg = "#1e1e2d" if is_dark else "#ffffff"
        header_bg = "#252538" if is_dark else "#f5f5f5"
        border_color = "#313244" if is_dark else "#e2e2e2"
        fg_color = "#e8ebe9" if is_dark else "#2c302e"

        # Create a single tab container for Specimen Audit
        tab_container = ttk.Frame(ui.reg_notebook)

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

        def _make_mousewheel_scroller(canvas):
            return lambda e: canvas.yview_scroll(int(-1 * (e.delta / 120)), "units")

        mw_scroller = _make_mousewheel_scroller(tab_canvas)
        tab_canvas.bind("<MouseWheel>", mw_scroller)
        tab_frame.bind("<MouseWheel>", mw_scroller)

        tab_canvas.pack(side="left", fill="both", expand=True)
        tab_scroll.pack(side="right", fill="y")

        ui._reg_tabs["General Data"] = {
            "container": tab_container,
            "canvas": tab_canvas,
            "frame": tab_frame,
            "fields": all_fields
        }

        ui.reg_notebook.add(tab_container, text="General Data")

        # Create O(1) lookup dictionary for registration config
        reg_config_dict = {f["name"]: f for f in ui.app.config.get("ui_sections", {}).get("registration", [])}

        # Generate collapsible accordion card layout inside the tab frame
        for c in card_defs:
            card_id = c["id"]
            card_title = c["title"]
            icon = c["icon"]
            fields_to_render = c["fields"]

            # Card frame (outer container with 1px border)
            card_frame = tk.Frame(tab_frame, bg=card_bg, highlightthickness=1, highlightbackground=border_color, bd=0)
            card_frame.pack(fill="x", padx=sc(10), pady=sc(6))

            # Header panel (interactive accordion trigger)
            header_frame = tk.Frame(card_frame, bg=header_bg, padx=sc(8), pady=sc(6), cursor="hand2")
            header_frame.pack(fill="x")

            toggle_lbl = tk.Label(
                header_frame, text="▼",
                font=("Inter", sc(9), "bold"),
                bg=header_bg, fg=fg_color, cursor="hand2"
            )
            toggle_lbl.pack(side="left", padx=(sc(2), sc(4)))

            icon_lbl = tk.Label(header_frame, text=icon, font=("Segoe UI Symbol", sc(11)), bg=header_bg, fg=fg_color, cursor="hand2")
            icon_lbl.pack(side="left", padx=(0, sc(6)))

            title_lbl = tk.Label(header_frame, text=card_title, font=("Inter", sc(10), "bold"), bg=header_bg, fg=fg_color, cursor="hand2")
            title_lbl.pack(side="left")

            # Problem count badge inside card header
            badge_lbl = tk.Label(
                header_frame, text="",
                font=("JetBrains Mono", sc(8), "bold"),
                bg=header_bg, fg="#c93a40"
            )
            badge_lbl.pack(side="left", padx=(sc(8), 0))

            if card_id == "taxonomy":
                prefs = config.load_prefs()
                show_gbif = prefs.get("enable_gbif", False)

                ui.gbif_btn = tk.Label(header_frame, text="🔍 Check GBIF", font=("Inter", sc(8), "bold"), bg="#2b8a3e", fg="#ffffff", cursor="hand2", padx=sc(6), pady=sc(2))
                if show_gbif:
                    ui.gbif_btn.pack(side="right", padx=sc(6))
                ui.gbif_btn.bind("<Button-1>", lambda e: ui.check_gbif_action())
                ui.gbif_btn.bind("<Enter>", lambda e, w=ui.gbif_btn: w.config(bg="#3bc954"))
                ui.gbif_btn.bind("<Leave>", lambda e, w=ui.gbif_btn: w.config(bg="#2b8a3e"))

            # Card content area
            body_frame = tk.Frame(card_frame, bg=card_bg, padx=sc(10), pady=sc(8))
            body_frame.pack(fill="x")
            body_frame.columnconfigure(0, weight=1)

            def _make_toggle_handler(b_frame, t_lbl, tc):
                def _handler(event=None):
                    if b_frame.winfo_manager():
                        b_frame.pack_forget()
                        t_lbl.config(text="▶")
                    else:
                        b_frame.pack(fill="x")
                        t_lbl.config(text="▼")
                    tc.configure(scrollregion=tc.bbox("all"))
                return _handler

            toggle_cmd = _make_toggle_handler(body_frame, toggle_lbl, tab_canvas)
            for w in (header_frame, toggle_lbl, icon_lbl, title_lbl):
                w.bind("<Button-1>", toggle_cmd)

            ui.card_frames[card_id] = {
                "frame": card_frame,
                "body": body_frame,
                "toggle_lbl": toggle_lbl,
                "badge_lbl": badge_lbl,
                "fields": fields_to_render
            }

            current_row = 0
            for fname in fields_to_render:
                field = reg_config_dict.get(fname)
                if not field:
                    continue

                name = field["name"]
                ftype = field.get("type", "text")
                var = tk.StringVar()
                ui.reg_vars[name] = var

                # Single individual field row
                frame = tk.Frame(body_frame, bg=card_bg)
                ui.reg_row_frames[name] = frame

                # Col 0: border bar + optional problem checkbox
                col0_frame = tk.Frame(frame, bg=card_bg)
                col0_frame.grid(row=0, column=0, sticky="nsw", padx=(2, 2))

                prob_col = field_to_problem.get(name)
                if prob_col:
                    prob_var = ui.problem_vars[prob_col]

                    border_bar = tk.Frame(col0_frame, width=3, bd=0, highlightthickness=0)
                    border_bar.pack(side="left", fill="y", padx=(0, 2))
                    ui.prob_border_bars[name] = border_bar

                    cb = ttk.Checkbutton(
                        col0_frame, text="", variable=prob_var, cursor="hand2",
                        command=lambda n=name, pc=prob_col: (
                            ui._update_problem_row_style(n, ui.problem_vars[pc].get()),
                            ui.commit_current_object()
                        )
                    )
                    cb.pack(side="left")
                    ui.add_tooltip(cb, f"Flag as having a problem ({prob_col.replace('_', ' ')}). Tab + Space to toggle.")

                    prob_var.trace_add(
                        "write",
                        lambda *_, n=name, pc=prob_col: ui.root.after_idle(
                            lambda: ui._update_problem_row_style(n, ui.problem_vars[pc].get())
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
                    ui.prob_label_widgets[name] = lbl

                # Col 2: input widget based on type
                if ftype == "choice":
                    choices = field.get("choices", [])
                    if "" not in choices:
                        choices = [""] + choices
                    widget = ttk.Combobox(frame, textvariable=var, values=choices, cursor="hand2")
                    widget.bind("<<ComboboxSelected>>", lambda e: ui.commit_current_object())
                elif ftype == "checkbox":
                    widget = ttk.Checkbutton(
                        frame, cursor="hand2",
                        text="",
                        variable=var,
                        onvalue="True",
                        offvalue="False",
                        command=lambda n=name, v=var: ui._on_checkbox_change(n, v)
                    )
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
                        w.bind("<KeyRelease>", ui._on_text_change)
                        w.bind("<FocusOut>", lambda e: ui.commit_current_object(), add="+")

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
                            dark = getattr(ui, "dark_mode_active", False)
                            fl.configure(bg="#a6e3a1" if dark else "#3a7d44")

                        def on_focus_out(e):
                            fl.configure(bg=default_bg)

                        w.bind("<FocusIn>", on_focus_in, add="+")
                        w.bind("<FocusOut>", on_focus_out, add="+")

                    make_focus_handlers(widget, focus_line, entry_container, card_bg)

                    widget.bind("<KeyRelease>", lambda e, n=name, w=widget: RegistryPanel.on_autocomplete_key(ui, e, n, w), add="+")
                    widget.bind("<KeyRelease>", lambda e: ui.root.after(500, lambda: RegistryPanel.validate_fields(ui)), add="+")
                    widget.bind("<FocusOut>", lambda e, n=name, w=widget: RegistryPanel.run_fuzzy_match(ui, n, w), add="+")
                    widget.bind("<FocusOut>", lambda e: ui.commit_current_object(), add="+")

                    if field.get("readonly"):
                        widget.configure(state="disabled")

                ui.reg_entries[name] = widget
                ui.reg_entry_list.append(widget)

                if ftype == "multiline" or name in ("Conservation Status", "Observation", "Comment", "ProblemDescription", "Problem Description"):
                    widget.grid(row=0, column=2, sticky="ew", pady=sc(2))
                elif ftype in ("choice", "checkbox"):
                    widget.grid(row=0, column=2, sticky="ew")
                else:
                    entry_container.grid(row=0, column=2, sticky="ew")

                # Unvalidated Source Flag toggle button
                unval_btn = tk.Label(
                    frame, text="?", font=("Segoe UI", sc(9), "bold"),
                    bg=card_bg, fg="#888888", cursor="hand2", padx=sc(4), pady=sc(1)
                )
                unval_btn.grid(row=0, column=3, padx=(sc(4), sc(2)), sticky="e")
                unval_btn.bind("<Button-1>", lambda e, n=name: ui._toggle_unvalidated_source(n))
                ui.unval_btns[name] = unval_btn
                ui.add_tooltip(unval_btn, f"Flag as Unvalidated Source ({name})")

                # Unvalidated comment container (hidden by default)
                unval_comment_frame = tk.Frame(frame, bg=card_bg)
                lbl_unval = tk.Label(unval_comment_frame, text="Unval Note:", font=("Segoe UI", sc(8), "italic"), bg=card_bg, fg="#f59e0b" if is_dark else "#d97706")
                lbl_unval.pack(side="left", padx=(0, sc(4)))
                unval_var = tk.StringVar()
                ui.unval_comment_vars[name] = unval_var
                unval_entry = tk.Entry(
                    unval_comment_frame, textvariable=unval_var, font=("Segoe UI", sc(9)),
                    bg="#2b2d30" if is_dark else "#fffbeb", fg=fg_color, relief="flat",
                    highlightthickness=1, highlightbackground="#f59e0b" if is_dark else "#d97706", insertbackground=fg_color
                )
                unval_entry.pack(side="left", fill="x", expand=True, ipady=sc(2))
                unval_entry.bind("<FocusOut>", lambda e, n=name: ui._on_unval_comment_change(n))
                unval_entry.bind("<Return>", lambda e, n=name: (ui._on_unval_comment_change(n), ui.root.focus_set()))
                ui.unval_comment_frames[name] = unval_comment_frame

                widget.bind("<Shift-Up>", ui._reg_nav_up)
                widget.bind("<Shift-Down>", ui._reg_nav_down)
                widget.bind("<Control-Up>", ui._reg_nav_up)
                widget.bind("<Control-Down>", ui._reg_nav_down)
                if ftype != "multiline":
                    widget.bind("<Return>", ui._reg_nav_down)

                frame.columnconfigure(0, minsize=sc(28), weight=0)
                frame.columnconfigure(1, minsize=sc(120), weight=0)
                frame.columnconfigure(2, weight=1)
                frame.columnconfigure(3, weight=0)

                frame.grid(row=current_row, column=0, sticky="ew", pady=4)
                current_row += 1

        # -------- PROBLEMS TAB --------
        tab_container = ttk.Frame(ui.reg_notebook)
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

        ui.reg_notebook.add(tab_container, text="Problems")
        ui._reg_tabs["Problems"] = {
            "container": tab_container,
            "canvas": tab_canvas,
            "frame": tab_frame,
            "fields": []
        }

        edit_frame = ttk.Frame(tab_frame, padding=12)
        edit_frame.pack(fill="x")

        ui.problem_checkbuttons = []
        for i, field in enumerate(ui.app.config["ui_sections"]["problems"]):
            name = field["name"]
            var = ui.problem_vars.get(name)
            if not var:
                var = tk.BooleanVar()
                ui.problem_vars[name] = var

            cb = ttk.Checkbutton(
                edit_frame, cursor="hand2",
                text=name.replace("_", " "),
                variable=var,
                command=lambda: (
                    RegistryPanel.update_reg_fields_visibility(ui, skip_snap=True),
                    ui.commit_current_object()
                )
            )
            row = i // 2
            col = i % 2
            cb.grid(row=row, column=col, sticky="w", padx=10, pady=6)
            ui.problem_checkbuttons.append(cb)

        edit_frame.columnconfigure(0, weight=1)
        edit_frame.columnconfigure(1, weight=1)

        ttk.Separator(tab_frame, orient="horizontal").pack(fill="x", pady=10)

        ui.problem_frame = ttk.Frame(tab_frame, padding=12)
        ui.problem_frame.pack(fill="both", expand=True)
        ui.problem_frame.tutorial_id = "problem_flags_frame"

        # -------- LOCATION --------
        for w in ui.location_frame.winfo_children():
            w.destroy()
        if hasattr(ui, 'loc_frame_horizontal'):
            for w in ui.loc_frame_horizontal.winfo_children():
                w.destroy()

        ui.location_vars.clear()
        ui.location_entries = []

        for field in ui.app.config["ui_sections"]["location"]:
            name = field["name"]
            var = tk.StringVar()
            ui.location_vars[name] = var

        ui._build_vertical_location_ui()
        if hasattr(ui, 'loc_frame_horizontal'):
            ui._build_horizontal_location_ui()

        # -------- PROBLEMS --------
        ui.update_problems_default_view()

    @staticmethod
    def update_reg_fields_visibility(ui, skip_snap=False):
        """Update field and card visibility based on Focus Mode and active problems."""
        if not ui.object_loaded:
            return

        focus_active = ui.focus_mode_var.get()
        focus_fallback = ui.focus_fallback_var.get()

        oid = ui.app.current_object_id
        if oid and not ui.loading_object:
            ui.commit_current_object(skip_heavy=True)

        active_problem_fields = set()
        for prob_col, mapped_field in ui.problem_to_field.items():
            if ui.problem_vars.get(prob_col) and ui.problem_vars[prob_col].get():
                active_problem_fields.add(mapped_field)

        if hasattr(ui, "loc_container") and hasattr(ui, "prob_container"):
            show_loc = not (focus_active and not ui.focus_visibility_vars.get("Location", tk.BooleanVar(value=True)).get())
            show_prob = not (focus_active and not ui.focus_visibility_vars.get("Problems", tk.BooleanVar(value=True)).get())

            ui.loc_container.pack_forget()

            loc_in_center = hasattr(ui, 'location_in_center_var') and ui.location_in_center_var.get()

            if show_loc and not loc_in_center:
                if str(ui.left_bottom_container) not in ui.left_panes.panes():
                    ui.left_panes.add(ui.left_bottom_container, weight=0)
                ui.loc_container.pack(side="top", fill="x")
            else:
                if str(ui.left_bottom_container) in ui.left_panes.panes():
                    ui.left_panes.forget(ui.left_bottom_container)

            if show_prob:
                try:
                    ui.reg_notebook.add(ui._reg_tabs["Problems"]["container"])
                except Exception:
                    pass
            else:
                try:
                    ui.reg_notebook.hide(ui._reg_tabs["Problems"]["container"])
                except Exception:
                    pass

        visible_count = 0

        for field in ui.app.config["ui_sections"]["registration"]:
            name = field["name"]
            frame = ui.reg_row_frames.get(name)
            if not frame:
                continue

            is_visible = True
            if focus_active:
                field_toggle = ui.focus_visibility_vars.get(name, tk.BooleanVar(value=True)).get()
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

        if hasattr(ui, "unknown_fields_container"):
            frame = ui.unknown_fields_container
            is_visible = not focus_active

            if is_visible:
                if frame.winfo_manager() != "grid":
                    frame.grid()
                visible_count += 1
            else:
                if frame.winfo_manager() == "grid":
                    frame.grid_remove()

        if focus_active:
            for field_name, check_var in ui.focus_visibility_vars.items():
                frame = ui.reg_row_frames.get(field_name)
                if frame and not check_var.get():
                    if frame.winfo_manager() == "grid":
                        visible_count -= 1
                    frame.grid_remove()

        if hasattr(ui, "no_problems_msg_label"):
            if focus_active and visible_count <= 0:
                ui.no_problems_msg_label.config(text="No fields visible in Focus mode.")
                if ui.no_problems_msg_label.winfo_manager() != "grid":
                    ui.no_problems_msg_label.grid(row=0, column=0, pady=15, sticky="ew")
            else:
                if ui.no_problems_msg_label.winfo_manager() == "grid":
                    ui.no_problems_msg_label.grid_remove()

        if hasattr(ui, "card_frames") and hasattr(ui, "card_defs_ordered"):
            for card_id in ui.card_defs_ordered:
                info = ui.card_frames[card_id]
                card_frame = info["frame"]
                fields = info["fields"]
                any_visible = False
                for f in fields:
                    row_frame = ui.reg_row_frames.get(f)
                    if row_frame and row_frame.winfo_manager() == "grid":
                        any_visible = True
                        break
                if any_visible:
                    if card_frame.winfo_manager() != "pack":
                        card_frame.pack(fill="x", padx=10, pady=8)
                else:
                    if card_frame.winfo_manager() == "pack":
                        card_frame.pack_forget()

        if not skip_snap and ui.snap_lock_var.get():
            ui.snap_to_place(shrink=focus_active)

    @staticmethod
    def refresh_field_background(ui, field_name):
        """Update individual field widget background color based on validation and problem state."""
        import config
        widget = ui.reg_entries.get(field_name)
        if not widget:
            return

        is_dark = getattr(ui, "dark_mode_active", ui.app.config.get("theme", "dark") == "dark")
        norm_bg = "#212622" if is_dark else "#ffffff"
        warn_bg = "#5c4d00" if is_dark else "#fff3cd"
        err_bg = "#5c1e1e" if is_dark else "#f8d7da"
        unknown_bg = "#5c461a" if is_dark else "#ffe4b3"
        suggest_bg = "#5c571a" if is_dark else "#fff3a3"

        is_active_problem = False
        prob_col = None
        for p_col, f_name in ui.problem_to_field.items():
            if f_name == field_name:
                prob_col = p_col
                break
        if prob_col and ui.problem_vars.get(prob_col) and ui.problem_vars[prob_col].get():
            is_active_problem = True

        genus = ui.reg_vars.get("Genus", tk.StringVar()).get().strip()
        species = ui.reg_vars.get("Species", tk.StringVar()).get().strip()
        building = ui.reg_vars.get("Building", tk.StringVar()).get().strip()
        loc_prob = ui.problem_vars.get("Loc_Problem", tk.BooleanVar()).get()

        color = norm_bg

        if is_active_problem:
            hl_color_name = "Default (Red)"
            try:
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
            else:
                tint = "#5c1e1e" if is_dark else "#ffdad6"
            color = tint
        elif field_name == "Species" and genus and not species:
            color = warn_bg
        elif field_name == "Building" and not building and not loc_prob:
            color = err_bg
        else:
            raw_val = ui.reg_vars.get(field_name, tk.StringVar()).get()
            if isinstance(raw_val, pd.Series):
                raw_val = raw_val.iloc[0]
            raw_val = str(raw_val)

            if ui.is_unknown(raw_val):
                color = unknown_bg
            elif getattr(ui, "show_all_history_var", None) and ui.show_all_history_var.get():
                if ui.current_object_suggestions and field_name in ui.collect_historical_suggestions(ui.app.current_object_id):
                    color = suggest_bg
            else:
                color = norm_bg

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

    @staticmethod
    def validate_fields(ui, event=None):
        if ui._is_navigating or ui.loading_object:
            return

        for f_name in ui.reg_entries.keys():
            RegistryPanel.refresh_field_background(ui, f_name)

    @staticmethod
    def run_fuzzy_match(ui, field_name, widget):
        if field_name not in ["Genus", "Species"]:
            return

        val = ui.reg_vars[field_name].get().strip()
        if not val or len(val) < 3:
            if hasattr(widget, "fuzzy_label"):
                widget.fuzzy_label.destroy()
                delattr(widget, "fuzzy_label")
            return

        history = ui.current_object_suggestions.get(field_name, [])
        if not history:
            return

        matches = difflib.get_close_matches(val, history, n=1, cutoff=0.7)

        if matches and matches[0].lower() != val.lower():
            suggestion = matches[0]
            if hasattr(widget, "fuzzy_label"):
                widget.fuzzy_label.destroy()

            lbl = ttk.Label(widget.master, text=f"Did you mean '{suggestion}'?", foreground="#4dabf7", font=("Segoe UI", 8, "underline"), cursor="hand2")
            lbl.grid(row=1, column=1, sticky="w")

            def apply_suggestion(e, s=suggestion, w=widget, n=field_name):
                ui.reg_vars[n].set(s)
                ui.commit_current_object()
                w.fuzzy_label.destroy()
                delattr(w, "fuzzy_label")
                RegistryPanel.validate_fields(ui)

            lbl.bind("<Button-1>", apply_suggestion)
            widget.fuzzy_label = lbl
        else:
            if hasattr(widget, "fuzzy_label"):
                widget.fuzzy_label.destroy()
                delattr(widget, "fuzzy_label")

    @staticmethod
    def clear_all_fuzzy_labels(ui):
        """Destroy any 'Did you mean' suggestion labels on all registration entry widgets."""
        for widget in ui.reg_entries.values():
            if hasattr(widget, "fuzzy_label"):
                try:
                    widget.fuzzy_label.destroy()
                except Exception:
                    pass
                delattr(widget, "fuzzy_label")

    @staticmethod
    def on_autocomplete_key(ui, event, name, widget):
        if event.keysym in ("Up", "Down", "Left", "Right", "Return", "Escape", "Tab", "Shift_L", "Shift_R", "Control_L", "Control_R", "Alt_L", "Alt_R"):
            return
        typed = widget.get().strip().lower()
        all_vals = ui.current_object_suggestions.get(name, [])
        if not all_vals:
            return
        if not typed:
            filtered = all_vals
        else:
            filtered = [v for v in all_vals if typed in str(v).lower()]
        if isinstance(widget, ttk.Combobox):
            widget.configure(values=filtered)
