import json
import os
import threading
import tkinter as tk
from tkinter import ttk, messagebox
import config
from utils import debug_error


class FilterDialogController:
    """Controller and UI builder for the Filter Objects dialog, presets, and integrated historical search."""

    @staticmethod
    def open_filter_menu(ui, initial_tab: str = "status"):
        """Open or lift the main Filter Objects modal dialog."""
        if hasattr(ui, "filter_window") and ui.filter_window and ui.filter_window.winfo_exists():
            ui.filter_window.lift()
            ui.filter_window.focus_force()
            if hasattr(ui, "filter_show_tab"):
                ui.filter_show_tab(initial_tab)
            return

        from config import sc
        import utils

        COLORS = {
            "surface": "#fbfaf8",
            "surface_dim": "#dadada",
            "surface_container_low": "#f2f5f1",
            "surface_container_highest": "#e2e2e2",
            "on_surface": "#2c302e",
            "on_surface_variant": "#444748",
            "outline": "#747878",
            "outline_variant": "#c4c7c7",
            "primary": "#000000",
            "on_primary": "#ffffff",
            "secondary": "#3a7d44",
            "error": "#c93a40",
            "botanical_green": "#3e7b3e",
            "search_orange": "#d9480f",
            "surface_tint": "#5f5e5e"
        }

        FONT_HEADLINE = ("Hanken Grotesk", sc(14), "bold")
        FONT_LABEL = ("JetBrains Mono", sc(10), "bold")
        FONT_DATA = ("JetBrains Mono", sc(11))

        # Ensure historical criteria variables exist on ui
        if not hasattr(ui, "filter_historical_vars"):
            ui.filter_historical_vars = {
                "Genus": tk.StringVar(value=""),
                "Species": tk.StringVar(value=""),
                "Author": tk.StringVar(value=""),
                "Family": tk.StringVar(value=""),
                "Collector": tk.StringVar(value=""),
                "Locality": tk.StringVar(value=""),
                "Year": tk.StringVar(value=""),
                "scope": tk.StringVar(value="both"),
                "match_all": tk.BooleanVar(value=True),
            }

        win = tk.Toplevel(ui.root)
        ui.filter_window = win
        win.title("Filter objects")
        win.geometry(f"{sc(860)}x{sc(680)}")
        win.minsize(sc(800), sc(600))
        win.configure(bg=COLORS["surface"])
        win.bind("<Destroy>", lambda e: setattr(ui, "filter_window", None) if e.widget == win else None)
        win.bind("<Escape>", lambda e: win.destroy())
        win.bind("<Control-Return>", lambda e: FilterDialogController.apply_filter_with_history(ui, win))

        main_container = tk.Frame(win, bg=COLORS["surface"], bd=0, highlightthickness=0)
        main_container.pack(fill="both", expand=True)

        header = tk.Frame(main_container, bg=COLORS["surface_container_low"], height=sc(56))
        header.pack(fill="x", side="top")
        header.pack_propagate(False)
        tk.Frame(header, bg=COLORS["outline"], height=1).pack(fill="x", side="bottom")

        left_header = tk.Frame(header, bg=COLORS["surface_container_low"])
        left_header.pack(side="left", fill="y", padx=sc(16))

        tk.Label(left_header, text="Filter objects", font=FONT_HEADLINE, fg=COLORS["primary"], bg=COLORS["surface_container_low"]).pack(side="left")

        search_frame = tk.Frame(left_header, bg=COLORS["surface"], highlightbackground=COLORS["search_orange"], highlightthickness=1)
        search_frame.pack(side="left", padx=sc(24), pady=sc(12), fill="y")
        tk.Label(search_frame, text="⌕", font=("Segoe UI", sc(12)), fg=COLORS["search_orange"], bg=COLORS["surface"]).pack(side="left", padx=(sc(8), 0))
        search_var = tk.StringVar()
        search_entry = tk.Entry(search_frame, textvariable=search_var, font=FONT_DATA, fg=COLORS["search_orange"], bg=COLORS["surface"], bd=0, insertbackground=COLORS["search_orange"], width=20)
        search_entry.pack(side="left", fill="both", expand=True, padx=sc(8), pady=sc(4))

        right_header = tk.Frame(header, bg=COLORS["surface_container_low"])
        right_header.pack(side="right", fill="y", padx=sc(16))

        def make_btn(parent, text, cmd):
            btn = tk.Button(parent, text=text, font=FONT_LABEL, fg=COLORS["on_surface"], bg=COLORS["surface"], bd=1, relief="solid", padx=sc(12), pady=sc(4), cursor="hand2", command=cmd)
            btn.pack(side="left", padx=sc(4), pady=sc(12))
            return btn

        make_btn(right_header, "Load Preset...", lambda: FilterDialogController.load_filter_preset(ui))
        make_btn(right_header, "Save Preset...", lambda: FilterDialogController.save_filter_preset(ui))

        tab_nav = tk.Frame(main_container, bg=COLORS["surface_container_highest"], height=sc(40))
        tab_nav.pack(fill="x", side="top")
        tab_nav.pack_propagate(False)
        tk.Frame(main_container, bg=COLORS["outline"], height=1).pack(fill="x", side="top")

        tab_content_area = tk.Frame(main_container, bg=COLORS["surface"])
        tab_content_area.pack(fill="both", expand=True)

        ui.filter_tabs = {}
        ui.filter_tab_buttons = {}

        def show_tab(tab_name):
            for name, frame in ui.filter_tabs.items():
                frame.pack_forget()
            if tab_name in ui.filter_tabs:
                ui.filter_tabs[tab_name].pack(fill="both", expand=True)

            for name, btn_tuple in ui.filter_tab_buttons.items():
                btn, border = btn_tuple
                if name == tab_name:
                    btn.config(fg=COLORS["primary"], bg=COLORS["surface"])
                    border.config(bg=COLORS["primary"])
                else:
                    btn.config(fg=COLORS["on_surface_variant"], bg=COLORS["surface_container_highest"])
                    border.config(bg=COLORS["outline"])

        ui.filter_show_tab = show_tab

        def create_tab_btn(name, label):
            btn_frame = tk.Frame(tab_nav, bg=COLORS["surface_container_highest"])
            btn_frame.pack(side="left", fill="y")

            tk.Frame(btn_frame, bg=COLORS["outline"], width=1).pack(side="right", fill="y")
            bottom_border = tk.Frame(btn_frame, bg=COLORS["outline"], height=2)
            bottom_border.pack(side="bottom", fill="x")

            btn = tk.Button(btn_frame, text=label, font=FONT_LABEL, fg=COLORS["on_surface_variant"], bg=COLORS["surface_container_highest"], bd=0, relief="flat", padx=sc(16), cursor="hand2", command=lambda n=name: show_tab(n))
            btn.pack(side="top", fill="both", expand=True)
            ui.filter_tab_buttons[name] = (btn, bottom_border)

        create_tab_btn("status", "Status & General")
        create_tab_btn("problems", "Problems")
        create_tab_btn("historical", "Historical & Books")
        create_tab_btn("images", "Images")
        create_tab_btn("location", "Location")

        all_widgets = []

        def create_group(parent, title):
            group = tk.Frame(parent, bg=COLORS["surface"], highlightbackground=COLORS["outline"], highlightthickness=1)
            group.pack(fill="x", pady=(0, sc(16)))
            tk.Label(group, text=title.upper(), font=FONT_LABEL, fg=COLORS["on_surface_variant"], bg=COLORS["surface"]).pack(anchor="w", padx=sc(12), pady=(sc(12), sc(8)))
            content = tk.Frame(group, bg=COLORS["surface"])
            content.pack(fill="x", padx=sc(12), pady=(0, sc(12)))
            return content

        def make_chk(parent, text, var, color_bar=None):
            f = tk.Frame(parent, bg=COLORS["surface"])
            f.pack(fill="x", pady=sc(2))
            chk = tk.Checkbutton(f, variable=var, bg=COLORS["surface"], activebackground=COLORS["surface"], selectcolor=COLORS["surface"], bd=0, highlightthickness=0, command=ui.update_filter_button_text, cursor="hand2")
            chk.pack(side="left")
            if color_bar:
                tk.Frame(f, bg=color_bar, width=4, height=sc(12)).pack(side="left", padx=(sc(4), sc(8)))
            lbl = tk.Label(f, text=text, font=FONT_DATA, fg=COLORS["on_surface"], bg=COLORS["surface"])
            lbl.pack(side="left", padx=(0, sc(8)))
            all_widgets.append((text.lower(), f, COLORS["surface"]))
            return chk

        def make_tristate_row(parent, text, var, color_bar=None):
            f = tk.Frame(parent, bg=COLORS["surface"], cursor="hand2")
            f.pack(fill="x", pady=sc(3))

            box_btn = tk.Label(
                f, text=" ", font=("JetBrains Mono", sc(11), "bold"),
                width=3, height=1, relief="solid", bd=1,
                bg=COLORS["surface"], fg=COLORS["outline"], cursor="hand2"
            )
            box_btn.pack(side="left", padx=(0, sc(6)))

            if color_bar:
                tk.Frame(f, bg=color_bar, width=4, height=sc(14)).pack(side="left", padx=(0, sc(8)))

            lbl = tk.Label(f, text=text, font=FONT_DATA, fg=COLORS["on_surface"], bg=COLORS["surface"], cursor="hand2")
            lbl.pack(side="left", padx=(0, sc(8)))

            badge = tk.Label(f, text="IGNORE", font=("JetBrains Mono", sc(9), "bold"), fg=COLORS["outline"], bg=COLORS["surface_container_low"], width=9, padx=sc(6), pady=sc(1), relief="flat")
            badge.pack(side="right", padx=sc(4))

            def update_visual():
                raw = var.get() if hasattr(var, "get") else "Ignore"
                val = str(raw).strip().lower()
                if val in ("has", "true", "1"):
                    box_btn.config(text="✓", fg=COLORS["secondary"], bg="#e8f5e9", highlightbackground=COLORS["secondary"], bd=1)
                    badge.config(text="HAS (✓)", fg="#2e7d32", bg="#e8f5e9")
                elif val in ("not", "false", "-1"):
                    box_btn.config(text="−", fg=COLORS["error"], bg="#ffebee", highlightbackground=COLORS["error"], bd=1)
                    badge.config(text="NOT (−)", fg="#c93a40", bg="#ffebee")
                else:
                    box_btn.config(text=" ", fg=COLORS["outline"], bg=COLORS["surface"], highlightbackground=COLORS["outline"], bd=1)
                    badge.config(text="IGNORE", fg=COLORS["outline"], bg=COLORS["surface_container_low"])

            def cycle_state(delta=1, event=None):
                states = ["Ignore", "Has", "Not"]
                curr = var.get() if hasattr(var, "get") else "Ignore"
                curr_normalized = "Has" if curr in ("Has", "HAS", True, 1) else ("Not" if curr in ("Not", "NOT", "-1") else "Ignore")
                idx = states.index(curr_normalized) if curr_normalized in states else 0
                next_state = states[(idx + delta) % len(states)]
                var.set(next_state)
                update_visual()
                ui.update_filter_button_text()
                return "break"

            for w in (f, box_btn, lbl, badge):
                w.bind("<Button-1>", lambda e: cycle_state(1, e))
                w.bind("<Button-3>", lambda e: cycle_state(-1, e))

            update_visual()
            all_widgets.append((text.lower(), f, COLORS["surface"]))
            return f

        # TAB 1: STATUS
        tab_status = tk.Frame(tab_content_area, bg=COLORS["surface"])
        ui.filter_tabs["status"] = tab_status

        status_left = tk.Frame(tab_status, bg=COLORS["surface"])
        status_left.pack(side="left", fill="both", expand=True, padx=sc(16), pady=sc(16))
        status_right = tk.Frame(tab_status, bg=COLORS["surface"])
        status_right.pack(side="right", fill="both", expand=True, padx=sc(16), pady=sc(16))

        p_status = create_group(status_left, "Processing Status")
        make_tristate_row(p_status, "Reviewed", ui.filter_vars["Reviewed"], COLORS["secondary"])
        make_tristate_row(p_status, "Has Suggestions from Books", ui.filter_vars["Has_History"], COLORS["outline_variant"])
        if "Has_Unvalidated" in ui.filter_vars:
            make_tristate_row(p_status, "Has Unvalidated Source", ui.filter_vars["Has_Unvalidated"], COLORS["outline_variant"])

        m_pres = create_group(status_right, "Metadata Presence")
        tk.Label(m_pres, text="Comments", font=FONT_LABEL, fg=COLORS["on_surface_variant"], bg=COLORS["surface"]).pack(anchor="w")
        tk.Frame(m_pres, bg=COLORS["outline"], height=1).pack(fill="x", pady=sc(4))
        make_tristate_row(m_pres, "Has Comment", ui.filter_vars["Has_Comment"])

        tk.Label(m_pres, text="Location Notes", font=FONT_LABEL, fg=COLORS["on_surface_variant"], bg=COLORS["surface"]).pack(anchor="w", pady=(sc(12), 0))
        tk.Frame(m_pres, bg=COLORS["outline"], height=1).pack(fill="x", pady=sc(4))
        make_tristate_row(m_pres, "Has Location Comment", ui.filter_vars["Has_Location_Comment"])

        if "Search_Old_Taxonomy" in ui.filter_vars:
            t_hist = create_group(status_right, "Taxonomy Audit Log Search")
            make_tristate_row(t_hist, "Search Old Taxonomy", ui.filter_vars["Search_Old_Taxonomy"], COLORS["surface_tint"])
            if hasattr(ui, "search_old_taxonomy_var"):
                ent_old_tax = ttk.Entry(t_hist, textvariable=ui.search_old_taxonomy_var)
                ent_old_tax.pack(fill="x", pady=(sc(4), 0))
                all_widgets.append(("old taxonomy", ent_old_tax, COLORS["surface"]))

        # TAB 2: PROBLEMS
        tab_probs = tk.Frame(tab_content_area, bg=COLORS["surface"])
        ui.filter_tabs["problems"] = tab_probs

        probs_canvas = tk.Canvas(tab_probs, bg=COLORS["surface"], highlightthickness=0, bd=0)
        probs_scrollbar = tk.Scrollbar(tab_probs, orient="vertical", command=probs_canvas.yview)
        probs_inner = tk.Frame(probs_canvas, bg=COLORS["surface"])

        probs_inner.bind("<Configure>", lambda e: probs_canvas.configure(scrollregion=probs_canvas.bbox("all")))
        probs_canvas_window = probs_canvas.create_window((0, 0), window=probs_inner, anchor="nw")
        probs_canvas.bind("<Configure>", lambda e: probs_canvas.itemconfig(probs_canvas_window, width=e.width) if getattr(probs_canvas, "_last_width", None) != e.width and not setattr(probs_canvas, "_last_width", e.width) else None)
        probs_canvas.configure(yscrollcommand=probs_scrollbar.set)

        probs_canvas.pack(side="left", fill="both", expand=True, padx=(sc(16), 0), pady=sc(16))
        probs_scrollbar.pack(side="right", fill="y", pady=sc(16))

        def _on_prob_scroll(event):
            probs_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        if hasattr(ui, "_bind_canvas_mousewheel"):
            ui.root.after(100, lambda: ui._bind_canvas_mousewheel(probs_canvas, _on_prob_scroll))

        prob_categories = getattr(ui, "problem_categories", {})

        # 1. Taxonomy & Scientific Identity
        tax_problems = [p for p in ui.problem_columns if prob_categories.get(p) == "taxonomy"]
        if tax_problems:
            g_tax = create_group(probs_inner, "🧬 Taxonomy & Scientific Identity")
            for col in tax_problems:
                make_tristate_row(g_tax, col.replace("_", " "), ui.filter_vars.get(col), COLORS["error"])

        # 2. Collection Event & Provenance
        col_problems = [p for p in ui.problem_columns if prob_categories.get(p) == "collection"]
        if col_problems:
            g_col = create_group(probs_inner, "📦 Collection Event & Provenance")
            for col in col_problems:
                make_tristate_row(g_col, col.replace("_", " "), ui.filter_vars.get(col), "#d9a036")

        # 3. Physical Object & Storage
        phys_problems = [p for p in ui.problem_columns if prob_categories.get(p) == "physical"]
        if phys_problems:
            g_phys = create_group(probs_inner, "🏷️ Physical Object & Storage")
            for col in phys_problems:
                bar_col = COLORS["outline"] if "PlantPart" in col else "#795548"
                make_tristate_row(g_phys, col.replace("_", " "), ui.filter_vars.get(col), bar_col)

        # 4. Other Discrepancies
        other_problems = [p for p in ui.problem_columns if prob_categories.get(p) not in ("taxonomy", "collection", "physical", "media") and "Image" not in p]
        if other_problems:
            g_oth = create_group(probs_inner, "📝 Other Discrepancies")
            for col in other_problems:
                make_tristate_row(g_oth, col.replace("_", " "), ui.filter_vars.get(col), COLORS["outline_variant"])

        # Fallback if no categorized problems found
        if not tax_problems and not col_problems and not phys_problems and not other_problems:
            p_list = create_group(probs_inner, "Problems Checklist")
            normal_problems = [p for p in ui.problem_columns if "Image" not in p]
            for col in normal_problems:
                make_tristate_row(p_list, col.replace("_", " "), ui.filter_vars.get(col), COLORS["error"])

        # Global Problem & History Filters
        g_glob = create_group(probs_inner, "Global Aggregates & History")
        make_tristate_row(g_glob, "Any problem (all error flags)", ui.filter_vars.get("Any_Problem"), COLORS["error"])

        if "Historical_Data" in ui.filter_vars:
            make_tristate_row(g_glob, "Historical Data (Has / No History)", ui.filter_vars.get("Historical_Data"), COLORS["surface_tint"])

        u_list = create_group(probs_inner, "Archival Gaps (Ukjent)")
        if "Unknown" in ui.filter_vars:
            make_tristate_row(u_list, "Any settled 'Ukjent' field", ui.filter_vars["Unknown"], color_bar="#d9a036")
        if "Needs_ICEDIG_Review" in ui.filter_vars:
            make_tristate_row(u_list, "Needs ICEDIG Review", ui.filter_vars["Needs_ICEDIG_Review"], color_bar="#d9a036")
        if "Has_ICEDIG_Code" in ui.filter_vars:
            make_tristate_row(u_list, "Has ICEDIG Code", ui.filter_vars["Has_ICEDIG_Code"], color_bar="#3a7d44")

        if hasattr(ui, "unknown_columns"):
            for col in ui.unknown_columns:
                if col in ui.filter_vars:
                    clean_name = col.replace("_Unknown", " Unknown").replace("_", " ")
                    make_tristate_row(u_list, clean_name, ui.filter_vars[col], color_bar="#d9a036")

        # TAB 3: HISTORICAL & BOOKS
        tab_hist = tk.Frame(tab_content_area, bg=COLORS["surface"])
        ui.filter_tabs["historical"] = tab_hist

        hist_canvas = tk.Canvas(tab_hist, bg=COLORS["surface"], highlightthickness=0, bd=0)
        hist_scrollbar = tk.Scrollbar(tab_hist, orient="vertical", command=hist_canvas.yview)
        hist_inner = tk.Frame(hist_canvas, bg=COLORS["surface"])

        hist_inner.bind("<Configure>", lambda e: hist_canvas.configure(scrollregion=hist_canvas.bbox("all")))
        hist_canvas_window = hist_canvas.create_window((0, 0), window=hist_inner, anchor="nw")
        hist_canvas.bind("<Configure>", lambda e: hist_canvas.itemconfig(hist_canvas_window, width=e.width) if getattr(hist_canvas, "_last_width", None) != e.width and not setattr(hist_canvas, "_last_width", e.width) else None)
        hist_canvas.configure(yscrollcommand=hist_scrollbar.set)

        hist_canvas.pack(side="left", fill="both", expand=True, padx=(sc(16), 0), pady=sc(16))
        hist_scrollbar.pack(side="right", fill="y", pady=sc(16))

        def _on_hist_scroll(event):
            hist_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        if hasattr(ui, "_bind_canvas_mousewheel"):
            ui.root.after(100, lambda: ui._bind_canvas_mousewheel(hist_canvas, _on_hist_scroll))

        tk.Label(
            hist_inner,
            text="Query active registry records and attached archival historical ledger books.",
            font=("Segoe UI", sc(9.5)),
            fg=COLORS["on_surface_variant"],
            bg=COLORS["surface"],
            anchor="w"
        ).pack(fill="x", pady=(0, sc(12)))

        c_group = create_group(hist_inner, "Historical & Ledger Search Criteria")
        fields = [
            ("Genus", "e.g. Quercus, Pinus"),
            ("Species", "e.g. alba, sylvestris"),
            ("Author", "e.g. L., Michx."),
            ("Family", "e.g. Fagaceae, Pinaceae"),
            ("Collector", "e.g. Dahl, Ove or Smith, John"),
            ("Locality", "e.g. Finmarken, Alta, Ridge"),
            ("Year", "e.g. 1895, 1924"),
        ]

        first_hist_entry = None
        for fld_name, placeholder in fields:
            f_row = tk.Frame(c_group, bg=COLORS["surface"])
            f_row.pack(fill="x", pady=sc(3))
            tk.Label(
                f_row,
                text=f"{fld_name}:",
                font=FONT_LABEL,
                fg=COLORS["on_surface"],
                bg=COLORS["surface"],
                width=12,
                anchor="w"
            ).pack(side="left", padx=sc(8))

            ent_frame = tk.Frame(f_row, bg=COLORS["surface"], highlightbackground=COLORS["outline_variant"], highlightthickness=1)
            ent_frame.pack(side="left", fill="x", expand=True, padx=(0, sc(8)))

            ent = tk.Entry(
                ent_frame,
                textvariable=ui.filter_historical_vars[fld_name],
                font=FONT_DATA,
                bg=COLORS["surface"],
                fg=COLORS["on_surface"],
                bd=0,
                insertbackground=COLORS["primary"]
            )
            ent.pack(fill="x", expand=True, padx=sc(6), pady=sc(3))
            ent.bind("<Return>", lambda e: FilterDialogController.apply_filter_with_history(ui, win))
            if first_hist_entry is None:
                first_hist_entry = ent
            all_widgets.append((fld_name.lower(), f_row, COLORS["surface"]))

        ui.filter_first_hist_entry = first_hist_entry

        opt_group = create_group(hist_inner, "Query Scope & Matching Logic")
        opt_row = tk.Frame(opt_group, bg=COLORS["surface"])
        opt_row.pack(fill="x", pady=sc(4))

        # Scope
        scope_col = tk.Frame(opt_row, bg=COLORS["surface"])
        scope_col.pack(side="left", fill="both", expand=True, padx=(0, sc(12)))

        tk.Label(scope_col, text="SEARCH SCOPE", font=FONT_LABEL, fg=COLORS["on_surface_variant"], bg=COLORS["surface"]).pack(anchor="w", pady=(0, sc(4)))
        tk.Radiobutton(scope_col, text="Both (Current & Books)", variable=ui.filter_historical_vars["scope"], value="both", font=FONT_DATA, bg=COLORS["surface"], fg=COLORS["on_surface"], activebackground=COLORS["surface"], highlightthickness=0, cursor="hand2", command=ui.update_filter_button_text).pack(anchor="w", pady=sc(1))
        tk.Radiobutton(scope_col, text="Historical Books Only", variable=ui.filter_historical_vars["scope"], value="suggestions_only", font=FONT_DATA, bg=COLORS["surface"], fg=COLORS["on_surface"], activebackground=COLORS["surface"], highlightthickness=0, cursor="hand2", command=ui.update_filter_button_text).pack(anchor="w", pady=sc(1))
        tk.Radiobutton(scope_col, text="Current Values Only", variable=ui.filter_historical_vars["scope"], value="current", font=FONT_DATA, bg=COLORS["surface"], fg=COLORS["on_surface"], activebackground=COLORS["surface"], highlightthickness=0, cursor="hand2", command=ui.update_filter_button_text).pack(anchor="w", pady=sc(1))

        tk.Frame(opt_row, bg=COLORS["outline_variant"], width=1).pack(side="left", fill="y", padx=sc(8))

        # Logic
        logic_col = tk.Frame(opt_row, bg=COLORS["surface"])
        logic_col.pack(side="left", fill="both", expand=True, padx=(sc(12), 0))

        tk.Label(logic_col, text="MATCH LOGIC", font=FONT_LABEL, fg=COLORS["on_surface_variant"], bg=COLORS["surface"]).pack(anchor="w", pady=(0, sc(4)))
        tk.Radiobutton(logic_col, text="Match ALL fields (AND)", variable=ui.filter_historical_vars["match_all"], value=True, font=FONT_DATA, bg=COLORS["surface"], fg=COLORS["on_surface"], activebackground=COLORS["surface"], highlightthickness=0, cursor="hand2").pack(anchor="w", pady=sc(1))
        tk.Radiobutton(logic_col, text="Match ANY field (OR)", variable=ui.filter_historical_vars["match_all"], value=False, font=FONT_DATA, bg=COLORS["surface"], fg=COLORS["on_surface"], activebackground=COLORS["surface"], highlightthickness=0, cursor="hand2").pack(anchor="w", pady=sc(1))

        act_group = create_group(hist_inner, "Execution & Preview")
        act_box = tk.Frame(act_group, bg=COLORS["surface"])
        act_box.pack(fill="x", pady=sc(4))

        hist_status_lbl = tk.Label(
            act_box,
            text="Enter search criteria above and click 'Apply Filter' (Ctrl+Enter) to query and filter.",
            font=("Segoe UI", sc(9)),
            fg=COLORS["on_surface_variant"],
            bg=COLORS["surface"],
            anchor="w"
        )
        hist_status_lbl.pack(side="left", fill="x", expand=True)

        hist_preview_btn = tk.Button(
            act_box,
            text="Run Ledger Search Only",
            font=FONT_LABEL,
            fg=COLORS["on_surface"],
            bg=COLORS["surface_container_highest"],
            bd=1,
            relief="solid",
            padx=sc(10),
            pady=sc(3),
            cursor="hand2"
        )
        hist_preview_btn.pack(side="right", padx=(sc(8), 0))

        def _do_preview_search():
            crit = {fld: ui.filter_historical_vars[fld].get().strip() for fld, _ in fields if ui.filter_historical_vars[fld].get().strip()}
            if not crit:
                hist_status_lbl.config(text="Please enter at least one search term (e.g. Genus, Collector).", fg=COLORS["error"])
                return
            hist_status_lbl.config(text="Querying records and attached historical ledger books...", fg=COLORS["primary"])
            hist_preview_btn.config(state="disabled")

            def _th():
                from backend.search import execute_advanced_historical_search
                try:
                    res = execute_advanced_historical_search(
                        df_reg=ui.app.df_reg,
                        historical_dbs=getattr(ui.app, "historical_dbs", None),
                        field_criteria=crit,
                        scope=ui.filter_historical_vars["scope"].get(),
                        match_all=bool(ui.filter_historical_vars["match_all"].get())
                    )
                    count = len(res)
                    def _update_ui():
                        if win.winfo_exists():
                            hist_status_lbl.config(text=f"Found {count} matching specimen(s). Click 'Apply Filter' to isolate.", fg=COLORS["secondary"])
                            hist_preview_btn.config(state="normal")
                    win.after(0, _update_ui)
                except Exception as ex:
                    def _err():
                        if win.winfo_exists():
                            hist_status_lbl.config(text=f"Error: {ex}", fg=COLORS["error"])
                            hist_preview_btn.config(state="normal")
                    win.after(0, _err)

            threading.Thread(target=_th, daemon=True).start()

        hist_preview_btn.config(command=_do_preview_search)

        # TAB 4: IMAGES
        tab_imgs = tk.Frame(tab_content_area, bg=COLORS["surface"])
        ui.filter_tabs["images"] = tab_imgs

        img_inner = tk.Frame(tab_imgs, bg=COLORS["surface"])
        img_inner.pack(fill="both", expand=True, padx=sc(16), pady=sc(16))

        i_list = create_group(img_inner, "Images Checklist")
        image_filters = ["Has_Images"]
        image_problems = [p for p in ui.problem_columns if "Image" in p]
        for col in image_filters + image_problems:
            if col in ui.filter_vars:
                clean_name = col.replace("_", " ")
                bar_color = COLORS["error"] if "Missing" in col or "Problem" in col else COLORS["botanical_green"]
                make_tristate_row(i_list, clean_name, ui.filter_vars[col], bar_color)

        # TAB 5: LOCATION
        tab_loc = tk.Frame(tab_content_area, bg=COLORS["surface"])
        ui.filter_tabs["location"] = tab_loc

        loc_canvas = tk.Canvas(tab_loc, bg=COLORS["surface"], highlightthickness=0, bd=0)
        loc_scrollbar = tk.Scrollbar(tab_loc, orient="vertical", command=loc_canvas.yview)
        loc_inner = tk.Frame(loc_canvas, bg=COLORS["surface"])

        loc_inner.bind("<Configure>", lambda e: loc_canvas.configure(scrollregion=loc_canvas.bbox("all")))
        loc_canvas_window = loc_canvas.create_window((0, 0), window=loc_inner, anchor="nw")
        loc_canvas.bind("<Configure>", lambda e: loc_canvas.itemconfig(loc_canvas_window, width=e.width) if getattr(loc_canvas, "_last_width", None) != e.width and not setattr(loc_canvas, "_last_width", e.width) else None)
        loc_canvas.configure(yscrollcommand=loc_scrollbar.set)

        loc_canvas.pack(side="left", fill="both", expand=True, padx=(sc(16), 0), pady=sc(16))
        loc_scrollbar.pack(side="right", fill="y", pady=sc(16))

        l_group = create_group(loc_inner, "Location Fields")
        loc_fields = ui.app.config.get("ui_sections", {}).get("location", [])

        style = ttk.Style(win)
        style.configure("Flat.TCombobox", fieldbackground=COLORS["surface"], background=COLORS["surface"], borderwidth=0)

        if not hasattr(ui, "filter_location_vars"):
            ui.filter_location_vars = {}

        for field in loc_fields:
            name = field["name"]
            ftype = field.get("type", "text")
            if name not in ui.filter_location_vars:
                ui.filter_location_vars[name] = tk.StringVar()

            f = tk.Frame(l_group, bg=COLORS["surface"])
            f.pack(fill="x", pady=sc(4))
            tk.Label(f, text=name, font=FONT_LABEL, fg=COLORS["on_surface"], bg=COLORS["surface"], width=20, anchor="w").pack(side="left", padx=sc(8))

            ent_frame = tk.Frame(f, bg=COLORS["surface"], highlightbackground=COLORS["outline"], highlightthickness=1)
            ent_frame.pack(side="left", fill="x", expand=True, padx=(0, sc(8)))

            if ftype in ("choice", "checkbox"):
                vals = [""] + list(field.get("choices", [])) if ftype == "choice" else ["", "True", "False"]
                cb = ttk.Combobox(ent_frame, textvariable=ui.filter_location_vars[name], values=vals, state="readonly", style="Flat.TCombobox", cursor="hand2")
                cb.pack(fill="x", expand=True, padx=sc(2), pady=sc(2))
                cb.bind("<BackSpace>", lambda e, w=cb: (w.set(""), ui.update_filter_button_text()))
                cb.bind("<Delete>", lambda e, w=cb: (w.set(""), ui.update_filter_button_text()))
            else:
                ent = tk.Entry(ent_frame, textvariable=ui.filter_location_vars[name], font=FONT_DATA, bg=COLORS["surface"], fg=COLORS["on_surface"], bd=0, insertbackground=COLORS["primary"])
                ent.pack(fill="x", expand=True, padx=sc(4), pady=sc(2))

            all_widgets.append((name.lower(), f, COLORS["surface"]))

        # Cache children for Quick Search
        for text, frame, orig_bg in all_widgets:
            cached = []
            for child in frame.winfo_children():
                if isinstance(child, tk.Frame) and child.cget("width") == 4:
                    continue
                cached.append(child)
            frame._cached_children = cached

        def on_search(*args):
            q = search_var.get().lower().strip()
            for text, frame, orig_bg in all_widgets:
                if not q:
                    bg_color = orig_bg
                elif q in text:
                    bg_color = COLORS["surface_container_highest"]
                else:
                    bg_color = orig_bg

                frame.config(bg=bg_color)
                for child in getattr(frame, "_cached_children", []):
                    try:
                        child.config(bg=bg_color)
                    except Exception:
                        pass

        search_var.trace("w", on_search)

        # Show requested tab
        show_tab(initial_tab)
        if initial_tab == "historical" and first_hist_entry:
            win.after(100, lambda: first_hist_entry.focus_set())

        # FOOTER ACTION BAR
        footer = tk.Frame(main_container, bg=COLORS["surface_container_low"], height=sc(56))
        footer.pack(fill="x", side="bottom")
        footer.pack_propagate(False)
        tk.Frame(footer, bg=COLORS["outline"], height=1).pack(fill="x", side="top")

        tk.Button(footer, text="Reset All", font=FONT_LABEL, fg=COLORS["error"], bg=COLORS["surface_container_low"], bd=0, relief="flat", cursor="hand2", command=lambda: FilterDialogController.clear_filter(ui, win)).pack(side="left", padx=sc(16), pady=sc(12))

        right_footer = tk.Frame(footer, bg=COLORS["surface_container_low"])
        right_footer.pack(side="right", fill="y", padx=sc(16))

        tk.Button(right_footer, text="Cancel", font=FONT_LABEL, fg=COLORS["on_surface"], bg=COLORS["surface"], bd=1, relief="solid", padx=sc(16), pady=sc(4), cursor="hand2", command=win.destroy).pack(side="left", padx=sc(8), pady=sc(12))

        apply_btn = tk.Button(right_footer, text="Apply Filter  |  Ctrl+Enter", font=FONT_LABEL, fg=COLORS["on_primary"], bg=COLORS["botanical_green"], bd=0, relief="flat", padx=sc(16), pady=sc(4), cursor="hand2", command=lambda: FilterDialogController.apply_filter_with_history(ui, win))
        apply_btn.pack(side="left", pady=sc(12))

        all_inputs = []
        for tab_name, frame in ui.filter_tabs.items():
            for group in frame.winfo_children():
                if isinstance(group, tk.Frame) and group.cget("highlightbackground") == COLORS["outline"]:
                    content = group.winfo_children()[-1]
                    for item_frame in content.winfo_children():
                        for child in item_frame.winfo_children():
                            if isinstance(child, (tk.Checkbutton, tk.Radiobutton, tk.Entry, ttk.Combobox)):
                                all_inputs.append(child)
        ui._filter_widgets = all_inputs
        ui._filter_index = 0

        utils.center_and_fit_toplevel(win, sc(860), sc(680))

    @staticmethod
    def apply_filter_with_history(ui, win):
        """Execute historical search if criteria populated, then apply standard filters with intersection."""
        criteria = {}
        if hasattr(ui, "filter_historical_vars"):
            for fld in ["Genus", "Species", "Author", "Family", "Collector", "Locality", "Year"]:
                if fld in ui.filter_historical_vars:
                    txt = ui.filter_historical_vars[fld].get().strip()
                    if txt:
                        criteria[fld] = txt

        if not criteria:
            ui._filter_history_matched_oids = None
            ui.apply_filter(win)
            return

        from backend.search import execute_advanced_historical_search
        scope = ui.filter_historical_vars.get("scope", tk.StringVar(value="both")).get()
        match_all = bool(ui.filter_historical_vars.get("match_all", tk.BooleanVar(value=True)).get())
        hist_dbs = getattr(ui.app, "historical_dbs", None)

        try:
            matched_oids = execute_advanced_historical_search(
                df_reg=ui.app.df_reg,
                historical_dbs=hist_dbs,
                field_criteria=criteria,
                scope=scope,
                match_all=match_all,
            )
            ui._filter_history_matched_oids = set(str(x) for x in matched_oids)
        except Exception as exc:
            messagebox.showerror("Historical Search Error", f"An error occurred during historical search:\n{exc}", parent=win)
            return

        ui.apply_filter(win)

    @staticmethod
    def save_filter_preset(ui):
        """Prompt the user and save current filter settings to filter_presets.json."""
        from tkinter import simpledialog
        name = simpledialog.askstring("Save Preset", "Enter preset name:", parent=ui.filter_window)
        if name:
            vars_to_save = {}
            for k, v in ui.filter_vars.items():
                if isinstance(v, tk.StringVar):
                    val = v.get().strip()
                    if val.lower() in ("has", "not"):
                        vars_to_save[k] = val
                elif isinstance(v, tk.BooleanVar) and v.get():
                    vars_to_save[k] = True

            hist_to_save = {}
            if hasattr(ui, "filter_historical_vars"):
                for k in ["Genus", "Species", "Author", "Family", "Collector", "Locality", "Year"]:
                    if k in ui.filter_historical_vars:
                        val = ui.filter_historical_vars[k].get().strip()
                        if val:
                            hist_to_save[k] = val
                scope_val = ui.filter_historical_vars.get("scope")
                if scope_val and scope_val.get() != "both":
                    hist_to_save["scope"] = scope_val.get()
                match_val = ui.filter_historical_vars.get("match_all")
                if match_val and not match_val.get():
                    hist_to_save["match_all"] = False

            preset = {
                "vars": vars_to_save,
                "locs": {k: v.get() for k, v in ui.filter_location_vars.items() if v.get()},
                "historical": hist_to_save,
                "mode": "AND"
            }
            prefs_dir = os.path.dirname(getattr(config, "_PREFS_PATH", "user_prefs.json"))
            presets_file = os.path.join(prefs_dir, "filter_presets.json")
            try:
                if os.path.exists(presets_file):
                    with open(presets_file, "r", encoding="utf-8") as f:
                        data = json.load(f)
                else:
                    data = {}
                data[name] = preset
                with open(presets_file, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=2)
                if hasattr(ui, "show_banner"):
                    ui.show_banner(f"Saved preset '{name}'", "success")
            except Exception as e:
                if hasattr(ui, "show_banner"):
                    ui.show_banner(f"Failed to save preset: {e}", "error")

    @staticmethod
    def load_filter_preset(ui):
        """Open preset picker and apply chosen preset."""
        from config import sc
        import utils
        prefs_dir = os.path.dirname(getattr(config, "_PREFS_PATH", "user_prefs.json"))
        presets_file = os.path.join(prefs_dir, "filter_presets.json")
        if not os.path.exists(presets_file):
            if hasattr(ui, "show_banner"):
                ui.show_banner("No presets saved yet.", "info")
            return

        with open(presets_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        if not data:
            if hasattr(ui, "show_banner"):
                ui.show_banner("No presets saved yet.", "info")
            return

        win = tk.Toplevel(ui.filter_window if hasattr(ui, "filter_window") and ui.filter_window and ui.filter_window.winfo_exists() else ui.root)
        win.title("Load Preset")
        win.resizable(True, True)
        win.transient(ui.root)

        is_dark = getattr(ui, "dark_mode_active", False)
        bg_color = "#181c19" if is_dark else "#fbfaf8"
        fg_color = "#e8ebe9" if is_dark else "#2c302e"
        fg_muted = "#a6adc8" if is_dark else "#757d77"
        border_color = "#2c302e" if is_dark else "#dadada"
        list_bg = "#111412" if is_dark else "#ffffff"
        btn_primary_bg = "#3a7d44" if is_dark else "#2c302e"
        btn_primary_hover = "#4b9e57" if is_dark else "#3d4240"
        btn_sec_bg = bg_color
        btn_sec_fg = fg_color
        btn_sec_hover = "#242a25" if is_dark else "#e9ece5"

        win.configure(bg=bg_color)
        utils.center_and_fit_toplevel(win, sc(380), sc(440))
        win.bind("<Escape>", lambda e: win.destroy())

        frame = tk.Frame(win, bg=bg_color, padx=sc(16), pady=sc(14))
        frame.pack(fill="both", expand=True)

        # Header Title
        hdr_frame = tk.Frame(frame, bg=bg_color)
        hdr_frame.pack(fill="x", pady=(0, sc(12)))

        tk.Label(
            hdr_frame,
            text="LOAD FILTER PRESET",
            font=("Segoe UI", sc(11), "bold"),
            fg=fg_color,
            bg=bg_color
        ).pack(anchor="w")

        tk.Label(
            hdr_frame,
            text=f"Select a preset ({len(data)} available) to apply:",
            font=("Segoe UI", sc(9)),
            fg=fg_muted,
            bg=bg_color
        ).pack(anchor="w", pady=(sc(2), 0))

        tk.Frame(hdr_frame, bg=border_color, height=1).pack(fill="x", pady=(sc(8), 0))

        # List Container with 1px border
        list_container = tk.Frame(frame, bg=list_bg, bd=1, relief="solid", highlightbackground=border_color, highlightthickness=1)
        list_container.pack(fill="both", expand=True, pady=(0, sc(12)))

        lb = tk.Listbox(
            list_container,
            bg=list_bg,
            fg=fg_color,
            font=("Segoe UI", sc(10)),
            selectbackground="#3a7d44",
            selectforeground="#ffffff",
            activestyle="none",
            relief="flat",
            bd=0,
            highlightthickness=0
        )
        sb = ttk.Scrollbar(list_container, orient="vertical", command=lb.yview)
        lb.configure(yscrollcommand=sb.set)

        lb.pack(side="left", fill="both", expand=True, padx=sc(4), pady=sc(4))
        sb.pack(side="right", fill="y")

        for k in data.keys():
            lb.insert("end", k)
        if lb.size() > 0:
            lb.selection_set(0)

        def on_load():
            sel = lb.curselection()
            if not sel:
                return
            name = lb.get(sel[0])
            preset = data[name]

            FilterDialogController.clear_filter(ui, getattr(ui, "filter_window", None), destroy_win=False)

            for k, v in preset.get("vars", {}).items():
                mapped_k = k
                if k == "Images_Missing":
                    mapped_k = "Has_Images"
                    if str(v).lower() in ("has", "true", "1"):
                        v = "Not"
                    elif str(v).lower() in ("not", "false", "-1"):
                        v = "Has"
                elif k == "Not_Reviewed":
                    mapped_k = "Reviewed"
                    if str(v).lower() in ("has", "true", "1"):
                        v = "Not"
                    elif str(v).lower() in ("not", "false", "-1"):
                        v = "Has"
                elif k == "Comment_Not_Empty":
                    mapped_k = "Has_Comment"
                elif k == "Comment_Empty":
                    mapped_k = "Has_Comment"
                    if str(v).lower() in ("has", "true", "1"):
                        v = "Not"
                    elif str(v).lower() in ("not", "false", "-1"):
                        v = "Has"
                elif k == "Extra_Not_Empty":
                    mapped_k = "Has_Location_Comment"
                elif k == "Extra_Empty":
                    mapped_k = "Has_Location_Comment"
                    if str(v).lower() in ("has", "true", "1"):
                        v = "Not"
                    elif str(v).lower() in ("not", "false", "-1"):
                        v = "Has"

                if mapped_k in ui.filter_vars:
                    target_var = ui.filter_vars[mapped_k]
                    if isinstance(target_var, tk.StringVar):
                        if str(v).lower() in ("has", "true", "1"):
                            target_var.set("Has")
                        elif str(v).lower() in ("not", "false", "-1"):
                            target_var.set("Not")
                        else:
                            target_var.set("Ignore")
                    elif isinstance(target_var, tk.BooleanVar):
                        target_var.set(bool(v))

            for k, v in preset.get("locs", {}).items():
                if k in ui.filter_location_vars:
                    ui.filter_location_vars[k].set(v)

            hist_preset = preset.get("historical", {})
            if hasattr(ui, "filter_historical_vars"):
                for k in ["Genus", "Species", "Author", "Family", "Collector", "Locality", "Year"]:
                    if k in ui.filter_historical_vars:
                        ui.filter_historical_vars[k].set(hist_preset.get(k, ""))
                if "scope" in ui.filter_historical_vars:
                    ui.filter_historical_vars["scope"].set(hist_preset.get("scope", "both"))
                if "match_all" in ui.filter_historical_vars:
                    ui.filter_historical_vars["match_all"].set(hist_preset.get("match_all", True))

            if hasattr(ui, "filter_mode"):
                ui.filter_mode.set("AND")

            ui.update_filter_button_text()
            win.destroy()

        lb.bind("<Double-Button-1>", lambda e: on_load())
        lb.bind("<Return>", lambda e: on_load())

        footer = tk.Frame(frame, bg=bg_color)
        footer.pack(fill="x", side="bottom")

        load_btn = tk.Button(
            footer, text="LOAD PRESET",
            bg=btn_primary_bg, fg="#ffffff",
            font=("Segoe UI", sc(9.5), "bold"),
            relief="flat", bd=0, cursor="hand2",
            padx=sc(16), pady=sc(6),
            command=on_load
        )
        load_btn.pack(side="right")
        load_btn.bind("<Enter>", lambda e: load_btn.config(bg=btn_primary_hover))
        load_btn.bind("<Leave>", lambda e: load_btn.config(bg=btn_primary_bg))

        cancel_btn = tk.Button(
            footer, text="CANCEL",
            bg=btn_sec_bg, fg=btn_sec_fg,
            font=("Segoe UI", sc(9.5), "bold"),
            relief="flat", bd=0, cursor="hand2",
            padx=sc(12), pady=sc(5),
            highlightthickness=1,
            highlightbackground=border_color,
            highlightcolor=border_color,
            command=win.destroy
        )
        cancel_btn.pack(side="right", padx=(0, sc(10)))
        cancel_btn.bind("<Enter>", lambda e: cancel_btn.config(bg=btn_sec_hover))
        cancel_btn.bind("<Leave>", lambda e: cancel_btn.config(bg=btn_sec_bg))

    @staticmethod
    def filter_nav_down(ui, event=None):
        if not hasattr(ui, "_filter_widgets"):
            return
        total = len(ui._filter_widgets)
        if total == 0:
            return
        ui._filter_index = (ui._filter_index + 1) % total
        ui._filter_widgets[ui._filter_index].focus_set()
        return "break"

    @staticmethod
    def filter_nav_up(ui, event=None):
        if not hasattr(ui, "_filter_widgets"):
            return
        total = len(ui._filter_widgets)
        if total == 0:
            return
        ui._filter_index = (ui._filter_index - 1) % total
        ui._filter_widgets[ui._filter_index].focus_set()
        return "break"

    @staticmethod
    def filter_activate(ui, event=None):
        widget = ui.root.focus_get()
        try:
            widget.invoke()
        except Exception as e:
            debug_error("Suppressed Error", str(e))
        return "break"

    @staticmethod
    def clear_filter(ui, win, destroy_win=True):
        """Reset all filter checkboxes, location filters, and historical criteria."""
        for v in ui.filter_vars.values():
            if isinstance(v, tk.StringVar):
                v.set("Ignore")
            else:
                v.set(False)

        if hasattr(ui, "filter_mode"):
            ui.filter_mode.set("AND")

        for v in ui.filter_location_vars.values():
            v.set("")

        if hasattr(ui, "filter_historical_vars"):
            for k in ["Genus", "Species", "Author", "Family", "Collector", "Locality", "Year"]:
                if k in ui.filter_historical_vars:
                    ui.filter_historical_vars[k].set("")
            if "scope" in ui.filter_historical_vars:
                ui.filter_historical_vars["scope"].set("both")
            if "match_all" in ui.filter_historical_vars:
                ui.filter_historical_vars["match_all"].set(True)

        ui._filter_history_matched_oids = None
        ui.app.active_object_ids = list(ui.app.df_reg.index) if ui.app.df_reg is not None else []
        ui._list_dirty = True
        ui.refresh_list()
        ui.update_object_count()
        ui.update_filter_button_text()

        if hasattr(ui, "filter_status_label"):
            ui.filter_status_label.config(text="")

        if destroy_win and win and win.winfo_exists():
            win.destroy()
