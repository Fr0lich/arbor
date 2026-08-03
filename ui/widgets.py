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

class TreeviewListboxWrapper(ttk.Treeview):
    def __init__(self, parent, main_window, **kwargs):
        self.main_window = main_window
        kwargs["columns"] = ("Rev", "ID", "Genus", "Species")
        kwargs["show"] = "headings"
        kwargs["selectmode"] = "extended"
        super().__init__(parent, **kwargs)

        self.heading("Rev", text="✔")
        self.heading("ID", text="ID")
        self.heading("Genus", text="Genus")
        self.heading("Species", text="Species")

        self.column("Rev", width=28, minwidth=28, stretch=False, anchor="center")
        self.column("ID", width=50, minwidth=35, stretch=True)
        self.column("Genus", width=85, minwidth=60, stretch=True)
        self.column("Species", width=85, minwidth=60, stretch=True)

        self.items_list = []
        self.bind("<Button-1>", self._on_treeview_click)

    def _on_treeview_click(self, event):
        region = self.identify_region(event.x, event.y)
        if region == "cell":
            column = self.identify_column(event.x)
            if column == "#1":
                item_id = self.identify_row(event.y)
                if item_id:
                    self.main_window._toggle_reviewed_for_id(item_id)
                    self.selection_clear()
                    self.selection_set(item_id)
                    return "break"

    def curselection(self):
        selection = self.selection()
        if not selection:
            return []
        res = []
        for item in selection:
            if item in self.items_list:
                res.append(self.items_list.index(item))
            else:
                children = list(self.get_children())
                if item in children:
                    res.append(children.index(item))
        return res

    def selection_clear(self, first, last=None):
        self.selection_remove(*self.selection())

    def selection_set(self, *args):
        if not args:
            return
        arg = args[0]
        if isinstance(arg, (int, float)):
            idx = int(arg)
            children = list(self.get_children())
            if 0 <= idx < len(children):
                item_id = children[idx]
                super().selection_set(item_id)
                self.focus(item_id)
        else:
            super().selection_set(*args)
            if isinstance(arg, str):
                self.focus(arg)

    def see(self, index):
        children = list(self.get_children())
        if 0 <= index < len(children):
            super().see(children[index])

    def activate(self, index):
        children = list(self.get_children())
        if 0 <= index < len(children):
            self.focus(children[index])

    def delete(self, first, last=None):
        self.selection_clear(0)
        children = self.get_children()
        if children:
            super().delete(*children)
        self.items_list.clear()

    def insert(self, index, title, genus=None, species=None, reviewed=None):
        # PERFORMANCE OPTIMIZATION (Bolt): Added reviewed parameter to bypass expensive DataFrame/pandas index
        # queries (O(1) with high pandas overhead) in large collection rendering loops.
        from repository import REVIEWED_COLUMN
        oid = title.split(" ")[0].strip()
        if genus is None or species is None:
            genus = ""
            species = ""
            if self.main_window.app.df_reg is not None and oid in self.main_window.app.df_reg.index:
                row = self.main_window.app.df_reg.loc[oid]
                if isinstance(row, pd.DataFrame):
                    row = row.iloc[0]
                genus = str(row.get("Genus", "")).strip()
                species = str(row.get("Species", "")).strip()
                if genus == "nan" or pd.isna(row.get("Genus")): genus = ""
                if species == "nan" or pd.isna(row.get("Species")): species = ""

        if reviewed is None:
            reviewed = False
            if self.main_window.app.df_obs is not None and oid in self.main_window.app.df_obs.index:
                try:
                    reviewed = bool(self.main_window.app.df_obs.loc[oid, REVIEWED_COLUMN])
                except Exception:
                    pass
        rev_char = "☑" if reviewed else "☐"

        row_tag = "even" if len(self.items_list) % 2 == 0 else "odd"
        item_id = super().insert("", "end", iid=oid, values=(rev_char, oid, genus, species), tags=(row_tag,))
        self.items_list.append(oid)

    def itemconfig(self, index, **kwargs):
        foreground = kwargs.get("foreground")
        if not foreground:
            return

        tag_name = f"color_{foreground.replace('#', '')}"
        self.tag_configure(tag_name, foreground=foreground)

        children = list(self.get_children())
        if index == "end" or index == tk.END:
            if children:
                target_item = children[-1]
            else:
                return
        else:
            if 0 <= index < len(children):
                target_item = children[index]
            else:
                return

        current_tags = list(self.item(target_item, "tags") or [])
        if tag_name not in current_tags:
            current_tags.append(tag_name)
            self.item(target_item, tags=current_tags)

    def xview_moveto(self, fraction):
        pass

    def bind(self, sequence, func, add=None):
        if sequence == "<<ListboxSelect>>":
            sequence = "<<TreeviewSelect>>"
        return super().bind(sequence, func, add)
