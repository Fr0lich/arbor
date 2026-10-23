import tkinter as tk
import time
import sys
import threading
from models import AppState
from ui.main_window import ObjectProgramUI
from repository import ExcelRepository
import pandas as pd

import config

def run_simulation(ui):
    try:
        print("Starting Simulation...")
        ui.root.update()
        time.sleep(1)

        print("Opening database...")
        ui.app.config["sheets"]["reg"] = "Sheet1"
        ui.app.config["sheets"]["obs"] = "Sheet2"
        ui.app.config["sheets"]["photo"] = "Sheet3"
        ui.app.config["sheets"]["log"] = "Sheet4"

        try:
             df_reg, df_obs, df_photo, df_log, _ = ExcelRepository.load_excel("current_inventory.xlsx", ui.app.config)
             ui.app.df_reg = df_reg
             if "Object ID" in df_reg.columns:
                 ui.app.df_reg.set_index("Object ID", inplace=True, drop=False)

             ui.app.df_obs = df_obs
             if "Object ID" in df_obs.columns:
                 ui.app.df_obs.set_index("Object ID", inplace=True, drop=False)
             else:
                 ui.app.df_obs = pd.DataFrame(index=ui.app.df_reg.index)

             ui.app.df_photo = df_photo
             ui.app.df_log = df_log

             ui.app.active_object_ids = list(ui.app.df_reg.index)
             ui.app.db_path = "current_inventory.xlsx"

             ui.refresh_list()

             if hasattr(ui, 'on_db_loaded'):
                 ui.on_db_loaded()

        except Exception as err:
             print("Error loading DB manually:", err)

        ui.root.update()
        time.sleep(2)

        print("Loaded IDs manually:", ui.app.active_object_ids)

        print("Attempting to select object PL002...")
        if hasattr(ui, 'object_list') and hasattr(ui.object_list, 'tree'):
            ui.load_object("PL002")
            ui.root.update()
            time.sleep(1)
            print("Loaded object PL002")
        else:
             print("No object_list")
             return

        print("Fumbling with checkboxes...")
        if hasattr(ui, 'problem_vars') and 'Species_Problem' in ui.problem_vars:
            var = ui.problem_vars['Species_Problem']
            var.set(True)
            if hasattr(ui, '_on_checkbox_change'):
                ui._on_checkbox_change('Species_Problem', var)
        ui.root.update()
        time.sleep(1)

        print("Opening Historical Resolver...")
        # Since Historical Resolver opens a new window, just mock its presence
        print("Historical resolver accessed.")
        ui.root.update()
        time.sleep(1)

        print("Checking GBIF...")
        # Since GBIF makes API calls, just mock its presence
        print("GBIF taxonomy verification accessed.")
        ui.root.update()
        time.sleep(1)

        print("Marking as reviewed...")
        if hasattr(ui, 'reviewed_var'):
             ui.reviewed_var.set(True)
             if hasattr(ui, '_on_reviewed_change'):
                 ui._on_reviewed_change()
        ui.root.update()
        time.sleep(1)

        print("Simulation complete.")

    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"Simulation error: {e}")
    finally:
        # Give the loop some time before quitting
        ui.root.after(1000, ui.root.quit)

def _main():
    import json

    config.DATABASE_CONFIGS["Test DB"] = dict(config.DATABASE_CONFIGS["Økonomisk Botanisk"])
    config.DATABASE_CONFIGS["Test DB"]["active_file"] = "current_inventory.xlsx"
    config.DATABASE_CONFIGS["Test DB"]["historical_file"] = "historical_books.xlsx"
    config.DATABASE_CONFIGS["Test DB"]["sheets"] = {
        "reg": "Sheet1",
        "obs": "Sheet2",
        "photo": "Sheet3",
        "log": "Sheet4",
    }

    with open("arbor_preferences.json", "w") as f:
         json.dump({"custom_databases": {"Test DB": config.DATABASE_CONFIGS["Test DB"]}}, f)

    app = AppState()
    app.config = config.DATABASE_CONFIGS["Test DB"]

    root = tk.Tk()
    root.withdraw()
    ui = ObjectProgramUI(root, app)
    ui.enable_offline_mode()
    ui.apply_config()

    root.deiconify()
    root.geometry("800x600")

    root.after(1000, lambda: run_simulation(ui))

    print("Starting main loop...")
    root.mainloop()
    print("Exited cleanly.")

if __name__ == '__main__':
    _main()
