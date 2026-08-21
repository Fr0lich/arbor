import tkinter as tk
from tkinter import ttk, messagebox
import pandas as pd
import config
from config import sc
import uuid

REVIEWED_COLUMN = "Reviewed"

# Design tokens matching AI_UI_GUIDE.md & Arbor theme
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
    "error": "#C62828",
    "on_error": "#ffffff",
    "error_container": "#ffebeb",
    "warning": "#FBC02D",
    "header_bg": "#f3f3f3",
    "card_bg": "#ffffff",
    "chip_bg": "#e2e2e2",
    "chip_active_bg": "#000000",
    "chip_active_fg": "#ffffff",
    "row_even": "#ffffff",
    "row_odd": "#f8f9fa",
    "select_bg": "#e2e2e2",
    "select_fg": "#000000",
    "step_active": "#2e6b30",
    "step_complete": "#2e6b30",
    "step_inactive": "#7e7576",
    "card_border": "#d1d1d1"
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
    "error_container": "#4c1414",
    "warning": "#f9e2af",
    "header_bg": "#181825",
    "card_bg": "#252538",
    "chip_bg": "#313244",
    "chip_active_bg": "#a6e3a1",
    "chip_active_fg": "#1e1e2e",
    "row_even": "#1e1e2e",
    "row_odd": "#181825",
    "select_bg": "#313244",
    "select_fg": "#cdd6f4",
    "step_active": "#a6e3a1",
    "step_complete": "#a6e3a1",
    "step_inactive": "#585b70",
    "card_border": "#45475a"
}

