import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import pandas as pd
import config
from datetime import datetime
import json

def sc(n):
    return config.sc(n)

class NewDatabaseWizard:
    def __init__(self, parent, app, on_complete):
        self.parent = parent
        self.app = app
        self.on_complete = on_complete
        
        self.win = tk.Toplevel(parent)
        self.win.title("New Database Setup")
        self.win.configure(bg="#f9f9f9")
        self.win.grab_set()
        self.win.transient(parent)
        
        import utils
        utils.center_and_fit_toplevel(self.win, sc(520), sc(540))
        
        self.main_frame = tk.Frame(self.win, bg="#f9f9f9", padx=sc(15), pady=sc(15))
        self.main_frame.pack(fill="both", expand=True)
        
        self.show_step1()

    def clear_frame(self):
        for widget in self.main_frame.winfo_children():
            widget.destroy()

    def _create_step_card(self, title):
        outer = tk.Frame(self.main_frame, bg="#ffffff", highlightthickness=1, highlightbackground="#d1d1d1")
        outer.pack(fill="both", expand=True, side="top")
        
        hdr = tk.Frame(outer, bg="#f3f3f3")
        hdr.pack(fill="x", side="top")
        tk.Label(hdr, text=title.upper(), font=("Hanken Grotesk", sc(11), "bold"),
                 bg="#f3f3f3", fg="#000000", anchor="w", padx=sc(12), pady=sc(8)).pack(fill="x")
        
        tk.Frame(outer, bg="#d1d1d1", height=1).pack(fill="x", side="top")          # separator
        
        content = tk.Frame(outer, bg="#ffffff", padx=sc(12), pady=sc(12))
        content.pack(fill="both", expand=True, side="top")
        return content

    def show_step1(self):
        self.clear_frame()
        content = self._create_step_card("Step 1: Choose Database Profile")
        
        tk.Label(content, text="Select an existing profile:", font=("Hanken Grotesk", sc(10), "bold"), bg="#ffffff", fg="#1a1c1c").pack(anchor="w", pady=(0, sc(4)))
        self.profile_var = tk.StringVar()
        profiles = list(config.DATABASE_CONFIGS.keys())
        cb = ttk.Combobox(content, textvariable=self.profile_var, values=profiles, state="readonly")
        cb.pack(fill="x", pady=sc(5))
        if profiles:
            cb.set(profiles[0])
            
        tk.Button(
            content, text="Use Selected Profile", font=("Hanken Grotesk", sc(10), "bold"),
            bg="#1a1c1c", fg="#ffffff", relief="flat", bd=0, cursor="hand2",
            padx=sc(16), pady=sc(6),
            command=self.use_existing_profile
        ).pack(pady=sc(10))
        
        ttk.Separator(content, orient="horizontal").pack(fill="x", pady=sc(15))
        
        tk.Label(content, text="Or create a new profile:", font=("Hanken Grotesk", sc(10), "bold"), bg="#ffffff", fg="#1a1c1c").pack(anchor="w", pady=(0, sc(4)))
        btn_frame = tk.Frame(content, bg="#ffffff")
        btn_frame.pack(fill="x", pady=sc(5))
        
        tk.Button(
            btn_frame, text="Create from Excel", font=("Hanken Grotesk", sc(9), "bold"),
            bg="#ffffff", fg="#1a1c1c", relief="solid", bd=1, cursor="hand2",
            padx=sc(12), pady=sc(6),
            command=self.step2_excel
        ).pack(side="left", padx=sc(5), expand=True, fill="x")
        
        tk.Button(
            btn_frame, text="Create from Scratch", font=("Hanken Grotesk", sc(9), "bold"),
            bg="#ffffff", fg="#1a1c1c", relief="solid", bd=1, cursor="hand2",
            padx=sc(12), pady=sc(6),
            command=self.step2_scratch
        ).pack(side="right", padx=sc(5), expand=True, fill="x")

    def use_existing_profile(self):
        profile = self.profile_var.get()
        if not profile:
            return
        self.app.config = config.DATABASE_CONFIGS[profile]
        self.step5_save_location()

    def step2_excel(self):
        import config
        file_path = filedialog.askopenfilename(
            parent=self.win,
            title="Select Template Excel File",
            filetypes=[("Excel files", "*.xlsx *.xls")],
            initialdir=config.get_last_dir("last_db_dir")
        )
        if not file_path:
            return
        config.set_last_dir("last_db_dir", file_path)
            
        try:
            df = pd.read_excel(file_path, nrows=0) # Just read headers
            columns = list(df.columns)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to read Excel file:\n{e}", parent=self.win)
            return
            
        self.clear_frame()
        content = self._create_step_card("Step 2: Select Registration Fields")
        
        canvas = tk.Canvas(content, bg="#ffffff", highlightthickness=0)
        scrollbar = ttk.Scrollbar(content, orient="vertical", command=canvas.yview)
        inner = tk.Frame(canvas, bg="#ffffff")
        
        inner.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=inner, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        canvas.pack(side="top", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        self.field_vars = {}
        for col in columns:
            if str(col).lower() == "objectid":
                continue
            var = tk.BooleanVar(value=True)
            self.field_vars[col] = var
            ttk.Checkbutton(inner, text=col, variable=var).pack(anchor="w", pady=sc(2))
            
        tk.Button(
            self.main_frame, text="Next Step", font=("Hanken Grotesk", sc(10), "bold"),
            bg="#1a1c1c", fg="#ffffff", relief="flat", bd=0, cursor="hand2",
            padx=sc(16), pady=sc(6),
            command=self.step3_problems_from_vars
        ).pack(pady=sc(10))

    def step2_scratch(self):
        self.clear_frame()
        content = self._create_step_card("Step 2: Define Registration Fields")
        
        add_frame = tk.Frame(content, bg="#ffffff")
        add_frame.pack(fill="x", pady=sc(5))
        
        self.new_field_var = tk.StringVar()
        entry = tk.Entry(
            add_frame, textvariable=self.new_field_var,
            relief="flat", bd=0,
            highlightthickness=1, highlightbackground="#d1d1d1",
            highlightcolor="#000000", insertbackground="#000000",
            bg="#ffffff", fg="#1a1c1c"
        )
        entry.pack(side="left", fill="x", expand=True, padx=sc(4))
        
        self.scratch_fields = []
        listbox = tk.Listbox(
            content, font=("Hanken Grotesk", sc(10)),
            bg="#ffffff", fg="#1a1c1c", relief="solid", bd=1, highlightthickness=0,
            exportselection=False
        )
        listbox.pack(fill="both", expand=True, pady=sc(5))
        
        def add_field(e=None):
            val = self.new_field_var.get().strip()
            if val and val.lower() != "objectid" and val not in self.scratch_fields:
                self.scratch_fields.append(val)
                listbox.insert(tk.END, val)
                self.new_field_var.set("")
                
        entry.bind("<Return>", add_field)
        
        tk.Button(
            add_frame, text="Add", font=("Hanken Grotesk", sc(9), "bold"),
            bg="#1a1c1c", fg="#ffffff", relief="flat", bd=0, cursor="hand2",
            padx=sc(10), pady=sc(3),
            command=add_field
        ).pack(side="right", padx=sc(5))
        
        def remove_field():
            sel = listbox.curselection()
            if sel:
                idx = sel[0]
                self.scratch_fields.pop(idx)
                listbox.delete(idx)
                
        tk.Button(
            content, text="Remove Selected", font=("Hanken Grotesk", sc(9)),
            bg="#ffffff", fg="#ba1a1a", relief="solid", bd=1, cursor="hand2",
            padx=sc(10), pady=sc(3),
            command=remove_field
        ).pack(anchor="e", pady=sc(4))
        
        tk.Button(
            self.main_frame, text="Next Step", font=("Hanken Grotesk", sc(10), "bold"),
            bg="#1a1c1c", fg="#ffffff", relief="flat", bd=0, cursor="hand2",
            padx=sc(16), pady=sc(6),
            command=lambda: self.step2b_field_types(self.scratch_fields)
        ).pack(pady=sc(10))

    def step3_problems_from_vars(self):
        fields = [f for f, v in self.field_vars.items() if v.get()]
        if not fields:
            messagebox.showwarning("Warning", "Select at least one field.", parent=self.win)
            return
        self.step2b_field_types(fields)

    def step2b_field_types(self, fields):
        self.registration_fields = fields
        self.clear_frame()
        content = self._create_step_card("Step 2b: Configure Field Types")
        
        canvas = tk.Canvas(content, bg="#ffffff", highlightthickness=0)
        scrollbar = ttk.Scrollbar(content, orient="vertical", command=canvas.yview)
        inner = tk.Frame(canvas, bg="#ffffff")
        
        inner.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=inner, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        canvas.pack(side="top", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        inner.columnconfigure(0, weight=1, minsize=sc(180))
        inner.columnconfigure(1, weight=1)
        
        self.field_type_vars = {}
        row = 0
        for f in fields:
            lbl = tk.Label(inner, text=f, font=("Hanken Grotesk", sc(10)), bg="#ffffff", fg="#1a1c1c")
            lbl.grid(row=row, column=0, sticky="w", padx=sc(5), pady=sc(4))
            
            choice_var = tk.StringVar()
            self.field_type_vars[f] = choice_var
            
            lower_name = f.lower()
            if any(kw in lower_name for kw in ["comment", "observation", "description", "note"]):
                default_type = "multiline"
            elif any(kw in lower_name for kw in ["status", "loan", "type", "store", "cabinet"]):
                default_type = "text"
            else:
                default_type = "text"
                
            choice_var.set(default_type)
            cb = ttk.Combobox(inner, textvariable=choice_var, values=["text", "multiline", "choice", "checkbox"], state="readonly", width=12)
            cb.grid(row=row, column=1, sticky="w", padx=sc(5), pady=sc(4))
            
            row += 1
            
        def on_next():
            self.field_types = {f: var.get() for f, var in self.field_type_vars.items()}
            self.step3_problems(self.registration_fields)
            
        tk.Button(
            self.main_frame, text="Next Step", font=("Hanken Grotesk", sc(10), "bold"),
            bg="#1a1c1c", fg="#ffffff", relief="flat", bd=0, cursor="hand2",
            padx=sc(16), pady=sc(6),
            command=on_next
        ).pack(pady=sc(10))

    def step3_problems(self, fields):
        self.registration_fields = fields
        self.clear_frame()
        content = self._create_step_card("Step 3: Auto-generate Problems")
        
        tk.Label(content, text="Check fields to create a [Field]_Problem flag:", font=("Hanken Grotesk", sc(9.5)), bg="#ffffff", fg="gray").pack(anchor="w", pady=(0, sc(5)))
        
        canvas = tk.Canvas(content, bg="#ffffff", highlightthickness=0)
        scrollbar = ttk.Scrollbar(content, orient="vertical", command=canvas.yview)
        inner = tk.Frame(canvas, bg="#ffffff")
        
        inner.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=inner, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        canvas.pack(side="top", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        self.prob_vars = {}
        for f in fields:
            var = tk.BooleanVar(value=False)
            self.prob_vars[f] = var
            ttk.Checkbutton(inner, text=f"Create {f}_Problem", variable=var).pack(anchor="w", pady=sc(2))
            
        tk.Button(
            self.main_frame, text="Next Step", font=("Hanken Grotesk", sc(10), "bold"),
            bg="#1a1c1c", fg="#ffffff", relief="flat", bd=0, cursor="hand2",
            padx=sc(16), pady=sc(6),
            command=self.step3b_define_groups
        ).pack(pady=sc(10))

    def step3b_define_groups(self):
        self.clear_frame()
        content = self._create_step_card("Step 3b: Define Field Groups (Optional)")
        
        pane = ttk.PanedWindow(content, orient="horizontal")
        pane.pack(fill="both", expand=True, pady=sc(5))
        
        left = tk.Frame(pane, bg="#ffffff")
        right = tk.Frame(pane, bg="#ffffff")
        pane.add(left, weight=1)
        pane.add(right, weight=1)
        
        tk.Label(left, text="Fields", font=("Hanken Grotesk", sc(10), "bold"), bg="#ffffff", fg="#1a1c1c").pack(anchor="w")
        fields_lb = tk.Listbox(
            left, selectmode="extended", font=("JetBrains Mono", sc(9.5)),
            bg="#ffffff", fg="#1a1c1c", relief="solid", bd=1, highlightthickness=0,
            exportselection=False
        )
        fields_lb.pack(fill="both", expand=True)
        for f in self.registration_fields:
            fields_lb.insert(tk.END, f)
            
        tk.Label(right, text="Groups", font=("Hanken Grotesk", sc(10), "bold"), bg="#ffffff", fg="#1a1c1c").pack(anchor="w")
        
        groups_frame = tk.Frame(right, bg="#ffffff")
        groups_frame.pack(fill="both", expand=True)
        
        groups_lb = tk.Listbox(
            groups_frame, selectmode="single", font=("Hanken Grotesk", sc(9.5)),
            bg="#ffffff", fg="#1a1c1c", relief="solid", bd=1, highlightthickness=0,
            exportselection=False
        )
        groups_lb.pack(side="left", fill="both", expand=True)
        
        self.reg_groups = {}
        
        from tkinter import simpledialog
        def add_group():
            name = simpledialog.askstring("New Group", "Group name:", parent=self.win)
            if name and name not in self.reg_groups:
                self.reg_groups[name] = []
                groups_lb.insert(tk.END, name)
                
        def delete_group():
            sel = groups_lb.curselection()
            if sel:
                name = groups_lb.get(sel[0])
                del self.reg_groups[name]
                groups_lb.delete(sel[0])
                
        def assign_fields():
            f_sel = fields_lb.curselection()
            g_sel = groups_lb.curselection()
            if not f_sel or not g_sel:
                return
            g_name = groups_lb.get(g_sel[0])
            added = 0
            for idx in f_sel:
                f_name = fields_lb.get(idx)
                if f_name not in self.reg_groups[g_name]:
                    self.reg_groups[g_name].append(f_name)
                    added += 1
            from tkinter import messagebox
            messagebox.showinfo("Assigned", f"Assigned {added} fields to {g_name}", parent=self.win)

        btn_frame = tk.Frame(right, bg="#ffffff")
        btn_frame.pack(fill="x", pady=sc(2))
        
        tk.Button(
            btn_frame, text="Add Group", font=("Hanken Grotesk", sc(9)),
            bg="#ffffff", fg="#1a1c1c", relief="solid", bd=1, cursor="hand2",
            padx=sc(8), pady=sc(3),
            command=add_group
        ).pack(side="left", padx=sc(2))
        
        tk.Button(
            btn_frame, text="Delete Group", font=("Hanken Grotesk", sc(9)),
            bg="#ffffff", fg="#ba1a1a", relief="solid", bd=1, cursor="hand2",
            padx=sc(8), pady=sc(3),
            command=delete_group
        ).pack(side="left", padx=sc(2))
        
        tk.Button(
            right, text="Assign Fields to Group", font=("Hanken Grotesk", sc(9), "bold"),
            bg="#1a1c1c", fg="#ffffff", relief="flat", bd=0, cursor="hand2",
            padx=sc(10), pady=sc(5),
            command=assign_fields
        ).pack(fill="x", pady=sc(5))
        
        tk.Button(
            self.main_frame, text="Next Step", font=("Hanken Grotesk", sc(10), "bold"),
            bg="#1a1c1c", fg="#ffffff", relief="flat", bd=0, cursor="hand2",
            padx=sc(16), pady=sc(6),
            command=self.step4_save_profile
        ).pack(pady=sc(10))

    def step4_save_profile(self):
        self.clear_frame()
        content = self._create_step_card("Step 4: Save Profile")
        
        tk.Label(content, text="Profile Name:", font=("Hanken Grotesk", sc(10), "bold"), bg="#ffffff", fg="#1a1c1c").pack(anchor="w")
        self.profile_name_var = tk.StringVar()
        entry_name = tk.Entry(
            content, textvariable=self.profile_name_var,
            relief="flat", bd=0,
            highlightthickness=1, highlightbackground="#d1d1d1",
            highlightcolor="#000000", insertbackground="#000000",
            bg="#ffffff", fg="#1a1c1c"
        )
        entry_name.pack(fill="x", pady=sc(5))
        
        tk.Label(content, text="Online Image URL Pattern (Optional):", font=("Hanken Grotesk", sc(10), "bold"), bg="#ffffff", fg="#1a1c1c").pack(anchor="w", pady=(sc(10), 0))
        self.image_url_pattern_var = tk.StringVar()
        entry_url = tk.Entry(
            content, textvariable=self.image_url_pattern_var,
            relief="flat", bd=0,
            highlightthickness=1, highlightbackground="#d1d1d1",
            highlightcolor="#000000", insertbackground="#000000",
            bg="#ffffff", fg="#1a1c1c"
        )
        entry_url.pack(fill="x", pady=sc(5))
        
        lbl_help = tk.Label(
            content, 
            text="Use {id} to insert the Object ID, or leave blank to append directly.", 
            font=("Hanken Grotesk", sc(9)), 
            bg="#ffffff", foreground="gray"
        )
        lbl_help.pack(anchor="w", pady=(0, sc(10)))
        
        tk.Button(
            self.main_frame, text="Save & Continue", font=("Hanken Grotesk", sc(10), "bold"),
            bg="#1a1c1c", fg="#ffffff", relief="flat", bd=0, cursor="hand2",
            padx=sc(16), pady=sc(6),
            command=self._save_profile_logic
        ).pack(pady=sc(10))

    def _save_profile_logic(self):
        name = self.profile_name_var.get().strip()
        if not name:
            messagebox.showwarning("Warning", "Enter a profile name.", parent=self.win)
            return
            
        if name in config.DATABASE_CONFIGS:
            if not messagebox.askyesno("Overwrite", f"Profile '{name}' already exists. Overwrite?", parent=self.win):
                return
                
        reg_sections = []
        for f in self.registration_fields:
            ftype = self.field_types.get(f, "text")
            reg_sections.append({"name": f, "type": ftype})
        reg_sections.append({"name": "UID", "type": "text", "readonly": True})
        
        problems_section = []
        for f, var in self.prob_vars.items():
            if var.get():
                problems_section.append({
                    "name": f"{f}_Problem",
                    "type": "bool",
                    "maps_to": f
                })
        problems_section.append({"name": "Images_Missing", "type": "bool"})
        problems_section.append({"name": "Other_problem", "type": "bool", "maps_to": "Other"})
        
        reg_groups_list = []
        if hasattr(self, 'reg_groups') and self.reg_groups:
            for g_name, g_fields in self.reg_groups.items():
                if g_fields:
                    reg_groups_list.append({"name": g_name, "fields": g_fields})

        url_pattern = self.image_url_pattern_var.get().strip()
        new_config = {
            "has_images": bool(url_pattern),
            "image_url_pattern": url_pattern,
            "sheets": {
                "reg": "Registration",
                "obs": "Observation",
                "photo": "Photo",
                "log": "Log",
            },
            "ui_sections": {
                "registration": reg_sections,
                "location": [], 
                "problems": problems_section,
                "unknown_fields": []
            }
        }
        
        if reg_groups_list:
            new_config["reg_groups"] = reg_groups_list

        
        prefs = config.load_prefs()
        if "custom_databases" not in prefs:
            prefs["custom_databases"] = {}
        prefs["custom_databases"][name] = new_config
        config.save_prefs(prefs)
        
        config.DATABASE_CONFIGS[name] = new_config
        self.app.config = new_config
        
        self.step5_save_location()

    def step5_save_location(self):
        import config
        file_path = filedialog.asksaveasfilename(
            parent=self.win,
            title="Choose where to save new database",
            defaultextension=".xlsx",
            filetypes=[("Excel files", "*.xlsx")],
            initialdir=config.get_last_dir("last_db_dir")
        )
        if not file_path:
            return
        config.set_last_dir("last_db_dir", file_path)
            
        self.initialize_database(file_path)

    def initialize_database(self, file_path):
        reg_cols = [f["name"] for f in self.app.config["ui_sections"].get("registration", [])]
        if "ObjectID" not in reg_cols:
            reg_cols.insert(0, "ObjectID")
            
        df_reg = pd.DataFrame(columns=reg_cols)
        df_reg.set_index("ObjectID", inplace=True)
        
        obs_cols = [f["name"] for f in self.app.config["ui_sections"].get("location", [])]
        prob_cols = [f["name"] for f in self.app.config["ui_sections"].get("problems", [])]
        obs_cols.extend(prob_cols)
        obs_cols.extend(["Reviewed", "ReviewedAt", "Images_Missing"])
        
        obs_cols = list(dict.fromkeys(obs_cols))
        
        df_obs = pd.DataFrame(columns=["ObjectID"] + obs_cols)
        df_obs.set_index("ObjectID", inplace=True)
        
        df_photo = pd.DataFrame(columns=["ObjectID", "ImagePath", "ImageNote"])
        df_photo.set_index("ObjectID", inplace=True)
        
        df_log = pd.DataFrame(columns=["Timestamp", "Action", "Columns", "Values"])
        
        with pd.ExcelWriter(file_path) as writer:
            df_reg.to_excel(writer, sheet_name=self.app.config["sheets"]["reg"])
            df_obs.to_excel(writer, sheet_name=self.app.config["sheets"]["obs"])
            df_photo.to_excel(writer, sheet_name=self.app.config["sheets"]["photo"])
            df_log.to_excel(writer, sheet_name=self.app.config["sheets"]["log"], index=False)
            
        self.app.excel_path = file_path
        self.app.output_path = file_path
        self.app.df_reg = df_reg
        self.app.df_obs = df_obs
        self.app.df_photo = df_photo
        self.app.df_log = df_log
        self.app.initial_df_obs = df_obs.copy()
        
        self.on_complete()
        self.win.destroy()
        messagebox.showinfo("Success", "New database initialized and ready!", parent=self.parent)
