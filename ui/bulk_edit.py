import tkinter as tk
from tkinter import ttk, messagebox
import config

REVIEWED_AT_COLUMN = "ReviewedAt"

def sc(n):
    return config.sc(n)

class BulkEditWindow:
    def __init__(self, parent, app, main_window, pre_selected_oids=None):
        self.parent = parent
        self.app = app
        self.main_window = main_window
        self.target_oids = pre_selected_oids if pre_selected_oids else []
        self.undo_stack = []  # For target list undo

        self.win = tk.Toplevel(parent)
        self.win.title("Bulk Edit Objects")
        self.win.configure(bg="#f9f9f9")
        self.win.bind("<Escape>", lambda e: self.win.destroy())
        self.win.bind("<Control-z>", self.undo_target_remove)
        self.win.transient(parent)

        self._build_ui()
        self._refresh_target_list()

        # Auto-detect layout
        self.win.update_idletasks()
        screen_h = self.win.winfo_screenheight()
        if screen_h * 0.9 < sc(700):
            self.two_col_mode = True
        else:
            self.two_col_mode = False
            
        self._apply_layout()

    def _toggle_layout(self):
        self.two_col_mode = not getattr(self, "two_col_mode", False)
        self._apply_layout()
        
    def _apply_layout(self):
        self.selection_frame.pack_forget()
        self.edit_frame.pack_forget()
        
        if self.two_col_mode:
            self.selection_frame.pack(side="left", fill="both", expand=True, padx=(0, sc(5)))
            self.edit_frame.pack(side="right", fill="both", expand=True, padx=(sc(5), 0))
            w, h = sc(900), sc(450)
        else:
            self.selection_frame.pack(side="top", fill="x", pady=(0, sc(10)))
            self.edit_frame.pack(side="top", fill="both", expand=True, pady=sc(5))
            w, h = sc(500), sc(700)
            
        import utils
        utils.center_and_fit_toplevel(self.win, w, h)

    def _create_card(self, parent, title):
        outer = tk.Frame(parent, bg="#ffffff", highlightthickness=1, highlightbackground="#d1d1d1")
        hdr   = tk.Frame(outer, bg="#f3f3f3")
        hdr.pack(fill="x", side="top")
        tk.Label(hdr, text=title.upper(), font=("Hanken Grotesk", sc(11), "bold"),
                 bg="#f3f3f3", fg="#000000", anchor="w", padx=sc(10), pady=sc(6)).pack(fill="x")
        tk.Frame(outer, bg="#d1d1d1", height=1).pack(fill="x", side="top")          # separator
        content = tk.Frame(outer, bg="#ffffff", padx=sc(10), pady=sc(10))
        content.pack(fill="both", expand=True, side="top")
        return outer, content

    def _build_ui(self):
        main_frame = tk.Frame(self.win, bg="#f9f9f9", padx=sc(10), pady=sc(10))
        main_frame.pack(fill="both", expand=True)

        # Header for Layout Toggle
        header = tk.Frame(main_frame, bg="#f9f9f9")
        header.pack(fill="x", pady=(0, sc(5)))
        
        tk.Button(
            header, text="Toggle Layout (1-Col / 2-Col)", 
            font=("Hanken Grotesk", sc(9)),
            bg="#ffffff", fg="#1a1c1c", relief="solid", bd=1, cursor="hand2",
            padx=sc(10), pady=sc(3),
            command=self._toggle_layout
        ).pack(side="right")
        
        self.content_frame = tk.Frame(main_frame, bg="#f9f9f9")
        self.content_frame.pack(fill="both", expand=True)

        # 1. Manual Object Selection
        self.selection_frame, selection_content = self._create_card(self.content_frame, "Target Objects")

        search_frame = tk.Frame(selection_content, bg="#ffffff")
        search_frame.pack(fill="x", pady=(0, sc(5)))
        tk.Label(search_frame, text="Add Object ID: ", font=("Hanken Grotesk", sc(10)), bg="#ffffff", fg="#1a1c1c").pack(side="left")
        
        self.search_var = tk.StringVar()
        self.search_entry = tk.Entry(
            search_frame, textvariable=self.search_var,
            relief="flat", bd=0,
            highlightthickness=1, highlightbackground="#d1d1d1",
            highlightcolor="#000000", insertbackground="#000000",
            bg="#ffffff", fg="#1a1c1c"
        )
        self.search_entry.pack(side="left", fill="x", expand=True, padx=sc(4))
        self.search_entry.bind("<Return>", self._on_add_object)

        tk.Button(
            search_frame, text="Add", font=("Hanken Grotesk", sc(9), "bold"),
            bg="#1a1c1c", fg="#ffffff", relief="flat", bd=0, cursor="hand2",
            padx=sc(10), pady=sc(3),
            command=self._on_add_object
        ).pack(side="left", padx=sc(5))

        self.target_listbox = tk.Listbox(
            selection_content, height=5, exportselection=False,
            font=("JetBrains Mono", sc(10)),
            relief="flat", bd=0,
            highlightthickness=1, highlightbackground="#d1d1d1",
            highlightcolor="#000000",
            bg="#ffffff", fg="#1a1c1c"
        )
        self.target_listbox.pack(fill="x", pady=sc(5))
        self.target_listbox.bind("<Double-Button-1>", self._on_remove_target)
        tk.Label(selection_content, text="Double-click an object to remove it. (Ctrl+Z to undo)", font=("Segoe UI", sc(8), "italic"), bg="#ffffff", fg="gray").pack(anchor="w")

        # 2. Edit Fields
        self.edit_frame, edit_content = self._create_card(self.content_frame, "Data to Apply")
        
        # We will dynamically build a small form based on config
        canvas = tk.Canvas(edit_content, bg="#ffffff", highlightthickness=0)
        scrollbar = ttk.Scrollbar(edit_content, orient="vertical", command=canvas.yview)
        self.inner_edit = tk.Frame(canvas, bg="#ffffff")

        self.inner_edit.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=self.inner_edit, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        self.bulk_vars = {}
        self.bulk_enable_vars = {}

        row = 0
        
        # Add Registration Fields
        tk.Label(self.inner_edit, text="Registration", font=("Hanken Grotesk", sc(10), "bold"), bg="#ffffff", fg="#000000").grid(row=row, column=0, columnspan=3, sticky="w", pady=(sc(10), sc(5)))
        row += 1
        
        reg_fields = self.app.config["ui_sections"]["registration"]
        
        for field in reg_fields:
            name = field["name"]
            ftype = field.get("type", "text")
            
            enable_var = tk.BooleanVar(value=False)
            val_var = tk.StringVar()
            
            self.bulk_enable_vars[name] = enable_var
            self.bulk_vars[name] = val_var

            ttk.Checkbutton(self.inner_edit, text=name, variable=enable_var).grid(row=row, column=0, sticky="w", padx=sc(5))
            
            if ftype == "choice":
                ttk.Combobox(self.inner_edit, textvariable=val_var, values=field.get("choices", [])).grid(row=row, column=1, sticky="ew", padx=sc(5))
            elif ftype == "checkbox":
                ttk.Checkbutton(self.inner_edit, text="Enable", variable=val_var, onvalue="True", offvalue="False").grid(row=row, column=1, sticky="w", padx=sc(5))
            else:
                tk.Entry(
                    self.inner_edit, textvariable=val_var,
                    relief="flat", bd=0,
                    highlightthickness=1, highlightbackground="#d1d1d1",
                    highlightcolor="#000000", insertbackground="#000000",
                    bg="#ffffff", fg="#1a1c1c"
                ).grid(row=row, column=1, sticky="ew", padx=sc(5))
            
            row += 1

        # Add Location Fields
        tk.Label(self.inner_edit, text="Location", font=("Hanken Grotesk", sc(10), "bold"), bg="#ffffff", fg="#000000").grid(row=row, column=0, columnspan=3, sticky="w", pady=(sc(10), sc(5)))
        row += 1
        
        loc_fields = self.app.config["ui_sections"]["location"]
        
        for field in loc_fields:
            name = field["name"]
            ftype = field.get("type", "text")
            
            enable_var = tk.BooleanVar(value=False)
            val_var = tk.StringVar()
            
            self.bulk_enable_vars[name] = enable_var
            self.bulk_vars[name] = val_var

            ttk.Checkbutton(self.inner_edit, text=name, variable=enable_var).grid(row=row, column=0, sticky="w", padx=sc(5))
            
            if ftype == "choice":
                ttk.Combobox(self.inner_edit, textvariable=val_var, values=field.get("choices", [])).grid(row=row, column=1, sticky="ew", padx=sc(5))
            elif ftype == "checkbox":
                ttk.Checkbutton(self.inner_edit, text="Enable", variable=val_var, onvalue="True", offvalue="False").grid(row=row, column=1, sticky="w", padx=sc(5))
            else:
                tk.Entry(
                    self.inner_edit, textvariable=val_var,
                    relief="flat", bd=0,
                    highlightthickness=1, highlightbackground="#d1d1d1",
                    highlightcolor="#000000", insertbackground="#000000",
                    bg="#ffffff", fg="#1a1c1c"
                ).grid(row=row, column=1, sticky="ew", padx=sc(5))
            
            row += 1

        # Add Problems
        tk.Label(self.inner_edit, text="Problems & Status", font=("Hanken Grotesk", sc(10), "bold"), bg="#ffffff", fg="#000000").grid(row=row, column=0, columnspan=3, sticky="w", pady=(sc(15), sc(5)))
        row += 1

        problem_columns = [f["name"] for f in self.app.config["ui_sections"].get("problems", [])]
        problem_columns.append("Reviewed")

        for name in problem_columns:
            enable_var = tk.BooleanVar(value=False)
            val_var = tk.StringVar(value="False")
            
            self.bulk_enable_vars[name] = enable_var
            self.bulk_vars[name] = val_var
            
            ttk.Checkbutton(self.inner_edit, text=name, variable=enable_var).grid(row=row, column=0, sticky="w", padx=sc(5))
            cb = ttk.Combobox(self.inner_edit, textvariable=val_var, values=["True", "False"], state="readonly", width=8)
            cb.grid(row=row, column=1, sticky="w", padx=sc(5))
            row += 1

        # 3. Actions
        action_frame = tk.Frame(main_frame, bg="#f9f9f9")
        action_frame.pack(fill="x", pady=sc(10))

        tk.Button(
            action_frame, text="Apply to Target List", font=("Hanken Grotesk", sc(10), "bold"),
            bg="#1a1c1c", fg="#ffffff", relief="flat", bd=0, cursor="hand2",
            padx=sc(16), pady=sc(6),
            command=self.apply_to_targets
        ).pack(side="left", padx=sc(5))
        
        tk.Button(
            action_frame, text="Apply to ALL Filtered Objects", font=("Hanken Grotesk", sc(10), "bold"),
            bg="#ffffff", fg="#1a1c1c", relief="solid", bd=1, cursor="hand2",
            padx=sc(16), pady=sc(6),
            command=self.apply_to_all_filtered
        ).pack(side="right", padx=sc(5))

    def _refresh_target_list(self):
        self.target_listbox.delete(0, tk.END)
        for oid in self.target_oids:
            self.target_listbox.insert(tk.END, oid)

    def _on_add_object(self, event=None):
        oid = self.search_var.get().strip()
        if not oid: return
        
        # Verify it exists in db
        if oid in self.app.df_reg.index:
            if oid not in self.target_oids:
                self.target_oids.append(oid)
                self._refresh_target_list()
                self.search_var.set("")
        else:
            messagebox.showwarning("Not Found", f"Object ID {oid} not found in database.")

    def _on_remove_target(self, event):
        sel = self.target_listbox.curselection()
        if sel:
            idx = sel[0]
            oid = self.target_oids.pop(idx)
            self.undo_stack.append((idx, oid))
            self._refresh_target_list()

    def undo_target_remove(self, event=None):
        if self.undo_stack:
            idx, oid = self.undo_stack.pop()
            self.target_oids.insert(idx, oid)
            self._refresh_target_list()

    def _get_updates(self):
        updates = {}
        for name, enable_var in self.bulk_enable_vars.items():
            if enable_var.get():
                updates[name] = self.bulk_vars[name].get()
        return updates

    def apply_to_targets(self):
        if not self.target_oids:
            messagebox.showinfo("No Targets", "Add objects to the target list first.")
            return
        self._apply_bulk(self.target_oids)

    def apply_to_all_filtered(self):
        oids = self.app.active_object_ids
        if not oids:
            return
        if messagebox.askyesno("Confirm", f"Are you sure you want to apply these changes to ALL {len(oids)} filtered objects?"):
            self._apply_bulk(oids)

    def _apply_bulk(self, oids):
        updates = self._get_updates()
        if not updates:
            messagebox.showinfo("No Changes", "Select at least one field to update.")
            return
            
        self.main_window._show_progress(f"Bulk applying to {len(oids)} objects...", len(oids))
        
        problem_keys = [f["name"] for f in self.app.config["ui_sections"].get("problems", [])] + ["Reviewed"]
        
        for i, oid in enumerate(oids):
            self.main_window.app.undo_stacks.setdefault(oid, []).append({
                "reg": self.app.df_reg.loc[oid].copy(),
                "obs": self.app.df_obs.loc[oid].copy(),
            })
            
            for key, val in updates.items():
                if key in self.app.df_reg.columns:
                    self.app.df_reg.at[oid, key] = val
                    if key == "Loaned out":
                        from datetime import datetime
                        if str(val).lower() == "true":
                            self.app.df_reg.at[oid, "Loaned out date"] = datetime.now().strftime("%d.%m.%Y %H:%M:%S")
                        else:
                            self.app.df_reg.at[oid, "Loaned out date"] = ""
                elif key in self.app.df_obs.columns:
                    if key in problem_keys:
                        val = str(val).lower() == "true"
                    self.app.df_obs.at[oid, key] = val
                    if key == "Reviewed" and val:
                        from datetime import datetime
                        self.app.df_obs.at[oid, REVIEWED_AT_COLUMN] = datetime.now().strftime("%d.%m.%Y %H:%M:%S")
            
            # Recalculate problems cache
            self.main_window._problem_cache.pop(oid, None)
            
            if i % 10 == 0:
                self.main_window.image_scan_progress.configure(value=i, maximum=len(oids))

        self.main_window._hide_progress("Bulk apply complete")
        self.app.dirty = True
        self.main_window.update_dirty_ui()
        self.main_window.refresh_list()
        
        # If currently looking at one of the affected, reload
        if self.app.current_object_id in oids:
            self.main_window.load_object(self.app.current_object_id)
            
        self.win.destroy()
        messagebox.showinfo("Success", f"Successfully updated {len(oids)} objects.")
