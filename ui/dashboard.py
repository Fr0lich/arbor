import tkinter as tk
from tkinter import ttk, messagebox
import pandas as pd
from config import sc
from repository import REVIEWED_COLUMN

class DashboardMixin:
    def show_statistics(self):
        if self.app.df_reg is None or self.app.df_obs is None:
            messagebox.showinfo("No data", "Load an Excel file first")
            return

        win = tk.Toplevel(self.root)
        win.title("Database Statistics")
        import utils
        try:
            utils.center_and_fit_toplevel(win, 650, 800)
        except Exception:
            win.geometry("650x800")
        win.bind("<Escape>", lambda e: win.destroy())

        # Initialize Fonts
        import tkinter.font as tkFont
        families = tkFont.families()
        ui_family = "Hanken Grotesk" if "Hanken Grotesk" in families else "Helvetica" if "Helvetica" in families else "Segoe UI" if "Segoe UI" in families else "sans-serif"
        mono_family = "JetBrains Mono" if "JetBrains Mono" in families else "Consolas" if "Consolas" in families else "Courier New"

        FONT_UI = (ui_family, sc(10))
        FONT_UI_BOLD = (ui_family, sc(10), "bold")
        FONT_UI_LG = (ui_family, sc(12), "bold")
        FONT_MONO_SM = (mono_family, sc(8))

        COLORS = {
            "bg": "#fbfaf8",
            "surface": "#ffffff",
            "surface_dim": "#e9ece5",
            "border": "#d1d1d1",
            "text": "#2c302e",
            "text_muted": "#444748",
            "primary": "#000000",
            "on_primary": "#ffffff",
            "success": "#3a7d44",
            "warning": "#f59e0b",
            "error": "#c93a40",
        }

        win.configure(bg=COLORS["bg"])

        # Header
        header = tk.Frame(win, bg=COLORS["surface"], height=sc(60))
        header.pack(fill="x", side="top")
        header.pack_propagate(False)
        tk.Frame(header, bg=COLORS["border"], height=1).pack(fill="x", side="bottom")

        tk.Label(header, text="DATABASE STATISTICS", font=FONT_UI_LG, fg=COLORS["primary"], bg=COLORS["surface"]).pack(side="left", padx=sc(24), pady=sc(16))

        # Footer
        footer = tk.Frame(win, bg=COLORS["surface_dim"], height=sc(60))
        footer.pack(fill="x", side="bottom")
        footer.pack_propagate(False)
        tk.Frame(footer, bg=COLORS["border"], height=1).pack(side="top", fill="x")

        btn_close = tk.Button(footer, text="CLOSE", font=FONT_UI_BOLD, fg=COLORS["text"], bg=COLORS["surface"], relief="solid", bd=1, padx=sc(16), pady=sc(8), command=win.destroy)
        btn_close.pack(side="right", padx=sc(16), pady=sc(12))

        btn_save = tk.Button(footer, text="SAVE SESSION STATS", font=FONT_UI_BOLD, fg=COLORS["on_primary"], bg=COLORS["primary"], relief="flat", bd=0, padx=sc(16), pady=sc(8), command=self.save_session_stats)
        btn_save.pack(side="right", padx=sc(8), pady=sc(12))

        # Main Scrollable Area
        main_area = tk.Frame(win, bg=COLORS["bg"])
        main_area.pack(fill="both", expand=True)

        canvas = tk.Canvas(main_area, bg=COLORS["bg"], highlightthickness=0)
        scrollbar = ttk.Scrollbar(main_area, orient="vertical", command=canvas.yview)
        scrollable_frame = tk.Frame(canvas, bg=COLORS["bg"])

        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw", width=win.winfo_width())

        def _on_canvas_configure(e):
            canvas.itemconfig(canvas.find_withtag("all")[0], width=e.width)
        canvas.bind("<Configure>", _on_canvas_configure)

        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # Mousewheel
        def _on_mousewheel(event):
            try:
                if canvas.winfo_exists():
                    canvas.yview_scroll(int(-1*(event.delta/120)), "units")
            except Exception:
                pass
        canvas.bind_all("<MouseWheel>", _on_mousewheel)

        def _cleanup(event=None):
            if event and event.widget != win:
                return
            try:
                canvas.unbind_all("<MouseWheel>")
            except Exception:
                pass
        win.bind("<Destroy>", _cleanup, add="+")

        # Stats calculations
        total = len(self.app.df_reg)
        if total == 0:
            tk.Label(scrollable_frame, text="No data loaded", font=FONT_UI, bg=COLORS["bg"], fg=COLORS["text_muted"]).pack(pady=sc(20))
            return

        reviewed_count = int(self.app.df_obs[REVIEWED_COLUMN].sum()) if REVIEWED_COLUMN in self.app.df_obs.columns else 0
        not_reviewed = total - reviewed_count

        mask_any_problem = pd.Series(False, index=self.app.df_reg.index)
        mask_actionable = pd.Series(False, index=self.app.df_reg.index)
        mask_image = pd.Series(False, index=self.app.df_reg.index)
        mask_unknown = pd.Series(False, index=self.app.df_reg.index)

        # Iterate over all possible problem columns
        for prob_col in getattr(self, "problem_columns", []):
            is_checked = pd.Series(False, index=self.app.df_reg.index)
            if prob_col in self.app.df_obs.columns:
                is_checked = self.app.df_obs[prob_col].fillna(False).astype(bool).reindex(self.app.df_reg.index, fill_value=False)

            is_missing = pd.Series(False, index=self.app.df_reg.index)
            is_unknown = pd.Series(False, index=self.app.df_reg.index)

            if hasattr(self, "problem_to_field") and prob_col in self.problem_to_field and prob_col != "Other_problem":
                field = self.problem_to_field.get(prob_col)
                if field and field != "Other" and field in self.app.df_reg.columns:
                    reg_s = self.app.df_reg[field].reindex(self.app.df_reg.index, fill_value="")
                    is_missing = reg_s.isna() | (reg_s.astype(str).str.strip() == "")
                    is_unknown = reg_s.astype(str).str.strip().str.lower().isin(["ukjent", "unknown", "?", "-"])

            # 1. Unknown issues: The field is explicitly marked as unknown
            mask_unknown |= is_unknown

            # 2. Any problem: Explicitly checked, OR missing, OR unknown
            mask_any_problem |= (is_checked | is_missing | is_unknown)

            # 3 & 4. Image vs Actionable
            if "Image" in prob_col:
                mask_image |= (is_checked | is_missing)
            else:
                # Actionable: It is a problem (checked or missing), but it is NOT marked as unknown
                mask_actionable |= ((is_checked | is_missing) & ~is_unknown)

        objects_with_problems = int(mask_any_problem.sum())
        actionable_problems = int(mask_actionable.sum())
        image_problems = int(mask_image.sum())
        issues_unknown = int(mask_unknown.sum())

        def _get_prob_series(prob_col, subset_idx=None, include_unknowns=False):
            # Keep this helper strictly for Card 3 and 4 total problem breakdown
            idx = self.app.df_reg.index if subset_idx is None else subset_idx
            obs_s = pd.Series(False, index=idx)
            if prob_col in self.app.df_obs.columns:
                vals = self.app.df_obs[prob_col].fillna(False).astype(bool)
                obs_s = vals.reindex(idx, fill_value=False)

            if hasattr(self, "problem_to_field") and prob_col in self.problem_to_field and prob_col != "Other_problem":
                field = self.problem_to_field.get(prob_col)
                if field and field != "Other" and field in self.app.df_reg.columns:
                    reg_s = self.app.df_reg[field].reindex(idx, fill_value="")
                    is_missing = reg_s.isna() | (reg_s.astype(str).str.strip() == "")
                    is_unknown = reg_s.astype(str).str.strip().str.lower().isin(["ukjent", "unknown", "?", "-"])
                    if include_unknowns:
                        obs_s |= (is_missing | is_unknown)
                    else:
                        obs_s |= (is_missing & ~is_unknown)
            return obs_s

        def pct(n):
            return f"{int(n / total * 100)}%" if total else "0%"

        # UI Builders
        def create_card(title, parent=scrollable_frame):
            card = tk.Frame(parent, bg=COLORS["surface"], highlightbackground=COLORS["border"], highlightthickness=1)
            card.pack(fill="x", padx=sc(24), pady=(sc(24), 0))

            card_header = tk.Frame(card, bg=COLORS["surface_dim"])
            card_header.pack(fill="x")
            tk.Label(card_header, text=title.upper(), font=FONT_UI_BOLD, fg=COLORS["text"], bg=COLORS["surface_dim"]).pack(side="left", padx=sc(16), pady=sc(10))
            tk.Frame(card, bg=COLORS["border"], height=1).pack(fill="x")

            content = tk.Frame(card, bg=COLORS["surface"])
            content.pack(fill="x", padx=sc(16), pady=sc(16))
            return content

        def add_row(parent, label, value, bold=False, value_color=COLORS["text"]):
            row = tk.Frame(parent, bg=COLORS["surface"])
            row.pack(fill="x", pady=sc(4))
            tk.Label(row, text=label, font=FONT_UI, fg=COLORS["text_muted"], bg=COLORS["surface"]).pack(side="left")
            font = FONT_UI_BOLD if bold else FONT_UI
            tk.Label(row, text=str(value), font=font, fg=value_color, bg=COLORS["surface"]).pack(side="right")
            return row

        # Card 1: Overall
        c_overall = create_card("OVERALL STATISTICS")
        add_row(c_overall, "Total objects", total, bold=True)
        add_row(c_overall, "Reviewed", f"{reviewed_count}  ({pct(reviewed_count)})", bold=reviewed_count > 0, value_color=COLORS["success"] if reviewed_count > 0 else COLORS["text"])
        add_row(c_overall, "Not reviewed", f"{not_reviewed}  ({pct(not_reviewed)})")
        add_row(c_overall, "Objects with problems", f"{objects_with_problems}  ({pct(objects_with_problems)})", bold=objects_with_problems > 0, value_color=COLORS["error"] if objects_with_problems > 0 else COLORS["text"])
        add_row(c_overall, 'Actionable problems (excluding "unknown" and Image Problems)', f"{actionable_problems}  ({pct(actionable_problems)})", bold=actionable_problems > 0, value_color=COLORS["error"] if actionable_problems > 0 else COLORS["text"])
        add_row(c_overall, "Image Problems", f"{image_problems}  ({pct(image_problems)})", bold=image_problems > 0, value_color=COLORS["warning"] if image_problems > 0 else COLORS["text"])
        add_row(c_overall, 'Issues (marked "unknown")', f"{issues_unknown}  ({pct(issues_unknown)})", bold=issues_unknown > 0, value_color=COLORS["warning"] if issues_unknown > 0 else COLORS["text"])

        active_count = len(self.app.active_object_ids) if hasattr(self.app, "active_object_ids") else 0
        add_row(c_overall, "Currently filtered", f"{active_count} of {total}")

        # Progress bar
        tk.Frame(c_overall, bg=COLORS["border"], height=1).pack(fill="x", pady=sc(12))
        tk.Label(c_overall, text="REVIEW PROGRESS", font=FONT_MONO_SM, fg=COLORS["text_muted"], bg=COLORS["surface"]).pack(anchor="w", pady=(0,sc(4)))

        prog_frame = tk.Frame(c_overall, bg=COLORS["surface_dim"], height=sc(12), highlightbackground=COLORS["border"], highlightthickness=1)
        prog_frame.pack(fill="x")
        prog_frame.pack_propagate(False)
        pct_val = reviewed_count / total if total > 0 else 0
        if pct_val > 0:
            tk.Frame(prog_frame, bg=COLORS["success"]).place(relwidth=pct_val, relheight=1.0)

        # Card 2: Session Statistics
        c_session = create_card("SESSION STATISTICS")
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

                for prob_col in getattr(self, "problem_columns", []):
                    if prob_col in current_obs.columns and prob_col in initial_obs.columns:
                        solved = (initial_obs[prob_col] == True) & (current_obs[prob_col] == False)
                        solved_count = int(solved.sum())
                        if solved_count > 0:
                            problems_solved_breakdown[prob_col.replace("_", " ")] = solved_count
                            problems_solved_total += solved_count

                        new_prob = (initial_obs[prob_col] == False) & (current_obs[prob_col] == True)
                        new_problems_total += int(new_prob.sum())

        add_row(c_session, "Newly reviewed today", session_reviewed, bold=session_reviewed > 0, value_color=COLORS["success"] if session_reviewed > 0 else COLORS["text"])
        add_row(c_session, "Total problems solved", problems_solved_total, bold=problems_solved_total > 0, value_color=COLORS["success"] if problems_solved_total > 0 else COLORS["text"])

        if problems_solved_total > 0:
            for prob_name, cnt in problems_solved_breakdown.items():
                add_row(c_session, f"  └ {prob_name}", f"{cnt} solved", value_color=COLORS["text_muted"])

        add_row(c_session, "Problems Observed Today", new_problems_total, bold=new_problems_total > 0, value_color=COLORS["warning"] if new_problems_total > 0 else COLORS["text"])

        # Card 3: Total Problems
        probs_content = None
        for prob_col in getattr(self, "problem_columns", []):
            if prob_col in self.app.df_obs.columns:
                count = int(_get_prob_series(prob_col, include_unknowns=True).sum())
                if count > 0:
                    if probs_content is None:
                        probs_content = create_card("TOTAL PROBLEMS BREAKDOWN")
                    label = prob_col.replace("_", " ")
                    add_row(probs_content, label, f"{count}  ({pct(count)})", bold=True, value_color=COLORS["error"])

        # Card 4: Problems in filtered
        if hasattr(self.app, "active_object_ids") and self.app.active_object_ids:
            filtered_total = len(self.app.active_object_ids)
            filtered_content = None
            for prob_col in getattr(self, "problem_columns", []):
                if prob_col in self.app.df_obs.columns:
                    count = int(_get_prob_series(prob_col, self.app.active_object_ids, include_unknowns=True).sum())
                    if count > 0:
                        if filtered_content is None:
                            filtered_content = create_card("PROBLEMS IN CURRENT FILTER")
                        label = prob_col.replace("_", " ")
                        pct_filtered = f"{int(count / filtered_total * 100)}%" if filtered_total else "0%"
                        add_row(filtered_content, label, f"{count}  ({pct_filtered})", bold=True, value_color=COLORS["error"])

        # Card 5: Per floor
        if "Floor" in self.app.df_obs.columns:
            floor_counts = (
                self.app.df_obs["Floor"]
                .replace("", float("nan"))
                .dropna()
                .value_counts()
                .sort_index()
            )
            no_floor = int((self.app.df_obs["Floor"].astype(str).str.strip() == "").sum())
            if not floor_counts.empty or no_floor > 0:
                c_floor = create_card("OBJECTS PER FLOOR")
                for floor_val, count in floor_counts.items():
                    add_row(c_floor, f"Floor {floor_val}", count)
                if no_floor:
                    add_row(c_floor, "No floor set", no_floor, value_color=COLORS["text_muted"])

        # Add bottom padding
        tk.Frame(scrollable_frame, bg=COLORS["bg"], height=sc(24)).pack(fill="x")

    def save_session_stats(self):
        import os, csv
        from datetime import datetime
        if not self.app.excel_path:
            messagebox.showinfo("Error", "No Excel file loaded.")
            return

        base_path = self.app.excel_path
        stats_file = os.path.splitext(base_path)[0] + "_session_stats.csv"

        total = len(self.app.df_reg)
        reviewed = int(self.app.df_obs[REVIEWED_COLUMN].sum()) if REVIEWED_COLUMN in self.app.df_obs.columns else 0
        if hasattr(self, "_problem_cache") and len(self._problem_cache) >= total:
            problems = sum(1 for oid in self.app.df_reg.index if self._problem_cache.get(oid, False))
        else:
            cols = [p for p in getattr(self, "problem_columns", []) if p in self.app.df_obs.columns]
            problems = int(self.app.df_obs[cols].any(axis=1).sum()) if cols else 0

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
        pass
