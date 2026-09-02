"""
ui/new_database_wizard.py - Modern New Database Setup Wizard for Arbor

Provides an intuitive, responsive multi-step wizard for creating new databases
from built-in starter templates, Excel/CSV schemas, or from scratch.
Fully styled according to AI_UI_GUIDE.md with Light/Dark theme support,
responsive layout scaling, interactive schema tools, category-first field organization,
problem flag rule engine, and real-time simulated record preview.
"""

import os
import shutil
import re
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog
from datetime import datetime
import pandas as pd
import config
from config import sc

# Design tokens matching AI_UI_GUIDE.md & Arbor theme
COLORS_LIGHT = {
    "surface": "#fbfaf8",
    "surface_dim": "#e9ece5",
    "surface_container_low": "#f2f5f1",
    "surface_container": "#e9ece5",
    "surface_container_high": "#e9ece5",
    "surface_container_highest": "#e9ece5",
    "on_surface": "#2c302e",
    "on_surface_variant": "#4c4546",
    "outline": "#7e7576",
    "outline_variant": "#cfc4c5",
    "primary": "#000000",
    "on_primary": "#ffffff",
    "primary_container": "#1b1b1b",
    "on_primary_container": "#848484",
    "secondary": "#3a7d44",
    "on_secondary": "#ffffff",
    "secondary_container": "#adf0a6",
    "on_secondary_container": "#326f34",
    "error": "#C62828",
    "on_error": "#ffffff",
    "error_container": "#ffebeb",
    "warning": "#FBC02D",
    "header_bg": "#f2f5f1",
    "card_bg": "#ffffff",
    "chip_bg": "#e9ece5",
    "chip_active_bg": "#000000",
    "chip_active_fg": "#ffffff",
    "row_even": "#ffffff",
    "row_odd": "#f8f9fa",
    "select_bg": "#e9ece5",
    "select_fg": "#2c302e",
    "step_active": "#3a7d44",
    "step_complete": "#3a7d44",
    "step_inactive": "#7e7576",
    "card_border": "#d1d1d1"
}

