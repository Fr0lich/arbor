import tkinter as tk
from tkinter import ttk, messagebox
import pandas as pd
from datetime import datetime
import os
import getpass
import tkinter.font as tkFont
import math
from typing import List, Dict, Any, Optional, Tuple, Set
from config import sc
from ui.state import app_bus, DATABASE_UPDATED
from backend.cross_validation import find_book_matches_for_gbif

FONT_UI = ("sans-serif", 10)
FONT_UI_BOLD = ("sans-serif", 10, "bold")
FONT_UI_LG = ("sans-serif", 12, "bold")
FONT_UI_XL = ("sans-serif", 15, "bold")
FONT_MONO = ("Consolas", 10)
FONT_MONO_SM = ("Consolas", 8)

_fonts_initialized = False
def init_fonts():
    global _fonts_initialized, FONT_UI, FONT_UI_BOLD, FONT_UI_LG, FONT_UI_XL, FONT_MONO, FONT_MONO_SM
    if _fonts_initialized:
        return
    families = tkFont.families()
    ui_family = "Hanken Grotesk" if "Hanken Grotesk" in families else "Helvetica" if "Helvetica" in families else "Segoe UI" if "Segoe UI" in families else "sans-serif"
    mono_family = "JetBrains Mono" if "JetBrains Mono" in families else "Consolas" if "Consolas" in families else "Courier New"

    FONT_UI = (ui_family, sc(10))
    FONT_UI_BOLD = (ui_family, sc(10), "bold")
    FONT_UI_LG = (ui_family, sc(12), "bold")
    FONT_UI_XL = (ui_family, sc(15), "bold")
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
    "primary": "#2c302e",
    "on_primary": "#ffffff",
    "error_bg": "#fef2f2",
    "error_border": "#c93a40",
    "error_text": "#c93a40",
    "success_bg": "#f0fdf4",
    "success_border": "#3a7d44",
    "success_text": "#2b8a3e",
    "warning": "#f59e0b",
    "warning_bg": "#fffbeb",
    "chip_tag": "#757d77"
}


