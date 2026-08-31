import tkinter as tk
from tkinter import ttk, simpledialog
import config
from config import sc

# Color scheme definitions matching Filter menu & Historical Conflict Resolver (Zero emojis/symbols)
COLORS_LIGHT = {
    "bg": "#fbfaf8",
    "surface": "#ffffff",
    "surface_dim": "#f2f5f1",
    "header_bg": "#eaeaea",
    "border": "#d1d1d1",
    "text": "#2c302e",
    "text_muted": "#444748",
    "primary": "#000000",
    "on_primary": "#ffffff",
    "success": "#3a7d44",
    "on_success": "#ffffff",
    "warning": "#c93a40",
    "on_warning": "#ffffff",
    "accent_bar": "#3e7b3e",
    "focus_line": "#3a7d44",
    "badge_bg": "#e9ece5",
}

COLORS_DARK = {
    "bg": "#181c19",
    "surface": "#212622",
    "surface_dim": "#1e221f",
    "header_bg": "#212622",
    "border": "#141715",
    "text": "#e8ebe9",
    "text_muted": "#a6adc8",
    "primary": "#ffffff",
    "on_primary": "#11111b",
    "success": "#a6e3a1",
    "on_success": "#11111b",
    "warning": "#c93a40",
    "on_warning": "#11111b",
    "accent_bar": "#a6e3a1",
    "focus_line": "#a6e3a1",
    "badge_bg": "#141715",
}

# Configured default fields and choices
DEFAULT_LOCATION_FIELDS = [
    {
        "name": "Stored as",
        "type": "choice",
        "choices": [
            "Mounted on wooden platform",
            "Petridish",
            "in plastic box",
            "in paper box",
            "Free standing",
            "in plastic bag"
        ]
    },
    {
        "name": "Building",
        "type": "choice",
        "choices": ["Lid's hus", "Økern", "Annet"]
    },
    {
        "name": "Floor",
        "type": "choice",
        "choices": ["4", "3", "2", "1", "-1", "-2"]
    },
    {"name": "Cabinet", "type": "text"},
    {"name": "Extra", "type": "text"},
    {"name": "Loaned out", "type": "checkbox"},
    {"name": "Loaned out date", "type": "text", "readonly": True}
]


