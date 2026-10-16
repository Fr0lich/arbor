"""ui_qt/gbif_review.py - GBIF Batch Taxonomy Reconciliation & Review Workspace.

Wraps 'qt designer/gbif_review.ui' (GBIFReviewDialog).
Features:
- Non-blocking chunked thread worker (GbifBatchReconciliationWorker)
- Fast multi-row review table with match status indicators (Confidence %, Rank, Accepted Name)
- Bulk selection controls (All, None, High Confidence >90%)
- Live search query filter
- Vectorized batch commits to app_state.df_reg, unflagging spelling problems, and structured audit logging.
"""
from __future__ import annotations

import getpass
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Tuple

import pandas as pd
from PySide6.QtCore import QObject, Qt, QThread, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QHeaderView,
    QMessageBox,
    QTableWidgetItem,
    QWidget,
)

from backend.gbif import check_gbif
from models import AppState
from repository import REVIEWED_COLUMN
from ui_qt.loader import load_ui


class GbifBatchReconciliationWorker(QThread):
    """Background worker executing GBIF taxonomy queries without blocking the UI thread."""

    progress_chunk = Signal(list, int, int)  # Emits (results_chunk, current_count, total_count)
    finished_all = Signal(list)              # Emits list of all resolved dicts

    def __init__(self, candidates: List[Dict[str, str]], parent: Optional[QObject] = None):
        super().__init__(parent)
        self.candidates = candidates
        self._is_cancelled = False

    def cancel(self) -> None:
        self._is_cancelled = True

    def run(self) -> None:
        all_results: List[Dict[str, Any]] = []
        chunk: List[Dict[str, Any]] = []
        total = len(self.candidates)

        for idx, item in enumerate(self.candidates):
            if self._is_cancelled:
                break

            oid = item.get("oid", "")
            genus = item.get("genus", "")
            species = item.get("species", "")

            result_entry: Dict[str, Any] = {
                "oid": oid,
                "orig_genus": genus,
                "orig_species": species,
                "orig_name": f"{genus} {species}".strip(),
                "matched_name": "—",
                "status": "NO MATCH",
                "confidence": 0,
                "gbif_data": {},
            }

            if genus:
                try:
                    res = check_gbif(genus, species)
                    if res and isinstance(res, dict) and not res.get("error"):
                        match_type = res.get("matchType", "NONE")
                        status = res.get("status", "UNKNOWN")
                        conf = int(res.get("confidence", 0))
                        sc_name = res.get("scientificName") or res.get("canonicalName") or ""

                        if match_type != "NONE" and sc_name:
                            result_entry["matched_name"] = sc_name
                            result_entry["status"] = status
                            result_entry["confidence"] = conf
                            result_entry["gbif_data"] = res
                except Exception:
                    result_entry["status"] = "ERROR"

            from backend.gbif import is_likely_family_name
            is_inversion = is_likely_family_name(species)
            has_rank_disc = False
            rank_disc_str = ""
            if is_inversion:
                has_rank_disc = True
                rank_disc_str = "⚠️ Species → Family"
            elif result_entry.get("gbif_data"):
                gb_d = result_entry["gbif_data"]
                r = (gb_d.get("rank") or "").upper()
                if r in ("FAMILY", "ORDER", "CLASS", "PHYLUM", "KINGDOM") or gb_d.get("matchType") == "HIGHERRANK":
                    has_rank_disc = True
                    rank_disc_str = f"⚠️ Rank Inversion ({r})"

            result_entry["has_rank_discrepancy"] = has_rank_disc
            result_entry["rank_discrepancy"] = rank_disc_str
            result_entry["auto_resolve_eligible"] = not has_rank_disc

            chunk.append(result_entry)
            all_results.append(result_entry)

            # Emit in chunks of 5 or at the end to minimize Qt event overhead
            if len(chunk) >= 5 or idx == total - 1:
                self.progress_chunk.emit(chunk, idx + 1, total)
                chunk = []

        self.finished_all.emit(all_results)


