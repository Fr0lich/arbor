"""scratch/execute_parity_audit.py
Phase 6: Live Data Side-by-Side Parity Verification & Review Test Harness.
Executes identical end-to-end user journeys on Tkinter and PySide6 runtimes
with mock_current_db.xlsx and mock_historical_books.xlsx loaded into memory.
"""
import os
import sys
import copy
import time
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config
config.UI_SCALE = 1.0

from models import AppState
from repository import ExcelRepository, _open_excel_reader, _normalize_object_id_series

MOCK_DB_PATH = os.path.abspath("scratch/mock_current_db.xlsx")
MOCK_BOOKS_PATH = os.path.abspath("scratch/mock_historical_books.xlsx")

results = {
    "tkinter": {},
    "qt": {},
    "comparisons": {}
}

def load_raw_data():
    cfg = config.DATABASE_CONFIGS["Økonomisk Botanisk"]
    df_reg, df_obs, df_photo, df_log, df_unval = ExcelRepository.load_excel(MOCK_DB_PATH, cfg)
    
    if "ObjectID" in df_reg.columns:
        df_reg["ObjectID"] = _normalize_object_id_series(df_reg["ObjectID"])
        df_reg_indexed = df_reg.set_index("ObjectID")
    else:
        df_reg_indexed = df_reg
        
    if "ObjectID" in df_obs.columns:
        df_obs["ObjectID"] = _normalize_object_id_series(df_obs["ObjectID"])
        df_obs_indexed = df_obs.set_index("ObjectID")
    else:
        df_obs_indexed = df_obs

    # Load historical books
    historical_dbs = []
    with _open_excel_reader(MOCK_BOOKS_PATH) as xls:
        for sheet in xls.sheet_names:
            h_df = pd.read_excel(xls, sheet_name=sheet)
            if "ObjectID" in h_df.columns:
                h_df["ObjectID"] = _normalize_object_id_series(h_df["ObjectID"])
                historical_dbs.append({
                    "name": f"Books: {sheet}",
                    "path": MOCK_BOOKS_PATH,
                    "df_reg": h_df,
                    "reg_by_id": h_df.set_index("ObjectID"),
                    "dict_cache": h_df.set_index("ObjectID").to_dict(orient="index")
                })

    return cfg, df_reg, df_obs, df_reg_indexed, df_obs_indexed, df_photo, df_log, df_unval, historical_dbs

# Non-blocking dialog patches
from PySide6.QtWidgets import QMessageBox
QMessageBox.information = lambda *args, **kwargs: QMessageBox.StandardButton.Ok
QMessageBox.warning = lambda *args, **kwargs: QMessageBox.StandardButton.Ok
QMessageBox.critical = lambda *args, **kwargs: QMessageBox.StandardButton.Ok
QMessageBox.question = lambda *args, **kwargs: QMessageBox.StandardButton.Yes

import tkinter.messagebox
tkinter.messagebox.showinfo = lambda *args, **kwargs: None
tkinter.messagebox.showwarning = lambda *args, **kwargs: None
tkinter.messagebox.showerror = lambda *args, **kwargs: None
tkinter.messagebox.askyesno = lambda *args, **kwargs: True

