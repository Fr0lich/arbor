import tkinter as tk
from tkinter import ttk
import pandas as pd

class ToggleSwitch(tk.Canvas):
    def __init__(self, parent, variable, command=None, width=42, height=22, ui_ref=None, **kwargs):
        from config import sc
        scaled_w = sc(width) if ui_ref else width
        scaled_h = sc(height) if ui_ref else height
        super().__init__(parent, width=scaled_w, height=scaled_h, highlightthickness=0, bd=0, **kwargs)
        self.variable = variable
        self.command = command
        self.ui_ref = ui_ref

        self.bind("<Button-1>", self._on_click)
        self.bind("<Configure>", lambda e: self.draw())
        self._trace_id = self.variable.trace_add("write", lambda *args: self.draw())

        self.draw()

    def _on_click(self, event=None):
        self.variable.set(not self.variable.get())
        if self.command:
            self.command()

    def draw(self):
        self.delete("all")
        w = self.winfo_width()
        h = self.winfo_height()
        if w <= 1:
            w = self.cget("width")
        if h <= 1:
            h = self.cget("height")

        try:
            w = int(w)
            h = int(h)
        except (ValueError, TypeError):
            w = 42
            h = 22

        is_dark = False
        if self.ui_ref and hasattr(self.ui_ref, "dark_mode_active"):
            is_dark = self.ui_ref.dark_mode_active

        val = self.variable.get()

        if is_dark:
            bg_canvas = "#1e1e2e"
            bg_active = "#a6e3a1"
            bg_inactive = "#313244"
            fg_knob_active = "#11111b"
            fg_knob_inactive = "#cdd6f4"
        else:
            bg_canvas = "#f3f3f3"
            bg_active = "#3b6934"
            bg_inactive = "#c4c7c7"
            fg_knob_active = "#ffffff"
            fg_knob_inactive = "#ffffff"

        self.configure(bg=bg_canvas)

        self.create_rectangle(0, 0, w, h, fill=bg_active if val else bg_inactive, outline="")

        pad = 2
        knob_size = h - pad * 2
        if val:
            x = w - pad - knob_size
            knob_color = fg_knob_active
        else:
            x = pad
            knob_color = fg_knob_inactive

        self.create_rectangle(x, pad, x + knob_size, pad + knob_size, fill=knob_color, outline="")

    def destroy(self):
        try:
            self.variable.trace_remove("write", self._trace_id)
        except Exception:
            pass
        super().destroy()

