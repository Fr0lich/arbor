import tkinter as tk
import time
from models import AppState
from ui.main_window import ObjectProgramUI
import ui.widgets
import config

app = AppState()
import pandas as pd
app.df_reg = pd.DataFrame({'Genus': ['A', 'B', 'C', 'D', 'E']}, index=[1, 2, 3, 4, 5])
app.df_obs = pd.DataFrame({'Reviewed': [False, False, False, False, False]}, index=[1, 2, 3, 4, 5])
app.active_object_ids = [1, 2, 3, 4, 5]
app.list_view_mode = "detailed"
app.current_object_id = 1
app.config = list(config.DATABASE_CONFIGS.values())[0]

root = tk.Tk()
ui_inst = ObjectProgramUI(root, app)
ui_inst.reg_by_id = app.df_reg
ui_inst.obs_by_id = app.df_obs
ui_inst.build_ui()
ui_inst.refresh_list()

def test_jump():
    print("Clicking on card 4!")
    # simulate clicking on card 4
    # We call _on_card_click with oid=4
    ui_inst.object_list._on_card_click(4)
    # Wait for the async list_select_job
    root.after(200, check_loaded)

def check_loaded():
    print("Currently loaded object ID is:", app.current_object_id)
    root.destroy()

root.update_idletasks()
root.after(100, test_jump)
root.mainloop()