class GBIFReviewDialog(tk.Toplevel):
    """
    High-Performance Paginated Taxonomic Reconciliation & Review dialog.
    Supports reviewing thousands of specimens with phased category triage,
    filter-scoped live application, real-time audit logging, and resilient fullscreen geometry.
    """
    def __init__(self, parent, app_state, diff_results: List[Dict[str, Any]], on_applied_callback=None):
        super().__init__(parent)
        self.withdraw()  # Prevent top-left flashing during widget construction
        init_fonts()
        self.parent = parent
        self.app_state = app_state
        self.diff_results = diff_results or []
        self.on_applied_callback = on_applied_callback

        is_dark = getattr(self.parent, "dark_mode_active", False) if hasattr(self.parent, "dark_mode_active") else False
        self.is_dark = is_dark
        self.colors = {
            "bg": "#181c19" if is_dark else COLORS["bg"],
            "surface": "#24273a" if is_dark else COLORS["surface"],
            "surface_dim": "#1e2030" if is_dark else COLORS["surface_dim"],
            "border": "#363a4f" if is_dark else COLORS["border"],
            "text": "#cad3f5" if is_dark else COLORS["text"],
            "text_muted": "#a5adcb" if is_dark else COLORS["text_muted"],
            "header_bg": "#1b1b1b" if is_dark else "#2c302e",
            "primary": "#cad3f5" if is_dark else COLORS["primary"],
            "success": "#3a7d44",
            "success_bg": "#122416" if is_dark else "#f0fdf4",
            "success_border": "#2b8a3e" if is_dark else "#3a7d44",
            "success_text": "#a6e3a1" if is_dark else "#2b8a3e",
            "warning": "#f59e0b",
            "warning_bg": "#332200" if is_dark else "#fffbeb",
            "error_bg": "#2e1518" if is_dark else "#fef2f2",
            "error_border": "#802024" if is_dark else "#c93a40",
            "error_text": "#e06c75" if is_dark else "#c93a40",
        }

        self.title("GBIF Taxonomic Review & Reconciliation")
        self.configure(bg=self.colors["bg"])
        self.minsize(sc(920), sc(600))

        # Workflow & Filter State
        self.page_size = 25
        self.current_page = 0
        self.search_query = ""
        self.category_tab = "pending"  # "pending", "verified", "accepted", "synonym", "applied"
        self._is_fullscreen = False

        # Applied tracking across session
        self._applied_oids: Set[str] = set()
        self.applied_changes: Set[Tuple[str, str]] = set()

        # Global Cross-Page Selection Tracking
        self.selection_state: Dict[Tuple[str, str], bool] = {}
        self.all_changes: Dict[Tuple[str, str], Dict[str, Any]] = {}
        self.oid_to_diff: Dict[str, Dict[str, Any]] = {}

        for d in self.diff_results:
            oid = str(d.get("oid", ""))
            self.oid_to_diff[oid] = d
            for chg in d.get("changes", []):
                field = chg.get("field", "")
                key = (oid, field)
                self.selection_state[key] = True
                self.all_changes[key] = chg

        # Page-local UI references
        self.item_cards = {}
        self.specimen_frames = {}
        self.specimen_dir_widgets = {}
        self.page_field_vars = {}
        self.tab_buttons = {}
        self.field_row_widgets = {}
        self.card_header_widgets = {}
        self._active_scroll_target = "main"
        self._toast_timer = None

        self._build_ui()
        self._update_tab_buttons()
        self._render_current_page()

        self.bind("<Control-a>", lambda e: self._apply_selected())
        self.bind("<Control-Return>", lambda e: self._apply_selected())
        self.bind("<Escape>", lambda e: self.destroy())
        self.bind("<F11>", lambda e: self._toggle_fullscreen())
        self.bind("<Alt-Return>", lambda e: self._toggle_fullscreen())
        self.bind("<Destroy>", self._on_dialog_destroy)

        self.bind_all("<MouseWheel>", self._on_routed_mousewheel)
        self.bind_all("<Button-4>", self._on_routed_mousewheel)
        self.bind_all("<Button-5>", self._on_routed_mousewheel)

        import utils
        utils.center_and_fit_toplevel(self, sc(1180), sc(760))
        self.lift()
        self.focus_set()
        self.deiconify()

    def _bind_mousewheel_recursive(self, widget, handler):
        try:
            widget.bind("<MouseWheel>", handler, add="+")
            widget.bind("<Button-4>", handler, add="+")
            widget.bind("<Button-5>", handler, add="+")
        except Exception:
            pass
        try:
            for child in widget.winfo_children():
                self._bind_mousewheel_recursive(child, handler)
        except Exception:
            pass

    @property
    def applied_oids(self) -> Set[str]:
        return {str(oid).strip().lower() for oid, f in self.applied_changes} | getattr(self, "_applied_oids", set())

    @applied_oids.setter
    def applied_oids(self, val):
        self._applied_oids = {str(x).strip().lower() for x in (val or set())}

    @property
    def status_filter(self) -> str:
        if self.category_tab == "pending":
            return "all"
        return self.category_tab

    @status_filter.setter
    def status_filter(self, val: str):
        if val == "all":
            self.category_tab = "pending"
        else:
            self.category_tab = val

    def _toggle_fullscreen(self, event=None):
        self._is_fullscreen = not self._is_fullscreen
        try:
            if self._is_fullscreen:
                self.state("zoomed")
            else:
                self.state("normal")
        except Exception:
            try:
                self.attributes("-fullscreen", self._is_fullscreen)
            except Exception:
                pass

        if hasattr(self, "btn_fullscreen") and self.btn_fullscreen.winfo_exists():
            self.btn_fullscreen.config(text="🗗 Restore" if self._is_fullscreen else "⛶ Maximize")

    def _diff_has_book_matches(self, diff: Dict[str, Any]) -> bool:
        oid = str(diff.get("oid", ""))
        for chg in diff.get("changes", []):
            field = chg.get("field", "")
            val = chg.get("new", "")
            if find_book_matches_for_gbif(self.app_state, oid, field, val):
                return True
        return False

    def _diff_has_unapplied_book_matches(self, diff: Dict[str, Any]) -> bool:
        oid = str(diff.get("oid", ""))
        for chg in diff.get("changes", []):
            field = chg.get("field", "")
            val = chg.get("new", "")
            if (oid, field) not in self.applied_changes:
                if find_book_matches_for_gbif(self.app_state, oid, field, val):
                    return True
        return False

    def _diff_has_unapplied_changes(self, diff: Dict[str, Any]) -> bool:
        oid = str(diff.get("oid", ""))
        return any((oid, chg.get("field", "")) not in self.applied_changes for chg in diff.get("changes", []))

    def _diff_has_applied_changes(self, diff: Dict[str, Any]) -> bool:
        oid = str(diff.get("oid", ""))
        return any((oid, chg.get("field", "")) in self.applied_changes for chg in diff.get("changes", []))

    def _is_diff_fully_applied(self, diff: Dict[str, Any]) -> bool:
        oid = str(diff.get("oid", ""))
        changes = diff.get("changes", [])
        if not changes:
            return True
        return all((oid, chg.get("field", "")) in self.applied_changes for chg in changes)

    def _get_specimen_title_info(self, diff: Dict[str, Any]) -> Dict[str, str]:
        oid = str(diff.get("oid", ""))
        curr = diff.get("current", {})
        prop = diff.get("proposed", {})
        curr_g = str(curr.get("Genus", "") or "").strip()
        curr_s = str(curr.get("Species", "") or "").strip()
        curr_tax = f"{curr_g} {curr_s}".strip() or "(No Taxon)"

        prop_g = str(prop.get("Genus", "") or "").strip()
        prop_s = str(prop.get("Species", "") or "").strip()
        prop_tax = f"{prop_g} {prop_s}".strip()

        is_rename = bool(prop_tax and prop_tax.lower() != curr_tax.lower())
        if is_rename:
            hdr_title = f"SPECIMEN #{oid} • {curr_tax}  →  {prop_tax}"
            sidebar_tax = f"{curr_tax} → {prop_tax}"
        else:
            hdr_title = f"SPECIMEN #{oid} • {curr_tax}"
            sidebar_tax = curr_tax

        return {
            "oid": oid,
            "header_title": hdr_title,
            "sidebar_tax": sidebar_tax,
            "curr_tax": curr_tax,
            "prop_tax": prop_tax,
            "is_rename": is_rename
        }

    def _find_reg_oid(self, oid: str):
        if not hasattr(self.app_state, "df_reg") or self.app_state.df_reg is None:
            return None
        reg_oid = oid
        if reg_oid not in self.app_state.df_reg.index:
            if str(oid).isdigit() and int(oid) in self.app_state.df_reg.index:
                reg_oid = int(oid)
            else:
                matches = [idx for idx in self.app_state.df_reg.index if str(idx).strip() == str(oid).strip()]
                if matches:
                    reg_oid = matches[0]
                else:
                    return None
        return reg_oid

    def _get_problem_to_field_map(self) -> Dict[str, str]:
        problem_to_field = {}
        if getattr(self.app_state, "config", None):
            problems_cfg = self.app_state.config.get("ui_sections", {}).get("problems", [])
            for p in problems_cfg:
                name = p.get("name")
                maps_to = p.get("maps_to") or p.get("target")
                if name and maps_to and maps_to != "Other" and name != "Other_problem":
                    problem_to_field[name] = maps_to
        return problem_to_field

    def _get_tab_counts(self) -> Dict[str, int]:
        unapplied_diffs = [d for d in self.diff_results if self._diff_has_unapplied_changes(d)]
        verified = [d for d in unapplied_diffs if self._diff_has_unapplied_book_matches(d)]
        synonyms = [d for d in unapplied_diffs if "synonym" in str(d.get("status", "")).strip().lower()]
        accepted = [d for d in unapplied_diffs if "synonym" not in str(d.get("status", "")).strip().lower()]
        applied_cnt = sum(1 for d in self.diff_results if self._diff_has_applied_changes(d))

        return {
            "pending": len(unapplied_diffs),
            "verified": len(verified),
            "accepted": len(accepted),
            "synonym": len(synonyms),
            "applied": applied_cnt
        }

    def _get_filtered_results(self) -> List[Dict[str, Any]]:
        q = self.search_query.strip().lower()
        tab = self.category_tab

        results = []
        for d in self.diff_results:
            oid = str(d.get("oid", "")).strip().lower()
            status = str(d.get("status", "")).strip().lower()
            match_type = str(d.get("match_type", "")).strip().lower()
            has_unapplied = self._diff_has_unapplied_changes(d)
            has_applied = self._diff_has_applied_changes(d)

            # Tab filter
            if tab == "applied":
                if not has_applied:
                    continue
            else:
                # Active triage tabs only include items with pending unapplied fields
                if not has_unapplied:
                    continue

                if tab == "verified":
                    if not self._diff_has_unapplied_book_matches(d):
                        continue
                elif tab == "synonym" and "synonym" not in status:
                    continue
                elif tab == "accepted" and "synonym" in status:
                    continue
                # tab == "pending" includes all items with unapplied fields

            # Query filter (matches OID or any taxon field)
            if q:
                curr_vals = " ".join(str(v).lower() for v in d.get("current", {}).values())
                prop_vals = " ".join(str(v).lower() for v in d.get("proposed", {}).values())
                combined = f"{oid} {status} {match_type} {curr_vals} {prop_vals}"
                if q not in combined:
                    continue

            results.append(d)

        return results

    def _build_ui(self):
        C = self.colors

        # 1. Top Header Bar (Full-bleed)
        header = tk.Frame(self, bg=C["surface"], height=sc(48))
        header.pack(fill="x", side="top")
        tk.Frame(header, bg=C["border"], height=sc(1)).pack(fill="x", side="bottom")

        hdr_left = tk.Frame(header, bg=C["surface"])
        hdr_left.pack(side="left", padx=sc(16), pady=sc(10))

        tk.Label(
            hdr_left,
            text="GBIF_TAXONOMIC_RECONCILIATION",
            font=FONT_UI_LG,
            fg=C["text"],
            bg=C["surface"]
        ).pack(side="left")

        # Fullscreen / Maximize button in header
        self.btn_fullscreen = tk.Button(
            hdr_left,
            text="⛶ Maximize",
            command=self._toggle_fullscreen,
            font=FONT_MONO_SM,
            bg=C["surface_dim"],
            fg=C["text"],
            relief="flat",
            bd=0,
            cursor="hand2",
            padx=sc(8),
            pady=sc(2),
            highlightthickness=1,
            highlightbackground=C["border"]
        )
        self.btn_fullscreen.pack(side="left", padx=(sc(12), 0))

        # Search box on Right of Header
        hdr_right = tk.Frame(header, bg=C["surface"])
        hdr_right.pack(side="right", padx=sc(16), pady=sc(8))

        self.search_var = tk.StringVar()
        self.search_entry = tk.Entry(
            hdr_right,
            textvariable=self.search_var,
            font=FONT_UI,
            bg=C["surface_dim"],
            fg=C["text"],
            relief="flat",
            bd=0,
            width=22,
            highlightthickness=1,
            highlightbackground=C["border"],
            highlightcolor=C["primary"]
        )
        self.search_entry.pack(side="right", ipady=sc(3))
        self.search_var.trace_add("write", lambda *args: self._on_search_changed())

        tk.Label(
            hdr_right,
            text="SEARCH:",
            font=FONT_MONO_SM,
            fg=C["text_muted"],
            bg=C["surface"]
        ).pack(side="right", padx=(0, sc(6)))

        # Backward compatibility for status_var
        self.status_var = tk.StringVar(value="All")

        # 2. Workflow Stage Tabs Bar
        tabs_bar = tk.Frame(self, bg=C["surface_dim"], height=sc(42))
        tabs_bar.pack(fill="x", side="top")
        tk.Frame(tabs_bar, bg=C["border"], height=sc(1)).pack(fill="x", side="bottom")

        tabs_content = tk.Frame(tabs_bar, bg=C["surface_dim"], padx=sc(14), pady=sc(6))
        tabs_content.pack(fill="x")

        tk.Label(
            tabs_content,
            text="WORKFLOW STAGES:",
            font=FONT_MONO_SM,
            fg=C["text_muted"],
            bg=C["surface_dim"]
        ).pack(side="left", padx=(0, sc(8)))

        self.tab_buttons = {}
        tab_defs = [
            ("pending", "All Pending", C["primary"]),
            ("verified", "✓ Verified in Books", C["success_text"]),
            ("accepted", "🔤 Accepted / Spelling", C["text"]),
            ("synonym", "⚠️ Synonyms", C["warning"]),
            ("applied", "✓ Applied", C["success_text"])
        ]

        for tab_key, label_prefix, accent in tab_defs:
            btn = tk.Button(
                tabs_content,
                text=label_prefix,
                command=lambda k=tab_key: self._set_category_tab(k),
                font=FONT_UI,
                bg=C["surface"],
                fg=C["text"],
                relief="flat",
                bd=0,
                cursor="hand2",
                padx=sc(10),
                pady=sc(3),
                highlightthickness=1,
                highlightbackground=C["border"]
            )
            btn.pack(side="left", padx=(0, sc(6)))
            self.tab_buttons[tab_key] = {"btn": btn, "prefix": label_prefix, "accent": accent}

        # 3. Triage Guidance Banner
        self.tip_frame = tk.Frame(self, bg=C["surface_dim"], padx=sc(16), pady=sc(4))
        self.tip_frame.pack(fill="x", side="top")
        tk.Frame(self.tip_frame, bg=C["border"], height=sc(1)).pack(fill="x", side="bottom")

        self.tip_label = tk.Label(
            self.tip_frame,
            text="💡 GUIDED TRIAGE: 1. Start with \"✓ Verified in Books\" (100% Safe)  →  2. Review \"Accepted / Spelling\"  →  3. Evaluate \"⚠️ Synonyms\" one-by-one.",
            font=FONT_MONO_SM,
            fg=C["text_muted"],
            bg=C["surface_dim"]
        )
        self.tip_label.pack(side="left", pady=sc(2))

        # 4. Floating Toast Notification Overlay (Hidden initially, uses place() on z-stack)
        self.toast_frame = tk.Frame(
            self,
            bg=C["success_bg"],
            highlightbackground=C["success_border"],
            highlightthickness=1,
            padx=sc(14),
            pady=sc(6)
        )
        self.toast_icon = tk.Label(
            self.toast_frame,
            text="✓",
            font=FONT_UI_BOLD,
            fg=C["success_text"],
            bg=C["success_bg"]
        )
        self.toast_icon.pack(side="left", padx=(0, sc(6)))

        self.toast_label = tk.Label(
            self.toast_frame,
            text="",
            font=FONT_UI_BOLD,
            fg=C["success_text"],
            bg=C["success_bg"]
        )
        self.toast_label.pack(side="left")

        self.toast_close = tk.Label(
            self.toast_frame,
            text="✕",
            font=FONT_UI_BOLD,
            fg=C["success_text"],
            bg=C["success_bg"],
            cursor="hand2"
        )
        self.toast_close.pack(side="right", padx=(sc(12), 0))
        self.toast_close.bind("<Button-1>", lambda e: self._hide_toast())

        # 5. Bottom Action Bar (Sticky, packed before main_area with fixed height)
        bottom_bar = tk.Frame(self, bg=C["surface_dim"], height=sc(60))
        bottom_bar.pack(fill="x", side="bottom")
        bottom_bar.pack_propagate(False)
        tk.Frame(bottom_bar, bg=C["border"], height=sc(1)).pack(side="top", fill="x")

        b_content = tk.Frame(bottom_bar, bg=C["surface_dim"], padx=sc(16), pady=sc(10))
        b_content.pack(fill="both", expand=True)

        # Batch Selection Controls
        self.sel_all_btn = tk.Button(
            b_content, text="Select All", command=self._select_all_batch,
            font=FONT_UI_BOLD, bg=C["surface"], fg=C["text"],
            relief="solid", bd=1, cursor="hand2", padx=sc(10), pady=sc(4)
        )
        self.sel_all_btn.pack(side="left", padx=(0, sc(6)))

        self.desel_all_btn = tk.Button(
            b_content, text="Deselect All", command=self._deselect_all_batch,
            font=FONT_UI_BOLD, bg=C["surface"], fg=C["text"],
            relief="solid", bd=1, cursor="hand2", padx=sc(10), pady=sc(4)
        )
        self.desel_all_btn.pack(side="left", padx=(0, sc(6)))

        self.sel_page_btn = tk.Button(
            b_content, text="Select Page", command=self._select_current_page,
            font=FONT_UI_BOLD, bg=C["surface"], fg=C["text"],
            relief="solid", bd=1, cursor="hand2", padx=sc(10), pady=sc(4)
        )
        self.sel_page_btn.pack(side="left", padx=(0, sc(6)))

        self.sel_verified_btn = tk.Button(
            b_content, text="🌟 Select Verified Only", command=self._select_verified_only,
            font=FONT_UI_BOLD, bg=C["surface"], fg=C["text"],
            relief="solid", bd=1, cursor="hand2", padx=sc(10), pady=sc(4)
        )
        self.sel_verified_btn.pack(side="left")

        # Summary label
        self.summary_label = tk.Label(
            b_content,
            text="",
            font=FONT_MONO,
            fg=C["text_muted"],
            bg=C["surface_dim"]
        )
        self.summary_label.pack(side="left", padx=sc(16))

        # Action Buttons
        cancel_btn = tk.Button(
            b_content, text="CLOSE & FINISH", command=self.destroy,
            font=FONT_UI_BOLD, bg=C["surface"], fg=C["text"],
            relief="solid", bd=1, cursor="hand2", padx=sc(16), pady=sc(6)
        )
        cancel_btn.pack(side="right", padx=(sc(8), 0))

        self.apply_btn = tk.Button(
            b_content, text="APPLY SELECTED UPDATES (CTRL+A)", command=self._apply_selected,
            font=FONT_UI_BOLD, bg=C["success"], fg="#ffffff",
            relief="flat", bd=0, cursor="hand2", padx=sc(18), pady=sc(6)
        )
        self.apply_btn.pack(side="right")

        # 6. Main content area (Split View: Left Sidebar Directory + Right Cards)
        main_area = tk.Frame(self, bg=C["bg"])
        main_area.pack(fill="both", expand=True)

        # --- Left Sidebar (Specimen Directory) ---
        sidebar = tk.Frame(main_area, width=sc(280), bg=C["surface_dim"])
        sidebar.pack(side="left", fill="y")
        sidebar.pack_propagate(False)
        tk.Frame(sidebar, bg=C["border"], width=sc(1)).pack(side="right", fill="y")

        dir_header = tk.Frame(sidebar, bg=C["surface_dim"], height=sc(36))
        dir_header.pack(fill="x")
        tk.Frame(dir_header, bg=C["border"], height=sc(1)).pack(side="bottom", fill="x")

        self.dir_title_label = tk.Label(
            dir_header,
            text="PAGE SPECIMENS",
            font=FONT_MONO_SM,
            fg=C["text_muted"],
            bg=C["surface_dim"]
        )
        self.dir_title_label.pack(side="left", padx=sc(12), pady=sc(8))

        # Dedicated Scrollbar Frame in Sidebar
        dir_scroll_frame = tk.Frame(sidebar, bg=C["surface_dim"])
        dir_scroll_frame.pack(fill="both", expand=True)

        self.dir_canvas = tk.Canvas(dir_scroll_frame, bg=C["surface_dim"], highlightthickness=0)
        self.dir_scrollbar = ttk.Scrollbar(dir_scroll_frame, orient="vertical", command=self.dir_canvas.yview)
        self.dir_list = tk.Frame(self.dir_canvas, bg=C["surface_dim"])

        self.dir_list.bind(
            "<Configure>",
            lambda e: self.dir_canvas.configure(scrollregion=self.dir_canvas.bbox("all")) if e.widget == self.dir_list else None
        )
        dir_canvas_window = self.dir_canvas.create_window((0, 0), window=self.dir_list, anchor="nw")
        self.dir_canvas.configure(yscrollcommand=self.dir_scrollbar.set)
        self.dir_canvas.bind("<Configure>", lambda e: self.dir_canvas.itemconfig(dir_canvas_window, width=e.width))

        self.dir_canvas.pack(side="left", fill="both", expand=True)
        self.dir_scrollbar.pack(side="right", fill="y")

        # Bind mousewheel and hover target routing to sidebar
        self._bind_mousewheel_recursive(sidebar, self._on_dir_mousewheel)
        self._bind_mousewheel_recursive(dir_scroll_frame, self._on_dir_mousewheel)
        sidebar.bind("<Enter>", lambda e: self._set_active_scroll_target("dir"), add="+")
        self.dir_canvas.bind("<Enter>", lambda e: self._set_active_scroll_target("dir"), add="+")
        self.dir_list.bind("<Enter>", lambda e: self._set_active_scroll_target("dir"), add="+")

        # --- Right Main Area (Scrollable Cards with Top Pagination) ---
        right_area = tk.Frame(main_area, bg=C["bg"])
        right_area.pack(side="left", fill="both", expand=True)

        # Top Pagination & Context Bar
        self.ctx_header = tk.Frame(right_area, bg=C["surface"], height=sc(48))
        self.ctx_header.pack(fill="x")
        tk.Frame(self.ctx_header, bg=C["border"], height=sc(1)).pack(side="bottom", fill="x")

        self.page_info_label = tk.Label(
            self.ctx_header,
            text="",
            font=FONT_MONO_SM,
            fg=C["text"],
            bg=C["surface"]
        )
        self.page_info_label.pack(side="left", padx=sc(16), pady=sc(12))

        # Pagination controls
        nav_frame = tk.Frame(self.ctx_header, bg=C["surface"])
        nav_frame.pack(side="right", padx=sc(16), pady=sc(6))

        self.btn_first = tk.Button(
            nav_frame, text="⏮", command=self._goto_first_page,
            font=FONT_UI_BOLD, bg=C["surface_dim"], fg=C["text"],
            relief="flat", bd=0, cursor="hand2", padx=sc(8), pady=sc(3),
            highlightthickness=1, highlightbackground=C["border"]
        )
        self.btn_first.pack(side="left", padx=(0, sc(4)))

        self.btn_prev = tk.Button(
            nav_frame, text="◀ Prev", command=self._goto_prev_page,
            font=FONT_UI_BOLD, bg=C["surface_dim"], fg=C["text"],
            relief="flat", bd=0, cursor="hand2", padx=sc(10), pady=sc(3),
            highlightthickness=1, highlightbackground=C["border"]
        )
        self.btn_prev.pack(side="left", padx=(0, sc(8)))

        self.page_num_label = tk.Label(
            nav_frame,
            text="Page 1 of 1",
            font=FONT_MONO_SM,
            fg=C["text_muted"],
            bg=C["surface"]
        )
        self.page_num_label.pack(side="left", padx=sc(4))

        self.btn_next = tk.Button(
            nav_frame, text="Next ▶", command=self._goto_next_page,
            font=FONT_UI_BOLD, bg=C["surface_dim"], fg=C["text"],
            relief="flat", bd=0, cursor="hand2", padx=sc(10), pady=sc(3),
            highlightthickness=1, highlightbackground=C["border"]
        )
        self.btn_next.pack(side="left", padx=(sc(8), sc(4)))

        self.btn_last = tk.Button(
            nav_frame, text="⏭", command=self._goto_last_page,
            font=FONT_UI_BOLD, bg=C["surface_dim"], fg=C["text"],
            relief="flat", bd=0, cursor="hand2", padx=sc(8), pady=sc(3),
            highlightthickness=1, highlightbackground=C["border"]
        )
        self.btn_last.pack(side="left", padx=(0, sc(12)))

        # Per-page selector
        tk.Label(nav_frame, text="Per page:", font=FONT_MONO_SM, fg=C["text_muted"], bg=C["surface"]).pack(side="left")
        self.page_size_var = tk.StringVar(value=str(self.page_size))
        ps_combo = ttk.Combobox(nav_frame, textvariable=self.page_size_var, values=["25", "50", "100"], state="readonly", width=4, font=FONT_MONO_SM)
        ps_combo.pack(side="left", padx=(sc(4), 0))
        ps_combo.bind("<<ComboboxSelected>>", self._on_page_size_changed)

        # Scrollable Canvas for Specimen Cards
        self.canvas = tk.Canvas(right_area, bg=C["bg"], highlightthickness=0)
        self.scrollbar = ttk.Scrollbar(right_area, orient="vertical", command=self.canvas.yview)
        self.cards_frame = tk.Frame(self.canvas, bg=C["bg"], padx=sc(16), pady=sc(14))

        self.cards_frame.bind(
            "<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")) if e.widget == self.cards_frame else None
        )
        self.canvas_window = self.canvas.create_window((0, 0), window=self.cards_frame, anchor="nw")
        self.canvas.bind("<Configure>", lambda e: self.canvas.itemconfig(self.canvas_window, width=e.width))

        self.canvas.pack(side="left", fill="both", expand=True)
        self.scrollbar.pack(side="right", fill="y")
        self.canvas.configure(yscrollcommand=self.scrollbar.set)

        self._bind_mousewheel_recursive(right_area, self._on_main_mousewheel)
        self._bind_mousewheel_recursive(self.cards_frame, self._on_main_mousewheel)
        right_area.bind("<Enter>", lambda e: self._set_active_scroll_target("main"), add="+")
        self.canvas.bind("<Enter>", lambda e: self._set_active_scroll_target("main"), add="+")
        self.cards_frame.bind("<Enter>", lambda e: self._set_active_scroll_target("main"), add="+")

    def _show_toast(self, message: str, level: str = "success"):
        C = self.colors
        if not hasattr(self, "toast_frame") or not self.toast_frame.winfo_exists():
            return

        if level == "undo" or level == "warning":
            toast_bg = C["warning_bg"]
            toast_fg = C["warning"]
            toast_border = C["warning"]
            icon_char = "⎌"
        elif level == "info":
            toast_bg = C["surface"]
            toast_fg = C["text"]
            toast_border = C["border"]
            icon_char = "ℹ"
        else:
            toast_bg = C["success_bg"]
            toast_fg = C["success_text"]
            toast_border = C["success_border"]
            icon_char = "✓"

        self.toast_frame.config(bg=toast_bg, highlightbackground=toast_border)
        self.toast_icon.config(text=icon_char, fg=toast_fg, bg=toast_bg)
        self.toast_label.config(text=message, fg=toast_fg, bg=toast_bg)
        self.toast_close.config(fg=toast_fg, bg=toast_bg)

        # Place floating overlay at top center over z-stack
        self.toast_frame.place(relx=0.5, y=sc(52), anchor="n")
        self.toast_frame.lift()

        # Reset timer
        if hasattr(self, "_toast_timer") and self._toast_timer is not None:
            try:
                self.after_cancel(self._toast_timer)
            except Exception:
                pass
        self._toast_timer = self.after(3500, self._hide_toast)

    def _hide_toast(self):
        if hasattr(self, "toast_frame") and self.toast_frame.winfo_exists():
            self.toast_frame.place_forget()
        self._toast_timer = None

    def _set_category_tab(self, tab_key: str):
        self.category_tab = tab_key
        self.current_page = 0
        # Sync status_var for compatibility
        if tab_key == "verified":
            self.status_var.set("✓ Verified in Books")
        elif tab_key == "synonym":
            self.status_var.set("Synonyms")
        elif tab_key == "accepted":
            self.status_var.set("Accepted / Spelling")
        elif tab_key == "applied":
            self.status_var.set("Applied")
        else:
            self.status_var.set("All")

        self._update_tab_buttons()
        self._render_current_page()

    def _update_tab_buttons(self):
        C = self.colors
        counts = self._get_tab_counts()

        for tab_key, info in self.tab_buttons.items():
            btn = info["btn"]
            prefix = info["prefix"]
            cnt = counts.get(tab_key, 0)
            btn.config(text=f"{prefix} ({cnt})")

            is_active = (self.category_tab == tab_key)
            if is_active:
                btn.config(
                    bg=C["header_bg"],
                    fg="#ffffff",
                    font=FONT_UI_BOLD,
                    highlightbackground=C["primary"]
                )
            else:
                btn.config(
                    bg=C["surface"],
                    fg=C["text"],
                    font=FONT_UI,
                    highlightbackground=C["border"]
                )

    def _update_sidebar_item(self, oid: str):
        """Update a specimen's sidebar badge and accent strip dynamically based on selection and applied state."""
        C = self.colors
        if oid in self.specimen_dir_widgets:
            info = self.specimen_dir_widgets[oid]
            tag_lbl = info["tag_lbl"]
            accent_bar = info["accent_bar"]
            status = info["status"]
            diff = self.oid_to_diff.get(oid, {})
            changes = diff.get("changes", [])
            total_cnt = len(changes)
            applied_cnt = sum(1 for chg in changes if (str(oid), chg["field"]) in self.applied_changes)

            if applied_cnt == total_cnt and total_cnt > 0:
                tag_lbl.config(text="✓ APPLIED", fg=C["success_text"])
                accent_bar.config(bg=C["success"])
                return

            unapplied_changes = [chg for chg in changes if (str(oid), chg["field"]) not in self.applied_changes]
            sel_cnt = sum(1 for chg in unapplied_changes if self.selection_state.get((str(oid), chg["field"]), True))
            accent_color = C["warning"] if status == "SYNONYM" else C["success"]

            if applied_cnt > 0:
                tag_lbl.config(text=f"PARTIAL ({applied_cnt}/{total_cnt})", fg=C["warning"])
                accent_bar.config(bg=C["warning"])
            elif sel_cnt == 0:
                tag_lbl.config(text="SKIPPED", fg=C["text_muted"])
                accent_bar.config(bg=C["border"])
            elif sel_cnt < len(unapplied_changes):
                tag_lbl.config(text=f"{status.upper()} ({sel_cnt}/{len(unapplied_changes)})", fg=accent_color)
                accent_bar.config(bg=accent_color)
            else:
                tag_lbl.config(text=status.upper(), fg=accent_color)
                accent_bar.config(bg=accent_color)

    def _select_card_fields(self, oid: str, mode: str = "all"):
        diff = self.oid_to_diff.get(oid, {})
        changes = diff.get("changes", [])
        for chg in changes:
            field = chg["field"]
            key = (str(oid), field)
            if key in self.applied_changes:
                continue
            if mode == "all":
                val = True
            elif mode == "none":
                val = False
            elif mode == "verified":
                val = bool(find_book_matches_for_gbif(self.app_state, str(oid), field, chg.get("new", "")))
            else:
                val = True
            self.selection_state[key] = val
            if key in self.page_field_vars:
                self.page_field_vars[key].set(val)
        self._update_sidebar_item(oid)
        self._update_summary()

    def _update_field_row_ui(self, oid: str, field: str):
        C = self.colors
        key = (str(oid), field)
        w = self.field_row_widgets.get(key)
        if not w:
            return

        is_field_applied = key in self.applied_changes
        old_val = w["old_val"]
        new_val = w["new_val"]
        matching_books = w["matching_books"]
        badge_code = w["badge_code"]
        badge_color = w["badge_color"]

        # 1. Update Checkbox
        chk = w["chk"]
        if is_field_applied:
            chk.config(
                fg=C["text_muted"],
                state="disabled",
                cursor="arrow"
            )
        else:
            chk.config(
                fg=C["text"],
                state="normal",
                cursor="hand2"
            )

        # 2. Rebuild Button Box
        btn_box = w["btn_box"]
        for child in btn_box.winfo_children():
            child.destroy()

        if is_field_applied:
            btn_undo = tk.Button(
                btn_box,
                text="⎌ Undo",
                command=lambda o=oid, f=field, ov=old_val, nv=new_val: self._undo_single_field(o, f, ov, nv),
                font=FONT_MONO_SM,
                bg=C["surface_dim"],
                fg=C["warning"],
                activebackground=C["warning_bg"],
                relief="solid",
                bd=1,
                cursor="hand2",
                padx=sc(6),
                pady=sc(1),
                highlightthickness=1,
                highlightbackground=C["warning"]
            )
            btn_undo.pack(side="right", padx=(sc(6), 0))

            lbl_applied = tk.Label(
                btn_box,
                text="✓ APPLIED TO DATABASE",
                font=FONT_MONO_SM,
                fg=C["success_text"],
                bg=C["success_bg"],
                padx=sc(6),
                pady=sc(2),
                highlightthickness=1,
                highlightbackground=C["success_border"]
            )
            lbl_applied.pack(side="right", padx=(sc(6), 0))
        else:
            btn_apply_field = tk.Button(
                btn_box,
                text="✓ Apply Field",
                command=lambda o=oid, f=field, ov=old_val, nv=new_val: self._apply_single_field(o, f, ov, nv),
                font=FONT_UI_BOLD,
                bg=C["surface_dim"],
                fg=C["success_text"],
                activebackground=C["success_bg"],
                relief="solid",
                bd=1,
                cursor="hand2",
                padx=sc(8),
                pady=sc(1),
                highlightthickness=1,
                highlightbackground=C["success_border"]
            )
            btn_apply_field.pack(side="right", padx=(sc(6), 0))

        lbl_badge = tk.Label(
            btn_box,
            text=badge_code,
            font=FONT_MONO_SM,
            fg="#ffffff",
            bg=badge_color,
            padx=sc(6),
            pady=sc(1)
        )
        lbl_badge.pack(side="right")

        # 3. Update Suggestion Box & Label
        sug_box = w["sug_box"]
        sug_lbl = w["sug_lbl"]
        if is_field_applied:
            sug_box.config(
                bg=C["surface_dim"],
                highlightbackground=C["border"],
                cursor="arrow"
            )
            sug_lbl.config(
                fg=C["text_muted"],
                bg=C["surface_dim"],
                cursor="arrow"
            )
        else:
            sug_box.config(
                bg=C["success_bg"],
                highlightbackground=C["success_border"],
                cursor="hand2"
            )
            sug_lbl.config(
                fg=C["success_text"],
                bg=C["success_bg"],
                cursor="hand2"
            )

        if "extra_badge" in w and w["extra_badge"] and w["extra_badge"].winfo_exists():
            w["extra_badge"].destroy()

        def _toggle_box(k=key, v=w["var"], target_oid=oid):
            if k in self.applied_changes:
                return
            v.set(not v.get())
            self.selection_state[k] = v.get()
            self._update_sidebar_item(target_oid)
            self._update_summary()

        if matching_books:
            book_badge_text = f"🌟 In Books: {matching_books[0].replace('Books: ', '')}"
            book_badge = tk.Label(
                sug_box,
                text=book_badge_text,
                font=FONT_MONO_SM,
                fg="#ffffff" if not is_field_applied else C["text_muted"],
                bg=C["success_border"] if not is_field_applied else C["surface_dim"],
                padx=sc(6),
                pady=sc(1),
                cursor="hand2" if not is_field_applied else "arrow"
            )
            book_badge.pack(side="right", padx=(sc(6), 0))
            book_badge.bind("<Button-1>", lambda e, f=_toggle_box: f())
            w["extra_badge"] = book_badge
        else:
            tag_lbl = tk.Label(
                sug_box,
                text="[GBIF Backbone]",
                font=FONT_MONO_SM,
                fg=C["success_border"] if not is_field_applied else C["text_muted"],
                bg=C["success_bg"] if not is_field_applied else C["surface_dim"],
                cursor="hand2" if not is_field_applied else "arrow"
            )
            tag_lbl.pack(side="right")
            tag_lbl.bind("<Button-1>", lambda e, f=_toggle_box: f())
            w["extra_badge"] = tag_lbl

    def _update_card_header_ui(self, oid: str):
        C = self.colors
        hw = self.card_header_widgets.get(str(oid))
        if not hw:
            return

        diff = hw["diff"]
        changes = diff.get("changes", [])
        status = diff.get("status", "ACCEPTED")
        match_type = diff.get("match_type", "MATCH")

        applied_chgs = [chg for chg in changes if (str(oid), chg["field"]) in self.applied_changes]
        unapplied_chgs = [chg for chg in changes if (str(oid), chg["field"]) not in self.applied_changes]
        is_fully_applied = len(applied_chgs) == len(changes) and len(changes) > 0
        is_partially_applied = len(applied_chgs) > 0 and not is_fully_applied

        book_matched_fields = [chg for chg in changes if find_book_matches_for_gbif(self.app_state, str(oid), chg["field"], chg.get("new", ""))]
        has_books = len(book_matched_fields) > 0

        hdr_right_box = hw["hdr_right_box"]
        for child in hdr_right_box.winfo_children():
            child.destroy()

        card_ctrls = tk.Frame(hdr_right_box, bg=C["header_bg"])
        card_ctrls.pack(side="left", padx=(0, sc(10)))

        if not is_fully_applied and len(unapplied_chgs) > 0:
            btn_all = tk.Button(
                card_ctrls, text="All", command=lambda o=oid: self._select_card_fields(o, "all"),
                font=FONT_MONO_SM, bg=C["surface_dim"], fg=C["text"], relief="flat", bd=0, cursor="hand2", padx=sc(5), pady=sc(1)
            )
            btn_all.pack(side="left", padx=(0, sc(2)))

            if has_books:
                btn_ver = tk.Button(
                    card_ctrls, text="Verified", command=lambda o=oid: self._select_card_fields(o, "verified"),
                    font=FONT_MONO_SM, bg=C["surface_dim"], fg=C["success_text"], relief="flat", bd=0, cursor="hand2", padx=sc(5), pady=sc(1)
                )
                btn_ver.pack(side="left", padx=(0, sc(2)))

            btn_none = tk.Button(
                card_ctrls, text="None", command=lambda o=oid: self._select_card_fields(o, "none"),
                font=FONT_MONO_SM, bg=C["surface_dim"], fg=C["text_muted"], relief="flat", bd=0, cursor="hand2", padx=sc(5), pady=sc(1)
            )
            btn_none.pack(side="left", padx=(0, sc(6)))

            btn_apply_card = tk.Button(
                card_ctrls,
                text="✓ Apply Remaining" if is_partially_applied else "✓ Apply Specimen",
                command=lambda o=oid: self._apply_specimen(o),
                font=FONT_UI_BOLD, bg=C["success"], fg="#ffffff", relief="flat", bd=0, cursor="hand2", padx=sc(8), pady=sc(2)
            )
            btn_apply_card.pack(side="left")

        if len(applied_chgs) > 0:
            btn_undo_card = tk.Button(
                card_ctrls,
                text="⎌ Undo Specimen",
                command=lambda o=oid: self._undo_specimen(o),
                font=FONT_UI_BOLD, bg=C["surface_dim"], fg=C["warning"], relief="flat", bd=0, cursor="hand2", padx=sc(8), pady=sc(2)
            )
            btn_undo_card.pack(side="left", padx=(sc(4), 0))

        if has_books:
            book_pill_bg = C["success"] if len(book_matched_fields) == len(changes) else C["warning"]
            book_pill_fg = "#ffffff" if len(book_matched_fields) == len(changes) else "#000000"
            tk.Label(
                hdr_right_box,
                text=f"🌟 {len(book_matched_fields)}/{len(changes)} Books",
                font=FONT_MONO_SM,
                fg=book_pill_fg,
                bg=book_pill_bg,
                padx=sc(6),
                pady=sc(2)
            ).pack(side="left", padx=(0, sc(6)))

        if is_fully_applied:
            badge_bg = C["success"]
            badge_fg = "#ffffff"
            badge_lbl_text = "[✓ ALL APPLIED]"
        elif is_partially_applied:
            badge_bg = C["warning"]
            badge_fg = "#000000"
            badge_lbl_text = f"[PARTIAL {len(applied_chgs)}/{len(changes)}]"
        else:
            badge_bg = C["warning"] if status == "SYNONYM" else (C["surface_dim"] if self.is_dark else "#444748")
            badge_fg = "#000000" if status == "SYNONYM" else "#ffffff"
            badge_lbl_text = f"[{status} | {match_type}]"

        tk.Label(
            hdr_right_box,
            text=badge_lbl_text,
            font=FONT_MONO_SM,
            fg=badge_fg,
            bg=badge_bg,
            padx=sc(8),
            pady=sc(2)
        ).pack(side="left")

    def _update_specimen_ui_in_place(self, oid: str):
        diff = self.oid_to_diff.get(str(oid), {})
        changes = diff.get("changes", [])
        for chg in changes:
            field = chg.get("field", "")
            self._update_field_row_ui(str(oid), field)
        self._update_card_header_ui(str(oid))
        self._update_sidebar_item(str(oid))
        self._update_tab_buttons()
        self._update_summary()
        self._update_selection_buttons()

    def _apply_single_field(self, oid: str, field: str, old_val: str, new_val: str):
        with self.app_state.df_lock:
            if self.app_state.df_reg is None:
                messagebox.showerror("Error", "No active database loaded.", parent=self)
                return
            reg_oid = self._find_reg_oid(oid)
            if reg_oid is None:
                messagebox.showerror("Error", f"Specimen #{oid} not found in database.", parent=self)
                return

            if field in self.app_state.df_reg.columns:
                self.app_state.df_reg.at[reg_oid, field] = new_val

            prob_changed = []
            prob_diffs = []
            df_obs = getattr(self.app_state, "df_obs", None)
            problem_to_field = self._get_problem_to_field_map()
            if df_obs is not None and problem_to_field:
                for pc, mf in problem_to_field.items():
                    if mf.lower().replace("_", " ").strip() == field.lower().replace("_", " ").strip():
                        if reg_oid in df_obs.index and pc in df_obs.columns:
                            val = df_obs.at[reg_oid, pc]
                            if pd.notna(val) and bool(val):
                                df_obs.at[reg_oid, pc] = False
                                prob_changed.append(pc)
                                prob_diffs.append(f'{pc}: "True" -> "False"')

            ts = datetime.now().isoformat(timespec="seconds")
            user_name = getpass.getuser()
            excel_p = getattr(self.app_state, "excel_path", "") or ""
            out_p = getattr(self.app_state, "output_path", "") or excel_p
            log_entry = {
                "Timestamp": ts,
                "User": user_name,
                "Action": "GBIF_UPDATE",
                "ObjectID": str(oid),
                "Reviewed": "",
                "ChangedFields": field,
                "ChangedValues": f'{field}: "{old_val}" -> "{new_val}"',
                "ProblemsChanged": ", ".join(prob_changed),
                "ProblemsChangedValues": " | ".join(prob_diffs),
                "LocationChanged": "",
                "LocationChangedValues": "",
                "SourceFile": os.path.basename(excel_p),
                "OutputFile": os.path.basename(out_p)
            }
            if not hasattr(self.app_state, "_log_records") or not self.app_state._log_records:
                df_log = getattr(self.app_state, "df_log", None)
                if df_log is not None and not df_log.empty:
                    self.app_state._log_records = df_log.to_dict(orient="records")
                else:
                    self.app_state._log_records = []
            self.app_state._log_records.append(log_entry)
            from repository import _normalise_log_dataframe
            self.app_state.df_log = _normalise_log_dataframe(pd.DataFrame(self.app_state._log_records))
            self.app_state.dirty = True

            self.applied_changes.add((str(oid), field))

        if self.on_applied_callback:
            try:
                self.on_applied_callback(1, 1)
            except Exception:
                pass

        self._show_toast(f"✓ Applied {field}: '{old_val}' → '{new_val}' for Specimen #{oid}", level="success")
        self._update_specimen_ui_in_place(oid)

    def _undo_single_field(self, oid: str, field: str, old_val: str, new_val: str):
        with self.app_state.df_lock:
            if self.app_state.df_reg is None:
                messagebox.showerror("Error", "No active database loaded.", parent=self)
                return
            reg_oid = self._find_reg_oid(oid)
            if reg_oid is None:
                messagebox.showerror("Error", f"Specimen #{oid} not found in database.", parent=self)
                return

            if field in self.app_state.df_reg.columns:
                self.app_state.df_reg.at[reg_oid, field] = old_val

            prob_changed = []
            prob_diffs = []
            df_obs = getattr(self.app_state, "df_obs", None)
            problem_to_field = self._get_problem_to_field_map()
            if df_obs is not None and problem_to_field:
                for pc, mf in problem_to_field.items():
                    if mf.lower().replace("_", " ").strip() == field.lower().replace("_", " ").strip():
                        if reg_oid in df_obs.index and pc in df_obs.columns:
                            df_obs.at[reg_oid, pc] = True
                            prob_changed.append(pc)
                            prob_diffs.append(f'{pc}: "False" -> "True"')

            ts = datetime.now().isoformat(timespec="seconds")
            user_name = getpass.getuser()
            excel_p = getattr(self.app_state, "excel_path", "") or ""
            out_p = getattr(self.app_state, "output_path", "") or excel_p
            log_entry = {
                "Timestamp": ts,
                "User": user_name,
                "Action": "GBIF_UNDO",
                "ObjectID": str(oid),
                "Reviewed": "",
                "ChangedFields": field,
                "ChangedValues": f'{field}: "{new_val}" -> "{old_val}"',
                "ProblemsChanged": ", ".join(prob_changed),
                "ProblemsChangedValues": " | ".join(prob_diffs),
                "LocationChanged": "",
                "LocationChangedValues": "",
                "SourceFile": os.path.basename(excel_p),
                "OutputFile": os.path.basename(out_p)
            }
            if not hasattr(self.app_state, "_log_records") or not self.app_state._log_records:
                df_log = getattr(self.app_state, "df_log", None)
                if df_log is not None and not df_log.empty:
                    self.app_state._log_records = df_log.to_dict(orient="records")
                else:
                    self.app_state._log_records = []
            self.app_state._log_records.append(log_entry)
            from repository import _normalise_log_dataframe
            self.app_state.df_log = _normalise_log_dataframe(pd.DataFrame(self.app_state._log_records))
            self.app_state.dirty = True

            self.applied_changes.discard((str(oid), field))
            self.selection_state[(str(oid), field)] = True
            if (str(oid), field) in self.page_field_vars:
                self.page_field_vars[(str(oid), field)].set(True)

        self._show_toast(f"⎌ Undid {field} update for Specimen #{oid} (reverted to '{old_val}')", level="undo")
        self._update_specimen_ui_in_place(oid)

    def _apply_specimen(self, oid: str):
        diff = self.oid_to_diff.get(oid, {})
        changes = diff.get("changes", [])
        to_apply = [
            chg for chg in changes
            if (str(oid), chg["field"]) not in self.applied_changes and self.selection_state.get((str(oid), chg["field"]), True)
        ]
        if not to_apply:
            messagebox.showinfo("No Changes Selected", f"No unapplied changes selected for Specimen #{oid}.", parent=self)
            return

        with self.app_state.df_lock:
            if self.app_state.df_reg is None:
                messagebox.showerror("Error", "No active database loaded.", parent=self)
                return
            reg_oid = self._find_reg_oid(oid)
            if reg_oid is None:
                messagebox.showerror("Error", f"Specimen #{oid} not found in database.", parent=self)
                return

            changed_fields = []
            changed_diffs = []
            prob_changed = []
            prob_diffs = []
            df_obs = getattr(self.app_state, "df_obs", None)
            problem_to_field = self._get_problem_to_field_map()

            for item in to_apply:
                f = item["field"]
                new_v = item["new"]
                old_v = item["old"]
                if f in self.app_state.df_reg.columns:
                    self.app_state.df_reg.at[reg_oid, f] = new_v
                    changed_fields.append(f)
                    changed_diffs.append(f'{f}: "{old_v}" -> "{new_v}"')
                    self.applied_changes.add((str(oid), f))

            if df_obs is not None and problem_to_field:
                for f in changed_fields:
                    for pc, mf in problem_to_field.items():
                        if mf.lower().replace("_", " ").strip() == f.lower().replace("_", " ").strip():
                            if reg_oid in df_obs.index and pc in df_obs.columns:
                                val = df_obs.at[reg_oid, pc]
                                if pd.notna(val) and bool(val):
                                    df_obs.at[reg_oid, pc] = False
                                    if pc not in prob_changed:
                                        prob_changed.append(pc)
                                        prob_diffs.append(f'{pc}: "True" -> "False"')

            if changed_fields or prob_changed:
                ts = datetime.now().isoformat(timespec="seconds")
                user_name = getpass.getuser()
                excel_p = getattr(self.app_state, "excel_path", "") or ""
                out_p = getattr(self.app_state, "output_path", "") or excel_p
                log_entry = {
                    "Timestamp": ts,
                    "User": user_name,
                    "Action": "GBIF_UPDATE",
                    "ObjectID": str(oid),
                    "Reviewed": "",
                    "ChangedFields": ", ".join(changed_fields),
                    "ChangedValues": " | ".join(changed_diffs),
                    "ProblemsChanged": ", ".join(prob_changed),
                    "ProblemsChangedValues": " | ".join(prob_diffs),
                    "LocationChanged": "",
                    "LocationChangedValues": "",
                    "SourceFile": os.path.basename(excel_p),
                    "OutputFile": os.path.basename(out_p)
                }
                if not hasattr(self.app_state, "_log_records") or not self.app_state._log_records:
                    df_log = getattr(self.app_state, "df_log", None)
                    if df_log is not None and not df_log.empty:
                        self.app_state._log_records = df_log.to_dict(orient="records")
                    else:
                        self.app_state._log_records = []
                self.app_state._log_records.append(log_entry)
                from repository import _normalise_log_dataframe
                self.app_state.df_log = _normalise_log_dataframe(pd.DataFrame(self.app_state._log_records))
                self.app_state.dirty = True

        if self.on_applied_callback:
            try:
                self.on_applied_callback(len(changed_fields), 1)
            except Exception:
                pass

        self._show_toast(f"✓ Applied {len(changed_fields)} updates for Specimen #{oid}", level="success")
        self._update_specimen_ui_in_place(oid)

    def _undo_specimen(self, oid: str):
        diff = self.oid_to_diff.get(str(oid), {})
        changes = diff.get("changes", [])
        applied_to_undo = [
            chg for chg in changes
            if (str(oid), chg["field"]) in self.applied_changes
        ]
        if not applied_to_undo:
            messagebox.showinfo("No Applied Changes", f"No applied changes to undo for Specimen #{oid}.", parent=self)
            return

        with self.app_state.df_lock:
            if self.app_state.df_reg is None:
                messagebox.showerror("Error", "No active database loaded.", parent=self)
                return
            reg_oid = self._find_reg_oid(oid)
            if reg_oid is None:
                messagebox.showerror("Error", f"Specimen #{oid} not found in database.", parent=self)
                return

            changed_fields = []
            changed_diffs = []
            prob_changed = []
            prob_diffs = []
            df_obs = getattr(self.app_state, "df_obs", None)
            problem_to_field = self._get_problem_to_field_map()

            for item in applied_to_undo:
                f = item["field"]
                new_v = item["new"]
                old_v = item["old"]
                if f in self.app_state.df_reg.columns:
                    self.app_state.df_reg.at[reg_oid, f] = old_v
                    changed_fields.append(f)
                    changed_diffs.append(f'{f}: "{new_v}" -> "{old_v}"')
                    self.applied_changes.discard((str(oid), f))
                    self.selection_state[(str(oid), f)] = True
                    if (str(oid), f) in self.page_field_vars:
                        self.page_field_vars[(str(oid), f)].set(True)

            if df_obs is not None and problem_to_field:
                for f in changed_fields:
                    for pc, mf in problem_to_field.items():
                        if mf.lower().replace("_", " ").strip() == f.lower().replace("_", " ").strip():
                            if reg_oid in df_obs.index and pc in df_obs.columns:
                                df_obs.at[reg_oid, pc] = True
                                if pc not in prob_changed:
                                    prob_changed.append(pc)
                                    prob_diffs.append(f'{pc}: "False" -> "True"')

            if changed_fields or prob_changed:
                ts = datetime.now().isoformat(timespec="seconds")
                user_name = getpass.getuser()
                excel_p = getattr(self.app_state, "excel_path", "") or ""
                out_p = getattr(self.app_state, "output_path", "") or excel_p
                log_entry = {
                    "Timestamp": ts,
                    "User": user_name,
                    "Action": "GBIF_UNDO",
                    "ObjectID": str(oid),
                    "Reviewed": "",
                    "ChangedFields": ", ".join(changed_fields),
                    "ChangedValues": " | ".join(changed_diffs),
                    "ProblemsChanged": ", ".join(prob_changed),
                    "ProblemsChangedValues": " | ".join(prob_diffs),
                    "LocationChanged": "",
                    "LocationChangedValues": "",
                    "SourceFile": os.path.basename(excel_p),
                    "OutputFile": os.path.basename(out_p)
                }
                if not hasattr(self.app_state, "_log_records") or not self.app_state._log_records:
                    df_log = getattr(self.app_state, "df_log", None)
                    if df_log is not None and not df_log.empty:
                        self.app_state._log_records = df_log.to_dict(orient="records")
                    else:
                        self.app_state._log_records = []
                self.app_state._log_records.append(log_entry)
                from repository import _normalise_log_dataframe
                self.app_state.df_log = _normalise_log_dataframe(pd.DataFrame(self.app_state._log_records))
                self.app_state.dirty = True

        self._show_toast(f"⎌ Undid {len(changed_fields)} updates for Specimen #{oid}", level="undo")
        self._update_specimen_ui_in_place(oid)

    def _render_current_page(self):
        C = self.colors

        # 1. Clear previous page widgets
        for child in self.dir_list.winfo_children():
            child.destroy()
        for child in self.cards_frame.winfo_children():
            child.destroy()

        self.item_cards.clear()
        self.specimen_frames.clear()
        self.specimen_dir_widgets.clear()
        self.page_field_vars.clear()
        self.field_row_widgets.clear()
        self.card_header_widgets.clear()

        # 2. Get filtered results and slice page
        filtered = self._get_filtered_results()
        total_items = len(filtered)
        total_pages = max(1, math.ceil(total_items / self.page_size))
        tab_counts = self._get_tab_counts()

        if self.current_page >= total_pages:
            self.current_page = max(0, total_pages - 1)

        start_idx = self.current_page * self.page_size
        end_idx = min(start_idx + self.page_size, total_items)
        page_items = filtered[start_idx:end_idx]

        # Update Navigation & Header Labels
        if total_items == 0:
            if tab_counts["pending"] == 0 and tab_counts["applied"] > 0:
                self.page_info_label.config(text="ALL BATCH RECONCILIATIONS COMPLETED!")
                # Render completion card
                comp_card = tk.Frame(self.cards_frame, bg=C["success_bg"], highlightbackground=C["success_border"], highlightthickness=1, padx=sc(24), pady=sc(24))
                comp_card.pack(fill="x", pady=sc(20))
                tk.Label(comp_card, text="🎉 ALL SPECIMEN UPDATES APPLIED!", font=FONT_UI_XL, fg=C["success_text"], bg=C["success_bg"]).pack(anchor="w")
                tk.Label(comp_card, text=f"Successfully resolved and saved changes across {tab_counts['applied']} specimens to your active database and audit log.", font=FONT_UI, fg=C["text"], bg=C["success_bg"]).pack(anchor="w", pady=(sc(6), sc(14)))
                tk.Button(comp_card, text="CLOSE & FINISH", font=FONT_UI_BOLD, bg=C["success"], fg="#ffffff", relief="flat", bd=0, padx=sc(16), pady=sc(6), command=self.destroy, cursor="hand2").pack(anchor="w")
            else:
                self.page_info_label.config(text="NO MATCHING SPECIMENS IN THIS VIEW.")
                empty_card = tk.Frame(self.cards_frame, bg=C["surface"], highlightbackground=C["border"], highlightthickness=1, padx=sc(20), pady=sc(20))
                empty_card.pack(fill="x", pady=sc(20))
                tk.Label(empty_card, text="No specimens match the active filter or search.", font=FONT_UI_BOLD, fg=C["text_muted"], bg=C["surface"]).pack(anchor="w")

            self.page_num_label.config(text="Page 0 of 0")
            self.btn_first.config(state="disabled")
            self.btn_prev.config(state="disabled")
            self.btn_next.config(state="disabled")
            self.btn_last.config(state="disabled")
        else:
            self.page_info_label.config(
                text=f"SHOWING SPECIMENS {start_idx + 1}–{end_idx} OF {total_items} (CATEGORY TOTAL: {total_items})"
            )
            self.page_num_label.config(text=f"Page {self.current_page + 1} of {total_pages}")
            self.btn_first.config(state="normal" if self.current_page > 0 else "disabled")
            self.btn_prev.config(state="normal" if self.current_page > 0 else "disabled")
            self.btn_next.config(state="normal" if self.current_page < total_pages - 1 else "disabled")
            self.btn_last.config(state="normal" if self.current_page < total_pages - 1 else "disabled")

        self.dir_title_label.config(text=f"PAGE SPECIMENS ({len(page_items)})")

        # 3. Populate Directory and Specimen Cards for Current Page
        for diff in page_items:
            oid = str(diff.get("oid", ""))
            status = diff.get("status", "ACCEPTED")
            changes = diff.get("changes", [])
            title_info = self._get_specimen_title_info(diff)

            applied_chgs = [chg for chg in changes if (oid, chg["field"]) in self.applied_changes]
            unapplied_chgs = [chg for chg in changes if (oid, chg["field"]) not in self.applied_changes]
            is_fully_applied = len(applied_chgs) == len(changes) and len(changes) > 0
            is_partially_applied = len(applied_chgs) > 0 and not is_fully_applied

            sel_cnt = sum(1 for chg in unapplied_chgs if self.selection_state.get((oid, chg["field"]), True))
            accent_color = C["warning"] if status == "SYNONYM" else C["success"]

            # Book Matches Count on Card
            book_matched_fields = [chg for chg in changes if find_book_matches_for_gbif(self.app_state, oid, chg["field"], chg.get("new", ""))]
            has_books = len(book_matched_fields) > 0

            if is_fully_applied:
                tag_text = "✓ APPLIED"
                tag_color = C["success_text"]
                bar_color = C["success"]
            elif is_partially_applied:
                tag_text = f"PARTIAL ({len(applied_chgs)}/{len(changes)})"
                tag_color = C["warning"]
                bar_color = C["warning"]
            elif sel_cnt == 0:
                tag_text = "SKIPPED"
                tag_color = C["text_muted"]
                bar_color = C["border"]
            elif sel_cnt < len(unapplied_chgs):
                tag_text = f"{status.upper()} ({sel_cnt}/{len(unapplied_chgs)})"
                tag_color = accent_color
                bar_color = accent_color
            else:
                tag_text = status.upper()
                tag_color = accent_color
                bar_color = accent_color

            # --- Left Directory Entry (2-Line Rich Entry) ---
            f_frame = tk.Frame(self.dir_list, bg=C["surface"], cursor="hand2")
            f_frame.pack(fill="x")
            tk.Frame(f_frame, bg=C["border"], height=sc(1)).pack(fill="x", side="bottom")

            # 4px Left Accent Strip
            accent_bar = tk.Frame(f_frame, bg=bar_color, width=sc(4))
            accent_bar.pack(side="left", fill="y")

            # Content container
            f_content = tk.Frame(f_frame, bg=C["surface"], padx=sc(8), pady=sc(6))
            f_content.pack(side="left", fill="x", expand=True)

            # Row 1: OID & Taxon
            r1 = tk.Frame(f_content, bg=C["surface"])
            r1.pack(fill="x")

            tk.Label(r1, text=f"#{oid}", font=FONT_MONO, fg=C["text"], bg=C["surface"]).pack(side="left")

            tax_disp = title_info["curr_tax"]
            if len(tax_disp) > 20:
                tax_disp = tax_disp[:18] + "…"
            tk.Label(r1, text=f"• {tax_disp}", font=FONT_UI_BOLD if not self.is_dark else FONT_UI, fg=C["text"], bg=C["surface"]).pack(side="left", padx=(sc(4), 0))

            if has_books:
                tk.Label(r1, text="🌟", font=FONT_MONO_SM, fg=C["warning"], bg=C["surface"]).pack(side="right")

            # Row 2: Change Count & Tag
            r2 = tk.Frame(f_content, bg=C["surface"])
            r2.pack(fill="x", pady=(sc(2), 0))

            tk.Label(r2, text=f"{len(changes)} chg", font=FONT_MONO_SM, fg=C["text_muted"], bg=C["surface"]).pack(side="left")
            tag_lbl = tk.Label(r2, text=tag_text, font=FONT_MONO_SM, fg=tag_color, bg=C["surface"])
            tag_lbl.pack(side="right")

            self.specimen_dir_widgets[oid] = {
                "tag_lbl": tag_lbl,
                "accent_bar": accent_bar,
                "status": status,
                "total_changes": len(changes)
            }

            def _scroll_to(target_oid=oid):
                if target_oid in self.item_cards:
                    card = self.item_cards[target_oid]
                    y = card.winfo_y()
                    if self.cards_frame.winfo_height() > 0:
                        self.canvas.yview_moveto(max(0, (y - 10) / self.cards_frame.winfo_height()))

            f_frame.bind("<Button-1>", lambda e, f=_scroll_to: f())
            f_content.bind("<Button-1>", lambda e, f=_scroll_to: f())
            r1.bind("<Button-1>", lambda e, f=_scroll_to: f())
            r2.bind("<Button-1>", lambda e, f=_scroll_to: f())
            for child in r1.winfo_children():
                child.bind("<Button-1>", lambda e, f=_scroll_to: f())
            for child in r2.winfo_children():
                child.bind("<Button-1>", lambda e, f=_scroll_to: f())

            self.specimen_frames[oid] = f_frame
            self._bind_mousewheel_recursive(f_frame, self._on_dir_mousewheel)

            # --- Right Card Frame ---
            card = tk.Frame(
                self.cards_frame,
                bg=C["surface"],
                highlightbackground=C["border"],
                highlightthickness=1
            )
            card.pack(fill="x", pady=(0, sc(12)))
            self.item_cards[oid] = card
            self._bind_mousewheel_recursive(card, self._on_main_mousewheel)

            # Solid Card Header Bar with Rich Taxon Title & Quick Actions
            c_header = tk.Frame(card, bg=C["header_bg"])
            c_header.pack(fill="x")

            hdr_left_box = tk.Frame(c_header, bg=C["header_bg"])
            hdr_left_box.pack(side="left", padx=sc(12), pady=sc(6))

            tk.Label(
                hdr_left_box,
                text=title_info["header_title"],
                font=FONT_UI_BOLD,
                fg="#ffffff",
                bg=C["header_bg"]
            ).pack(side="left")

            hdr_right_box = tk.Frame(c_header, bg=C["header_bg"])
            hdr_right_box.pack(side="right", padx=sc(12), pady=sc(6))

            self.card_header_widgets[oid] = {
                "hdr_right_box": hdr_right_box,
                "diff": diff
            }
            self._update_card_header_ui(oid)

            # Card Content Body
            card_body = tk.Frame(card, bg=C["surface"], padx=sc(16), pady=sc(12))
            card_body.pack(fill="x")

            # Field Rows
            for chg in changes:
                field = chg["field"]
                old_val = str(chg.get("old", ""))
                new_val = str(chg.get("new", ""))

                key = (oid, field)
                is_field_applied = key in self.applied_changes
                is_selected = self.selection_state.get(key, True)

                var = tk.BooleanVar(value=is_selected)
                self.page_field_vars[key] = var

                def _on_toggle(k=key, v=var, target_oid=oid):
                    self.selection_state[k] = v.get()
                    self._update_sidebar_item(target_oid)
                    self._update_summary()

                # Determine Domain Badge (TAX / PROV)
                field_upper = field.upper()
                badge_code = "TAX"
                badge_color = "#C62828"
                if "AUTHOR" in field_upper or "COLLECTOR" in field_upper:
                    badge_code = "PROV"
                    badge_color = "#D9A036"

                row_frame = tk.Frame(card_body, bg=C["surface"], pady=sc(4))
                row_frame.pack(fill="x", pady=(0, sc(8)))

                # Sub-header Row with Checkbox, Confidence Pill, Domain Badge & Inline Apply
                sub_hdr = tk.Frame(row_frame, bg=C["surface"])
                sub_hdr.pack(fill="x", pady=(0, sc(4)))

                chk = tk.Checkbutton(
                    sub_hdr,
                    text=f"FIELD: {field_upper}",
                    variable=var,
                    font=FONT_UI_BOLD,
                    fg=C["text"] if not is_field_applied else C["text_muted"],
                    bg=C["surface"],
                    activebackground=C["surface"],
                    activeforeground=C["primary"],
                    selectcolor=C["surface"],
                    cursor="hand2" if not is_field_applied else "arrow",
                    state="disabled" if is_field_applied else "normal",
                    command=_on_toggle
                )
                chk.pack(side="left")

                # Inline Apply Button / Undo / Applied Badge Container
                btn_box = tk.Frame(sub_hdr, bg=C["surface"])
                btn_box.pack(side="right")

                # Comparison Grid Frame
                grid_frame = tk.Frame(row_frame, bg=C["surface"])
                grid_frame.pack(fill="x")
                grid_frame.columnconfigure(0, weight=1)
                grid_frame.columnconfigure(1, weight=1)

                # 1. Current Value Container
                cur_col = tk.Frame(grid_frame, bg=C["surface"])
                cur_col.grid(row=0, column=0, sticky="nsew", padx=(0, sc(6)))

                tk.Label(
                    cur_col,
                    text="CURRENT_VALUE",
                    font=FONT_MONO_SM,
                    fg=C["text_muted"],
                    bg=C["surface"]
                ).pack(anchor="w", pady=(0, sc(2)))

                cur_box = tk.Frame(
                    cur_col,
                    bg=C["surface_dim"],
                    highlightbackground=C["border"],
                    highlightthickness=1,
                    padx=sc(10),
                    pady=sc(8)
                )
                cur_box.pack(fill="both", expand=True)

                cur_disp = old_val if old_val else "[BLANK]"
                cur_fg = C["text"] if old_val else C["text_muted"]
                tk.Label(
                    cur_box,
                    text=cur_disp,
                    font=FONT_MONO,
                    fg=cur_fg,
                    bg=C["surface_dim"],
                    anchor="w"
                ).pack(fill="x")

                # 2. GBIF Suggestion Container
                sug_col = tk.Frame(grid_frame, bg=C["surface"])
                sug_col.grid(row=0, column=1, sticky="nsew", padx=(sc(6), 0))

                tk.Label(
                    sug_col,
                    text="GBIF_SUGGESTION",
                    font=FONT_MONO_SM,
                    fg=C["text_muted"],
                    bg=C["surface"]
                ).pack(anchor="w", pady=(0, sc(2)))

                sug_box = tk.Frame(
                    sug_col,
                    bg=C["success_bg"] if not is_field_applied else C["surface_dim"],
                    highlightbackground=C["success_border"] if not is_field_applied else C["border"],
                    highlightthickness=1,
                    padx=sc(10),
                    pady=sc(8),
                    cursor="hand2" if not is_field_applied else "arrow"
                )
                sug_box.pack(fill="both", expand=True)

                def _toggle_box(k=key, v=var, target_oid=oid):
                    if k in self.applied_changes:
                        return
                    v.set(not v.get())
                    self.selection_state[k] = v.get()
                    self._update_sidebar_item(target_oid)
                    self._update_summary()

                sug_lbl = tk.Label(
                    sug_box,
                    text=new_val or "[BLANK]",
                    font=FONT_MONO,
                    fg=C["success_text"] if not is_field_applied else C["text_muted"],
                    bg=C["success_bg"] if not is_field_applied else C["surface_dim"],
                    anchor="w",
                    cursor="hand2" if not is_field_applied else "arrow"
                )
                sug_lbl.pack(side="left", fill="x", expand=True)

                sug_box.bind("<Button-1>", lambda e, f=_toggle_box: f())
                sug_lbl.bind("<Button-1>", lambda e, f=_toggle_box: f())

                matching_books = find_book_matches_for_gbif(self.app_state, oid, field, new_val)

                self.field_row_widgets[key] = {
                    "chk": chk,
                    "btn_box": btn_box,
                    "sug_box": sug_box,
                    "sug_lbl": sug_lbl,
                    "var": var,
                    "old_val": old_val,
                    "new_val": new_val,
                    "badge_code": badge_code,
                    "badge_color": badge_color,
                    "matching_books": matching_books,
                    "extra_badge": None
                }

                self._update_field_row_ui(oid, field)

        # Reset and configure scrollable areas
        self.dir_canvas.configure(scrollregion=self.dir_canvas.bbox("all"))
        self.dir_canvas.yview_moveto(0)
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        self.canvas.yview_moveto(0)
        self._update_summary()
        self._update_selection_buttons()

    def _goto_first_page(self):
        if self.current_page != 0:
            self.current_page = 0
            self._render_current_page()

    def _goto_prev_page(self):
        if self.current_page > 0:
            self.current_page -= 1
            self._render_current_page()

    def _goto_next_page(self):
        filtered = self._get_filtered_results()
        total_pages = max(1, math.ceil(len(filtered) / self.page_size))
        if self.current_page < total_pages - 1:
            self.current_page += 1
            self._render_current_page()

    def _goto_last_page(self):
        filtered = self._get_filtered_results()
        total_pages = max(1, math.ceil(len(filtered) / self.page_size))
        if self.current_page != total_pages - 1:
            self.current_page = total_pages - 1
            self._render_current_page()

    def _on_page_size_changed(self, event=None):
        try:
            new_size = int(self.page_size_var.get())
            if new_size > 0:
                self.page_size = new_size
                self.current_page = 0
                self._render_current_page()
        except Exception:
            pass

    def _on_search_changed(self):
        self.search_query = self.search_var.get()
        self.current_page = 0
        self._render_current_page()

    def _on_status_filter_changed(self, event=None):
        val = self.status_var.get()
        if "Verified" in val:
            self.category_tab = "verified"
        elif "Synonyms" in val:
            self.category_tab = "synonym"
        elif "Accepted" in val:
            self.category_tab = "accepted"
        elif "Applied" in val:
            self.category_tab = "applied"
        else:
            self.category_tab = "pending"
        self.current_page = 0
        self._update_tab_buttons()
        self._render_current_page()

    def _set_active_scroll_target(self, target: str):
        self._active_scroll_target = target

    def _on_routed_mousewheel(self, event):
        if not self.winfo_exists():
            return
        if getattr(self, "_active_scroll_target", "main") == "dir":
            self._on_dir_mousewheel(event)
        else:
            self._on_main_mousewheel(event)

    def _on_dir_mousewheel(self, event):
        if not hasattr(self, "dir_canvas") or not self.dir_canvas.winfo_exists():
            return
        if hasattr(event, "delta") and event.delta:
            self.dir_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        elif getattr(event, "num", None) == 4:
            self.dir_canvas.yview_scroll(-1, "units")
        elif getattr(event, "num", None) == 5:
            self.dir_canvas.yview_scroll(1, "units")

    def _on_main_mousewheel(self, event):
        if not hasattr(self, "canvas") or not self.canvas.winfo_exists():
            return
        if hasattr(event, "delta") and event.delta:
            self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        elif getattr(event, "num", None) == 4:
            self.canvas.yview_scroll(-1, "units")
        elif getattr(event, "num", None) == 5:
            self.canvas.yview_scroll(1, "units")

    def _on_dialog_destroy(self, event=None):
        if event and event.widget != self:
            return
        try:
            self.unbind_all("<MouseWheel>")
            self.unbind_all("<Button-4>")
            self.unbind_all("<Button-5>")
        except Exception:
            pass

    def _update_selection_buttons(self):
        if not hasattr(self, "sel_all_btn") or not self.sel_all_btn.winfo_exists():
            return
        filtered = self._get_filtered_results()
        is_filtered = (self.category_tab != "pending") or bool(self.search_query.strip())

        if is_filtered:
            self.sel_all_btn.config(
                text=f"Select Filtered ({len(filtered)})",
                command=self._select_filtered_batch
            )
            self.desel_all_btn.config(
                text="Deselect Filtered",
                command=self._deselect_filtered_batch
            )
        else:
            self.sel_all_btn.config(
                text=f"Select All (Batch)",
                command=self._select_all_batch
            )
            self.desel_all_btn.config(
                text="Deselect All",
                command=self._deselect_all_batch
            )

    def _select_all_batch(self):
        for k in self.selection_state.keys():
            if k not in self.applied_changes:
                self.selection_state[k] = True
        for (oid, field), var in self.page_field_vars.items():
            if (oid, field) not in self.applied_changes:
                var.set(True)
        for oid in self.specimen_dir_widgets.keys():
            self._update_sidebar_item(oid)
        self._update_summary()

    def _deselect_all_batch(self):
        for k in self.selection_state.keys():
            self.selection_state[k] = False
        for var in self.page_field_vars.values():
            var.set(False)
        for oid in self.specimen_dir_widgets.keys():
            self._update_sidebar_item(oid)
        self._update_summary()

    def _select_filtered_batch(self):
        filtered = self._get_filtered_results()
        for d in filtered:
            oid = str(d.get("oid", ""))
            for chg in d.get("changes", []):
                key = (oid, chg["field"])
                if key not in self.applied_changes:
                    self.selection_state[key] = True
        for (oid, field), var in self.page_field_vars.items():
            var.set(self.selection_state.get((oid, field), True))
        for oid in self.specimen_dir_widgets.keys():
            self._update_sidebar_item(oid)
        self._update_summary()

    def _deselect_filtered_batch(self):
        filtered = self._get_filtered_results()
        for d in filtered:
            oid = str(d.get("oid", ""))
            for chg in d.get("changes", []):
                self.selection_state[(oid, chg["field"])] = False
        for (oid, field), var in self.page_field_vars.items():
            var.set(self.selection_state.get((oid, field), False))
        for oid in self.specimen_dir_widgets.keys():
            self._update_sidebar_item(oid)
        self._update_summary()

    def _select_current_page(self):
        for (oid, field), var in self.page_field_vars.items():
            if (oid, field) not in self.applied_changes:
                self.selection_state[(oid, field)] = True
                var.set(True)
        for oid in self.specimen_dir_widgets.keys():
            self._update_sidebar_item(oid)
        self._update_summary()

    def _select_verified_only(self):
        filtered = self._get_filtered_results()
        for d in filtered:
            oid = str(d.get("oid", ""))
            for chg in d.get("changes", []):
                field = chg["field"]
                key = (oid, field)
                if key in self.applied_changes:
                    continue
                is_ver = bool(find_book_matches_for_gbif(self.app_state, oid, field, chg.get("new", "")))
                self.selection_state[key] = is_ver
        for (oid, field), var in self.page_field_vars.items():
            var.set(self.selection_state.get((oid, field), False))
        for oid in self.specimen_dir_widgets.keys():
            self._update_sidebar_item(oid)
        self._update_summary()

    def _update_summary(self):
        filtered = self._get_filtered_results()
        filtered_oids = {str(d.get("oid", "")) for d in filtered}

        # Count selected within current filtered view (only unapplied)
        filt_sel_count = sum(
            1 for (oid, f), v in self.selection_state.items()
            if v and oid in filtered_oids and (oid, f) in self.all_changes and (oid, f) not in self.applied_changes
        )
        filt_total_count = sum(
            sum(1 for chg in d.get("changes", []) if (str(d.get("oid", "")), chg["field"]) not in self.applied_changes)
            for d in filtered
        )
        filt_skipped = filt_total_count - filt_sel_count

        # Global unapplied count
        batch_sel_count = sum(
            1 for (oid, f), v in self.selection_state.items()
            if v and (oid, f) in self.all_changes and (oid, f) not in self.applied_changes
        )
        batch_total_count = sum(
            sum(1 for chg in d.get("changes", []) if (str(d.get("oid", "")), chg["field"]) not in self.applied_changes)
            for d in self.diff_results
        )

        tab_title = {
            "pending": "PENDING",
            "verified": "VERIFIED",
            "accepted": "SPELLING/ACCEPTED",
            "synonym": "SYNONYM",
            "applied": "APPLIED"
        }.get(self.category_tab, "FILTERED")

        applied_specimens_cnt = sum(1 for d in self.diff_results if self._diff_has_applied_changes(d))

        if self.category_tab == "applied":
            self.summary_label.config(text=f"Viewing {applied_specimens_cnt} applied specimens ({len(self.applied_changes)} updates recorded)")
            self.apply_btn.config(text="ALL APPLIED (VIEW ONLY)", state="disabled", bg=self.colors["surface_dim"], fg=self.colors["text_muted"])
        else:
            self.summary_label.config(
                text=f"Filtered: {filt_sel_count}/{filt_total_count} selected ({filt_skipped} skipped)  •  Batch Total: {batch_sel_count}/{batch_total_count} selected"
            )
            self.apply_btn.config(
                text=f"APPLY {filt_sel_count} [{tab_title}] UPDATES (CTRL+A)",
                state="normal" if filt_sel_count > 0 else "disabled",
                bg=self.colors["success"] if filt_sel_count > 0 else self.colors["surface_dim"],
                fg="#ffffff" if filt_sel_count > 0 else self.colors["text_muted"]
            )

    def _apply_selected(self):
        filtered = self._get_filtered_results()
        filtered_oids = {str(d.get("oid", "")) for d in filtered}

        # Apply selected changes belonging to the filtered view (unapplied only)
        selected_updates = [
            (oid, self.all_changes[(oid, field)])
            for (oid, field), is_sel in self.selection_state.items()
            if is_sel and (oid, field) in self.all_changes and oid in filtered_oids and (oid, field) not in self.applied_changes
        ]

        if not selected_updates:
            messagebox.showwarning(
                "No Changes Selected",
                "Please select at least one unapplied taxonomic update in the current view to apply.",
                parent=self
            )
            return

        with self.app_state.df_lock:
            if self.app_state.df_reg is None:
                messagebox.showerror("Error", "No active database loaded.", parent=self)
                return

            if not hasattr(self.app_state, "_log_records") or not self.app_state._log_records:
                df_log = getattr(self.app_state, "df_log", None)
                if df_log is not None and not df_log.empty:
                    self.app_state._log_records = df_log.to_dict(orient="records")
                else:
                    self.app_state._log_records = []

            problem_to_field = self._get_problem_to_field_map()

            # Group updates by oid
            by_oid = {}
            for oid, chg in selected_updates:
                by_oid.setdefault(oid, []).append(chg)

            applied_count = 0
            ts = datetime.now().isoformat(timespec="seconds")
            user_name = getpass.getuser()

            for oid, chg_list in by_oid.items():
                reg_oid = self._find_reg_oid(oid)
                if reg_oid is None:
                    continue

                changed_fields = []
                changed_diffs = []
                prob_changed = []
                prob_diffs = []

                for item in chg_list:
                    f = item["field"]
                    new_v = item["new"]
                    old_v = item["old"]

                    if f in self.app_state.df_reg.columns:
                        self.app_state.df_reg.at[reg_oid, f] = new_v
                        changed_fields.append(f)
                        changed_diffs.append(f'{f}: "{old_v}" -> "{new_v}"')
                        applied_count += 1
                        self.applied_changes.add((str(oid), f))

                # Auto-clear mapped problem flags
                df_obs = getattr(self.app_state, "df_obs", None)
                if df_obs is not None and problem_to_field:
                    for f in changed_fields:
                        for pc, mf in problem_to_field.items():
                            if mf.lower().replace("_", " ").strip() == f.lower().replace("_", " ").strip():
                                if reg_oid in df_obs.index and pc in df_obs.columns:
                                    val = df_obs.at[reg_oid, pc]
                                    if pd.notna(val) and bool(val):
                                        df_obs.at[reg_oid, pc] = False
                                        if pc not in prob_changed:
                                            prob_changed.append(pc)
                                            prob_diffs.append(f'{pc}: "True" -> "False"')

                if changed_fields or prob_changed:
                    excel_p = getattr(self.app_state, "excel_path", "") or ""
                    out_p = getattr(self.app_state, "output_path", "") or excel_p
                    log_entry = {
                        "Timestamp": ts,
                        "User": user_name,
                        "Action": "GBIF_UPDATE",
                        "ObjectID": str(oid),
                        "Reviewed": "",
                        "ChangedFields": ", ".join(changed_fields),
                        "ChangedValues": " | ".join(changed_diffs),
                        "ProblemsChanged": ", ".join(prob_changed),
                        "ProblemsChangedValues": " | ".join(prob_diffs),
                        "LocationChanged": "",
                        "LocationChangedValues": "",
                        "SourceFile": os.path.basename(excel_p),
                        "OutputFile": os.path.basename(out_p)
                    }
                    self.app_state._log_records.append(log_entry)

            self.app_state.df_log = pd.DataFrame(self.app_state._log_records)
            self.app_state.dirty = True

        if self.on_applied_callback:
            try:
                self.on_applied_callback(applied_count, len(by_oid))
            except Exception:
                pass

        # Show notification toast and stay open for continuous triage
        self._show_toast(f"✓ Successfully applied {applied_count} changes across {len(by_oid)} specimens to active database.", level="success")
        self._update_tab_buttons()
        self._render_current_page()




