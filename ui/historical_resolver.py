import tkinter as tk
from tkinter import ttk
import tkinter.font as tkFont
from config import sc

FONT_UI = ("sans-serif", 10)
FONT_UI_BOLD = ("sans-serif", 10, "bold")
FONT_UI_LG = ("sans-serif", 12, "bold")
FONT_UI_XL = ("sans-serif", 16, "bold")
FONT_MONO = ("Consolas", 10)
FONT_MONO_SM = ("Consolas", 8)

_fonts_initialized = False
def init_fonts():
    global _fonts_initialized, FONT_UI, FONT_UI_BOLD, FONT_UI_LG, FONT_UI_XL, FONT_MONO, FONT_MONO_SM
    if _fonts_initialized: return
    families = tkFont.families()
    ui_family = "Hanken Grotesk" if "Hanken Grotesk" in families else "Helvetica" if "Helvetica" in families else "Segoe UI" if "Segoe UI" in families else "sans-serif"
    mono_family = "JetBrains Mono" if "JetBrains Mono" in families else "Consolas" if "Consolas" in families else "Courier New"
    
    FONT_UI = (ui_family, sc(10))
    FONT_UI_BOLD = (ui_family, sc(10), "bold")
    FONT_UI_LG = (ui_family, sc(12), "bold")
    FONT_UI_XL = (ui_family, sc(16), "bold")
    FONT_MONO = (mono_family, sc(10))
    FONT_MONO_SM = (mono_family, sc(8))
    _fonts_initialized = True

COLORS = {
    "bg": "#fbfaf8",
    "surface": "#ffffff",
    "surface_dim": "#e9ece5",
    "border": "#d1d1d1",
    "text": "#2c302e",
    "text_muted": "#444748",
    "primary": "#000000",
    "on_primary": "#ffffff",
    "error": "#c93a40",
    "on_error": "#ffffff",
    "warning": "#f59e0b",
    "on_warning": "#000000",
    "conflict": "#0284c7",
    "on_conflict": "#ffffff",
    "success": "#3a7d44",
    "on_success": "#ffffff",
}