# ==============================================================================
# AUDIT 1: QT RUNTIME UNDER LIVE DATA
# ==============================================================================
def audit_qt_runtime():
    print("\n=======================================================")
    print("=== EXECUTING AUDIT ON PYSIDE6 / QT WORKSTATION ===")
    print("=======================================================")
    from PySide6.QtWidgets import QApplication
    from PySide6.QtCore import Qt
    from ui_qt.main_window import QtMainWindow
    from ui_qt.filter_dialog import QtFilterDialog
    from ui_qt.problem_queue import QtProblemQueueDialog
    from ui_qt.historical_resolver import QtHistoricalResolverDialog
    from ui_qt.gbif_dialog import QtGbifUpdateDialog
    from ui_qt.gbif_review import QtGbifReviewDialog
    from ui_qt.bulk_edit import QtBulkEditDialog

    app = QApplication.instance() or QApplication(sys.argv)
    cfg, df_reg_raw, df_obs_raw, df_reg, df_obs, df_photo, df_log, df_unval, historical_dbs = load_raw_data()

    qt_state = AppState()
    qt_state.config = cfg
    qt_state.config_name = "Økonomisk Botanisk"
    qt_win = QtMainWindow(qt_state)

    # 1. Loading DB via open_excel
    qt_win.open_excel(MOCK_DB_PATH)
    qt_win.load_books(MOCK_BOOKS_PATH)

    qt_res = results["qt"]
    qt_res["loaded_records_count"] = len(qt_state.df_reg) if qt_state.df_reg is not None else 0
    qt_res["df_reg_index_type"] = str(type(qt_state.df_reg.index))
    qt_res["df_reg_index_sample"] = list(qt_state.df_reg.index[:5])
    qt_res["active_object_ids_sample"] = qt_state.active_object_ids[:5]
    qt_res["tree_item_count"] = qt_win.win.tree_objects.topLevelItemCount()
    qt_res["tree_items_sample"] = [
        (qt_win.win.tree_objects.topLevelItem(i).text(0),
         qt_win.win.tree_objects.topLevelItem(i).text(1),
         qt_win.win.tree_objects.topLevelItem(i).text(2))
        for i in range(min(5, qt_win.win.tree_objects.topLevelItemCount()))
    ]

    # Splitter geometry
    sizes = qt_win.win.splitter_main.sizes() if hasattr(qt_win.win, "splitter_main") else []
    qt_res["splitter_sizes"] = sizes

    # Check status bar metrics
    qt_res["status_objects"] = qt_win.win.lbl_sb_object_count.text() if hasattr(qt_win.win, "lbl_sb_object_count") else "N/A"
    qt_res["status_reviewed"] = qt_win.win.lbl_sb_reviewed.text() if hasattr(qt_win.win, "lbl_sb_reviewed") else "N/A"
    qt_res["status_problems"] = qt_win.win.lbl_sb_problems.text() if hasattr(qt_win.win, "lbl_sb_problems") else "N/A"

    # Test Selection & Form Binding
    # Select first item
    first_item = qt_win.win.tree_objects.topLevelItem(0)
    qt_win.win.tree_objects.setCurrentItem(first_item)
    qt_res["selected_oid"] = qt_state.current_object_id
    qt_res["lbl_specimen_name"] = qt_win.win.lbl_specimen_name.text() if hasattr(qt_win.win, "lbl_specimen_name") else "N/A"
    qt_res["lbl_id_badge"] = qt_win.win.lbl_id_badge.text() if hasattr(qt_win.win, "lbl_id_badge") else "N/A"
    
    # Check if form fields are rendered in tab_general
    general_inputs = qt_win.win.tab_general.findChildren(object)
    qt_res["tab_general_inputs_count"] = len(general_inputs)

    # 2. Test Search in Qt
    qt_win.win.edit_search.setText("Pinus")
    qt_res["search_pinus_matched_count"] = len(qt_state.active_object_ids)
    qt_res["search_pinus_matched_sample"] = qt_state.active_object_ids[:5]
    qt_win.win.edit_search.setText("") # reset

    # 3. Test Filter Dialog in Qt
    filter_dialog = QtFilterDialog(parent=None, app_state=qt_state)
    # Check tabs populated
    qt_res["filter_tabs_count"] = filter_dialog.dialog.tabs_filter.count()
    qt_res["filter_tab_names"] = [filter_dialog.dialog.tabs_filter.tabText(i) for i in range(filter_dialog.dialog.tabs_filter.count())]
    
    # Apply filter for unreviewed items (Reviewed == False)
    # Tri-state cycling: 0 -> None, 1 -> True, 2 -> False
    # Let's test filter execution via backend/filter.py
    # Apply filter for unreviewed items (Reviewed == Not)
    if "Reviewed" in filter_dialog.rows:
        filter_dialog.rows["Reviewed"].set_state("Not")
        unreviewed_matched = filter_dialog._compute_matches()
        qt_res["filter_unreviewed_matched_count"] = len(unreviewed_matched)
        qt_res["filter_unreviewed_matched_sample"] = unreviewed_matched[:5]

    # 4. Test Problem Queue in Qt
    prob_dialog = QtProblemQueueDialog(parent=None, app_state=qt_state)
    qt_res["problem_queue_count"] = prob_dialog.queue_ctrl.total_count
    qt_res["problem_queue_sample"] = prob_dialog.queue_ctrl.oid_queue[:5]
    qt_res["problem_queue_cur_oid"] = prob_dialog.queue_ctrl.current_oid
    if hasattr(prob_dialog.dialog, "lbl_field_name"):
        qt_res["problem_queue_field_name"] = prob_dialog.dialog.lbl_field_name.text()
    if hasattr(prob_dialog.dialog, "edit_field_value"):
        qt_res["problem_queue_field_value"] = prob_dialog.dialog.edit_field_value.text()

    # 5. Test Historical Books Resolver in Qt
    test_hist_state = AppState()
    test_hist_state.config = cfg
    test_hist_state.df_reg = df_reg.copy()
    test_hist_state.df_obs = df_obs.copy()
    test_hist_state.df_log = df_log.copy()
    test_hist_state.historical_dbs = historical_dbs
    test_hist_state.current_object_id = "1003"

    hist_dialog = QtHistoricalResolverDialog(parent=None, app_state=test_hist_state, oid="1003")
    qt_res["historical_resolver_discrepancies_count"] = len(hist_dialog.discrepancies)
    qt_res["historical_resolver_discrepancies"] = [
        {"field": d["field"], "current": d["current_val"], "historical": d["historical_val"], "is_different": d["is_different"]}
        for d in hist_dialog.discrepancies
    ]
    # Test accepting historical value for 1003 (Pinuss -> Pinus)
    if hist_dialog.discrepancies:
        cb = hist_dialog.dialog.table_diff.cellWidget(0, 3)
        if cb:
            cb.setCurrentIndex(1) # Accept Book Value
            hist_dialog.apply_resolutions()
            qt_res["historical_resolved_value_in_df"] = test_hist_state.df_reg.loc["1003", "Genus"]

    # 6. Test GBIF Dialog in Qt
    test_gbif_state = AppState()
    test_gbif_state.config = cfg
    test_gbif_state.df_reg = df_reg.copy()
    test_gbif_state.df_obs = df_obs.copy()
    test_gbif_state.df_log = df_log.copy()
    test_gbif_state.current_object_id = "1001"

    gbif_dialog = QtGbifUpdateDialog(parent=None, app_state=test_gbif_state, oid="1001")
    qt_res["gbif_dialog_oid"] = gbif_dialog.dialog.lbl_object_id.text() if hasattr(gbif_dialog.dialog, "lbl_object_id") else "N/A"
    qt_res["gbif_dialog_curr_genus"] = gbif_dialog.dialog.lbl_curr_genus.text() if hasattr(gbif_dialog.dialog, "lbl_curr_genus") else "N/A"

    # 7. Test Bulk Edit in Qt
    test_bulk_state = AppState()
    test_bulk_state.config = cfg
    test_bulk_state.df_reg = df_reg.copy()
    test_bulk_state.df_obs = df_obs.copy()
    test_bulk_state.df_log = df_log.copy()
    bulk_dialog = QtBulkEditDialog(parent=None, app_state=test_bulk_state, selected_oids=["1001", "1002", "1003"])
    qt_res["bulk_edit_target_count"] = len(bulk_dialog.selected_oids)
    qt_res["bulk_edit_fields_populated"] = bulk_dialog.win.combo_field.count() > 0

    print("PySide6 / Qt audit completed.")

