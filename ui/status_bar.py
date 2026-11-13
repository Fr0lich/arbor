import tkinter as tk
from tkinter import ttk
from repository import REVIEWED_COLUMN
from ui.state import app_bus, OBJECT_DATA_CHANGED, OBJECT_LOADED


class StatusBarPanel:
    """Decoupled status bar component for Arbor desktop UI."""

    # Backward compatibility stub properties for legacy inspection scripts
    @property
    def sb_top(self):
        return None

    @sb_top.setter
    def sb_top(self, val):
        pass

    @property
    def sb_buttons_frame(self):
        return None

    @sb_buttons_frame.setter
    def sb_buttons_frame(self, val):
        pass

    @property
    def sb_settings_btn(self):
        return None

    @sb_settings_btn.setter
    def sb_settings_btn(self, val):
        pass

    @property
    def sb_help_btn(self):
        return None

    @sb_help_btn.setter
    def sb_help_btn(self, val):
        pass

    def __init__(self, parent_frame, ui):
        self.frame = parent_frame
        self.ui = ui
        self.labels = {}

        from config import sc

        statusbar_bg = "#1c1b1b"
        statusbar_fg = "#e2e2e2"
        # Single-row streamlined status bar: 26px height
        # Settings & Help are now hosted on the Top Navigation Bar.

        # Ensure sb_bottom references the single status bar frame
        self.sb_bottom = self.frame

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
        self.ui.sb_bottom = self.sb_bottom

        # Subscribe to app_bus events
        app_bus.subscribe_managed(self.frame, OBJECT_DATA_CHANGED, self._on_bus_data_changed)
        app_bus.subscribe_managed(self.frame, OBJECT_LOADED, self._on_bus_object_loaded)

    def update_status(self, total=None, reviewed=None, problems=None, last_save=None):
        """Update status bar telemetry labels directly or from active dataset."""
        if not self.frame.winfo_exists():
            return

        if total is None and reviewed is None and problems is None and last_save is None:
            self.update_object_count()
            self.update_review_progress()
            return

        if total is not None and "object_count" in self.labels:
            if isinstance(total, int):
                self.labels["object_count"].config(text=f"OBJECT_COUNT: {total:,}")
            else:
                self.labels["object_count"].config(text=f"OBJECT_COUNT: {total}")

        if reviewed is not None and "reviewed" in self.labels:
            self.labels["reviewed"].config(text=f"REVIEWED: {reviewed}")

        if problems is not None and "problems" in self.labels:
            self.labels["problems"].config(text=f"PROBLEMS: {problems}")
            if hasattr(self, "problems_lbl") and self.problems_lbl.winfo_exists():
                try:
                    prob_val = int(problems)
                    self.problems_lbl.config(fg="#ff6b6b" if prob_val > 0 else "#e2e2e2")
                except (ValueError, TypeError):
                    pass

        if last_save is not None and "last_save" in self.labels:
            self.labels["last_save"].config(text=f"LAST_SAVE: {last_save}")

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
