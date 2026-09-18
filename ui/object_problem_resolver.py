import tkinter as tk
from tkinter import ttk
import tkinter.font as tkFont
import pandas as pd
from ui.state import app_bus, DATABASE_UPDATED
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
    "gbif_bg": "#f0fdf4",
    "gbif_border": "#3a7d44",
    "gbif_text": "#2b8a3e",
}

class ObjectProblemResolver:
    def __init__(self, main_app, oid_or_list, suggestions=None):
        init_fonts()
        self.main_app = main_app
        
        if isinstance(oid_or_list, (list, tuple)):
            self._oid_queue = [str(x) for x in oid_or_list]
            self._queue_idx = 0
            self.oid = str(self._oid_queue[0]) if self._oid_queue else ""
        else:
            self._oid_queue = None
            self._queue_idx = 0
            self.oid = str(oid_or_list) if oid_or_list is not None else ""
        
        parent_root = getattr(main_app, "root", main_app)
        self.win = tk.Toplevel(parent_root)
        self.win.title("Problem Resolution" if not self._is_queue_mode else f"Problem Resolution (Queue: {len(self._oid_queue)} Objects)")
        self.win.configure(bg=COLORS["bg"])
        if isinstance(parent_root, (tk.Tk, tk.Toplevel)):
            try:
                self.win.transient(parent_root)
            except Exception:
                pass
        
        import utils
        utils.center_and_fit_toplevel(self.win, sc(1100), sc(700))
        
        # State
        self._taxonomy_fields = self._get_taxonomy_fields()
        self._gbif_result = None
        self._gbif_frames = {}
        self.field_frames = {}
        self.card_frames = {}
        self.res_vars = {}
        
        if suggestions is not None:
            self.initial_suggestions = suggestions
            self.suggestions = suggestions
        else:
            if hasattr(self.main_app, "collect_historical_suggestions"):
                self.suggestions = self.main_app.collect_historical_suggestions(self.oid, show_all_override=False)
            else:
                self.suggestions = {}
            self.initial_suggestions = self.suggestions
            
        self.fields = self._get_sorted_fields(self.suggestions.keys())
        
        self.build_ui()
        self.reload_suggestions()
        self._start_gbif_lookup()

    @property
    def _is_queue_mode(self) -> bool:
        return self._oid_queue is not None and len(self._oid_queue) > 1

    def _get_taxonomy_fields(self) -> set:
        """
        Returns the set of field names whose mapped problem has category='taxonomy'
        in the DATABASE_CONFIGS problems list.
        """
        import config
        taxonomy_fields = set()
        app_obj = getattr(self.main_app, 'app', self.main_app)
        db_key = getattr(app_obj, 'current_db_key', 'Økonomisk Botanisk')
        db_config = getattr(app_obj, 'config', None) or config.DATABASE_CONFIGS.get(db_key, {})
        probs_list = db_config.get('problems', []) or db_config.get('ui_sections', {}).get('problems', [])
        for prob in probs_list:
            if prob.get('category') == 'taxonomy' and 'maps_to' in prob:
                taxonomy_fields.add(prob['maps_to'])
        if not taxonomy_fields:
            taxonomy_fields = {"Genus", "Species", "Family", "Author", "Higher Classification"}
        return taxonomy_fields

    def _start_gbif_lookup(self):
        """Triggers one background GBIF check for the current object."""
        app_state = getattr(self.main_app, 'app', None)
        if not app_state or getattr(app_state, 'df_reg', None) is None:
            self._gbif_result = None
            self._update_gbif_views()
            return

        oid = self.oid
        reg = app_state.df_reg
        genus = ""
        species = ""
        try:
            target_idx = None
            if oid in reg.index:
                target_idx = oid
            elif str(oid).isdigit() and int(oid) in reg.index:
                target_idx = int(oid)

            if target_idx is not None:
                genus = str(reg.at[target_idx, 'Genus']).strip() if 'Genus' in reg.columns else ''
                species = str(reg.at[target_idx, 'Species']).strip() if 'Species' in reg.columns else ''
        except Exception:
            self._gbif_result = None
            self._update_gbif_views()
            return

        if not genus or genus.lower() in ('nan', '', 'none', '?'):
            self._gbif_result = None
            self._update_gbif_views()
            return

        self._gbif_result = 'loading'
        self._update_gbif_views()

        from backend.gbif import check_gbif
        from backend.task_queue import app_worker

        def _fetch():
            return check_gbif(genus, species)

        def _done(result):
            self._gbif_result = result
            self._on_gbif_result(result)

        def _err(exc):
            self._gbif_result = {'error': str(exc)}
            self._on_gbif_result(self._gbif_result)

        app_worker.run_in_background(_fetch, callback=_done, error_callback=_err)

    def _on_gbif_result(self, result):
        try:
            if not hasattr(self, "win") or not self.win.winfo_exists():
                return
        except Exception:
            return
        self._update_gbif_views()

    def _update_gbif_views(self):
        for field, frame in list(self._gbif_frames.items()):
            try:
                if frame.winfo_exists():
                    self._render_gbif_frame(field, frame)
            except Exception:
                pass

    def _render_gbif_frame(self, field: str, frame: tk.Frame):
        for w in frame.winfo_children():
            w.destroy()

        if field not in self._taxonomy_fields:
            return

        tk.Label(frame, text="GBIF_BACKBONE", font=FONT_MONO_SM, fg=COLORS["text_muted"], bg=COLORS["surface"]).pack(anchor="w", pady=(0, sc(4)))

        if self._gbif_result == 'loading':
            loading_box = tk.Frame(frame, bg=COLORS["surface_dim"], highlightbackground=COLORS["border"], highlightthickness=1)
            loading_box.pack(fill="x", pady=(0, sc(12)))
            tk.Label(loading_box, text="Loading GBIF backbone data… ◌", font=FONT_MONO_SM, fg=COLORS["text_muted"], bg=COLORS["surface_dim"], padx=sc(10), pady=sc(6)).pack(anchor="w")
            return

        if not self._gbif_result:
            box = tk.Frame(frame, bg=COLORS["surface_dim"], highlightbackground=COLORS["border"], highlightthickness=1)
            box.pack(fill="x", pady=(0, sc(12)))
            tk.Label(box, text="No GBIF match found for this taxon.", font=FONT_MONO_SM, fg=COLORS["text_muted"], bg=COLORS["surface_dim"], padx=sc(10), pady=sc(6)).pack(anchor="w")
            return

        if isinstance(self._gbif_result, dict) and "error" in self._gbif_result:
            box = tk.Frame(frame, bg=COLORS["surface_dim"], highlightbackground=COLORS["border"], highlightthickness=1)
            box.pack(fill="x", pady=(0, sc(12)))
            tk.Label(box, text="GBIF unavailable — showing historical sources only.", font=FONT_MONO_SM, fg=COLORS["text_muted"], bg=COLORS["surface_dim"], padx=sc(10), pady=sc(6)).pack(anchor="w")
            return

        match_type = self._gbif_result.get("matchType")
        if match_type == "NONE" or not self._gbif_result.get("scientificName"):
            box = tk.Frame(frame, bg=COLORS["surface_dim"], highlightbackground=COLORS["border"], highlightthickness=1)
            box.pack(fill="x", pady=(0, sc(12)))
            tk.Label(box, text="No GBIF match found for this taxon.", font=FONT_MONO_SM, fg=COLORS["text_muted"], bg=COLORS["surface_dim"], padx=sc(10), pady=sc(6)).pack(anchor="w")
            return

        # Extract proposed value for this specific field
        field_lower = field.lower().replace("_", " ").strip()
        gbif_val = ""
        if field_lower == "genus":
            gbif_val = self._gbif_result.get("genus", "")
        elif field_lower == "species":
            gbif_val = self._gbif_result.get("species", "")
        elif field_lower == "author":
            gbif_val = self._gbif_result.get("author", "")
        elif field_lower == "family":
            gbif_val = self._gbif_result.get("family", "")
        elif "higher" in field_lower or "classification" in field_lower:
            gbif_val = self._gbif_result.get("higherClassification", "")

        gbif_val = str(gbif_val or "").strip()
        if not gbif_val:
            box = tk.Frame(frame, bg=COLORS["surface_dim"], highlightbackground=COLORS["border"], highlightthickness=1)
            box.pack(fill="x", pady=(0, sc(12)))
            tk.Label(box, text="No GBIF proposal for this field.", font=FONT_MONO_SM, fg=COLORS["text_muted"], bg=COLORS["surface_dim"], padx=sc(10), pady=sc(6)).pack(anchor="w")
            return

        # Check for Historical Book Corroboration
        app_state = getattr(self.main_app, "app", None) or getattr(self.main_app, "app_state", None)
        from backend.cross_validation import find_book_matches_for_gbif
        matching_books = []
        try:
            matching_books = find_book_matches_for_gbif(app_state, self.oid, field, gbif_val)
        except Exception:
            pass

        sug_box = tk.Frame(frame, bg=COLORS["gbif_bg"], highlightbackground=COLORS["gbif_border"], highlightthickness=1, cursor="hand2")
        sug_box.pack(fill="x", pady=(0, sc(12)))

        res_var = self.res_vars.get(field)
        def _populate(v=gbif_val, rv=res_var):
            if rv:
                rv.set(v)

        chip_btn = tk.Button(
            sug_box,
            text=f"🧬 {gbif_val}",
            font=FONT_MONO,
            justify="left",
            bg=COLORS["gbif_bg"],
            fg=COLORS["gbif_text"],
            relief="flat",
            bd=0,
            anchor="w",
            cursor="hand2",
            command=_populate
        )
        chip_btn.pack(side="left", fill="both", expand=True, padx=sc(8), pady=sc(8))
        chip_btn.bind("<Return>", lambda e, f=_populate: f())
        chip_btn.bind("<space>", lambda e, f=_populate: f())

        if matching_books:
            bk_names = ", ".join(b.replace("Books: ", "") for b in matching_books)
            corrob_text = f"✓ Corroborated by {len(matching_books)} books: {bk_names}"
            corrob_lbl = tk.Label(sug_box, text=corrob_text, font=FONT_MONO_SM, fg="#ffffff", bg=COLORS["success"], padx=sc(6), pady=sc(2))
            corrob_lbl.pack(side="right", padx=sc(8), pady=sc(8))
        else:
            tag_lbl = tk.Label(sug_box, text="[GBIF Backbone Match]", font=FONT_MONO_SM, fg=COLORS["gbif_text"], bg=COLORS["gbif_bg"], padx=sc(8))
            tag_lbl.pack(side="right", padx=sc(8), pady=sc(8))

    def build_ui(self):
        # Header
        header = tk.Frame(self.win, bg=COLORS["surface"], height=sc(48))
        header.pack(fill="x", side="top")
        tk.Frame(header, bg=COLORS["border"], height=sc(1)).pack(fill="x", side="bottom")
        
        self.header_title_label = tk.Label(header, text="PROBLEM_RESOLUTION", font=FONT_UI_LG, fg=COLORS["primary"], bg=COLORS["surface"])
        self.header_title_label.pack(side="left", padx=sc(16), pady=sc(12))

        # Queue Navigation Bar (if in queue mode)
        if self._is_queue_mode:
            self._build_queue_nav_bar()
        
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
        sidebar_bottom = tk.Frame(sidebar, bg=COLORS["border"], height=sc(80))
        sidebar_bottom.pack(side="bottom", fill="x")
        sidebar_bottom.pack_propagate(False)

        self.show_all_var = tk.BooleanVar(value=False)
        chk = tk.Checkbutton(sidebar_bottom, text="Show all fields", variable=self.show_all_var, 
                             font=FONT_UI_BOLD, bg=COLORS["surface"], fg=COLORS["primary"],
                             activebackground=COLORS["surface"], activeforeground=COLORS["primary"],
                             selectcolor=COLORS["surface"], relief="flat", bd=0,
                             command=self.reload_suggestions, cursor="hand2")
        chk.pack(fill="x", expand=False, padx=sc(1), pady=(sc(1), 0))

        self.sort_alpha_var = tk.BooleanVar(value=False)
        sort_chk = tk.Checkbutton(sidebar_bottom, text="Sort alphabetically", variable=self.sort_alpha_var,
                             font=FONT_UI_BOLD, bg=COLORS["surface"], fg=COLORS["primary"],
                             activebackground=COLORS["surface"], activeforeground=COLORS["primary"],
                             selectcolor=COLORS["surface"], relief="flat", bd=0,
                             command=self.reload_suggestions, cursor="hand2")
        sort_chk.pack(fill="x", expand=False, padx=sc(1), pady=(sc(1), sc(1)))

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
        tk.Label(ctx_header, text="Review and resolve outstanding taxonomy and provenance problems in the fields below.", font=FONT_UI, fg=COLORS["text_muted"], bg=COLORS["surface"]).pack(anchor="w", padx=sc(24), pady=(0, sc(16)))
        
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
        
        btn_apply_all = tk.Button(footer, text="APPLY ALL RESOLVED (CTRL+A)", font=FONT_UI_BOLD, fg=COLORS["on_success"], bg=COLORS["success"], relief="flat", bd=0, padx=sc(16), pady=sc(8), command=self.apply_all, cursor="hand2")
        btn_apply_all.pack(side="right", padx=sc(16), pady=sc(6))
        
        if self._is_queue_mode:
            btn_skip = tk.Button(footer, text="SKIP OBJECT →", font=FONT_UI_BOLD, fg=COLORS["text"], bg=COLORS["surface"], relief="solid", bd=1, padx=sc(14), pady=sc(8), command=lambda: self._queue_navigate(1), cursor="hand2")
            btn_skip.pack(side="right", padx=sc(8), pady=sc(6))
            close_text = "CLOSE QUEUE"
        else:
            close_text = "CLOSE"

        btn_close = tk.Button(footer, text=close_text, font=FONT_UI_BOLD, fg=COLORS["text"], bg=COLORS["surface"], relief="solid", bd=1, padx=sc(16), pady=sc(8), command=self.win.destroy, cursor="hand2")
        btn_close.pack(side="right", padx=sc(8), pady=sc(6))

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

    def _build_queue_nav_bar(self):
        nav_bar = tk.Frame(self.win, bg=COLORS["surface_dim"], height=sc(36))
        nav_bar.pack(fill="x", side="top")
        tk.Frame(nav_bar, bg=COLORS["border"], height=sc(1)).pack(fill="x", side="bottom")

        self._prev_btn = tk.Button(
            nav_bar, text="← Prev", font=FONT_UI_BOLD,
            bg=COLORS["surface"], fg=COLORS["text"], relief="solid", bd=1,
            padx=sc(10), pady=sc(2), cursor="hand2",
            command=lambda: self._queue_navigate(-1),
            state="disabled" if self._queue_idx <= 0 else "normal"
        )
        self._prev_btn.pack(side="left", padx=(sc(16), sc(8)), pady=sc(4))

        self._queue_label = tk.Label(
            nav_bar,
            text=f"Object {self._queue_idx + 1} of {len(self._oid_queue)} with active problems (OID: {self.oid})",
            font=FONT_MONO,
            fg=COLORS["text"],
            bg=COLORS["surface_dim"]
        )
        self._queue_label.pack(side="left", padx=sc(8), pady=sc(4))

        self._next_btn = tk.Button(
            nav_bar,
            text="Next →" if self._queue_idx < len(self._oid_queue) - 1 else "Done — Close",
            font=FONT_UI_BOLD,
            bg=COLORS["surface"], fg=COLORS["text"], relief="solid", bd=1,
            padx=sc(10), pady=sc(2), cursor="hand2",
            command=lambda: self._queue_navigate(1)
        )
        self._next_btn.pack(side="left", padx=sc(8), pady=sc(4))

    def _queue_navigate(self, delta: int):
        new_idx = self._queue_idx + delta
        if new_idx < 0 or new_idx >= len(self._oid_queue):
            if new_idx >= len(self._oid_queue):
                self.win.destroy()
            return

        self._queue_idx = new_idx
        self.oid = str(self._oid_queue[new_idx])

        if hasattr(self.main_app, "load_object"):
            try:
                self.main_app.load_object(self.oid)
            except Exception:
                pass

        try:
            if self.win.winfo_exists():
                self.win.lift()
                self.win.focus_force()
        except Exception:
            pass

        if hasattr(self.main_app, "collect_historical_suggestions"):
            self.initial_suggestions = self.main_app.collect_historical_suggestions(
                self.oid, show_all_override=self.show_all_var.get()
            )
        else:
            self.initial_suggestions = {}

        self.suggestions = self.initial_suggestions
        self.fields = self._get_sorted_fields(self.suggestions.keys())

        self._gbif_result = None
        self._gbif_frames = {}

        self.populate_fields()
        self.issue_count_label.config(text=f"RECORD REVIEW: {len(self.fields)} ISSUES")
        self.update_stats()

        if hasattr(self, "_queue_label") and self._queue_label.winfo_exists():
            self._queue_label.config(text=f"Object {self._queue_idx + 1} of {len(self._oid_queue)} with active problems (OID: {self.oid})")
        if hasattr(self, "_prev_btn") and self._prev_btn.winfo_exists():
            self._prev_btn.config(state="normal" if self._queue_idx > 0 else "disabled")
        if hasattr(self, "_next_btn") and self._next_btn.winfo_exists():
            self._next_btn.config(text="Next →" if self._queue_idx < len(self._oid_queue) - 1 else "Done — Close")

        try:
            if self.win.winfo_exists():
                self.win.lift()
                self.win.focus_force()
                self.win.after_idle(lambda: self.win.winfo_exists() and (self.win.lift(), self.win.focus_force()))
        except Exception:
            pass

        self._start_gbif_lookup()

    def _get_sorted_fields(self, field_names):
        if hasattr(self, 'sort_alpha_var') and self.sort_alpha_var.get():
            return sorted(list(field_names))

        reg_cols = []
        if hasattr(self.main_app, 'app') and hasattr(self.main_app.app, 'df_reg') and self.main_app.app.df_reg is not None:
            reg_cols = list(self.main_app.app.df_reg.columns)
        elif hasattr(self.main_app, 'reg_by_id') and self.main_app.reg_by_id is not None:
            if hasattr(self.main_app.reg_by_id, 'columns'):
                reg_cols = list(self.main_app.reg_by_id.columns)
            elif isinstance(self.main_app.reg_by_id, dict) and self.main_app.reg_by_id:
                first_row = next(iter(self.main_app.reg_by_id.values()))
                reg_cols = list(first_row.keys())

        col_order = {col: i for i, col in enumerate(reg_cols)}
        return sorted(list(field_names), key=lambda x: (col_order.get(x, float('inf')), x))

    def reload_suggestions(self):
        show_all = self.show_all_var.get()
        if not show_all:
            self.suggestions = self.initial_suggestions
        else:
            if hasattr(self.main_app, "collect_historical_suggestions"):
                new_suggestions = self.main_app.collect_historical_suggestions(self.oid, show_all_override=True)
            else:
                new_suggestions = self.initial_suggestions
            self.suggestions = new_suggestions
        self.fields = self._get_sorted_fields(self.suggestions.keys())
        self.populate_fields()
        self.issue_count_label.config(text=f"RECORD REVIEW: {len(self.fields)} ISSUES")
        self.update_stats()
        self._update_gbif_views()

    def populate_fields(self):
        for w in self.dir_list.winfo_children(): w.destroy()
        for w in self.scrollable_frame.winfo_children(): w.destroy()
        
        self.field_frames = {}
        self.card_frames = {}
        self.res_vars = {}
        self._gbif_frames = {}
        
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
        current_val = ""
        reg_dict = self.main_app._get_reg_dict() if hasattr(self.main_app, "_get_reg_dict") else {}
        reg = reg_dict.get(self.oid)
        if reg is None and hasattr(self.main_app, "reg_by_id") and self.main_app.reg_by_id is not None:
            if hasattr(self.main_app.reg_by_id, "index") and self.oid in self.main_app.reg_by_id.index:
                reg = self.main_app.reg_by_id.loc[self.oid]
        if isinstance(reg, pd.DataFrame):
            reg = reg.iloc[0]
        if reg is not None:
            current_val = str(reg.get(field, "")).strip()

        is_unknown = self.main_app.is_unknown(current_val) if hasattr(self.main_app, "is_unknown") else False

        is_active_problem = any(
            self.main_app.problem_vars.get(pc) and self.main_app.problem_vars[pc].get()
            for pc, mf in getattr(self.main_app, "problem_to_field", {}).items() if mf == field
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
        
        tk.Frame(item, bg=color, width=sc(4)).pack(side="left", fill="y")
        
        tk.Label(item, text=field.upper(), font=FONT_MONO, fg=color, bg=COLORS["surface"]).pack(side="left", padx=sc(12), pady=sc(12))
        tk.Label(item, text=status_code, font=FONT_MONO_SM, fg=color, bg=COLORS["surface"]).pack(side="right", padx=sc(12), pady=sc(12))
        
        def _scroll_to_card(event, f=field):
            if f in self.card_frames:
                y = self.card_frames[f].winfo_y()
                if self.scrollable_frame.winfo_height() > 0:
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
        
        header = tk.Frame(card, bg=bg_color)
        header.pack(fill="x")
        tk.Label(header, text=f"FIELD: {field.upper()}", font=FONT_UI_BOLD, fg=fg_color, bg=bg_color).pack(side="left", padx=sc(16), pady=sc(10))
        tk.Label(header, text=status_code, font=FONT_MONO_SM, fg=fg_color, bg=bg_color).pack(side="right", padx=sc(16), pady=sc(10))
        
        content = tk.Frame(card, bg=COLORS["surface"])
        content.pack(fill="x", padx=sc(20), pady=sc(20))
        
        reg_dict = self.main_app._get_reg_dict() if hasattr(self.main_app, "_get_reg_dict") else {}
        reg_row = reg_dict.get(self.oid)
        if reg_row is None and hasattr(self.main_app, "app") and getattr(self.main_app.app, "df_reg", None) is not None:
            if self.oid in self.main_app.app.df_reg.index:
                reg_row = self.main_app.app.df_reg.loc[self.oid]
            elif str(self.oid).isdigit() and int(self.oid) in self.main_app.app.df_reg.index:
                reg_row = self.main_app.app.df_reg.loc[int(self.oid)]
        if reg_row is None and hasattr(self.main_app, "reg_by_id") and self.main_app.reg_by_id is not None:
            if hasattr(self.main_app.reg_by_id, "index") and self.oid in self.main_app.reg_by_id.index:
                reg_row = self.main_app.reg_by_id.loc[self.oid]
        if isinstance(reg_row, pd.DataFrame):
            reg_row = reg_row.iloc[0]

        current_val = str(reg_row.get(field, "") if reg_row is not None else "").strip()
        if current_val == "nan": current_val = ""
        
        # 1. Current Value Block
        cv_frame = tk.Frame(content, bg=COLORS["surface"], highlightbackground=COLORS["border"], highlightthickness=1)
        cv_frame.pack(fill="x", pady=(sc(10), sc(16)))
        
        tk.Label(content, text="CURRENT_VALUE", font=FONT_MONO_SM, fg=COLORS["text_muted"], bg=COLORS["surface"]).place(x=sc(12), y=-sc(4))
        
        disp_val = current_val if current_val else "[BLANK]"
        disp_color = COLORS["text"] if current_val else COLORS["text_muted"]
        tk.Label(cv_frame, text=disp_val, font=FONT_MONO, fg=disp_color, bg=COLORS["surface"]).pack(anchor="w", padx=sc(16), pady=sc(12))
        
        # 2. GBIF Backbone Section (Only for taxonomy fields)
        is_taxonomy = field in self._taxonomy_fields
        if is_taxonomy:
            gbif_frame = tk.Frame(content, bg=COLORS["surface"])
            gbif_frame.pack(fill="x", pady=(0, sc(8)))
            self._gbif_frames[field] = gbif_frame
            self._render_gbif_frame(field, gbif_frame)

        # 3. Historical Suggestions Block
        values_map = self.suggestions.get(field, {})
        unique_vals = [v for v in values_map if v != "(No data found)"]
        
        tk.Label(content, text="HISTORICAL_SUGGESTIONS", font=FONT_MONO_SM, fg=COLORS["text_muted"], bg=COLORS["surface"]).pack(anchor="w", pady=(0, sc(8)))
        
        import config
        prefs = config.load_prefs() or {}
        auto_resolve = prefs.get("auto_resolve_conflicts", False)
        if getattr(self.main_app, "auto_resolve_conflicts_var", None) is not None:
            auto_resolve = self.main_app.auto_resolve_conflicts_var.get()

        # Provenance field safety: blank entry by default on load, no auto-resolve
        if is_taxonomy:
            initial_val = current_val
            if auto_resolve and len(unique_vals) == 1 and (not current_val or current_val == "nan" or (hasattr(self.main_app, "is_unknown") and self.main_app.is_unknown(current_val)) or status_code in ("ERR", "UKN")):
                initial_val = unique_vals[0]
        else:
            initial_val = ""

        res_var = tk.StringVar(value=initial_val)
        self.res_vars[field] = res_var
        
        if unique_vals:
            for val in unique_vals:
                sug_frame = tk.Frame(content, bg=COLORS["surface"], highlightbackground=COLORS["border"], highlightthickness=1, cursor="hand2")
                sug_frame.pack(fill="x", pady=(0, sc(8)))
                
                sources = list(values_map.get(val, set()))
                src_str = f"[{', '.join(sorted(sources))}]" if sources else ""
                
                sug_btn = tk.Button(sug_frame, text=f"{val}\n{src_str}", font=FONT_MONO, justify="left", bg=COLORS["surface"], fg=COLORS["text"], relief="flat", bd=0, anchor="w", cursor="hand2")
                sug_btn.pack(fill="both", expand=True, padx=sc(8), pady=sc(8))
                
                def _populate_hist(v=val, rv=res_var):
                    rv.set(v)
                    
                sug_btn.configure(command=_populate_hist)
                sug_btn.bind("<Return>", lambda e, f=_populate_hist: f())
                sug_btn.bind("<space>", lambda e, f=_populate_hist: f())
        else:
            tk.Label(content, text="No historical suggestions found.", font=FONT_MONO, fg=COLORS["text_muted"], bg=COLORS["surface"]).pack(anchor="w", pady=(0, sc(16)))
            
        # 4. Manual Entry Block
        tk.Frame(content, bg=COLORS["border"], height=sc(1)).pack(fill="x", pady=(sc(8), sc(16)))
        tk.Label(content, text="MANUAL_ENTRY", font=FONT_MONO_SM, fg=COLORS["text_muted"], bg=COLORS["surface"]).pack(anchor="w", pady=(0, sc(8)))
        
        entry_frame = tk.Frame(content, bg=COLORS["surface"])
        entry_frame.pack(fill="x")
        
        entry = tk.Entry(entry_frame, textvariable=res_var, font=FONT_MONO, bg=COLORS["surface"], fg=COLORS["text"], highlightbackground=COLORS["border"], highlightthickness=1, relief="flat")
        entry.pack(side="left", fill="x", expand=True, ipady=sc(4))
        
        def _apply(f=field, rv=res_var, cv=current_val, c=card, h=header):
            new_val = rv.get().strip()
            if new_val and new_val != cv:
                if hasattr(self.main_app, "push_undo_state"):
                    try:
                        self.main_app.push_undo_state(self.oid)
                        if hasattr(self.main_app, "app") and hasattr(self.main_app.app, "redo_stacks") and isinstance(self.main_app.app.redo_stacks, dict):
                            self.main_app.app.redo_stacks.setdefault(self.oid, []).clear()
                    except Exception:
                        pass

                reg_changed_fields = [f]
                reg_changed_values = [f'{f}: "{cv}"  "{new_val}"']
                prob_changed_fields = []
                prob_changed_values = []
 
                app_obj = getattr(self.main_app, "app", None)
                if app_obj and getattr(app_obj, "df_reg", None) is not None:
                    if self.oid in app_obj.df_reg.index:
                        app_obj.df_reg.loc[self.oid, f] = new_val
                    elif str(self.oid).isdigit() and int(self.oid) in app_obj.df_reg.index:
                        app_obj.df_reg.loc[int(self.oid), f] = new_val

                if hasattr(self.main_app, "reg_vars") and f in self.main_app.reg_vars:
                    self.main_app.reg_vars[f].set(new_val)
                if hasattr(self.main_app, "reg_entries") and f in self.main_app.reg_entries:
                    w = self.main_app.reg_entries[f]
                    if isinstance(w, tk.Text):
                        w.delete("1.0", tk.END)
                        w.insert("1.0", str(new_val))
                if getattr(self.main_app, "_cached_reg_dict", None) is not None and self.oid in self.main_app._cached_reg_dict:
                    self.main_app._cached_reg_dict[self.oid][f] = new_val
 
                prob_to_field = getattr(self.main_app, "problem_to_field", {})
                for pc, mf in prob_to_field.items():
                    if mf == f and hasattr(self.main_app, "problem_vars") and pc in self.main_app.problem_vars:
                        old_prob = False
                        if app_obj and getattr(app_obj, "df_obs", None) is not None:
                            if self.oid in app_obj.df_obs.index:
                                old_prob = bool(app_obj.df_obs.loc[self.oid].get(pc, False))
                                app_obj.df_obs.loc[self.oid, pc] = False
                            elif str(self.oid).isdigit() and int(self.oid) in app_obj.df_obs.index:
                                old_prob = bool(app_obj.df_obs.loc[int(self.oid)].get(pc, False))
                                app_obj.df_obs.loc[int(self.oid), pc] = False

                        if old_prob:
                            prob_changed_fields.append(pc)
                            prob_changed_values.append(f'{pc}: "True"  "False"')
                        self.main_app.problem_vars[pc].set(False)

                        if getattr(self.main_app, "_cached_obs_dict", None) is not None and self.oid in self.main_app._cached_obs_dict:
                            self.main_app._cached_obs_dict[self.oid][pc] = False
                        if hasattr(self.main_app, "loaded_problem_states"):
                            self.main_app.loaded_problem_states[pc] = False
                
                self.main_app._row_cache_dirty = True
                if hasattr(self.main_app, "commit_current_object"):
                    self.main_app.commit_current_object(skip_logging=True)
 
                if hasattr(self.main_app, "log_action"):
                    self.main_app.log_action(
                        "RESOLVE_HISTORICAL_CONFLICT",
                        changed_fields=reg_changed_fields,
                        changed_values=reg_changed_values,
                        prob_fields=prob_changed_fields,
                        prob_values=prob_changed_values
                    )
 
                if hasattr(self.main_app, "object_list") and hasattr(self.main_app.object_list, "refresh_object_card"):
                    self.main_app.object_list.refresh_object_card(self.oid)

                app_bus.publish(DATABASE_UPDATED)
                self.update_stats()
                
                c.configure(highlightbackground=COLORS["success"])
                for w in h.winfo_children():
                    w.configure(bg=COLORS["success"])
                h.configure(bg=COLORS["success"])
                
        btn_apply = tk.Button(entry_frame, text="APPLY", font=FONT_UI_BOLD, fg=COLORS["on_primary"], bg=COLORS["primary"], relief="flat", bd=0, padx=sc(16), command=_apply, cursor="hand2")
        btn_apply.pack(side="right", padx=(sc(8), 0))
        
        entry.bind("<Return>", lambda e, f=_apply: f())
        
        self.card_frames[field] = card
        
        def _on_focus(event):
            y = card.winfo_y()
            if self.scrollable_frame.winfo_height() > 0:
                self.canvas.yview_moveto(y / self.scrollable_frame.winfo_height())
                
        for widget in [entry, btn_apply]:
            widget.bind("<FocusIn>", _on_focus, add="+")
            
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

        undo_pushed = False
        app_obj = getattr(self.main_app, "app", None)

        for field in self.fields:
            reg_dict = self.main_app._get_reg_dict() if hasattr(self.main_app, "_get_reg_dict") else {}
            reg_row = reg_dict.get(self.oid)
            if reg_row is None and app_obj and getattr(app_obj, "df_reg", None) is not None:
                if self.oid in app_obj.df_reg.index:
                    reg_row = app_obj.df_reg.loc[self.oid]
                elif str(self.oid).isdigit() and int(self.oid) in app_obj.df_reg.index:
                    reg_row = app_obj.df_reg.loc[int(self.oid)]
            if reg_row is None and hasattr(self.main_app, "reg_by_id") and self.main_app.reg_by_id is not None:
                if hasattr(self.main_app.reg_by_id, "index") and self.oid in self.main_app.reg_by_id.index:
                    reg_row = self.main_app.reg_by_id.loc[self.oid]
            if isinstance(reg_row, pd.DataFrame):
                reg_row = reg_row.iloc[0]

            current_val = str(reg_row.get(field, "") if reg_row is not None else "").strip()
            if current_val == "nan": current_val = ""
            
            res_var = self.res_vars.get(field)
            new_val = res_var.get().strip() if res_var else ""
            if new_val and new_val != current_val:
                if not undo_pushed and hasattr(self.main_app, "push_undo_state"):
                    try:
                        self.main_app.push_undo_state(self.oid)
                        if app_obj and hasattr(app_obj, "redo_stacks") and isinstance(app_obj.redo_stacks, dict):
                            app_obj.redo_stacks.setdefault(self.oid, []).clear()
                        undo_pushed = True
                    except Exception:
                        pass

                if app_obj and getattr(app_obj, "df_reg", None) is not None:
                    if self.oid in app_obj.df_reg.index:
                        app_obj.df_reg.loc[self.oid, field] = new_val
                    elif str(self.oid).isdigit() and int(self.oid) in app_obj.df_reg.index:
                        app_obj.df_reg.loc[int(self.oid), field] = new_val

                if hasattr(self.main_app, "reg_vars") and field in self.main_app.reg_vars:
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
                    
                prob_to_field = getattr(self.main_app, "problem_to_field", {})
                for pc, mf in prob_to_field.items():
                    if mf == field and hasattr(self.main_app, "problem_vars") and pc in self.main_app.problem_vars:
                        old_prob = False
                        if app_obj and getattr(app_obj, "df_obs", None) is not None:
                            if self.oid in app_obj.df_obs.index:
                                old_prob = bool(app_obj.df_obs.loc[self.oid].get(pc, False))
                                app_obj.df_obs.loc[self.oid, pc] = False
                            elif str(self.oid).isdigit() and int(self.oid) in app_obj.df_obs.index:
                                old_prob = bool(app_obj.df_obs.loc[int(self.oid)].get(pc, False))
                                app_obj.df_obs.loc[int(self.oid), pc] = False

                        if old_prob:
                            prob_changed_fields.append(pc)
                            prob_changed_values.append(f'{pc}: "True"  "False"')
                        self.main_app.problem_vars[pc].set(False)

                        if getattr(self.main_app, "_cached_obs_dict", None) is not None and self.oid in self.main_app._cached_obs_dict:
                            self.main_app._cached_obs_dict[self.oid][pc] = False
                        if hasattr(self.main_app, "loaded_problem_states"):
                            self.main_app.loaded_problem_states[pc] = False
                        
                if field in self.card_frames:
                    card = self.card_frames[field]
                    card.configure(highlightbackground=COLORS["success"])
                    header = card.winfo_children()[0]
                    header.configure(bg=COLORS["success"])
                    for w in header.winfo_children():
                        w.configure(bg=COLORS["success"])
                        
        if reg_changed_fields or prob_changed_fields:
            self.main_app._row_cache_dirty = True
            if hasattr(self.main_app, "commit_current_object"):
                self.main_app.commit_current_object(skip_logging=True)
            if hasattr(self.main_app, "log_action"):
                self.main_app.log_action(
                    "RESOLVE_HISTORICAL_CONFLICT",
                    changed_fields=reg_changed_fields,
                    changed_values=reg_changed_values,
                    prob_fields=prob_changed_fields,
                    prob_values=prob_changed_values
                )

        if hasattr(self.main_app, "object_list") and hasattr(self.main_app.object_list, "refresh_object_card"):
            self.main_app.object_list.refresh_object_card(self.oid)

        app_bus.publish(DATABASE_UPDATED)
        self.update_stats()

        if self._is_queue_mode:
            if self._queue_idx < len(self._oid_queue) - 1:
                self._queue_navigate(1)
            else:
                self.win.destroy()
        else:
            self.win.destroy()
            if getattr(self.main_app, "auto_advance_history_var", None) and self.main_app.auto_advance_history_var.get():
                if hasattr(self.main_app, "goto_next_problem_with_history"):
                    self.main_app.goto_next_problem_with_history()


class ProblemQueueDialog(tk.Toplevel):
    """
    Scope selector shown before opening ObjectProblemResolver in queue mode.
    Used by the 'Process Objects with Problems' menu action.
    """
    def __init__(self, parent, main_app):
        super().__init__(parent)
        init_fonts()
        self.main_app = main_app
        self.title("Process Objects with Problems")
        self.configure(bg=COLORS["bg"])
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()

        import utils
        utils.center_and_fit_toplevel(self, sc(520), sc(490))

        self.scope_var = tk.StringVar(value="filtered")
        self.cat_taxonomy_var = tk.BooleanVar(value=True)
        self.cat_collection_var = tk.BooleanVar(value=True)
        self.cat_physical_var = tk.BooleanVar(value=True)
        self.cat_notes_var = tk.BooleanVar(value=True)

        self._build_ui()
        self._update_matching_count()

    def _build_ui(self):
        # Header
        header = tk.Frame(self, bg=COLORS["surface"], height=sc(44))
        header.pack(fill="x", side="top")
        header.pack_propagate(False)
        tk.Frame(header, bg=COLORS["border"], height=sc(1)).pack(fill="x", side="bottom")
        tk.Label(header, text="BATCH_PROBLEM_QUEUE", font=FONT_UI_LG, fg=COLORS["primary"], bg=COLORS["surface"]).pack(side="left", padx=sc(16), pady=sc(10))

        # Footer (packed first to guarantee visibility)
        footer = tk.Frame(self, bg=COLORS["surface_dim"], height=sc(52))
        footer.pack(fill="x", side="bottom")
        footer.pack_propagate(False)
        tk.Frame(footer, bg=COLORS["border"], height=sc(1)).pack(side="top", fill="x")

        self.btn_confirm = tk.Button(footer, text="OPEN QUEUE", font=FONT_UI_BOLD, fg=COLORS["on_primary"], bg=COLORS["primary"], relief="flat", bd=0, padx=sc(16), pady=sc(6), command=self._on_confirm, cursor="hand2")
        self.btn_confirm.pack(side="right", padx=sc(16), pady=sc(8))

        btn_cancel = tk.Button(footer, text="CANCEL", font=FONT_UI_BOLD, fg=COLORS["text"], bg=COLORS["surface"], relief="solid", bd=1, padx=sc(14), pady=sc(6), command=self.destroy, cursor="hand2")
        btn_cancel.pack(side="right", padx=sc(8), pady=sc(8))

        content = tk.Frame(self, bg=COLORS["bg"], padx=sc(20), pady=sc(14))
        content.pack(fill="both", expand=True)

        # 1. Scope Selection
        tk.Label(content, text="SCOPE", font=FONT_MONO_SM, fg=COLORS["text_muted"], bg=COLORS["bg"]).pack(anchor="w", pady=(0, sc(4)))
        scope_box = tk.Frame(content, bg=COLORS["surface"], highlightbackground=COLORS["border"], highlightthickness=1, padx=sc(12), pady=sc(8))
        scope_box.pack(fill="x", pady=(0, sc(12)))

        tk.Radiobutton(scope_box, text="All currently filtered objects in view", variable=self.scope_var, value="filtered", font=FONT_UI, bg=COLORS["surface"], activebackground=COLORS["surface"], command=self._update_matching_count).pack(anchor="w", pady=sc(2))
        
        has_selection = False
        if hasattr(self.main_app, "object_list") and hasattr(self.main_app.object_list, "selection"):
            try:
                has_selection = len(self.main_app.object_list.selection()) > 1
            except Exception:
                has_selection = False
        
        rb_sel = tk.Radiobutton(scope_box, text="Selected objects only", variable=self.scope_var, value="selected", font=FONT_UI, bg=COLORS["surface"], activebackground=COLORS["surface"], state="normal" if has_selection else "disabled", command=self._update_matching_count)
        rb_sel.pack(anchor="w", pady=sc(2))

        # 2. Problem Categories
        tk.Label(content, text="PROBLEM CATEGORIES TO INCLUDE", font=FONT_MONO_SM, fg=COLORS["text_muted"], bg=COLORS["bg"]).pack(anchor="w", pady=(0, sc(4)))
        cat_box = tk.Frame(content, bg=COLORS["surface"], highlightbackground=COLORS["border"], highlightthickness=1, padx=sc(12), pady=sc(8))
        cat_box.pack(fill="x", pady=(0, sc(12)))

        row1 = tk.Frame(cat_box, bg=COLORS["surface"])
        row1.pack(fill="x", pady=sc(2))
        tk.Checkbutton(row1, text="🧬 Taxonomy (Genus, Species, Family, Author)", variable=self.cat_taxonomy_var, font=FONT_UI, bg=COLORS["surface"], activebackground=COLORS["surface"], command=self._update_matching_count).pack(side="left")

        row2 = tk.Frame(cat_box, bg=COLORS["surface"])
        row2.pack(fill="x", pady=sc(2))
        tk.Checkbutton(row2, text="📦 Collection (Collector, Date, Place)", variable=self.cat_collection_var, font=FONT_UI, bg=COLORS["surface"], activebackground=COLORS["surface"], command=self._update_matching_count).pack(side="left")

        row3 = tk.Frame(cat_box, bg=COLORS["surface"])
        row3.pack(fill="x", pady=sc(2))
        tk.Checkbutton(row3, text="🏷️ Physical (Box Label, Plant Part)", variable=self.cat_physical_var, font=FONT_UI, bg=COLORS["surface"], activebackground=COLORS["surface"], command=self._update_matching_count).pack(side="left")

        row4 = tk.Frame(cat_box, bg=COLORS["surface"])
        row4.pack(fill="x", pady=sc(2))
        tk.Checkbutton(row4, text="📝 Notes & Other", variable=self.cat_notes_var, font=FONT_UI, bg=COLORS["surface"], activebackground=COLORS["surface"], command=self._update_matching_count).pack(side="left")

        # 3. Match count label
        self.count_label = tk.Label(content, text="0 objects with matching problems", font=FONT_MONO, fg=COLORS["primary"], bg=COLORS["bg"])
        self.count_label.pack(anchor="w", pady=(0, sc(4)))

    def _get_matching_oids(self) -> list:
        app_obj = getattr(self.main_app, "app", self.main_app)
        if not app_obj or getattr(app_obj, "df_reg", None) is None:
            return []

        # 1. Determine target candidate OIDs
        if self.scope_var.get() == "selected" and hasattr(self.main_app, "object_list"):
            candidate_oids = [str(x) for x in self.main_app.object_list.selection()]
        else:
            candidate_oids = [str(x) for x in getattr(app_obj, "active_object_ids", list(app_obj.df_reg.index))]

        # 2. Determine active problem columns based on selected categories
        import config
        db_key = getattr(app_obj, 'current_db_key', 'Økonomisk Botanisk')
        db_config = getattr(app_obj, 'config', None) or config.DATABASE_CONFIGS.get(db_key, {})
        probs_list = db_config.get('problems', []) or db_config.get('ui_sections', {}).get('problems', [])
        
        target_cats = set()
        if self.cat_taxonomy_var.get(): target_cats.add("taxonomy")
        if self.cat_collection_var.get(): target_cats.add("collection")
        if self.cat_physical_var.get(): target_cats.add("physical")
        if self.cat_notes_var.get(): 
            target_cats.add("notes")
            target_cats.add("other")

        target_prob_cols = []
        for prob in probs_list:
            if prob.get('category', 'other') in target_cats:
                target_prob_cols.append(prob.get('name'))

        if not target_prob_cols:
            if self.cat_taxonomy_var.get():
                target_prob_cols.extend(["Genus_Problem", "Species_Problem", "Family_Problem", "Author_Problem"])
            if self.cat_collection_var.get():
                target_prob_cols.extend(["Collector_Problem", "Collection_Date_Problem", "Collection_Place_Problem"])
            if self.cat_physical_var.get():
                target_prob_cols.extend(["Box_Label_Problem", "PlantPart_Problem"])
            if self.cat_notes_var.get():
                target_prob_cols.extend(["Other_problem", "Images_Problem"])

        # 3. Filter candidates
        matching = []
        obs_dict = self.main_app._get_obs_dict() if hasattr(self.main_app, "_get_obs_dict") else {}
        df_obs = getattr(app_obj, "df_obs", None)

        for oid in candidate_oids:
            obs_row = obs_dict.get(oid)
            if obs_row is None and str(oid).isdigit():
                obs_row = obs_dict.get(int(oid))
            if obs_row is None and df_obs is not None:
                if oid in df_obs.index:
                    obs_row = df_obs.loc[oid].to_dict()
                elif str(oid).isdigit() and int(oid) in df_obs.index:
                    obs_row = df_obs.loc[int(oid)].to_dict()

            if obs_row:
                has_prob = any(bool(obs_row.get(col, False)) for col in target_prob_cols)
                if has_prob:
                    matching.append(oid)

        return matching

    def _update_matching_count(self):
        matching = self._get_matching_oids()
        count = len(matching)
        if hasattr(self, "count_label") and self.count_label.winfo_exists():
            self.count_label.config(text=f"{count} object{'s' if count != 1 else ''} with matching problems")
        if hasattr(self, "btn_confirm") and self.btn_confirm.winfo_exists():
            self.btn_confirm.config(
                text=f"OPEN QUEUE ({count} OBJECT{'S' if count != 1 else ''})",
                state="normal" if count > 0 else "disabled"
            )

    def _on_confirm(self):
        matching = self._get_matching_oids()
        if not matching:
            return
        self.destroy()
        ObjectProblemResolver(self.main_app, matching)


# Backward-compatibility alias for existing code and tests
HistoricalConflictResolverWindow = ObjectProblemResolver