# ==============================================================================
# AUDIT 2: TKINTER RUNTIME UNDER LIVE DATA
# ==============================================================================
def audit_tkinter_runtime():
    print("\n=======================================================")
    print("=== EXECUTING AUDIT ON TKINTER WORKSTATION ===")
    print("=======================================================")
    import tkinter as tk
    from ui.main_window import ObjectProgramUI
    from ui.filter_dialog import FilterDialogController
    from ui.object_problem_resolver import ObjectProblemResolver

    root = tk.Tk()
    root.withdraw()

    cfg, df_reg_raw, df_obs_raw, df_reg, df_obs, df_photo, df_log, df_unval, historical_dbs = load_raw_data()

    tk_state = AppState()
    tk_state.config = cfg
    tk_state.config_name = "Økonomisk Botanisk"
    tk_ui = ObjectProgramUI(root, tk_state)
    tk_ui.apply_config()

    # Emulate finish_open_excel
    tk_state.excel_path = MOCK_DB_PATH
    tk_state.output_path = MOCK_DB_PATH
    tk_state.df_reg = df_reg.copy()
    tk_state.df_obs = df_obs.copy()
    tk_state.df_photo = df_photo.copy()
    tk_state.df_log = df_log.copy()
    tk_state.initial_df_obs = df_obs.copy()
    tk_state.df_unvalidated = df_unval.copy()
    tk_state.historical_dbs = historical_dbs
    tk_state.active_object_ids = list(df_reg.index)

    tk_ui.reg_by_id = tk_state.df_reg
    tk_ui.obs_by_id = tk_state.df_obs
    tk_ui.photo_by_id = tk_state.df_photo
    tk_ui.active_object_ids = list(df_reg.index)
    tk_ui.refresh_list()

    tk_res = results["tkinter"]
    tk_res["loaded_records_count"] = len(tk_state.df_reg)
    tk_res["df_reg_index_type"] = str(type(tk_state.df_reg.index))
    tk_res["df_reg_index_sample"] = list(tk_state.df_reg.index[:5])
    tk_res["active_object_ids_sample"] = tk_state.active_object_ids[:5]
    
    # Treeview listbox items
    items = tk_ui.object_list.get(0, min(4, tk_ui.object_list.size()-1)) if hasattr(tk_ui.object_list, "get") else []
    tk_res["tree_items_sample"] = items

    # Splitter geometry
    tk_res["panes_weights"] = [0, 3, 3] # left 0, middle 3, right 3

    # Status Bar
    total = len(tk_state.df_reg)
    reviewed_count = int(tk_state.df_obs["Reviewed"].sum())
    prob_cols = [c for c in tk_state.df_obs.columns if c.endswith("_Problem")]
    prob_count = int(tk_state.df_obs[prob_cols].any(axis=1).sum())
    tk_res["status_objects"] = f"Total: {total}"
    tk_res["status_reviewed"] = f"Reviewed: {reviewed_count} ({int(reviewed_count/total*100)}%)"
    tk_res["status_problems"] = f"Problems: {prob_count}"

    # Load Object 1001
    tk_ui.load_object("1001")
    tk_res["selected_oid"] = tk_state.current_object_id
    tk_res["lbl_specimen_name"] = tk_ui.title_label.cget("text") if hasattr(tk_ui, "title_label") else "N/A"
    tk_res["lbl_id_badge"] = tk_ui.header_id_badge.cget("text") if hasattr(tk_ui, "header_id_badge") else "N/A"
    tk_res["tab_general_inputs_count"] = len(getattr(tk_ui, "reg_entries", {}))
    tk_res["reg_entries_values_1001"] = {
        k: tk_ui.reg_entries[k].get() if hasattr(tk_ui.reg_entries[k], "get") else ""
        for k in ["Genus", "Species", "Author", "Collector", "Collection Place"]
        if k in getattr(tk_ui, "reg_entries", {})
    }

    # Search in Tkinter
    if hasattr(tk_ui, "_inline_search_var"):
        tk_ui._inline_search_var.set("Pinus")
        tk_ui._apply_inline_search()
        tk_res["search_pinus_matched_count"] = len(tk_ui.active_object_ids)
        tk_res["search_pinus_matched_sample"] = tk_ui.active_object_ids[:5]
        tk_ui._inline_search_var.set("")
        tk_ui._apply_inline_search()

    # Historical Resolver suggestions for 1003
    suggestions = tk_ui.collect_historical_suggestions(oid="1003") if hasattr(tk_ui, "collect_historical_suggestions") else {}
    tk_res["historical_suggestions_1003"] = suggestions

    root.destroy()
    print("Tkinter audit completed.")

if __name__ == "__main__":
    audit_qt_runtime()
    audit_tkinter_runtime()
    
    print("\n=======================================================")
    print("=== SIDE-BY-SIDE AUDIT RESULTS COMPARISON ===")
    print("=======================================================")
    import json
    print(json.dumps(results, indent=2, default=str))