class HistoricalConflictResolverWindow:
    def __init__(self, main_app, oid, suggestions):
        init_fonts()
        self.main_app = main_app
        self.oid = oid
        self.suggestions = suggestions
        
        self.win = tk.Toplevel(main_app.root)
        self.win.title("Historical Database Conflict Resolver")
        self.win.configure(bg=COLORS["bg"])
        
        import utils
        utils.center_and_fit_toplevel(self.win, sc(1100), sc(700))
        
        # State
        self.initial_suggestions = suggestions
        self.fields = list(suggestions.keys())
        self.field_frames = {}
        self.card_frames = {}
        self.res_vars = {}
        
        self.build_ui()
        
    def build_ui(self):
        # Header
        header = tk.Frame(self.win, bg=COLORS["surface"], height=sc(48))
        header.pack(fill="x", side="top")
        tk.Frame(header, bg=COLORS["border"], height=sc(1)).pack(fill="x", side="bottom")
        
        tk.Label(header, text="HISTORICAL_DATABASE_CONFLICT_RESOLVER", font=FONT_UI_LG, fg=COLORS["primary"], bg=COLORS["surface"]).pack(side="left", padx=sc(16), pady=sc(12))
        
        # Main content area
        main_area = tk.Frame(self.win, bg=COLORS["bg"])
        main_area.pack(fill="both", expand=True)
        
        # Left Sidebar (Field Directory)
        sidebar = tk.Frame(main_area, width=sc(280), bg=COLORS["surface_dim"])
        sidebar.pack(side="left", fill="y")
        sidebar.pack_propagate(False)
        tk.Frame(sidebar, bg=COLORS["border"], width=sc(1)).pack(side="right", fill="y")
        
        dir_header = tk.Frame(sidebar, bg=COLORS["border"], height=sc(40))
        dir_header.pack(fill="x")
        tk.Label(dir_header, text="FIELD_DIRECTORY", font=FONT_MONO_SM, fg=COLORS["text_muted"], bg=COLORS["border"]).pack(side="left", padx=sc(12), pady=sc(12))
        
        # Bottom toggle
        sidebar_bottom = tk.Frame(sidebar, bg=COLORS["border"], height=sc(48))
        sidebar_bottom.pack(side="bottom", fill="x")
        sidebar_bottom.pack_propagate(False)
        self.show_all_var = tk.BooleanVar(value=False)
        chk = tk.Checkbutton(sidebar_bottom, text="Show all fields", variable=self.show_all_var, 
                             font=FONT_UI_BOLD, bg=COLORS["surface"], fg=COLORS["primary"],
                             activebackground=COLORS["surface"], activeforeground=COLORS["primary"],
                             selectcolor=COLORS["surface"], relief="flat", bd=0,
                             command=self.reload_suggestions, cursor="hand2")
        chk.pack(fill="both", expand=True, padx=sc(1), pady=sc(1)) # 1px border visually
        
        self.dir_canvas = tk.Canvas(sidebar, bg=COLORS["surface_dim"], highlightthickness=0)
        dir_scrollbar = ttk.Scrollbar(sidebar, orient="vertical", command=self.dir_canvas.yview)
        self.dir_list = tk.Frame(self.dir_canvas, bg=COLORS["surface_dim"])
        
        self.dir_list.bind(
            "<Configure>",
            lambda e: self.dir_canvas.configure(scrollregion=self.dir_canvas.bbox("all")) if e.widget == self.dir_list else None
        )
        
        dir_canvas_window = self.dir_canvas.create_window((0, 0), window=self.dir_list, anchor="nw")
        self.dir_canvas.configure(yscrollcommand=dir_scrollbar.set)
        
        self.dir_canvas.bind("<Configure>", lambda e: self.dir_canvas.itemconfig(dir_canvas_window, width=e.width))
        
        self.dir_canvas.pack(side="left", fill="both", expand=True)
        dir_scrollbar.pack(side="right", fill="y")
        
        self.dir_canvas.bind("<MouseWheel>", self._on_dir_mousewheel)
        
        # Right Area (Scrollable Cards)
        right_area = tk.Frame(main_area, bg=COLORS["bg"])
        right_area.pack(side="left", fill="both", expand=True)
        
        # Context Header
        ctx_header = tk.Frame(right_area, bg=COLORS["surface"], height=sc(80))
        ctx_header.pack(fill="x")
        tk.Frame(ctx_header, bg=COLORS["border"], height=sc(1)).pack(side="bottom", fill="x")
        
        self.issue_count_label = tk.Label(ctx_header, text=f"RECORD REVIEW: {len(self.fields)} ISSUES", font=FONT_UI_XL, fg=COLORS["primary"], bg=COLORS["surface"])
        self.issue_count_label.pack(anchor="w", padx=sc(24), pady=(sc(16), sc(4)))
        tk.Label(ctx_header, text="Review and resolve outstanding conflicts and data problems in the fields below. Scroll to view all issues.", font=FONT_UI, fg=COLORS["text_muted"], bg=COLORS["surface"]).pack(anchor="w", padx=sc(24), pady=(0, sc(16)))
        
        # Scrollable Canvas for cards
        self.canvas = tk.Canvas(right_area, bg=COLORS["bg"], highlightthickness=0)
        scrollbar = ttk.Scrollbar(right_area, orient="vertical", command=self.canvas.yview)
        self.scrollable_frame = tk.Frame(self.canvas, bg=COLORS["bg"])
        
        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")) if e.widget == self.scrollable_frame else None
        )
        canvas_window = self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        self.canvas.bind("<Configure>", lambda e, cw=canvas_window: self.canvas.itemconfig(cw, width=e.width))
        
        self.canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        self.canvas.configure(yscrollcommand=scrollbar.set)
        
        # Bind mousewheel
        def _on_mousewheel(event):
            try:
                if self.canvas.winfo_exists():
                    self.canvas.yview_scroll(int(-1*(event.delta/120)), "units")
            except Exception:
                pass
        self.canvas.bind_all("<MouseWheel>", _on_mousewheel)
        
        self.populate_fields()
        
        # Footer
        footer = tk.Frame(self.win, bg=COLORS["surface_dim"], height=sc(48))
        footer.pack(fill="x", side="bottom")
        tk.Frame(footer, bg=COLORS["border"], height=sc(1)).pack(side="top", fill="x")
        
        self.stats_label = tk.Label(footer, text="", font=FONT_MONO, fg=COLORS["text_muted"], bg=COLORS["surface_dim"])
        self.stats_label.pack(side="left", padx=sc(24), pady=sc(12))
        
        btn_apply_all = tk.Button(footer, text="APPLY ALL RESOLVED (CTRL+A)", font=FONT_UI_BOLD, fg=COLORS["on_success"], bg=COLORS["success"], relief="flat", bd=0, padx=sc(16), pady=sc(8), command=self.apply_all)
        btn_apply_all.pack(side="right", padx=sc(16), pady=sc(6))
        
        # Cleanup routine
        def _cleanup(event=None):
            if event and event.widget != self.win:
                return
            try:
                self.canvas.unbind_all("<MouseWheel>")
            except Exception:
                pass
            try:
                self.dir_canvas.unbind_all("<MouseWheel>")
            except Exception:
                pass
 
        self.win.bind("<Destroy>", _cleanup)
 
        btn_close = tk.Button(footer, text="CLOSE", font=FONT_UI_BOLD, fg=COLORS["text"], bg=COLORS["surface"], relief="solid", bd=1, padx=sc(16), pady=sc(8), command=self.win.destroy)
        btn_close.pack(side="right", padx=sc(8), pady=sc(6))

        # Tutorial IDs
        sidebar.tutorial_id = "hr_sidebar"
        chk.tutorial_id = "hr_show_all"
        self.canvas.tutorial_id = "hr_cards"
        btn_apply_all.tutorial_id = "hr_apply_all"

        # Check and launch tutorial
        import config
        prefs = config.load_prefs()
        if "historical_resolver" not in prefs.get("completed_tutorials", []):
            from ui.tutorial import TutorialManager
            self.win.after(500, lambda: TutorialManager().start_tutorial("historical_resolver", self.win))
        
        self.win.bind("<Control-a>", lambda e: self.apply_all())
        self.update_stats()
        
    def reload_suggestions(self):
        show_all = self.show_all_var.get()
        if not show_all:
            self.suggestions = self.initial_suggestions
        else:
            new_suggestions = self.main_app.collect_historical_suggestions(self.oid, show_all_override=True)
            self.suggestions = new_suggestions
        self.fields = sorted(list(self.suggestions.keys()))
        self.populate_fields()
        self.issue_count_label.config(text=f"RECORD REVIEW: {len(self.fields)} ISSUES")
        self.update_stats()

    def populate_fields(self):
        # Clear existing
        for w in self.dir_list.winfo_children(): w.destroy()
        for w in self.scrollable_frame.winfo_children(): w.destroy()
        
        self.field_frames = {}
        self.card_frames = {}
        self.res_vars = {}
        
        for field in self.fields:
            self.create_directory_item(field)
            self.create_card(field)
            
        self.win.update_idletasks()
        try:
            self.dir_canvas.configure(scrollregion=self.dir_canvas.bbox("all"))
            self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        except Exception:
            pass
            
    def get_field_status(self, field):
        import pandas as pd
        # Check current value for unknown status
        current_val = ""
        if self.oid in self.main_app.reg_by_id.index:
            reg_dict = self.main_app._get_reg_dict() if hasattr(self.main_app, "_get_reg_dict") else {}
            reg = reg_dict.get(self.oid) or self.main_app.reg_by_id.loc[self.oid]
            if isinstance(reg, pd.DataFrame):
                reg = reg.iloc[0]
            current_val = str(reg.get(field, "")).strip()

        is_unknown = self.main_app.is_unknown(current_val)

        is_active_problem = any(
            self.main_app.problem_vars.get(pc) and self.main_app.problem_vars[pc].get()
            for pc, mf in self.main_app.problem_to_field.items() if mf == field
        )

        if is_active_problem:
            return "ERR", COLORS["error"], COLORS["on_error"]
        elif is_unknown:
            return "UKN", COLORS["warning"], COLORS["on_warning"]
        else:
            return "CFCT", COLORS["conflict"], COLORS["on_conflict"]
            
    def _on_dir_mousewheel(self, event):
        if hasattr(self, "dir_canvas") and self.dir_canvas.winfo_exists():
            self.dir_canvas.yview_scroll(int(-1*(event.delta/120)), "units")

    def create_directory_item(self, field):
        status_code, color, _ = self.get_field_status(field)
        
        item = tk.Frame(self.dir_list, bg=COLORS["surface"], cursor="hand2")
        item.pack(fill="x")
        tk.Frame(item, bg=COLORS["border"], height=sc(1)).pack(fill="x", side="bottom")
        
        # Indicator bar
        tk.Frame(item, bg=color, width=sc(4)).pack(side="left", fill="y")
        
        tk.Label(item, text=field.upper(), font=FONT_MONO, fg=color, bg=COLORS["surface"]).pack(side="left", padx=sc(12), pady=sc(12))
        tk.Label(item, text=status_code, font=FONT_MONO_SM, fg=color, bg=COLORS["surface"]).pack(side="right", padx=sc(12), pady=sc(12))
        
        def _scroll_to_card(event, f=field):
            if f in self.card_frames:
                # get y pos
                y = self.card_frames[f].winfo_y()
                self.canvas.yview_moveto(y / self.scrollable_frame.winfo_height())
                
        item.bind("<Button-1>", _scroll_to_card)
        item.bind("<MouseWheel>", self._on_dir_mousewheel)
        for child in item.winfo_children():
            child.bind("<Button-1>", _scroll_to_card)
            child.bind("<MouseWheel>", self._on_dir_mousewheel)
            
        self.field_frames[field] = item
        
    def create_card(self, field):
        status_code, bg_color, fg_color = self.get_field_status(field)
        
        card = tk.Frame(self.scrollable_frame, bg=COLORS["surface"], highlightbackground=bg_color, highlightthickness=1)
        card.pack(fill="x", padx=sc(24), pady=(sc(24), 0))
        
        # Header
        header = tk.Frame(card, bg=bg_color)
        header.pack(fill="x")
        tk.Label(header, text=f"FIELD: {field.upper()}", font=FONT_UI_BOLD, fg=fg_color, bg=bg_color).pack(side="left", padx=sc(16), pady=sc(10))
        tk.Label(header, text=status_code, font=FONT_MONO_SM, fg=fg_color, bg=bg_color).pack(side="right", padx=sc(16), pady=sc(10))
        
        content = tk.Frame(card, bg=COLORS["surface"])
        content.pack(fill="x", padx=sc(20), pady=sc(20))
        
        reg_dict = self.main_app._get_reg_dict() if hasattr(self.main_app, "_get_reg_dict") else {}
        reg_row = reg_dict.get(self.oid) or self.main_app.app.df_reg.loc[self.oid]
        current_val = str(reg_row.get(field, "")).strip()
        if current_val == "nan": current_val = ""
        
        # Current Value
        cv_frame = tk.Frame(content, bg=COLORS["surface"], highlightbackground=COLORS["border"], highlightthickness=1)
        cv_frame.pack(fill="x", pady=(sc(10), sc(16)))
        
        tk.Label(content, text="CURRENT_VALUE", font=FONT_MONO_SM, fg=COLORS["text_muted"], bg=COLORS["surface"]).place(x=sc(12), y=-sc(4)) # fake overlap
        
        disp_val = current_val if current_val else "[BLANK]"
        disp_color = COLORS["text"] if current_val else COLORS["text_muted"]
        tk.Label(cv_frame, text=disp_val, font=FONT_MONO, fg=disp_color, bg=COLORS["surface"]).pack(anchor="w", padx=sc(16), pady=sc(12))
        
        # Suggestions
        values_map = self.suggestions.get(field, {})
        unique_vals = [v for v in values_map if v != "(No data found)"]
        
        tk.Label(content, text="HISTORICAL_SUGGESTIONS", font=FONT_MONO_SM, fg=COLORS["text_muted"], bg=COLORS["surface"]).pack(anchor="w", pady=(0, sc(8)))
        
        import config
        prefs = config.load_prefs() or {}
        auto_resolve = prefs.get("auto_resolve_conflicts", False)
        if getattr(self.main_app, "auto_resolve_conflicts_var", None) is not None:
            auto_resolve = self.main_app.auto_resolve_conflicts_var.get()

        initial_val = current_val
        if auto_resolve and len(unique_vals) == 1 and (not current_val or current_val == "nan" or (hasattr(self.main_app, "is_unknown") and self.main_app.is_unknown(current_val)) or status_code in ("ERR", "UKN")):
            initial_val = unique_vals[0]

        res_var = tk.StringVar(value=initial_val)
        self.res_vars[field] = res_var
        
        if unique_vals:
            for val in unique_vals:
                sug_frame = tk.Frame(content, bg=COLORS["surface"], highlightbackground=COLORS["border"], highlightthickness=1, cursor="hand2")
                sug_frame.pack(fill="x", pady=(0, sc(8)))
                
                sources = values_map.get(val, set())
                src_str = f"[{', '.join(sorted(sources))}]" if sources else ""
                
                # We need it to be focusable for keyboard nav
                sug_btn = tk.Button(sug_frame, text=f"{val}\n{src_str}", font=FONT_MONO, justify="left", bg=COLORS["surface"], fg=COLORS["text"], relief="flat", bd=0, anchor="w")
                sug_btn.pack(fill="both", expand=True, padx=sc(8), pady=sc(8))
                
                def _populate(v=val, rv=res_var):
                    rv.set(v)
                    
                sug_btn.configure(command=_populate)
                sug_btn.bind("<Return>", lambda e, f=_populate: f())
                sug_btn.bind("<space>", lambda e, f=_populate: f())
        else:
            tk.Label(content, text="No suggestions found.", font=FONT_MONO, fg=COLORS["text_muted"], bg=COLORS["surface"]).pack(anchor="w", pady=(0, sc(16)))
            
        # Manual Entry
        tk.Frame(content, bg=COLORS["border"], height=sc(1)).pack(fill="x", pady=(sc(8), sc(16)))
        tk.Label(content, text="MANUAL_ENTRY", font=FONT_MONO_SM, fg=COLORS["text_muted"], bg=COLORS["surface"]).pack(anchor="w", pady=(0, sc(8)))
        
        entry_frame = tk.Frame(content, bg=COLORS["surface"])
        entry_frame.pack(fill="x")
        
        entry = tk.Entry(entry_frame, textvariable=res_var, font=FONT_MONO, bg=COLORS["surface"], fg=COLORS["text"], highlightbackground=COLORS["border"], highlightthickness=1, relief="flat")
        entry.pack(side="left", fill="x", expand=True, ipady=sc(4))
        
        def _apply(f=field, rv=res_var, cv=current_val, c=card, h=header):
            new_val = rv.get().strip()
            if new_val and new_val != cv:
                reg_changed_fields = [f]
                reg_changed_values = [f'{f}: "{cv}"  "{new_val}"']
                prob_changed_fields = []
                prob_changed_values = []
 
                self.main_app.app.df_reg.loc[self.oid, f] = new_val
                if f in self.main_app.reg_vars:
                    self.main_app.reg_vars[f].set(new_val)
                if hasattr(self.main_app, "reg_entries") and f in self.main_app.reg_entries:
                    w = self.main_app.reg_entries[f]
                    if isinstance(w, tk.Text):
                        w.delete("1.0", tk.END)
                        w.insert("1.0", str(new_val))
                if getattr(self.main_app, "_cached_reg_dict", None) is not None and self.oid in self.main_app._cached_reg_dict:
                    self.main_app._cached_reg_dict[self.oid][f] = new_val
 
                for pc, mf in self.main_app.problem_to_field.items():
                    if mf == f and pc in self.main_app.problem_vars:
                        old_prob = bool(self.main_app.app.df_obs.loc[self.oid].get(pc, False))
                        if old_prob:
                            prob_changed_fields.append(pc)
                            prob_changed_values.append(f'{pc}: "True"  "False"')
                        self.main_app.problem_vars[pc].set(False)
                        self.main_app.app.df_obs.loc[self.oid, pc] = False
                        if getattr(self.main_app, "_cached_obs_dict", None) is not None and self.oid in self.main_app._cached_obs_dict:
                            self.main_app._cached_obs_dict[self.oid][pc] = False
                        if hasattr(self.main_app, "loaded_problem_states"):
                            self.main_app.loaded_problem_states[pc] = False
                
                self.main_app._row_cache_dirty = True
                self.main_app.commit_current_object()
 
                self.main_app.log_action(
                    "RESOLVE_HISTORICAL_CONFLICT",
                    changed_fields=reg_changed_fields,
                    changed_values=reg_changed_values,
                    prob_fields=prob_changed_fields,
                    prob_values=prob_changed_values
                )
 
                self.main_app.update_dirty_ui()
                self.update_stats()
                
                # Visual feedback on card
                c.configure(highlightbackground=COLORS["success"])
                for w in h.winfo_children():
                    w.configure(bg=COLORS["success"])
                h.configure(bg=COLORS["success"])
                
        btn_apply = tk.Button(entry_frame, text="APPLY", font=FONT_UI_BOLD, fg=COLORS["on_primary"], bg=COLORS["primary"], relief="flat", bd=0, padx=sc(16), command=_apply)
        btn_apply.pack(side="right", padx=(sc(8), 0))
        
        entry.bind("<Return>", lambda e, f=_apply: f())
        
        self.card_frames[field] = card
        
        # Auto-scroll when tabbing
        def _on_focus(event):
            y = card.winfo_y()
            if self.scrollable_frame.winfo_height() > 0:
                self.canvas.yview_moveto(y / self.scrollable_frame.winfo_height())
                
        for widget in [entry, btn_apply]:
            widget.bind("<FocusIn>", _on_focus, add="+")
            
        if unique_vals:
            for child in content.winfo_children():
                for subchild in child.winfo_children():
                    if isinstance(subchild, tk.Button):
                        subchild.bind("<FocusIn>", _on_focus, add="+")

    def update_stats(self):
        err = 0
        cfct = 0
        resolved = 0
        
        for field in self.fields:
            status_code, _, _ = self.get_field_status(field)
            if status_code == "ERR": err += 1
            elif status_code == "CFCT": cfct += 1
            else: resolved += 1
            
            # If resolved, update dir list
            if status_code not in ("ERR", "CFCT") and field in self.field_frames:
                f_frame = self.field_frames[field]
                f_frame.winfo_children()[1].configure(bg=COLORS["success"])
                f_frame.winfo_children()[2].configure(fg=COLORS["success"])
                f_frame.winfo_children()[3].configure(text="OK", fg=COLORS["success"])
                
        self.stats_label.configure(text=f"RESOLVED: {resolved}/{len(self.fields)}    ERR: {err}    CFCT: {cfct}")
        
    def apply_all(self):
        reg_changed_fields = []
        reg_changed_values = []
        prob_changed_fields = []
        prob_changed_values = []

        reg_updates = {}
        prob_updates = {}

        # Fetch outside the loop if it doesn't change per field in a way that matters for get
        reg_dict = self.main_app._get_reg_dict() if hasattr(self.main_app, "_get_reg_dict") else {}
        reg_row = reg_dict.get(self.oid) or self.main_app.app.df_reg.loc[self.oid]

        # We simulate clicking apply on all fields that have a value different from current
        for field in self.fields:
            current_val = str(reg_row.get(field, "")).strip()
            if current_val == "nan": current_val = ""
            
            new_val = self.res_vars[field].get().strip()
            if new_val and new_val != current_val:
                reg_updates[field] = new_val

                if field in self.main_app.reg_vars:
                    self.main_app.reg_vars[field].set(new_val)
                if hasattr(self.main_app, "reg_entries") and field in self.main_app.reg_entries:
                    w = self.main_app.reg_entries[field]
                    if isinstance(w, tk.Text):
                        w.delete("1.0", tk.END)
                        w.insert("1.0", str(new_val))
                if getattr(self.main_app, "_cached_reg_dict", None) is not None and self.oid in self.main_app._cached_reg_dict:
                    self.main_app._cached_reg_dict[self.oid][field] = new_val
                
                reg_changed_fields.append(field)
                reg_changed_values.append(f'{field}: "{current_val}"  "{new_val}"')
                    
                for pc, mf in self.main_app.problem_to_field.items():
                    if mf == field and pc in self.main_app.problem_vars:
                        old_prob = bool(self.main_app.app.df_obs.loc[self.oid].get(pc, False))
                        if old_prob:
                            prob_changed_fields.append(pc)
                            prob_changed_values.append(f'{pc}: "True"  "False"')
                        self.main_app.problem_vars[pc].set(False)
                        prob_updates[pc] = False
                        if getattr(self.main_app, "_cached_obs_dict", None) is not None and self.oid in self.main_app._cached_obs_dict:
                            self.main_app._cached_obs_dict[self.oid][pc] = False
                        if hasattr(self.main_app, "loaded_problem_states"):
                            self.main_app.loaded_problem_states[pc] = False

                # Update card visually
                if field in self.card_frames:
                    card = self.card_frames[field]
                    card.configure(highlightbackground=COLORS["success"])
                    header = card.winfo_children()[0]
                    header.configure(bg=COLORS["success"])
                    for w in header.winfo_children():
                        w.configure(bg=COLORS["success"])
                        
        if reg_updates:
            keys = list(reg_updates.keys())
            values = list(reg_updates.values())
            if len(keys) == 1:
                self.main_app.app.df_reg.loc[self.oid, keys[0]] = values[0]
            else:
                self.main_app.app.df_reg.loc[self.oid, keys] = values
        if prob_updates:
            keys = list(prob_updates.keys())
            values = list(prob_updates.values())
            if len(keys) == 1:
                self.main_app.app.df_obs.loc[self.oid, keys[0]] = values[0]
            else:
                self.main_app.app.df_obs.loc[self.oid, keys] = values

        if reg_changed_fields or prob_changed_fields:
            self.main_app._row_cache_dirty = True
            self.main_app.commit_current_object()

            self.main_app.log_action(
                "RESOLVE_HISTORICAL_CONFLICT",
                changed_fields=reg_changed_fields,
                changed_values=reg_changed_values,
                prob_fields=prob_changed_fields,
                prob_values=prob_changed_values
            )

        self.main_app.update_dirty_ui()
        self.update_stats()
        self.win.destroy()

        if getattr(self.main_app, "auto_advance_history_var", None) and self.main_app.auto_advance_history_var.get():
            if hasattr(self.main_app, "goto_next_problem_with_history"):
                self.main_app.goto_next_problem_with_history()
