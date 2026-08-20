"""
ui/new_database_wizard.py - Modern New Database Setup Wizard for Arbor

Provides an intuitive, responsive multi-step wizard for creating new databases
from built-in starter templates, Excel/CSV schemas, or from scratch.
Fully styled according to AI_UI_GUIDE.md with Light/Dark theme support,
responsive layout scaling, interactive schema tools, category-first field organization,
problem flag rule engine, and real-time simulated record preview.
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


class NewDatabaseWizard:
    """
    Modern 5-Step New Database Creation Wizard.
    Steps:
      1. Profile & Template / Data Source
      2. Schema & Field Editor
      3. Problem Flags & Field Groups (Category-First)
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
        # Schema definition: list of dicts {"name": str, "type": str, "readonly": bool, "choices": list}
        self.fields = []
        # Problem flags: dict of field_name -> bool
        self.problem_flags = {}
        # Custom user-defined problem flags: list of dicts {"name": str, "maps_to": str, "description": str, "category": str}
        self.custom_problem_flags = []
        self._deleted_flags_undo_stack = []
        self.flag_category_filter = "All"
        self.validation_strategy = "key_fields"  # "key_fields", "all_fields", "general_only", "none"
        self.preview_active_group = ""
        self.active_category = "General"
        self.move_chip_open_field = None  # Tracks which field has the inline move chip bar open
        self.preview_mode = "standard"  # "standard" or "focus"

        self.common_problems = {
            "Images_Problem": True,
            "Other_problem": True
        }
        # Groups: list of group names and mapping
        self.group_names = ["General", "Taxonomy", "Collection", "Details", "Notes", "Admin"]
        self.field_group_map = {}
        # Image config
        self.has_images = True
        self.image_url_pattern = "https://www.unimus.no/photos/image/jpeg/O-V-OE-{num:04d}{suffix}.jpg"
        self.test_specimen_id = "1001"
        # Sub-modules toggles
        self.include_location = True
        self.include_loan = False
        self.include_condition = False
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
        self.FONT_SMALL_BOLD = ("Inter", sc(9), "bold")
        self.FONT_MONO = ("JetBrains Mono", sc(10))
        self.FONT_MONO_SM = ("JetBrains Mono", sc(8.5))
        self.FONT_BUTTON = ("Hanken Grotesk", sc(9.5), "bold")

        # Build Window
        self._setup_window()
        self._build_shell()
        self.goto_step(1)

    @property
    def groups(self):
        g_dict = {g: [] for g in self.group_names}
        for f in self.fields:
            fname = f["name"]
            g = self.field_group_map.get(fname, "General")
            if g not in g_dict:
                g_dict[g] = []
            g_dict[g].append(fname)
        return {k: v for k, v in g_dict.items() if v or k in self.group_names}

    @groups.setter
    def groups(self, val):
        if isinstance(val, dict):
            self.group_names = list(val.keys())
            self.field_group_map = {}
            for g, f_list in val.items():
                for f in f_list:
                    self.field_group_map[f] = g

    def _setup_window(self):
        self.win = tk.Toplevel(self.parent)
        self.win.title("New Database Setup Wizard")
        self.win.configure(bg=self.colors["surface"])
        self.win.grab_set()
        self.win.transient(self.parent)

        import utils
        utils.center_and_fit_toplevel(self.win, sc(780), sc(690))
        self.win.minsize(sc(640), sc(540))

        self.win.bind("<Escape>", lambda e: self._on_cancel())
        self.win.bind("<Control-Return>", lambda e: self._on_next())
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
            fg=self.colors["on_surface"], padx=sc(10), pady=sc(2)
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
        self.content_container.pack(fill="both", expand=True, padx=sc(16), pady=sc(10))

        # Bottom Action Bar
        action_bar = tk.Frame(self.win, bg=self.colors["surface_container_low"], padx=sc(16), pady=sc(10))
        action_bar.pack(fill="x", side="bottom")
        tk.Frame(self.win, bg=self.colors["card_border"], height=1).pack(fill="x", side="bottom")

        self.btn_cancel = tk.Button(
            action_bar, text="Cancel", font=self.FONT_BUTTON,
            bg=self.colors["card_bg"], fg=self.colors["on_surface"],
            relief="solid", bd=1, cursor="hand2", padx=sc(14), pady=sc(5),
            command=self._on_cancel
        )
        self.btn_cancel.pack(side="left")

        self.btn_next = tk.Button(
            action_bar, text="Next Step →", font=self.FONT_BUTTON,
            bg=self.colors["primary"], fg=self.colors["on_primary"],
            relief="flat", bd=0, cursor="hand2", padx=sc(18), pady=sc(6),
            command=self._on_next
        )
        self.btn_next.pack(side="right")

        self.btn_back = tk.Button(
            action_bar, text="← Back", font=self.FONT_BUTTON,
            bg=self.colors["card_bg"], fg=self.colors["on_surface"],
            relief="solid", bd=1, cursor="hand2", padx=sc(14), pady=sc(5),
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
            if canvas.winfo_exists():
                canvas.configure(scrollregion=canvas.bbox("all"))

        def _on_canvas_config(e):
            if canvas.winfo_exists():
                canvas.itemconfig(inner_id, width=e.width)

        inner.bind("<Configure>", _on_inner_config)
        canvas.bind("<Configure>", _on_canvas_config)
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # Mousewheel scroll support scoped to widget
        def _on_mousewheel(e):
            if canvas.winfo_exists():
                canvas.yview_scroll(int(-1 * (e.delta / 120)), "units")

        inner.bind("<Enter>", lambda e: canvas.bind_all("<MouseWheel>", _on_mousewheel))
        inner.bind("<Leave>", lambda e: canvas.unbind_all("<MouseWheel>"))

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
            try:
                self.win.unbind_all("<MouseWheel>")
            except Exception:
                pass
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
            name = self.profile_name_var.get().strip() if hasattr(self, "profile_name_var") else ""
            if not name:
                messagebox.showwarning("Validation Warning", "Please specify a profile name.", parent=self.win)
                return False
            path = self.output_path_var.get().strip() if hasattr(self, "output_path_var") else ""
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
        self.custom_problem_flags = []
        for p in probs:
            p_map = p.get("maps_to")
            p_name = p.get("name", "")
            if p_name in ["Images_Problem", "Images_Missing", "Other_problem"]:
                continue
            if p_map and p_map != "Other":
                clean_map = p_map.replace(" ", "").replace("_", "").lower()
                clean_pname = p_name.replace(" ", "").replace("_", "").lower()
                if clean_pname in [f"{clean_map}problem", clean_map]:
                    self.problem_flags[p_map] = True
                else:
                    self.custom_problem_flags.append({
                        "name": p_name,
                        "maps_to": p_map,
                        "description": p.get("description", ""),
                        "category": self._deduce_flag_category(p_name, p_map)
                    })
            elif p_name:
                self.custom_problem_flags.append({
                    "name": p_name,
                    "maps_to": "Other",
                    "description": p.get("description", ""),
                    "category": self._deduce_flag_category(p_name, "Other")
                })

        # Load groups
        self.group_names = []
        self.field_group_map = {}
        for g in ui_sections.get("reg_groups", []):
            g_name = g.get("name")
            g_fields = g.get("fields", [])
            if g_name:
                self.group_names.append(g_name)
                for f in g_fields:
                    if f != "ObjectID":
                        self.field_group_map[f] = g_name

        if not self.group_names:
            self.group_names = ["General", "Details", "Notes", "Admin"]

        self.active_category = self.group_names[0] if self.group_names else "General"

        # Load image settings
        self.has_images = template_cfg.get("has_images", False)
        self.image_url_pattern = template_cfg.get("image_url_pattern", "")

        # Default profile name
        self.profile_name = template_key.replace(" / ", "_").replace(" ", "_") + "_DB"

    def _deduce_flag_category(self, flag_name, maps_to=""):
        combined = f"{flag_name} {maps_to}".lower()
        if any(w in combined for w in ["genus", "species", "taxon", "family", "nomenclature", "scientific"]):
            return "Taxonomy"
        if any(w in combined for w in ["place", "locality", "location", "geo", "coord", "country"]):
            return "Locality"
        if any(w in combined for w in ["date", "time", "year", "due", "return", "overdue"]):
            return "Dates"
        if any(w in combined for w in ["person", "collector", "borrower", "author", "user"]):
            return "Personnel"
        if any(w in combined for w in ["price", "cost", "value", "receipt"]):
            return "Valuation"
        return "General"

    # --------------------------------------------------------------------------
    # STEP 1: Template & Source Selection
    # --------------------------------------------------------------------------
    def _render_step1(self):
        inner = self._create_scrollable_card("Step 1: Choose Starter Template or Import Schema")

        tk.Label(
            inner, text="Select a domain starter template, import from an existing Excel/CSV file, or build from scratch.",
            font=self.FONT_SMALL, bg=self.colors["card_bg"], fg=self.colors["on_surface_variant"]
        ).pack(anchor="w", pady=(0, sc(10)))

        # Built-in Core Template Cards
        templates_grid = tk.Frame(inner, bg=self.colors["card_bg"])
        templates_grid.pack(fill="x", pady=sc(4))

        templates = [
            ("Botany / Herbarium", "🌿", "Taxonomy & Specimen", "Standard herbarium collection schema with taxonomy, collection details, plant parts, and observation notes.", ["Taxonomy", "Geography", "Images"]),
            ("Loan Tracking", "📋", "Curatorial & Loans", "Track outbound items, borrowers, institutions, loan dates, due dates, statuses, and return conditions.", ["Curatorial", "Due Dates", "Borrowers"]),
            ("Blank Minimal", "📄", "Minimalist & Fast", "A light, clean starter schema with Title, Category, Date, Status, Description, and Notes.", ["Lean", "Fast Setup", "Generic"])
        ]

        self.template_cards = []
        for name, icon, badge, desc, tags in templates:
            card = self._build_template_card(templates_grid, name, icon, badge, desc, tags)
            card.pack(fill="x", pady=sc(4))
            self.template_cards.append((name, card))

        self._highlight_selected_template()

        # Separator
        ttk.Separator(inner, orient="horizontal").pack(fill="x", pady=sc(12))

        # Secondary Actions: Import File & Scratch
        tk.Label(
            inner, text="Or import from an existing spreadsheet or saved profile:",
            font=self.FONT_LABEL_BOLD, bg=self.colors["card_bg"], fg=self.colors["on_surface"]
        ).pack(anchor="w", pady=(0, sc(6)))

        btn_row = tk.Frame(inner, bg=self.colors["card_bg"])
        btn_row.pack(fill="x", pady=sc(2))

        btn_import = tk.Button(
            btn_row, text="📊 Import from Excel / CSV", font=self.FONT_BUTTON,
            bg=self.colors["surface_container_low"], fg=self.colors["on_surface"],
            relief="solid", bd=1, cursor="hand2", padx=sc(14), pady=sc(7),
            command=self._import_schema_file
        )
        btn_import.pack(side="left", fill="x", expand=True, padx=(0, sc(4)))

        btn_scratch = tk.Button(
            btn_row, text="✏ Create Blank Custom", font=self.FONT_BUTTON,
            bg=self.colors["surface_container_low"], fg=self.colors["on_surface"],
            relief="solid", bd=1, cursor="hand2", padx=sc(14), pady=sc(7),
            command=self._create_scratch_schema
        )
        btn_scratch.pack(side="right", fill="x", expand=True, padx=(sc(4), 0))

        # Existing Profiles Dropdown
        existing_profiles = list(config.DATABASE_CONFIGS.keys())
        if existing_profiles:
            prof_card = tk.Frame(
                inner, bg=self.colors["surface_container_low"],
                highlightthickness=1, highlightbackground=self.colors["card_border"],
                padx=sc(10), pady=sc(8)
            )
            prof_card.pack(fill="x", pady=(sc(10), sc(4)))

            tk.Label(prof_card, text="📁 Load Schema from Existing Profile:", font=self.FONT_LABEL_BOLD, bg=self.colors["surface_container_low"], fg=self.colors["on_surface"]).pack(side="left", padx=(0, sc(8)))
            self.profile_cb_var = tk.StringVar(value=existing_profiles[0])
            cb = ttk.Combobox(prof_card, textvariable=self.profile_cb_var, values=existing_profiles, state="readonly", width=26)
            cb.pack(side="left", padx=(0, sc(8)))

            tk.Button(
                prof_card, text="Load Profile", font=self.FONT_BUTTON,
                bg=self.colors["primary"], fg=self.colors["on_primary"],
                relief="flat", bd=0, cursor="hand2", padx=sc(12), pady=sc(4),
                command=lambda: self._select_existing_profile(self.profile_cb_var.get())
            ).pack(side="left")

    def _build_template_card(self, parent, name, icon, badge, desc, tags=None):
        card = tk.Frame(
            parent, bg=self.colors["surface_container_low"],
            highlightthickness=1, highlightbackground=self.colors["card_border"],
            cursor="hand2", padx=sc(12), pady=sc(9)
        )
        card.bind("<Button-1>", lambda e, n=name: self._select_template(n))

        top = tk.Frame(card, bg=self.colors["surface_container_low"])
        top.pack(fill="x")
        top.bind("<Button-1>", lambda e, n=name: self._select_template(n))

        tk.Label(
            top, text=f"{icon}  {name}", font=self.FONT_HEADER,
            bg=self.colors["surface_container_low"], fg=self.colors["on_surface"]
        ).pack(side="left")

        tk.Label(
            top, text=badge, font=("Inter", sc(8), "bold"),
            bg=self.colors["surface_container_highest"], fg=self.colors["on_surface"],
            padx=sc(8), pady=sc(2)
        ).pack(side="right")

        tk.Label(
            card, text=desc, font=self.FONT_SMALL,
            bg=self.colors["surface_container_low"], fg=self.colors["on_surface_variant"],
            wraplength=sc(620), justify="left"
        ).pack(anchor="w", pady=(sc(4), sc(4)))

        if tags:
            tag_row = tk.Frame(card, bg=self.colors["surface_container_low"])
            tag_row.pack(fill="x")
            for t in tags:
                t_lbl = tk.Label(
                    tag_row, text=f"• {t}", font=("Inter", sc(7.5)),
                    bg=self.colors["card_bg"], fg=self.colors["secondary"],
                    padx=sc(6), pady=1, highlightthickness=1, highlightbackground=self.colors["card_border"]
                )
                t_lbl.pack(side="left", padx=(0, sc(4)))
                t_lbl.bind("<Button-1>", lambda e, n=name: self._select_template(n))

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
                df = pd.read_excel(file_path, nrows=50, engine='calamine')

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
                    "choices": [str(x) for x in series.unique() if pd.notna(x)] if ftype == "choice" else []
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
    # STEP 2: Interactive Schema Builder (Strict Column Alignment)
    # --------------------------------------------------------------------------
    def _render_step2(self):
        inner = self._create_scrollable_card("Step 2: Customize Schema & Field Definitions")

        # Top Bar: Add Single Field
        add_bar = tk.Frame(inner, bg=self.colors["card_bg"])
        add_bar.pack(fill="x", pady=(0, sc(6)))

        tk.Label(add_bar, text="New Field Name:", font=self.FONT_LABEL_BOLD, bg=self.colors["card_bg"], fg=self.colors["on_surface"]).pack(side="left", padx=(0, sc(6)))

        self.new_field_var = tk.StringVar()
        entry = tk.Entry(
            add_bar, textvariable=self.new_field_var, font=self.FONT_MONO,
            relief="solid", bd=1, highlightthickness=0, bg=self.colors["surface"], fg=self.colors["on_surface"]
        )
        entry.pack(side="left", fill="x", expand=True, padx=(0, sc(6)), ipady=sc(3))
        entry.bind("<Return>", lambda e: self._add_field())

        self.new_field_type_var = tk.StringVar(value="text")
        cb = ttk.Combobox(add_bar, textvariable=self.new_field_type_var, values=["text", "multiline", "choice", "checkbox"], state="readonly", width=11)
        cb.pack(side="left", padx=(0, sc(6)))

        btn_add = tk.Button(
            add_bar, text="+ Add Field", font=self.FONT_BUTTON,
            bg=self.colors["primary"], fg=self.colors["on_primary"],
            relief="flat", bd=0, cursor="hand2", padx=sc(12), pady=sc(4),
            command=self._add_field
        )
        btn_add.pack(side="right")

        # Quick Bulk Operations Bar
        bulk_bar = tk.Frame(inner, bg=self.colors["surface_container_low"], padx=sc(8), pady=sc(4), highlightthickness=1, highlightbackground=self.colors["card_border"])
        bulk_bar.pack(fill="x", pady=(0, sc(8)))

        tk.Label(bulk_bar, text="Quick Tools:", font=self.FONT_SMALL_BOLD, bg=self.colors["surface_container_low"], fg=self.colors["on_surface"]).pack(side="left", padx=(0, sc(6)))

        tk.Button(
            bulk_bar, text="➕ Add Multiple Fields", font=self.FONT_SMALL,
            bg=self.colors["card_bg"], fg=self.colors["on_surface"],
            relief="solid", bd=1, cursor="hand2", padx=sc(6), pady=sc(2),
            command=self._prompt_batch_add_fields
        ).pack(side="left", padx=sc(2))

        tk.Button(
            bulk_bar, text="🔒 Toggle All Readonly", font=self.FONT_SMALL,
            bg=self.colors["card_bg"], fg=self.colors["on_surface"],
            relief="solid", bd=1, cursor="hand2", padx=sc(6), pady=sc(2),
            command=self._toggle_all_readonly
        ).pack(side="left", padx=sc(2))

        tk.Button(
            bulk_bar, text="🧹 Clear Non-Essential", font=self.FONT_SMALL,
            bg=self.colors["card_bg"], fg=self.colors["error"],
            relief="solid", bd=1, cursor="hand2", padx=sc(6), pady=sc(2),
            command=self._clear_non_essential_fields
        ).pack(side="left", padx=sc(2))

        # Field Counter Badge
        self.field_count_lbl = tk.Label(
            bulk_bar, text=f"Total: {len(self.fields)} fields",
            font=self.FONT_SMALL_BOLD, bg=self.colors["surface_container_highest"],
            fg=self.colors["on_surface"], padx=sc(6), pady=1
        )
        self.field_count_lbl.pack(side="right")

        # Fields List Container (Grid-based layout)
        self.fields_container = tk.Frame(inner, bg=self.colors["card_bg"])
        self.fields_container.pack(fill="both", expand=True, pady=sc(4))
        self.fields_container.columnconfigure(0, weight=0, minsize=sc(30))
        self.fields_container.columnconfigure(1, weight=1, minsize=sc(150))
        self.fields_container.columnconfigure(2, weight=0, minsize=sc(115))
        self.fields_container.columnconfigure(3, weight=0, minsize=sc(125))
        self.fields_container.columnconfigure(4, weight=0, minsize=sc(90))
        self.fields_container.columnconfigure(5, weight=0, minsize=sc(90))

        self._refresh_fields_table()

    def _refresh_fields_table(self):
        for w in self.fields_container.winfo_children():
            w.destroy()

        if hasattr(self, "field_count_lbl") and self.field_count_lbl.winfo_exists():
            self.field_count_lbl.config(text=f"Total: {len(self.fields)} fields")

        # Row 0: Table Header
        hdr_bg = self.colors["surface_container_low"]
        hdr_row_frame = tk.Frame(self.fields_container, bg=hdr_bg)
        hdr_row_frame.grid(row=0, column=0, columnspan=6, sticky="nsew", pady=(0, sc(2)))

        tk.Label(self.fields_container, text="#", font=self.FONT_STEPPER, bg=hdr_bg, fg=self.colors["on_surface"]).grid(row=0, column=0, sticky="w", padx=sc(6), pady=sc(5))
        tk.Label(self.fields_container, text="FIELD NAME", font=self.FONT_STEPPER, anchor="w", bg=hdr_bg, fg=self.colors["on_surface"]).grid(row=0, column=1, sticky="w", padx=sc(6), pady=sc(5))
        tk.Label(self.fields_container, text="DATA TYPE", font=self.FONT_STEPPER, anchor="w", bg=hdr_bg, fg=self.colors["on_surface"]).grid(row=0, column=2, sticky="w", padx=sc(6), pady=sc(5))
        tk.Label(self.fields_container, text="CHOICES / OPTIONS", font=self.FONT_STEPPER, anchor="w", bg=hdr_bg, fg=self.colors["on_surface"]).grid(row=0, column=3, sticky="w", padx=sc(6), pady=sc(5))
        tk.Label(self.fields_container, text="READONLY", font=self.FONT_STEPPER, anchor="center", bg=hdr_bg, fg=self.colors["on_surface"]).grid(row=0, column=4, sticky="ew", padx=sc(6), pady=sc(5))
        tk.Label(self.fields_container, text="ACTIONS", font=self.FONT_STEPPER, anchor="e", bg=hdr_bg, fg=self.colors["on_surface"]).grid(row=0, column=5, sticky="e", padx=sc(6), pady=sc(5))

        for idx, f in enumerate(self.fields):
            row_idx = idx + 1
            row_bg = self.colors["row_even"] if idx % 2 == 0 else self.colors["row_odd"]

            # Background strip
            bg_strip = tk.Frame(self.fields_container, bg=row_bg)
            bg_strip.grid(row=row_idx, column=0, columnspan=6, sticky="nsew", pady=1)

            # Col 0: Index
            tk.Label(self.fields_container, text=str(idx + 1), font=self.FONT_SMALL, bg=row_bg, fg=self.colors["on_surface_variant"]).grid(row=row_idx, column=0, sticky="w", padx=sc(6), pady=sc(3))

            # Col 1: Field Name
            tk.Label(self.fields_container, text=f["name"], font=self.FONT_MONO, anchor="w", bg=row_bg, fg=self.colors["on_surface"]).grid(row=row_idx, column=1, sticky="w", padx=sc(6), pady=sc(3))

            # Col 2: Data Type Combobox
            type_var = tk.StringVar(value=f.get("type", "text"))
            def _on_type_change(e, f_idx=idx, var=type_var):
                self.fields[f_idx]["type"] = var.get()
                self._refresh_fields_table()
            cb = ttk.Combobox(self.fields_container, textvariable=type_var, values=["text", "multiline", "choice", "checkbox"], state="readonly", width=11)
            cb.grid(row=row_idx, column=2, sticky="w", padx=sc(6), pady=sc(3))
            cb.bind("<<ComboboxSelected>>", _on_type_change)

            # Col 3: Choices / Options
            if f.get("type") == "choice":
                c_count = len(f.get("choices", []))
                btn_choices = tk.Button(
                    self.fields_container, text=f"⚙ {c_count} Choices...", font=("Inter", sc(7.5)),
                    bg=self.colors["card_bg"], fg=self.colors["secondary"],
                    relief="solid", bd=1, cursor="hand2", padx=sc(4), pady=0,
                    command=lambda i=idx: self._edit_field_choices(i)
                )
                btn_choices.grid(row=row_idx, column=3, sticky="w", padx=sc(6), pady=sc(3))
            else:
                tk.Label(self.fields_container, text="—", font=self.FONT_SMALL, bg=row_bg, fg=self.colors["outline"]).grid(row=row_idx, column=3, sticky="w", padx=sc(12), pady=sc(3))

            # Col 4: Readonly Checkbox (Center-aligned under header)
            ro_var = tk.BooleanVar(value=f.get("readonly", False))
            def _on_ro_change(f_idx=idx, var=ro_var):
                self.fields[f_idx]["readonly"] = var.get()
            chk = ttk.Checkbutton(self.fields_container, variable=ro_var, command=_on_ro_change)
            chk.grid(row=row_idx, column=4, sticky="n", padx=sc(6), pady=sc(3))

            # Col 5: Actions (Up, Down, Duplicate, Delete)
            actions_frame = tk.Frame(self.fields_container, bg=row_bg)
            actions_frame.grid(row=row_idx, column=5, sticky="e", padx=sc(6), pady=sc(3))

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

            btn_dup = tk.Button(
                actions_frame, text="📋", font=("Inter", sc(7)),
                bg=self.colors["surface_container_highest"], fg=self.colors["on_surface"],
                relief="flat", bd=0, cursor="hand2", width=2,
                command=lambda i=idx: self._duplicate_field(i)
            )
            btn_dup.pack(side="left", padx=1)

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

    def _duplicate_field(self, idx):
        if 0 <= idx < len(self.fields):
            src = self.fields[idx]
            base_name = src["name"]
            counter = 1
            new_name = f"{base_name}_Copy"
            while any(f["name"].lower() == new_name.lower() for f in self.fields):
                counter += 1
                new_name = f"{base_name}_Copy{counter}"

            cloned = {
                "name": new_name,
                "type": src.get("type", "text"),
                "readonly": src.get("readonly", False),
                "choices": list(src.get("choices", []))
            }
            self.fields.insert(idx + 1, cloned)
            self._refresh_fields_table()

    def _edit_field_choices(self, idx):
        if not (0 <= idx < len(self.fields)):
            return
        field = self.fields[idx]

        dlg = tk.Toplevel(self.win)
        dlg.title(f"Dropdown Choices: {field['name']}")
        dlg.configure(bg=self.colors["surface"])
        dlg.transient(self.win)
        dlg.grab_set()

        import utils
        utils.center_and_fit_toplevel(dlg, sc(420), sc(340))

        tk.Label(dlg, text=f"Dropdown Choices for '{field['name']}'", font=self.FONT_HEADER, bg=self.colors["surface"], fg=self.colors["on_surface"]).pack(anchor="w", padx=sc(16), pady=(sc(12), sc(4)))
        tk.Label(dlg, text="Enter choices separated by commas or one per line:", font=self.FONT_SMALL, bg=self.colors["surface"], fg=self.colors["on_surface_variant"]).pack(anchor="w", padx=sc(16), pady=(0, sc(8)))

        text_area = tk.Text(dlg, font=self.FONT_MONO, height=8, bg=self.colors["card_bg"], fg=self.colors["on_surface"], relief="solid", bd=1)
        text_area.pack(fill="both", expand=True, padx=sc(16), pady=sc(4))
        text_area.insert("1.0", "\n".join(field.get("choices", [])))

        btn_bar = tk.Frame(dlg, bg=self.colors["surface"], padx=sc(16), pady=sc(10))
        btn_bar.pack(fill="x", side="bottom")

        def _save_choices():
            raw = text_area.get("1.0", "end-1c")
            lines = [line.strip() for line in raw.replace(",", "\n").splitlines() if line.strip()]
            field["choices"] = list(dict.fromkeys(lines))
            dlg.destroy()
            self._refresh_fields_table()

        tk.Button(btn_bar, text="Cancel", font=self.FONT_BUTTON, bg=self.colors["surface_container_low"], fg=self.colors["on_surface"], relief="solid", bd=1, cursor="hand2", padx=sc(10), pady=sc(4), command=dlg.destroy).pack(side="right", padx=(sc(6), 0))
        tk.Button(btn_bar, text="✓ Save Choices", font=self.FONT_BUTTON, bg=self.colors["primary"], fg=self.colors["on_primary"], relief="flat", bd=0, cursor="hand2", padx=sc(12), pady=sc(4), command=_save_choices).pack(side="right")

    def _prompt_batch_add_fields(self):
        dlg = tk.Toplevel(self.win)
        dlg.title("Batch Add Multiple Fields")
        dlg.configure(bg=self.colors["surface"])
        dlg.transient(self.win)
        dlg.grab_set()

        import utils
        utils.center_and_fit_toplevel(dlg, sc(460), sc(380))

        tk.Label(dlg, text="➕ Batch Add Fields", font=self.FONT_HEADER, bg=self.colors["surface"], fg=self.colors["on_surface"]).pack(anchor="w", padx=sc(16), pady=(sc(12), sc(4)))
        tk.Label(dlg, text="Enter field names separated by newlines or commas:", font=self.FONT_SMALL, bg=self.colors["surface"], fg=self.colors["on_surface_variant"]).pack(anchor="w", padx=sc(16), pady=(0, sc(8)))

        text_area = tk.Text(dlg, font=self.FONT_MONO, height=8, bg=self.colors["card_bg"], fg=self.colors["on_surface"], relief="solid", bd=1)
        text_area.pack(fill="both", expand=True, padx=sc(16), pady=sc(4))

        type_row = tk.Frame(dlg, bg=self.colors["surface"], padx=sc(16), pady=sc(4))
        type_row.pack(fill="x")
        tk.Label(type_row, text="Default Type:", font=self.FONT_LABEL_BOLD, bg=self.colors["surface"], fg=self.colors["on_surface"]).pack(side="left", padx=(0, sc(6)))
        batch_type_var = tk.StringVar(value="text")
        cb = ttk.Combobox(type_row, textvariable=batch_type_var, values=["text", "multiline", "choice", "checkbox"], state="readonly", width=12)
        cb.pack(side="left")

        btn_bar = tk.Frame(dlg, bg=self.colors["surface"], padx=sc(16), pady=sc(10))
        btn_bar.pack(fill="x", side="bottom")

        def _save_batch():
            raw = text_area.get("1.0", "end-1c")
            tokens = [t.strip() for t in raw.replace(",", "\n").splitlines() if t.strip()]
            dtype = batch_type_var.get()
            added_count = 0

            uid_idx = next((i for i, f in enumerate(self.fields) if f["name"].upper() == "UID"), -1)

            for token in tokens:
                if token.lower() == "objectid":
                    continue
                if any(f["name"].lower() == token.lower() for f in self.fields):
                    continue
                new_f = {"name": token, "type": dtype, "readonly": False, "choices": []}
                if uid_idx >= 0:
                    self.fields.insert(uid_idx, new_f)
                    uid_idx += 1
                else:
                    self.fields.append(new_f)
                added_count += 1

            dlg.destroy()
            self._refresh_fields_table()
            messagebox.showinfo("Fields Added", f"Successfully added {added_count} new fields.", parent=self.win)

        tk.Button(btn_bar, text="Cancel", font=self.FONT_BUTTON, bg=self.colors["surface_container_low"], fg=self.colors["on_surface"], relief="solid", bd=1, cursor="hand2", padx=sc(10), pady=sc(4), command=dlg.destroy).pack(side="right", padx=(sc(6), 0))
        tk.Button(btn_bar, text="✓ Add Fields", font=self.FONT_BUTTON, bg=self.colors["primary"], fg=self.colors["on_primary"], relief="flat", bd=0, cursor="hand2", padx=sc(12), pady=sc(4), command=_save_batch).pack(side="right")

    def _toggle_all_readonly(self):
        if not self.fields:
            return
        new_state = not all(f.get("readonly", False) for f in self.fields if f["name"].upper() != "UID")
        for f in self.fields:
            if f["name"].upper() != "UID":
                f["readonly"] = new_state
        self._refresh_fields_table()

    def _clear_non_essential_fields(self):
        if messagebox.askyesno("Clear Fields", "Keep only basic core fields (Title, Category, Description, UID)?", parent=self.win):
            self.fields = [
                {"name": "Title", "type": "text", "readonly": False, "choices": []},
                {"name": "Category", "type": "text", "readonly": False, "choices": []},
                {"name": "Description", "type": "multiline", "readonly": False, "choices": []},
                {"name": "UID", "type": "text", "readonly": True, "choices": []}
            ]
            self.problem_flags = {"Title": True}
            self.groups = {"General": ["Title", "Category", "Description"], "Admin": ["UID"]}
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
    # STEP 3: Category-First Field Organization & Quality Flags (POLISHED)
    # --------------------------------------------------------------------------
    def _render_step3(self):
        inner = self._create_scrollable_card("Step 3: Organize Fields by Category & Configure Quality Flags")

        if not self.active_category or self.active_category not in self.group_names:
            self.active_category = self.group_names[0] if self.group_names else "General"
        self.preview_active_group = self.active_category

        # 1. Clear Purpose & Context Banner
        info_box = tk.Frame(
            inner, bg=self.colors["surface_container_low"],
            highlightthickness=1, highlightbackground=self.colors["card_border"],
            padx=sc(10), pady=sc(7)
        )
        info_box.pack(fill="x", pady=(0, sc(8)))

        tk.Label(
            info_box, text="💡 What to do here:",
            font=self.FONT_LABEL_BOLD, bg=self.colors["surface_container_low"],
            fg=self.colors["secondary"]
        ).pack(anchor="w")

        tk.Label(
            info_box,
            text="1. Select a category tab above to see what fields belong inside that workspace section.\n"
                 "2. Click '⇄ Move' or click '+ Field' to pull fields into this category.\n"
                 "3. Toggle '🚩 Flagged' on fields where curators should verify data accuracy during audits.",
            font=self.FONT_SMALL, bg=self.colors["surface_container_low"],
            fg=self.colors["on_surface_variant"], justify="left"
        ).pack(anchor="w", pady=(sc(2), 0))

        # 2. Category Tabs Strip (Category-First Navigation)
        self.cat_nav_container = tk.Frame(inner, bg=self.colors["card_bg"])
        self.cat_nav_container.pack(fill="x", pady=(0, sc(8)))

        # 3. Two-Column Workspace: Left = Category Field Manager, Right = Synchronized Live Preview
        split_pane = tk.Frame(inner, bg=self.colors["card_bg"])
        split_pane.pack(fill="both", expand=True, pady=(0, sc(8)))
        split_pane.columnconfigure(0, weight=3)
        split_pane.columnconfigure(1, weight=3)

        # ── LEFT COLUMN: Active Category Field Manager ──
        self.left_cat_col = tk.Frame(split_pane, bg=self.colors["card_bg"])
        self.left_cat_col.grid(row=0, column=0, sticky="nsew", padx=(0, sc(6)))

        # ── RIGHT COLUMN: Synchronized Live Form Preview ──
        self.right_prev_col = tk.Frame(
            split_pane, bg=self.colors["surface_container_low"],
            highlightthickness=1, highlightbackground=self.colors["card_border"],
            padx=sc(10), pady=sc(8)
        )
        self.right_prev_col.grid(row=0, column=1, sticky="nsew", padx=(sc(6), 0))

        # Preview Header & Mode Switcher
        prev_hdr = tk.Frame(self.right_prev_col, bg=self.colors["surface_container_low"])
        prev_hdr.pack(fill="x", pady=(0, sc(4)))

        self.prev_title_lbl = tk.Label(
            prev_hdr, text=f"👁️ PREVIEW: {self.active_category.upper()}",
            font=self.FONT_STEPPER, bg=self.colors["surface_container_low"],
            fg=self.colors["secondary"]
        )
        self.prev_title_lbl.pack(side="left")

        # Preview Mode Toggle (Standard vs Flagged Focus)
        self.btn_prev_mode = tk.Button(
            prev_hdr, text="🔍 Focus Mode" if self.preview_mode == "standard" else "📋 All Fields",
            font=("Inter", sc(7.5)), bg=self.colors["card_bg"], fg=self.colors["on_surface"],
            relief="solid", bd=1, cursor="hand2", padx=sc(5), pady=0,
            command=self._toggle_preview_mode
        )
        self.btn_prev_mode.pack(side="right")

        tk.Label(
            self.right_prev_col, text="Simulated live Arbor audit card for this section:",
            font=self.FONT_SMALL, bg=self.colors["surface_container_low"],
            fg=self.colors["on_surface_variant"]
        ).pack(anchor="w", pady=(0, sc(6)))

        # Preview Body
        self.preview_body_frame = tk.Frame(
            self.right_prev_col, bg=self.colors["card_bg"],
            highlightthickness=1, highlightbackground=self.colors["card_border"],
            padx=sc(8), pady=sc(8)
        )
        self.preview_body_frame.pack(fill="both", expand=True)

        # Global Bottom Custom Flags Drawer
        self.custom_flags_container = tk.Frame(inner, bg=self.colors["card_bg"])
        self.custom_flags_container.pack(fill="x", pady=(sc(6), 0))

        # Populate Left & Right Panels
        self._refresh_step3_ui()

    def _select_category_tab(self, cat_name):
        self.active_category = cat_name
        self.preview_active_group = cat_name
        self.move_chip_open_field = None
        self._refresh_step3_ui()

    def _refresh_step3_ui(self):
        # Ensure active category is valid
        if not self.active_category or self.active_category not in self.group_names:
            self.active_category = self.group_names[0] if self.group_names else "General"
        self.preview_active_group = self.active_category

        # 1. Render Category Navigation Tabs Strip
        for w in self.cat_nav_container.winfo_children():
            w.destroy()

        tab_scroll = tk.Frame(self.cat_nav_container, bg=self.colors["card_bg"])
        tab_scroll.pack(fill="x")

        # Group field counts
        cat_counts = {g: 0 for g in self.group_names}
        for f in self.fields:
            g = self.field_group_map.get(f["name"], "General")
            cat_counts[g] = cat_counts.get(g, 0) + 1

        for g in self.group_names:
            is_active = (g == self.active_category)
            count = cat_counts.get(g, 0)
            icon = "🧬" if "tax" in g.lower() else ("📦" if "coll" in g.lower() else ("📝" if "note" in g.lower() else ("⚙" if "admin" in g.lower() else "📁")))
            tab_text = f"{icon} {g} ({count})"

            btn_bg = self.colors["primary"] if is_active else self.colors["surface_container_low"]
            btn_fg = self.colors["on_primary"] if is_active else self.colors["on_surface"]

            btn = tk.Button(
                tab_scroll, text=tab_text,
                font=("Inter", sc(8.5), "bold" if is_active else "normal"),
                bg=btn_bg, fg=btn_fg, relief="flat" if is_active else "solid",
                bd=0 if is_active else 1, cursor="hand2", padx=sc(8), pady=sc(3),
                command=lambda gn=g: self._select_category_tab(gn)
            )
            btn.pack(side="left", padx=sc(2))

        # Add New Category Button
        btn_add_cat = tk.Button(
            tab_scroll, text="➕ New Category...", font=("Inter", sc(8)),
            bg=self.colors["surface_container_highest"], fg=self.colors["on_surface"],
            relief="flat", bd=0, cursor="hand2", padx=sc(6), pady=sc(3),
            command=self._prompt_add_group
        )
        btn_add_cat.pack(side="left", padx=sc(4))

        # Smart Auto-Organize button
        btn_auto = tk.Button(
            tab_scroll, text="⚡ Auto-Organize", font=("Inter", sc(8), "bold"),
            bg=self.colors["secondary"], fg=self.colors["on_secondary"],
            relief="flat", bd=0, cursor="hand2", padx=sc(8), pady=sc(3),
            command=self._smart_auto_organize
        )
        btn_auto.pack(side="right")

        # 2. Render Left Column: Active Category Field Manager
        for w in self.left_cat_col.winfo_children():
            w.destroy()

        # Category Header Card
        cat_card = tk.Frame(
            self.left_cat_col, bg=self.colors["surface_container_low"],
            highlightthickness=1, highlightbackground=self.colors["card_border"],
            padx=sc(8), pady=sc(6)
        )
        cat_card.pack(fill="x", pady=(0, sc(6)))

        cat_hdr = tk.Frame(cat_card, bg=self.colors["surface_container_low"])
        cat_hdr.pack(fill="x")

        icon_act = "🧬" if "tax" in self.active_category.lower() else ("📦" if "coll" in self.active_category.lower() else ("📝" if "note" in self.active_category.lower() else ("⚙" if "admin" in self.active_category.lower() else "📁")))
        tk.Label(
            cat_hdr, text=f"{icon_act} Fields in {self.active_category}:",
            font=self.FONT_LABEL_BOLD, bg=self.colors["surface_container_low"],
            fg=self.colors["on_surface"]
        ).pack(side="left")

        # Category Delete Button (if not core)
        if self.active_category not in ["Admin", "General"] and len(self.group_names) > 1:
            tk.Button(
                cat_hdr, text="Delete Category ✕", font=("Inter", sc(7)),
                bg=self.colors["surface_container_low"], fg=self.colors["error"],
                relief="flat", bd=0, cursor="hand2",
                command=lambda gn=self.active_category: self._delete_group(gn)
            ).pack(side="right")

        # Strategy presets chips bar for quick bulk flagging
        strat_sub = tk.Frame(cat_card, bg=self.colors["surface_container_low"])
        strat_sub.pack(fill="x", pady=(sc(4), 0))
        tk.Label(strat_sub, text="Quality Flags Strategy:", font=self.FONT_SMALL, bg=self.colors["surface_container_low"], fg=self.colors["on_surface_variant"]).pack(side="left", padx=(0, sc(4)))

        for s_key, s_lbl in [("key_fields", "🎯 Key Fields"), ("all_fields", "📋 All Flags"), ("none", "🚫 None")]:
            is_s = (self.validation_strategy == s_key)
            tk.Button(
                strat_sub, text=s_lbl, font=("Inter", sc(7)),
                bg=self.colors["primary"] if is_s else self.colors["card_bg"],
                fg=self.colors["on_primary"] if is_s else self.colors["on_surface"],
                relief="flat" if is_s else "solid", bd=0 if is_s else 1,
                cursor="hand2", padx=sc(4), pady=0,
                command=lambda sk=s_key: self._apply_validation_strategy(sk)
            ).pack(side="left", padx=1)

        # Fields in Active Category List Container
        fields_box = tk.Frame(self.left_cat_col, bg=self.colors["card_bg"])
        fields_box.pack(fill="both", expand=True)

        cat_fields = [f for f in self.fields if self.field_group_map.get(f["name"], "General") == self.active_category]

        if not cat_fields:
            empty_frame = tk.Frame(fields_box, bg=self.colors["surface_container_low"], padx=sc(8), pady=sc(10), highlightthickness=1, highlightbackground=self.colors["card_border"])
            empty_frame.pack(fill="x", pady=sc(4))
            tk.Label(
                empty_frame, text=f"No fields in '{self.active_category}' yet.\nUse the transfer chips below to pull fields in.",
                font=self.FONT_SMALL, bg=self.colors["surface_container_low"], fg=self.colors["outline"], justify="center"
            ).pack()
        else:
            for f in cat_fields:
                fname = f["name"]
                ftype = f.get("type", "text")
                icon = self._get_field_icon(fname, ftype)

                frow = tk.Frame(fields_box, bg=self.colors["surface_container_low"], padx=sc(6), pady=sc(3), highlightthickness=1, highlightbackground=self.colors["card_border"])
                frow.pack(fill="x", pady=1)

                # Field Name + Type
                tk.Label(
                    frow, text=f"{icon} {fname}", font=self.FONT_MONO, width=17,
                    anchor="w", bg=self.colors["surface_container_low"], fg=self.colors["on_surface"]
                ).pack(side="left")

                # Problem Flag Toggle
                if fname.upper() != "UID":
                    is_flagged = self.problem_flags.get(fname, False)
                    flag_btn_bg = self.colors["error"] if is_flagged else self.colors["card_bg"]
                    flag_btn_fg = "#ffffff" if is_flagged else self.colors["on_surface"]
                    flag_text = "🚩 Flagged" if is_flagged else "⚐ No Flag"

                    def _toggle_f_flag(fn=fname):
                        self.problem_flags[fn] = not self.problem_flags.get(fn, False)
                        self._refresh_step3_ui()

                    tk.Button(
                        frow, text=flag_text, font=("Inter", sc(7.5), "bold" if is_flagged else "normal"),
                        bg=flag_btn_bg, fg=flag_btn_fg, relief="flat" if is_flagged else "solid",
                        bd=0 if is_flagged else 1, cursor="hand2",
                        padx=sc(4), pady=0, command=_toggle_f_flag
                    ).pack(side="left", padx=sc(2))

                    # Move to other category toggle chip
                    is_open = (self.move_chip_open_field == fname)
                    def _toggle_move_chips(fn=fname):
                        self.move_chip_open_field = None if self.move_chip_open_field == fn else fn
                        self._refresh_step3_ui()

                    tk.Button(
                        frow, text="⇄ Move..." if not is_open else "✕ Close", font=("Inter", sc(7)),
                        bg=self.colors["primary"] if is_open else self.colors["card_bg"],
                        fg=self.colors["on_primary"] if is_open else self.colors["secondary"],
                        relief="flat" if is_open else "solid", bd=0 if is_open else 1,
                        cursor="hand2", padx=sc(4), pady=0,
                        command=_toggle_move_chips
                    ).pack(side="right")

                # Inline Move Destination Chips (revealed when '⇄ Move...' is clicked)
                if self.move_chip_open_field == fname:
                    move_chip_bar = tk.Frame(fields_box, bg=self.colors["surface_container_highest"], padx=sc(6), pady=sc(3))
                    move_chip_bar.pack(fill="x", pady=(0, 2))
                    tk.Label(move_chip_bar, text="Move to:", font=self.FONT_SMALL_BOLD, bg=self.colors["surface_container_highest"], fg=self.colors["on_surface"]).pack(side="left", padx=(0, sc(4)))

                    for target_g in self.group_names:
                        if target_g != self.active_category:
                            def _do_move(fn=fname, tg=target_g):
                                self.field_group_map[fn] = tg
                                self.move_chip_open_field = None
                                self._refresh_step3_ui()

                            tk.Button(
                                move_chip_bar, text=target_g, font=("Inter", sc(7)),
                                bg=self.colors["card_bg"], fg=self.colors["on_surface"],
                                relief="solid", bd=1, cursor="hand2", padx=sc(4), pady=0,
                                command=_do_move
                            ).pack(side="left", padx=1)

        # 3. Quick Pull Transfer Section (Fields from other categories ready to be pulled into active category)
        other_fields = [f for f in self.fields if self.field_group_map.get(f["name"], "General") != self.active_category and f["name"].upper() != "UID"]
        if other_fields:
            pull_box = tk.Frame(
                self.left_cat_col, bg=self.colors["card_bg"],
                highlightthickness=1, highlightbackground=self.colors["card_border"],
                padx=sc(6), pady=sc(4)
            )
            pull_box.pack(fill="x", pady=(sc(6), 0))

            tk.Label(
                pull_box, text=f"➕ Click to pull fields into '{self.active_category}':",
                font=self.FONT_SMALL_BOLD, bg=self.colors["card_bg"],
                fg=self.colors["secondary"]
            ).pack(anchor="w", pady=(0, sc(2)))

            pull_chips_frame = tk.Frame(pull_box, bg=self.colors["card_bg"])
            pull_chips_frame.pack(fill="x")

            for of in other_fields[:8]:  # Show top quick-pull chips
                of_name = of["name"]
                def _pull_field(fn=of_name):
                    self.field_group_map[fn] = self.active_category
                    self._refresh_step3_ui()

                tk.Button(
                    pull_chips_frame, text=f"+ {of_name}", font=("Inter", sc(7)),
                    bg=self.colors["surface_container_low"], fg=self.colors["on_surface"],
                    relief="solid", bd=1, cursor="hand2", padx=sc(4), pady=0,
                    command=_pull_field
                ).pack(side="left", padx=1, pady=1)

        # 4. Inline Add Field to Active Category
        add_in_cat = tk.Frame(self.left_cat_col, bg=self.colors["card_bg"])
        add_in_cat.pack(fill="x", pady=(sc(6), 0))

        tk.Button(
            add_in_cat, text=f"+ Add New Field to {self.active_category}", font=("Inter", sc(8)),
            bg=self.colors["surface_container_low"], fg=self.colors["on_surface"],
            relief="solid", bd=1, cursor="hand2", padx=sc(8), pady=sc(2),
            command=lambda gn=self.active_category: self._add_field_to_group(gn)
        ).pack(side="left")

        # 5. Render Custom Flags & System Flags at Bottom
        for w in self.custom_flags_container.winfo_children():
            w.destroy()

        if self.custom_problem_flags or self._deleted_flags_undo_stack:
            cf_box = tk.Frame(
                self.custom_flags_container, bg=self.colors["surface_container_low"],
                highlightthickness=1, highlightbackground=self.colors["card_border"],
                padx=sc(6), pady=sc(4)
            )
            cf_box.pack(fill="x", pady=(0, sc(4)))

            cf_top = tk.Frame(cf_box, bg=self.colors["surface_container_low"])
            cf_top.pack(fill="x", pady=(0, sc(2)))

            tk.Label(
                cf_top, text=f"Custom Problem Rules ({len(self.custom_problem_flags)})",
                font=self.FONT_LABEL_BOLD, bg=self.colors["surface_container_low"],
                fg=self.colors["on_surface"]
            ).pack(side="left")

            if self._deleted_flags_undo_stack:
                tk.Button(
                    cf_top, text="↩ Undo Delete", font=("Inter", sc(7.5), "bold"),
                    bg=self.colors["secondary"], fg=self.colors["on_secondary"],
                    relief="flat", bd=0, cursor="hand2", padx=sc(4), pady=0,
                    command=self._undo_delete_custom_flag
                ).pack(side="right")

            # Filtered flag list
            for c_idx, cf in enumerate(self.custom_problem_flags):
                c_row = tk.Frame(cf_box, bg=self.colors["card_bg"], padx=sc(4), pady=1, highlightthickness=1, highlightbackground=self.colors["card_border"])
                c_row.pack(fill="x", pady=1)

                tk.Label(c_row, text=f"🏷️ {cf['name']}", font=self.FONT_MONO_SM, bg=self.colors["card_bg"], fg=self.colors["on_surface"]).pack(side="left")
                tk.Label(c_row, text=f"🔗 {cf.get('maps_to', 'General')}", font=self.FONT_SMALL, bg=self.colors["card_bg"], fg=self.colors["secondary"]).pack(side="left", padx=sc(4))

                tk.Button(
                    c_row, text="🗑️", font=("Inter", sc(7)),
                    bg=self.colors["card_bg"], fg=self.colors["error"],
                    relief="flat", bd=0, cursor="hand2",
                    command=lambda idx=c_idx: self._delete_custom_flag(idx)
                ).pack(side="right")

                tk.Button(
                    c_row, text="✏️", font=("Inter", sc(7)),
                    bg=self.colors["card_bg"], fg=self.colors["on_surface"],
                    relief="flat", bd=0, cursor="hand2",
                    command=lambda idx=c_idx: self._edit_custom_flag(idx)
                ).pack(side="right", padx=(0, sc(2)))

        # Bottom row: Custom flag trigger and system flags
        bot_row = tk.Frame(self.custom_flags_container, bg=self.colors["card_bg"])
        bot_row.pack(fill="x", pady=(sc(2), 0))

        tk.Button(
            bot_row, text="🚩 + Custom Flag Rule...", font=("Inter", sc(8)),
            bg=self.colors["surface_container_low"], fg=self.colors["on_surface"],
            relief="solid", bd=1, cursor="hand2", padx=sc(8), pady=sc(2),
            command=self._prompt_add_custom_flag
        ).pack(side="left", padx=(0, sc(8)))

        if self.has_images:
            v_img = tk.BooleanVar(value=self.common_problems.get("Images_Problem", True))
            def _t_img(v=v_img):
                self.common_problems["Images_Problem"] = v.get()
                self._update_live_preview()
            ttk.Checkbutton(bot_row, text="Missing Photos Flag", variable=v_img, command=_t_img).pack(side="left", padx=sc(4))

        v_oth = tk.BooleanVar(value=self.common_problems.get("Other_problem", True))
        def _t_oth(v=v_oth):
            self.common_problems["Other_problem"] = v.get()
            self._update_live_preview()
        ttk.Checkbutton(bot_row, text="General Review Flag", variable=v_oth, command=_t_oth).pack(side="left", padx=sc(4))

        # 6. Update Live Mini Record Preview for Active Category
        self._update_live_preview()

    def _toggle_preview_mode(self):
        self.preview_mode = "focus" if self.preview_mode == "standard" else "standard"
        if hasattr(self, "btn_prev_mode") and self.btn_prev_mode.winfo_exists():
            self.btn_prev_mode.config(text="🔍 Focus Mode" if self.preview_mode == "standard" else "📋 All Fields")
        self._update_live_preview()

    def _update_live_preview(self):
        if hasattr(self, "prev_title_lbl") and self.prev_title_lbl.winfo_exists():
            self.prev_title_lbl.config(text=f"👁️ PREVIEW: {self.active_category.upper()}")

        # Update Preview Body
        for w in self.preview_body_frame.winfo_children():
            w.destroy()

        active_fields = [f for f in self.fields if self.field_group_map.get(f["name"], "General") == self.active_category]

        if not active_fields:
            tk.Label(
                self.preview_body_frame, text=f"No fields in '{self.active_category}' tab.",
                font=self.FONT_SMALL, bg=self.colors["card_bg"], fg=self.colors["outline"]
            ).pack(pady=sc(10))
            return

        rendered_count = 0
        for f in active_fields:
            fname = f["name"]
            ftype = f.get("type", "text")
            is_flagged = self.problem_flags.get(fname, False)
            custom_matches = [cf["name"] for cf in self.custom_problem_flags if cf.get("maps_to") == fname]
            if custom_matches:
                is_flagged = True

            # If in Focus Mode, only show flagged fields
            if self.preview_mode == "focus" and not is_flagged:
                continue

            rendered_count += 1
            field_box = tk.Frame(self.preview_body_frame, bg=self.colors["card_bg"])
            field_box.pack(fill="x", pady=sc(3))

            # Label row with optional 🚩 indicator
            lbl_row = tk.Frame(field_box, bg=self.colors["card_bg"])
            lbl_row.pack(fill="x")

            lbl_color = self.colors["error"] if is_flagged else self.colors["on_surface"]
            tk.Label(lbl_row, text=fname, font=self.FONT_LABEL_BOLD, bg=self.colors["card_bg"], fg=lbl_color).pack(side="left")

            if is_flagged:
                flag_desc = "🚩 Flag Active" if not custom_matches else f"🚩 {custom_matches[0]}"
                tk.Label(lbl_row, text=flag_desc, font=("Inter", sc(7), "bold"), bg=self.colors["card_bg"], fg=self.colors["error"]).pack(side="right")

            # Mock Input Container with 3px Accent bar when flagged
            border_color = self.colors["error"] if is_flagged else self.colors["outline_variant"]
            bg_input = self.colors["error_container"] if is_flagged else self.colors["surface_container_low"]

            mock_input = tk.Frame(
                field_box, bg=bg_input,
                highlightthickness=1, highlightbackground=border_color,
                padx=sc(6), pady=sc(3)
            )
            mock_input.pack(fill="x", pady=(1, 0))

            if is_flagged:
                # Left accent red bar matching AI_UI_GUIDE.md
                accent_bar = tk.Frame(mock_input, bg=self.colors["error"], width=sc(3))
                accent_bar.pack(side="left", fill="y", padx=(0, sc(4)))

            if ftype == "multiline":
                tk.Label(mock_input, text="— (Multi-line text area) —\nLine 2 notes...", font=self.FONT_SMALL, bg=bg_input, fg=self.colors["on_surface_variant"], justify="left").pack(anchor="w")
            elif ftype == "choice":
                choices = f.get("choices", [])
                val_text = f"▼ {choices[0]}" if choices else "▼ Select option..."
                tk.Label(mock_input, text=val_text, font=self.FONT_SMALL, bg=bg_input, fg=self.colors["on_surface_variant"]).pack(anchor="w")
            elif ftype == "checkbox":
                tk.Label(mock_input, text="☐ (Boolean Checkbox)", font=self.FONT_SMALL, bg=bg_input, fg=self.colors["on_surface_variant"]).pack(anchor="w")
            else:
                placeholder = f"— {fname} value —"
                tk.Label(mock_input, text=placeholder, font=self.FONT_SMALL, bg=bg_input, fg=self.colors["on_surface_variant"]).pack(anchor="w")

        if rendered_count == 0 and self.preview_mode == "focus":
            tk.Label(
                self.preview_body_frame, text="✨ No flagged fields in this section.\nAll fields verified!",
                font=self.FONT_SMALL, bg=self.colors["card_bg"], fg=self.colors["secondary"], justify="center"
            ).pack(pady=sc(12))

    def _get_field_icon(self, name, ftype="text"):
        n = name.lower()
        if name.upper() == "UID":
            return "🔑"
        if any(kw in n for kw in ["genus", "species", "family", "author", "taxon", "plant", "mineral"]):
            return "🌿"
        if any(kw in n for kw in ["date", "tid", "dato", "due", "time"]):
            return "📅"
        if any(kw in n for kw in ["place", "location", "locality", "room", "building"]):
            return "📍"
        if any(kw in n for kw in ["borrower", "collector", "author", "person", "user"]):
            return "👤"
        if any(kw in n for kw in ["comment", "obs", "note", "desc", "notat"]):
            return "📝"
        if ftype == "checkbox":
            return "☑"
        if ftype == "choice":
            return "☰"
        return "🏷"

    def _get_flag_suggestions(self, field_name, field_type="text"):
        n = field_name.lower()
        if any(kw in n for kw in ["genus", "species", "family", "author", "taxon", "scientific"]):
            return [
                ("Nomenclature_Outdated", "Taxonomic name is deprecated or outdated"),
                ("Spelling_Doubtful", "Suspected typography typo or phonetic spelling"),
                ("Type_Unverified", "Unverified type specimen status")
            ]
        elif any(kw in n for kw in ["place", "locality", "location", "coordinates", "lat", "lon", "country"]):
            return [
                ("Georef_Needed", "Coordinates need georeferencing"),
                ("Imprecise_Location", "Locality is vague or ambiguous"),
                ("Boundary_Unverified", "County/administrative boundary unconfirmed")
            ]
        elif any(kw in n for kw in ["date", "due", "return", "year", "tid", "dato"]):
            return [
                ("Date_Ambiguous", "Date format is incomplete or uncertain"),
                ("Overdue_Notice", "Past scheduled return date")
            ]
        elif any(kw in n for kw in ["collector", "borrower", "person", "determiner"]):
            return [
                ("Unknown_Person", "Person not matched in institutional directory"),
                ("Contact_Missing", "Affiliation or contact details absent")
            ]
        elif any(kw in n for kw in ["price", "cost", "value", "weight", "quantity"]):
            return [
                ("Valuation_Unverified", "Financial/numeric valuation needs audit"),
                ("Receipt_Missing", "Supporting invoice or receipt absent")
            ]
        elif field_type == "multiline" or any(kw in n for kw in ["note", "comment", "desc", "obs"]):
            return [
                ("Transcription_Needed", "Handwritten label text needs transcription"),
                ("Language_Translation", "Foreign language text requires translation")
            ]
        else:
            return [
                (f"{field_name}_Review", f"Review required for {field_name}"),
                (f"{field_name}_Missing", f"Required {field_name} value is missing")
            ]

    def _prompt_add_custom_flag(self, default_target=None):
        dlg = tk.Toplevel(self.win)
        dlg.title("Create Custom Problem Flag")
        dlg.configure(bg=self.colors["surface"])
        dlg.transient(self.win)
        dlg.grab_set()

        import utils
        utils.center_and_fit_toplevel(dlg, sc(500), sc(440))

        tk.Label(dlg, text="🚩 Create Custom Problem Rule", font=self.FONT_HEADER, bg=self.colors["surface"], fg=self.colors["on_surface"]).pack(anchor="w", padx=sc(16), pady=(sc(12), sc(2)))
        tk.Label(dlg, text="Attach a specific validation issue to a field or create a general audit flag.", font=self.FONT_SMALL, bg=self.colors["surface"], fg=self.colors["on_surface_variant"]).pack(anchor="w", padx=sc(16), pady=(0, sc(10)))

        # Target Field Selector
        field_row = tk.Frame(dlg, bg=self.colors["surface"])
        field_row.pack(fill="x", padx=sc(16), pady=sc(4))

        tk.Label(field_row, text="Connected Field:", font=self.FONT_LABEL_BOLD, bg=self.colors["surface"], fg=self.colors["on_surface"]).pack(side="left")

        field_names = [f["name"] for f in self.fields if f["name"].upper() != "UID"] + ["(General Database Flag)"]
        target_var = tk.StringVar(value=default_target if default_target in field_names else field_names[0])

        cb_target = ttk.Combobox(field_row, textvariable=target_var, values=field_names, state="readonly", width=22)
        cb_target.pack(side="right")

        # Flag Name Input
        name_row = tk.Frame(dlg, bg=self.colors["surface"])
        name_row.pack(fill="x", padx=sc(16), pady=sc(4))
        tk.Label(name_row, text="Flag Column Name:", font=self.FONT_LABEL_BOLD, bg=self.colors["surface"], fg=self.colors["on_surface"]).pack(anchor="w")

        name_var = tk.StringVar()
        entry_name = tk.Entry(dlg, textvariable=name_var, font=self.FONT_MONO, relief="solid", bd=1, highlightthickness=0, bg=self.colors["card_bg"], fg=self.colors["on_surface"])
        entry_name.pack(fill="x", padx=sc(16), pady=sc(2), ipady=sc(3))

        # Description Input
        desc_row = tk.Frame(dlg, bg=self.colors["surface"])
        desc_row.pack(fill="x", padx=sc(16), pady=(sc(4), 0))
        tk.Label(desc_row, text="Description / Issue Reason:", font=self.FONT_LABEL_BOLD, bg=self.colors["surface"], fg=self.colors["on_surface"]).pack(anchor="w")

        desc_var = tk.StringVar()
        entry_desc = tk.Entry(dlg, textvariable=desc_var, font=self.FONT_SMALL, relief="solid", bd=1, highlightthickness=0, bg=self.colors["card_bg"], fg=self.colors["on_surface"])
        entry_desc.pack(fill="x", padx=sc(16), pady=sc(2), ipady=sc(3))

        # Suggestions Container
        sugg_box = tk.Frame(dlg, bg=self.colors["surface_container_low"], highlightthickness=1, highlightbackground=self.colors["card_border"], padx=sc(8), pady=sc(6))
        sugg_box.pack(fill="both", expand=True, padx=sc(16), pady=sc(8))

        tk.Label(sugg_box, text="💡 1-Click Suggestions for Selected Field:", font=self.FONT_LABEL_BOLD, bg=self.colors["surface_container_low"], fg=self.colors["secondary"]).pack(anchor="w")

        sugg_chips_frame = tk.Frame(sugg_box, bg=self.colors["surface_container_low"])
        sugg_chips_frame.pack(fill="both", expand=True, pady=sc(4))

        def _update_suggestions():
            for w in sugg_chips_frame.winfo_children():
                w.destroy()
            cur_target = target_var.get()
            suggs = self._get_flag_suggestions(cur_target if cur_target != "(General Database Flag)" else "General")
            for s_name, s_desc in suggs:
                def _apply_sugg(sn=s_name, sd=s_desc):
                    name_var.set(sn)
                    desc_var.set(sd)
                btn = tk.Button(
                    sugg_chips_frame, text=f"+ {s_name}", font=("Inter", sc(7.5)),
                    bg=self.colors["card_bg"], fg=self.colors["on_surface"],
                    relief="solid", bd=1, cursor="hand2", padx=sc(4), pady=sc(2),
                    command=_apply_sugg
                )
                btn.pack(anchor="w", pady=1)

        cb_target.bind("<<ComboboxSelected>>", lambda e: _update_suggestions())
        _update_suggestions()

        # Save Button
        btn_bar = tk.Frame(dlg, bg=self.colors["surface"], padx=sc(16), pady=sc(8))
        btn_bar.pack(fill="x", side="bottom")

        def _on_save():
            raw_name = name_var.get().strip()
            if not raw_name:
                messagebox.showwarning("Missing Name", "Please enter a flag name.", parent=dlg)
                return
            clean_name = re.sub(r"[^\w]", "_", raw_name)
            target = target_var.get()
            if target == "(General Database Flag)":
                target = "Other"

            if any(cf["name"] == clean_name for cf in self.custom_problem_flags):
                messagebox.showwarning("Duplicate Flag", f"Flag '{clean_name}' already exists.", parent=dlg)
                return

            self.custom_problem_flags.append({
                "name": clean_name,
                "maps_to": target,
                "description": desc_var.get().strip(),
                "category": self._deduce_flag_category(clean_name, target)
            })
            dlg.destroy()
            self._refresh_step3_ui()

        tk.Button(btn_bar, text="Cancel", font=self.FONT_BUTTON, bg=self.colors["surface_container_low"], fg=self.colors["on_surface"], relief="solid", bd=1, cursor="hand2", padx=sc(8), pady=sc(3), command=dlg.destroy).pack(side="right", padx=(sc(6), 0))
        tk.Button(btn_bar, text="✓ Save Custom Flag", font=self.FONT_BUTTON, bg=self.colors["primary"], fg=self.colors["on_primary"], relief="flat", bd=0, cursor="hand2", padx=sc(10), pady=sc(3), command=_on_save).pack(side="right")

    def _edit_custom_flag(self, idx):
        if not (0 <= idx < len(self.custom_problem_flags)):
            return
        cf = self.custom_problem_flags[idx]

        dlg = tk.Toplevel(self.win)
        dlg.title(f"Edit Flag: {cf['name']}")
        dlg.configure(bg=self.colors["surface"])
        dlg.transient(self.win)
        dlg.grab_set()

        import utils
        utils.center_and_fit_toplevel(dlg, sc(460), sc(320))

        tk.Label(dlg, text="✏️ Edit Custom Flag Rule", font=self.FONT_HEADER, bg=self.colors["surface"], fg=self.colors["on_surface"]).pack(anchor="w", padx=sc(16), pady=(sc(12), sc(4)))

        # Target Field Selector
        field_row = tk.Frame(dlg, bg=self.colors["surface"])
        field_row.pack(fill="x", padx=sc(16), pady=sc(4))
        tk.Label(field_row, text="Connected Field:", font=self.FONT_LABEL_BOLD, bg=self.colors["surface"], fg=self.colors["on_surface"]).pack(side="left")

        field_names = [f["name"] for f in self.fields if f["name"].upper() != "UID"] + ["Other"]
        cur_target = cf.get("maps_to", "Other")
        target_var = tk.StringVar(value=cur_target if cur_target in field_names else "Other")
        cb_target = ttk.Combobox(field_row, textvariable=target_var, values=field_names, state="readonly", width=20)
        cb_target.pack(side="right")

        # Name
        name_row = tk.Frame(dlg, bg=self.colors["surface"])
        name_row.pack(fill="x", padx=sc(16), pady=sc(4))
        tk.Label(name_row, text="Flag Name:", font=self.FONT_LABEL_BOLD, bg=self.colors["surface"], fg=self.colors["on_surface"]).pack(anchor="w")
        name_var = tk.StringVar(value=cf["name"])
        tk.Entry(dlg, textvariable=name_var, font=self.FONT_MONO, relief="solid", bd=1, highlightthickness=0, bg=self.colors["card_bg"], fg=self.colors["on_surface"]).pack(fill="x", padx=sc(16), pady=sc(2), ipady=sc(3))

        # Description
        desc_row = tk.Frame(dlg, bg=self.colors["surface"])
        desc_row.pack(fill="x", padx=sc(16), pady=(sc(4), 0))
        tk.Label(desc_row, text="Description:", font=self.FONT_LABEL_BOLD, bg=self.colors["surface"], fg=self.colors["on_surface"]).pack(anchor="w")
        desc_var = tk.StringVar(value=cf.get("description", ""))
        tk.Entry(dlg, textvariable=desc_var, font=self.FONT_SMALL, relief="solid", bd=1, highlightthickness=0, bg=self.colors["card_bg"], fg=self.colors["on_surface"]).pack(fill="x", padx=sc(16), pady=sc(2), ipady=sc(3))

        btn_bar = tk.Frame(dlg, bg=self.colors["surface"], padx=sc(16), pady=sc(10))
        btn_bar.pack(fill="x", side="bottom")

        def _save_edit():
            new_name = re.sub(r"[^\w]", "_", name_var.get().strip())
            if not new_name:
                return
            cf["name"] = new_name
            cf["maps_to"] = target_var.get()
            cf["description"] = desc_var.get().strip()
            cf["category"] = self._deduce_flag_category(new_name, cf["maps_to"])
            dlg.destroy()
            self._refresh_step3_ui()

        tk.Button(btn_bar, text="Cancel", font=self.FONT_BUTTON, bg=self.colors["surface_container_low"], fg=self.colors["on_surface"], relief="solid", bd=1, cursor="hand2", padx=sc(8), pady=sc(3), command=dlg.destroy).pack(side="right", padx=(sc(6), 0))
        tk.Button(btn_bar, text="✓ Save Changes", font=self.FONT_BUTTON, bg=self.colors["primary"], fg=self.colors["on_primary"], relief="flat", bd=0, cursor="hand2", padx=sc(10), pady=sc(3), command=_save_edit).pack(side="right")

    def _delete_custom_flag(self, idx):
        if 0 <= idx < len(self.custom_problem_flags):
            deleted = self.custom_problem_flags.pop(idx)
            self._deleted_flags_undo_stack.append(deleted)
            self._refresh_step3_ui()

    def _undo_delete_custom_flag(self):
        if self._deleted_flags_undo_stack:
            restored = self._deleted_flags_undo_stack.pop()
            self.custom_problem_flags.append(restored)
            self._refresh_step3_ui()

    def _add_field_to_group(self, group_name):
        new_name = simpledialog.askstring("Add Field", f"Enter new field name for '{group_name}':", parent=self.win)
        if new_name and new_name.strip():
            clean_name = new_name.strip()
            if any(f["name"].lower() == clean_name.lower() for f in self.fields):
                messagebox.showwarning("Duplicate Field", f"Field '{clean_name}' already exists.", parent=self.win)
                return
            if clean_name.lower() == "objectid":
                messagebox.showwarning("Reserved Field", "ObjectID is the primary key and is created automatically.", parent=self.win)
                return

            # Insert field before UID
            uid_idx = next((i for i, f in enumerate(self.fields) if f["name"].upper() == "UID"), -1)
            new_entry = {"name": clean_name, "type": "text", "readonly": False, "choices": []}
            if uid_idx >= 0:
                self.fields.insert(uid_idx, new_entry)
            else:
                self.fields.append(new_entry)

            self.field_group_map[clean_name] = group_name
            self._refresh_step3_ui()

    def _prompt_add_group(self):
        new_g = simpledialog.askstring("Add Group Section", "Enter new UI section/tab name (e.g. Preservation, Conservation):", parent=self.win)
        if new_g and new_g.strip():
            clean_g = new_g.strip()
            if clean_g not in self.group_names:
                self.group_names.append(clean_g)
                self.active_category = clean_g
                self.preview_active_group = clean_g
                self._refresh_step3_ui()

    def _delete_group(self, group_name):
        if group_name in self.group_names and len(self.group_names) > 1:
            self.group_names.remove(group_name)
            # Reassign orphaned fields to General
            for f in self.fields:
                if self.field_group_map.get(f["name"]) == group_name:
                    self.field_group_map[f["name"]] = "General"
            if "General" not in self.group_names:
                self.group_names.insert(0, "General")
            self.active_category = self.group_names[0]
            self.preview_active_group = self.group_names[0]
            self._refresh_step3_ui()

    def _apply_validation_strategy(self, strategy):
        self.validation_strategy = strategy
        if strategy == "key_fields":
            for f in self.fields:
                fn = f["name"]
                if fn.upper() != "UID":
                    fn_lower = fn.lower()
                    self.problem_flags[fn] = any(kw in fn_lower for kw in ["genus", "species", "title", "borrower", "item", "collector", "date"])
        elif strategy == "all_fields":
            for f in self.fields:
                if f["name"].upper() != "UID":
                    self.problem_flags[f["name"]] = True
        elif strategy == "general_only" or strategy == "none":
            for f in self.fields:
                self.problem_flags[f["name"]] = False

        self._refresh_step3_ui()

    def _smart_auto_organize(self):
        # Auto-detect groups based on best practice keywords
        for f in self.fields:
            fn = f["name"]
            fn_lower = fn.lower()
            if fn.upper() == "UID":
                g = "Admin"
            elif any(kw in fn_lower for kw in ["genus", "species", "family", "author", "order", "class", "taxon", "variant", "rank"]):
                g = "Taxonomy"
            elif any(kw in fn_lower for kw in ["collect", "date", "place", "locality", "innsamling", "country", "altitude"]):
                g = "Collection"
            elif any(kw in fn_lower for kw in ["obs", "comment", "note", "problem", "desc", "notat", "beskrivelse"]):
                g = "Notes"
            elif any(kw in fn_lower for kw in ["loan", "borrower", "due", "return", "status"]):
                g = "Loan Details"
            else:
                g = "Details"

            if g not in self.group_names:
                self.group_names.append(g)
            self.field_group_map[fn] = g

        self._apply_validation_strategy(self.validation_strategy)
        self._refresh_step3_ui()

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

        # URL Preset Buttons
        preset_row = tk.Frame(img_box, bg=self.colors["surface_container_low"])
        preset_row.pack(fill="x", pady=(sc(2), sc(4)))

        tk.Label(preset_row, text="Presets:", font=self.FONT_SMALL_BOLD, bg=self.colors["surface_container_low"], fg=self.colors["on_surface"]).pack(side="left", padx=(0, sc(4)))

        presets = [
            ("Unimus", "https://www.unimus.no/photos/image/jpeg/O-V-OE-{num:04d}{suffix}.jpg"),
            ("GBIF / CDN", "https://images.gbif.org/specimens/{id}_{suffix}.jpg"),
            ("Local Path", "images/specimen_{num:04d}.jpg")
        ]
        for p_name, p_pattern in presets:
            tk.Button(
                preset_row, text=p_name, font=("Inter", sc(7.5)),
                bg=self.colors["card_bg"], fg=self.colors["on_surface"],
                relief="solid", bd=1, cursor="hand2", padx=sc(5), pady=0,
                command=lambda pat=p_pattern: self._apply_url_preset(pat)
            ).pack(side="left", padx=sc(2))

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

        # Live Token Preview with Interactive Test ID Box
        prev_box = tk.Frame(img_box, bg=self.colors["card_bg"], padx=sc(8), pady=sc(6), highlightthickness=1, highlightbackground=self.colors["card_border"])
        prev_box.pack(fill="x", pady=(sc(8), 0))

        test_row = tk.Frame(prev_box, bg=self.colors["card_bg"])
        test_row.pack(fill="x")

        tk.Label(test_row, text="Live URL Preview  (Test ID:", font=self.FONT_LABEL_BOLD, bg=self.colors["card_bg"], fg=self.colors["on_surface"]).pack(side="left")

        self.test_id_var = tk.StringVar(value=self.test_specimen_id)
        test_entry = tk.Entry(test_row, textvariable=self.test_id_var, font=self.FONT_MONO_SM, width=8, relief="solid", bd=1, bg=self.colors["surface"], fg=self.colors["on_surface"])
        test_entry.pack(side="left", padx=sc(4))
        tk.Label(test_row, text="):", font=self.FONT_LABEL_BOLD, bg=self.colors["card_bg"], fg=self.colors["on_surface"]).pack(side="left")

        self.test_id_var.trace_add("write", lambda *_: self._update_url_preview())

        self.url_preview_lbl = tk.Label(prev_box, text="", font=self.FONT_MONO, bg=self.colors["card_bg"], fg=self.colors["secondary"], wraplength=sc(580), justify="left")
        self.url_preview_lbl.pack(anchor="w", pady=(sc(4), 0))

        self.url_var.trace_add("write", lambda *_: self._update_url_preview())
        self._update_url_preview()

        # Location & Loan Modules Section
        mod_box = tk.Frame(inner, bg=self.colors["surface_container_low"], highlightthickness=1, highlightbackground=self.colors["card_border"], padx=sc(12), pady=sc(10))
        mod_box.pack(fill="x")

        tk.Label(mod_box, text="Integrated Modules & Sub-Tables", font=self.FONT_HEADER, bg=self.colors["surface_container_low"], fg=self.colors["on_surface"]).pack(anchor="w")

        self.loc_var = tk.BooleanVar(value=self.include_location)
        ttk.Checkbutton(mod_box, text="Include Standard Location Module (Building, Floor, Room, Cabinet, Shelf, Stored as)", variable=self.loc_var, command=lambda: setattr(self, "include_location", self.loc_var.get())).pack(anchor="w", pady=sc(4))

        self.loan_var = tk.BooleanVar(value=self.include_loan)
        ttk.Checkbutton(mod_box, text="Include Outbound Loan Module (Borrower, Loan Date, Due Date, Return Date, Status)", variable=self.loan_var, command=lambda: setattr(self, "include_loan", self.loan_var.get())).pack(anchor="w", pady=sc(2))

        self.cond_var = tk.BooleanVar(value=self.include_condition)
        ttk.Checkbutton(mod_box, text="Include Condition & Conservation Module (Condition Status, Conservation Notes, Examined Date)", variable=self.cond_var, command=lambda: setattr(self, "include_condition", self.cond_var.get())).pack(anchor="w", pady=sc(2))

    def _apply_url_preset(self, pattern):
        self.url_var.set(pattern)
        if hasattr(self, "has_images_var") and not self.has_images_var.get():
            self.has_images_var.set(True)
            self.has_images = True
        self._update_url_preview()

    def _update_url_preview(self):
        if not getattr(self, "has_images_var", None) or not self.has_images_var.get():
            if hasattr(self, "url_preview_lbl") and self.url_preview_lbl.winfo_exists():
                self.url_preview_lbl.config(text="Online image fetching disabled.", fg=self.colors["outline"])
            return

        pattern = self.url_var.get().strip() if hasattr(self, "url_var") else ""
        if not pattern:
            if hasattr(self, "url_preview_lbl") and self.url_preview_lbl.winfo_exists():
                self.url_preview_lbl.config(text="No URL pattern entered.", fg=self.colors["outline"])
            return

        raw_test_id = self.test_id_var.get().strip() if hasattr(self, "test_id_var") else "1001"
        try:
            num_val = int(re.sub(r"\D", "", raw_test_id) or "1001")
            sample = pattern.format(id=raw_test_id, num=num_val, suffix="")
            if hasattr(self, "url_preview_lbl") and self.url_preview_lbl.winfo_exists():
                self.url_preview_lbl.config(text=sample, fg=self.colors["secondary"])
        except Exception:
            if hasattr(self, "url_preview_lbl") and self.url_preview_lbl.winfo_exists():
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

        active_prob_count = sum(1 for v in self.problem_flags.values() if v) + len(self.custom_problem_flags)
        group_count = len(self.groups)

        stats = [
            ("Starter Template:", self.selected_template),
            ("Registration Fields:", f"{len(self.fields)} fields (ObjectID auto-indexed)"),
            ("Problem Flags:", f"{active_prob_count} active validation rules"),
            ("Field Groups:", f"{group_count} UI sections ({', '.join(list(self.groups.keys())[:3])}...)"),
            ("Online Photos:", "Enabled" if self.has_images else "Disabled"),
            ("Location Module:", "Included" if self.include_location else "Omitted"),
            ("Loan Module:", "Included" if self.include_loan else "Omitted"),
            ("Condition Module:", "Included" if self.include_condition else "Omitted"),
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

        for cf in getattr(self, "custom_problem_flags", []):
            cf_name = cf.get("name")
            if cf_name and not any(p["name"] == cf_name for p in problem_sections):
                problem_sections.append({
                    "name": cf_name,
                    "type": "bool",
                    "maps_to": cf.get("maps_to", "Other"),
                    "description": cf.get("description", "")
                })

        if self.common_problems.get("Images_Problem", True) and self.has_images:
            problem_sections.append({"name": "Images_Missing", "type": "bool"})
        if self.common_problems.get("Other_problem", True):
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

        # Condition & Conservation sections
        if self.include_condition:
            loc_sections.extend([
                {"name": "Condition Status", "type": "text"},
                {"name": "Conservation Notes", "type": "multiline"},
                {"name": "Examined Date", "type": "text"}
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

            try:
                self.win.unbind_all("<MouseWheel>")
            except Exception:
                pass
            self.win.destroy()
            messagebox.showinfo("Success", f"Database successfully created and initialized!\nLocation: {file_path}", parent=self.parent)

        except Exception as e:
            messagebox.showerror("Initialization Error", f"Failed to initialize database file:\n{e}", parent=self.win)