class LocationPanel(tk.Frame):
    """
    Decoupled Location Panel Component for Arbor.
    Supports three visual modes:
      - 'vertical': Left Column vertical stacked card view.
      - 'horizontal' / 'horizontal_1row': Middle Column default single-row grid.
      - 'horizontal_2row': Middle Column alternate 2-row grid for max vertical space utilization.
    """
    def __init__(
        self,
        parent,
        mode="vertical",
        location_vars=None,
        config_ref=None,
        live_callbacks=None,
        dark_mode=False,
        **kwargs
    ):
        super().__init__(parent, **kwargs)
        self.mode = mode if mode in ("vertical", "horizontal", "horizontal_1row", "horizontal_2row") else "vertical"
        self.dark_mode = dark_mode
        self.config_ref = config_ref or getattr(config, "DEFAULT_CONFIG", {})
        self.live_callbacks = live_callbacks or {}
        
        # Initialize or link location variables
        self.location_vars = location_vars if location_vars is not None else {}
        self._ensure_location_vars()
        
        self.active_preset_var = tk.StringVar(value="Default")
        self.toast_var = tk.StringVar(value="")
        
        self.field_entries = []
        self.colors = COLORS_DARK if self.dark_mode else COLORS_LIGHT
        
        self.configure(bg=self.colors["bg"])
        self.build_ui()

    def _ensure_location_vars(self):
        field_defs = self._get_field_defs()
        for f in field_defs:
            name = f["name"]
            if name not in self.location_vars:
                self.location_vars[name] = tk.StringVar(value="")
                self.location_vars[name].trace_add("write", lambda *_, n=name: self._on_field_var_change(n))

    def _get_field_defs(self):
        if self.config_ref and isinstance(self.config_ref, dict):
            loc_sections = self.config_ref.get("ui_sections", {}).get("location", [])
            if loc_sections:
                return loc_sections
        return DEFAULT_LOCATION_FIELDS

    def _on_field_var_change(self, field_name):
        val = self.location_vars[field_name].get()
        if field_name == "Loaned out" and hasattr(self, "_loan_card_widgets"):
            for card, bar, lbl in self._loan_card_widgets:
                if card.winfo_exists():
                    self._update_loan_card_style(card, bar, lbl)
        if "on_field_change" in self.live_callbacks:
            self.live_callbacks["on_field_change"](field_name, val)

    def set_dark_mode(self, is_dark):
        self.dark_mode = is_dark
        self.colors = COLORS_DARK if self.dark_mode else COLORS_LIGHT
        self.configure(bg=self.colors["bg"])
        self.build_ui()

    def set_layout_mode(self, mode_name):
        if mode_name in ("vertical", "horizontal", "horizontal_1row", "horizontal_2row"):
            self.mode = mode_name
            self.build_ui()

    def build_ui(self):
        for child in self.winfo_children():
            child.destroy()
        self.field_entries.clear()
        self._loan_card_widgets = []
        
        if self.mode == "vertical":
            self._build_vertical_ui()
        elif self.mode in ("horizontal", "horizontal_1row"):
            self._build_horizontal_1row_ui()
        elif self.mode == "horizontal_2row":
            self._build_horizontal_2row_ui()

    # -------------------------------------------------------------------------
    # Presets Helpers
    # -------------------------------------------------------------------------
    def _get_preset_names(self):
        prefs = config.load_prefs()
        presets = list(prefs.get("data_presets", {}).keys())
        if "Default" not in presets:
            presets.insert(0, "Default")
        return presets

    def _build_presets_toolbar(self, parent_frame, is_horiz=False):
        c = self.colors
        p_frame = tk.Frame(parent_frame, bg=c["surface_dim"] if is_horiz else c["bg"])
        
        lbl = tk.Label(
            p_frame,
            text="PRESETS",
            font=("JetBrains Mono", sc(9), "bold"),
            bg=p_frame.cget("bg"),
            fg=c["text_muted"]
        )
        lbl.pack(side="left", padx=(0, sc(4)))
        
        preset_names = self._get_preset_names()
        if self.active_preset_var.get() not in preset_names and preset_names:
            self.active_preset_var.set(preset_names[0])
            
        self.preset_combobox = ttk.Combobox(
            p_frame,
            textvariable=self.active_preset_var,
            values=preset_names,
            state="normal",
            width=sc(10) if is_horiz else sc(12)
        , cursor="hand2")
        self.preset_combobox.pack(side="left", padx=sc(2))
        
        save_text = "Save..." if is_horiz else "Save Preset..."
        save_btn = tk.Button(
            p_frame,
            text=save_text,
            font=("JetBrains Mono", sc(9), "bold"),
            fg=c["text"], bg=c["surface"],
            bd=1, relief="solid",
            activebackground=c["surface_dim"],
            cursor="hand2",
            padx=sc(6), pady=sc(2),
            command=self.save_current_preset
        )
        save_btn.pack(side="left", padx=sc(2))
        
        apply_text = "Apply" if is_horiz else "Apply Preset(Ctrl+K)"
        apply_btn = tk.Button(
            p_frame,
            text=apply_text,
            font=("JetBrains Mono", sc(9), "bold"),
            fg=c["on_primary"], bg=c["primary"],
            bd=1, relief="solid",
            activebackground=c["surface_dim"],
            cursor="hand2",
            padx=sc(6), pady=sc(2),
            command=self.apply_active_preset
        )
        apply_btn.pack(side="left", padx=sc(2))
        
        # Tooltip status bindings for horizontal mode
        def _on_enter_save(e):
            if not self.toast_var.get().startswith("[PRESET"):
                self.toast_var.set("[Save current location preset]")
        def _on_leave_save(e):
            if not self.toast_var.get().startswith("[PRESET"):
                self.toast_var.set("")
        save_btn.bind("<Enter>", _on_enter_save)
        save_btn.bind("<Leave>", _on_leave_save)

        def _on_enter_apply(e):
            if not self.toast_var.get().startswith("[PRESET"):
                self.toast_var.set("[Apply selected preset (Ctrl+K)]")
        def _on_leave_apply(e):
            if not self.toast_var.get().startswith("[PRESET"):
                self.toast_var.set("")
        apply_btn.bind("<Enter>", _on_enter_apply)
        apply_btn.bind("<Leave>", _on_leave_apply)
        
        return p_frame

    def apply_active_preset(self):
        preset_name = self.active_preset_var.get().strip() or "Default"
        prefs = config.load_prefs()
        saved = prefs.get("data_presets", {}).get(preset_name, {})
        
        for k, var in self.location_vars.items():
            if k in saved:
                var.set(saved[k])
                
        self.toast_var.set(f"[PRESET APPLIED: {preset_name.upper()}]")
        self.after(3000, lambda: self.toast_var.set(""))
        
        if "on_preset_applied" in self.live_callbacks:
            self.live_callbacks["on_preset_applied"](preset_name, saved)
        if "on_commit" in self.live_callbacks:
            self.live_callbacks["on_commit"](self.get_data())

    def save_current_preset(self):
        name = self.active_preset_var.get().strip()
        if not name or name == "Default":
            asked = simpledialog.askstring("Save Preset", "Enter a name for this Location Preset:", parent=self)
            if not asked:
                return
            name = asked.strip()
            self.active_preset_var.set(name)
            
        prefs = config.load_prefs()
        if "data_presets" not in prefs:
            prefs["data_presets"] = {}
            
        vals = self.get_data()
        prefs["data_presets"][name] = vals
        config.save_prefs(prefs)
        
        preset_names = self._get_preset_names()
        self.preset_combobox["values"] = preset_names
        
        self.toast_var.set(f"[PRESET SAVED: {name.upper()}]")
        self.after(3000, lambda: self.toast_var.set(""))
        
        if "on_preset_saved" in self.live_callbacks:
            self.live_callbacks["on_preset_saved"](name, vals)

    # -------------------------------------------------------------------------
    # Loan Status Card
    # -------------------------------------------------------------------------
    def _build_loan_status_card(self, parent_frame, is_horiz=False):
        c = self.colors
        is_loaned = self.location_vars.get("Loaned out", tk.StringVar(value="False")).get() in ("True", "true", "1", True)
        
        card_bg = c["surface"]
        bar_color = c["warning"] if is_loaned else c["success"]
        status_text = "STATUS: ON LOAN [ACTIVE]" if is_loaned else "STATUS: AVAILABLE"
        
        card = tk.Frame(parent_frame, bg=card_bg, highlightbackground=c["border"], highlightthickness=1)
        
        # Left color indicator bar (4px)
        bar = tk.Frame(card, bg=bar_color, width=sc(4))
        bar.pack(side="left", fill="y")
        
        lbl = tk.Label(
            card,
            text=status_text,
            font=("JetBrains Mono", sc(9), "bold"),
            fg=bar_color if is_loaned else c["text"],
            bg=card_bg,
            cursor="hand2"
        )
        lbl.pack(side="left", padx=sc(8), pady=sc(4))
        
        def _toggle_loan(e=None):
            new_val = "False" if self.location_vars.get("Loaned out").get() in ("True", "true", "1", True) else "True"
            self.location_vars.get("Loaned out").set(new_val)
            self._update_loan_card_style(card, bar, lbl)
            if "on_loan_toggle" in self.live_callbacks:
                self.live_callbacks["on_loan_toggle"](new_val == "True")
            if "on_commit" in self.live_callbacks:
                self.live_callbacks["on_commit"](self.get_data())

        card.bind("<Button-1>", _toggle_loan)
        lbl.bind("<Button-1>", _toggle_loan)
        
        if not hasattr(self, "_loan_card_widgets"):
            self._loan_card_widgets = []
        self._loan_card_widgets.append((card, bar, lbl))

        return card

    def _update_loan_card_style(self, card, bar, lbl):
        c = self.colors
        is_loaned = self.location_vars.get("Loaned out").get() in ("True", "true", "1", True)
        bar_color = c["warning"] if is_loaned else c["success"]
        status_text = "STATUS: ON LOAN [ACTIVE]" if is_loaned else "STATUS: AVAILABLE"
        
        bar.configure(bg=bar_color)
        lbl.configure(text=status_text, fg=bar_color if is_loaned else c["text"])

    # -------------------------------------------------------------------------
    # Field Builder Helper
    # -------------------------------------------------------------------------
    def _create_field_widget(self, parent, name, fdef, is_horiz=False):
        c = self.colors
        var = self.location_vars[name]
        ftype = fdef.get("type", "text")
        
        container = tk.Frame(parent, bg=c["bg"])
        
        if is_horiz:
            lbl = tk.Label(
                container, text=name.upper(),
                font=("JetBrains Mono", sc(9), "bold"),
                bg=c["bg"], fg=c["text_muted"], anchor="w"
            )
            lbl.pack(fill="x", pady=(0, sc(2)))
        else:
            lbl = tk.Label(
                container, text=name.upper(), width=13,
                font=("JetBrains Mono", sc(9.5), "bold"),
                bg=c["bg"], fg=c["text_muted"], anchor="w"
            )
            lbl.pack(side="left", padx=(0, sc(4)))
            
        if ftype == "choice":
            choices = fdef.get("choices", [])
            if "" not in choices:
                choices = [""] + choices
            widget = ttk.Combobox(
                container,
                textvariable=var,
                values=choices,
                state="readonly" if name != "Stored as" else "normal",
                font=("JetBrains Mono", sc(10))
            , cursor="hand2")
            widget.bind("<<ComboboxSelected>>", lambda e: self._trigger_commit())
            if is_horiz:
                widget.pack(fill="x", expand=True, ipady=sc(2))
            else:
                widget.pack(side="left", fill="x", expand=True, ipady=sc(2))
        else:
            entry_box = tk.Frame(container, bg=c["bg"])
            widget = tk.Entry(
                entry_box,
                textvariable=var,
                state="disabled" if fdef.get("readonly") else "normal",
                font=("JetBrains Mono", sc(10)),
                bg=c["surface"], fg=c["text"],
                insertbackground=c["text"],
                highlightthickness=1, highlightbackground=c["border"], highlightcolor=c["surface"],
                relief="flat"
            )
            widget.pack(fill="x", expand=True, ipady=sc(2))
            
            focus_line = tk.Frame(entry_box, height=sc(2), bg=c["bg"])
            focus_line.pack(fill="x", side="bottom")
            
            def _on_in(e, fl=focus_line):
                fl.configure(bg=self.colors["focus_line"])
            def _on_out(e, fl=focus_line):
                fl.configure(bg=self.colors["bg"])
                self._trigger_commit()
                
            widget.bind("<FocusIn>", _on_in, add="+")
            widget.bind("<FocusOut>", _on_out, add="+")
            
            if is_horiz:
                entry_box.pack(fill="x", expand=True)
            else:
                entry_box.pack(side="left", fill="x", expand=True)
                
        self.field_entries.append(widget)
        widget.bind("<Shift-Up>", self._nav_prev)
        widget.bind("<Shift-Down>", self._nav_next)
        widget.bind("<Control-Up>", self._nav_prev)
        widget.bind("<Control-Down>", self._nav_next)
        if ftype != "multiline":
            widget.bind("<Return>", self._nav_next)
            
        return container

    def _trigger_commit(self):
        if "on_commit" in self.live_callbacks:
            self.live_callbacks["on_commit"](self.get_data())

    def _nav_next(self, event=None):
        if not self.field_entries: return "break"
        curr = self.focus_get()
        try:
            idx = self.field_entries.index(curr)
            next_w = self.field_entries[(idx + 1) % len(self.field_entries)]
            next_w.focus_set()
        except ValueError:
            self.field_entries[0].focus_set()
        return "break"

    def _nav_prev(self, event=None):
        if not self.field_entries: return "break"
        curr = self.focus_get()
        try:
            idx = self.field_entries.index(curr)
            prev_w = self.field_entries[(idx - 1) % len(self.field_entries)]
            prev_w.focus_set()
        except ValueError:
            self.field_entries[-1].focus_set()
        return "break"

    # -------------------------------------------------------------------------
    # Mode A: Vertical UI (Left Column)
    # -------------------------------------------------------------------------
    def _build_vertical_ui(self):
        c = self.colors
        
        # Top Header Frame
        hdr = tk.Frame(self, bg=c["surface_dim"])
        hdr.pack(fill="x", side="top")
        
        tk.Label(
            hdr, text="LOCATION",
            font=("Hanken Grotesk", sc(11), "bold"),
            bg=c["surface_dim"], fg=c["text"]
        ).pack(side="left", padx=sc(8), pady=sc(6))
        
        # Toast message badge if active
        toast_lbl = tk.Label(
            hdr, textvariable=self.toast_var,
            font=("JetBrains Mono", sc(8), "bold"),
            bg=c["surface_dim"], fg=c["success"]
        )
        toast_lbl.pack(side="right", padx=sc(8))
        
        tk.Frame(self, bg=c["border"], height=1).pack(fill="x", side="top")
        
        # Presets Toolbar
        p_toolbar = self._build_presets_toolbar(self, is_horiz=False)
        p_toolbar.pack(fill="x", padx=sc(8), pady=sc(6))
        
        tk.Frame(self, bg=c["border"], height=1).pack(fill="x", padx=sc(8), pady=(0, sc(6)))
        
        # Fields Stack
        field_defs = {f["name"]: f for f in self._get_field_defs()}
        order = ["Stored as", "Building", "Floor", "Cabinet", "Extra"]
        
        content = tk.Frame(self, bg=c["bg"])
        content.pack(fill="both", expand=True, padx=sc(8))
        
        for name in order:
            fdef = field_defs.get(name)
            if not fdef: continue
            row = self._create_field_widget(content, name, fdef, is_horiz=False)
            row.pack(fill="x", pady=sc(3))
            
        tk.Frame(content, bg=c["border"], height=1).pack(fill="x", pady=sc(6))
        
        # Loan status card
        loan_card = self._build_loan_status_card(content, is_horiz=False)
        loan_card.pack(fill="x", pady=sc(4))

    # -------------------------------------------------------------------------
    # Mode B: Horizontal 1-Row UI (Middle Column Default)
    # -------------------------------------------------------------------------
    def _build_horizontal_1row_ui(self):
        c = self.colors
        
        hdr = tk.Frame(self, bg=c["header_bg"])
        hdr.pack(fill="x", side="top")
        
        tk.Label(
            hdr, text="LOCATION",
            font=("Hanken Grotesk", sc(10), "bold"),
            bg=c["header_bg"], fg=c["text"]
        ).pack(side="left", padx=sc(8), pady=sc(4))
        
        # Presets inline
        p_toolbar = self._build_presets_toolbar(hdr, is_horiz=True)
        p_toolbar.pack(side="left", padx=sc(12))
        
        # Toast message badge
        toast_lbl = tk.Label(
            hdr, textvariable=self.toast_var,
            font=("JetBrains Mono", sc(8), "bold"),
            bg=c["header_bg"], fg=c["success"]
        )
        toast_lbl.pack(side="left", padx=sc(8))
        
        # Loan status card right
        loan_card = self._build_loan_status_card(hdr, is_horiz=True)
        loan_card.pack(side="right", padx=sc(8), pady=sc(2))
        
        tk.Frame(self, bg=c["border"], height=1).pack(fill="x", side="top")
        
        # 5-Column Grid Content
        content = tk.Frame(self, bg=c["bg"])
        content.pack(fill="x", padx=sc(8), pady=sc(6))
        
        for i in range(5):
            content.columnconfigure(i, weight=1, uniform="col")
            
        field_defs = {f["name"]: f for f in self._get_field_defs()}
        order = ["Stored as", "Building", "Floor", "Cabinet", "Extra"]
        
        for idx, name in enumerate(order):
            fdef = field_defs.get(name)
            if not fdef: continue
            cell = tk.Frame(content, bg=c["bg"])
            cell.grid(row=0, column=idx, sticky="nsew", padx=sc(4))
            row = self._create_field_widget(cell, name, fdef, is_horiz=True)
            row.pack(fill="x")

    # -------------------------------------------------------------------------
    # Mode C: Horizontal 2-Row UI (Middle Column Alternate)
    # -------------------------------------------------------------------------
    def _build_horizontal_2row_ui(self):
        c = self.colors
        
        hdr = tk.Frame(self, bg=c["header_bg"])
        hdr.pack(fill="x", side="top")
        
        tk.Label(
            hdr, text="LOCATION",
            font=("Hanken Grotesk", sc(10), "bold"),
            bg=c["header_bg"], fg=c["text"]
        ).pack(side="left", padx=sc(8), pady=sc(4))
        
        # Presets inline
        p_toolbar = self._build_presets_toolbar(hdr, is_horiz=True)
        p_toolbar.pack(side="left", padx=sc(12))
        
        toast_lbl = tk.Label(
            hdr, textvariable=self.toast_var,
            font=("JetBrains Mono", sc(8), "bold"),
            bg=c["header_bg"], fg=c["success"]
        )
        toast_lbl.pack(side="left", padx=sc(8))
        
        tk.Frame(self, bg=c["border"], height=1).pack(fill="x", side="top")
        
        field_defs = {f["name"]: f for f in self._get_field_defs()}
        
        content = tk.Frame(self, bg=c["bg"])
        content.pack(fill="x", padx=sc(8), pady=sc(6))
        
        content.columnconfigure(0, weight=1, uniform="loc_col")
        content.columnconfigure(1, weight=1, uniform="loc_col")
        content.columnconfigure(2, weight=1, uniform="loc_col")
        
        # Row 0: Stored as, Building, Floor
        c0 = tk.Frame(content, bg=c["bg"])
        c0.grid(row=0, column=0, sticky="nsew", padx=sc(4), pady=(0, sc(6)))
        if field_defs.get("Stored as"):
            self._create_field_widget(c0, "Stored as", field_defs["Stored as"], is_horiz=True).pack(fill="x")
            
        c1 = tk.Frame(content, bg=c["bg"])
        c1.grid(row=0, column=1, sticky="nsew", padx=sc(4), pady=(0, sc(6)))
        if field_defs.get("Building"):
            self._create_field_widget(c1, "Building", field_defs["Building"], is_horiz=True).pack(fill="x")
            
        c2 = tk.Frame(content, bg=c["bg"])
        c2.grid(row=0, column=2, sticky="nsew", padx=sc(4), pady=(0, sc(6)))
        if field_defs.get("Floor"):
            self._create_field_widget(c2, "Floor", field_defs["Floor"], is_horiz=True).pack(fill="x")

        # Row 1: Cabinet, Extra, Loan status
        c3 = tk.Frame(content, bg=c["bg"])
        c3.grid(row=1, column=0, sticky="nsew", padx=sc(4))
        if field_defs.get("Cabinet"):
            self._create_field_widget(c3, "Cabinet", field_defs["Cabinet"], is_horiz=True).pack(fill="x")
            
        c4 = tk.Frame(content, bg=c["bg"])
        c4.grid(row=1, column=1, sticky="nsew", padx=sc(4))
        if field_defs.get("Extra"):
            self._create_field_widget(c4, "Extra", field_defs["Extra"], is_horiz=True).pack(fill="x")
            
        c5 = tk.Frame(content, bg=c["bg"])
        c5.grid(row=1, column=2, sticky="nsew", padx=sc(4))
        
        loan_lbl = tk.Label(
            c5, text="LOAN STATUS",
            font=("JetBrains Mono", sc(9), "bold"),
            bg=c["bg"], fg=c["text_muted"], anchor="w"
        )
        loan_lbl.pack(fill="x", pady=(0, sc(2)))
        
        loan_card = self._build_loan_status_card(c5, is_horiz=True)
        loan_card.pack(fill="x")

    # -------------------------------------------------------------------------
    # Data Accessors
    # -------------------------------------------------------------------------
    def get_data(self):
        data = {}
        for k, var in self.location_vars.items():
            data[k] = var.get()
        return data

    def set_data(self, data_dict):
        for k, v in data_dict.items():
            if k in self.location_vars:
                self.location_vars[k].set(str(v))


