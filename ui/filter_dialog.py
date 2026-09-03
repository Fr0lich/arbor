import json
import os
import tkinter as tk
from tkinter import ttk, messagebox
import config
from utils import debug_error


class FilterDialogController:
    """Controller and UI builder for the Filter Objects dialog and presets."""

    @staticmethod
    def open_filter_menu(ui):
        """Open or lift the main Filter Objects modal dialog."""
        if hasattr(ui, "filter_window") and ui.filter_window and ui.filter_window.winfo_exists():
            ui.filter_window.lift()
            ui.filter_window.focus_force()
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

        win = tk.Toplevel(ui.root)
        ui.filter_window = win
        win.title("Filter objects")
        win.geometry(f"{sc(800)}x{sc(600)}")
        win.configure(bg=COLORS["surface"])
        win.bind("<Destroy>", lambda e: setattr(ui, "filter_window", None) if e.widget == win else None)
        win.bind("<Escape>", lambda e: win.destroy())
        win.bind("<Control-Return>", lambda e: ui.apply_filter(win))

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
        tk.Frame(tab_nav, bg=COLORS["outline"], height=1).pack(fill="x", side="bottom")

        # Global Match Mode Toggle
        global_mode_frame = tk.Frame(tab_nav, bg=COLORS["surface_container_highest"])
        global_mode_frame.pack(side="right", fill="y", padx=sc(16))

        tk.Label(global_mode_frame, text="Match criteria:", font=FONT_LABEL, fg=COLORS["on_surface_variant"], bg=COLORS["surface_container_highest"]).pack(side="left", padx=(0, sc(8)))

        style = ttk.Style(ui.root)
        style.configure("GlobalMode.TCombobox", fieldbackground=COLORS["surface"], background=COLORS["surface"], borderwidth=0)

        def on_global_mode_change(event):
            val = global_mode_cb.get()
            if "ALL" in val.upper():
                ui.filter_mode.set("AND")
            else:
                ui.filter_mode.set("OR")
            ui.update_filter_button_text()

        current_mode = ui.filter_mode.get()
        cb_val = "All selected (AND)" if current_mode == "AND" else "Any selected (OR)"

        global_mode_cb = ttk.Combobox(global_mode_frame, values=["All selected (AND)", "Any selected (OR)"], state="readonly", width=18, style="GlobalMode.TCombobox", cursor="hand2")
        global_mode_cb.set(cb_val)
        global_mode_cb.pack(side="left", pady=sc(8))
        global_mode_cb.bind("<<ComboboxSelected>>", on_global_mode_change)

        tab_content_area = tk.Frame(main_container, bg=COLORS["surface"])
        tab_content_area.pack(fill="both", expand=True)

        ui.filter_tabs = {}
        ui.filter_tab_buttons = {}

        def show_tab(tab_name):
            for name, frame in ui.filter_tabs.items():
                frame.pack_forget()
            ui.filter_tabs[tab_name].pack(fill="both", expand=True)

            for name, btn_tuple in ui.filter_tab_buttons.items():
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
            ui.filter_tab_buttons[name] = (btn, bottom_border)

        create_tab_btn("status", "Status & General")
        create_tab_btn("problems", "Problems & Unknowns")
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

        # TAB 1: STATUS
        tab_status = tk.Frame(tab_content_area, bg=COLORS["surface"])
        ui.filter_tabs["status"] = tab_status

        status_left = tk.Frame(tab_status, bg=COLORS["surface"])
        status_left.pack(side="left", fill="both", expand=True, padx=sc(16), pady=sc(16))
        status_right = tk.Frame(tab_status, bg=COLORS["surface"])
        status_right.pack(side="right", fill="both", expand=True, padx=sc(16), pady=sc(16))

        p_status = create_group(status_left, "Processing Status")
        make_chk(p_status, "Reviewed", ui.filter_vars["Reviewed"], COLORS["secondary"])
        make_chk(p_status, "Not Reviewed (Pending)", ui.filter_vars["Not_Reviewed"], COLORS["surface_tint"])
        make_chk(p_status, "Reviewed + Has Problem (REV+ERR)", ui.filter_vars["Reviewed_With_Problem"], COLORS["error"])
        make_chk(p_status, "Problem + Has History", ui.filter_vars["Problem_With_History"], COLORS["error"])
        make_chk(p_status, "Has Suggestions from Books", ui.filter_vars["Has_History"], COLORS["outline_variant"])
        if "Has_Unvalidated" in ui.filter_vars:
            make_chk(p_status, "Has Unvalidated Source", ui.filter_vars["Has_Unvalidated"], COLORS["outline_variant"])

        m_pres = create_group(status_right, "Metadata Presence")
        tk.Label(m_pres, text="Comments", font=FONT_LABEL, fg=COLORS["on_surface_variant"], bg=COLORS["surface"]).pack(anchor="w")
        tk.Frame(m_pres, bg=COLORS["outline"], height=1).pack(fill="x", pady=sc(4))
        make_chk(m_pres, "Missing Comment", ui.filter_vars["Comment_Empty"])
        make_chk(m_pres, "Has Comment", ui.filter_vars["Comment_Not_Empty"])

        tk.Label(m_pres, text="Location Notes", font=FONT_LABEL, fg=COLORS["on_surface_variant"], bg=COLORS["surface"]).pack(anchor="w", pady=(sc(12), 0))
        tk.Frame(m_pres, bg=COLORS["outline"], height=1).pack(fill="x", pady=sc(4))
        make_chk(m_pres, "No Location Comment", ui.filter_vars["Extra_Empty"])
        make_chk(m_pres, "Has Location Comment", ui.filter_vars["Extra_Not_Empty"])

        if "Search_Old_Taxonomy" in ui.filter_vars:
            t_hist = create_group(status_right, "Taxonomy Audit Log Search")
            make_chk(t_hist, "Search Old Taxonomy", ui.filter_vars["Search_Old_Taxonomy"], COLORS["surface_tint"])
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

        p_list = create_group(probs_inner, "Problems Checklist")
        normal_problems = [p for p in ui.problem_columns if "Image" not in p]
        for col in normal_problems:
            make_chk(p_list, col.replace("_", " "), ui.filter_vars.get(col), COLORS["error"])
        make_chk(p_list, "Any problem (except images)", ui.filter_vars.get("Any_Problem"), COLORS["error"])

        u_list = create_group(probs_inner, "Unknown values")
        if not hasattr(ui, "filter_unknown_var"):
            ui.filter_unknown_var = tk.BooleanVar()
        make_chk(u_list, "Show objects with unknown fields", ui.filter_unknown_var)

        # TAB 3: IMAGES
        tab_imgs = tk.Frame(tab_content_area, bg=COLORS["surface"])
        ui.filter_tabs["images"] = tab_imgs

        img_inner = tk.Frame(tab_imgs, bg=COLORS["surface"])
        img_inner.pack(fill="both", expand=True, padx=sc(16), pady=sc(16))

        i_list = create_group(img_inner, "Images Checklist")
        image_filters = ["Images_Missing", "Has_Images"]
        image_problems = [p for p in ui.problem_columns if "Image" in p]
        for col in image_filters + image_problems:
            if col in ui.filter_vars:
                clean_name = col.replace("_", " ")
                bar_color = COLORS["error"] if "Missing" in col or "Problem" in col else COLORS["botanical_green"]
                make_chk(i_list, clean_name, ui.filter_vars[col], bar_color)

        # TAB 4: LOCATION
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

        style.configure("Flat.TCombobox", fieldbackground=COLORS["surface"], background=COLORS["surface"], borderwidth=0)

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

        show_tab("status")

        # FOOTER ACTION BAR
        footer = tk.Frame(main_container, bg=COLORS["surface_container_low"], height=sc(56))
        footer.pack(fill="x", side="bottom")
        footer.pack_propagate(False)
        tk.Frame(footer, bg=COLORS["outline"], height=1).pack(fill="x", side="top")

        tk.Button(footer, text="Reset All", font=FONT_LABEL, fg=COLORS["error"], bg=COLORS["surface_container_low"], bd=0, relief="flat", cursor="hand2", command=lambda: FilterDialogController.clear_filter(ui, win)).pack(side="left", padx=sc(16), pady=sc(12))

        right_footer = tk.Frame(footer, bg=COLORS["surface_container_low"])
        right_footer.pack(side="right", fill="y", padx=sc(16))

        tk.Button(right_footer, text="Cancel", font=FONT_LABEL, fg=COLORS["on_surface"], bg=COLORS["surface"], bd=1, relief="solid", padx=sc(16), pady=sc(4), cursor="hand2", command=win.destroy).pack(side="left", padx=sc(8), pady=sc(12))

        apply_btn = tk.Button(right_footer, text="Apply Filter  |  Ctrl+Enter", font=FONT_LABEL, fg=COLORS["on_primary"], bg=COLORS["botanical_green"], bd=0, relief="flat", padx=sc(16), pady=sc(4), cursor="hand2", command=lambda: ui.apply_filter(win))
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

        utils.center_and_fit_toplevel(win, sc(800), sc(600))

    @staticmethod
    def save_filter_preset(ui):
        """Prompt the user and save current filter settings to filter_presets.json."""
        from tkinter import simpledialog
        name = simpledialog.askstring("Save Preset", "Enter preset name:", parent=ui.filter_window)
        if name:
            preset = {
                "vars": {k: v.get() for k, v in ui.filter_vars.items() if isinstance(v, tk.BooleanVar) and v.get()},
                "locs": {k: v.get() for k, v in ui.filter_location_vars.items() if v.get()},
                "mode": ui.filter_mode.get()
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
            return

        win = tk.Toplevel(ui.filter_window)
        win.title("Load Preset")
        utils.center_and_fit_toplevel(win, 250, 300)

        lb = tk.Listbox(win)
        lb.pack(fill="both", expand=True, padx=10, pady=10)
        for k in data.keys():
            lb.insert("end", k)

        def on_load():
            sel = lb.curselection()
            if not sel:
                return
            name = lb.get(sel[0])
            preset = data[name]

            FilterDialogController.clear_filter(ui, ui.filter_window, destroy_win=False)

            for k, v in preset.get("vars", {}).items():
                if k in ui.filter_vars:
                    ui.filter_vars[k].set(v)
            for k, v in preset.get("locs", {}).items():
                if k in ui.filter_location_vars:
                    ui.filter_location_vars[k].set(v)

            legacy_modes = preset.get("modes", {})
            if "mode" in preset:
                ui.filter_mode.set(preset["mode"])
            elif legacy_modes:
                if any(m == "AND" for m in legacy_modes.values()):
                    ui.filter_mode.set("AND")
                else:
                    ui.filter_mode.set("OR")
            else:
                ui.filter_mode.set("AND")

            ui.update_filter_button_text()
            win.destroy()

        ttk.Button(win, text="Load", command=on_load, cursor="hand2").pack(pady=10)

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
        """Reset all filter checkboxes and location filters, updating list and status."""
        for v in ui.filter_vars.values():
            v.set(False)
        if hasattr(ui, "filter_unknown_var"):
            ui.filter_unknown_var.set(False)

        ui.filter_mode.set("AND")

        for v in ui.filter_location_vars.values():
            v.set("")

        ui.app.active_object_ids = list(ui.app.df_reg.index) if ui.app.df_reg is not None else []
        ui._list_dirty = True
        ui.refresh_list()
        ui.update_object_count()
        ui.update_filter_button_text()

        if hasattr(ui, "filter_status_label"):
            ui.filter_status_label.config(text="")

        if destroy_win and win and win.winfo_exists():
            win.destroy()
