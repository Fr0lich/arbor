"""PySide6 implementation of the Database Statistics Dashboard.

Wraps ``qt designer/database_statistics.ui`` and binds aggregated record metrics,
completion percentages, problem breakdown tables, and progress bars from AppState.
"""
from __future__ import annotations

import csv
from datetime import datetime
import os
from typing import Optional

import pandas as pd
from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QDialog,
    QHeaderView,
    QMessageBox,
    QTableWidgetItem,
    QWidget,
)

from config import ALL_UNKNOWN_TOKENS, PROBLEM_CATEGORY_THEMES
from models import AppState
from repository import REVIEWED_COLUMN
from ui_qt.loader import load_ui


class QtDatabaseStatisticsDialog:
    """Controller wrapping ``qt designer/database_statistics.ui``."""

    def __init__(self, parent: Optional[QWidget] = None, app_state: Optional[AppState] = None):
        self.parent = parent
        self.app = app_state or AppState()
        self.win: QDialog = load_ui("database_statistics.ui", parent)

        self._setup_ui()
        self.refresh()

    def _setup_ui(self) -> None:
        """Configure widget behaviors, table headers, and shortcuts."""
        # Connect close button
        if hasattr(self.win, "btn_close"):
            self.win.btn_close.clicked.connect(self.win.accept)

        # Setup problem breakdown table
        if hasattr(self.win, "table_problems"):
            table = self.win.table_problems
            table.setColumnCount(2)
            table.setHorizontalHeaderLabels(["Problem Category", "Count"])
            table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
            table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
            table.verticalHeader().setVisible(False)
            table.setSelectionBehavior(table.SelectionBehavior.SelectRows)
            table.setEditTriggers(table.EditTrigger.NoEditTriggers)

        # ESC to close
        QShortcut(QKeySequence(Qt.Key.Key_Escape), self.win).activated.connect(self.win.accept)

    def refresh(self) -> None:
        """Calculate metrics from AppState and update all dashboard widgets."""
        df_reg = self.app.df_reg
        df_obs = self.app.df_obs
        total = len(df_reg) if df_reg is not None else 0

        # Update database info label
        db_path = self.app.excel_path or "No database loaded"
        filename = os.path.basename(db_path) if self.app.excel_path else "No active database"
        if hasattr(self.win, "lbl_db_info"):
            self.win.lbl_db_info.setText(f"Active Database: {filename} ({total} records)")

        if total == 0 or df_reg is None or df_obs is None:
            if hasattr(self.win, "bar_review_progress"):
                self.win.bar_review_progress.setValue(0)
            if hasattr(self.win, "lbl_prog_stats"):
                self.win.lbl_prog_stats.setText("Reviewed: 0 / 0 objects (0.0%)")
            if hasattr(self.win, "lbl_total_objects"):
                self.win.lbl_total_objects.setText("Total Objects: 0")
            if hasattr(self.win, "lbl_gbif_validated"):
                self.win.lbl_gbif_validated.setText("Taxonomy Validated: 0")
            if hasattr(self.win, "lbl_books_matched"):
                self.win.lbl_books_matched.setText("Historical Records Matched: 0")
            if hasattr(self.win, "lbl_probs_total"):
                self.win.lbl_probs_total.setText("Objects with Flagged Problems: 0")
            if hasattr(self.win, "table_problems"):
                self.win.table_problems.setRowCount(0)
            return

        # 1. Review Progress
        reviewed_count = (
            int(df_obs[REVIEWED_COLUMN].sum())
            if REVIEWED_COLUMN in df_obs.columns
            else 0
        )
        pct_reviewed = (reviewed_count / total * 100.0) if total > 0 else 0.0

        if hasattr(self.win, "bar_review_progress"):
            self.win.bar_review_progress.setRange(0, 100)
            self.win.bar_review_progress.setValue(int(pct_reviewed))

        if hasattr(self.win, "lbl_prog_stats"):
            self.win.lbl_prog_stats.setText(
                f"Reviewed: {reviewed_count} / {total} objects ({pct_reviewed:.1f}%)"
            )

        # 2. Record Metrics
        if hasattr(self.win, "lbl_total_objects"):
            self.win.lbl_total_objects.setText(f"Total Objects: {total}")

        # Taxonomy Validated count (GBIF or clean taxonomy)
        gbif_cols = [c for c in df_obs.columns if "gbif" in c.lower()]
        if gbif_cols:
            gbif_col = gbif_cols[0]
            val_s = df_obs[gbif_col].fillna("").astype(str).str.strip()
            gbif_count = int((val_s != "").sum())
        else:
            # Verified/reviewed with taxonomy present
            has_genus = (
                df_reg["Genus"].notna() & (df_reg["Genus"].astype(str).str.strip() != "")
                if "Genus" in df_reg.columns
                else pd.Series(False, index=df_reg.index)
            )
            gbif_count = int((has_genus & (df_obs[REVIEWED_COLUMN] if REVIEWED_COLUMN in df_obs.columns else False)).sum())

        if hasattr(self.win, "lbl_gbif_validated"):
            self.win.lbl_gbif_validated.setText(f"Taxonomy Validated: {gbif_count}")

        # Historical Books matched count
        matched_books = 0
        if getattr(self.app, "historical_dbs", None):
            all_hist_ids = set()
            for hdb in self.app.historical_dbs:
                h_df = hdb.get("df_reg")
                if h_df is not None and "ObjectID" in h_df.columns:
                    all_hist_ids.update(h_df["ObjectID"].dropna().astype(str).tolist())
                elif h_df is not None and hasattr(h_df, "index"):
                    all_hist_ids.update(h_df.index.dropna().astype(str).tolist())
            matched_books = len(set(df_reg.index.astype(str)).intersection(all_hist_ids))

        if hasattr(self.win, "lbl_books_matched"):
            self.win.lbl_books_matched.setText(f"Historical Records Matched: {matched_books}")

        # 3. Validation & Problems Breakdown
        # Gather problem definitions from config
        problem_defs = []
        cfg = getattr(self.app, "config", None)
        if cfg and "ui_sections" in cfg and "problems" in cfg["ui_sections"]:
            problem_defs = cfg["ui_sections"]["problems"]

        prob_columns = [p["name"] for p in problem_defs] if problem_defs else [
            c for c in df_obs.columns if c.endswith("_Problem") or c == "Other_problem"
        ]
        prob_to_field = {p["name"]: p.get("maps_to") for p in problem_defs} if problem_defs else {}
        prob_to_cat = {p["name"]: p.get("category", "notes") for p in problem_defs} if problem_defs else {}

        mask_any_problem = pd.Series(False, index=df_reg.index)
        problem_counts: dict[str, int] = {}
        category_counts: dict[str, int] = {}

        for prob_col in prob_columns:
            is_checked = pd.Series(False, index=df_reg.index)
            if prob_col in df_obs.columns:
                is_checked = df_obs[prob_col].fillna(False).astype(bool).reindex(df_reg.index, fill_value=False)

            is_missing = pd.Series(False, index=df_reg.index)
            is_unknown = pd.Series(False, index=df_reg.index)

            field = prob_to_field.get(prob_col)
            if field and field in df_reg.columns:
                reg_s = df_reg[field].reindex(df_reg.index, fill_value="")
                is_missing = reg_s.isna() | (reg_s.astype(str).str.strip() == "")
                is_unknown = reg_s.astype(str).str.strip().str.lower().isin(ALL_UNKNOWN_TOKENS)

            col_problem_mask = is_checked | is_missing | is_unknown
            cnt = int(col_problem_mask.sum())
            if cnt > 0:
                clean_name = prob_col.replace("_Problem", "").replace("_", " ")
                problem_counts[clean_name] = cnt

                cat = prob_to_cat.get(prob_col, "notes")
                category_counts[cat] = category_counts.get(cat, 0) + cnt

            mask_any_problem |= col_problem_mask

        objects_with_problems = int(mask_any_problem.sum())
        if hasattr(self.win, "lbl_probs_total"):
            self.win.lbl_probs_total.setText(f"Objects with Flagged Problems: {objects_with_problems}")

        # Populate table_problems with categories and problem breakdowns
        if hasattr(self.win, "table_problems"):
            table = self.win.table_problems
            table.setRowCount(0)

            rows: list[tuple[str, int, bool]] = []
            # Group by categories first
            sorted_cats = sorted(
                category_counts.keys(),
                key=lambda c: PROBLEM_CATEGORY_THEMES.get(c, {}).get("rank", 99),
            )
            for cat in sorted_cats:
                theme = PROBLEM_CATEGORY_THEMES.get(cat, {})
                cat_label = f"{theme.get('icon', '•')} {theme.get('label', cat.title()).upper()}"
                rows.append((cat_label, category_counts[cat], True))

            # Add specific problem rows
            for prob_name, cnt in sorted(problem_counts.items(), key=lambda x: x[1], reverse=True):
                rows.append((f"  └ {prob_name}", cnt, False))

            table.setRowCount(len(rows))
            for i, (name, count, is_category) in enumerate(rows):
                pct_str = f" ({int(count / total * 100)}%)" if total else ""
                item_name = QTableWidgetItem(name)
                item_count = QTableWidgetItem(f"{count}{pct_str}")

                if is_category:
                    font = item_name.font()
                    font.setBold(True)
                    item_name.setFont(font)
                    item_count.setFont(font)
                    item_name.setBackground(Qt.GlobalColor.lightGray)
                    item_count.setBackground(Qt.GlobalColor.lightGray)

                item_count.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                table.setItem(i, 0, item_name)
                table.setItem(i, 1, item_count)

    def save_session_stats(self) -> None:
        """Export session summary statistics to a CSV log file."""
        if not self.app.excel_path:
            QMessageBox.information(self.win, "No Database", "No database file loaded.")
            return

        base_path = self.app.excel_path
        stats_file = os.path.splitext(base_path)[0] + "_session_stats.csv"

        total = len(self.app.df_reg) if self.app.df_reg is not None else 0
        reviewed = (
            int(self.app.df_obs[REVIEWED_COLUMN].sum())
            if self.app.df_obs is not None and REVIEWED_COLUMN in self.app.df_obs.columns
            else 0
        )
        prob_cols = [c for c in self.app.df_obs.columns if c.endswith("_Problem")] if self.app.df_obs is not None else []
        problems = int(self.app.df_obs[prob_cols].any(axis=1).sum()) if prob_cols and self.app.df_obs is not None else 0

        file_exists = os.path.isfile(stats_file)
        try:
            with open(stats_file, mode="a", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                if not file_exists:
                    writer.writerow(["Date", "Total Objects", "Total Reviewed", "Total Problems"])
                writer.writerow([datetime.now().strftime("%Y-%m-%d %H:%M:%S"), total, reviewed, problems])
            QMessageBox.information(self.win, "Saved", f"Session statistics saved to:\n{stats_file}")
        except Exception as e:
            QMessageBox.critical(self.win, "Error", f"Failed to save statistics:\n{e}")

    def exec(self) -> int:
        return self.win.exec()

    def show(self) -> None:
        self.win.show()

    def __getattr__(self, name: str):
        """Forward unrecognized attributes to wrapped QDialog widget."""
        return getattr(self.win, name)