COLORS_DARK = {
    "surface": "#181c19",
    "surface_dim": "#212622",
    "surface_container_low": "#212622",
    "surface_container": "#181c19",
    "surface_container_high": "#1e221f",
    "surface_container_highest": "#141715",
    "on_surface": "#e8ebe9",
    "on_surface_variant": "#bac2de",
    "outline": "#45475a",
    "outline_variant": "#585b70",
    "primary": "#e8ebe9",
    "on_primary": "#181c19",
    "primary_container": "#141715",
    "on_primary_container": "#a6adc8",
    "secondary": "#a6e3a1",
    "on_secondary": "#181c19",
    "secondary_container": "#1e221f",
    "on_secondary_container": "#a6e3a1",
    "error": "#c93a40",
    "on_error": "#181c19",
    "error_container": "#4c1414",
    "warning": "#f9e2af",
    "header_bg": "#212622",
    "card_bg": "#1e221f",
    "chip_bg": "#141715",
    "chip_active_bg": "#a6e3a1",
    "chip_active_fg": "#181c19",
    "row_even": "#181c19",
    "row_odd": "#212622",
    "select_bg": "#141715",
    "select_fg": "#e8ebe9",
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
        "2. Define Fields",
        "3. Organize Layout",
        "4. Quality Flags",
        "5. External Modules",
        "6. Review & Finalize"
    ]

    def __init__(self, parent, app=None, on_complete=None, edit_config=None, edit_mode=False):
        self.parent = parent
        self.app = app
        self.on_complete = on_complete
        self.edit_mode = edit_mode
        self.edit_config = edit_config

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
        self.groups = {}
        self.group_names = ["General", "Taxonomy", "Collection", "Details", "Notes", "Admin"]
        self.field_group_map = {}
        # Image config
        self.has_images = True
        self.has_images_var = tk.BooleanVar(value=self.has_images)
        self.image_url_pattern = "https://www.unimus.no/photos/image/jpeg/O-V-OE-{num:04d}{suffix}.jpg"
        self.url_var = tk.StringVar(value=self.image_url_pattern)
        self.test_specimen_id = "1001"
        self.test_id_var = tk.StringVar(value=self.test_specimen_id)
        self.url_preview_lbl = tk.Label(self.parent)
        # Sub-modules toggles
        self.include_location = True
        self.include_loan = False
        self.include_condition = False
        # Starting object ID and record count
        self.start_object_id = "1"
        self.start_id_var = tk.StringVar(value=self.start_object_id)
        self.initial_records_count = 1
        self.row_count_var = tk.IntVar(value=self.initial_records_count)
        self.output_file_path = ""
        self.output_path_var = tk.StringVar(value=self.output_file_path)
        self.profile_name = "New_Database"
        self.profile_name_var = tk.StringVar(value=self.profile_name)

        # Initialize default template schema
        if self.edit_mode and self.edit_config:
            self._load_from_edit_config()
        else:
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
        self.step_indicator_lbl.config(text=f"Step {step_num} of 6")
        self._build_stepper()

        # Update button states
        self.btn_back.config(state="normal" if step_num > 1 else "disabled")
        if step_num == 6:
            btn_text = "💾 Save Updates" if getattr(self, "edit_mode", False) else "✨ Create Database"
            self.btn_next.config(text=btn_text, bg=self.colors["secondary"])
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
        elif step_num == 6:
            self._render_step6()

    def _on_next(self):
        if not self._validate_step(self.current_step):
            return
        if self.current_step < 6:
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
        elif step == 6:
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
    def _load_from_edit_config(self):
        self.profile_name = "Edited Database" # Will be overridden in step 6
        self.fields = []
        if "ui_sections" in self.edit_config:
            # Registration fields
            for f in self.edit_config["ui_sections"].get("registration", []):
                new_f = dict(f)
                new_f["original_name"] = f["name"]
                self.fields.append(new_f)

            # Problem flags
            self.problem_flags = {}
            for pf in self.edit_config["ui_sections"].get("problems", []):
                # problem maps to field
                if pf.get("maps_to"):
                    self.problem_flags[pf["maps_to"]] = True

            # Groups
            self.groups = {}
            for g in self.edit_config["ui_sections"].get("reg_groups", []):
                self.groups[g["name"]] = list(g["fields"])
                if g["name"] not in self.group_names:
                    self.group_names.append(g["name"])
                for fname in g["fields"]:
                    self.field_group_map[fname] = g["name"]

        self.has_images = self.edit_config.get("has_images", True)
        self.image_url_pattern = self.edit_config.get("image_url_pattern", "")

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
            cb = ttk.Combobox(prof_card, textvariable=self.profile_cb_var, values=existing_profiles, state="readonly", width=26, cursor="hand2")
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
        cb = ttk.Combobox(add_bar, textvariable=self.new_field_type_var, values=["text", "multiline", "choice", "checkbox"], state="readonly", width=11, cursor="hand2")
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
            cb = ttk.Combobox(self.fields_container, textvariable=type_var, values=["text", "multiline", "choice", "checkbox"], state="readonly", width=11, cursor="hand2")
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
            chk = ttk.Checkbutton(self.fields_container, variable=ro_var, command=_on_ro_change, cursor="hand2")
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

    def _add_field_to_group(self, group_name):
        import tkinter.simpledialog as sd
        name = sd.askstring("Add Field", f"Enter new field name for {group_name}:", parent=self.win)
        if not name:
            return
        name = name.strip()
        if not name:
            return
        if any(f["name"].lower() == name.lower() for f in self.fields):
            messagebox.showwarning("Duplicate Field", f"Field '{name}' already exists.", parent=self.win)
            return

        new_entry = {"name": name, "type": "text", "readonly": False, "choices": []}
        self.fields.append(new_entry)
        self.field_group_map[name] = group_name
        self._refresh_step3_ui()

    def _toggle_preview_mode(self):
        self.preview_mode = "focus" if self.preview_mode == "standard" else "standard"
        if hasattr(self, "_refresh_step3_ui"):
            self._refresh_step3_ui()

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
        cb = ttk.Combobox(type_row, textvariable=batch_type_var, values=["text", "multiline", "choice", "checkbox"], state="readonly", width=12, cursor="hand2")
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
    def _smart_auto_organize(self):
        """Auto-organize fields into categories based on field name keywords."""
        if not hasattr(self, "groups") or not isinstance(self.groups, dict):
            self.groups = {}

        category_keywords = {
            "Taxonomy": ["genus", "species", "family", "author", "taxon"],
            "Collection": ["collector", "collection", "place", "date", "locality"],
            "Notes": ["comment", "observation", "problem", "notes", "description"],
            "Admin": ["uid", "status", "id"]
        }

        for field in self.fields:
            fname = field.get("name", "")
            if fname == "ObjectID":
                continue
            lower_fname = fname.lower()
            assigned = False
            for cat, keywords in category_keywords.items():
                if any(w in lower_fname for w in keywords):
                    g_list = self.groups.setdefault(cat, [])
                    if not isinstance(g_list, list):
                        g_list = []
                        self.groups[cat] = g_list
                    if fname not in g_list:
                        g_list.append(fname)
                    self.field_group_map[fname] = cat
                    if cat not in self.group_names:
                        self.group_names.append(cat)
                    assigned = True
                    break

            if not assigned:
                cat = "General"
                g_list = self.groups.setdefault(cat, [])
                if not isinstance(g_list, list):
                    g_list = []
                    self.groups[cat] = g_list
                if fname not in g_list:
                    g_list.append(fname)
                self.field_group_map[fname] = cat
                if cat not in self.group_names:
                    self.group_names.append(cat)

    def _render_step3(self):
        inner = self._create_scrollable_card("Step 3: Organize Fields by Category")

        # Run smart auto organize immediately when step loads if we haven't done it manually yet
        if not hasattr(self, "_auto_organized_done"):
            self._smart_auto_organize()
            self._auto_organized_done = True

        if not self.active_category or self.active_category not in self.group_names:
            self.active_category = self.group_names[0] if self.group_names else "General"

        info_box = tk.Frame(inner, bg=self.colors["surface_container_low"], highlightthickness=1, highlightbackground=self.colors["card_border"], padx=config.sc(10), pady=config.sc(7))
        info_box.pack(fill="x", pady=(0, config.sc(8)))
        tk.Label(info_box, text="💡 Group your fields:", font=self.FONT_LABEL_BOLD, bg=self.colors["surface_container_low"], fg=self.colors["secondary"]).pack(anchor="w")
        tk.Label(info_box, text="1. Select a category on the left.\n2. Move fields into the category on the right.", font=self.FONT_SMALL, bg=self.colors["surface_container_low"], fg=self.colors["on_surface_variant"], justify="left").pack(anchor="w", pady=(config.sc(2), 0))

        split_pane = tk.Frame(inner, bg=self.colors["card_bg"])
        split_pane.pack(fill="both", expand=True, pady=(0, config.sc(8)))
        split_pane.columnconfigure(0, weight=1)
        split_pane.columnconfigure(1, weight=2)

        # LEFT PANE: Categories
        self.left_cat_col = tk.Frame(split_pane, bg=self.colors["surface_container_low"], highlightthickness=1, highlightbackground=self.colors["card_border"], padx=config.sc(8), pady=config.sc(8))
        self.left_cat_col.grid(row=0, column=0, sticky="nsew", padx=(0, config.sc(6)))

        tk.Label(self.left_cat_col, text="Categories", font=self.FONT_HEADER, bg=self.colors["surface_container_low"], fg=self.colors["on_surface"]).pack(anchor="w", pady=(0, config.sc(6)))

        self.cat_list_frame = tk.Frame(self.left_cat_col, bg=self.colors["surface_container_low"])
        self.cat_list_frame.pack(fill="both", expand=True)

        btn_add_cat = tk.Button(self.left_cat_col, text="+ Add Category", font=self.FONT_BUTTON, bg=self.colors["primary"], fg=self.colors["on_primary"], cursor="hand2", command=self._add_category)
        btn_add_cat.pack(fill="x", pady=(config.sc(8), 0))

        # RIGHT PANE: Field Manager
        self.right_field_col = tk.Frame(split_pane, bg=self.colors["surface_container_low"], highlightthickness=1, highlightbackground=self.colors["card_border"], padx=config.sc(8), pady=config.sc(8))
        self.right_field_col.grid(row=0, column=1, sticky="nsew", padx=(config.sc(6), 0))

        self._refresh_step3_layout()

    def _add_category(self):
        new_cat = tk.simpledialog.askstring("New Category", "Category Name:", parent=self.win)
        if new_cat and new_cat.strip() not in self.group_names:
            self.group_names.append(new_cat.strip())
            self.active_category = new_cat.strip()
            self._refresh_step3_layout()

    def _refresh_step3_layout(self):
        # Refresh categories
        for w in self.cat_list_frame.winfo_children():
            w.destroy()

        for cat in self.group_names:
            is_active = (cat == self.active_category)
            bg_color = self.colors["primary_container"] if is_active else self.colors["surface_container_low"]
            fg_color = self.colors["on_primary_container"] if is_active else self.colors["on_surface"]

            btn = tk.Button(self.cat_list_frame, text=cat, font=self.FONT_LABEL_BOLD if is_active else self.FONT_LABEL, bg=bg_color, fg=fg_color, relief="flat", anchor="w", padx=config.sc(8), pady=config.sc(4), command=lambda c=cat: self._select_category(c), cursor="hand2")
            btn.pack(fill="x", pady=config.sc(2))

        # Refresh right pane
        for w in self.right_field_col.winfo_children():
            w.destroy()

        header = tk.Frame(self.right_field_col, bg=self.colors["surface_container_low"])
        header.pack(fill="x", pady=(0, config.sc(6)))
        tk.Label(header, text=f"Fields in: {self.active_category}", font=self.FONT_HEADER, bg=self.colors["surface_container_low"], fg=self.colors["secondary"]).pack(side="left")

        # Uncategorized or other fields combo
        all_other_fields = [f["name"] for f in self.fields if self.field_group_map.get(f["name"]) != self.active_category]
        if all_other_fields:
            add_frame = tk.Frame(self.right_field_col, bg=self.colors["surface_container_low"])
            add_frame.pack(fill="x", pady=(0, config.sc(8)))

            self.pull_field_var = tk.StringVar()
            if all_other_fields:
                self.pull_field_var.set(all_other_fields[0])
            cb = ttk.Combobox(add_frame, textvariable=self.pull_field_var, values=all_other_fields, state="readonly", width=20, cursor="hand2")
            cb.pack(side="left", padx=(0, config.sc(6)))

            tk.Button(add_frame, text="Pull into Category", font=self.FONT_SMALL, bg=self.colors["card_bg"], command=self._pull_field, cursor="hand2").pack(side="left")

        # List of fields in this category
        fields_in_cat = [f["name"] for f in self.fields if self.field_group_map.get(f["name"], "General") == self.active_category]
        for fname in fields_in_cat:
            row = tk.Frame(self.right_field_col, bg=self.colors["card_bg"], highlightthickness=1, highlightbackground=self.colors["card_border"], padx=config.sc(6), pady=config.sc(4))
            row.pack(fill="x", pady=config.sc(2))
            tk.Label(row, text=fname, font=self.FONT_MONO, bg=self.colors["card_bg"], fg=self.colors["on_surface"]).pack(side="left")

            # Remove from category (moves to General or Uncategorized)
            if self.active_category != "General":
                tk.Button(row, text="Remove", font=self.FONT_SMALL, bg=self.colors["error_container"], fg=self.colors["on_surface"], bd=0, command=lambda fn=fname: self._remove_field_from_cat(fn), cursor="hand2").pack(side="right")

    def _pull_field(self):
        fname = self.pull_field_var.get()
        if fname:
            self.field_group_map[fname] = self.active_category
            self._refresh_step3_layout()

    def _remove_field_from_cat(self, fname):
        self.field_group_map[fname] = "General"
        self._refresh_step3_layout()

    def _select_category(self, cat):
        self.active_category = cat
        self.preview_active_group = cat
        self._refresh_step3_layout()

    _select_category_tab = _select_category

    def _refresh_step3_ui(self):
        if hasattr(self, "_refresh_step3_layout"):
            self._refresh_step3_layout()

    def _apply_validation_strategy(self, strategy):
        self.validation_strategy = strategy
        for f in self.fields:
            fname = f.get("name", "")
            if strategy == "all_fields":
                self.problem_flags[fname] = True
            elif strategy == "none":
                self.problem_flags[fname] = False
            elif strategy == "key_fields":
                lower = fname.lower()
                is_key = any(w in lower for w in ["genus", "species", "title", "item", "borrower"])
                self.problem_flags[fname] = is_key

    def _get_flag_suggestions(self, field_name, field_type):
        suggestions = []
        lower = field_name.lower()
        if "species" in lower or "genus" in lower:
            suggestions.append(("Nomenclature_Outdated", "Taxonomic name needs review"))
        if "collector" in lower or "place" in lower or "location" in lower or "locality" in lower:
            suggestions.append(("Locality_Unverified", "Geographic location needs check"))
            suggestions.append(("Georef_Needed", "Geographic coordinates missing"))
        if "date" in lower or "due" in lower or "return" in lower:
            suggestions.append(("Overdue_Notice", "Date or loan deadline passed"))
        return suggestions

    def _render_step4(self):
        inner = self._create_scrollable_card("Step 4: Quality Flags & Validation")

        info_box = tk.Frame(inner, bg=self.colors["surface_container_low"], highlightthickness=1, highlightbackground=self.colors["card_border"], padx=config.sc(10), pady=config.sc(7))
        info_box.pack(fill="x", pady=(0, config.sc(8)))
        tk.Label(info_box, text="💡 Set up quality flags:", font=self.FONT_LABEL_BOLD, bg=self.colors["surface_container_low"], fg=self.colors["secondary"]).pack(anchor="w")
        tk.Label(info_box, text="Attach problem flags to specific fields. These flags highlight fields during data audits.", font=self.FONT_SMALL, bg=self.colors["surface_container_low"], fg=self.colors["on_surface_variant"], justify="left").pack(anchor="w", pady=(config.sc(2), 0))

        split_pane = tk.Frame(inner, bg=self.colors["card_bg"])
        split_pane.pack(fill="both", expand=True, pady=(0, config.sc(8)))
        split_pane.columnconfigure(0, weight=2)
        split_pane.columnconfigure(1, weight=1)

        # LEFT PANE: Simulated Card
        self.left_sim_col = tk.Frame(split_pane, bg=self.colors["surface_container_low"], highlightthickness=1, highlightbackground=self.colors["card_border"], padx=config.sc(8), pady=config.sc(8))
        self.left_sim_col.grid(row=0, column=0, sticky="nsew", padx=(0, config.sc(6)))

        # RIGHT PANE: Flag Toolbox
        self.right_flag_col = tk.Frame(split_pane, bg=self.colors["surface_container_low"], highlightthickness=1, highlightbackground=self.colors["card_border"], padx=config.sc(8), pady=config.sc(8))
        self.right_flag_col.grid(row=0, column=1, sticky="nsew", padx=(config.sc(6), 0))

        self.selected_flag_field = None
        self._refresh_step4_layout()

    def _refresh_step4_layout(self):
        # Left pane (Simulated Card)
        for w in self.left_sim_col.winfo_children():
            w.destroy()

        tk.Label(self.left_sim_col, text="Simulated Object Card", font=self.FONT_HEADER, bg=self.colors["surface_container_low"], fg=self.colors["on_surface"]).pack(anchor="w", pady=(0, config.sc(6)))

        # Global block
        global_frame = tk.Frame(self.left_sim_col, bg=self.colors["card_bg"], highlightthickness=1, highlightbackground=self.colors["card_border"], padx=config.sc(8), pady=config.sc(8))
        global_frame.pack(fill="x", pady=(0, config.sc(6)))
        tk.Label(global_frame, text="Global Record Settings", font=self.FONT_LABEL_BOLD, bg=self.colors["card_bg"], fg=self.colors["on_surface"]).pack(anchor="w")

        global_flags = [pf for pf in self.custom_problem_flags if pf.get("maps_to") == "Other"]
        if self.common_problems.get("Images_Problem", True) and self.has_images:
            tk.Label(global_frame, text="[🚩 Images_Missing]", font=self.FONT_MONO_SM, bg=self.colors["card_bg"], fg=self.colors["error"]).pack(anchor="w")
        if self.common_problems.get("Other_problem", True):
            tk.Label(global_frame, text="[🚩 Other_problem]", font=self.FONT_MONO_SM, bg=self.colors["card_bg"], fg=self.colors["error"]).pack(anchor="w")
        for gf in global_flags:
            tk.Label(global_frame, text=f"[🚩 {gf.get('name')}]", font=self.FONT_MONO_SM, bg=self.colors["card_bg"], fg=self.colors["error"]).pack(anchor="w")

        # Grouped fields
        for cat in self.group_names:
            cat_fields = [f["name"] for f in self.fields if self.field_group_map.get(f["name"], "General") == cat]
            if not cat_fields: continue

            cat_frame = tk.Frame(self.left_sim_col, bg=self.colors["card_bg"], highlightthickness=1, highlightbackground=self.colors["card_border"], padx=config.sc(8), pady=config.sc(8))
            cat_frame.pack(fill="x", pady=config.sc(4))
            tk.Label(cat_frame, text=cat.upper(), font=self.FONT_LABEL_BOLD, bg=self.colors["card_bg"], fg=self.colors["secondary"]).pack(anchor="w", pady=(0, config.sc(4)))

            for fname in cat_fields:
                row = tk.Frame(cat_frame, bg=self.colors["card_bg"], cursor="hand2")
                row.pack(fill="x", pady=config.sc(2))
                is_sel = (fname == self.selected_flag_field)
                bg_col = self.colors["surface_container_highest"] if is_sel else self.colors["card_bg"]
                row.config(bg=bg_col)

                lbl = tk.Label(row, text=fname, font=self.FONT_MONO, bg=bg_col, fg=self.colors["on_surface"])
                lbl.pack(side="left")

                # Show flags mapped to this field
                if self.problem_flags.get(fname):
                    tk.Label(row, text=f"[🚩 {fname}_Problem]", font=self.FONT_MONO_SM, bg=bg_col, fg=self.colors["error"]).pack(side="left", padx=(config.sc(4), 0))

                for cf in self.custom_problem_flags:
                    if cf.get("maps_to") == fname:
                        tk.Label(row, text=f"[🚩 {cf.get('name')}]", font=self.FONT_MONO_SM, bg=bg_col, fg=self.colors["error"]).pack(side="left", padx=(config.sc(4), 0))

                # Bind click to select field
                row.bind("<Button-1>", lambda e, f=fname: self._select_flag_field(f))
                lbl.bind("<Button-1>", lambda e, f=fname: self._select_flag_field(f))

        # Right pane (Toolbox)
        for w in self.right_flag_col.winfo_children():
            w.destroy()

        if not self.selected_flag_field:
            tk.Label(self.right_flag_col, text="Select a field on the left to manage its flags.", font=self.FONT_SMALL, bg=self.colors["surface_container_low"], fg=self.colors["on_surface_variant"], wraplength=config.sc(150)).pack(pady=config.sc(20))
            return

        tk.Label(self.right_flag_col, text=f"Flags for: {self.selected_flag_field}", font=self.FONT_HEADER, bg=self.colors["surface_container_low"], fg=self.colors["on_surface"]).pack(anchor="w", pady=(0, config.sc(8)))

        # Default flag toggle
        has_default = self.problem_flags.get(self.selected_flag_field, False)
        btn_def = tk.Button(self.right_flag_col, text=f"Remove '{self.selected_flag_field}_Problem'" if has_default else f"Add '{self.selected_flag_field}_Problem'",
                          font=self.FONT_SMALL, bg=self.colors["error_container"] if has_default else self.colors["primary_container"],
                          command=self._toggle_default_flag, cursor="hand2")
        btn_def.pack(fill="x", pady=config.sc(4))

        # Custom flags
        tk.Label(self.right_flag_col, text="Custom Flags:", font=self.FONT_LABEL_BOLD, bg=self.colors["surface_container_low"], fg=self.colors["on_surface"]).pack(anchor="w", pady=(config.sc(8), config.sc(4)))
        for cf in self.custom_problem_flags:
            if cf.get("maps_to") == self.selected_flag_field:
                cf_row = tk.Frame(self.right_flag_col, bg=self.colors["surface_container_low"])
                cf_row.pack(fill="x", pady=config.sc(2))
                tk.Label(cf_row, text=cf.get("name"), font=self.FONT_MONO_SM, bg=self.colors["surface_container_low"], fg=self.colors["on_surface"]).pack(side="left")
                tk.Button(cf_row, text="X", font=self.FONT_SMALL, bg=self.colors["error"], fg="white", bd=0, command=lambda c=cf: self._remove_custom_flag(c), cursor="hand2").pack(side="right")

        tk.Button(self.right_flag_col, text="+ Add Custom Flag", font=self.FONT_SMALL, bg=self.colors["card_bg"], command=self._add_custom_flag, cursor="hand2").pack(fill="x", pady=(config.sc(8), 0))

    def _select_flag_field(self, fname):
        self.selected_flag_field = fname
        self._refresh_step4_layout()

    def _toggle_default_flag(self):
        if self.selected_flag_field:
            self.problem_flags[self.selected_flag_field] = not self.problem_flags.get(self.selected_flag_field, False)
            self._refresh_step4_layout()

    def _add_custom_flag(self):
        if not self.selected_flag_field: return
        name = tk.simpledialog.askstring("Custom Flag", "Flag Name (e.g. Needs_Conservation):", parent=self.win)
        if name:
            name = re.sub(r'[^a-zA-Z0-9_]', '_', name)
            self.custom_problem_flags.append({
                "name": name,
                "maps_to": self.selected_flag_field,
                "description": f"Custom flag for {self.selected_flag_field}"
            })
            self._refresh_step4_layout()

    def _delete_custom_flag(self, index_or_item):
        if isinstance(index_or_item, int):
            if 0 <= index_or_item < len(self.custom_problem_flags):
                flag = self.custom_problem_flags.pop(index_or_item)
                self._deleted_flags_undo_stack.append(flag)
        elif index_or_item in self.custom_problem_flags:
            self.custom_problem_flags.remove(index_or_item)
            self._deleted_flags_undo_stack.append(index_or_item)
        if hasattr(self, "_refresh_step4_layout") and hasattr(self, "left_sim_col"):
            self._refresh_step4_layout()

    def _remove_custom_flag(self, flag_dict):
        self._delete_custom_flag(flag_dict)

    def _undo_delete_custom_flag(self):
        if self._deleted_flags_undo_stack:
            flag = self._deleted_flags_undo_stack.pop()
            if flag not in self.custom_problem_flags:
                self.custom_problem_flags.append(flag)
            if hasattr(self, "_refresh_step4_layout") and hasattr(self, "left_sim_col"):
                self._refresh_step4_layout()

    def _render_step5(self):
        inner = self._create_scrollable_card("Step 5: Configure External Modules (Images & Locations)")

        # Online Image Fetching Section
        img_box = tk.Frame(inner, bg=self.colors["surface_container_low"], highlightthickness=1, highlightbackground=self.colors["card_border"], padx=sc(12), pady=sc(10))
        img_box.pack(fill="x", pady=(0, sc(12)))

        tk.Label(img_box, text="Online Specimen Image Fetching", font=self.FONT_HEADER, bg=self.colors["surface_container_low"], fg=self.colors["on_surface"]).pack(anchor="w")

        self.has_images_var.set(self.has_images)
        def _on_img_toggle():
            self.has_images = self.has_images_var.get()
            url_entry.config(state="normal" if self.has_images else "disabled")
            self._update_url_preview()

        ttk.Checkbutton(img_box, text="Enable Online Image URL Resolution", variable=self.has_images_var, command=_on_img_toggle, cursor="hand2").pack(anchor="w", pady=sc(4))

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

        self.url_var.set(self.image_url_pattern)
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

        self.test_id_var.set(self.test_specimen_id)
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
        ttk.Checkbutton(mod_box, text="Include Standard Location Module (Building, Floor, Room, Cabinet, Shelf, Stored as)", variable=self.loc_var, command=lambda: setattr(self, "include_location", self.loc_var.get()), cursor="hand2").pack(anchor="w", pady=sc(4))

        self.loan_var = tk.BooleanVar(value=self.include_loan)
        ttk.Checkbutton(mod_box, text="Include Outbound Loan Module (Borrower, Loan Date, Due Date, Return Date, Status)", variable=self.loan_var, command=lambda: setattr(self, "include_loan", self.loan_var.get()), cursor="hand2").pack(anchor="w", pady=sc(2))

        self.cond_var = tk.BooleanVar(value=self.include_condition)
        ttk.Checkbutton(mod_box, text="Include Condition & Conservation Module (Condition Status, Conservation Notes, Examined Date)", variable=self.cond_var, command=lambda: setattr(self, "include_condition", self.cond_var.get()), cursor="hand2").pack(anchor="w", pady=sc(2))

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
    def _render_step6(self):
        inner = self._create_scrollable_card("Step 6: Review & Finalize Database")

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

        if not any(f["name"].upper() == "UID" for f in reg_sections):
            reg_sections.append({"name": "UID", "type": "text", "readonly": True})

        problem_sections = []
        for f_name, enabled in self.problem_flags.items():
            if enabled:
                problem_sections.append({"name": f"{f_name}_Problem", "type": "bool", "maps_to": f_name})

        for cf in getattr(self, "custom_problem_flags", []):
            cf_name = cf.get("name")
            if cf_name and not any(p["name"] == cf_name for p in problem_sections):
                p_entry = {"name": cf_name, "type": "bool", "description": cf.get("description", "")}
                p_map = cf.get("maps_to")
                if p_map and p_map != "Other":
                    p_entry["maps_to"] = p_map
                problem_sections.append(p_entry)

        if self.common_problems.get("Images_Problem", True) and self.has_images:
            problem_sections.append({"name": "Images_Missing", "type": "bool"})
        if self.common_problems.get("Other_problem", True):
            problem_sections.append({"name": "Other_problem", "type": "bool"})

        reg_groups_list = []
        for g_name, g_fields in self.groups.items():
            if g_fields:
                reg_groups_list.append({"name": g_name, "fields": g_fields})

        loc_sections = []
        if self.include_location:
            loc_sections = [{"name": "Stored as", "type": "text"}, {"name": "Building", "type": "text"}, {"name": "Floor", "type": "text"}, {"name": "Room", "type": "text"}, {"name": "Cabinet", "type": "text"}, {"name": "Shelf", "type": "text"}]
        if self.include_loan:
            loc_sections.extend([{"name": "Loaned out", "type": "checkbox"}, {"name": "Borrower", "type": "text"}, {"name": "Loan Date", "type": "text"}, {"name": "Due Date", "type": "text"}, {"name": "Return Date", "type": "text"}])
        if self.include_condition:
            loc_sections.extend([{"name": "Condition Status", "type": "text"}, {"name": "Conservation Notes", "type": "multiline"}, {"name": "Examined Date", "type": "text"}])

        image_pattern = self.url_var.get().strip() if hasattr(self, "url_var") else self.image_url_pattern

        new_config = {
            "has_images": self.has_images,
            "image_url_pattern": image_pattern,
            "sheets": {"reg": "Registration", "obs": "Observation", "photo": "Photo", "log": "Log"},
            "ui_sections": {"registration": reg_sections, "reg_groups": reg_groups_list, "location": loc_sections, "problems": problem_sections, "unknown_fields": []}
        }

        if getattr(self, "edit_mode", False) and getattr(self.app, "excel_path", None):
            # Edit mode logic
            try:
                import shutil
                bak_path = self.app.excel_path + ".bak"
                shutil.copy2(self.app.excel_path, bak_path)

                df_reg = self.app.df_reg.copy()
                df_obs = self.app.df_obs.copy()
                df_photo = self.app.df_photo.copy()
                df_log = self.app.df_log.copy()

                # Apply renames to reg
                rename_map = {}
                for f in self.fields:
                    orig = f.get("original_name")
                    if orig and orig != f["name"] and orig in df_reg.columns:
                        rename_map[orig] = f["name"]
                if rename_map:
                    df_reg.rename(columns=rename_map, inplace=True)

                # Drop removed cols
                current_reg_cols = [f["name"] for f in reg_sections]
                for col in list(df_reg.columns):
                    if col not in current_reg_cols:
                        df_reg.drop(columns=[col], inplace=True)

                # Add new cols
                for col in current_reg_cols:
                    if col not in df_reg.columns:
                        df_reg[col] = pd.NA

                # Observation cols update
                obs_cols = [f["name"] for f in loc_sections]
                prob_cols = [f["name"] for f in problem_sections]
                obs_cols.extend(prob_cols)
                obs_cols.extend(["Reviewed", "ReviewedAt", "Images_Missing"])
                obs_cols = list(dict.fromkeys(obs_cols))

                for col in list(df_obs.columns):
                    if col not in obs_cols and col not in ["ObjectID"]:
                        df_obs.drop(columns=[col], inplace=True)

                for col in obs_cols:
                    if col not in df_obs.columns:
                        if col in prob_cols or col == "Reviewed" or col == "Images_Missing":
                            df_obs[col] = False
                        else:
                            df_obs[col] = pd.NA

                # Save changes
                with pd.ExcelWriter(self.app.excel_path) as writer:
                    df_reg.to_excel(writer, sheet_name=new_config["sheets"]["reg"])
                    df_obs.to_excel(writer, sheet_name=new_config["sheets"]["obs"])
                    df_photo.to_excel(writer, sheet_name=new_config["sheets"]["photo"])
                    df_log.to_excel(writer, sheet_name=new_config["sheets"]["log"], index=False)

                prefs = config.load_prefs()
                if "custom_databases" not in prefs:
                    prefs["custom_databases"] = {}
                prefs["custom_databases"][name] = new_config
                config.save_prefs(prefs)
                config.DATABASE_CONFIGS[name] = new_config

                self.app.config = new_config
                self.app.config_name = name
                self.app.df_reg = df_reg
                self.app.df_obs = df_obs

                try:
                    self.win.unbind_all("<MouseWheel>")
                except Exception:
                    pass
                self.win.destroy()
                messagebox.showinfo("Success", "Database schema updated successfully! A backup was created at " + bak_path, parent=self.parent)

                if self.on_complete:
                    self.on_complete(self.app.excel_path, name)
            except Exception as e:
                messagebox.showerror("Update Error", f"Failed to update schema:\n{e}", parent=self.win)
            return

        # NEW DB CREATION
        try:
            # Generate ObjectIDs
            object_ids = []
            try:
                numeric_id = int(start_id)
                for i in range(row_count):
                    object_ids.append(numeric_id + i)
            except ValueError:
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

            reg_cols = [f["name"] for f in reg_sections]
            df_reg = pd.DataFrame(index=object_ids, columns=reg_cols)
            df_reg.index.name = "ObjectID"

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

            df_photo = pd.DataFrame(columns=["ObjectID", "ImagePath", "ImageNote"])
            df_photo.set_index("ObjectID", inplace=True)

            df_log = pd.DataFrame([{
                "Timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "Action": "DATABASE_CREATED",
                "Columns": f"Created with {len(reg_cols)} columns",
                "Values": f"Initial records count: {row_count}"
            }])

            os.makedirs(os.path.dirname(os.path.abspath(file_path)), exist_ok=True)
            with pd.ExcelWriter(file_path) as writer:
                df_reg.to_excel(writer, sheet_name=new_config["sheets"]["reg"])
                df_obs.to_excel(writer, sheet_name=new_config["sheets"]["obs"])
                df_photo.to_excel(writer, sheet_name=new_config["sheets"]["photo"])
                df_log.to_excel(writer, sheet_name=new_config["sheets"]["log"], index=False)

            prefs = config.load_prefs()
            if "custom_databases" not in prefs:
                prefs["custom_databases"] = {}
            prefs["custom_databases"][name] = new_config
            config.save_prefs(prefs)
            config.DATABASE_CONFIGS[name] = new_config

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
