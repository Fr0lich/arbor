import os
import tkinter as tk
from tkinter import ttk, messagebox
import config
from config import sc
from utils import debug_error
from repository import REVIEWED_COLUMN

class DashboardMixin:
    def open_session_dashboard_window(self):
        if self.dashboard_mode_var.get() == "Window":
            if hasattr(self, "dash_win") and self.dash_win.winfo_exists():
                self.dash_win.focus_set()
                return

            self.dash_win = tk.Toplevel(self.root)
            self.dash_win.title("Session Dashboard")
            import utils
            utils.center_and_fit_toplevel(self.dash_win, 400, 150)
            self._build_dashboard_ui(self.dash_win, is_embedded=False)
        else:
            if not hasattr(self, "dash_embedded_frame") or not self.dash_embedded_frame.winfo_exists():
                self.dash_embedded_frame = ttk.Frame(self.middle_frame, padding=15, relief="groove")
                self._build_dashboard_ui(self.dash_embedded_frame, is_embedded=True)

            if self.dash_embedded_frame.winfo_manager():
                self.dash_embedded_frame.pack_forget()
            else:
                self.dash_embedded_frame.pack(side="bottom", fill="x", pady=(10, 0))

            self.update_dashboard()


    def _build_dashboard_ui(self, parent, is_embedded=False):
        container = ttk.Frame(parent)
        container.pack(fill="both", expand=True)

        ttk.Label(container, text="📊 Session Dashboard", font=("Segoe UI", sc(12), "bold")).pack(anchor="w", pady=(0,10))

        grid_frame = ttk.Frame(container)
        grid_frame.pack(fill="x")
        grid_frame.columnconfigure(0, weight=1)
        grid_frame.columnconfigure(1, weight=1)

        lbl_rev = ttk.Label(grid_frame, text="Reviewed: 0 / 0 (0%)", font=("Segoe UI", sc(9), "bold"))
        lbl_rev.grid(row=0, column=0, sticky="w", pady=2)

        lbl_prob = ttk.Label(grid_frame, text="Objects with Problems: 0", font=("Segoe UI", sc(9), "bold"))
        lbl_prob.grid(row=0, column=1, sticky="w", pady=2)

        prog = ttk.Progressbar(container, orient="horizontal", mode="determinate")
        prog.pack(fill="x", pady=(15, 2))

        ttk.Button(container, text="📊 Open Analytics", command=self.show_statistics).pack(pady=(10, 0))

        if is_embedded:
            self.dash_embedded_reviewed_lbl = lbl_rev
            self.dash_embedded_problems_lbl = lbl_prob
            self.dash_embedded_progress = prog
        else:
            self.dash_reviewed_lbl = lbl_rev
            self.dash_problems_lbl = lbl_prob
            self.dash_progress = prog

        self.update_dashboard()


    def show_statistics(self):
        if self.app.df_reg is None or self.app.df_obs is None:
            messagebox.showinfo("No data", "Load an Excel file first")
            return

        win = tk.Toplevel(self.root)
        win.title("Statistics")
        import utils
        utils.center_and_fit_toplevel(win, 520, 720)
        win.bind("<Escape>", lambda e: win.destroy())

        canvas = tk.Canvas(win)
        scrollbar = ttk.Scrollbar(win, orient="vertical", command=canvas.yview)
        frame = ttk.Frame(canvas, padding=16)

        frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        canvas.create_window((0, 0), window=frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        total = len(self.app.df_reg)
        if total == 0:
            ttk.Label(frame, text="No data loaded").pack()
            return

        reviewed_count = int(self.app.df_obs[REVIEWED_COLUMN].sum())
        not_reviewed = total - reviewed_count
        with_problems = sum(1 for oid in self.app.df_reg.index if self.has_any_problem(oid))

        def pct(n):
            return f"{int(n / total * 100)}%" if total else "0%"

        def add_section(title, row_start):
            ttk.Label(
                frame, text=title, font=("Segoe UI", 11, "bold")
            ).grid(row=row_start, column=0, columnspan=2, sticky="w", pady=(16, 6))
            return row_start + 1

        def add_row(label, value, row, bold=False):
            font = ("Segoe UI", 9, "bold") if bold else ("Segoe UI", 9)
            ttk.Label(frame, text=label, foreground="gray").grid(
                row=row, column=0, sticky="w", padx=(12, 20), pady=1
            )
            ttk.Label(frame, text=value, font=font).grid(
                row=row, column=1, sticky="w", pady=1
            )

        r = 0

        # --- Oversikt ---
        r = add_section("Overall Statistics", r)
        add_row("Total objects", str(total), r); r += 1
        add_row("Reviewed", f"{reviewed_count}  ({pct(reviewed_count)})", r, bold=reviewed_count > 0); r += 1
        add_row("Not reviewed", f"{not_reviewed}  ({pct(not_reviewed)})", r); r += 1
        add_row("With problems", f"{with_problems}  ({pct(with_problems)})", r, bold=with_problems > 0); r += 1
        add_row("Currently filtered", f"{len(self.app.active_object_ids)} of {total}", r); r += 1

        # --- Session Statistics ---
        ttk.Separator(frame, orient="horizontal").grid(row=r, column=0, columnspan=2, sticky="ew", pady=8); r += 1
        r = add_section("Session Statistics", r)

        session_reviewed = 0
        problems_solved_total = 0
        problems_solved_breakdown = {}
        new_problems_total = 0

        if getattr(self.app, "initial_df_obs", None) is not None:
            common_idx = self.app.df_obs.index.intersection(self.app.initial_df_obs.index)
            if len(common_idx) > 0:
                current_obs = self.app.df_obs.loc[common_idx]
                initial_obs = self.app.initial_df_obs.loc[common_idx]

                if REVIEWED_COLUMN in current_obs.columns and REVIEWED_COLUMN in initial_obs.columns:
                    newly_reviewed = (initial_obs[REVIEWED_COLUMN] == False) & (current_obs[REVIEWED_COLUMN] == True)
                    session_reviewed = int(newly_reviewed.sum())

                for prob_col in self.problem_columns:
                    if prob_col in current_obs.columns and prob_col in initial_obs.columns:
                        solved = (initial_obs[prob_col] == True) & (current_obs[prob_col] == False)
                        solved_count = int(solved.sum())
                        if solved_count > 0:
                            problems_solved_breakdown[prob_col.replace("_", " ")] = solved_count
                            problems_solved_total += solved_count

                        new_prob = (initial_obs[prob_col] == False) & (current_obs[prob_col] == True)
                        new_problems_total += int(new_prob.sum())

        add_row("Newly reviewed today", str(session_reviewed), r, bold=session_reviewed > 0); r += 1
        add_row("Total problems solved", str(problems_solved_total), r, bold=problems_solved_total > 0); r += 1

        if problems_solved_total > 0:
            for prob_name, cnt in problems_solved_breakdown.items():
                add_row(f"  - {prob_name}", f"{cnt} solved", r); r += 1

        add_row("Problems Observed Today", str(new_problems_total), r); r += 1

        # --- Problemer ---
        ttk.Separator(frame, orient="horizontal").grid(row=r, column=0, columnspan=2, sticky="ew", pady=8); r += 1
        r = add_section("Total Problems", r)

        for prob_col in self.problem_columns:
            if prob_col in self.app.df_obs.columns:
                count = sum(1 for oid in self.app.df_reg.index if self.is_problem_active(oid, prob_col))
                label = prob_col.replace("_", " ")
                add_row(label, f"{count}  ({pct(count)})", r, bold=count > 0)
                r += 1

        ttk.Separator(frame, orient="horizontal").grid(row=r, column=0, columnspan=2, sticky="ew", pady=8); r += 1
        r = add_section("Problems in filtered", r)

        for prob_col in self.problem_columns:
            if prob_col in self.app.df_obs.columns:
                if self.app.active_object_ids:
                    count = sum(1 for oid in self.app.active_object_ids if self.is_problem_active(oid, prob_col))
                else:
                    count = 0
                label = prob_col.replace("_", " ")
                # Percentage of filtered objects
                filtered_total = len(self.app.active_object_ids)
                pct_filtered = f"{int(count / filtered_total * 100)}%" if filtered_total else "0%"
                add_row(label, f"{count}  ({pct_filtered})", r, bold=count > 0)
                r += 1

        # --- Per etasje ---
        if "Floor" in self.app.df_obs.columns:
            ttk.Separator(frame, orient="horizontal").grid(row=r, column=0, columnspan=2, sticky="ew", pady=8); r += 1
            r = add_section("Objects per floor", r)

            floor_counts = (
                self.app.df_obs["Floor"]
                .replace("", float("nan"))
                .dropna()
                .value_counts()
                .sort_index()
            )
            for floor_val, count in floor_counts.items():
                add_row(f"Floor {floor_val}", str(count), r)
                r += 1

            no_floor = int((self.app.df_obs["Floor"].astype(str).str.strip() == "").sum())
            if no_floor:
                add_row("No floor set", str(no_floor), r)
                r += 1

        btn_frame = ttk.Frame(frame)
        btn_frame.grid(row=r, column=0, columnspan=2, sticky="ew", pady=20)

        ttk.Button(btn_frame, text="Close", command=win.destroy).pack(side="right", padx=5)
        ttk.Button(btn_frame, text="Save Session Stats", command=self.save_session_stats).pack(side="left", padx=5)


    def save_session_stats(self):
        import os, csv
        from datetime import datetime
        if not self.app.excel_path:
            messagebox.showinfo("Error", "No Excel file loaded.")
            return

        base_path = self.app.excel_path
        stats_file = os.path.splitext(base_path)[0] + "_session_stats.csv"

        total = len(self.app.df_reg)
        reviewed = int(self.app.df_obs[REVIEWED_COLUMN].sum())
        problems = sum(1 for oid in self.app.df_reg.index if self.has_any_problem(oid))

        # In a real app we'd track session duration, here we mock it or track from startup
        duration_mins = (datetime.now() - getattr(self.app, "session_start_time", datetime.now())).total_seconds() / 60

        file_exists = os.path.isfile(stats_file)

        try:
            with open(stats_file, mode="a", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                if not file_exists:
                    writer.writerow(["Date", "Duration (mins)", "Total Objects", "Total Reviewed", "Total Problems"])
                writer.writerow([datetime.now().strftime("%Y-%m-%d %H:%M:%S"), round(duration_mins, 1), total, reviewed, problems])
            messagebox.showinfo("Saved", f"Session statistics saved to:\n{stats_file}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save stats:\n{e}")


    def update_dashboard(self):
        if self.app.df_obs is None or self.app.df_reg is None:
            return

        total = len(self.app.df_obs)
        if total == 0:
            return

        reviewed = int(self.app.df_obs[REVIEWED_COLUMN].sum())
        pct = int((reviewed / total) * 100)

        current_oid = self.app.current_object_id
        problems_count = 0
        for oid in self.app.df_obs.index:
            if oid == current_oid and self.object_loaded:
                has_any_prob = any(
                    self.problem_vars.get(p).get()
                    for p in self.problem_columns
                    if self.problem_vars.get(p)
                )
                if has_any_prob:
                    problems_count += 1
            else:
                has_any_prob = any(
                    bool(self.app.df_obs.loc[oid, p])
                    for p in self.problem_columns
                    if p in self.app.df_obs.columns
                )
                if has_any_prob:
                    problems_count += 1

        # Update Window mode dashboard
        if hasattr(self, "dash_reviewed_lbl") and self.dash_reviewed_lbl.winfo_exists():
            self.dash_reviewed_lbl.config(text=f"Reviewed: {reviewed} / {total} ({pct}%)")
            self.dash_problems_lbl.config(text=f"Objects with Problems: {problems_count}")
            self.dash_progress["value"] = pct

        # Update Embedded mode dashboard
        if hasattr(self, "dash_embedded_reviewed_lbl") and self.dash_embedded_reviewed_lbl.winfo_exists():
            self.dash_embedded_reviewed_lbl.config(text=f"Reviewed: {reviewed} / {total} ({pct}%)")
            self.dash_embedded_problems_lbl.config(text=f"Objects with Problems: {problems_count}")
            self.dash_embedded_progress["value"] = pct

        if hasattr(self, "review_progress_label") and self.review_progress_label is not None:
            self.review_progress_label.config(text=f"Reviewed: {pct}% ({reviewed}/{total})")
        if hasattr(self, "review_progress") and self.review_progress is not None:
            self.review_progress["value"] = pct
