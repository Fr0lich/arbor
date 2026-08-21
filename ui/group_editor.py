import tkinter as tk
from tkinter import ttk, messagebox
import config

def sc(n):
    return config.sc(n)

class GroupEditorWindow:
    def __init__(self, parent, app, main_window):
        self.parent = parent
        self.app = app
        self.main_window = main_window

        self.win = tk.Toplevel(parent)
        self.win.title("Configure Registration Tabs")
        self.win.configure(bg="#fbfaf8")
        self.win.bind("<Escape>", lambda e: self.win.destroy())
        self.win.transient(parent)

        # Load current custom tabs or generate default
        self.load_tabs()

        self.setup_styles()
        self._build_ui()
        
        import utils
        utils.center_and_fit_toplevel(self.win, sc(640), sc(480))

        self.refresh_tabs_list()

    def setup_styles(self):
        style = ttk.Style()
        style.configure("FlatCard.TLabelframe", background="#ffffff", bordercolor="#d1d1d1", borderwidth=1, relief="solid")
        style.configure("FlatCard.TLabelframe.Label", font=("Hanken Grotesk", sc(11), "bold"), background="#ffffff", foreground="#2c302e")

    def load_tabs(self):
        prefs = config.load_prefs() or {}
        custom = prefs.get("custom_reg_tabs")
        import copy
        
        if custom:
            # Deep copy to allow rollback on Cancel
            self.groups = copy.deepcopy(custom)
        else:
            default = self.app.config.get("reg_groups", [])
            self.groups = copy.deepcopy(default)

        # Make sure Miscellaneous exists if needed
        all_fields = [f["name"] for f in self.app.config["ui_sections"]["registration"]]
        assigned_fields = set()
        for g in self.groups:
            assigned_fields.update(g.get("fields", []))
            
        misc = [f for f in all_fields if f not in assigned_fields]
        if misc:
            # Check if Miscellaneous is already in groups
            if not any(g["name"] == "Miscellaneous" for g in self.groups):
                self.groups.append({"name": "Miscellaneous", "fields": misc})

    def _create_card_frame(self, parent, title):
        outer = tk.Frame(parent, bg="#ffffff", highlightthickness=1, highlightbackground="#d1d1d1")
        hdr   = tk.Frame(outer, bg="#f2f5f1")
        hdr.pack(fill="x", side="top")
        tk.Label(hdr, text=title.upper(), font=("Hanken Grotesk", sc(11), "bold"),
                 bg="#f2f5f1", fg="#000000", anchor="w", padx=sc(10), pady=sc(6)).pack(fill="x")
        tk.Frame(outer, bg="#d1d1d1", height=1).pack(fill="x", side="top")          # separator
        content = tk.Frame(outer, bg="#ffffff", padx=sc(10), pady=sc(10))
        content.pack(fill="both", expand=True, side="top")
        return outer, content

    def _build_ui(self):
        main_frame = tk.Frame(self.win, bg="#fbfaf8", padx=sc(12), pady=sc(12))
        main_frame.pack(fill="both", expand=True)

        # Split Left/Right panes
        panes = tk.PanedWindow(main_frame, orient="horizontal", bg="#d1d1d1", bd=0, sashwidth=sc(4))
        panes.pack(fill="both", expand=True, pady=(0, sc(12)))

        # Left Column: Tabs List
        left_pane, left_content = self._create_card_frame(panes, "Tabs (Groups)")
        panes.add(left_pane, width=sc(260))

        self.tabs_listbox = tk.Listbox(
            left_content, font=("Hanken Grotesk", sc(10)),
            bg="#ffffff", fg="#2c302e", relief="solid", bd=1, highlightthickness=0,
            exportselection=False
        )
        self.tabs_listbox.pack(fill="both", expand=True, pady=(0, sc(8)))
        self.tabs_listbox.bind("<<ListboxSelect>>", self.on_tab_select)
        self.tabs_listbox.bind("<Button-3>", self.show_tabs_context_menu)
        self.tabs_listbox.bind("<Button-2>", self.show_tabs_context_menu)

        btn_tab_row = tk.Frame(left_content, bg="#ffffff")
        btn_tab_row.pack(fill="x")

        add_tab_btn = tk.Button(
            btn_tab_row, text="Add Tab", font=("Hanken Grotesk", sc(9)),
            bg="#ffffff", fg="#2c302e", relief="solid", bd=1, cursor="hand2", padx=sc(6), pady=sc(2),
            command=self.add_tab
        )
        add_tab_btn.pack(side="left", padx=(0, sc(4)))

        rename_tab_btn = tk.Button(
            btn_tab_row, text="Rename", font=("Hanken Grotesk", sc(9)),
            bg="#ffffff", fg="#2c302e", relief="solid", bd=1, cursor="hand2", padx=sc(6), pady=sc(2),
            command=self.rename_tab
        )
        rename_tab_btn.pack(side="left", padx=sc(4))

        del_tab_btn = tk.Button(
            btn_tab_row, text="Delete", font=("Hanken Grotesk", sc(9)),
            bg="#ffffff", fg="#c93a40", relief="solid", bd=1, cursor="hand2", padx=sc(6), pady=sc(2),
            command=self.delete_tab
        )
        del_tab_btn.pack(side="right")

        # Right Column: Fields inside Selected Tab
        right_pane, right_content = self._create_card_frame(panes, "Fields in Selected Tab")
        panes.add(right_pane, width=sc(340))

        self.fields_listbox = tk.Listbox(
            right_content, font=("JetBrains Mono", sc(10)),
            bg="#ffffff", fg="#2c302e", relief="solid", bd=1, highlightthickness=0
        )
        self.fields_listbox.pack(fill="both", expand=True, pady=(0, sc(8)))
        self.fields_listbox.bind("<Button-3>", self.show_fields_context_menu)
        self.fields_listbox.bind("<Button-2>", self.show_fields_context_menu)

        btn_field_row = tk.Frame(right_content, bg="#ffffff")
        btn_field_row.pack(fill="x")

        move_up_btn = tk.Button(
            btn_field_row, text="Move Up", font=("Hanken Grotesk", sc(9)),
            bg="#ffffff", fg="#2c302e", relief="solid", bd=1, cursor="hand2", padx=sc(6), pady=sc(2),
            command=lambda: self.move_field_order(-1)
        )
        move_up_btn.pack(side="left", padx=(0, sc(4)))

        move_down_btn = tk.Button(
            btn_field_row, text="Move Down", font=("Hanken Grotesk", sc(9)),
            bg="#ffffff", fg="#2c302e", relief="solid", bd=1, cursor="hand2", padx=sc(6), pady=sc(2),
            command=lambda: self.move_field_order(1)
        )
        move_down_btn.pack(side="left", padx=sc(4))

        move_to_btn = tk.Button(
            btn_field_row, text="Move to Tab...", font=("Hanken Grotesk", sc(9)),
            bg="#ffffff", fg="#2c302e", relief="solid", bd=1, cursor="hand2", padx=sc(6), pady=sc(2),
            command=self.move_field_to_tab
        )
        move_to_btn.pack(side="right")

        edit_field_row = tk.Frame(right_content, bg="#ffffff")
        edit_field_row.pack(fill="x", pady=(sc(4), 0))

        add_field_btn = tk.Button(
            edit_field_row, text="Add Field", font=("Hanken Grotesk", sc(9)),
            bg="#ffffff", fg="#2c302e", relief="solid", bd=1, cursor="hand2", padx=sc(6), pady=sc(2),
            command=self.add_field
        )
        add_field_btn.pack(side="left", padx=(0, sc(4)))

        rename_field_btn = tk.Button(
            edit_field_row, text="Rename Field", font=("Hanken Grotesk", sc(9)),
            bg="#ffffff", fg="#2c302e", relief="solid", bd=1, cursor="hand2", padx=sc(6), pady=sc(2),
            command=self.rename_field
        )
        rename_field_btn.pack(side="left", padx=sc(4))

        del_field_btn = tk.Button(
            edit_field_row, text="Delete Field", font=("Hanken Grotesk", sc(9)),
            bg="#ffffff", fg="#c93a40", relief="solid", bd=1, cursor="hand2", padx=sc(6), pady=sc(2),
            command=self.delete_field
        )
        del_field_btn.pack(side="right")

        # Pinned Actions at the bottom
        actions = tk.Frame(main_frame, bg="#fbfaf8")
        actions.pack(fill="x")

        save_btn = tk.Button(
            actions, text="Save Settings", font=("Hanken Grotesk", sc(10), "bold"),
            bg="#2c302e", fg="#ffffff", relief="flat", bd=0, cursor="hand2", padx=sc(16), pady=sc(6),
            command=self.save_settings
        )
        save_btn.pack(side="right", padx=sc(4))

        cancel_btn = tk.Button(
            actions, text="Cancel", font=("Hanken Grotesk", sc(10)),
            bg="#ffffff", fg="#2c302e", relief="solid", bd=1, cursor="hand2", padx=sc(12), pady=sc(5),
            command=self.win.destroy
        )
        cancel_btn.pack(side="left")

    def refresh_tabs_list(self):
        self.tabs_listbox.delete(0, tk.END)
        for g in self.groups:
            self.tabs_listbox.insert(tk.END, g["name"])
        
        # Select first tab
        if self.groups:
            self.tabs_listbox.selection_set(0)
            self.on_tab_select(None)

    def get_selected_group_idx(self):
        sel = self.tabs_listbox.curselection()
        if not sel:
            return None
        return sel[0]

    def on_tab_select(self, event):
        idx = self.get_selected_group_idx()
        if idx is None:
            self.fields_listbox.delete(0, tk.END)
            return

        self.fields_listbox.delete(0, tk.END)
        fields = self.groups[idx].get("fields", [])
        for f in fields:
            self.fields_listbox.insert(tk.END, f)

    def add_tab(self):
        from tkinter import simpledialog
        name = simpledialog.askstring("Add Tab", "Enter new tab name:", parent=self.win)
        if not name or not name.strip():
            return
        
        name = name.strip()
        if any(g["name"].lower() == name.lower() for g in self.groups):
            messagebox.showerror("Conflict", "A tab with this name already exists.", parent=self.win)
            return

        self.groups.append({"name": name, "fields": []})
        self.refresh_tabs_list()
        
        # Select the newly created tab
        self.tabs_listbox.selection_clear(0, tk.END)
        self.tabs_listbox.selection_set(tk.END)
        self.on_tab_select(None)

    def rename_tab(self):
        idx = self.get_selected_group_idx()
        if idx is None:
            return
            
        old_name = self.groups[idx]["name"]
        if old_name == "Miscellaneous":
            messagebox.showwarning("System Tab", "The Miscellaneous tab cannot be renamed.", parent=self.win)
            return

        from tkinter import simpledialog
        name = simpledialog.askstring("Rename Tab", f"Rename tab '{old_name}' to:", parent=self.win)
        if not name or not name.strip() or name.strip() == old_name:
            return
            
        name = name.strip()
        if any(g["name"].lower() == name.lower() for g in self.groups):
            messagebox.showerror("Conflict", "A tab with this name already exists.", parent=self.win)
            return

        self.groups[idx]["name"] = name
        self.refresh_tabs_list()
        self.tabs_listbox.selection_set(idx)

    def delete_tab(self):
        idx = self.get_selected_group_idx()
        if idx is None:
            return
            
        group = self.groups[idx]
        if group["name"] == "Miscellaneous":
            messagebox.showwarning("System Tab", "The Miscellaneous tab cannot be deleted.", parent=self.win)
            return

        # If tab is empty, delete immediately
        if not group.get("fields"):
            if not messagebox.askyesno("Delete Tab", f"Delete empty tab '{group['name']}'?", parent=self.win):
                return
            self.groups.pop(idx)
            self.refresh_tabs_list()
            return

        # Tab has fields — open the Move & Delete dialog
        self._open_move_and_delete_dialog(idx)

    def _open_move_and_delete_dialog(self, src_idx):
        src_group = self.groups[src_idx]
        dest_choices = [g["name"] for i, g in enumerate(self.groups) if i != src_idx]

        if not dest_choices:
            messagebox.showerror(
                "No Destination",
                "There are no other tabs to move fields into. Create another tab first.",
                parent=self.win
            )
            return

        dialog = tk.Toplevel(self.win)
        dialog.title(f"Delete Tab: {src_group['name']}")
        dialog.configure(bg="#fbfaf8")
        dialog.transient(self.win)
        dialog.grab_set()

        import utils
        utils.center_and_fit_toplevel(dialog, sc(420), sc(380))

        # --- Header ---
        hdr = tk.Frame(dialog, bg="#fbfaf8")
        hdr.pack(fill="x", padx=sc(14), pady=(sc(12), sc(4)))
        tk.Label(
            hdr, text=f"Move fields from  \"{src_group['name']}\"  before deleting",
            font=("Hanken Grotesk", sc(10)), bg="#fbfaf8", fg="#2c302e", anchor="w"
        ).pack(fill="x")

        # --- Destination selector ---
        dest_row = tk.Frame(dialog, bg="#fbfaf8")
        dest_row.pack(fill="x", padx=sc(14), pady=(sc(4), sc(8)))
        tk.Label(dest_row, text="Move into tab:", font=("Hanken Grotesk", sc(9.5)), bg="#fbfaf8", fg="#444748").pack(side="left")
        dest_var = tk.StringVar(value=dest_choices[0])
        dest_cb = ttk.Combobox(dest_row, textvariable=dest_var, values=dest_choices, state="readonly",
                               font=("Hanken Grotesk", sc(10)), width=20, cursor="hand2")
        dest_cb.pack(side="left", padx=sc(8))

        # --- Fields list with reorder ---
        list_frame = tk.Frame(dialog, bg="#ffffff", highlightthickness=1, highlightbackground="#d1d1d1")
        list_frame.pack(fill="both", expand=True, padx=sc(14), pady=(0, sc(8)))

        list_hdr = tk.Frame(list_frame, bg="#f2f5f1")
        list_hdr.pack(fill="x")
        tk.Label(list_hdr, text="FIELD ORDER (will be appended to destination)", font=("Hanken Grotesk", sc(9), "bold"),
                 bg="#f2f5f1", fg="#444748", anchor="w", padx=sc(8), pady=sc(5)).pack(fill="x")
        tk.Frame(list_frame, bg="#d1d1d1", height=1).pack(fill="x")

        inner = tk.Frame(list_frame, bg="#ffffff")
        inner.pack(fill="both", expand=True, padx=sc(6), pady=sc(6))

        # Working copy of fields to allow reordering
        working_fields = list(src_group.get("fields", []))

        lbox = tk.Listbox(
            inner, font=("JetBrains Mono", sc(10)),
            bg="#ffffff", fg="#2c302e", relief="flat", bd=0,
            highlightthickness=0, selectbackground="#e9ece5", selectforeground="#2c302e"
        )
        lbox.pack(side="left", fill="both", expand=True)

        sb = ttk.Scrollbar(inner, orient="vertical", command=lbox.yview)
        sb.pack(side="right", fill="y")
        lbox.configure(yscrollcommand=sb.set)

        def refresh_lbox():
            lbox.delete(0, tk.END)
            for f in working_fields:
                lbox.insert(tk.END, f)

        refresh_lbox()

        # Reorder buttons
        btn_col = tk.Frame(list_frame, bg="#f2f5f1")
        btn_col.pack(fill="x")
        tk.Frame(btn_col, bg="#d1d1d1", height=1).pack(fill="x")
        btn_inner = tk.Frame(btn_col, bg="#f2f5f1")
        btn_inner.pack(fill="x", padx=sc(6), pady=sc(4))

        def move_item(direction):
            sel = lbox.curselection()
            if not sel:
                return
            i = sel[0]
            j = i + direction
            if 0 <= j < len(working_fields):
                working_fields[i], working_fields[j] = working_fields[j], working_fields[i]
                refresh_lbox()
                lbox.selection_set(j)

        tk.Button(
            btn_inner, text="▲ Move Up", font=("Hanken Grotesk", sc(9)),
            bg="#ffffff", fg="#2c302e", relief="solid", bd=1, cursor="hand2", padx=sc(6), pady=sc(2),
            command=lambda: move_item(-1)
        ).pack(side="left", padx=(0, sc(4)))

        tk.Button(
            btn_inner, text="▼ Move Down", font=("Hanken Grotesk", sc(9)),
            bg="#ffffff", fg="#2c302e", relief="solid", bd=1, cursor="hand2", padx=sc(6), pady=sc(2),
            command=lambda: move_item(1)
        ).pack(side="left")

        # --- Footer buttons ---
        footer = tk.Frame(dialog, bg="#fbfaf8")
        footer.pack(fill="x", padx=sc(14), pady=(0, sc(12)))

        def commit():
            dest_name = dest_var.get()
            dest_group = next((g for g in self.groups if g["name"] == dest_name), None)
            if dest_group is None:
                return
            # Append reordered fields to destination
            dest_group.setdefault("fields", []).extend(working_fields)
            # Delete source tab
            self.groups.pop(src_idx)
            dialog.destroy()
            self.refresh_tabs_list()
            # Select the destination tab
            dest_new_idx = next((i for i, g in enumerate(self.groups) if g["name"] == dest_name), 0)
            self.tabs_listbox.selection_clear(0, tk.END)
            self.tabs_listbox.selection_set(dest_new_idx)
            self.on_tab_select(None)

        tk.Button(
            footer, text="Move & Delete Tab", font=("Hanken Grotesk", sc(10), "bold"),
            bg="#c93a40", fg="#ffffff", activebackground="#8b1313", activeforeground="#ffffff",
            relief="flat", bd=0, cursor="hand2", padx=sc(14), pady=sc(6),
            command=commit
        ).pack(side="right", padx=sc(4))

        tk.Button(
            footer, text="Cancel", font=("Hanken Grotesk", sc(10)),
            bg="#ffffff", fg="#2c302e", relief="solid", bd=1, cursor="hand2", padx=sc(12), pady=sc(5),
            command=dialog.destroy
        ).pack(side="left")

    def refresh_tabs_list(self):
        self.tabs_listbox.delete(0, tk.END)
        for g in self.groups:
            self.tabs_listbox.insert(tk.END, g["name"])
        
        # Select first tab if nothing selected
        if self.groups and not self.tabs_listbox.curselection():
            self.tabs_listbox.selection_set(0)
            self.on_tab_select(None)

    def move_field_order(self, direction):
        g_idx = self.get_selected_group_idx()
        if g_idx is None:
            return
            
        f_sel = self.fields_listbox.curselection()
        if not f_sel:
            return
            
        f_idx = f_sel[0]
        fields = self.groups[g_idx]["fields"]
        
        new_idx = f_idx + direction
        if 0 <= new_idx < len(fields):
            # Swap
            fields[f_idx], fields[new_idx] = fields[new_idx], fields[f_idx]
            
            # Refresh fields
            self.on_tab_select(None)
            self.fields_listbox.selection_set(new_idx)

    def move_field_to_tab(self):
        g_idx = self.get_selected_group_idx()
        if g_idx is None:
            return
            
        f_sel = self.fields_listbox.curselection()
        if not f_sel:
            return
            
        f_idx = f_sel[0]
        field_name = self.groups[g_idx]["fields"][f_idx]

        # Choose destination tab via temporary Top dialog
        dest_win = tk.Toplevel(self.win)
        dest_win.title("Move Field")
        dest_win.configure(bg="#fbfaf8")
        dest_win.transient(self.win)
        
        tk.Label(
            dest_win, text=f"Move field '{field_name}' to tab:",
            font=("Hanken Grotesk", sc(10)), bg="#fbfaf8", fg="#2c302e"
        ).pack(pady=sc(8), padx=sc(12))
        
        choices = [g["name"] for i, g in enumerate(self.groups) if i != g_idx]
        if not choices:
            messagebox.showinfo("No Destination", "No other tabs exist to move this field to.", parent=self.win)
            dest_win.destroy()
            return
            
        choice_var = tk.StringVar(value=choices[0])
        cb = ttk.Combobox(dest_win, textvariable=choice_var, values=choices, font=("Hanken Grotesk", sc(10)), state="readonly", cursor="hand2")
        cb.pack(pady=sc(6), padx=sc(12))
        
        def do_move():
            dest_name = choice_var.get()
            dest_group = next(g for g in self.groups if g["name"] == dest_name)
            
            # Remove from current
            self.groups[g_idx]["fields"].pop(f_idx)
            # Add to destination
            dest_group.setdefault("fields", []).append(field_name)
            
            self.on_tab_select(None)
            dest_win.destroy()
            
        tk.Button(
            dest_win, text="Move", font=("Hanken Grotesk", sc(10), "bold"),
            bg="#2c302e", fg="#ffffff", relief="flat", bd=0, cursor="hand2", padx=sc(12), pady=sc(4),
            command=do_move
        ).pack(pady=sc(8))
        
        import utils
        utils.center_and_fit_toplevel(dest_win, sc(300), sc(180))

    def save_settings(self):
        # Save to prefs
        prefs = config.load_prefs() or {}
        prefs["custom_reg_tabs"] = self.groups
        config.save_prefs(prefs)
        
        messagebox.showinfo("Saved", "Tab configuration saved. Rebuilding workspace...", parent=self.win)
        
        # Trigger rebuild in main window
        self.main_window.build_sections()
        self.main_window.update_problems_default_view()
        self.main_window.update_reg_fields_visibility()
        
        self.win.destroy()

    def show_tabs_context_menu(self, event):
        idx = self.tabs_listbox.nearest(event.y)
        if idx >= 0:
            self.tabs_listbox.selection_clear(0, tk.END)
            self.tabs_listbox.selection_set(idx)
            self.on_tab_select(None)
            
            menu = tk.Menu(self.win, tearoff=0)
            menu.add_command(label="Add Tab", command=self.add_tab)
            menu.add_command(label="Rename Tab", command=self.rename_tab)
            menu.add_command(label="Delete Tab", command=self.delete_tab)
            menu.post(event.x_root, event.y_root)
            
    def show_fields_context_menu(self, event):
        g_idx = self.get_selected_group_idx()
        if g_idx is None:
            return
            
        f_idx = self.fields_listbox.nearest(event.y)
        if f_idx >= 0:
            self.fields_listbox.selection_clear(0, tk.END)
            self.fields_listbox.selection_set(f_idx)
            
            menu = tk.Menu(self.win, tearoff=0)
            menu.add_command(label="Move Up", command=lambda: self.move_field_order(-1))
            menu.add_command(label="Move Down", command=lambda: self.move_field_order(1))
            
            # Cascade for Move to Tab
            move_submenu = tk.Menu(menu, tearoff=0)
            
            # Find other tabs
            choices = [g["name"] for i, g in enumerate(self.groups) if i != g_idx]
            if choices:
                group_map = {g["name"]: g for g in self.groups}
                for dest_name in choices:
                    def do_move(dest=dest_name):
                        field_name = self.groups[g_idx]["fields"].pop(f_idx)
                        group_map[dest].setdefault("fields", []).append(field_name)
                        self.on_tab_select(None)
                        
                    move_submenu.add_command(label=dest_name, command=do_move)
                menu.add_cascade(label="Move to Tab", menu=move_submenu)
            
            menu.add_separator()
            menu.add_command(label="Add Field", command=self.add_field)
            menu.add_command(label="Rename Field", command=self.rename_field)
            menu.add_command(label="Delete Field", command=self.delete_field)
            
            menu.post(event.x_root, event.y_root)

    def add_field(self):
        g_idx = self.get_selected_group_idx()
        if g_idx is None:
            return
            
        from tkinter import simpledialog
        name = simpledialog.askstring("Add Field", "Enter new field name:", parent=self.win)
        if not name or not name.strip():
            return
            
        name = name.strip()
        all_assigned = []
        for g in self.groups:
            all_assigned.extend(g.get("fields", []))
            
        if name in all_assigned:
            messagebox.showerror("Conflict", f"Field '{name}' is already assigned to a tab.", parent=self.win)
            return
            
        self.groups[g_idx].setdefault("fields", []).append(name)
        
        reg_fields = [f["name"] for f in self.app.config["ui_sections"]["registration"]]
        if name not in reg_fields:
            self.app.config["ui_sections"]["registration"].append({"name": name, "type": "text"})
            
        self.on_tab_select(None)
        
    def rename_field(self):
        g_idx = self.get_selected_group_idx()
        if g_idx is None:
            return
            
        f_sel = self.fields_listbox.curselection()
        if not f_sel:
            return
            
        f_idx = f_sel[0]
        old_name = self.groups[g_idx]["fields"][f_idx]
        
        from tkinter import simpledialog
        name = simpledialog.askstring("Rename Field", f"Rename field '{old_name}' to:", parent=self.win)
        if not name or not name.strip() or name.strip() == old_name:
            return
            
        name = name.strip()
        all_assigned = []
        for g in self.groups:
            all_assigned.extend(g.get("fields", []))
            
        if name in all_assigned:
            messagebox.showerror("Conflict", f"Field '{name}' already exists.", parent=self.win)
            return
            
        self.groups[g_idx]["fields"][f_idx] = name
        
        for f in self.app.config["ui_sections"]["registration"]:
            if f["name"] == old_name:
                f["name"] = name
                break
                
        self.on_tab_select(None)
        
    def delete_field(self):
        g_idx = self.get_selected_group_idx()
        if g_idx is None:
            return
            
        f_sel = self.fields_listbox.curselection()
        if not f_sel:
            return
            
        f_idx = f_sel[0]
        field_name = self.groups[g_idx]["fields"][f_idx]
        
        if not messagebox.askyesno("Confirm Delete", f"Are you sure you want to remove field '{field_name}' from this tab?", parent=self.win):
            return
            
        self.groups[g_idx]["fields"].pop(f_idx)
        self.on_tab_select(None)