def rollback_gbif_updates(app_state, main_window=None):
    """
    Roll back the latest un-reverted GBIF_UPDATE batch by inspecting df_log.
    """
    with app_state.df_lock:
        if app_state.df_reg is None:
            if main_window:
                messagebox.showerror("Error", "No active database loaded.")
            return False, "No active database loaded"

        if not hasattr(app_state, "_log_records") or not app_state._log_records:
            if app_state.df_log is not None and not app_state.df_log.empty:
                app_state._log_records = app_state.df_log.to_dict(orient="records")
            else:
                app_state._log_records = []

        def _norm_ts(ts):
            if not ts:
                return ""
            return str(ts).strip().replace(" ", "T").split(".")[0]

        # Identify batches that were already rolled back
        rolled_back_ts = set()
        for e in app_state._log_records:
            if e.get("Action") == "GBIF_ROLLBACK":
                cf = str(e.get("ChangedFields", ""))
                if "from GBIF update at " in cf:
                    ts_part = cf.split("from GBIF update at ", 1)[1].strip()
                    rolled_back_ts.add(_norm_ts(ts_part))

        gbif_entries = [
            e for e in app_state._log_records
            if e.get("Action") == "GBIF_UPDATE" and _norm_ts(e.get("Timestamp", "")) not in rolled_back_ts
        ]
        if not gbif_entries:
            if main_window:
                messagebox.showinfo("No Updates Found", "No GBIF taxonomic updates found in the audit log to roll back.")
            return False, "No GBIF updates found in log"

        latest_ts = gbif_entries[-1].get("Timestamp")
        norm_latest = _norm_ts(latest_ts)
        target_entries = [e for e in gbif_entries if _norm_ts(e.get("Timestamp")) == norm_latest]

        reverted_count = 0
        for entry in target_entries:
            oid = str(entry.get("ObjectID", "")).strip()
            if not oid:
                continue

            reg_oid = oid
            if reg_oid not in app_state.df_reg.index:
                if str(oid).isdigit() and int(oid) in app_state.df_reg.index:
                    reg_oid = int(oid)
                else:
                    matches = [idx for idx in app_state.df_reg.index if str(idx).strip() == oid]
                    if matches:
                        reg_oid = matches[0]
                    else:
                        continue

            cv_str = str(entry.get("ChangedValues", ""))
            diffs = cv_str.split(" | ")
            for d in diffs:
                if ' -> ' in d and ': "' in d:
                    parts = d.split(': "', 1)
                    field = parts[0].strip()
                    val_parts = parts[1].split('" -> "', 1)
                    old_val = val_parts[0]
                    if field in app_state.df_reg.columns:
                        app_state.df_reg.at[reg_oid, field] = old_val
                        reverted_count += 1

            # Restore cleared problems if recorded
            pcv_str = str(entry.get("ProblemsChangedValues", ""))
            if pcv_str and app_state.df_obs is not None:
                prob_diffs = pcv_str.split(" | ")
                for pd_item in prob_diffs:
                    if ' -> ' in pd_item and ': "' in pd_item:
                        p_parts = pd_item.split(': "', 1)
                        p_col = p_parts[0].strip()
                        p_val_parts = p_parts[1].split('" -> "', 1)
                        p_old_val = p_val_parts[0].strip().lower() == "true"
                        if reg_oid in app_state.df_obs.index and p_col in app_state.df_obs.columns:
                            app_state.df_obs.at[reg_oid, p_col] = p_old_val

        rollback_log = {
            "Timestamp": datetime.now().isoformat(timespec="seconds"),
            "User": getpass.getuser(),
            "Action": "GBIF_ROLLBACK",
            "ObjectID": "BATCH",
            "Reviewed": "",
            "ChangedFields": f"Rolled back {reverted_count} fields from GBIF update at {latest_ts}",
            "ChangedValues": "",
            "ProblemsChanged": "",
            "ProblemsChangedValues": "",
            "LocationChanged": "",
            "LocationChangedValues": "",
            "SourceFile": os.path.basename(app_state.excel_path or ""),
            "OutputFile": os.path.basename(app_state.output_path or app_state.excel_path or "")
        }
        from repository import _normalise_log_dataframe
        app_state._log_records.append(rollback_log)
        app_state.df_log = _normalise_log_dataframe(pd.DataFrame(app_state._log_records))
        app_state.dirty = True

    if main_window:
        if hasattr(main_window, "_invalidate_row_cache"):
            main_window._invalidate_row_cache()
        if hasattr(main_window, "invalidate_search_index"):
            main_window.invalidate_search_index()
        if hasattr(main_window, "display_object") and getattr(app_state, "current_object_id", None):
            main_window.display_object(app_state.current_object_id)
        if hasattr(main_window, "object_list") and hasattr(main_window.object_list, "refresh_all_cards"):
            main_window.object_list.refresh_all_cards()
        messagebox.showinfo("Rollback Complete", f"Successfully rolled back {reverted_count} taxonomic changes from {latest_ts}.")

    return True, f"Rolled back {reverted_count} changes"
