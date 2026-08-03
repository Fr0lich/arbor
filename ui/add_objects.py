import tkinter as tk
from tkinter import ttk, messagebox
import config
import uuid

REVIEWED_COLUMN = "Reviewed"

# Local scale helper
def sc(n):
    return config.sc(n)

class AddObjectsWindow:
    def __init__(self, parent, app, main_window):
        self.parent = parent
        self.app = app
        self.main_window = main_window

        if self.app.df_reg is None:
            messagebox.showwarning("No data", "Initialize a database first.")
            return

        self.win = tk.Toplevel(parent)
        self.win.title("Create New Objects")
        self.win.configure(bg="#f9f9f9")
        self.win.bind("<Escape>", lambda e: self.win.destroy())
        self.win.transient(parent)
        self.win.resizable(True, True)

        # Staged object data
        self.staged_data = {}
        self.current_selected_id = None

        # Style initializations
        self.setup_styles()

        self._build_ui()

        # Auto-detect layout
        self.win.update_idletasks()
        screen_h = self.win.winfo_screenheight()
        # If screen is too small for the vertical layout, default to 2-columns
        if screen_h * 0.9 < sc(700):
            self.two_col_mode = True
        else:
            self.two_col_mode = False
            
        self._apply_layout()

    def setup_styles(self):
        style = ttk.Style()
        # Flat, sharp layout frames
        style.configure("Flat.TFrame", background="#f9f9f9")
        style.configure("FlatCard.TLabelframe", background="#ffffff", bordercolor="#d1d1d1", borderwidth=1, relief="solid")
        style.configure("FlatCard.TLabelframe.Label", font=("Hanken Grotesk", sc(11), "bold"), background="#ffffff", foreground="#1a1c1c")

    def _toggle_layout(self):
        self.two_col_mode = not getattr(self, "two_col_mode", False)
        self._apply_layout()
        
    def _apply_layout(self):
        self.id_frame.pack_forget()
        self.edit_frame.pack_forget()
        
        if self.two_col_mode:
            self.id_frame.pack(side="left", fill="both", expand=True, padx=(0, sc(5)))
            self.edit_frame.pack(side="right", fill="both", expand=True, padx=(sc(5), 0))
            w, h = sc(1100), sc(600)
            if hasattr(self, "toggle_btn"):
                self.toggle_btn.config(text="⊟ Switch to Single Column")
        else:
            self.id_frame.pack(side="top", fill="x", pady=(0, sc(10)))
            self.edit_frame.pack(side="top", fill="both", expand=True, pady=sc(5))
            w, h = sc(600), sc(800)
            if hasattr(self, "toggle_btn"):
                self.toggle_btn.config(text="⊞ Switch to 2-Column")
            
        import utils
        utils.center_and_fit_toplevel(self.win, w, h)

    def _create_location_style_card(self, parent, title):
        main_box = tk.Frame(parent, bg="#ffffff", highlightthickness=1, highlightbackground="#d1d1d1")
        
        hdr = tk.Frame(main_box, bg="#f3f3f3", highlightthickness=0)
        hdr.pack(fill="x", side="top")
        
        lbl = tk.Label(
            hdr, text=title.upper(), 
            font=("Hanken Grotesk", sc(11), "bold"), 
            bg="#f3f3f3", fg="#000000",
            anchor="w", padx=sc(10), pady=sc(6)
        )
        lbl.pack(side="left", fill="both", expand=True)
        
        sep = tk.Frame(main_box, bg="#d1d1d1", height=1)
        sep.pack(fill="x", side="top")
        
        content = tk.Frame(main_box, bg="#ffffff", padx=sc(10), pady=sc(10))
        content.pack(fill="both", expand=True, side="top")
        
        return main_box, content

    def _build_ui(self):
        main_frame = tk.Frame(self.win, bg="#f9f9f9", padx=sc(12), pady=sc(12))
        main_frame.pack(fill="both", expand=True)
        
        # Header for Layout Toggle
        header = tk.Frame(main_frame, bg="#f9f9f9")
        header.pack(fill="x", pady=(0, sc(8)))
        
        self.toggle_btn = tk.Button(
            header, text="⊞ Switch to 2-Column", 
            font=("Hanken Grotesk", sc(9.5)),
            bg="#ffffff", fg="#1a1c1c", 
            activebackground="#e2e2e2", activeforeground="#1a1c1c",
            relief="solid", bd=1, cursor="hand2", padx=sc(8), pady=sc(3),
            command=self._toggle_layout
        )
        self.toggle_btn.pack(side="right")
        
        self.content_frame = tk.Frame(main_frame, bg="#f9f9f9")
        self.content_frame.pack(fill="both", expand=True)

        # 1. Target IDs
        self.id_frame, id_content = self._create_location_style_card(self.content_frame, "Object IDs")
        
        lbl_n = tk.Label(id_content, text="Generate Next N IDs:", font=("Hanken Grotesk", sc(9.5)), bg="#ffffff", fg="#1a1c1c")
        lbl_n.grid(row=0, column=0, sticky="w", pady=sc(4))
        
        self.auto_n_var = tk.IntVar(value=1)
        spin = ttk.Spinbox(id_content, from_=1, to=1000, textvariable=self.auto_n_var, width=5, font=("JetBrains Mono", sc(9.5)))
        spin.grid(row=0, column=1, sticky="w", padx=sc(6))
        
        gen_btn = tk.Button(
            id_content, text="Generate",
            font=("Hanken Grotesk", sc(9.5)),
            bg="#ffffff", fg="#1a1c1c",
            activebackground="#e2e2e2", activeforeground="#1a1c1c",
            relief="solid", bd=1, cursor="hand2", padx=sc(8), pady=sc(2),
            command=self._generate_auto_ids
        )
        gen_btn.grid(row=0, column=2, sticky="w", padx=sc(6))
 
        lbl_manual = tk.Label(id_content, text="Or manually enter IDs (comma-separated):", font=("Hanken Grotesk", sc(9.5)), bg="#ffffff", fg="#1a1c1c")
        lbl_manual.grid(row=1, column=0, columnspan=3, sticky="w", pady=(sc(12), sc(4)))
        
        self.manual_ids_var = tk.StringVar()
        ent_manual = tk.Entry(
            id_content, textvariable=self.manual_ids_var,
            font=("JetBrains Mono", sc(9.5)), relief="flat", bd=0,
            highlightthickness=1, highlightbackground="#d1d1d1",
            highlightcolor="#000000", insertbackground="#000000",
            bg="#ffffff", fg="#1a1c1c"
        )
        ent_manual.grid(row=2, column=0, columnspan=3, sticky="ew", pady=sc(4))
        id_content.columnconfigure(1, weight=1)

        self.target_listbox = tk.Listbox(
            id_content, height=4,
            font=("JetBrains Mono", sc(10)),
            bg="#ffffff", fg="#1a1c1c",
            relief="flat", bd=0, highlightthickness=1,
            highlightbackground="#d1d1d1", highlightcolor="#000000"
        )
        self.target_listbox.grid(row=3, column=0, columnspan=3, sticky="ew", pady=sc(8))
        self.target_listbox.bind("<<ListboxSelect>>", self._on_listbox_select)
        
        btn_frame = tk.Frame(id_content, bg="#ffffff")
        btn_frame.grid(row=4, column=0, columnspan=3, sticky="ew")
        
        add_btn = tk.Button(
            btn_frame, text="Add Manual IDs",
            font=("Hanken Grotesk", sc(9.5)),
            bg="#ffffff", fg="#1a1c1c",
            activebackground="#e2e2e2", activeforeground="#1a1c1c",
            relief="solid", bd=1, cursor="hand2", padx=sc(8), pady=sc(3),
            command=self._add_manual_ids
        )
        add_btn.pack(side="left")
        
        clear_btn = tk.Button(
            btn_frame, text="Clear List",
            font=("Hanken Grotesk", sc(9.5)),
            bg="#ffffff", fg="#ba1a1a",
            activebackground="#ffdad6", activeforeground="#ba1a1a",
            relief="solid", bd=1, cursor="hand2", padx=sc(8), pady=sc(3),
            command=lambda: self.target_listbox.delete(0, tk.END)
        )
        clear_btn.pack(side="right")

        # 2. Edit Fields
        self.edit_frame, edit_content = self._create_location_style_card(self.content_frame, "Default Data to Apply")
        
        canvas = tk.Canvas(edit_content, bg="#ffffff", highlightthickness=0)
        scrollbar = ttk.Scrollbar(edit_content, orient="vertical", command=canvas.yview)
        
        # Ensure flat container inside canvas
        self.inner_edit = tk.Frame(canvas, bg="#ffffff")

        self.inner_edit.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas_window = canvas.create_window((0, 0), window=self.inner_edit, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        canvas.bind("<Configure>", lambda e: canvas.itemconfig(canvas_window, width=e.width))
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        self.field_vars = {}

        row = 0
        
        # Registration Section Header
        lbl_reg_hdr = tk.Label(self.inner_edit, text="Registration", font=("Hanken Grotesk", sc(11), "bold"), bg="#ffffff", fg="#1a1c1c")
        lbl_reg_hdr.grid(row=row, column=0, columnspan=4, sticky="w", pady=(sc(10), sc(6)))
        row += 1
        
        reg_fields = self.app.config["ui_sections"].get("registration", [])
        col_idx = 0
        for field in reg_fields:
            name = field["name"]
            if name == "UID" or field.get("readonly", False):
                continue
                
            ftype = field.get("type", "text")
            val_var = tk.StringVar()
            self.field_vars[name] = val_var

            lbl_f = tk.Label(self.inner_edit, text=name, font=("Hanken Grotesk", sc(9.5)), bg="#ffffff", fg="#444748")
            lbl_f.grid(row=row, column=col_idx*2, sticky="w", padx=sc(5), pady=sc(4))
            
            if ftype == "choice":
                choices = field.get("choices", [])
                if "" not in choices:
                    choices = [""] + choices
                cb = ttk.Combobox(self.inner_edit, textvariable=val_var, values=choices, font=("JetBrains Mono", sc(9.5)), state="readonly")
                cb.grid(row=row, column=col_idx*2 + 1, sticky="ew", padx=sc(5), pady=sc(4))
            elif ftype == "checkbox":
                cb = ttk.Checkbutton(self.inner_edit, text="Enable", variable=val_var, onvalue="True", offvalue="False")
                cb.grid(row=row, column=col_idx*2 + 1, sticky="w", padx=sc(5), pady=sc(4))
            else:
                ent = tk.Entry(
                    self.inner_edit, textvariable=val_var, 
                    font=("JetBrains Mono", sc(9.5)), relief="flat", bd=0, 
                    highlightthickness=1, highlightbackground="#d1d1d1",
                    highlightcolor="#000000", insertbackground="#000000",
                    bg="#ffffff", fg="#1a1c1c"
                )
                ent.grid(row=row, column=col_idx*2 + 1, sticky="ew", padx=sc(5), pady=sc(4))
                
            col_idx += 1
            if col_idx == 2:
                col_idx = 0
                row += 1
                
        if col_idx > 0:
            col_idx = 0
            row += 1

        # Location Section Header
        loc_fields = self.app.config["ui_sections"].get("location", [])
        if loc_fields:
            lbl_loc_hdr = tk.Label(self.inner_edit, text="Location", font=("Hanken Grotesk", sc(11), "bold"), bg="#ffffff", fg="#1a1c1c")
            lbl_loc_hdr.grid(row=row, column=0, columnspan=4, sticky="w", pady=(sc(16), sc(6)))
            row += 1
            
            col_idx = 0
            for field in loc_fields:
                name = field["name"]
                if field.get("readonly", False):
                    continue
                    
                ftype = field.get("type", "text")
                val_var = tk.StringVar()
                self.field_vars[name] = val_var

                lbl_lf = tk.Label(self.inner_edit, text=name, font=("Hanken Grotesk", sc(9.5)), bg="#ffffff", fg="#444748")
                lbl_lf.grid(row=row, column=col_idx*2, sticky="w", padx=sc(5), pady=sc(4))
                
                if ftype == "choice":
                    choices = field.get("choices", [])
                    if "" not in choices:
                        choices = [""] + choices
                    cb = ttk.Combobox(self.inner_edit, textvariable=val_var, values=choices, font=("JetBrains Mono", sc(9.5)), state="readonly")
                    cb.grid(row=row, column=col_idx*2 + 1, sticky="ew", padx=sc(5), pady=sc(4))
                elif ftype == "checkbox":
                    cb = ttk.Checkbutton(self.inner_edit, text="Enable", variable=val_var, onvalue="True", offvalue="False")
                    cb.grid(row=row, column=col_idx*2 + 1, sticky="w", padx=sc(5), pady=sc(4))
                else:
                    ent = tk.Entry(
                        self.inner_edit, textvariable=val_var, 
                        font=("JetBrains Mono", sc(9.5)), relief="flat", bd=0, 
                        highlightthickness=1, highlightbackground="#d1d1d1",
                        highlightcolor="#000000", insertbackground="#000000",
                        bg="#ffffff", fg="#1a1c1c"
                    )
                    ent.grid(row=row, column=col_idx*2 + 1, sticky="ew", padx=sc(5), pady=sc(4))
                    
                col_idx += 1
                if col_idx == 2:
                    col_idx = 0
                    row += 1
                    
            if col_idx > 0:
                col_idx = 0
                row += 1

        self.inner_edit.columnconfigure(1, weight=1)
        self.inner_edit.columnconfigure(3, weight=1)

        # 3. Actions
        action_frame = tk.Frame(main_frame, bg="#f9f9f9")
        action_frame.pack(fill="x", pady=(sc(10), 0))

        create_btn = tk.Button(
            action_frame, text="Create Objects", 
            font=("Hanken Grotesk", sc(10), "bold"),
            bg="#1a1c1c", fg="#ffffff",
            activebackground="#333333", activeforeground="#ffffff",
            relief="flat", bd=0, cursor="hand2", padx=sc(16), pady=sc(6),
            command=self._create_objects
        )
        create_btn.pack(side="right", padx=sc(5))
        
        cancel_btn = tk.Button(
            action_frame, text="Cancel", 
            font=("Hanken Grotesk", sc(10)),
            bg="#ffffff", fg="#1a1c1c",
            activebackground="#e2e2e2", activeforeground="#1a1c1c",
            relief="solid", bd=1, cursor="hand2", padx=sc(12), pady=sc(5),
            command=self.win.destroy
        )
        cancel_btn.pack(side="left", padx=sc(5))

    def _save_current_staged_data(self):
        if self.current_selected_id is not None:
            data = {}
            for k, v in self.field_vars.items():
                data[k] = v.get()
            self.staged_data[self.current_selected_id] = data

    def _load_staged_data(self, oid):
        data = self.staged_data.get(oid, {})
        for k, v in self.field_vars.items():
            v.set(data.get(k, ""))

    def _on_listbox_select(self, event):
        sel = self.target_listbox.curselection()
        if not sel:
            return
        new_id = self.target_listbox.get(sel[0])
        
        # Save old
        self._save_current_staged_data()
        
        # Initialize if not present (starts blank)
        if new_id not in self.staged_data:
            self.staged_data[new_id] = {k: "" for k in self.field_vars.keys()}
            
        # Load new
        self._load_staged_data(new_id)
        self.current_selected_id = new_id

    def _get_target_oids(self):
        return list(self.target_listbox.get(0, tk.END))

    def _generate_auto_ids(self):
        try:
            n = self.auto_n_var.get()
        except tk.TclError:
            n = 1
        if n < 1: n = 1
        
        existing_ids = [int(x) for x in self.app.df_reg.index if str(x).isdigit()]
        start_id = max(existing_ids) + 1 if existing_ids else 1
        
        for i in range(n):
            new_id = str(start_id + i)
            if new_id not in self._get_target_oids() and new_id not in self.app.df_reg.index:
                self.target_listbox.insert(tk.END, new_id)
                self.staged_data[new_id] = {k: "" for k in self.field_vars.keys()}

    def _add_manual_ids(self):
        raw = self.manual_ids_var.get()
        if not raw: return
        
        parts = [p.strip() for p in raw.split(",") if p.strip()]
        for p in parts:
            if p not in self._get_target_oids():
                if p in self.app.df_reg.index:
                    messagebox.showwarning("Exists", f"ObjectID {p} already exists in database.", parent=self.win)
                else:
                    self.target_listbox.insert(tk.END, p)
                    self.staged_data[p] = {k: "" for k in self.field_vars.keys()}
        self.manual_ids_var.set("")

    def _create_objects(self):
        oids = self._get_target_oids()
        if not oids:
            messagebox.showwarning("No IDs", "Add at least one target Object ID to create.", parent=self.win)
            return

        for oid in oids:
            if oid in self.app.df_reg.index:
                messagebox.showerror("Conflict", f"Object {oid} already exists!", parent=self.win)
                return

        # Save current edits first
        self._save_current_staged_data()
        
        for oid in oids:
            obj_data = self.staged_data.get(oid, {})
            updates = {k: v for k, v in obj_data.items() if v.strip()}
            
            # df_reg
            new_reg_row = {col: "" for col in self.app.df_reg.columns}
            new_reg_row["UID"] = uuid.uuid4().hex[:8]
            for k, v in updates.items():
                if k in self.app.df_reg.columns:
                    new_reg_row[k] = v
            self.app.df_reg.loc[oid] = new_reg_row

            # df_obs
            problem_columns = [f["name"] for f in self.app.config["ui_sections"].get("problems", [])]
            location_columns = [f["name"] for f in self.app.config["ui_sections"].get("location", [])]
            
            new_obs_row = {col: False for col in problem_columns}
            new_obs_row["Images_Missing"] = True
            
            for col in location_columns:
                new_obs_row[col] = updates.get(col, "")
                
            self.app.df_obs.loc[oid] = new_obs_row

            # df_photo
            if not self.app.df_photo.empty:
                new_photo_row = {col: "" for col in self.app.df_photo.columns}
                self.app.df_photo.loc[oid] = new_photo_row

            self.app.active_object_ids.append(oid)
            
            self.main_window.log_action(
                "CREATE_OBJECT",
                ["ObjectID"],
                [f"Created {oid}"]
            )

        self.main_window._list_dirty = True
        self.main_window.refresh_list()
        
        # Select the first created object
        idx = self.app.active_object_ids.index(oids[0])
        self.main_window.object_list.selection_clear(0, tk.END)
        self.main_window.object_list.selection_set(idx)
        self.main_window.object_list.see(idx)
        self.main_window.load_object(oids[0])

        self.app.dirty = True
        self.main_window.update_dirty_ui()

        messagebox.showinfo("Success", f"Successfully created {len(oids)} object(s).", parent=self.main_window.root)
        self.win.destroy()