class AddObjectsWizard:
    STEP_NAMES = [
        "1. Object IDs",
        "2. Initial Metadata",
        "3. Review & Create"
    ]

    def __init__(self, parent, app, main_window):
        self.parent = parent
        self.app = app
        self.main_window = main_window

        if getattr(self.app, 'df_reg', None) is None:
            messagebox.showwarning("No data", "Initialize a database first.")
            return

        self.is_dark = config.load_prefs().get("dark_mode", False)
        self.colors = COLORS_DARK if self.is_dark else COLORS_LIGHT

        self.current_step = 0
        self.staged_data = {}
        self.current_selected_id = None
        self.field_vars = {}

        self.manual_ids_var = tk.StringVar()
        self.auto_n_var = tk.IntVar(value=1)

        self._setup_window()
        self._build_shell()
        self.goto_step(0)

    def _setup_window(self):
        self.win = tk.Toplevel(self.parent)
        self.win.title("Create New Objects")
        self.win.configure(bg=self.colors["surface"])
        self.win.grab_set()
        self.win.transient(self.parent)

        import utils
        utils.center_and_fit_toplevel(self.win, sc(780), sc(650))
        self.win.minsize(sc(640), sc(540))

        self.win.bind("<Escape>", lambda e: self._on_cancel())
        self.win.protocol("WM_DELETE_WINDOW", self._on_cancel)

    def _build_shell(self):
        # Header banner
        header_frame = tk.Frame(self.win, bg=self.colors["surface_container_low"], padx=sc(16), pady=sc(10))
        header_frame.pack(fill="x", side="top")

        title_row = tk.Frame(header_frame, bg=self.colors["surface_container_low"])
        title_row.pack(fill="x")

        title_lbl = tk.Label(title_row, text="Create New Objects", font=("Hanken Grotesk", sc(16), "bold"), bg=self.colors["surface_container_low"], fg=self.colors["on_surface"])
        title_lbl.pack(side="left")

        self.subtitle_lbl = tk.Label(title_row, text="Step 1", font=("Hanken Grotesk", sc(11)), bg=self.colors["surface_container_low"], fg=self.colors["on_surface_variant"])
        self.subtitle_lbl.pack(side="left", padx=(sc(10), 0), pady=(sc(4), 0))

        # Stepper
        self.stepper_frame = tk.Frame(header_frame, bg=self.colors["surface_container_low"])
        self.stepper_frame.pack(fill="x", pady=(sc(10), 0))
        self._build_stepper()

        # Main content area
        self.content_frame = tk.Frame(self.win, bg=self.colors["surface"], padx=sc(20), pady=sc(20))
        self.content_frame.pack(fill="both", expand=True)

        # Footer
        footer_frame = tk.Frame(self.win, bg=self.colors["surface_container"], padx=sc(16), pady=sc(12))
        footer_frame.pack(fill="x", side="bottom")

        self.cancel_btn = tk.Button(
            footer_frame, text="Cancel", font=("Hanken Grotesk", sc(10)),
            bg=self.colors["surface"], fg=self.colors["on_surface"],
            activebackground=self.colors["surface_container_high"], activeforeground=self.colors["on_surface"],
            relief="solid", bd=1, cursor="hand2", padx=sc(12), pady=sc(4),
            command=self._on_cancel
        )
        self.cancel_btn.pack(side="left")

        self.next_btn = tk.Button(
            footer_frame, text="Next  →", font=("Hanken Grotesk", sc(10), "bold"),
            bg=self.colors["primary"], fg=self.colors["on_primary"],
            activebackground=self.colors["on_surface_variant"], activeforeground=self.colors["on_primary"],
            relief="flat", bd=0, cursor="hand2", padx=sc(16), pady=sc(4),
            command=self._on_next
        )
        self.next_btn.pack(side="right")

        self.back_btn = tk.Button(
            footer_frame, text="←  Back", font=("Hanken Grotesk", sc(10)),
            bg=self.colors["surface"], fg=self.colors["on_surface"],
            activebackground=self.colors["surface_container_high"], activeforeground=self.colors["on_surface"],
            relief="solid", bd=1, cursor="hand2", padx=sc(12), pady=sc(4),
            command=self._on_back
        )
        self.back_btn.pack(side="right", padx=(0, sc(10)))

    def _build_stepper(self):
        for widget in self.stepper_frame.winfo_children():
            widget.destroy()

        self.step_labels = []
        for i, name in enumerate(self.STEP_NAMES):
            lbl = tk.Label(self.stepper_frame, text=name, font=("Hanken Grotesk", sc(9), "bold"), bg=self.colors["surface_container_low"], fg=self.colors["step_inactive"])
            lbl.pack(side="left", padx=(0, sc(16)))
            self.step_labels.append(lbl)

    def goto_step(self, step_num):
        # Clear content
        for widget in self.content_frame.winfo_children():
            widget.destroy()

        self.current_step = step_num
        self.subtitle_lbl.config(text=self.STEP_NAMES[step_num])

        for i, lbl in enumerate(self.step_labels):
            if i < step_num:
                lbl.config(fg=self.colors["step_complete"])
            elif i == step_num:
                lbl.config(fg=self.colors["step_active"])
            else:
                lbl.config(fg=self.colors["step_inactive"])

        self.back_btn.pack(side="right", padx=(0, sc(10)))
        if step_num == 0:
            self.back_btn.pack_forget()
            self.next_btn.config(text="Next  →")
        elif step_num == len(self.STEP_NAMES) - 1:
            self.next_btn.config(text="Create Objects")
        else:
            self.next_btn.config(text="Next  →")

        if step_num == 0:
            self._render_step1()
        elif step_num == 1:
            self._render_step2()
        elif step_num == 2:
            self._render_step3()

    def _render_step1(self):
        # Two pane layout: Left for tools, Right for list
        pane = tk.PanedWindow(self.content_frame, orient="horizontal", bd=0, sashwidth=sc(4), bg=self.colors["surface"])
        pane.pack(fill="both", expand=True)

        # LEFT PANE: Tools
        left_frame = tk.Frame(pane, bg=self.colors["surface"])
        pane.add(left_frame, minsize=sc(300), sticky="nsew")

        # Auto Generation Card
        auto_card = tk.LabelFrame(left_frame, text="Auto-Generate IDs", font=("Hanken Grotesk", sc(11), "bold"), bg=self.colors["card_bg"], fg=self.colors["on_surface"], padx=sc(10), pady=sc(10))
        auto_card.pack(fill="x", pady=(0, sc(16)))

        tk.Label(auto_card, text="Finds the highest numeric ID and adds N new IDs.", font=("Inter", sc(9)), bg=self.colors["card_bg"], fg=self.colors["on_surface_variant"], wraplength=sc(250), justify="left").pack(anchor="w", pady=(0, sc(8)))

        auto_row = tk.Frame(auto_card, bg=self.colors["card_bg"])
        auto_row.pack(fill="x")
        tk.Label(auto_row, text="Count:", font=("Inter", sc(9.5)), bg=self.colors["card_bg"], fg=self.colors["on_surface"]).pack(side="left")
        
        spin = ttk.Spinbox(auto_row, from_=1, to=1000, textvariable=self.auto_n_var, width=sc(8), font=("JetBrains Mono", sc(10)))
        spin.pack(side="left", padx=sc(8))

        tk.Button(
            auto_row, text="Generate", font=("Hanken Grotesk", sc(9)),
            bg=self.colors["select_bg"], fg=self.colors["select_fg"], relief="flat", bd=0, cursor="hand2", padx=sc(8), pady=sc(2),
            command=self._generate_auto_ids
        ).pack(side="left")

        # Manual Entry Card
        manual_card = tk.LabelFrame(left_frame, text="Manual Entry", font=("Hanken Grotesk", sc(11), "bold"), bg=self.colors["card_bg"], fg=self.colors["on_surface"], padx=sc(10), pady=sc(10))
        manual_card.pack(fill="x")

        tk.Label(manual_card, text="Comma separated IDs (e.g. A1, A2, B_100):", font=("Inter", sc(9)), bg=self.colors["card_bg"], fg=self.colors["on_surface_variant"]).pack(anchor="w", pady=(0, sc(4)))

        man_ent = tk.Entry(
            manual_card, textvariable=self.manual_ids_var, font=("JetBrains Mono", sc(10)),
            bg=self.colors["surface_container_low"], fg=self.colors["on_surface"], relief="flat", highlightthickness=1, highlightbackground=self.colors["card_border"]
        )
        man_ent.pack(fill="x", pady=(0, sc(8)))

        tk.Button(
            manual_card, text="Add IDs", font=("Hanken Grotesk", sc(9)),
            bg=self.colors["select_bg"], fg=self.colors["select_fg"], relief="flat", bd=0, cursor="hand2", padx=sc(8), pady=sc(2),
            command=self._add_manual_ids
        ).pack(anchor="e")

        # RIGHT PANE: Staged IDs List
        right_frame = tk.Frame(pane, bg=self.colors["surface"])
        pane.add(right_frame, minsize=sc(200), sticky="nsew")

        tk.Label(right_frame, text="Staged IDs to Create", font=("Hanken Grotesk", sc(11), "bold"), bg=self.colors["surface"], fg=self.colors["on_surface"]).pack(anchor="w", pady=(0, sc(4)))

        list_frame = tk.Frame(right_frame, bg=self.colors["surface"], highlightthickness=1, highlightbackground=self.colors["card_border"])
        list_frame.pack(fill="both", expand=True)

        self.target_listbox = tk.Listbox(
            list_frame, font=("JetBrains Mono", sc(10)),
            bg=self.colors["card_bg"], fg=self.colors["on_surface"],
            selectbackground=self.colors["select_bg"], selectforeground=self.colors["select_fg"],
            relief="flat", bd=0, highlightthickness=0
        )
        self.target_listbox.pack(side="left", fill="both", expand=True)
        
        sb = ttk.Scrollbar(list_frame, orient="vertical", command=self.target_listbox.yview)
        sb.pack(side="right", fill="y")
        self.target_listbox.config(yscrollcommand=sb.set)
        
        tk.Button(
            right_frame, text="Remove Selected", font=("Hanken Grotesk", sc(9)),
            bg=self.colors["error_container"], fg=self.colors["error"], relief="flat", bd=0, cursor="hand2", padx=sc(8), pady=sc(4),
            command=self._remove_selected_id
        ).pack(anchor="e", pady=(sc(8), 0))

        # Repopulate list if returning
        for oid in self.staged_data.keys():
            self.target_listbox.insert(tk.END, oid)

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
                self.staged_data[new_id] = {}

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
                    self.staged_data[p] = {}
        self.manual_ids_var.set("")

    def _remove_selected_id(self):
        sel = self.target_listbox.curselection()
        if not sel: return

        idx = sel[0]
        oid = self.target_listbox.get(idx)
        self.target_listbox.delete(idx)
        if oid in self.staged_data:
            del self.staged_data[oid]

    def _render_step2(self):
        pane = tk.PanedWindow(self.content_frame, orient="horizontal", bd=0, sashwidth=sc(4), bg=self.colors["surface"])
        pane.pack(fill="both", expand=True)

        # LEFT PANE: Select ID
        left_frame = tk.Frame(pane, bg=self.colors["surface"])
        pane.add(left_frame, minsize=sc(150), sticky="nsew")

        tk.Label(left_frame, text="Select Object", font=("Hanken Grotesk", sc(11), "bold"), bg=self.colors["surface"], fg=self.colors["on_surface"]).pack(anchor="w", pady=(0, sc(4)))

        list_frame = tk.Frame(left_frame, bg=self.colors["surface"], highlightthickness=1, highlightbackground=self.colors["card_border"])
        list_frame.pack(fill="both", expand=True)

        self.edit_listbox = tk.Listbox(
            list_frame, font=("JetBrains Mono", sc(10)),
            bg=self.colors["card_bg"], fg=self.colors["on_surface"],
            selectbackground=self.colors["select_bg"], selectforeground=self.colors["select_fg"],
            relief="flat", bd=0, highlightthickness=0, exportselection=False
        )
        self.edit_listbox.pack(side="left", fill="both", expand=True)
        sb = ttk.Scrollbar(list_frame, orient="vertical", command=self.edit_listbox.yview)
        sb.pack(side="right", fill="y")
        self.edit_listbox.config(yscrollcommand=sb.set)
        self.edit_listbox.bind("<<ListboxSelect>>", self._on_edit_listbox_select)

        for oid in sorted(self.staged_data.keys()):
            self.edit_listbox.insert(tk.END, oid)

        # RIGHT PANE: Edit Form
        right_frame = tk.Frame(pane, bg=self.colors["surface"])
        pane.add(right_frame, minsize=sc(300), sticky="nsew")

        tk.Label(right_frame, text="Set Initial Values", font=("Hanken Grotesk", sc(11), "bold"), bg=self.colors["surface"], fg=self.colors["on_surface"]).pack(anchor="w", pady=(0, sc(4)))

        # Create Scrollable Canvas for form
        canvas_frame = tk.Frame(right_frame, bg=self.colors["surface"], highlightthickness=1, highlightbackground=self.colors["card_border"])
        canvas_frame.pack(fill="both", expand=True)

        self.form_canvas = tk.Canvas(canvas_frame, bg=self.colors["card_bg"], highlightthickness=0)
        vsb = ttk.Scrollbar(canvas_frame, orient="vertical", command=self.form_canvas.yview)

        self.inner_form = tk.Frame(self.form_canvas, bg=self.colors["card_bg"], padx=sc(10), pady=sc(10))
        self.form_window = self.form_canvas.create_window((0, 0), window=self.inner_form, anchor="nw")

        self.inner_form.bind("<Configure>", lambda e: self.form_canvas.configure(scrollregion=self.form_canvas.bbox("all")))
        self.form_canvas.bind("<Configure>", lambda e: self.form_canvas.itemconfig(self.form_window, width=e.width))
        self.form_canvas.configure(yscrollcommand=vsb.set)

        self.form_canvas.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

        def _on_form_scroll(event):
            self.form_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        self.form_canvas.bind("<Enter>", lambda e: self.form_canvas.bind_all("<MouseWheel>", _on_form_scroll))
        self.form_canvas.bind("<Leave>", lambda e: self.form_canvas.unbind_all("<MouseWheel>"))

        # Build Fields based on config
        self.field_vars = {}
        row = 0

        def _build_section(title, fields):
            nonlocal row
            if not fields: return

            tk.Label(self.inner_form, text=title.upper(), font=("Hanken Grotesk", sc(11), "bold"), bg=self.colors["surface_container_low"], fg=self.colors["on_surface"], anchor="w", padx=sc(6), pady=sc(4)).grid(row=row, column=0, columnspan=2, sticky="ew", pady=(sc(10) if row > 0 else 0, sc(8)))
            row += 1

            for field in fields:
                name = field["name"]
                if field.get("readonly", False): continue

                ftype = field.get("type", "text")
                var = tk.StringVar()
                self.field_vars[name] = var

                tk.Label(self.inner_form, text=name, font=("Inter", sc(9.5)), bg=self.colors["card_bg"], fg=self.colors["on_surface_variant"], width=sc(15), anchor="w").grid(row=row, column=0, sticky="w", padx=sc(4), pady=sc(4))

                if ftype == "choice":
                    choices = [""] + field.get("choices", [])
                    cb = ttk.Combobox(self.inner_form, textvariable=var, values=choices, font=("Inter", sc(10)), state="readonly")
                    cb.grid(row=row, column=1, sticky="ew", padx=sc(4), pady=sc(4))
                elif ftype == "checkbox":
                    cb = ttk.Checkbutton(self.inner_form, text="Enable", variable=var, onvalue="True", offvalue="False")
                    cb.grid(row=row, column=1, sticky="w", padx=sc(4), pady=sc(4))
                else:
                    ent = tk.Entry(self.inner_form, textvariable=var, font=("Inter", sc(10)), bg=self.colors["surface_container_low"], fg=self.colors["on_surface"], relief="flat", highlightthickness=1, highlightbackground=self.colors["card_border"])
                    ent.grid(row=row, column=1, sticky="ew", padx=sc(4), pady=sc(4))
                row += 1

        self.inner_form.columnconfigure(1, weight=1)

        reg_fields = self.app.config.get("ui_sections", {}).get("registration", [])
        loc_fields = self.app.config.get("ui_sections", {}).get("location", [])

        _build_section("Registration", reg_fields)
        _build_section("Location", loc_fields)

        # Ensure all staged data dicts have keys for all active fields
        for oid in self.staged_data:
            for k in self.field_vars:
                if k not in self.staged_data[oid]:
                    self.staged_data[oid][k] = ""

        # Auto-select first item
        self.current_selected_id = None
        if self.edit_listbox.size() > 0:
            self.edit_listbox.selection_set(0)
            self._on_edit_listbox_select(None)

    def _save_current_staged_data(self):
        if self.current_selected_id is not None and self.current_selected_id in self.staged_data:
            for k, v in self.field_vars.items():
                self.staged_data[self.current_selected_id][k] = v.get()

    def _load_staged_data(self, oid):
        if oid in self.staged_data:
            for k, v in self.field_vars.items():
                v.set(self.staged_data[oid].get(k, ""))

    def _on_edit_listbox_select(self, event):
        sel = self.edit_listbox.curselection()
        if not sel: return

        new_id = self.edit_listbox.get(sel[0])
        if new_id == self.current_selected_id: return

        self._save_current_staged_data()
        self._load_staged_data(new_id)
        self.current_selected_id = new_id

    def _render_step3(self):
        container = tk.Frame(self.content_frame, bg=self.colors["surface"])
        container.place(relx=0.5, rely=0.5, anchor="center")

        n_objects = len(self.staged_data)

        tk.Label(container, text="Ready to create", font=("Hanken Grotesk", sc(14)), bg=self.colors["surface"], fg=self.colors["on_surface_variant"]).pack(pady=(0, sc(4)))
        tk.Label(container, text=f"{n_objects} Object{'s' if n_objects != 1 else ''}", font=("Hanken Grotesk", sc(24), "bold"), bg=self.colors["surface"], fg=self.colors["on_surface"]).pack(pady=(0, sc(16)))

        tk.Label(container, text="Click 'Create Objects' below to commit these to your database.", font=("Inter", sc(10)), bg=self.colors["surface"], fg=self.colors["on_surface_variant"]).pack(pady=(0, sc(20)))

    def _on_next(self):
        if self.current_step == 0:
            if not self.staged_data:
                messagebox.showwarning("No IDs", "Please add at least one Object ID to continue.", parent=self.win)
                return
            self.goto_step(1)
        elif self.current_step == 1:
            self._save_current_staged_data()
            self.goto_step(2)
        elif self.current_step == 2:
            self._create_objects()

    def _create_objects(self):
        oids = list(self.staged_data.keys())
        if not oids:
            messagebox.showwarning("No IDs", "Add at least one target Object ID to create.", parent=self.win)
            return

        for oid in oids:
            if oid in self.app.df_reg.index:
                messagebox.showerror("Conflict", f"Object {oid} already exists!", parent=self.win)
                return

        problem_columns = [f["name"] for f in self.app.config.get("ui_sections", {}).get("problems", [])]
        location_fields = self.app.config.get("ui_sections", {}).get("location", [])
        location_columns = [f["name"] for f in location_fields]
        checkbox_loc_cols = {f["name"] for f in location_fields if f.get("type") == "checkbox"}
        bool_cols = set(problem_columns) | {"Images_Problem", "Images_Wrong", REVIEWED_COLUMN, "Online_Images_Exist"}
        all_obs_cols = list(self.app.df_obs.columns) if self.app.df_obs is not None else []

        new_reg_dict = {}
        new_obs_dict = {}
        new_photo_dict = {}

        for oid in oids:
            obj_data = self.staged_data.get(oid, {})
            updates = {k: v for k, v in obj_data.items() if str(v).strip()}
            
            # df_reg row
            reg_row = {col: "" for col in self.app.df_reg.columns}
            reg_row["UID"] = uuid.uuid4().hex[:8]
            for k, v in updates.items():
                if k in self.app.df_reg.columns:
                    reg_row[k] = v
            new_reg_dict[oid] = reg_row

            # df_obs row
            obs_row = {}
            for col in all_obs_cols:
                if col in bool_cols:
                    obs_row[col] = False
                elif col == "Images_Missing":
                    obs_row[col] = True
                elif col in checkbox_loc_cols:
                    obs_row[col] = "False"
                else:
                    obs_row[col] = ""
            
            # Guarantee core required columns
            obs_row["Images_Missing"] = True
            obs_row["Images_Problem"] = False
            obs_row["Images_Wrong"] = False
            obs_row[REVIEWED_COLUMN] = False
            obs_row["ReviewedAt"] = ""
            obs_row["Online_Images_Exist"] = False
            
            for col in location_columns:
                if col in updates:
                    obs_row[col] = updates[col]
                elif col in checkbox_loc_cols:
                    obs_row[col] = "False"
                
            new_obs_dict[oid] = obs_row

            if getattr(self.app, 'df_photo', None) is not None and not self.app.df_photo.empty:
                new_photo_dict[oid] = {col: "" for col in self.app.df_photo.columns}

            if not hasattr(self.app, 'active_object_ids'):
                self.app.active_object_ids = []
            if oid not in self.app.active_object_ids:
                self.app.active_object_ids.append(oid)
            
            if hasattr(self.main_window, 'log_action'):
                self.main_window.log_action(
                    "CREATE_OBJECT",
                    ["ObjectID"],
                    [f"Created {oid}"]
                )

        # Batch append to dataframes (zero fragmentation)
        if new_reg_dict:
            new_reg_df = pd.DataFrame.from_dict(new_reg_dict, orient="index")
            new_reg_df.index.name = self.app.df_reg.index.name
            self.app.df_reg = pd.concat([self.app.df_reg, new_reg_df])

        if new_obs_dict:
            new_obs_df = pd.DataFrame.from_dict(new_obs_dict, orient="index")
            new_obs_df.index.name = self.app.df_obs.index.name
            self.app.df_obs = pd.concat([self.app.df_obs, new_obs_df])

        if new_photo_dict and getattr(self.app, 'df_photo', None) is not None:
            new_photo_df = pd.DataFrame.from_dict(new_photo_dict, orient="index")
            new_photo_df.index.name = self.app.df_photo.index.name
            self.app.df_photo = pd.concat([self.app.df_photo, new_photo_df])

        if hasattr(self.main_window, '_invalidate_row_cache'):
            self.main_window._invalidate_row_cache()
        if hasattr(self.main_window, 'invalidate_search_index'):
            self.main_window.invalidate_search_index()
        if hasattr(self.main_window, 'refresh_list'):
            self.main_window.refresh_list()
        
        # Select the first created object
        if hasattr(self.main_window, 'object_list') and hasattr(self.main_window, 'load_object'):
            try:
                idx = self.app.active_object_ids.index(oids[0])
                self.main_window.object_list.selection_clear(0, tk.END)
                self.main_window.object_list.selection_set(idx)
                self.main_window.object_list.see(idx)
                self.main_window.load_object(oids[0])
            except Exception:
                pass

        self.app.dirty = True
        if hasattr(self.main_window, 'update_dirty_ui'):
            self.main_window.update_dirty_ui()
        if hasattr(self.main_window, 'update_object_count'):
            self.main_window.update_object_count()
        if hasattr(self.main_window, 'update_review_progress'):
            self.main_window.update_review_progress()

        messagebox.showinfo("Success", f"Successfully created {len(oids)} object(s).", parent=self.main_window.root)
        self.win.destroy()

    def _on_back(self):
        if self.current_step > 0:
            if self.current_step == 1:
                self._save_current_staged_data()
            self.goto_step(self.current_step - 1)

    def _on_cancel(self):
        self.win.destroy()
