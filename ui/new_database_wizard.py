"""
ui/new_database_wizard.py - Modern New Database Setup Wizard for Arbor

Provides an intuitive, responsive multi-step wizard for creating new databases
from built-in starter templates, Excel/CSV schemas, or from scratch.
"""

import os
import re
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog
from datetime import datetime
import pandas as pd
import config
from config import sc

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
    "error": "#ba1a1a",
    "on_error": "#ffffff",
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


class NewDatabaseWizard:
    """
    Modern 5-Step New Database Creation Wizard.
    Steps:
      1. Profile & Template / Data Source
      2. Schema & Field Editor
      3. Problem Flags & Field Groups
      4. Image URL & Location Modules
      5. Review, Starting ID & Initialization
    """

    STEP_NAMES = [
        "1. Template & Source",
        "2. Schema & Fields",
        "3. Flags & Groups",
        "4. Image & Location",
        "5. Review & Create"
    ]

    def __init__(self, parent, app=None, on_complete=None):
        self.parent = parent
        self.app = app
        self.on_complete = on_complete

        # Detect dark mode
        self.dark_mode = False
        if app and hasattr(app, "dark_mode_active"):
            self.dark_mode = app.dark_mode_active
        else:
            self.dark_mode = config.load_prefs().get("dark_mode", False)

        self.colors = COLORS_DARK if self.dark_mode else COLORS_LIGHT

        # State data for database config
        self.current_step = 1
        self.max_step_visited = 1
        self.selected_template = "Botany / Herbarium"
        self.profile_name = "My New Database"
        
        # Schema definition: list of dicts {"name": str, "type": str, "readonly": bool, "choices": list}
        self.fields = []
        # Problem flags: dict of field_name -> bool
        self.problem_flags = {}
        self.common_problems = {
            "Images_Problem": True,
            "Other_problem": True
        }
        # Groups: dict of group_name -> list of field names
        self.groups = {}
        # Image config
        self.has_images = True
        self.image_url_pattern = "https://www.unimus.no/photos/image/jpeg/O-V-OE-{num:04d}{suffix}.jpg"
        # Location & Loan toggles
        self.include_location = True
        self.include_loan = False
        # Starting object ID and record count
        self.start_object_id = "1"
        self.initial_records_count = 1
        self.output_file_path = ""

        # Initialize default template schema
        self._load_template_data("Botany / Herbarium")

        # Fonts
        self.FONT_TITLE = ("Lora", sc(13), "bold")
        self.FONT_STEPPER = ("Hanken Grotesk", sc(9), "bold")
        self.FONT_HEADER = ("Hanken Grotesk", sc(11), "bold")
        self.FONT_LABEL = ("Hanken Grotesk", sc(10))
        self.FONT_LABEL_BOLD = ("Hanken Grotesk", sc(10), "bold")
        self.FONT_SMALL = ("Inter", sc(9))
        self.FONT_MONO = ("JetBrains Mono", sc(10))
        self.FONT_BUTTON = ("Hanken Grotesk", sc(9.5), "bold")

        # Build Window
        self._setup_window()
        self._build_shell()
        self.goto_step(1)

    def _setup_window(self):
        self.win = tk.Toplevel(self.parent)
        self.win.title("New Database Setup Wizard")
        self.win.configure(bg=self.colors["surface"])
        self.win.grab_set()
        self.win.transient(self.parent)

        import utils
        utils.center_and_fit_toplevel(self.win, sc(720), sc(650))
        self.win.minsize(sc(600), sc(520))

        self.win.bind("<Escape>", lambda e: self._on_cancel())
        self.win.protocol("WM_DELETE_WINDOW", self._on_cancel)

    def _build_shell(self):
        # Header banner
        header_frame = tk.Frame(self.win, bg=self.colors["surface_container_low"], padx=sc(16), pady=sc(10))
        header_frame.pack(fill="x", side="top")

        title_row = tk.Frame(header_frame, bg=self.colors["surface_container_low"])
        title_row.pack(fill="x")
        
        tk.Label(
            title_row, text="Create New Database",
            font=self.FONT_TITLE, bg=self.colors["surface_container_low"],
            fg=self.colors["on_surface"]
        ).pack(side="left")

        self.step_indicator_lbl = tk.Label(
            title_row, text="Step 1 of 5",
            font=self.FONT_STEPPER, bg=self.colors["surface_container_highest"],
            fg=self.colors["on_surface"], padx=sc(8), pady=sc(2)
        )
        self.step_indicator_lbl.pack(side="right")

        # Stepper Progress Bar
        self.stepper_frame = tk.Frame(header_frame, bg=self.colors["surface_container_low"], pady=sc(8))
        self.stepper_frame.pack(fill="x")
        self._build_stepper()

        # Divider
        tk.Frame(self.win, bg=self.colors["card_border"], height=1).pack(fill="x", side="top")

        # Content Frame
        self.content_container = tk.Frame(self.win, bg=self.colors["surface"])
        self.content_container.pack(fill="both", expand=True, padx=sc(16), pady=sc(12))

        # Bottom Action Bar
        action_bar = tk.Frame(self.win, bg=self.colors["surface_container_low"], padx=sc(16), pady=sc(10))
        action_bar.pack(fill="x", side="bottom")
        tk.Frame(self.win, bg=self.colors["card_border"], height=1).pack(fill="x", side="bottom")

        self.btn_cancel = tk.Button(
            action_bar, text="Cancel", font=self.FONT_BUTTON,
            bg=self.colors["card_bg"], fg=self.colors["on_surface"],
            relief="solid", bd=1, cursor="hand2", padx=sc(12), pady=sc(5),
            command=self._on_cancel
        )
        self.btn_cancel.pack(side="left")

        self.btn_next = tk.Button(
            action_bar, text="Next Step →", font=self.FONT_BUTTON,
            bg=self.colors["primary"], fg=self.colors["on_primary"],
            relief="flat", bd=0, cursor="hand2", padx=sc(16), pady=sc(6),
            command=self._on_next
        )
        self.btn_next.pack(side="right")

        self.btn_back = tk.Button(
            action_bar, text="← Back", font=self.FONT_BUTTON,
            bg=self.colors["card_bg"], fg=self.colors["on_surface"],
            relief="solid", bd=1, cursor="hand2", padx=sc(12), pady=sc(5),
            command=self._on_back
        )
        self.btn_back.pack(side="right", padx=(0, sc(8)))

    def _build_stepper(self):
        for widget in self.stepper_frame.winfo_children():
            widget.destroy()

        self.step_nodes = []
        cols = len(self.STEP_NAMES)
        for i in range(cols * 2 - 1):
            self.stepper_frame.columnconfigure(i, weight=1 if i % 2 == 1 else 0)

        for i, name in enumerate(self.STEP_NAMES, start=1):
            col_idx = (i - 1) * 2

            node_frame = tk.Frame(self.stepper_frame, bg=self.colors["surface_container_low"], cursor="hand2")
            node_frame.grid(row=0, column=col_idx, sticky="ew")
            node_frame.bind("<Button-1>", lambda e, s=i: self._on_step_click(s))

            is_active = (i == self.current_step)
            is_done = (i < self.current_step)

            badge_bg = self.colors["step_active"] if is_active else (self.colors["step_complete"] if is_done else self.colors["surface_container_highest"])
            badge_fg = "#ffffff" if (is_active or is_done) else self.colors["step_inactive"]
            badge_text = "✓" if is_done else str(i)

            badge = tk.Label(
                node_frame, text=badge_text, font=("Hanken Grotesk", sc(8.5), "bold"),
                bg=badge_bg, fg=badge_fg, width=2, height=1, relief="flat"
            )
            badge.pack(side="left", padx=(0, sc(4)))
            badge.bind("<Button-1>", lambda e, s=i: self._on_step_click(s))

            lbl = tk.Label(
                node_frame, text=name.split(". ")[1],
                font=("Hanken Grotesk", sc(8.5), "bold" if is_active else "normal"),
                bg=self.colors["surface_container_low"],
                fg=self.colors["on_surface"] if (is_active or is_done) else self.colors["step_inactive"]
            )
            lbl.pack(side="left")
            lbl.bind("<Button-1>", lambda e, s=i: self._on_step_click(s))

            self.step_nodes.append((badge, lbl, node_frame))

            # Connecting line between step nodes
            if i < cols:
                line_col = col_idx + 1
                line_bg = self.colors["step_complete"] if i < self.current_step else self.colors["card_border"]
                line = tk.Frame(self.stepper_frame, bg=line_bg, height=2)
                line.grid(row=0, column=line_col, sticky="ew", padx=sc(4))

    def _on_step_click(self, step_num):
        if step_num <= self.max_step_visited:
            if self._validate_step(self.current_step):
                self.goto_step(step_num)

    def _create_scrollable_card(self, title):
        card = tk.Frame(self.content_container, bg=self.colors["card_bg"], highlightthickness=1, highlightbackground=self.colors["card_border"])
        card.pack(fill="both", expand=True)

        hdr = tk.Frame(card, bg=self.colors["surface_container_low"], padx=sc(12), pady=sc(8))
        hdr.pack(fill="x", side="top")
        tk.Label(hdr, text=title.upper(), font=self.FONT_HEADER, bg=self.colors["surface_container_low"], fg=self.colors["on_surface"]).pack(anchor="w")

        tk.Frame(card, bg=self.colors["card_border"], height=1).pack(fill="x", side="top")

        content_frame = tk.Frame(card, bg=self.colors["card_bg"])
        content_frame.pack(fill="both", expand=True, side="top")

        canvas = tk.Canvas(content_frame, bg=self.colors["card_bg"], highlightthickness=0)
        scrollbar = ttk.Scrollbar(content_frame, orient="vertical", command=canvas.yview)
        inner = tk.Frame(canvas, bg=self.colors["card_bg"], padx=sc(12), pady=sc(10))

        inner_id = canvas.create_window((0, 0), window=inner, anchor="nw")

        def _on_inner_config(e):
            canvas.configure(scrollregion=canvas.bbox("all"))

        def _on_canvas_config(e):
            canvas.itemconfig(inner_id, width=e.width)

        inner.bind("<Configure>", _on_inner_config)
        canvas.bind("<Configure>", _on_canvas_config)
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # Mousewheel scroll support
        def _on_mousewheel(e):
            if canvas.winfo_exists():
                canvas.yview_scroll(int(-1 * (e.delta / 120)), "units")

        canvas.bind_all("<MouseWheel>", _on_mousewheel)

        return inner

    def goto_step(self, step_num):
        self.current_step = step_num
        self.max_step_visited = max(self.max_step_visited, step_num)
        self.step_indicator_lbl.config(text=f"Step {step_num} of 5")
        self._build_stepper()

        # Update button states
        self.btn_back.config(state="normal" if step_num > 1 else "disabled")
        if step_num == 5:
            self.btn_next.config(text="✨ Create Database", bg=self.colors["secondary"])
        else:
            self.btn_next.config(text="Next Step →", bg=self.colors["primary"])

        # Clear existing content
        for w in self.content_container.winfo_children():
            w.destroy()

        if step_num == 1:
            self._render_step1()
        elif step_num == 2:
            self._render_step2()
        elif step_num == 3:
            self._render_step3()
        elif step_num == 4:
            self._render_step4()
        elif step_num == 5:
            self._render_step5()

    def _on_next(self):
        if not self._validate_step(self.current_step):
            return
        if self.current_step < 5:
            self.goto_step(self.current_step + 1)
        else:
            self._initialize_database()

    def _on_back(self):
        if self.current_step > 1:
            self.goto_step(self.current_step - 1)

    def _on_cancel(self):
        if messagebox.askyesno("Cancel Setup", "Are you sure you want to exit the database setup wizard?", parent=self.win):
            self.win.destroy()

    def _validate_step(self, step):
        if step == 2:
            if not self.fields:
                messagebox.showwarning("Validation Warning", "Please add at least one registration field.", parent=self.win)
                return False
            # Check unique names
            names = [f["name"].strip().lower() for f in self.fields if f["name"].strip()]
            if len(names) != len(set(names)):
                messagebox.showwarning("Validation Warning", "Field names must be unique.", parent=self.win)
                return False
        elif step == 5:
            name = self.profile_name_var.get().strip()
            if not name:
                messagebox.showwarning("Validation Warning", "Please specify a profile name.", parent=self.win)
                return False
            path = self.output_path_var.get().strip()
            if not path:
                messagebox.showwarning("Validation Warning", "Please choose a destination file path.", parent=self.win)
                return False
        return True

    # --------------------------------------------------------------------------
    # Template loading helpers
    # --------------------------------------------------------------------------
    def _load_template_data(self, template_key):
        self.selected_template = template_key
        
        cfg_key = template_key
        if hasattr(config, "BUILTIN_TEMPLATES") and template_key in config.BUILTIN_TEMPLATES:
            cfg_key = config.BUILTIN_TEMPLATES[template_key].get("config_key", template_key)

        template_cfg = config.DATABASE_CONFIGS.get(cfg_key, {})
        ui_sections = template_cfg.get("ui_sections", {})
        
        # Load fields
        reg_fields = ui_sections.get("registration", [])
        self.fields = []
        for rf in reg_fields:
            if rf.get("name") == "ObjectID":
                continue
            self.fields.append({
                "name": rf.get("name", ""),
                "type": rf.get("type", "text"),
                "readonly": rf.get("readonly", False),
                "choices": rf.get("choices", [])
            })

        if not self.fields:
            # Minimal fallback
            self.fields = [
                {"name": "Title", "type": "text", "readonly": False, "choices": []},
                {"name": "Category", "type": "text", "readonly": False, "choices": []},
                {"name": "Date", "type": "text", "readonly": False, "choices": []},
                {"name": "Description", "type": "multiline", "readonly": False, "choices": []},
                {"name": "UID", "type": "text", "readonly": True, "choices": []}
            ]

        # Load problem flags
        probs = ui_sections.get("problems", [])
        self.problem_flags = {}
        for p in probs:
            p_map = p.get("maps_to")
            if p_map and p_map != "Other":
                self.problem_flags[p_map] = True

        # Load groups
        self.groups = {}
        for g in ui_sections.get("reg_groups", []):
            g_name = g.get("name")
            g_fields = g.get("fields", [])
            if g_name:
                self.groups[g_name] = [f for f in g_fields if f != "ObjectID"]

        # Load image settings
        self.has_images = template_cfg.get("has_images", False)
        self.image_url_pattern = template_cfg.get("image_url_pattern", "")

        # Default profile name
        self.profile_name = template_key.replace(" / ", "_").replace(" ", "_") + "_DB"

    # --------------------------------------------------------------------------
    # STEP 1: Template & Source Selection
    # --------------------------------------------------------------------------
    def _render_step1(self):
        inner = self._create_scrollable_card("Step 1: Choose Starter Template or Import Schema")

        tk.Label(
            inner, text="Select a domain starter template, import from an existing Excel/CSV file, or build from scratch.",
            font=self.FONT_SMALL, bg=self.colors["card_bg"], fg=self.colors["on_surface_variant"]
        ).pack(anchor="w", pady=(0, sc(10)))

        # 3 Built-in Core Template Cards
        templates_grid = tk.Frame(inner, bg=self.colors["card_bg"])
        templates_grid.pack(fill="x", pady=sc(4))

        templates = [
            ("Botany / Herbarium", "🌿", "Specimen & Taxonomy", "Standard herbarium collection schema with taxonomy, collection details, plant parts, and observation notes."),
            ("Loan Tracking", "📋", "Loans & Curatorial", "Track outbound items, borrowers, institutions, loan dates, due dates, statuses, and return conditions."),
            ("Blank Minimal", "📄", "Minimal & Fast", "A light, clean starter schema with Title, Category, Date, Status, Description, and Notes.")
        ]

        self.template_cards = []
        for name, icon, badge, desc in templates:
            card = self._build_template_card(templates_grid, name, icon, badge, desc)
            card.pack(fill="x", pady=sc(4))
            self.template_cards.append((name, card))

        self._highlight_selected_template()

        # Separator
        ttk.Separator(inner, orient="horizontal").pack(fill="x", pady=sc(12))

        # Secondary Actions: Import File & Scratch
        tk.Label(
            inner, text="Or import from an existing file or profile:",
            font=self.FONT_LABEL_BOLD, bg=self.colors["card_bg"], fg=self.colors["on_surface"]
        ).pack(anchor="w", pady=(0, sc(6)))

        btn_row = tk.Frame(inner, bg=self.colors["card_bg"])
        btn_row.pack(fill="x", pady=sc(2))

        btn_import = tk.Button(
            btn_row, text="📊 Import from Excel / CSV", font=self.FONT_BUTTON,
            bg=self.colors["surface_container_low"], fg=self.colors["on_surface"],
            relief="solid", bd=1, cursor="hand2", padx=sc(12), pady=sc(6),
            command=self._import_schema_file
        )
        btn_import.pack(side="left", fill="x", expand=True, padx=(0, sc(4)))

        btn_scratch = tk.Button(
            btn_row, text="✏ Create Blank Custom", font=self.FONT_BUTTON,
            bg=self.colors["surface_container_low"], fg=self.colors["on_surface"],
            relief="solid", bd=1, cursor="hand2", padx=sc(12), pady=sc(6),
            command=self._create_scratch_schema
        )
        btn_scratch.pack(side="right", fill="x", expand=True, padx=(sc(4), 0))

        # Existing Profiles Dropdown
        existing_profiles = list(config.DATABASE_CONFIGS.keys())
        if existing_profiles:
            prof_row = tk.Frame(inner, bg=self.colors["card_bg"])
            prof_row.pack(fill="x", pady=(sc(10), sc(4)))
            
            tk.Label(prof_row, text="Load from existing profile:", font=self.FONT_LABEL, bg=self.colors["card_bg"], fg=self.colors["on_surface"]).pack(side="left", padx=(0, sc(8)))
            self.profile_cb_var = tk.StringVar(value=existing_profiles[0])
            cb = ttk.Combobox(prof_row, textvariable=self.profile_cb_var, values=existing_profiles, state="readonly", width=24)
            cb.pack(side="left", padx=(0, sc(8)))
            
            tk.Button(
                prof_row, text="Load", font=self.FONT_SMALL,
                bg=self.colors["primary"], fg=self.colors["on_primary"],
                relief="flat", bd=0, cursor="hand2", padx=sc(10), pady=sc(3),
                command=lambda: self._select_existing_profile(self.profile_cb_var.get())
            ).pack(side="left")

    def _build_template_card(self, parent, name, icon, badge, desc):
        card = tk.Frame(
            parent, bg=self.colors["surface_container_low"],
            highlightthickness=1, highlightbackground=self.colors["card_border"],
            cursor="hand2", padx=sc(12), pady=sc(8)
        )
        card.bind("<Button-1>", lambda e, n=name: self._select_template(n))

        top = tk.Frame(card, bg=self.colors["surface_container_low"])
        top.pack(fill="x")
        top.bind("<Button-1>", lambda e, n=name: self._select_template(n))

        tk.Label(
            top, text=f"{icon} {name}", font=self.FONT_HEADER,
            bg=self.colors["surface_container_low"], fg=self.colors["on_surface"]
        ).pack(side="left")

        tk.Label(
            top, text=badge, font=("Inter", sc(8), "bold"),
            bg=self.colors["surface_container_highest"], fg=self.colors["on_surface"],
            padx=sc(6), pady=sc(1)
        ).pack(side="right")

        tk.Label(
            card, text=desc, font=self.FONT_SMALL,
            bg=self.colors["surface_container_low"], fg=self.colors["on_surface_variant"],
            wraplength=sc(580), justify="left"
        ).pack(anchor="w", pady=(sc(4), 0))

        return card

    def _select_template(self, name):
        self._load_template_data(name)
        self._highlight_selected_template()

    def _highlight_selected_template(self):
        for name, card in getattr(self, "template_cards", []):
            if name == self.selected_template:
                card.config(highlightbackground=self.colors["secondary"], highlightthickness=2)
            else:
                card.config(highlightbackground=self.colors["card_border"], highlightthickness=1)

    def _select_existing_profile(self, name):
        self._load_template_data(name)
        messagebox.showinfo("Profile Loaded", f"Loaded profile '{name}' schema successfully!", parent=self.win)
        self.goto_step(2)

    def _import_schema_file(self):
        file_path = filedialog.askopenfilename(
            parent=self.win,
            title="Select Spreadsheet to Import Schema",
            filetypes=[("Excel / CSV files", "*.xlsx *.xls *.csv")],
            initialdir=config.get_last_dir("last_db_dir")
        )
        if not file_path:
            return
        config.set_last_dir("last_db_dir", file_path)

        try:
            if file_path.endswith(".csv"):
                df = pd.read_csv(file_path, nrows=50)
            else:
                df = pd.read_excel(file_path, nrows=50)

            inferred_fields = []
            for col in df.columns:
                col_str = str(col).strip()
                if col_str.lower() == "objectid":
                    continue

                col_lower = col_str.lower()
                series = df[col].dropna()

                # Infer type
                if any(kw in col_lower for kw in ["comment", "obs", "notat", "beskrivelse", "description", "note"]):
                    ftype = "multiline"
                elif series.dtype == bool or (len(series) > 0 and set(series.unique()).issubset({True, False, 0, 1, "0", "1", "true", "false", "yes", "no"})):
                    ftype = "checkbox"
                elif len(series) > 0 and len(series.unique()) <= 6 and series.dtype == object:
                    ftype = "choice"
                else:
                    ftype = "text"

                inferred_fields.append({
                    "name": col_str,
                    "type": ftype,
                    "readonly": (col_str.upper() == "UID"),
                    "choices": list(series.unique()) if ftype == "choice" else []
                })

            if "UID" not in [f["name"] for f in inferred_fields]:
                inferred_fields.append({"name": "UID", "type": "text", "readonly": True, "choices": []})

            self.fields = inferred_fields
            self.problem_flags = {f["name"]: True for f in inferred_fields if not f.get("readonly")}
            self.groups = {"General": [f["name"] for f in inferred_fields if f["name"] != "UID"], "Admin": ["UID"]}
            base_name = os.path.splitext(os.path.basename(file_path))[0]
            self.profile_name = f"{base_name}_DB"
            self.selected_template = f"Imported: {base_name}"

            messagebox.showinfo("Import Successful", f"Successfully imported {len(self.fields)} fields from:\n{os.path.basename(file_path)}", parent=self.win)
            self.goto_step(2)
        except Exception as e:
            messagebox.showerror("Import Error", f"Failed to parse schema from file:\n{e}", parent=self.win)

    def _create_scratch_schema(self):
        self.fields = [
            {"name": "Title", "type": "text", "readonly": False, "choices": []},
            {"name": "Description", "type": "multiline", "readonly": False, "choices": []},
            {"name": "UID", "type": "text", "readonly": True, "choices": []}
        ]
        self.problem_flags = {"Title": True}
        self.groups = {"General": ["Title", "Description"], "Admin": ["UID"]}
        self.selected_template = "Custom Scratch"
        self.profile_name = "Custom_DB"
        self.goto_step(2)

    # --------------------------------------------------------------------------
    # STEP 2: Interactive Schema Builder
    # --------------------------------------------------------------------------
    def _render_step2(self):
        inner = self._create_scrollable_card("Step 2: Customize Schema & Field Definitions")

        # Top Add Field Bar
        add_bar = tk.Frame(inner, bg=self.colors["card_bg"])
        add_bar.pack(fill="x", pady=(0, sc(8)))

        tk.Label(add_bar, text="New Field Name:", font=self.FONT_LABEL_BOLD, bg=self.colors["card_bg"], fg=self.colors["on_surface"]).pack(side="left", padx=(0, sc(6)))
        
        self.new_field_var = tk.StringVar()
        entry = tk.Entry(
            add_bar, textvariable=self.new_field_var, font=self.FONT_MONO,
            relief="solid", bd=1, highlightthickness=0, bg=self.colors["surface"], fg=self.colors["on_surface"]
        )
        entry.pack(side="left", fill="x", expand=True, padx=(0, sc(6)), ipady=sc(3))
        entry.bind("<Return>", lambda e: self._add_field())

        self.new_field_type_var = tk.StringVar(value="text")
        cb = ttk.Combobox(add_bar, textvariable=self.new_field_type_var, values=["text", "multiline", "choice", "checkbox"], state="readonly", width=10)
        cb.pack(side="left", padx=(0, sc(6)))

        btn_add = tk.Button(
            add_bar, text="+ Add Field", font=self.FONT_BUTTON,
            bg=self.colors["primary"], fg=self.colors["on_primary"],
            relief="flat", bd=0, cursor="hand2", padx=sc(10), pady=sc(3),
            command=self._add_field
        )
        btn_add.pack(side="right")

        # Table Header
        table_hdr = tk.Frame(inner, bg=self.colors["surface_container_low"], padx=sc(8), pady=sc(4))
        table_hdr.pack(fill="x")
        
        tk.Label(table_hdr, text="#", font=self.FONT_STEPPER, width=3, bg=self.colors["surface_container_low"], fg=self.colors["on_surface"]).pack(side="left")
        tk.Label(table_hdr, text="FIELD NAME", font=self.FONT_STEPPER, width=24, anchor="w", bg=self.colors["surface_container_low"], fg=self.colors["on_surface"]).pack(side="left", padx=sc(4))
        tk.Label(table_hdr, text="DATA TYPE", font=self.FONT_STEPPER, width=14, anchor="w", bg=self.colors["surface_container_low"], fg=self.colors["on_surface"]).pack(side="left", padx=sc(4))
        tk.Label(table_hdr, text="READONLY", font=self.FONT_STEPPER, width=10, anchor="w", bg=self.colors["surface_container_low"], fg=self.colors["on_surface"]).pack(side="left", padx=sc(4))
        tk.Label(table_hdr, text="REORDER / REMOVE", font=self.FONT_STEPPER, anchor="e", bg=self.colors["surface_container_low"], fg=self.colors["on_surface"]).pack(side="right", padx=sc(4))

        # Fields List Container
        self.fields_container = tk.Frame(inner, bg=self.colors["card_bg"])
        self.fields_container.pack(fill="both", expand=True, pady=sc(4))

        self._refresh_fields_table()

    def _refresh_fields_table(self):
        for w in self.fields_container.winfo_children():
            w.destroy()

        for idx, f in enumerate(self.fields):
            row_bg = self.colors["row_even"] if idx % 2 == 0 else self.colors["row_odd"]
            row = tk.Frame(self.fields_container, bg=row_bg, padx=sc(8), pady=sc(3))
            row.pack(fill="x", pady=1)

            # Index
            tk.Label(row, text=str(idx + 1), font=self.FONT_SMALL, width=3, bg=row_bg, fg=self.colors["on_surface_variant"]).pack(side="left")

            # Field Name
            name_lbl = tk.Label(row, text=f["name"], font=self.FONT_MONO, width=24, anchor="w", bg=row_bg, fg=self.colors["on_surface"])
            name_lbl.pack(side="left", padx=sc(4))

            # Data Type Combobox
            type_var = tk.StringVar(value=f.get("type", "text"))
            def _on_type_change(e, f_idx=idx, var=type_var):
                self.fields[f_idx]["type"] = var.get()
            cb = ttk.Combobox(row, textvariable=type_var, values=["text", "multiline", "choice", "checkbox"], state="readonly", width=12)
            cb.pack(side="left", padx=sc(4))
            cb.bind("<<ComboboxSelected>>", _on_type_change)

            # Readonly Checkbox
            ro_var = tk.BooleanVar(value=f.get("readonly", False))
            def _on_ro_change(f_idx=idx, var=ro_var):
                self.fields[f_idx]["readonly"] = var.get()
            chk = ttk.Checkbutton(row, variable=ro_var, command=_on_ro_change)
            chk.pack(side="left", padx=sc(16))

            # Actions (Up, Down, Delete)
            actions_frame = tk.Frame(row, bg=row_bg)
            actions_frame.pack(side="right")

            btn_up = tk.Button(
                actions_frame, text="▲", font=("Inter", sc(7)),
                bg=self.colors["surface_container_highest"], fg=self.colors["on_surface"],
                relief="flat", bd=0, cursor="hand2", width=2,
                command=lambda i=idx: self._move_field(i, -1)
            )
            btn_up.pack(side="left", padx=1)

            btn_down = tk.Button(
                actions_frame, text="▼", font=("Inter", sc(7)),
                bg=self.colors["surface_container_highest"], fg=self.colors["on_surface"],
                relief="flat", bd=0, cursor="hand2", width=2,
                command=lambda i=idx: self._move_field(i, 1)
            )
            btn_down.pack(side="left", padx=1)

            is_uid = (f["name"].upper() == "UID")
            btn_del = tk.Button(
                actions_frame, text="✕", font=("Inter", sc(8), "bold"),
                bg=self.colors["card_bg"], fg=self.colors["error"],
                relief="flat", bd=0, cursor="hand2" if not is_uid else "arrow", width=2,
                state="normal" if not is_uid else "disabled",
                command=lambda i=idx: self._remove_field(i)
            )
            btn_del.pack(side="left", padx=(sc(4), 0))

    def _add_field(self):
        name = self.new_field_var.get().strip()
        ftype = self.new_field_type_var.get()
        if not name:
            return
        if name.lower() == "objectid":
            messagebox.showwarning("Reserved Field", "ObjectID is the primary key and is created automatically.", parent=self.win)
            return
        if any(f["name"].lower() == name.lower() for f in self.fields):
            messagebox.showwarning("Duplicate Field", f"Field '{name}' already exists.", parent=self.win)
            return

        # Insert before UID if UID exists
        uid_idx = next((i for i, f in enumerate(self.fields) if f["name"].upper() == "UID"), -1)
        new_entry = {"name": name, "type": ftype, "readonly": False, "choices": []}
        if uid_idx >= 0:
            self.fields.insert(uid_idx, new_entry)
        else:
            self.fields.append(new_entry)

        self.new_field_var.set("")
        self._refresh_fields_table()

    def _remove_field(self, idx):
        if 0 <= idx < len(self.fields):
            f_name = self.fields[idx]["name"]
            if f_name.upper() == "UID":
                return
            self.fields.pop(idx)
            if f_name in self.problem_flags:
                del self.problem_flags[f_name]
            self._refresh_fields_table()

    def _move_field(self, idx, direction):
        target = idx + direction
        if 0 <= target < len(self.fields):
            self.fields[idx], self.fields[target] = self.fields[target], self.fields[idx]
            self._refresh_fields_table()

    # --------------------------------------------------------------------------
    # STEP 3: Problem Flags & Field Groups
    # --------------------------------------------------------------------------
    def _render_step3(self):
        inner = self._create_scrollable_card("Step 3: Auto-generate Problem Flags & Field Groups")

        # Top Explanation
        tk.Label(
            inner, text="Configure validation problem flags and organize fields into visual collapsible group panels.",
            font=self.FONT_SMALL, bg=self.colors["card_bg"], fg=self.colors["on_surface_variant"]
        ).pack(anchor="w", pady=(0, sc(8)))

        # Paned Layout: Left for Problems, Right for Groups
        pane = tk.Frame(inner, bg=self.colors["card_bg"])
        pane.pack(fill="both", expand=True)
        pane.columnconfigure(0, weight=1, uniform="group_pane")
        pane.columnconfigure(1, weight=1, uniform="group_pane")

        # LEFT: Problem Flag Generator
        left_card = tk.Frame(pane, bg=self.colors["surface_container_low"], highlightthickness=1, highlightbackground=self.colors["card_border"], padx=sc(8), pady=sc(8))
        left_card.grid(row=0, column=0, sticky="nsew", padx=(0, sc(4)))

        tk.Label(left_card, text="Problem Detection Flags", font=self.FONT_LABEL_BOLD, bg=self.colors["surface_container_low"], fg=self.colors["on_surface"]).pack(anchor="w")
        tk.Label(left_card, text="Auto-create [Field]_Problem flags:", font=self.FONT_SMALL, bg=self.colors["surface_container_low"], fg=self.colors["on_surface_variant"]).pack(anchor="w", pady=(0, sc(4)))

        btn_flag_bar = tk.Frame(left_card, bg=self.colors["surface_container_low"])
        btn_flag_bar.pack(fill="x", pady=(0, sc(4)))

        def _select_all_flags(val):
            for f in self.fields:
                if f["name"].upper() != "UID":
                    self.problem_flags[f["name"]] = val
            self._render_step3()

        tk.Button(btn_flag_bar, text="Select All", font=self.FONT_SMALL, bg=self.colors["card_bg"], fg=self.colors["on_surface"], relief="solid", bd=1, cursor="hand2", padx=sc(6), pady=1, command=lambda: _select_all_flags(True)).pack(side="left", padx=(0, sc(4)))
        tk.Button(btn_flag_bar, text="Clear All", font=self.FONT_SMALL, bg=self.colors["card_bg"], fg=self.colors["on_surface"], relief="solid", bd=1, cursor="hand2", padx=sc(6), pady=1, command=lambda: _select_all_flags(False)).pack(side="left")

        prob_canvas_frame = tk.Frame(left_card, bg=self.colors["card_bg"], highlightthickness=1, highlightbackground=self.colors["card_border"])
        prob_canvas_frame.pack(fill="both", expand=True)

        prob_canvas = tk.Canvas(prob_canvas_frame, bg=self.colors["card_bg"], highlightthickness=0, height=sc(180))
        prob_scroll = ttk.Scrollbar(prob_canvas_frame, orient="vertical", command=prob_canvas.yview)
        prob_inner = tk.Frame(prob_canvas, bg=self.colors["card_bg"], padx=sc(6), pady=sc(4))
        
        prob_canvas.create_window((0, 0), window=prob_inner, anchor="nw")
        prob_inner.bind("<Configure>", lambda e: prob_canvas.configure(scrollregion=prob_canvas.bbox("all")))
        prob_canvas.configure(yscrollcommand=prob_scroll.set)

        prob_canvas.pack(side="left", fill="both", expand=True)
        prob_scroll.pack(side="right", fill="y")

        for f in self.fields:
            fname = f["name"]
            if fname.upper() == "UID":
                continue
            var = tk.BooleanVar(value=self.problem_flags.get(fname, False))
            def _toggle_prob(fn=fname, v=var):
                self.problem_flags[fn] = v.get()
            ttk.Checkbutton(prob_inner, text=f"Flag: {fname}_Problem", variable=var, command=_toggle_prob).pack(anchor="w", pady=1)

        # RIGHT: Field Grouping
        right_card = tk.Frame(pane, bg=self.colors["surface_container_low"], highlightthickness=1, highlightbackground=self.colors["card_border"], padx=sc(8), pady=sc(8))
        right_card.grid(row=0, column=1, sticky="nsew", padx=(sc(4), 0))

        tk.Label(right_card, text="Field Groups (Sections)", font=self.FONT_LABEL_BOLD, bg=self.colors["surface_container_low"], fg=self.colors["on_surface"]).pack(anchor="w")

        # Auto-group button
        def _auto_group():
            self.groups = {}
            for f in self.fields:
                fn = f["name"]
                fn_lower = fn.lower()
                if fn.upper() == "UID":
                    g = "Admin"
                elif any(kw in fn_lower for kw in ["genus", "species", "family", "author", "order", "class", "taxon"]):
                    g = "Taxonomy"
                elif any(kw in fn_lower for kw in ["collect", "date", "place", "locality", "innsamling"]):
                    g = "Collection"
                elif any(kw in fn_lower for kw in ["obs", "comment", "note", "problem", "desc"]):
                    g = "Notes"
                elif any(kw in fn_lower for kw in ["loan", "borrower", "due", "return"]):
                    g = "Loan Info"
                else:
                    g = "Details"
                self.groups.setdefault(g, []).append(fn)
            self._render_step3()

        btn_group_bar = tk.Frame(right_card, bg=self.colors["surface_container_low"])
        btn_group_bar.pack(fill="x", pady=(0, sc(4)))
        tk.Button(btn_group_bar, text="⚡ Smart Auto-Group", font=self.FONT_SMALL, bg=self.colors["secondary"], fg=self.colors["on_secondary"], relief="flat", bd=0, cursor="hand2", padx=sc(6), pady=1, command=_auto_group).pack(side="left")

        # Groups listbox
        groups_list_frame = tk.Frame(right_card, bg=self.colors["card_bg"], highlightthickness=1, highlightbackground=self.colors["card_border"])
        groups_list_frame.pack(fill="both", expand=True)

        self.groups_lb = tk.Listbox(groups_list_frame, font=self.FONT_MONO, bg=self.colors["card_bg"], fg=self.colors["on_surface"], relief="flat", bd=0, height=8)
        self.groups_lb.pack(fill="both", expand=True, padx=sc(4), pady=sc(4))
        
        if not self.groups:
            _auto_group()
        else:
            for g_name, g_fields in self.groups.items():
                self.groups_lb.insert(tk.END, f"📁 {g_name} ({len(g_fields)} fields)")

    # --------------------------------------------------------------------------
    # STEP 4: Image & Location Setup
    # --------------------------------------------------------------------------
    def _render_step4(self):
        inner = self._create_scrollable_card("Step 4: Configure Image Fetching & Location Modules")

        # Online Image Fetching Section
        img_box = tk.Frame(inner, bg=self.colors["surface_container_low"], highlightthickness=1, highlightbackground=self.colors["card_border"], padx=sc(12), pady=sc(10))
        img_box.pack(fill="x", pady=(0, sc(12)))

        tk.Label(img_box, text="Online Specimen Image Fetching", font=self.FONT_HEADER, bg=self.colors["surface_container_low"], fg=self.colors["on_surface"]).pack(anchor="w")
        
        self.has_images_var = tk.BooleanVar(value=self.has_images)
        def _on_img_toggle():
            self.has_images = self.has_images_var.get()
            url_entry.config(state="normal" if self.has_images else "disabled")
            self._update_url_preview()

        ttk.Checkbutton(img_box, text="Enable Online Image URL Resolution", variable=self.has_images_var, command=_on_img_toggle).pack(anchor="w", pady=sc(4))

        tk.Label(img_box, text="URL Pattern Template:", font=self.FONT_LABEL_BOLD, bg=self.colors["surface_container_low"], fg=self.colors["on_surface"]).pack(anchor="w", pady=(sc(4), 0))

        self.url_var = tk.StringVar(value=self.image_url_pattern)
        url_entry = tk.Entry(
            img_box, textvariable=self.url_var, font=self.FONT_MONO,
            relief="solid", bd=1, highlightthickness=0, bg=self.colors["surface"], fg=self.colors["on_surface"]
        )
        url_entry.pack(fill="x", pady=sc(3), ipady=sc(3))
        url_entry.config(state="normal" if self.has_images else "disabled")

        tk.Label(
            img_box, text="Available tokens: {id} = Object ID, {num:04d} = Zero-padded ID, {suffix} = Photo suffix",
            font=self.FONT_SMALL, bg=self.colors["surface_container_low"], fg=self.colors["on_surface_variant"]
        ).pack(anchor="w")

        # Live Token Preview
        prev_box = tk.Frame(img_box, bg=self.colors["card_bg"], padx=sc(8), pady=sc(6), highlightthickness=1, highlightbackground=self.colors["card_border"])
        prev_box.pack(fill="x", pady=(sc(8), 0))

        tk.Label(prev_box, text="Live URL Preview (Test with ID: 1001):", font=self.FONT_LABEL_BOLD, bg=self.colors["card_bg"], fg=self.colors["on_surface"]).pack(anchor="w")
        self.url_preview_lbl = tk.Label(prev_box, text="", font=self.FONT_MONO, bg=self.colors["card_bg"], fg=self.colors["secondary"], wraplength=sc(560), justify="left")
        self.url_preview_lbl.pack(anchor="w", pady=(sc(2), 0))

        self.url_var.trace_add("write", lambda *_: self._update_url_preview())
        self._update_url_preview()

        # Location & Loan Modules Section
        mod_box = tk.Frame(inner, bg=self.colors["surface_container_low"], highlightthickness=1, highlightbackground=self.colors["card_border"], padx=sc(12), pady=sc(10))
        mod_box.pack(fill="x")

        tk.Label(mod_box, text="Integrated Storage & Loan Panels", font=self.FONT_HEADER, bg=self.colors["surface_container_low"], fg=self.colors["on_surface"]).pack(anchor="w")

        self.loc_var = tk.BooleanVar(value=self.include_location)
        ttk.Checkbutton(mod_box, text="Include Standard Location Panel (Building, Floor, Cabinet, Room, Stored as)", variable=self.loc_var, command=lambda: setattr(self, "include_location", self.loc_var.get())).pack(anchor="w", pady=sc(4))

        self.loan_var = tk.BooleanVar(value=self.include_loan)
        ttk.Checkbutton(mod_box, text="Include Outbound Loan Tracking Panel (Borrower, Due Date, Loan Status)", variable=self.loan_var, command=lambda: setattr(self, "include_loan", self.loan_var.get())).pack(anchor="w", pady=sc(2))

    def _update_url_preview(self):
        if not getattr(self, "has_images_var", None) or not self.has_images_var.get():
            if hasattr(self, "url_preview_lbl"):
                self.url_preview_lbl.config(text="Online image fetching disabled.", fg=self.colors["outline"])
            return

        pattern = self.url_var.get().strip() if hasattr(self, "url_var") else ""
        if not pattern:
            if hasattr(self, "url_preview_lbl"):
                self.url_preview_lbl.config(text="No URL pattern entered.", fg=self.colors["outline"])
            return

        try:
            # Format test with sample id
            test_id = 1001
            sample = pattern.format(id=test_id, num=test_id, suffix="")
            if hasattr(self, "url_preview_lbl"):
                self.url_preview_lbl.config(text=sample, fg=self.colors["secondary"])
        except Exception:
            if hasattr(self, "url_preview_lbl"):
                self.url_preview_lbl.config(text="Pattern contains unrecognised token format", fg=self.colors["error"])

    # --------------------------------------------------------------------------
    # STEP 5: Review & Workspace Initialization
    # --------------------------------------------------------------------------
    def _render_step5(self):
        inner = self._create_scrollable_card("Step 5: Review & Initialize Database")

        # Summary Card
        summary_card = tk.Frame(inner, bg=self.colors["surface_container_low"], highlightthickness=1, highlightbackground=self.colors["card_border"], padx=sc(12), pady=sc(10))
        summary_card.pack(fill="x", pady=(0, sc(12)))

        tk.Label(summary_card, text="Database Configuration Summary", font=self.FONT_HEADER, bg=self.colors["surface_container_low"], fg=self.colors["on_surface"]).pack(anchor="w", pady=(0, sc(6)))

        active_prob_count = sum(1 for v in self.problem_flags.values() if v)
        group_count = len(self.groups)

        stats = [
            ("Starter Template:", self.selected_template),
            ("Registration Fields:", f"{len(self.fields)} fields (ObjectID auto-indexed)"),
            ("Problem Flags:", f"{active_prob_count} auto-generated problem flags"),
            ("Field Groups:", f"{group_count} UI sections"),
            ("Online Photos:", "Enabled" if self.has_images else "Disabled"),
            ("Location Panel:", "Included" if self.include_location else "Omitted"),
            ("Loan Module:", "Included" if self.include_loan else "Omitted"),
        ]

        for label, val in stats:
            row = tk.Frame(summary_card, bg=self.colors["surface_container_low"])
            row.pack(fill="x", pady=1)
            tk.Label(row, text=label, font=self.FONT_LABEL_BOLD, width=20, anchor="w", bg=self.colors["surface_container_low"], fg=self.colors["on_surface"]).pack(side="left")
            tk.Label(row, text=val, font=self.FONT_MONO, bg=self.colors["surface_container_low"], fg=self.colors["on_surface_variant"]).pack(side="left")

        # Configuration Options
        init_box = tk.Frame(inner, bg=self.colors["card_bg"])
        init_box.pack(fill="x", pady=sc(4))

        # 1. Profile Name
        tk.Label(init_box, text="Database Profile Name:", font=self.FONT_LABEL_BOLD, bg=self.colors["card_bg"], fg=self.colors["on_surface"]).pack(anchor="w")
        self.profile_name_var = tk.StringVar(value=self.profile_name)
        tk.Entry(init_box, textvariable=self.profile_name_var, font=self.FONT_MONO, relief="solid", bd=1, highlightthickness=0, bg=self.colors["surface"], fg=self.colors["on_surface"]).pack(fill="x", pady=(sc(2), sc(8)), ipady=sc(3))

        # 2. Starting Object ID & Row count
        row_id = tk.Frame(init_box, bg=self.colors["card_bg"])
        row_id.pack(fill="x", pady=(0, sc(8)))

        tk.Label(row_id, text="Starting Object ID:", font=self.FONT_LABEL_BOLD, bg=self.colors["card_bg"], fg=self.colors["on_surface"]).pack(side="left", padx=(0, sc(6)))
        self.start_id_var = tk.StringVar(value=self.start_object_id)
        tk.Entry(row_id, textvariable=self.start_id_var, font=self.FONT_MONO, width=12, relief="solid", bd=1, highlightthickness=0, bg=self.colors["surface"], fg=self.colors["on_surface"]).pack(side="left", padx=(0, sc(16)), ipady=sc(2))

        tk.Label(row_id, text="Initial Blank Records:", font=self.FONT_LABEL_BOLD, bg=self.colors["card_bg"], fg=self.colors["on_surface"]).pack(side="left", padx=(0, sc(6)))
        self.row_count_var = tk.IntVar(value=self.initial_records_count)
        tk.Spinbox(row_id, from_=1, to=100, textvariable=self.row_count_var, font=self.FONT_MONO, width=6, relief="solid", bd=1, highlightthickness=0, bg=self.colors["surface"], fg=self.colors["on_surface"]).pack(side="left", ipady=sc(2))

        # 3. File Save Destination
        tk.Label(init_box, text="Save Database As (.xlsx):", font=self.FONT_LABEL_BOLD, bg=self.colors["card_bg"], fg=self.colors["on_surface"]).pack(anchor="w")
        
        dest_row = tk.Frame(init_box, bg=self.colors["card_bg"])
        dest_row.pack(fill="x", pady=(sc(2), 0))

        if not self.output_file_path:
            last_dir = config.get_last_dir("last_db_dir") or os.getcwd()
            clean_name = re.sub(r'[^a-zA-Z0-9_-]', '_', self.profile_name)
            self.output_file_path = os.path.join(last_dir, f"{clean_name}.xlsx")

        self.output_path_var = tk.StringVar(value=self.output_file_path)
        tk.Entry(dest_row, textvariable=self.output_path_var, font=self.FONT_MONO, relief="solid", bd=1, highlightthickness=0, bg=self.colors["surface"], fg=self.colors["on_surface"]).pack(side="left", fill="x", expand=True, padx=(0, sc(6)), ipady=sc(3))

        def _browse_dest():
            p = filedialog.asksaveasfilename(
                parent=self.win,
                title="Save Database Workbook",
                defaultextension=".xlsx",
                filetypes=[("Excel files", "*.xlsx")],
                initialdir=os.path.dirname(self.output_path_var.get()) if self.output_path_var.get() else config.get_last_dir("last_db_dir")
            )
            if p:
                config.set_last_dir("last_db_dir", p)
                self.output_path_var.set(p)

        tk.Button(
            dest_row, text="Browse...", font=self.FONT_BUTTON,
            bg=self.colors["surface_container_low"], fg=self.colors["on_surface"],
            relief="solid", bd=1, cursor="hand2", padx=sc(10), pady=sc(3),
            command=_browse_dest
        ).pack(side="right")

    # --------------------------------------------------------------------------
    # Database Initialization & Session Binding
    # --------------------------------------------------------------------------
    def _initialize_database(self):
        file_path = self.output_path_var.get().strip()
        name = self.profile_name_var.get().strip()
        start_id = self.start_id_var.get().strip() or "1"
        row_count = max(1, self.row_count_var.get())

        # Construct final UI configuration dictionary
        reg_sections = []
        for f in self.fields:
            entry = {"name": f["name"], "type": f.get("type", "text")}
            if f.get("readonly"):
                entry["readonly"] = True
            if f.get("choices"):
                entry["choices"] = f["choices"]
            reg_sections.append(entry)

        # Ensure UID is present
        if not any(f["name"].upper() == "UID" for f in reg_sections):
            reg_sections.append({"name": "UID", "type": "text", "readonly": True})

        # Problem flags
        problem_sections = []
        for f_name, enabled in self.problem_flags.items():
            if enabled:
                problem_sections.append({
                    "name": f"{f_name}_Problem",
                    "type": "bool",
                    "maps_to": f_name
                })
        problem_sections.append({"name": "Images_Missing", "type": "bool"})
        problem_sections.append({"name": "Other_problem", "type": "bool", "maps_to": "Other"})

        # Group sections
        reg_groups_list = []
        for g_name, g_fields in self.groups.items():
            if g_fields:
                reg_groups_list.append({"name": g_name, "fields": g_fields})

        # Location sections
        loc_sections = []
        if self.include_location:
            loc_sections = [
                {"name": "Stored as", "type": "text"},
                {"name": "Building", "type": "text"},
                {"name": "Floor", "type": "text"},
                {"name": "Room", "type": "text"},
                {"name": "Cabinet", "type": "text"},
                {"name": "Shelf", "type": "text"}
            ]

        # Loan sections
        if self.include_loan:
            loc_sections.extend([
                {"name": "Loaned out", "type": "checkbox"},
                {"name": "Borrower", "type": "text"},
                {"name": "Loan Date", "type": "text"},
                {"name": "Due Date", "type": "text"},
                {"name": "Return Date", "type": "text"}
            ])

        image_pattern = self.url_var.get().strip() if hasattr(self, "url_var") else self.image_url_pattern

        new_config = {
            "has_images": self.has_images,
            "image_url_pattern": image_pattern,
            "sheets": {
                "reg": "Registration",
                "obs": "Observation",
                "photo": "Photo",
                "log": "Log",
            },
            "ui_sections": {
                "registration": reg_sections,
                "reg_groups": reg_groups_list,
                "location": loc_sections,
                "problems": problem_sections,
                "unknown_fields": []
            }
        }

        # Build initial DataFrames
        try:
            # Generate ObjectIDs
            object_ids = []
            try:
                numeric_id = int(start_id)
                for i in range(row_count):
                    object_ids.append(numeric_id + i)
            except ValueError:
                # String prefix e.g. V-0001
                m = re.match(r"^(.*?)(\d+)$", start_id)
                if m:
                    prefix, num_str = m.groups()
                    pad_len = len(num_str)
                    base_num = int(num_str)
                    for i in range(row_count):
                        object_ids.append(f"{prefix}{str(base_num + i).zfill(pad_len)}")
                else:
                    for i in range(row_count):
                        object_ids.append(f"{start_id}_{i+1}" if i > 0 else start_id)

            # Registration sheet
            reg_cols = [f["name"] for f in reg_sections]
            df_reg = pd.DataFrame(index=object_ids, columns=reg_cols)
            df_reg.index.name = "ObjectID"
            
            # Observation sheet
            obs_cols = [f["name"] for f in loc_sections]
            prob_cols = [f["name"] for f in problem_sections]
            obs_cols.extend(prob_cols)
            obs_cols.extend(["Reviewed", "ReviewedAt", "Images_Missing"])
            obs_cols = list(dict.fromkeys(obs_cols))
            df_obs = pd.DataFrame(index=object_ids, columns=obs_cols)
            df_obs.index.name = "ObjectID"
            for p in prob_cols:
                df_obs[p] = False
            df_obs["Reviewed"] = False
            df_obs["Images_Missing"] = False

            # Photo sheet
            df_photo = pd.DataFrame(columns=["ObjectID", "ImagePath", "ImageNote"])
            df_photo.set_index("ObjectID", inplace=True)

            # Log sheet
            df_log = pd.DataFrame([{
                "Timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "Action": "DATABASE_CREATED",
                "Columns": f"Created with {len(reg_cols)} columns",
                "Values": f"Initial records count: {row_count}"
            }])

            # Save Excel File
            os.makedirs(os.path.dirname(os.path.abspath(file_path)), exist_ok=True)
            with pd.ExcelWriter(file_path) as writer:
                df_reg.to_excel(writer, sheet_name=new_config["sheets"]["reg"])
                df_obs.to_excel(writer, sheet_name=new_config["sheets"]["obs"])
                df_photo.to_excel(writer, sheet_name=new_config["sheets"]["photo"])
                df_log.to_excel(writer, sheet_name=new_config["sheets"]["log"], index=False)

            # Save config into preferences
            prefs = config.load_prefs()
            if "custom_databases" not in prefs:
                prefs["custom_databases"] = {}
            prefs["custom_databases"][name] = new_config
            config.save_prefs(prefs)
            config.DATABASE_CONFIGS[name] = new_config

            # Update app session state if running
            if self.app:
                self.app.config = new_config
                self.app.config_name = name
                self.app.excel_path = file_path
                self.app.output_path = file_path
                self.app.df_reg = df_reg
                self.app.df_obs = df_obs
                self.app.df_photo = df_photo
                self.app.df_log = df_log
                self.app.initial_df_obs = df_obs.copy()

            # Execute completion callback
            if self.on_complete:
                try:
                    # Callback can accept (file_path, name) or no args
                    import inspect
                    sig = inspect.signature(self.on_complete)
                    if len(sig.parameters) >= 2:
                        self.on_complete(file_path, name)
                    elif len(sig.parameters) == 1:
                        self.on_complete(file_path)
                    else:
                        self.on_complete()
                except Exception:
                    self.on_complete()

            self.win.destroy()
            messagebox.showinfo("Success", f"Database successfully created and initialized!\nLocation: {file_path}", parent=self.parent)

        except Exception as e:
            messagebox.showerror("Initialization Error", f"Failed to initialize database file:\n{e}", parent=self.win)