class QtGbifReviewDialog(QDialog):
    """Controller for GBIF Batch Taxonomy Reconciliation Review dialog."""

    def __init__(
        self,
        parent: Optional[QWidget] = None,
        app_state: Optional[AppState] = None,
        on_applied: Optional[Callable[[int], None]] = None,
        auto_start: bool = True,
    ):
        super().__init__(parent)
        self.app = app_state or AppState()
        self.on_applied = on_applied

        # Load declarative Qt Designer UI
        self.dialog = load_ui("gbif_review.ui")
        if parent:
            self.dialog.setParent(parent, Qt.Dialog)

        self.results: List[Dict[str, Any]] = []
        self.visible_indices: List[int] = []
        self.worker: Optional[GbifBatchReconciliationWorker] = None

        self._setup_table_headers()
        self._connect_signals()

        if auto_start:
            self.start_batch_reconciliation()

    def _setup_table_headers(self) -> None:
        """Format table dimensions and interactive column policies."""
        if not hasattr(self.dialog, "table_review"):
            return
        table = self.dialog.table_review
        header = table.horizontalHeader()
        table.setColumnCount(7)
        table.setHorizontalHeaderItem(6, QTableWidgetItem("Rank Discrepancy"))
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(6, QHeaderView.ResizeMode.Interactive)

        table.setColumnWidth(0, 50)
        table.setColumnWidth(1, 80)
        table.setColumnWidth(2, 160)
        table.setColumnWidth(4, 110)
        table.setColumnWidth(5, 90)
        table.setColumnWidth(6, 170)

    def _connect_signals(self) -> None:
        """Wire buttons and filter inputs to slots."""
        if hasattr(self.dialog, "btn_select_all"):
            self.dialog.btn_select_all.clicked.connect(self.select_all)
        if hasattr(self.dialog, "btn_deselect_all"):
            self.dialog.btn_deselect_all.clicked.connect(self.deselect_all)
        if hasattr(self.dialog, "btn_select_confident"):
            self.dialog.btn_select_confident.clicked.connect(self.select_confident)
        if hasattr(self.dialog, "input_search_review"):
            self.dialog.input_search_review.textChanged.connect(self._on_search_query_changed)
        if hasattr(self.dialog, "btn_cancel"):
            self.dialog.btn_cancel.clicked.connect(self.close)
        if hasattr(self.dialog, "btn_accept_selected"):
            self.dialog.btn_accept_selected.clicked.connect(self.accept_selected)

    # -------------------------------------------------------------------------
    # Worker Execution
    # -------------------------------------------------------------------------

    def _collect_unverified_candidates(self) -> List[Dict[str, str]]:
        """Collect records in df_reg needing GBIF verification."""
        candidates: List[Dict[str, str]] = []
        if self.app.df_reg is None:
            return candidates

        with self.app.df_lock:
            for oid in self.app.df_reg.index:
                row = self.app.df_reg.loc[oid]
                genus = str(row.get("Genus", "")).strip() if pd.notna(row.get("Genus", "")) else ""
                species = str(row.get("Species", "")).strip() if pd.notna(row.get("Species", "")) else ""

                if genus and genus.lower() not in ("nan", "", "none", "?"):
                    candidates.append({
                        "oid": str(oid),
                        "genus": genus,
                        "species": species,
                    })
        return candidates

    def start_batch_reconciliation(self, candidates: Optional[List[Dict[str, str]]] = None) -> None:
        """Launch background reconciliation thread."""
        target_candidates = candidates if candidates is not None else self._collect_unverified_candidates()
        if not target_candidates:
            if hasattr(self.dialog, "lbl_match_count"):
                self.dialog.lbl_match_count.setText("No eligible taxa found for batch review.")
            return

        self.results.clear()
        if hasattr(self.dialog, "table_review"):
            self.dialog.table_review.setRowCount(0)

        if hasattr(self.dialog, "lbl_match_count"):
            self.dialog.lbl_match_count.setText(f"Reconciling 0 of {len(target_candidates)}...")

        self.worker = GbifBatchReconciliationWorker(target_candidates, parent=self)
        self.worker.progress_chunk.connect(self._on_worker_chunk)
        self.worker.finished_all.connect(self._on_worker_finished)
        self.worker.start()

    def _on_worker_chunk(self, chunk: List[Dict[str, Any]], current: int, total: int) -> None:
        """Incrementally append results chunk to table."""
        self.results.extend(chunk)
        if hasattr(self.dialog, "lbl_match_count"):
            self.dialog.lbl_match_count.setText(f"Reconciled {current} of {total}...")
        self._refresh_table()

    def _on_worker_finished(self, all_results: List[Dict[str, Any]]) -> None:
        """Handle worker completion."""
        self.results = all_results
        self._refresh_table()
        self._update_selection_counter()

    # -------------------------------------------------------------------------
    # Table Population & Filtering
    # -------------------------------------------------------------------------

    def _refresh_table(self) -> None:
        """Populate table_review from results filtered by input_search_review."""
        if not hasattr(self.dialog, "table_review"):
            return

        table = self.dialog.table_review
        search_query = self.dialog.input_search_review.text().strip().lower() if hasattr(self.dialog, "input_search_review") else ""

        # Filter indices
        self.visible_indices = []
        for idx, res in enumerate(self.results):
            if not search_query:
                self.visible_indices.append(idx)
            else:
                oid = res.get("oid", "").lower()
                orig = res.get("orig_name", "").lower()
                matched = res.get("matched_name", "").lower()
                if search_query in oid or search_query in orig or search_query in matched:
                    self.visible_indices.append(idx)

        table.setUpdatesEnabled(False)
        table.setRowCount(len(self.visible_indices))

        for row_pos, res_idx in enumerate(self.visible_indices):
            res = self.results[res_idx]

            # Column 0: Checkbox
            chk = QCheckBox()
            # Preserve selection state or default to True if confident and not flagged with rank discrepancy
            default_checked = (
                res.get("confidence", 0) >= 90
                and res.get("status") == "ACCEPTED"
                and not res.get("has_rank_discrepancy")
            )
            chk.setChecked(res.get("checked", default_checked))
            chk.stateChanged.connect(lambda state, r_idx=res_idx: self._on_row_checked(r_idx, bool(state)))
            table.setCellWidget(row_pos, 0, chk)

            # Column 1: ObjectID
            item_oid = QTableWidgetItem(res.get("oid", ""))
            item_oid.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            table.setItem(row_pos, 1, item_oid)

            # Column 2: Original Name
            item_orig = QTableWidgetItem(res.get("orig_name", ""))
            item_orig.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            table.setItem(row_pos, 2, item_orig)

            # Column 3: Matched GBIF Name
            item_match = QTableWidgetItem(res.get("matched_name", "—"))
            item_match.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            table.setItem(row_pos, 3, item_match)

            # Column 4: Status
            status_text = res.get("status", "NO MATCH")
            item_stat = QTableWidgetItem(status_text)
            item_stat.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            if status_text == "ACCEPTED":
                item_stat.setForeground(Qt.darkGreen)
            elif status_text == "SYNONYM":
                item_stat.setForeground(Qt.darkYellow)
            else:
                item_stat.setForeground(Qt.darkRed)
            table.setItem(row_pos, 4, item_stat)

            # Column 5: Confidence
            conf_val = res.get("confidence", 0)
            item_conf = QTableWidgetItem(f"{conf_val}%" if conf_val else "—")
            item_conf.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            table.setItem(row_pos, 5, item_conf)

            # Column 6: Rank Discrepancy
            rank_disc = res.get("rank_discrepancy", "")
            item_rank = QTableWidgetItem(rank_disc if rank_disc else "—")
            item_rank.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            if res.get("has_rank_discrepancy"):
                item_rank.setForeground(Qt.red)
            else:
                item_rank.setForeground(Qt.gray)
            table.setItem(row_pos, 6, item_rank)

        table.setUpdatesEnabled(True)
        self._update_selection_counter()

    def _on_row_checked(self, res_idx: int, is_checked: bool) -> None:
        """Update result dict selection state."""
        if 0 <= res_idx < len(self.results):
            self.results[res_idx]["checked"] = is_checked
        self._update_selection_counter()

    def _on_search_query_changed(self, text: str) -> None:
        """Re-filter review table."""
        self._refresh_table()

    # -------------------------------------------------------------------------
    # Bulk Selection Controls
    # -------------------------------------------------------------------------

    def select_all(self) -> None:
        """Select all visible rows, strictly excluding items with rank discrepancies."""
        for idx in self.visible_indices:
            if not self.results[idx].get("has_rank_discrepancy"):
                self.results[idx]["checked"] = True
            else:
                self.results[idx]["checked"] = False
        self._refresh_table()

    def deselect_all(self) -> None:
        """Deselect all visible rows."""
        for idx in self.visible_indices:
            self.results[idx]["checked"] = False
        self._refresh_table()

    def select_confident(self) -> None:
        """Select only visible rows with confidence >= 90% and ACCEPTED status, strictly excluding rank discrepancies."""
        for idx in self.visible_indices:
            res = self.results[idx]
            if res.get("has_rank_discrepancy"):
                res["checked"] = False
            else:
                res["checked"] = res.get("confidence", 0) >= 90 and res.get("status") == "ACCEPTED"
        self._refresh_table()

    def _update_selection_counter(self) -> None:
        """Update matches label (e.g. 'Matches: 12 of 45 selected (3 rank discrepancies skipped)')."""
        if not hasattr(self.dialog, "lbl_match_count"):
            return
        selected = sum(1 for r in self.results if r.get("checked"))
        total = len(self.results)
        skipped = sum(1 for r in self.results if r.get("has_rank_discrepancy"))
        txt = f"Matches: {selected} of {total} selected"
        if skipped > 0:
            txt += f" (⚠️ {skipped} rank discrepancies require manual review)"
        self.dialog.lbl_match_count.setText(txt)

    # -------------------------------------------------------------------------
    # Vectorized Batch Commits
    # -------------------------------------------------------------------------

    def accept_selected(self) -> None:
        """Commit all checked GBIF updates atomically to app_state."""
        selected_items = [r for r in self.results if r.get("checked") and r.get("gbif_data")]
        if not selected_items:
            QMessageBox.information(self.dialog, "No Matches Selected", "Please select at least one GBIF match to apply.")
            return

        if self.app.df_reg is None:
            return

        now_iso = datetime.now().isoformat(timespec="seconds")
        user = getpass.getuser()

        applied_count = 0
        accepted_oids = []
        updates_dict: Dict[str, Dict[str, Any]] = {}
        log_rows: List[Dict[str, Any]] = []

        with self.app.df_lock:
            for item in selected_items:
                oid = item["oid"]
                if oid not in self.app.df_reg.index:
                    continue

                gbif_data = item["gbif_data"]
                row_updates: Dict[str, Any] = {}

                # Fields to map
                if "genus" in self.app.df_reg.columns and gbif_data.get("genus"):
                    row_updates["Genus"] = gbif_data["genus"]
                if "species" in self.app.df_reg.columns and gbif_data.get("species"):
                    row_updates["Species"] = gbif_data["species"]
                if "Author" in self.app.df_reg.columns and gbif_data.get("author"):
                    row_updates["Author"] = gbif_data["author"]
                if "Family" in self.app.df_reg.columns and gbif_data.get("family"):
                    row_updates["Family"] = gbif_data["family"]
                if "TaxonID" in self.app.df_reg.columns and (gbif_data.get("usageKey") or gbif_data.get("taxonKey")):
                    row_updates["TaxonID"] = str(gbif_data.get("usageKey") or gbif_data.get("taxonKey"))

                if row_updates:
                    updates_dict[oid] = row_updates
                    accepted_oids.append(oid)
                    applied_count += 1

                    # Log entry
                    log_rows.append({
                        "Timestamp": now_iso,
                        "User": user,
                        "Action": "GBIF_BATCH_UPDATE",
                        "ObjectID": oid,
                        "Reviewed": "",
                        "ChangedFields": "; ".join(row_updates.keys()),
                        "ChangedValues": f"Batch matched to {item.get('matched_name')}",
                        "ProblemsChanged": "Genus_Problem; Species_Problem",
                        "ProblemsChangedValues": "False; False",
                        "LocationChanged": "",
                        "LocationChangedValues": "",
                    })

            # Vectorized registry update
            if updates_dict:
                df_updates = pd.DataFrame.from_dict(updates_dict, orient="index")
                self.app.df_reg.update(df_updates)

            # Vectorized problem clearing in df_obs
            if self.app.df_obs is not None and accepted_oids:
                prob_cols = [c for c in ["Genus_Problem", "Species_Problem", "Author_Problem", "Family_Problem"] if c in self.app.df_obs.columns]
                valid_obs_oids = [o for o in accepted_oids if o in self.app.df_obs.index]
                if prob_cols and valid_obs_oids:
                    self.app.df_obs.loc[valid_obs_oids, prob_cols] = False

                # Mark Reviewed if present
                if REVIEWED_COLUMN in self.app.df_obs.columns and valid_obs_oids:
                    self.app.df_obs.loc[valid_obs_oids, REVIEWED_COLUMN] = True

            # Concatenate batch log entries
            if log_rows and self.app.df_log is not None:
                self.app.df_log = pd.concat([self.app.df_log, pd.DataFrame(log_rows)], ignore_index=True)

            self.app.dirty = True

        QMessageBox.information(
            self.dialog,
            "Reconciliation Applied",
            f"Successfully updated taxonomy for {applied_count} specimen(s).",
        )

        if self.on_applied:
            self.on_applied(applied_count)

        self.dialog.accept()

    def close(self) -> bool:
        """Cancel worker if active and close dialog."""
        if self.worker and self.worker.isRunning():
            self.worker.cancel()
            self.worker.wait(500)
        return self.dialog.close()

    def exec(self) -> int:
        return self.dialog.exec()

    def show(self) -> None:
        self.dialog.show()
