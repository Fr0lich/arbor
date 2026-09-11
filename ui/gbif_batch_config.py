import tkinter as tk
from tkinter import ttk, messagebox
import tkinter.font as tkFont
import pandas as pd
import threading
from typing import List, Dict, Any, Optional
from config import sc

FONT_UI = ("sans-serif", 10)
FONT_UI_BOLD = ("sans-serif", 10, "bold")
FONT_UI_LG = ("sans-serif", 12, "bold")
FONT_UI_XL = ("sans-serif", 14, "bold")
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
    FONT_UI_XL = (ui_family, sc(14), "bold")
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
    "error": "#c93a40",
    "error_bg": "#fef2f2",
    "success": "#3a7d44",
    "success_bg": "#f0fdf4",
    "success_border": "#3a7d44",
    "warning": "#f59e0b",
    "conflict": "#0284c7",
}


class GBIFBatchConfigDialog(tk.Toplevel):
    """
    Onboarding and Scope Configuration Dialog for Bulk GBIF Taxonomic Analysis.
    Provides clear scope selection, safety guarantees, and quiet background execution.
    """
    def __init__(self, parent, main_app):
        super().__init__(parent)
        self.withdraw()  # Prevent premature top-left rendering flicker
        init_fonts()
        self.parent = parent
        self.main_app = main_app

        self.title("Batch GBIF Taxonomy Analysis")
        self.minsize(sc(640), sc(540))
        self.transient(parent)

        self.cancel_event = threading.Event()
        self.scope_var = tk.StringVar(value="filtered")
        self._is_analyzing = False

        # Gather counts
        self.all_count = len(self.main_app.app.df_reg) if getattr(self.main_app.app, "df_reg", None) is not None else 0
        active_ids = getattr(self.main_app.app, "active_object_ids", None)
        self.filtered_count = len(active_ids) if active_ids else self.all_count

        selected_ids = []
        if hasattr(self.main_app, "object_list") and hasattr(self.main_app.object_list, "get_selected_ids"):
            try:
                selected_ids = self.main_app.object_list.get_selected_ids() or []
            except Exception:
                selected_ids = []
        self.selected_count = len(selected_ids)
        self.selected_ids = selected_ids

        # Set sensible default scope
        if self.selected_count > 0:
            self.scope_var.set("selected")
        elif self.filtered_count < self.all_count and self.filtered_count > 0:
            self.scope_var.set("filtered")
        else:
            self.scope_var.set("all")

        self._build_ui()
        import utils
        utils.center_and_fit_toplevel(self, sc(660), sc(580))
        self.lift()
        self.focus_set()
        self.bind("<Return>", lambda e: self._start_analysis())
        self.bind("<Escape>", lambda e: self._on_cancel())

    def _build_ui(self):
        is_dark = getattr(self.main_app, "dark_mode_active", False)
        bg = "#181c19" if is_dark else COLORS["bg"]
        surface = "#24273a" if is_dark else COLORS["surface"]
        surface_dim = "#1e2030" if is_dark else COLORS["surface_dim"]
        border = "#363a4f" if is_dark else COLORS["border"]
        text_color = "#cad3f5" if is_dark else COLORS["text"]
        text_muted = "#a5adcb" if is_dark else COLORS["text_muted"]

        notice_bg = "#122416" if is_dark else "#f0fdf4"
        notice_border = "#3a7d44"
        notice_fg = "#a6e3a1" if is_dark else "#3a7d44"

        self.configure(bg=bg)

        # 1. Top Header Bar (Full-bleed)
        header = tk.Frame(self, bg=surface, height=sc(48))
        header.pack(fill="x", side="top")
        tk.Frame(header, bg=border, height=sc(1)).pack(fill="x", side="bottom")

        tk.Label(
            header,
            text="BATCH_GBIF_TAXONOMY_ANALYSIS",
            font=FONT_UI_LG,
            fg=text_color,
            bg=surface
        ).pack(side="left", padx=sc(16), pady=sc(12))

        # 2. Sticky Bottom Footer (Packed before main_area to guarantee bottom pinning)
        footer = tk.Frame(self, bg=surface_dim, height=sc(48))
        footer.pack(fill="x", side="bottom")
        tk.Frame(footer, bg=border, height=sc(1)).pack(side="top", fill="x")

        self.summary_label = tk.Label(
            footer,
            text="",
            font=FONT_MONO,
            fg=text_muted,
            bg=surface_dim
        )
        self.summary_label.pack(side="left", padx=sc(20), pady=sc(12))

        self.analyze_btn = tk.Button(
            footer,
            text="START ANALYSIS →",
            command=self._start_analysis,
            font=FONT_UI_BOLD,
            bg="#3a7d44",
            fg="#ffffff",
            relief="flat",
            bd=0,
            padx=sc(18),
            pady=sc(8),
            cursor="hand2"
        )
        self.analyze_btn.pack(side="right", padx=sc(16), pady=sc(6))

        self.cancel_btn = tk.Button(
            footer,
            text="CLOSE",
            command=self._on_cancel,
            font=FONT_UI_BOLD,
            bg=surface,
            fg=text_color,
            relief="solid",
            bd=1,
            padx=sc(16),
            pady=sc(8),
            cursor="hand2"
        )
        self.cancel_btn.pack(side="right", padx=sc(8), pady=sc(6))

        # 3. Main content area
        main_area = tk.Frame(self, bg=bg)
        main_area.pack(fill="both", expand=True)

        # Context Header
        ctx_header = tk.Frame(main_area, bg=surface)
        ctx_header.pack(fill="x")
        tk.Frame(ctx_header, bg=border, height=sc(1)).pack(side="bottom", fill="x")

        tk.Label(
            ctx_header,
            text="RECONCILE COLLECTION TAXONOMY",
            font=FONT_UI_XL,
            fg=text_color,
            bg=surface
        ).pack(anchor="w", padx=sc(20), pady=(sc(12), sc(2)))

        tk.Label(
            ctx_header,
            text="Query the GBIF Backbone Taxonomy to detect spelling errors, outdated synonyms, and accepted scientific names across your collection.",
            font=FONT_UI,
            fg=text_muted,
            bg=surface,
            wraplength=sc(540),
            justify="left"
        ).pack(anchor="w", padx=sc(20), pady=(0, sc(12)))

        # Central Scrollable/Cards Container
        container = tk.Frame(main_area, bg=bg, padx=sc(18), pady=sc(14))
        container.pack(fill="both", expand=True)

        # Safety Guarantee Banner
        notice_frame = tk.Frame(
            container,
            bg=notice_bg,
            highlightbackground=notice_border,
            highlightthickness=1,
            padx=sc(14),
            pady=sc(10)
        )
        notice_frame.pack(fill="x", pady=(0, sc(14)))

        tk.Label(
            notice_frame,
            text="🛡️  SAFETY GUARANTEE: Full Review Required",
            font=FONT_UI_BOLD,
            fg=notice_fg,
            bg=notice_bg
        ).pack(anchor="w")

        tk.Label(
            notice_frame,
            text="No data will be changed automatically. You will be presented with an interactive review screen to inspect, compare, and select every change before applying.",
            font=FONT_UI,
            fg=text_color,
            bg=notice_bg,
            wraplength=sc(520),
            justify="left"
        ).pack(anchor="w", pady=(sc(2), 0))

        # Scope Selection Card
        scope_card = tk.Frame(
            container,
            bg=surface,
            highlightbackground=border,
            highlightthickness=1
        )
        scope_card.pack(fill="x", pady=(0, sc(14)))

        # Scope Card Header Bar
        card_hdr = tk.Frame(scope_card, bg="#2c302e" if not is_dark else "#1b1b1b")
        card_hdr.pack(fill="x")
        tk.Label(
            card_hdr,
            text="SELECT OBJECT SCOPE",
            font=FONT_UI_BOLD,
            fg="#ffffff",
            bg="#2c302e" if not is_dark else "#1b1b1b"
        ).pack(side="left", padx=sc(12), pady=sc(8))

        scope_body = tk.Frame(scope_card, bg=surface, padx=sc(14), pady=sc(10))
        scope_body.pack(fill="x")

        def _make_scope_row(parent, val, title, count_text, enabled=True):
            row = tk.Frame(parent, bg=surface, cursor="hand2" if enabled else "arrow")
            row.pack(fill="x", pady=sc(4))

            rb = tk.Radiobutton(
                row,
                text=title,
                variable=self.scope_var,
                value=val,
                font=FONT_UI_BOLD if val == self.scope_var.get() else FONT_UI,
                fg=text_color if enabled else text_muted,
                bg=surface,
                activebackground=surface,
                activeforeground=text_color,
                selectcolor=surface,
                cursor="hand2" if enabled else "arrow",
                state="normal" if enabled else "disabled",
                command=self._update_scope_summary
            )
            rb.pack(side="left")

            count_badge = tk.Label(
                row,
                text=count_text,
                font=FONT_MONO_SM,
                fg=text_muted,
                bg=surface_dim,
                padx=sc(6),
                pady=sc(2)
            )
            count_badge.pack(side="right")
            return rb

        # Radio Options
        self.rb_filt = _make_scope_row(
            scope_body,
            "filtered",
            "Filtered Objects",
            f"{self.filtered_count} objects"
        )

        self.rb_sel = _make_scope_row(
            scope_body,
            "selected",
            "Selected Objects",
            f"{self.selected_count} objects",
            enabled=(self.selected_count > 0)
        )

        self.rb_all = _make_scope_row(
            scope_body,
            "all",
            "All Database Objects",
            f"{self.all_count} objects"
        )

        # Progress Section (Hidden initially)
        self.progress_frame = tk.Frame(
            container,
            bg=surface,
            highlightbackground=border,
            highlightthickness=1,
            padx=sc(16),
            pady=sc(12)
        )

        progress_hdr = tk.Frame(self.progress_frame, bg=surface)
        progress_hdr.pack(fill="x", pady=(0, sc(6)))

        self.status_var = tk.StringVar(value="")
        self.status_label = tk.Label(
            progress_hdr,
            textvariable=self.status_var,
            font=FONT_UI_BOLD,
            fg=notice_fg,
            bg=surface
        )
        self.status_label.pack(side="left", anchor="w")

        self.pct_var = tk.StringVar(value="0%")
        self.pct_label = tk.Label(
            progress_hdr,
            textvariable=self.pct_var,
            font=FONT_UI_BOLD,
            fg=text_color,
            bg=surface
        )
        self.pct_label.pack(side="right", anchor="e")

        self.progress_var = tk.DoubleVar(value=0.0)
        self.progress_bar = ttk.Progressbar(
            self.progress_frame,
            variable=self.progress_var,
            maximum=100,
            mode="determinate"
        )
        self.progress_bar.pack(fill="x", pady=(0, sc(6)))

        self.detail_var = tk.StringVar(value="")
        self.detail_label = tk.Label(
            self.progress_frame,
            textvariable=self.detail_var,
            font=FONT_MONO_SM,
            fg=text_muted,
            bg=surface
        )
        self.detail_label.pack(anchor="w")

        self._update_scope_summary()

    def _update_scope_summary(self):
        scope = self.scope_var.get()
        count = self.all_count
        if scope == "selected":
            count = self.selected_count
        elif scope == "filtered":
            count = self.filtered_count
        if hasattr(self, "summary_label") and self.summary_label.winfo_exists():
            self.summary_label.config(text=f"READY • {count} OBJECT{'S' if count != 1 else ''} TARGETED")

    def _on_cancel(self):
        self.cancel_event.set()
        self.destroy()

    def _start_analysis(self):
        if self._is_analyzing:
            return

        scope = self.scope_var.get()
        target_ids = []

        if scope == "selected" and self.selected_ids:
            target_ids = list(self.selected_ids)
        elif scope == "filtered":
            active_ids = getattr(self.main_app.app, "active_object_ids", None)
            target_ids = list(active_ids) if active_ids else list(self.main_app.app.df_reg.index)
        else:
            target_ids = list(self.main_app.app.df_reg.index)

        if not target_ids:
            messagebox.showinfo("No Objects", "No objects found for the chosen scope.", parent=self)
            return

        items = []
        df_reg = self.main_app.app.df_reg
        for oid in target_ids:
            reg_oid = oid
            if reg_oid not in df_reg.index:
                if str(oid).isdigit() and int(oid) in df_reg.index:
                    reg_oid = int(oid)
                else:
                    matches = [idx for idx in df_reg.index if str(idx).strip() == str(oid).strip()]
                    if matches:
                        reg_oid = matches[0]
                    else:
                        continue

            row = df_reg.loc[reg_oid]
            if isinstance(row, pd.DataFrame):
                row = row.iloc[0]

            genus = str(row.get("Genus", "") if pd.notna(row.get("Genus")) else "").strip()
            species = str(row.get("Species", "") if pd.notna(row.get("Species")) else "").strip()
            author = str(row.get("Author", "") if pd.notna(row.get("Author")) else "").strip()
            family = str(row.get("Family", "") if pd.notna(row.get("Family")) else "").strip()

            if genus or species:
                items.append({
                    "oid": str(oid),
                    "genus": genus,
                    "species": species,
                    "author": author,
                    "family": family,
                })

        if not items:
            messagebox.showinfo("No Taxa", "No objects with Genus or Species found to check against GBIF.", parent=self)
            return

        self._is_analyzing = True
        self.rb_all.config(state="disabled")
        self.rb_filt.config(state="disabled")
        self.rb_sel.config(state="disabled")
        self.analyze_btn.config(text="ANALYZING...", fg="#ffffff", bg="#245e31", cursor="watch")

        self.status_var.set(f"Querying GBIF taxonomy for {len(items)} objects in background...")
        self.pct_var.set("0%")
        self.detail_var.set(f"Starting analysis on {len(items)} objects...")
        self.progress_var.set(0.0)
        self.progress_frame.pack(fill="x", pady=(0, sc(14)))
        self.update_idletasks()

        # Dynamically ensure window expands height if needed to accommodate progress box
        try:
            cur_w = self.winfo_width()
            cur_h = self.winfo_height()
            req_h = sc(640)
            if cur_h < req_h:
                self.geometry(f"{max(cur_w, sc(660))}x{req_h}")
        except Exception:
            pass

        def on_progress(completed_taxa, total_taxa, current_name):
            pct = int((completed_taxa / total_taxa) * 100) if total_taxa > 0 else 0

            def do_ui_update():
                if not self.winfo_exists() or self.cancel_event.is_set():
                    return
                self.progress_var.set(pct)
                self.pct_var.set(f"{pct}%")
                self.detail_var.set(f"Checked {completed_taxa}/{total_taxa} unique taxa — {current_name}")

            from backend.task_queue import app_worker
            app_worker.task_queue.put(do_ui_update)

        def worker():
            import backend.gbif
            try:
                diff_results = backend.gbif.batch_gbif_match(
                    items,
                    progress_callback=on_progress,
                    cancel_event=self.cancel_event
                )
            except Exception as e:
                diff_results = []
                print(f"Error in batch GBIF worker: {e}")

            if not self.cancel_event.is_set():
                from backend.task_queue import app_worker
                app_worker.task_queue.put(lambda: self._on_analysis_complete(diff_results))

        self._worker_thread = threading.Thread(target=worker, daemon=True)
        self._worker_thread.start()

    def _on_analysis_complete(self, diff_results):
        if not self.winfo_exists():
            return
        parent_ref = self.parent
        app_ref = self.main_app.app
        main_app_ref = self.main_app

        self.destroy()

        if not diff_results:
            messagebox.showinfo(
                "GBIF Review",
                "All checked taxonomy records are up to date with GBIF (no changes detected).",
                parent=parent_ref
            )
            return

        from ui.gbif_review import GBIFReviewDialog
        GBIFReviewDialog(
            parent_ref,
            app_ref,
            diff_results,
            on_applied_callback=main_app_ref._on_gbif_batch_applied
        )