class TreeviewListboxWrapper(ttk.Frame):
    def __init__(self, parent, main_window, **kwargs):
        super().__init__(parent)
        self.main_window = main_window
        from config import sc

        # State tracking
        self.items_list = []      # list of oids in order
        self.items_set = set()    # fast lookup set
        self.item_data = {}       # oid -> {title, genus, species, reviewed, foreground, tags, ...}
        self.selected_iids = []   # list of selected oids
        self.focused_iid = None
        self._resize_job = None

        # Event binding storage
        self.custom_bindings = []

        # Create Treeview for Compact Mode
        self.tree = ttk.Treeview(self, columns=("Rev", "ID", "Genus", "Species"), show="headings", selectmode="extended")
        self.tree.heading("Rev", text="✔")
        self.tree.heading("ID", text="ID")
        self.tree.heading("Genus", text="Genus")
        self.tree.heading("Species", text="Species")

        self.tree.column("Rev", width=sc(28), minwidth=sc(28), stretch=False, anchor="center")
        self.tree.column("ID", width=sc(50), minwidth=sc(35), stretch=True)
        self.tree.column("Genus", width=sc(85), minwidth=sc(60), stretch=True)
        self.tree.column("Species", width=sc(85), minwidth=sc(60), stretch=True)

        # Bind double-click and selection for Treeview click
        self.tree.bind("<Button-1>", self._on_treeview_click)
        self.tree.bind("<<TreeviewSelect>>", self._on_treeview_select)

        # Create Scrollable Canvas for Detailed Mode
        self.canvas_container = ttk.Frame(self)
        self.canvas = tk.Canvas(self.canvas_container, highlightthickness=0)
        self.scrollable_frame = tk.Frame(self.canvas)

        self.scrollable_frame_window = self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")

        self.scrollable_frame.bind("<Configure>", self._on_frame_configure)
        self.canvas.bind("<Configure>", self._on_canvas_configure)

        # Mousewheel on canvas/frame
        self.canvas.bind("<Enter>", lambda e: self.canvas.bind_all("<MouseWheel>", self._on_mousewheel))
        self.canvas.bind("<Leave>", lambda e: self.canvas.unbind_all("<MouseWheel>"))
        self.scrollable_frame.bind("<Enter>", lambda e: self.canvas.bind_all("<MouseWheel>", self._on_mousewheel))
        self.scrollable_frame.bind("<Leave>", lambda e: self.canvas.unbind_all("<MouseWheel>"))

        # Keyboard Navigation bindings for Detailed Mode
        self.bind("<Up>", self._on_keypress_up)
        self.bind("<Down>", self._on_keypress_down)
        self.bind("<Return>", self._on_keypress_return)

        # Initial active view check
        self._trace_id = None
        if hasattr(self.main_window, "focus_mode_var"):
            self.focus_mode_var = self.main_window.focus_mode_var
            self._trace_id = self.focus_mode_var.trace_add("write", self._on_focus_mode_changed)
        else:
            self.focus_mode_var = None

        self.active_view = "compact"
        self.update_view_visibility()

    def _on_keypress_up(self, event):
        if self.active_view == "compact":
            return
        if not self.items_list:
            return "break"
        if not self.selected_iids:
            new_idx = 0
        else:
            try:
                curr_idx = self.items_list.index(self.selected_iids[0])
                new_idx = max(0, curr_idx - 1)
            except Exception:
                new_idx = 0
        self.selection_clear()
        self.selection_set(new_idx)
        self.see(new_idx)
        self.event_generate("<<ListboxSelect>>")
        return "break"

    def _on_keypress_down(self, event):
        if self.active_view == "compact":
            return
        if not self.items_list:
            return "break"
        if not self.selected_iids:
            new_idx = 0
        else:
            try:
                curr_idx = self.items_list.index(self.selected_iids[0])
                new_idx = min(len(self.items_list) - 1, curr_idx + 1)
            except Exception:
                new_idx = 0
        self.selection_clear()
        self.selection_set(new_idx)
        self.see(new_idx)
        self.event_generate("<<ListboxSelect>>")
        return "break"

    def _on_keypress_return(self, event):
        if self.active_view == "compact":
            return
        if hasattr(self.main_window, "_on_list_return"):
            self.main_window._on_list_return(event)
        return "break"

    def _on_focus_mode_changed(self, *args):
        self.update_view_visibility()
        if hasattr(self.main_window, "refresh_list"):
            self.main_window.refresh_list()

    def update_view_visibility(self):
        focus_active = self.focus_mode_var.get() if self.focus_mode_var else False
        is_dark = self.main_window.dark_mode_active if hasattr(self.main_window, "dark_mode_active") else False
        canvas_bg = "#1e1e2e" if is_dark else "#f3f3f3"
        self.canvas.configure(bg=canvas_bg)
        self.scrollable_frame.configure(bg=canvas_bg)

        if focus_active:
            # Compact view (Treeview)
            self.canvas_container.pack_forget()
            self.tree.pack(fill="both", expand=True)
            self.active_view = "compact"
        else:
            # Detailed view (Canvas Cards)
            self.tree.pack_forget()
            self.canvas_container.pack(fill="both", expand=True)
            self.canvas.pack(fill="both", expand=True)
            self.active_view = "detailed"

            # PERFORMANCE OPTIMIZATION (Bolt): Lazily build card widgets for all loaded items that do not have one yet
            for oid in self.items_list:
                if oid in self.item_data and "card_frame" not in self.item_data[oid]:
                    self._create_card_widget(oid)

        self._sync_view_selections()

    def _on_frame_configure(self, event):
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _on_canvas_configure(self, event):
        self._last_canvas_width = event.width
        if hasattr(self, "_resize_job") and self._resize_job:
            try:
                self.canvas.after_cancel(self._resize_job)
            except Exception:
                pass
        self._resize_job = self.canvas.after(100, self._deferred_canvas_configure)

    def _deferred_canvas_configure(self):
        self._resize_job = None
        if not self.winfo_exists():
            return
        width = getattr(self, "_last_canvas_width", self.canvas.winfo_width())
        try:
            self.canvas.itemconfig(self.scrollable_frame_window, width=width)
        except Exception:
            pass

    def _on_mousewheel(self, event):
        self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    def _on_treeview_click(self, event):
        region = self.tree.identify_region(event.x, event.y)
        if region == "cell":
            column = self.tree.identify_column(event.x)
            if column == "#1":
                item_id = self.tree.identify_row(event.y)
                if item_id:
                    self.main_window._toggle_reviewed_for_id(item_id)
                    self.selection_clear()
                    self.selection_set(item_id)
                    return "break"

    def _on_treeview_select(self, event):
        tree_sel = self.tree.selection()
        if tree_sel:
            self.selected_iids = list(tree_sel)
            self.focused_iid = tree_sel[0]

    def _sync_view_selections(self):
        # Sync Treeview selection
        tree_sel = self.tree.selection()
        if set(tree_sel) != set(self.selected_iids):
            self.tree.selection_set(self.selected_iids)
        # Sync cards highlight in detailed mode
        if self.active_view == "detailed":
            self.redraw_cards_highlights()

    def redraw_cards_highlights(self):
        is_dark = self.main_window.dark_mode_active if hasattr(self.main_window, "dark_mode_active") else False
        bg_selected = "#e8f5e9" if not is_dark else "#3b4252"
        border_selected = "#3b6934" if not is_dark else "#a6e3a1"
        bg_normal = "#ffffff" if not is_dark else "#24273a"
        border_normal = "#e0e0e0" if not is_dark else "#494d64"

        for oid in self.items_list:
            if oid in self.item_data:
                card = self.item_data[oid].get("card_frame")
                if card and card.winfo_exists():
                    is_sel = oid in self.selected_iids
                    bg = bg_selected if is_sel else bg_normal
                    bd = border_selected if is_sel else border_normal
                    card.configure(bg=bg, highlightbackground=bd)
                    self._set_bg_recursive(card, bg)

    def _set_bg_recursive(self, widget, bg_color):
        if hasattr(widget, "is_badge") and widget.is_badge:
            return
        try:
            widget.configure(bg=bg_color)
        except Exception:
            pass
        for child in widget.winfo_children():
            self._set_bg_recursive(child, bg_color)

    def _on_card_click(self, oid, event=None):
        self.selected_iids = [oid]
        self.focused_iid = oid
        self._sync_view_selections()
        self.event_generate("<<ListboxSelect>>")

    def _on_card_double_click(self, oid, event):
        self._on_card_click(oid, event)
        if hasattr(self.main_window, "_on_list_double_click"):
            self.main_window._on_list_double_click(event)

    def _on_checkbox_click(self, oid, event):
        self.main_window._toggle_reviewed_for_id(oid)
        self.selection_clear()
        self.selection_set(oid)
        return "break"

    def _update_card_checkbox(self, oid):
        if oid in self.item_data:
            reviewed = self.item_data[oid].get("reviewed", False)
            rev_char = "☑" if reviewed else "☐"
            cb_lbl = self.item_data[oid].get("cb_label")
            is_dark = self.main_window.dark_mode_active if hasattr(self.main_window, "dark_mode_active") else False
            sec_text_color = "#6c757d" if not is_dark else "#a6adc8"
            cb_color = "#28a745" if reviewed else sec_text_color
            if cb_lbl and cb_lbl.winfo_exists():
                cb_lbl.configure(text=rev_char, fg=cb_color)

    def _create_badge(self, parent, text, bg, fg, border_color):
        from config import sc
        badge = tk.Label(
            parent,
            text=text,
            bg=bg,
            fg=fg,
            font=("Segoe UI", sc(8), "bold"),
            padx=sc(4),
            pady=sc(1),
            highlightthickness=1,
            highlightbackground=border_color,
            bd=0
        )
        badge.is_badge = True
        return badge

    def _create_card_widget(self, oid):
        # PERFORMANCE OPTIMIZATION (Bolt): Prevent duplicated widget creation
        if oid in self.item_data and "card_frame" in self.item_data[oid]:
            card_frame = self.item_data[oid]["card_frame"]
            if card_frame and card_frame.winfo_exists():
                return

        from config import sc
        is_dark = self.main_window.dark_mode_active if hasattr(self.main_window, "dark_mode_active") else False

        bg_color = "#ffffff" if not is_dark else "#24273a"
        border_color = "#e0e0e0" if not is_dark else "#494d64"
        text_color = "#000000" if not is_dark else "#cad3f5"
        sec_text_color = "#6c757d" if not is_dark else "#a5adcb"

        card = tk.Frame(
            self.scrollable_frame,
            bg=bg_color,
            highlightthickness=1,
            highlightbackground=border_color,
            bd=0,
            padx=sc(6),
            pady=sc(6)
        )
        card.pack(fill="x", padx=sc(4), pady=sc(3))
        self.item_data[oid]["card_frame"] = card

        # --- Top Line Frame ---
        top_line = tk.Frame(card, bg=bg_color)
        top_line.pack(fill="x", anchor="w")

        reviewed = self.item_data[oid].get("reviewed", False)
        rev_char = "☑" if reviewed else "☐"
        cb_color = "#28a745" if reviewed else sec_text_color

        cb_lbl = tk.Label(
            top_line,
            text=rev_char,
            bg=bg_color,
            fg=cb_color,
            font=("Segoe UI", sc(11), "bold"),
            cursor="hand2"
        )
        cb_lbl.pack(side="left", padx=(0, sc(4)))
        cb_lbl.bind("<Button-1>", lambda e, o=oid: self._on_checkbox_click(o, e))
        self.item_data[oid]["cb_label"] = cb_lbl

        genus = self.item_data[oid].get("genus", "")
        species = self.item_data[oid].get("species", "")
        tax_text = f"{genus} {species}".strip()
        if not tax_text:
            tax_text = "Unknown Specimen"

        tax_lbl = tk.Label(
            top_line,
            text=tax_text,
            bg=bg_color,
            fg=text_color,
            font=("Segoe UI", sc(9), "italic bold"),
            anchor="w"
        )
        tax_lbl.pack(side="left", padx=(0, sc(4)))
        self.item_data[oid]["tax_label"] = tax_lbl

        # Problem status badge (Amber)
        has_problem = self.main_window._get_cached_problem(oid) if hasattr(self.main_window, "_get_cached_problem") else False
        if has_problem:
            badge_bg = "#ffe0b2" if not is_dark else "#443622"
            badge_fg = "#e65100" if not is_dark else "#ffb74d"
            badge_bd = "#ffb74d" if not is_dark else "#ffe0b2"
            p_badge = self._create_badge(top_line, "Issue", badge_bg, badge_fg, badge_bd)
            p_badge.pack(side="left", padx=sc(2))

        # Loaned out status badge (Blue)
        loaned = False
        obs_df = self.main_window.app.df_obs
        if obs_df is not None and oid in obs_df.index:
            try:
                row = obs_df.loc[oid]
                if isinstance(row, pd.DataFrame):
                    row = row.iloc[0]
                loaned_raw = row.get("Loaned out", False)
                if isinstance(loaned_raw, str):
                    loaned = loaned_raw.strip().lower() == "true"
                else:
                    loaned = bool(loaned_raw)
            except Exception:
                pass

        if loaned:
            badge_bg = "#e3f2fd" if not is_dark else "#203040"
            badge_fg = "#0d47a1" if not is_dark else "#64b5f6"
            badge_bd = "#90caf9" if not is_dark else "#bbdefb"
            l_badge = self._create_badge(top_line, "Loaned Out", badge_bg, badge_fg, badge_bd)
            l_badge.pack(side="left", padx=sc(2))

        # --- Middle Line Frame ---
        mid_line = tk.Frame(card, bg=bg_color)
        mid_line.pack(fill="x", anchor="w", pady=(sc(2), 0))

        truncated_id = oid.split("-")[-1]
        id_lbl = tk.Label(
            mid_line,
            text=truncated_id,
            bg=bg_color,
            fg=text_color,
            font=("Segoe UI", sc(9), "bold")
        )
        id_lbl.pack(side="left", padx=(sc(16), sc(8)))
        self.item_data[oid]["id_label"] = id_lbl

        # Photo count
        photo_count = 0
        if self.main_window.app.df_photo is not None and oid in self.main_window.app.df_photo.index:
            try:
                photo_data = self.main_window.app.df_photo.loc[oid]
                if isinstance(photo_data, pd.DataFrame):
                    photo_count = len(photo_data)
                elif isinstance(photo_data, pd.Series):
                    photo_count = 1
            except Exception:
                pass

        local_count = 0
        if hasattr(self.main_window, "image_index"):
            local_count = len(self.main_window.image_index.get(oid, []))

        photo_count = max(local_count, photo_count)

        photo_lbl = tk.Label(
            mid_line,
            text=f"📷 {photo_count} photo{'s' if photo_count != 1 else ''}",
            bg=bg_color,
            fg=sec_text_color,
            font=("Segoe UI", sc(8))
        )
        photo_lbl.pack(side="left")

        # --- Bottom Line Frame ---
        bot_line = tk.Frame(card, bg=bg_color)
        bot_line.pack(fill="x", anchor="w", pady=(sc(2), 0))

        building = ""
        floor_room = ""
        stored_as_val = ""
        if obs_df is not None and oid in obs_df.index:
            try:
                row = obs_df.loc[oid]
                if isinstance(row, pd.DataFrame):
                    row = row.iloc[0]
                building = str(row.get("Building", "")).strip()
                floor = str(row.get("Floor", "")).strip()
                extra = str(row.get("Extra", "")).strip()
                stored_as = str(row.get("Stored as", "")).strip()
                cabinet = str(row.get("Cabinet", "")).strip()

                if building in ("nan", "None"): building = ""
                if floor in ("nan", "None"): floor = ""
                if extra in ("nan", "None"): extra = ""
                if stored_as in ("nan", "None"): stored_as = ""
                if cabinet in ("nan", "None"): cabinet = ""

                parts = []
                if floor:
                    parts.append(f"Floor {floor}")
                if extra:
                    parts.append(extra)
                floor_room = ", ".join(parts) if parts else ""

                parts_stored = []
                if stored_as:
                    parts_stored.append(stored_as)
                if cabinet:
                    parts_stored.append(f"Cab {cabinet}")
                stored_as_val = " / ".join(parts_stored) if parts_stored else ""
            except Exception:
                pass

        loc_parts = []
        if building:
            loc_parts.append(building)
        if floor_room:
            loc_parts.append(floor_room)
        if stored_as_val:
            loc_parts.append(stored_as_val)

        loc_text = " • ".join(loc_parts) if loc_parts else "No Location Info"

        loc_lbl = tk.Label(
            bot_line,
            text=loc_text,
            bg=bg_color,
            fg=sec_text_color,
            font=("Segoe UI", sc(8)),
            anchor="w",
            justify="left"
        )
        loc_lbl.pack(side="left", padx=(sc(16), 0), fill="x", expand=True)

        # Bind hover & selection on the entire card recursive
        self._bind_card_events(card, oid)

    def _bind_card_events(self, widget, oid):
        is_dark = self.main_window.dark_mode_active if hasattr(self.main_window, "dark_mode_active") else False

        def _on_enter(event):
            if oid not in self.selected_iids:
                hover_bg = "#f5f5f5" if not is_dark else "#2a2d42"
                self._set_bg_recursive(widget, hover_bg)

        def _on_leave(event):
            if oid not in self.selected_iids:
                normal_bg = "#ffffff" if not is_dark else "#24273a"
                self._set_bg_recursive(widget, normal_bg)

        widget.bind("<Enter>", _on_enter, add="+")
        widget.bind("<Leave>", _on_leave, add="+")
        widget.bind("<Button-1>", lambda e, o=oid: self._on_card_click(o, e), add="+")
        widget.bind("<Double-Button-1>", lambda e, o=oid: self._on_card_double_click(o, e), add="+")

        for seq, func, add in self.custom_bindings:
            if "Select" in seq or seq.startswith("<<"):
                continue
            widget.bind(seq, lambda e: func(e), add="+")

        for child in widget.winfo_children():
            if child != self.item_data[oid].get("cb_label"):
                self._bind_card_events_recursive(child, oid, _on_enter, _on_leave)

    def _bind_card_events_recursive(self, child, oid, on_enter, on_leave):
        child.bind("<Enter>", on_enter, add="+")
        child.bind("<Leave>", on_leave, add="+")
        child.bind("<Button-1>", lambda e, o=oid: self._on_card_click(o, e), add="+")
        child.bind("<Double-Button-1>", lambda e, o=oid: self._on_card_double_click(o, e), add="+")

        for seq, func, add in self.custom_bindings:
            if "Select" in seq or seq.startswith("<<"):
                continue
            child.bind(seq, lambda e: func(e), add="+")

        for grandchild in child.winfo_children():
            self._bind_card_events_recursive(grandchild, oid, on_enter, on_leave)

    def _apply_tags_to_card(self, oid):
        if oid in self.item_data:
            tags = self.item_data[oid].get("tags", [])
            card = self.item_data[oid].get("card_frame")
            if not card or not card.winfo_exists():
                return

            fg_color = None
            for t in tags:
                if t.startswith("color_"):
                    fg_color = "#" + t.split("_")[1]
                    break

            is_dark = self.main_window.dark_mode_active if hasattr(self.main_window, "dark_mode_active") else False
            default_color = "#000000" if not is_dark else "#cad3f5"
            target_color = fg_color if fg_color else default_color

            tax_lbl = self.item_data[oid].get("tax_label")
            id_lbl = self.item_data[oid].get("id_label")
            if tax_lbl and tax_lbl.winfo_exists():
                tax_lbl.configure(fg=target_color)
            if id_lbl and id_lbl.winfo_exists():
                id_lbl.configure(fg=target_color)

    def curselection(self):
        res = []
        for oid in self.selected_iids:
            if oid in self.items_list:
                res.append(self.items_list.index(oid))
        return res

    def selection_clear(self, first=0, last=None):
        self.selected_iids.clear()
        self.tree.selection_remove(*self.tree.selection())
        self._sync_view_selections()

    def selection_set(self, *args):
        if not args:
            return
        arg = args[0]
        if isinstance(arg, (int, float)):
            idx = int(arg)
            if 0 <= idx < len(self.items_list):
                self.selected_iids = [self.items_list[idx]]
        else:
            if len(args) == 1 and isinstance(args[0], (list, tuple)):
                self.selected_iids = [str(x) for x in args[0]]
            else:
                self.selected_iids = [str(x) for x in args]

        self._sync_view_selections()
        if self.selected_iids:
            self.see(self.selected_iids[0])

    def see(self, index_or_iid):
        if not self.items_list:
            return
        if isinstance(index_or_iid, (int, float)):
            idx = int(index_or_iid)
            if 0 <= idx < len(self.items_list):
                oid = self.items_list[idx]
            else:
                return
        else:
            oid = str(index_or_iid)

        if self.active_view == "compact":
            if oid in self.items_list:
                self.tree.see(oid)
        else:
            if oid in self.item_data:
                card = self.item_data[oid].get("card_frame")
                if card and card.winfo_exists():
                    self.scroll_to_widget(card)

    def scroll_to_widget(self, widget):
        self.canvas.update_idletasks()
        try:
            widget_y = widget.winfo_y()
            widget_h = widget.winfo_height()
            canvas_h = self.canvas.winfo_height()
            scroll_region = self.canvas.bbox("all")
            if scroll_region:
                total_h = scroll_region[3] - scroll_region[1]
                if total_h > canvas_h:
                    target_y = widget_y - (canvas_h / 2) + (widget_h / 2)
                    target_y = max(0, min(target_y, total_h - canvas_h))
                    self.canvas.yview_moveto(target_y / total_h)
        except Exception:
            pass

    def activate(self, index_or_iid):
        self.see(index_or_iid)
        if isinstance(index_or_iid, (int, float)):
            idx = int(index_or_iid)
            if 0 <= idx < len(self.items_list):
                self.focused_iid = self.items_list[idx]
        else:
            self.focused_iid = str(index_or_iid)

    def delete(self, first, last=None):
        self.items_list.clear()
        self.items_set.clear()
        self.selected_iids.clear()
        self.focused_iid = None
        children = self.tree.get_children()
        if children:
            self.tree.delete(*children)

        for oid in self.item_data:
            card = self.item_data[oid].get("card_frame")
            if card and card.winfo_exists():
                card.destroy()
        self.item_data.clear()

    def insert(self, index, title, genus=None, species=None, reviewed=None, bulk=False):
        oid = title.split(" ")[0].strip()
        if not bulk:
            if oid in self.items_set:
                try:
                    self.items_list.remove(oid)
                except ValueError:
                    pass
            else:
                self.items_set.add(oid)
        else:
            self.items_set.add(oid)

        self.items_list.append(oid)

        if not bulk and self.tree.exists(oid):
            try:
                self.tree.delete(oid)
            except Exception:
                pass

        rev_char = "☑" if reviewed else "☐"
        row_tag = "even" if len(self.items_list) % 2 == 0 else "odd"
        self.tree.insert("", "end", iid=oid, values=(rev_char, oid, genus or "", species or ""), tags=(row_tag,))

        self.item_data[oid] = {
            "title": title,
            "genus": genus or "",
            "species": species or "",
            "reviewed": bool(reviewed),
            "tags": [row_tag],
            "values": [rev_char, oid, genus or "", species or ""]
        }

        # PERFORMANCE OPTIMIZATION (Bolt): Only create card widget if we are actually in detailed view,
        # otherwise defer widget creation to avoid high CPU and memory overhead on database load.
        if self.active_view == "detailed":
            self._create_card_widget(oid)

    def itemconfig(self, index, **kwargs):
        foreground = kwargs.get("foreground")
        if not foreground:
            return

        tag_name = f"color_{foreground.replace('#', '')}"
        self.tag_configure(tag_name, foreground=foreground)

        if isinstance(index, (int, float)):
            idx = int(index)
            if 0 <= idx < len(self.items_list):
                oid = self.items_list[idx]
                current_tags = list(self.item(oid, "tags") or [])
                if tag_name not in current_tags:
                    current_tags.append(tag_name)
                    self.item(oid, tags=current_tags)
        else:
            # "end" or similar
            if self.items_list:
                oid = self.items_list[-1]
                current_tags = list(self.item(oid, "tags") or [])
                if tag_name not in current_tags:
                    current_tags.append(tag_name)
                    self.item(oid, tags=current_tags)

    def xview_moveto(self, fraction):
        pass

    def bind(self, sequence, func, add=None):
        if sequence == "<<ListboxSelect>>":
            sequence = "<<TreeviewSelect>>"
        bind_id = super().bind(sequence, func, add)
        self.custom_bindings.append((sequence, func, add))
        self.tree.bind(sequence, func, add)
        return bind_id

    def focus(self, item=None):
        if item is None:
            if self.active_view == "compact":
                return self.tree.focus()
            else:
                return self.focused_iid or ""
        else:
            oid = str(item)
            if self.active_view == "compact":
                self.tree.focus(oid)
            else:
                self.focused_iid = oid

    def item(self, item, option=None, **kwargs):
        oid = str(item)
        if self.active_view == "compact":
            return self.tree.item(oid, option, **kwargs)

        if oid not in self.item_data:
            self.item_data[oid] = {"tags": [], "values": [], "title": "", "genus": "", "species": "", "reviewed": False}

        if option == "tags":
            return self.item_data[oid].get("tags", [])
        if option == "values":
            reviewed = self.item_data[oid].get("reviewed", False)
            rev_char = "☑" if reviewed else "☐"
            genus = self.item_data[oid].get("genus", "")
            species = self.item_data[oid].get("species", "")
            return [rev_char, oid, genus, species]

        if "tags" in kwargs:
            self.item_data[oid]["tags"] = kwargs["tags"]
            self._apply_tags_to_card(oid)
        if "values" in kwargs:
            self.item_data[oid]["values"] = kwargs["values"]
            vals = kwargs["values"]
            if vals:
                self.item_data[oid]["reviewed"] = (vals[0] == "☑")
                self._update_card_checkbox(oid)

        if option is None and not kwargs:
            reviewed = self.item_data[oid].get("reviewed", False)
            rev_char = "☑" if reviewed else "☐"
            genus = self.item_data[oid].get("genus", "")
            species = self.item_data[oid].get("species", "")
            return {
                "tags": self.item_data[oid].get("tags", []),
                "values": [rev_char, oid, genus, species]
            }

    def identify_row(self, y):
        if self.active_view == "compact":
            return self.tree.identify_row(y)
        else:
            canvas_y = self.canvas.canvasy(y)
            for oid in self.items_list:
                card = self.item_data.get(oid, {}).get("card_frame")
                if card and card.winfo_exists():
                    y_start = card.winfo_y()
                    y_end = y_start + card.winfo_height()
                    if y_start <= canvas_y <= y_end:
                        return oid
            if self.selected_iids:
                return self.selected_iids[0]
            return ""

    def selection(self):
        if self.active_view == "compact":
            return self.tree.selection()
        else:
            return tuple(self.selected_iids)

    def tag_configure(self, tagname, **kwargs):
        self.tree.tag_configure(tagname, **kwargs)
        if not hasattr(self, "_tag_configs"):
            self._tag_configs = {}
        self._tag_configs[tagname] = kwargs
        for oid in self.items_list:
            if tagname in self.item_data.get(oid, {}).get("tags", []):
                self._apply_tags_to_card(oid)

    def yview(self, *args):
        if self.active_view == "compact":
            return self.tree.yview(*args)
        else:
            return self.canvas.yview(*args)

    def configure(self, **kwargs):
        if "yscrollcommand" in kwargs:
            yscroll = kwargs["yscrollcommand"]
            self.tree.configure(yscrollcommand=yscroll)
            self.canvas.configure(yscrollcommand=yscroll)
            del kwargs["yscrollcommand"]
        if kwargs:
            super().configure(**kwargs)

    def yview_scroll(self, number, what):
        if self.active_view == "compact":
            self.tree.yview_scroll(number, what)
        else:
            self.canvas.yview_scroll(number, what)

    def get_children(self, item=None):
        if item is not None:
            return ()
        return tuple(self.items_list)

    def focus_set(self):
        if self.active_view == "compact":
            self.tree.focus_set()
        else:
            self.canvas.focus_set()

    def destroy(self):
        if hasattr(self, "_resize_job") and self._resize_job:
            try:
                self.canvas.after_cancel(self._resize_job)
            except Exception:
                pass
        if self._trace_id and self.focus_mode_var:
            try:
                self.focus_mode_var.trace_remove("write", self._trace_id)
            except Exception:
                pass
        super().destroy()