# -----------------------------------------------------------------------------
# Plug-and-Play Launcher Function
# -----------------------------------------------------------------------------
def create_location_panel(
    parent,
    mode="vertical",
    location_vars=None,
    config_ref=None,
    live_callbacks=None,
    dark_mode=False,
    **kwargs
):
    """
    Exposes a 1-line plug-and-play entry point for host applications.
    """
    return LocationPanel(
        parent,
        mode=mode,
        location_vars=location_vars,
        config_ref=config_ref,
        live_callbacks=live_callbacks,
        dark_mode=dark_mode,
        **kwargs
    )


# -----------------------------------------------------------------------------
# Standalone Test Harness
# -----------------------------------------------------------------------------
if __name__ == "__main__":
    root = tk.Tk()
    root.title("Location Panel - Standalone Test Harness")
    root.geometry("900x650")
    
    # Top Control Bar
    ctrl_bar = tk.Frame(root, bg="#eaeaea", pady=8, padx=12)
    ctrl_bar.pack(fill="x", side="top")
    
    mode_var = tk.StringVar(value="vertical")
    dark_var = tk.BooleanVar(value=False)
    
    tk.Label(ctrl_bar, text="LAYOUT MODE:", font=("JetBrains Mono", 10, "bold"), bg="#eaeaea").pack(side="left", padx=(0, 6))
    
    rb_vert = tk.Radiobutton(ctrl_bar, text="Vertical (Left)", variable=mode_var, value="vertical", bg="#eaeaea", cursor="hand2")
    rb_vert.pack(side="left", padx=4)
    
    rb_h1 = tk.Radiobutton(ctrl_bar, text="Middle (1-Row Default)", variable=mode_var, value="horizontal_1row", bg="#eaeaea", cursor="hand2")
    rb_h1.pack(side="left", padx=4)
    
    rb_h2 = tk.Radiobutton(ctrl_bar, text="Middle (2-Row Alternate)", variable=mode_var, value="horizontal_2row", bg="#eaeaea", cursor="hand2")
    rb_h2.pack(side="left", padx=4)
    
    chk_dark = tk.Checkbutton(ctrl_bar, text="Dark Mode", variable=dark_var, bg="#eaeaea", cursor="hand2")
    chk_dark.pack(side="right", padx=12)
    
    tk.Frame(root, bg="#d1d1d1", height=1).pack(fill="x")
    
    # Main content container
    panel_container = tk.Frame(root, bg="#fbfaf8")
    panel_container.pack(fill="both", expand=True, padx=12, pady=12)
    
    # Bottom Event Log Box
    log_frame = tk.LabelFrame(root, text="LIVE CALLBACK EVENT LOG", font=("JetBrains Mono", 9, "bold"), bg="#f2f5f1", padx=8, pady=6)
    log_frame.pack(fill="x", side="bottom", padx=12, pady=(0, 12))
    
    log_text = tk.Text(log_frame, height=5, font=("JetBrains Mono", 9), bg="#1e1e1e", fg="#00ff00")
    log_text.pack(fill="both", expand=True)
    
    def log_event(name, *args):
        msg = f"[{name.upper()}] {args}\n"
        log_text.insert("end", msg)
        log_text.see("end")
        
    callbacks = {
        "on_field_change": lambda f, v: log_event("on_field_change", f, v),
        "on_commit": lambda d: log_event("on_commit", d),
        "on_preset_applied": lambda p, d: log_event("on_preset_applied", p),
        "on_preset_saved": lambda p, d: log_event("on_preset_saved", p),
        "on_loan_toggle": lambda active: log_event("on_loan_toggle", active),
    }
    
    # Instantiate standalone panel
    loc_panel = create_location_panel(
        panel_container,
        mode="vertical",
        live_callbacks=callbacks,
        dark_mode=False
    )
    loc_panel.pack(fill="both", expand=True)
    
    def _on_mode_change(*_):
        loc_panel.set_layout_mode(mode_var.get())
        
    def _on_dark_change(*_):
        is_dark = dark_var.get()
        bg_col = "#181c19" if is_dark else "#fbfaf8"
        panel_container.configure(bg=bg_col)
        loc_panel.set_dark_mode(is_dark)
        
    mode_var.trace_add("write", _on_mode_change)
    dark_var.trace_add("write", _on_dark_change)
    
    root.mainloop()
