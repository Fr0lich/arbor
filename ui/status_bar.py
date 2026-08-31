import tkinter as tk
from tkinter import ttk
from repository import REVIEWED_COLUMN
from ui.state import app_bus, OBJECT_DATA_CHANGED, OBJECT_LOADED


class StatusBarPanel:
    """Decoupled status bar component for Arbor desktop UI."""

    def __init__(self, parent_frame, ui):
        self.frame = parent_frame
        self.ui = ui

        from config import sc

        statusbar_bg = "#1c1b1b"
        statusbar_fg = "#e2e2e2"

        # Row 1: Buttons
        self.sb_top = tk.Frame(self.frame, bg=statusbar_bg, height=32)
        self.sb_top.pack(side="top", fill="x")
        self.sb_top.pack_propagate(False)

        # Row 2: Stats
        self.sb_bottom = tk.Frame(self.frame, bg=statusbar_bg, height=24)
        self.sb_bottom.pack(side="top", fill="x")
        self.sb_bottom.pack_propagate(False)

        self.labels = {}

        # Buttons (Row 1) matching left column
        self.sb_buttons_frame = tk.Frame(self.sb_top, bg=statusbar_bg, height=32)
        self.sb_buttons_frame.pack(side="left", fill="y")
        self.sb_buttons_frame.grid_propagate(False)
        self.sb_buttons_frame.rowconfigure(0, weight=1)
        self.sb_buttons_frame.columnconfigure(0, weight=1)
        self.sb_buttons_frame.columnconfigure(1, weight=0)
        self.sb_buttons_frame.columnconfigure(2, weight=1)
        self.sb_buttons_frame.columnconfigure(3, weight=0)
        self.sb_buttons_frame.columnconfigure(4, weight=1)

        self.sb_settings_btn = ttk.Button(
            self.sb_buttons_frame,
            text="SETTINGS",
            style="Nav.TButton",
            command=self.ui._open_unified,
            cursor="hand2"
        )
        if hasattr(self.ui, "toolbar_buttons"):
            self.ui.toolbar_buttons['SETTINGS'] = self.sb_settings_btn
        if hasattr(self.ui, "add_tooltip"):
            self.ui.add_tooltip(self.sb_settings_btn, "Open Application Settings")
        self.sb_settings_btn.grid(row=0, column=0, sticky="nsew", padx=(6, 2), pady=3)

        sep2 = ttk.Separator(self.sb_buttons_frame, orient="vertical")
        sep2.grid(row=0, column=3, sticky="ns", pady=3)

        self.sb_help_btn = ttk.Button(
            self.sb_buttons_frame,
            text="HELP",
            style="Nav.TButton",
            command=self.ui.open_help_window,
            cursor="hand2"
        )
        if hasattr(self.ui, "toolbar_buttons"):
            self.ui.toolbar_buttons['HELP'] = self.sb_help_btn
        if hasattr(self.ui, "add_tooltip"):
            self.ui.add_tooltip(self.sb_help_btn, "Open Help Window")
        self.sb_help_btn.grid(row=0, column=4, sticky="nsew", padx=(2, 6), pady=3)

        # Left stats group
        sb_left = tk.Frame(self.sb_bottom, bg=statusbar_bg)
        sb_left.pack(side="left", fill="y")

        def _sb_label(parent, key, text):
            lbl = tk.Label(parent, text=text, bg=statusbar_bg, fg=statusbar_fg,
                           font=("Courier New", sc(9)), padx=6, pady=0, anchor="w")
            lbl.pack(side="left")
            self.labels[key] = lbl
            return lbl

        def _sb_sep(parent):
            tk.Label(parent, text="|", bg=statusbar_bg, fg="#555555",
                     font=("Courier New", sc(9))).pack(side="left")

        _sb_label(sb_left, "object_count", "OBJECT_COUNT: —")
        _sb_sep(sb_left)
        _sb_label(sb_left, "reviewed", "REVIEWED: —")
        _sb_sep(sb_left)
        self.problems_lbl = _sb_label(sb_left, "problems", "PROBLEMS: —")
        _sb_sep(sb_left)
        _sb_label(sb_left, "last_save", "LAST_SAVE: —")

        self.filter_active_badge = tk.Label(
            sb_left, text="", bg=statusbar_bg, fg="#e07b39",
            font=("Courier New", sc(9), "bold"), padx=4
        )
        self.filter_active_badge.pack(side="left")

        # Right links group
        sb_right = tk.Frame(self.sb_bottom, bg=statusbar_bg)
        sb_right.pack(side="right", fill="y")

        def _sb_link(parent, text, cmd):
            lbl = tk.Label(parent, text=text, bg=statusbar_bg, fg="#c8c8c8",
                           font=("Courier New", sc(9)), padx=8, cursor="hand2")
            lbl.pack(side="right")
            lbl.bind("<Button-1>", lambda e: cmd())
            lbl.bind("<Enter>", lambda e: lbl.config(fg="#ffffff"))
            lbl.bind("<Leave>", lambda e: lbl.config(fg="#c8c8c8"))
            return lbl

        _sb_link(sb_right, "DB_STATUS", self.ui.show_statistics)
        _sb_link(sb_right, "LOG_VIEWER", self.ui.open_log_viewer_window)

        # Wire backward-compatibility references on ui
        self.ui._status_bar_labels = self.labels
        self.ui._status_bar_problems_lbl = self.problems_lbl
        self.ui._filter_active_badge = self.filter_active_badge
        self.ui.sb_top = self.sb_top
        self.ui.sb_bottom = self.sb_bottom
        self.ui.sb_buttons_frame = self.sb_buttons_frame
        self.ui.sb_settings_btn = self.sb_settings_btn
        self.ui.sb_help_btn = self.sb_help_btn

        # Subscribe to app_bus events
        app_bus.subscribe(OBJECT_DATA_CHANGED, self._on_bus_data_changed)
        app_bus.subscribe(OBJECT_LOADED, self._on_bus_object_loaded)

    def _on_bus_data_changed(self, *args, **kwargs):
        if self.frame.winfo_exists():
            self.update_object_count()
            self.update_review_progress()

    def _on_bus_object_loaded(self, *args, **kwargs):
        if self.frame.winfo_exists():
            self.update_object_count()
            self.update_review_progress()

    def update_object_count(self):
        """Update object counter, problems count, and filter active indicator."""
        if not self.frame.winfo_exists():
            return

        app = self.ui.app
        count = len(app.active_object_ids) if app.active_object_ids else 0
        total = len(app.df_reg) if app.df_reg is not None else 0

        if hasattr(self.ui, "search_count_label") and self.ui.search_count_label is not None:
            try:
                if self.ui.search_count_label.winfo_exists():
                    self.ui.search_count_label.config(text=f"Objects: {count} / {total}")
            except Exception:
                pass

        if "object_count" in self.labels:
            self.labels["object_count"].config(text=f"OBJECT_COUNT: {total:,}")

            if app.df_obs is not None and len(app.df_obs) > 0:
                df_obs = app.df_obs
                rev = int(df_obs[REVIEWED_COLUMN].sum()) if REVIEWED_COLUMN in df_obs.columns else 0
                pct = int((rev / len(df_obs)) * 100)
                if "reviewed" in self.labels:
                    self.labels["reviewed"].config(text=f"REVIEWED: {pct}%")

                if getattr(self.ui, "_row_cache_dirty", True) or not hasattr(self.ui, "_cached_problems_count"):
                    try:
                        prob_cols = [
                            c for c in df_obs.columns
                            if c not in (REVIEWED_COLUMN, "ReviewedAt")
                            and str(df_obs[c].dtype) == "bool"
                        ]
                        self.ui._cached_problems_count = int((df_obs[prob_cols].any(axis=1)).sum()) if prob_cols else 0
                    except Exception:
                        self.ui._cached_problems_count = 0

                problems_count = self.ui._cached_problems_count
                if "problems" in self.labels:
                    self.labels["problems"].config(text=f"PROBLEMS: {problems_count}")
                if hasattr(self, "problems_lbl") and self.problems_lbl.winfo_exists():
                    self.problems_lbl.config(fg="#ff6b6b" if problems_count > 0 else "#e2e2e2")

        if hasattr(self, "filter_active_badge") and self.filter_active_badge.winfo_exists():
            shown = len(app.active_object_ids) if app.active_object_ids else 0
            is_filtered = (shown < total) and total > 0
            self.filter_active_badge.config(
                text=" ● FILTER" if is_filtered else "",
                fg="#e07b39"
            )

    def update_review_progress(self):
        """Update the review progress bar and label."""
        if not self.frame.winfo_exists():
            return

        app = self.ui.app
        if app.df_obs is None:
            return

        total = len(app.df_obs)
        if total == 0:
            return

        reviewed = int(app.df_obs[REVIEWED_COLUMN].sum())
        percent = int((reviewed / total) * 100)

        if hasattr(self.ui, "review_progress") and self.ui.review_progress is not None:
            try:
                if self.ui.review_progress.winfo_exists():
                    self.ui.review_progress["value"] = percent
                    self.ui.review_progress["maximum"] = 100
            except Exception:
                pass

        if hasattr(self.ui, "review_progress_label") and self.ui.review_progress_label is not None:
            try:
                if self.ui.review_progress_label.winfo_exists():
                    self.ui.review_progress_label.config(
                        text=f"Reviewed: {percent}% ({reviewed}/{total})"
                    )
            except Exception:
                pass
