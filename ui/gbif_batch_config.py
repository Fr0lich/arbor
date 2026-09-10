import tkinter as tk
from tkinter import ttk, messagebox
import pandas as pd
import threading
from typing import List, Dict, Any, Optional
from config import sc


class GBIFBatchConfigDialog(tk.Toplevel):
    """
    Onboarding and Scope Configuration Dialog for Bulk GBIF Taxonomic Analysis.
    Provides clear scope selection, safety guarantees, and quiet background execution.
    """
    def __init__(self, parent, main_app):
        super().__init__(parent)
        self.withdraw()  # Prevent premature top-left rendering flicker
        self.parent = parent
        self.main_app = main_app

        self.title("Batch GBIF Taxonomy Analysis")
        self.minsize(sc(540), sc(440))
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
        utils.center_and_fit_toplevel(self, sc(560), sc(480))
        self.lift()
        self.focus_set()

    def _build_ui(self):
        is_dark = getattr(self.main_app, "dark_mode_active", False)
        bg_color = "#181c19" if is_dark else "#fbfaf8"
        fg_title = "#e8ebe9" if is_dark else "#2c302e"
        fg_muted = "#a6adc8" if is_dark else "#757d77"
        border_color = "#2c302e" if is_dark else "#dadada"
        card_bg = "#111412" if is_dark else "#ffffff"
        notice_bg = "#122416" if is_dark else "#f0fdf4"
        notice_border = "#3a7d44"
        notice_fg = "#3a7d44"

        btn_primary_bg = "#3a7d44" if is_dark else "#2c302e"
        btn_sec_bg = card_bg
        btn_sec_fg = fg_title
        btn_sec_hover = "#242a25" if is_dark else "#e9ece5"

        self.configure(bg=bg_color)

        container = tk.Frame(self, bg=bg_color, padx=sc(20), pady=sc(18))
        container.pack(fill="both", expand=True)

        # 1. Header & Onboarding
        hdr_frame = tk.Frame(container, bg=bg_color)
        hdr_frame.pack(fill="x", pady=(0, sc(12)))

        tk.Label(
            hdr_frame,
            text="🌿 Batch GBIF Taxonomy Analysis",
            font=("Segoe UI", sc(13), "bold"),
            fg=fg_title,
            bg=bg_color
        ).pack(anchor="w")

        tk.Label(
            hdr_frame,
            text="Query the Global Biodiversity Information Facility (GBIF) to check for updated\naccepted taxonomy, spelling corrections, and synonym replacements across your collection.",
            font=("Segoe UI", sc(9.5)),
            fg=fg_muted,
            bg=bg_color,
            justify="left"
        ).pack(anchor="w", pady=(sc(4), 0))

        # 2. Safety Guarantee Banner
        notice_frame = tk.Frame(
            container,
            bg=notice_bg,
            highlightbackground=notice_border,
            highlightthickness=1,
            padx=sc(12),
            pady=sc(8)
        )
        notice_frame.pack(fill="x", pady=(0, sc(16)))

        tk.Label(
            notice_frame,
            text="🛡️  SAFETY GUARANTEE: Never Auto-Resolved",
            font=("Segoe UI", sc(9), "bold"),
            fg=notice_fg,
            bg=notice_bg
        ).pack(anchor="w")

        tk.Label(
            notice_frame,
            text="No data will be changed automatically. You will be presented with a full\ninteractive review screen to inspect, compare, and select every change before applying.",
            font=("Segoe UI", sc(8.5)),
            fg=fg_title,
            bg=notice_bg,
            justify="left"
        ).pack(anchor="w", pady=(sc(2), 0))

        # 3. Scope Selection Card
        scope_card = tk.Frame(
            container,
            bg=card_bg,
            highlightbackground=border_color,
            highlightthickness=1,
            padx=sc(16),
            pady=sc(12)
        )
        scope_card.pack(fill="x", pady=(0, sc(16)))

        tk.Label(
            scope_card,
            text="SELECT OBJECT SCOPE",
            font=("Segoe UI", sc(9), "bold"),
            fg=fg_muted,
            bg=card_bg
        ).pack(anchor="w", pady=(0, sc(8)))

        # Radio Option 1: All
        self.rb_all = tk.Radiobutton(
            scope_card,
            text=f"Check All Objects in Database ({self.all_count} objects)",
            variable=self.scope_var,
            value="all",
            font=("Segoe UI", sc(9.5)),
            fg=fg_title,
            bg=card_bg,
            activebackground=card_bg,
            activeforeground=fg_title,
            selectcolor=card_bg,
            cursor="hand2"
        )
        self.rb_all.pack(anchor="w", pady=sc(3))

        # Radio Option 2: Filtered
        self.rb_filt = tk.Radiobutton(
            scope_card,
            text=f"Check Currently Filtered Objects ({self.filtered_count} objects)",
            variable=self.scope_var,
            value="filtered",
            font=("Segoe UI", sc(9.5)),
            fg=fg_title,
            bg=card_bg,
            activebackground=card_bg,
            activeforeground=fg_title,
            selectcolor=card_bg,
            cursor="hand2"
        )
        self.rb_filt.pack(anchor="w", pady=sc(3))

        # Radio Option 3: Selected
        sel_text = f"Check Selected Objects ({self.selected_count} objects)"
        self.rb_sel = tk.Radiobutton(
            scope_card,
            text=sel_text,
            variable=self.scope_var,
            value="selected",
            font=("Segoe UI", sc(9.5)),
            fg=fg_title if self.selected_count > 0 else fg_muted,
            bg=card_bg,
            activebackground=card_bg,
            activeforeground=fg_title,
            selectcolor=card_bg,
            cursor="hand2" if self.selected_count > 0 else "arrow",
            state="normal" if self.selected_count > 0 else "disabled"
        )
        self.rb_sel.pack(anchor="w", pady=sc(3))

        # 4. Progress Section (Container configured with Progressbar and %)
        self.progress_frame = tk.Frame(
            container,
            bg=card_bg,
            highlightbackground=border_color,
            highlightthickness=1,
            padx=sc(16),
            pady=sc(12)
        )

        progress_hdr = tk.Frame(self.progress_frame, bg=card_bg)
        progress_hdr.pack(fill="x", pady=(0, sc(6)))

        self.status_var = tk.StringVar(value="")
        self.status_label = tk.Label(
            progress_hdr,
            textvariable=self.status_var,
            font=("Segoe UI", sc(9.5), "bold"),
            fg=notice_fg,
            bg=card_bg
        )
        self.status_label.pack(side="left", anchor="w")

        self.pct_var = tk.StringVar(value="0%")
        self.pct_label = tk.Label(
            progress_hdr,
            textvariable=self.pct_var,
            font=("Segoe UI", sc(10), "bold"),
            fg=fg_title,
            bg=card_bg
        )
        self.pct_label.pack(side="right", anchor="e")

        # Progress bar
        self.progress_var = tk.DoubleVar(value=0.0)
        self.progress_bar = ttk.Progressbar(
            self.progress_frame,
            variable=self.progress_var,
            maximum=100,
            mode="determinate"
        )
        self.progress_bar.pack(fill="x", pady=(0, sc(6)))

        # Sub-status detail label
        self.detail_var = tk.StringVar(value="")
        self.detail_label = tk.Label(
            self.progress_frame,
            textvariable=self.detail_var,
            font=("Segoe UI", sc(8.5)),
            fg=fg_muted,
            bg=card_bg
        )
        self.detail_label.pack(anchor="w")

        # 5. Action Buttons
        self.btn_frame = tk.Frame(container, bg=bg_color)
        self.btn_frame.pack(fill="x", side="bottom")

        self.cancel_btn = tk.Button(
            self.btn_frame,
            text="Cancel",
            command=self._on_cancel,
            font=("Segoe UI", sc(9.5), "bold"),
            bg=btn_sec_bg,
            fg=btn_sec_fg,
            relief="flat",
            bd=0,
            cursor="hand2",
            padx=sc(14),
            pady=sc(6),
            highlightthickness=1,
            highlightbackground=border_color,
            highlightcolor=border_color
        )
        self.cancel_btn.pack(side="right", padx=(sc(8), 0))
        self.cancel_btn.bind("<Enter>", lambda e: self.cancel_btn.config(bg=btn_sec_hover))
        self.cancel_btn.bind("<Leave>", lambda e: self.cancel_btn.config(bg=btn_sec_bg))

        self.analyze_btn = tk.Button(
            self.btn_frame,
            text="Analyze Taxonomy →",
            command=self._start_analysis,
            font=("Segoe UI", sc(9.5), "bold"),
            bg=btn_primary_bg,
            fg="#ffffff",
            relief="flat",
            bd=0,
            cursor="hand2",
            padx=sc(18),
            pady=sc(6)
        )
        self.analyze_btn.pack(side="right")

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

        # Build items safely from df_reg
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
        self.analyze_btn.config(state="disabled", text="Analyzing...")

        self.status_var.set(f"Querying GBIF taxonomy for {len(items)} objects in background...")
        self.pct_var.set("0%")
        self.detail_var.set(f"Starting analysis on {len(items)} objects...")
        self.progress_var.set(0.0)
        self.progress_frame.pack(fill="x", pady=(0, sc(16)), before=self.btn_frame)

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