class FieldGroupEditorDialog(GroupEditorWindow):
    def __init__(self, parent, all_fields, current_groups, on_save, app=None):
        self.parent = parent
        self.on_save_callback = on_save

        if app is not None:
            self.app = app
        else:
            class DummyApp:
                def __init__(self, fields):
                    self.config = {
                        "ui_sections": {
                            "registration": [{"name": f, "type": "text"} for f in fields]
                        }
                    }
            self.app = DummyApp(all_fields)

        import copy
        self.groups = copy.deepcopy(current_groups)

        # Ensure Miscellaneous exists if needed
        assigned_fields = set()
        for g in self.groups:
            assigned_fields.update(g.get("fields", []))

        misc = [f for f in all_fields if f not in assigned_fields]
        if misc:
            # Check if Miscellaneous is already in groups
            if not any(g["name"] == "Miscellaneous" for g in self.groups):
                self.groups.append({"name": "Miscellaneous", "fields": misc})

        self.win = tk.Toplevel(parent)
        self.win.title("Configure Field Groups")
        self.win.configure(bg="#fbfaf8")
        self.win.bind("<Escape>", lambda e: self.win.destroy())
        self.win.transient(parent)

        self.setup_styles()
        self._build_ui()

        import utils
        utils.center_and_fit_toplevel(self.win, sc(640), sc(480))

        self.refresh_tabs_list()

    def save_settings(self):
        if self.on_save_callback:
            self.on_save_callback(self.groups)
        self.win.destroy()
