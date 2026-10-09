"""PySide6 implementation of Arbor's GBIF Single-Record Specimen Validator.

Wraps ``qt designer/gbif_dialog.ui`` to provide live backbone taxonomy verification,
side-by-side reconciliation diffs, and selective field commitment to AppState.
"""
from __future__ import annotations

from datetime import datetime
import threading
from typing import Callable, Optional

import pandas as pd
from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QDialog,
    QMessageBox,
    QWidget,
)

import backend.gbif
from models import AppState
from ui_qt import qss_tokens
from ui_qt.loader import load_ui


class _GbifWorkerSignals(QObject):
    """Signals for background GBIF queries."""
    finished = Signal(dict)
    failed = Signal(str)


class QtGbifUpdateDialog:
    """Controller for GBIF single-record taxonomy reconciliation dialog."""

    def __init__(
        self,
        parent: Optional[QWidget] = None,
        app_state: Optional[AppState] = None,
        oid: Optional[str] = None,
        on_applied: Optional[Callable[[dict], None]] = None,
        auto_query: bool = True,
        blocking_query: bool = False,
    ):
        self.parent = parent
        self.app = app_state or AppState()
        self.oid = str(oid or getattr(self.app, "current_object_id", "") or "")
        self.on_applied = on_applied
        self.dialog: QDialog = load_ui("gbif_dialog.ui", parent=parent)

        self.gbif_result: dict | None = None
        self.is_querying: bool = False
        self.current_data: dict[str, str] = {}
        self._signals = _GbifWorkerSignals()
        self._signals.finished.connect(self._on_query_completed)
        self._signals.failed.connect(self._on_query_failed)

        self._init_current_data()
        self._wire_signals()

        if auto_query and self.current_data.get("genus"):
            self.query_gbif(blocking=blocking_query)
        elif not self.current_data.get("genus"):
            if hasattr(self.dialog, "lbl_status"):
                self.dialog.lbl_status.setText("Genus is required for GBIF lookup.")
            if hasattr(self.dialog, "btn_accept"):
                self.dialog.btn_accept.setEnabled(False)

    def _init_current_data(self) -> None:
        """Extract and display metadata from AppState for active specimen."""
        df_reg = self.app.df_reg

        genus = ""
        species = ""
        author = ""
        family = ""
        taxon_id = ""

        if df_reg is not None and self.oid in df_reg.index:
            row = df_reg.loc[self.oid]
            genus = str(row.get("Genus", "")).strip() if pd.notna(row.get("Genus", "")) else ""
            species = str(row.get("Species", "")).strip() if pd.notna(row.get("Species", "")) else ""
            author = str(row.get("Author", "")).strip() if pd.notna(row.get("Author", "")) else ""
            family = str(row.get("Family", "")).strip() if pd.notna(row.get("Family", "")) else ""

            for key in ("TaxonID", "Taxon_ID", "TaxonKey", "taxonKey"):
                if key in df_reg.columns and pd.notna(row.get(key, "")):
                    taxon_id = str(row.get(key, "")).strip()
                    break

        sciname = f"{genus} {species} {author}".strip()
        canonical = f"{genus} {species}".strip()
        rank = "SPECIES" if species else ("GENUS" if genus else "—")

        self.current_data = {
            "genus": genus,
            "species": species,
            "author": author,
            "family": family,
            "taxon_id": taxon_id,
            "scientific_name": sciname,
            "canonical_name": canonical,
            "rank": rank,
        }

        # Populate Current labels in UI
        if hasattr(self.dialog, "lbl_target_info"):
            self.dialog.lbl_target_info.setText(f"Object #{self.oid}")
        if hasattr(self.dialog, "lbl_cur_sciname"):
            self.dialog.lbl_cur_sciname.setText(f"Scientific Name: {sciname or '—'}")
        if hasattr(self.dialog, "lbl_cur_canonical"):
            self.dialog.lbl_cur_canonical.setText(f"Canonical Name: {canonical or '—'}")
        if hasattr(self.dialog, "lbl_cur_genus"):
            self.dialog.lbl_cur_genus.setText(f"Genus: {genus or '—'}")
        if hasattr(self.dialog, "lbl_cur_species"):
            self.dialog.lbl_cur_species.setText(f"Species: {species or '—'}")
        if hasattr(self.dialog, "lbl_cur_author"):
            self.dialog.lbl_cur_author.setText(f"Author: {author or '—'}")
        if hasattr(self.dialog, "lbl_cur_family"):
            self.dialog.lbl_cur_family.setText(f"Family: {family or '—'}")
        if hasattr(self.dialog, "lbl_cur_rank"):
            self.dialog.lbl_cur_rank.setText(f"Rank: {rank}")
        if hasattr(self.dialog, "lbl_cur_status"):
            self.dialog.lbl_cur_status.setText("Status: Local Record")
        if hasattr(self.dialog, "lbl_cur_taxonkey"):
            self.dialog.lbl_cur_taxonkey.setText(f"Taxon Key: {taxon_id or '—'}")

        # Initially disable accept button until query result is ready
        if hasattr(self.dialog, "btn_accept"):
            self.dialog.btn_accept.setEnabled(False)

    def _wire_signals(self) -> None:
        """Connect button signals and keyboard shortcuts."""
        if hasattr(self.dialog, "btn_select_all"):
            self.dialog.btn_select_all.clicked.connect(self._select_all_fields)
        if hasattr(self.dialog, "btn_deselect_all"):
            self.dialog.btn_deselect_all.clicked.connect(self._deselect_all_fields)

        if hasattr(self.dialog, "btn_reject"):
            self.dialog.btn_reject.clicked.connect(self.dialog.reject)
        if hasattr(self.dialog, "btn_cancel"):
            self.dialog.btn_cancel.clicked.connect(self.dialog.reject)
        if hasattr(self.dialog, "btn_accept"):
            self.dialog.btn_accept.clicked.connect(self.apply_updates)

        QShortcut(QKeySequence("Escape"), self.dialog).activated.connect(self.dialog.reject)
        QShortcut(QKeySequence("Ctrl+Return"), self.dialog).activated.connect(self.apply_updates)
        QShortcut(QKeySequence("Ctrl+Enter"), self.dialog).activated.connect(self.apply_updates)

    def _select_all_fields(self) -> None:
        """Check all selective reconciliation checkboxes."""
        for name in ("chk_apply_genus", "chk_apply_species", "chk_apply_author", "chk_apply_family", "chk_apply_taxon_id"):
            widget = getattr(self.dialog, name, None)
            if widget:
                widget.setChecked(True)

    def _deselect_all_fields(self) -> None:
        """Uncheck all selective reconciliation checkboxes."""
        for name in ("chk_apply_genus", "chk_apply_species", "chk_apply_author", "chk_apply_family", "chk_apply_taxon_id"):
            widget = getattr(self.dialog, name, None)
            if widget:
                widget.setChecked(False)

    def query_gbif(self, blocking: bool = False) -> Optional[dict]:
        """Execute GBIF backbone taxonomy verification query."""
        genus = self.current_data.get("genus", "").strip()
        species = self.current_data.get("species", "").strip()

        if not genus:
            if hasattr(self.dialog, "lbl_status"):
                self.dialog.lbl_status.setText("Genus is required to check GBIF.")
            if hasattr(self.dialog, "btn_accept"):
                self.dialog.btn_accept.setEnabled(False)
            return None

        self.is_querying = True
        if hasattr(self.dialog, "lbl_status"):
            self.dialog.lbl_status.setText("Querying GBIF backbone taxonomy API...")
        if hasattr(self.dialog, "btn_accept"):
            self.dialog.btn_accept.setEnabled(False)

        def _worker():
            try:
                res = backend.gbif.check_gbif(genus, species)
                if res and isinstance(res, dict) and res.get("synonym") and res.get("acceptedUsageKey"):
                    acc = backend.gbif.get_accepted_name(res["acceptedUsageKey"])
                    if acc and isinstance(acc, dict) and "error" not in acc:
                        for k in ("genus", "species", "author", "family", "canonicalName", "scientificName", "rank", "status", "taxonKey", "usageKey"):
                            if k in acc and acc[k]:
                                res[k] = acc[k]
                return res
            except Exception as e:
                return {"error": str(e)}

        if blocking:
            res = _worker()
            if isinstance(res, dict) and "error" in res:
                self._on_query_failed(res["error"])
            else:
                self._on_query_completed(res or {})
            return res

        def _thread_target():
            res = _worker()
            if isinstance(res, dict) and "error" in res:
                self._signals.failed.emit(res["error"])
            else:
                self._signals.finished.emit(res or {})

        thread = threading.Thread(target=_thread_target, daemon=True)
        thread.start()
        return None

    def _on_query_failed(self, error_msg: str) -> None:
        """Handle network or API connection error."""
        self.is_querying = False
        if hasattr(self.dialog, "lbl_status"):
            self.dialog.lbl_status.setText(f"GBIF Error: {error_msg}")
            self.dialog.lbl_status.setStyleSheet(f"color: {qss_tokens.RED}; font-weight: bold;")
        if hasattr(self.dialog, "lbl_confidence_badge"):
            self.dialog.lbl_confidence_badge.setText("NETWORK ERROR")
            self.dialog.lbl_confidence_badge.setStyleSheet(
                f"background-color: {qss_tokens.RED}; color: #ffffff; padding: 3px 6px; font-weight: bold;"
            )
        if hasattr(self.dialog, "btn_accept"):
            self.dialog.btn_accept.setEnabled(False)

    def _on_query_completed(self, result: dict) -> None:
        """Populate GBIF suggested match card and diff details."""
        self.is_querying = False
        if not result or not result.get("genus"):
            if hasattr(self.dialog, "lbl_status"):
                self.dialog.lbl_status.setText("No taxonomic match found in GBIF backbone.")
                self.dialog.lbl_status.setStyleSheet(f"color: {qss_tokens.SUBTEXT}; font-weight: bold;")
            if hasattr(self.dialog, "lbl_confidence_badge"):
                self.dialog.lbl_confidence_badge.setText("NO MATCH")
                self.dialog.lbl_confidence_badge.setStyleSheet(
                    f"background-color: {qss_tokens.YELLOW}; color: #ffffff; padding: 3px 6px; font-weight: bold;"
                )
            if hasattr(self.dialog, "btn_accept"):
                self.dialog.btn_accept.setEnabled(False)
            return

        self.gbif_result = result

        sciname = result.get("scientificName", "")
        canonical = result.get("canonicalName", "")
        genus = result.get("genus", "")
        species = result.get("species", "")
        author = result.get("author", "")
        family = result.get("family", "")
        rank = result.get("rank", "SPECIES")
        status = result.get("status", "ACCEPTED")
        confidence = result.get("confidence", 0)
        taxon_key = str(result.get("usageKey") or result.get("taxonKey") or result.get("acceptedUsageKey") or "")

        # Populate Right card
        if hasattr(self.dialog, "lbl_gbif_sciname"):
            self.dialog.lbl_gbif_sciname.setText(f"Scientific Name: {sciname or '—'}")
        if hasattr(self.dialog, "lbl_gbif_canonical"):
            self.dialog.lbl_gbif_canonical.setText(f"Canonical Name: {canonical or '—'}")
        if hasattr(self.dialog, "lbl_gbif_genus"):
            self.dialog.lbl_gbif_genus.setText(f"Genus: {genus or '—'}")
        if hasattr(self.dialog, "lbl_gbif_species"):
            self.dialog.lbl_gbif_species.setText(f"Species: {species or '—'}")
        if hasattr(self.dialog, "lbl_gbif_author"):
            self.dialog.lbl_gbif_author.setText(f"Author: {author or '—'}")
        if hasattr(self.dialog, "lbl_gbif_family"):
            self.dialog.lbl_gbif_family.setText(f"Family: {family or '—'}")
        if hasattr(self.dialog, "lbl_gbif_rank"):
            self.dialog.lbl_gbif_rank.setText(f"Rank: {rank or '—'}")
        if hasattr(self.dialog, "lbl_gbif_status"):
            self.dialog.lbl_gbif_status.setText(f"Taxonomic Status: {status or '—'}")
        if hasattr(self.dialog, "lbl_gbif_taxonkey"):
            self.dialog.lbl_gbif_taxonkey.setText(f"Taxon Key: {taxon_key or '—'}")

        # Confidence Badge
        if hasattr(self.dialog, "lbl_confidence_badge"):
            conf_text = f"CONFIDENCE: {confidence}%" if confidence else f"STATUS: {status}"
            badge_color = qss_tokens.GREEN if confidence >= 90 else (qss_tokens.YELLOW if confidence >= 70 else qss_tokens.RED)
            self.dialog.lbl_confidence_badge.setText(conf_text)
            self.dialog.lbl_confidence_badge.setStyleSheet(
                f"background-color: {badge_color}; color: #ffffff; padding: 3px 6px; font-weight: bold;"
            )

        # Set default selection for checkboxes based on differences
        has_diff = False
        cur = self.current_data
        if hasattr(self.dialog, "chk_apply_genus"):
            g_diff = bool(genus and genus.strip().lower() != cur["genus"].strip().lower())
            self.dialog.chk_apply_genus.setChecked(g_diff or bool(genus))
            if g_diff: has_diff = True

        if hasattr(self.dialog, "chk_apply_species"):
            s_diff = bool(species and species.strip().lower() != cur["species"].strip().lower())
            self.dialog.chk_apply_species.setChecked(s_diff or bool(species))
            if s_diff: has_diff = True

        if hasattr(self.dialog, "chk_apply_author"):
            a_diff = bool(author and not backend.gbif.is_author_equivalent(cur["author"], author))
            self.dialog.chk_apply_author.setChecked(a_diff or bool(author))
            if a_diff: has_diff = True

        if hasattr(self.dialog, "chk_apply_family"):
            f_diff = bool(family and family.strip().lower() != cur["family"].strip().lower())
            self.dialog.chk_apply_family.setChecked(f_diff or (bool(family) and not cur["family"]))
            if f_diff: has_diff = True

        if hasattr(self.dialog, "chk_apply_taxon_id"):
            t_diff = bool(taxon_key and taxon_key.strip() != cur["taxon_id"].strip())
            self.dialog.chk_apply_taxon_id.setChecked(t_diff or bool(taxon_key))
            if t_diff: has_diff = True

        if hasattr(self.dialog, "btn_accept"):
            self.dialog.btn_accept.setEnabled(True)

        if hasattr(self.dialog, "lbl_status"):
            match_type = result.get("matchType", "MATCH")
            diff_note = "Differences detected." if has_diff else "Record is currently up to date."
            self.dialog.lbl_status.setText(f"{match_type} match ready. {diff_note}")
            self.dialog.lbl_status.setStyleSheet(f"color: {qss_tokens.GREEN if has_diff else qss_tokens.SUBTEXT}; font-weight: bold;")

    def apply_updates(self) -> None:
        """Commit selected taxonomy fields to AppState, undo stacks, and audit log."""
        if not self.gbif_result or not self.oid:
            return

        df_reg = self.app.df_reg
        df_obs = self.app.df_obs

        if df_reg is None or self.oid not in df_reg.index:
            QMessageBox.warning(self.dialog, "Error", f"Object #{self.oid} not found in database.")
            return

        selected_updates = {}
        if hasattr(self.dialog, "chk_apply_genus") and self.dialog.chk_apply_genus.isChecked():
            if self.gbif_result.get("genus"):
                selected_updates["Genus"] = self.gbif_result["genus"]

        if hasattr(self.dialog, "chk_apply_species") and self.dialog.chk_apply_species.isChecked():
            if self.gbif_result.get("species"):
                selected_updates["Species"] = self.gbif_result["species"]

        if hasattr(self.dialog, "chk_apply_author") and self.dialog.chk_apply_author.isChecked():
            if self.gbif_result.get("author"):
                selected_updates["Author"] = self.gbif_result["author"]

        if hasattr(self.dialog, "chk_apply_family") and self.dialog.chk_apply_family.isChecked():
            if self.gbif_result.get("family"):
                selected_updates["Family"] = self.gbif_result["family"]

        taxon_key = str(
            self.gbif_result.get("usageKey")
            or self.gbif_result.get("taxonKey")
            or self.gbif_result.get("acceptedUsageKey")
            or ""
        )
        if hasattr(self.dialog, "chk_apply_taxon_id") and self.dialog.chk_apply_taxon_id.isChecked():
            if taxon_key:
                # Target existing column or default to TaxonID
                target_col = "TaxonID"
                for col in ("TaxonID", "Taxon_ID", "TaxonKey"):
                    if col in df_reg.columns:
                        target_col = col
                        break
                selected_updates[target_col] = taxon_key

        if not selected_updates:
            QMessageBox.information(
                self.dialog,
                "No Changes Selected",
                "Please select at least one field to update.",
            )
            return

        # 1. Snapshot Undo State
        reg_snap = df_reg.loc[self.oid].copy()
        obs_snap = df_obs.loc[self.oid].copy() if (df_obs is not None and self.oid in df_obs.index) else {}
        self.app.undo_stacks.setdefault(self.oid, []).append({
            "reg": reg_snap,
            "obs": obs_snap,
        })
        if hasattr(self.app, "redo_stacks") and isinstance(self.app.redo_stacks, dict):
            self.app.redo_stacks.setdefault(self.oid, []).clear()

        # 2. Commit updates to df_reg
        reg_changed_fields = []
        reg_changed_values = []
        for field, new_val in selected_updates.items():
            old_val = str(df_reg.loc[self.oid, field]) if field in df_reg.columns and pd.notna(df_reg.loc[self.oid, field]) else ""
            if old_val != str(new_val):
                reg_changed_fields.append(field)
                reg_changed_values.append(f'{field}: "{old_val}" -> "{new_val}"')
            df_reg.at[self.oid, field] = str(new_val)

        # 3. Auto-clear mapped problem flags in df_obs
        prob_changed_fields = []
        prob_changed_values = []
        if df_obs is not None and self.oid in df_obs.index:
            problem_map = {
                "Genus": "Genus_Problem",
                "Species": "Species_Problem",
                "Author": "Author_Problem",
                "Family": "Family_Problem",
            }
            for reg_f, prob_col in problem_map.items():
                if reg_f in selected_updates and prob_col in df_obs.columns:
                    val = df_obs.loc[self.oid, prob_col]
                    if pd.notna(val) and bool(val):
                        df_obs.at[self.oid, prob_col] = False
                        prob_changed_fields.append(prob_col)
                        prob_changed_values.append(f'{prob_col}: "True" -> "False"')

        # 4. Append audit log entry to df_log
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_entry = {
            "Timestamp": now_str,
            "User": getattr(self.app, "current_user", "Arbor User"),
            "Action": "GBIF_UPDATE",
            "ObjectID": self.oid,
            "Reviewed": "",
            "ChangedFields": "; ".join(reg_changed_fields),
            "ChangedValues": "; ".join(reg_changed_values),
            "ProblemsChanged": "; ".join(prob_changed_fields),
            "ProblemsChangedValues": "; ".join(prob_changed_values),
            "LocationChanged": "",
            "LocationChangedValues": "",
        }

        if hasattr(self.app, "_log_records") and isinstance(self.app._log_records, list):
            self.app._log_records.append(log_entry)

        df_log_row = pd.DataFrame([log_entry])
        if self.app.df_log is not None and not self.app.df_log.empty:
            self.app.df_log = pd.concat([self.app.df_log, df_log_row], ignore_index=True)
        else:
            self.app.df_log = df_log_row

        self.app.dirty = True

        if self.on_applied:
            try:
                self.on_applied({
                    "oid": self.oid,
                    "updated_fields": selected_updates,
                    "reg_changed_fields": reg_changed_fields,
                    "prob_changed_fields": prob_changed_fields,
                })
            except Exception:
                pass

        self.dialog.accept()

    def exec(self) -> int:
        """Display modal dialog and return exit code."""
        return self.dialog.exec()

    def show(self) -> None:
        """Display non-modal dialog."""
        self.dialog.show()
