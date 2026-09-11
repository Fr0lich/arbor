import tkinter as tk
from tkinter import ttk, messagebox
import pandas as pd
from datetime import datetime
import os
import getpass
import tkinter.font as tkFont
import math
from typing import List, Dict, Any, Optional, Tuple
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
    "chip_tag": "#757d77"
}


class GBIFReviewDialog(tk.Toplevel):
    """
    High-Performance Paginated Taxonomic Reconciliation & Review dialog.
    Supports reviewing thousands of specimens instantaneously with 0 GDI coordinate overflow,
    virtualized page rendering, live filtering, and global cross-page batch selection tracking.
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
        self.minsize(sc(880), sc(580))

        # Pagination & Filter State
        self.page_size = 25
        self.current_page = 0
        self.search_query = ""
        self.status_filter = "all"  # "all", "verified", "synonym", "accepted"
        self._is_fullscreen = False

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
        self.specimen_dir_widgets = {}  # oid -> {"tag_lbl": Label, "accent_bar": Frame, "status": str, "total_changes": int}
        self.page_field_vars = {}  # (oid, field) -> BooleanVar on current page

        self._build_ui()
        self._render_current_page()

        self.bind("<Control-a>", lambda e: self._apply_selected())
        self.bind("<Control-Return>", lambda e: self._apply_selected())
        self.bind("<Escape>", lambda e: self.destroy())
        self.bind("<F11>", lambda e: self._toggle_fullscreen())

        import utils
        utils.center_and_fit_toplevel(self, sc(1160), sc(740))
        self.transient(parent)
        self.lift()
        self.focus_set()

    def _toggle_fullscreen(self, event=None):
        self._is_fullscreen = not self._is_fullscreen
        try:
            # On Windows, try zoomed state or -fullscreen attribute
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
            self.btn_fullscreen.config(text="🗗 Restore" if self._is_fullscreen else "⛶ Fullscreen")

    def _diff_has_book_matches(self, diff: Dict[str, Any]) -> bool:
        oid = str(diff.get("oid", ""))
        for chg in diff.get("changes", []):
            field = chg.get("field", "")
            val = chg.get("new", "")
            if find_book_matches_for_gbif(self.app_state, oid, field, val):
                return True
        return False

    def _get_filtered_results(self) -> List[Dict[str, Any]]:
        q = self.search_query.strip().lower()
        sf = self.status_filter

        results = []
        for d in self.diff_results:
            oid = str(d.get("oid", "")).strip().lower()
            status = str(d.get("status", "")).strip().lower()
            match_type = str(d.get("match_type", "")).strip().lower()

            # Status filter
            if sf == "verified":
                if not self._diff_has_book_matches(d):
                    continue
            elif sf == "synonym" and "synonym" not in status:
                continue
            elif sf == "accepted" and "synonym" in status:
                continue

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

        # Fullscreen button in header
        self.btn_fullscreen = tk.Button(
            hdr_left,
            text="⛶ Fullscreen",
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

        # Search & Status Filter on Right of Header
        hdr_right = tk.Frame(header, bg=C["surface"])
        hdr_right.pack(side="right", padx=sc(16), pady=sc(8))

        # Status filter pills & Book verified count
        syn_count = sum(1 for d in self.diff_results if d.get("status") == "SYNONYM")
        acc_count = len(self.diff_results) - syn_count
        verified_count = sum(1 for d in self.diff_results if self._diff_has_book_matches(d))

        self.status_var = tk.StringVar(value="all")
        stat_combo = ttk.Combobox(
            hdr_right,
            textvariable=self.status_var,
            values=[
                f"All ({len(self.diff_results)})",
                f"✓ Verified in Books ({verified_count})",
                f"Synonyms ({syn_count})",
                f"Accepted / Spelling ({acc_count})"
            ],
            state="readonly",
            width=26,
            font=FONT_UI
        )
        stat_combo.current(0)
        stat_combo.bind("<<ComboboxSelected>>", self._on_status_filter_changed)
        stat_combo.pack(side="right", padx=(sc(8), 0))

        # Search box
        self.search_var = tk.StringVar()
        self.search_entry = tk.Entry(
            hdr_right,
            textvariable=self.search_var,
            font=FONT_UI,
            bg=C["surface_dim"],
            fg=C["text"],
            relief="flat",
            bd=0,
            width=18,
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

        # 2. Bottom Action Bar (Sticky, packed before main_area to guarantee it stays pinned in fullscreen/resizing)
        bottom_bar = tk.Frame(self, bg=C["surface_dim"], height=sc(56))
        bottom_bar.pack(fill="x", side="bottom")
        tk.Frame(bottom_bar, bg=C["border"], height=sc(1)).pack(side="top", fill="x")

        b_content = tk.Frame(bottom_bar, bg=C["surface_dim"], padx=sc(16), pady=sc(8))
        b_content.pack(fill="both", expand=True)

        # Batch Selection Controls
        self.sel_all_btn = tk.Button(
            b_content, text="Select All (Batch)", command=self._select_all_batch,
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
        self.sel_page_btn.pack(side="left")

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
            b_content, text="CLOSE", command=self.destroy,
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

        # 3. Main content area (Split View: Left Sidebar Directory + Right Cards)
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
        self.dir_canvas.bind("<MouseWheel>", self._on_dir_mousewheel)

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
        self.canvas.bind("<MouseWheel>", self._on_main_mousewheel)

    def _update_sidebar_item(self, oid: str):
        """Update a specimen's sidebar badge and accent strip dynamically based on selection."""
        C = self.colors
        if oid in self.specimen_dir_widgets:
            info = self.specimen_dir_widgets[oid]
            tag_lbl = info["tag_lbl"]
            accent_bar = info["accent_bar"]
            status = info["status"]
            changes = self.oid_to_diff.get(oid, {}).get("changes", [])
            total_cnt = len(changes)
            sel_cnt = sum(1 for chg in changes if self.selection_state.get((oid, chg["field"]), True))

            accent_color = C["warning"] if status == "SYNONYM" else C["success"]

            if sel_cnt == 0:
                tag_lbl.config(text="SKIPPED", fg=C["text_muted"])
                accent_bar.config(bg=C["border"])
            elif sel_cnt < total_cnt:
                tag_lbl.config(text=f"{status.upper()} ({sel_cnt}/{total_cnt})", fg=accent_color)
                accent_bar.config(bg=accent_color)
            else:
                tag_lbl.config(text=status.upper(), fg=accent_color)
                accent_bar.config(bg=accent_color)

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

        # 2. Get filtered results and slice page
        filtered = self._get_filtered_results()
        total_items = len(filtered)
        total_pages = max(1, math.ceil(total_items / self.page_size))

        if self.current_page >= total_pages:
            self.current_page = max(0, total_pages - 1)

        start_idx = self.current_page * self.page_size
        end_idx = min(start_idx + self.page_size, total_items)
        page_items = filtered[start_idx:end_idx]

        # Update Navigation & Header Labels
        if total_items == 0:
            self.page_info_label.config(text="NO MATCHING SPECIMENS FOUND.")
            self.page_num_label.config(text="Page 0 of 0")
            self.btn_first.config(state="disabled")
            self.btn_prev.config(state="disabled")
            self.btn_next.config(state="disabled")
            self.btn_last.config(state="disabled")
        else:
            self.page_info_label.config(
                text=f"SHOWING SPECIMENS {start_idx + 1}–{end_idx} OF {total_items} (BATCH TOTAL: {len(self.diff_results)})"
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

            sel_cnt = sum(1 for chg in changes if self.selection_state.get((oid, chg["field"]), True))
            accent_color = C["warning"] if status == "SYNONYM" else C["success"]

            if sel_cnt == 0:
                tag_text = "SKIPPED"
                tag_color = C["text_muted"]
                bar_color = C["border"]
            elif sel_cnt < len(changes):
                tag_text = f"{status.upper()} ({sel_cnt}/{len(changes)})"
                tag_color = accent_color
                bar_color = accent_color
            else:
                tag_text = status.upper()
                tag_color = accent_color
                bar_color = accent_color

            # --- Left Directory Entry ---
            f_frame = tk.Frame(self.dir_list, bg=C["surface"], cursor="hand2")
            f_frame.pack(fill="x")
            tk.Frame(f_frame, bg=C["border"], height=sc(1)).pack(fill="x", side="bottom")

            # 4px Left Accent Strip
            accent_bar = tk.Frame(f_frame, bg=bar_color, width=sc(4))
            accent_bar.pack(side="left", fill="y")

            # Content container
            f_content = tk.Frame(f_frame, bg=C["surface"], padx=sc(8), pady=sc(6))
            f_content.pack(side="left", fill="x", expand=True)

            tk.Label(f_content, text=f"#{oid}", font=FONT_MONO, fg=C["text"], bg=C["surface"]).pack(side="left")
            tk.Label(f_content, text=f"({len(changes)} chg)", font=FONT_MONO_SM, fg=C["text_muted"], bg=C["surface"]).pack(side="left", padx=sc(4))
            tag_lbl = tk.Label(f_content, text=tag_text, font=FONT_MONO_SM, fg=tag_color, bg=C["surface"])
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
            for child in f_content.winfo_children():
                child.bind("<Button-1>", lambda e, f=_scroll_to: f())

            self.specimen_frames[oid] = f_frame

            # --- Right Card Frame ---
            card = tk.Frame(
                self.cards_frame,
                bg=C["surface"],
                highlightbackground=C["border"],
                highlightthickness=1
            )
            card.pack(fill="x", pady=(0, sc(12)))
            self.item_cards[oid] = card

            # Solid Card Header Bar
            c_header = tk.Frame(card, bg=C["header_bg"])
            c_header.pack(fill="x")

            tk.Label(
                c_header,
                text=f"SPECIMEN #{oid}",
                font=FONT_UI_BOLD,
                fg="#ffffff",
                bg=C["header_bg"]
            ).pack(side="left", padx=sc(14), pady=sc(8))

            match_type = diff.get("match_type", "MATCH")
            badge_bg = C["warning"] if status == "SYNONYM" else (C["surface_dim"] if self.is_dark else "#444748")
            badge_fg = "#000000" if status == "SYNONYM" else "#ffffff"
            tk.Label(
                c_header,
                text=f"[{status} | {match_type}]",
                font=FONT_MONO_SM,
                fg=badge_fg,
                bg=badge_bg,
                padx=sc(8),
                pady=sc(2)
            ).pack(side="right", padx=sc(14), pady=sc(6))

            # Card Content Body
            card_body = tk.Frame(card, bg=C["surface"], padx=sc(16), pady=sc(12))
            card_body.pack(fill="x")

            # Field Rows
            for chg in changes:
                field = chg["field"]
                old_val = str(chg.get("old", ""))
                new_val = str(chg.get("new", ""))

                key = (oid, field)
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

                # Sub-header Row with Checkbox & Domain Badge
                sub_hdr = tk.Frame(row_frame, bg=C["surface"])
                sub_hdr.pack(fill="x", pady=(0, sc(4)))

                chk = tk.Checkbutton(
                    sub_hdr,
                    text=f"FIELD: {field_upper}",
                    variable=var,
                    font=FONT_UI_BOLD,
                    fg=C["text"],
                    bg=C["surface"],
                    activebackground=C["surface"],
                    activeforeground=C["primary"],
                    selectcolor=C["surface"],
                    cursor="hand2",
                    command=_on_toggle
                )
                chk.pack(side="left")

                tk.Label(
                    sub_hdr,
                    text=badge_code,
                    font=FONT_MONO_SM,
                    fg="#ffffff",
                    bg=badge_color,
                    padx=sc(6),
                    pady=sc(1)
                ).pack(side="right")

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
                    bg=C["success_bg"],
                    highlightbackground=C["success_border"],
                    highlightthickness=1,
                    padx=sc(10),
                    pady=sc(8),
                    cursor="hand2"
                )
                sug_box.pack(fill="both", expand=True)

                def _toggle_box(k=key, v=var, target_oid=oid):
                    v.set(not v.get())
                    self.selection_state[k] = v.get()
                    self._update_sidebar_item(target_oid)
                    self._update_summary()

                sug_lbl = tk.Label(
                    sug_box,
                    text=new_val or "[BLANK]",
                    font=FONT_MONO,
                    fg=C["success_text"],
                    bg=C["success_bg"],
                    anchor="w",
                    cursor="hand2"
                )
                sug_lbl.pack(side="left", fill="x", expand=True)

                # Check for Historical Book Corroboration
                matching_books = find_book_matches_for_gbif(self.app_state, oid, field, new_val)
                if matching_books:
                    book_badge_text = f"✓ In Books ({matching_books[0].replace('Books: ', '')})"
                    book_badge = tk.Label(
                        sug_box,
                        text=book_badge_text,
                        font=FONT_MONO_SM,
                        fg="#ffffff",
                        bg=C["success_border"],
                        padx=sc(6),
                        pady=sc(1),
                        cursor="hand2"
                    )
                    book_badge.pack(side="right", padx=(sc(6), 0))
                    book_badge.bind("<Button-1>", lambda e, f=_toggle_box: f())

                tag_lbl = tk.Label(
                    sug_box,
                    text="[GBIF Match]",
                    font=FONT_MONO_SM,
                    fg=C["success_border"],
                    bg=C["success_bg"],
                    cursor="hand2"
                )
                tag_lbl.pack(side="right")

                sug_box.bind("<Button-1>", lambda e, f=_toggle_box: f())
                sug_lbl.bind("<Button-1>", lambda e, f=_toggle_box: f())
                tag_lbl.bind("<Button-1>", lambda e, f=_toggle_box: f())

        # Scroll to top of cards
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
            self.status_filter = "verified"
        elif "Synonyms" in val:
            self.status_filter = "synonym"
        elif "Accepted" in val:
            self.status_filter = "accepted"
        else:
            self.status_filter = "all"
        self.current_page = 0
        self._render_current_page()

    def _on_dir_mousewheel(self, event):
        if event.delta:
            self.dir_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    def _on_main_mousewheel(self, event):
        if event.delta:
            self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    def _update_selection_buttons(self):
        if not hasattr(self, "sel_all_btn") or not self.sel_all_btn.winfo_exists():
            return
        filtered = self._get_filtered_results()
        is_filtered = (self.status_filter != "all") or bool(self.search_query.strip())

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
            self.selection_state[k] = True
        for var in self.page_field_vars.values():
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
                self.selection_state[(oid, chg["field"])] = True
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
        for k, var in self.page_field_vars.items():
            self.selection_state[k] = True
            var.set(True)
        for oid in self.specimen_dir_widgets.keys():
            self._update_sidebar_item(oid)
        self._update_summary()

    def _update_summary(self):
        sel_count = sum(1 for v in self.selection_state.values() if v)
        total_count = len(self.selection_state)
        selected_oids = {oid for (oid, f), v in self.selection_state.items() if v}
        self.summary_label.config(text=f"Selected: {sel_count} / {total_count} field updates ({len(selected_oids)} specimens)")
        self.apply_btn.config(text=f"APPLY SELECTED UPDATES ({sel_count})")

    def _apply_selected(self):
        selected_updates = [
            (oid, self.all_changes[(oid, field)])
            for (oid, field), is_sel in self.selection_state.items()
            if is_sel and (oid, field) in self.all_changes
        ]

        if not selected_updates:
            messagebox.showwarning(
                "No Changes Selected",
                "Please select at least one taxonomic update to apply.",
                parent=self
            )
            return

        with self.app_state.df_lock:
            if self.app_state.df_reg is None:
                messagebox.showerror("Error", "No active database loaded.", parent=self)
                return

            if not hasattr(self.app_state, "_log_records") or not self.app_state._log_records:
                if self.app_state.df_log is not None and not self.app_state.df_log.empty:
                    self.app_state._log_records = self.app_state.df_log.to_dict(orient="records")
                else:
                    self.app_state._log_records = []

            problem_to_field = {}
            if getattr(self.app_state, "config", None):
                problems_cfg = self.app_state.config.get("ui_sections", {}).get("problems", [])
                for p in problems_cfg:
                    name = p.get("name")
                    maps_to = p.get("maps_to") or p.get("target")
                    if name and maps_to and maps_to != "Other" and name != "Other_problem":
                        problem_to_field[name] = maps_to

            # Group updates by oid
            by_oid = {}
            for oid, chg in selected_updates:
                by_oid.setdefault(oid, []).append(chg)

            applied_count = 0
            ts = datetime.now().isoformat(timespec="seconds")
            user_name = getpass.getuser()

            for oid, chg_list in by_oid.items():
                reg_oid = oid
                if reg_oid not in self.app_state.df_reg.index:
                    if str(oid).isdigit() and int(oid) in self.app_state.df_reg.index:
                        reg_oid = int(oid)
                    else:
                        matches = [idx for idx in self.app_state.df_reg.index if str(idx).strip() == str(oid).strip()]
                        if matches:
                            reg_oid = matches[0]
                        else:
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

                # Auto-clear mapped problem flags
                if self.app_state.df_obs is not None and problem_to_field:
                    for f in changed_fields:
                        for pc, mf in problem_to_field.items():
                            if mf.lower().replace("_", " ").strip() == f.lower().replace("_", " ").strip():
                                if reg_oid in self.app_state.df_obs.index and pc in self.app_state.df_obs.columns:
                                    val = self.app_state.df_obs.at[reg_oid, pc]
                                    if pd.notna(val) and bool(val):
                                        self.app_state.df_obs.at[reg_oid, pc] = False
                                        if pc not in prob_changed:
                                            prob_changed.append(pc)
                                            prob_diffs.append(f'{pc}: "True" -> "False"')

                if changed_fields or prob_changed:
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
                        "SourceFile": os.path.basename(self.app_state.excel_path or ""),
                        "OutputFile": os.path.basename(self.app_state.output_path or self.app_state.excel_path or "")
                    }
                    self.app_state._log_records.append(log_entry)

            self.app_state.df_log = pd.DataFrame(self.app_state._log_records)
            self.app_state.dirty = True

        if self.on_applied_callback:
            try:
                self.on_applied_callback(applied_count, len(by_oid))
            except Exception:
                pass

        messagebox.showinfo(
            "GBIF Updates Applied",
            f"Successfully applied {applied_count} taxonomic changes across {len(by_oid)} objects.",
            parent=self.parent
        )
        self.destroy()



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
