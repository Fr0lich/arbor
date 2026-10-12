"""scratch/test_tkinter_runtime.py
Test script to inspect Tkinter workstation under live mock data load within mainloop.
"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import tkinter as tk
import pandas as pd
import config
config.UI_SCALE = 1.0

from models import AppState
from ui.main_window import ObjectProgramUI

root = tk.Tk()
root.withdraw() # Headless

app_state = AppState()
app_state.config = config.DATABASE_CONFIGS["Økonomisk Botanisk"]
app_state.config_name = "Økonomisk Botanisk"
ui = ObjectProgramUI(root, app_state)
ui.apply_config()

mock_db = os.path.abspath("scratch/mock_current_db.xlsx")
mock_books = os.path.abspath("scratch/mock_historical_books.xlsx")

def run_tests():
    try:
        print("--- Loading Tkinter DB Synchronously ---")
        from repository import ExcelRepository
        df_reg, df_obs, df_photo, df_log, df_unval = ExcelRepository.load_excel(mock_db, app_state.config)
        app_state.excel_path = mock_db
        app_state.df_reg = df_reg
        app_state.df_obs = df_obs
        app_state.df_photo = df_photo
        app_state.df_log = df_log
        app_state.df_unvalidated = df_unval
        app_state.active_object_ids = list(df_reg.index)
        ui.reg_by_id = df_reg
        ui.obs_by_id = df_obs
        ui.active_object_ids = list(df_reg.index)
        ui.refresh_list()
        print(f"Tkinter loaded records: {len(app_state.df_reg)}")
        print(f"Tkinter active_object_ids: {len(app_state.active_object_ids)}")

        # Load Historical Books
        print("--- Loading Tkinter Historical Books ---")
        from repository import _open_excel_reader, _normalize_object_id_series
        with _open_excel_reader(mock_books) as xls:
            loaded = []
            for sheet_name in xls.sheet_names:
                df = pd.read_excel(xls, sheet_name=sheet_name)
                df["ObjectID"] = _normalize_object_id_series(df["ObjectID"])
                loaded.append({"name": f"Books: {sheet_name}", "path": mock_books, "df_reg": df, "reg_by_id": df.set_index("ObjectID")})
        app_state.historical_dbs = loaded
        ui._history_presence_set = {1001, 1002, 1003, 1004, 1005, 1007, 1010, 1012, 1015, 1020, 1021}
        print(f"Tkinter historical_dbs: {len(app_state.historical_dbs)}")

        # Navigation & Load Object 1001
        print("\n--- Navigating to Specimen 1001 ---")
        ui.load_object(1001)
        print(f"Active ID: {app_state.current_object_id}")
        print("Genus:", ui.reg_entries["Genus"]["widget"].get())
        print("Species:", ui.reg_entries["Species"]["widget"].get())
        print("Author:", ui.reg_entries["Author"]["widget"].get())
        print("Collector:", ui.reg_entries["Collector"]["widget"].get())
        print("Reviewed status:", app_state.df_obs.loc[1001, "Reviewed"])

        # Navigation & Load Object 1003 (flawed Genus)
        print("\n--- Navigating to Specimen 1003 (Flawed Genus) ---")
        ui.load_object(1003)
        print(f"Active ID: {app_state.current_object_id}")
        print("Genus:", ui.reg_entries["Genus"]["widget"].get())
        print("Species:", ui.reg_entries["Species"]["widget"].get())
        print("Genus_Problem:", app_state.df_obs.loc[1003, "Genus_Problem"])

        # Status Bar metrics
        print("\n--- Status Bar Metrics in Tkinter ---")
        total = len(app_state.df_reg)
        reviewed_count = int(app_state.df_obs["Reviewed"].sum())
        prob_cols = [c for c in app_state.df_obs.columns if c.endswith("_Problem")]
        prob_count = int(app_state.df_obs[prob_cols].any(axis=1).sum())
        print(f"Total: {total}, Reviewed: {reviewed_count} ({int(reviewed_count/total*100)}%), Problems: {prob_count}")

        # Search Bar
        print("\n--- Testing Live Search in Tkinter ---")
        ui.search_var.set("Pinus")
        ui.filter_list_by_search()
        print(f"Query 'Pinus' -> active_object_ids ({len(ui.active_object_ids)}): {ui.active_object_ids}")

        # Clear search
        ui.search_var.set("")
        ui.filter_list_by_search()
        print(f"Cleared search -> active_object_ids ({len(ui.active_object_ids)})")

        print("\nTkinter tests PASSED cleanly.")
    except Exception as e:
        import traceback
        traceback.print_exc()
    finally:
        root.quit()

root.after(50, run_tests)
root.mainloop()
